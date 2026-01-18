"""V-JEPA 2 World Model Integration — December 2025.

Integrates Meta's V-JEPA 2 video world model capabilities.

V-JEPA 2 Key Features:
- Trained on 1M+ hours of video
- 65-80% success rate on complex robot tasks
- Video understanding for navigation and manipulation
- Self-supervised pre-training without labels

This module provides:
1. V-JEPA 2 video encoder
2. Integration with existing KagamiWorldModel
3. Video prediction in latent space
4. Robot task understanding

References:
- V-JEPA: arxiv.org/abs/2404.08471
- V-JEPA 2: meta.com/ai/research/v-jepa-2
- Original JEPA: LeCun (2022) "A Path Towards Autonomous Machine Intelligence"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class VJEPA2Config:
    """Configuration for V-JEPA 2 integration."""

    # Model selection
    model_name: str = "facebook/vjepa2-vitl"

    # Video processing
    num_frames: int = 16  # Frames per video clip
    frame_size: int = 224  # Frame resolution
    patch_size: int = 16  # ViT patch size
    tubelet_size: int = 2  # Temporal tubelet size

    # Architecture
    embed_dim: int = 1024  # ViT-L dimension
    hidden_dim: int = 2048
    num_heads: int = 16
    num_layers: int = 24
    dropout: float = 0.1

    # Context encoder (target)
    use_context_encoder: bool = True
    context_mask_ratio: float = 0.9  # High mask ratio for prediction

    # Predictor
    predictor_depth: int = 6
    predictor_embed_dim: int = 384

    # Loss weights
    prediction_weight: float = 1.0

    # Device
    device: str | None = None


# ============================================================================
# Video Tokenizer
# ============================================================================


class VideoTokenizer(nn.Module):
    """Tokenize video into spatio-temporal patches (tubelets).

    Input: [B, T, C, H, W]
    Output: [B, N, D] where N = (T/t) * (H/p) * (W/p)
    """

    def __init__(
        self,
        frame_size: int = 224,
        patch_size: int = 16,
        tubelet_size: int = 2,
        in_channels: int = 3,
        embed_dim: int = 1024,
    ):
        super().__init__()
        self.frame_size = frame_size
        self.patch_size = patch_size
        self.tubelet_size = tubelet_size
        self.embed_dim = embed_dim

        # 3D convolution for tubelet embedding
        self.proj = nn.Conv3d(
            in_channels,
            embed_dim,
            kernel_size=(tubelet_size, patch_size, patch_size),
            stride=(tubelet_size, patch_size, patch_size),
        )

        # Calculate number of tokens
        self.num_patches_spatial = (frame_size // patch_size) ** 2

    def forward(self, video: torch.Tensor) -> torch.Tensor:
        """Tokenize video.

        Args:
            video: [B, T, C, H, W]

        Returns:
            tokens: [B, N, D]
        """
        _B, _T, _C, _H, _W = video.shape

        # Rearrange for 3D conv: [B, C, T, H, W]
        x = video.permute(0, 2, 1, 3, 4)

        # Project to tubelets
        x = self.proj(x)  # [B, D, T', H', W']

        # Flatten spatial dimensions
        x = x.flatten(2)  # [B, D, N]
        x = x.transpose(1, 2)  # [B, N, D]

        return x


# ============================================================================
# V-JEPA 2 Encoder
# ============================================================================


class VJEPA2Encoder(nn.Module):
    """V-JEPA 2 video encoder.

    Uses Vision Transformer architecture with:
    - Tubelet embedding for spatio-temporal patches
    - Position embeddings for space and time
    - Transformer encoder blocks
    """

    def __init__(self, config: VJEPA2Config):
        super().__init__()
        self.config = config

        # Video tokenizer
        self.tokenizer = VideoTokenizer(
            frame_size=config.frame_size,
            patch_size=config.patch_size,
            tubelet_size=config.tubelet_size,
            embed_dim=config.embed_dim,
        )

        # CLS token
        self.cls_token = nn.Parameter(torch.zeros(1, 1, config.embed_dim))

        # Position embeddings
        num_time = config.num_frames // config.tubelet_size
        num_space = (config.frame_size // config.patch_size) ** 2
        num_patches = num_time * num_space + 1  # +1 for CLS
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, config.embed_dim))

        # Transformer blocks
        self.blocks = nn.ModuleList(
            [
                TransformerBlock(
                    dim=config.embed_dim,
                    num_heads=config.num_heads,
                    mlp_ratio=4,
                    dropout=config.dropout,
                )
                for _ in range(config.num_layers)
            ]
        )

        self.norm = nn.LayerNorm(config.embed_dim)

        # Initialize
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

    def forward(
        self,
        video: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode video to latent representation.

        Args:
            video: [B, T, C, H, W]
            mask: Optional mask for masked prediction

        Returns:
            encoded: [B, N+1, D] (includes CLS token)
        """
        B = video.shape[0]

        # Tokenize
        x = self.tokenizer(video)  # [B, N, D]

        # Add CLS token
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls_tokens, x], dim=1)

        # Add position embeddings
        x = x + self.pos_embed[:, : x.shape[1]]

        # Apply mask if provided
        if mask is not None:
            # Mask visible tokens (keep CLS)
            x[:, 1:] = x[:, 1:] * mask.unsqueeze(-1)

        # Transformer blocks
        for block in self.blocks:
            x = block(x)

        x = self.norm(x)

        return x


class TransformerBlock(nn.Module):
    """Standard Transformer block with pre-norm."""

    def __init__(
        self,
        dim: int,
        num_heads: int,
        mlp_ratio: int = 4,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(
            dim,
            num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, dim * mlp_ratio),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim * mlp_ratio, dim),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Self-attention with residual
        x_norm = self.norm1(x)
        attn_out, _ = self.attn(x_norm, x_norm, x_norm)
        x = x + attn_out

        # MLP with residual
        x = x + self.mlp(self.norm2(x))

        return x


# ============================================================================
# V-JEPA 2 Predictor
# ============================================================================


class VJEPA2Predictor(nn.Module):
    """V-JEPA 2 predictor for masked prediction.

    Predicts masked tokens from visible tokens in latent space.
    """

    def __init__(self, config: VJEPA2Config):
        super().__init__()
        self.config = config

        # Project from encoder to predictor dimension
        self.in_proj = nn.Linear(config.embed_dim, config.predictor_embed_dim)

        # Mask token for prediction targets
        self.mask_token = nn.Parameter(torch.zeros(1, 1, config.predictor_embed_dim))

        # Predictor transformer
        self.blocks = nn.ModuleList(
            [
                TransformerBlock(
                    dim=config.predictor_embed_dim,
                    num_heads=config.num_heads // 4,  # Smaller predictor
                    dropout=config.dropout,
                )
                for _ in range(config.predictor_depth)
            ]
        )

        self.norm = nn.LayerNorm(config.predictor_embed_dim)

        # Project back to encoder dimension
        self.out_proj = nn.Linear(config.predictor_embed_dim, config.embed_dim)

        nn.init.trunc_normal_(self.mask_token, std=0.02)

    def forward(
        self,
        visible_tokens: torch.Tensor,
        mask_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Predict masked tokens.

        Args:
            visible_tokens: [B, N_vis, D] from encoder
            mask_indices: [B, N_mask] indices to predict

        Returns:
            predictions: [B, N_mask, D]
        """
        B = visible_tokens.shape[0]
        N_mask = mask_indices.shape[1]

        # Project to predictor dimension
        x = self.in_proj(visible_tokens)

        # Add mask tokens for prediction targets
        mask_tokens = self.mask_token.expand(B, N_mask, -1)
        x = torch.cat([x, mask_tokens], dim=1)

        # Predictor transformer
        for block in self.blocks:
            x = block(x)

        x = self.norm(x)

        # Get only mask predictions
        predictions = x[:, -N_mask:]

        # Project back to encoder dimension
        predictions = self.out_proj(predictions)

        return predictions


# ============================================================================
# V-JEPA 2 World Model
# ============================================================================


class VJEPA2WorldModel(nn.Module):
    """V-JEPA 2 integrated world model.

    Combines:
    - Context encoder (target, EMA updated)
    - Predictor encoder (trained)
    - Masked prediction objective

    Can be used standalone or integrated with KagamiWorldModel.
    """

    def __init__(self, config: VJEPA2Config | None = None):
        super().__init__()
        self.config = config or VJEPA2Config()

        # Context encoder (target, updated via EMA)
        self.context_encoder = VJEPA2Encoder(self.config)
        for p in self.context_encoder.parameters():
            p.requires_grad = False

        # Predictor encoder (trained)
        self.predictor_encoder = VJEPA2Encoder(self.config)

        # Predictor head
        self.predictor = VJEPA2Predictor(self.config)

        # EMA decay
        self.ema_decay = 0.996
        self._ema_step = 0

        logger.info(f"✅ VJEPA2WorldModel: {self.config.model_name}")

    @torch.no_grad()
    def update_context_encoder(self) -> None:
        """Update context encoder via EMA."""
        for context_param, predictor_param in zip(
            self.context_encoder.parameters(),
            self.predictor_encoder.parameters(),
            strict=False,
        ):
            context_param.data.mul_(self.ema_decay).add_(
                predictor_param.data, alpha=1 - self.ema_decay
            )
        self._ema_step += 1

    def generate_mask(
        self,
        batch_size: int,
        num_tokens: int,
        mask_ratio: float = 0.9,
        device: torch.device | str = "cpu",
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Generate random mask for prediction.

        Args:
            batch_size: Batch size
            num_tokens: Number of tokens (excluding CLS)
            mask_ratio: Fraction to mask
            device: Device

        Returns:
            visible_mask: [B, N] binary mask (1 = visible)
            mask_indices: [B, N_mask] indices of masked tokens
        """
        num_mask = int(num_tokens * mask_ratio)
        num_visible = num_tokens - num_mask

        # Random permutation per sample
        noise = torch.rand(batch_size, num_tokens, device=device)
        ids_shuffle = torch.argsort(noise, dim=1)

        # Visible and masked indices
        visible_indices = ids_shuffle[:, :num_visible]
        mask_indices = ids_shuffle[:, num_visible:]

        # Binary mask
        visible_mask = torch.zeros(batch_size, num_tokens, device=device)
        visible_mask.scatter_(1, visible_indices, 1)

        return visible_mask, mask_indices

    def forward(
        self,
        video: torch.Tensor,
        mask_ratio: float | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Forward pass with V-JEPA 2 objective.

        Args:
            video: [B, T, C, H, W]
            mask_ratio: Override mask ratio

        Returns:
            loss: Prediction loss
            info: Dict with metrics
        """
        B = video.shape[0]
        mask_ratio = mask_ratio or self.config.context_mask_ratio

        # Get target from context encoder (no grad)
        with torch.no_grad():
            target = self.context_encoder(video)  # [B, N+1, D]
            target = target[:, 1:]  # Remove CLS for prediction

        num_tokens = target.shape[1]

        # Generate mask
        visible_mask, mask_indices = self.generate_mask(B, num_tokens, mask_ratio, video.device)

        # Encode visible tokens
        encoded = self.predictor_encoder(video, visible_mask)
        visible_tokens = encoded[:, 1:]  # Remove CLS

        # Select only visible tokens
        visible_indices = visible_mask.nonzero(as_tuple=True)[1].view(B, -1)
        visible_tokens = torch.gather(
            visible_tokens,
            dim=1,
            index=visible_indices.unsqueeze(-1).expand(-1, -1, visible_tokens.shape[-1]),
        )

        # Predict masked tokens
        predictions = self.predictor(visible_tokens, mask_indices)

        # Get target for masked positions
        target_masked = torch.gather(
            target,
            dim=1,
            index=mask_indices.unsqueeze(-1).expand(-1, -1, target.shape[-1]),
        )

        # Smooth L1 loss (robust to outliers)
        loss = F.smooth_l1_loss(predictions, target_masked)

        # Update context encoder
        if self.training:
            self.update_context_encoder()

        info = {
            "vjepa2_loss": loss.item(),
            "mask_ratio": mask_ratio,
            "num_masked": mask_indices.shape[1],
            "ema_step": self._ema_step,
        }

        return loss, info

    @torch.no_grad()
    def encode_video(self, video: torch.Tensor) -> torch.Tensor:
        """Encode video to latent representation.

        Args:
            video: [B, T, C, H, W]

        Returns:
            encoded: [B, D] global video representation
        """
        # Use context encoder for inference
        encoded = self.context_encoder(video)

        # Return CLS token as global representation
        return encoded[:, 0]

    @torch.no_grad()
    def predict_future(
        self,
        video: torch.Tensor,
        num_future_frames: int = 4,
    ) -> torch.Tensor:
        """Predict future frame representations.

        Args:
            video: [B, T, C, H, W] past video
            num_future_frames: Number of future frames to predict

        Returns:
            future_repr: [B, num_future, D] future representations
        """
        # This is a simplified version - full implementation would
        # predict iteratively in latent space
        current = self.encode_video(video)

        # Simple linear extrapolation (placeholder)
        # Real implementation would use learned dynamics
        future = current.unsqueeze(1).expand(-1, num_future_frames, -1)

        return future


# ============================================================================
# Integration with KagamiWorldModel
# ============================================================================


class VJEPA2KagamiIntegration(nn.Module):
    """Integrate V-JEPA 2 features with KagamiWorldModel.

    Adds video understanding to the existing world model:
    1. Video encoder for temporal context
    2. Fusion with colony RSSM states
    3. Enhanced prediction from video features
    """

    def __init__(
        self,
        kagami_latent_dim: int = 64,
        vjepa2_config: VJEPA2Config | None = None,
    ):
        super().__init__()

        self.vjepa2_config = vjepa2_config or VJEPA2Config()
        self.kagami_latent_dim = kagami_latent_dim

        # V-JEPA 2 world model
        self.vjepa2 = VJEPA2WorldModel(self.vjepa2_config)

        # Fusion layer: V-JEPA 2 features → Kagami latent
        self.fusion = nn.Sequential(
            nn.Linear(self.vjepa2_config.embed_dim, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(512, kagami_latent_dim),
        )

        # Gate for combining with RSSM state
        self.gate = nn.Sequential(
            nn.Linear(kagami_latent_dim * 2, kagami_latent_dim),
            nn.Sigmoid(),
        )

        logger.info(f"✅ VJEPA2KagamiIntegration: video → {kagami_latent_dim}D latent")

    def encode_video_context(self, video: torch.Tensor) -> torch.Tensor:
        """Encode video to Kagami-compatible latent.

        Args:
            video: [B, T, C, H, W]

        Returns:
            context: [B, kagami_latent_dim]
        """
        # Get V-JEPA 2 encoding
        vjepa2_repr = self.vjepa2.encode_video(video)  # [B, embed_dim]

        # Project to Kagami dimension
        context = self.fusion(vjepa2_repr)  # [B, kagami_latent_dim]

        return context

    def fuse_with_rssm(
        self,
        video_context: torch.Tensor,
        rssm_state: torch.Tensor,
    ) -> torch.Tensor:
        """Fuse video context with RSSM state.

        Args:
            video_context: [B, kagami_latent_dim] from V-JEPA 2
            rssm_state: [B, kagami_latent_dim] from Colony RSSM

        Returns:
            fused: [B, kagami_latent_dim]
        """
        # Gated fusion
        combined = torch.cat([video_context, rssm_state], dim=-1)
        gate = self.gate(combined)

        # Weighted combination
        fused = gate * video_context + (1 - gate) * rssm_state

        return fused

    def forward(
        self,
        video: torch.Tensor,
        rssm_state: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Forward pass with optional RSSM fusion.

        Args:
            video: [B, T, C, H, W]
            rssm_state: Optional RSSM state for fusion

        Returns:
            output: Fused representation or video context
            info: Metrics dict[str, Any]
        """
        # Train V-JEPA 2 if in training mode
        if self.training:
            vjepa2_loss, vjepa2_info = self.vjepa2(video)
        else:
            vjepa2_loss = torch.tensor(0.0, device=video.device)
            vjepa2_info = {}

        # Get video context
        video_context = self.encode_video_context(video)

        # Optionally fuse with RSSM
        if rssm_state is not None:
            output = self.fuse_with_rssm(video_context, rssm_state)
            info = {
                **vjepa2_info,
                "fused": True,
            }
        else:
            output = video_context
            info = {
                **vjepa2_info,
                "fused": False,
            }

        # Expose training loss for observability (do not backprop here).
        try:
            info["vjepa2_loss"] = float(vjepa2_loss.detach().item())
        except Exception:
            pass

        info["video_context_norm"] = video_context.norm(dim=-1).mean().item()

        return output, info


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "TransformerBlock",
    "VJEPA2Config",
    "VJEPA2Encoder",
    "VJEPA2KagamiIntegration",
    "VJEPA2Predictor",
    "VJEPA2WorldModel",
    "VideoTokenizer",
]
