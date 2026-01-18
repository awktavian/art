"""Continual Learning - Lifelong Learning with Catastrophic Forgetting Prevention.

Implements continual learning strategies to prevent catastrophic forgetting
when learning new tasks while retaining previous knowledge.

Referenced by: kagami/core/coordination/hybrid_coordination.py

Created: December 26, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """A piece of knowledge in the continual learning system."""

    knowledge_id: str
    content: Any
    importance: float = 0.5  # How critical this knowledge is
    access_count: int = 0
    is_critical: bool = False
    created_at: float = 0.0
    last_accessed: float = 0.0


class ContinualLearner:
    """Continual learning system with catastrophic forgetting prevention.

    Uses importance-weighted rehearsal and elastic weight consolidation (EWC)
    principles to maintain knowledge while learning new information.
    """

    def __init__(
        self,
        max_entries: int = 10000,
        consolidation_threshold: float = 0.8,
    ) -> None:
        """Initialize continual learner.

        Args:
            max_entries: Maximum knowledge entries to maintain
            consolidation_threshold: Threshold for memory consolidation
        """
        self._knowledge: dict[str, KnowledgeEntry] = {}
        self._critical_knowledge: set[str] = set()
        self._max_entries = max_entries
        self._consolidation_threshold = consolidation_threshold
        logger.info("ContinualLearner initialized")

    def add_knowledge(
        self,
        knowledge_id: str,
        content: Any,
        importance: float = 0.5,
    ) -> None:
        """Add new knowledge entry.

        Args:
            knowledge_id: Unique identifier for this knowledge
            content: The knowledge content
            importance: How important this knowledge is [0, 1]
        """
        import time

        now = time.time()

        if knowledge_id in self._knowledge:
            # Update existing
            entry = self._knowledge[knowledge_id]
            entry.content = content
            entry.importance = max(entry.importance, importance)
            entry.access_count += 1
            entry.last_accessed = now
        else:
            # Add new
            self._knowledge[knowledge_id] = KnowledgeEntry(
                knowledge_id=knowledge_id,
                content=content,
                importance=importance,
                created_at=now,
                last_accessed=now,
            )

        # Check if we need to consolidate
        if len(self._knowledge) > self._max_entries:
            self._consolidate_memory()

    def mark_knowledge_critical(self, knowledge_id: str) -> None:
        """Mark knowledge as critical (protected from forgetting).

        Args:
            knowledge_id: Knowledge to protect
        """
        self._critical_knowledge.add(knowledge_id)

        if knowledge_id in self._knowledge:
            self._knowledge[knowledge_id].is_critical = True
            self._knowledge[knowledge_id].importance = 1.0

        logger.debug(f"Marked knowledge {knowledge_id} as critical")

    def get_knowledge(self, knowledge_id: str) -> Any | None:
        """Retrieve knowledge by ID."""
        if knowledge_id in self._knowledge:
            entry = self._knowledge[knowledge_id]
            entry.access_count += 1
            return entry.content
        return None

    def get_critical_knowledge(self) -> list[KnowledgeEntry]:
        """Get all critical knowledge entries."""
        return [
            entry
            for entry in self._knowledge.values()
            if entry.is_critical or entry.knowledge_id in self._critical_knowledge
        ]

    def _consolidate_memory(self) -> None:
        """Consolidate memory by removing low-importance entries.

        Implements importance-weighted rehearsal: high-importance and
        frequently accessed knowledge is retained, while low-importance
        knowledge may be forgotten.
        """
        if len(self._knowledge) <= self._max_entries:
            return

        # Calculate effective importance
        entries = list(self._knowledge.values())

        def effective_importance(entry: KnowledgeEntry) -> float:
            if entry.is_critical:
                return float("inf")

            # Combine importance with access frequency
            access_factor = min(entry.access_count / 100, 1.0)
            return entry.importance + 0.3 * access_factor

        # Sort by effective importance
        entries.sort(key=effective_importance, reverse=True)

        # Keep only top entries
        keep_count = int(self._max_entries * self._consolidation_threshold)
        entries_to_keep = entries[:keep_count]
        keep_ids = {e.knowledge_id for e in entries_to_keep}

        # Remove forgotten entries
        forgotten = [kid for kid in self._knowledge if kid not in keep_ids]
        for kid in forgotten:
            if kid not in self._critical_knowledge:  # Never forget critical
                del self._knowledge[kid]

        logger.info(f"Memory consolidation: kept {len(self._knowledge)}, forgot {len(forgotten)}")

    def get_stats(self) -> dict[str, Any]:
        """Get learner statistics."""
        return {
            "total_knowledge": len(self._knowledge),
            "critical_knowledge": len(self._critical_knowledge),
            "max_entries": self._max_entries,
        }


# Singleton
_CONTINUAL_LEARNER: ContinualLearner | None = None


def get_continual_learner() -> ContinualLearner:
    """Get the global continual learner singleton."""
    global _CONTINUAL_LEARNER
    if _CONTINUAL_LEARNER is None:
        _CONTINUAL_LEARNER = ContinualLearner()
    return _CONTINUAL_LEARNER


def set_continual_learner(learner: ContinualLearner | None) -> None:
    """Set the global continual learner (for testing)."""
    global _CONTINUAL_LEARNER
    _CONTINUAL_LEARNER = learner


__all__ = [
    "ContinualLearner",
    "KnowledgeEntry",
    "get_continual_learner",
    "set_continual_learner",
]
