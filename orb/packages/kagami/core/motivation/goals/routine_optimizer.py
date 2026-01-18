"""Routine Optimizer Goal — Organism goal to continuously improve smart home routines.

Analyzes routine execution receipts and user feedback to suggest parameter improvements.
Part of the self-improvement loop:
    Action -> Receipt -> Learn -> Improve -> Better Action

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GoalEvaluation:
    """Evaluation of whether a goal should be pursued."""

    should_pursue: bool
    reason: str
    priority_boost: float = 0.0


@dataclass
class GoalResult:
    """Result of pursuing a goal."""

    success: bool
    message: str
    suggestions_generated: int = 0


@dataclass
class RoutineSuggestion:
    """A suggestion for routine parameter adjustment."""

    id: str
    routine_id: str
    param_name: str | None
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float
    source: str  # "learning_engine" or "manual_override_pattern"

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
        }


@dataclass
class OrganismState:
    """State passed to goals for evaluation and pursuit."""

    receipts: list[dict[str, Any]] = field(default_factory=list)
    learning_updates: list[Any] = field(default_factory=list)
    manual_overrides: list[dict[str, Any]] = field(default_factory=list)


class RoutineOptimizerGoal:
    """Organism goal: continuously improve smart home routines via learning.

    This goal:
    1. Queries learning updates from SmartHome learning bridge
    2. Analyzes manual override patterns from receipts
    3. Generates parameter adjustment suggestions
    4. Stores suggestions for user approval
    """

    id = "routine_optimizer"
    name = "Smart Home Routine Optimizer"
    priority = 0.3  # Background priority

    def __init__(self):
        self._pending_suggestions: dict[str, RoutineSuggestion] = {}
        self._last_evaluation: float = 0.0
        self._evaluation_interval_seconds = 3600  # 1 hour

    async def evaluate(self, state: OrganismState) -> GoalEvaluation:
        """Check if there are improvement opportunities.

        Args:
            state: Current organism state with receipts and learning updates

        Returns:
            GoalEvaluation indicating whether to pursue
        """
        # Don't evaluate too frequently
        now = time.time()
        if now - self._last_evaluation < self._evaluation_interval_seconds:
            return GoalEvaluation(
                should_pursue=False,
                reason="Evaluated recently",
            )

        # Query for improvement opportunities
        issues = self._analyze_for_issues(state)

        if issues:
            return GoalEvaluation(
                should_pursue=True,
                reason=f"Found {len(issues)} improvement opportunities",
                priority_boost=0.1 if any(i.get("severity") == "high" for i in issues) else 0,
            )

        return GoalEvaluation(
            should_pursue=False,
            reason="No issues detected",
        )

    async def pursue(self, state: OrganismState) -> GoalResult:
        """Generate improvement suggestions.

        Args:
            state: Current organism state

        Returns:
            GoalResult with suggestions generated
        """
        self._last_evaluation = time.time()
        suggestions: list[RoutineSuggestion] = []

        # Process learning updates
        for update in state.learning_updates:
            if hasattr(update, "confidence") and update.confidence > 0.7:
                suggestion = RoutineSuggestion(
                    id=str(uuid.uuid4())[:8],
                    routine_id=update.routine_id if hasattr(update, "routine_id") else "unknown",
                    param_name=update.metadata.get("param_name")
                    if hasattr(update, "metadata")
                    else None,
                    suggested_value=update.metadata.get("suggested_value")
                    if hasattr(update, "metadata")
                    else None,
                    current_value=update.metadata.get("current_value")
                    if hasattr(update, "metadata")
                    else None,
                    reason=f"Learning engine confidence: {update.confidence:.0%}",
                    confidence=update.confidence,
                    source="learning_engine",
                )
                suggestions.append(suggestion)

        # Analyze manual override patterns
        override_patterns = self._analyze_override_patterns(state.manual_overrides)
        for pattern in override_patterns:
            suggestion = RoutineSuggestion(
                id=str(uuid.uuid4())[:8],
                routine_id=pattern["routine_id"],
                param_name=pattern["param_name"],
                suggested_value=pattern["avg_override_value"],
                current_value=pattern["current_value"],
                reason=f"User manually adjusted {pattern['override_count']} times",
                confidence=min(pattern["override_count"] / 10, 1.0),
                source="manual_override_pattern",
            )
            suggestions.append(suggestion)

        # Store for user approval
        for suggestion in suggestions:
            self._pending_suggestions[suggestion.id] = suggestion
            self._emit_suggestion_receipt(suggestion)

        logger.info(f"RoutineOptimizerGoal generated {len(suggestions)} suggestions")

        return GoalResult(
            success=True,
            message=f"Generated {len(suggestions)} improvement suggestions",
            suggestions_generated=len(suggestions),
        )

    def _analyze_for_issues(self, state: OrganismState) -> list[dict[str, Any]]:
        """Analyze state for improvement issues."""
        issues = []

        # Check for learning updates with high confidence
        for update in state.learning_updates:
            if hasattr(update, "confidence") and update.confidence > 0.7:
                issues.append(
                    {
                        "type": "learning_opportunity",
                        "severity": "medium",
                        "routine_id": getattr(update, "routine_id", "unknown"),
                    }
                )

        # Check for repeated manual overrides
        override_counts: dict[str, int] = {}
        for override in state.manual_overrides:
            routine_id = override.get("routine_id", "unknown")
            override_counts[routine_id] = override_counts.get(routine_id, 0) + 1

        for routine_id, count in override_counts.items():
            if count >= 3:
                issues.append(
                    {
                        "type": "frequent_override",
                        "severity": "high" if count >= 5 else "medium",
                        "routine_id": routine_id,
                        "count": count,
                    }
                )

        return issues

    def _analyze_override_patterns(
        self,
        overrides: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Analyze manual override patterns to suggest parameter changes."""
        patterns: list[dict[str, Any]] = []

        # Group overrides by routine and parameter
        grouped: dict[str, list[dict[str, Any]]] = {}
        for override in overrides:
            key = f"{override.get('routine_id', 'unknown')}:{override.get('param_name', 'unknown')}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(override)

        # Analyze each group
        for key, group in grouped.items():
            if len(group) >= 3:  # Need at least 3 overrides to establish pattern
                routine_id, param_name = key.split(":", 1)

                # Calculate average override value
                values = [o.get("new_value") for o in group if o.get("new_value") is not None]
                if values and all(isinstance(v, (int, float)) for v in values):
                    avg_value = sum(values) / len(values)

                    patterns.append(
                        {
                            "routine_id": routine_id,
                            "param_name": param_name,
                            "avg_override_value": avg_value,
                            "current_value": group[0].get("old_value"),
                            "override_count": len(group),
                        }
                    )

        return patterns

    def _emit_suggestion_receipt(self, suggestion: RoutineSuggestion) -> None:
        """Emit receipt for suggestion generation."""
        try:
            from kagami.core.receipts.facade import URF, emit_receipt

            emit_receipt(
                URF.generate_correlation_id(),
                "routine.suggestion.generated",
                event_data=suggestion.to_dict(),
            )
        except ImportError:
            logger.debug(f"Generated suggestion: {suggestion.to_dict()}")

    def get_pending_suggestions(self) -> list[RoutineSuggestion]:
        """Get all pending suggestions."""
        return list(self._pending_suggestions.values())

    def get_suggestion(self, suggestion_id: str) -> RoutineSuggestion | None:
        """Get a suggestion by ID."""
        return self._pending_suggestions.get(suggestion_id)

    def mark_suggestion_approved(self, suggestion_id: str) -> bool:
        """Mark a suggestion as approved (after applying)."""
        if suggestion_id in self._pending_suggestions:
            del self._pending_suggestions[suggestion_id]
            return True
        return False

    def mark_suggestion_rejected(self, suggestion_id: str) -> bool:
        """Mark a suggestion as rejected."""
        if suggestion_id in self._pending_suggestions:
            del self._pending_suggestions[suggestion_id]
            return True
        return False


__all__ = [
    "GoalEvaluation",
    "GoalResult",
    "OrganismState",
    "RoutineOptimizerGoal",
    "RoutineSuggestion",
]
