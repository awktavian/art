"""K os Core module.

CONSOLIDATED ARCHITECTURE (December 2025):
==========================================
This module provides the core components of K OS, organized into:

- config/: Configuration and constants (dimensions.py is canonical for E8)
- e8/: Canonical E8 quantization (consolidated from 10+ duplicate implementations)
- world_model/: KagamiWorldModel and related components
- safety/: Control barrier functions and safety constraints
- intrinsic/: Intrinsic motivation (empowerment, curiosity)
- unified_agents/: Colony system and Fano routing
- services/: Embedding, LLM, voice services

EXTRACTED TO TOP-LEVEL (December 2025):
=======================================
- kagami.math: Mathematical primitives (octonions, E8, G2, Fano plane)
- kagami.forge: 3D/Mascot generation service

MPS NATIVE OPS (December 20, 2025):
===================================
Patches torch.linalg.qr with native MPS Householder implementation.
No CPU fallback - runs entirely on Apple Silicon GPU.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Suppress external package warnings BEFORE any imports
# These are deprecation warnings from third-party packages, not our code
import warnings

# pkg_resources deprecation from opentelemetry/tensorboard (will be fixed upstream)
warnings.filterwarnings(
    "ignore",
    message=".*pkg_resources is deprecated.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*pkg_resources is deprecated.*",
    category=DeprecationWarning,
)

# PyTorch nested_tensor warning (internal optimization, not actionable)
warnings.filterwarnings(
    "ignore",
    message=".*enable_nested_tensor is True.*",
    category=UserWarning,
)

# Multiprocessing resource tracker warning (cleanup at shutdown)
warnings.filterwarnings(
    "ignore",
    message=".*resource_tracker.*leaked semaphore.*",
    category=UserWarning,
)

# OPTIMIZED (Dec 28, 2025): Defer MPS patching to avoid 583ms import-time cost
# Patch is applied lazily when first MPS tensor operation occurs
_MPS_PATCHED = False


def _ensure_mps_patched() -> None:
    """Apply MPS patch lazily (first call only)."""
    global _MPS_PATCHED
    if _MPS_PATCHED:
        return
    _MPS_PATCHED = True
    try:
        from kagami.core.utils.mps_ops import patch_torch_linalg

        patch_torch_linalg()
    except Exception:
        pass  # MPS patching is optional


__all__ = [
    # E8 Module (new consolidated module)
    "e8",
    # Compatibility exports
    "redis_factory",
]


# Lazy import to avoid circular dependencies
def __getattr__(name: str) -> Any:
    from typing import Any

    if name == "e8":
        from kagami.core import e8

        return e8
    if name == "redis_factory":
        from kagami.core import redis_factory

        return redis_factory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
