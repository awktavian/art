"""Comprehensive tests for Orb State Machine.

Tests cover:
- Valid state transitions
- Invalid transition rejection
- Safety-critical transitions (emergency_stop)
- Transition listeners
- Strict mode exceptions
- Safety score integration
- Recovery mechanisms
- Edge cases and boundary conditions

Colony: Nexus (e₄) — Testing state synchronization integrity
"""

from __future__ import annotations

import pytest
from kagami.core.orb import (
    InvalidTransitionError,
    OrbActivity,
    OrbStateMachine,
    TransitionResult,
)


class TestOrbStateMachineInitialization:
    """Test state machine initialization."""

    def test_default_initialization(self) -> None:
        """State machine starts in IDLE by default."""
        machine = OrbStateMachine()
        assert machine.current_state == OrbActivity.IDLE
        assert machine.is_idle
        assert not machine.is_active
        assert not machine.is_in_error_state

    def test_custom_initial_state(self) -> None:
        """State machine can start in any valid state."""
        machine = OrbStateMachine(initial_state=OrbActivity.LISTENING)
        assert machine.current_state == OrbActivity.LISTENING
        assert not machine.is_idle
        assert machine.is_active

    def test_strict_mode_initialization(self) -> None:
        """Strict mode can be enabled on initialization."""
        machine = OrbStateMachine(strict_mode=True)
        assert machine.current_state == OrbActivity.IDLE

    def test_empty_transition_history(self) -> None:
        """New state machine has empty transition history."""
        machine = OrbStateMachine()
        assert machine.transition_history == []


class TestValidTransitions:
    """Test valid state transitions."""

    def test_idle_to_listening(self) -> None:
        """IDLE can transition to LISTENING."""
        machine = OrbStateMachine()
        assert machine.can_transition(OrbActivity.LISTENING)
        assert machine.transition(OrbActivity.LISTENING)
        assert machine.current_state == OrbActivity.LISTENING

    def test_listening_to_processing(self) -> None:
        """LISTENING can transition to PROCESSING."""
        machine = OrbStateMachine(initial_state=OrbActivity.LISTENING)
        assert machine.can_transition(OrbActivity.PROCESSING)
        assert machine.transition(OrbActivity.PROCESSING)
        assert machine.current_state == OrbActivity.PROCESSING

    def test_listening_to_idle(self) -> None:
        """LISTENING can transition back to IDLE (cancel/timeout)."""
        machine = OrbStateMachine(initial_state=OrbActivity.LISTENING)
        assert machine.can_transition(OrbActivity.IDLE)
        assert machine.transition(OrbActivity.IDLE)
        assert machine.current_state == OrbActivity.IDLE

    def test_processing_to_responding(self) -> None:
        """PROCESSING can transition to RESPONDING."""
        machine = OrbStateMachine(initial_state=OrbActivity.PROCESSING)
        assert machine.can_transition(OrbActivity.RESPONDING)
        assert machine.transition(OrbActivity.RESPONDING)
        assert machine.current_state == OrbActivity.RESPONDING

    def test_responding_to_idle(self) -> None:
        """RESPONDING can transition to IDLE (completion)."""
        machine = OrbStateMachine(initial_state=OrbActivity.RESPONDING)
        assert machine.can_transition(OrbActivity.IDLE)
        assert machine.transition(OrbActivity.IDLE)
        assert machine.current_state == OrbActivity.IDLE

    def test_portable_to_idle(self) -> None:
        """PORTABLE can transition to IDLE (docked)."""
        machine = OrbStateMachine(initial_state=OrbActivity.PORTABLE)
        assert machine.can_transition(OrbActivity.IDLE)
        assert machine.transition(OrbActivity.IDLE)
        assert machine.current_state == OrbActivity.IDLE

    def test_error_to_idle(self) -> None:
        """ERROR can transition to IDLE (recovery)."""
        machine = OrbStateMachine(initial_state=OrbActivity.ERROR)
        assert machine.can_transition(OrbActivity.IDLE)
        assert machine.transition(OrbActivity.IDLE)
        assert machine.current_state == OrbActivity.IDLE

    def test_safety_alert_to_idle(self) -> None:
        """SAFETY_ALERT can transition to IDLE (recovery)."""
        machine = OrbStateMachine(initial_state=OrbActivity.SAFETY_ALERT)
        assert machine.can_transition(OrbActivity.IDLE)
        assert machine.transition(OrbActivity.IDLE)
        assert machine.current_state == OrbActivity.IDLE

    def test_full_normal_flow(self) -> None:
        """Test complete normal interaction flow."""
        machine = OrbStateMachine()

        # IDLE -> LISTENING -> PROCESSING -> RESPONDING -> IDLE
        assert machine.transition(OrbActivity.LISTENING)
        assert machine.transition(OrbActivity.PROCESSING)
        assert machine.transition(OrbActivity.RESPONDING)
        assert machine.transition(OrbActivity.IDLE)

        assert machine.current_state == OrbActivity.IDLE
        assert len(machine.transition_history) == 4


class TestInvalidTransitions:
    """Test invalid state transitions are rejected."""

    def test_idle_cannot_skip_to_processing(self) -> None:
        """IDLE cannot directly transition to PROCESSING."""
        machine = OrbStateMachine()
        assert not machine.can_transition(OrbActivity.PROCESSING)
        assert not machine.transition(OrbActivity.PROCESSING)
        assert machine.current_state == OrbActivity.IDLE

    def test_idle_cannot_skip_to_responding(self) -> None:
        """IDLE cannot directly transition to RESPONDING."""
        machine = OrbStateMachine()
        assert not machine.can_transition(OrbActivity.RESPONDING)
        assert not machine.transition(OrbActivity.RESPONDING)
        assert machine.current_state == OrbActivity.IDLE

    def test_processing_cannot_go_back_to_listening(self) -> None:
        """PROCESSING cannot go back to LISTENING."""
        machine = OrbStateMachine(initial_state=OrbActivity.PROCESSING)
        assert not machine.can_transition(OrbActivity.LISTENING)
        assert not machine.transition(OrbActivity.LISTENING)
        assert machine.current_state == OrbActivity.PROCESSING

    def test_processing_cannot_go_to_idle_directly(self) -> None:
        """PROCESSING cannot skip to IDLE (must go through RESPONDING)."""
        machine = OrbStateMachine(initial_state=OrbActivity.PROCESSING)
        assert not machine.can_transition(OrbActivity.IDLE)
        assert not machine.transition(OrbActivity.IDLE)
        assert machine.current_state == OrbActivity.PROCESSING

    def test_responding_cannot_go_back_to_processing(self) -> None:
        """RESPONDING cannot go back to PROCESSING."""
        machine = OrbStateMachine(initial_state=OrbActivity.RESPONDING)
        assert not machine.can_transition(OrbActivity.PROCESSING)
        assert not machine.transition(OrbActivity.PROCESSING)
        assert machine.current_state == OrbActivity.RESPONDING

    def test_responding_cannot_go_to_listening(self) -> None:
        """RESPONDING cannot go to LISTENING."""
        machine = OrbStateMachine(initial_state=OrbActivity.RESPONDING)
        assert not machine.can_transition(OrbActivity.LISTENING)
        assert not machine.transition(OrbActivity.LISTENING)
        assert machine.current_state == OrbActivity.RESPONDING


class TestSafetyTransitions:
    """Test safety-critical transitions (ERROR, SAFETY_ALERT)."""

    @pytest.mark.parametrize(
        "initial_state",
        [
            OrbActivity.IDLE,
            OrbActivity.LISTENING,
            OrbActivity.PROCESSING,
            OrbActivity.RESPONDING,
            OrbActivity.PORTABLE,
        ],
    )
    def test_any_state_can_go_to_error(self, initial_state: OrbActivity) -> None:
        """Any non-error state can transition to ERROR."""
        machine = OrbStateMachine(initial_state=initial_state)
        assert machine.can_transition(OrbActivity.ERROR)
        assert machine.transition(OrbActivity.ERROR)
        assert machine.current_state == OrbActivity.ERROR

    @pytest.mark.parametrize(
        "initial_state",
        [
            OrbActivity.IDLE,
            OrbActivity.LISTENING,
            OrbActivity.PROCESSING,
            OrbActivity.RESPONDING,
            OrbActivity.PORTABLE,
        ],
    )
    def test_any_state_can_go_to_safety_alert(self, initial_state: OrbActivity) -> None:
        """Any non-alert state can transition to SAFETY_ALERT."""
        machine = OrbStateMachine(initial_state=initial_state)
        assert machine.can_transition(OrbActivity.SAFETY_ALERT)
        assert machine.transition(OrbActivity.SAFETY_ALERT)
        assert machine.current_state == OrbActivity.SAFETY_ALERT

    def test_error_can_go_to_safety_alert(self) -> None:
        """ERROR can transition to SAFETY_ALERT."""
        machine = OrbStateMachine(initial_state=OrbActivity.ERROR)
        assert machine.can_transition(OrbActivity.SAFETY_ALERT)
        assert machine.transition(OrbActivity.SAFETY_ALERT)
        assert machine.current_state == OrbActivity.SAFETY_ALERT

    def test_safety_alert_can_go_to_error(self) -> None:
        """SAFETY_ALERT can transition to ERROR."""
        machine = OrbStateMachine(initial_state=OrbActivity.SAFETY_ALERT)
        assert machine.can_transition(OrbActivity.ERROR)
        assert machine.transition(OrbActivity.ERROR)
        assert machine.current_state == OrbActivity.ERROR


class TestEmergencyStop:
    """Test emergency_stop functionality."""

    @pytest.mark.parametrize(
        "initial_state",
        list(OrbActivity),
    )
    def test_emergency_stop_from_any_state(self, initial_state: OrbActivity) -> None:
        """emergency_stop works from any state."""
        machine = OrbStateMachine(initial_state=initial_state)
        machine.emergency_stop()
        assert machine.current_state == OrbActivity.SAFETY_ALERT

    def test_emergency_stop_is_forced(self) -> None:
        """emergency_stop bypasses normal validation."""
        # Even from SAFETY_ALERT (which can't normally go to itself)
        machine = OrbStateMachine(initial_state=OrbActivity.SAFETY_ALERT)
        # Manually force to something else first
        machine._current_state = OrbActivity.RESPONDING
        machine.emergency_stop()
        assert machine.current_state == OrbActivity.SAFETY_ALERT


class TestErrorMethod:
    """Test error() method."""

    @pytest.mark.parametrize(
        "initial_state",
        list(OrbActivity),
    )
    def test_error_from_any_state(self, initial_state: OrbActivity) -> None:
        """error() works from any state."""
        machine = OrbStateMachine(initial_state=initial_state)
        machine.error()
        assert machine.current_state == OrbActivity.ERROR

    def test_error_with_reason(self) -> None:
        """error() accepts a reason parameter."""
        machine = OrbStateMachine()
        machine.error("Connection timeout")
        assert machine.current_state == OrbActivity.ERROR


class TestRecovery:
    """Test recovery mechanism."""

    def test_recover_from_error(self) -> None:
        """recover() transitions from ERROR to IDLE."""
        machine = OrbStateMachine(initial_state=OrbActivity.ERROR)
        assert machine.is_in_error_state
        assert machine.recover()
        assert machine.current_state == OrbActivity.IDLE
        assert not machine.is_in_error_state

    def test_recover_from_safety_alert(self) -> None:
        """recover() transitions from SAFETY_ALERT to IDLE."""
        machine = OrbStateMachine(initial_state=OrbActivity.SAFETY_ALERT)
        assert machine.is_in_error_state
        assert machine.recover()
        assert machine.current_state == OrbActivity.IDLE

    def test_recover_from_non_error_state(self) -> None:
        """recover() returns False when not in error state."""
        machine = OrbStateMachine()
        assert not machine.is_in_error_state
        assert not machine.recover()
        assert machine.current_state == OrbActivity.IDLE


class TestReset:
    """Test reset functionality."""

    def test_reset_to_idle(self) -> None:
        """reset() returns to IDLE state."""
        machine = OrbStateMachine(initial_state=OrbActivity.PROCESSING)
        machine.reset()
        assert machine.current_state == OrbActivity.IDLE

    def test_reset_clears_history(self) -> None:
        """reset() clears transition history."""
        machine = OrbStateMachine()
        machine.transition(OrbActivity.LISTENING)
        machine.transition(OrbActivity.PROCESSING)
        assert len(machine.transition_history) == 2

        machine.reset()
        assert machine.transition_history == []


class TestSafetyScoreIntegration:
    """Test safety score checking."""

    def test_safe_score_returns_true(self) -> None:
        """Safe score (>= threshold) returns True."""
        machine = OrbStateMachine()
        assert machine.check_safety(0.8)
        assert machine.check_safety(0.5)  # Exactly at threshold
        assert machine.current_state == OrbActivity.IDLE

    def test_unsafe_score_triggers_alert(self) -> None:
        """Unsafe score (< threshold) triggers SAFETY_ALERT."""
        machine = OrbStateMachine()
        assert not machine.check_safety(0.3)
        assert machine.current_state == OrbActivity.SAFETY_ALERT

    def test_unsafe_score_at_boundary(self) -> None:
        """Score just below threshold triggers alert."""
        machine = OrbStateMachine()
        assert not machine.check_safety(0.49)
        assert machine.current_state == OrbActivity.SAFETY_ALERT

    def test_safety_threshold_value(self) -> None:
        """Safety threshold is 0.5."""
        assert OrbStateMachine.SAFETY_THRESHOLD == 0.5


class TestTransitionListeners:
    """Test transition listener functionality."""

    def test_listener_called_on_transition(self) -> None:
        """Listener is called on successful transition."""
        machine = OrbStateMachine()
        transitions: list[tuple[OrbActivity, OrbActivity]] = []

        def listener(old: OrbActivity, new: OrbActivity) -> None:
            transitions.append((old, new))

        machine.add_listener(listener)
        machine.transition(OrbActivity.LISTENING)

        assert len(transitions) == 1
        assert transitions[0] == (OrbActivity.IDLE, OrbActivity.LISTENING)

    def test_listener_not_called_on_invalid_transition(self) -> None:
        """Listener is not called when transition fails."""
        machine = OrbStateMachine()
        transitions: list[tuple[OrbActivity, OrbActivity]] = []

        def listener(old: OrbActivity, new: OrbActivity) -> None:
            transitions.append((old, new))

        machine.add_listener(listener)
        machine.transition(OrbActivity.PROCESSING)  # Invalid from IDLE

        assert len(transitions) == 0

    def test_multiple_listeners(self) -> None:
        """Multiple listeners all receive notifications."""
        machine = OrbStateMachine()
        results1: list[OrbActivity] = []
        results2: list[OrbActivity] = []

        machine.add_listener(lambda o, n: results1.append(n))
        machine.add_listener(lambda o, n: results2.append(n))

        machine.transition(OrbActivity.LISTENING)

        assert results1 == [OrbActivity.LISTENING]
        assert results2 == [OrbActivity.LISTENING]

    def test_remove_listener(self) -> None:
        """Removed listener no longer receives notifications."""
        machine = OrbStateMachine()
        results: list[OrbActivity] = []

        def listener(old: OrbActivity, new: OrbActivity) -> None:
            results.append(new)

        machine.add_listener(listener)
        machine.transition(OrbActivity.LISTENING)
        assert len(results) == 1

        assert machine.remove_listener(listener)
        machine.transition(OrbActivity.PROCESSING)
        assert len(results) == 1  # No new notification

    def test_remove_nonexistent_listener(self) -> None:
        """Removing nonexistent listener returns False."""
        machine = OrbStateMachine()
        assert not machine.remove_listener(lambda o, n: None)

    def test_listener_exception_doesnt_break_machine(self) -> None:
        """Exception in listener doesn't break state machine."""
        machine = OrbStateMachine()

        def bad_listener(old: OrbActivity, new: OrbActivity) -> None:
            raise ValueError("Listener error")

        results: list[OrbActivity] = []

        def good_listener(old: OrbActivity, new: OrbActivity) -> None:
            results.append(new)

        machine.add_listener(bad_listener)
        machine.add_listener(good_listener)

        # Should complete despite exception
        machine.transition(OrbActivity.LISTENING)
        assert machine.current_state == OrbActivity.LISTENING
        assert results == [OrbActivity.LISTENING]


class TestStrictMode:
    """Test strict mode behavior."""

    def test_strict_mode_raises_on_invalid_transition(self) -> None:
        """Strict mode raises InvalidTransitionError on invalid transition."""
        machine = OrbStateMachine(strict_mode=True)

        with pytest.raises(InvalidTransitionError) as exc_info:
            machine.transition(OrbActivity.PROCESSING)

        assert exc_info.value.from_state == OrbActivity.IDLE
        assert exc_info.value.to_state == OrbActivity.PROCESSING
        assert OrbActivity.LISTENING in exc_info.value.valid_targets

    def test_strict_mode_valid_transition_succeeds(self) -> None:
        """Strict mode allows valid transitions."""
        machine = OrbStateMachine(strict_mode=True)
        machine.transition(OrbActivity.LISTENING)
        assert machine.current_state == OrbActivity.LISTENING

    def test_strict_mode_force_bypasses_exception(self) -> None:
        """Force parameter bypasses strict mode exception."""
        machine = OrbStateMachine(strict_mode=True)
        machine.transition(OrbActivity.PROCESSING, force=True)
        assert machine.current_state == OrbActivity.PROCESSING


class TestForceTransition:
    """Test forced transitions."""

    def test_force_allows_invalid_transition(self) -> None:
        """Force parameter allows normally invalid transitions."""
        machine = OrbStateMachine()
        assert machine.transition(OrbActivity.RESPONDING, force=True)
        assert machine.current_state == OrbActivity.RESPONDING

    def test_force_with_valid_transition(self) -> None:
        """Force works with already valid transitions too."""
        machine = OrbStateMachine()
        assert machine.transition(OrbActivity.LISTENING, force=True)
        assert machine.current_state == OrbActivity.LISTENING


class TestTransitionWithResult:
    """Test transition_with_result method."""

    def test_successful_transition_result(self) -> None:
        """Successful transition returns TransitionResult with success=True."""
        machine = OrbStateMachine()
        result = machine.transition_with_result(OrbActivity.LISTENING)

        assert result.success
        assert result.from_state == OrbActivity.IDLE
        assert result.to_state == OrbActivity.LISTENING
        assert result.reason is None

    def test_failed_transition_result(self) -> None:
        """Failed transition returns TransitionResult with details."""
        machine = OrbStateMachine()
        result = machine.transition_with_result(OrbActivity.PROCESSING)

        assert not result.success
        assert result.from_state == OrbActivity.IDLE
        assert result.to_state == OrbActivity.PROCESSING
        assert "Invalid transition" in result.reason

    def test_transition_result_boolean_conversion(self) -> None:
        """TransitionResult converts to boolean correctly."""
        machine = OrbStateMachine()

        success_result = machine.transition_with_result(OrbActivity.LISTENING)
        assert bool(success_result) is True

        fail_result = machine.transition_with_result(OrbActivity.RESPONDING)
        assert bool(fail_result) is False


class TestTransitionHistory:
    """Test transition history tracking."""

    def test_history_records_transitions(self) -> None:
        """History records all successful transitions."""
        machine = OrbStateMachine()
        machine.transition(OrbActivity.LISTENING)
        machine.transition(OrbActivity.PROCESSING)

        history = machine.transition_history
        assert len(history) == 2
        assert history[0][0] == OrbActivity.IDLE
        assert history[0][1] == OrbActivity.LISTENING
        assert history[1][0] == OrbActivity.LISTENING
        assert history[1][1] == OrbActivity.PROCESSING

    def test_history_includes_timestamp(self) -> None:
        """Each history entry includes a timestamp."""
        import time

        machine = OrbStateMachine()
        before = time.time()
        machine.transition(OrbActivity.LISTENING)
        after = time.time()

        history = machine.transition_history
        assert len(history) == 1
        assert before <= history[0][2] <= after

    def test_history_not_recorded_for_failed_transitions(self) -> None:
        """Failed transitions are not recorded in history."""
        machine = OrbStateMachine()
        machine.transition(OrbActivity.PROCESSING)  # Invalid

        assert machine.transition_history == []

    def test_history_bounded_at_100(self) -> None:
        """History is bounded at 100 entries."""
        machine = OrbStateMachine()

        # Create many transitions
        for _ in range(60):
            machine.transition(OrbActivity.LISTENING)
            machine.transition(OrbActivity.IDLE)

        # Should have at most 100 entries
        assert len(machine.transition_history) <= 100

    def test_history_is_copy(self) -> None:
        """transition_history returns a copy, not the original."""
        machine = OrbStateMachine()
        machine.transition(OrbActivity.LISTENING)

        history = machine.transition_history
        history.clear()

        # Original should be unchanged
        assert len(machine.transition_history) == 1


class TestGetValidTransitions:
    """Test get_valid_transitions method."""

    def test_valid_transitions_from_idle(self) -> None:
        """IDLE has correct valid transitions."""
        machine = OrbStateMachine()
        valid = machine.get_valid_transitions()

        assert OrbActivity.LISTENING in valid
        assert OrbActivity.ERROR in valid
        assert OrbActivity.SAFETY_ALERT in valid
        assert OrbActivity.PROCESSING not in valid
        assert OrbActivity.RESPONDING not in valid

    def test_valid_transitions_from_processing(self) -> None:
        """PROCESSING has correct valid transitions."""
        machine = OrbStateMachine(initial_state=OrbActivity.PROCESSING)
        valid = machine.get_valid_transitions()

        assert OrbActivity.RESPONDING in valid
        assert OrbActivity.ERROR in valid
        assert OrbActivity.SAFETY_ALERT in valid
        assert OrbActivity.IDLE not in valid
        assert OrbActivity.LISTENING not in valid

    def test_valid_transitions_returns_copy(self) -> None:
        """get_valid_transitions returns a copy."""
        machine = OrbStateMachine()
        valid = machine.get_valid_transitions()
        valid.add(OrbActivity.RESPONDING)

        # Original should be unchanged
        assert OrbActivity.RESPONDING not in machine.get_valid_transitions()


class TestPropertyFlags:
    """Test convenience property flags."""

    def test_is_idle(self) -> None:
        """is_idle correctly reports IDLE state."""
        machine = OrbStateMachine()
        assert machine.is_idle

        machine.transition(OrbActivity.LISTENING)
        assert not machine.is_idle

    def test_is_active(self) -> None:
        """is_active correctly reports active states."""
        machine = OrbStateMachine()
        assert not machine.is_active

        machine.transition(OrbActivity.LISTENING)
        assert machine.is_active

        machine.transition(OrbActivity.PROCESSING)
        assert machine.is_active

        machine.transition(OrbActivity.RESPONDING)
        assert machine.is_active

        machine.transition(OrbActivity.IDLE)
        assert not machine.is_active

    def test_is_in_error_state(self) -> None:
        """is_in_error_state correctly reports error states."""
        machine = OrbStateMachine()
        assert not machine.is_in_error_state

        machine.transition(OrbActivity.ERROR)
        assert machine.is_in_error_state

        machine.transition(OrbActivity.SAFETY_ALERT)
        assert machine.is_in_error_state

        machine.transition(OrbActivity.IDLE)
        assert not machine.is_in_error_state


class TestRepr:
    """Test string representation."""

    def test_repr_format(self) -> None:
        """__repr__ provides useful info."""
        machine = OrbStateMachine()
        repr_str = repr(machine)

        assert "OrbStateMachine" in repr_str
        assert "idle" in repr_str
        assert "history_len=0" in repr_str

    def test_repr_with_history(self) -> None:
        """__repr__ shows correct history length."""
        machine = OrbStateMachine()
        machine.transition(OrbActivity.LISTENING)
        machine.transition(OrbActivity.PROCESSING)

        repr_str = repr(machine)
        assert "processing" in repr_str
        assert "history_len=2" in repr_str


class TestIntegrationWithOrbState:
    """Test integration scenarios with OrbState."""

    def test_state_machine_with_orb_state(self) -> None:
        """State machine works alongside OrbState."""
        from kagami.core.orb import OrbState, create_orb_state

        machine = OrbStateMachine()

        # Simulate interaction flow
        machine.transition(OrbActivity.LISTENING)
        state = create_orb_state(
            activity=machine.current_state,
            active_colony="flow",
        )
        assert state.activity == OrbActivity.LISTENING

        machine.transition(OrbActivity.PROCESSING)
        state = create_orb_state(
            activity=machine.current_state,
            active_colony="forge",
        )
        assert state.activity == OrbActivity.PROCESSING

    def test_safety_integration(self) -> None:
        """Safety score triggers proper state transitions."""
        from kagami.core.orb import create_orb_state

        machine = OrbStateMachine()
        machine.transition(OrbActivity.LISTENING)

        # Simulate safety violation
        safety_score = 0.3
        if not machine.check_safety(safety_score):
            state = create_orb_state(
                activity=machine.current_state,
                safety_score=safety_score,
            )
            assert state.activity == OrbActivity.SAFETY_ALERT
            assert not state.is_safe
