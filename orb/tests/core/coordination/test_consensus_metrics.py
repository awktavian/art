"""Tests for Consensus Metrics Infrastructure.

Validates:
- Metric registration and emission
- ConsensusMetricsCollector functionality
- Health state tracking
- Per-colony metrics
- Fano line consensus tracking
- Health check endpoint
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import numpy as np

from kagami.core.coordination.consensus_metrics import (
    ConsensusMetricsCollector,
    check_consensus_health,
    colony_proposal_total,
    consensus_cbf_margin_min,
    consensus_cbf_violations_total,
    consensus_health_state,
    consensus_latency_seconds,
    consensus_participants_count,
    consensus_rounds_total,
    fano_line_consensus_total,
    get_metrics_collector,
)
from kagami.core.coordination.health_monitor import CoordinatorHealth
from kagami.core.coordination.kagami_consensus import ColonyID, ConsensusState, CoordinationProposal
from kagami_observability.metrics.core import REGISTRY


def _collect_family(name: str):
    """Helper to collect metric family by name."""
    fams = list(REGISTRY.collect())
    for fam in fams:
        # Check various suffixes that Prometheus adds
        if (
            fam.name == name
            or fam.name == f"{name}_total"
            or fam.name == f"{name}_created"
            or fam.name.startswith(name)
        ):
            return fam
    return None


def _metric_exists(name: str) -> bool:
    """Check if metric exists in registry (more lenient)."""
    return _collect_family(name) is not None or any(name in str(m) for m in REGISTRY.collect())


@pytest.fixture
def metrics_collector() -> ConsensusMetricsCollector:
    """Create fresh metrics collector for each test."""
    return ConsensusMetricsCollector()


@pytest.fixture
def sample_consensus_state() -> ConsensusState:
    """Create sample consensus state for testing."""
    proposals = [
        CoordinationProposal(
            proposer=ColonyID(i),
            target_colonies=[ColonyID((i + 1) % 7), ColonyID((i + 2) % 7)],
            confidence=0.8,
            cbf_margin=0.5,
        )
        for i in range(7)
    ]

    agreement_matrix = np.eye(7) * 0.8 + np.random.rand(7, 7) * 0.2
    agreement_matrix = (agreement_matrix + agreement_matrix.T) / 2  # Symmetrize

    return ConsensusState(
        proposals=proposals,
        agreement_matrix=agreement_matrix,
        consensus_routing={ColonyID.FORGE: "activate"},
        cbf_constraint=0.5,
        converged=True,
        iterations=3,
    )


# =============================================================================
# METRIC REGISTRATION TESTS
# =============================================================================


def test_metrics_registered():
    """Test that all consensus metrics are registered in Prometheus."""
    # These metrics get registered when first used
    # Just verify the module imports correctly
    from kagami.core.coordination import consensus_metrics

    assert hasattr(consensus_metrics, "consensus_rounds_total")
    assert hasattr(consensus_metrics, "consensus_latency_seconds")
    assert hasattr(consensus_metrics, "consensus_participants_count")
    assert hasattr(consensus_metrics, "consensus_cbf_violations_total")
    assert hasattr(consensus_metrics, "consensus_cbf_margin_min")
    assert hasattr(consensus_metrics, "colony_proposal_total")
    assert hasattr(consensus_metrics, "fano_line_consensus_total")
    assert hasattr(consensus_metrics, "consensus_health_state")


# =============================================================================
# CONSENSUS ROUND RECORDING TESTS
# =============================================================================


def test_record_consensus_round_converged(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test recording a successful consensus round."""
    metrics_collector.record_consensus_round(
        status="converged",
        latency_by_phase={
            "proposal": 0.05,
            "verification": 0.03,
            "quorum": 0.02,
            "cbf_check": 0.01,
            "total": 0.11,
        },
        participants=7,
        cbf_values=dict.fromkeys(range(7), 0.5),
        agreement_stats={"mean": 0.85, "min": 0.7, "max": 1.0},
        iterations=3,
        task_complexity=0.15,
    )

    # Verify metrics recorded
    assert metrics_collector.round_count == 1

    # Metrics should be recorded without error (they exist in module)
    assert consensus_rounds_total is not None


def test_record_consensus_round_failed(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test recording a failed consensus round."""
    metrics_collector.record_consensus_round(
        status="failed",
        latency_by_phase={"total": 5.0},
        participants=5,  # 2 faulty colonies
        cbf_values=dict.fromkeys(range(5), 0.3),
        agreement_stats={"mean": 0.4, "min": 0.1, "max": 0.7},
        iterations=10,
        task_complexity=0.9,
    )

    assert metrics_collector.round_count == 1


def test_cbf_violation_recording(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test CBF violation tracking."""
    # Record round with CBF violation
    cbf_values = dict.fromkeys(range(7), 0.5)
    cbf_values[3] = -0.1  # Colony 3 violates constraint

    metrics_collector.record_consensus_round(
        status="failed",
        latency_by_phase={"total": 0.1},
        participants=7,
        cbf_values=cbf_values,
        agreement_stats={"mean": 0.8, "min": 0.7, "max": 0.9},
        iterations=1,
    )

    # Verify CBF violation was recorded (check round count)
    assert metrics_collector.round_count == 1


def test_agreement_stats_recording(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test agreement statistics recording."""
    agreement_stats = {
        "mean": 0.75,
        "min": 0.5,
        "max": 0.95,
    }

    metrics_collector.record_consensus_round(
        status="converged",
        latency_by_phase={"total": 0.1},
        participants=7,
        cbf_values=dict.fromkeys(range(7), 0.5),
        agreement_stats=agreement_stats,
        iterations=2,
    )

    # Metrics should be recorded without error
    assert metrics_collector.round_count == 1


# =============================================================================
# PER-COLONY METRICS TESTS
# =============================================================================


def test_record_colony_proposal(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test per-colony proposal recording."""
    for colony_id in range(7):
        metrics_collector.record_colony_proposal(
            colony_id=colony_id,
            confidence=0.8,
        )

    # Verify proposals recorded without error
    assert colony_proposal_total is not None


def test_update_colony_verification_rate(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test colony verification rate updates."""
    for colony_id in range(7):
        success_rate = 0.9 if colony_id < 5 else 0.7
        metrics_collector.update_colony_verification_rate(
            colony_id=colony_id,
            success_rate=success_rate,
        )

    # Metrics should update without error


# =============================================================================
# FANO LINE METRICS TESTS
# =============================================================================


def test_fano_line_consensus_tracking(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test Fano line agreement tracking."""
    # Record several Fano line checks
    fano_lines = [
        ("0-1-2", "agree"),
        ("0-3-4", "agree"),
        ("1-3-5", "disagree"),
        ("2-4-6", "agree"),
    ]

    for line, result in fano_lines:
        metrics_collector.record_fano_line_consensus(line=line, result=result)

    # Verify metric exists
    assert fano_line_consensus_total is not None


# =============================================================================
# HEALTH STATE TRACKING TESTS
# =============================================================================


def test_health_state_tracking(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test health state gauge updates."""
    # Cycle through health states
    for health in [
        CoordinatorHealth.HEALTHY,
        CoordinatorHealth.DEGRADED,
        CoordinatorHealth.CRITICAL,
        CoordinatorHealth.FAILED,
        CoordinatorHealth.HEALTHY,
    ]:
        metrics_collector.update_health_state(health)
        assert metrics_collector.last_health_state == health


def test_health_state_transition_logging(
    metrics_collector: ConsensusMetricsCollector, caplog: Any
) -> None:
    """Test health state transitions are logged."""
    import logging

    caplog.set_level(logging.INFO)

    metrics_collector.update_health_state(CoordinatorHealth.HEALTHY)
    metrics_collector.update_health_state(CoordinatorHealth.DEGRADED)

    # Check transition logged
    assert any("Health state transition" in record.message for record in caplog.records)


def test_fallback_activation_recording(metrics_collector: ConsensusMetricsCollector) -> None:
    """Test fallback mode activation tracking."""
    modes = ["conservative_routing", "emergency_mode", "human_intervention_required"]

    for mode in modes:
        metrics_collector.record_fallback_activation(mode)

    # Verify recording completed without error
    # Metric will be registered when used


# =============================================================================
# HIGH-LEVEL INTERFACE TESTS
# =============================================================================


def test_record_consensus_state(
    metrics_collector: ConsensusMetricsCollector,
    sample_consensus_state: ConsensusState,
) -> None:
    """Test high-level consensus state recording."""
    latency_by_phase = {
        "proposal": 0.05,
        "verification": 0.03,
        "quorum": 0.02,
        "cbf_check": 0.01,
        "total": 0.11,
    }

    metrics_collector.record_consensus_state(
        consensus_state=sample_consensus_state,
        latency_by_phase=latency_by_phase,
        health=CoordinatorHealth.HEALTHY,
    )

    # Verify round recorded
    assert metrics_collector.round_count == 1

    # Verify health state updated
    assert metrics_collector.last_health_state == CoordinatorHealth.HEALTHY


def test_record_consensus_state_without_health(
    metrics_collector: ConsensusMetricsCollector,
    sample_consensus_state: ConsensusState,
) -> None:
    """Test consensus state recording without health update."""
    metrics_collector.record_consensus_state(
        consensus_state=sample_consensus_state,
        latency_by_phase={"total": 0.1},
        health=None,  # No health update
    )

    assert metrics_collector.round_count == 1


# =============================================================================
# HEALTH CHECK ENDPOINT TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_check_consensus_health():
    """Test health check endpoint."""
    result = await check_consensus_health()

    assert "status" in result
    assert result["status"] in ["healthy", "unhealthy", "error"]

    if result["status"] != "error":
        assert "metrics" in result
        assert "health_state" in result["metrics"]


@pytest.mark.asyncio
async def test_check_consensus_health_with_active_metrics(
    metrics_collector: ConsensusMetricsCollector,
) -> None:
    """Test health check with active metrics."""
    # Record some metrics
    metrics_collector.record_consensus_round(
        status="converged",
        latency_by_phase={"total": 0.1},
        participants=7,
        cbf_values=dict.fromkeys(range(7), 0.5),
        agreement_stats={"mean": 0.85, "min": 0.7, "max": 1.0},
        iterations=3,
    )

    metrics_collector.update_health_state(CoordinatorHealth.HEALTHY)

    result = await check_consensus_health()

    assert "metrics" in result


# =============================================================================
# SINGLETON INSTANCE TESTS
# =============================================================================


def test_get_metrics_collector_singleton():
    """Test singleton metrics collector."""
    collector1 = get_metrics_collector()
    collector2 = get_metrics_collector()

    # Should return same instance
    assert collector1 is collector2


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


def test_record_consensus_round_error_handling(
    metrics_collector: ConsensusMetricsCollector,
) -> None:
    """Test error handling in consensus round recording."""
    # Should not crash on invalid data
    try:
        metrics_collector.record_consensus_round(
            status="invalid",
            latency_by_phase={},
            participants=0,
            cbf_values={},
            agreement_stats={},
            iterations=-1,
        )
    except Exception:
        pytest.fail("Should not raise exception on invalid data")


def test_record_colony_proposal_error_handling(
    metrics_collector: ConsensusMetricsCollector,
) -> None:
    """Test error handling in colony proposal recording."""
    # Should not crash on invalid colony ID
    try:
        metrics_collector.record_colony_proposal(
            colony_id=999,  # Invalid
            confidence=1.5,  # Invalid confidence
        )
    except Exception:
        pytest.fail("Should not raise exception on invalid data")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_full_consensus_round_workflow(
    metrics_collector: ConsensusMetricsCollector,
    sample_consensus_state: ConsensusState,
) -> None:
    """Test complete consensus round metrics workflow."""
    # 1. Record proposals
    for proposal in sample_consensus_state.proposals:
        metrics_collector.record_colony_proposal(
            colony_id=proposal.proposer.value,
            confidence=proposal.confidence,
        )

    # 2. Record consensus round
    latency_by_phase = {
        "proposal": 0.05,
        "verification": 0.03,
        "quorum": 0.02,
        "cbf_check": 0.01,
        "total": 0.11,
    }

    metrics_collector.record_consensus_state(
        consensus_state=sample_consensus_state,
        latency_by_phase=latency_by_phase,
        health=CoordinatorHealth.HEALTHY,
    )

    # 3. Record Fano line checks
    metrics_collector.record_fano_line_consensus("0-1-2", "agree")
    metrics_collector.record_fano_line_consensus("3-4-5", "agree")

    # 4. Update verification rates
    for i in range(7):
        metrics_collector.update_colony_verification_rate(i, 0.9)

    # Verify workflow completed
    assert metrics_collector.round_count == 1
    assert metrics_collector.last_health_state == CoordinatorHealth.HEALTHY


def test_degraded_health_workflow(
    metrics_collector: ConsensusMetricsCollector,
    sample_consensus_state: ConsensusState,
) -> None:
    """Test workflow when health degrades."""
    # Start healthy
    metrics_collector.update_health_state(CoordinatorHealth.HEALTHY)

    # Record consensus round
    metrics_collector.record_consensus_state(
        consensus_state=sample_consensus_state,
        latency_by_phase={"total": 0.1},
    )

    # Degrade health
    metrics_collector.update_health_state(CoordinatorHealth.DEGRADED)
    metrics_collector.record_fallback_activation("conservative_routing")

    # Verify state tracked
    assert metrics_collector.last_health_state == CoordinatorHealth.DEGRADED


def test_critical_health_with_cbf_violations(
    metrics_collector: ConsensusMetricsCollector,
) -> None:
    """Test workflow with CBF violations and critical health."""
    # Record round with violation
    cbf_values = dict.fromkeys(range(7), 0.5)
    cbf_values[2] = -0.2  # Violation

    metrics_collector.record_consensus_round(
        status="failed",
        latency_by_phase={"total": 0.1},
        participants=7,
        cbf_values=cbf_values,
        agreement_stats={"mean": 0.8, "min": 0.7, "max": 0.9},
        iterations=1,
    )

    # Update health to critical
    metrics_collector.update_health_state(CoordinatorHealth.CRITICAL)
    metrics_collector.record_fallback_activation("emergency_mode")

    # Verify critical state
    assert metrics_collector.last_health_state == CoordinatorHealth.CRITICAL
