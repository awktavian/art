"""Genesis video generation re-exports.

This module provides compatibility imports from the kagami_genesis satellite package.
"""

from __future__ import annotations

# Re-export from kagami_genesis satellite package
try:
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
except ImportError:
    # If kagami_genesis is not installed, provide stub imports
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
    "GenesisVideoGenerator",
    "LightSpec",
    "PhysicsEntitySpec",
    "PhysicsSolver",
    "VideoSpec",
    "_infer_domain_bounds",
    "create_material_showcase_spec",
    "create_neon_cathedral_spec",
    "create_physics_diversity_spec",
]
