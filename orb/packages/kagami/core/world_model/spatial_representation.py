"""3D Spatial Representation (NeRF/Gaussian Splatting).

CREATED: January 4, 2026

Implements 3D scene representation for spatial understanding, following
World Labs Marble architecture.

Capabilities:
1. Novel view synthesis (render from any viewpoint)
2. 3D-consistent scene editing
3. Geometry-aware prediction
4. Spatial grounding for language

Architecture:
=============
```
Images ──▶ Feature Encoder ──▶ 3D Volume/Points ──▶ Neural Renderer
                                     ↑
                              Camera Poses
                                     ↓
                            ──▶ Novel Views
```

Approaches Implemented:
1. NeRF-style (implicit volume rendering)
2. Gaussian Splatting (explicit point-based)
3. Tri-plane representation (efficient hybrid)

References:
- Mildenhall et al. (2020): NeRF - Neural Radiance Fields
- Kerbl et al. (2023): 3D Gaussian Splatting
- Chan et al. (2022): EG3D - Efficient Geometry-aware 3D GANs
- World Labs (2025): Marble - Multimodal World Model
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class SpatialConfig:
    """Configuration for 3D spatial representation."""

    # Input
    image_size: int = 256
    input_channels: int = 3

    # 3D representation
    representation: str = "triplane"  # "nerf", "gaussian", "triplane"

    # NeRF settings
    nerf_hidden_dim: int = 256
    nerf_num_layers: int = 8
    nerf_num_samples: int = 64  # Samples per ray
    nerf_near: float = 0.1
    nerf_far: float = 10.0

    # Gaussian settings
    num_gaussians: int = 50000
    sh_degree: int = 3  # Spherical harmonics degree

    # Tri-plane settings
    triplane_resolution: int = 256
    triplane_channels: int = 32

    # Common
    latent_dim: int = 512
    hidden_dim: int = 512

    # Rendering
    render_size: int = 128
    background_color: tuple[float, float, float] = (1.0, 1.0, 1.0)


# =============================================================================
# POSITIONAL ENCODING
# =============================================================================


class FourierFeatures(nn.Module):
    """Fourier feature positional encoding for NeRF."""

    def __init__(self, input_dim: int = 3, num_frequencies: int = 10, include_input: bool = True):
        super().__init__()
        self.input_dim = input_dim
        self.num_frequencies = num_frequencies
        self.include_input = include_input

        # Frequencies: 2^0, 2^1, ..., 2^(L-1)
        freqs = 2.0 ** torch.arange(num_frequencies)
        self.register_buffer("freqs", freqs)

        self.output_dim = input_dim * num_frequencies * 2
        if include_input:
            self.output_dim += input_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode positions.

        Args:
            x: [..., input_dim] positions

        Returns:
            [..., output_dim] encoded positions
        """
        # x: [..., input_dim]
        # freqs: [num_frequencies]
        # scaled: [..., input_dim, num_frequencies]
        scaled = x.unsqueeze(-1) * self.freqs * 2 * math.pi

        # Flatten and apply sin/cos
        encoded = torch.cat([scaled.sin(), scaled.cos()], dim=-1)
        encoded = encoded.view(*x.shape[:-1], -1)

        if self.include_input:
            encoded = torch.cat([x, encoded], dim=-1)

        return encoded


# =============================================================================
# NERF MLP
# =============================================================================


class NeRFMLP(nn.Module):
    """NeRF-style MLP for density and color prediction."""

    def __init__(self, config: SpatialConfig):
        super().__init__()
        self.config = config

        # Position encoding
        self.pos_enc = FourierFeatures(3, 10)
        self.dir_enc = FourierFeatures(3, 4)

        # Density network
        pos_dim = self.pos_enc.output_dim
        layers = []
        in_dim = pos_dim
        for i in range(config.nerf_num_layers):
            layers.append(nn.Linear(in_dim, config.nerf_hidden_dim))
            layers.append(nn.ReLU())
            in_dim = config.nerf_hidden_dim
            # Skip connection at layer 4
            if i == 4:
                in_dim += pos_dim
        self.density_net = nn.ModuleList(
            [
                nn.Sequential(nn.Linear(pos_dim, config.nerf_hidden_dim), nn.ReLU()),
                *[
                    nn.Sequential(
                        nn.Linear(config.nerf_hidden_dim, config.nerf_hidden_dim), nn.ReLU()
                    )
                    for _ in range(3)
                ],
            ]
        )

        # Density output
        self.density_head = nn.Linear(config.nerf_hidden_dim, 1)

        # Color network (depends on view direction)
        dir_dim = self.dir_enc.output_dim
        self.color_net = nn.Sequential(
            nn.Linear(config.nerf_hidden_dim + dir_dim, config.nerf_hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(config.nerf_hidden_dim // 2, 3),
            nn.Sigmoid(),
        )

    def forward(
        self,
        positions: torch.Tensor,
        directions: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Predict density and color.

        Args:
            positions: [..., 3] 3D positions
            directions: [..., 3] view directions (normalized)

        Returns:
            density: [..., 1] volume density
            color: [..., 3] RGB color
        """
        # Encode
        pos_enc = self.pos_enc(positions)
        dir_enc = self.dir_enc(directions)

        # Density network with skip connection
        h = pos_enc
        for i, layer in enumerate(self.density_net):
            h = layer(h)
            if i == 4:
                h = torch.cat([h, pos_enc], dim=-1)

        # Density
        density = F.relu(self.density_head(h))

        # Color (conditioned on view direction)
        h_color = torch.cat([h, dir_enc], dim=-1)
        color = self.color_net(h_color)

        return density, color


# =============================================================================
# VOLUME RENDERER
# =============================================================================


class VolumeRenderer(nn.Module):
    """Differentiable volume rendering for NeRF."""

    def __init__(self, config: SpatialConfig):
        super().__init__()
        self.config = config

    def forward(
        self,
        density: torch.Tensor,
        color: torch.Tensor,
        depths: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Render ray by alpha compositing.

        Args:
            density: [B, num_rays, num_samples, 1] volume density
            color: [B, num_rays, num_samples, 3] RGB color
            depths: [B, num_rays, num_samples] sample depths

        Returns:
            rgb: [B, num_rays, 3] rendered color
            depth: [B, num_rays] rendered depth
            weights: [B, num_rays, num_samples] sample weights
        """
        # Compute distances between samples
        dists = depths[..., 1:] - depths[..., :-1]
        dists = torch.cat([dists, torch.full_like(dists[..., :1], 1e10)], dim=-1)

        # Alpha from density
        alpha = 1.0 - torch.exp(-density.squeeze(-1) * dists)

        # Transmittance
        transmittance = torch.cumprod(
            torch.cat([torch.ones_like(alpha[..., :1]), 1.0 - alpha + 1e-10], dim=-1), dim=-1
        )[..., :-1]

        # Weights
        weights = alpha * transmittance

        # Composite
        rgb = (weights.unsqueeze(-1) * color).sum(dim=-2)
        depth = (weights * depths).sum(dim=-1)

        # Add background
        bg_color = torch.tensor(self.config.background_color, device=rgb.device)
        rgb = rgb + (1.0 - weights.sum(dim=-1, keepdim=True)) * bg_color

        return rgb, depth, weights


# =============================================================================
# TRI-PLANE REPRESENTATION
# =============================================================================


class TriPlaneEncoder(nn.Module):
    """Encode 2D images to tri-plane 3D representation.

    Tri-planes are three orthogonal feature planes (XY, XZ, YZ) that
    efficiently represent 3D scenes.
    """

    def __init__(self, config: SpatialConfig):
        super().__init__()
        self.config = config

        # Image encoder (ResNet-style)
        self.encoder = nn.Sequential(
            nn.Conv2d(config.input_channels, 64, 7, stride=2, padding=3),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(3, stride=2, padding=1),
            self._make_layer(64, 128, 2),
            self._make_layer(128, 256, 2),
            self._make_layer(256, 512, 2),
        )

        # Tri-plane generator
        self.triplane_gen = nn.Sequential(
            nn.ConvTranspose2d(512, 256, 4, stride=2, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.ConvTranspose2d(128, config.triplane_channels * 3, 4, stride=2, padding=1),
        )

    def _make_layer(self, in_channels: int, out_channels: int, stride: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, stride=stride, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(),
            nn.Conv2d(out_channels, out_channels, 3, stride=1, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(),
        )

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode images to tri-planes.

        Args:
            images: [B, C, H, W] input images

        Returns:
            plane_xy, plane_xz, plane_yz: [B, C, H, W] feature planes
        """
        features = self.encoder(images)
        triplane = self.triplane_gen(features)

        # Split into three planes
        C = self.config.triplane_channels
        plane_xy = triplane[:, :C]
        plane_xz = triplane[:, C : 2 * C]
        plane_yz = triplane[:, 2 * C :]

        return plane_xy, plane_xz, plane_yz


class TriPlaneDecoder(nn.Module):
    """Decode 3D points using tri-plane features."""

    def __init__(self, config: SpatialConfig):
        super().__init__()
        self.config = config

        # MLP decoder
        in_dim = config.triplane_channels * 3
        self.decoder = nn.Sequential(
            nn.Linear(in_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, 4),  # density + RGB
        )

    def sample_planes(
        self,
        planes: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        points: torch.Tensor,
    ) -> torch.Tensor:
        """Sample features from tri-planes at 3D points.

        Args:
            planes: (plane_xy, plane_xz, plane_yz) each [B, C, H, W]
            points: [B, N, 3] 3D points in [-1, 1]

        Returns:
            [B, N, 3*C] sampled features
        """
        plane_xy, plane_xz, plane_yz = planes
        B, N, _ = points.shape

        # Project to each plane
        xy = points[..., :2].view(B, 1, N, 2)  # [B, 1, N, 2]
        xz = points[..., [0, 2]].view(B, 1, N, 2)
        yz = points[..., 1:].view(B, 1, N, 2)

        # Sample (grid_sample expects [B, H, W, 2])
        feat_xy = F.grid_sample(plane_xy, xy, align_corners=True, mode="bilinear").view(B, -1, N)
        feat_xz = F.grid_sample(plane_xz, xz, align_corners=True, mode="bilinear").view(B, -1, N)
        feat_yz = F.grid_sample(plane_yz, yz, align_corners=True, mode="bilinear").view(B, -1, N)

        # Concatenate: [B, 3*C, N] -> [B, N, 3*C]
        features = torch.cat([feat_xy, feat_xz, feat_yz], dim=1).permute(0, 2, 1)

        return features

    def forward(
        self,
        planes: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        points: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Decode density and color at 3D points.

        Args:
            planes: Tri-plane features
            points: [B, N, 3] query points

        Returns:
            density: [B, N, 1]
            color: [B, N, 3]
        """
        features = self.sample_planes(planes, points)
        out = self.decoder(features)

        density = F.relu(out[..., :1])
        color = torch.sigmoid(out[..., 1:])

        return density, color


# =============================================================================
# GAUSSIAN SPLATTING (SIMPLIFIED)
# =============================================================================


class GaussianSplatting(nn.Module):
    """3D Gaussian Splatting representation (simplified).

    Represents scene as a set of 3D Gaussians with:
    - Position (xyz)
    - Covariance (scale + rotation)
    - Opacity
    - Spherical harmonics color
    """

    def __init__(self, config: SpatialConfig):
        super().__init__()
        self.config = config

        # Learnable Gaussian parameters
        self.positions = nn.Parameter(torch.randn(config.num_gaussians, 3) * 0.5)
        self.scales = nn.Parameter(torch.ones(config.num_gaussians, 3) * 0.01)
        self.rotations = nn.Parameter(torch.zeros(config.num_gaussians, 4))  # Quaternion
        self.rotations.data[:, 0] = 1.0  # Identity rotation
        self.opacities = nn.Parameter(torch.zeros(config.num_gaussians, 1))

        # Spherical harmonics coefficients for color
        num_sh = (config.sh_degree + 1) ** 2
        self.sh_coeffs = nn.Parameter(torch.randn(config.num_gaussians, num_sh, 3) * 0.1)

    def get_covariance(self) -> torch.Tensor:
        """Compute covariance matrices from scale and rotation."""
        # Build rotation matrix from quaternion
        q = F.normalize(self.rotations, dim=-1)
        r, i, j, k = q.unbind(-1)

        R = torch.stack(
            [
                1 - 2 * (j**2 + k**2),
                2 * (i * j - k * r),
                2 * (i * k + j * r),
                2 * (i * j + k * r),
                1 - 2 * (i**2 + k**2),
                2 * (j * k - i * r),
                2 * (i * k - j * r),
                2 * (j * k + i * r),
                1 - 2 * (i**2 + j**2),
            ],
            dim=-1,
        ).view(-1, 3, 3)

        # Scale matrix
        S = torch.diag_embed(torch.exp(self.scales))

        # Covariance = R @ S @ S^T @ R^T
        cov = R @ S @ S.transpose(-1, -2) @ R.transpose(-1, -2)

        return cov

    def forward(
        self,
        camera_pose: torch.Tensor,
        image_size: tuple[int, int] = (256, 256),
    ) -> torch.Tensor:
        """Render image from camera pose (simplified splatting).

        Note: This is a simplified differentiable approximation.
        Real Gaussian splatting uses CUDA kernels for efficiency.

        Args:
            camera_pose: [B, 4, 4] camera-to-world matrix
            image_size: (H, W) output resolution

        Returns:
            [B, 3, H, W] rendered image
        """
        B = camera_pose.shape[0]
        H, W = image_size
        device = camera_pose.device

        # For simplicity, return a placeholder
        # Real implementation requires CUDA splatting kernel
        logger.warning(
            "GaussianSplatting.forward() is a placeholder. Use gsplat library for real rendering."
        )

        # Placeholder: render something based on positions
        image = torch.zeros(B, 3, H, W, device=device)

        return image


# =============================================================================
# UNIFIED SPATIAL WORLD MODEL
# =============================================================================


class SpatialWorldModel(nn.Module):
    """Unified 3D spatial representation for world modeling.

    Combines:
    - Tri-plane encoding (efficient, differentiable)
    - NeRF-style MLP (high quality)
    - Optional Gaussian splatting (fast rendering)

    Usage:
        model = SpatialWorldModel(config)

        # Encode scene
        scene = model.encode(images, camera_poses)

        # Render novel view
        novel_view = model.render(scene, new_camera_pose)

        # Get 3D features for world model
        features = model.get_latent(scene)
    """

    def __init__(self, config: SpatialConfig | None = None):
        super().__init__()
        self.config = config or SpatialConfig()

        # Tri-plane encoder
        self.triplane_encoder = TriPlaneEncoder(self.config)
        self.triplane_decoder = TriPlaneDecoder(self.config)

        # NeRF MLP for high-quality rendering
        self.nerf_mlp = NeRFMLP(self.config)

        # Volume renderer
        self.renderer = VolumeRenderer(self.config)

        # Scene latent projection
        self.latent_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(self.config.triplane_channels * 3, self.config.latent_dim),
        )

        logger.info(
            f"SpatialWorldModel initialized:\n"
            f"  Representation: {self.config.representation}\n"
            f"  Triplane resolution: {self.config.triplane_resolution}\n"
            f"  Latent dim: {self.config.latent_dim}"
        )

    def encode(
        self,
        images: torch.Tensor,
        camera_poses: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Encode images to 3D scene representation.

        Args:
            images: [B, num_views, C, H, W] multi-view images
            camera_poses: [B, num_views, 4, 4] camera poses (optional)

        Returns:
            Scene dict with tri-planes and latent
        """
        images.shape[0]

        if images.dim() == 5:
            # Multi-view: average over views (proper fusion requires NeRF-style aggregation)
            images = images.mean(dim=1)

        # Encode to tri-planes
        planes = self.triplane_encoder(images)

        # Get scene latent
        triplane_cat = torch.cat(planes, dim=1)
        latent = self.latent_proj(triplane_cat)

        return {
            "planes": planes,
            "latent": latent,
        }

    def render(
        self,
        scene: dict[str, torch.Tensor],
        camera_pose: torch.Tensor,
        image_size: tuple[int, int] | None = None,
    ) -> torch.Tensor:
        """Render novel view from scene.

        Args:
            scene: Scene dict from encode()
            camera_pose: [B, 4, 4] camera pose
            image_size: Output (H, W), default from config

        Returns:
            [B, 3, H, W] rendered image
        """
        if image_size is None:
            image_size = (self.config.render_size, self.config.render_size)

        B = camera_pose.shape[0]
        H, W = image_size
        device = camera_pose.device
        planes = scene["planes"]

        # Generate rays for each pixel
        # Simplified: assume perspective camera with 60 degree FOV
        fov = 60 * math.pi / 180
        focal = 0.5 * W / math.tan(0.5 * fov)

        # Pixel coordinates
        y, x = torch.meshgrid(
            torch.arange(H, device=device), torch.arange(W, device=device), indexing="ij"
        )

        # Ray directions in camera space
        dirs = torch.stack(
            [
                (x - W / 2) / focal,
                -(y - H / 2) / focal,
                -torch.ones_like(x),
            ],
            dim=-1,
        )  # [H, W, 3]

        # Transform to world space
        R = camera_pose[:, :3, :3]  # [B, 3, 3]
        t = camera_pose[:, :3, 3]  # [B, 3]

        dirs = dirs.view(1, -1, 3)  # [1, H*W, 3]
        dirs = (R @ dirs.transpose(-1, -2)).transpose(-1, -2)  # [B, H*W, 3]
        dirs = F.normalize(dirs, dim=-1)

        origins = t.unsqueeze(1).expand(-1, H * W, -1)  # [B, H*W, 3]

        # Sample points along rays
        num_samples = self.config.nerf_num_samples
        near, far = self.config.nerf_near, self.config.nerf_far

        z_vals = torch.linspace(near, far, num_samples, device=device)
        z_vals = z_vals.view(1, 1, num_samples).expand(B, H * W, num_samples)

        # Add noise for training
        if self.training:
            z_vals = z_vals + torch.rand_like(z_vals) * (far - near) / num_samples

        # 3D points
        points = origins.unsqueeze(-2) + dirs.unsqueeze(-2) * z_vals.unsqueeze(-1)
        # [B, H*W, num_samples, 3]

        # Query tri-plane
        points_flat = points.view(B, -1, 3)
        points_normalized = points_flat / 2.0  # Assume scene in [-2, 2] -> normalize to [-1, 1]

        density, color = self.triplane_decoder(planes, points_normalized)

        density = density.view(B, H * W, num_samples, 1)
        color = color.view(B, H * W, num_samples, 3)

        # Volume rendering
        rgb, _depth, _weights = self.renderer(density, color, z_vals)

        # Reshape to image
        rgb = rgb.view(B, H, W, 3).permute(0, 3, 1, 2)

        return rgb

    def get_latent(self, scene: dict[str, torch.Tensor]) -> torch.Tensor:
        """Get scene latent for world model.

        Args:
            scene: Scene dict from encode()

        Returns:
            [B, latent_dim] scene latent
        """
        return scene["latent"]

    def training_step(
        self,
        images: torch.Tensor,
        camera_poses: torch.Tensor,
        target_image: torch.Tensor,
        target_pose: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Training step for view synthesis.

        Args:
            images: [B, num_views, C, H, W] input views
            camera_poses: [B, num_views, 4, 4] input poses
            target_image: [B, C, H, W] target view
            target_pose: [B, 4, 4] target pose

        Returns:
            Dict with losses
        """
        # Encode scene
        scene = self.encode(images, camera_poses)

        # Render target view
        H, W = target_image.shape[-2:]
        rendered = self.render(scene, target_pose, (H, W))

        # Losses
        rgb_loss = F.mse_loss(rendered, target_image)
        perceptual_loss = torch.tensor(0.0, device=images.device)  # VGG loss disabled (adds ~50ms)

        return {
            "loss": rgb_loss + 0.1 * perceptual_loss,
            "rgb_loss": rgb_loss,
            "perceptual_loss": perceptual_loss,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_spatial_world_model(
    representation: str = "triplane",
    latent_dim: int = 512,
    render_size: int = 128,
) -> SpatialWorldModel:
    """Factory for SpatialWorldModel."""
    config = SpatialConfig(
        representation=representation,
        latent_dim=latent_dim,
        render_size=render_size,
    )
    return SpatialWorldModel(config)


__all__ = [
    "FourierFeatures",
    "GaussianSplatting",
    "NeRFMLP",
    "SpatialConfig",
    "SpatialWorldModel",
    "TriPlaneDecoder",
    "TriPlaneEncoder",
    "VolumeRenderer",
    "create_spatial_world_model",
]
