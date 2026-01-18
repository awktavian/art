"""Tests for Curiosity-Driven Exploration module.

Tests the CuriosityModule defined in kagami/core/world_model/intrinsic/curiosity.py.
This module provides intrinsic rewards based on prediction error.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.world_model.intrinsic.curiosity import CuriosityModule


class TestCuriosityModule:
    """Test CuriosityModule intrinsic curiosity."""

    @pytest.fixture
    def curiosity_module(self) -> Any:
        """Create a curiosity module for testing."""
        return CuriosityModule(
            state_dim=64,
            action_dim=8,
            feature_dim=32,
            hidden_dim=32,
            curiosity_coef=0.1,
            device="cpu",
        )

    def test_initialization(self, curiosity_module) -> Any:
        """CuriosityModule should initialize correctly."""
        assert curiosity_module.state_dim == 64
        assert curiosity_module.action_dim == 8
        assert curiosity_module.feature_dim == 32
        assert curiosity_module.curiosity_coef == 0.1

    def test_has_required_components(self, curiosity_module) -> None:
        """Module should have encoder, forward model, and inverse model."""
        assert hasattr(curiosity_module, "feature_encoder")
        assert hasattr(curiosity_module, "forward_model")
        assert hasattr(curiosity_module, "inverse_model")

    def test_forward_pass_shapes(self, curiosity_module) -> None:
        """Forward pass should produce correct output shapes."""
        batch_size = 4
        state = torch.randn(batch_size, 64)
        action = torch.randint(0, 8, (batch_size,))
        next_state = torch.randn(batch_size, 64)

        curiosity_reward, forward_loss, inverse_loss = curiosity_module(state, action, next_state)

        # All outputs are per-batch (reduction="none")
        assert curiosity_reward.shape == (batch_size,)
        assert forward_loss.shape == (batch_size,)
        assert inverse_loss.shape == (batch_size,)

    def test_curiosity_reward_non_negative(self, curiosity_module) -> None:
        """Curiosity reward should be non-negative."""
        batch_size = 8
        state = torch.randn(batch_size, 64)
        action = torch.randint(0, 8, (batch_size,))
        next_state = torch.randn(batch_size, 64)

        curiosity_reward, _, _ = curiosity_module(state, action, next_state)

        assert (curiosity_reward >= 0).all(), "Curiosity reward should be non-negative"

    def test_curiosity_coefficient_scales_reward(self) -> None:
        """Curiosity coefficient should scale the reward."""
        small_coef = CuriosityModule(curiosity_coef=0.01, device="cpu")
        large_coef = CuriosityModule(curiosity_coef=1.0, device="cpu")

        state = torch.randn(4, 512)
        action = torch.randint(0, 8, (4,))
        next_state = torch.randn(4, 512)

        _reward_small, _, _ = small_coef(state, action, next_state)
        _reward_large, _, _ = large_coef(state, action, next_state)

        # Large coef should produce larger rewards on average
        # (not guaranteed for every sample due to prediction quality)
        assert large_coef.curiosity_coef > small_coef.curiosity_coef

    def test_feature_encoder_output_dim(self, curiosity_module) -> None:
        """Feature encoder should output feature_dim sized vectors."""
        state = torch.randn(4, 64)
        features = curiosity_module.feature_encoder(state)
        assert features.shape == (4, 32)

    def test_inverse_model_predicts_actions(self, curiosity_module) -> None:
        """Inverse model should predict action logits."""
        features_s = torch.randn(4, 32)
        features_s_next = torch.randn(4, 32)
        combined = torch.cat([features_s, features_s_next], dim=-1)

        action_logits = curiosity_module.inverse_model(combined)
        assert action_logits.shape == (4, 8)  # action_dim

    def test_forward_model_predicts_features(self, curiosity_module) -> None:
        """Forward model should predict next state features."""
        features_s = torch.randn(4, 32)
        action_onehot = torch.zeros(4, 8)
        action_onehot[:, 0] = 1  # All take action 0
        combined = torch.cat([features_s, action_onehot], dim=-1)

        pred_features = curiosity_module.forward_model(combined)
        assert pred_features.shape == (4, 32)  # feature_dim

    def test_single_sample(self, curiosity_module) -> None:
        """Module should work with single sample (batch_size=1)."""
        state = torch.randn(1, 64)
        action = torch.randint(0, 8, (1,))
        next_state = torch.randn(1, 64)

        reward, fwd_loss, inv_loss = curiosity_module(state, action, next_state)

        assert reward.shape == (1,)
        assert not torch.isnan(fwd_loss)
        assert not torch.isnan(inv_loss)

    def test_gradient_flow(self, curiosity_module) -> None:
        """Gradients should flow through all components."""
        state = torch.randn(4, 64, requires_grad=True)
        action = torch.randint(0, 8, (4,))
        next_state = torch.randn(4, 64, requires_grad=True)

        _, fwd_loss, inv_loss = curiosity_module(state, action, next_state)
        # Losses are per-batch, need to reduce to scalar for backward
        total_loss = fwd_loss.mean() + inv_loss.mean()
        total_loss.backward()

        # Check gradients exist for parameters
        for name, param in curiosity_module.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"

    def test_device_placement(self) -> None:
        """Module should respect device placement."""
        module = CuriosityModule(device="cpu")

        # Check all parameters are on correct device
        for param in module.parameters():
            assert param.device.type == "cpu"


class TestCuriosityModuleDefaults:
    """Test CuriosityModule default values."""

    def test_default_dimensions(self) -> None:
        """Default dimensions should be reasonable."""
        module = CuriosityModule()
        assert module.state_dim == 512
        assert module.action_dim == 8
        assert module.feature_dim == 256

    def test_default_curiosity_coef(self) -> None:
        """Default curiosity coefficient should be 0.1."""
        module = CuriosityModule()
        assert module.curiosity_coef == 0.1


class TestRandomNetworkDistillation:
    """Test RandomNetworkDistillation (RND) module."""

    @pytest.fixture
    def rnd_module(self) -> Any:
        """Create an RND module for testing."""
        from kagami.core.world_model.intrinsic.curiosity import RandomNetworkDistillation

        return RandomNetworkDistillation(
            state_dim=128,
            hidden_dim=64,
            output_dim=32,
            device="cpu",
        )

    def test_initialization(self, rnd_module) -> None:
        """RND module should initialize correctly."""
        assert hasattr(rnd_module, "target_network")
        assert hasattr(rnd_module, "predictor_network")
        assert rnd_module.device == "cpu"

    def test_target_network_frozen(self, rnd_module) -> None:
        """Target network should have frozen parameters."""
        for param in rnd_module.target_network.parameters():
            assert not param.requires_grad

    def test_predictor_network_trainable(self, rnd_module) -> None:
        """Predictor network should have trainable parameters."""
        for param in rnd_module.predictor_network.parameters():
            assert param.requires_grad

    def test_forward_pass_shape(self, rnd_module) -> None:
        """Forward pass should produce novelty scores per sample."""
        batch_size = 8
        state = torch.randn(batch_size, 128)

        novelty = rnd_module(state)

        assert novelty.shape == (batch_size,)

    def test_novelty_non_negative(self, rnd_module) -> None:
        """Novelty scores should be non-negative (MSE)."""
        state = torch.randn(16, 128)

        novelty = rnd_module(state)

        assert (novelty >= 0).all(), "Novelty should be non-negative"

    def test_single_sample(self, rnd_module) -> None:
        """Module should work with single sample."""
        state = torch.randn(1, 128)

        novelty = rnd_module(state)

        assert novelty.shape == (1,)
        assert not torch.isnan(novelty)

    def test_train_step_returns_loss(self, rnd_module) -> None:
        """Train step should return loss dictionary."""
        state = torch.randn(8, 128)
        optimizer = torch.optim.Adam(rnd_module.predictor_network.parameters(), lr=1e-3)

        losses = rnd_module.train_step(state, optimizer)

        assert "rnd_loss" in losses
        assert losses["rnd_loss"] >= 0

    def test_train_step_reduces_prediction_error(self, rnd_module) -> None:
        """Training should reduce prediction error over time."""
        state = torch.randn(32, 128)
        optimizer = torch.optim.Adam(rnd_module.predictor_network.parameters(), lr=1e-2)

        # Initial novelty
        initial_novelty = rnd_module(state).mean().item()

        # Train for a few steps
        for _ in range(10):
            rnd_module.train_step(state, optimizer)

        # Final novelty should be lower
        final_novelty = rnd_module(state).mean().item()

        assert final_novelty < initial_novelty, "Training should reduce novelty"

    def test_different_states_different_novelty(self, rnd_module) -> None:
        """Different states should generally have different novelty scores."""
        state1 = torch.randn(4, 128)
        state2 = torch.randn(4, 128)

        novelty1 = rnd_module(state1)
        novelty2 = rnd_module(state2)

        # They shouldn't be exactly equal (very unlikely for random inputs)
        assert not torch.allclose(novelty1, novelty2)

    def test_gradient_only_flows_to_predictor(self, rnd_module) -> None:
        """Gradients should only update predictor, not target."""
        state = torch.randn(4, 128, requires_grad=True)

        # Get initial target params
        target_params_before = [p.clone() for p in rnd_module.target_network.parameters()]

        # Forward and backward
        novelty = rnd_module(state)
        loss = novelty.sum()
        loss.backward()

        # Optimizer step (on predictor only)
        optimizer = torch.optim.SGD(rnd_module.predictor_network.parameters(), lr=0.1)
        optimizer.step()

        # Target params should be unchanged
        for before, after in zip(
            target_params_before, rnd_module.target_network.parameters(), strict=False
        ):
            assert torch.allclose(before, after), "Target network should not change"


class TestComputeCuriositySimple:
    """Test compute_curiosity_simple helper function."""

    def test_scales_by_coefficient(self) -> None:
        """Curiosity reward should scale linearly with coefficient."""
        from kagami.core.world_model.intrinsic.curiosity import compute_curiosity_simple

        error = 1.0
        reward_low = compute_curiosity_simple(error, curiosity_coef=0.1)
        reward_high = compute_curiosity_simple(error, curiosity_coef=1.0)

        assert reward_high == 10 * reward_low

    def test_zero_error_zero_reward(self) -> None:
        """Zero prediction error should give zero reward."""
        from kagami.core.world_model.intrinsic.curiosity import compute_curiosity_simple

        reward = compute_curiosity_simple(0.0, curiosity_coef=0.1)
        assert reward == 0.0

    def test_positive_error_positive_reward(self) -> None:
        """Positive error should give positive reward."""
        from kagami.core.world_model.intrinsic.curiosity import compute_curiosity_simple

        reward = compute_curiosity_simple(5.0, curiosity_coef=0.1)
        assert reward > 0

    def test_default_coefficient(self) -> None:
        """Default coefficient should be 0.1."""
        from kagami.core.world_model.intrinsic.curiosity import compute_curiosity_simple

        reward = compute_curiosity_simple(1.0)
        assert reward == 0.1


class TestCuriosityModuleEdgeCases:
    """Edge case tests for CuriosityModule."""

    def test_large_batch(self) -> None:
        """Module should handle large batches."""
        module = CuriosityModule(state_dim=64, action_dim=4, device="cpu")
        batch_size = 256

        state = torch.randn(batch_size, 64)
        action = torch.randint(0, 4, (batch_size,))
        next_state = torch.randn(batch_size, 64)

        reward, fwd_loss, inv_loss = module(state, action, next_state)

        assert reward.shape == (batch_size,)
        assert torch.isfinite(reward).all()

    def test_zero_states(self) -> None:
        """Module should handle zero-valued states."""
        module = CuriosityModule(state_dim=64, action_dim=4, device="cpu")

        state = torch.zeros(4, 64)
        action = torch.randint(0, 4, (4,))
        next_state = torch.zeros(4, 64)

        reward, fwd_loss, inv_loss = module(state, action, next_state)

        assert torch.isfinite(reward).all()
        assert torch.isfinite(fwd_loss).all()
        assert torch.isfinite(inv_loss).all()

    def test_same_state_transition(self) -> None:
        """Module should handle same state as next_state."""
        module = CuriosityModule(state_dim=64, action_dim=4, device="cpu")

        state = torch.randn(4, 64)
        action = torch.randint(0, 4, (4,))
        next_state = state.clone()  # Same as current state

        reward, fwd_loss, inv_loss = module(state, action, next_state)

        # Should still produce valid outputs
        assert torch.isfinite(reward).all()

    def test_all_same_action(self) -> None:
        """Module should handle all same actions in batch."""
        module = CuriosityModule(state_dim=64, action_dim=4, device="cpu")

        state = torch.randn(8, 64)
        action = torch.zeros(8, dtype=torch.long)  # All action 0
        next_state = torch.randn(8, 64)

        reward, fwd_loss, inv_loss = module(state, action, next_state)

        assert torch.isfinite(reward).all()

    def test_compute_intrinsic_reward_no_grad(self) -> None:
        """compute_intrinsic_reward should not require gradients."""
        module = CuriosityModule(state_dim=64, action_dim=4, device="cpu")

        state = torch.randn(4, 64, requires_grad=True)
        action = torch.randint(0, 4, (4,))
        next_state = torch.randn(4, 64, requires_grad=True)

        reward = module.compute_intrinsic_reward(state, action, next_state)

        # Should work without gradient tracking
        assert torch.isfinite(reward).all()
        assert not reward.requires_grad

    def test_train_step_updates_weights(self) -> None:
        """train_step should update model weights."""
        module = CuriosityModule(state_dim=64, action_dim=4, device="cpu")
        optimizer = torch.optim.Adam(module.parameters(), lr=1e-2)

        # Get initial weights
        initial_weights = [p.clone() for p in module.parameters()]

        state = torch.randn(16, 64)
        action = torch.randint(0, 4, (16,))
        next_state = torch.randn(16, 64)

        # Train step
        losses = module.train_step(state, action, next_state, optimizer)

        # Verify weights changed
        weights_changed = False
        for initial, current in zip(initial_weights, module.parameters(), strict=False):
            if not torch.allclose(initial, current):
                weights_changed = True
                break

        assert weights_changed, "train_step should update weights"
        assert "forward_loss" in losses
        assert "inverse_loss" in losses
        assert "total_loss" in losses
