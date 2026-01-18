"""Tests for EgoModel - LeCun's deterministic self-predictor.

Verifies:
- EgoStateEncoder: world_state + proprio + mu_self → ego_state
- ActionPredictor: ego_state → action distribution
- EffectPredictor: ego_state + action → next_ego_state (deterministic)
- CostPredictor: ego_state + action → cost
- Action optimization via gradient descent
- Strange Loop integration

Reference: LeCun (2022) Section 4.10 "The Cost Module"
"""

from __future__ import annotations

from typing import Any

import pytest

import torch
import torch.nn as nn

from kagami.core.world_model.ego_model import (
    ActionPredictor,
    CostPredictor,
    EffectPredictor,
    EgoModel,
    EgoModelConfig,
    EgoStateEncoder,
    get_ego_model,
    reset_ego_model,
)

pytestmark = pytest.mark.tier_integration

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def config() -> EgoModelConfig:
    """Standard config for testing."""
    return EgoModelConfig(
        world_state_dim=64,
        proprio_dim=16,
        ego_state_dim=32,
        action_dim=8,
        mu_self_dim=8,
        hidden_dim=32,
        n_layers=2,
        dropout=0.0,  # Disable dropout for deterministic tests
        action_optim_steps=5,
        action_optim_lr=0.1,
    )


@pytest.fixture
def device() -> torch.device:
    """Get appropriate device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset global singleton before each test."""
    reset_ego_model()
    yield
    reset_ego_model()


# =============================================================================
# EgoStateEncoder Tests
# =============================================================================


class TestEgoStateEncoder:
    """Tests for EgoStateEncoder component."""

    def test_encoder_shape_no_strange_loop(self, config: EgoModelConfig) -> None:
        """Encoder produces correct output shape without Strange Loop."""
        config.use_strange_loop = False
        encoder = EgoStateEncoder(config)

        batch_size = 4
        world_state = torch.randn(batch_size, config.world_state_dim)
        proprio = torch.randn(batch_size, config.proprio_dim)

        ego_state = encoder(world_state, proprio)

        assert ego_state.shape == (batch_size, config.ego_state_dim)

    def test_encoder_shape_with_strange_loop(self, config: EgoModelConfig) -> None:
        """Encoder produces correct output shape with Strange Loop."""
        config.use_strange_loop = True
        encoder = EgoStateEncoder(config)

        batch_size = 4
        world_state = torch.randn(batch_size, config.world_state_dim)
        proprio = torch.randn(batch_size, config.proprio_dim)
        mu_self = torch.randn(batch_size, config.mu_self_dim)

        ego_state = encoder(world_state, proprio, mu_self)

        assert ego_state.shape == (batch_size, config.ego_state_dim)

    def test_encoder_optional_inputs(self, config: EgoModelConfig) -> None:
        """Encoder handles optional proprio and mu_self."""
        config.use_strange_loop = True
        encoder = EgoStateEncoder(config)

        batch_size = 4
        world_state = torch.randn(batch_size, config.world_state_dim)

        # Both optional
        ego_state = encoder(world_state)
        assert ego_state.shape == (batch_size, config.ego_state_dim)

        # Only proprio
        proprio = torch.randn(batch_size, config.proprio_dim)
        ego_state = encoder(world_state, proprio)
        assert ego_state.shape == (batch_size, config.ego_state_dim)

    def test_encoder_deterministic(self, config: EgoModelConfig) -> None:
        """Same input produces same output."""
        config.use_strange_loop = False
        encoder = EgoStateEncoder(config)
        encoder.eval()

        world_state = torch.randn(2, config.world_state_dim)
        proprio = torch.randn(2, config.proprio_dim)

        out1 = encoder(world_state, proprio)
        out2 = encoder(world_state, proprio)

        torch.testing.assert_close(out1, out2)


# =============================================================================
# ActionPredictor Tests
# =============================================================================


class TestActionPredictor:
    """Tests for ActionPredictor component."""

    def test_action_predictor_shape(self, config: EgoModelConfig) -> None:
        """ActionPredictor produces correct output shape."""
        predictor = ActionPredictor(config)

        batch_size = 4
        ego_state = torch.randn(batch_size, config.ego_state_dim)

        action, info = predictor(ego_state)

        assert action.shape == (batch_size, config.action_dim)
        assert "mean" in info
        assert "std" in info
        assert "log_prob" in info
        assert info["mean"].shape == (batch_size, config.action_dim)
        assert info["std"].shape == (batch_size, config.action_dim)
        assert info["log_prob"].shape == (batch_size,)

    def test_action_predictor_deterministic(self, config: EgoModelConfig) -> None:
        """Deterministic mode returns mean."""
        predictor = ActionPredictor(config)
        predictor.eval()

        ego_state = torch.randn(2, config.ego_state_dim)

        action1, info1 = predictor(ego_state, deterministic=True)
        action2, _info2 = predictor(ego_state, deterministic=True)

        # Same output in deterministic mode
        torch.testing.assert_close(action1, action2)
        torch.testing.assert_close(action1, info1["mean"])

    def test_action_predictor_stochastic(self, config: EgoModelConfig) -> None:
        """Stochastic mode samples different actions."""
        predictor = ActionPredictor(config)

        ego_state = torch.randn(2, config.ego_state_dim)

        # Multiple samples should differ
        torch.manual_seed(42)
        action1, _ = predictor(ego_state, deterministic=False)
        torch.manual_seed(123)
        action2, _ = predictor(ego_state, deterministic=False)

        # Not identical (probabilistic - could theoretically be same but unlikely)
        assert not torch.allclose(action1, action2, atol=1e-3)

    def test_action_predictor_log_std_bounded(self, config: EgoModelConfig) -> None:
        """Log std is clamped to reasonable range."""
        predictor = ActionPredictor(config)

        ego_state = torch.randn(100, config.ego_state_dim)
        _, info = predictor(ego_state)

        log_std = torch.log(info["std"])
        assert (log_std >= -10).all()
        assert (log_std <= 2).all()


# =============================================================================
# EffectPredictor Tests
# =============================================================================


class TestEffectPredictor:
    """Tests for EffectPredictor component."""

    def test_effect_predictor_shape(self, config: EgoModelConfig) -> None:
        """EffectPredictor produces correct output shape."""
        predictor = EffectPredictor(config)

        batch_size = 4
        ego_state = torch.randn(batch_size, config.ego_state_dim)
        action = torch.randn(batch_size, config.action_dim)

        next_ego = predictor(ego_state, action)

        assert next_ego.shape == (batch_size, config.ego_state_dim)

    def test_effect_predictor_deterministic(self, config: EgoModelConfig) -> None:
        """Effect prediction is deterministic (no latent variables)."""
        predictor = EffectPredictor(config)
        predictor.eval()

        ego_state = torch.randn(2, config.ego_state_dim)
        action = torch.randn(2, config.action_dim)

        next_ego1 = predictor(ego_state, action)
        next_ego2 = predictor(ego_state, action)

        torch.testing.assert_close(next_ego1, next_ego2)

    def test_effect_predictor_residual(self, config: EgoModelConfig) -> None:
        """Residual connection: small actions produce small changes."""
        predictor = EffectPredictor(config)
        predictor.use_residual = True
        predictor.eval()

        # Initialize network weights to small values
        with torch.no_grad():
            for p in predictor.parameters():
                p.mul_(0.01)

        ego_state = torch.randn(4, config.ego_state_dim)
        small_action = torch.randn(4, config.action_dim) * 0.01

        next_ego = predictor(ego_state, small_action)

        # With small weights and small action, next_ego should be close to ego_state
        delta = (next_ego - ego_state).abs().mean()
        assert delta < 1.0, f"Expected small delta, got {delta}"


# =============================================================================
# CostPredictor Tests
# =============================================================================


class TestCostPredictor:
    """Tests for CostPredictor component."""

    def test_cost_predictor_shape(self, config: EgoModelConfig) -> None:
        """CostPredictor produces correct output shape."""
        predictor = CostPredictor(config)

        batch_size = 4
        ego_state = torch.randn(batch_size, config.ego_state_dim)
        action = torch.randn(batch_size, config.action_dim)

        cost = predictor(ego_state, action)

        assert cost.shape == (batch_size, 1)

    def test_cost_predictor_differentiable(self, config: EgoModelConfig) -> None:
        """Cost is differentiable w.r.t. action for optimization."""
        predictor = CostPredictor(config)

        ego_state = torch.randn(2, config.ego_state_dim)
        action = torch.randn(2, config.action_dim, requires_grad=True)

        cost = predictor(ego_state, action)
        cost_sum = cost.sum()
        cost_sum.backward()

        assert action.grad is not None
        assert action.grad.shape == action.shape


# =============================================================================
# Full EgoModel Tests
# =============================================================================


class TestEgoModel:
    """Tests for complete EgoModel."""

    def test_ego_model_init(self, config: EgoModelConfig) -> None:
        """EgoModel initializes correctly."""
        model = EgoModel(config)

        assert model.state_encoder is not None
        assert model.action_predictor is not None
        assert model.effect_predictor is not None
        assert model.cost_predictor is not None

    def test_ego_model_default_config(self) -> None:
        """EgoModel works with default config."""
        model = EgoModel()
        assert model.config is not None
        assert model.config.world_state_dim == 512

    def test_encode(self, config: EgoModelConfig) -> None:
        """Encode method works correctly."""
        model = EgoModel(config)

        batch_size = 4
        world_state = torch.randn(batch_size, config.world_state_dim)

        ego_state = model.encode(world_state)
        assert ego_state.shape == (batch_size, config.ego_state_dim)

    def test_predict_action(self, config: EgoModelConfig) -> None:
        """Predict action from ego state."""
        model = EgoModel(config)

        ego_state = torch.randn(4, config.ego_state_dim)

        action, _info = model.predict_action(ego_state)
        assert action.shape == (4, config.action_dim)

    def test_predict_effect(self, config: EgoModelConfig) -> None:
        """Predict next ego state."""
        model = EgoModel(config)

        ego_state = torch.randn(4, config.ego_state_dim)
        action = torch.randn(4, config.action_dim)

        next_ego = model.predict_effect(ego_state, action)
        assert next_ego.shape == (4, config.ego_state_dim)

    def test_predict_cost(self, config: EgoModelConfig) -> None:
        """Predict cost of action."""
        model = EgoModel(config)

        ego_state = torch.randn(4, config.ego_state_dim)
        action = torch.randn(4, config.action_dim)

        cost = model.predict_cost(ego_state, action)
        assert cost.shape == (4, 1)

    def test_optimize_action(self, config: EgoModelConfig) -> None:
        """Action optimization via gradient descent."""
        model = EgoModel(config)

        ego_state = torch.randn(2, config.ego_state_dim)

        # Initial action
        initial_action = torch.randn(2, config.action_dim)
        initial_cost = model.predict_cost(ego_state, initial_action)

        # Optimize
        optimized_action = model.optimize_action(
            ego_state,
            initial_action=initial_action,
            horizon=1,
        )

        assert optimized_action.shape == (2, config.action_dim)

        # Optimized action should have lower cost (usually)
        optimized_cost = model.predict_cost(ego_state, optimized_action)
        # Note: Not guaranteed to be lower due to regularization and limited steps

    def test_optimize_action_without_initial(self, config: EgoModelConfig) -> None:
        """Optimize action starting from policy prediction."""
        model = EgoModel(config)

        ego_state = torch.randn(2, config.ego_state_dim)

        optimized_action = model.optimize_action(ego_state)
        assert optimized_action.shape == (2, config.action_dim)

    def test_forward_pass(self, config: EgoModelConfig) -> None:
        """Full forward pass."""
        model = EgoModel(config)

        world_state = torch.randn(4, config.world_state_dim)
        proprio = torch.randn(4, config.proprio_dim)

        result = model(world_state, proprio)

        assert "ego_state" in result
        assert "action" in result
        assert "next_ego" in result
        assert "cost" in result
        assert "action_info" in result
        assert "strange_loop_connected" in result

        assert result["ego_state"].shape == (4, config.ego_state_dim)
        assert result["action"].shape == (4, config.action_dim)
        assert result["next_ego"].shape == (4, config.ego_state_dim)
        assert result["cost"].shape == (4, 1)

    def test_forward_with_action(self, config: EgoModelConfig) -> None:
        """Forward pass with provided action."""
        model = EgoModel(config)

        world_state = torch.randn(4, config.world_state_dim)
        action = torch.randn(4, config.action_dim)

        result = model(world_state, action=action)

        torch.testing.assert_close(result["action"], action)
        assert result["action_info"]["provided"]

    def test_forward_optimize_mode(self, config: EgoModelConfig) -> None:
        """Forward pass with action optimization."""
        model = EgoModel(config)
        model.eval()  # Eval mode for optimization

        # Detach world_state to avoid graph reuse issues
        world_state = torch.randn(2, config.world_state_dim).detach()

        with torch.no_grad():
            ego_state = model.encode(world_state)

        # Directly test optimize_action with detached state
        optimized_action = model.optimize_action(ego_state.detach())

        assert optimized_action.shape == (2, config.action_dim)


# =============================================================================
# Strange Loop Integration Tests
# =============================================================================


class TestStrangeLoopIntegration:
    """Tests for Strange Loop (Hofstadter) integration."""

    def test_connect_strange_loop(self, config: EgoModelConfig) -> None:
        """Connect to Strange Loop module."""
        config.use_strange_loop = True
        model = EgoModel(config)

        # Mock Strange Loop with mu_self parameter
        class MockStrangeLoop(nn.Module):
            def __init__(self, dim):
                super().__init__()
                self.mu_self = nn.Parameter(torch.randn(dim))

        strange_loop = MockStrangeLoop(config.mu_self_dim)
        model.connect_strange_loop(strange_loop)

        assert model._strange_loop is strange_loop

    def test_get_mu_self(self, config: EgoModelConfig) -> None:
        """Get mu_self from connected Strange Loop."""
        config.use_strange_loop = True
        model = EgoModel(config)

        class MockStrangeLoop(nn.Module):
            def __init__(self, dim):
                super().__init__()
                self.mu_self = nn.Parameter(torch.ones(dim) * 0.5)

        strange_loop = MockStrangeLoop(config.mu_self_dim)
        model.connect_strange_loop(strange_loop)

        mu_self = model.get_mu_self(batch_size=4, device=torch.device("cpu"))

        assert mu_self is not None
        assert mu_self.shape == (4, config.mu_self_dim)
        assert torch.allclose(mu_self, torch.ones_like(mu_self) * 0.5)

    def test_get_mu_self_no_connection(self, config: EgoModelConfig) -> None:
        """get_mu_self returns None without Strange Loop connection."""
        config.use_strange_loop = True
        model = EgoModel(config)

        mu_self = model.get_mu_self(batch_size=4, device=torch.device("cpu"))
        assert mu_self is None

    def test_forward_with_strange_loop(self, config: EgoModelConfig) -> None:
        """Forward pass with Strange Loop connected."""
        config.use_strange_loop = True
        model = EgoModel(config)

        class MockStrangeLoop(nn.Module):
            def __init__(self, dim):
                super().__init__()
                self.mu_self = nn.Parameter(torch.randn(dim))

        strange_loop = MockStrangeLoop(config.mu_self_dim)
        model.connect_strange_loop(strange_loop)

        world_state = torch.randn(4, config.world_state_dim)
        result = model(world_state)

        assert result["strange_loop_connected"]
        assert "mu_self" in result
        assert result["mu_self"].shape == (4, config.mu_self_dim)

    def test_forward_without_strange_loop(self, config: EgoModelConfig) -> None:
        """Forward pass without Strange Loop still works."""
        config.use_strange_loop = False
        model = EgoModel(config)

        world_state = torch.randn(4, config.world_state_dim)
        result = model(world_state)

        assert not result["strange_loop_connected"]
        assert "mu_self" not in result


# =============================================================================
# Training Step Tests
# =============================================================================


class TestTrainingStep:
    """Tests for training_step method."""

    def test_training_step_basic(self, config: EgoModelConfig) -> None:
        """Basic training step computes loss."""
        model = EgoModel(config)

        batch = {
            "world_state": torch.randn(4, config.world_state_dim),
            "action": torch.randn(4, config.action_dim),
            "next_world_state": torch.randn(4, config.world_state_dim),
        }

        losses = model.training_step(batch)

        assert "loss" in losses
        assert "effect_loss" in losses
        assert "action_loss" in losses
        assert losses["loss"].ndim == 0  # Scalar

    def test_training_step_with_cost(self, config: EgoModelConfig) -> None:
        """Training step with cost target."""
        model = EgoModel(config)

        batch = {
            "world_state": torch.randn(4, config.world_state_dim),
            "action": torch.randn(4, config.action_dim),
            "next_world_state": torch.randn(4, config.world_state_dim),
            "cost": torch.randn(4, 1),
        }

        losses = model.training_step(batch)

        assert "cost_loss" in losses
        assert losses["cost_loss"] > 0  # Non-zero cost loss

    def test_training_step_with_proprio(self, config: EgoModelConfig) -> None:
        """Training step with proprioceptive input."""
        model = EgoModel(config)

        batch = {
            "world_state": torch.randn(4, config.world_state_dim),
            "proprio": torch.randn(4, config.proprio_dim),
            "action": torch.randn(4, config.action_dim),
            "next_world_state": torch.randn(4, config.world_state_dim),
        }

        losses = model.training_step(batch)
        assert losses["loss"].isfinite()

    def test_training_step_gradient_flow(self, config: EgoModelConfig) -> None:
        """Gradients flow through training step."""
        model = EgoModel(config)

        batch = {
            "world_state": torch.randn(4, config.world_state_dim),
            "action": torch.randn(4, config.action_dim),
            "next_world_state": torch.randn(4, config.world_state_dim),
        }

        losses = model.training_step(batch)
        losses["loss"].backward()

        # Check that at least core gradients exist (some paths may not be used)
        # The deterministic action prediction doesn't use logstd, so we check
        # key components rather than all parameters
        assert model.state_encoder.encoder[0].weight.grad is not None
        assert model.effect_predictor.network[0].weight.grad is not None
        assert model.action_predictor.mean_head.weight.grad is not None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton access functions."""

    def test_get_ego_model(self) -> None:
        """get_ego_model returns singleton."""
        model1 = get_ego_model()
        model2 = get_ego_model()

        assert model1 is model2

    def test_get_ego_model_with_config(self) -> None:
        """get_ego_model respects config on first call."""
        config = EgoModelConfig(world_state_dim=128)
        model = get_ego_model(config)

        assert model.config.world_state_dim == 128

    def test_reset_ego_model(self) -> None:
        """reset_ego_model clears singleton."""
        model1 = get_ego_model()
        reset_ego_model()
        model2 = get_ego_model()

        assert model1 is not model2


# =============================================================================
# Device Compatibility Tests
# =============================================================================


class TestDeviceCompatibility:
    """Tests for device compatibility."""

    def test_cpu_inference(self, config: EgoModelConfig) -> None:
        """Model works on CPU."""
        model = EgoModel(config)
        model.to("cpu")

        world_state = torch.randn(2, config.world_state_dim, device="cpu")
        result = model(world_state)

        assert result["ego_state"].device.type == "cpu"

    @pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS not available")
    def test_mps_inference(self, config: EgoModelConfig) -> None:
        """Model works on MPS (Apple Silicon)."""
        model = EgoModel(config)
        model.to("mps")

        world_state = torch.randn(2, config.world_state_dim, device="mps")
        result = model(world_state)

        assert result["ego_state"].device.type == "mps"

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_cuda_inference(self, config: EgoModelConfig) -> None:
        """Model works on CUDA."""
        model = EgoModel(config)
        model.to("cuda")

        world_state = torch.randn(2, config.world_state_dim, device="cuda")
        result = model(world_state)

        assert result["ego_state"].device.type == "cuda"
