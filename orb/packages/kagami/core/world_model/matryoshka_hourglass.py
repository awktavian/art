"""Matryoshka Multi-Scale Hourglass — Train All Sizes At Once.

ARCHITECTURE (December 7, 2025):
================================
Single encoder with nested representations at multiple scales.
All scales share the TRUE Exceptional Hierarchy backbone.

    Input(any) → E₈(248) → E₇(133) → E₆(78) → F₄(52) → G₂(14) → S⁷(7) → E8 VQ
                    ↓         ↓         ↓        ↓        ↓        ↓
                 out_xl   out_large  out_base  out_small out_nano  out_micro

MULTI-SCALE OUTPUTS:
====================
- micro: 7D (S⁷ intrinsic — 7 colonies)
- nano: 14D (G₂ automorphisms)
- small: 52D (F₄ Jordan algebra)
- base: 78D (E₆ structure group)
- large: 133D (E₇ Freudenthal)
- xl: 248D (E₈ complete)

This follows Matryoshka Representation Learning (Kusupati et al. 2022)
but uses the natural Lie algebra hierarchy instead of arbitrary truncation.

TRAINING:
=========
Loss = Σᵢ αᵢ × L(scale_i)

where αᵢ weights each scale. Default: uniform or curriculum.

References:
- Kusupati et al. (2022): Matryoshka Representation Learning
- Viazovska (2017): Sphere Packing in Dimension 8

Created: December 7, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy
from kagami_math.e8_lattice_protocol import (
    E8LatticeResidualConfig,
    ResidualE8LatticeVQ,
)

# Lazy import to avoid circular dependency

logger = logging.getLogger(__name__)


# Matryoshka scale dimensions (from exceptional Lie algebra hierarchy)
MATRYOSHKA_SCALES = {
    "micro": 7,  # S⁷ (7 colonies)
    "nano": 14,  # G₂ (automorphisms)
    "small": 52,  # F₄ (Jordan algebra)
    "base": 78,  # E₆ (structure group)
    "large": 133,  # E₇ (Freudenthal)
    "xl": 248,  # E₈ (complete)
}

SCALE_ORDER = ["micro", "nano", "small", "base", "large", "xl"]


@dataclass
class MatryoshkaConfig:
    """Configuration for Matryoshka Multi-Scale Training.

    HARDWARE OPTIMIZATION (512GB MPS):
    ==================================
    - max_bulk_dim: 8192 for giga-scale
    - batch_per_scale: 512 for 2560 total samples
    - gradient_checkpointing: True for memory efficiency
    """

    # Maximum bulk dimension (input/output)
    max_bulk_dim: int = 2048

    # Which scales to train (subset of SCALE_ORDER)
    active_scales: list[str] = field(default_factory=lambda: SCALE_ORDER.copy())

    # Scale weights for loss (default: uniform)
    scale_weights: dict[str, float] = field(default_factory=dict[str, Any])

    # E8 VQ configuration
    training_levels: int = 8
    inference_levels: int = 16

    # Training optimization
    gradient_checkpointing: bool = True
    mixed_precision: bool = False  # MPS has issues with fp16

    # Regularization
    dropout: float = 0.1
    layer_norm_eps: float = 1e-6

    def __post_init__(self) -> None:
        # Default uniform weights
        if not self.scale_weights:
            self.scale_weights = {s: 1.0 / len(self.active_scales) for s in self.active_scales}

        # Normalize weights
        total = sum(self.scale_weights.values())
        self.scale_weights = {k: v / total for k, v in self.scale_weights.items()}


class MatryoshkaHourglass(nn.Module):
    """Multi-Scale Matryoshka Hourglass with TRUE Exceptional Hierarchy.

    All scales share the same exceptional hierarchy backbone.
    Each scale uses a natural truncation point in the Lie algebra chain.

    ARCHITECTURE:
    =============

    ENCODER (shared):
        Input(max_bulk) → E₈(248) → E₇(133) → E₆(78) → F₄(52) → G₂(14) → S⁷(7)
                              ↓         ↓         ↓        ↓        ↓        ↓
                           out_xl   out_large  out_base  out_small out_nano out_micro

    E8 VQ (shared):
        S⁷(7) → Tower → E8 VQ(8)

    DECODERS (per-scale):
        E8 VQ(8) → Tower → S⁷(7) → ... → E₈(248) → Output(bulk_dim)

        Each decoder truncates at its scale level.
    """

    def __init__(self, config: MatryoshkaConfig | None = None):
        super().__init__()

        self.config = config or MatryoshkaConfig()
        cfg = self.config

        # === SHARED EXCEPTIONAL HIERARCHY ===
        self.exceptional_hierarchy = TrueExceptionalHierarchy()

        # === ENCODER: max_bulk → E8(248) ===
        self.bulk_to_e8 = nn.Sequential(
            nn.Linear(cfg.max_bulk_dim, 248),
            nn.LayerNorm(248, eps=cfg.layer_norm_eps),
            nn.GELU(),
        )

        # Lazy import to avoid circular dependency
        from kagami.core.world_model.layers.catastrophe_kan import CatastropheKANLayer

        # === SHARED E8 VQ ===
        self.s7_to_tower = CatastropheKANLayer(7, 28, colony_idx=0, use_residual=False)
        self.tower_to_e8_vq = CatastropheKANLayer(28, 8, colony_idx=0, use_residual=False)

        residual_config = E8LatticeResidualConfig(
            max_levels=cfg.inference_levels,
            min_levels=1,
            adaptive_levels=True,
            residual_threshold=1e-3,
        )
        self.residual_e8 = ResidualE8LatticeVQ(residual_config)

        # === PER-SCALE DECODERS ===
        self.decoders = nn.ModuleDict()
        self.scale_projectors = nn.ModuleDict()

        for scale in cfg.active_scales:
            scale_dim = MATRYOSHKA_SCALES[scale]

            # Projector from scale dimension to output
            # Each scale has its own bulk projection
            bulk_dim = min(cfg.max_bulk_dim, scale_dim * 8)  # Scale-appropriate bulk

            self.decoders[scale] = nn.Sequential(
                nn.Linear(8, scale_dim),  # E8 VQ → scale
                nn.LayerNorm(scale_dim, eps=cfg.layer_norm_eps),
                nn.GELU(),
                nn.Linear(scale_dim, bulk_dim),  # scale → bulk
                nn.LayerNorm(bulk_dim, eps=cfg.layer_norm_eps),
            )

            self.scale_projectors[scale] = nn.Linear(scale_dim, bulk_dim)

        # === LAYER NORMS ===
        self.norms = nn.ModuleDict(
            {
                "e8": nn.LayerNorm(248, eps=cfg.layer_norm_eps),
                "tower": nn.LayerNorm(28, eps=cfg.layer_norm_eps),
                "e8_vq": nn.LayerNorm(8, eps=cfg.layer_norm_eps),
            }
        )

        self.dropout = nn.Dropout(cfg.dropout)

        self._init_weights()
        self._log_architecture()

    def _init_weights(self) -> None:
        """Xavier initialization."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def _log_architecture(self) -> None:
        """Log architecture summary."""
        total_params = sum(p.numel() for p in self.parameters())
        logger.info(
            f"MatryoshkaHourglass: {total_params:,} params, "
            f"scales={self.config.active_scales}, "
            f"max_bulk={self.config.max_bulk_dim}D"
        )

    def encode(
        self,
        x: torch.Tensor,
        return_all_scales: bool = False,
    ) -> dict[str, Any]:
        """Encode to multi-scale representations.

        Args:
            x: [B, max_bulk_dim] input
            return_all_scales: Return representations at all hierarchy levels

        Returns:
            dict[str, Any] with:
                - e8_vq: [B, 8] quantized representation
                - e8_indices: List of index tensors
                - scales: dict[scale_name, [B, scale_dim]] if return_all_scales
        """
        x.shape[0]

        # === STEP 1: Bulk → E8(248) ===
        e8_rep = self.bulk_to_e8(x)
        e8_rep = self.norms["e8"](e8_rep)
        e8_rep = self.dropout(e8_rep)

        # === STEP 2: E8 → E7 → E6 → F4 → G2 → S7 ===
        hierarchy_states = cast(
            dict[str, torch.Tensor],
            self.exceptional_hierarchy.project_to_level(
                e8_rep, target_level="S7", return_intermediates=True
            ),
        )

        # === STEP 3: S7 → Tower → E8 VQ ===
        s7_rep = hierarchy_states["S7"]
        tower = self.s7_to_tower(s7_rep)
        tower = self.norms["tower"](tower)
        tower = self.dropout(tower)

        e8_continuous = self.tower_to_e8_vq(tower)
        e8_continuous = self.norms["e8_vq"](e8_continuous)

        # === STEP 4: E8 VQ Quantization ===
        num_levels = self.config.training_levels if self.training else self.config.inference_levels
        vq_result = self.residual_e8(e8_continuous, num_levels=num_levels)
        # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
        e8_quantized = vq_result["quantized"]
        codes_tensor = vq_result["indices"]  # [B, L, 8] where L = num_levels
        codes = [codes_tensor[:, i, :] for i in range(codes_tensor.shape[1])]
        metrics = {"num_levels": len(codes), "e8_vq_loss": vq_result["loss"]}

        result = {
            "e8_vq": e8_quantized,
            "e8_codes": codes,
            "metrics": metrics,
        }

        if return_all_scales:
            # Map hierarchy levels to scale names
            scale_mapping: dict[str, torch.Tensor] = {
                "micro": hierarchy_states["S7"],  # 7D
                "nano": hierarchy_states["G2"],  # 14D
                "small": hierarchy_states["F4"],  # 52D
                "base": hierarchy_states["E6"],  # 78D
                "large": hierarchy_states["E7"],  # 133D
                "xl": hierarchy_states["E8"],  # 248D (from e8_rep)
            }
            # Use the actual E8 from encoder, not hierarchy
            scale_mapping["xl"] = e8_rep

            result["scales"] = {s: scale_mapping[s] for s in self.config.active_scales}

        return result

    def decode(
        self,
        e8_vq: torch.Tensor,
        scale: str = "base",
    ) -> torch.Tensor:
        """Decode from E8 VQ to specified scale.

        Args:
            e8_vq: [B, 8] quantized representation
            scale: Target scale ("micro", "nano", "small", "base", "large", "xl")

        Returns:
            [B, bulk_dim] reconstructed at specified scale
        """
        if scale not in self.decoders:
            raise ValueError(f"Scale {scale} not in active scales: {self.config.active_scales}")

        return self.decoders[scale](e8_vq)

    def forward(
        self,
        x: torch.Tensor,
        target_scale: str | None = None,
    ) -> dict[str, torch.Tensor]:
        """Full encode-decode pass for training.

        Args:
            x: [B, max_bulk_dim] input
            target_scale: If specified, decode only this scale. Otherwise decode all.

        Returns:
            dict[str, Any] with:
                - reconstructions: dict[scale, [B, bulk_dim]]
                - e8_vq: [B, 8] bottleneck
                - metrics: training metrics
        """
        # Encode
        encoded = self.encode(x, return_all_scales=True)

        # Decode
        if target_scale:
            scales_to_decode = [target_scale]
        else:
            scales_to_decode = self.config.active_scales

        reconstructions = {}
        for scale in scales_to_decode:
            reconstructions[scale] = self.decode(encoded["e8_vq"], scale)

        return {
            "reconstructions": reconstructions,
            "e8_vq": encoded["e8_vq"],
            "scales": encoded.get("scales", {}),
            "metrics": encoded["metrics"],
        }

    def compute_loss(
        self,
        x: torch.Tensor,
        output: dict[str, torch.Tensor],
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """Compute multi-scale Matryoshka loss.

        Loss = Σᵢ αᵢ × MSE(x, reconstruct_i)

        Plus E8 VQ commitment loss.
        """
        total_loss = torch.tensor(0.0, device=x.device)
        loss_breakdown = {}

        # Reconstruction loss per scale
        reconstructions = cast(dict[str, torch.Tensor], output["reconstructions"])
        for scale, recon in reconstructions.items():
            # Project x to scale's bulk dimension if needed
            if recon.shape[-1] != x.shape[-1]:
                x_proj = x[..., : recon.shape[-1]]
            else:
                x_proj = x

            scale_loss = F.mse_loss(recon, x_proj)
            weight = self.config.scale_weights.get(scale, 1.0)
            total_loss = total_loss + weight * scale_loss
            loss_breakdown[f"recon_{scale}"] = scale_loss.item()

        # E8 VQ losses
        metrics = cast(dict[str, Any], output["metrics"])
        if "commitment_loss" in metrics:
            commitment = metrics["commitment_loss"]
            if isinstance(commitment, torch.Tensor):
                total_loss = total_loss + 0.25 * commitment
                loss_breakdown["commitment"] = commitment.item()

        if "balance_loss" in metrics:
            balance = metrics["balance_loss"]
            if isinstance(balance, torch.Tensor):
                total_loss = total_loss + 0.1 * balance
                loss_breakdown["balance"] = balance.item()

        loss_breakdown["total"] = total_loss.item()

        return total_loss, loss_breakdown


def create_matryoshka_model(
    max_bulk_dim: int = 2048,
    active_scales: list[str] | None = None,
    device: str = "mps",
) -> MatryoshkaHourglass:
    """Create Matryoshka model optimized for hardware.

    Args:
        max_bulk_dim: Maximum bulk dimension
        active_scales: Scales to train (default: all)
        device: Target device

    Returns:
        Configured MatryoshkaHourglass
    """
    config = MatryoshkaConfig(
        max_bulk_dim=max_bulk_dim,
        active_scales=active_scales or SCALE_ORDER.copy(),
    )

    model = MatryoshkaHourglass(config)
    model = model.to(device)

    return model


# Convenience aliases
def micro() -> int:
    return MATRYOSHKA_SCALES["micro"]


def nano() -> int:
    return MATRYOSHKA_SCALES["nano"]


def small() -> int:
    return MATRYOSHKA_SCALES["small"]


def base() -> int:
    return MATRYOSHKA_SCALES["base"]


def large() -> int:
    return MATRYOSHKA_SCALES["large"]


def xl() -> int:
    return MATRYOSHKA_SCALES["xl"]
