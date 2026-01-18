"""Tests for Chaos Safety Monitor.

Tests OGY control, CBF integration, and safe state finding.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import numpy as np

from kagami.core.safety.chaos_safety import ChaosSafetyMonitor


class TestChaosSafetyMonitor:
    """Test chaos safety monitoring."""

    def test_initialization(self) -> None:
        """Test monitor initialization."""
        monitor = ChaosSafetyMonitor()
        assert monitor.safety_margin == 0.1
        assert monitor.intervention_threshold == 0.05
        assert monitor.interventions == 0
        assert monitor.violations_prevented == 0

    def test_check_chaos_safety_no_cbf(self) -> None:
        """Test safety check without CBF function."""
        monitor = ChaosSafetyMonitor()
        state = np.array([1.0, 2.0, 3.0])

        result = monitor.check_chaos_safety(state, cbf_function=None)

        assert result.safe is True
        assert result.cbf_value is None
        assert result.intervention_needed is False

    def test_check_chaos_safety_with_cbf(self) -> None:
        """Test safety check with CBF function."""
        monitor = ChaosSafetyMonitor()

        def cbf_function(state: np.ndarray) -> float:
            # Simple CBF: h(x) = 1.0 - ||x||
            return 1.0 - np.linalg.norm(state)

        # Safe state (norm < 1.0)
        safe_state = np.array([0.1, 0.2, 0.3])
        result = monitor.check_chaos_safety(safe_state, cbf_function)
        assert result.safe is True
        assert result.cbf_value is not None and result.cbf_value > 0.0

        # Unsafe state (norm > 1.0)
        unsafe_state = np.array([1.0, 1.0, 1.0])
        result = monitor.check_chaos_safety(unsafe_state, cbf_function)
        assert result.safe is False
        assert result.cbf_value is not None and result.cbf_value < 0.0

    def test_stabilize_chaos_with_target(self) -> None:
        """Test chaos stabilization with target state."""
        monitor = ChaosSafetyMonitor()
        chaotic_state = np.array([2.0, 3.0, 4.0])
        target_state = np.array([1.0, 1.0, 1.0])

        stabilized = monitor.stabilize_chaos(chaotic_state, target_state=target_state, gain=0.5)

        # Should move toward target
        assert np.linalg.norm(stabilized - target_state) < np.linalg.norm(
            chaotic_state - target_state
        )

    def test_stabilize_chaos_with_cbf(self) -> None:
        """Test chaos stabilization with CBF."""
        monitor = ChaosSafetyMonitor()

        def cbf_function(state: np.ndarray) -> float:
            # CBF: h(x) = 1.0 - ||x||
            return 1.0 - np.linalg.norm(state)

        chaotic_state = np.array([2.0, 2.0, 2.0])  # Unsafe (norm > 1.0)

        stabilized = monitor.stabilize_chaos(chaotic_state, cbf_function=cbf_function, gain=0.1)

        # Should be safer (closer to origin)
        assert np.linalg.norm(stabilized) <= np.linalg.norm(chaotic_state)

    def test_find_safe_state(self) -> None:
        """Test finding safe state via CBF."""
        monitor = ChaosSafetyMonitor()

        def cbf_function(state: np.ndarray) -> float:
            # CBF: h(x) = 1.0 - ||x||
            return 1.0 - np.linalg.norm(state)

        unsafe_state = np.array([2.0, 2.0, 2.0])

        safe_state = monitor._find_safe_state(unsafe_state, cbf_function)

        # Should satisfy CBF
        h_x = cbf_function(safe_state)
        assert h_x >= 0.0

    def test_get_safety_metrics(self) -> None:
        """Test getting safety metrics."""
        monitor = ChaosSafetyMonitor()
        monitor.interventions = 10
        monitor.violations_prevented = 5

        metrics = monitor.get_safety_metrics()

        assert metrics.total_interventions == 10
        assert metrics.violations_prevented == 5
        assert metrics.intervention_rate >= 0.0
