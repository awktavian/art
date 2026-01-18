"""Unified Device Management for K OS.

CRITICAL: This is THE SINGLE SOURCE OF TRUTH for device selection.
All modules should import from here instead of rolling their own device logic.

MPS-FIRST ARCHITECTURE (Dec 8, 2025):
=====================================
Apple Silicon with MPS is the PRIMARY target platform.
Device priority: MPS > CUDA > CPU

Key Functions:
- get_device(): Returns optimal torch.device
- get_device_str(): Returns device as string
- synchronize(): Device-agnostic synchronization
- empty_cache(): Device-agnostic cache clearing
- to_device(): Move tensor/module to optimal device
- ensure_dtype(): Convert to MPS-compatible dtype (no float64)

Usage:
    from kagami.core.utils.device import get_device, synchronize, empty_cache

    device = get_device()  # Returns torch.device("mps") on Apple Silicon
    model = model.to(device)

    # Before timing
    synchronize()
    start = time.time()

    # After heavy operations
    empty_cache()

Scientific Basis:
- Apple M3/M4 Ultra: 76+ GPU cores, 512GB unified memory
- MPS provides ~3-5x speedup over CPU for typical workloads
- Unified memory eliminates CPU↔GPU transfer overhead

Created: December 8, 2025
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch
    from torch import Tensor

logger = logging.getLogger(__name__)


# =============================================================================
# DEVICE DETECTION
# =============================================================================


@lru_cache(maxsize=1)
def get_device() -> torch.device:
    """Get optimal compute device.

    Priority: MPS > CUDA > CPU

    This is MPS-first because:
    1. K OS is developed on Apple Silicon
    2. Unified memory provides massive advantages
    3. No CPU↔GPU transfer overhead

    Returns:
        torch.device: Optimal device for computation

    Example:
        device = get_device()  # torch.device("mps") on M3 Ultra
    """
    import torch

    # Check environment override first
    env_device = os.getenv("KAGAMI_DEVICE", "").lower()
    if env_device in ("mps", "cuda", "cpu"):
        if env_device == "mps" and torch.backends.mps.is_available():
            return torch.device("mps")
        elif env_device == "cuda" and torch.cuda.is_available():
            return torch.device("cuda")
        elif env_device == "cpu":
            return torch.device("cpu")
        # Fall through if requested device not available

    # MPS first (Apple Silicon)
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        try:
            # Verify MPS actually works
            test = torch.tensor([1.0], device="mps")
            del test
            return torch.device("mps")
        except Exception as e:
            logger.warning(f"MPS available but not functional: {e}")

    # CUDA second (NVIDIA)
    if torch.cuda.is_available():
        return torch.device("cuda")

    # CPU fallback
    return torch.device("cpu")


def get_device_str() -> str:
    """Get device as string.

    Returns:
        str: "mps", "cuda", or "cpu"
    """
    return get_device().type


def is_mps() -> bool:
    """Check if running on MPS."""
    return get_device().type == "mps"


def is_cuda() -> bool:
    """Check if running on CUDA."""
    return get_device().type == "cuda"


def is_cpu() -> bool:
    """Check if running on CPU."""
    return get_device().type == "cpu"


def is_gpu() -> bool:
    """Check if running on any GPU (MPS or CUDA)."""
    return get_device().type in ("mps", "cuda")


# =============================================================================
# SYNCHRONIZATION
# =============================================================================


def synchronize(device: torch.device | str | None = None) -> None:
    """Synchronize device operations.

    CRITICAL for accurate timing measurements.
    Call before and after timed sections.

    Args:
        device: Device to synchronize (default: auto-detect)

    Example:
        synchronize()
        start = time.perf_counter()
        result = model(x)
        synchronize()
        elapsed = time.perf_counter() - start
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    if device.type == "cuda":
        torch.cuda.synchronize()
    elif device.type == "mps":
        # MPS synchronization
        if hasattr(torch.mps, "synchronize"):
            torch.mps.synchronize()
        else:
            # Fallback: force sync by moving small tensor
            _ = torch.tensor([1.0], device="mps").cpu()


def empty_cache(device: torch.device | str | None = None) -> None:
    """Clear device memory cache.

    Call after heavy operations to free unused memory.

    Args:
        device: Device to clear cache (default: auto-detect)
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    if device.type == "cuda":
        torch.cuda.empty_cache()
    elif device.type == "mps":
        if hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()


# =============================================================================
# DATA TYPE MANAGEMENT
# =============================================================================


def ensure_dtype(
    tensor: Tensor,
    target_dtype: torch.dtype | None = None,
) -> Tensor:
    """Ensure tensor has MPS-compatible dtype.

    MPS does NOT support float64 (double precision).
    This function converts float64 → float32 automatically.

    Args:
        tensor: Input tensor
        target_dtype: Target dtype (default: auto-select)

    Returns:
        Tensor with compatible dtype
    """
    import torch

    device = tensor.device

    # MPS doesn't support float64
    if device.type == "mps" and tensor.dtype == torch.float64:
        return tensor.to(torch.float32)

    # Apply explicit target dtype
    if target_dtype is not None and tensor.dtype != target_dtype:
        return tensor.to(target_dtype)

    return tensor


def get_default_dtype(device: torch.device | str | None = None) -> torch.dtype:
    """Get optimal default dtype for device.

    MPS: float32 (no float64 support)
    CUDA: float32 (or float16 for memory efficiency)
    CPU: float32

    Args:
        device: Target device

    Returns:
        Optimal dtype
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    # MPS doesn't support float64
    if device.type == "mps":
        return torch.float32

    return torch.float32


def get_autocast_dtype(device: torch.device | str | None = None) -> torch.dtype:
    """Get optimal dtype for autocast (mixed precision).

    MPS: bfloat16 (better than float16 for stability)
    CUDA: float16 (or bfloat16 on Ampere+)
    CPU: bfloat16

    Args:
        device: Target device

    Returns:
        Optimal autocast dtype
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    if device.type == "mps":
        return torch.bfloat16
    elif device.type == "cuda":
        # Use bfloat16 on Ampere+ (compute capability 8.0+)
        if torch.cuda.get_device_capability()[0] >= 8:
            return torch.bfloat16
        return torch.float16
    else:
        return torch.bfloat16


# =============================================================================
# DEVICE MOVEMENT
# =============================================================================


def to_device(
    obj: Tensor | Any,
    device: torch.device | str | None = None,
    non_blocking: bool = True,
) -> Tensor | Any:
    """Move tensor or module to optimal device.

    Handles dtype conversion for MPS compatibility.

    Args:
        obj: Tensor or Module to move
        device: Target device (default: auto-detect)
        non_blocking: Use non-blocking transfer

    Returns:
        Object on target device
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    # Handle float64 for MPS
    if isinstance(obj, torch.Tensor):
        if device.type == "mps" and obj.dtype == torch.float64:
            obj = obj.to(torch.float32)
        return obj.to(device, non_blocking=non_blocking)
    else:
        # Import nn lazily to avoid torch side effects at import-time.
        import torch.nn as nn

        if not isinstance(obj, nn.Module):
            return obj

        # Convert all float64 parameters to float32 for MPS
        if device.type == "mps":
            for param in obj.parameters():
                if param.dtype == torch.float64:
                    param.data = param.data.to(torch.float32)
            for buffer_name, buffer in obj.named_buffers():
                if buffer.dtype == torch.float64:
                    obj.register_buffer(buffer_name, buffer.to(torch.float32))
        return obj.to(device)


# =============================================================================
# AUTOCAST CONTEXT
# =============================================================================


def autocast_context(
    device: torch.device | str | None = None,
    enabled: bool = True,
) -> Any:
    """Get autocast context manager for device.

    Args:
        device: Target device (default: auto-detect)
        enabled: Whether to enable autocast

    Returns:
        Autocast context manager
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    if not enabled:
        from contextlib import nullcontext

        return nullcontext()

    dtype = get_autocast_dtype(device)

    if device.type == "mps":
        return torch.amp.autocast("mps", dtype=dtype)
    elif device.type == "cuda":
        return torch.amp.autocast("cuda", dtype=dtype)
    else:
        # CPU autocast
        return torch.amp.autocast("cpu", dtype=dtype)


# =============================================================================
# MEMORY INFO
# =============================================================================


def get_memory_info(device: torch.device | str | None = None) -> dict[str, Any]:
    """Get memory information for device.

    Args:
        device: Target device (default: auto-detect)

    Returns:
        Dict with memory stats
    """
    import torch

    if device is None:
        device = get_device()
    elif isinstance(device, str):
        device = torch.device(device)

    info: dict[str, Any] = {
        "device": str(device),
        "device_type": device.type,
    }

    if device.type == "cuda":
        props = torch.cuda.get_device_properties(device)
        info["total_gb"] = props.total_memory / (1024**3)
        info["allocated_gb"] = torch.cuda.memory_allocated(device) / (1024**3)
        info["reserved_gb"] = torch.cuda.memory_reserved(device) / (1024**3)
        info["device_name"] = props.name
    elif device.type == "mps":
        try:
            import psutil

            mem = psutil.virtual_memory()
            info["total_gb"] = mem.total / (1024**3)
            info["available_gb"] = mem.available / (1024**3)
            info["used_percent"] = mem.percent
            info["device_name"] = "Apple MPS (Unified Memory)"
        except ImportError:
            info["device_name"] = "Apple MPS"
    else:
        try:
            import psutil

            mem = psutil.virtual_memory()
            info["total_gb"] = mem.total / (1024**3)
            info["available_gb"] = mem.available / (1024**3)
        except ImportError:
            pass
        info["device_name"] = "CPU"

    return info


# =============================================================================
# APPLY MPS PATCHES
# =============================================================================


_mps_patches_applied = False


def apply_mps_env_patches(*, force: bool = False) -> None:
    """Apply *environment-only* MPS compatibility patches.

    This is safe to call in modules that must stay torch-free at import time.
    """
    if force:
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
        return

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")


def apply_mps_patches(*, force_env: bool = False) -> None:
    """Apply MPS compatibility patches globally.

    Call this at application startup for best compatibility.
    Safe to call multiple times.
    """
    global _mps_patches_applied

    # Env patches are always safe to (re)apply; allow forced override.
    apply_mps_env_patches(force=force_env)

    if _mps_patches_applied:
        return

    import torch

    if not torch.backends.mps.is_available():
        return

    # Set default dtype to float32 (MPS doesn't support float64)
    torch.set_default_dtype(torch.float32)

    _mps_patches_applied = True
    logger.debug("Applied MPS compatibility patches")


# =============================================================================
# CONVENIENCE DECORATOR
# =============================================================================


def on_device(device: torch.device | str | None = None) -> None:
    """Decorator to run function with tensors on specified device.

    Example:
        @on_device("mps")
        def forward(self, x):
            return self.model(x)
    """

    def decorator(func: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import torch

            target = device if device is not None else get_device()
            if isinstance(target, str):
                target = torch.device(target)

            # Move tensor args to device
            new_args = []
            for arg in args:
                if isinstance(arg, torch.Tensor):
                    new_args.append(to_device(arg, target))
                else:
                    new_args.append(arg)

            new_kwargs = {}
            for k, v in kwargs.items():
                if isinstance(v, torch.Tensor):
                    new_kwargs[k] = to_device(v, target)
                else:
                    new_kwargs[k] = v

            return func(*new_args, **new_kwargs)

        return wrapper

    return decorator  # type: ignore[return-value]


# =============================================================================
# MODULE EXPORTS
# =============================================================================


__all__ = [
    # Patches
    "apply_mps_env_patches",
    "apply_mps_patches",
    "autocast_context",
    "empty_cache",
    # Data types
    "ensure_dtype",
    "get_autocast_dtype",
    "get_default_dtype",
    # Core device detection
    "get_device",
    "get_device_str",
    # Memory info
    "get_memory_info",
    "is_cpu",
    "is_cuda",
    "is_gpu",
    "is_mps",
    # Decorator
    "on_device",
    # Synchronization
    "synchronize",
    # Device movement
    "to_device",
]
