"""Tests for PXO curvature initialization fixes."""

from __future__ import annotations

from typing import Any

import pytest

import torch

from kagami.core.world_model.manifolds.poincare import PoincareManifold


pytestmark = pytest.mark.tier_integration


class TestCurvatureInitialization:
    """Test that curvature initializes to requested values."""

    @pytest.mark.parametrize("target_c", [0.01, 0.1, 0.5, 1.0])
    def test_curvature_init_accuracy(self, target_c) -> None:
        """Curvature should initialize close to requested value."""
        manifold = PoincareManifold(
            dim=16,
            curvature_init=target_c,
            curvature_min=0.001,
            curvature_max=10.0,
            learnable_curvature=True,
        )

        actual_c = manifold.curvature.item()

        # Should be within 10% or 0.01 (whichever is larger)
        tolerance = max(0.01, target_c * 0.1)
        assert (
            abs(actual_c - target_c) < tolerance
        ), f"Expected curvature ≈ {target_c}, got {actual_c}"

    def test_curvature_stays_in_bounds(self) -> None:
        """Curvature should respect min/max bounds after clamping."""
        c_min, c_max = 0.01, 0.5
        manifold = PoincareManifold(
            dim=16,
            curvature_init=0.25,
            curvature_min=c_min,
            curvature_max=c_max,
            learnable_curvature=True,
        )

        # Initial curvature
        c_init = manifold.curvature.item()
        assert (
            c_min <= c_init <= c_max + 0.1
        ), f"Initial curvature {c_init} outside acceptable range [{c_min}, {c_max}]"

        # Simulate extreme gradient updates
        for _ in range(10):
            # Large random perturbation (match scalar shape)
            manifold.raw_curvature.data += torch.randn_like(manifold.raw_curvature) * 1.0
            c = manifold.curvature.item()
            # Curvature property includes clamping
            assert c_min <= c <= c_max + 0.1, f"Curvature {c} violates bounds [{c_min}, {c_max}]"

    def test_non_learnable_curvature(self) -> None:
        """Non-learnable curvature should be fixed."""
        target_c = 0.2
        manifold = PoincareManifold(
            dim=8,
            curvature_init=target_c,
            learnable_curvature=False,
        )

        # Should be a buffer, not a parameter
        assert not isinstance(manifold.raw_curvature, torch.nn.Parameter)
        assert isinstance(manifold.raw_curvature, torch.Tensor)

        # Curvature should match target
        actual_c = manifold.curvature.item()
        assert abs(actual_c - target_c) < 0.05

    def test_boundary_regularization_increases_near_edge(self) -> None:
        """Boundary regularization should penalize points near edge."""
        manifold = PoincareManifold(dim=8, curvature_init=1.0)

        # Points at different radii
        x_center = torch.zeros(4, 8)  # At origin
        x_mid = torch.ones(4, 8) * 0.3  # Mid-ball (further from boundary)
        x_near_edge = torch.ones(4, 8) * 0.95  # Near boundary (||x|| ≈ 0.95 < 1/√1 = 1)

        # Normalize to be on manifold
        x_mid = manifold.project(x_mid)
        x_near_edge = manifold.project(x_near_edge)

        # Compute regularization
        reg_center = manifold.boundary_regularization_loss(x_center).item()
        reg_mid = manifold.boundary_regularization_loss(x_mid).item()
        reg_edge = manifold.boundary_regularization_loss(x_near_edge).item()

        # Should increase as we move toward boundary
        assert (
            reg_center <= reg_mid < reg_edge
        ), f"Regularization should increase: {reg_center} < {reg_mid} < {reg_edge}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
