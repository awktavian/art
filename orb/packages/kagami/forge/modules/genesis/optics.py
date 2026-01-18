"""Genesis optics module bridge.

Re-exports optics components from kagami_genesis satellite package.
"""

from __future__ import annotations

try:
    from kagami_genesis.optics import (
        GenesisSurfaceSpec,
        RayTracerLight,
        RayTracerOptions,
        ReconBackend,
        SurfaceKind,
    )
except ImportError as e:
    import warnings

    warnings.warn(
        f"kagami_genesis.optics not available: {e}",
        ImportWarning,
        stacklevel=2,
    )
    GenesisSurfaceSpec = None  # type: ignore
    RayTracerLight = None  # type: ignore
    RayTracerOptions = None  # type: ignore
    ReconBackend = None  # type: ignore
    SurfaceKind = None  # type: ignore

__all__ = [
    "GenesisSurfaceSpec",
    "RayTracerLight",
    "RayTracerOptions",
    "ReconBackend",
    "SurfaceKind",
]
