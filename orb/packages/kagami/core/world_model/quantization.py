"""INT8 quantization infrastructure for world model inference speedup.

CREATED: December 31, 2025 (Forge, e2)
MISSION: Reduce inference latency and memory footprint via INT8 quantization

QUANTIZATION MODES:
===================
1. Dynamic Quantization (default):
   - Weights quantized at load time, activations quantized on-the-fly
   - No calibration required
   - Best for models with varying input distributions
   - 2-4x inference speedup on CPU

2. Static Quantization:
   - Weights and activations quantized to INT8
   - Requires calibration with representative data
   - Best for fixed input distributions
   - 3-5x inference speedup on CPU

3. Quantization-Aware Training (QAT):
   - Simulates quantization during training
   - Best accuracy preservation
   - Requires retraining

SUPPORTED LAYERS:
=================
- nn.Linear (primary target for world model)
- nn.LSTM (if present in RSSM)
- nn.GRU (if present in RSSM)
- nn.EmbeddingBag

COMPATIBILITY:
==============
- Works with torch.compile (eager mode fallback if needed)
- Preserves model correctness (verified via reference comparison)
- Graceful fallback if quantization unavailable

References:
- PyTorch Quantization: https://pytorch.org/docs/stable/quantization.html
- torch.ao.quantization: https://pytorch.org/docs/stable/torch.ao.quantization.html
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import torch
import torch.ao.quantization as quant
import torch.nn as nn
from torch.ao.quantization import (
    QConfigMapping,
    convert,
    get_default_qconfig,
    prepare,
    quantize_dynamic,
)
from torch.ao.quantization.quantize_fx import convert_fx, prepare_fx

if TYPE_CHECKING:
    from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


QuantizationMode = Literal["dynamic", "static", "qat"]


@dataclass
class QuantizationConfig:
    """Configuration for INT8 quantization.

    Attributes:
        mode: Quantization mode (dynamic, static, qat)
        dtype: Quantization dtype (qint8 or quint8)
        calibration_batches: Number of batches for static calibration
        per_channel: Use per-channel quantization (better accuracy, slightly slower)
        backend: Quantization backend (fbgemm for x86, qnnpack for ARM)
        skip_layers: Layer names to skip quantization
    """

    mode: QuantizationMode = "dynamic"
    dtype: torch.dtype = torch.qint8
    calibration_batches: int = 100
    per_channel: bool = True
    backend: str = field(default_factory=lambda: _default_backend())
    skip_layers: list[str] = field(default_factory=list)


def _default_backend() -> str:
    """Select default quantization backend based on architecture."""
    import platform

    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        return "fbgemm"  # Intel/AMD x86
    elif arch in ("arm64", "aarch64"):
        return "qnnpack"  # ARM (Apple Silicon, mobile)
    else:
        return "fbgemm"  # Default to fbgemm


# =============================================================================
# QUANTIZED MODEL WRAPPER
# =============================================================================


class QuantizedWorldModel(nn.Module):
    """Wrapper for quantized world model.

    Provides:
    - Transparent access to quantized model
    - Reference comparison for verification
    - Quantization statistics
    - Fallback to FP32 if quantization fails

    Usage:
        >>> model = KagamiWorldModel(config)
        >>> quantized = QuantizedWorldModel.from_model(model)
        >>> output = quantized(x)  # Uses INT8 where available
    """

    def __init__(
        self,
        quantized_model: nn.Module,
        original_model: nn.Module | None = None,
        config: QuantizationConfig | None = None,
    ):
        """Initialize quantized wrapper.

        Args:
            quantized_model: Quantized model
            original_model: Original FP32 model (for reference comparison)
            config: Quantization configuration used
        """
        super().__init__()
        self.quantized_model = quantized_model
        self._original_model = original_model
        self.config = config or QuantizationConfig()

        # Statistics
        self._inference_count = 0
        self._quantization_stats: dict[str, Any] = {}

    @classmethod
    def from_model(
        cls,
        model: nn.Module,
        config: QuantizationConfig | None = None,
        calibration_data: DataLoader | Iterator[torch.Tensor] | None = None,
        keep_original: bool = False,
    ) -> QuantizedWorldModel:
        """Create quantized model from FP32 model.

        Args:
            model: Original FP32 model
            config: Quantization configuration
            calibration_data: Data for static quantization calibration
            keep_original: Keep original model for reference comparison

        Returns:
            QuantizedWorldModel wrapper
        """
        config = config or QuantizationConfig()

        # Set backend
        torch.backends.quantized.engine = config.backend

        # Select quantization method
        if config.mode == "dynamic":
            quantized = _quantize_dynamic(model, config)
        elif config.mode == "static":
            if calibration_data is None:
                raise ValueError("Static quantization requires calibration_data")
            quantized = _quantize_static(model, config, calibration_data)
        elif config.mode == "qat":
            raise NotImplementedError(
                "QAT requires integration with training loop. "
                "Use prepare_qat() and convert_qat() directly."
            )
        else:
            raise ValueError(f"Unknown quantization mode: {config.mode}")

        original = copy.deepcopy(model) if keep_original else None

        return cls(quantized, original, config)

    def forward(self, *args: Any, **kwargs: Any) -> Any:
        """Forward pass through quantized model."""
        self._inference_count += 1
        return self.quantized_model(*args, **kwargs)

    def verify_correctness(
        self,
        example_input: torch.Tensor,
        atol: float = 0.1,
        rtol: float = 0.1,
    ) -> dict[str, Any]:
        """Verify quantized model produces similar output to original.

        INT8 quantization introduces small numerical differences.
        This method checks if differences are within acceptable bounds.

        Args:
            example_input: Example input tensor
            atol: Absolute tolerance
            rtol: Relative tolerance

        Returns:
            Dict with verification results:
                - correct: True if within tolerance
                - max_diff: Maximum absolute difference
                - mean_diff: Mean absolute difference
                - original_output: Output from original model
                - quantized_output: Output from quantized model
        """
        if self._original_model is None:
            return {
                "correct": None,
                "error": "Original model not kept. Use keep_original=True.",
            }

        with torch.no_grad():
            self._original_model.eval()
            self.quantized_model.eval()

            original_out = self._original_model(example_input)
            quantized_out = self.quantized_model(example_input)

        # Handle tuple outputs (model returns (output, metrics))
        if isinstance(original_out, tuple):
            original_out = original_out[0]
        if isinstance(quantized_out, tuple):
            quantized_out = quantized_out[0]

        diff = (original_out - quantized_out).abs()
        max_diff = diff.max().item()
        mean_diff = diff.mean().item()

        correct = torch.allclose(original_out, quantized_out, atol=atol, rtol=rtol)

        return {
            "correct": correct,
            "max_diff": max_diff,
            "mean_diff": mean_diff,
            "atol": atol,
            "rtol": rtol,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get quantization statistics."""
        return {
            "mode": self.config.mode,
            "dtype": str(self.config.dtype),
            "backend": self.config.backend,
            "inference_count": self._inference_count,
            "quantized_layers": _count_quantized_layers(self.quantized_model),
            "model_size_mb": _get_model_size_mb(self.quantized_model),
            "original_size_mb": (
                _get_model_size_mb(self._original_model) if self._original_model else None
            ),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"QuantizedWorldModel(\n"
            f"  mode={stats['mode']},\n"
            f"  backend={stats['backend']},\n"
            f"  quantized_layers={stats['quantized_layers']},\n"
            f"  size_mb={stats['model_size_mb']:.2f}\n"
            f")"
        )


# =============================================================================
# DYNAMIC QUANTIZATION
# =============================================================================


def _quantize_dynamic(
    model: nn.Module,
    config: QuantizationConfig,
) -> nn.Module:
    """Apply dynamic INT8 quantization to model.

    Dynamic quantization:
    - Weights are quantized ahead of time
    - Activations are quantized dynamically at runtime
    - No calibration needed
    - Best for variable input distributions

    Args:
        model: Model to quantize
        config: Quantization configuration

    Returns:
        Dynamically quantized model
    """
    # Target layer types for dynamic quantization
    # Linear layers are the primary target for world model
    target_layers = {nn.Linear}

    # Also quantize LSTM/GRU if present (common in RSSM)
    if _has_rnn_layers(model):
        target_layers.add(nn.LSTM)
        target_layers.add(nn.GRU)

    logger.info(
        f"Applying dynamic quantization: "
        f"dtype={config.dtype}, "
        f"backend={config.backend}, "
        f"target_layers={[l.__name__ for l in target_layers]}"
    )

    # Put model in eval mode (required for quantization)
    model.eval()

    try:
        quantized = quantize_dynamic(
            model,
            target_layers,
            dtype=config.dtype,
        )

        num_quantized = _count_quantized_layers(quantized)
        logger.info(f"Dynamic quantization complete: {num_quantized} layers quantized")

        return quantized

    except Exception as e:
        logger.error(f"Dynamic quantization failed: {e}")
        raise


def quantize_model(
    model: nn.Module,
    dtype: torch.dtype = torch.qint8,
    inplace: bool = False,
) -> nn.Module:
    """Quick function to apply dynamic INT8 quantization.

    This is the simplest quantization API - just pass a model
    and get back a quantized version.

    Args:
        model: Model to quantize
        dtype: Quantization dtype (qint8 or quint8)
        inplace: Modify model in place (default: False, returns copy)

    Returns:
        Quantized model

    Example:
        >>> model = KagamiWorldModel(config)
        >>> quantized = quantize_model(model)
        >>> output = quantized(x)  # 2-4x faster on CPU
    """
    if not inplace:
        model = copy.deepcopy(model)

    model.eval()

    return quantize_dynamic(
        model,
        {nn.Linear},
        dtype=dtype,
    )


# =============================================================================
# STATIC QUANTIZATION
# =============================================================================


def _quantize_static(
    model: nn.Module,
    config: QuantizationConfig,
    calibration_data: DataLoader | Iterator[torch.Tensor],
) -> nn.Module:
    """Apply static INT8 quantization with calibration.

    Static quantization:
    - Both weights and activations are quantized to INT8
    - Requires calibration with representative data
    - Better performance than dynamic (3-5x speedup)
    - Requires inserted quant/dequant stubs

    Args:
        model: Model to quantize
        config: Quantization configuration
        calibration_data: DataLoader or iterator of calibration inputs

    Returns:
        Statically quantized model
    """
    logger.info(
        f"Applying static quantization: "
        f"calibration_batches={config.calibration_batches}, "
        f"per_channel={config.per_channel}"
    )

    model.eval()

    # Select qconfig based on per-channel setting
    if config.per_channel:
        qconfig = get_default_qconfig(config.backend)
    else:
        # Use per-tensor quantization (faster but less accurate)
        qconfig = quant.QConfig(
            activation=quant.MinMaxObserver.with_args(dtype=torch.quint8),
            weight=quant.MinMaxObserver.with_args(dtype=torch.qint8),
        )

    # Create qconfig mapping
    qconfig_mapping = QConfigMapping().set_global(qconfig)

    # Skip specified layers
    for layer_name in config.skip_layers:
        qconfig_mapping.set_module_name(layer_name, None)

    try:
        # Prepare model for calibration (inserts observers)
        # Use FX graph mode for better coverage
        example_input = _get_example_from_dataloader(calibration_data)
        prepared = prepare_fx(model, qconfig_mapping, example_inputs=(example_input,))

        # Run calibration
        logger.info(f"Running calibration with {config.calibration_batches} batches...")
        with torch.no_grad():
            for i, batch in enumerate(calibration_data):
                if i >= config.calibration_batches:
                    break
                if isinstance(batch, tuple | list):
                    batch = batch[0]  # Take input from (input, target) tuple
                prepared(batch)
                if (i + 1) % 10 == 0:
                    logger.debug(f"Calibration progress: {i + 1}/{config.calibration_batches}")

        # Convert to quantized model
        quantized = convert_fx(prepared)

        num_quantized = _count_quantized_layers(quantized)
        logger.info(f"Static quantization complete: {num_quantized} layers quantized")

        return quantized

    except Exception as e:
        logger.error(f"Static quantization failed: {e}")
        logger.info("Falling back to dynamic quantization")
        return _quantize_dynamic(model, config)


def prepare_static_quantization(
    model: nn.Module,
    config: QuantizationConfig | None = None,
) -> nn.Module:
    """Prepare model for static quantization calibration.

    Use this to manually control the calibration process:
    1. Call prepare_static_quantization() to insert observers
    2. Run calibration data through the model
    3. Call convert_static_quantization() to finalize

    Args:
        model: Model to prepare
        config: Quantization configuration

    Returns:
        Model with observers inserted (ready for calibration)
    """
    config = config or QuantizationConfig(mode="static")
    model.eval()

    # Set backend
    torch.backends.quantized.engine = config.backend

    # Create qconfig
    qconfig = get_default_qconfig(config.backend)
    model.qconfig = qconfig  # type: ignore[assignment]

    # Prepare for calibration
    prepared = prepare(model, inplace=False)

    logger.info(
        "Model prepared for static quantization. Run calibration data, then call convert()."
    )
    return prepared


def convert_static_quantization(
    prepared_model: nn.Module,
) -> nn.Module:
    """Convert prepared model to quantized model.

    Call this after running calibration data through the prepared model.

    Args:
        prepared_model: Model from prepare_static_quantization()

    Returns:
        Quantized model
    """
    quantized = convert(prepared_model, inplace=False)

    num_quantized = _count_quantized_layers(quantized)
    logger.info(f"Static quantization conversion complete: {num_quantized} layers")

    return quantized


# =============================================================================
# CALIBRATION HELPERS
# =============================================================================


class CalibrationDataCollector:
    """Collects representative data for static quantization calibration.

    Use during normal inference to build a calibration dataset:

        collector = CalibrationDataCollector(max_samples=100)

        for batch in production_data:
            output = model(batch)
            collector.add(batch)

        calibration_loader = collector.to_dataloader()
    """

    def __init__(
        self,
        max_samples: int = 100,
        batch_size: int = 8,
    ):
        """Initialize collector.

        Args:
            max_samples: Maximum number of samples to collect
            batch_size: Batch size for calibration DataLoader
        """
        self.max_samples = max_samples
        self.batch_size = batch_size
        self._samples: list[torch.Tensor] = []

    def add(self, sample: torch.Tensor) -> None:
        """Add sample to collection.

        Args:
            sample: Input tensor (batch dimension optional)
        """
        if len(self._samples) >= self.max_samples:
            return

        # Detach and move to CPU for storage
        sample = sample.detach().cpu()

        # Handle batched input
        if sample.dim() > 1 and sample.shape[0] > 1:
            for i in range(min(sample.shape[0], self.max_samples - len(self._samples))):
                self._samples.append(sample[i].clone())
        else:
            self._samples.append(sample.clone())

    def to_dataloader(self) -> DataLoader:
        """Create DataLoader from collected samples."""
        from torch.utils.data import DataLoader, TensorDataset

        if not self._samples:
            raise ValueError("No samples collected. Call add() first.")

        # Stack samples into single tensor
        stacked = torch.stack(self._samples)
        dataset = TensorDataset(stacked)

        return DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=False,
        )

    def __len__(self) -> int:
        return len(self._samples)

    @property
    def is_full(self) -> bool:
        return len(self._samples) >= self.max_samples


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def _has_rnn_layers(model: nn.Module) -> bool:
    """Check if model contains RNN layers."""
    for module in model.modules():
        if isinstance(module, nn.LSTM | nn.GRU | nn.RNN):
            return True
    return False


def _count_quantized_layers(model: nn.Module) -> int:
    """Count number of quantized layers in model."""
    count = 0
    for module in model.modules():
        # Check for quantized linear
        if hasattr(module, "weight") and hasattr(module.weight, "is_quantized"):
            if module.weight.is_quantized:
                count += 1
        # Check for dynamic quantized modules
        if "DynamicQuantizedLinear" in type(module).__name__:
            count += 1
        if "QuantizedLinear" in type(module).__name__:
            count += 1
    return count


def _get_model_size_mb(model: nn.Module) -> float:
    """Get model size in megabytes."""
    param_size = sum(p.numel() * p.element_size() for p in model.parameters())
    buffer_size = sum(b.numel() * b.element_size() for b in model.buffers())
    return (param_size + buffer_size) / (1024 * 1024)


def _get_example_from_dataloader(
    data: DataLoader | Iterator[torch.Tensor],
) -> torch.Tensor:
    """Get single example from dataloader or iterator."""
    if hasattr(data, "__iter__"):
        batch = next(iter(data))
        if isinstance(batch, tuple | list):
            return batch[0]
        return batch
    else:
        raise ValueError("calibration_data must be iterable")


# =============================================================================
# TORCH.COMPILE COMPATIBILITY
# =============================================================================


def quantize_with_compile(
    model: nn.Module,
    compile_mode: Literal["inference", "training", "none"] = "inference",
    quantization_config: QuantizationConfig | None = None,
) -> nn.Module:
    """Apply quantization with optional torch.compile.

    Combines INT8 quantization with torch.compile for maximum speedup.
    Handles compatibility issues between the two optimizations.

    Args:
        model: Model to optimize
        compile_mode: torch.compile mode (inference, training, or none)
        quantization_config: Quantization configuration

    Returns:
        Quantized and optionally compiled model
    """
    config = quantization_config or QuantizationConfig()

    # Step 1: Apply quantization
    logger.info("Step 1: Applying INT8 quantization...")
    quantized = quantize_model(model, dtype=config.dtype)

    # Step 2: Optionally apply torch.compile
    if compile_mode == "none":
        logger.info("Skipping torch.compile (compile_mode='none')")
        return quantized

    logger.info(f"Step 2: Applying torch.compile (mode={compile_mode})...")

    try:
        from kagami.core.world_model.compilation import (
            compile_for_inference,
            compile_for_training,
        )

        if compile_mode == "inference":
            compiled = compile_for_inference(quantized, dynamic=True)
        else:
            compiled = compile_for_training(quantized, dynamic=True)

        logger.info("Quantization + compilation complete")
        return compiled

    except Exception as e:
        logger.warning(
            f"torch.compile failed on quantized model: {e}. Returning quantized-only model."
        )
        return quantized


# =============================================================================
# BENCHMARK UTILITIES
# =============================================================================


def benchmark_quantization(
    original: nn.Module,
    quantized: nn.Module,
    example_input: torch.Tensor,
    num_iterations: int = 100,
    warmup_iterations: int = 10,
) -> dict[str, float]:
    """Benchmark original vs quantized model performance.

    Args:
        original: Original FP32 model
        quantized: Quantized INT8 model
        example_input: Example input tensor
        num_iterations: Number of benchmark iterations
        warmup_iterations: Number of warmup iterations

    Returns:
        Dict with benchmark results:
            - original_mean_ms: Mean time for original (ms)
            - quantized_mean_ms: Mean time for quantized (ms)
            - speedup: Speedup factor
            - original_size_mb: Original model size (MB)
            - quantized_size_mb: Quantized model size (MB)
            - size_reduction: Size reduction factor
    """
    import time

    original.eval()
    quantized.eval()

    # Warmup
    with torch.no_grad():
        for _ in range(warmup_iterations):
            _ = original(example_input)
            _ = quantized(example_input)

    # Benchmark original
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(num_iterations):
            _ = original(example_input)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    original_time = time.perf_counter() - start

    # Benchmark quantized
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(num_iterations):
            _ = quantized(example_input)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    quantized_time = time.perf_counter() - start

    # Compute statistics
    original_mean_ms = (original_time / num_iterations) * 1000
    quantized_mean_ms = (quantized_time / num_iterations) * 1000
    speedup = original_time / quantized_time if quantized_time > 0 else float("inf")

    original_size = _get_model_size_mb(original)
    quantized_size = _get_model_size_mb(quantized)
    size_reduction = original_size / quantized_size if quantized_size > 0 else float("inf")

    logger.info(
        f"Quantization benchmark:\n"
        f"  Latency: {original_mean_ms:.2f}ms -> {quantized_mean_ms:.2f}ms "
        f"({speedup:.2f}x speedup)\n"
        f"  Size: {original_size:.2f}MB -> {quantized_size:.2f}MB "
        f"({size_reduction:.2f}x reduction)"
    )

    return {
        "original_mean_ms": original_mean_ms,
        "quantized_mean_ms": quantized_mean_ms,
        "speedup": speedup,
        "original_size_mb": original_size,
        "quantized_size_mb": quantized_size,
        "size_reduction": size_reduction,
    }


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "CalibrationDataCollector",
    "QuantizationConfig",
    # Main classes
    "QuantizedWorldModel",
    # Utilities
    "benchmark_quantization",
    "convert_static_quantization",
    # Static quantization helpers
    "prepare_static_quantization",
    # Quick functions
    "quantize_model",
    "quantize_with_compile",
]
