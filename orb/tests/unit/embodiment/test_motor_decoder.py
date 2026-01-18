"""Tests for Motor Decoder.

Tests cover:
- Decoder initialization
- Forward pass with various input shapes
- Output action types (discrete, continuous, digital)
- Uncertainty estimation
- Action selection and sampling

Coverage target: kagami/core/embodiment/motor_decoder.py
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import torch
import torch.nn as nn

from kagami.core.embodiment import (
    CONTINUOUS_ACTION_SPACE,
    DISCRETE_ACTIONS,
    MotorDecoder,
    create_motor_decoder,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def device():
    """Get appropriate device for testing."""
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


@pytest.fixture
def decoder(device: Any) -> Any:
    """Create motor decoder with default settings."""
    return MotorDecoder(device=device)


@pytest.fixture
def manifold_state_2d(device: Any) -> Any:
    """Create 2D manifold state [B, dim]."""
    return torch.randn(4, 256, device=device)


@pytest.fixture
def manifold_state_3d(device: Any) -> Any:
    """Create 3D manifold state [B, N, dim] with sequence."""
    return torch.randn(4, 10, 256, device=device)


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestDecoderInit:
    """Tests for decoder initialization."""

    def test_default_init(self, device) -> Any:
        """Test default initialization."""
        decoder = MotorDecoder(device=device)
        assert decoder is not None
        assert decoder.device == device

    def test_custom_dimensions(self, device) -> None:
        """Test initialization with custom dimensions."""
        decoder = MotorDecoder(
            input_dim=512,
            num_discrete_actions=128,
            continuous_action_dim=14,
            num_digital_tools=50,
            device=device,
        )
        # Check heads have correct output dims
        assert decoder.discrete_head[-1].out_features == 128
        assert decoder.continuous_head[0].out_features == 14
        assert decoder.digital_head[-1].out_features == 50

    def test_feature_extractor_created(self, decoder) -> None:
        """Test feature extractor is properly initialized."""
        assert hasattr(decoder, "feature_extractor")
        assert isinstance(decoder.feature_extractor, nn.Sequential)

    def test_all_heads_created(self, decoder) -> None:
        """Test all action heads are created."""
        assert hasattr(decoder, "discrete_head")
        assert hasattr(decoder, "continuous_head")
        assert hasattr(decoder, "digital_head")
        assert hasattr(decoder, "uncertainty_head")
        assert hasattr(decoder, "speech_head")


# =============================================================================
# FORWARD PASS TESTS
# =============================================================================


class TestDecoderForward:
    """Tests for decoder forward pass."""

    def test_forward_2d_input(self, decoder: Any, manifold_state_2d: Any) -> None:
        """Test forward pass with 2D input [B, dim]."""
        output = decoder(manifold_state_2d)

        assert isinstance(output, dict)
        assert "discrete_actions" in output
        assert "continuous_actions" in output
        assert "digital_tools" in output
        assert "action_uncertainty" in output

    def test_forward_3d_input(self, decoder: Any, manifold_state_3d: Any) -> None:
        """Test forward pass with 3D input [B, N, dim] (pools sequence)."""
        output = decoder(manifold_state_3d)

        assert isinstance(output, dict)
        assert "discrete_actions" in output
        # Should pool over sequence dimension
        assert output["discrete_actions"].shape[0] == 4  # Batch size preserved

    def test_forward_single_sample(self, decoder, device) -> None:
        """Test forward pass with single sample."""
        single_input = torch.randn(1, 256, device=device)
        output = decoder(single_input)
        assert output["discrete_actions"].shape[0] == 1


# =============================================================================
# OUTPUT SHAPE TESTS
# =============================================================================


class TestOutputShapes:
    """Tests for output shapes."""

    def test_discrete_output_shape(self, decoder, manifold_state_2d) -> None:
        """Test discrete action output shape."""
        output = decoder(manifold_state_2d)
        # Default: 256 discrete actions
        assert output["discrete_actions"].shape == (4, 256)

    def test_continuous_output_shape(self, decoder, manifold_state_2d) -> None:
        """Test continuous action output shape."""
        output = decoder(manifold_state_2d)
        # Default: 7 continuous dims
        assert output["continuous_actions"].shape == (4, 7)

    def test_digital_output_shape(self, decoder, manifold_state_2d) -> None:
        """Test digital tool output shape."""
        output = decoder(manifold_state_2d)
        # Default: 100 digital tools
        assert output["digital_tools"].shape == (4, 100)

    def test_uncertainty_output_shape(self, decoder, manifold_state_2d) -> None:
        """Test uncertainty output shape."""
        output = decoder(manifold_state_2d)
        assert output["action_uncertainty"].shape == (4, 1)

    def test_speech_output_shape(self, decoder, manifold_state_2d) -> None:
        """Test speech embedding output shape."""
        output = decoder(manifold_state_2d)
        if "speech_params" in output:
            # Default: 64-dim speech embedding
            assert output["speech_params"].shape == (4, 64)


# =============================================================================
# OUTPUT RANGE TESTS
# =============================================================================


class TestOutputRanges:
    """Tests for output value ranges."""

    def test_continuous_bounded(self, decoder, manifold_state_2d) -> None:
        """Test continuous actions are bounded [-1, 1] by Tanh."""
        output = decoder(manifold_state_2d)
        continuous = output["continuous_actions"]
        assert continuous.min() >= -1.0
        assert continuous.max() <= 1.0

    def test_uncertainty_bounded(self, decoder, manifold_state_2d) -> None:
        """Test uncertainty is bounded [0, 1] by Sigmoid."""
        output = decoder(manifold_state_2d)
        uncertainty = output["action_uncertainty"]
        assert uncertainty.min() >= 0.0
        assert uncertainty.max() <= 1.0

    def test_discrete_logits(self, decoder, manifold_state_2d) -> None:
        """Test discrete outputs are logits (unbounded)."""
        output = decoder(manifold_state_2d)
        discrete = output["discrete_actions"]
        # Logits can be any real value
        assert discrete.dtype == torch.float32


# =============================================================================
# ACTION SELECTION TESTS
# =============================================================================


class TestActionSelection:
    """Tests for action selection utilities."""

    def test_discrete_argmax(self, decoder, manifold_state_2d) -> None:
        """Test selecting discrete action via argmax."""
        output = decoder(manifold_state_2d)
        actions = output["discrete_actions"].argmax(dim=-1)
        assert actions.shape == (4,)
        assert actions.dtype == torch.int64

    def test_discrete_sampling(self, decoder, manifold_state_2d) -> None:
        """Test sampling discrete actions."""
        output = decoder(manifold_state_2d)
        probs = torch.softmax(output["discrete_actions"], dim=-1)
        sampled = torch.multinomial(probs, num_samples=1)
        assert sampled.shape == (4, 1)

    def test_digital_tool_selection(self, decoder, manifold_state_2d) -> None:
        """Test selecting digital tool."""
        output = decoder(manifold_state_2d)
        tool_idx = output["digital_tools"].argmax(dim=-1)
        assert tool_idx.shape == (4,)
        assert tool_idx.min() >= 0
        assert tool_idx.max() < 100  # Default num_digital_tools


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunction:
    """Tests for create_motor_decoder factory."""

    def test_create_default(self, device) -> None:
        """Test factory with defaults."""
        decoder = create_motor_decoder(device=device)
        assert isinstance(decoder, MotorDecoder)

    def test_create_with_options(self, device) -> None:
        """Test factory with custom device."""
        decoder = create_motor_decoder(device=device)
        assert decoder.device == device


# =============================================================================
# GRADIENT FLOW TESTS
# =============================================================================


class TestGradientFlow:
    """Tests for gradient flow through decoder."""

    def test_gradients_flow(self, decoder, device) -> None:
        """Test that gradients flow through decoder."""
        decoder.train()

        input_tensor = torch.randn(4, 256, device=device, requires_grad=True)
        output = decoder(input_tensor)

        # Sum all outputs for loss
        loss = sum(v.sum() for v in output.values() if isinstance(v, torch.Tensor))
        loss.backward()  # type: ignore[union-attr]

        assert input_tensor.grad is not None
        assert input_tensor.grad.shape == (4, 256)

    def test_no_grad_inference(self, decoder, manifold_state_2d) -> None:
        """Test inference with no_grad."""
        decoder.eval()

        with torch.no_grad():
            output = decoder(manifold_state_2d)

        assert output is not None


# =============================================================================
# CONSTANTS TESTS
# =============================================================================


class TestActionConstants:
    """Tests for action space constants."""

    def test_discrete_actions_defined(self) -> None:
        """Test DISCRETE_ACTIONS constant exists."""
        assert DISCRETE_ACTIONS is not None
        # Should be a list or dict of action names
        assert len(DISCRETE_ACTIONS) > 0

    def test_continuous_action_space_defined(self) -> None:
        """Test CONTINUOUS_ACTION_SPACE constant exists."""
        assert CONTINUOUS_ACTION_SPACE is not None


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_input(self, decoder, device) -> None:
        """Test handling of zero input."""
        zero_input = torch.zeros(4, 256, device=device)
        output = decoder(zero_input)
        assert output is not None

    def test_large_batch(self, decoder, device) -> None:
        """Test handling of large batch."""
        large_input = torch.randn(128, 256, device=device)
        output = decoder(large_input)
        assert output["discrete_actions"].shape[0] == 128

    def test_long_sequence(self, decoder, device) -> None:
        """Test handling of long sequence."""
        long_seq = torch.randn(4, 100, 256, device=device)
        output = decoder(long_seq)
        assert output["discrete_actions"].shape[0] == 4

    def test_deterministic_mode(self, decoder, manifold_state_2d) -> None:
        """Test deterministic output in eval mode."""
        decoder.eval()

        with torch.no_grad():
            out1 = decoder(manifold_state_2d)
            out2 = decoder(manifold_state_2d)

        torch.testing.assert_close(out1["discrete_actions"], out2["discrete_actions"])
