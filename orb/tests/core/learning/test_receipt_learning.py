"""Unit tests for receipt learning engine.

Tests the self-improvement loop:
    Receipt → Analysis → Update → Improved Performance
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.learning.receipt_learning import (
    ReceiptLearningEngine,
    ReceiptAnalysis,
    LearningUpdate,
    get_learning_engine,
)
from kagami.core.unified_agents.memory.stigmergy import (
    StigmergyLearner,
    ColonyGameModel,
)


@pytest.fixture
def stigmergy_learner():
    """Create a stigmergy learner for testing."""
    learner = StigmergyLearner(
        max_cache_size=100,
        enable_persistence=False,  # Don't persist during tests
        enable_game_model=True,
    )
    return learner


@pytest.fixture
def learning_engine(stigmergy_learner: Any) -> Any:
    """Create a receipt learning engine for testing."""
    engine = ReceiptLearningEngine(
        organism_rssm=None,  # No world model for basic tests
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=3,
    )
    return engine


@pytest.fixture
def sample_receipts():
    """Create sample receipts for testing."""
    return [
        {
            "intent": {"action": "research.web", "complexity": 0.6},
            "actor": "colony:grove:agent1",
            "verifier": {"status": "verified"},
            "duration_ms": 1500,
            "g_value": 0.8,
        },
        {
            "intent": {"action": "research.web", "complexity": 0.5},
            "actor": "colony:grove:agent2",
            "verifier": {"status": "verified"},
            "duration_ms": 1200,
            "g_value": 0.7,
        },
        {
            "intent": {"action": "research.web", "complexity": 0.7},
            "actor": "colony:crystal:agent3",
            "verifier": {"status": "failed"},
            "duration_ms": 2000,
            "g_value": 1.5,
        },
        {
            "intent": {"action": "research.web", "complexity": 0.6},
            "actor": "colony:grove:agent1",
            "verifier": {"status": "verified"},
            "duration_ms": 1300,
            "g_value": 0.6,
        },
    ]


def test_receipt_analysis_basic(learning_engine: Any, sample_receipts: Any) -> None:
    """Test basic receipt analysis."""
    analysis = learning_engine.analyze_receipts(sample_receipts, "research.web")

    assert analysis.intent_type == "research.web"
    assert analysis.sample_size == 4
    assert 0.0 <= analysis.success_rate <= 1.0
    assert analysis.avg_g_value > 0
    assert analysis.avg_complexity > 0
    assert analysis.avg_duration > 0
    assert "grove" in analysis.colony_contributions
    assert "crystal" in analysis.colony_contributions


def test_receipt_analysis_success_rate(learning_engine: Any, sample_receipts: Any) -> None:
    """Test success rate calculation."""
    analysis = learning_engine.analyze_receipts(sample_receipts, "research.web")

    # 3 verified, 1 failed → 75% success
    assert abs(analysis.success_rate - 0.75) < 0.01


def test_receipt_analysis_colony_contributions(learning_engine: Any, sample_receipts: Any) -> None:
    """Test colony contribution tracking."""
    analysis = learning_engine.analyze_receipts(sample_receipts, "research.web")

    # grove: 3/4 = 0.75, crystal: 1/4 = 0.25
    assert abs(analysis.colony_contributions["grove"] - 0.75) < 0.01
    assert abs(analysis.colony_contributions["crystal"] - 0.25) < 0.01


def test_receipt_analysis_empty(learning_engine: Any) -> None:
    """Test analysis with empty receipts."""
    analysis = learning_engine.analyze_receipts([], "test.action")

    assert analysis.intent_type == "test.action"
    assert analysis.sample_size == 0
    assert analysis.success_rate == 0.5  # Default
    assert analysis.avg_g_value == 1.0  # Default
    assert len(analysis.colony_contributions) == 0


def test_compute_learning_update_success(learning_engine: Any) -> None:
    """Test learning update computation for successful pattern."""
    analysis = ReceiptAnalysis(
        intent_type="research.web",
        success_rate=0.9,  # High success
        avg_g_value=0.5,  # Low G (good)
        avg_complexity=0.6,
        avg_duration=1.5,
        colony_contributions={"grove": 0.7, "crystal": 0.3},
        sample_size=10,
    )

    update = learning_engine.compute_learning_update(analysis)

    # High success should produce positive deltas
    assert update.confidence > 0
    assert len(update.colony_utility_deltas) == 2
    assert update.colony_utility_deltas["grove"] > 0
    assert update.colony_utility_deltas["crystal"] > 0


def test_compute_learning_update_failure(learning_engine: Any) -> None:
    """Test learning update computation for failure pattern."""
    analysis = ReceiptAnalysis(
        intent_type="build.feature",
        success_rate=0.2,  # Low success
        avg_g_value=1.5,  # High G (bad)
        avg_complexity=0.6,
        avg_duration=3.0,
        colony_contributions={"forge": 0.8, "flow": 0.2},
        sample_size=10,
    )

    update = learning_engine.compute_learning_update(analysis)

    # Low success should produce negative deltas
    assert update.confidence > 0
    assert len(update.colony_utility_deltas) == 2
    assert update.colony_utility_deltas["forge"] < 0
    assert update.colony_utility_deltas["flow"] < 0


def test_compute_learning_update_insufficient_samples(learning_engine: Any) -> None:
    """Test learning update with insufficient samples."""
    analysis = ReceiptAnalysis(
        intent_type="test.action",
        success_rate=0.9,
        avg_g_value=0.5,
        avg_complexity=0.6,
        avg_duration=1.5,
        colony_contributions={"grove": 1.0},
        sample_size=2,  # Below min_sample_size=3
    )

    update = learning_engine.compute_learning_update(analysis)

    assert update.confidence == 0.0
    assert len(update.colony_utility_deltas) == 0
    assert "insufficient_samples" in update.metadata.get("reason", "")


def test_apply_update(learning_engine: Any) -> None:
    """Test applying learning update to game model."""
    # Create update
    update = LearningUpdate(
        colony_utility_deltas={"grove": 0.05, "crystal": 0.02},
        confidence=0.8,
    )

    # Get initial utilities
    game_model = learning_engine.stigmergy.game_model
    grove_util_before = game_model.get_colony_utility("grove").success_rate
    crystal_util_before = game_model.get_colony_utility("crystal").success_rate

    # Apply update
    learning_engine.apply_update(update)

    # Check utilities were updated
    grove_util_after = game_model.get_colony_utility("grove").success_rate
    crystal_util_after = game_model.get_colony_utility("crystal").success_rate

    assert grove_util_after > grove_util_before
    assert crystal_util_after > crystal_util_before


def test_apply_update_clamping(learning_engine: Any) -> None:
    """Test that utility updates are clamped to [0, 1]."""
    # Create large update that would push utility > 1
    update = LearningUpdate(
        colony_utility_deltas={"grove": 0.9},  # Large positive delta
        confidence=1.0,
    )

    # Apply update multiple times
    for _ in range(10):
        learning_engine.apply_update(update)

    # Check utility is clamped at 1.0
    grove_util = learning_engine.stigmergy.game_model.get_colony_utility("grove")
    assert grove_util.success_rate <= 1.0


@pytest.mark.asyncio
async def test_learn_from_receipts_integration(learning_engine: Any, sample_receipts: Any) -> None:
    """Test end-to-end learning pipeline."""
    # Add receipts to stigmergy cache
    learning_engine.stigmergy.receipt_cache.extend(sample_receipts)

    # Run learning
    update = await learning_engine.learn_from_receipts(sample_receipts, "research.web")

    assert update is not None
    assert update.confidence > 0
    assert len(update.colony_utility_deltas) > 0

    # Check that patterns were updated
    assert len(learning_engine.stigmergy.patterns) > 0


@pytest.mark.asyncio
async def test_learn_from_stigmergy_with_intent_type(
    learning_engine: Any, sample_receipts: Any
) -> None:
    """Test learning from stigmergy cache with specific intent type."""
    # Add receipts to cache
    learning_engine.stigmergy.receipt_cache.extend(sample_receipts)

    # Learn from specific intent type
    update = await learning_engine.learn_from_stigmergy("research")

    assert update is not None
    assert "research" in update.metadata.get("intent_type", "")


@pytest.mark.asyncio
async def test_learn_from_stigmergy_all_intents(learning_engine: Any) -> None:
    """Test learning from all receipts in stigmergy cache."""
    # Add mixed receipts
    receipts = [
        {
            "intent": {"action": "research.web"},
            "actor": "colony:grove:agent1",
            "verifier": {"status": "verified"},
            "duration_ms": 1000,
        },
        {
            "intent": {"action": "research.web"},
            "actor": "colony:grove:agent2",
            "verifier": {"status": "verified"},
            "duration_ms": 1100,
        },
        {
            "intent": {"action": "research.web"},
            "actor": "colony:grove:agent3",
            "verifier": {"status": "verified"},
            "duration_ms": 1200,
        },
        {
            "intent": {"action": "build.feature"},
            "actor": "colony:forge:agent1",
            "verifier": {"status": "verified"},
            "duration_ms": 2000,
        },
        {
            "intent": {"action": "build.feature"},
            "actor": "colony:forge:agent2",
            "verifier": {"status": "verified"},
            "duration_ms": 2100,
        },
    ]
    learning_engine.stigmergy.receipt_cache.extend(receipts)

    # Learn from largest group (should be research with 3 receipts)
    update = await learning_engine.learn_from_stigmergy()

    assert update is not None
    assert update.metadata.get("intent_type") == "research"


@pytest.mark.asyncio
async def test_learn_from_stigmergy_empty_cache(learning_engine: Any) -> None:
    """Test learning from empty stigmergy cache."""
    update = await learning_engine.learn_from_stigmergy()
    assert update is None


def test_get_stats(learning_engine: Any, sample_receipts: Any) -> None:
    """Test statistics retrieval."""
    learning_engine.stigmergy.receipt_cache.extend(sample_receipts)
    learning_engine.stigmergy.extract_patterns()

    stats = learning_engine.get_stats()

    assert "learning_rate" in stats
    assert "min_sample_size" in stats
    assert "receipts_cached" in stats
    assert "patterns_learned" in stats
    assert "game_model" in stats

    assert stats["receipts_cached"] == len(sample_receipts)
    assert stats["patterns_learned"] > 0


def test_global_learning_engine():
    """Test global learning engine singleton."""
    engine1 = get_learning_engine()
    engine2 = get_learning_engine()

    assert engine1 is engine2  # Same instance


def test_confidence_increases_with_samples(learning_engine: Any) -> None:
    """Test that confidence increases with more samples."""
    # Small sample
    analysis_small = ReceiptAnalysis(
        intent_type="test",
        success_rate=0.9,
        avg_g_value=0.5,
        avg_complexity=0.5,
        avg_duration=1.0,
        colony_contributions={"grove": 1.0},
        sample_size=3,
    )

    # Large sample
    analysis_large = ReceiptAnalysis(
        intent_type="test",
        success_rate=0.9,
        avg_g_value=0.5,
        avg_complexity=0.5,
        avg_duration=1.0,
        colony_contributions={"grove": 1.0},
        sample_size=20,
    )

    update_small = learning_engine.compute_learning_update(analysis_small)
    update_large = learning_engine.compute_learning_update(analysis_large)

    assert update_large.confidence > update_small.confidence


def test_confidence_increases_with_extreme_success(learning_engine: Any) -> None:
    """Test that confidence increases with more extreme success rates."""
    # Moderate success (uncertain)
    analysis_moderate = ReceiptAnalysis(
        intent_type="test",
        success_rate=0.5,  # Neutral
        avg_g_value=0.5,
        avg_complexity=0.5,
        avg_duration=1.0,
        colony_contributions={"grove": 1.0},
        sample_size=10,
    )

    # High success (confident)
    analysis_high = ReceiptAnalysis(
        intent_type="test",
        success_rate=0.95,  # Very successful
        avg_g_value=0.5,
        avg_complexity=0.5,
        avg_duration=1.0,
        colony_contributions={"grove": 1.0},
        sample_size=10,
    )

    update_moderate = learning_engine.compute_learning_update(analysis_moderate)
    update_high = learning_engine.compute_learning_update(analysis_high)

    assert update_high.confidence > update_moderate.confidence


def test_colony_contribution_weighting(learning_engine: Any) -> None:
    """Test that colony contributions are properly weighted."""
    analysis = ReceiptAnalysis(
        intent_type="test",
        success_rate=0.8,
        avg_g_value=0.5,
        avg_complexity=0.5,
        avg_duration=1.0,
        colony_contributions={
            "grove": 0.7,  # High contribution
            "crystal": 0.3,  # Low contribution
        },
        sample_size=10,
    )

    update = learning_engine.compute_learning_update(analysis)

    # Grove should get more credit (higher delta)
    grove_delta = abs(update.colony_utility_deltas["grove"])
    crystal_delta = abs(update.colony_utility_deltas["crystal"])

    assert grove_delta > crystal_delta


@pytest.mark.asyncio
async def test_learning_loop_convergence(learning_engine: Any) -> None:
    """Test that learning loop converges over multiple iterations."""
    # Simulate consistent successful executions
    success_receipts = [
        {
            "intent": {"action": "research.web"},
            "actor": "colony:grove:agent1",
            "verifier": {"status": "verified"},
            "duration_ms": 1000,
            "g_value": 0.5,
        }
        for _ in range(5)
    ]

    grove_utils = []

    # Run learning multiple times
    for _ in range(5):
        learning_engine.stigmergy.receipt_cache.extend(success_receipts)
        await learning_engine.learn_from_receipts(success_receipts, "research")

        # Track grove utility
        grove_util = learning_engine.stigmergy.game_model.get_colony_utility("grove")
        grove_utils.append(grove_util.success_rate)

    # Utility should increase over time (learning is working)
    assert grove_utils[-1] > grove_utils[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
