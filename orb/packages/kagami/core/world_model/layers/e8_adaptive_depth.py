"""Adaptive E8 Depth Selection - VRVQ-inspired variable bitrate quantization.

REFERENCE:
==========
Wang et al. (2025). "VRVQ: Variable-Rate Residual Vector Quantization for
Neural Compression." NeurIPS 2025.

ARCHITECTURE:
=============
Traditional E8 residual quantization uses fixed depth (L levels). This module
implements adaptive depth selection per latent frame, allowing the model to
allocate more bits to complex frames and fewer to simple frames.

Components:
1. E8ImportancePredictor - Conv1D network that predicts importance scores p ∈ (0,1)^T
2. ImportanceToMask (I2M) - Converts importance to binary masks via Heaviside
3. AdaptiveE8Quantizer - Wraps ResidualE8LatticeVQ with adaptive depth

IMPORTANCE NETWORK (E_p):
=========================
Five Conv1D blocks: [1024→512→128→32→8→1]
- Weight normalization (RMSNorm equivalent)
- Snake activation (smooth periodic activation)
- Final sigmoid → p ∈ (0,1)

IMPORTANCE-TO-MASK (I2M):
=========================
Binary mask per level k:
    m[t,k] = H^k(S(p[t]))

where:
    S(p) = N_q · p        (scaling to [0, N_q])
    H^k = Heaviside step  (1 if s > k, else 0)

Smooth approximation for gradients:
    f_α^k(s) = (1/2α)log(cosh(α(s-k))/cosh(α(-s+k+1))) + 1/2

Straight-through estimator:
    p[t] ↦ I2M_soft^α(p[t]) + sg(I2M(p[t]) - I2M_soft^α(p[t]))

RATE LOSS:
==========
    ℒ_R = (1/T)∑ᵗ E_p(E₁(x))[t]

Total loss: ℒ_D + β·ℒ_R  (β=2 recommended)

INTEGRATION:
============
Replace fixed-depth calls to ResidualE8LatticeVQ with AdaptiveE8Quantizer:

    # Old:
    quantized, codes = residual_e8(x, num_levels=8)

    # New:
    quantized, codes, info = adaptive_e8(x, features=encoder_features)
    rate_loss = info["rate_loss"]
    total_loss = reconstruction_loss + beta * rate_loss

Created: December 14, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.e8_lattice_protocol import (
    E8LatticeResidualConfig,
    ResidualE8LatticeVQ,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class E8AdaptiveConfig:
    """Configuration for adaptive E8 depth selection."""

    # E8 quantizer settings
    max_levels: int = 16
    min_levels: int = 1

    # Importance predictor network
    importance_channels: list[int] | None = None  # [1024, 512, 128, 32, 8, 1]
    importance_kernels: list[int] | None = None  # [5, 3, 3, 3, 1]
    importance_input_dim: int = 1024  # Expected encoder feature dimension

    # I2M smooth approximation
    alpha: float = 10.0  # Smoothness parameter (higher = sharper)

    # Rate loss weight
    beta: float = 2.0

    # Training
    use_straight_through: bool = True  # STE for discrete masks

    def __post_init__(self) -> None:
        """Set default channel/kernel configs if not provided."""
        if self.importance_channels is None:
            # Default VRVQ architecture, but starting with importance_input_dim
            self.importance_channels = [self.importance_input_dim, 512, 128, 32, 8, 1]
        else:
            # If custom channels provided, ensure first channel matches input dim
            if self.importance_channels[0] != self.importance_input_dim:
                raise ValueError(
                    f"importance_channels[0] ({self.importance_channels[0]}) must match "
                    f"importance_input_dim ({self.importance_input_dim})"
                )

        if self.importance_kernels is None:
            self.importance_kernels = [5, 3, 3, 3, 1]

        # Validate
        if len(self.importance_kernels) != len(self.importance_channels) - 1:
            raise ValueError(
                f"Need {len(self.importance_channels) - 1} kernels for "
                f"{len(self.importance_channels)} channels"
            )


# =============================================================================
# SNAKE ACTIVATION
# =============================================================================


class Snake(nn.Module):
    """Snake activation: smooth periodic activation function.

    Reference: Liu et al. (2020) "Activation Functions for Deep Learning".

    Snake(x) = x + (1/a)·sin²(a·x)

    Properties:
    - Smooth and continuously differentiable
    - Periodic component helps with temporal patterns
    - Used in VRVQ importance predictor
    """

    def __init__(self, frequency: float = 1.0):
        super().__init__()
        self.frequency = nn.Parameter(torch.tensor(frequency))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + (1.0 / self.frequency) * torch.sin(self.frequency * x).pow(2)


# =============================================================================
# IMPORTANCE PREDICTOR
# =============================================================================


class E8ImportancePredictor(nn.Module):
    """Importance map network E_p: predicts per-frame importance scores.

    Architecture (VRVQ-inspired):
    - Five Conv1D blocks with decreasing channels
    - Weight norm + Snake activation
    - Final sigmoid → p ∈ (0,1)^T

    Input: [..., T, C] encoder features
    Output: [..., T] importance scores p ∈ (0,1)
    """

    def __init__(self, config: E8AdaptiveConfig):
        super().__init__()
        self.config = config

        channels = config.importance_channels
        kernels = config.importance_kernels

        # Build conv blocks
        blocks = []
        for i in range(len(kernels)):  # type: ignore[arg-type]
            in_c = channels[i]  # type: ignore[index]
            out_c = channels[i + 1]  # type: ignore[index]
            k = kernels[i]  # type: ignore[index]

            conv = nn.Conv1d(
                in_c,
                out_c,
                kernel_size=k,
                padding=k // 2,  # Same padding
            )
            # Weight normalization (stabilizes training)
            conv = nn.utils.weight_norm(conv)

            blocks.append(conv)
            if i < len(kernels) - 1:  # type: ignore[arg-type]
                # Snake activation for all but last layer
                blocks.append(Snake())  # type: ignore[arg-type]

        self.network = nn.Sequential(*blocks)
        self.sigmoid = nn.Sigmoid()

        logger.debug(f"E8ImportancePredictor: {channels[0]}→{channels[-1]}, kernels={kernels}")  # type: ignore[index]

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Predict importance scores.

        Args:
            features: [..., T, C] encoder features

        Returns:
            importance: [..., T] scores p ∈ (0,1)
        """
        # Conv1D expects [B, C, T]
        original_shape = features.shape
        if features.dim() < 3:
            raise ValueError(f"Expected [..., T, C], got shape {original_shape}")

        # Flatten batch dimensions
        features = features.view(-1, original_shape[-2], original_shape[-1])
        features = features.transpose(-2, -1)  # [B, C, T]

        # Network forward
        logits = self.network(features)  # [B, 1, T]
        logits = logits.squeeze(1)  # [B, T]
        importance = self.sigmoid(logits)

        # Restore shape
        importance = importance.view(*original_shape[:-2], -1)  # [..., T]

        return importance


# =============================================================================
# IMPORTANCE-TO-MASK (I2M)
# =============================================================================


class ImportanceToMask(nn.Module):
    """Converts importance scores to binary masks via Heaviside steps.

    For each level k ∈ [0, N_q):
        m[t,k] = H^k(S(p[t]))

    where:
        S(p) = N_q · p        (scale to [0, N_q])
        H^k(s) = 1 if s > k else 0

    Training: Use smooth approximation f_α^k(s) for gradients
    Inference: Use hard Heaviside steps
    """

    def __init__(self, config: E8AdaptiveConfig):
        super().__init__()
        self.config = config
        self.alpha = config.alpha
        self.num_levels = config.max_levels

    def heaviside(self, s: torch.Tensor, k: int) -> torch.Tensor:
        """Hard Heaviside: H^k(s) = 1 if s > k else 0."""
        return (s > k).float()

    def smooth_heaviside(self, s: torch.Tensor, k: int) -> torch.Tensor:
        """Smooth approximation for gradients.

        f_α^k(s) = (1/2α)log(cosh(α(s-k))/cosh(α(-s+k+1))) + 1/2

        This is a smooth sigmoid-like function that:
        - Approaches 1 when s >> k
        - Approaches 0 when s << k
        - Has controllable sharpness via α
        """
        alpha = self.alpha

        # Numerically stable implementation
        # log(cosh(x)) = log((exp(x) + exp(-x))/2) = x + log(1 + exp(-2x)) - log(2)
        # But PyTorch has F.softplus(x) = log(1 + exp(x)), so:
        # log(cosh(x)) = x + log(1 + exp(-2x)) - log(2)
        #              = x + softplus(-2x) - log(2)

        # For numerical stability, use the identity:
        # log(cosh(x)) = |x| + log(1 + exp(-2|x|)) - log(2)

        x1 = alpha * (s - k)
        x2 = alpha * (-s + k + 1)

        log_cosh_x1 = torch.abs(x1) + F.softplus(-2 * torch.abs(x1)) - torch.log(torch.tensor(2.0))
        log_cosh_x2 = torch.abs(x2) + F.softplus(-2 * torch.abs(x2)) - torch.log(torch.tensor(2.0))

        return (log_cosh_x1 - log_cosh_x2) / (2 * alpha) + 0.5

    def forward(
        self,
        importance: torch.Tensor,
        mode: Literal["hard", "soft", "ste"] = "ste",
    ) -> torch.Tensor:
        """Convert importance to masks.

        Args:
            importance: [..., T] importance scores p ∈ (0,1)
            mode: "hard" (Heaviside), "soft" (smooth), "ste" (straight-through)

        Returns:
            masks: [..., T, N_q] binary masks (or soft approximations)
        """
        # Scale importance to [0, N_q]
        s = importance * self.num_levels  # [..., T]

        # Compute masks for each level
        masks_list = []
        for k in range(self.num_levels):
            if mode == "soft":
                m_k = self.smooth_heaviside(s, k)
            elif mode == "hard":
                m_k = self.heaviside(s, k)
            elif mode == "ste":
                # Straight-through: hard forward, soft backward
                m_soft = self.smooth_heaviside(s, k)
                m_hard = self.heaviside(s, k)
                m_k = m_soft + (m_hard - m_soft).detach()
            else:
                raise ValueError(f"Unknown mode: {mode}")

            masks_list.append(m_k)

        masks = torch.stack(masks_list, dim=-1)  # [..., T, N_q]
        return masks


# =============================================================================
# ADAPTIVE E8 QUANTIZER
# =============================================================================


class AdaptiveE8Quantizer(nn.Module):
    """Adaptive E8 quantizer with learned importance-based depth selection.

    Wraps ResidualE8LatticeVQ with an importance predictor that determines
    how many levels to use for each temporal frame.

    Training: Uses smooth I2M + STE for gradients
    Inference: Uses hard I2M for discrete masks
    """

    def __init__(
        self,
        config: E8AdaptiveConfig | None = None,
        e8_config: E8LatticeResidualConfig | None = None,
    ):
        super().__init__()
        self.config = config or E8AdaptiveConfig()

        # Build E8 quantizer
        if e8_config is None:
            e8_config = E8LatticeResidualConfig(
                max_levels=self.config.max_levels,
                min_levels=self.config.min_levels,
            )
        self.e8_quantizer = ResidualE8LatticeVQ(e8_config)

        # Build importance predictor
        self.importance_predictor = E8ImportancePredictor(self.config)

        # Build I2M
        self.i2m = ImportanceToMask(self.config)

        logger.info(
            f"AdaptiveE8Quantizer: {self.config.min_levels}-{self.config.max_levels} "
            f"levels, alpha={self.config.alpha}, beta={self.config.beta}"
        )

    def forward(
        self,
        x: torch.Tensor,
        features: torch.Tensor | None = None,
        return_info: bool = True,
    ) -> tuple[torch.Tensor, list[torch.Tensor], dict[str, Any] | None]:
        """Adaptive quantization with learned depth selection.

        Args:
            x: [..., T, 8] continuous E8 latents to quantize
            features: [..., T, C] encoder features for importance prediction
                     If None, uses x itself (assumes x has enough dimensions)
            return_info: Return auxiliary information (importance, masks, losses)

        Returns:
            quantized: [..., T, 8] quantized E8 latents
            codes: List of [..., T, 8] int64 lattice codes per level
            info: Dict with importance, masks, rate_loss, etc. (if return_info=True)
        """
        if x.shape[-1] != 8:
            raise ValueError(f"Expected [..., T, 8], got shape {x.shape}")

        # Use features for importance prediction, or x itself
        if features is None:
            if x.shape[-2] < 2:
                # Need temporal dimension - add it
                features = x.unsqueeze(-2)  # [..., 1, 8]
            else:
                features = x

        # Predict importance scores
        importance = self.importance_predictor(features)  # [..., T]

        # Convert to masks
        mode = "ste" if (self.training and self.config.use_straight_through) else "hard"
        masks = self.i2m(importance, mode=mode)  # [..., T, N_q]

        # Quantize with variable depth per frame
        # For now, use average mask across temporal dimension to determine num_levels
        # More sophisticated: per-frame quantization (future work)
        avg_mask = masks.mean(dim=-2)  # [..., N_q]
        num_levels_float = avg_mask.sum(dim=-1).mean()  # scalar
        num_levels = int(
            torch.clamp(
                torch.round(num_levels_float),
                min=self.config.min_levels,
                max=self.config.max_levels,
            ).item()
        )

        # Quantize
        original_shape = x.shape
        x_flat = x.view(-1, 8)
        vq_result = self.e8_quantizer(x_flat, num_levels=num_levels)
        # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
        quantized_flat = vq_result["quantized"]
        codes_tensor = vq_result["indices"]  # [N, L, 8] where L = num_levels
        codes = [codes_tensor[:, i, :] for i in range(codes_tensor.shape[1])]
        quantized = quantized_flat.view(original_shape)

        # Reshape codes to match original shape
        codes = [c.view(*original_shape[:-1], 8) for c in codes]

        # Compute rate loss: ℒ_R = (1/T)∑ᵗ p[t]
        # This encourages sparsity in importance scores
        rate_loss = importance.mean()

        info = None
        if return_info:
            info = {
                "importance": importance,  # [..., T]
                "masks": masks,  # [..., T, N_q]
                "num_levels": num_levels,
                "num_levels_float": num_levels_float,
                "rate_loss": rate_loss,
                "avg_importance": importance.mean(),
                "std_importance": importance.std(),
            }

        return quantized, codes, info

    def decode(self, codes: list[torch.Tensor]) -> torch.Tensor:
        """Decode E8 codes to continuous latents.

        Args:
            codes: List of [..., T, 8] int64 lattice codes

        Returns:
            [..., T, 8] decoded E8 latents
        """
        return self.e8_quantizer.decode(codes)

    def compute_total_loss(
        self,
        reconstruction_loss: torch.Tensor,
        rate_loss: torch.Tensor,
    ) -> torch.Tensor:
        """Compute total loss: ℒ_D + β·ℒ_R.

        Args:
            reconstruction_loss: Distortion loss (MSE, etc.)
            rate_loss: Rate loss from forward()

        Returns:
            Total loss
        """
        return reconstruction_loss + self.config.beta * rate_loss


# =============================================================================
# FACTORY
# =============================================================================


def create_adaptive_e8_quantizer(
    max_levels: int = 16,
    min_levels: int = 1,
    importance_input_dim: int = 1024,
    alpha: float = 10.0,
    beta: float = 2.0,
) -> AdaptiveE8Quantizer:
    """Factory for creating adaptive E8 quantizer.

    Args:
        max_levels: Maximum quantization levels
        min_levels: Minimum quantization levels
        importance_input_dim: Encoder feature dimension
        alpha: Smoothness parameter for I2M
        beta: Rate loss weight

    Returns:
        Configured AdaptiveE8Quantizer

    Example:
        >>> quantizer = create_adaptive_e8_quantizer(
        ...     max_levels=16,
        ...     importance_input_dim=512,
        ...     beta=2.0,
        ... )
        >>> quantized, codes, info = quantizer(latents, encoder_features)
        >>> loss = quantizer.compute_total_loss(recon_loss, info["rate_loss"])
    """
    config = E8AdaptiveConfig(
        max_levels=max_levels,
        min_levels=min_levels,
        importance_input_dim=importance_input_dim,
        alpha=alpha,
        beta=beta,
    )
    return AdaptiveE8Quantizer(config)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "AdaptiveE8Quantizer",
    "E8AdaptiveConfig",
    "E8ImportancePredictor",
    "ImportanceToMask",
    "Snake",
    "create_adaptive_e8_quantizer",
]
