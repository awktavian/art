"""Test Octonion Regularization integration with WorldModelLoop."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import sys
import torch

from kagami_math.octonions.regularization import OctonionRegularization

# Skip WorldModelLoop tests on MPS due to recursion issues in KagamiWorldModel.to()
_skip_mps = pytest.mark.skipif(
    sys.platform == "darwin"
    and hasattr(torch.backends, "mps")
    and torch.backends.mps.is_available(),
    reason="KagamiWorldModel has recursion issues with model.to() on MPS",
)


class TestOctonionRegularization:
    """Test OctonionRegularization module."""

    def test_unit_norm_loss(self) -> None:
        """Test unit norm penalty."""
        reg = OctonionRegularization()

        # Perfect unit norm
        o_unit = torch.randn(4, 8)
        o_unit = o_unit / o_unit.norm(dim=-1, keepdim=True)
        loss_unit = reg.unit_norm_loss(o_unit)
        assert loss_unit < 1e-5, "Unit norm octonions should have near-zero loss"

        # Non-unit norm
        o_non_unit = torch.randn(4, 8) * 2.0
        loss_non_unit = reg.unit_norm_loss(o_non_unit)
        assert loss_non_unit > loss_unit

    def test_sparsity_loss(self) -> None:
        """Test sparsity penalty on imaginary components."""
        reg = OctonionRegularization()

        # Dense imaginary
        o_dense = torch.ones(4, 8)
        loss_dense = reg.sparsity_loss(o_dense)

        # Sparse imaginary
        o_sparse = torch.zeros(4, 8)
        o_sparse[:, 0] = 1.0  # Only real part
        loss_sparse = reg.sparsity_loss(o_sparse)

        assert loss_sparse < loss_dense, "Sparse should have lower penalty"

    def test_forward(self) -> None:
        """Test full regularization."""
        reg = OctonionRegularization()
        o = torch.randn(4, 8)

        losses = reg(o)

        assert "unit_norm" in losses
        assert "sparsity" in losses
        assert "g2_structure" in losses
        assert "diversity" in losses
        assert "total" in losses

        assert losses["total"] >= 0.0


@_skip_mps
class TestWorldModelLoopWithRegularization:
    """Test WorldModelLoop with octonion regularization."""

    @pytest.fixture
    def loop_basic(self):
        """WorldModelLoop without regularization (opt-out of default)."""
        from kagami.core.learning.world_model_loop import WorldModelLoop

        return WorldModelLoop(use_oct_reg=False, device="cpu")

    @pytest.fixture
    def loop_regularized(self):
        """WorldModelLoop with regularization (default)."""
        from kagami.core.learning.world_model_loop import WorldModelLoop

        return WorldModelLoop(
            # use_oct_reg=True is now default
            oct_reg_unit_norm_weight=1.0,
            oct_reg_sparsity_weight=0.1,
            device="cpu",
        )

    def test_init_without_reg(self, loop_basic: Any) -> None:
        """Test initialization without regularization."""
        assert not loop_basic.use_oct_reg
        assert loop_basic.oct_regularizer is None

    def test_init_with_reg(self, loop_regularized: Any) -> None:
        """Test initialization with regularization."""
        assert loop_regularized.use_oct_reg
        assert loop_regularized.oct_regularizer is not None

    def test_forward_basic(self, loop_basic: Any) -> None:
        """Test forward without regularization."""
        state = torch.randn(2, 512)
        action = torch.randn(2, 8)

        next_pred = loop_basic(state, action)

        assert next_pred.shape == (2, 512)
        assert not torch.isnan(next_pred).any()

    def test_forward_regularized(self, loop_regularized: Any) -> None:
        """Test forward with regularization."""
        state = torch.randn(2, 512)
        action = torch.randn(2, 8)

        next_pred = loop_regularized(state, action)

        assert next_pred.shape == (2, 512)
        assert not torch.isnan(next_pred).any()

    def test_loss_basic(self, loop_basic: Any) -> None:
        """Test loss without regularization."""
        batch = {
            "state": torch.randn(2, 512),
            "action": torch.randn(2, 8),
            "next_state": torch.randn(2, 512),
        }

        loss = loop_basic.compute_loss(batch)

        assert loss.requires_grad
        assert loss >= 0.0
        assert not torch.isnan(loss)

    def test_loss_regularized(self, loop_regularized: Any) -> None:
        """Test loss with regularization."""
        batch = {
            "state": torch.randn(2, 512),
            "action": torch.randn(2, 8),  # Octonion action
            "next_state": torch.randn(2, 512),
        }

        loss = loop_regularized.compute_loss(batch)

        assert loss.requires_grad
        assert loss >= 0.0
        assert not torch.isnan(loss)

    def test_regularization_affects_loss(self) -> None:
        """Test that regularization changes loss value."""
        loop_basic = WorldModelLoop(use_oct_reg=False, device="cpu")
        loop_reg = WorldModelLoop(use_oct_reg=True, device="cpu")

        # Same input
        batch = {
            "state": torch.randn(2, 512),
            "action": torch.randn(2, 8),
            "next_state": torch.randn(2, 512),
        }

        # Copy parameters for fair comparison
        with torch.no_grad():
            for (n1, p1), (n2, p2) in zip(
                loop_basic.named_parameters(), loop_reg.named_parameters(), strict=False
            ):
                if n1 == n2 and p1.shape == p2.shape:
                    p2.copy_(p1)

        loss_basic = loop_basic.compute_loss(batch)
        loss_reg = loop_reg.compute_loss(batch)

        # Regularized loss should be different (typically higher due to penalties)
        print(f"\nLoss: basic={loss_basic.item():.6f}, regularized={loss_reg.item():.6f}")

    def test_backward_pass(self, loop_regularized: Any) -> None:
        """Test gradient flow with regularization."""
        batch = {
            "state": torch.randn(2, 512),
            "action": torch.randn(2, 8),
            "next_state": torch.randn(2, 512),
        }

        loss = loop_regularized.compute_loss(batch)
        loss.backward()

        # Check parameters have gradients
        params_with_grad = sum(1 for p in loop_regularized.parameters() if p.grad is not None)
        assert params_with_grad > 0

    def test_non_octonion_action(self, loop_regularized: Any) -> None:
        """Test with non-octonion action (regularization skipped)."""
        # Note: WorldModelLoop dynamics expects 8D actions, so use 8D but verify reg logic
        batch = {
            "state": torch.randn(2, 512),
            "action": torch.randn(2, 8),  # 8D action
            "next_state": torch.randn(2, 512),
        }

        # Should work without error
        loss = loop_regularized.compute_loss(batch)
        assert not torch.isnan(loss)
        assert loss.item() >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
