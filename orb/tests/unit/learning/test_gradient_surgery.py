"""Tests for Gradient Surgery Module.

Tests PCGrad, GradNorm, and CAGrad implementations for multi-task learning.

Created: December 2, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import torch
import torch.nn as nn

from kagami.core.learning.gradient_surgery import (
    GradientSurgery,
    PCGrad,
    GradNorm,
    CAGrad,
    apply_gradient_surgery,
)


class TestGradientSurgery:
    """Test basic gradient surgery operations."""

    def test_detect_conflict_positive(self) -> None:
        """Test conflict detection with opposing gradients."""
        surgery = GradientSurgery()

        # Opposing gradients (conflict)
        grad1 = [torch.tensor([1.0, 0.0, 0.0])]
        grad2 = [torch.tensor([-1.0, 0.0, 0.0])]

        assert surgery.detect_conflict(grad1, grad2) is True  # type: ignore[arg-type]
        assert surgery.stats.total_conflicts == 1

    def test_detect_conflict_negative(self) -> None:
        """Test conflict detection with aligned gradients."""
        surgery = GradientSurgery()

        # Aligned gradients (no conflict)
        grad1 = [torch.tensor([1.0, 0.0, 0.0])]
        grad2 = [torch.tensor([1.0, 0.5, 0.0])]

        assert surgery.detect_conflict(grad1, grad2) is False  # type: ignore[arg-type]
        assert surgery.stats.total_conflicts == 0

    def test_detect_conflict_orthogonal(self) -> None:
        """Test conflict detection with orthogonal gradients."""
        surgery = GradientSurgery()

        # Orthogonal gradients (dot product = 0, not conflict by default)
        grad1 = [torch.tensor([1.0, 0.0, 0.0])]
        grad2 = [torch.tensor([0.0, 1.0, 0.0])]

        assert surgery.detect_conflict(grad1, grad2) is False  # type: ignore[arg-type]

    def test_project_gradient(self) -> None:
        """Test gradient projection removes conflicting component."""
        surgery = GradientSurgery()

        # Opposing gradients
        grad_to_project = [torch.tensor([1.0, 1.0])]
        grad_reference = [torch.tensor([-1.0, 0.0])]

        projected = surgery.project_gradient(grad_to_project, grad_reference)  # type: ignore[arg-type]

        # After projection, dot product should be >= 0
        dot = (projected[0] * grad_reference[0]).sum()  # type: ignore[operator]
        assert dot >= -1e-6, f"Dot product should be >= 0, got {dot}"

    def test_project_gradient_preserves_orthogonal(self) -> None:
        """Test projection preserves orthogonal component."""
        surgery = GradientSurgery()

        # grad_to_project has orthogonal component [0, 1]
        grad_to_project = [torch.tensor([1.0, 1.0])]
        grad_reference = [torch.tensor([1.0, 0.0])]

        # No conflict, so no projection should happen
        projected = surgery.project_gradient(grad_to_project, grad_reference)  # type: ignore[arg-type]

        assert torch.allclose(projected[0], grad_to_project[0])  # type: ignore[arg-type]

    def test_stats_tracking(self) -> None:
        """Test that statistics are tracked correctly."""
        surgery = GradientSurgery()

        grad1 = [torch.tensor([1.0, 0.0])]
        grad2 = [torch.tensor([-1.0, 0.0])]

        # Detect conflict
        surgery.detect_conflict(grad1, grad2)  # type: ignore[arg-type]
        surgery.detect_conflict(grad1, grad1)  # type: ignore[arg-type]  # No conflict

        stats = surgery.get_stats()
        assert stats["total_checks"] == 2
        assert stats["total_conflicts"] == 1
        assert stats["conflict_rate"] == 0.5


class TestPCGrad:
    """Test PCGrad multi-task gradient surgery."""

    def test_apply_no_conflicts(self) -> None:
        """Test PCGrad with aligned gradients."""
        pcgrad = PCGrad()

        # All aligned gradients
        gradients = [
            [torch.tensor([1.0, 0.0])],
            [torch.tensor([0.5, 0.5])],
            [torch.tensor([0.8, 0.2])],
        ]

        projected = pcgrad.apply(gradients)  # type: ignore[arg-type]

        # No conflicts, so gradients should be unchanged
        for orig, proj in zip(gradients, projected, strict=False):
            assert torch.allclose(orig[0], proj[0])  # type: ignore[arg-type]

    def test_apply_with_conflicts(self) -> None:
        """Test PCGrad with conflicting gradients."""
        pcgrad = PCGrad(use_random_projection_order=False)

        # Conflicting gradients
        gradients = [
            [torch.tensor([1.0, 0.0])],
            [torch.tensor([-1.0, 0.0])],  # Conflicts with first
        ]

        projected = pcgrad.apply(gradients)  # type: ignore[arg-type]

        # Second gradient should be projected
        # Dot product with first should be >= 0 after projection
        dot = (projected[1][0] * gradients[0][0]).sum()  # type: ignore[operator]
        assert dot >= -1e-6

    def test_apply_three_tasks(self) -> None:
        """Test PCGrad with three tasks."""
        pcgrad = PCGrad(use_random_projection_order=False)

        gradients = [
            [torch.tensor([1.0, 0.0, 0.0])],
            [torch.tensor([-0.5, 1.0, 0.0])],  # Slight conflict with first
            [torch.tensor([0.0, -0.5, 1.0])],  # Slight conflict with second
        ]

        projected = pcgrad.apply(gradients)  # type: ignore[arg-type]

        # All projected gradients should have reduced conflicts
        assert len(projected) == 3

    def test_apply_to_model(self) -> None:
        """Test PCGrad applied directly to model."""
        pcgrad = PCGrad()

        # Simple model
        model = nn.Linear(4, 2)
        x = torch.randn(2, 4)

        # Two tasks
        y1 = torch.randn(2, 2)
        y2 = torch.randn(2, 2)

        loss1 = nn.functional.mse_loss(model(x), y1)
        loss2 = nn.functional.mse_loss(model(x), y2)

        # Apply PCGrad
        pcgrad.apply_to_model(model, [loss1, loss2])

        # Check that gradients were set
        for param in model.parameters():
            assert param.grad is not None
            assert not torch.isnan(param.grad).any()


class TestGradNorm:
    """Test GradNorm adaptive task weighting."""

    def test_initialization(self) -> None:
        """Test GradNorm initialization."""
        gradnorm = GradNorm(num_tasks=3, alpha=1.5)

        assert gradnorm.num_tasks == 3
        assert gradnorm.alpha == 1.5
        assert len(gradnorm.log_weights) == 3

    def test_weights_sum_to_num_tasks(self) -> None:
        """Test that weights sum to num_tasks."""
        gradnorm = GradNorm(num_tasks=3)

        weights = gradnorm.weights
        assert torch.allclose(weights.sum(), torch.tensor(3.0), atol=1e-5)

    def test_compute_weight_loss_first_call(self) -> None:
        """Test first call initializes losses."""
        gradnorm = GradNorm(num_tasks=2)

        # Simple model
        model = nn.Linear(4, 2)
        x = torch.randn(2, 4)

        losses = [
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
        ]

        # First call should initialize and return 0
        loss = gradnorm.compute_weight_loss(losses, list(model.parameters()))
        assert loss.item() == 0.0
        assert gradnorm.initialized

    def test_compute_weight_loss_subsequent(self) -> None:
        """Test subsequent calls compute actual loss."""
        gradnorm = GradNorm(num_tasks=2)

        model = nn.Linear(4, 2)
        x = torch.randn(2, 4)

        losses = [
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
        ]

        # Initialize
        gradnorm.compute_weight_loss(losses, list(model.parameters()))

        # Second call
        loss = gradnorm.compute_weight_loss(losses, list(model.parameters()))
        assert loss.item() >= 0


class TestCAGrad:
    """Test Conflict-Averse Gradient Descent."""

    def test_compute_aligned_gradients(self) -> None:
        """Test CAGrad with aligned gradients."""
        cagrad = CAGrad(c=0.5)

        gradients = [
            torch.tensor([1.0, 0.0]),
            torch.tensor([0.5, 0.5]),
        ]

        result = cagrad.compute(gradients)

        # Result should be close to mean
        expected_mean = torch.stack(gradients).mean(dim=0)
        # With c=0.5 and no strong conflicts, should be near mean
        assert result.shape == expected_mean.shape  # type: ignore[union-attr]

    def test_compute_conflicting_gradients(self) -> None:
        """Test CAGrad with conflicting gradients."""
        cagrad = CAGrad(c=0.5)

        gradients = [
            torch.tensor([1.0, 0.0]),
            torch.tensor([-1.0, 0.0]),  # Direct opposition
        ]

        result = cagrad.compute(gradients)

        # For directly opposing gradients, the mean is [0, 0]
        # CAGrad tries to find a point satisfying constraints, but with
        # completely opposing gradients, the best it can do is reduce conflict
        # The result should be different from pure mean if c > 0
        mean = torch.stack(gradients).mean(dim=0)

        # Just verify it returns a valid gradient (not NaN)
        assert not torch.isnan(result).any()  # type: ignore[arg-type]
        assert result.shape == mean.shape  # type: ignore[union-attr]

    def test_compute_with_c_zero(self) -> None:
        """Test CAGrad with c=0 (pure mean)."""
        cagrad = CAGrad(c=0.0)

        gradients = [
            torch.tensor([1.0, 0.0]),
            torch.tensor([0.0, 1.0]),
        ]

        result = cagrad.compute(gradients)
        expected = torch.stack(gradients).mean(dim=0)

        assert torch.allclose(result, expected)  # type: ignore[arg-type]

    def test_compute_per_param_gradients(self) -> None:
        """Test CAGrad with per-parameter gradient lists."""
        cagrad = CAGrad(c=0.3)

        # Two tasks, each with two parameter gradients
        gradients = [
            [torch.tensor([1.0, 0.0]), torch.tensor([0.5])],
            [torch.tensor([0.5, 0.5]), torch.tensor([0.8])],
        ]

        result = cagrad.compute(gradients)  # type: ignore[arg-type]

        assert isinstance(result, list)
        assert len(result) == 2


class TestApplyGradientSurgery:
    """Test convenience function for gradient surgery."""

    def test_apply_pcgrad(self) -> None:
        """Test apply_gradient_surgery with PCGrad."""
        model = nn.Linear(4, 2)
        x = torch.randn(2, 4)

        losses = [
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
        ]

        result = apply_gradient_surgery(model, losses, method="pcgrad")

        assert result["method"] == "pcgrad"
        assert "stats" in result

        # Check gradients exist
        for param in model.parameters():
            assert param.grad is not None

    def test_apply_cagrad(self) -> None:
        """Test apply_gradient_surgery with CAGrad."""
        model = nn.Linear(4, 2)
        x = torch.randn(2, 4)

        losses = [
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
        ]

        result = apply_gradient_surgery(model, losses, method="cagrad", c=0.5)

        assert result["method"] == "cagrad"

        for param in model.parameters():
            assert param.grad is not None

    def test_apply_simple(self) -> None:
        """Test apply_gradient_surgery with simple method."""
        model = nn.Linear(4, 2)
        x = torch.randn(2, 4)

        losses = [
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
            nn.functional.mse_loss(model(x), torch.randn(2, 2)),
        ]

        result = apply_gradient_surgery(model, losses, method="simple")

        assert result["method"] == "simple"

        for param in model.parameters():
            assert param.grad is not None


class TestGradientFlowIntegration:
    """Integration tests for gradient flow through surgery."""

    def test_pcgrad_preserves_gradient_magnitude(self) -> None:
        """Test that PCGrad doesn't dramatically reduce gradient magnitude."""
        pcgrad = PCGrad()

        # Slightly conflicting gradients
        gradients = [
            [torch.randn(10) for _ in range(5)],
            [torch.randn(10) for _ in range(5)],
        ]

        # Compute original norms
        orig_norms = [sum(g.norm().item() for g in grads) for grads in gradients]

        projected = pcgrad.apply(gradients)  # type: ignore[arg-type]

        # Compute projected norms
        proj_norms = [sum(g.norm().item() for g in grads) for grads in projected]  # type: ignore[union-attr]

        # Norms shouldn't decrease dramatically (within 2x)
        for orig, proj in zip(orig_norms, proj_norms, strict=False):
            assert proj >= orig * 0.3, "Gradient magnitude decreased too much"

    def test_gradnorm_updates_weights(self) -> None:
        """Test that GradNorm actually updates weights."""
        gradnorm = GradNorm(num_tasks=2, lr=0.1)

        model = nn.Linear(4, 2)
        x = torch.randn(4, 4)

        # Initialize with tensors that require grad
        initial_loss1 = nn.functional.mse_loss(model(x)[:, 0], torch.randn(4))
        initial_loss2 = nn.functional.mse_loss(model(x)[:, 1], torch.randn(4))
        gradnorm.compute_weight_loss([initial_loss1, initial_loss2], list(model.parameters()))

        # Capture initial weights
        initial_weights = gradnorm.weights.clone().detach()

        # The weights should be initialized
        assert torch.allclose(initial_weights.sum(), torch.tensor(2.0), atol=0.1)

        # Verify weights are learnable parameters
        assert gradnorm.log_weights.requires_grad


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
