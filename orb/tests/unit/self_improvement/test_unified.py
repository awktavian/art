"""Tests for Recursive Self-Improvement system.

Tests the self-improvement interface defined in kagami/core/self_improvement/unified.py.
This system enables Kagami to modify its own code for performance improvement.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


from kagami.core.self_improvement.unified import (
    ImprovementProposal,
    ImprovementResult,
    RecursiveSelfImprover,
)


class TestImprovementProposal:
    """Test ImprovementProposal dataclass."""

    def test_proposal_creation(self) -> None:
        """ImprovementProposal should store all fields correctly."""
        proposal = ImprovementProposal(
            file_path="kagami/core/example.py",
            current_code_snippet="def slow():\n    pass",
            proposed_code_snippet="def fast():\n    pass",
            rationale="Renamed for clarity",
            expected_improvement=5.0,
            risk_level="low",
            requires_approval=False,
            metrics_to_track=["latency_ms", "memory_mb"],
        )

        assert proposal.file_path == "kagami/core/example.py"
        assert "slow" in proposal.current_code_snippet
        assert "fast" in proposal.proposed_code_snippet
        assert proposal.rationale == "Renamed for clarity"
        assert proposal.expected_improvement == 5.0
        assert proposal.risk_level == "low"
        assert proposal.requires_approval is False
        assert "latency_ms" in proposal.metrics_to_track

    def test_proposal_high_risk(self) -> None:
        """High risk proposals should require approval."""
        proposal = ImprovementProposal(
            file_path="kagami/core/safety/cbf.py",
            current_code_snippet="# original",
            proposed_code_snippet="# modified",
            rationale="Critical path optimization",
            expected_improvement=20.0,
            risk_level="high",
            requires_approval=True,
            metrics_to_track=["safety_h_x"],
        )

        assert proposal.risk_level == "high"
        assert proposal.requires_approval is True


class TestImprovementResult:
    """Test ImprovementResult dataclass."""

    def test_successful_result(self) -> None:
        """Successful improvement result should capture metrics."""
        proposal = ImprovementProposal(
            file_path="test.py",
            current_code_snippet="old",
            proposed_code_snippet="new",
            rationale="test",
            expected_improvement=10.0,
            risk_level="low",
            requires_approval=False,
            metrics_to_track=["latency_ms"],
        )

        result = ImprovementResult(
            success=True,
            improvement_percent=12.5,
            proposal=proposal,
            metrics_before={"latency_ms": 100.0},
            metrics_after={"latency_ms": 87.5},
        )

        assert result.success is True
        assert result.improvement_percent == 12.5
        assert result.metrics_before["latency_ms"] == 100.0
        assert result.metrics_after["latency_ms"] == 87.5
        assert result.rollback_performed is False
        assert result.error is None

    def test_failed_result_with_rollback(self) -> None:
        """Failed result should track rollback and error."""
        proposal = ImprovementProposal(
            file_path="test.py",
            current_code_snippet="old",
            proposed_code_snippet="buggy",
            rationale="test",
            expected_improvement=10.0,
            risk_level="medium",
            requires_approval=False,
            metrics_to_track=["latency_ms"],
        )

        result = ImprovementResult(
            success=False,
            improvement_percent=-20.0,  # Degradation
            proposal=proposal,
            metrics_before={"latency_ms": 100.0},
            metrics_after={"latency_ms": 120.0},
            rollback_performed=True,
            error="Performance regression detected",
        )

        assert result.success is False
        assert result.improvement_percent == -20.0
        assert result.rollback_performed is True
        assert result.error == "Performance regression detected"


class TestRecursiveSelfImprover:
    """Test RecursiveSelfImprover interface."""

    @pytest.fixture
    def improver(self) -> Any:
        """Create a self-improver instance."""
        return RecursiveSelfImprover()

    def test_initialization_state(self, improver) -> Any:
        """Improver should start uninitialized."""
        assert improver._initialized is False
        assert improver._improvement_log is None
        assert improver._self_healing is None

    def test_resource_limits_aggressive(self, improver) -> None:
        """Resource limits should be set (AGGRESSIVE mode)."""
        assert improver._max_modifications_per_day == 50
        assert improver._max_modifications_per_hour == 10
        assert improver._max_tokens_per_day == 500_000
        assert improver._max_cpu_percent == 70

    def test_usage_tracking_starts_zero(self, improver) -> None:
        """Usage tracking should start at zero."""
        assert improver._modifications_today == 0
        assert improver._modifications_this_hour == 0
        assert improver._tokens_used_today == 0
        assert improver._total_modifications_applied == 0

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, improver: Any) -> None:
        """Initialize should be idempotent (safe to call multiple times)."""
        await improver.initialize()
        assert improver._initialized is True

        # Second call should not error
        await improver.initialize()
        assert improver._initialized is True

    def test_has_required_methods(self, improver) -> None:
        """Improver should have required interface methods."""
        assert hasattr(improver, "initialize")
        assert callable(improver.initialize)


class TestResourceLimits:
    """Test that resource limits are reasonable."""

    def test_hourly_limit_less_than_daily(self) -> None:
        """Hourly limit should be less than daily limit."""
        improver = RecursiveSelfImprover()
        assert improver._max_modifications_per_hour < improver._max_modifications_per_day

    def test_cpu_limit_below_100(self) -> None:
        """CPU limit should be below 100%."""
        improver = RecursiveSelfImprover()
        assert improver._max_cpu_percent < 100
        assert improver._max_cpu_percent > 0
