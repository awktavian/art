"""Tests for Phase Transition Detector.

Validates phase detection, boundary crossing, and Fano line analysis
based on Nov 2025 research on multi-agent coordination phases.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import numpy as np

from kagami.core.unified_agents.phase_detector import (
    PhaseTransitionDetector,
    CoordinationPhase,
    PhaseTransitionEvent,
    FanoLineMetrics,
    create_phase_detector,
    COORDINATED_CSR_THRESHOLD,
    JAMMED_CSR_THRESHOLD,
)


class TestPhaseTransitionDetector:
    """Test phase transition detector."""

    def test_initialization(self) -> None:
        """Test detector initialization."""
        detector = PhaseTransitionDetector(window_size=50)

        assert detector.window_size == 50
        assert detector.current_phase == CoordinationPhase.UNKNOWN
        assert len(detector.csr_history) == 0
        assert len(detector.td_variance_history) == 0
        assert detector.phase_transition_count == 0
        assert len(detector.fano_line_metrics) == 7  # 7 Fano lines

    def test_factory(self) -> None:
        """Test factory function."""
        detector = create_phase_detector(window_size=100)
        assert isinstance(detector, PhaseTransitionDetector)
        assert detector.window_size == 100

    def test_update_single_task(self) -> None:
        """Test updating with single task result."""
        detector = PhaseTransitionDetector(window_size=10)

        # Simulate successful task
        td_errors = {0: 0.1, 1: 0.2, 2: 0.15}
        detector.update(task_success=True, td_errors=td_errors)

        assert len(detector.csr_history) == 1
        assert len(detector.td_variance_history) == 1
        assert detector.csr_history[0] == 1.0
        assert detector.total_updates == 1

    def test_coordinated_phase_detection(self) -> None:
        """Test detection of coordinated phase (high CSR, low variance)."""
        detector = PhaseTransitionDetector(window_size=100)

        # Simulate 30 successful tasks with low TD variance
        for _ in range(30):
            td_errors = {i: np.random.uniform(0.0, 0.2) for i in range(7)}
            detector.update(task_success=True, td_errors=td_errors)

        phase = detector.detect_phase()
        assert phase == CoordinationPhase.COORDINATED

        stats = detector.get_stats()
        assert stats["csr"] > COORDINATED_CSR_THRESHOLD
        assert stats["current_phase"] == "coordinated"

    def test_jammed_phase_detection(self) -> None:
        """Test detection of jammed phase (low CSR, high variance)."""
        detector = PhaseTransitionDetector(window_size=100)

        # Simulate 30 failed tasks with high TD variance
        for _ in range(30):
            td_errors = {i: np.random.uniform(0.8, 1.5) for i in range(7)}
            detector.update(task_success=False, td_errors=td_errors)

        phase = detector.detect_phase()
        assert phase == CoordinationPhase.JAMMED

        stats = detector.get_stats()
        assert stats["csr"] < JAMMED_CSR_THRESHOLD
        assert stats["current_phase"] == "jammed"

    def test_transition_phase_detection(self) -> None:
        """Test detection of transition phase (intermediate CSR/variance)."""
        detector = PhaseTransitionDetector(window_size=100)

        # Simulate mixed success/failure with moderate variance
        for i in range(30):
            success = i % 2 == 0  # 50% success rate
            td_errors = {j: np.random.uniform(0.3, 0.7) for j in range(7)}
            detector.update(task_success=success, td_errors=td_errors)

        phase = detector.detect_phase()
        assert phase == CoordinationPhase.TRANSITION

        stats = detector.get_stats()
        assert JAMMED_CSR_THRESHOLD < stats["csr"] < COORDINATED_CSR_THRESHOLD
        assert stats["current_phase"] == "transition"

    def test_phase_transition_detection(self) -> None:
        """Test phase boundary crossing detection."""
        detector = PhaseTransitionDetector(window_size=50)

        # Start in coordinated phase
        for _ in range(25):
            td_errors = dict.fromkeys(range(7), 0.1)
            detector.update(task_success=True, td_errors=td_errors)

        assert detector.detect_phase() == CoordinationPhase.COORDINATED

        # Force phase to update
        detector.current_phase = CoordinationPhase.COORDINATED

        # Transition to jammed phase - need more failures to get CSR < 0.3
        # 25 successes + 60 failures = 25/85 = 0.29 CSR < 0.3 threshold
        for _ in range(60):
            td_errors = {i: np.random.uniform(0.8, 1.2) for i in range(7)}
            detector.update(task_success=False, td_errors=td_errors)

        event = detector.phase_changed()
        assert event is not None
        assert isinstance(event, PhaseTransitionEvent)
        assert event.old_phase == CoordinationPhase.COORDINATED
        assert event.new_phase == CoordinationPhase.JAMMED
        assert detector.phase_transition_count == 1

    def test_no_phase_change_on_same_phase(self) -> None:
        """Test that no event is emitted when phase stays the same."""
        detector = PhaseTransitionDetector(window_size=50)

        # Establish coordinated phase
        for _ in range(30):
            td_errors = dict.fromkeys(range(7), 0.1)
            detector.update(task_success=True, td_errors=td_errors)

        detector.current_phase = CoordinationPhase.COORDINATED

        # Continue coordinated behavior
        for _ in range(10):
            td_errors = dict.fromkeys(range(7), 0.1)
            detector.update(task_success=True, td_errors=td_errors)

        event = detector.phase_changed()
        assert event is None  # No transition

    def test_fano_line_tracking(self) -> None:
        """Test Fano line success tracking."""
        detector = PhaseTransitionDetector(window_size=50)

        # Update with Fano line 0
        for i in range(10):
            success = i % 2 == 0  # 50% success
            detector.update(task_success=success, td_errors={0: 0.5}, fano_line_idx=0)

        line_0 = detector.fano_line_metrics[0]
        assert line_0.total_tasks == 10
        assert line_0.success_count == 5
        assert line_0.failure_count == 5
        assert abs(line_0.csr - 0.5) < 0.01  # type: ignore[operator]

    def test_fano_line_summary(self) -> None:
        """Test Fano line summary generation."""
        detector = PhaseTransitionDetector(window_size=50)

        # Create varying success rates across lines
        for line_idx in range(7):
            success_rate = (line_idx + 1) / 7.0  # 0.14, 0.28, ..., 1.0
            num_tasks = 10
            for i in range(num_tasks):
                success = i < int(num_tasks * success_rate)
                detector.update(task_success=success, td_errors={0: 0.3}, fano_line_idx=line_idx)

        summary = detector.get_fano_line_summary()
        assert "fano_lines" in summary
        assert len(summary["fano_lines"]) == 7

        # Check sorting (worst first)
        worst = summary["worst_line"]
        best = summary["best_line"]
        assert worst is not None
        assert best is not None
        assert worst["csr"] < best["csr"]

    def test_failing_fano_lines(self) -> None:
        """Test identification of failing Fano lines."""
        detector = PhaseTransitionDetector(window_size=50)

        # Line 0: 20% success (failing)
        for i in range(10):
            detector.update(task_success=(i < 2), td_errors={0: 0.5}, fano_line_idx=0)

        # Line 1: 80% success (good)
        for i in range(10):
            detector.update(task_success=(i < 8), td_errors={0: 0.2}, fano_line_idx=1)

        failing = detector.get_failing_fano_lines(threshold=0.4)
        assert 0 in failing  # Line 0 should be flagged
        assert 1 not in failing  # Line 1 should not be flagged

    def test_coupling_adjustment_suggestion(self) -> None:
        """Test coupling strength adjustment based on phase."""
        detector = PhaseTransitionDetector(window_size=50)

        # Coordinated phase → decrease coupling
        for _ in range(30):
            detector.update(task_success=True, td_errors=dict.fromkeys(range(7), 0.1))

        detector.current_phase = CoordinationPhase.COORDINATED
        adjustment = detector.suggest_coupling_adjustment()
        assert adjustment < 1.0  # Should decrease

        # Jammed phase → increase coupling
        detector.reset()
        for _ in range(30):
            detector.update(task_success=False, td_errors=dict.fromkeys(range(7), 1.2))

        detector.current_phase = CoordinationPhase.JAMMED
        adjustment = detector.suggest_coupling_adjustment()
        assert adjustment > 1.0  # Should increase

        # Transition phase → maintain coupling
        detector.current_phase = CoordinationPhase.TRANSITION
        adjustment = detector.suggest_coupling_adjustment()
        assert adjustment == 1.0  # No change

    def test_insufficient_data_returns_unknown(self) -> None:
        """Test that detector returns UNKNOWN with insufficient data."""
        detector = PhaseTransitionDetector(window_size=100)

        # Only 10 samples (< 20 minimum)
        for _ in range(10):
            detector.update(task_success=True, td_errors={0: 0.1})

        phase = detector.detect_phase()
        assert phase == CoordinationPhase.UNKNOWN

    def test_window_size_limit(self) -> None:
        """Test that history respects window size."""
        detector = PhaseTransitionDetector(window_size=10)

        # Add 20 updates
        for _i in range(20):
            detector.update(task_success=True, td_errors={0: 0.1})

        # Only last 10 should be kept
        assert len(detector.csr_history) == 10
        assert len(detector.td_variance_history) == 10

    def test_stats_output(self) -> None:
        """Test statistics output structure."""
        detector = PhaseTransitionDetector(window_size=50)

        # Add some data
        for _ in range(30):
            detector.update(task_success=True, td_errors=dict.fromkeys(range(7), 0.1))

        stats = detector.get_stats()
        assert "current_phase" in stats
        assert "csr" in stats
        assert "td_variance" in stats
        assert "phase_transition_count" in stats
        assert "fano_line_summary" in stats
        assert "suggested_coupling_adjustment" in stats
        assert stats["total_updates"] == 30

    def test_reset(self) -> None:
        """Test detector reset."""
        detector = PhaseTransitionDetector(window_size=50)

        # Add data
        for _ in range(30):
            detector.update(task_success=True, td_errors={0: 0.1})

        detector.current_phase = CoordinationPhase.COORDINATED

        # Reset
        detector.reset()

        assert len(detector.csr_history) == 0
        assert len(detector.td_variance_history) == 0
        assert detector.current_phase == CoordinationPhase.UNKNOWN

    def test_phase_transition_event_serialization(self) -> None:
        """Test PhaseTransitionEvent to_dict."""
        event = PhaseTransitionEvent(
            timestamp=1234.5,
            old_phase=CoordinationPhase.COORDINATED,
            new_phase=CoordinationPhase.JAMMED,
            csr=0.25,
            td_variance=1.2,
            window_size=100,
            metadata={"test": "data"},
        )

        event_dict = event.to_dict()
        assert event_dict["timestamp"] == 1234.5
        assert event_dict["old_phase"] == "coordinated"
        assert event_dict["new_phase"] == "jammed"
        assert event_dict["csr"] == 0.25
        assert event_dict["td_variance"] == 1.2
        assert event_dict["metadata"]["test"] == "data"

    def test_fano_line_metrics_colony_names(self) -> None:
        """Test FanoLineMetrics colony name extraction."""
        from kagami_math.fano_plane import get_fano_lines_zero_indexed

        fano_lines = get_fano_lines_zero_indexed()
        metrics = FanoLineMetrics(line_idx=0, colonies=fano_lines[0])

        colony_names = metrics.colony_names
        assert len(colony_names) == 3
        assert all(isinstance(name, str) for name in colony_names)

    def test_td_variance_computation(self) -> None:
        """Test TD-error variance computation."""
        detector = PhaseTransitionDetector(window_size=50)

        # High variance TD errors
        high_var_errors = {0: 0.1, 1: 1.5, 2: 0.2}  # Variance ~ 0.44
        detector.update(task_success=True, td_errors=high_var_errors)

        # Low variance TD errors
        low_var_errors = {0: 0.5, 1: 0.52, 2: 0.48}  # Variance ~ 0.0004
        detector.update(task_success=True, td_errors=low_var_errors)

        assert detector.td_variance_history[0] > detector.td_variance_history[1]

    def test_multiple_phase_transitions(self) -> None:
        """Test multiple phase transitions are counted correctly."""
        detector = PhaseTransitionDetector(window_size=30)

        # Coordinated → Transition
        for _ in range(25):
            detector.update(task_success=True, td_errors=dict.fromkeys(range(7), 0.1))
        detector.current_phase = CoordinationPhase.COORDINATED

        for _ in range(20):
            success = _ % 2 == 0
            detector.update(task_success=success, td_errors=dict.fromkeys(range(7), 0.5))

        event1 = detector.phase_changed()
        assert event1 is not None

        # Transition → Jammed
        for _ in range(20):
            detector.update(task_success=False, td_errors=dict.fromkeys(range(7), 1.2))

        event2 = detector.phase_changed()
        assert event2 is not None

        assert detector.phase_transition_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
