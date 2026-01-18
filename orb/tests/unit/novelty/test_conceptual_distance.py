"""Tests for novelty and conceptual distance metrics.

Tests the novelty metrics defined in kagami/core/coordination/novelty/conceptual_distance.py.
These metrics measure how novel a concept is based on various heuristics.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


from kagami.core.coordination.novelty.conceptual_distance import (
    ConceptualDistanceMetric,
    NoveltyScore,
    SimpleNoveltyMetric,
)


class TestNoveltyScore:
    """Test NoveltyScore dataclass."""

    def test_novelty_score_creation(self) -> None:
        """NoveltyScore should store all fields correctly."""
        score = NoveltyScore(
            overall=0.75,
            semantic_distance=0.6,
            structural_distance=0.5,
            violated_assumptions=3,
        )
        assert score.overall == 0.75
        assert score.semantic_distance == 0.6
        assert score.structural_distance == 0.5
        assert score.violated_assumptions == 3

    def test_novelty_score_defaults(self) -> None:
        """NoveltyScore should have sensible defaults."""
        score = NoveltyScore(overall=0.5)
        assert score.semantic_distance == 0.0
        assert score.structural_distance == 0.0
        assert score.violated_assumptions == 0


class TestSimpleNoveltyMetric:
    """Test SimpleNoveltyMetric."""

    @pytest.fixture
    def metric(self) -> Any:
        """Create metric instance."""
        return SimpleNoveltyMetric()

    @pytest.mark.asyncio
    async def test_zero_violations_low_novelty(self, metric: Any) -> Any:
        """Concept with no violations should have low novelty."""
        concept = {"violated": []}
        score = await metric.measure_novelty(concept)
        assert score.overall == 0.0
        assert score.violated_assumptions == 0

    @pytest.mark.asyncio
    async def test_violations_increase_novelty(self, metric: Any) -> None:
        """More violations should increase novelty score."""
        concept_1 = {"violated": ["assumption_1"]}
        concept_2 = {"violated": ["assumption_1", "assumption_2"]}
        concept_3 = {"violated": ["a", "b", "c", "d"]}

        score_1 = await metric.measure_novelty(concept_1)
        score_2 = await metric.measure_novelty(concept_2)
        score_3 = await metric.measure_novelty(concept_3)

        assert score_1.overall < score_2.overall
        assert score_2.overall < score_3.overall
        assert score_1.violated_assumptions == 1
        assert score_2.violated_assumptions == 2
        assert score_3.violated_assumptions == 4

    @pytest.mark.asyncio
    async def test_novelty_capped_at_1(self, metric: Any) -> None:
        """Novelty should be capped at 1.0."""
        concept = {"violated": ["a", "b", "c", "d", "e", "f", "g", "h"]}
        score = await metric.measure_novelty(concept)
        assert score.overall <= 1.0

    @pytest.mark.asyncio
    async def test_paradigm_shift_bonus(self, metric: Any) -> None:
        """Paradigm shift should add novelty bonus."""
        concept_normal = {"violated": ["a"]}
        concept_paradigm = {"violated": ["a"], "paradigm_shift": True}

        score_normal = await metric.measure_novelty(concept_normal)
        score_paradigm = await metric.measure_novelty(concept_paradigm)

        assert score_paradigm.overall > score_normal.overall

    @pytest.mark.asyncio
    async def test_orthogonal_bonus(self, metric: Any) -> None:
        """Orthogonal exploration should add novelty bonus."""
        concept_normal = {"violated": ["a"]}
        concept_orthogonal = {"violated": ["a"], "orthogonal": True}

        score_normal = await metric.measure_novelty(concept_normal)
        score_orthogonal = await metric.measure_novelty(concept_orthogonal)

        assert score_orthogonal.overall > score_normal.overall

    @pytest.mark.asyncio
    async def test_combined_bonuses(self, metric: Any) -> None:
        """Combined bonuses should stack (but cap at 1.0)."""
        concept = {
            "violated": ["a", "b"],
            "paradigm_shift": True,
            "orthogonal": True,
        }
        score = await metric.measure_novelty(concept)
        assert score.overall <= 1.0
        assert score.overall > 0.5  # Should be high with all bonuses

    @pytest.mark.asyncio
    async def test_semantic_structural_proportional(self, metric: Any) -> None:
        """Semantic and structural distances should be proportional to overall."""
        concept = {"violated": ["a", "b", "c"]}
        score = await metric.measure_novelty(concept)

        # Should be roughly proportional to overall
        assert score.semantic_distance == pytest.approx(score.overall * 0.8)
        assert score.structural_distance == pytest.approx(score.overall * 0.6)


class TestConceptualDistanceMetric:
    """Test ConceptualDistanceMetric."""

    @pytest.fixture
    def metric(self) -> Any:
        """Create metric instance."""
        return ConceptualDistanceMetric()

    @pytest.mark.asyncio
    async def test_identical_concepts_zero_distance(self, metric: Any) -> Any:
        """Identical concepts should have zero distance."""
        concept_a = {"description": "A red car"}
        concept_b = {"description": "A red car"}

        distance = await metric.measure_distance(concept_a, concept_b)
        assert distance == 0.0

    @pytest.mark.asyncio
    async def test_different_concepts_positive_distance(self, metric: Any) -> None:
        """Different concepts should have positive distance."""
        concept_a = {"description": "A red car"}
        concept_b = {"description": "A blue bicycle"}

        distance = await metric.measure_distance(concept_a, concept_b)
        assert distance > 0.0
        assert distance <= 1.0

    @pytest.mark.asyncio
    async def test_empty_concepts_zero_distance(self, metric: Any) -> None:
        """Empty concepts should have zero distance."""
        concept_a = {}
        concept_b = {}

        distance = await metric.measure_distance(concept_a, concept_b)
        assert distance == 0.0

    @pytest.mark.asyncio
    async def test_distance_symmetric(self, metric: Any) -> None:
        """Distance should be symmetric."""
        concept_a = {"description": "Machine learning"}
        concept_b = {"description": "Deep neural networks"}

        dist_ab = await metric.measure_distance(concept_a, concept_b)
        dist_ba = await metric.measure_distance(concept_b, concept_a)

        assert dist_ab == dist_ba

    @pytest.mark.asyncio
    async def test_distance_bounded(self, metric: Any) -> None:
        """Distance should be in [0, 1]."""
        concept_a = {"description": "Completely unrelated concept about cooking"}
        concept_b = {"description": "Mathematics physics quantum mechanics"}

        distance = await metric.measure_distance(concept_a, concept_b)
        assert 0.0 <= distance <= 1.0

    @pytest.mark.asyncio
    async def test_partial_overlap_medium_distance(self, metric: Any) -> None:
        """Partially overlapping concepts should have medium distance."""
        concept_a = {"description": "Machine learning for image recognition"}
        concept_b = {"description": "Machine learning for text analysis"}

        distance = await metric.measure_distance(concept_a, concept_b)
        # Should have some overlap ("machine", "learning", "for")
        # but also differences
        assert 0.0 < distance < 1.0

    @pytest.mark.asyncio
    async def test_case_insensitive(self, metric: Any) -> None:
        """Distance calculation should be case insensitive."""
        concept_a = {"description": "MACHINE LEARNING"}
        concept_b = {"description": "machine learning"}

        distance = await metric.measure_distance(concept_a, concept_b)
        assert distance == 0.0
