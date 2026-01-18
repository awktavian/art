"""Adaptive Routine — Base class for intelligent, context-aware routines.

Each routine:
1. Decides whether to trigger based on context
2. Computes actions based on context (no side effects)
3. Executes actions via ReceiptedExecutor with full audit trail

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from kagami_smarthome.context.context_engine import HomeContext
from kagami_smarthome.execution.receipted_executor import (
    Action,
    ActionResult,
    ReceiptedExecutor,
)
from kagami_smarthome.state.routine_state_machine import (
    RoutineEvent,
    RoutineStateMachine,
)

logger = logging.getLogger(__name__)


@dataclass
class RoutineResult:
    """Result of a routine execution."""

    routine_id: str
    success: bool
    actions: list[ActionResult] = field(default_factory=list)
    trigger_reason: str | None = None
    context_summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "routine_id": self.routine_id,
            "success": self.success,
            "actions": [a.to_dict() for a in self.actions],
            "trigger_reason": self.trigger_reason,
            "context_summary": self.context_summary,
            "error": self.error,
        }


class AdaptiveRoutine(ABC):
    """Base class for all intelligent, context-aware routines.

    Subclasses must implement:
    - should_trigger(context) -> (bool, reason)
    - compute_actions(context) -> list[Action]

    Usage:
        class WelcomeHomeRoutine(AdaptiveRoutine):
            id = "welcome_home"
            name = "Welcome Home"

            async def should_trigger(self, context):
                if context.owner_just_arrived:
                    return True, "owner_arrived"
                return False, ""

            async def compute_actions(self, context):
                level = 60 if context.circadian_phase == CircadianPhase.EVENING else 30
                return [Action("set_lights", {"level": level, "rooms": ["Entry"]})]
    """

    # Required class attributes
    id: str = ""
    name: str = ""
    description: str = ""
    safety_critical: bool = False

    # Adaptation parameters (can be tuned by optimizer)
    params: dict[str, Any] = {}
    param_ranges: dict[str, tuple[float, float]] = {}

    def __init__(self):
        """Initialize routine with state machine."""
        self._state_machine = RoutineStateMachine(
            self.id,
            timeout_seconds=30.0,
            max_rollback_attempts=3,
        )

    @property
    def state(self):
        """Current state machine state."""
        return self._state_machine.state

    @abstractmethod
    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Determine if routine should trigger.

        Args:
            context: Current home context

        Returns:
            Tuple of (should_trigger, reason_string)
        """
        ...

    @abstractmethod
    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute actions based on context. No side effects.

        Args:
            context: Current home context

        Returns:
            List of actions to execute
        """
        ...

    def get_rollback_action(self, action: Action) -> Action | None:
        """Get rollback action for an action.

        Override in subclasses to provide rollback capability.

        Args:
            action: The action to create a rollback for

        Returns:
            Rollback action or None if not applicable
        """
        # Default: no rollback
        return None

    async def execute(
        self,
        executor: ReceiptedExecutor,
        context: HomeContext,
    ) -> RoutineResult:
        """Execute routine with full receipt trail.

        This method handles the entire routine lifecycle:
        1. Emit start receipt
        2. Compute actions
        3. Execute each action via executor
        4. Emit complete receipt
        5. Handle errors and rollback if needed

        Args:
            executor: ReceiptedExecutor instance
            context: Current home context

        Returns:
            RoutineResult with success/failure and action details
        """
        correlation_id = self._generate_correlation_id()

        # Emit start receipt
        self._emit_receipt(
            correlation_id,
            f"routine.{self.id}.start",
            event_data={"context_summary": context.summary()},
        )

        # Transition state machine
        await self._state_machine.transition(RoutineEvent.TRIGGER)

        try:
            # Compute actions
            actions = await self.compute_actions(context)
            await self._state_machine.transition(RoutineEvent.COMPUTE_DONE)

            if not actions:
                # No actions to execute
                await self._state_machine.transition(RoutineEvent.EXECUTE_START)
                await self._state_machine.transition(RoutineEvent.ALL_DONE)
                await self._state_machine.reset()

                return RoutineResult(
                    routine_id=self.id,
                    success=True,
                    actions=[],
                    context_summary=context.summary(),
                )

            # Execute actions
            await self._state_machine.transition(RoutineEvent.EXECUTE_START)
            results: list[ActionResult] = []
            all_success = True

            for action in actions:
                # Record action for potential rollback
                rollback = self.get_rollback_action(action)
                self._state_machine.record_action(
                    {"type": action.type, "params": action.params},
                    {"type": rollback.type, "params": rollback.params} if rollback else None,
                )

                # Execute action
                result = await executor.execute(
                    action.type,
                    action.params,
                    routine_id=self.id,
                    correlation_id=correlation_id,
                )
                results.append(result)

                if result.success:
                    await self._state_machine.transition(RoutineEvent.ACTION_SUCCESS)
                else:
                    all_success = False
                    logger.warning(f"Action {action.type} failed in routine {self.id}")

                    # Trigger rollback if action failed
                    await self._state_machine.transition(RoutineEvent.ACTION_FAILURE)
                    await self._state_machine.rollback(executor)
                    break

            if all_success:
                await self._state_machine.transition(RoutineEvent.ALL_DONE)

            await self._state_machine.reset()

            # Emit complete receipt
            self._emit_receipt(
                correlation_id,
                f"routine.{self.id}.complete",
                event_data={
                    "actions_count": len(actions),
                    "all_success": all_success,
                    "context_summary": context.summary(),
                },
            )

            return RoutineResult(
                routine_id=self.id,
                success=all_success,
                actions=results,
                context_summary=context.summary(),
            )

        except Exception as e:
            logger.error(f"Routine {self.id} failed: {e}")

            # Emit error receipt
            self._emit_receipt(
                correlation_id,
                f"routine.{self.id}.error",
                status="error",
                event_data={
                    "error": str(e),
                    "context_summary": context.summary(),
                },
            )

            await self._state_machine.recover()

            return RoutineResult(
                routine_id=self.id,
                success=False,
                error=str(e),
                context_summary=context.summary(),
            )

    def update_params(self, new_params: dict[str, Any]) -> None:
        """Update routine parameters.

        Called by the optimizer when user approves a suggestion.

        Args:
            new_params: New parameter values to apply
        """
        for key, value in new_params.items():
            if key in self.params:
                # Validate against ranges if defined
                if key in self.param_ranges:
                    min_val, max_val = self.param_ranges[key]
                    value = max(min_val, min(max_val, value))
                self.params[key] = value

    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for routine execution."""
        try:
            from kagami.core.receipts.facade import URF

            return URF.generate_correlation_id(prefix=f"routine_{self.id}")
        except ImportError:
            import uuid

            return f"routine_{self.id}_{uuid.uuid4().hex[:8]}"

    def _emit_receipt(
        self,
        correlation_id: str,
        event_name: str,
        status: str = "success",
        event_data: dict[str, Any] | None = None,
    ) -> None:
        """Emit receipt for routine."""
        try:
            from kagami.core.receipts.facade import emit_receipt

            emit_receipt(
                correlation_id,
                event_name,
                status=status,
                event_data=event_data or {},
            )
        except ImportError:
            logger.debug(f"Receipt: {event_name} [{status}] - {event_data}")


__all__ = [
    "Action",
    "AdaptiveRoutine",
    "RoutineResult",
]
