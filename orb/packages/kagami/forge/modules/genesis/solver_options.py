"""Genesis solver options module bridge.

Re-exports solver options from kagami_genesis satellite package.
"""

from __future__ import annotations

try:
    from kagami_genesis.solver_options import (
        FEMOptionsSpec,
        MPMOptionsSpec,
        PBDOptionsSpec,
        SPHOptionsSpec,
    )
except ImportError as e:
    import warnings

    warnings.warn(
        f"kagami_genesis.solver_options not available: {e}",
        ImportWarning,
        stacklevel=2,
    )
    FEMOptionsSpec = None  # type: ignore
    MPMOptionsSpec = None  # type: ignore
    PBDOptionsSpec = None  # type: ignore
    SPHOptionsSpec = None  # type: ignore

__all__ = [
    "FEMOptionsSpec",
    "MPMOptionsSpec",
    "PBDOptionsSpec",
    "SPHOptionsSpec",
]
