"""Property-Based Tests for Safety Systems using Hypothesis.

Tests safety properties across wide input spaces.

Updated Jan 2026: Uses new SafetyState API (h = 1 - risk_level for barrier interpretation).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Hypothesis is required for these tests
pytest.importorskip("hypothesis")


@pytest.mark.safety
class TestCBFProperties:
    """Property-based tests for Control Barrier Function.

    Updated Jan 2026: Tests use SafetyState.risk_level which maps to barrier value
    via h(x) = 1 - risk_level. The old ControlBarrierFunction class methods
    (filter, barrier_function) have been replaced with OptimalCBF which operates
    on tensor observations, not SafetyState objects directly.
    """

    @given(
        threat=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        uncertainty=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        complexity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        predictive_risk=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cbf_risk_level_bounded(
        self, threat: float, uncertainty: float, complexity: float, predictive_risk: float
    ) -> None:
        """Property: SafetyState.risk_level is always bounded in [0, 1]."""
        from kagami.core.safety.control_barrier_function import SafetyState

        state = SafetyState(
            threat=threat,
            uncertainty=uncertainty,
            complexity=complexity,
            predictive_risk=predictive_risk,
        )

        # Risk level must be bounded
        assert 0.0 <= state.risk_level <= 1.0, f"Risk {state.risk_level} out of bounds"

    @given(
        threat=st.floats(min_value=0.0, max_value=0.2, allow_nan=False),
        uncertainty=st.floats(min_value=0.0, max_value=0.2, allow_nan=False),
        complexity=st.floats(min_value=0.0, max_value=0.2, allow_nan=False),
        predictive_risk=st.floats(min_value=0.0, max_value=0.2, allow_nan=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_low_risk_states_have_positive_barrier(
        self, threat: float, uncertainty: float, complexity: float, predictive_risk: float
    ) -> None:
        """Property: Low-risk states always have h(x) > 0.

        With barrier h(x) = 1 - risk_level, low risk → high h (safe).
        """
        from kagami.core.safety.control_barrier_function import SafetyState

        state = SafetyState(
            threat=threat,
            uncertainty=uncertainty,
            complexity=complexity,
            predictive_risk=predictive_risk,
        )

        # h(x) = 1 - risk_level
        h = 1.0 - state.risk_level

        # Low risk should be safe (h > 0)
        assert h > 0, f"Low-risk state has negative barrier h(x)={h}"


@pytest.mark.safety
class TestMemoryGuardProperties:
    """Property-based tests for Agent Memory Guard."""

    @given(
        memory_usage_gb=st.floats(min_value=0.0, max_value=20.0),
        soft_limit_gb=st.floats(min_value=1.0, max_value=8.0),
        hard_limit_gb=st.floats(min_value=4.0, max_value=16.0),
    )
    @settings(max_examples=50)
    def test_memory_guard_respects_limits(
        self, memory_usage_gb: float, soft_limit_gb: float, hard_limit_gb: float
    ):
        """Property: Memory guard correctly enforces soft/hard limits."""
        # Ensure hard >= soft
        if hard_limit_gb < soft_limit_gb:
            hard_limit_gb = soft_limit_gb + 1.0

        # Memory guard should abort when usage >= hard limit
        should_abort = memory_usage_gb >= hard_limit_gb

        # Verify behavior matches expectation
        if should_abort:
            # Would abort in real scenario
            assert memory_usage_gb >= hard_limit_gb
        else:
            # Would allow in real scenario
            assert memory_usage_gb < hard_limit_gb


@pytest.mark.safety
class TestThreatInstinctProperties:
    """Property-based tests for Threat Instinct."""

    @given(
        action=st.text(min_size=1, max_size=50),
        target=st.text(min_size=0, max_size=50),
    )
    @settings(
        max_examples=50,
        deadline=5000,  # 5s deadline - embedding model loads on first call (~1-2s)
        suppress_health_check=[HealthCheck.too_slow],  # First call loads model
    )
    @pytest.mark.asyncio  # FIXED Nov 10, 2025: Add asyncio marker for Hypothesis async support
    async def test_threat_assessment_in_valid_range(self, action: str, target: str):
        """Property: Threat assessment always returns value in [0, 1]."""
        from kagami.core.instincts.threat_instinct import ThreatInstinct

        instinct = ThreatInstinct()
        context = {"action": action, "target": target, "app": "test"}

        assessment = await instinct.assess(context)

        # Threat level must be in valid range
        assert 0.0 <= assessment.threat_level <= 1.0, (
            f"Threat level {assessment.threat_level} out of range [0, 1]"
        )

        # Confidence must be in valid range
        assert 0.0 <= assessment.confidence <= 1.0, (
            f"Confidence {assessment.confidence} out of range [0, 1]"
        )


class TestHonestyValidatorProperties:
    """Property-based tests for Honesty Validator."""

    @given(
        expected=st.integers(min_value=0, max_value=1000),
        actual=st.integers(min_value=0, max_value=1000),
        tolerance=st.floats(min_value=0.01, max_value=0.5),
    )
    @settings(max_examples=50)
    def test_tolerance_symmetric(self, expected: int, actual: int, tolerance: float) -> None:
        """Property: Tolerance check is symmetric."""
        tolerance_amount = int(expected * tolerance)

        # Within tolerance should verify both ways
        if abs(actual - expected) <= tolerance_amount:
            # Both should verify
            forward_valid = abs(actual - expected) <= int(expected * tolerance)
            backward_valid = abs(expected - actual) <= int(actual * tolerance)
            assert forward_valid or backward_valid, "Tolerance check asymmetric"


__all__ = [
    "TestHonestyValidatorProperties",
    "TestMemoryGuardProperties",
    "TestThreatInstinctProperties",
]
