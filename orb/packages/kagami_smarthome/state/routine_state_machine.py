"""Routine State Machine — Tracks routine execution lifecycle.

Simple state machine for tracking routine execution phases.

Created: January 2, 2026
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RoutineState(Enum):
    """States a routine can be in."""

    IDLE = "idle"
    TRIGGERED = "triggered"
    COMPUTING = "computing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class RoutineEvent(Enum):
    """Events that cause state transitions."""

    TRIGGER = "trigger"
    COMPUTE_DONE = "compute_done"
    EXECUTE_START = "execute_start"
    ACTION_SUCCESS = "action_success"
    ACTION_FAILURE = "action_failure"
    ALL_DONE = "all_done"
    RESET = "reset"


# State transition table
TRANSITIONS: dict[tuple[RoutineState, RoutineEvent], RoutineState] = {
    # From IDLE
    (RoutineState.IDLE, RoutineEvent.TRIGGER): RoutineState.TRIGGERED,
    # From TRIGGERED
    (RoutineState.TRIGGERED, RoutineEvent.COMPUTE_DONE): RoutineState.COMPUTING,
    # From COMPUTING
    (RoutineState.COMPUTING, RoutineEvent.EXECUTE_START): RoutineState.EXECUTING,
    (RoutineState.COMPUTING, RoutineEvent.ALL_DONE): RoutineState.COMPLETED,  # No actions
    # From EXECUTING
    (RoutineState.EXECUTING, RoutineEvent.ACTION_SUCCESS): RoutineState.EXECUTING,
    (RoutineState.EXECUTING, RoutineEvent.ACTION_FAILURE): RoutineState.EXECUTING,
    (RoutineState.EXECUTING, RoutineEvent.ALL_DONE): RoutineState.COMPLETED,
    # From any state
    (RoutineState.COMPLETED, RoutineEvent.RESET): RoutineState.IDLE,
    (RoutineState.FAILED, RoutineEvent.RESET): RoutineState.IDLE,
}


class RoutineStateMachine:
    """Simple state machine for routine execution tracking.

    Usage:
        sm = RoutineStateMachine("goodnight")
        await sm.transition(RoutineEvent.TRIGGER)
        await sm.transition(RoutineEvent.COMPUTE_DONE)
        await sm.transition(RoutineEvent.EXECUTE_START)
        await sm.transition(RoutineEvent.ALL_DONE)
    """

    def __init__(self, routine_id: str):
        self.routine_id = routine_id
        self._state = RoutineState.IDLE
        self._history: list[tuple[RoutineState, RoutineEvent, RoutineState]] = []

    @property
    def state(self) -> RoutineState:
        """Current state."""
        return self._state

    @property
    def is_idle(self) -> bool:
        """Check if in idle state."""
        return self._state == RoutineState.IDLE

    @property
    def is_running(self) -> bool:
        """Check if routine is currently running."""
        return self._state in (
            RoutineState.TRIGGERED,
            RoutineState.COMPUTING,
            RoutineState.EXECUTING,
        )

    async def transition(self, event: RoutineEvent) -> bool:
        """Attempt state transition.

        Args:
            event: The event to process

        Returns:
            True if transition succeeded
        """
        key = (self._state, event)
        new_state = TRANSITIONS.get(key)

        if new_state is None:
            logger.warning(
                f"Invalid transition: {self.routine_id} {self._state.value} + {event.value}"
            )
            return False

        old_state = self._state
        self._state = new_state
        self._history.append((old_state, event, new_state))

        logger.debug(
            f"Routine {self.routine_id}: {old_state.value} → {new_state.value} ({event.value})"
        )
        return True

    def reset(self) -> None:
        """Reset to idle state."""
        self._state = RoutineState.IDLE

    def get_history(self) -> list[dict[str, Any]]:
        """Get transition history."""
        return [
            {
                "from": old.value,
                "event": event.value,
                "to": new.value,
            }
            for old, event, new in self._history
        ]


__all__ = [
    "RoutineEvent",
    "RoutineState",
    "RoutineStateMachine",
]
