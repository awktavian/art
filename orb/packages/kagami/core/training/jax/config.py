"""JAX Configuration - Mirrors PyTorch config structure.

BRICK-BY-BRICK COMPARISON:
=========================
PyTorch Source                          | JAX Target
----------------------------------------|-------------------------------------
unified_config.RSSMConfig               | OrganismRSSMConfig
losses/composed.py:LossConfig           | LossConfig
training/tpu/curriculum.py:PhaseConfig  | PhaseConfig, CurriculumConfig

Created: January 8, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# CURRICULUM PHASES (mirrors curriculum.py:CurriculumPhase)
# =============================================================================


class CurriculumPhase(str, Enum):
    """Training curriculum phases.

    Mirrors unified_curriculum.py:CurriculumPhase.

    7 phases aligned with catastrophe types:
    - WARMUP: Pre-fold stabilization (β≈0)
    - GEOMETRY: Fold (A₂) - 2 colonies
    - ROTATION: Cusp (A₃) - 3 colonies (Fano line)
    - DYNAMICS: Swallowtail (A₄) - 4 colonies
    - JOINT: Butterfly (A₅) - 7 colonies (full Fano)
    - GENERATION: Hyperbolic (D₄⁺) - 7 colonies
    - LANGUAGE: Elliptic (D₄⁻) - 7 colonies, language grounding
    """

    WARMUP = "warmup"  # Pre-fold: β≈0 reconstruction-only (Jan 5, 2026)
    GEOMETRY = "geometry"  # Fold (A₂): E8 lattice, hyperbolic embeddings
    ROTATION = "rotation"  # Cusp (A₃): Rotational equivariance
    DYNAMICS = "dynamics"  # Swallowtail (A₄): World model prediction
    JOINT = "joint"  # Butterfly (A₅): RSSM + EFE unified
    GENERATION = "generation"  # Hyperbolic (D₄⁺): Fine-grained generation
    LANGUAGE = "language"  # Elliptic (D₄⁻): Language grounding (Jan 4, 2026)


# =============================================================================
# MODEL CONFIGURATION (mirrors unified_config.RSSMConfig)
# =============================================================================


@dataclass
class OrganismRSSMConfig:
    """Configuration for OrganismRSSM model.

    PyTorch: packages/kagami/core/config/unified_config.py:RSSMConfig

    BRICK-BY-BRICK:
    - obs_dim: Observation dimension (default 8 for E8)
    - action_dim: Action dimension (default 8 for E8 lattice)
    - num_colonies: Number of colonies = 7 (octonion imaginary basis)
    - colony_dim/deter_dim: Hidden state dimension H (default 384)
    - stochastic_dim: Stochastic state dimension Z (default 32)
    - latent_classes: E8 root categorical (default 240)
    """

    # === Dimensions ===
    obs_dim: int = 64  # Observation dimension
    action_dim: int = 8  # Action dimension (E8 lattice)
    num_colonies: int = 7  # Octonion imaginary basis e₁...e₇
    deter_dim: int = 384  # Deterministic hidden state H
    stoch_dim: int = 32  # Stochastic state Z

    # === Discrete Latents (DreamerV3) ===
    discrete_categories: int = 32  # Number of categorical distributions
    discrete_classes: int = 32  # Classes per category
    latent_classes: int = 240  # E8 root categorical classes

    # === KL Settings ===
    unimix: float = 0.01  # Uniform mixing to prevent collapse
    free_bits: float = 3.0  # Free bits floor (increased from 1.0)
    kl_dyn_weight: float = 0.8  # Dynamics KL weight
    kl_rep_weight: float = 0.2  # Representation KL weight

    # === TwoHot ===
    num_reward_bins: int = 255
    reward_low: float = -20.0
    reward_high: float = 20.0

    # === Architecture ===
    gru_num_blocks: int = 8
    attention_dim: int = 384
    attention_heads: int = 8
    head_dim: int = 48  # attention_dim // attention_heads
    attention_dropout: float = 0.1

    # === SimNorm ===
    simnorm_anchors: int = 4

    # === H-JEPA Horizons ===
    hjepa_horizons: tuple[int, ...] = (1, 4, 16)


# =============================================================================
# LOSS CONFIGURATION (mirrors losses/composed.py:LossConfig)
# =============================================================================


@dataclass
class LossConfig:
    """Loss configuration with tiered structure.

    PyTorch: packages/kagami/core/world_model/losses/composed.py:LossConfig

    TIER 1: Core Prediction (always enabled)
    - prediction_weight: symlog reconstruction

    TIER 2: Essential Losses
    - e8_commitment_weight: VQ codebook training
    - ib_kl_weight: Information bottleneck
    - rssm_kl_weight: RSSM dynamics
    - fano_synergy_weight: Colony coordination
    - h_jepa_pred_weight: Multi-horizon prediction
    - loop_closure_weight: Strange loop
    - stability_weight: Gradient regularization

    TIER 3: Auxiliary (disabled by default)
    - manifold_curvature_weight
    - catastrophe_weight
    - etc.
    """

    # === TIER 1: Core Prediction ===
    prediction_weight: float = 1.0

    # === TIER 2: Essential Losses ===
    e8_commitment_weight: float = 0.05
    e8_commitment_warmup_steps: int = 2000

    ib_kl_weight: float = 0.01
    ib_free_bits: float = 1.0

    rssm_kl_weight: float = 0.1

    seq_ib_recon_weight: float = 0.1
    seq_ib_kl_weight: float = 0.01

    fano_synergy_weight: float = 0.01
    h_jepa_pred_weight: float = 0.05
    loop_closure_weight: float = 0.01
    stability_weight: float = 0.01

    # === TIER 3: Auxiliary ===
    manifold_curvature_weight: float = 0.01
    catastrophe_weight: float = 0.0
    chaos_entropy_weight: float = 0.0
    recognition_weight: float = 0.0
    reward_weight: float = 0.5
    value_weight: float = 0.5
    continue_weight: float = 0.1

    # === Gradient Control ===
    max_gradient_norm: float = 100.0

    # === Uncertainty Weighting (Kendall 2017) ===
    enable_uncertainty_weighting: bool = False


# =============================================================================
# PHASE CONFIGURATION (mirrors curriculum.py:PhaseConfig)
# =============================================================================


@dataclass
class PhaseConfig:
    """Configuration for a curriculum phase.

    Mirrors unified_curriculum.py:PhaseConfig.

    KL ANNEALING (Jan 5, 2026):
    - kl_beta: β for VAE loss (L = recon + β*KL)
    - Use 1e-6 instead of 0 during WARMUP to avoid JAX graph recompilation

    PLATEAU PATIENCE (Jan 5, 2026):
    - plateau_patience: Steps without improvement before LR reduction
    """

    name: CurriculumPhase
    min_steps: int
    max_steps: int
    loss_threshold: float
    lr_multiplier: float

    # === Transition Thresholds ===
    gradient_threshold: float = 0.001  # Gradient norm must be below this
    velocity_threshold: float = 0.001  # Loss velocity must be near zero

    # === Phase-specific loss weights ===
    e8_weight: float = 0.1  # E8 commitment weight
    kl_weight: float = 0.5  # KL loss weight (within phase)
    recon_weight: float = 1.0  # Reconstruction weight
    reward_weight: float = 0.5  # Reward prediction weight
    fano_weight: float = 0.01  # Fano synergy weight
    hjepa_weight: float = 0.05  # H-JEPA prediction weight

    # === KL Annealing (Jan 5, 2026) ===
    kl_beta: float = 1.0  # β for VAE (1e-6 during WARMUP)

    # === Plateau Patience (Jan 5, 2026) ===
    plateau_patience: int = 400  # Steps before LR reduction

    # === Module enables ===
    efe_enabled: bool = False  # Enable EFE loss
    alignment_enabled: bool = False  # Enable alignment loss
    language_enabled: bool = False  # Enable language losses (LANGUAGE phase)

    # === Data weights (curriculum-aware sampling) ===
    data_weights: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 1.0,
        }
    )

    # === Extra config ===
    extra_config: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CURRICULUM CONFIGURATION (mirrors curriculum.py:HyperscaleCurriculumConfig)
# =============================================================================


@dataclass
class CurriculumConfig:
    """Configuration for hyperscale training curriculum.

    PyTorch: packages/kagami/core/training/tpu/curriculum.py:HyperscaleCurriculumConfig
    """

    # === Scale Parameters ===
    num_chips: int = 4
    baseline_batch_size: int = 64
    baseline_lr: float = 3e-4

    # === Batch Scaling ===
    max_per_device_batch: int = 128
    sqrt_scaling_threshold: int = 8192
    gradient_accumulation_steps: int = 0

    # === Learning Rate Scaling ===
    base_warmup_steps: int = 2000
    min_warmup_steps: int = 500
    lr_scaling_mode: str = "auto"

    # === Curriculum Phases ===
    enable_curriculum: bool = True
    phase_patience: int = 5000
    auto_advance: bool = True

    # === E8 Commitment ===
    e8_warmup_start: int = 1000
    e8_warmup_end: int = 5000

    # === Total Training ===
    total_steps: int = 100_000
    checkpoint_every: int = 1000
    log_every: int = 100


# =============================================================================
# TRAINING STATE CONFIG
# =============================================================================


@dataclass(frozen=True)
class TrainingConfig:
    """Training configuration (frozen for JAX hashing).

    Note: frozen=True makes this hashable for jax.jit static_argnums.
    """

    batch_size: int = 64
    seq_len: int = 16
    total_steps: int = 100_000
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    warmup_steps: int = 1000
    grad_clip: float = 100.0
    seed: int = 42


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "CurriculumConfig",
    "CurriculumPhase",
    "LossConfig",
    "OrganismRSSMConfig",
    "PhaseConfig",
    "TrainingConfig",
]
