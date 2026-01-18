from __future__ import annotations

"""Intrinsic curiosity drive for autonomous exploration and learning.

Generates self-directed learning goals without external prompts,
enabling autonomous capability expansion.
"""
import logging
import random
from dataclasses import dataclass
from typing import Any

from kagami.core.instincts.prediction_instinct import get_prediction_instinct

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeGap:
    """Identified gap in understanding."""

    topic: str
    uncertainty: float  # 0.0 (certain) to 1.0 (completely uncertain)
    novelty: float  # 0.0 (seen before) to 1.0 (brand new)
    importance: float  # 0.0 (trivial) to 1.0 (critical)
    curiosity_score: float  # Combined metric


@dataclass
class ExploratoryAction:
    """Self-generated action to learn more."""

    action_type: str  # experiment|explore|test|analyze
    target: str
    hypothesis: str
    expected_learning: float
    risk: float


class CuriosityInstinct:
    """Intrinsic drive to explore and learn autonomously."""

    def __init__(self) -> None:
        # Track what we've explored
        self._explored_topics: set[str] = set()

        # Knowledge gaps discovered
        self._knowledge_gaps: list[KnowledgeGap] = []

        # Exploration history
        self._explorations: list[dict[str, Any]] = []

        # Curiosity parameters
        self._curiosity_threshold = 0.7  # Explore if score > threshold
        self._exploration_budget = 10  # Max autonomous explorations per session

    async def detect_knowledge_gap(self, context: dict[str, Any]) -> KnowledgeGap | None:
        """Identify what we don't understand about current situation.

        High curiosity when:
        - Low prediction confidence (uncertain)
        - Novel situation (not seen before)
        - Important for goals (high impact)
        """
        prediction_instinct = get_prediction_instinct()

        # Measure uncertainty
        prediction = await prediction_instinct.predict(context)
        uncertainty = 1.0 - prediction.confidence

        # Measure novelty
        novelty = self._compute_novelty(context)

        # Measure importance (heuristic)
        importance = self._assess_importance(context)

        # Combined curiosity score
        curiosity = uncertainty * novelty * importance

        if curiosity < self._curiosity_threshold:
            return None

        gap = KnowledgeGap(
            topic=context.get("action", "unknown"),
            uncertainty=uncertainty,
            novelty=novelty,
            importance=importance,
            curiosity_score=curiosity,
        )

        self._knowledge_gaps.append(gap)

        logger.info(
            f"🔍 Knowledge gap detected: {gap.topic[:40]} "
            f"(curiosity: {curiosity:.2f}, uncertainty: {uncertainty:.2f}, "
            f"novelty: {novelty:.2f})"
        )

        return gap

    def _compute_novelty(self, context: dict[str, Any]) -> float:
        """How novel is this situation?"""
        topic = context.get("action", "")

        # Check exploration history
        if topic in self._explored_topics:
            return 0.2  # Seen before

        # Check if similar to anything we've seen
        similar_count = sum(
            1 for explored in self._explored_topics if self._is_similar(topic, explored)
        )

        if similar_count > 5:
            return 0.4  # Similar to many things
        elif similar_count > 0:
            return 0.7  # Somewhat similar
        else:
            return 1.0  # Completely novel

    def _is_similar(self, topic1: str, topic2: str) -> bool:
        """Check if two topics are similar."""
        # Simple token overlap heuristic
        tokens1 = set(topic1.lower().split())
        tokens2 = set(topic2.lower().split())

        overlap = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return overlap / union > 0.5 if union > 0 else False

    def _assess_importance(self, context: dict[str, Any]) -> float:
        """How important is understanding this?"""
        # Heuristics for importance
        action = context.get("action", "").lower()

        # Core system operations are important
        if any(kw in action for kw in ["auth", "security", "payment", "data"]):
            return 0.9

        # Check encounter frequency from receipts
        from kagami.core.receipts.store import ReceiptStore  # type: ignore[attr-defined]

        try:
            store = ReceiptStore()
            # Count recent encounters with this action type
            recent_receipts = store.get_recent(limit=100)
            encounter_count = sum(
                1
                for r in recent_receipts
                if r.get("intent", {}).get("action", "").lower() == action
            )
            # More encounters = higher importance (capped at 0.9)
            return min(0.3 + (encounter_count * 0.1), 0.9)
        except Exception:
            # If receipts unavailable, use action complexity as proxy
            word_count = len(action.split())
            return min(0.3 + (word_count * 0.1), 0.8)

    def generate_exploratory_action(self, knowledge_gap: KnowledgeGap) -> ExploratoryAction | None:
        """Generate autonomous action to learn more about gap.

        Self-directed learning - no human prompt needed.
        """
        if len(self._explorations) >= self._exploration_budget:
            logger.debug("Exploration budget exhausted for this session")
            return None

        # Different exploration strategies
        strategies = [
            self._generate_experiment,
            self._generate_analysis,
            self._generate_test,
            self._generate_probe,
        ]

        # Try strategies in order
        for strategy in strategies:
            action = strategy(knowledge_gap)
            if action:
                return action

        return None

    def _generate_experiment(self, gap: KnowledgeGap) -> ExploratoryAction | None:
        """Generate an experimental action to explore the knowledge gap."""
        if gap.curiosity_score < 0.5:
            return None
        return ExploratoryAction(
            action_type="experiment",
            target=gap.topic,
            hypothesis=f"Testing hypothesis about {gap.topic}",
            expected_learning=gap.curiosity_score * 0.8,
            risk=gap.uncertainty * 0.3,
        )

    def _generate_analysis(self, gap: KnowledgeGap) -> ExploratoryAction | None:
        """Generate an analytical action to explore the knowledge gap."""
        if gap.novelty < 0.3:
            return None
        return ExploratoryAction(
            action_type="analyze",
            target=gap.topic,
            hypothesis=f"Analyzing patterns in {gap.topic}",
            expected_learning=gap.curiosity_score * 0.6,
            risk=0.1,
        )

    def _generate_test(self, gap: KnowledgeGap) -> ExploratoryAction | None:
        """Generate a testing action to verify understanding."""
        if gap.importance < 0.4:
            return None
        return ExploratoryAction(
            action_type="test",
            target=gap.topic,
            hypothesis=f"Verifying understanding of {gap.topic}",
            expected_learning=gap.curiosity_score * 0.5,
            risk=0.2,
        )

    def _generate_probe(self, gap: KnowledgeGap) -> ExploratoryAction | None:
        """Generate a probing action for initial exploration."""
        return ExploratoryAction(
            action_type="explore",
            target=gap.topic,
            hypothesis=f"Initial exploration of {gap.topic}",
            expected_learning=gap.curiosity_score * 0.4,
            risk=0.05,
        )

    def should_explore_autonomously(self) -> bool:
        """Should we explore even without user prompt?

        Returns True if:
        - We have high-curiosity knowledge gaps
        - We haven't exhausted exploration budget
        - System is idle (would check load in real implementation)
        """
        if len(self._explorations) >= self._exploration_budget:
            return False

        # Check if we have high-curiosity gaps
        high_curiosity_gaps = [g for g in self._knowledge_gaps if g.curiosity_score > 0.8]

        if not high_curiosity_gaps:
            return False

        # Simulate idle check (in real implementation, check system load)
        # For now, randomly explore 10% of the time
        return random.random() < 0.1

    def record_exploration(self, action: ExploratoryAction, outcome: dict[str, Any]) -> None:
        """Record results of autonomous exploration."""
        self._explored_topics.add(action.target)
        self._explorations.append(
            {
                "action": action,
                "outcome": outcome,
                "learned": outcome.get("status") == "success",
            }
        )

        # Log learning
        if outcome.get("status") == "success":
            logger.info(
                f"✅ Autonomous exploration succeeded: {action.target[:40]} "
                f"(learned: {action.expected_learning:.2f})"
            )
        else:
            logger.info(
                f"❌ Autonomous exploration failed: {action.target[:40]} (but gained information)"
            )

    def get_curiosity_summary(self) -> dict[str, Any]:
        """Get summary of curiosity-driven learning."""
        return {
            "total_explorations": len(self._explorations),
            "topics_explored": len(self._explored_topics),
            "knowledge_gaps_identified": len(self._knowledge_gaps),
            "avg_curiosity_score": (
                sum(g.curiosity_score for g in self._knowledge_gaps) / len(self._knowledge_gaps)
                if self._knowledge_gaps
                else 0.0
            ),
            "exploration_budget_used": len(self._explorations) / self._exploration_budget,
            "successful_explorations": sum(
                1 for e in self._explorations if e.get("learned", False)
            ),
        }


# Global singleton
_curiosity_instinct: CuriosityInstinct | None = None


def get_curiosity_instinct() -> CuriosityInstinct:
    """Get or create global curiosity instinct."""
    global _curiosity_instinct

    if _curiosity_instinct is None:
        _curiosity_instinct = CuriosityInstinct()

    return _curiosity_instinct
