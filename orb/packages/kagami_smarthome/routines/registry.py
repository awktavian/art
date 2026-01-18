"""Routine Registry — Manages all routines, their configs, and execution history.

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.context.context_engine import HomeContext
    from kagami_smarthome.execution.receipted_executor import ReceiptedExecutor

from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine, RoutineResult

logger = logging.getLogger(__name__)

# Global registry instance
_registry: RoutineRegistry | None = None


@dataclass
class RoutineSuggestion:
    """A suggestion for routine parameter adjustment."""

    id: str
    routine_id: str
    param_name: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float
    source: str  # "learning_engine" or "manual_override_pattern"
    status: str = "pending"  # pending, approved, rejected

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "routine_id": self.routine_id,
            "param_name": self.param_name,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "confidence": self.confidence,
            "source": self.source,
            "status": self.status,
        }


@dataclass
class RoutineStats:
    """Statistics for a routine."""

    routine_id: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration_ms: float = 0.0
    last_execution: float | None = None
    avg_actions_per_execution: float = 0.0


class RoutineRegistry:
    """Manages all routines, their configs, and execution history.

    Usage:
        registry = RoutineRegistry()
        registry.register(WelcomeHomeRoutine())
        result = await registry.execute_routine("welcome_home", context, executor)
    """

    def __init__(self):
        """Initialize registry."""
        self._routines: dict[str, AdaptiveRoutine] = {}
        self._execution_history: list[RoutineResult] = []
        self._param_overrides: dict[str, dict[str, Any]] = {}  # User customizations
        self._pending_suggestions: dict[str, RoutineSuggestion] = {}
        self._stats: dict[str, RoutineStats] = {}

    def register(self, routine: AdaptiveRoutine) -> None:
        """Register a routine.

        Args:
            routine: Routine instance to register
        """
        self._routines[routine.id] = routine
        self._stats[routine.id] = RoutineStats(routine_id=routine.id)
        logger.info(f"Registered routine: {routine.id} ({routine.name})")

    def unregister(self, routine_id: str) -> bool:
        """Unregister a routine.

        Args:
            routine_id: ID of routine to remove

        Returns:
            True if removed, False if not found
        """
        if routine_id in self._routines:
            del self._routines[routine_id]
            return True
        return False

    def get_routine(self, routine_id: str) -> AdaptiveRoutine | None:
        """Get a routine by ID."""
        return self._routines.get(routine_id)

    def get_all_routines(self) -> list[AdaptiveRoutine]:
        """Get all registered routines."""
        return list(self._routines.values())

    def get_routine_ids(self) -> list[str]:
        """Get all routine IDs."""
        return list(self._routines.keys())

    async def execute_routine(
        self,
        routine_id: str,
        context: HomeContext,
        executor: ReceiptedExecutor,
    ) -> RoutineResult:
        """Execute a routine by ID.

        Args:
            routine_id: ID of routine to execute
            context: Current home context
            executor: ReceiptedExecutor instance

        Returns:
            RoutineResult with execution details
        """
        import time

        routine = self._routines.get(routine_id)
        if not routine:
            return RoutineResult(
                routine_id=routine_id,
                success=False,
                error=f"Routine not found: {routine_id}",
            )

        # Apply any user parameter overrides
        if routine_id in self._param_overrides:
            routine.update_params(self._param_overrides[routine_id])

        # Execute routine
        start_time = time.time()
        result = await routine.execute(executor, context)
        duration_ms = (time.time() - start_time) * 1000

        # Update stats
        stats = self._stats[routine_id]
        stats.execution_count += 1
        if result.success:
            stats.success_count += 1
        else:
            stats.failure_count += 1
        stats.total_duration_ms += duration_ms
        stats.last_execution = time.time()
        stats.avg_actions_per_execution = (
            stats.avg_actions_per_execution * (stats.execution_count - 1) + len(result.actions)
        ) / stats.execution_count

        # Add to history (keep last 100)
        self._execution_history.append(result)
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]

        return result

    async def check_triggers(
        self,
        context: HomeContext,
        executor: ReceiptedExecutor,
    ) -> list[RoutineResult]:
        """Check all routines for triggers and execute matching ones.

        Args:
            context: Current home context
            executor: ReceiptedExecutor instance

        Returns:
            List of RoutineResults for executed routines
        """
        results = []

        for routine in self._routines.values():
            should_trigger, reason = await routine.should_trigger(context)

            if should_trigger:
                logger.info(f"Routine {routine.id} triggered: {reason}")
                result = await self.execute_routine(routine.id, context, executor)
                result.trigger_reason = reason
                results.append(result)

        return results

    def get_routine_stats(self, routine_id: str) -> RoutineStats | None:
        """Get execution statistics for a routine."""
        return self._stats.get(routine_id)

    def get_all_stats(self) -> dict[str, RoutineStats]:
        """Get statistics for all routines."""
        return self._stats.copy()

    def update_params(self, routine_id: str, params: dict[str, Any]) -> bool:
        """Update routine parameters (used by optimizer).

        Args:
            routine_id: ID of routine to update
            params: New parameter values

        Returns:
            True if updated, False if routine not found
        """
        if routine_id not in self._routines:
            return False

        self._param_overrides[routine_id] = params
        return True

    def get_execution_history(
        self,
        routine_id: str | None = None,
        limit: int = 50,
    ) -> list[RoutineResult]:
        """Get execution history.

        Args:
            routine_id: Optional filter by routine ID
            limit: Maximum results to return

        Returns:
            List of RoutineResults
        """
        history = self._execution_history
        if routine_id:
            history = [r for r in history if r.routine_id == routine_id]
        return history[-limit:]

    # Suggestion management

    def add_suggestion(self, suggestion: RoutineSuggestion) -> None:
        """Add a parameter suggestion."""
        self._pending_suggestions[suggestion.id] = suggestion

    def get_pending_suggestions(self) -> list[RoutineSuggestion]:
        """Get all pending suggestions."""
        return [s for s in self._pending_suggestions.values() if s.status == "pending"]

    def get_suggestion(self, suggestion_id: str) -> RoutineSuggestion | None:
        """Get a suggestion by ID."""
        return self._pending_suggestions.get(suggestion_id)

    async def apply_suggestion(self, suggestion: RoutineSuggestion) -> bool:
        """Apply a suggestion (after user approval).

        Args:
            suggestion: The suggestion to apply

        Returns:
            True if applied successfully
        """
        routine = self._routines.get(suggestion.routine_id)
        if not routine:
            return False

        # Update parameter
        if suggestion.routine_id not in self._param_overrides:
            self._param_overrides[suggestion.routine_id] = {}

        self._param_overrides[suggestion.routine_id][suggestion.param_name] = (
            suggestion.suggested_value
        )
        suggestion.status = "approved"

        logger.info(
            f"Applied suggestion {suggestion.id}: "
            f"{suggestion.routine_id}.{suggestion.param_name} = {suggestion.suggested_value}"
        )

        return True

    def reject_suggestion(self, suggestion_id: str, reason: str | None = None) -> bool:
        """Reject a suggestion.

        Args:
            suggestion_id: ID of suggestion to reject
            reason: Optional rejection reason

        Returns:
            True if rejected, False if not found
        """
        suggestion = self._pending_suggestions.get(suggestion_id)
        if not suggestion:
            return False

        suggestion.status = "rejected"
        logger.info(f"Rejected suggestion {suggestion_id}: {reason}")

        return True


def get_routine_registry() -> RoutineRegistry:
    """Get or create global routine registry."""
    global _registry
    if _registry is None:
        _registry = RoutineRegistry()
    return _registry


__all__ = [
    "RoutineRegistry",
    "RoutineStats",
    "RoutineSuggestion",
    "get_routine_registry",
]
