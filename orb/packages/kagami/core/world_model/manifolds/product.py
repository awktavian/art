"""Product manifold operations for H¹⁴ × S⁷.

This module provides the product manifold combining:
- Poincaré ball (H¹⁴): Hyperbolic space for hierarchical representations
- Octonion sphere (S⁷): Spherical space for compositional structure

The product manifold H¹⁴ × S⁷ is the core geometric structure of K OS,
enabling:
1. Hierarchical reasoning in hyperbolic space
2. Parallel colony computation on S⁷
3. Cross-manifold coupling for integrated processing

Mathematical Foundation:
========================
The product manifold M = H¹⁴ × S⁷ has:
- Total dimension: 14 + 7 = 21D
- Metric: g_M = g_H ⊕ g_S (direct sum)
- Curvature: Mixed (negative in H¹⁴, positive in S⁷)

References:
- Ganea et al. (2018): Hyperbolic Neural Networks
- Nickel & Kiela (2017): Poincaré Embeddings
- Baez (2002): The Octonions

Created: December 6, 2025
"""

from __future__ import annotations

import torch
import torch.nn as nn
from kagami_math.dimensions import HYPERBOLIC_DIM, S7_INTRINSIC_DIM


class ProductManifold(nn.Module):
    """Product manifold H¹⁴ × S⁷ for hierarchical-compositional reasoning.

    This manifold combines:
    - Poincaré ball (H¹⁴): dim=14, negative curvature, for hierarchies
    - Octonion sphere (S⁷): dim=7, positive curvature, for composition

    Points are represented as concatenated vectors:
        x = [x_H, x_S] ∈ ℝ^21

    Where x_H ∈ H¹⁴ and x_S ∈ S⁷.
    """

    def __init__(
        self,
        hyperbolic_dim: int = HYPERBOLIC_DIM,
        spherical_dim: int = S7_INTRINSIC_DIM,
        curvature_init: float = 0.1,
        learnable_curvature: bool = True,
        coupling_weight: float = 0.1,
    ) -> None:
        """Initialize product manifold.

        Args:
            hyperbolic_dim: Dimension of hyperbolic component (default: 14)
            spherical_dim: Dimension of spherical component (default: 7)
            curvature_init: Initial curvature for Poincaré ball
            learnable_curvature: Whether curvature is learnable
            coupling_weight: Weight for cross-manifold coupling
        """
        super().__init__()

        self.hyperbolic_dim = hyperbolic_dim
        self.spherical_dim = spherical_dim
        self.total_dim = hyperbolic_dim + spherical_dim
        self.coupling_weight = coupling_weight
        self.eps = 1e-15

        # Lazy import to avoid circular dependency
        from kagami_math.octonions import OctonionManifold

        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        # Initialize component manifolds
        self.poincare = PoincareManifold(
            dim=hyperbolic_dim,
            curvature_init=curvature_init,
            learnable_curvature=learnable_curvature,
        )
        self.octonion = OctonionManifold()

        # Cross-manifold coupling (optional)
        if coupling_weight > 0:
            self.coupling_h_to_s = nn.Linear(hyperbolic_dim, spherical_dim, bias=False)
            self.coupling_s_to_h = nn.Linear(spherical_dim, hyperbolic_dim, bias=False)

            # Initialize with small weights for stability
            nn.init.xavier_uniform_(self.coupling_h_to_s.weight, gain=0.1)
            nn.init.xavier_uniform_(self.coupling_s_to_h.weight, gain=0.1)
        else:
            self.coupling_h_to_s = None  # type: ignore[assignment]
            self.coupling_s_to_h = None  # type: ignore[assignment]

    def split(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Split product manifold point into components.

        Args:
            x: Point on product manifold [..., 21]

        Returns:
            x_h: Hyperbolic component [..., 14]
            x_s: Spherical component [..., 7]
        """
        return x[..., : self.hyperbolic_dim], x[..., self.hyperbolic_dim :]

    def combine(self, x_h: torch.Tensor, x_s: torch.Tensor) -> torch.Tensor:
        """Combine components into product manifold point.

        Args:
            x_h: Hyperbolic component [..., 14]
            x_s: Spherical component [..., 7]

        Returns:
            x: Point on product manifold [..., 21]
        """
        return torch.cat([x_h, x_s], dim=-1)

    def project(self, x: torch.Tensor) -> torch.Tensor:
        """Project point onto product manifold.

        Projects hyperbolic component into Poincaré ball and
        spherical component onto S⁷.

        Args:
            x: Point to project [..., 21]

        Returns:
            Projected point on M = H¹⁴ × S⁷
        """
        x_h, x_s = self.split(x)

        # Project each component
        x_h_proj = self.poincare.project(x_h)
        x_s_proj = self.octonion.project_to_s7(x_s)

        return self.combine(x_h_proj, x_s_proj)

    def _s7_distance(self, x_s: torch.Tensor, y_s: torch.Tensor) -> torch.Tensor:
        """Great-circle distance on S⁷.

        d(x, y) = arccos(x · y) for unit vectors x, y.

        Args:
            x_s: First point on S⁷ [..., 7]
            y_s: Second point on S⁷ [..., 7]

        Returns:
            Angular distance [...]
        """
        # Ensure unit vectors
        x_s = x_s / (x_s.norm(dim=-1, keepdim=True) + self.eps)
        y_s = y_s / (y_s.norm(dim=-1, keepdim=True) + self.eps)

        # Dot product clamped for numerical stability
        dot = (x_s * y_s).sum(dim=-1).clamp(-1 + self.eps, 1 - self.eps)

        return torch.acos(dot)

    def exp_map(
        self,
        x: torch.Tensor,
        v: torch.Tensor,
    ) -> torch.Tensor:
        """Exponential map on product manifold.

        Applies exp map independently on each component:
            exp_M(x, v) = (exp_H(x_h, v_h), exp_S(x_s, v_s))

        Args:
            x: Base point [..., 21]
            v: Tangent vector [..., 21]

        Returns:
            exp_x(v) on product manifold
        """
        x_h, x_s = self.split(x)
        v_h, v_s = self.split(v)

        # Exp maps on each component
        y_h = self.poincare.exp(x_h, v_h)
        y_s = self.octonion.exp_s7(x_s, v_s)

        return self.combine(y_h, y_s)

    def log_map(
        self,
        x: torch.Tensor,
        y: torch.Tensor,
    ) -> torch.Tensor:
        """Logarithmic map on product manifold.

        Applies log map independently on each component:
            log_M(x, y) = (log_H(x_h, y_h), log_S(x_s, y_s))

        Args:
            x: Base point [..., 21]
            y: Target point [..., 21]

        Returns:
            log_x(y) tangent vector
        """
        x_h, x_s = self.split(x)
        y_h, y_s = self.split(y)

        # Log maps on each component
        v_h = self.poincare.log(x_h, y_h)
        v_s = self.octonion.log_s7(x_s, y_s)

        return self.combine(v_h, v_s)

    def distance(
        self,
        x: torch.Tensor,
        y: torch.Tensor,
        weighted: bool = True,
    ) -> torch.Tensor:
        """Compute distance on product manifold.

        Uses the product metric:
            d_M(x, y)² = d_H(x_h, y_h)² + d_S(x_s, y_s)²

        Args:
            x: First point [..., 21]
            y: Second point [..., 21]
            weighted: Whether to weight components (default: True)

        Returns:
            Distance scalar [...]
        """
        x_h, x_s = self.split(x)
        y_h, y_s = self.split(y)

        # Compute component distances
        d_h = self.poincare.distance(x_h, y_h)
        d_s = self._s7_distance(x_s, y_s)

        # Product metric
        if weighted:
            # Weight by dimension for balanced contribution
            w_h = self.hyperbolic_dim / self.total_dim
            w_s = self.spherical_dim / self.total_dim
            return torch.sqrt(w_h * d_h**2 + w_s * d_s**2 + self.eps)
        else:
            return torch.sqrt(d_h**2 + d_s**2 + self.eps)

    def parallel_transport(
        self,
        x: torch.Tensor,
        y: torch.Tensor,
        v: torch.Tensor,
    ) -> torch.Tensor:
        """Parallel transport tangent vector along geodesic.

        Transports v from T_x M to T_y M along the geodesic x → y.

        Args:
            x: Source point [..., 21]
            y: Target point [..., 21]
            v: Tangent vector at x [..., 21]

        Returns:
            Transported vector at y [..., 21]
        """
        x_h, x_s = self.split(x)
        y_h, y_s = self.split(y)
        v_h, v_s = self.split(v)

        # Transport independently on each component
        v_h_transported = self.poincare.parallel_transport(x_h, y_h, v_h)
        v_s_transported = self.octonion.parallel_transport(x_s, y_s, v_s)

        return self.combine(v_h_transported, v_s_transported)

    def coupled_transform(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:
        """Apply cross-manifold coupling.

        Allows information flow between hyperbolic and spherical components.
        This is essential for the Strange Loop architecture where self-reference
        must span both hierarchical and compositional aspects.

        Args:
            x: Point on product manifold [..., 21]

        Returns:
            Coupled point [..., 21]
        """
        if self.coupling_h_to_s is None:
            return x

        x_h, x_s = self.split(x)

        # Cross-coupling: each component receives information from the other
        h_influence = self.coupling_s_to_h(x_s)
        s_influence = self.coupling_h_to_s(x_h)

        # Add influence with coupling weight
        x_h_coupled = x_h + self.coupling_weight * h_influence
        x_s_coupled = x_s + self.coupling_weight * s_influence

        # Re-project to maintain manifold constraints
        x_h_proj = self.poincare.project(x_h_coupled)
        x_s_proj = self.octonion.project_to_s7(x_s_coupled)

        return self.combine(x_h_proj, x_s_proj)

    def random_point(
        self,
        batch_size: int = 1,
        device: torch.device | str | None = None,
    ) -> torch.Tensor:
        """Sample random point on product manifold.

        Args:
            batch_size: Number of points to sample
            device: Device for tensor

        Returns:
            Random point on M = H¹⁴ × S⁷ [batch_size, 21]
        """
        # Random point in Poincaré ball (inside the ball)
        x_h = torch.randn(batch_size, self.hyperbolic_dim, device=device)
        x_h = self.poincare.project(x_h * 0.5)  # Scale to stay well inside ball

        # Random point on S⁷ (on the sphere)
        x_s = torch.randn(batch_size, self.spherical_dim, device=device)
        x_s = self.octonion.project_to_s7(x_s)

        return self.combine(x_h, x_s)

    def origin(
        self,
        batch_size: int = 1,
        device: torch.device | str | None = None,
    ) -> torch.Tensor:
        """Return origin point on product manifold.

        The origin is (0, e_1) where:
        - 0 is the center of the Poincaré ball
        - e_1 is the first standard basis vector on S⁷

        Args:
            batch_size: Number of origin points
            device: Device for tensor

        Returns:
            Origin points [batch_size, 21]
        """
        # Poincaré origin
        x_h = torch.zeros(batch_size, self.hyperbolic_dim, device=device)

        # S⁷ "origin" - first basis vector
        x_s = torch.zeros(batch_size, self.spherical_dim, device=device)
        x_s[..., 0] = 1.0  # e_1

        return self.combine(x_h, x_s)


__all__ = [
    "ProductManifold",
]
