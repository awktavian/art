"""World Model Configuration.

CREATED: December 28, 2025

This module contains WorldModelConfig extracted from unified_config.py to break
the circular import:

    kagami.core.config.unified_config
      → kagami_math.g2
        → kagami.core.world_model
          → kagami.core.world_model.model_config
            → kagami.core.config.unified_config  ❌ CIRCULAR

By isolating WorldModelConfig, we allow world_model modules to import just
the configuration they need without pulling in the entire unified_config tree.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator, model_validator

# OPTIMIZED (Dec 28, 2025): Defer torch import to avoid 637ms module-level cost
# torch is only needed in validators and get_torch_dtype method
if TYPE_CHECKING:
    import torch

# Lazy import to avoid circular dependency with kagami_math.g2
# from kagami_math.dimensions import get_bulk_dim, get_layer_dimensions, get_matryoshka_dimensions

logger = logging.getLogger(__name__)


# =============================================================================
# E8 BOTTLENECK CONFIG
# =============================================================================


class E8BottleneckConfig(BaseModel):
    """Configuration for E8 residual quantization bottleneck.

    Controls the adaptive E8 lattice quantization used in the
    MatryoshkaHourglass architecture.
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # Quantization depth
    training_levels: int = Field(default=4, ge=1, le=16)
    inference_levels: int = Field(default=8, ge=1, le=16)
    adaptive_levels: bool = Field(default=True)

    # Temperature annealing (for Gumbel-Softmax)
    temp_start: float = Field(default=1.0, gt=0.0)
    temp_end: float = Field(default=0.01, gt=0.0)
    temp_anneal_steps: int = Field(default=50000, ge=100)

    # Loss weights
    commitment_weight: float = Field(default=0.25, ge=0.0, le=1.0)

    # Adaptive depth settings (Dec 14, 2025)
    adaptive_e8_enabled: bool = Field(default=False)
    adaptive_e8_rate_weight: float = Field(default=0.01, ge=0.0)
    adaptive_e8_target_depth: float = Field(default=8.0, gt=0.0)
    adaptive_e8_smoothness_weight: float = Field(default=0.005, ge=0.0)
    e8_gumbel_temperature: float = Field(default=1.0, gt=0.0)

    @field_validator("temp_end")
    @classmethod
    def validate_temp_end(cls, v: float, info: Any) -> float:
        """Ensure temp_end < temp_start."""
        if "temp_start" in info.data and v >= info.data["temp_start"]:
            raise ValueError(f"temp_end ({v}) must be < temp_start ({info.data['temp_start']})")
        return v

    @field_validator("inference_levels")
    @classmethod
    def validate_inference_levels(cls, v: int, info: Any) -> int:
        """Ensure inference_levels >= training_levels."""
        if "training_levels" in info.data and v < info.data["training_levels"]:
            raise ValueError(
                f"inference_levels ({v}) must be >= training_levels ({info.data['training_levels']})"
            )
        return v


# =============================================================================
# WORLD MODEL CONFIG
# =============================================================================

# Import RSSMConfig here to avoid circular import
# We defer this import to avoid importing the entire unified_config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class WorldModelConfig(BaseModel):
    """Configuration for KagamiWorldModel.

    Central configuration for the world model, including bulk dimensions,
    hierarchical layer dimensions, and RSSM configuration.

    EXTRACTED: December 28, 2025 from unified_config.py to break circular import.
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # === Dimensional interface ===
    bulk_dim: int = Field(
        default=128, ge=32, le=4096
    )  # default_factory removed to avoid early import
    layer_dimensions: tuple[int, ...] = Field(default_factory=lambda: ())

    # Runtime
    device: str = Field(default="cpu")
    dtype: str = Field(default="float32")  # String for serialization

    # Sequence-IB (variable-length nucleus)
    ib_bottleneck_dim: int = Field(default=64, ge=8)
    ib_beta: float = Field(default=0.01, gt=0.0)
    ib_max_levels: int = Field(default=16, ge=1)
    ib_num_heads: int = Field(default=4, ge=1)
    ib_num_layers: int = Field(default=2, ge=1)

    # RSSM
    rssm: Any = Field(default=None)  # RSSMConfig, but use Any to avoid circular import
    rssm_action_dim: int = Field(default=8, ge=1)  # E8 lattice

    # Attention/MoE
    num_heads: int = Field(default=4, ge=1)
    num_experts: int = Field(default=2, ge=1)
    moe_top_k: int = Field(default=1, ge=1)

    # Fano attention (Dec 20, 2025)
    use_fano_attention: bool = Field(default=False)
    fano_attention_num_heads: int = Field(default=4, ge=1)
    fano_attention_dropout: float = Field(default=0.1, ge=0.0, le=0.5)

    # === REGULARIZATION (Dec 29, 2025) ===
    # Dropout for preventing overfitting (train/val gap)
    dropout: float = Field(default=0.1, ge=0.0, le=0.5)
    attention_dropout: float = Field(default=0.1, ge=0.0, le=0.5)

    # === GPU MIXED PRECISION (Jan 4, 2026) ===
    # Automatic mixed precision for GPU training via torch.amp.autocast
    use_amp: bool = Field(
        default=False,
        description="Enable automatic mixed precision (AMP) for GPU training. "
        "Wraps forward/training_step with torch.amp.autocast for faster training.",
    )
    amp_dtype: str = Field(
        default="float16",
        description="Data type for AMP autocast. Options: 'float16' (default) or 'bfloat16'. "
        "bfloat16 is recommended for TPU and newer GPUs (Ampere+).",
    )

    # E8 bottleneck
    e8_bottleneck: E8BottleneckConfig = Field(default_factory=E8BottleneckConfig)

    # === GENERATION CAPABILITIES (Dec 28, 2025) ===
    # Language decoder: DISABLED by default (requires massive data, use pretrained_encoders)
    enable_language_decoder: bool = Field(default=False)
    # Legacy VL-JEPA embedding-predictor decoder (optional; large head)
    enable_e8_language_decoder: bool = Field(default=False)
    # Frozen-LM language grounding + generation (CoCa/DeCap-style)
    language_model_name: str = Field(default="Qwen/Qwen2.5-0.5B")
    language_prefix_len: int = Field(default=8, ge=1, le=64)
    language_max_length: int = Field(default=64, ge=8, le=512)
    language_temperature: float = Field(default=0.07, gt=0.0)
    # Frame decoder: enables video generation from WM states
    enable_frame_decoder: bool = Field(default=True)

    # Matryoshka
    matryoshka_dims: tuple[int, ...] = Field(default_factory=lambda: ())

    # === CUDA GRAPHS (Dec 31, 2025) ===
    # CUDA Graphs for low-latency inference (requires static tensor shapes)
    use_cuda_graphs: bool = Field(
        default=False,
        description="Enable CUDA Graphs for low-latency inference. "
        "Requires CUDA device and static tensor shapes.",
    )
    cuda_graph_warmup_iterations: int = Field(
        default=3, ge=1, le=10, description="Number of warmup iterations before graph capture."
    )

    @field_validator("bulk_dim")
    @classmethod
    def validate_bulk_dim(cls, v: int) -> int:
        """Ensure bulk_dim is multiple of 8."""
        if v % 8 != 0:
            raise ValueError(f"bulk_dim must be multiple of 8, got {v}")
        return v

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Normalize and validate device."""
        v = v.strip().lower()
        if v not in {"cpu", "cuda", "mps"}:
            logger.warning(f"Unknown device {v!r}, using cpu")
            return "cpu"
        if v == "cuda":
            import torch  # Lazy import for device detection

            if not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                return "cpu"
        return v

    @field_validator("dtype")
    @classmethod
    def validate_dtype(cls, v: str) -> str:
        """Validate dtype string."""
        valid_dtypes = {"float16", "float32", "bfloat16"}
        if v not in valid_dtypes:
            raise ValueError(f"dtype must be in {valid_dtypes}, got {v}")
        return v

    @field_validator("amp_dtype")
    @classmethod
    def validate_amp_dtype(cls, v: str) -> str:
        """Validate AMP dtype string."""
        valid_amp_dtypes = {"float16", "bfloat16"}
        if v not in valid_amp_dtypes:
            raise ValueError(f"amp_dtype must be in {valid_amp_dtypes}, got {v}")
        return v

    @model_validator(mode="after")
    def derive_dimensions(self) -> WorldModelConfig:
        """Derive layer_dimensions and matryoshka_dims from bulk_dim if not set[Any]."""
        # Lazy import to avoid circular dependency with kagami_math.g2
        from kagami_math.dimensions import get_layer_dimensions, get_matryoshka_dimensions

        if not self.layer_dimensions:
            self.layer_dimensions = get_layer_dimensions(self.bulk_dim)

        if not self.matryoshka_dims:
            self.matryoshka_dims = get_matryoshka_dimensions(self.bulk_dim)

        # Validate first dimension matches bulk
        if self.layer_dimensions[0] != self.bulk_dim:
            self.layer_dimensions = (self.bulk_dim, *self.layer_dimensions[1:])

        # Set default RSSM config if not provided or ensure it's the right type
        # Import RSSMConfig lazily to break circular dependency:
        # world_model_config -> unified_config -> world_model_config
        if self.rssm is None or isinstance(self.rssm, dict):
            # Defer import until needed
            import importlib

            unified_config = importlib.import_module("kagami.core.config.unified_config")
            RSSMConfig = unified_config.RSSMConfig

            if self.rssm is None:
                self.rssm = RSSMConfig()
            elif isinstance(self.rssm, dict):
                # Convert dict[str, Any] back to RSSMConfig after deserialization
                self.rssm = RSSMConfig.model_validate(self.rssm)

        return self

    def get_torch_dtype(self) -> torch.dtype:
        """Convert dtype string to torch.dtype."""
        import torch  # Lazy import

        dtype_attr = getattr(torch, self.dtype)
        assert isinstance(dtype_attr, torch.dtype)
        return dtype_attr


__all__ = [
    "E8BottleneckConfig",
    "WorldModelConfig",
]
