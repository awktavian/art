"""Unified Configuration System for Kagami OS.

CREATED: December 14, 2025

This module consolidates 5 scattered configuration files into a single,
validated, Pydantic V2-based configuration system:
    1. kagami/core/config/e2e_model_config.py
    2. kagami/core/world_model/model_config.py (deprecated, removal Q2 2026)
    3. kagami/core/training/training_config.py
    5. kagami/core/safety/cbf_config.py (DELETED Dec 16, 2025 - replaced by SafetyConfig)

DESIGN PRINCIPLES:
==================
1. Pydantic V2 with comprehensive validation
2. Cross-field validation for dimension consistency
3. Backward compatibility via re-exports
4. Environment variable overrides
5. Hierarchical structure matching system architecture

STRUCTURE:
==========
KagamiConfig (root)
    ├── world_model: WorldModelConfig
    │   ├── bulk_dim, layer_dimensions
    │   ├── rssm: RSSMConfig
    │   └── e8_bottleneck: E8BottleneckConfig
    ├── training: TrainingConfig
    └── safety: SafetyConfig (CBF)

USAGE:
======
from kagami.core.config.unified_config import get_kagami_config

config = get_kagami_config()  # Uses environment + defaults
config = get_kagami_config(profile="large")  # Named preset
config = get_kagami_config(bulk_dim=1024)  # Override
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# OPTIMIZED (Dec 28, 2025): Defer torch import to avoid 582ms module-level cost
# torch is only needed for device detection in normalize_device validator
# Lazy import to avoid circular dependency with kagami_math.g2
# from kagami_math.dimensions import get_layer_dimensions, get_matryoshka_dimensions
# Import WorldModelConfig and E8BottleneckConfig from separate module (Dec 28, 2025)
# This breaks the circular import: unified_config → kagami_math.g2 → world_model → model_config → unified_config
from kagami.core.config.world_model_config import E8BottleneckConfig, WorldModelConfig

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class DynamicsType(str, Enum):
    """RSSM dynamics types."""

    GRU = "gru"
    LSTM = "lstm"
    TRANSFORMER = "transformer"


class ActivationType(str, Enum):
    """Activation function types."""

    SWISH = "swish"
    GELU = "gelu"
    RELU = "relu"
    SILU = "silu"


class ClassKType(str, Enum):
    """CBF class-K function types."""

    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    POLYNOMIAL = "polynomial"
    SIGMOID = "sigmoid"


class MatryoshkaWeightStrategy(str, Enum):
    """Weight strategies for Matryoshka loss."""

    UNIFORM = "uniform"
    EXPONENTIAL = "exponential"
    INVERSE = "inverse"
    LEARNED = "learned"


# =============================================================================
# E8 BOTTLENECK CONFIG (moved to world_model_config.py)
# =============================================================================
# E8BottleneckConfig is now imported from kagami.core.config.world_model_config


# =============================================================================
# RSSM CONFIG
# =============================================================================


class HofstadterLoopConfig(BaseModel):
    """Configuration for Hofstadter strange loops in the RSSM."""

    model_config = {"frozen": False, "validate_assignment": True}

    # Loop structure
    max_loop_depth: int = Field(default=3, ge=1)
    loop_decay_factor: float = Field(default=0.9, gt=0.0, le=1.0)
    self_reference_strength: float = Field(default=0.1, ge=0.0)

    # Gödel encoding
    godel_encoding_dim: int = Field(default=64, ge=8)
    godel_temperature: float = Field(default=1.0, gt=0.0)
    enable_diagonal_masking: bool = Field(default=True)

    # Fixed point
    fixed_point_iterations: int = Field(default=10, ge=1)
    fixed_point_tolerance: float = Field(default=1e-6, gt=0.0)

    # Meta-learning
    enable_meta_learning: bool = Field(default=True)
    meta_step_size: float = Field(default=0.01, gt=0.0)

    # Strange loop μ_self (S7 space, Dec 13, 2025)
    internal_dim: int = Field(default=14, ge=1)  # G2
    self_dim: int = Field(default=7, ge=1)  # S7
    action_dim: int = Field(default=8, ge=0)  # E8
    sensory_dim: int = Field(default=7, ge=0)  # S7

    # μ_self EMA
    init_scale: float = Field(default=0.1, gt=0.0)
    self_momentum: float = Field(default=0.99, gt=0.0, le=1.0)
    warmup_momentum: float = Field(default=0.7, gt=0.0, le=1.0)
    warmup_steps: int = Field(default=100, ge=0)


class RSSMConfig(BaseModel):
    """Configuration for Colony Recurrent State Space Model.

    COMPREHENSIVE UPDATE (Nov 30, 2025):
    All features are ALWAYS enabled in production configuration.
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # Core architecture
    state_dim: int = Field(default=256, ge=32)
    action_dim: int = Field(default=8, ge=1)  # E8
    obs_dim: int = Field(default=15, ge=1)  # E8(8) + S7(7)
    latent_dim: int = Field(default=256, ge=32)

    # Colony structure
    num_colonies: int = Field(default=7, ge=7, le=7)  # FIXED at 7
    colony_dim: int = Field(default=256, ge=32)
    fano_plane_enabled: bool = Field(default=True)

    # RSSM components
    hidden_dim: int = Field(default=256, ge=32)
    embedding_dim: int = Field(default=256, ge=32)
    num_layers: int = Field(default=4, ge=1, le=12)

    # Attention
    attention_heads: int = Field(default=8, ge=1)
    attention_dim: int = Field(default=64, ge=8)
    use_sparse_fano_attention: bool = Field(default=True)
    attention_dropout: float = Field(default=0.1, ge=0.0, le=0.5)

    # Computed head dimension (set[Any] in model_validator)
    head_dim: int = Field(default=8, init=False)  # Computed as attention_dim // attention_heads

    # Gated Fano attention (Dec 14, 2025)
    use_gated_fano_attention: bool = Field(default=False)
    fano_gate_init_bias: float = Field(default=2.0)
    fano_gate_l1_weight: float = Field(default=0.0, ge=0.0)

    # Dynamics
    dynamics_type: DynamicsType = Field(default=DynamicsType.GRU)
    use_spectral_norm: bool = Field(default=True)
    activation: ActivationType = Field(default=ActivationType.SWISH)

    # Stochastic components
    use_stochastic: bool = Field(default=True)
    stochastic_dim: int = Field(default=14, ge=1)  # H14
    min_std: float = Field(default=0.1, gt=0.0)
    max_std: float = Field(default=1.0, gt=0.0)

    # Discrete latent (E8 roots)
    latent_classes: int = Field(default=240, ge=2)  # E8 has 240 roots
    # DreamerV3 uses 0.01 (1%) uniform mixing to prevent deterministic collapse
    # 0.10 was causing KL collapse by making prior/posterior too similar
    unimix: float = Field(default=0.01, ge=0.0, le=1.0)

    # Training
    kl_weight: float = Field(default=1.0, ge=0.0)
    kl_balance: float = Field(default=0.8, ge=0.0, le=1.0)
    # DreamerV3 free_bits INCREASED from 1.0 to 3.0 (Jan 6, 2026)
    # Root cause: KL collapse detected in v6e training (KL went to -1.49e-7)
    # Analysis: 1.0 nats floor was too low for 240-class E8 categorical
    # For 240-class: max entropy = ln(240) = 5.48 nats
    # Healthy KL should be ~0.5-2.0 nats (10-40% of max entropy)
    # Floor at 3.0 nats (55% of max) ensures information flow
    kl_free_nats: float = Field(default=3.0, ge=0.0)
    # KL collapse detection threshold (Jan 6, 2026)
    # If KL falls below this, training is likely failing
    kl_collapse_threshold: float = Field(default=1e-4, ge=0.0)

    # Sequence modeling
    sequence_length: int = Field(default=50, ge=1)
    burn_in_steps: int = Field(default=5, ge=0)

    # Hofstadter loops
    hofstadter_config: HofstadterLoopConfig = Field(default_factory=HofstadterLoopConfig)

    # Regularization
    dropout: float = Field(default=0.1, ge=0.0, le=0.5)
    weight_decay: float = Field(default=0.01, ge=0.0)
    gradient_clip: float = Field(default=100.0, gt=0.0)

    # Compilation
    compile_mode: str | None = Field(default="max-autotune")  # None disables torch.compile

    # Optimization
    learning_rate: float = Field(default=3e-4, gt=0.0)
    adam_eps: float = Field(default=1e-8, gt=0.0)

    # Advanced features (ALL ENABLED)
    enable_godel_agent: bool = Field(default=True)
    enable_batched_organism: bool = Field(default=True)
    enable_strange_loops: bool = Field(default=True)
    enable_self_reference: bool = Field(default=True)
    enable_meta_learning: bool = Field(default=True)

    # Colony coordination
    enable_colony_communication: bool = Field(default=True)
    communication_dim: int = Field(default=128, ge=16)
    max_message_length: int = Field(default=32, ge=1)

    # Runtime
    device: str = Field(default="cpu")
    dtype: str = Field(default="float32")

    # Performance
    use_mixed_precision: bool = Field(default=True)
    compile_model: bool = Field(default=True)
    use_gradient_checkpointing: bool = Field(default=False)
    # TPU OPTIMIZATION (Jan 4, 2026): torch.compile mode for kernel fusion
    # Options: "max-autotune" (best fusion, slower compile), "reduce-overhead" (faster compile),
    # "default" (balanced). "max-autotune" recommended for TPU/long training runs.
    compile_mode: str = Field(default="max-autotune")

    @field_validator("state_dim", "colony_dim")
    @classmethod
    def validate_divisible_by_8(cls, v: int) -> int:
        """Ensure dimensions are divisible by 8."""
        if v % 8 != 0:
            raise ValueError(f"Dimension must be divisible by 8, got {v}")
        return v

    @field_validator("max_std")
    @classmethod
    def validate_max_std(cls, v: float, info: Any) -> float:
        """Ensure max_std > min_std."""
        if "min_std" in info.data and v <= info.data["min_std"]:
            raise ValueError(f"max_std ({v}) must be > min_std ({info.data['min_std']})")
        return v

    @field_validator("burn_in_steps")
    @classmethod
    def validate_burn_in(cls, v: int, info: Any) -> int:
        """Ensure burn_in_steps < sequence_length."""
        if "sequence_length" in info.data and v >= info.data["sequence_length"]:
            raise ValueError(
                f"burn_in_steps ({v}) must be < sequence_length ({info.data['sequence_length']})"
            )
        return v

    @model_validator(mode="after")
    def compute_head_dim(self) -> RSSMConfig:
        """Compute head_dim from attention_dim and attention_heads."""
        if self.attention_dim % self.attention_heads != 0:
            raise ValueError(
                f"attention_dim ({self.attention_dim}) must be divisible by "
                f"attention_heads ({self.attention_heads})"
            )
        # Use object.__setattr__ to avoid infinite recursion with validate_assignment=True
        object.__setattr__(self, "head_dim", self.attention_dim // self.attention_heads)
        return self


# =============================================================================
# WORLD MODEL CONFIG (moved to world_model_config.py)
# =============================================================================
# WorldModelConfig is now imported from kagami.core.config.world_model_config


# =============================================================================
# TRAINING CONFIG
# =============================================================================


class TrainingConfig(BaseModel):
    """Configuration for world model pretraining.

    TUNED: December 13, 2025 on M3 Ultra 512GB
    - lr=1e-3 with warmup beats lr=3e-4 without by 36.6%
    - batch_size=2048 optimal for MPS (9,270 tokens/sec)
    - warmup_steps=5 per 100 batch gives best convergence
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # Model preset
    model_preset: str = Field(default="balanced")
    student_dim: int | None = Field(default=None)  # Set from preset if None

    # Sequence
    sequence_length: int = Field(default=8, ge=1)

    # Data
    datasets: list[str] = Field(default_factory=list[Any])
    num_workers: int = Field(default=8, ge=0)
    max_samples: int | None = Field(default=None)

    # Optimization
    batch_size: int = Field(default=256, ge=1)
    learning_rate: float = Field(default=1e-5, gt=0.0)
    weight_decay: float = Field(default=0.01, ge=0.0)
    warmup_steps: int = Field(default=100, ge=0)
    gradient_accumulation_steps: int = Field(default=1, ge=1)
    max_steps: int | None = Field(default=10000)
    grad_clip: float = Field(default=10.0, gt=0.0)

    # Distillation
    distillation_weight: float = Field(default=0.0, ge=0.0)

    # Curriculum
    use_curriculum: bool = Field(default=True)
    use_fano_curriculum: bool = Field(default=True)  # Use Fano curriculum (not CurriculumScheduler)
    enable_fano_routing: bool = Field(default=False)  # Enable Fano plane routing in training loop

    # Language modeling
    use_lm_training: bool = Field(default=True)  # Enable language model training
    lm_sample_rate: float = Field(default=0.2, ge=0.0, le=1.0)  # Train LM on 20% of batches

    # Language generation (Dec 18, 2025)
    use_language_generation: bool = Field(default=True)  # Enable WM → text generation
    generation_loss_weight: float = Field(default=0.1, ge=0.0)  # Weight for generation loss

    # Video prediction / neural world model (Dec 2025)
    enable_video_prediction: bool = Field(default=False)  # Enable video/render loss
    enable_render_stream: bool = Field(default=False)  # Alias for enable_video_prediction
    render_width: int = Field(default=128, ge=1)  # Width of rendered frames
    render_height: int = Field(default=128, ge=1)  # Height of rendered frames
    render_loss_weight: float = Field(default=1.0, ge=0.0)  # Weight for render MSE loss
    perceptual_loss_weight: float = Field(default=0.3, ge=0.0)  # Weight for VGG perceptual loss

    # Stage configuration
    stage_config_path: str | None = Field(default=None)  # Path to stage-specific YAML

    # Runtime
    device: str = Field(default="auto")
    mixed_precision: bool = Field(default=True)
    gradient_checkpointing: bool = Field(
        default=False
    )  # Enable for large models (bulk_dim >= 1024)
    compile_model: bool = Field(default=True)

    # Logging
    log_interval: int = Field(default=100, ge=1)
    save_interval: int = Field(default=1000, ge=1)
    eval_interval: int = Field(default=1000, ge=1)

    # Monitoring (W&B only - Dec 27, 2025)
    # MIGRATION: TensorBoard removed, using W&B as primary logging backend
    use_wandb: bool = Field(default=True)  # Weights & Biases logging
    wandb_project: str = Field(default="kagami-world-model")
    wandb_entity: str | None = Field(default=None)
    wandb_run_name: str | None = Field(default=None)

    # Checkpointing (configurable strategy - Dec 16, 2025)
    # UPDATED Jan 5, 2026: GCS checkpointing enabled by default
    checkpoint_dir: str = Field(default="checkpoints")
    checkpoint_interval: int = Field(default=1000, ge=1)  # Save checkpoint every N steps
    checkpoint_keep_last: int | None = Field(
        default=5
    )  # Keep only last K checkpoints (None = keep all)
    checkpoint_on_best: bool = Field(default=True)  # Save checkpoint on best validation loss
    best_checkpoint_path: str = Field(
        default="checkpoints/best_model.pt"
    )  # Separate best checkpoint

    # GCS Checkpointing (Jan 5, 2026) — ENABLED BY DEFAULT
    checkpoint_to_gcs: bool = Field(default=True)  # Sync checkpoints to GCS
    gcs_checkpoint_bucket: str = Field(
        default="gs://kagami-training-schizodactyl-2026"
    )  # GCS bucket for checkpoints
    gcs_checkpoint_prefix: str = Field(default="checkpoints")  # Prefix within bucket
    gcs_async_upload: bool = Field(default=True)  # Non-blocking uploads
    gcs_checksum_verify: bool = Field(default=True)  # SHA256 verification on load

    @field_validator("model_preset")
    @classmethod
    def validate_preset(cls, v: str) -> str:
        """Validate model preset."""
        valid_presets = {"minimal", "balanced", "large", "maximal"}
        v = v.strip().lower()
        if v not in valid_presets:
            raise ValueError(f"model_preset must be in {valid_presets}, got {v}")
        return v

    @field_validator("device")
    @classmethod
    def normalize_device(cls, v: str) -> str:
        """Normalize device with auto-detection."""
        v = v.strip().lower()
        if v == "auto":
            import torch  # Lazy import for device detection

            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            elif torch.cuda.is_available():
                return "cuda"
            else:
                return "cpu"
        elif v in {"cpu", "cuda", "mps"}:
            return v
        raise ValueError(f"Invalid device: {v!r}. Valid: auto, cpu, cuda, mps")

    @field_validator("checkpoint_interval")
    @classmethod
    def validate_checkpoint_interval(cls, v: int) -> int:
        """Validate checkpoint_interval is positive."""
        if v <= 0:
            raise ValueError("checkpoint_interval must be positive")
        return v

    @field_validator("checkpoint_keep_last")
    @classmethod
    def validate_checkpoint_keep_last(cls, v: int | None) -> int | None:
        """Validate checkpoint_keep_last is positive or None."""
        if v is not None and v <= 0:
            raise ValueError("checkpoint_keep_last must be positive or None")
        return v

    @model_validator(mode="after")
    def apply_preset_defaults(self) -> TrainingConfig:
        """Apply preset defaults including student_dim."""
        preset_to_student_dim = {
            "minimal": 32,
            "balanced": 128,
            "large": 512,
            "maximal": 2048,
        }

        # Set student_dim from preset if not explicitly set[Any]
        if self.student_dim is None:
            self.student_dim = preset_to_student_dim.get(self.model_preset, 128)

        # Validate student_dim
        if self.student_dim < 32:
            raise ValueError(f"student_dim must be >= 32, got {self.student_dim}")

        return self


# =============================================================================
# SAFETY CONFIG (CBF)
# =============================================================================


class CBFDynamicsConfig(BaseModel):
    """Configuration for CBF dynamics (f_drift and g_control matrices)."""

    model_config = {"frozen": False, "validate_assignment": True}

    # Natural risk evolution without control (4D state vector)
    f_drift: list[float] = Field(
        default_factory=lambda: [
            0.1,
            0.05,
            0.02,
            0.08,
        ]  # [threat, uncertainty, complexity, predictive]
    )

    # Control influence matrix (4x2: state dimensions × control dimensions)
    g_control: list[list[float]] = Field(
        default_factory=lambda: [
            [-0.3, -0.2],  # threat
            [-0.2, -0.1],  # uncertainty
            [-0.1, -0.3],  # complexity
            [-0.2, -0.15],  # predictive
        ]
    )

    @field_validator("f_drift")
    @classmethod
    def validate_f_drift(cls, v: list[float]) -> list[float]:
        """Validate f_drift has 4 elements."""
        if len(v) != 4:
            raise ValueError(f"f_drift must have 4 elements, got {len(v)}")
        return v

    @field_validator("g_control")
    @classmethod
    def validate_g_control(cls, v: list[list[float]]) -> list[list[float]]:
        """Validate g_control is 4x2."""
        if len(v) != 4:
            raise ValueError(f"g_control must have 4 rows, got {len(v)}")
        for i, row in enumerate(v):
            if len(row) != 2:
                raise ValueError(f"g_control row {i} must have 2 elements, got {len(row)}")
        return v


class ClassKConfig(BaseModel):
    """Configuration for class-K function α(h)."""

    model_config = {"frozen": False, "validate_assignment": True}

    function_type: ClassKType = Field(default=ClassKType.LINEAR)
    k: float = Field(default=1.0, gt=0.0)  # Scaling parameter
    lambda_param: float = Field(default=1.0, gt=0.0)  # Exponential/sigmoid steepness
    p: float = Field(default=2.0, gt=0.0)  # Polynomial degree


class AdaptiveConfig(BaseModel):
    """Configuration for adaptive CBF learning."""

    model_config = {"frozen": False, "validate_assignment": True}

    enabled: bool = Field(default=True)
    learning_rate: float = Field(default=0.01, gt=0.0, lt=1.0)
    adaptation_window: int = Field(default=100, ge=10)
    min_observations: int = Field(default=20, ge=5)
    target_safety_margin: float = Field(default=0.5, gt=0.0, lt=1.0)
    alpha_min: float = Field(default=0.1, gt=0.0)
    alpha_max: float = Field(default=10.0, gt=0.0)
    auto_tune_class_k: bool = Field(default=True)

    @field_validator("min_observations")
    @classmethod
    def validate_min_observations(cls, v: int, info: Any) -> int:
        """Ensure min_observations <= adaptation_window."""
        if "adaptation_window" in info.data and v > info.data["adaptation_window"]:
            raise ValueError("min_observations must be <= adaptation_window")
        return v

    @field_validator("alpha_max")
    @classmethod
    def validate_alpha_max(cls, v: float, info: Any) -> float:
        """Ensure alpha_max > alpha_min."""
        if "alpha_min" in info.data and v <= info.data["alpha_min"]:
            raise ValueError("alpha_max must be > alpha_min")
        return v


class SafetyConfig(BaseModel):
    """Complete CBF configuration with adaptive learning support.

    CRITICAL FIX (Nov 10, 2025): safety_threshold increased from 0.3 to 0.5
    to allow external operations with conservative defaults.
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # Core CBF parameters
    safety_threshold: float = Field(default=0.5, gt=0.0, lt=1.0)
    u_min: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    u_max: list[float] = Field(default_factory=lambda: [1.0, 1.0])

    # Risk weights for h(x) calculation
    risk_weights: list[float] = Field(default_factory=lambda: [0.4, 0.3, 0.1, 0.2])

    # Dynamics
    dynamics: CBFDynamicsConfig = Field(default_factory=CBFDynamicsConfig)

    # Class-K function
    class_k: ClassKConfig = Field(default_factory=ClassKConfig)

    # Adaptive learning
    adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)

    # QP solver
    qp_tolerance: float = Field(default=1e-6, gt=0.0, lt=0.1)
    qp_max_iterations: int = Field(default=60, ge=10)
    robust_delta: float = Field(default=0.0, ge=0.0)

    @field_validator("u_min", "u_max")
    @classmethod
    def validate_control_bounds(cls, v: list[float]) -> list[float]:
        """Validate control bounds have 2 elements."""
        if len(v) != 2:
            raise ValueError("Control bounds must have 2 elements")
        return v

    @field_validator("risk_weights")
    @classmethod
    def validate_risk_weights(cls, v: list[float]) -> list[float]:
        """Validate risk_weights."""
        if len(v) != 4:
            raise ValueError(f"risk_weights must have 4 elements, got {len(v)}")
        if not all(w >= 0 for w in v):
            raise ValueError("risk_weights must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_control_bounds_order(self) -> SafetyConfig:
        """Ensure u_min < u_max."""
        for i, (lo, hi) in enumerate(zip(self.u_min, self.u_max, strict=False)):
            if lo >= hi:
                raise ValueError(f"u_min[{i}]={lo} must be < u_max[{i}]={hi}")
        return self


# =============================================================================
# SYMBIOTE CONFIG (Theory of Mind)
# =============================================================================


class SymbioteConfig(BaseModel):
    """Configuration for Symbiote Module - Theory of Mind capability.

    The Symbiote Module provides Kagami with the ability to model and predict
    the mental states of other agents (users, other AIs), enabling more
    empathetic and socially-aware interactions.

    MATHEMATICAL LINK: Corresponds to e₈, completing the octonion structure
    that underpins the seven colonies (e₁-e₇) and the E₈ lattice.

    Created: December 21, 2025 (Symbiote Evolution)
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # Social World Model dimensions
    social_input_dim: int = Field(default=512, ge=64, le=2048)
    social_hidden_dim: int = Field(default=256, ge=32, le=1024)
    social_output_dim: int = Field(default=128, ge=16, le=512)
    social_num_layers: int = Field(default=3, ge=1, le=8)

    # Agent model limits
    max_agent_models: int = Field(default=100, ge=1, le=1000)
    belief_history_limit: int = Field(default=50, ge=10, le=500)
    intent_history_limit: int = Field(default=20, ge=5, le=100)

    # Social surprise (EFE integration)
    social_surprise_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    surprise_threshold: float = Field(default=0.7, gt=0.0, le=1.0)

    # Social safety (CBF integration)
    social_safety_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    manipulation_threshold: float = Field(default=0.5, gt=0.0, le=1.0)

    # Nexus integration
    enable_nexus_integration: bool = Field(default=True)
    relationship_decay_rate: float = Field(default=0.01, ge=0.0, le=0.1)

    # Inference settings
    update_interval_ms: int = Field(default=100, ge=10, le=5000)
    inference_temperature: float = Field(default=1.0, gt=0.0, le=2.0)


# =============================================================================
# ROOT CONFIG
# =============================================================================


class KagamiConfig(BaseModel):
    """Unified configuration for Kagami OS.

    This is the SINGLE SOURCE for all system configuration.
    Consolidates 5 scattered configs into one validated hierarchy.

    USAGE:
    ======
    from kagami.core.config.unified_config import get_kagami_config

    config = get_kagami_config()  # Uses environment + defaults
    config = get_kagami_config(profile="large")  # Named preset
    config = get_kagami_config(bulk_dim=1024)  # Override specific fields
    """

    model_config = {
        "frozen": False,
        "validate_assignment": True,
        "arbitrary_types_allowed": True,
    }

    # Hierarchical configuration
    world_model: WorldModelConfig = Field(default_factory=WorldModelConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    symbiote: SymbioteConfig = Field(default_factory=SymbioteConfig)

    # Metadata
    profile_name: str = Field(default="base")
    version: str = Field(default="1.0.0")

    @model_validator(mode="after")
    def synchronize_dimensions(self) -> KagamiConfig:
        """Synchronize dimensions across configs."""
        # Sync bulk_dim between world_model and training preset
        bulk_dim = self.world_model.bulk_dim

        # Sync RSSM dimensions
        self.world_model.rssm.state_dim = bulk_dim
        self.world_model.rssm.latent_dim = bulk_dim

        # ALWAYS sync student_dim with bulk_dim (world model is source of truth)
        # This ensures profile changes properly propagate to training config
        object.__setattr__(self.training, "student_dim", bulk_dim)

        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for serialization)."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KagamiConfig:
        """Create from dictionary."""
        return cls.model_validate(data)

    def save(self, path: str | Path) -> None:
        """Save configuration to JSON file."""
        import json

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Configuration saved to {path}")

    @classmethod
    def load(cls, path: str | Path) -> KagamiConfig:
        """Load configuration from JSON file."""
        import json

        with open(path) as f:
            data = json.load(f)

        config = cls.from_dict(data)
        logger.info(f"Configuration loaded from {path}")
        return config


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def get_kagami_config(
    profile: str | None = None, bulk_dim: int | None = None, **overrides: Any
) -> KagamiConfig:
    """Get unified Kagami configuration.

    Args:
        profile: Named profile (minimal/balanced/large/maximal)
        bulk_dim: Override bulk dimension (takes precedence over profile)
        **overrides: Additional config overrides (nested dict[str, Any] for sub-configs)

    Returns:
        Configured KagamiConfig instance

    Examples:
        >>> config = get_kagami_config()  # Default
        >>> config = get_kagami_config(profile="large")
        >>> config = get_kagami_config(bulk_dim=1024)
        >>> config = get_kagami_config(world_model={"bulk_dim": 512})
    """
    # Start with defaults
    config = KagamiConfig()

    # Apply profile
    if profile is not None:
        profile = profile.strip().lower()
        if profile == "minimal":
            config.world_model.bulk_dim = 32
            config.training.batch_size = 8
        elif profile == "balanced":
            config.world_model.bulk_dim = 128
            config.training.batch_size = 32
        elif profile == "large":
            config.world_model.bulk_dim = 512
            config.training.batch_size = 16
        elif profile == "maximal":
            config.world_model.bulk_dim = 2048
            config.training.batch_size = 4
        else:
            raise ValueError(
                f"Unknown profile: {profile}. Valid: minimal, balanced, large, maximal"
            )
        config.profile_name = profile

    # Apply bulk_dim override
    if bulk_dim is not None:
        # Lazy import to avoid circular dependency with kagami_math.g2
        from kagami_math.dimensions import get_layer_dimensions, get_matryoshka_dimensions

        config.world_model.bulk_dim = bulk_dim
        config.world_model.layer_dimensions = get_layer_dimensions(bulk_dim)
        config.world_model.matryoshka_dims = get_matryoshka_dimensions(bulk_dim)

    # Apply nested overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            if isinstance(value, dict):
                # Nested config update
                nested_config = getattr(config, key)
                for nested_key, nested_value in value.items():
                    if hasattr(nested_config, nested_key):
                        setattr(nested_config, nested_key, nested_value)
                    else:
                        logger.warning(f"Unknown nested key: {key}.{nested_key}")
            else:
                setattr(config, key, value)
        else:
            logger.warning(f"Unknown config key: {key}")

    # Re-validate after overrides
    config = config.model_validate(config.model_dump())

    return config


# =============================================================================
# ENVIRONMENT VARIABLE SUPPORT
# =============================================================================


def apply_env_overrides(config: KagamiConfig) -> KagamiConfig:
    """Apply environment variable overrides to configuration.

    Supported environment variables:
        KAGAMI_BULK_DIM: Override bulk dimension
        KAGAMI_DEVICE: Override device (cpu/cuda/mps)
        KAGAMI_BATCH_SIZE: Override batch size
        KAGAMI_LEARNING_RATE: Override learning rate
        KAGAMI_CBF_SAFETY_THRESHOLD: Override CBF safety threshold

    Args:
        config: Configuration to update

    Returns:
        Updated configuration
    """
    overrides: dict[str, Any] = {}

    # Bulk dimension
    if bulk_dim_str := os.getenv("KAGAMI_BULK_DIM"):
        try:
            overrides.setdefault("world_model", {})["bulk_dim"] = int(bulk_dim_str)
        except ValueError:
            logger.error(f"Invalid KAGAMI_BULK_DIM: {bulk_dim_str}")

    # Device
    if device := os.getenv("KAGAMI_DEVICE"):
        overrides.setdefault("world_model", {})["device"] = device
        overrides.setdefault("training", {})["device"] = device

    # Batch size
    if batch_size_str := os.getenv("KAGAMI_BATCH_SIZE"):
        try:
            overrides.setdefault("training", {})["batch_size"] = int(batch_size_str)
        except ValueError:
            logger.error(f"Invalid KAGAMI_BATCH_SIZE: {batch_size_str}")

    # Learning rate
    if lr_str := os.getenv("KAGAMI_LEARNING_RATE"):
        try:
            overrides.setdefault("training", {})["learning_rate"] = float(lr_str)
        except ValueError:
            logger.error(f"Invalid KAGAMI_LEARNING_RATE: {lr_str}")

    # CBF safety threshold
    if threshold_str := os.getenv("KAGAMI_CBF_SAFETY_THRESHOLD"):
        try:
            overrides.setdefault("safety", {})["safety_threshold"] = float(threshold_str)
        except ValueError:
            logger.error(f"Invalid KAGAMI_CBF_SAFETY_THRESHOLD: {threshold_str}")

    # Apply overrides
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict):
                nested_config = getattr(config, key)
                for nested_key, nested_value in value.items():
                    setattr(nested_config, nested_key, nested_value)
            else:
                setattr(config, key, value)

        # Re-validate
        config = config.model_validate(config.model_dump())

    return config


# =============================================================================
# ENVIRONMENT CONFIGURATION (migrated from config_root.py Dec 31, 2025)
# =============================================================================

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Literal

import yaml

try:
    from watchdog.events import FileSystemEventHandler as _FileSystemEventHandler
    from watchdog.observers import Observer

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    Observer = None
    _FileSystemEventHandler = object

# Note: We use a simple singleton pattern here instead of singleton_factory
# to avoid circular imports with kagami.core.shared_abstractions

EnvMode = Literal["development", "staging", "production", "test"]


class EnvironmentConfig:
    """Central environment configuration class for Kagami OS.

    Migrated from config_root.py to unified_config.py on Dec 31, 2025.
    This class handles environment variable loading and validation.
    """

    _loaded = False

    def __init__(self) -> None:
        """Initialize configuration and load environment variables."""
        if not EnvironmentConfig._loaded:
            self.load_environment()
            EnvironmentConfig._loaded = True

    @staticmethod
    def load_environment() -> None:
        """Load environment variables.

        Priority:
        1) Process environment (e.g., GitHub Actions Secrets)
        2) ~/.kagami/.env by default, unless KAGAMI_SKIP_DOTENV=1
        """
        from kagami.core.config_parser import (
            detect_environment_conflicts,
            load_dotenv_file,
            normalize_environment_mode,
            set_environment_defaults,
        )

        # 1. Load session environment
        save_session_env: Callable[[], None] | None = None
        try:
            from kagami.core.session_env import (
                load_session_env,
            )
            from kagami.core.session_env import (
                save_session_env as _save_session_env,
            )

            load_session_env()
            save_session_env = _save_session_env
        except Exception:
            pass

        # 2. Load .env file (unless skipped)
        skip_dotenv = os.getenv("KAGAMI_SKIP_DOTENV", "").lower() in ("1", "true", "yes", "on")
        if not skip_dotenv:
            from kagami.core.utils.paths import get_user_kagami_dir

            env_path = get_user_kagami_dir() / ".env"
            load_dotenv_file(env_path)
        else:
            logger.info("KAGAMI_SKIP_DOTENV set; skipping ~/.kagami/.env load")

        # 3. Validate environment
        try:
            EnvironmentConfig._validate_environment()
        except Exception as e:
            if os.getenv("ENVIRONMENT", "development").lower() == "production":
                raise
            logger.warning("Environment validation warning (non-prod): %s", e)

        # 4. Normalize environment mode
        environment = normalize_environment_mode()

        # 5. Detect conflicts
        detect_environment_conflicts()

        # 6. Set defaults
        set_environment_defaults(environment)

        # 7. Save session if available
        try:
            if save_session_env is not None:
                save_session_env()
        except Exception:
            pass

    @staticmethod
    def _validate_environment() -> None:
        """Validate that critical environment variables are set."""
        critical_vars = ["JWT_SECRET", "KAGAMI_API_KEY"]
        missing_vars = []
        environment = os.getenv("ENVIRONMENT", "development")
        for var in critical_vars:
            value = os.getenv(var)
            allow_autogen = environment != "production"
            need_strong = environment == "production"
            too_short = value is not None and len(value) < 32
            if not value or (need_strong and too_short):
                if allow_autogen:
                    import secrets

                    if var == "KAGAMI_API_KEY":
                        os.environ[var] = secrets.token_urlsafe(48)
                        logger.info("Generated process-only KAGAMI_API_KEY (test/dev)")
                        continue
                    if var == "JWT_SECRET":
                        os.environ[var] = secrets.token_urlsafe(64)
                        logger.info("Generated process-only JWT_SECRET (test/dev)")
                        continue
                if not value:
                    missing_vars.append(var)
                elif too_short:
                    logger.error(f"{var} is too short for production use (minimum 32 characters)")
                    missing_vars.append(f"{var} (too short)")

        if environment == "production":
            if (
                os.getenv("KAGAMI_ADMIN_PASSWORD") in ["admin123", "password", "admin"]
                or os.getenv("KAGAMI_USER_PASSWORD") in ["user123", "password", "user"]
                or os.getenv("KAGAMI_GUEST_PASSWORD") in ["guest123", "password", "guest"]
            ):
                logger.critical("DEFAULT PASSWORDS DETECTED IN PRODUCTION - SYSTEM WILL NOT START")
                raise RuntimeError("Production deployment with default passwords is not allowed")
            api_key = os.getenv("KAGAMI_API_KEY", "")
            default_keys = [
                "default-key",
                "test-key",
                "dev-key",
                "changeme",
                "secret",
                "admin",
                "demo",
                "placeholder",
            ]
            if not api_key or api_key in default_keys:
                logger.critical(
                    "DEFAULT/MISSING API KEY DETECTED IN PRODUCTION - SYSTEM WILL NOT START"
                )
                raise RuntimeError("Production deployment requires a secure, unique API key")

        if missing_vars:
            from kagami.core.utils.paths import get_user_kagami_dir

            env_path = get_user_kagami_dir() / ".env"
            error_msg = f"Critical environment variables missing: {', '.join(missing_vars)}. Please set them in {env_path}"
            logger.error(error_msg)
            if environment == "production":
                raise RuntimeError(error_msg)
            logger.warning(error_msg)

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        """Get configuration value."""
        return os.getenv(key, default)

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = os.getenv(key, "").lower()
        if not value:
            return default
        return value in ("true", "1", "yes", "on")

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def get_database_url() -> str:
        """Get database URL."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            cr_host = os.getenv("CRDB_HOST", "localhost")
            cr_port = os.getenv("CRDB_PORT", "26257")
            cr_db = os.getenv("CRDB_DATABASE", "kagami")
            db_url = f"cockroachdb://root@{cr_host}:{cr_port}/{cr_db}?sslmode=disable"
        return db_url

    @staticmethod
    def get_redis_url() -> str:
        """Get Redis URL with defaults."""
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @staticmethod
    def get_model_cache_path() -> Path:
        """Get model cache path."""
        default_path = Path.home() / ".cache" / "forge_ai_models"
        path_str = os.getenv("MODEL_CACHE_PATH", str(default_path))
        return Path(path_str).expanduser()

    @staticmethod
    def get_all() -> dict[str, str]:
        """Get all configuration values (non-sensitive only)."""
        sensitive_keys = {
            "JWT_SECRET",
            "KAGAMI_API_KEY",
            "MYSQL_PASSWORD",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "HF_TOKEN",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_API_SECRET",
        }
        config = {}
        for key, value in os.environ.items():
            if key not in sensitive_keys:
                config[key] = value
            else:
                config[key] = "***REDACTED***"
        return config


# Global singleton instance
_env_config_instance: EnvironmentConfig | None = None
_env_config_lock = threading.Lock()


def _get_env_config() -> EnvironmentConfig:
    """Get the global environment config singleton (lazy initialization)."""
    global _env_config_instance
    if _env_config_instance is None:
        with _env_config_lock:
            if _env_config_instance is None:
                _env_config_instance = EnvironmentConfig()
    return _env_config_instance


# Backward compatibility: lazy proxy for `config` object
class _EnvConfigProxy:
    """Lazy proxy for backward compatibility with code that imports config directly."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_env_config(), name)


# Legacy Config alias for backward compatibility
Config = EnvironmentConfig
config = _EnvConfigProxy()


# =============================================================================
# ENVIRONMENT HELPER FUNCTIONS (migrated from config_root.py)
# =============================================================================


def get_config(key: str, default: str | None = None) -> str | None:
    """Get configuration value."""
    return _get_env_config().get(key, default)


def get_str_config(key: str, default: str | None = None) -> str | None:
    """Back-compat alias for get_config()."""
    return get_config(key, default)


def get_bool_config(key: str, default: bool = False) -> bool:
    """Get boolean configuration value."""
    return _get_env_config().get_bool(key, default)


def get_int_config(key: str, default: int = 0) -> int:
    """Get integer configuration value."""
    return _get_env_config().get_int(key, default)


def get_database_url() -> str:
    """Get database URL."""
    return _get_env_config().get_database_url()


def get_redis_url() -> str:
    """Get Redis URL."""
    return _get_env_config().get_redis_url()


def get_model_cache_path() -> Path:
    """Get model cache path."""
    return _get_env_config().get_model_cache_path()


def is_production() -> bool:
    """Return True when running in production environment.

    This helper MUST return False for any non-production environment regardless of
    other flags. It is the single source of truth for prod detection across the
    codebase.
    """
    try:
        env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").strip().lower()
        return env == "production"
    except Exception:
        return False


class _Settings:
    """Settings view exposing selected config fields as attributes.

    This preserves compatibility with older imports:
        from kagami.core.config import settings
    """

    @property
    def TEMPORAL_HOST(self) -> str:
        return os.getenv("TEMPORAL_HOST", "localhost")

    @property
    def TEMPORAL_PORT(self) -> int:
        try:
            return int(os.getenv("TEMPORAL_PORT", "7233"))
        except Exception:
            return 7233

    @property
    def TEMPORAL_NAMESPACE(self) -> str:
        return os.getenv("TEMPORAL_NAMESPACE", "kagami")

    @property
    def TEMPORAL_TASK_QUEUE(self) -> str:
        return os.getenv("TEMPORAL_TASK_QUEUE", "kagami-main")

    @property
    def COCKROACH_HOST(self) -> str:
        return os.getenv("CRDB_HOST", "localhost")

    @property
    def COCKROACH_PORT(self) -> int:
        try:
            return int(os.getenv("CRDB_PORT", "26257"))
        except ValueError:
            return 26257

    @property
    def COCKROACH_DATABASE(self) -> str:
        return os.getenv("CRDB_DATABASE", "kagami")

    @property
    def COCKROACH_USER(self) -> str:
        return os.getenv("CRDB_USER", "root")

    @property
    def COCKROACH_PASSWORD(self) -> str | None:
        return os.getenv("CRDB_PASSWORD")


settings = _Settings()


# =============================================================================
# RUNTIME CONFIG MANAGER (migrated from comprehensive_config.py Dec 31, 2025)
# =============================================================================


class ConfigFormat(Enum):
    """Supported configuration file formats."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"


class ConfigSource(Enum):
    """Configuration source types."""

    FILE = "file"
    ENVIRONMENT = "environment"
    COMMAND_LINE = "command_line"
    REMOTE = "remote"
    DEFAULT = "default"


@dataclass
class ConfigValue:
    """Represents a configuration value with metadata."""

    value: Any
    source: ConfigSource
    timestamp: float = dataclass_field(default_factory=time.time)
    validated: bool = False
    sensitive: bool = False


@dataclass
class ConfigSchema:
    """Schema definition for configuration validation."""

    field_type: type[Any]
    required: bool = False
    default: Any = None
    description: str = ""
    sensitive: bool = False
    validator: Callable | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    allowed_values: list[Any] | None = None
    pattern: str | None = None


class ConfigWatcher(_FileSystemEventHandler):
    """File system watcher for configuration hot-reloading."""

    def __init__(self, config_manager: RuntimeConfigManager):
        self.config_manager = config_manager
        self._debounce_timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        config_path = Path(event.src_path)
        if config_path in self.config_manager._watched_files:
            logger.info(f"Configuration file changed: {config_path}")

            with self._lock:
                if self._debounce_timer:
                    self._debounce_timer.cancel()

                self._debounce_timer = threading.Timer(
                    1.0,
                    self._reload_config,
                    args=[config_path],
                )
                self._debounce_timer.start()

    def _reload_config(self, config_path: Path):
        """Reload configuration after debounce period."""
        try:
            self.config_manager._reload_file(config_path)
            logger.info(f"Successfully reloaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Failed to reload configuration from {config_path}: {e}")


class RuntimeConfigManager:
    """Runtime configuration manager with hot-reloading support.

    Migrated from ComprehensiveConfigManager in comprehensive_config.py on Dec 31, 2025.
    Provides runtime configuration management with file watching, multiple formats,
    and change callbacks.
    """

    def __init__(self, app_name: str = "kagami"):
        self.app_name = app_name
        self._config_data: dict[str, ConfigValue] = {}
        self._schemas: dict[str, ConfigSchema] = {}
        self._lock = threading.RLock()

        # Hot-reloading
        self._observer: Observer | None = None
        self._watcher: ConfigWatcher | None = None
        self._watched_files: set[Path] = set()

        # Change callbacks
        self._change_callbacks: list[Callable] = []

        # Load order tracking
        self._load_history: list[dict[str, Any]] = []

    def define_schema(self, key: str, schema: ConfigSchema) -> None:
        """Define schema for a configuration key."""
        with self._lock:
            self._schemas[key] = schema
            logger.debug(f"Defined schema for config key: {key}")

    def load_from_file(
        self,
        file_path: str | Path,
        format_hint: ConfigFormat | None = None,
        watch_for_changes: bool = False,
        required: bool = True,
    ) -> None:
        """Load configuration from a file."""
        from kagami.core.exceptions import ConfigurationError

        file_path = Path(file_path)

        if not file_path.exists():
            if required:
                raise ConfigurationError(f"Required configuration file not found: {file_path}")
            else:
                logger.info(f"Optional configuration file not found, skipping: {file_path}")
                return

        if format_hint is None:
            format_hint = self._detect_format(file_path)

        try:
            config_data = self._load_file_data(file_path, format_hint)

            with self._lock:
                self._merge_config_data(config_data, ConfigSource.FILE)

                if watch_for_changes:
                    self._setup_file_watching(file_path)

                self._load_history.append(
                    {
                        "timestamp": time.time(),
                        "source": "file",
                        "path": str(file_path),
                        "format": format_hint.value,
                        "keys_loaded": list(config_data.keys()),
                    }
                )

            logger.info(f"Loaded configuration from {file_path} ({format_hint.value})")

        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
            if required:
                raise ConfigurationError(f"Failed to load required configuration file: {e}") from e

    def load_from_environment(self, prefix: str | None = None) -> None:
        """Load configuration from environment variables."""
        if prefix is None:
            prefix = f"{self.app_name.upper()}_"

        env_config = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()
                config_key = config_key.replace("__", ".")
                parsed_value = self._parse_env_value(value)
                env_config[config_key] = parsed_value

        with self._lock:
            self._merge_config_data(env_config, ConfigSource.ENVIRONMENT)

            self._load_history.append(
                {
                    "timestamp": time.time(),
                    "source": "environment",
                    "prefix": prefix,
                    "keys_loaded": list(env_config.keys()),
                }
            )

        logger.info(
            f"Loaded {len(env_config)} configuration values from environment (prefix: {prefix})"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        with self._lock:
            if key in self._config_data:
                return self._config_data[key].value
            return self._get_nested_value(key) or default

    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.COMMAND_LINE) -> None:
        """Set a configuration value."""
        with self._lock:
            config_value = ConfigValue(value=value, source=source)
            old_value = self._config_data.get(key)
            self._config_data[key] = config_value

            self._notify_change_callbacks(key, old_value.value if old_value else None, value)

    def has(self, key: str) -> bool:
        """Check if a configuration key exists."""
        with self._lock:
            return key in self._config_data or self._get_nested_value(key) is not None

    def add_change_callback(self, callback: Callable) -> None:
        """Add a callback to be notified of configuration changes."""
        with self._lock:
            self._change_callbacks.append(callback)

    def start_watching(self) -> None:
        """Start file system watching for configuration changes."""
        if not _WATCHDOG_AVAILABLE:
            logger.warning("Watchdog not available - cannot start file watching")
            return

        if self._observer is not None:
            return

        if not self._watched_files:
            logger.warning("No files to watch for configuration changes")
            return

        self._watcher = ConfigWatcher(self)
        self._observer = Observer()

        watched_dirs = set()
        for file_path in self._watched_files:
            directory = file_path.parent
            if directory not in watched_dirs:
                self._observer.schedule(self._watcher, str(directory), recursive=False)
                watched_dirs.add(directory)

        self._observer.start()
        logger.info(f"Started watching {len(watched_dirs)} directories for configuration changes")

    def stop_watching(self) -> None:
        """Stop file system watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._watcher = None
            logger.info("Stopped watching for configuration changes")

    def export_config(
        self,
        output_path: str | Path,
        format_hint: ConfigFormat = ConfigFormat.JSON,
        include_sensitive: bool = False,
    ) -> None:
        """Export current configuration to a file."""
        from kagami.core.exceptions import ConfigurationError

        output_path = Path(output_path)

        with self._lock:
            export_data = {}
            for key, config_value in self._config_data.items():
                if config_value.sensitive and not include_sensitive:
                    continue
                export_data[key] = config_value.value

        try:
            if format_hint == ConfigFormat.JSON:
                with open(output_path, "w") as f:
                    json.dump(export_data, f, indent=2, default=str)
            elif format_hint == ConfigFormat.YAML:
                with open(output_path, "w") as f:
                    yaml.dump(export_data, f, default_flow_style=False)
            else:
                raise ConfigurationError(f"Export format {format_hint} not supported")

            logger.info(f"Exported configuration to {output_path} ({format_hint.value})")

        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            raise ConfigurationError(f"Export failed: {e}") from e

    # Private methods

    def _detect_format(self, file_path: Path) -> ConfigFormat:
        """Detect configuration file format from extension."""
        extension = file_path.suffix.lower()
        if extension == ".json":
            return ConfigFormat.JSON
        elif extension in (".yml", ".yaml"):
            return ConfigFormat.YAML
        elif extension == ".toml":
            return ConfigFormat.TOML
        elif extension in (".ini", ".cfg"):
            return ConfigFormat.INI
        return ConfigFormat.JSON

    def _load_file_data(self, file_path: Path, format_hint: ConfigFormat) -> dict[str, Any]:
        """Load data from configuration file based on format."""
        from kagami.core.exceptions import ConfigurationError

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if format_hint == ConfigFormat.JSON:
                return json.loads(content)
            elif format_hint == ConfigFormat.YAML:
                return yaml.safe_load(content) or {}
            elif format_hint == ConfigFormat.TOML:
                try:
                    import tomllib

                    with open(file_path, "rb") as f:
                        return tomllib.load(f)
                except ImportError:
                    import tomli

                    with open(file_path, "rb") as f:
                        return tomli.load(f)
            elif format_hint == ConfigFormat.INI:
                import configparser

                parser = configparser.ConfigParser()
                parser.read_string(content)
                result = {}
                for section_name in parser.sections():
                    result[section_name] = dict(parser[section_name])
                return result
            else:
                raise ConfigurationError(f"Unsupported configuration format: {format_hint}")

        except Exception as e:
            raise ConfigurationError(
                f"Failed to load {format_hint.value} file {file_path}: {e}"
            ) from e

    def _merge_config_data(self, new_data: dict[str, Any], source: ConfigSource) -> None:
        """Merge new configuration data into existing configuration."""
        for key, value in new_data.items():
            if isinstance(value, dict):
                self._merge_nested_dict(key, value, source)
            else:
                is_sensitive = self._is_sensitive_key(key)
                config_value = ConfigValue(value=value, source=source, sensitive=is_sensitive)
                old_value = self._config_data.get(key)
                self._config_data[key] = config_value

                if old_value and old_value.value != value:
                    self._notify_change_callbacks(key, old_value.value, value)

    def _merge_nested_dict(self, prefix: str, data: dict[str, Any], source: ConfigSource) -> None:
        """Recursively merge nested dictionary into flat configuration."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}"
            if isinstance(value, dict):
                self._merge_nested_dict(full_key, value, source)
            else:
                is_sensitive = self._is_sensitive_key(full_key)
                config_value = ConfigValue(value=value, source=source, sensitive=is_sensitive)
                old_value = self._config_data.get(full_key)
                self._config_data[full_key] = config_value

                if old_value and old_value.value != value:
                    self._notify_change_callbacks(full_key, old_value.value, value)

    def _get_nested_value(self, key: str) -> Any:
        """Get value using dot notation for nested keys."""
        parts = key.split(".")
        for config_key, _config_value in self._config_data.items():
            if config_key.startswith(f"{parts[0]}."):
                remaining_parts = parts[1:]
                current_key = parts[0]
                while remaining_parts:
                    current_key += f".{remaining_parts[0]}"
                    if current_key in self._config_data:
                        if len(remaining_parts) == 1:
                            return self._config_data[current_key].value
                        remaining_parts = remaining_parts[1:]
                    else:
                        break
        return None

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value, trying to detect type."""
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            if "." not in value:
                return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        return value

    def _is_sensitive_key(self, key: str) -> bool:
        """Detect if a configuration key contains sensitive data."""
        sensitive_patterns = [
            "password",
            "secret",
            "key",
            "token",
            "credential",
            "auth",
            "api_key",
            "private_key",
            "certificate",
        ]
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)

    def _setup_file_watching(self, file_path: Path) -> None:
        """Setup file watching for a configuration file."""
        self._watched_files.add(file_path)
        logger.debug(f"Added {file_path} to watch list")

    def _reload_file(self, file_path: Path) -> None:
        """Reload a specific configuration file."""
        if not file_path.exists():
            logger.warning(f"Watched file no longer exists: {file_path}")
            return

        format_hint = self._detect_format(file_path)

        try:
            config_data = self._load_file_data(file_path, format_hint)

            with self._lock:
                self._merge_config_data(config_data, ConfigSource.FILE)

                self._load_history.append(
                    {
                        "timestamp": time.time(),
                        "source": "file_reload",
                        "path": str(file_path),
                        "format": format_hint.value,
                        "keys_loaded": list(config_data.keys()),
                    }
                )

        except Exception as e:
            logger.error(f"Failed to reload configuration from {file_path}: {e}")
            raise

    def _notify_change_callbacks(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify all registered change callbacks."""
        for callback in self._change_callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")


# Backward compatibility alias
ComprehensiveConfigManager = RuntimeConfigManager

# Global configuration manager singleton
_global_config_manager: RuntimeConfigManager | None = None
_manager_lock = threading.Lock()


def get_config_manager(app_name: str = "kagami") -> RuntimeConfigManager:
    """Get the global configuration manager."""
    global _global_config_manager

    with _manager_lock:
        if _global_config_manager is None:
            _global_config_manager = RuntimeConfigManager(app_name)
        return _global_config_manager


def reset_config_manager() -> None:
    """Reset the global configuration manager (for testing)."""
    global _global_config_manager

    with _manager_lock:
        if _global_config_manager:
            _global_config_manager.stop_watching()
        _global_config_manager = None


def load_config_file(file_path: str | Path, **kwargs) -> None:
    """Load configuration from a file using the global manager."""
    manager = get_config_manager()
    manager.load_from_file(file_path, **kwargs)


def load_env_config(prefix: str | None = None) -> None:
    """Load configuration from environment variables using the global manager."""
    manager = get_config_manager()
    manager.load_from_environment(prefix)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "ActivationType",
    "AdaptiveConfig",
    "CBFDynamicsConfig",
    "ClassKConfig",
    "ClassKType",
    "ComprehensiveConfigManager",  # Alias for backward compatibility
    "Config",  # Alias for backward compatibility
    "ConfigFormat",
    "ConfigSchema",
    "ConfigSource",
    "ConfigValue",
    "ConfigWatcher",
    "DynamicsType",
    "E8BottleneckConfig",
    # Environment configuration (migrated from config_root.py)
    "EnvironmentConfig",
    "HofstadterLoopConfig",
    # Pydantic V2 configuration models
    "KagamiConfig",
    "MatryoshkaWeightStrategy",
    "RSSMConfig",
    # Runtime config management (migrated from comprehensive_config.py)
    "RuntimeConfigManager",
    "SafetyConfig",
    "SymbioteConfig",
    "TrainingConfig",
    "WorldModelConfig",
    "apply_env_overrides",
    "config",  # Global singleton proxy
    "get_bool_config",
    "get_config",
    "get_config_manager",
    "get_database_url",
    "get_int_config",
    # Factory functions
    "get_kagami_config",
    "get_model_cache_path",
    "get_redis_url",
    "get_str_config",
    "is_production",
    "load_config_file",
    "load_env_config",
    "reset_config_manager",
    "settings",  # Settings view
]
