"""Unified Equivariant Hierarchy - TRUE Exceptional Lie Algebra Cascade.

ARCHITECTURE (December 7, 2025):
================================
    Bulk(512) → E₈(248) → E₇(133) → E₆(78) → F₄(52) → G₂(14) → E8 VQ(8)
                                                                    ↓
    Bulk(512) ← E₈(248) ← E₇(133) ← E₆(78) ← F₄(52) ← G₂(14) ← Tower(7)

KEY FEATURES:
=============
1. **TRUE Exceptional Hierarchy**: Full E8→E7→E6→F4→G2 cascade with Clebsch-Gordan
2. **E8 Residual Bottleneck**: Variable-length optimal sphere packing (Viazovska 2016)
3. **CatastropheKAN**: Colony-specific activation functions at each level

KAN INTEGRATION:
================
From "KAN: Kolmogorov-Arnold Networks" (ICLR 2025):
- Replace linear W with learnable univariate φ(x) on each edge
- Nodes perform summation only (no activation)
- B-spline parametrization enables adaptive function learning
- Better extrapolation and interpretability

Architecture: φ composition replaces W∘σ composition
    MLP: y = W₂ ∘ σ ∘ W₁(x)
    KAN: y = Φ₂ ∘ Φ₁(x) where Φ = matrix of learnable splines

OPTIMAL LAYER DESIGN (from papers):
===================================
- KAN depth 2-3 layers optimal for most functions
- Use base activation (residual to linear) for stability
- Grid extension: start coarse → refine for accuracy
- 8 B-spline knots per edge is good default

References:
- Liu et al. (2024): KAN: Kolmogorov-Arnold Networks
- Viazovska (2017): Sphere Packing in Dimension 8
- Bronstein et al. (2021): Geometric Deep Learning
- Gu & Dao (2023): Mamba - Selective State Spaces

Created: December 1, 2025
Updated: December 2, 2025 - KAN Integration, E8 Residual Bottleneck
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

# TRUE Exceptional Hierarchy - Clebsch-Gordan coefficients (Dec 7, 2025)
from kagami_math.clebsch_gordan_exceptional import (
    TrueExceptionalHierarchy,
)
from kagami_math.dimensions import (
    OCTONION_EMBEDDING_DIM,
    S7_INTRINSIC_DIM,
    get_bulk_dim,
)

# Import E8 residual quantization (v2 lattice protocol)
from kagami_math.e8_lattice_protocol import (
    E8LatticeResidualConfig,
    ResidualE8LatticeVQ,
)

# CatastropheKAN Layers - MANDATORY (Dec 7, 2025)
# Replace generic B-spline KAN with catastrophe-aware activations
# Lazy import to avoid circular dependency
# Canonical Fano plane (G₂ 3-form derived) - Dec 6, 2025
from kagami_math.fano_plane import get_fano_lines_zero_indexed

# G₂ Irrep Tower - MANDATORY for tower processing (Dec 2, 2025)
# E8 residual is the bottleneck, G₂ tower processes the tower representation
from kagami_math.g2_irrep_tower import (
    G2CrossCopyInteraction,
    G2HardwareConfig,
    G2IrrepTower,
    IrrepLevel,
    ScalableG2Hierarchy,
    get_optimal_g2_config,
)
from torch.utils.checkpoint import checkpoint as gradient_checkpoint

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


class HierarchyLevel(IntEnum):
    """Levels in the E8 residual hierarchy."""

    E8_RESIDUAL = 0  # Variable-depth E8 residual (1-16 levels; varint bytes on-wire)
    TOWER = 1  # 7k D tower
    BULK = 2  # Configurable (512D default)


# Legacy capacity proxy (bits per residual level).
# NOTE: v2 lattice protocol encodes an E8 lattice point (8 half-step ints) per level,
# so bitrate is not fixed. We keep log₂(240) ≈ 7.91 as a *telemetry* proxy (root-shell).
E8_BITS_PER_LEVEL = math.log2(240)  # ≈ 7.91 (legacy proxy)

# Parameter allocation ratios (based on information theory)
PARAM_ALLOCATION = {
    "bulk_tower": 0.60,  # Bulk ↔ Tower transformation
    "tower_process": 0.25,  # Tower processing (G₂ irreps)
    "e8_quantize": 0.15,  # E8 residual quantization
}


def get_configurable_bulk_dim() -> int:
    """Get bulk dimension from environment or default."""
    env_val = os.environ.get("KAGAMI_BULK_DIM")
    if env_val:
        try:
            dim = int(env_val)
            if dim < 32:
                logger.warning(f"KAGAMI_BULK_DIM={dim} too small, using 32")
                return 32
            return dim
        except ValueError:
            pass
    return get_bulk_dim()


@dataclass
class UnifiedHierarchyConfig:
    """Configuration for E8 Residual Bottleneck Hierarchy.

    ARCHITECTURE:
    =============
    Bulk(configurable) → Tower(7k) → E8 Residual (1-16 levels) → Tower → Bulk

    BULK DIMENSION:
    ==============
    Set via KAGAMI_BULK_DIM environment variable or constructor.
    Defaults to 512 for base model. Scales:
    - nano: 64      (1M params)
    - small: 128    (4M params)
    - base: 512     (50M params)
    - large: 1024   (200M params)
    - xl: 2048      (800M params)

    E8 RESIDUAL BOTTLENECK:
    ======================
    Variable-depth E8 residual codes (1-16 levels by default).
    The underlying v2 lattice protocol encodes each level as an E8 lattice point
    (8 half-step integers) with varint bytes, so on-wire size is variable.

    PARAMETER ALLOCATION:
    ====================
    - 60% Bulk↔Tower (linear projections)
    - 25% Tower processing (G₂ irrep tower)
    - 15% E8 quantization (residual VQ)
    """

    # === BULK DIMENSION (CONFIGURABLE) ===
    bulk_dim: int = field(default_factory=get_configurable_bulk_dim)

    # Model size preset (overrides bulk_dim if set[Any])
    model_size: str = ""  # "", "nano", "small", "base", "large", "xl"

    # Representation multiplier for tower (k copies of 7D)
    rep_multiplier: int = 1

    # === E8 RESIDUAL BOTTLENECK ===
    # OPTIMIZED (Dec 6, 2025): Increased levels for adequate information capacity
    # Rate-distortion analysis: MSE=0.1 requires ~380 bits = 48 E8 levels
    # Practical sweet spot: training=8, inference=16 levels (63-126 bits)
    training_levels: int = 8  # E8 levels during training (was 4)
    inference_levels: int = 16  # E8 levels during inference (was 8)
    min_levels: int = 2  # Minimum 2 bytes (16 bits) for meaningful compression
    max_levels: int = 24  # Maximum 24 bytes (190 bits) for extreme precision
    adaptive_levels: bool = True  # Adapt to input complexity
    complexity_threshold: float = 0.005  # Tighter threshold for better adaptation

    # Temperature annealing (exploration → exploitation)
    temp_start: float = 1.0
    temp_end: float = 0.01
    temp_anneal_steps: int = 50000

    # VQ-VAE training
    commitment_weight: float = 0.25
    use_ema_codebook: bool = True  # EMA for stable codebook
    ema_decay: float = 0.99
    entropy_weight: float = 0.01  # Encourage codebook utilization

    # === G₂ TOWER PROCESSING (MANDATORY) ===
    # G₂ irrep tower ALWAYS used for tower processing
    # No optional flag - this is core to the architecture
    irrep_level: IrrepLevel = IrrepLevel.STANDARD
    hardware_preset: str = "auto"
    num_tower_layers: int = 3

    # SKIP CONNECTIONS REMOVED (Dec 7, 2025)
    # Skip connections allowed geometric bypass - now enforced pure path

    # === FANO CONSTRAINTS (MANDATORY) ===
    # Fano plane colony interactions - always enforced
    learnable_fano_weights: bool = True

    # === REGULARIZATION ===
    dropout: float = 0.1
    layer_norm_eps: float = 1e-6

    # === INITIALIZATION ===
    init_std: float = 0.02  # For linear layers
    use_xavier_init: bool = True

    # === CATASTROPHE KAN - MANDATORY (Dec 7, 2025) ===
    # All 7 elementary catastrophes for bifurcation-aware processing
    # NO generic B-spline KAN - CatastropheKAN only
    catastrophe_dropout: float = 0.1  # Dropout in catastrophe layers

    # === GRADIENT CHECKPOINTING (Jan 4, 2026) ===
    # Enable gradient checkpointing to reduce memory usage during training.
    # Critical for TPU/XLA where activation memory is limiting.
    # Trades compute for memory by recomputing activations during backward pass.
    gradient_checkpointing: bool = False  # Default False for backwards compat

    # Hardware configuration (computed)
    _hardware_config: G2HardwareConfig | None = field(default=None, repr=False)

    # Model size presets
    # Optimized for 512GB unified memory (Apple Silicon)
    SIZE_PRESETS = {
        # Edge/Testing
        "nano": {"bulk_dim": 64, "rep_multiplier": 1, "num_tower_layers": 2},  # ~600K params
        "small": {"bulk_dim": 128, "rep_multiplier": 1, "num_tower_layers": 2},  # ~1M params
        # Production
        "base": {"bulk_dim": 512, "rep_multiplier": 1, "num_tower_layers": 3},  # ~6.5M params
        "large": {"bulk_dim": 1024, "rep_multiplier": 2, "num_tower_layers": 4},  # ~23M params
        "xl": {"bulk_dim": 2048, "rep_multiplier": 4, "num_tower_layers": 6},  # ~87M params
        # Large-scale (512GB+ memory)
        "xxl": {"bulk_dim": 4096, "rep_multiplier": 8, "num_tower_layers": 8},  # ~350M params
        "huge": {"bulk_dim": 6144, "rep_multiplier": 12, "num_tower_layers": 10},  # ~700M params
        "giga": {"bulk_dim": 8192, "rep_multiplier": 16, "num_tower_layers": 12},  # ~1.4B params
    }

    def __post_init__(self) -> None:
        """Validate and compute derived dimensions."""
        # Apply model size preset if specified
        if self.model_size and self.model_size in self.SIZE_PRESETS:
            preset = self.SIZE_PRESETS[self.model_size]
            self.bulk_dim = preset["bulk_dim"]
            self.rep_multiplier = preset["rep_multiplier"]
            self.num_tower_layers = preset["num_tower_layers"]

        # Validate
        if self.bulk_dim < 32:
            raise ValueError(f"bulk_dim must be >= 32, got {self.bulk_dim}")
        if self.rep_multiplier < 1:
            raise ValueError(f"rep_multiplier must be >= 1, got {self.rep_multiplier}")

        # Configure hardware-optimized G₂ tower (MANDATORY)
        self._hardware_config = get_optimal_g2_config(
            hardware=self.hardware_preset,
            model_size=self._infer_model_size(),
        )
        if self._hardware_config.rep_multiplier > self.rep_multiplier:
            self.rep_multiplier = self._hardware_config.rep_multiplier
        self.irrep_level = self._hardware_config.irrep_level

        # Compute derived dimensions
        self._tower_dim = S7_INTRINSIC_DIM * self.rep_multiplier
        self._e8_input_dim = 8  # E8 lattice is 8D

        # Compute parameter allocation
        self._param_allocation = self._compute_param_allocation()

        logger.debug("UnifiedHierarchyConfig: bulk=%d, tower=%d", self.bulk_dim, self._tower_dim)

    def _infer_model_size(self) -> str:
        """Infer model size from bulk dimension."""
        if self.bulk_dim <= 64:
            return "nano"
        elif self.bulk_dim <= 128:
            return "small"
        elif self.bulk_dim <= 512:
            return "base"
        elif self.bulk_dim <= 1024:
            return "large"
        return "xl"

    def _compute_param_allocation(self) -> dict[str, int]:
        """Compute parameter budget per component."""
        # Estimate total params
        total_params = self.bulk_dim * self._tower_dim * 2  # Rough estimate
        total_params += self._tower_dim * 8 * 2  # Tower to E8
        total_params += 240 * 8  # E8 codebook

        return {
            "bulk_tower": int(total_params * PARAM_ALLOCATION["bulk_tower"]),
            "tower_process": int(total_params * PARAM_ALLOCATION["tower_process"]),
            "e8_quantize": int(total_params * PARAM_ALLOCATION["e8_quantize"]),
        }

    @property
    def tower_dim(self) -> int:
        """Tower dimension (7 * rep_multiplier)."""
        return self._tower_dim

    @property
    def colony_dim(self) -> int:
        """Dimension per colony (scaled octonion)."""
        return OCTONION_EMBEDDING_DIM * self.rep_multiplier

    @property
    def total_colony_dim(self) -> int:
        """Total dimension for all 7 colonies."""
        return 7 * self.colony_dim

    @property
    def e8_capacity_bits(self) -> tuple[float, float]:
        """E8 capacity range in bits (training, inference)."""
        return (
            self.training_levels * E8_BITS_PER_LEVEL,
            self.inference_levels * E8_BITS_PER_LEVEL,
        )


# =============================================================================
# FANO COLONY LAYER (Preserved from original)
# =============================================================================

# Fano plane lines (7 lines, each connecting 3 colonies)
# CANONICAL: Uses G₂ 3-form derived lines from quantum/fano_plane.py
FANO_LINES = get_fano_lines_zero_indexed()


class FanoColonyLayer(nn.Module):
    """Fano plane-constrained colony interactions.

    Implements the octonion multiplication structure via Fano plane.
    Each of the 7 lines represents a valid 3-colony interaction.

    TORCH.COMPILE OPTIMIZATION (Dec 16, 2025):
    =========================================
    - Pre-compute softmax weights (no graph breaks from F.softmax parameter access)
    - Use torch.zeros() instead of torch.zeros_like() (avoids data-dependent ops)
    - Stack outputs into tensor instead of list[Any] (better CUDA graph compatibility)
    """

    def __init__(
        self,
        colony_dim: int = 8,
        learnable_weights: bool = True,
    ):
        super().__init__()
        self.colony_dim = colony_dim

        # 7 Fano lines, each with learnable weight
        # Use raw weights (not softmax) to avoid graph breaks
        if learnable_weights:
            self.line_weights_raw = nn.Parameter(torch.ones(7) / 7)
        else:
            self.register_buffer("line_weights_raw", torch.ones(7) / 7)

        # Per-line projections (3 colonies → output)
        self.line_projs = nn.ModuleList([nn.Linear(3 * colony_dim, colony_dim) for _ in range(7)])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply Fano-constrained interactions.

        Args:
            x: [B, 7, colony_dim] colony representations

        Returns:
            [B, 7, colony_dim] with Fano interactions applied
        """
        batch_size = x.shape[0]

        # Softmax weights for proper mixing (avoid accessing .line_weights directly)
        weights = F.softmax(self.line_weights_raw, dim=0)

        # Stack outputs for better torch.compile compatibility
        line_outputs = []

        for line_idx, (i, j, k) in enumerate(FANO_LINES):
            # Gather 3 colonies on this line
            triple = torch.cat([x[:, i], x[:, j], x[:, k]], dim=-1)
            # Project
            line_out = self.line_projs[line_idx](triple)
            line_outputs.append(line_out * weights[line_idx])

        # Scatter back to colonies using torch.zeros (not zeros_like - avoids graph break)
        result = torch.zeros(batch_size, 7, self.colony_dim, dtype=x.dtype, device=x.device)

        for line_idx, (i, j, k) in enumerate(FANO_LINES):
            result[:, i] += line_outputs[line_idx]
            result[:, j] += line_outputs[line_idx]
            result[:, k] += line_outputs[line_idx]

        # Normalize by participation count (each colony in 3 lines)
        result = result / 3.0

        return result + x  # Residual


# =============================================================================
# UNIFIED EQUIVARIANT HOURGLASS (E8 Residual Bottleneck)
# =============================================================================


class UnifiedEquivariantHourglass(nn.Module):
    """E8 Residual Bottleneck World Model Architecture.

    ARCHITECTURE:
    =============
        Bulk(configurable)
            ↓ (Linear + LayerNorm)
        Tower(7k)
            ↓ (G₂ Irrep Tower, optional)
        Tower'(7k)
            ↓ (Linear)
        E8 Residual (1-16 bytes, adaptive)
            ↓ (Decode)
        Tower''(7k)
            ↓ (G₂ Irrep Tower, optional)
        Tower'''(7k)
            ↓ (Linear + LayerNorm)
        Bulk(configurable)

    BOTTLENECK:
    ===========
    Variable-length E8 residual codes (not fixed G₂ 14D).
    - Training: 4 levels = 31.6 bits
    - Inference: 8 levels = 63.3 bits
    - Maximum: 16 levels = 126.6 bits

    DEEP LEARNING FEATURES:
    =======================
    - Xavier initialization
    - EMA codebook (VQ stability)
    - Entropy regularization (codebook utilization)
    - Skip connections with learnable gates
    - Layer normalization
    - Temperature annealing
    """

    def __init__(self, config: UnifiedHierarchyConfig | None = None):
        super().__init__()

        self.config = config or UnifiedHierarchyConfig()
        cfg = self.config

        # === TRUE EXCEPTIONAL HIERARCHY (Dec 7, 2025) ===
        # E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7)
        # Uses mathematically exact Clebsch-Gordan coefficients
        self.exceptional_hierarchy = TrueExceptionalHierarchy()

        # === ENCODER: Bulk(512) → E8(248) → ... → G2(14) → Tower(7) → E8 VQ(8) ===
        # Step 1: Bulk → E8 (expand to 248D exceptional space)
        self.bulk_to_e8 = nn.Sequential(
            nn.Linear(cfg.bulk_dim, 248),
            nn.LayerNorm(248, eps=cfg.layer_norm_eps),
            nn.GELU(),
        )

        # Step 2: Exceptional hierarchy compression (handled by self.exceptional_hierarchy)
        # E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7)

        # Lazy import to avoid circular dependency
        from kagami.core.world_model.layers.catastrophe_kan import CatastropheKANLayer

        # Step 3: S7(7) → Tower processing
        self.s7_to_tower = CatastropheKANLayer(
            7,
            cfg.tower_dim,
            colony_idx=0,  # Fold for initial processing
            use_residual=False,
        )

        # Step 4: Tower → 8D for E8 VQ
        self.tower_to_e8_vq = CatastropheKANLayer(
            cfg.tower_dim,
            8,
            colony_idx=0,  # Fold for final projection
            use_residual=False,
        )

        # === E8 RESIDUAL QUANTIZER ===
        residual_config = E8LatticeResidualConfig(
            max_levels=cfg.max_levels,
            min_levels=cfg.min_levels,
        )
        self.residual_e8 = ResidualE8LatticeVQ(residual_config)

        # === DECODER: E8 VQ(8) → Tower(7) → G2(14) → ... → E8(248) → Bulk(512) ===
        # Step 1: E8 VQ(8) → Tower
        self.e8_vq_to_tower = CatastropheKANLayer(
            8,
            cfg.tower_dim,
            colony_idx=0,  # Fold for initial expansion
            use_residual=False,
        )

        # Step 2: Tower → S7(7)
        self.tower_to_s7 = CatastropheKANLayer(
            cfg.tower_dim,
            7,
            colony_idx=0,
            use_residual=False,
        )

        # Step 3: Exceptional hierarchy expansion (handled by self.exceptional_hierarchy.embed_from_level)
        # S7(7) → G2(14) → F4(52) → E6(78) → E7(133) → E8(248)

        # Step 4: E8(248) → Bulk
        self.e8_to_bulk = nn.Sequential(
            nn.Linear(248, cfg.bulk_dim),
            nn.LayerNorm(cfg.bulk_dim, eps=cfg.layer_norm_eps),
            nn.GELU(),
        )

        # === G₂ IRREP TOWER (MANDATORY for tower processing) ===
        self.encoder_g2_tower = ScalableG2Hierarchy(
            input_dim=cfg.tower_dim,
            output_dim=cfg.tower_dim,
            config=cfg._hardware_config,
            num_layers=cfg.num_tower_layers,
        )
        self.decoder_g2_tower = ScalableG2Hierarchy(
            input_dim=cfg.tower_dim,
            output_dim=cfg.tower_dim,
            config=cfg._hardware_config,
            num_layers=cfg.num_tower_layers,
        )

        # === FANO COLONY LAYER ===
        # FanoColonyLayer operates on tower representation (7 colonies × rep_multiplier)
        # Not on full colony_dim (which is used for octonion embedding)
        self.fano_layer = FanoColonyLayer(
            colony_dim=cfg.rep_multiplier,
            learnable_weights=cfg.learnable_fano_weights,
        )

        # === LAYER NORMS ===
        self.enc_norms = nn.ModuleDict(
            {
                "tower": nn.LayerNorm(cfg.tower_dim, eps=cfg.layer_norm_eps),
                "e8": nn.LayerNorm(8, eps=cfg.layer_norm_eps),
            }
        )
        self.dec_norms = nn.ModuleDict(
            {
                "tower": nn.LayerNorm(cfg.tower_dim, eps=cfg.layer_norm_eps),
                "bulk": nn.LayerNorm(cfg.bulk_dim, eps=cfg.layer_norm_eps),
            }
        )

        # SKIP CONNECTIONS REMOVED (Dec 7, 2025) - Enforced pure geometric path
        # Skip connections allowed bypass of geometric bottleneck - now removed

        # === DROPOUT ===
        self.dropout = nn.Dropout(cfg.dropout)

        # Initialize weights
        self._init_weights()

        # Statistics (use buffer for torch.compile compatibility)
        self.register_buffer("_forward_count", torch.tensor(0, dtype=torch.long), persistent=False)

        # TPU OPTIMIZATION (Jan 4, 2026): Gradient checkpointing support
        # Reduces memory by recomputing activations during backward pass
        self._use_gradient_checkpointing: bool = cfg.gradient_checkpointing

        self._log_architecture()

    def _init_weights(self) -> None:
        """Initialize weights using deep learning best practices."""
        cfg = self.config

        for module in self.modules():
            if isinstance(module, nn.Linear):
                if cfg.use_xavier_init:
                    nn.init.xavier_uniform_(module.weight)
                else:
                    nn.init.normal_(module.weight, std=cfg.init_std)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

    def _log_architecture(self) -> None:
        """Log architecture summary."""
        cfg = self.config
        total_params = sum(p.numel() for p in self.parameters())
        sum(p.numel() for p in self.parameters() if p.requires_grad)

        _train_bits, _inf_bits = cfg.e8_capacity_bits

        logger.debug(
            "UnifiedEquivariantHourglass: bulk=%dD, tower=%dD, params=%d",
            cfg.bulk_dim,
            cfg.tower_dim,
            total_params,
        )

    def _encoder_cascade(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        """Encoder cascade: Bulk → E8(248) → hierarchy → Tower → E8 VQ(8).

        TPU OPTIMIZATION (Jan 4, 2026): Extracted for gradient checkpointing.
        This method performs the heavy compute of the encoder path.

        Args:
            x: [B, bulk_dim] input (already flattened if sequence)

        Returns:
            Tuple of (e8_continuous, tower_out, hierarchy_states)
        """
        cfg = self.config

        # === STEP 1: Bulk(512) → E8(248) ===
        e8_rep = self.bulk_to_e8(x)  # [B, 248]

        # === STEP 2: E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7) ===
        hierarchy_states: dict[str, torch.Tensor] = self.exceptional_hierarchy.project_to_level(
            e8_rep, target_level="S7", return_intermediates=True
        )
        s7_rep = hierarchy_states.get("S7")

        # === STEP 3: S7(7) → Tower processing ===
        tower = self.s7_to_tower(s7_rep)  # [B, tower_dim]
        tower = self.enc_norms["tower"](tower)
        tower = self.dropout(tower)

        # === STEP 3.5: Fano Colony Interactions ===
        tower_reshaped = tower.view(-1, 7, cfg.rep_multiplier)
        tower_reshaped = self.fano_layer(tower_reshaped)
        tower = tower_reshaped.view(-1, cfg.tower_dim)

        # G2 Irrep Tower (MANDATORY)
        tower = self.encoder_g2_tower(tower)

        # === STEP 4: Tower → 8D for E8 VQ ===
        e8_continuous = self.tower_to_e8_vq(tower)
        e8_continuous = self.enc_norms["e8"](e8_continuous)

        return e8_continuous, tower, hierarchy_states

    def _decoder_cascade(self, e8_decoded: torch.Tensor) -> torch.Tensor:
        """Decoder cascade: E8 VQ(8) → Tower → hierarchy → E8(248) → Bulk.

        TPU OPTIMIZATION (Jan 4, 2026): Extracted for gradient checkpointing.
        This method performs the heavy compute of the decoder path.

        Args:
            e8_decoded: [B, 8] E8 VQ representation

        Returns:
            [B, bulk_dim] reconstructed bulk representation
        """
        cfg = self.config

        # === STEP 1: E8 VQ(8) → Tower ===
        tower = self.e8_vq_to_tower(e8_decoded)
        tower = self.dec_norms["tower"](tower)
        tower = self.dropout(tower)

        # G2 Irrep Tower (MANDATORY)
        tower = self.decoder_g2_tower(tower)

        # === STEP 1.5: Fano Colony Interactions ===
        tower_reshaped = tower.view(-1, 7, cfg.rep_multiplier)
        tower_reshaped = self.fano_layer(tower_reshaped)
        tower = tower_reshaped.view(-1, cfg.tower_dim)

        # === STEP 2: Tower → S7(7) ===
        s7_rep = self.tower_to_s7(tower)  # [B, 7]

        # === STEP 3: S7(7) → G2(14) → F4(52) → E6(78) → E7(133) → E8(248) ===
        e8_rep = self.exceptional_hierarchy.embed_from_level(s7_rep, source_level="S7")  # [B, 248]

        # === STEP 4: E8(248) → Bulk(512) ===
        bulk = self.e8_to_bulk(e8_rep)
        bulk = self.dec_norms["bulk"](bulk)

        return bulk

    def encode(
        self,
        x: torch.Tensor,
        return_intermediates: bool = False,
        return_all: bool = False,
        seq_len: int | None = None,
    ) -> dict[str, Any] | tuple[list[torch.Tensor], dict[str, Any]]:
        """Encode bulk to E8 residual indices via TRUE exceptional hierarchy.

        ARCHITECTURE (Dec 7, 2025):
        ===========================
        Bulk(512) → E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7) → Tower → E8 VQ(8)

        Args:
            x: [B, bulk_dim] or [B, S, bulk_dim] input
            return_intermediates: Return all intermediate states
            return_all: Alias for return_intermediates
            seq_len: Unused (for API compatibility)

        Returns:
            If return_intermediates: dict[str, Any] with all states
            Otherwise: (codes, info_dict)
        """
        _ = seq_len
        return_intermediates = return_intermediates or return_all
        cfg = self.config

        # Handle sequence dimension
        has_seq = x.dim() == 3
        if has_seq:
            B, S, D = x.shape
            # Use reshape instead of view for non-contiguous tensors (Dec 14, 2025)
            x = x.reshape(B * S, D)
        else:
            B = x.shape[0]

        intermediates = {"input": x}

        # TPU OPTIMIZATION (Jan 4, 2026): Gradient checkpointing for encoder cascade
        # Wraps the heavy compute (Bulk → E8 hierarchy → Tower → E8 VQ) in checkpoint
        # when enabled, trading compute for memory during backward pass.
        if self.training and self._use_gradient_checkpointing:
            # Gradient checkpoint requires use_reentrant=False for XLA/TPU compatibility
            e8_continuous, tower, hierarchy_states = gradient_checkpoint(
                self._encoder_cascade,
                x,
                use_reentrant=False,
            )
        else:
            e8_continuous, tower, hierarchy_states = self._encoder_cascade(x)

        # Populate intermediates from cascade results
        # Note: e8_248 is computed inside cascade, we recompute for intermediates if needed
        intermediates["e8_248"] = self.bulk_to_e8(x) if return_intermediates else None
        intermediates["e7"] = hierarchy_states.get("E7")  # type: ignore[assignment]
        intermediates["e6"] = hierarchy_states.get("E6")  # type: ignore[assignment]
        intermediates["f4"] = hierarchy_states.get("F4")  # type: ignore[assignment]
        intermediates["g2"] = hierarchy_states.get("G2")  # type: ignore[assignment]
        intermediates["s7"] = hierarchy_states.get("S7")  # type: ignore[assignment]
        intermediates["tower_out"] = tower
        intermediates["e8_continuous"] = e8_continuous

        # === STEP 5: E8 Residual Quantization (VARIABLE LENGTH!) ===
        num_levels = cfg.training_levels if self.training else cfg.inference_levels
        vq_result = self.residual_e8(e8_continuous, num_levels=num_levels)
        # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
        e8_quantized = vq_result["quantized"]
        codes = vq_result["indices"]  # [B, L, 8] where L = num_levels
        # Convert codes from [B, L, 8] to list of [B, 8] for compatibility
        codes = [codes[:, i, :] for i in range(codes.shape[1])]
        intermediates["e8_quantized"] = e8_quantized
        intermediates["e8_vq_loss"] = vq_result["loss"]
        intermediates["e8_perplexity"] = vq_result["perplexity"]
        intermediates["num_levels"] = len(codes)  # type: ignore[assignment]

        # VARIABLE-LENGTH NUCLEUS SEQUENCE (Dec 6, 2025)
        # Returns [B, L, 8] per-level embeddings instead of summed [B, 8]
        # This preserves the hierarchical structure for downstream IB/memory/RSSM
        nucleus_sequence = self.residual_e8.decode_sequence(codes)
        intermediates["nucleus_sequence"] = nucleus_sequence
        intermediates["nucleus_levels"] = len(codes)  # type: ignore[assignment]

        # E8 VQ is THE bottleneck (8D quantized to 240 roots)
        # 8D quantized = optimal sphere packing (Viazovska)
        intermediates["e8_vq"] = e8_quantized  # Distinct from e8_248

        # Manifold = E8 (8D) + tower intrinsic (7D) = 15D
        manifold = torch.cat([e8_quantized, tower[..., :S7_INTRINSIC_DIM]], dim=-1)
        intermediates["manifold"] = manifold

        # Restore sequence dimension
        if has_seq:
            for key in intermediates:
                if isinstance(intermediates[key], torch.Tensor):
                    if intermediates[key].dim() == 2:
                        intermediates[key] = intermediates[key].view(B, S, -1)
                    elif intermediates[key].dim() == 3 and key == "nucleus_sequence":
                        # nucleus_sequence is [B*S, L, 8] → [B, S, L, 8]
                        L = intermediates[key].shape[1]
                        intermediates[key] = intermediates[key].view(B, S, L, 8)
            codes = [c.view(B, S, 8) for c in codes]

        # Backward-compatible naming:
        # - "e8_codes": lattice half-step integer codes per residual level (v2 protocol)
        # - "e8_indices": legacy alias kept for older call sites
        intermediates["e8_codes"] = codes
        intermediates["e8_indices"] = codes

        if return_intermediates:
            return intermediates

        # Extract nucleus_sequence for return dict[str, Any]
        nucleus_seq = intermediates.get("nucleus_sequence")

        # Provide lightweight metrics (no learned codebook losses in lattice VQ)
        metrics = {
            "num_levels": len(codes),
            "quantization_error": (x.view(B * S, -1)[:, :8] - e8_quantized.view(B * S, 8))
            .pow(2)
            .mean()
            .item()
            if has_seq
            else (e8_continuous - e8_quantized).pow(2).mean().item(),
        }

        return codes, {
            "e8_quantized": e8_quantized.view(B, S, -1) if has_seq else e8_quantized,
            "nucleus_sequence": nucleus_seq,
            "num_levels": len(codes),
            "metrics": metrics,
            "intermediates": intermediates,
        }

    def decode(
        self,
        e8_input: torch.Tensor | list[torch.Tensor],
        encoder_states: dict[str, torch.Tensor] | None = None,
        return_all: bool = False,
    ) -> torch.Tensor | dict[str, torch.Tensor]:
        """Decode E8 representation back to bulk via TRUE exceptional hierarchy.

        ARCHITECTURE (Dec 7, 2025 - ENFORCED PURE PATH):
        =================================================
        E8 VQ(8) → Tower → S7(7) → G2(14) → F4(52) → E6(78) → E7(133) → E8(248) → Bulk(512)

        NO SKIP CONNECTIONS. Pure geometric information flow through bottleneck.

        Args:
            e8_input: Either:
                - [B, 8] quantized E8 tensor
                - List of E8 index tensors (from encode)
            encoder_states: UNUSED (kept for API compatibility)
            return_all: Return dict[str, Any] with all intermediates

        Returns:
            [B, bulk_dim] reconstructed, or dict[str, Any] if return_all
        """
        # Handle input formats
        if isinstance(e8_input, list):
            # List of E8 indices → decode via residual VQ
            e8_decoded = self.residual_e8.decode(e8_input)
        elif e8_input.shape[-1] == 8:
            # 8D E8 tensor → use directly
            e8_decoded = e8_input
        else:
            raise ValueError(
                f"decode() expects 8D E8 tensor or list[Any] of indices. "
                f"Got tensor with shape {e8_input.shape}"
            )

        # Handle sequence dimension
        has_seq = e8_decoded.dim() == 3
        if has_seq:
            B, S, D = e8_decoded.shape
            e8_decoded = e8_decoded.view(B * S, D)
            if encoder_states:
                encoder_states = {
                    k: v.view(B * S, -1) if isinstance(v, torch.Tensor) and v.dim() == 3 else v
                    for k, v in encoder_states.items()
                }
        else:
            B = e8_decoded.shape[0]

        intermediates = {"e8_vq": e8_decoded}
        _ = encoder_states  # Unused - skip connections removed

        # TPU OPTIMIZATION (Jan 4, 2026): Gradient checkpointing for decoder cascade
        # Wraps the heavy compute (E8 VQ → Tower → hierarchy → Bulk) in checkpoint
        # when enabled, trading compute for memory during backward pass.
        if self.training and self._use_gradient_checkpointing:
            # Gradient checkpoint requires use_reentrant=False for XLA/TPU compatibility
            bulk = gradient_checkpoint(
                self._decoder_cascade,
                e8_decoded,
                use_reentrant=False,
            )
        else:
            bulk = self._decoder_cascade(e8_decoded)

        intermediates["bulk"] = bulk

        # Restore sequence dimension
        if has_seq:
            bulk = bulk.view(B, S, -1)
            for key in intermediates:
                if isinstance(intermediates[key], torch.Tensor) and intermediates[key].dim() == 2:
                    intermediates[key] = intermediates[key].view(B, S, -1)

        if return_all:
            return intermediates
        return bulk

    def forward(
        self,
        x: torch.Tensor,
        return_all: bool = False,
    ) -> torch.Tensor | dict[str, Any]:
        """Full encode-decode pass.

        PERFORMANCE OPTIMIZATION (Dec 16, 2025):
        =======================================
        Uses conditional torch.compile based on device:
        - GPU: torch.compile ENABLED (3-4x speedup)
        - CPU: torch.compile DISABLED by default (avoids 60s+ timeouts)
        - Edge cases: batch=1, seq_len>512 skip compilation on CPU

        Override with ENABLE_TORCH_COMPILE=true/false environment variable.

        DEPRECATED DECORATOR (Dec 16, 2025):
        ===================================
        Removed unconditional @torch.compile decorator. Compilation is now
        device-aware via is_compilation_enabled() in compilation.py.

        Args:
            x: [B, bulk_dim] or [B, S, bulk_dim] input
            return_all: Return dict[str, Any] with all outputs

        Returns:
            Reconstructed tensor, or dict[str, Any] with all outputs
        """
        # Encode (FanoColonyLayer now applied internally on tower representation)
        enc = self.encode(x, return_intermediates=True)
        assert isinstance(enc, dict), (
            "encode() with return_intermediates=True must return dict[str, Any]"
        )
        indices_list = enc["e8_indices"]

        # Decode (pure geometric path - skip connections removed Dec 7, 2025)
        reconstructed = self.decode(enc["e8_quantized"])

        # In-place for torch.compile compatibility
        self._forward_count.add_(1)  # type: ignore[operator]

        if return_all:
            num_levels_val = enc.get("num_levels", 0)
            num_levels_int = num_levels_val if isinstance(num_levels_val, int) else 0
            return {
                "reconstructed": reconstructed,
                "e8_indices": indices_list,
                "e8_quantized": enc["e8_quantized"],
                "e8": enc["e8_quantized"],  # Alias
                "manifold": enc["manifold"],
                "num_levels": enc["num_levels"],
                "bits_used": num_levels_int * E8_BITS_PER_LEVEL,
                "encoder_states": enc,
                "metrics": enc.get("metrics", {}),
            }

        return reconstructed

    def get_compression_stats(self) -> dict[str, Any]:
        """Get compression statistics."""
        cfg = self.config
        stats = self.residual_e8.get_stats()
        stats.update(
            {
                "bulk_dim": cfg.bulk_dim,
                "tower_dim": cfg.tower_dim,
                "e8_levels_train": cfg.training_levels,
                "e8_levels_infer": cfg.inference_levels,
                "bits_train": cfg.training_levels * E8_BITS_PER_LEVEL,
                "bits_infer": cfg.inference_levels * E8_BITS_PER_LEVEL,
            }
        )
        return stats

    def to_bytes(self, x: torch.Tensor) -> bytes:
        """Encode to byte string (compatible with E8MessageBus).

        Args:
            x: [bulk_dim] or [B, bulk_dim] input

        Returns:
            Byte string
        """
        if x.dim() == 1:
            x = x.unsqueeze(0)

        # v2 protocol currently supports encoding a single vector payload.
        if x.shape[0] != 1:
            raise ValueError("to_bytes only supports batch size 1")
        enc = self.encode(x, return_intermediates=True)
        assert isinstance(enc, dict), "encode() must return dict[str, Any]"
        e8_q = (
            enc["e8_quantized"][0] if enc["e8_quantized"].dim() == 2 else enc["e8_quantized"][0, 0]
        )
        num_levels_val = enc["num_levels"]
        num_levels_int = int(num_levels_val) if isinstance(num_levels_val, (int, float)) else 0
        return self.residual_e8.encode_bytes(e8_q, num_levels=num_levels_int)

    def from_bytes(self, data: bytes, device: str = "cpu") -> torch.Tensor:
        """Decode from byte string.

        Args:
            data: Byte string from to_bytes()
            device: Target device

        Returns:
            [bulk_dim] reconstructed
        """
        xq, codes = self.residual_e8.decode_bytes(data)
        xq = xq.to(device)
        result = self.decode([c.to(device) for c in codes])
        assert isinstance(result, torch.Tensor), "decode() should return Tensor"
        return result.squeeze(0)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_unified_hourglass(
    bulk_dim: int | None = None,
    model_size: str = "",
    **kwargs: Any,
) -> UnifiedEquivariantHourglass:
    """Create unified hourglass with E8 residual bottleneck.

    Args:
        bulk_dim: Override bulk dimension
        model_size: "nano", "small", "base", "large", "xl"
        **kwargs: Additional config options

    Returns:
        Configured UnifiedEquivariantHourglass
    """
    config = UnifiedHierarchyConfig(model_size=model_size, **kwargs)
    if bulk_dim is not None:
        config.bulk_dim = bulk_dim
        config.__post_init__()  # Recompute derived values
    return UnifiedEquivariantHourglass(config)


def create_nano_hourglass(**kwargs: Any) -> UnifiedEquivariantHourglass:
    """Create nano model (64D bulk, ~1M params)."""
    return create_unified_hourglass(model_size="nano", **kwargs)


def create_small_hourglass(**kwargs: Any) -> UnifiedEquivariantHourglass:
    """Create small model (128D bulk, ~4M params)."""
    return create_unified_hourglass(model_size="small", **kwargs)


def create_base_hourglass(**kwargs: Any) -> UnifiedEquivariantHourglass:
    """Create base model (512D bulk, ~50M params)."""
    return create_unified_hourglass(model_size="base", **kwargs)


def create_large_hourglass(**kwargs: Any) -> UnifiedEquivariantHourglass:
    """Create large model (1024D bulk, ~200M params)."""
    return create_unified_hourglass(model_size="large", **kwargs)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "E8_BITS_PER_LEVEL",
    "PARAM_ALLOCATION",
    "FanoColonyLayer",
    "G2CrossCopyInteraction",
    # Re-exports for compatibility
    "G2HardwareConfig",
    "G2IrrepTower",
    "HierarchyLevel",
    "IrrepLevel",
    "ScalableG2Hierarchy",
    # Main class
    "UnifiedEquivariantHourglass",
    # Config
    "UnifiedHierarchyConfig",
    "create_base_hourglass",
    "create_large_hourglass",
    "create_nano_hourglass",
    "create_small_hourglass",
    # Factories
    "create_unified_hourglass",
    "get_optimal_g2_config",
]
