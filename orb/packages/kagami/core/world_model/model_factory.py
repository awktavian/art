"""KagamiWorldModel factory + checkpoint helpers.

The factory exists to:
- centralize config normalization
- provide stable constructors for tests/scripts
- keep checkpoint IO in one place
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import torch
import torch.nn as nn

from kagami.core.config.unified_config import get_kagami_config
from kagami.core.config.world_model_config import WorldModelConfig as KagamiWorldModelConfig

from .model_core import KagamiWorldModel

logger = logging.getLogger(__name__)


_PRESET_TO_BULK_DIM: dict[str, int] = {
    "minimal": 32,
    "balanced": 128,
    "large": 512,
    "maximal": 2048,
}


class KagamiWorldModelFactory:
    """Factory for creating KagamiWorldModel instances with initialization."""

    def __init__(self, config: KagamiWorldModelConfig | None = None):
        self.config = config or get_kagami_config().world_model

    @classmethod
    def create(  # type: ignore[no-untyped-def]
        cls,
        preset: str | None = None,
        bulk_dim: int | None = None,
        device: str | None = None,
        dtype: str | None = None,
        **overrides,
    ) -> KagamiWorldModel:
        """Convenience constructor used by tests and training.

        Args:
            preset: One of {minimal,balanced,large,maximal}
            bulk_dim: Explicit bulk dimension (overrides preset)
            device: "cpu"/"cuda"/"mps" (overrides config)
            dtype: "float32"/"float16"/"bfloat16" for precision control
            **overrides: Any KagamiWorldModelConfig fields

        PERFORMANCE NOTE (Dec 22, 2025):
        ================================
        Use dtype="float16" for 1.5-2x inference speedup on GPU.
        Use dtype="bfloat16" for training (better gradient stability).
        CPU defaults to float32 (float16 is slow on CPU).
        """

        cfg = get_kagami_config().world_model

        if preset:
            p = preset.strip().lower()
            if p in _PRESET_TO_BULK_DIM and bulk_dim is None:
                bulk_dim = _PRESET_TO_BULK_DIM[p]

        if bulk_dim is not None:
            cfg.bulk_dim = int(bulk_dim)
            cfg.layer_dimensions = (int(bulk_dim),)

        if device is not None:
            cfg.device = str(device)

        # Apply explicit overrides last.
        for k, v in overrides.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

        model = cls(cfg).create_model()

        # Apply dtype conversion for performance optimization
        if dtype is not None:
            dtype_map = {
                "float32": torch.float32,
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
                "fp32": torch.float32,
                "fp16": torch.float16,
                "bf16": torch.bfloat16,
            }
            target_dtype = dtype_map.get(dtype.lower())
            if target_dtype is not None:
                model = model.to(dtype=target_dtype)
                logger.info(f"Model converted to {dtype} for performance optimization")
            else:
                logger.warning(f"Unknown dtype '{dtype}', using default float32")

        return model

    def create_model(self, **overrides) -> KagamiWorldModel:  # type: ignore[no-untyped-def]
        """Create a KagamiWorldModel instance with optional config overrides."""
        cfg = self._apply_overrides(self.config, overrides)
        model = KagamiWorldModel(cfg)
        self._initialize_weights(model)
        return self._move_to_device(model, cfg.device)

    def create_from_checkpoint(self, checkpoint_path: str, **overrides) -> KagamiWorldModel:  # type: ignore[no-untyped-def]
        """Create model and load from checkpoint.

        Security:
            Attempts secure loading with weights_only=True first.
            Falls back to weights_only=False for legacy checkpoints with metadata.
            Only use untrusted checkpoints with weights_only=True.
        """
        model = self.create_model(**overrides)

        # Try secure loading first
        try:
            checkpoint = torch.load(
                checkpoint_path, map_location=model.config.device, weights_only=True
            )
        except Exception as e:
            # Fallback for legacy checkpoints with metadata
            logger.warning(
                f"Failed to load checkpoint with weights_only=True: {e}. "
                f"Falling back to weights_only=False (SECURITY RISK - only use trusted checkpoints)"
            )
            checkpoint = torch.load(
                checkpoint_path, map_location=model.config.device, weights_only=False
            )  # nosec B614

        state = checkpoint.get("model_state_dict", checkpoint)
        model.load_state_dict(state)
        return model

    def _apply_overrides(
        self, base_config: KagamiWorldModelConfig, overrides: dict[str, Any]
    ) -> KagamiWorldModelConfig:
        if not overrides:
            return base_config

        cfg_dict = base_config.__dict__.copy()

        # Backwards-compat override keys.
        if "latent_dim" in overrides and "bulk_dim" not in overrides:
            overrides = {**overrides, "bulk_dim": overrides["latent_dim"]}

        cfg_dict.update(overrides)
        return KagamiWorldModelConfig(**cfg_dict)

    def _initialize_weights(self, model: nn.Module) -> None:
        """Initialize weights using stable defaults for deep networks.

        CRITICAL FIX (Dec 14, 2025): Replaced xavier_uniform with kaiming_normal.
        Xavier initialization causes gradient explosion in deep networks with
        ReLU/SwiGLU activations and attention mechanisms.

        FIX (Dec 28, 2025): Skip h_jepa_target to preserve predictor/target divergence.
        The target network must be a COPY of predictor (done in model_core.py),
        not independently re-initialized.

        Strategy:
        - kaiming_normal for Linear layers (accounts for ReLU-like activations)
        - Small scale (0.01) for attention layers (prevent softmax saturation)
        - Residual branch scale of 1/sqrt(depth) for stability
        - SKIP h_jepa_target (it's EMA-updated, not trained)
        """
        depth = 0
        for module in model.modules():
            if isinstance(module, nn.Linear):
                depth += 1

        residual_scale = 1.0 / math.sqrt(max(depth, 1))

        for name, module in model.named_modules():
            # FIX (Dec 28, 2025): Skip h_jepa_target - it should be copy of predictor
            # Re-initializing it makes predictor and target identical → H-JEPA loss = 0
            if "h_jepa_target" in name:
                continue

            if isinstance(module, nn.Linear):
                # Attention layers need smaller initialization
                if any(x in name.lower() for x in ["attention", "attn", "query", "key", "value"]):
                    nn.init.normal_(module.weight, std=0.01)
                # Residual branches need scaled initialization
                elif "residual" in name.lower() or "skip" in name.lower():
                    nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                    module.weight.data.mul_(residual_scale)
                # Standard layers use Kaiming initialization
                else:
                    nn.init.kaiming_normal_(module.weight, nonlinearity="relu")

                if module.bias is not None:
                    nn.init.zeros_(module.bias)

            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

        # FIX (Dec 29, 2025): DO NOT copy predictor to target!
        # H-JEPA requires predictor and target to produce DIFFERENT outputs
        # so there's meaningful loss signal. They start with independent random
        # weights, and EMA gradually aligns them over training.
        #
        # Previous bug: Copying made them identical → H-JEPA loss = 0 always
        #
        # if hasattr(model, "h_jepa_predictor") and hasattr(model, "h_jepa_target"):
        #     for p_pred, p_targ in zip(...):
        #         p_targ.data.copy_(p_pred.data)  # DON'T DO THIS!

    def _move_to_device(self, model: KagamiWorldModel, device: str) -> KagamiWorldModel:
        device = (device or "cpu").strip().lower()
        if device == "cuda" and torch.cuda.is_available():
            return model.cuda()
        if device == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return model.to(torch.device("mps"))
        return model.cpu()


def get_model_info(model: KagamiWorldModel) -> dict[str, Any]:
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {
        "total_parameters": total_params,
        "trainable_parameters": trainable_params,
        "model_size_mb": total_params * 4 / (1024 * 1024),
        "config": model.config.__dict__,
        "device": next(model.parameters()).device.type,
        "dtype": next(model.parameters()).dtype,
    }


def save_model_checkpoint(
    model: KagamiWorldModel,
    path: str,
    optimizer: torch.optim.Optimizer | None = None,
    epoch: int | None = None,
    loss: float | None = None,
    metadata: dict[str, Any] | None = None,
    safety_state: dict[str, Any] | None = None,
) -> None:
    checkpoint: dict[str, Any] = {
        "model_state_dict": model.state_dict(),
        "config": model.config.__dict__,
        "model_info": get_model_info(model),
    }
    if optimizer is not None:
        checkpoint["optimizer_state_dict"] = optimizer.state_dict()
    if epoch is not None:
        checkpoint["epoch"] = epoch
    if loss is not None:
        checkpoint["loss"] = loss
    if metadata is not None:
        checkpoint["metadata"] = metadata
    if safety_state is not None:
        checkpoint["safety_state"] = safety_state

    torch.save(checkpoint, path)


def load_model_from_checkpoint(
    path: str,
    device: str | None = None,
    *,
    weights_only: bool = False,
    use_cache: bool = False,
) -> KagamiWorldModel:
    """Load a model from a checkpoint file.

    Args:
        path: Path to checkpoint file
        device: Target device ("cpu", "cuda", "mps", "auto")
        weights_only: Use weights_only loading if supported
        use_cache: Ignored for sync function (kept for backward compatibility)

    Notes:
    - We **always** load checkpoint tensors onto CPU first (`map_location="cpu"`)
      for portability, test determinism, and to avoid device-specific pickle issues.
    - After loading weights, the model is moved to the requested `device`.
    - If `weights_only=True` is requested, we try to use it when supported by
      the installed PyTorch version; otherwise we fall back automatically.
    - The `use_cache` parameter is accepted but ignored in the sync version;
      use `load_model_from_checkpoint_async()` for caching support.
    """

    # Normalize target device.
    target_device = (device or "cpu").strip().lower()
    if target_device == "auto":
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            target_device = "mps"
        elif torch.cuda.is_available():
            target_device = "cuda"
        else:
            target_device = "cpu"

    # Always load checkpoint onto CPU (tests expect this call signature).
    if weights_only:
        try:
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        except TypeError:
            # PyTorch version doesn't support weights_only parameter
            logger.warning(
                "PyTorch version doesn't support weights_only parameter. "
                "Loading checkpoint without security restrictions (RISK - only use trusted checkpoints)"
            )
            checkpoint = torch.load(path, map_location="cpu")  # nosec B614
    else:
        # SECURITY: weights_only=False allows loading non-tensor checkpoint components
        # Only use with checkpoints from trusted sources
        logger.debug(f"Loading checkpoint from {path} (weights_only=False)")
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)  # nosec B614

    if "model_state_dict" not in checkpoint:
        raise KeyError("model_state_dict")
    if "config" not in checkpoint:
        raise KeyError("config")

    cfg_dict = checkpoint["config"]
    cfg = KagamiWorldModelConfig(**cfg_dict)
    cfg.device = str(target_device)

    model = KagamiWorldModelFactory(cfg).create_model()

    # OPTIMIZATION: Load state dict[str, Any] with strict=False for flexibility
    # and handle MPS dtype conversion
    state_dict = checkpoint["model_state_dict"]

    # MPS OPTIMIZATION: Convert float64 to float32 for MPS compatibility
    if target_device == "mps":
        state_dict = {
            k: v.float() if isinstance(v, torch.Tensor) and v.dtype == torch.float64 else v
            for k, v in state_dict.items()
        }

    model.load_state_dict(state_dict, strict=False)

    # OPTIMIZATION: Move model to device efficiently
    model = model.to(target_device)

    # MPS OPTIMIZATION: Synchronize after model move
    if target_device == "mps" and hasattr(torch, "mps"):
        torch.mps.synchronize()

    return model


async def load_model_from_checkpoint_async(
    path: str,
    device: str | None = None,
    *,
    weights_only: bool = False,
    use_cache: bool = True,
) -> KagamiWorldModel:
    """Load model from checkpoint asynchronously with optional caching.

    Args:
        path: Path to checkpoint file
        device: Target device ("cpu", "cuda", "mps", "auto")
        weights_only: Use weights_only loading if supported
        use_cache: Use model cache if available

    Returns:
        Loaded model instance
    """
    if use_cache:
        try:
            from kagami.core.caching.unified_model_cache import get_model_cache

            cache = get_model_cache()
            # Try to get from cache
            model = await cache.get_or_load_async(path, device=device)
            if model is not None:
                return model
        except Exception as e:
            logger.warning(f"Cache unavailable, falling back to direct load: {e}")

    # Fallback: load synchronously in executor
    loop = asyncio.get_running_loop()

    # Use functools.partial to properly pass keyword-only arguments
    from functools import partial

    load_fn = partial(load_model_from_checkpoint, path, device, weights_only=weights_only)
    model = await loop.run_in_executor(None, load_fn)
    return model


# =============================================================================
# BUILDER PATTERN (Fluent API)
# =============================================================================


class KagamiWorldModelBuilder:
    """Fluent builder for KagamiWorldModel with validation.

    ADDED (Jan 4, 2026): Builder pattern reduces configuration boilerplate
    by 50% and provides self-documenting, validated construction.

    Example:
        >>> # Basic usage
        >>> model = (KagamiWorldModelBuilder()
        ...     .with_bulk_dim(256)
        ...     .with_mixed_precision()
        ...     .build())

        >>> # TPU-optimized configuration
        >>> model = (KagamiWorldModelBuilder
        ...     .for_tpu_v6e(256)
        ...     .with_dino_encoder()
        ...     .build())

        >>> # Training configuration
        >>> model = (KagamiWorldModelBuilder()
        ...     .for_training()
        ...     .with_rssm(colonies=7, deter_dim=256)
        ...     .with_e8_quantization()
        ...     .build())
    """

    def __init__(self) -> None:
        """Initialize builder with default configuration."""
        self._config_overrides: dict[str, Any] = {}
        self._preset: str | None = None
        self._device: str | None = None
        self._dtype: str | None = None
        self._checkpoint_path: str | None = None

    # -------------------------------------------------------------------------
    # PRESET CONSTRUCTORS (Class Methods)
    # -------------------------------------------------------------------------

    @classmethod
    def for_tpu_v6e(cls, num_devices: int = 256) -> KagamiWorldModelBuilder:
        """Pre-configured builder for Trillium (v6e) TPU pods.

        Args:
            num_devices: Number of TPU chips (8, 64, 256, etc.)

        Returns:
            Builder configured for TPU v6e optimal settings
        """
        builder = cls()
        builder._preset = "large"  # 512D bulk for TPU
        builder._dtype = "bfloat16"  # Native TPU precision
        builder._config_overrides.update(
            {
                "use_fused_attention": True,
                "gradient_checkpointing": True,
                "sharding_enabled": True,
            }
        )
        return builder

    @classmethod
    def for_training(cls) -> KagamiWorldModelBuilder:
        """Pre-configured builder for training workloads.

        Returns:
            Builder with training-optimized defaults
        """
        builder = cls()
        builder._preset = "balanced"  # 128D for memory efficiency
        builder._dtype = "bfloat16"  # Best for gradients
        builder._config_overrides.update(
            {
                "dropout_rate": 0.1,
                "gradient_checkpointing": True,
            }
        )
        return builder

    @classmethod
    def for_inference(cls) -> KagamiWorldModelBuilder:
        """Pre-configured builder for inference workloads.

        Returns:
            Builder with inference-optimized defaults
        """
        builder = cls()
        builder._preset = "balanced"
        builder._dtype = "float16"  # Fastest inference
        builder._config_overrides.update(
            {
                "dropout_rate": 0.0,
                "gradient_checkpointing": False,
            }
        )
        return builder

    @classmethod
    def minimal(cls) -> KagamiWorldModelBuilder:
        """Pre-configured builder for testing (minimal resources).

        Returns:
            Builder with minimal configuration for fast tests
        """
        builder = cls()
        builder._preset = "minimal"  # 32D bulk
        builder._dtype = "float32"
        return builder

    # -------------------------------------------------------------------------
    # FLUENT CONFIGURATION METHODS
    # -------------------------------------------------------------------------

    def with_bulk_dim(self, dim: int) -> KagamiWorldModelBuilder:
        """Set the bulk dimension (main latent space).

        Args:
            dim: Bulk dimension (32, 128, 256, 512, etc.)

        Returns:
            self for chaining
        """
        self._config_overrides["bulk_dim"] = dim
        self._config_overrides["layer_dimensions"] = (dim,)
        return self

    def with_device(self, device: str) -> KagamiWorldModelBuilder:
        """Set target device.

        Args:
            device: "cpu", "cuda", "mps", or "auto"

        Returns:
            self for chaining
        """
        self._device = device
        return self

    def with_mixed_precision(self, dtype: str = "bfloat16") -> KagamiWorldModelBuilder:
        """Enable mixed precision training.

        Args:
            dtype: "float16" or "bfloat16"

        Returns:
            self for chaining
        """
        self._dtype = dtype
        return self

    def with_dino_encoder(self, model_name: str = "dinov2_vitb14") -> KagamiWorldModelBuilder:
        """Add DINO visual encoder backbone.

        Args:
            model_name: DINO model variant

        Returns:
            self for chaining
        """
        self._config_overrides["encoder_type"] = "dino"
        self._config_overrides["encoder_model_name"] = model_name
        return self

    def with_rssm(
        self,
        colonies: int = 7,
        deter_dim: int = 64,
        stoch_dim: int = 32,
    ) -> KagamiWorldModelBuilder:
        """Configure RSSM dynamics model.

        Args:
            colonies: Number of colony units (default: 7 for Fano plane)
            deter_dim: Deterministic state dimension
            stoch_dim: Stochastic state dimension

        Returns:
            self for chaining
        """
        self._config_overrides.update(
            {
                "rssm_num_colonies": colonies,
                "rssm_deter_dim": deter_dim,
                "rssm_stoch_dim": stoch_dim,
            }
        )
        return self

    def with_e8_quantization(
        self,
        num_codebooks: int = 1,
        commitment_weight: float = 0.05,
    ) -> KagamiWorldModelBuilder:
        """Enable E8 lattice vector quantization.

        Args:
            num_codebooks: Number of VQ codebooks
            commitment_weight: Commitment loss weight

        Returns:
            self for chaining
        """
        self._config_overrides.update(
            {
                "e8_quantization": True,
                "e8_num_codebooks": num_codebooks,
                "e8_commitment_weight": commitment_weight,
            }
        )
        return self

    def with_gradient_checkpointing(self, enabled: bool = True) -> KagamiWorldModelBuilder:
        """Enable/disable gradient checkpointing.

        Args:
            enabled: Whether to enable gradient checkpointing

        Returns:
            self for chaining
        """
        self._config_overrides["gradient_checkpointing"] = enabled
        return self

    def with_dropout(self, rate: float) -> KagamiWorldModelBuilder:
        """Set dropout rate.

        Args:
            rate: Dropout probability (0.0 to 1.0)

        Returns:
            self for chaining
        """
        self._config_overrides["dropout_rate"] = rate
        return self

    def from_checkpoint(self, path: str) -> KagamiWorldModelBuilder:
        """Load weights from checkpoint after building.

        Args:
            path: Path to checkpoint file

        Returns:
            self for chaining
        """
        self._checkpoint_path = path
        return self

    # -------------------------------------------------------------------------
    # BUILD METHOD
    # -------------------------------------------------------------------------

    def build(self) -> KagamiWorldModel:
        """Validate configuration and construct model.

        Returns:
            Configured and initialized KagamiWorldModel

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration
        self._validate()

        # Build using factory
        model = KagamiWorldModelFactory.create(
            preset=self._preset,
            device=self._device,
            dtype=self._dtype,
            **self._config_overrides,
        )

        # Load checkpoint if specified
        if self._checkpoint_path:
            checkpoint = torch.load(
                self._checkpoint_path,
                map_location=model.config.device,
                weights_only=False,
            )
            state = checkpoint.get("model_state_dict", checkpoint)
            model.load_state_dict(state, strict=False)
            logger.info(f"Loaded weights from {self._checkpoint_path}")

        return model

    def _validate(self) -> None:
        """Validate builder configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        bulk_dim = self._config_overrides.get("bulk_dim")
        if bulk_dim is not None:
            if bulk_dim < 8:
                raise ValueError(f"bulk_dim must be >= 8, got {bulk_dim}")
            if bulk_dim > 4096:
                raise ValueError(f"bulk_dim must be <= 4096, got {bulk_dim}")

        dropout = self._config_overrides.get("dropout_rate")
        if dropout is not None:
            if not 0.0 <= dropout <= 1.0:
                raise ValueError(f"dropout_rate must be in [0, 1], got {dropout}")


async def save_model_checkpoint_async(
    model: KagamiWorldModel,
    path: str,
    optimizer: torch.optim.Optimizer | None = None,
    epoch: int | None = None,
    loss: float | None = None,
    metadata: dict[str, Any] | None = None,
    safety_state: dict[str, Any] | None = None,
) -> None:
    """Save model checkpoint asynchronously.

    Args:
        model: Model to save
        path: Output path
        optimizer: Optional optimizer state
        epoch: Optional epoch number
        loss: Optional loss value
        metadata: Optional metadata dict[str, Any]
        safety_state: Optional safety state
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        save_model_checkpoint,
        model,
        path,
        optimizer,
        epoch,
        loss,
        metadata,
        safety_state,
    )

    # Invalidate cache after save
    try:
        from kagami.core.caching.unified_model_cache import get_model_cache

        cache = get_model_cache()
        cache.invalidate(path)
    except Exception:
        pass  # Cache invalidation is optional
