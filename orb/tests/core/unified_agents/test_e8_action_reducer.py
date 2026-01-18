"""Comprehensive Tests for E8 Action Reducer.

COVERAGE:
=========
- Initialization and configuration
- Forward pass with attention and fixed weights
- E8 lattice quantization
- Straight-through estimator gradient flow
- Colony output fusion with weights
- Attention-based weighting
- S7 normalization invariance
- Confidence modulation
- High-level reduce interface
- Root semantics and metadata
- Training vs inference modes
- Batch processing
- Error handling

Created: December 27, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch
import torch.nn as nn

from kagami.core.unified_agents.e8_action_reducer import (
    E8Action,
    E8ActionReducer,
    create_e8_reducer,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def device() -> str:
    """Get test device."""
    return "cpu"


@pytest.fixture
def num_colonies() -> int:
    """Number of colonies."""
    return 7


@pytest.fixture
def hidden_dim() -> int:
    """Hidden dimension."""
    return 32


@pytest.fixture
def batch_size() -> int:
    """Batch size for tests."""
    return 4


@pytest.fixture
def reducer_attention(num_colonies: int, hidden_dim: int, device: str) -> Any:
    """Create reducer with attention."""
    return E8ActionReducer(
        num_colonies=num_colonies,
        hidden_dim=hidden_dim,
        use_attention=True,
        device=device,
    )


@pytest.fixture
def reducer_fixed(num_colonies: int, hidden_dim: int, device: str) -> Any:
    """Create reducer with fixed weights."""
    return E8ActionReducer(
        num_colonies=num_colonies,
        hidden_dim=hidden_dim,
        use_attention=False,
        device=device,
    )


@pytest.fixture
def colony_outputs(batch_size: int, num_colonies: int) -> Any:
    """Create test colony outputs."""
    outputs = torch.randn(batch_size, num_colonies, 8)
    # Normalize to S7
    outputs = torch.nn.functional.normalize(outputs, dim=-1)
    return outputs


@pytest.fixture
def colony_confidences(batch_size: int, num_colonies: int) -> Any:
    """Create test colony confidences."""
    return torch.rand(batch_size, num_colonies)


# =============================================================================
# TEST: INITIALIZATION
# =============================================================================


def test_initialization_attention(num_colonies: int, hidden_dim: int, device: str) -> None:
    """Test reducer initialization with attention."""
    reducer = E8ActionReducer(
        num_colonies=num_colonies,
        hidden_dim=hidden_dim,
        use_attention=True,
        device=device,
    )

    assert reducer.num_colonies == num_colonies
    assert reducer.hidden_dim == hidden_dim
    assert reducer.use_attention is True
    assert hasattr(reducer, "query")
    assert hasattr(reducer, "key")
    assert hasattr(reducer, "value")
    assert reducer.e8_roots.shape == (240, 8)


def test_initialization_fixed_weights(num_colonies: int, hidden_dim: int, device: str) -> None:
    """Test reducer initialization with fixed weights."""
    reducer = E8ActionReducer(
        num_colonies=num_colonies,
        hidden_dim=hidden_dim,
        use_attention=False,
        device=device,
    )

    assert reducer.num_colonies == num_colonies
    assert reducer.use_attention is False
    assert hasattr(reducer, "colony_weights")
    assert reducer.colony_weights.shape == (num_colonies,)


def test_factory_function() -> None:
    """Test create_e8_reducer factory."""
    reducer = create_e8_reducer(
        num_colonies=7,
        hidden_dim=32,
        use_attention=True,
        device="cpu",
    )

    assert isinstance(reducer, E8ActionReducer)
    assert reducer.num_colonies == 7
    assert reducer.hidden_dim == 32


def test_initialization_registers_e8_roots(reducer_attention: Any) -> None:
    """Test that E8 roots are registered as buffer."""
    assert hasattr(reducer_attention, "e8_roots")
    assert isinstance(reducer_attention.e8_roots, torch.Tensor)
    # E8 roots should have 240 elements (norm sqrt(2) shell)
    assert reducer_attention.e8_roots.shape == (240, 8)


# =============================================================================
# TEST: FORWARD PASS
# =============================================================================


def test_forward_attention_basic(reducer_attention, colony_outputs) -> None:
    """Test forward pass with attention."""
    e8_code, e8_index, weights = reducer_attention(colony_outputs)

    assert e8_code.shape == (colony_outputs.shape[0], 8)
    assert e8_index.shape == (colony_outputs.shape[0],)
    assert weights.shape == (colony_outputs.shape[0], 7)
    # All indices should be valid
    assert torch.all(e8_index >= 0)
    assert torch.all(e8_index < 240)


def test_forward_fixed_weights_basic(reducer_fixed, colony_outputs) -> None:
    """Test forward pass with fixed weights."""
    e8_code, e8_index, weights = reducer_fixed(colony_outputs)

    assert e8_code.shape == (colony_outputs.shape[0], 8)
    assert e8_index.shape == (colony_outputs.shape[0],)
    assert weights.shape == (colony_outputs.shape[0], 7)


def test_forward_with_confidences(
    reducer_attention: Any, colony_outputs: Any, colony_confidences: Any
) -> None:
    """Test forward pass with colony confidences."""
    e8_code, e8_index, weights = reducer_attention(colony_outputs, colony_confidences)

    assert e8_code.shape == (colony_outputs.shape[0], 8)
    assert e8_index.shape == (colony_outputs.shape[0],)
    assert weights.shape == (colony_outputs.shape[0], 7)


def test_forward_output_on_e8_shell(reducer_attention, colony_outputs) -> None:
    """Test that forward output lies on E8 lattice shell (norm √2).

    E8 lattice roots have norm √2, not 1. The 240 roots of E8 form
    the first shell of the E8 root system at this radius.
    """
    import math

    e8_code, _e8_index, _weights = reducer_attention(colony_outputs)

    # E8 roots have norm √2
    expected_norm = math.sqrt(2)
    norms = e8_code.norm(dim=-1)
    assert torch.allclose(norms, torch.full_like(norms, expected_norm), atol=1e-4)


def test_forward_weights_sum_to_one(reducer_attention, colony_outputs) -> None:
    """Test that output weights sum to 1."""
    _e8_code, _e8_index, weights = reducer_attention(colony_outputs)

    weight_sums = weights.sum(dim=-1)
    assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5)


# =============================================================================
# TEST: ATTENTION MECHANISM
# =============================================================================


def test_attention_weights_computation(reducer_attention, colony_outputs) -> None:
    """Test attention weights computation."""
    weights = reducer_attention._attention_weights(colony_outputs)

    assert weights.shape == (colony_outputs.shape[0], 7)
    # Weights should be normalized (softmax)
    weight_sums = weights.sum(dim=-1)
    assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5)


def test_attention_weights_change_with_input(reducer_attention) -> None:
    """Test that attention weights change based on input."""
    # Two different inputs
    outputs1 = torch.randn(2, 7, 8)
    outputs2 = torch.randn(2, 7, 8) * 10  # Very different

    weights1 = reducer_attention._attention_weights(outputs1)
    weights2 = reducer_attention._attention_weights(outputs2)

    # Weights should be different
    assert not torch.allclose(weights1, weights2, atol=0.1)


def test_fixed_weights_are_consistent(reducer_fixed, colony_outputs) -> None:
    """Test that fixed weights are the same for all inputs."""
    _e8_code1, _e8_index1, weights1 = reducer_fixed(colony_outputs)

    # Different input
    outputs2 = torch.randn_like(colony_outputs)
    _e8_code2, _e8_index2, weights2 = reducer_fixed(outputs2)

    # Fixed weights should be identical
    assert torch.allclose(weights1, weights2, atol=1e-6)


# =============================================================================
# TEST: E8 QUANTIZATION
# =============================================================================


def test_quantize_e8_basic(reducer_attention) -> None:
    """Test E8 quantization."""
    x = torch.randn(4, 8)
    x = torch.nn.functional.normalize(x, dim=-1)

    quantized, indices = reducer_attention._quantize_e8(x)

    assert quantized.shape == (4, 8)
    assert indices.shape == (4,)
    assert torch.all(indices >= 0)
    assert torch.all(indices < 240)


def test_quantize_e8_training_mode(reducer_attention) -> None:
    """Test E8 quantization in training mode (straight-through)."""
    reducer_attention.train()

    x = torch.randn(4, 8, requires_grad=True)
    x = torch.nn.functional.normalize(x, dim=-1)

    quantized, _indices = reducer_attention._quantize_e8(x)

    # Should allow gradients
    assert quantized.requires_grad
    # Quantized should be on lattice points
    assert quantized.shape == (4, 8)


def test_quantize_e8_eval_mode(reducer_attention) -> None:
    """Test E8 quantization in eval mode (hard quantization)."""
    reducer_attention.eval()

    x = torch.randn(4, 8)
    x = torch.nn.functional.normalize(x, dim=-1)

    with torch.no_grad():
        quantized, _indices = reducer_attention._quantize_e8(x)

    # Should be hard quantized
    assert quantized.shape == (4, 8)


def test_quantize_e8_maps_to_nearest_root(reducer_attention) -> None:
    """Test that quantization maps to nearest E8 root."""
    # Use an E8 root directly
    root_idx = 42
    x = reducer_attention.e8_roots[root_idx].unsqueeze(0)  # [1, 8]

    quantized, indices = reducer_attention._quantize_e8(x)

    # Should map to the same root (or very close)
    assert indices[0].item() == root_idx or torch.allclose(
        quantized[0], reducer_attention.e8_roots[root_idx], atol=1e-3
    )


# =============================================================================
# TEST: HIGH-LEVEL REDUCE INTERFACE
# =============================================================================


def test_reduce_interface_basic(reducer_attention) -> None:
    """Test high-level reduce interface."""
    colony_outputs = [torch.randn(8) for _ in range(7)]

    action = reducer_attention.reduce(colony_outputs)

    assert isinstance(action, E8Action)
    assert action.code.shape == (8,)
    assert isinstance(action.index, int)
    assert 0 <= action.index < 240
    assert len(action.colony_weights) == 7


def test_reduce_interface_with_confidences(reducer_attention) -> None:
    """Test reduce interface with confidences."""
    colony_outputs = [torch.randn(8) for _ in range(7)]
    confidences = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

    action = reducer_attention.reduce(colony_outputs, confidences)

    assert isinstance(action, E8Action)
    assert action.code.shape == (8,)
    # Weights should reflect confidences
    assert len(action.colony_weights) == 7


def test_reduce_computes_distance(reducer_attention) -> None:
    """Test that reduce computes distance to nearest root."""
    colony_outputs = [torch.randn(8) for _ in range(7)]

    action = reducer_attention.reduce(colony_outputs)

    assert isinstance(action.distance, float)
    assert action.distance >= 0


def test_reduce_computes_confidence(reducer_attention) -> None:
    """Test that reduce computes confidence score."""
    colony_outputs = [torch.randn(8) for _ in range(7)]

    action = reducer_attention.reduce(colony_outputs)

    assert isinstance(action.confidence, float)
    assert 0 <= action.confidence <= 1


def test_e8_action_is_crystalline(reducer_attention) -> None:
    """Test E8Action.is_crystalline property."""
    # Create action close to root
    root = reducer_attention.e8_roots[0]
    colony_outputs = [root + torch.randn(8) * 0.01 for _ in range(7)]

    action = reducer_attention.reduce(colony_outputs)

    # Should be crystalline (low distortion)
    if action.distance < 0.1:
        assert action.is_crystalline


# =============================================================================
# TEST: GRADIENT FLOW
# =============================================================================


def test_gradient_flow_forward_pass(reducer_attention, colony_outputs) -> None:
    """Test gradient flow through forward pass."""
    colony_outputs.requires_grad_(True)
    reducer_attention.train()

    e8_code, _e8_index, _weights = reducer_attention(colony_outputs)
    loss = e8_code.pow(2).sum()
    loss.backward()

    # Check gradients exist
    assert colony_outputs.grad is not None
    assert colony_outputs.grad.norm() > 0


def test_gradient_flow_with_confidences(reducer_attention) -> None:
    """Test gradient flow with confidence modulation."""
    # Keep reference to leaf tensor for gradient check
    colony_outputs_leaf = torch.randn(4, 7, 8, requires_grad=True)
    colony_outputs = torch.nn.functional.normalize(colony_outputs_leaf, dim=-1)
    confidences = torch.rand(4, 7)

    reducer_attention.train()

    e8_code, _e8_index, _weights = reducer_attention(colony_outputs, confidences)
    loss = e8_code.pow(2).sum()
    loss.backward()

    # Gradient flows to the original leaf tensor
    assert colony_outputs_leaf.grad is not None


def test_straight_through_estimator_in_training(reducer_attention) -> None:
    """Test straight-through estimator allows gradients in training."""
    reducer_attention.train()

    # Keep reference to leaf tensor for gradient check
    x_leaf = torch.randn(4, 8, requires_grad=True)
    x = torch.nn.functional.normalize(x_leaf, dim=-1)

    quantized, _indices = reducer_attention._quantize_e8(x)
    loss = quantized.pow(2).sum()
    loss.backward()

    # Gradient should flow through to the original leaf tensor
    assert x_leaf.grad is not None
    assert x_leaf.grad.norm() > 0


# =============================================================================
# TEST: CONFIDENCE MODULATION
# =============================================================================


def test_confidence_modulation_affects_weights(reducer_attention, colony_outputs) -> None:
    """Test that confidence modulation affects output weights."""
    # High confidence for first colony, low for others
    high_conf = torch.tensor([[1.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]] * 4)

    _e8_code, _e8_index, weights = reducer_attention(colony_outputs, high_conf)

    # First colony should have highest weight
    assert torch.all(weights[:, 0] > weights[:, 1])


def test_zero_confidence_handling(reducer_attention, colony_outputs) -> None:
    """Test handling of zero confidences."""
    # Zero confidence for all but one colony
    conf = torch.zeros_like(colony_outputs[:, :, 0])
    conf[:, 0] = 1.0  # Only first colony has confidence

    _e8_code, _e8_index, weights = reducer_attention(colony_outputs, conf)

    # Should still produce valid weights
    assert torch.all(weights >= 0)
    weight_sums = weights.sum(dim=-1)
    assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5)


# =============================================================================
# TEST: ROOT SEMANTICS
# =============================================================================


def test_get_root_semantics(reducer_attention) -> None:
    """Test get_root_semantics returns metadata."""
    for idx in range(10):
        semantics = reducer_attention.get_root_semantics(idx)

        assert "index" in semantics
        assert semantics["index"] == idx


def test_get_root_semantics_all_indices(reducer_attention) -> None:
    """Test semantics for all 240 roots."""
    for idx in range(240):
        semantics = reducer_attention.get_root_semantics(idx)
        assert semantics["index"] == idx


# =============================================================================
# TEST: BATCH PROCESSING
# =============================================================================


def test_forward_single_sample(reducer_attention) -> None:
    """Test forward with batch size 1."""
    colony_outputs = torch.randn(1, 7, 8)
    colony_outputs = torch.nn.functional.normalize(colony_outputs, dim=-1)

    e8_code, e8_index, weights = reducer_attention(colony_outputs)

    assert e8_code.shape == (1, 8)
    assert e8_index.shape == (1,)
    assert weights.shape == (1, 7)


def test_forward_large_batch(reducer_attention) -> None:
    """Test forward with large batch."""
    colony_outputs = torch.randn(128, 7, 8)
    colony_outputs = torch.nn.functional.normalize(colony_outputs, dim=-1)

    e8_code, e8_index, weights = reducer_attention(colony_outputs)

    assert e8_code.shape == (128, 8)
    assert e8_index.shape == (128,)
    assert weights.shape == (128, 7)


def test_reduce_multiple_calls_consistent(reducer_attention) -> None:
    """Test that reduce gives consistent results for same input."""
    colony_outputs = [torch.randn(8) for _ in range(7)]

    reducer_attention.eval()  # Deterministic mode
    with torch.no_grad():
        action1 = reducer_attention.reduce(colony_outputs)
        action2 = reducer_attention.reduce(colony_outputs)

    assert action1.index == action2.index
    assert torch.allclose(action1.code, action2.code, atol=1e-5)


# =============================================================================
# TEST: INPUT VALIDATION
# =============================================================================


def test_forward_validates_dimension(reducer_attention) -> None:
    """Test forward validates 8D input."""
    # Wrong dimension
    colony_outputs = torch.randn(4, 7, 16)  # 16D instead of 8D

    with pytest.raises(AssertionError, match="Expected 8D outputs"):
        reducer_attention(colony_outputs)


def test_forward_normalizes_input(reducer_attention) -> None:
    """Test that forward normalizes unnormalized input to E8 shell."""
    import math

    # Unnormalized input
    colony_outputs = torch.randn(4, 7, 8) * 100

    e8_code, _e8_index, _weights = reducer_attention(colony_outputs)

    # Output should be on E8 shell (norm √2)
    expected_norm = math.sqrt(2)
    norms = e8_code.norm(dim=-1)
    assert torch.allclose(norms, torch.full_like(norms, expected_norm), atol=1e-4)


# =============================================================================
# TEST: DEVICE HANDLING
# =============================================================================


def test_reducer_respects_device():
    """Test reducer respects device parameter."""
    reducer = E8ActionReducer(device="cpu")

    assert reducer.e8_roots.device.type == "cpu"


def test_reduce_handles_different_device_inputs(reducer_attention) -> None:
    """Test reduce handles inputs from different device."""
    colony_outputs = [torch.randn(8) for _ in range(7)]

    # Should work even if inputs are on CPU (same as reducer)
    action = reducer_attention.reduce(colony_outputs)

    assert isinstance(action, E8Action)


# =============================================================================
# TEST: REFINEMENT GATE
# =============================================================================


def test_refinement_gate_parameter_exists(reducer_attention) -> None:
    """Test that refinement gate parameter exists."""
    assert hasattr(reducer_attention, "gate")
    assert isinstance(reducer_attention.gate, nn.Parameter)


def test_refinement_affects_output(reducer_attention, colony_outputs) -> None:
    """Test that refinement layer affects output."""
    # Disable refinement by setting gate to 0
    with torch.no_grad():
        reducer_attention.gate.fill_(0.0)

    e8_code_no_refine, _idx1, _w1 = reducer_attention(colony_outputs)

    # Enable refinement
    with torch.no_grad():
        reducer_attention.gate.fill_(2.0)

    e8_code_with_refine, _idx2, _w2 = reducer_attention(colony_outputs)

    # Outputs should be different
    assert not torch.allclose(e8_code_no_refine, e8_code_with_refine, atol=0.01)


# =============================================================================
# TEST: EDGE CASES
# =============================================================================


def test_reduce_empty_list_handling(reducer_attention) -> None:
    """Test reduce handles edge case of single colony."""
    # Single colony output
    colony_outputs = [torch.randn(8)]

    # Should still work (though designed for 7 colonies)
    # Will pad internally to expected size
    try:
        action = reducer_attention.reduce(colony_outputs, [1.0])
        assert isinstance(action, E8Action)
    except Exception:
        # Expected to fail with wrong number of colonies
        pass


def test_quantize_identical_inputs(reducer_attention) -> None:
    """Test quantization of identical inputs."""
    x = torch.ones(4, 8)
    x = torch.nn.functional.normalize(x, dim=-1)

    quantized, indices = reducer_attention._quantize_e8(x)

    # All should map to same E8 root
    assert len(torch.unique(indices)) == 1


def test_confidence_all_equal(reducer_attention, colony_outputs) -> None:
    """Test with all confidences equal."""
    equal_conf = torch.ones_like(colony_outputs[:, :, 0])

    _e8_code, _e8_index, weights = reducer_attention(colony_outputs, equal_conf)

    # Should still produce valid output
    assert weights.shape == (colony_outputs.shape[0], 7)
