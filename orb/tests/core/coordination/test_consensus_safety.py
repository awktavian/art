"""Tests for compositional CBF consensus safety verification.

CREATED: December 15, 2025
PURPOSE: Verify safety guarantees of consensus decision-making

TEST COVERAGE:
==============
1. Basic safety verification (all colonies safe)
2. Safety violations (some colonies unsafe)
3. Fallback selection (safest colony)
4. Simulation-based prediction
5. Batch verification
6. Metrics tracking
7. Edge cases (empty consensus, single colony, etc.)
"""

from __future__ import annotations
from typing import Any


import pytest
import asyncio

import torch

from kagami.core.coordination.consensus_safety import (
    SafetyVerificationResult,
    SafetyViolation,
    compute_safety_margin_distribution,
    filter_unsafe_consensus,
    get_safest_colony,
    verify_batch_consensus,
    verify_compositional_cbf,
)
from kagami.core.coordination.kagami_consensus import ColonyID, CoordinationProposal
from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def dcbf():
    """Create FanoDecentralizedCBF instance."""
    return FanoDecentralizedCBF(
        state_dim=4,
        hidden_dim=32,
        safety_threshold=0.3,
    )


@pytest.fixture
def safe_states():
    """Create safe colony states (all h_i > 0)."""
    # Low risk states: [threat, uncertainty, complexity, risk] all low
    states = torch.tensor(
        [
            [0.1, 0.1, 0.1, 0.1],  # Spark
            [0.1, 0.1, 0.1, 0.1],  # Forge
            [0.1, 0.1, 0.1, 0.1],  # Flow
            [0.1, 0.1, 0.1, 0.1],  # Nexus
            [0.1, 0.1, 0.1, 0.1],  # Beacon
            [0.1, 0.1, 0.1, 0.1],  # Grove
            [0.1, 0.1, 0.1, 0.1],  # Crystal
        ]
    ).unsqueeze(0)  # [1, 7, 4]

    return states


@pytest.fixture
def unsafe_states():
    """Create unsafe colony states (some h_i < 0)."""
    # High risk for some colonies
    states = torch.tensor(
        [
            [0.1, 0.1, 0.1, 0.1],  # Spark - safe
            [0.9, 0.9, 0.9, 0.9],  # Forge - UNSAFE
            [0.1, 0.1, 0.1, 0.1],  # Flow - safe
            [0.8, 0.8, 0.8, 0.8],  # Nexus - UNSAFE
            [0.1, 0.1, 0.1, 0.1],  # Beacon - safe
            [0.1, 0.1, 0.1, 0.1],  # Grove - safe
            [0.1, 0.1, 0.1, 0.1],  # Crystal - safe
        ]
    ).unsqueeze(0)  # [1, 7, 4]

    return states


@pytest.fixture
def consensus_actions_all_active():
    """Consensus with all colonies active."""
    return dict.fromkeys(ColonyID, "activate")


@pytest.fixture
def consensus_actions_subset():
    """Consensus with subset of colonies active."""
    return {
        ColonyID.SPARK: "activate",
        ColonyID.FORGE: "activate",
        ColonyID.CRYSTAL: "activate",
    }


@pytest.fixture
def sample_proposals():
    """Create sample coordination proposals."""
    return [
        CoordinationProposal(
            proposer=colony,
            target_colonies=[ColonyID.FORGE, ColonyID.CRYSTAL],
            confidence=0.8,
            cbf_margin=0.5,
        )
        for colony in ColonyID
    ]


class MockWorldModel:
    """Mock world model for testing."""

    def __init__(self, return_states: torch.Tensor):
        self.return_states = return_states
        self.rssm = None  # No RSSM by default


# =============================================================================
# BASIC SAFETY VERIFICATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_verify_safe_consensus(
    dcbf: Any, safe_states: Any, consensus_actions_all_active: Any
) -> None:
    """Test verification of safe consensus (all h_i ≥ 0)."""
    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions_all_active,
        dcbf=dcbf,
        world_model=None,
        current_states=safe_states,
        threshold=0.0,
        use_simulation=False,
    )

    assert is_safe is True
    assert details["min_barrier"] >= 0.0
    assert len(details["violated_colonies"]) == 0
    assert details["fallback_colony"] is None

    # Check h_values dict
    assert len(details["h_values"]) == 7
    for h_val in details["h_values"].values():
        assert h_val >= 0.0


@pytest.mark.asyncio
async def test_verify_unsafe_consensus(
    dcbf: Any, unsafe_states: Any, consensus_actions_all_active: Any
) -> None:
    """Test verification of unsafe consensus (some h_i < 0)."""
    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions_all_active,
        dcbf=dcbf,
        world_model=None,
        current_states=unsafe_states,
        threshold=0.0,
        use_simulation=False,
    )

    assert is_safe is False
    assert details["min_barrier"] < 0.0
    assert len(details["violated_colonies"]) > 0
    assert details["fallback_colony"] is not None

    # Check that violated colonies are detected
    violated = details["violated_colonies"]
    assert len(violated) >= 1  # At least one violation

    # Check fallback is safest colony
    fallback_idx = details["fallback_colony"]
    fallback_h = details["h_values"][fallback_idx]

    # Fallback should have highest h value
    for h_val in details["h_values"].values():
        assert fallback_h >= h_val


@pytest.mark.asyncio
async def test_verify_with_threshold(
    dcbf: Any, safe_states: Any, consensus_actions_subset: Any
) -> None:
    """Test verification with non-zero safety threshold."""
    # Safe states but with strict threshold
    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions_subset,
        dcbf=dcbf,
        world_model=None,
        current_states=safe_states,
        threshold=0.5,  # Strict threshold
        use_simulation=False,
    )

    # With strict threshold, some colonies might fail
    # Check that violations are correctly identified
    if not is_safe:
        assert len(details["violated_colonies"]) > 0
        assert details["min_barrier"] < 0.5


# =============================================================================
# SIMULATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_simulation_based_verification(
    dcbf: Any, safe_states: Any, consensus_actions_subset: Any
) -> None:
    """Test verification with world model simulation."""
    mock_wm = MockWorldModel(return_states=safe_states)

    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions_subset,
        dcbf=dcbf,
        world_model=mock_wm,
        current_states=safe_states,
        threshold=0.0,
        use_simulation=True,  # Use simulation
    )

    # Should work with simulation
    assert isinstance(is_safe, bool)
    assert "h_values" in details
    assert details.get("simulation_used") in [True, False]  # Depends on mock


@pytest.mark.asyncio
async def test_simulation_fallback(dcbf: Any, consensus_actions_subset: Any) -> None:
    """Test fallback when simulation unavailable."""
    # No world model, no current states — should create synthetic states
    mock_wm = MockWorldModel(return_states=torch.zeros(1, 7, 4))

    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions_subset,
        dcbf=dcbf,
        world_model=mock_wm,
        current_states=None,
        threshold=0.0,
        use_simulation=True,
    )

    # Should not crash, should return valid result
    assert isinstance(is_safe, bool)
    assert "h_values" in details


# =============================================================================
# FALLBACK SELECTION TESTS
# =============================================================================


def test_get_safest_colony():
    """Test safest colony selection (argmax_i h_i)."""
    h_values = {
        0: 0.1,
        1: -0.5,  # Unsafe
        2: 0.3,
        3: -0.2,  # Unsafe
        4: 0.8,  # Safest
        5: 0.2,
        6: 0.4,
    }

    safest = get_safest_colony(h_values)
    assert safest == 4  # Colony 4 has highest h value


def test_safety_margin_distribution():
    """Test computation of safety margin statistics."""
    h_values = {
        0: 0.1,
        1: 0.2,
        2: 0.3,
        3: 0.4,
        4: 0.5,
        5: 0.6,
        6: 0.7,
    }

    stats = compute_safety_margin_distribution(h_values)

    # Use approximate equality for float comparisons
    assert abs(stats["min"] - 0.1) < 0.01
    assert abs(stats["max"] - 0.7) < 0.01
    assert 0.3 < stats["mean"] < 0.5
    assert stats["std"] > 0.0


# =============================================================================
# FILTER UNSAFE CONSENSUS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_safe_proposals(dcbf: Any, safe_states: Any, sample_proposals: Any) -> None:
    """Test filtering when consensus is safe."""
    mock_wm = MockWorldModel(return_states=safe_states)

    safe_proposals, result = await filter_unsafe_consensus(
        proposals=sample_proposals,
        dcbf=dcbf,
        world_model=mock_wm,
        threshold=0.0,
    )

    # All proposals should pass
    assert len(safe_proposals) == len(sample_proposals)
    assert result.is_safe is True


@pytest.mark.asyncio
async def test_filter_unsafe_proposals(
    dcbf: Any, unsafe_states: Any, sample_proposals: Any
) -> None:
    """Test filtering when consensus is unsafe (fallback to safest)."""
    mock_wm = MockWorldModel(return_states=unsafe_states)

    safe_proposals, result = await filter_unsafe_consensus(
        proposals=sample_proposals,
        dcbf=dcbf,
        world_model=mock_wm,
        threshold=0.0,
    )

    # Should fallback to single safest colony
    if not result.is_safe:
        assert len(safe_proposals) <= 1  # At most one fallback proposal
        if len(safe_proposals) == 1:
            # Fallback proposal should be from safest colony
            fallback_colony_idx = result.fallback_colony
            assert safe_proposals[0].proposer.value == fallback_colony_idx


# =============================================================================
# BATCH VERIFICATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_batch_verification(dcbf: Any, safe_states: Any, unsafe_states: Any) -> None:
    """Test batch verification of multiple consensus decisions."""
    mock_wm = MockWorldModel(return_states=safe_states)

    # Create batch of consensus actions
    batch_actions = [
        {ColonyID.SPARK: "activate", ColonyID.FORGE: "activate"},
        {ColonyID.BEACON: "activate", ColonyID.GROVE: "activate"},
        dict.fromkeys(ColonyID, "activate"),  # All active
    ]

    results = await verify_batch_consensus(
        batch_consensus_actions=batch_actions,
        dcbf=dcbf,
        world_model=mock_wm,
        threshold=0.0,
    )

    assert len(results) == 3
    for result in results:
        assert isinstance(result, SafetyVerificationResult)
        assert "h_values" in result.details


# =============================================================================
# EDGE CASES
# =============================================================================


@pytest.mark.asyncio
async def test_empty_consensus(dcbf: Any, safe_states: Any) -> None:
    """Test verification with empty consensus (no colonies active)."""
    empty_actions = {}

    is_safe, _details = await verify_compositional_cbf(
        consensus_actions=empty_actions,
        dcbf=dcbf,
        world_model=None,
        current_states=safe_states,
        threshold=0.0,
        use_simulation=False,
    )

    # Should still verify (all colonies in safe state)
    assert isinstance(is_safe, bool)


@pytest.mark.asyncio
async def test_single_colony_consensus(dcbf: Any, safe_states: Any) -> None:
    """Test verification with single colony active."""
    single_action = {ColonyID.FORGE: "activate"}

    is_safe, details = await verify_compositional_cbf(
        consensus_actions=single_action,
        dcbf=dcbf,
        world_model=None,
        current_states=safe_states,
        threshold=0.0,
        use_simulation=False,
    )

    assert isinstance(is_safe, bool)
    assert len(details["h_values"]) == 7  # All colonies evaluated


@pytest.mark.asyncio
async def test_invalid_inputs(dcbf: Any) -> None:
    """Test error handling for invalid inputs."""
    # No world model and no current states - should return False with error
    is_safe, details = await verify_compositional_cbf(
        consensus_actions={},
        dcbf=dcbf,
        world_model=None,
        current_states=None,
        threshold=0.0,
        use_simulation=False,
    )

    # Should handle error gracefully
    assert is_safe is False
    assert "error" in details


@pytest.mark.asyncio
async def test_wrong_state_dimensions(dcbf: Any, consensus_actions_subset: Any) -> None:
    """Test error handling for wrong state dimensions."""
    wrong_states = torch.randn(1, 5, 4)  # Only 5 colonies (should be 7)

    # Should handle error gracefully and return False
    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions_subset,
        dcbf=dcbf,
        world_model=None,
        current_states=wrong_states,
        threshold=0.0,
        use_simulation=False,
    )

    # Should detect error and return False
    assert is_safe is False
    assert "error" in details


# =============================================================================
# METRICS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_metrics_tracking(dcbf: Any, safe_states: Any, consensus_actions_subset: Any) -> None:
    """Test that metrics are correctly updated."""
    from kagami.core.coordination.consensus_safety import (
        cbf_checks_total,
        cbf_margin_min,
    )

    # Get initial metric values
    initial_safe_count = cbf_checks_total.labels(result="safe")._value.get()

    # Run verification
    await verify_compositional_cbf(
        consensus_actions=consensus_actions_subset,
        dcbf=dcbf,
        world_model=None,
        current_states=safe_states,
        threshold=0.0,
        use_simulation=False,
    )

    # Check metric incremented
    final_safe_count = cbf_checks_total.labels(result="safe")._value.get()
    assert final_safe_count > initial_safe_count

    # Check gauge updated (min barrier)
    min_barrier_metric = cbf_margin_min._value.get()
    assert min_barrier_metric is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_full_consensus_safety_workflow(
    dcbf: Any, safe_states: Any, sample_proposals: Any
) -> None:
    """Test full workflow: proposals → consensus → safety check → execution."""
    mock_wm = MockWorldModel(return_states=safe_states)

    # Step 1: Filter proposals for safety
    safe_proposals, result = await filter_unsafe_consensus(
        proposals=sample_proposals,
        dcbf=dcbf,
        world_model=mock_wm,
        threshold=0.0,
    )

    # Step 2: Verify result structure
    assert isinstance(result, SafetyVerificationResult)
    assert result.check_duration > 0.0

    # Step 3: Check consensus actions can be extracted
    if result.is_safe:
        # Safe: use all proposals
        assert len(safe_proposals) > 0
    else:
        # Unsafe: fallback to safest
        assert result.fallback_colony is not None

    # Step 4: Compute margin distribution
    if result.h_values:
        stats = compute_safety_margin_distribution(result.h_values)
        assert "min" in stats
        assert "max" in stats


@pytest.mark.asyncio
async def test_byzantine_fault_tolerance(
    dcbf: Any, unsafe_states: Any, sample_proposals: Any
) -> None:
    """Test that safety verification handles Byzantine faults (unsafe colonies)."""
    # Simulate Byzantine behavior: 2 colonies propose unsafe actions
    # With 7 colonies, can tolerate up to 2 Byzantine faults
    mock_wm = MockWorldModel(return_states=unsafe_states)

    _safe_proposals, result = await filter_unsafe_consensus(
        proposals=sample_proposals,
        dcbf=dcbf,
        world_model=mock_wm,
        threshold=0.0,
    )

    # System should detect violations and fallback
    if not result.is_safe:
        # Should identify violated colonies
        assert len(result.violated_colonies) > 0

        # Should provide fallback
        assert result.fallback_colony is not None

        # Fallback should be safe
        fallback_h = result.h_values[result.fallback_colony]
        assert fallback_h >= 0.0


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_verification_performance(
    dcbf: Any, safe_states: Any, consensus_actions_subset: Any
) -> None:
    """Test that verification completes quickly."""
    import time

    start = time.time()

    await verify_compositional_cbf(
        consensus_actions=consensus_actions_subset,
        dcbf=dcbf,
        world_model=None,
        current_states=safe_states,
        threshold=0.0,
        use_simulation=False,
    )

    duration = time.time() - start

    # Should complete in under 100ms for single verification
    assert duration < 0.1


@pytest.mark.asyncio
async def test_batch_performance(dcbf: Any, safe_states: Any) -> None:
    """Test batch verification performance."""
    mock_wm = MockWorldModel(return_states=safe_states)

    # Create large batch
    batch_size = 50
    batch_actions = [
        {ColonyID.SPARK: "activate", ColonyID.FORGE: "activate"} for _ in range(batch_size)
    ]

    import time

    start = time.time()

    results = await verify_batch_consensus(
        batch_consensus_actions=batch_actions,
        dcbf=dcbf,
        world_model=mock_wm,
        threshold=0.0,
    )

    duration = time.time() - start

    assert len(results) == batch_size

    # Should complete in under 5 seconds for 50 verifications
    assert duration < 5.0

    # Average per-item time
    avg_time = duration / batch_size
    assert avg_time < 0.1  # Under 100ms per verification


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
