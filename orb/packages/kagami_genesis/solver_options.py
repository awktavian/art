"""Portable Genesis solver option specs (no Genesis import at import time).

This module provides dataclass specifications that mirror the Genesis 0.3.10
physics simulation option objects without requiring the `genesis-world` package
at import time. This enables unit testing and builds that don't need the full
simulation runtime.

Supported solver types:
    - SPHOptionsSpec: Smoothed Particle Hydrodynamics for fluid simulation
    - MPMOptionsSpec: Material Point Method for deformable solids
    - FEMOptionsSpec: Finite Element Method for structural mechanics
    - PBDOptionsSpec: Position-Based Dynamics for real-time cloth/soft bodies

Each spec class provides:
    - `merged_with()`: Combine with another spec, preferring non-None overrides
    - `to_gs_kwargs()`: Convert to keyword arguments for Genesis constructors

Example:
    >>> base = SPHOptionsSpec(dt=0.001, gravity=(0, -9.8, 0))
    >>> override = SPHOptionsSpec(dt=0.0005)  # Override just dt
    >>> final = base.merged_with(override)
    >>> final.dt
    0.0005

Colony: Forge (e₂)
Created: 2025
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


def _merge_dataclass(base: Any, override: Any) -> Any:
    """Merge two dataclass instances, preferring non-None values from override.

    Creates a new instance of the same type as `base`, combining fields from both.
    For each field, uses the override value if it is not None, otherwise keeps base.

    Args:
        base: The base dataclass instance providing default values.
        override: The override dataclass instance with values to apply.

    Returns:
        A new dataclass instance of the same type as `base` with merged values.

    Example:
        >>> @dataclass
        ... class Config:
        ...     a: int | None = None
        ...     b: str | None = None
        >>> base = Config(a=1, b="hello")
        >>> override = Config(a=2, b=None)
        >>> result = _merge_dataclass(base, override)
        >>> result.a, result.b
        (2, 'hello')
    """
    merged = dict(base.__dict__)
    for k, v in override.__dict__.items():
        if v is not None:
            merged[k] = v
    return type(base)(**merged)


@dataclass
class SPHOptionsSpec:
    """Smoothed Particle Hydrodynamics (SPH) solver options.

    SPH is a Lagrangian mesh-free method for simulating fluid dynamics.
    Particles carry mass and move through space, interacting via kernel
    functions to compute density, pressure, and viscosity forces.

    Common applications:
        - Water, liquids, and splashing effects
        - Blood flow and medical simulations
        - Ocean and wave simulations
        - Cosmological N-body simulations

    Attributes:
        dt: Simulation timestep in seconds. Smaller = more stable but slower.
            Typical range: 0.0001 to 0.01.
        gravity: Gravitational acceleration vector (x, y, z) in m/s².
            Standard Earth gravity: (0, -9.8, 0).
        particle_size: Radius of each SPH particle in meters.
            Affects visual appearance and interaction kernel.
        pressure_solver: Algorithm for pressure computation.
            - "WCSPH": Weakly Compressible SPH (faster, less accurate)
            - "DFSPH": Divergence-Free SPH (slower, more accurate)
        lower_bound: Simulation domain minimum corner (x, y, z).
        upper_bound: Simulation domain maximum corner (x, y, z).
        hash_grid_res: Spatial hash grid resolution for neighbor search.
        hash_grid_cell_size: Size of each hash grid cell in meters.
        max_divergence_error: Convergence threshold for divergence solver.
        max_density_error_percent: Maximum allowed density variation (%).
        max_divergence_solver_iterations: Iteration limit for divergence solve.
        max_density_solver_iterations: Iteration limit for density solve.

    Example:
        >>> water = SPHOptionsSpec(
        ...     dt=0.001,
        ...     gravity=(0, -9.8, 0),
        ...     particle_size=0.02,
        ...     pressure_solver="DFSPH",
        ... )
    """

    dt: float | None = None
    """Simulation timestep in seconds."""
    gravity: tuple[float, float, float] | None = None
    """Gravitational acceleration (x, y, z) in m/s²."""
    particle_size: float | None = None
    """SPH particle radius in meters."""
    pressure_solver: Literal["WCSPH", "DFSPH"] | None = None
    """Pressure computation algorithm: WCSPH (fast) or DFSPH (accurate)."""
    lower_bound: tuple[float, float, float] | None = None
    """Simulation domain minimum corner."""
    upper_bound: tuple[float, float, float] | None = None
    """Simulation domain maximum corner."""
    hash_grid_res: tuple[float, float, float] | None = None
    """Spatial hash grid resolution."""
    hash_grid_cell_size: float | None = None
    """Hash grid cell size in meters."""
    max_divergence_error: float | None = None
    """Divergence solver convergence threshold."""
    max_density_error_percent: float | None = None
    """Maximum density error percentage."""
    max_divergence_solver_iterations: int | None = None
    """Maximum divergence solver iterations."""
    max_density_solver_iterations: int | None = None
    """Maximum density solver iterations."""

    def merged_with(self, override: SPHOptionsSpec) -> SPHOptionsSpec:
        """Merge this spec with another, preferring non-None override values.

        Args:
            override: Another SPHOptionsSpec with values to apply on top.

        Returns:
            A new SPHOptionsSpec with merged values.
        """
        from typing import cast

        return cast(SPHOptionsSpec, _merge_dataclass(self, override))

    def to_gs_kwargs(self) -> dict[str, Any]:
        """Convert to Genesis-compatible keyword arguments.

        Returns:
            Dictionary of non-None field values for Genesis SPHOptions constructor.
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class MPMOptionsSpec:
    """Material Point Method (MPM) solver options.

    MPM is a hybrid Lagrangian-Eulerian method combining the strengths of
    particle-based and grid-based approaches. Excellent for materials that
    undergo large deformations and topology changes.

    Common applications:
        - Snow, sand, and granular materials
        - Mud, clay, and viscoplastic flows
        - Fracture and destruction simulations
        - Multi-material interactions

    Attributes:
        dt: Simulation timestep in seconds. Typical: 0.0001 to 0.001.
        gravity: Gravitational acceleration vector (x, y, z) in m/s².
        particle_size: Radius of each material point in meters.
        grid_density: Background grid resolution factor.
            Higher = more accurate but slower. Typical: 64-256.
        enable_CPIC: Enable Compatible Particle-In-Cell transfer.
            Reduces numerical dissipation at cost of stability.
        lower_bound: Simulation domain minimum corner (x, y, z).
        upper_bound: Simulation domain maximum corner (x, y, z).
        use_sparse_grid: [DEPRECATED] Use sparse grid storage.
        leaf_block_size: [DEPRECATED] Sparse grid leaf block size.

    Example:
        >>> snow = MPMOptionsSpec(
        ...     dt=0.0001,
        ...     gravity=(0, -9.8, 0),
        ...     grid_density=128,
        ...     enable_CPIC=True,
        ... )
    """

    dt: float | None = None
    """Simulation timestep in seconds."""
    gravity: tuple[float, float, float] | None = None
    """Gravitational acceleration (x, y, z) in m/s²."""
    particle_size: float | None = None
    """Material point radius in meters."""
    grid_density: float | None = None
    """Background grid resolution factor."""
    enable_CPIC: bool | None = None
    """Enable Compatible Particle-In-Cell transfer."""
    lower_bound: tuple[float, float, float] | None = None
    """Simulation domain minimum corner."""
    upper_bound: tuple[float, float, float] | None = None
    """Simulation domain maximum corner."""

    # Deprecated in Genesis docs, but kept for compatibility
    use_sparse_grid: bool | None = None
    """[DEPRECATED] Use sparse grid storage."""
    leaf_block_size: int | None = None
    """[DEPRECATED] Sparse grid leaf block size."""

    def merged_with(self, override: MPMOptionsSpec) -> MPMOptionsSpec:
        """Merge this spec with another, preferring non-None override values.

        Args:
            override: Another MPMOptionsSpec with values to apply on top.

        Returns:
            A new MPMOptionsSpec with merged values.
        """
        from typing import cast

        return cast(MPMOptionsSpec, _merge_dataclass(self, override))

    def to_gs_kwargs(self) -> dict[str, Any]:
        """Convert to Genesis-compatible keyword arguments.

        Returns:
            Dictionary of non-None field values for Genesis MPMOptions constructor.
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class FEMOptionsSpec:
    """Finite Element Method (FEM) solver options.

    FEM discretizes a continuous domain into finite elements (typically
    tetrahedra) and solves partial differential equations on them. Ideal
    for accurate structural mechanics and elastic/plastic deformations.

    Common applications:
        - Soft body physics with accurate stress/strain
        - Structural engineering simulations
        - Biological tissue modeling
        - Vehicle crash simulations

    Solver modes:
        - Explicit: Fast but conditionally stable (small dt required)
        - Implicit: Slower per step but unconditionally stable

    Attributes:
        dt: Simulation timestep in seconds.
        gravity: Gravitational acceleration vector (x, y, z) in m/s².
        damping: Global damping coefficient (0 = no damping, 1 = critical).
        floor_height: Y-coordinate of collision floor plane.
        use_implicit_solver: Use implicit time integration (more stable).
        n_newton_iterations: Newton solver iteration limit.
        n_pcg_iterations: Preconditioned Conjugate Gradient iteration limit.
        n_linesearch_iterations: Line search iteration limit.
        newton_dx_threshold: Newton convergence threshold on displacement.
        pcg_threshold: PCG convergence threshold.
        linesearch_c: Armijo line search parameter c.
        linesearch_tau: Line search step reduction factor.
        damping_alpha: Rayleigh damping mass coefficient.
        damping_beta: Rayleigh damping stiffness coefficient.
        enable_vertex_constraints: Enable per-vertex position constraints.

    Example:
        >>> soft_body = FEMOptionsSpec(
        ...     dt=0.01,
        ...     gravity=(0, -9.8, 0),
        ...     use_implicit_solver=True,
        ...     damping=0.1,
        ... )
    """

    dt: float | None = None
    """Simulation timestep in seconds."""
    gravity: tuple[float, float, float] | None = None
    """Gravitational acceleration (x, y, z) in m/s²."""
    damping: float | None = None
    """Global damping coefficient."""
    floor_height: float | None = None
    """Y-coordinate of collision floor plane."""

    # Implicit solver parameters
    use_implicit_solver: bool | None = None
    """Use implicit time integration for unconditional stability."""
    n_newton_iterations: int | None = None
    """Maximum Newton solver iterations."""
    n_pcg_iterations: int | None = None
    """Maximum PCG iterations per Newton step."""
    n_linesearch_iterations: int | None = None
    """Maximum line search iterations."""
    newton_dx_threshold: float | None = None
    """Newton convergence threshold on displacement."""
    pcg_threshold: float | None = None
    """PCG solver convergence threshold."""
    linesearch_c: float | None = None
    """Armijo line search parameter."""
    linesearch_tau: float | None = None
    """Line search step reduction factor."""

    # Rayleigh damping parameters
    damping_alpha: float | None = None
    """Rayleigh mass damping coefficient (α in C = αM + βK)."""
    damping_beta: float | None = None
    """Rayleigh stiffness damping coefficient (β in C = αM + βK)."""
    enable_vertex_constraints: bool | None = None
    """Enable per-vertex position constraints (Dirichlet BCs)."""

    def merged_with(self, override: FEMOptionsSpec) -> FEMOptionsSpec:
        """Merge this spec with another, preferring non-None override values.

        Args:
            override: Another FEMOptionsSpec with values to apply on top.

        Returns:
            A new FEMOptionsSpec with merged values.
        """
        from typing import cast

        return cast(FEMOptionsSpec, _merge_dataclass(self, override))

    def to_gs_kwargs(self) -> dict[str, Any]:
        """Convert to Genesis-compatible keyword arguments.

        Returns:
            Dictionary of non-None field values for Genesis FEMOptions constructor.
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class PBDOptionsSpec:
    """Position-Based Dynamics (PBD) solver options.

    PBD is a fast, stable method for real-time simulation of soft bodies,
    cloth, and fluids. It directly manipulates particle positions using
    constraint projections rather than computing forces.

    Common applications:
        - Real-time cloth and fabric simulation
        - Hair and fur dynamics
        - Rope, chain, and cable physics
        - Interactive soft body deformation
        - Game physics

    Key advantage: Unconditionally stable regardless of timestep,
    making it ideal for real-time applications.

    Attributes:
        dt: Simulation timestep in seconds.
        gravity: Gravitational acceleration vector (x, y, z) in m/s².
        max_stretch_solver_iterations: Iterations for distance constraints.
        max_bending_solver_iterations: Iterations for bending constraints.
        max_volume_solver_iterations: Iterations for volume preservation.
        max_density_solver_iterations: Iterations for fluid density.
        max_viscosity_solver_iterations: Iterations for viscosity.
        particle_size: Radius of each PBD particle in meters.
        hash_grid_res: Spatial hash grid resolution for collision detection.
        hash_grid_cell_size: Size of each hash grid cell in meters.
        lower_bound: Simulation domain minimum corner (x, y, z).
        upper_bound: Simulation domain maximum corner (x, y, z).

    Example:
        >>> cloth = PBDOptionsSpec(
        ...     dt=0.016,  # 60 FPS
        ...     gravity=(0, -9.8, 0),
        ...     max_stretch_solver_iterations=10,
        ...     max_bending_solver_iterations=5,
        ... )
    """

    dt: float | None = None
    """Simulation timestep in seconds."""
    gravity: tuple[float, float, float] | None = None
    """Gravitational acceleration (x, y, z) in m/s²."""

    # Constraint solver iterations
    max_stretch_solver_iterations: int | None = None
    """Maximum iterations for distance/stretch constraints."""
    max_bending_solver_iterations: int | None = None
    """Maximum iterations for bending angle constraints."""
    max_volume_solver_iterations: int | None = None
    """Maximum iterations for volume preservation constraints."""
    max_density_solver_iterations: int | None = None
    """Maximum iterations for fluid density constraints."""
    max_viscosity_solver_iterations: int | None = None
    """Maximum iterations for viscosity constraints."""

    # Spatial configuration
    particle_size: float | None = None
    """PBD particle radius in meters."""
    hash_grid_res: tuple[float, float, float] | None = None
    """Spatial hash grid resolution for neighbor queries."""
    hash_grid_cell_size: float | None = None
    """Hash grid cell size in meters."""
    lower_bound: tuple[float, float, float] | None = None
    """Simulation domain minimum corner."""
    upper_bound: tuple[float, float, float] | None = None
    """Simulation domain maximum corner."""

    def merged_with(self, override: PBDOptionsSpec) -> PBDOptionsSpec:
        """Merge this spec with another, preferring non-None override values.

        Args:
            override: Another PBDOptionsSpec with values to apply on top.

        Returns:
            A new PBDOptionsSpec with merged values.
        """
        from typing import cast

        return cast(PBDOptionsSpec, _merge_dataclass(self, override))

    def to_gs_kwargs(self) -> dict[str, Any]:
        """Convert to Genesis-compatible keyword arguments.

        Returns:
            Dictionary of non-None field values for Genesis PBDOptions constructor.
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}


__all__ = [
    "FEMOptionsSpec",
    "MPMOptionsSpec",
    "PBDOptionsSpec",
    "SPHOptionsSpec",
]
