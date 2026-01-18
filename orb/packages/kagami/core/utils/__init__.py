"""K OS core utils module.

IMPORTANT: Keep this package lightweight.

Historically this package imported `kagami.core.utils.device` at import time, which
pulls in `torch` immediately. That made *non-ML* subsystems (e.g. config, rooms)
slow to import and caused brittle test behavior when running under parallel test
runners.

We keep the convenient `from kagami.core.utils import get_device` API, but we
resolve those symbols lazily via `__getattr__` so `torch` is only imported when
device helpers are actually used.

CONSOLIDATED (December 13, 2025):
=================================
Added ml_utils and math_utils for common ML/math patterns.
These are also lazy-loaded to avoid pulling in torch/numpy unnecessarily.
"""

from __future__ import annotations

from typing import Any

_DEVICE_EXPORTS = {
    "get_device",
    "get_device_str",
    "is_mps",
    "is_cuda",
    "is_cpu",
    "is_gpu",
    "synchronize",
    "empty_cache",
    "ensure_dtype",
    "get_default_dtype",
    "get_autocast_dtype",
    "to_device",
    "autocast_context",
    "get_memory_info",
    "apply_mps_patches",
    "on_device",
}

# ML utilities - lazy loaded to avoid torch import
_ML_EXPORTS = {
    "MLUtils",
    "LayerFactory",
    "TrainingUtils",
    "TensorOps",
    "ModelUtils",
    "CommonLosses",
    "create_adamw_optimizer",
    "create_cosine_scheduler",
    "safe_model_forward",
    "get_activation_function",
}

# Math utilities - lazy loaded to avoid numpy import at top level
_MATH_EXPORTS = {
    "LinearAlgebra",
    "Statistics",
    "Geometry",
    "Numerical",
    "Signal",
    "Interpolation",
    "Optimization",
    "SpecialFunctions",
    "ArrayUtils",
    "normalize",
    "create_meshgrid",
    "random_orthogonal_matrix",
    "compute_eigenvalues_safe",
    "stable_rank",
}

# Safe operations - lazy loaded
_SAFE_EXPORTS = {
    "safe_divide",
    "safe_multiply",
    "safe_add",
    "safe_subtract",
    "safe_percentage",
    "safe_concat",
    "safe_format_string",
    "safe_increment",
    "safe_min",
    "safe_max",
    "safe_duration",
}

# Singleton utilities - lazy loaded
_SINGLETON_EXPORTS = {
    "singleton",
    "SingletonMeta",
    "get_or_create",
    "AsyncSingleton",
    "LazySingleton",
}

# Deprecation utilities - lazy loaded (Jan 4, 2026)
_DEPRECATION_EXPORTS = {
    "deprecated",
    "deprecated_parameter",
    "deprecated_import",
    "DeprecatedClass",
    "DeprecationWarningLevel",
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name in _DEVICE_EXPORTS:
        from kagami.core.utils import device as _device

        return getattr(_device, name)

    if name in _ML_EXPORTS:
        from kagami.core.utils import ml_utils as _ml

        return getattr(_ml, name)

    if name in _MATH_EXPORTS:
        from kagami.core.utils import math_utils as _math

        return getattr(_math, name)

    if name in _SAFE_EXPORTS:
        from kagami.core.utils import safe_operations as _safe

        return getattr(_safe, name)

    if name in _SINGLETON_EXPORTS:
        from kagami.core.utils import singleton as _singleton

        return getattr(_singleton, name)

    if name in _DEPRECATION_EXPORTS:
        from kagami.core.utils import deprecation as _deprecation

        return getattr(_deprecation, name)

    raise AttributeError(name)


def __dir__() -> list[str]:  # pragma: no cover
    return sorted(
        list(globals().keys())  # type: ignore[operator]
        | _DEVICE_EXPORTS
        | _ML_EXPORTS
        | _MATH_EXPORTS
        | _SAFE_EXPORTS
        | _SINGLETON_EXPORTS
        | _DEPRECATION_EXPORTS
    )


__all__ = sorted(
    _DEVICE_EXPORTS
    | _ML_EXPORTS
    | _MATH_EXPORTS
    | _SAFE_EXPORTS
    | _SINGLETON_EXPORTS
    | _DEPRECATION_EXPORTS
)
