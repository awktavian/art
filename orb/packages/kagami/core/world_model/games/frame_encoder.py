"""Game Frame Encoder.

CNN encoder for game observations that maps frames to RSSM-compatible
embeddings. Follows EfficientZero/DreamerV3 architecture patterns.

Architecture:
- Residual blocks for stable deep features
- LayerNorm for training stability
- Configurable for different observation shapes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class EncoderConfig:
    """Configuration for game frame encoder."""

    observation_shape: tuple[int, ...] = (4, 84, 84)  # (C, H, W)
    embed_dim: int = 256  # Output embedding dimension
    depth: int = 4  # Number of residual blocks
    channels: tuple[int, ...] = (32, 64, 128, 256)  # Channel progression
    kernel_sizes: tuple[int, ...] = (8, 4, 3, 3)  # Kernel sizes
    strides: tuple[int, ...] = (4, 2, 1, 1)  # Strides
    use_layer_norm: bool = True  # DreamerV3-style normalization


class ResidualBlock(nn.Module):
    """Residual block with optional LayerNorm."""

    def __init__(
        self,
        channels: int,
        use_layer_norm: bool = True,
    ) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.use_layer_norm = use_layer_norm

        if use_layer_norm:
            self.norm1 = nn.LayerNorm(channels)
            self.norm2 = nn.LayerNorm(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward with residual connection.

        Args:
            x: Input tensor (B, C, H, W)

        Returns:
            Output tensor (B, C, H, W)
        """
        identity = x

        out = self.conv1(x)
        if self.use_layer_norm:
            # LayerNorm on channel dim
            B, C, H, W = out.shape
            out = out.permute(0, 2, 3, 1).reshape(B * H * W, C)
            out = self.norm1(out)
            out = out.reshape(B, H, W, C).permute(0, 3, 1, 2)
        out = F.silu(out)

        out = self.conv2(out)
        if self.use_layer_norm:
            B, C, H, W = out.shape
            out = out.permute(0, 2, 3, 1).reshape(B * H * W, C)
            out = self.norm2(out)
            out = out.reshape(B, H, W, C).permute(0, 3, 1, 2)

        out = out + identity
        out = F.silu(out)

        return out


class GameFrameEncoder(nn.Module):
    """CNN encoder for game frames.

    Maps game observations to embeddings suitable for RSSM input.
    Uses DreamerV3-style architecture with:
    - Strided convolutions for downsampling
    - Residual blocks for feature extraction
    - LayerNorm for stability
    - SiLU activations

    Example:
        encoder = GameFrameEncoder(
            observation_shape=(4, 84, 84),
            embed_dim=256,
        )
        frames = torch.randn(32, 4, 84, 84)  # Batch of stacked frames
        embeddings = encoder(frames)  # (32, 256)
    """

    def __init__(
        self,
        observation_shape: tuple[int, ...] = (4, 84, 84),
        embed_dim: int = 256,
        depth: int = 4,
        channels: tuple[int, ...] = (32, 64, 128, 256),
        kernel_sizes: tuple[int, ...] = (8, 4, 3, 3),
        strides: tuple[int, ...] = (4, 2, 1, 1),
        use_layer_norm: bool = True,
    ) -> None:
        """Initialize frame encoder.

        Args:
            observation_shape: Input shape (C, H, W)
            embed_dim: Output embedding dimension
            depth: Number of residual blocks per stage
            channels: Channel sizes for each stage
            kernel_sizes: Kernel sizes for downsampling convs
            strides: Strides for downsampling convs
            use_layer_norm: Use LayerNorm (DreamerV3 style)
        """
        super().__init__()

        self.observation_shape = observation_shape
        self.embed_dim = embed_dim
        self.use_layer_norm = use_layer_norm

        in_channels = observation_shape[0]
        layers: list[nn.Module] = []

        # Build encoder stages
        for _i, (out_channels, kernel, stride) in enumerate(
            zip(channels, kernel_sizes, strides, strict=False)
        ):
            # Downsampling conv
            layers.append(nn.Conv2d(in_channels, out_channels, kernel, stride, padding=kernel // 2))
            layers.append(nn.SiLU())

            # Residual blocks
            for _ in range(depth // len(channels)):
                layers.append(ResidualBlock(out_channels, use_layer_norm))

            in_channels = out_channels

        self.encoder = nn.Sequential(*layers)

        # Compute output shape
        with torch.no_grad():
            dummy = torch.zeros(1, *observation_shape)
            encoded = self.encoder(dummy)
            self._encoded_shape = encoded.shape[1:]  # (C, H, W)
            flat_dim = encoded.numel()

        # Project to embedding dim
        self.projection = nn.Sequential(
            nn.Flatten(),
            nn.Linear(flat_dim, embed_dim),
            nn.LayerNorm(embed_dim) if use_layer_norm else nn.Identity(),
            nn.SiLU(),
        )

        logger.info(
            f"GameFrameEncoder initialized: {observation_shape} → {embed_dim}, "
            f"encoded_shape={self._encoded_shape}"
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode game frames to embeddings.

        Args:
            x: Input frames (B, C, H, W) or (B, T, C, H, W)

        Returns:
            Embeddings (B, embed_dim) or (B, T, embed_dim)
        """
        # Handle sequence input
        has_time = len(x.shape) == 5
        if has_time:
            B, T, C, H, W = x.shape
            x = x.reshape(B * T, C, H, W)

        # Encode
        encoded = self.encoder(x)
        embeddings = self.projection(encoded)

        if has_time:
            embeddings = embeddings.reshape(B, T, self.embed_dim)

        return embeddings

    @property
    def encoded_shape(self) -> tuple[int, ...]:
        """Get shape after CNN encoding (before projection)."""
        return self._encoded_shape


class GameFrameDecoder(nn.Module):
    """CNN decoder for reconstructing game frames from embeddings.

    Mirrors the encoder architecture for reconstruction loss training.
    """

    def __init__(
        self,
        observation_shape: tuple[int, ...] = (4, 84, 84),
        embed_dim: int = 256,
        channels: tuple[int, ...] = (256, 128, 64, 32),
        use_layer_norm: bool = True,
    ) -> None:
        """Initialize frame decoder.

        Args:
            observation_shape: Target output shape (C, H, W)
            embed_dim: Input embedding dimension
            channels: Channel sizes (reverse of encoder)
            use_layer_norm: Use LayerNorm
        """
        super().__init__()

        self.observation_shape = observation_shape
        self.embed_dim = embed_dim

        # Initial projection
        # Assuming encoder ends at ~6x6 spatial size for 84x84 input
        init_h, init_w = 6, 6
        init_c = channels[0]

        self.init_projection = nn.Sequential(
            nn.Linear(embed_dim, init_c * init_h * init_w),
            nn.LayerNorm(init_c * init_h * init_w) if use_layer_norm else nn.Identity(),
            nn.SiLU(),
        )
        self.init_shape = (init_c, init_h, init_w)

        # Build decoder with transposed convolutions
        layers: list[nn.Module] = []
        in_channels = init_c

        # Upsample stages
        upsample_factors = [2, 2, 2, 2]  # 6 → 12 → 24 → 48 → 96
        for _i, (out_channels, factor) in enumerate(
            zip(channels[1:], upsample_factors[:-1], strict=False)
        ):
            layers.append(
                nn.ConvTranspose2d(in_channels, out_channels, 4, stride=factor, padding=1)
            )
            layers.append(nn.SiLU())
            in_channels = out_channels

        # Final layer to output channels
        layers.append(nn.ConvTranspose2d(in_channels, observation_shape[0], 4, stride=2, padding=1))

        self.decoder = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Decode embeddings to game frames.

        Args:
            x: Embeddings (B, embed_dim) or (B, T, embed_dim)

        Returns:
            Reconstructed frames (B, C, H, W) or (B, T, C, H, W)
        """
        has_time = len(x.shape) == 3
        if has_time:
            B, T, E = x.shape
            x = x.reshape(B * T, E)

        # Project and reshape
        x = self.init_projection(x)
        x = x.reshape(-1, *self.init_shape)

        # Decode
        decoded = self.decoder(x)

        # Crop/pad to exact size
        target_h, target_w = self.observation_shape[1:]
        decoded = F.interpolate(
            decoded, size=(target_h, target_w), mode="bilinear", align_corners=False
        )

        if has_time:
            B_out = decoded.shape[0] // T
            decoded = decoded.reshape(B_out, T, *self.observation_shape)

        return decoded


__all__ = ["EncoderConfig", "GameFrameDecoder", "GameFrameEncoder", "ResidualBlock"]
