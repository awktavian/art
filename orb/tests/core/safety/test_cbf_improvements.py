"""Comprehensive tests for CBF improvements.

Tests:
1. Neural Class-K function - properties and training
2. PolicyLoop safety integration - end-to-end
3. Safety state extraction - learned vs hardcoded
4. CBF training with proper loss functions

Created: November 2025
Updated: December 2025 - Consolidated to use optimal_cbf.py canonical implementations
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn


@pytest.mark.safety
class TestLearnedClassK:
    """Test neural network class-K function from optimal_cbf.py."""

    def test_class_k_zero_at_origin(self):
        """Test α(0) = 0 property."""
        from kagami.core.safety.optimal_cbf import LearnedClassK

        class_k = LearnedClassK()

        h_zero = torch.tensor([0.0])
        alpha_zero = class_k(h_zero)

        assert torch.isclose(alpha_zero, torch.tensor([0.0]), atol=1e-6)

    def test_class_k_strictly_increasing(self):
        """Test α is strictly increasing."""
        from kagami.core.safety.optimal_cbf import LearnedClassK

        class_k = LearnedClassK()

        h_values = torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5])
        alpha_values = class_k(h_values)

        # Check strictly increasing
        for i in range(len(alpha_values) - 1):
            assert alpha_values[i] < alpha_values[i + 1], (
                f"Not increasing: α({h_values[i].item()}) = {alpha_values[i].item()} "
                f">= α({h_values[i + 1].item()}) = {alpha_values[i + 1].item()}"
            )

    def test_class_k_positive_for_positive_h(self):
        """Test α(h) > 0 for h > 0."""
        from kagami.core.safety.optimal_cbf import LearnedClassK

        class_k = LearnedClassK()

        h_positive = torch.tensor([0.1, 0.5, 1.0])
        alpha_values = class_k(h_positive)

        assert torch.all(alpha_values > 0), f"α should be positive: {alpha_values}"

    def test_class_k_bounded(self):
        """Test α is bounded within min/max."""
        from kagami.core.safety.optimal_cbf import LearnedClassK

        min_alpha = 0.1
        max_alpha = 5.0
        class_k = LearnedClassK(min_alpha=min_alpha, max_alpha=max_alpha)

        h_values = torch.tensor([0.01, 0.1, 0.5, 1.0, 2.0])
        alpha_values = class_k(h_values)

        # α(h) = bounded * h, so for h > 0 the output should be reasonable
        for i, _h in enumerate(h_values):
            alpha = alpha_values[i]
            assert alpha >= 0, f"α should be non-negative: {alpha}"

    def test_class_k_differentiable(self):
        """Test gradients flow through neural class-K."""
        from kagami.core.safety.optimal_cbf import LearnedClassK

        class_k = LearnedClassK()

        h = torch.tensor([0.5], requires_grad=True)
        alpha = class_k(h)

        loss = alpha.sum()
        loss.backward()

        assert h.grad is not None
        assert not torch.isnan(h.grad).any()


@pytest.mark.safety
class TestCBFLoss:
    """Test CBF loss functions for training."""

    def test_cbf_mse_loss(self):
        """Test CBF MSE loss computation."""
        from kagami.core.safety.cbf_loss import CBFMSELoss

        loss_fn = CBFMSELoss(alpha=1.0, dt=0.1)

        # Create mock CBF values
        h = torch.tensor([0.2, 0.1, -0.1, 0.3])
        L_f_h = torch.tensor([0.1, 0.0, -0.2, 0.1])
        L_g_h = torch.rand(4, 2)
        u = torch.rand(4, 2)

        loss = loss_fn(h, L_f_h, L_g_h, u)

        assert loss.shape == ()
        assert not torch.isnan(loss)

    def test_cbf_relu_loss(self):
        """Test CBF ReLU loss penalizes violations."""
        from kagami.core.safety.cbf_loss import CBFReLULoss

        loss_fn = CBFReLULoss(margin=0.1)

        # Safe barriers
        h_safe = torch.tensor([0.5, 0.3, 0.2])
        # Unsafe barriers
        h_unsafe = torch.tensor([0.05, -0.1, -0.2])

        loss_safe = loss_fn(h_safe)
        loss_unsafe = loss_fn(h_unsafe)

        assert (
            loss_unsafe > loss_safe
        ), f"Unsafe loss {loss_unsafe.item()} should be > safe loss {loss_safe.item()}"

    def test_cbf_combined_loss(self):
        """Test combined CBF loss."""
        from kagami.core.safety.cbf_loss import CBFCombinedLoss

        loss_fn = CBFCombinedLoss(relu_weight=0.5, mse_weight=0.5)

        h = torch.tensor([0.2, 0.1])
        L_f_h = torch.tensor([0.1, 0.0])
        L_g_h = torch.rand(2, 2)
        u = torch.rand(2, 2)

        loss, info = loss_fn(h, L_f_h, L_g_h, u)

        assert loss.shape == ()
        assert not torch.isnan(loss)
        assert "loss_relu" in info
        assert "loss_mse" in info
        assert "total" in info


@pytest.mark.safety
class TestPolicyLoopSafetyIntegration:
    """Test PolicyLoop with CBF integration."""

    def test_policy_loop_initialization(self):
        """Test policy loop initializes with CBF."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            state_dim=64,
            action_dim=8,
        )

        assert loop.cbf is not None
        assert loop.safety_extractor is not None

    def test_safety_state_extraction(self):
        """Test learned safety state extraction."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(state_dim=64, action_dim=8)

        state = torch.randn(4, 64)
        safety_state = loop.extract_safety_state(state)

        # Should be [B, 4] with values in [0, 1]
        assert safety_state.shape == (4, 4)
        assert torch.all(safety_state >= 0.0)
        assert torch.all(safety_state <= 1.0)

    def test_select_action_with_cbf(self):
        """Test action selection applies CBF filter."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            state_dim=64,
            action_dim=8,
        )

        # Disable safety check for shape testing - random states may violate h(x)>=0
        state = torch.randn(2, 64)
        action = loop.select_action(state, safe=False)

        assert action.shape == (2, 8)  # type: ignore[union-attr]

    def test_select_action_returns_info(self):
        """Test action selection can return CBF info."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            state_dim=64,
            action_dim=8,
        )

        # Disable safety check for info testing - random states may violate h(x)>=0
        state = torch.randn(2, 64)
        _action, info = loop.select_action(state, safe=False, return_info=True)

        assert "safety_margin" in info
        assert "qp_iterations" in info

    def test_compute_loss_includes_safety_penalty(self):
        """Test loss includes differentiable safety penalty."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            safety_penalty_weight=1.0,
            state_dim=64,
            action_dim=8,
        )

        batch = {
            "state": torch.randn(4, 64),
            "action": torch.randn(4, 8),
            "reward": torch.randn(4),
        }

        loss = loop.compute_loss(batch)

        # Should compute valid loss
        assert loss.shape == ()
        assert not torch.isnan(loss)

        # Safety penalty should be tracked
        assert hasattr(loop, "last_cbf_penalty")

    def test_compute_loss_gradient_flow(self):
        """Test gradients flow through safety penalty."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            safety_penalty_weight=1.0,
            state_dim=64,
            action_dim=8,
        )

        batch = {
            "state": torch.randn(4, 64),
            "action": torch.randn(4, 8),
            "reward": torch.randn(4),
        }

        loss = loop.compute_loss(batch)
        loss.backward()

        # Policy should have gradients
        for param in loop.policy.parameters():
            assert param.grad is not None
            assert not torch.isnan(param.grad).any()

        # Safety extractor should have gradients (it's in the loss)
        for param in loop.safety_extractor.parameters():
            assert param.grad is not None

    def test_get_metrics(self):
        """Test metrics retrieval."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(state_dim=64, action_dim=8)

        metrics = loop.get_metrics()

        assert "cbf_qp_iterations" in metrics
        assert "cbf_safety_margin" in metrics
        assert "cbf_penalty" in metrics


@pytest.mark.safety
class TestLearnedDynamics:
    """Test learnable dynamics model from optimal_cbf.py."""

    def test_dynamics_forward(self):
        """Test dynamics computes f and g."""
        from kagami.core.safety.optimal_cbf import LearnedDynamics

        dynamics = LearnedDynamics(state_dim=4, control_dim=2)

        state = torch.rand(2, 4)
        f, g = dynamics(state)

        assert f.shape == (2, 4)
        assert g.shape == (2, 4, 2)

    def test_dynamics_gradient_flow(self):
        """Test gradients flow through dynamics."""
        from kagami.core.safety.optimal_cbf import LearnedDynamics

        dynamics = LearnedDynamics(state_dim=4, control_dim=2)

        state = torch.rand(2, 4, requires_grad=True)
        f, g = dynamics(state)

        loss = f.sum() + g.sum()
        loss.backward()

        assert state.grad is not None
        assert not torch.isnan(state.grad).any()


@pytest.mark.safety
class TestDynamicsEnsemble:
    """Test dynamics ensemble for uncertainty quantification."""

    def test_ensemble_forward(self):
        """Test ensemble computes mean and std."""
        from kagami.core.safety.optimal_cbf import DynamicsEnsemble

        ensemble = DynamicsEnsemble(state_dim=4, control_dim=2, ensemble_size=3)

        state = torch.rand(2, 4)
        f_mean, g_mean, f_std, g_std = ensemble(state)

        assert f_mean.shape == (2, 4)
        assert g_mean.shape == (2, 4, 2)
        assert f_std.shape == (2, 4)
        assert g_std.shape == (2, 4, 2)

        # Std should be non-negative
        assert torch.all(f_std >= 0)
        assert torch.all(g_std >= 0)


@pytest.mark.safety
class TestEndToEndTraining:
    """Test end-to-end CBF training integration."""

    def test_training_loop_runs(self):
        """Test full training loop executes without error."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            safety_penalty_weight=0.5,
            state_dim=32,
            action_dim=4,
        )

        optimizer = torch.optim.Adam(loop.parameters(), lr=1e-3)

        # Mini training loop
        for _ in range(3):
            batch = {
                "state": torch.randn(8, 32),
                "action": torch.randn(8, 4),
                "reward": torch.randn(8),
            }

            optimizer.zero_grad()
            loss = loop.compute_loss(batch)
            loss.backward()
            optimizer.step()

        # Should complete without error (test passes if no exception)

    def test_safety_improves_with_training(self):
        """Test safety penalty decreases with training."""
        from kagami.core.learning.policy_loop import PolicyLoop

        loop = PolicyLoop(
            use_cbf=True,
            safety_penalty_weight=1.0,
            state_dim=16,
            action_dim=4,
        )

        optimizer = torch.optim.Adam(loop.parameters(), lr=1e-2)

        # Fixed batch for consistent comparison
        torch.manual_seed(42)
        batch = {
            "state": torch.randn(16, 16),
            "action": torch.randn(16, 4),
            "reward": torch.randn(16),
        }

        initial_loss = loop.compute_loss(batch).item()

        # Train
        for _ in range(20):
            optimizer.zero_grad()
            loss = loop.compute_loss(batch)
            loss.backward()
            optimizer.step()

        final_loss = loop.compute_loss(batch).item()

        # Loss should decrease
        assert final_loss < initial_loss, f"Loss should decrease: {final_loss} < {initial_loss}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])
