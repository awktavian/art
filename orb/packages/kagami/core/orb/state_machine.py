"""Orb State Machine - Enforces valid state transitions with h(x) >= 0 safety.

This module provides a finite state machine for the Orb, ensuring that
only valid state transitions occur. Invalid transitions are rejected,
maintaining system integrity and safety guarantees.

The state machine is server-authoritative and integrates with the
existing OrbState model for consistent cross-client synchronization.

Colony: Nexus (e₄) — State synchronization and safety enforcement

Example:
    >>> from kagami.core.orb import OrbStateMachine, OrbActivity
    >>> machine = OrbStateMachine()
    >>> machine.transition(OrbActivity.LISTENING)
    True
    >>> machine.current_state
    <OrbActivity.LISTENING: 'listening'>
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kagami.core.orb.state import OrbActivity

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

logger = logging.getLogger(__name__)

# Type alias for transition listeners
TransitionListener = Callable[[OrbActivity, OrbActivity], None]


@dataclass
class TransitionResult:
    """Result of a state transition attempt.

    Attributes:
        success: Whether the transition succeeded
        from_state: The state before transition
        to_state: The target state (actual state after if successful)
        reason: Explanation if transition failed
    """

    success: bool
    from_state: OrbActivity
    to_state: OrbActivity
    reason: str | None = None

    def __bool__(self) -> bool:
        """Allow using result directly in boolean context."""
        return self.success


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        from_state: OrbActivity,
        to_state: OrbActivity,
        valid_targets: AbstractSet[OrbActivity],
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.valid_targets = valid_targets
        valid_str = ", ".join(s.value for s in valid_targets)
        super().__init__(
            f"Invalid transition: {from_state.value} → {to_state.value}. "
            f"Valid targets: [{valid_str}]"
        )


class OrbStateMachine:
    """Enforces valid state transitions for the Orb.

    The state machine ensures consistent Orb behavior across all clients
    by validating transitions before they occur. Safety-critical transitions
    (to ERROR or SAFETY_ALERT) are always allowed from any state.

    Valid transitions:
        IDLE → LISTENING (user interaction begins)
        LISTENING → PROCESSING (voice/input detected)
        LISTENING → IDLE (user cancelled/timeout)
        PROCESSING → RESPONDING (execution begins)
        RESPONDING → IDLE (complete)

        Any → ERROR (system error)
        Any → SAFETY_ALERT (h(x) < threshold)
        ERROR → IDLE (recovery)
        SAFETY_ALERT → IDLE (recovery)
        SAFETY_ALERT → ERROR (error during alert)
        ERROR → SAFETY_ALERT (safety issue during error)

        PORTABLE → IDLE (hardware docked)

    Attributes:
        current_state: The current OrbActivity state
        transition_history: List of (from, to, timestamp) tuples

    Example:
        >>> machine = OrbStateMachine()
        >>> machine.can_transition(OrbActivity.LISTENING)
        True
        >>> machine.transition(OrbActivity.LISTENING)
        True
        >>> machine.current_state
        <OrbActivity.LISTENING: 'listening'>
    """

    # Define valid state transitions
    # Safety states (ERROR, SAFETY_ALERT) are reachable from anywhere
    VALID_TRANSITIONS: dict[OrbActivity, set[OrbActivity]] = {
        OrbActivity.IDLE: {
            OrbActivity.LISTENING,
            OrbActivity.ERROR,
            OrbActivity.SAFETY_ALERT,
        },
        OrbActivity.LISTENING: {
            OrbActivity.PROCESSING,
            OrbActivity.IDLE,
            OrbActivity.ERROR,
            OrbActivity.SAFETY_ALERT,
        },
        OrbActivity.PROCESSING: {
            OrbActivity.RESPONDING,
            OrbActivity.ERROR,
            OrbActivity.SAFETY_ALERT,
        },
        OrbActivity.RESPONDING: {
            OrbActivity.IDLE,
            OrbActivity.ERROR,
            OrbActivity.SAFETY_ALERT,
        },
        OrbActivity.ERROR: {
            OrbActivity.IDLE,
            OrbActivity.SAFETY_ALERT,
        },
        OrbActivity.SAFETY_ALERT: {
            OrbActivity.IDLE,
            OrbActivity.ERROR,
        },
        OrbActivity.PORTABLE: {
            OrbActivity.IDLE,
            OrbActivity.ERROR,
            OrbActivity.SAFETY_ALERT,
        },
    }

    # Safety threshold for automatic SAFETY_ALERT transition
    SAFETY_THRESHOLD = 0.5

    def __init__(
        self,
        initial_state: OrbActivity = OrbActivity.IDLE,
        *,
        strict_mode: bool = False,
    ) -> None:
        """Initialize the state machine.

        Args:
            initial_state: Starting state (default: IDLE)
            strict_mode: If True, invalid transitions raise exceptions
                        instead of returning False
        """
        self._current_state = initial_state
        self._strict_mode = strict_mode
        self._listeners: list[TransitionListener] = []
        self._transition_history: list[tuple[OrbActivity, OrbActivity, float]] = []

    @property
    def current_state(self) -> OrbActivity:
        """Get the current state.

        Returns:
            Current OrbActivity state
        """
        return self._current_state

    @property
    def transition_history(self) -> list[tuple[OrbActivity, OrbActivity, float]]:
        """Get the transition history.

        Returns:
            List of (from_state, to_state, timestamp) tuples
        """
        return self._transition_history.copy()

    @property
    def is_in_error_state(self) -> bool:
        """Check if currently in an error state.

        Returns:
            True if in ERROR or SAFETY_ALERT state
        """
        return self._current_state in {OrbActivity.ERROR, OrbActivity.SAFETY_ALERT}

    @property
    def is_idle(self) -> bool:
        """Check if currently idle.

        Returns:
            True if in IDLE state
        """
        return self._current_state == OrbActivity.IDLE

    @property
    def is_active(self) -> bool:
        """Check if currently in an active processing state.

        Returns:
            True if in LISTENING, PROCESSING, or RESPONDING state
        """
        return self._current_state in {
            OrbActivity.LISTENING,
            OrbActivity.PROCESSING,
            OrbActivity.RESPONDING,
        }

    def get_valid_transitions(self) -> set[OrbActivity]:
        """Get all valid transitions from current state.

        Returns:
            Set of valid target states
        """
        return self.VALID_TRANSITIONS.get(self._current_state, set()).copy()

    def can_transition(self, to_state: OrbActivity) -> bool:
        """Check if a transition to the target state is valid.

        Args:
            to_state: The desired target state

        Returns:
            True if the transition is valid
        """
        valid_targets = self.VALID_TRANSITIONS.get(self._current_state, set())
        return to_state in valid_targets

    def transition(
        self,
        to_state: OrbActivity,
        *,
        force: bool = False,
    ) -> bool:
        """Attempt a state transition.

        Args:
            to_state: The desired target state
            force: If True, bypass validation (use for emergency transitions)

        Returns:
            True if transition succeeded, False otherwise

        Raises:
            InvalidTransitionError: If strict_mode is enabled and transition
                                   is invalid (and force=False)

        Example:
            >>> machine = OrbStateMachine()
            >>> machine.transition(OrbActivity.LISTENING)
            True
            >>> machine.transition(OrbActivity.IDLE)  # Invalid from LISTENING->IDLE? No, it's valid
            True
        """
        if not force and not self.can_transition(to_state):
            valid_targets = self.get_valid_transitions()
            logger.warning(
                "Invalid transition attempted: %s → %s (valid: %s)",
                self._current_state.value,
                to_state.value,
                [s.value for s in valid_targets],
            )
            if self._strict_mode:
                raise InvalidTransitionError(self._current_state, to_state, valid_targets)
            return False

        old_state = self._current_state
        self._current_state = to_state

        # Record transition
        import time

        self._transition_history.append((old_state, to_state, time.time()))

        # Keep history bounded (last 100 transitions)
        if len(self._transition_history) > 100:
            self._transition_history = self._transition_history[-100:]

        logger.debug("State transition: %s → %s", old_state.value, to_state.value)

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(old_state, to_state)
            except Exception:
                logger.exception("Error in transition listener")

        return True

    def transition_with_result(
        self,
        to_state: OrbActivity,
        *,
        force: bool = False,
    ) -> TransitionResult:
        """Attempt a state transition and return detailed result.

        Args:
            to_state: The desired target state
            force: If True, bypass validation

        Returns:
            TransitionResult with success status and details

        Example:
            >>> machine = OrbStateMachine()
            >>> result = machine.transition_with_result(OrbActivity.PROCESSING)
            >>> result.success
            False
            >>> result.reason
            'Invalid transition from IDLE to PROCESSING'
        """
        from_state = self._current_state

        if not force and not self.can_transition(to_state):
            return TransitionResult(
                success=False,
                from_state=from_state,
                to_state=to_state,
                reason=f"Invalid transition from {from_state.value} to {to_state.value}",
            )

        # Perform the transition
        success = self.transition(to_state, force=force)

        return TransitionResult(
            success=success,
            from_state=from_state,
            to_state=self._current_state,
            reason=None if success else "Transition failed",
        )

    def add_listener(
        self,
        callback: TransitionListener,
    ) -> None:
        """Add a transition listener.

        The listener is called after each successful transition with
        (old_state, new_state) arguments.

        Args:
            callback: Function to call on state transitions

        Example:
            >>> def on_transition(old, new):
            ...     print(f"{old.value} → {new.value}")
            >>> machine = OrbStateMachine()
            >>> machine.add_listener(on_transition)
            >>> machine.transition(OrbActivity.LISTENING)
            idle → listening
            True
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: TransitionListener) -> bool:
        """Remove a transition listener.

        Args:
            callback: The listener to remove

        Returns:
            True if listener was found and removed
        """
        try:
            self._listeners.remove(callback)
            return True
        except ValueError:
            return False

    def emergency_stop(self) -> None:
        """Force immediate transition to SAFETY_ALERT.

        This bypasses normal validation and should be used when
        h(x) < 0 or other safety violations occur.

        The transition is forced regardless of current state.

        Example:
            >>> machine = OrbStateMachine()
            >>> machine.transition(OrbActivity.PROCESSING)  # Invalid but let's say we're there
            False
            >>> machine.emergency_stop()
            >>> machine.current_state
            <OrbActivity.SAFETY_ALERT: 'safety_alert'>
        """
        logger.warning(
            "EMERGENCY STOP: Forcing transition from %s to SAFETY_ALERT",
            self._current_state.value,
        )
        self.transition(OrbActivity.SAFETY_ALERT, force=True)

    def error(self, reason: str | None = None) -> None:
        """Force immediate transition to ERROR state.

        This bypasses normal validation for error handling.

        Args:
            reason: Optional reason for the error (logged)

        Example:
            >>> machine = OrbStateMachine()
            >>> machine.error("API connection lost")
            >>> machine.current_state
            <OrbActivity.ERROR: 'error'>
        """
        if reason:
            logger.error("Error transition: %s", reason)
        else:
            logger.error("Error transition from %s", self._current_state.value)
        self.transition(OrbActivity.ERROR, force=True)

    def recover(self) -> bool:
        """Attempt to recover from ERROR or SAFETY_ALERT to IDLE.

        Returns:
            True if recovery succeeded (was in error state and transitioned)

        Example:
            >>> machine = OrbStateMachine()
            >>> machine.error()
            >>> machine.recover()
            True
            >>> machine.current_state
            <OrbActivity.IDLE: 'idle'>
        """
        if not self.is_in_error_state:
            logger.debug("Recover called but not in error state")
            return False

        logger.info("Recovering from %s to IDLE", self._current_state.value)
        return self.transition(OrbActivity.IDLE)

    def reset(self) -> None:
        """Reset state machine to IDLE, clearing history.

        This is a hard reset that bypasses validation and clears
        all transition history. Use with caution.
        """
        logger.info("State machine reset")
        self._current_state = OrbActivity.IDLE
        self._transition_history.clear()

    def check_safety(self, safety_score: float) -> bool:
        """Check safety score and transition to SAFETY_ALERT if needed.

        Args:
            safety_score: h(x) value (0.0 to 1.0)

        Returns:
            True if safety is OK, False if triggered SAFETY_ALERT

        Example:
            >>> machine = OrbStateMachine()
            >>> machine.check_safety(0.8)  # Safe
            True
            >>> machine.check_safety(0.3)  # Unsafe - triggers alert
            False
            >>> machine.current_state
            <OrbActivity.SAFETY_ALERT: 'safety_alert'>
        """
        if safety_score < self.SAFETY_THRESHOLD:
            logger.warning(
                "Safety score %.2f below threshold %.2f - triggering SAFETY_ALERT",
                safety_score,
                self.SAFETY_THRESHOLD,
            )
            self.emergency_stop()
            return False
        return True

    def __repr__(self) -> str:
        """Return string representation."""
        return f"OrbStateMachine(state={self._current_state.value}, history_len={len(self._transition_history)})"
