"""Explainability Layer for Ambient Intelligence.

Provides transparency into ambient system decisions:
- Log every ambient action with trigger and reasoning
- Answer "why did it do that?" queries
- Dashboard of recent decisions
- Natural language explanations

Design Principles:
1. Every action is traceable: trigger → reasoning → effect
2. User-friendly explanations: No jargon
3. Temporal context: What happened before?
4. Reversibility info: Can this be undone?

Created: December 7, 2025
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of ambient decisions."""

    LIGHT_CHANGE = "light_change"
    SOUND_CHANGE = "sound_change"
    HAPTIC = "haptic"
    VOICE_OUTPUT = "voice_output"
    PRESENCE_ADAPT = "presence_adapt"
    SAFETY_ALERT = "safety_alert"
    COLONY_EXPRESS = "colony_express"
    HANDOFF = "handoff"
    CONTEXT_INFER = "context_infer"
    PAUSE = "pause"
    RESUME = "resume"
    OTHER = "other"


class TriggerType(Enum):
    """Types of triggers that cause decisions."""

    PRESENCE_CHANGE = "presence_change"
    COLONY_STATE = "colony_state"
    SAFETY_THRESHOLD = "safety_threshold"
    TIME_OF_DAY = "time_of_day"
    BREATH_CYCLE = "breath_cycle"
    USER_COMMAND = "user_command"
    DEVICE_EVENT = "device_event"
    CONTEXT_CHANGE = "context_change"
    SCHEDULED = "scheduled"
    SYSTEM = "system"


@dataclass
class AmbientDecision:
    """A logged ambient decision."""

    id: str
    timestamp: float
    decision_type: DecisionType
    trigger_type: TriggerType
    trigger_details: str  # What specifically triggered this
    reasoning: str  # Why this decision was made
    effect: str  # What happened
    reversible: bool = True
    reversed: bool = False
    confidence: float = 1.0  # How confident the system was
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "timestamp_human": datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S"),
            "decision_type": self.decision_type.value,
            "trigger_type": self.trigger_type.value,
            "trigger_details": self.trigger_details,
            "reasoning": self.reasoning,
            "effect": self.effect,
            "reversible": self.reversible,
            "reversed": self.reversed,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    def explain(self, verbose: bool = False) -> str:
        """Generate human-readable explanation.

        Args:
            verbose: Include more detail

        Returns:
            Natural language explanation
        """
        time_str = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")

        if verbose:
            return (
                f"At {time_str}, {self.trigger_details}. "
                f"Because of this, {self.reasoning.lower()} "
                f"Result: {self.effect}. "
                f"{'This can be undone.' if self.reversible else 'This cannot be undone.'}"
            )
        else:
            return f"{time_str}: {self.reasoning} → {self.effect}"


@dataclass
class ExplainabilityConfig:
    """Explainability engine configuration."""

    # History
    max_history: int = 1000
    summary_window_minutes: int = 30

    # Logging
    log_all_decisions: bool = True
    log_to_file: bool = False
    log_file_path: str = ""

    # Verbosity
    default_verbose: bool = False


class ExplainabilityEngine:
    """Engine for explaining ambient decisions.

    Responsibilities:
    - Log all ambient decisions
    - Provide queryable history
    - Generate natural language explanations
    - Support "why did that happen?" queries
    """

    def __init__(self, config: ExplainabilityConfig | None = None):
        """Initialize explainability engine.

        Args:
            config: Engine configuration
        """
        self.config = config or ExplainabilityConfig()

        # Decision history (ring buffer)
        self._history: deque[AmbientDecision] = deque(maxlen=self.config.max_history)

        # Decision counter for IDs
        self._counter = 0

        # Statistics
        self._stats: dict[str, int | dict[str, int]] = {
            "total_decisions": 0,
            "by_type": {},
            "by_trigger": {},
            "queries": 0,
            "reversals": 0,
        }

        logger.info("💡 Explainability engine initialized")

    # =========================================================================
    # Decision Logging
    # =========================================================================

    def log_decision(
        self,
        decision_type: DecisionType,
        trigger_type: TriggerType,
        trigger_details: str,
        reasoning: str,
        effect: str,
        reversible: bool = True,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> AmbientDecision:
        """Log an ambient decision.

        Args:
            decision_type: Type of decision
            trigger_type: What triggered it
            trigger_details: Specific trigger info
            reasoning: Why this decision was made
            effect: What happened
            reversible: Can this be undone?
            confidence: System confidence (0-1)
            metadata: Additional data

        Returns:
            The logged decision
        """
        self._counter += 1

        decision = AmbientDecision(
            id=f"d{self._counter:06d}",
            timestamp=time.time(),
            decision_type=decision_type,
            trigger_type=trigger_type,
            trigger_details=trigger_details,
            reasoning=reasoning,
            effect=effect,
            reversible=reversible,
            confidence=confidence,
            metadata=metadata or {},
        )

        self._history.append(decision)

        # Update stats
        total = self._stats["total_decisions"]
        assert isinstance(total, int)
        self._stats["total_decisions"] = total + 1

        by_type = self._stats["by_type"]
        assert isinstance(by_type, dict)
        by_type[decision_type.value] = by_type.get(decision_type.value, 0) + 1

        by_trigger = self._stats["by_trigger"]
        assert isinstance(by_trigger, dict)
        by_trigger[trigger_type.value] = by_trigger.get(trigger_type.value, 0) + 1

        if self.config.log_all_decisions:
            logger.debug(f"💡 Decision: {decision.explain()}")

        return decision

    # =========================================================================
    # Convenience Loggers
    # =========================================================================

    def log_light_change(
        self,
        trigger: str,
        reasoning: str,
        old_state: dict[str, Any],
        new_state: dict[str, Any],
    ) -> AmbientDecision:
        """Log a light change decision."""
        effect = f"Lights changed to {new_state.get('brightness', '?')}% brightness"

        return self.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=self._infer_trigger_type(trigger),
            trigger_details=trigger,
            reasoning=reasoning,
            effect=effect,
            reversible=True,
            metadata={"old_state": old_state, "new_state": new_state},
        )

    def log_sound_change(
        self,
        trigger: str,
        reasoning: str,
        effect_description: str,
    ) -> AmbientDecision:
        """Log a sound change decision."""
        return self.log_decision(
            decision_type=DecisionType.SOUND_CHANGE,
            trigger_type=self._infer_trigger_type(trigger),
            trigger_details=trigger,
            reasoning=reasoning,
            effect=effect_description,
            reversible=True,
        )

    def log_presence_adapt(
        self,
        old_level: str,
        new_level: str,
        adaptations: list[str],
    ) -> AmbientDecision:
        """Log presence adaptation."""
        return self.log_decision(
            decision_type=DecisionType.PRESENCE_ADAPT,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details=f"Presence changed from {old_level} to {new_level}",
            reasoning=f"Adapting ambient to {new_level} presence level",
            effect="; ".join(adaptations) if adaptations else "No changes needed",
            reversible=True,
            metadata={"old_level": old_level, "new_level": new_level},
        )

    def log_safety_alert(
        self,
        h_value: float,
        threat: str,
        actions_taken: list[str],
    ) -> AmbientDecision:
        """Log safety alert."""
        return self.log_decision(
            decision_type=DecisionType.SAFETY_ALERT,
            trigger_type=TriggerType.SAFETY_THRESHOLD,
            trigger_details=f"Safety barrier h(x) = {h_value:.3f}",
            reasoning=f"Safety alert triggered: {threat}",
            effect="; ".join(actions_taken) if actions_taken else "Alert displayed",
            reversible=False,  # Safety alerts shouldn't be undone
            metadata={"h_value": h_value, "threat": threat},
        )

    def log_colony_expression(
        self,
        colony: str,
        activation: float,
        expressions: list[str],
    ) -> AmbientDecision:
        """Log colony expression."""
        return self.log_decision(
            decision_type=DecisionType.COLONY_EXPRESS,
            trigger_type=TriggerType.COLONY_STATE,
            trigger_details=f"Colony {colony} activation: {activation:.2f}",
            reasoning=f"Expressing {colony} colony state",
            effect="; ".join(expressions) if expressions else "Subtle expression",
            reversible=True,
            metadata={"colony": colony, "activation": activation},
        )

    def _infer_trigger_type(self, trigger: str) -> TriggerType:
        """Infer trigger type from trigger string."""
        trigger_lower = trigger.lower()

        if "presence" in trigger_lower:
            return TriggerType.PRESENCE_CHANGE
        elif "colony" in trigger_lower:
            return TriggerType.COLONY_STATE
        elif "safety" in trigger_lower or "h(x)" in trigger_lower:
            return TriggerType.SAFETY_THRESHOLD
        elif "time" in trigger_lower or "schedule" in trigger_lower:
            return TriggerType.TIME_OF_DAY
        elif "breath" in trigger_lower:
            return TriggerType.BREATH_CYCLE
        elif "user" in trigger_lower or "command" in trigger_lower:
            return TriggerType.USER_COMMAND
        elif "device" in trigger_lower or "battery" in trigger_lower:
            return TriggerType.DEVICE_EVENT
        elif "context" in trigger_lower:
            return TriggerType.CONTEXT_CHANGE
        else:
            return TriggerType.SYSTEM

    # =========================================================================
    # Queries
    # =========================================================================

    def query_recent(
        self,
        minutes: int = 30,
        decision_type: DecisionType | None = None,
        limit: int = 50,
    ) -> list[AmbientDecision]:
        """Query recent decisions.

        Args:
            minutes: How far back to look
            decision_type: Filter by type
            limit: Max results

        Returns:
            List of decisions
        """
        queries = self._stats["queries"]
        assert isinstance(queries, int)
        self._stats["queries"] = queries + 1

        cutoff = time.time() - (minutes * 60)

        results = [d for d in self._history if d.timestamp >= cutoff]

        if decision_type:
            results = [d for d in results if d.decision_type == decision_type]

        # Sort by most recent first
        results.sort(key=lambda d: d.timestamp, reverse=True)

        return results[:limit]

    def query_by_id(self, decision_id: str) -> AmbientDecision | None:
        """Get a specific decision by ID.

        Args:
            decision_id: Decision ID

        Returns:
            Decision or None
        """
        for decision in self._history:
            if decision.id == decision_id:
                return decision
        return None

    def explain_last(self, count: int = 1, verbose: bool = False) -> list[str]:
        """Explain the last N decisions.

        Args:
            count: Number of decisions
            verbose: Use verbose explanations

        Returns:
            List of explanations
        """
        recent = list(self._history)[-count:]
        return [d.explain(verbose=verbose) for d in reversed(recent)]

    def explain_question(self, question: str) -> str:
        """Answer a natural language question about ambient behavior.

        Args:
            question: User's question

        Returns:
            Natural language answer
        """
        queries = self._stats["queries"]
        assert isinstance(queries, int)
        self._stats["queries"] = queries + 1
        question_lower = question.lower()

        # Parse question type
        if "why" in question_lower:
            return self._answer_why(question_lower)
        elif "what" in question_lower:
            return self._answer_what(question_lower)
        elif "when" in question_lower:
            return self._answer_when(question_lower)
        elif "how many" in question_lower or "count" in question_lower:
            return self._answer_count(question_lower)
        else:
            # Default: show recent activity
            recent = self.explain_last(3, verbose=True)
            if recent:
                return "Recent activity:\n" + "\n".join(f"• {e}" for e in recent)
            return "No recent ambient activity to explain."

    def _answer_why(self, question: str) -> str:
        """Answer 'why' questions."""
        # Check for specific decision types
        if "light" in question:
            decisions = self.query_recent(
                minutes=30, decision_type=DecisionType.LIGHT_CHANGE, limit=1
            )
        elif "sound" in question or "audio" in question:
            decisions = self.query_recent(
                minutes=30, decision_type=DecisionType.SOUND_CHANGE, limit=1
            )
        elif "alert" in question or "safety" in question:
            decisions = self.query_recent(
                minutes=30, decision_type=DecisionType.SAFETY_ALERT, limit=1
            )
        else:
            decisions = self.query_recent(minutes=30, limit=1)

        if not decisions:
            return "I haven't made any relevant decisions recently."

        d = decisions[0]
        return d.explain(verbose=True)

    def _answer_what(self, question: str) -> str:
        """Answer 'what' questions."""
        if ("happening" in question) or ("happened" in question) or ("doing" in question):
            recent = self.query_recent(minutes=5, limit=5)
            if not recent:
                return "Nothing notable in the last 5 minutes."

            actions = [d.effect for d in recent]
            return "In the last 5 minutes:\n" + "\n".join(f"• {a}" for a in actions)

        elif "changed" in question:
            recent = self.query_recent(minutes=30, limit=10)
            changes = [d for d in recent if d.decision_type != DecisionType.OTHER]
            if not changes:
                return "No changes in the last 30 minutes."

            return "Recent changes:\n" + "\n".join(f"• {d.explain()}" for d in changes[:5])

        # Default "what" answer: show the most recent non-trivial change, else say nothing happened.
        recent = self.query_recent(minutes=30, limit=5)
        changes = [d for d in recent if d.decision_type != DecisionType.OTHER]
        if not changes:
            return "Nothing notable recently."
        d = changes[0]
        return f"Something changed recently: {d.effect}"

    def _answer_when(self, question: str) -> str:
        """Answer 'when' questions."""
        if "last" in question:
            if "light" in question:
                decisions = self.query_recent(
                    minutes=1440, decision_type=DecisionType.LIGHT_CHANGE, limit=1
                )
            elif "alert" in question:
                decisions = self.query_recent(
                    minutes=1440, decision_type=DecisionType.SAFETY_ALERT, limit=1
                )
            else:
                decisions = self.query_recent(minutes=1440, limit=1)

            if decisions:
                d = decisions[0]
                time_str = datetime.fromtimestamp(d.timestamp).strftime("%H:%M:%S")
                return f"Last occurrence was at {time_str}: {d.reasoning}"
            return "No matching events found in the last 24 hours."

        return "I'm not sure what timeframe you're asking about."

    def _answer_count(self, question: str) -> str:
        """Answer count questions."""
        recent = self.query_recent(minutes=self.config.summary_window_minutes)

        if "light" in question:
            count = sum(1 for d in recent if d.decision_type == DecisionType.LIGHT_CHANGE)
            return f"There have been {count} light changes in the last {self.config.summary_window_minutes} minutes."
        elif "alert" in question:
            count = sum(1 for d in recent if d.decision_type == DecisionType.SAFETY_ALERT)
            return f"There have been {count} safety alerts in the last {self.config.summary_window_minutes} minutes."
        else:
            return f"There have been {len(recent)} ambient decisions in the last {self.config.summary_window_minutes} minutes."

    # =========================================================================
    # Reversal
    # =========================================================================

    async def reverse_decision(self, decision_id: str) -> bool:
        """Attempt to reverse a decision.

        Args:
            decision_id: Decision to reverse

        Returns:
            True if reversal successful
        """
        decision = self.query_by_id(decision_id)

        if not decision:
            logger.warning(f"Decision {decision_id} not found")
            return False

        if not decision.reversible:
            logger.warning(f"Decision {decision_id} is not reversible")
            return False

        if decision.reversed:
            logger.warning(f"Decision {decision_id} already reversed")
            return False

        # Attempt reversal based on type
        # Note: Actual reversal would need integration with ambient subsystems
        decision.reversed = True
        reversals = self._stats["reversals"]
        assert isinstance(reversals, int)
        self._stats["reversals"] = reversals + 1

        logger.info(f"↩️ Reversed decision {decision_id}")
        return True

    # =========================================================================
    # Summary & Dashboard
    # =========================================================================

    def get_summary(self, minutes: int = 30) -> dict[str, Any]:
        """Get summary of recent activity.

        Args:
            minutes: Time window

        Returns:
            Summary data
        """
        recent = self.query_recent(minutes=minutes, limit=1000)

        # Count by type
        by_type: dict[str, int] = {}
        for d in recent:
            by_type[d.decision_type.value] = by_type.get(d.decision_type.value, 0) + 1

        # Count by trigger
        by_trigger: dict[str, int] = {}
        for d in recent:
            by_trigger[d.trigger_type.value] = by_trigger.get(d.trigger_type.value, 0) + 1

        # Most recent of each type
        most_recent = {}
        for d in recent:
            if d.decision_type.value not in most_recent:
                most_recent[d.decision_type.value] = d.to_dict()

        return {
            "window_minutes": minutes,
            "total_decisions": len(recent),
            "by_type": by_type,
            "by_trigger": by_trigger,
            "most_recent_by_type": most_recent,
            "latest": recent[0].to_dict() if recent else None,
        }

    def get_dashboard(self) -> dict[str, Any]:
        """Get dashboard data for UI.

        Returns:
            Dashboard data
        """
        return {
            "summary_30min": self.get_summary(30),
            "recent_explanations": self.explain_last(5, verbose=False),
            "stats": self._stats,
            "history_size": len(self._history),
            "max_history": self.config.max_history,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get statistics."""
        return {
            **self._stats,
            "history_size": len(self._history),
        }


# =============================================================================
# Global Instance
# =============================================================================

_EXPLAINABILITY_ENGINE: ExplainabilityEngine | None = None


def get_explainability_engine() -> ExplainabilityEngine:
    """Get global explainability engine instance."""
    global _EXPLAINABILITY_ENGINE
    if _EXPLAINABILITY_ENGINE is None:
        _EXPLAINABILITY_ENGINE = ExplainabilityEngine()
    return _EXPLAINABILITY_ENGINE
