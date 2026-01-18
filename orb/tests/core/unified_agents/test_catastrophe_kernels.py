"""Tests for Catastrophe Decision Kernels.

COVERAGE:
========
- Individual kernel instantiation and forward pass
- Fast path (k<3) reflexive decisions
- Slow path (k≥3) deliberative decisions
- k-value routing logic
- Batched evaluation of all 7 colonies
- Epistemic/pragmatic bias per colony
- Gradient flow for training
- S⁷ normalization invariant
- Context integration (goals, weights)

Created: December 14, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.unified_agents.catastrophe_kernels import (
    CatastropheKernel,
    FoldKernel,
    CuspKernel,
    SwallowtailKernel,
    ButterflyKernel,
    HyperbolicKernel,
    EllipticKernel,
    ParabolicKernel,
    create_colony_kernel,
    batch_evaluate_kernels,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def batch_size():
    """Default batch size for tests."""
    return 4


@pytest.fixture
def state_dim():
    """Default state dimension."""
    return 256


@pytest.fixture
def hidden_dim():
    """Default hidden dimension."""
    return 256


@pytest.fixture
def device():
    """Default device."""
    return "cpu"


@pytest.fixture
def test_state(batch_size, state_dim, device) -> Any:
    """Create test state tensor."""
    return torch.randn(batch_size, state_dim, device=device)


@pytest.fixture
def test_goals(batch_size, device) -> Any:
    """Create test goals tensor."""
    return torch.randn(batch_size, 15, device=device)  # E8(8) + S⁷(7)


@pytest.fixture
def test_context(test_goals) -> Dict[str, Any]:
    """Create test context dict."""
    return {"goals": test_goals}


# =============================================================================
# TEST: INDIVIDUAL KERNEL INSTANTIATION
# =============================================================================


@pytest.mark.parametrize(
    "colony_idx,kernel_class",
    [
        (0, FoldKernel),
        (1, CuspKernel),
        (2, SwallowtailKernel),
        (3, ButterflyKernel),
        (4, HyperbolicKernel),
        (5, EllipticKernel),
        (6, ParabolicKernel),
    ],
)
def test_kernel_instantiation(colony_idx, kernel_class, state_dim, hidden_dim) -> None:
    """Test individual kernel instantiation."""
    kernel = create_colony_kernel(colony_idx, state_dim, hidden_dim)
    assert isinstance(kernel, kernel_class)
    assert kernel.colony_idx == colony_idx
    assert kernel.state_dim == state_dim
    assert kernel.hidden_dim == hidden_dim


# =============================================================================
# TEST: FAST PATH (k<3)
# =============================================================================


@pytest.mark.parametrize("colony_idx", range(7))
def test_fast_path(colony_idx, test_state, batch_size) -> None:
    """Test fast path forward pass."""
    kernel = create_colony_kernel(colony_idx)

    # Fast path (k=1)
    action = kernel.forward_fast(test_state)

    # Check shape
    assert action.shape == (batch_size, 8)

    # Check S⁷ normalization
    norms = action.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    # Check differentiability
    assert action.requires_grad


@pytest.mark.parametrize("k_value", [1, 2])
def test_routing_to_fast_path(test_state, k_value) -> None:
    """Test routing to fast path when k<3."""
    kernel = create_colony_kernel(0)  # Spark
    action = kernel(test_state, k_value=k_value)

    # Should use fast path
    assert action.shape == (test_state.shape[0], 8)


# =============================================================================
# TEST: SLOW PATH (k≥3)
# =============================================================================


@pytest.mark.parametrize("colony_idx", range(7))
def test_slow_path(colony_idx, test_state, test_context, batch_size) -> None:
    """Test slow path forward pass."""
    kernel = create_colony_kernel(colony_idx)

    # Slow path (k=5)
    action = kernel.forward_slow(test_state, test_context)

    # Check shape
    assert action.shape == (batch_size, 8)

    # Check S⁷ normalization
    norms = action.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    # Check differentiability
    assert action.requires_grad


@pytest.mark.parametrize("k_value", [3, 5, 7, 11])
def test_routing_to_slow_path(test_state, test_context, k_value) -> None:
    """Test routing to slow path when k≥3."""
    kernel = create_colony_kernel(0)  # Spark
    action = kernel(test_state, k_value=k_value, context=test_context)

    # Should use slow path
    assert action.shape == (test_state.shape[0], 8)


# =============================================================================
# TEST: K-VALUE ROUTING
# =============================================================================


def test_k_value_routing_logic(test_state, test_context) -> None:
    """Test that k-value correctly routes to fast vs slow path."""
    kernel = create_colony_kernel(0)  # Spark

    # k<3: Fast path
    action_k1 = kernel(test_state, k_value=1)
    action_k2 = kernel(test_state, k_value=2)

    # k≥3: Slow path
    action_k3 = kernel(test_state, k_value=3, context=test_context)
    action_k5 = kernel(test_state, k_value=5, context=test_context)

    # Fast path should be identical for k=1 and k=2 (same logic)
    # But different from slow path
    fast_slow_diff = (action_k1 - action_k3).norm()
    assert fast_slow_diff > 0.1  # Should be significantly different


# =============================================================================
# TEST: BATCHED EVALUATION
# =============================================================================


def test_batch_evaluate_all_colonies(test_state, test_context, batch_size) -> None:
    """Test batched evaluation of all 7 colonies."""
    kernels = [create_colony_kernel(i) for i in range(7)]

    actions = batch_evaluate_kernels(
        kernels,
        test_state,
        k_value=3,
        context=test_context,
    )

    # Check shape [batch, 7, 8]
    assert actions.shape == (batch_size, 7, 8)

    # Check all normalized
    norms = actions.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


# =============================================================================
# TEST: EPISTEMIC/PRAGMATIC BIASES
# =============================================================================


@pytest.mark.parametrize(
    "colony_idx,expected_epistemic,expected_pragmatic",
    [
        (0, 1.5, 0.5),  # Spark: high curiosity
        (1, 0.5, 2.0),  # Forge: high goal focus
        (2, 0.8, 1.5),  # Flow: moderate
        (3, 1.2, 1.2),  # Nexus: balanced
        (4, 1.0, 1.8),  # Beacon: planning
        (5, 2.0, 0.3),  # Grove: maximum curiosity
        (6, 0.3, 2.5),  # Crystal: maximum goal focus
    ],
)
def test_colony_biases(colony_idx, expected_epistemic, expected_pragmatic) -> None:
    """Test that each colony has correct epistemic/pragmatic bias."""
    kernel = create_colony_kernel(colony_idx)

    epistemic = kernel.epistemic_bias.item()  # type: ignore[operator]
    pragmatic = kernel.pragmatic_bias.item()  # type: ignore[operator]

    assert epistemic == pytest.approx(expected_epistemic, abs=1e-6)
    assert pragmatic == pytest.approx(expected_pragmatic, abs=1e-6)


def test_epistemic_pragmatic_influence():
    """Test that epistemic/pragmatic weights can be set in context."""
    kernel = create_colony_kernel(0)  # Spark
    state = torch.randn(1, 256)
    goals = torch.randn(1, 15)

    # High epistemic (exploration)
    context_explore = {
        "goals": goals,
        "epistemic_weight": 5.0,
        "pragmatic_weight": 0.01,
    }
    action_explore = kernel.forward_slow(state, context_explore)

    # High pragmatic (exploitation)
    context_exploit = {
        "goals": goals,
        "epistemic_weight": 0.01,
        "pragmatic_weight": 5.0,
    }
    action_exploit = kernel.forward_slow(state, context_exploit)

    # Both should be valid S⁷ vectors
    assert action_explore.shape == (1, 8)
    assert action_exploit.shape == (1, 8)
    assert torch.allclose(action_explore.norm(dim=-1), torch.ones(1), atol=1e-5)
    assert torch.allclose(action_exploit.norm(dim=-1), torch.ones(1), atol=1e-5)


# =============================================================================
# TEST: GRADIENT FLOW
# =============================================================================


def test_gradient_flow_fast_path():
    """Test gradient flow through fast path."""
    kernel = create_colony_kernel(0)
    state = torch.randn(4, 256, requires_grad=True)

    action = kernel.forward_fast(state)
    loss = action.pow(2).sum()
    loss.backward()

    # Check state gradients
    assert state.grad is not None
    assert state.grad.norm() > 0


def test_gradient_flow_slow_path():
    """Test gradient flow through slow path."""
    kernel = create_colony_kernel(0)
    state = torch.randn(4, 256, requires_grad=True)
    goals = torch.randn(4, 15)
    context = {"goals": goals}

    action = kernel.forward_slow(state, context)
    loss = action.pow(2).sum()
    loss.backward()

    # Check state gradients
    assert state.grad is not None
    assert state.grad.norm() > 0

    # Check parameter gradients exist
    has_grads = sum(1 for p in kernel.parameters() if p.grad is not None)
    assert has_grads > 0


# =============================================================================
# TEST: S⁷ NORMALIZATION INVARIANT
# =============================================================================


@pytest.mark.parametrize("k_value", [1, 3, 5])
def test_s7_normalization_invariant(k_value) -> None:
    """Test that all outputs are normalized to S⁷."""
    kernel = create_colony_kernel(0)
    state = torch.randn(10, 256)  # Larger batch
    goals = torch.randn(10, 15)
    context = {"goals": goals}

    action = kernel(state, k_value=k_value, context=context)

    # All norms should be 1.0 (unit sphere)
    norms = action.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


# =============================================================================
# TEST: CONTEXT INTEGRATION
# =============================================================================


def test_context_with_goals():
    """Test context integration with goals."""
    kernel = create_colony_kernel(0)
    state = torch.randn(2, 256)
    goals = torch.randn(2, 15)
    context = {"goals": goals}

    # Should work with goals
    action = kernel.forward_slow(state, context)
    assert action.shape == (2, 8)


def test_context_without_goals():
    """Test context without goals (should still work)."""
    kernel = create_colony_kernel(0)
    state = torch.randn(2, 256)
    context = {}  # Empty context

    # Should work without goals
    action = kernel.forward_slow(state, context)
    assert action.shape == (2, 8)


# =============================================================================
# TEST: COLONY-SPECIFIC BEHAVIORS
# =============================================================================


def test_flow_safety_margin_modulation():
    """Test Flow kernel's safety margin context integration."""
    kernel = create_colony_kernel(2)  # Flow
    state = torch.randn(2, 256)
    goals = torch.randn(2, 15)

    # With low safety margin
    context_unsafe = {
        "goals": goals,
        "safety_margin": torch.tensor([-0.5, -0.3]),  # Unsafe
    }
    action_unsafe = kernel.forward_slow(state, context_unsafe)

    # With high safety margin
    context_safe = {
        "goals": goals,
        "safety_margin": torch.tensor([0.8, 0.9]),  # Safe
    }
    action_safe = kernel.forward_slow(state, context_safe)

    # Both should be normalized to S⁷
    assert torch.allclose(action_unsafe.norm(dim=-1), torch.ones(2), atol=1e-5)
    assert torch.allclose(action_safe.norm(dim=-1), torch.ones(2), atol=1e-5)

    # Both should be valid outputs
    assert action_unsafe.shape == (2, 8)
    assert action_safe.shape == (2, 8)


def test_crystal_cbf_projection():
    """Test Crystal kernel's CBF awareness."""
    kernel = create_colony_kernel(6)  # Crystal
    state = torch.randn(2, 256)
    goals = torch.randn(2, 15)

    # Mock barrier function (h(x) < 0 for unsafe)
    def barrier_function(s):
        # First sample unsafe, second safe
        return torch.tensor([-0.2, 0.5])

    context = {
        "goals": goals,
        "barrier_function": barrier_function,
    }

    action = kernel.forward_slow(state, context)

    # Should still be normalized
    norms = action.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


# =============================================================================
# TEST: EDGE CASES
# =============================================================================


def test_single_sample_batch():
    """Test with batch size 1."""
    kernel = create_colony_kernel(0)
    state = torch.randn(1, 256)
    goals = torch.randn(1, 15)
    context = {"goals": goals}

    action = kernel(state, k_value=3, context=context)
    assert action.shape == (1, 8)


def test_large_batch():
    """Test with large batch size."""
    kernel = create_colony_kernel(0)
    state = torch.randn(128, 256)
    goals = torch.randn(128, 15)
    context = {"goals": goals}

    action = kernel(state, k_value=3, context=context)
    assert action.shape == (128, 8)


def test_invalid_colony_idx():
    """Test error handling for invalid colony index."""
    with pytest.raises(ValueError, match="colony_idx must be in"):
        create_colony_kernel(colony_idx=7)  # Out of range


# =============================================================================
# TEST: REPRODUCIBILITY
# =============================================================================


def test_deterministic_with_fixed_seed():
    """Test reproducibility with fixed random seed."""
    kernel = create_colony_kernel(0)
    state = torch.randn(2, 256)
    goals = torch.randn(2, 15)
    context = {"goals": goals}

    # Set seed
    torch.manual_seed(42)
    action1 = kernel(state, k_value=3, context=context)

    # Reset seed
    torch.manual_seed(42)
    action2 = kernel(state, k_value=3, context=context)

    # Should be identical
    assert torch.allclose(action1, action2, atol=1e-6)
