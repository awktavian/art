"""Integration test for receipt learning feedback loop.

Tests the complete Nexus bridge:
Receipt emission → Pattern storage → Learning trigger → Colony utility updates

NEXUS ARCHITECTURE:
==================
UnifiedOrganism.execute_intent()
    ↓
Receipt emitted (via stigmergy patterns)
    ↓
Receipt stored (in StigmergyLearner.patterns)
    ↓
Every N executions: _trigger_receipt_learning()
    ↓
Colony utilities updated (ColonyGameModel)
    ↓
Better future routing (Nash equilibrium)

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)
from kagami.core.unified_agents.memory.stigmergy import (
    get_stigmergy_learner,
    ReceiptPattern,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_learning_end_to_end() -> None:
    """Test full receipt learning loop.

    1. Execute intent 50 times
    2. Verify learning trigger fires
    3. Check colony utilities updated
    4. Confirm pattern-based routing improves
    """
    # Create organism with low learning frequency for testing
    config = OrganismConfig(
        max_workers_per_colony=2,
        homeostasis_interval=600.0,  # Disable homeostasis for test
    )
    organism = UnifiedOrganism(config=config)
    organism._learning_frequency = 10  # Learn every 10 executions (not 50)

    # Get stigmergy learner
    stigmergy = get_stigmergy_learner()

    # Seed some patterns for the test
    # Simulate "build" tasks succeeding with Forge colony
    pattern = ReceiptPattern(
        action="build.feature",
        domain="forge",
        success_count=8,
        failure_count=2,
        avg_duration=1.5,
    )
    stigmergy.patterns[("build.feature", "forge")] = pattern

    # Simulate "research" tasks succeeding with Grove colony
    pattern2 = ReceiptPattern(
        action="research.topic",
        domain="grove",
        success_count=9,
        failure_count=1,
        avg_duration=2.0,
    )
    stigmergy.patterns[("research.topic", "grove")] = pattern2

    # Ensure game model exists
    if stigmergy.game_model is None:
        from kagami.core.unified_agents.memory.stigmergy import ColonyGameModel

        stigmergy.game_model = ColonyGameModel()

    # Record initial colony utilities
    initial_forge_utility = stigmergy.game_model.get_colony_utility("forge")
    initial_grove_utility = stigmergy.game_model.get_colony_utility("grove")

    assert initial_forge_utility is not None
    assert initial_grove_utility is not None

    initial_forge_rate = initial_forge_utility.success_rate
    initial_grove_rate = initial_grove_utility.success_rate

    # Execute "build" intent 10 times (triggers learning once)
    for i in range(10):
        result = await organism.execute_intent(
            intent="build.feature",
            params={"feature": f"test_{i}"},
            context={},
        )
        assert result["success"], f"Intent {i} failed"

    # Verify learning was triggered
    assert organism._execution_count == 10
    assert organism._last_learning_time > 0

    # Check that colony utilities were updated
    updated_forge_utility = stigmergy.game_model.get_colony_utility("forge")
    assert updated_forge_utility is not None

    # Forge should have improved (had 80% success in patterns)
    # Delta = 0.8 - 0.5 = 0.3, update = 0.3 * 0.1 = +0.03
    assert (
        updated_forge_utility.success_rate >= initial_forge_rate
    ), "Forge utility should improve with good patterns"

    # Execute "research" intent 10 times (triggers learning again)
    for i in range(10):
        result = await organism.execute_intent(
            intent="research.topic",
            params={"topic": f"test_{i}"},
            context={},
        )
        assert result["success"], f"Intent {i} failed"

    assert organism._execution_count == 20

    # Check Grove utility improved
    updated_grove_utility = stigmergy.game_model.get_colony_utility("grove")
    assert updated_grove_utility is not None
    assert (
        updated_grove_utility.success_rate >= initial_grove_rate
    ), "Grove utility should improve with good patterns"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_pattern_retrieval() -> None:
    """Test that receipt patterns can be retrieved via get_patterns()."""
    stigmergy = get_stigmergy_learner()

    # Clear existing patterns
    stigmergy.patterns.clear()

    # Add test patterns
    pattern1 = ReceiptPattern(
        action="test.action1",
        domain="forge",
        success_count=5,
        failure_count=1,
    )
    pattern2 = ReceiptPattern(
        action="test.action2",
        domain="grove",
        success_count=3,
        failure_count=3,
    )
    pattern3 = ReceiptPattern(
        action="other.action",
        domain="spark",
        success_count=2,
        failure_count=0,
    )

    stigmergy.patterns[("test.action1", "forge")] = pattern1
    stigmergy.patterns[("test.action2", "grove")] = pattern2
    stigmergy.patterns[("other.action", "spark")] = pattern3

    # Retrieve all patterns
    all_receipts = stigmergy.get_patterns(intent_type=None, limit=100)
    assert len(all_receipts) == 3

    # Retrieve filtered patterns
    test_receipts = stigmergy.get_patterns(intent_type="test", limit=100)
    assert len(test_receipts) == 2

    # Verify receipt format
    receipt = test_receipts[0]
    assert "intent" in receipt
    assert "action" in receipt["intent"]
    assert "actor" in receipt
    assert "verifier" in receipt
    assert "status" in receipt["verifier"]
    assert "success_count" in receipt
    assert "failure_count" in receipt


@pytest.mark.integration
@pytest.mark.asyncio
async def test_colony_utility_update() -> None:
    """Test that colony utilities update correctly from receipt learning."""
    from kagami.core.unified_agents.memory.stigmergy import ColonyGameModel

    game_model = ColonyGameModel()

    # Get initial Forge utility
    forge = game_model.get_colony_utility("forge")
    assert forge is not None

    initial_rate = forge.success_rate
    initial_cost = forge.resource_cost

    # Positive update (colony performed well)
    game_model.update_utility("forge", delta=0.3)

    # Success rate should increase
    assert forge.success_rate > initial_rate
    assert forge.success_rate <= 1.0

    # Resource cost should decrease (better performance → lower cost)
    assert forge.resource_cost < initial_cost

    # Negative update (colony underperformed)
    game_model.update_utility("forge", delta=-0.4)

    # Success rate should decrease
    assert forge.success_rate < initial_rate + 0.03  # (0.3 * 0.1)

    # Resource cost should increase
    assert forge.resource_cost > initial_cost * 0.95


@pytest.mark.integration
@pytest.mark.asyncio
async def test_learning_frequency_control() -> None:
    """Test that learning triggers at correct frequency."""
    config = OrganismConfig()
    organism = UnifiedOrganism(config=config)
    organism._learning_frequency = 5  # Learn every 5 executions

    # Mock the learning method to count calls
    call_count = 0

    async def mock_learning(intent: str):
        nonlocal call_count
        call_count += 1

    organism._trigger_receipt_learning = mock_learning  # type: ignore[method-assign]

    # Execute 15 intents
    for _i in range(15):
        await organism.execute_intent(
            intent="test.action",
            params={},
            context={},
        )

    # Learning should have triggered 3 times (at 5, 10, 15)
    assert call_count == 3
    assert organism._execution_count == 15


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_learning_with_no_patterns() -> None:
    """Test that learning handles empty pattern sets gracefully."""
    config = OrganismConfig()
    organism = UnifiedOrganism(config=config)
    organism._learning_frequency = 1  # Learn every execution

    stigmergy = get_stigmergy_learner()
    stigmergy.patterns.clear()  # No patterns

    # Should not crash
    result = await organism.execute_intent(
        intent="unknown.action",
        params={},
        context={},
    )

    assert result["success"]

    assert organism._execution_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_learning_improves_routing() -> None:
    """Test that receipt learning improves routing decisions over time.

    This is the KEY integration test: does the loop actually close?
    """
    config = OrganismConfig()
    organism = UnifiedOrganism(config=config)
    organism._learning_frequency = 5

    stigmergy = get_stigmergy_learner()
    stigmergy.patterns.clear()

    # Seed pattern: "build" tasks succeed with Forge
    for _ in range(20):
        pattern = ReceiptPattern(
            action="build.feature",
            domain="forge",
            success_count=9,
            failure_count=1,
        )
        stigmergy.patterns[("build.feature", "forge")] = pattern

    # Execute "build" tasks and verify Forge gets selected
    forge_selections = 0
    total_executions = 10

    for i in range(total_executions):
        result = await organism.execute_intent(
            intent="build.feature",
            params={"iteration": i},
            context={},
        )

        # Check routing result
        if result["success"]:
            # Routing should prefer Forge for "build" tasks
            # (either single or as primary in Fano line)
            routing = organism._router.route("build.feature", {}, context={})
            if routing.actions[0].colony_name == "forge":
                forge_selections += 1

    # At least 50% of routings should select Forge as primary
    # (conservative threshold since complexity inference can vary)
    assert (
        forge_selections >= total_executions * 0.5
    ), f"Forge selected {forge_selections}/{total_executions} times"
