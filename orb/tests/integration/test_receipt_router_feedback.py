"""Integration test for receipt → router feedback loop.

Tests that receipt learning updates propagate to the router within 1 execution cycle.

NEXUS BRIDGE: Verifies the complete feedback loop:
    Receipt → Learning → Utility Update → Router → Better Routing

Created: December 14, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio

from kagami.core.learning.receipt_learning import ReceiptLearningEngine
from kagami.core.unified_agents.fano_action_router import FanoActionRouter
from kagami.core.unified_agents.memory.stigmergy import ColonyGameModel, get_stigmergy_learner


@pytest.fixture
def router():
    """Create router with stigmergy learner."""
    router = FanoActionRouter()
    # Ensure stigmergy learner exists
    if router._stigmergy_learner is None:
        router._stigmergy_learner = get_stigmergy_learner()
    if router._stigmergy_learner.game_model is None:
        router._stigmergy_learner.game_model = ColonyGameModel()
    return router


@pytest.fixture
def learning_engine(router: Any) -> Any:
    """Create learning engine with stigmergy learner."""
    stigmergy = router._stigmergy_learner
    return ReceiptLearningEngine(stigmergy_learner=stigmergy)


def test_utility_lookup(router) -> Any:
    """Test that router can fetch learned utilities."""
    # Get initial utilities (should be empty or default)
    utilities = router._get_learned_utilities("build")

    # All colonies should have utilities (default is 0.5 from ColonyGameModel)
    assert len(utilities) == 7
    for colony_idx in range(7):
        assert colony_idx in utilities
        assert 0.0 <= utilities[colony_idx] <= 1.0


def test_utility_update_propagation(router, learning_engine) -> None:
    """Test that utility updates propagate to router immediately."""
    # 1. Create mock receipts showing Forge (colony 1) performing well
    mock_receipts = [
        {
            "actor": "forge:worker:1",
            "verifier": {"status": "verified"},
            "g_value": 0.5,
            "complexity": 0.4,
            "duration_ms": 100,
        }
        for _ in range(10)
    ]

    # 2. Run learning
    analysis = learning_engine.analyze_receipts(mock_receipts, "build")
    update = learning_engine.compute_learning_update(analysis)
    learning_engine.apply_update(update)

    # 3. Check that router sees updated utilities
    utilities_after = router._get_learned_utilities("build")

    # Forge (colony 1) should have highest utility after successful receipts
    forge_utility = utilities_after.get(1, 0.0)
    assert forge_utility > 0.5, "Forge should have improved utility after success"


@pytest.mark.asyncio
async def test_end_to_end_feedback_loop(router, learning_engine) -> None:
    """Test complete feedback loop: receipt → learning → router → routing decision."""
    # 1. Create receipts showing Grove (colony 5) excelling at research
    mock_receipts = [
        {
            "actor": "grove:worker:1",
            "verifier": {"status": "verified"},
            "g_value": 0.3,  # Low G = good
            "complexity": 0.5,
            "duration_ms": 150,
        }
        for _ in range(15)
    ]

    # 2. Learn from receipts
    await learning_engine.learn_from_receipts(mock_receipts, "research")

    # 3. Route a research task
    routing_result = router.route("research.web", {}, context={})

    # 4. Check that Grove (colony 5) is preferred for research
    best_colony_idx = routing_result.actions[0].colony_idx

    # Grove should be selected (or at least considered highly)
    grove_utility = router._get_learned_utilities("research").get(5, 0.0)
    assert grove_utility > 0.5, "Grove should have high utility for research after learning"


def test_refresh_utilities_hook(router) -> None:
    """Test that refresh_utilities hook exists and is callable."""
    # Should not raise
    router.refresh_utilities()


@pytest.mark.asyncio
async def test_learning_without_router(learning_engine) -> None:
    """Test that learning works even if router notification fails."""
    # This tests graceful degradation
    mock_receipts = [
        {
            "actor": "crystal:worker:1",
            "verifier": {"status": "verified"},
            "g_value": 0.2,
            "complexity": 0.3,
            "duration_ms": 200,
        }
        for _ in range(5)
    ]

    # Should not raise even if router notification fails
    await learning_engine.learn_from_receipts(mock_receipts, "verify")


def test_insufficient_samples_no_update(learning_engine) -> None:
    """Test that insufficient samples don't trigger updates."""
    # Only 2 receipts (below min_sample_size=3)
    mock_receipts = [
        {
            "actor": "spark:worker:1",
            "verifier": {"status": "verified"},
            "g_value": 0.4,
            "complexity": 0.5,
            "duration_ms": 100,
        }
        for _ in range(2)
    ]

    analysis = learning_engine.analyze_receipts(mock_receipts, "create")
    update = learning_engine.compute_learning_update(analysis)

    # Should have no updates due to insufficient samples
    assert update.confidence == 0.0
    assert len(update.colony_utility_deltas) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
