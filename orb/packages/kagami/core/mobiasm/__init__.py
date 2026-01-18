"""MOBIASM - Mobius Assembly Language Compiler and Runtime.

This package provides the MobiASM compiler and production runtime.

Architecture:
- Compiler: Parse MOBIASM text -> executable operations
- Runtime: Execute MOBIASM instructions on actual manifolds (zero-overhead)
- Benchmark: Measure performance of all operations

Version: 2.0.0
"""

from typing import TYPE_CHECKING, Any

# Lazy imports to avoid import chain issues with kagami_benchmarks
if TYPE_CHECKING:
    from kagami.core.mobiasm.benchmark import MobiASMBenchmark

from kagami.core.mobiasm.compiler import MobiASMCompiler
from kagami.core.mobiasm.runtime_zero_overhead import (
    MobiASMZeroOverheadRuntime,
)


def create_mobiasm_v2(  # type: ignore[no-untyped-def]
    hyperbolic_dim: int = 7,
    curvature: float = 0.1,
    device: str = "mps",
    dtype=None,
    use_compile: bool = False,
) -> Any:
    """Factory function for creating MOBIASM runtime (v2 compatible).

    Args:
        hyperbolic_dim: Dimension of hyperbolic space (default: 7)
        curvature: Curvature of hyperbolic space (default: 0.1)
        device: Device to run on (default: "mps")
        dtype: Data type (default: torch.float32)
        use_compile: Whether to use torch.compile (default: False)

    Returns:
        MobiASMZeroOverheadRuntime instance
    """
    import torch

    if dtype is None:
        dtype = torch.float32

    return MobiASMZeroOverheadRuntime(
        hyperbolic_dim=hyperbolic_dim,
        curvature=curvature,
        device=device,
        dtype=dtype,
        use_compile=use_compile,
    )


def __getattr__(name: str) -> Any:
    """Lazy import MobiASMBenchmark to avoid import chain issues."""
    if name == "MobiASMBenchmark":
        from kagami.core.mobiasm.benchmark import MobiASMBenchmark

        return MobiASMBenchmark
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MobiASMBenchmark",
    "MobiASMCompiler",
    "MobiASMZeroOverheadRuntime",
    "create_mobiasm_v2",
]

__version__ = "2.0.0"
