"""Integration tests for K os safety systems with real behavioral checks."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import numpy as np


class TestSafetyState:
    """Validate SafetyState normalization and aggregate risk."""

    def test_values_clamped_into_valid_range(self) -> None:
        from kagami.core.safety.control_barrier_function import SafetyState

        state = SafetyState(threat_score=1.7, uncertainty=-0.4, complexity=0.2, predictive_risk=2.0)
        assert 0.0 <= state.threat_score <= 1.0
        assert 0.0 <= state.uncertainty <= 1.0
        assert 0.0 <= state.predictive_risk <= 1.0

    def test_risk_level_uses_weighted_average(self) -> None:
        from kagami.core.safety.control_barrier_function import SafetyState

        state = SafetyState(threat_score=0.5, uncertainty=0.0, complexity=0.0, predictive_risk=0.0)
        assert state.risk_level == pytest.approx(0.2)  # 0.5 * weight 0.4


class TestControlBarrierFunction:
    """Exercise CBF calculations directly instead of checking imports."""

    def test_barrier_positive_for_safe_state(self) -> None:
        from kagami.core.safety.control_barrier_function import (
            ControlBarrierFunction,
            SafetyState,
        )

        cbf = ControlBarrierFunction(safety_threshold=0.6)
        safe_state = SafetyState(0.1, 0.1, 0.05, 0.1)
        assert cbf.barrier_function(safe_state) > 0  # type: ignore[operator]

    def test_barrier_negative_for_high_risk_state(self) -> None:
        from kagami.core.safety.control_barrier_function import (
            ControlBarrierFunction,
            SafetyState,
        )

        cbf = ControlBarrierFunction(safety_threshold=0.4)
        unsafe_state = SafetyState(0.9, 0.9, 0.9, 0.9)
        assert cbf.barrier_function(unsafe_state) < 0  # type: ignore[operator]

    def test_class_k_increasing(self) -> None:
        from kagami.core.safety.control_barrier_function import ControlBarrierFunction

        cbf = ControlBarrierFunction()
        assert cbf.class_k_function(0.2) > cbf.class_k_function(0.1)  # type: ignore[operator]

    def test_lie_derivative_shapes(self) -> None:
        from kagami.core.safety.control_barrier_function import (
            ControlBarrierFunction,
            SafetyState,
        )

        cbf = ControlBarrierFunction()
        state = SafetyState(0.2, 0.3, 0.1, 0.4)
        lie_g = cbf.lie_derivative_g(state)  # type: ignore[operator]
        assert isinstance(lie_g, list)
        assert len(lie_g) == 2


class TestCBFInvariantMonteCarlo:
    """Monte Carlo sampling to ensure CBF never returns NaN and h(x) is well-defined."""

    def test_barrier_function_stability(self) -> None:
        from kagami.core.safety.control_barrier_function import (
            ControlBarrierFunction,
            SafetyState,
        )

        cbf = ControlBarrierFunction()
        for _ in range(20):
            state = SafetyState(
                threat_score=np.random.rand(),
                uncertainty=np.random.rand(),
                complexity=np.random.rand(),
                predictive_risk=np.random.rand(),
            )
            h_x = cbf.barrier_function(state)  # type: ignore[operator]
            assert np.isfinite(h_x)


class TestAgentMemoryGuard:
    """Ensure AgentMemoryGuard enforces singleton semantics and registration."""

    def test_memory_guard_singleton_and_registration(self) -> None:
        from kagami.core.safety.agent_memory_guard import (
            AgentMemoryGuard,
            register_agent_memory_limit,
        )

        guard = AgentMemoryGuard.get_instance()
        register_agent_memory_limit("integration-test-agent", soft_limit_gb=0.1, hard_limit_gb=0.2)
        assert "integration-test-agent" in guard.limits


class TestSafetyIntegration:
    """Integration-style smoke tests across safety components."""

    @pytest.mark.asyncio
    async def test_multi_layer_safety_stack_initializes(self) -> None:
        from kagami.core.safety.agent_memory_guard import AgentMemoryGuard
        from kagami.core.safety.control_barrier_function import ControlBarrierFunction, SafetyState

        cbf = ControlBarrierFunction()
        guard = AgentMemoryGuard.get_instance()
        # Use real state to ensure barrier value is computed
        state = SafetyState(0.2, 0.2, 0.1, 0.3)
        assert cbf.barrier_function(state) >= -1.0  # type: ignore[operator]
        assert guard is not None
