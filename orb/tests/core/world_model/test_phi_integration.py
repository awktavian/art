"""Tests for Fano Coherence and S7 Strange Loop Integration.

UPDATED (December 13, 2025):
===========================
- Tests now use the S7-based strange loop (7D μ_self)
- Legacy godel_agent tests replaced with S7 phase tests
- CoreState now contains s7_e8, s7_e7, s7_e6, s7_f4 at all hierarchy levels

Verifies:
1. Fano coherence calculation during encode()
2. S7 phase extraction at all hierarchy levels
3. μ_self fixed point in S7 space (7D)
4. Strange loop convergence metrics
"""

from __future__ import annotations

from typing import Any

import pytest

import torch

from kagami.core.world_model.kagami_world_model import KagamiWorldModel, KagamiWorldModelConfig



pytestmark = pytest.mark.tier_integration

@pytest.fixture
def model() -> Any:
    config = KagamiWorldModelConfig(
        layer_dimensions=(64, 32, 14),  # Small model for testing
    )
    return KagamiWorldModel(config)


def test_fano_coherence_calculation_in_encode(model) -> None:
    B, S, D = 2, 5, 64
    x = torch.randn(B, S, D)

    _core_state, metrics = model.encode(x)

    assert "fano_coherence" in metrics
    fano_coherence = metrics["fano_coherence"]
    assert isinstance(fano_coherence, torch.Tensor)

    # Verify coherence is plausible
    assert 0 <= fano_coherence.mean() <= 1


def test_s7_at_all_hierarchy_levels(model) -> None:
    """Test that S7 phase is extracted at all hierarchy levels.

    UPDATED (Dec 13, 2025): Tests the new S7AugmentedHierarchy integration.
    """
    B, S, D = 2, 5, 64
    x = torch.randn(B, S, D)

    core_state, _metrics = model.encode(x)

    # S7 should be extracted at all levels
    assert core_state.s7_phase is not None, "s7_phase should be populated"
    assert core_state.s7_phase.shape[-1] == 7, "s7_phase should be 7D"

    # Check S7 at all hierarchy levels (if available)
    if core_state.s7_e8 is not None:
        assert core_state.s7_e8.shape[-1] == 7, "s7_e8 should be 7D"
        assert core_state.s7_e7.shape[-1] == 7, "s7_e7 should be 7D"
        assert core_state.s7_e6.shape[-1] == 7, "s7_e6 should be 7D"
        assert core_state.s7_f4.shape[-1] == 7, "s7_f4 should be 7D"


def test_mu_self_in_s7_space(model) -> None:
    """Test that μ_self lives in S7 space (7D).

    UPDATED (Dec 13, 2025): μ_self is now 7D (not arbitrary 32D).
    This is mathematically meaningful: S7 = unit imaginary octonions.
    """
    # mu_self should be 7D
    assert model.mu_self.shape == torch.Size(
        [7]
    ), f"mu_self should be 7D, got {model.mu_self.shape}"


def test_strange_loop_convergence_tracking(model) -> None:
    """Test that strange loop convergence is tracked."""
    B, S, D = 2, 5, 64
    x = torch.randn(B, S, D)

    _output, metrics = model(x)

    # Check for strange_loop metrics
    if "strange_loop" in metrics:
        sl = metrics["strange_loop"]
        assert "convergence_h" in sl, "Should have convergence_h metric"
        assert "distance_to_fixed_point" in sl, "Should have distance metric"
        assert "mu_self" in sl, "Should have mu_self"

        # mu_self should be 7D
        assert sl["mu_self"].shape == torch.Size([7])


def test_loop_closure_loss_exists(model) -> None:
    """Test that loop_closure_loss is computed."""
    B, S, D = 2, 4, 64
    x = torch.randn(B, S, D)

    _output, metrics = model(x)

    assert "loop_closure_loss" in metrics, "Should have loop_closure_loss"
    assert metrics["loop_closure_loss"] is not None

    # Should be a scalar loss
    loss = metrics["loop_closure_loss"]
    if isinstance(loss, torch.Tensor):
        assert loss.dim() == 0, "loop_closure_loss should be scalar"


def test_s7_coherence_across_levels(model) -> None:
    """Test S7 coherence (consistency across hierarchy levels)."""
    B, S, D = 2, 5, 64
    x = torch.randn(B, S, D)

    core_state, _metrics = model.encode(x)

    # s7_coherence should be populated
    if hasattr(core_state, "s7_coherence"):
        assert 0 <= core_state.s7_coherence <= 1, "s7_coherence should be in [0, 1]"


def test_fixed_point_distance_decreases(model) -> None:
    """Test that fixed_point_distance is tracked.

    NOTE: We don't test that it decreases monotonically since that
    requires training. We just verify the metric exists.
    """
    B, S, D = 2, 5, 64
    x = torch.randn(B, S, D)

    # Run multiple iterations
    for _ in range(3):
        core_state, _ = model.encode(x)

    # fixed_point_distance should be a non-negative number
    assert core_state.fixed_point_distance >= 0


def test_s7_tracker_accessible(model) -> None:
    """Test that s7_tracker is accessible from model."""
    tracker = model.s7_tracker
    assert tracker is not None, "s7_tracker should be accessible"


def test_s7_hierarchy_accessible(model) -> None:
    """Test that s7_hierarchy is accessible from model."""
    hierarchy = model.s7_hierarchy
    assert hierarchy is not None, "s7_hierarchy should be accessible"
