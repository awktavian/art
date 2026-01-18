"""Genesis module bridge.

This module provides compatibility imports from the kagami_genesis satellite package.
Tests import from kagami.forge.modules.genesis.* but the actual implementation
is in the kagami_genesis satellite package.
"""

from __future__ import annotations

# Re-export from kagami_genesis satellite package
try:
    from kagami_genesis.optics import (
        GenesisSurfaceSpec,
        RayTracerLight,
        RayTracerOptions,
        ReconBackend,
        SurfaceKind,
    )
    from kagami_genesis.solver_options import (
        FEMOptionsSpec,
        MPMOptionsSpec,
        PBDOptionsSpec,
        SPHOptionsSpec,
    )
    from kagami_genesis.video_generation import (
        GenesisVideoGenerator,
        LightSpec,
        PhysicsEntitySpec,
        PhysicsSolver,
        VideoSpec,
        _infer_domain_bounds,
        create_material_showcase_spec,
        create_neon_cathedral_spec,
        create_physics_diversity_spec,
    )
except ImportError as e:
    # If kagami_genesis is not installed, provide stub imports
    import warnings

    warnings.warn(
        f"kagami_genesis satellite package not available: {e}. "
        "Genesis functionality will be limited.",
        ImportWarning,
        stacklevel=2,
    )

    # Create minimal stubs for typing
    GenesisSurfaceSpec = None  # type: ignore
    RayTracerLight = None  # type: ignore
    RayTracerOptions = None  # type: ignore
    ReconBackend = None  # type: ignore
    SurfaceKind = None  # type: ignore
    FEMOptionsSpec = None  # type: ignore
    MPMOptionsSpec = None  # type: ignore
    PBDOptionsSpec = None  # type: ignore
    SPHOptionsSpec = None  # type: ignore
    GenesisVideoGenerator = None  # type: ignore
    LightSpec = None  # type: ignore
    PhysicsEntitySpec = None  # type: ignore
    PhysicsSolver = None  # type: ignore
    VideoSpec = None  # type: ignore
    _infer_domain_bounds = None  # type: ignore
    create_material_showcase_spec = None  # type: ignore
    create_neon_cathedral_spec = None  # type: ignore
    create_physics_diversity_spec = None  # type: ignore

__all__ = [
    "FEMOptionsSpec",
    "GenesisSurfaceSpec",
    "GenesisVideoGenerator",
    "LightSpec",
    "MPMOptionsSpec",
    "PBDOptionsSpec",
    "PhysicsEntitySpec",
    "PhysicsSolver",
    "RayTracerLight",
    "RayTracerOptions",
    "ReconBackend",
    "SPHOptionsSpec",
    "SurfaceKind",
    "VideoSpec",
    "_infer_domain_bounds",
    "create_material_showcase_spec",
    "create_neon_cathedral_spec",
    "create_physics_diversity_spec",
]
