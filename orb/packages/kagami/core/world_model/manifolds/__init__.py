"""Manifold operations for Poincaré × Octonion Transformer.

This module provides differentiable manifold operations for:
- Poincaré ball (hyperbolic space) with learnable curvature
- Octonion algebra (S⁷ unit octonions) with Cayley-Dickson product
- Product manifolds (𝒟ᶜ × S⁷) with cross-coupling

All operations are:
- Fully differentiable (PyTorch autograd)
- Numerically stable (ε-safe guards)
- Manifold-preserving (invariants maintained)
"""

# Import from consolidated octonions package for backward compatibility
from kagami_math.octonions import (
    OctonionManifold,
    cayley_dickson_mul,
    octonion_conjugate,
    octonion_norm,
    unit_normalize,
)

from kagami.core.world_model.manifolds.poincare import (
    PoincareManifold,
    exp0,
    log0,
    mobius_add,
    mobius_scalar_mul,
    poincare_distance,
)
from kagami.core.world_model.manifolds.product import (
    ProductManifold,
)

__all__ = [
    "ChristoffelTransport",
    "G2HolonomyConstraint",
    # Gauge theory enhancements (Nov 2025)
    "HierarchicalMatryoshkaConnection",
    "OctonionManifold",
    "PoincareManifold",
    "ProductManifold",
    "cayley_dickson_mul",
    "exp0",
    "log0",
    "mobius_add",
    "mobius_scalar_mul",
    "octonion_conjugate",
    "octonion_norm",
    "poincare_distance",
    "unit_normalize",
]

# Import gauge enhancements
try:
    from kagami.core.world_model.manifolds.christoffel_transport import ChristoffelTransport
    from kagami.core.world_model.manifolds.hierarchical_connections import (
        HierarchicalMatryoshkaConnection,
    )
    from kagami.core.world_model.manifolds.holonomy_constraints import G2HolonomyConstraint
except ImportError:
    pass  # Optional enhancements
