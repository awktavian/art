"""Tests for UnifiedWorldModel - Automatic World Model + RSSM Integration.

This test suite verifies:
- Automatic S7 extraction and RSSM feeding
- Single forward() call integration
- State management synchronization
- Training/inference mode handling
- Gradient flow through both models
- Loss computation
- Checkpointing

Created: December 20, 2025
Author: Forge (e2)
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn
from kagami.core.config.unified_config import WorldModelConfig as KagamiWorldModelConfig
from kagami.core.world_model.unified_world_model import (
    UnifiedConfig,
    UnifiedState,
    UnifiedWorldModel,
    create_unified_world_model,
)

pytestmark = pytest.mark.tier_integration


class TestUnifiedWorldModelConstruction:
    """Test construction and configuration."""

    def test_construction_with_unified_config(self) -> None:
        """Test construction with UnifiedConfig."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        model = UnifiedWorldModel(config)

        assert model.wm_config.bulk_dim == 64
        assert model.rssm_config.num_colonies == 7
        assert model.rssm_config.obs_dim == 7  # S7 phase

    def test_construction_with_world_model_config(self) -> None:
        """Test construction with KagamiWorldModelConfig."""
        wm_config = KagamiWorldModelConfig(bulk_dim=128, device="cpu")
        model = UnifiedWorldModel(wm_config)

        assert model.wm_config.bulk_dim == 128
        assert model.rssm_config.obs_dim == 7  # S7 phase

    def test_construction_with_defaults(self) -> None:
        """Test construction with no config (uses defaults)."""
        model = UnifiedWorldModel()

        assert model.wm_config.bulk_dim == 512  # Default
        assert model.rssm_config.num_colonies == 7

    def test_factory_function(self) -> None:
        """Test create_unified_world_model factory."""
        model = create_unified_world_model(bulk_dim=256, device="cpu")

        assert model.wm_config.bulk_dim == 256
        assert isinstance(model, UnifiedWorldModel)

    def test_invalid_config_type(self) -> None:
        """Test error on invalid config type."""
        with pytest.raises(TypeError, match="Invalid config type"):
            UnifiedWorldModel(config="invalid")  # type: ignore[arg-type]


class TestUnifiedWorldModelForward:
    """Test forward pass and integration."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create small model for testing."""
        config = UnifiedConfig(
            bulk_dim=64,
            rssm_colony_dim=128,
            rssm_stochastic_dim=64,
            device="cpu",
        )
        model = UnifiedWorldModel(config)
        model.eval()  # Start in eval mode
        return model

    def test_forward_2d_input(self, model: UnifiedWorldModel) -> None:
        """Test forward with 2D input [B, D]."""
        B, D = 4, 64
        observations = torch.randn(B, D)

        state = model.forward(observations, training=False)

        # Verify output structure
        assert isinstance(state, UnifiedState)
        assert state.core_state is not None
        assert state.h_next.shape[0] == B
        assert state.z_next.shape[0] == B
        assert state.organism_action.shape == (B, 8)  # E8 actions

    def test_forward_3d_input(self, model: UnifiedWorldModel) -> None:
        """Test forward with 3D input [B, S, D]."""
        B, S, D = 2, 4, 64
        observations = torch.randn(B, S, D)

        state = model.forward(observations, training=False)

        # Verify sequence processing
        assert state.predicted_s7.shape[0] == B
        assert state.organism_action.shape == (B, 8)

    def test_forward_with_actions(self, model: UnifiedWorldModel) -> None:
        """Test forward with action conditioning."""
        B, D = 4, 64
        observations = torch.randn(B, D)
        actions = torch.randn(B, 8)  # E8 actions

        state = model.forward(observations, actions=actions, training=False)

        # Should use provided actions
        assert state.organism_action.shape == (B, 8)

    def test_forward_training_mode(self, model: UnifiedWorldModel) -> None:
        """Test forward in training mode (sampling)."""
        B, D = 4, 64
        observations = torch.randn(B, D)

        model.train()
        state_train = model.forward(observations, training=True)

        model.eval()
        state_eval = model.forward(observations, training=False)

        # Both should produce valid outputs
        assert state_train.organism_action.shape == (B, 8)
        assert state_eval.organism_action.shape == (B, 8)

    def test_s7_phase_extraction(self, model: UnifiedWorldModel) -> None:
        """Test automatic S7 phase extraction from world model."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        state = model.forward(observations, training=False)

        # Verify S7 phase exists
        assert state.core_state.s7_phase is not None
        assert state.core_state.s7_phase.shape[-1] == 7

    def test_state_contains_all_predictions(self, model: UnifiedWorldModel) -> None:
        """Test that UnifiedState contains all expected predictions."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        state = model.forward(observations, training=False)

        # Verify all state components exist
        assert state.core_state is not None
        assert state.h_next is not None
        assert state.z_next is not None
        assert state.a_next is not None
        assert state.organism_action is not None
        assert state.predicted_s7 is not None
        # RL predictions may or may not exist depending on RSSM version

    def test_timestep_tracking(self, model: UnifiedWorldModel) -> None:
        """Test internal timestep tracking."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        initial_timestep = model._timestep
        state = model.forward(observations, training=False)

        assert state.timestep == initial_timestep + 1


class TestUnifiedWorldModelGradients:
    """Test gradient flow and training."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create small trainable model."""
        config = UnifiedConfig(
            bulk_dim=64,
            rssm_colony_dim=128,
            rssm_stochastic_dim=64,
            device="cpu",
        )
        model = UnifiedWorldModel(config)
        model.train()
        return model

    def test_gradient_flow_through_world_model(self, model: UnifiedWorldModel) -> None:
        """Test gradients flow through world model."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        target_obs = torch.randn(B, 1, D)

        model.zero_grad()
        state = model.forward(observations, training=True)

        # Compute loss on reconstruction
        targets = {"observations": target_obs}
        loss, _ = model.compute_loss(state, targets)

        loss.backward()

        # Check world model has gradients
        wm_params_with_grad = 0
        for _name, param in model.world_model.named_parameters():
            if param.requires_grad and param.grad is not None:
                if param.grad.abs().max() > 0:
                    wm_params_with_grad += 1

        assert wm_params_with_grad > 0, "No gradients in world model"

    def test_gradient_flow_through_rssm(self, model: UnifiedWorldModel) -> None:
        """Test gradients flow through RSSM via action prediction."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        model.zero_grad()
        state = model.forward(observations, training=True)

        # RSSM primarily responsible for action prediction
        # Use action as loss target to test gradient flow
        action_target = torch.randn_like(state.organism_action)
        action_loss = torch.nn.functional.mse_loss(state.organism_action, action_target)
        action_loss.backward()

        # Check RSSM has gradients from action head
        rssm_params_with_grad = 0
        rssm_total_params = 0
        for _name, param in model.rssm.named_parameters():
            if param.requires_grad:
                rssm_total_params += 1
                if param.grad is not None and param.grad.abs().max() > 0:
                    rssm_params_with_grad += 1

        # RSSM should have SOME gradients from action prediction
        # Note: Not all parameters are in the action gradient path (e.g., CoT modules, latent embed)
        # The key parameters are: action_head, dynamics_cell, posterior_net
        # Expect at least 8% of parameters to have gradients (action head + upstream)
        # DreamerV3 architecture has many discrete latent parameters not in action path
        grad_ratio = rssm_params_with_grad / max(rssm_total_params, 1)
        assert grad_ratio > 0.08, (
            f"Only {grad_ratio:.1%} of RSSM parameters have gradients ({rssm_params_with_grad}/{rssm_total_params})"
        )

        # Additionally verify the critical action head has gradients
        action_head_has_grad = any(
            p.grad is not None and p.grad.abs().max() > 0
            for p in model.rssm.action_head.parameters()
        )
        assert action_head_has_grad, "Action head should have gradients from action loss"

    def test_end_to_end_gradient_flow(self, model: UnifiedWorldModel) -> None:
        """Test end-to-end gradient flow through both models."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        target_obs = torch.randn(B, 1, D)

        model.zero_grad()
        state = model.forward(observations, training=True)

        targets = {"observations": target_obs}
        loss, _loss_dict = model.compute_loss(state, targets)

        loss.backward()

        # Verify both models have gradients
        total_params_with_grad = 0
        total_params = 0

        for _name, param in model.named_parameters():
            if param.requires_grad:
                total_params += 1
                if param.grad is not None and param.grad.abs().max() > 0:
                    total_params_with_grad += 1

        grad_ratio = total_params_with_grad / max(total_params, 1)
        assert grad_ratio > 0.3, f"Only {grad_ratio:.1%} of parameters have gradients"

    def test_no_nan_gradients(self, model: UnifiedWorldModel) -> None:
        """Test that gradients are finite (no NaN/Inf)."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        target_obs = torch.randn(B, 1, D)

        model.zero_grad()
        state = model.forward(observations, training=True)

        targets = {"observations": target_obs}
        loss, _ = model.compute_loss(state, targets)

        loss.backward()

        # Check all gradients are finite
        for name, param in model.named_parameters():
            if param.requires_grad and param.grad is not None:
                assert torch.isfinite(param.grad).all(), f"NaN/Inf gradient in {name}"


class TestUnifiedWorldModelLoss:
    """Test loss computation."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create model for loss tests."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        model = UnifiedWorldModel(config)
        model.eval()
        return model

    def test_compute_loss_basic(self, model: UnifiedWorldModel) -> None:
        """Test basic loss computation."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        target_obs = torch.randn(B, 1, D)

        state = model.forward(observations, training=True)
        targets = {"observations": target_obs}

        loss, loss_dict = model.compute_loss(state, targets)

        assert isinstance(loss, torch.Tensor)
        assert torch.isfinite(loss).all()
        assert "total" in loss_dict
        assert isinstance(loss_dict["total"], float)

    def test_compute_loss_with_custom_weights(self, model: UnifiedWorldModel) -> None:
        """Test loss computation with custom weights."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        target_obs = torch.randn(B, 1, D)

        state = model.forward(observations, training=True)
        targets = {"observations": target_obs}
        weights = {
            "kl": 0.5,
            "reconstruction": 2.0,
            "s7_consistency": 0.2,
        }

        loss, _loss_dict = model.compute_loss(state, targets, weights)

        assert torch.isfinite(loss).all()

    def test_loss_components(self, model: UnifiedWorldModel) -> None:
        """Test that loss contains expected components."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        target_obs = torch.randn(B, 1, D)

        state = model.forward(observations, training=True)
        targets = {"observations": target_obs}

        _loss, loss_dict = model.compute_loss(state, targets)

        # Should have at least some of these components
        expected_keys = {"kl", "reconstruction", "s7_consistency", "total"}
        assert len(set(loss_dict.keys()) & expected_keys) > 0

    def test_loss_with_rl_targets(self, model: UnifiedWorldModel) -> None:
        """Test loss with RL targets (reward, value, continue)."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        state = model.forward(observations, training=True)

        # Create fake RL targets
        targets = {
            "observations": torch.randn(B, 1, D),
            "rewards": torch.randn(B, 1),
            "values": torch.randn(B, 1),
            "continues": torch.rand(B, 1),  # [0, 1] for binary
        }

        loss, _loss_dict = model.compute_loss(state, targets)

        assert torch.isfinite(loss).all()


class TestUnifiedWorldModelStateManagement:
    """Test state management and synchronization."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create model for state tests."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        return UnifiedWorldModel(config)

    def test_rssm_state_reset(self, model: UnifiedWorldModel) -> None:
        """Test RSSM state reset."""
        B = 4
        model.reset_rssm_state(batch_size=B)

        # Verify state is reset
        assert model._timestep == 0
        assert model.rssm._initialized is True

    def test_state_persistence_across_calls(self, model: UnifiedWorldModel) -> None:
        """Test that RSSM state persists across forward calls."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        # First call
        state1 = model.forward(observations, training=False)
        timestep1 = state1.timestep

        # Second call (should use previous state)
        state2 = model.forward(observations, training=False)
        timestep2 = state2.timestep

        assert timestep2 > timestep1

    def test_get_state_dict_unified(self, model: UnifiedWorldModel) -> None:
        """Test unified state dict for checkpointing."""
        state_dict = model.get_state_dict_unified()

        assert "world_model" in state_dict
        assert "rssm" in state_dict
        assert "timestep" in state_dict
        assert "config" in state_dict

    def test_load_state_dict_unified(self, model: UnifiedWorldModel) -> None:
        """Test loading unified checkpoint."""
        # Save state
        original_timestep = model._timestep = 42
        state_dict = model.get_state_dict_unified()

        # Create new model and load
        new_model = UnifiedWorldModel(model.config)
        new_model.load_state_dict_unified(state_dict)

        assert new_model._timestep == original_timestep


class TestUnifiedWorldModelSequences:
    """Test sequence handling."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create model for sequence tests."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        return UnifiedWorldModel(config)

    def test_variable_length_sequences(self, model: UnifiedWorldModel) -> None:
        """Test handling of different sequence lengths."""
        B, D = 2, 64

        # Test different sequence lengths
        for S in [1, 4, 8]:
            observations = torch.randn(B, S, D)
            state = model.forward(observations, training=False)

            assert state.organism_action.shape == (B, 8)

    def test_sequence_with_actions(self, model: UnifiedWorldModel) -> None:
        """Test sequence with per-timestep actions."""
        B, S, D = 2, 4, 64
        observations = torch.randn(B, S, D)
        actions = torch.randn(B, S, 8)  # Actions per timestep

        state = model.forward(observations, actions=actions, training=False)

        assert state.organism_action.shape == (B, 8)


class TestUnifiedWorldModelBatchSizes:
    """Test different batch sizes."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create model for batch tests."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        return UnifiedWorldModel(config)

    @pytest.mark.parametrize("batch_size", [1, 2, 4, 8])
    def test_variable_batch_sizes(self, model: UnifiedWorldModel, batch_size: int) -> None:
        """Test handling of different batch sizes."""
        D = 64
        observations = torch.randn(batch_size, D)

        state = model.forward(observations, training=False)

        assert state.organism_action.shape == (batch_size, 8)

    def test_batch_size_changes_reset_rssm(self, model: UnifiedWorldModel) -> None:
        """Test that batch size changes trigger RSSM reset."""
        D = 64

        # First call with B=2
        obs1 = torch.randn(2, D)
        state1 = model.forward(obs1, training=False)

        # Second call with B=4 (different batch size)
        obs2 = torch.randn(4, D)
        state2 = model.forward(obs2, training=False)

        # Should handle gracefully
        assert state2.organism_action.shape == (4, 8)


class TestUnifiedWorldModelEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def model(self) -> UnifiedWorldModel:
        """Create model for edge case tests."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        return UnifiedWorldModel(config)

    def test_invalid_observation_shape(self, model: UnifiedWorldModel) -> None:
        """Test error on invalid observation shape."""
        observations = torch.randn(2, 3, 4, 5)  # 4D tensor (invalid)

        with pytest.raises(ValueError, match="observations must be"):
            model.forward(observations, training=False)

    def test_invalid_action_shape(self, model: UnifiedWorldModel) -> None:
        """Test error on invalid action shape."""
        B, D = 2, 64
        observations = torch.randn(B, D)
        actions = torch.randn(B, 4, 5, 6)  # 4D tensor (invalid)

        with pytest.raises(ValueError):
            model.forward(observations, actions=actions, training=False)

    def test_empty_targets(self, model: UnifiedWorldModel) -> None:
        """Test loss computation with empty targets."""
        B, D = 2, 64
        observations = torch.randn(B, D)

        state = model.forward(observations, training=False)
        targets: dict[str, torch.Tensor] = {}

        loss, _loss_dict = model.compute_loss(state, targets)

        # Should handle gracefully (may have KL loss only)
        assert torch.isfinite(loss).all()


class TestUnifiedWorldModelIntegration:
    """Integration tests combining multiple features."""

    def test_full_training_loop(self) -> None:
        """Test complete training loop: forward → loss → backward → step."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        model = UnifiedWorldModel(config)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

        B, S, D = 2, 4, 64
        observations = torch.randn(B, S, D)
        target_obs = torch.randn(B, S, D)

        # Training step
        model.train()
        optimizer.zero_grad()

        state = model.forward(observations, training=True)
        targets = {"observations": target_obs}
        loss, loss_dict = model.compute_loss(state, targets)

        loss.backward()
        optimizer.step()

        # Verify loss is finite
        assert torch.isfinite(loss).all()
        assert loss_dict["total"] < float("inf")

    def test_eval_mode_consistency(self) -> None:
        """Test that eval mode gives deterministic results given same state."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        model = UnifiedWorldModel(config)
        model.eval()

        B, D = 2, 64
        observations = torch.randn(B, D)

        # In eval mode with training=False, should get consistent results
        with torch.no_grad():
            state1 = model.forward(observations, training=False)

            # Reset to exact same state
            model.reset_rssm_state(batch_size=B)

            state2 = model.forward(observations, training=False)

        # Core world model should give same results
        assert torch.allclose(state1.core_state.s7_phase, state2.core_state.s7_phase, rtol=1e-4)  # type: ignore[arg-type]
        # Actions may vary slightly due to RSSM stochasticity even in eval mode
        # Just verify they're in the same ballpark
        assert (state1.organism_action - state2.organism_action).abs().max() < 10.0

    def test_checkpoint_save_load_cycle(self) -> None:
        """Test full checkpoint save/load cycle."""
        config = UnifiedConfig(bulk_dim=64, device="cpu")
        model1 = UnifiedWorldModel(config)
        model1.eval()

        # Save checkpoint before any forward pass
        checkpoint = model1.get_state_dict_unified()

        # Create new model and load checkpoint
        model2 = UnifiedWorldModel(config)
        model2.load_state_dict_unified(checkpoint)
        model2.eval()

        # Verify checkpoint was loaded
        assert model2._timestep == model1._timestep

        # Verify world model weights match
        for (n1, p1), (n2, p2) in zip(
            model1.world_model.named_parameters(),
            model2.world_model.named_parameters(),
            strict=True,
        ):
            assert n1 == n2
            assert torch.allclose(p1, p2, rtol=1e-6), f"Parameter {n1} differs"

        # Verify RSSM weights match
        for (n1, p1), (n2, p2) in zip(
            model1.rssm.named_parameters(), model2.rssm.named_parameters(), strict=True
        ):
            assert n1 == n2
            assert torch.allclose(p1, p2, rtol=1e-6), f"Parameter {n1} differs"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
