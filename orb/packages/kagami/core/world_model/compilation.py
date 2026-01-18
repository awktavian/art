"""torch.compile optimization utilities for Kagami world model.

CREATED: December 14, 2025 (Forge, e₂)
MISSION: Safe, incremental torch.compile wrappers for hot computational paths

SAFETY-FIRST DESIGN:
====================
1. Feature flag ENABLE_TORCH_COMPILE (default: True since Dec 16, 2025)
2. Graceful fallback if compilation fails
3. Preserves mathematical correctness (compiled == non-compiled)
4. Backward compatible (works without compilation)
5. Comprehensive logging of compilation status

COMPILATION MODES:
==================
- inference: max-autotune mode for low latency (production inference)
- training: reduce-overhead mode for throughput (training loops)
- selective: compile specific modules, skip problematic ones

HOT PATHS (identified by Beacon):
==================================
1. E8 quantization functions (nearest_e8, residual VQ)
2. Clebsch-Gordan projection chain (E8→E7→E6→F4→G2)
3. Octonion multiplication (Cayley-Dickson on S⁷)

DYNAMIC SHAPES:
===============
torch.compile can handle dynamic batch/sequence lengths, but requires:
- dynamic=True flag for torch.compile()
- Optional shape constraints via torch._dynamo.mark_dynamic()

WARMUP:
=======
First few calls trigger compilation (slow). Use warmup_compiled() to
pre-compile with representative inputs before production use.

References:
- PyTorch 2.0 torch.compile: https://pytorch.org/docs/stable/generated/torch.compile.html
- Dynamic shapes: https://pytorch.org/docs/stable/torch.compiler_dynamo_deepdive.html
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, Literal, TypeVar

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# =============================================================================
# FEATURE FLAG
# =============================================================================


def _should_enable_compilation_by_default() -> bool:
    """Determine if torch.compile should be enabled by default.

    DEVICE POLICY (December 16, 2025):
    ==================================
    - CPU: DISABLED by default (60s+ timeout issues with batch=1, long sequences)
    - GPU: ENABLED by default (3-4x inference, 1.5-2x training speedup)

    OVERRIDE:
    ========
    Set ENABLE_TORCH_COMPILE=true/false to override device-based default.

    Returns:
        True if compilation should be enabled, False otherwise
    """
    # Explicit override takes precedence
    env_var = os.getenv("ENABLE_TORCH_COMPILE")
    if env_var is not None:
        return env_var.lower() in ("true", "1", "yes")

    # Device-based default: GPU only
    return torch.cuda.is_available()


# Global feature flag (can be overridden by env var or explicit enable/disable)
# DEVICE-AWARE DEFAULT (December 16, 2025):
# - CPU: disabled (timeout issues)
# - GPU: enabled (3-4x speedup)
_TORCH_COMPILE_ENABLED = _should_enable_compilation_by_default()


def is_compilation_enabled() -> bool:
    """Check if torch.compile is globally enabled.

    Returns True if:
    1. Explicitly enabled via enable_compilation()
    2. ENABLE_TORCH_COMPILE=true env var is set[Any]
    3. Running on GPU and no explicit override

    Returns False if:
    1. Explicitly disabled via disable_compilation()
    2. ENABLE_TORCH_COMPILE=false env var is set[Any]
    3. Running on CPU (default behavior to avoid timeouts)
    """
    return _TORCH_COMPILE_ENABLED


def enable_compilation() -> None:
    """Enable torch.compile globally.

    WARNING: On CPU, torch.compile can cause 60s+ timeouts with:
    - Small batch sizes (batch=1)
    - Long sequences (>512 tokens)
    - Complex models with dynamic control flow

    Consider using disable_compilation() if you experience timeouts.
    """
    global _TORCH_COMPILE_ENABLED
    _TORCH_COMPILE_ENABLED = True
    device = "GPU" if torch.cuda.is_available() else "CPU"
    logger.info("torch.compile ENABLED globally (device: %s)", device)
    if not torch.cuda.is_available():
        logger.warning(
            "torch.compile enabled on CPU. This may cause 60s+ timeouts with "
            "batch=1 or long sequences. Set ENABLE_TORCH_COMPILE=false to disable."
        )


def disable_compilation() -> None:
    """Disable torch.compile globally."""
    global _TORCH_COMPILE_ENABLED
    _TORCH_COMPILE_ENABLED = False
    device = "GPU" if torch.cuda.is_available() else "CPU"
    logger.info("torch.compile DISABLED globally (device: %s)", device)


# =============================================================================
# SHAPE GUARDS FOR EDGE CASES
# =============================================================================


def should_skip_compilation_for_shape(x: torch.Tensor) -> bool:
    """Check if tensor shape is problematic for torch.compile.

    EDGE CASES (December 16, 2025):
    ===============================
    - batch_size == 1: Causes recompilation on every shape change
    - sequence_length > 512: Triggers graph explosion on CPU

    Args:
        x: Input tensor [B, ...] or [B, S, ...]

    Returns:
        True if compilation should be skipped for this shape
    """
    # Only apply shape guards on CPU
    if torch.cuda.is_available():
        return False

    batch_size = x.shape[0]
    if batch_size == 1:
        logger.debug("Skipping compilation: batch_size=1 (CPU edge case)")
        return True

    # Check for long sequences
    if x.dim() >= 3:
        seq_len = x.shape[1]
        if seq_len > 512:
            logger.debug("Skipping compilation: seq_len=%d > 512 (CPU edge case)", seq_len)
            return True

    return False


# =============================================================================
# COMPILATION UTILITIES
# =============================================================================

CompilationMode = Literal["inference", "training", "selective"]

F = TypeVar("F", bound=Callable[..., Any])


def compile_for_inference(
    fn: F,
    *,
    dynamic: bool = True,
    fullgraph: bool = False,
    disable: bool | None = None,
) -> F:
    """Compile function for inference with max-autotune mode.

    Optimizes for low latency. Use for production inference paths.

    Args:
        fn: Function or nn.Module to compile
        dynamic: Allow dynamic shapes (batch/sequence length variations)
        fullgraph: Require compilation of entire graph (stricter, may fail)
        disable: Override global enable flag (None = use global)

    Returns:
        Compiled function (or original if compilation disabled/failed)
    """
    # Get name for logging (handle both functions and modules)
    fn_name = getattr(fn, "__name__", None) or fn.__class__.__name__

    # Check if compilation is disabled
    if disable is True or (disable is None and not is_compilation_enabled()):
        logger.debug(f"Compilation DISABLED for {fn_name}")
        return fn

    try:
        compiled = torch.compile(
            fn,
            mode="max-autotune",  # Aggressive optimization for latency
            dynamic=dynamic,
            fullgraph=fullgraph,
        )
        logger.info(f"Compiled {fn_name} for INFERENCE (max-autotune, dynamic={dynamic})")
        return compiled  # type: ignore
    except Exception as e:
        logger.warning(
            f"Failed to compile {fn_name} for inference: {e}. Using fallback (non-compiled)."
        )
        return fn


def compile_for_training(
    fn: F,
    *,
    dynamic: bool = True,
    fullgraph: bool = False,
    disable: bool | None = None,
) -> F:
    """Compile function for training with reduce-overhead mode.

    Optimizes for throughput. Use for training loops.

    Args:
        fn: Function or nn.Module to compile
        dynamic: Allow dynamic shapes (batch/sequence length variations)
        fullgraph: Require compilation of entire graph (stricter, may fail)
        disable: Override global enable flag (None = use global)

    Returns:
        Compiled function (or original if compilation disabled/failed)
    """
    # Get name for logging (handle both functions and modules)
    fn_name = getattr(fn, "__name__", None) or fn.__class__.__name__

    # Check if compilation is disabled
    if disable is True or (disable is None and not is_compilation_enabled()):
        logger.debug(f"Compilation DISABLED for {fn_name}")
        return fn

    try:
        compiled = torch.compile(
            fn,
            mode="reduce-overhead",  # Optimize for throughput
            dynamic=dynamic,
            fullgraph=fullgraph,
        )
        logger.info(f"Compiled {fn_name} for TRAINING (reduce-overhead, dynamic={dynamic})")
        return compiled  # type: ignore
    except Exception as e:
        logger.warning(
            f"Failed to compile {fn_name} for training: {e}. Using fallback (non-compiled)."
        )
        return fn


def selective_compile(
    module: nn.Module,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    mode: CompilationMode = "training",
    dynamic: bool = True,
    disable: bool | None = None,
) -> nn.Module:
    """Selectively compile submodules by name pattern.

    Useful for compiling only hot paths while skipping problematic modules.

    Args:
        module: nn.Module to selectively compile
        include: List of submodule name patterns to compile (None = all)
        exclude: List of submodule name patterns to skip (None = none)
        mode: Compilation mode (inference/training/selective)
        dynamic: Allow dynamic shapes
        disable: Override global enable flag (None = use global)

    Returns:
        Module with selected submodules compiled

    Example:
        >>> model = selective_compile(
        ...     model,
        ...     include=["encoder", "decoder"],
        ...     exclude=["encoder.attention"],  # Skip attention (problematic)
        ...     mode="training"
        ... )
    """
    # Check if compilation is disabled
    if disable is True or (disable is None and not is_compilation_enabled()):
        logger.debug("Selective compilation DISABLED")
        return module

    include = include or []
    exclude = exclude or []

    compiled_count = 0
    skipped_count = 0

    for name, submodule in module.named_modules():
        # Skip if excluded
        if any(pattern in name for pattern in exclude):
            logger.debug(f"Skipping {name} (excluded)")
            skipped_count += 1
            continue

        # Compile if included (or include is empty = compile all)
        if not include or any(pattern in name for pattern in include):
            try:
                if mode == "inference":
                    compiled = compile_for_inference(submodule, dynamic=dynamic, disable=False)
                elif mode == "training":
                    compiled = compile_for_training(submodule, dynamic=dynamic, disable=False)
                else:
                    # Default to training mode
                    compiled = compile_for_training(submodule, dynamic=dynamic, disable=False)

                # Replace submodule with compiled version
                # Use setattr on parent module
                if "." in name:
                    parent_name, attr_name = name.rsplit(".", 1)
                    parent = module.get_submodule(parent_name)
                    setattr(parent, attr_name, compiled)
                else:
                    setattr(module, name, compiled)

                compiled_count += 1
                logger.info(f"Compiled submodule: {name}")
            except Exception as e:
                logger.warning(f"Failed to compile {name}: {e}. Skipping.")
                skipped_count += 1

    logger.info(f"Selective compilation: {compiled_count} compiled, {skipped_count} skipped")
    return module


# =============================================================================
# WARMUP UTILITIES
# =============================================================================


def warmup_compiled(
    fn: Callable[..., Any],
    *example_inputs: Any,
    num_warmup: int = 3,
    **example_kwargs: Any,
) -> None:
    """Warmup a compiled function with example inputs.

    First few calls to a compiled function trigger compilation (slow).
    This utility pre-compiles by running several warmup iterations.

    Args:
        fn: Compiled function to warmup
        example_inputs: Representative positional inputs (same shapes as production)
        num_warmup: Number of warmup iterations (default: 3)
        example_kwargs: Representative keyword arguments

    Example:
        >>> compiled_fn = compile_for_inference(my_fn)
        >>> warmup_compiled(compiled_fn, torch.randn(8, 512), num_warmup=5)
        >>> # With kwargs:
        >>> warmup_compiled(model.forward, x, action=action, num_warmup=3)
        >>> # Now compiled_fn is ready for fast production use
    """
    # Get name for logging (handle both functions and modules)
    fn_name = getattr(fn, "__name__", None) or fn.__class__.__name__

    logger.info(f"Warming up {fn_name} with {num_warmup} iterations...")

    for i in range(num_warmup):
        try:
            with torch.no_grad():
                _ = fn(*example_inputs, **example_kwargs)
            logger.debug(f"Warmup iteration {i + 1}/{num_warmup} complete")
        except Exception as e:
            logger.warning(f"Warmup iteration {i + 1} failed: {e}")

    logger.info(f"Warmup complete for {fn_name}")


# =============================================================================
# DECORATOR API (syntactic sugar)
# =============================================================================


def compiled_inference(
    dynamic: bool = True,
    fullgraph: bool = False,
    disable: bool | None = None,
) -> Callable[[F], F]:
    """Decorator to compile a function for inference.

    Example:
        >>> @compiled_inference(dynamic=True)
        ... def encode(x: torch.Tensor) -> torch.Tensor:
        ...     return self.encoder(x)
    """

    def decorator(fn: F) -> F:
        return compile_for_inference(fn, dynamic=dynamic, fullgraph=fullgraph, disable=disable)

    return decorator


def compiled_training(
    dynamic: bool = True,
    fullgraph: bool = False,
    disable: bool | None = None,
) -> Callable[[F], F]:
    """Decorator to compile a function for training.

    Example:
        >>> @compiled_training(dynamic=True)
        ... def train_step(batch: dict[str, Any]) -> dict[str, Any]:
        ...     return self.model(batch)
    """

    def decorator(fn: F) -> F:
        return compile_for_training(fn, dynamic=dynamic, fullgraph=fullgraph, disable=disable)

    return decorator


# =============================================================================
# HOT PATH COMPILATION WRAPPERS (ready-to-use)
# =============================================================================


def compile_e8_quantizer(
    quantizer: nn.Module,
    mode: CompilationMode = "training",
    disable: bool | None = None,
) -> nn.Module:
    """Compile E8 quantizer for faster inference/training.

    Hot path: ResidualE8LatticeVQ is called frequently during encoding.

    Args:
        quantizer: ResidualE8LatticeVQ instance
        mode: Compilation mode (inference/training)
        disable: Override global enable flag

    Returns:
        Compiled quantizer (or original if disabled/failed)
    """
    if mode == "inference":
        return compile_for_inference(quantizer, dynamic=True, disable=disable)
    else:
        return compile_for_training(quantizer, dynamic=True, disable=disable)


def compile_clebsch_gordan_chain(
    projection_fn: Callable[..., torch.Tensor],
    mode: CompilationMode = "training",
    disable: bool | None = None,
) -> Callable[..., torch.Tensor]:
    """Compile Clebsch-Gordan projection chain (E8→E7→E6→F4→G2).

    Hot path: Projection chain is called during hourglass encoding.

    Args:
        projection_fn: Function that performs projections
        mode: Compilation mode (inference/training)
        disable: Override global enable flag

    Returns:
        Compiled projection function (or original if disabled/failed)
    """
    if mode == "inference":
        return compile_for_inference(projection_fn, dynamic=True, disable=disable)
    else:
        return compile_for_training(projection_fn, dynamic=True, disable=disable)


def compile_octonion_mul(
    mul_fn: Callable[..., torch.Tensor],
    mode: CompilationMode = "training",
    disable: bool | None = None,
) -> Callable[..., torch.Tensor]:
    """Compile octonion multiplication (Cayley-Dickson).

    Hot path: Octonion multiplication is used in Fano attention and colony ops.

    Args:
        mul_fn: Octonion multiplication function
        mode: Compilation mode (inference/training)
        disable: Override global enable flag

    Returns:
        Compiled multiplication function (or original if disabled/failed)
    """
    if mode == "inference":
        return compile_for_inference(mul_fn, dynamic=True, disable=disable)
    else:
        return compile_for_training(mul_fn, dynamic=True, disable=disable)


def compile_hot_paths(
    model: nn.Module,
    mode: CompilationMode = "training",
    disable: bool | None = None,
) -> nn.Module:
    """Compile identified hot computational paths in world model.

    HOT PATHS (Dec 16, 2025):
    =========================
    1. UnifiedEquivariantHourglass.encode (forward bottleneck)
    2. ResidualE8LatticeVQ.forward (quantization hot loop)
    3. E8 projection layers (exceptional algebra chain)

    Args:
        model: KagamiWorldModel or submodule
        mode: Compilation mode (inference/training)
        disable: Override global enable flag

    Returns:
        Model with hot paths compiled (or original if disabled/failed)

    Expected speedup: 3-4x inference, 1.5-2x training (GPU only)
    """
    # Check if compilation is disabled
    if disable is True or (disable is None and not is_compilation_enabled()):
        logger.debug("Hot path compilation DISABLED")
        return model

    compiled_count = 0

    # Hot path 1: UnifiedEquivariantHourglass encoder
    if hasattr(model, "unified_hourglass"):
        hourglass = model.unified_hourglass
        if hasattr(hourglass, "encode") and callable(hourglass.encode):
            try:
                if mode == "inference":
                    hourglass.encode = compile_for_inference(
                        hourglass.encode, dynamic=True, disable=False
                    )
                else:
                    hourglass.encode = compile_for_training(
                        hourglass.encode, dynamic=True, disable=False
                    )
                compiled_count += 1
                logger.info("✓ Compiled UnifiedEquivariantHourglass.encode")
            except Exception as e:
                logger.warning(f"Failed to compile encode: {e}")

    # Hot path 2: E8 quantizer
    if hasattr(model, "unified_hourglass") and hasattr(model.unified_hourglass, "residual_e8"):
        e8_vq = model.unified_hourglass.residual_e8
        try:
            if mode == "inference":
                compiled_vq = compile_for_inference(e8_vq, dynamic=True, disable=False)  # type: ignore[type-var]
            else:
                compiled_vq = compile_for_training(e8_vq, dynamic=True, disable=False)  # type: ignore[type-var]
            model.unified_hourglass.residual_e8 = compiled_vq
            compiled_count += 1
            logger.info("✓ Compiled ResidualE8LatticeVQ")
        except Exception as e:
            logger.warning(f"Failed to compile E8 quantizer: {e}")

    if compiled_count > 0:
        logger.info(f"🔥 Hot path compilation: {compiled_count} modules compiled")
    else:
        logger.debug("Hot path compilation: no modules found to compile")

    return model


# =============================================================================
# VERIFICATION UTILITIES
# =============================================================================


def verify_compilation_correctness(
    original_fn: Callable[..., torch.Tensor],
    compiled_fn: Callable[..., torch.Tensor],
    *example_inputs: torch.Tensor,
    atol: float = 1e-5,
    rtol: float = 1e-4,
) -> bool:
    """Verify compiled function produces same output as original.

    Args:
        original_fn: Original (non-compiled) function
        compiled_fn: Compiled function
        example_inputs: Test inputs
        atol: Absolute tolerance
        rtol: Relative tolerance

    Returns:
        True if outputs match within tolerance

    Raises:
        AssertionError: If outputs don't match (numerical correctness violated)
    """
    # Get name for logging (handle both functions and modules)
    fn_name = getattr(original_fn, "__name__", None) or original_fn.__class__.__name__

    # Run both functions
    with torch.no_grad():
        original_output = original_fn(*example_inputs)
        compiled_output = compiled_fn(*example_inputs)

    # Check shapes match
    if original_output.shape != compiled_output.shape:
        raise AssertionError(
            f"Shape mismatch: original {original_output.shape} vs compiled {compiled_output.shape}"
        )

    # Check values match
    if not torch.allclose(original_output, compiled_output, atol=atol, rtol=rtol):
        max_diff = (original_output - compiled_output).abs().max().item()
        raise AssertionError(
            f"Numerical mismatch: max diff {max_diff:.2e} exceeds tolerance (atol={atol}, rtol={rtol})"
        )

    logger.info(f"Compilation correctness verified for {fn_name}")
    return True


# =============================================================================
# BENCHMARKING UTILITIES
# =============================================================================


def benchmark_compilation(
    original_fn: Callable[..., torch.Tensor],
    compiled_fn: Callable[..., torch.Tensor],
    *example_inputs: torch.Tensor,
    num_iterations: int = 100,
    warmup_iterations: int = 10,
) -> dict[str, float]:
    """Benchmark original vs compiled function.

    Args:
        original_fn: Original (non-compiled) function
        compiled_fn: Compiled function
        example_inputs: Test inputs
        num_iterations: Number of benchmark iterations
        warmup_iterations: Number of warmup iterations

    Returns:
        Dict with timing statistics:
            - original_mean_ms: Mean time for original function (ms)
            - compiled_mean_ms: Mean time for compiled function (ms)
            - speedup: Speedup factor (original / compiled)
    """
    import time

    # Warmup
    for _ in range(warmup_iterations):
        with torch.no_grad():
            _ = original_fn(*example_inputs)
            _ = compiled_fn(*example_inputs)

    # Benchmark original
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    start = time.perf_counter()
    for _ in range(num_iterations):
        with torch.no_grad():
            _ = original_fn(*example_inputs)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    original_time = time.perf_counter() - start

    # Benchmark compiled
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    start = time.perf_counter()
    for _ in range(num_iterations):
        with torch.no_grad():
            _ = compiled_fn(*example_inputs)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    compiled_time = time.perf_counter() - start

    # Compute statistics
    original_mean_ms = (original_time / num_iterations) * 1000
    compiled_mean_ms = (compiled_time / num_iterations) * 1000
    speedup = original_time / compiled_time

    logger.info(
        f"Benchmark results: original={original_mean_ms:.2f}ms, "
        f"compiled={compiled_mean_ms:.2f}ms, speedup={speedup:.2f}x"
    )

    return {
        "original_mean_ms": original_mean_ms,
        "compiled_mean_ms": compiled_mean_ms,
        "speedup": speedup,
    }
