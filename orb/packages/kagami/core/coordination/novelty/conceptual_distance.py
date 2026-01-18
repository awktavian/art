# Standard library imports
import logging
from dataclasses import dataclass
from typing import Any

"""Novelty metrics for measuring conceptual distance.

Provides simple default metrics when more sophisticated ones aren't available.
"""

logger = logging.getLogger(__name__)


@dataclass
class NoveltyScore:
    """Score representing how novel a concept is."""

    overall: float  # 0.0-1.0
    semantic_distance: float = 0.0
    structural_distance: float = 0.0
    violated_assumptions: int = 0


class SimpleNoveltyMetric:
    """Simple novelty metric based on constraint violations."""

    async def measure_novelty(self, concept: dict[str, Any]) -> NoveltyScore:
        """
        Measure novelty based on how many assumptions were violated.

        More violated assumptions = more novel.
        """
        violated = concept.get("violated", [])
        num_violated = len(violated)

        # Base novelty from violations
        base_novelty = min(num_violated * 0.25, 1.0)

        # Bonus for paradigm shifts
        if concept.get("paradigm_shift"):
            base_novelty = min(base_novelty + 0.2, 1.0)

        # Bonus for orthogonal exploration
        if concept.get("orthogonal"):
            base_novelty = min(base_novelty + 0.15, 1.0)

        return NoveltyScore(
            overall=base_novelty,
            semantic_distance=base_novelty * 0.8,
            structural_distance=base_novelty * 0.6,
            violated_assumptions=num_violated,
        )


class ConceptualDistanceMetric:
    """Measure conceptual distance between concepts."""

    def __init__(self) -> None:
        self._concept_space: dict[str, Any] = {}

    async def measure_distance(self, concept_a: dict[str, Any], concept_b: dict[str, Any]) -> float:
        """
        Measure distance between two concepts.

        Returns:
            Distance in [0.0, 1.0] where 1.0 is maximally different
        """
        # Simple string-based distance for now
        desc_a = str(concept_a.get("description", ""))
        desc_b = str(concept_b.get("description", ""))

        # Count unique words
        words_a = set(desc_a.lower().split())
        words_b = set(desc_b.lower().split())

        if not words_a and not words_b:
            return 0.0

        # Jaccard distance
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)

        if union == 0:
            return 0.0

        similarity = intersection / union
        distance = 1.0 - similarity

        return distance

    async def add_to_space(self, concept: dict[str, Any], label: str) -> None:
        """Add a concept to the known concept space."""
        self._concept_space[label] = concept

    async def find_nearest(
        self, concept: dict[str, Any], top_k: int = 5
    ) -> list[tuple[str, float]]:
        """Find nearest concepts in the space."""
        if not self._concept_space:
            return []

        distances = []
        for label, known_concept in self._concept_space.items():
            distance = await self.measure_distance(concept, known_concept)
            distances.append((label, distance))

        # Sort by distance (ascending)
        distances.sort(key=lambda x: x[1])

        return distances[:top_k]
