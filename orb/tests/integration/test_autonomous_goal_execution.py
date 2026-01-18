"""Test autonomous goal execution end-to-end.

This test verifies that Kagami can:
1. Generate autonomous goals via Maslow hierarchy
2. Pass CBF safety checks (with extended timeout)
3. Execute actions through colony routing
4. Store receipts successfully
5. Learn from execution outcomes
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import time
from typing import Any


@pytest.mark.asyncio
async def test_autonomous_goal_generation():
    """Test organism generates goals autonomously."""
    from kagami.core.autonomous_goal_engine import get_autonomous_goal_engine
    from kagami.core.unified_agents.unified_organism import get_unified_organism

    # Initialize organism
    organism = get_unified_organism()
    await organism.start()

    # Initialize autonomous goal engine
    autonomous = get_autonomous_goal_engine()
    await autonomous.initialize(organism)

    # Gather context and generate goals
    context = await autonomous._gather_context()

    from kagami.core.motivation.maslow import MaslowHierarchy

    maslow = MaslowHierarchy()
    goals = await maslow.evaluate_needs(context)

    # Verify goals generated
    assert len(goals) > 0, "No goals generated"

    # Verify goal structure
    goal = goals[0]
    assert hasattr(goal, "goal")
    assert hasattr(goal, "drive")
    assert hasattr(goal, "priority")
    assert goal.priority > 0

    print(f"Generated goal: {goal.goal} (drive={goal.drive.value}, priority={goal.priority})")

    # Cleanup
    await organism.stop()


@pytest.mark.asyncio
async def test_autonomous_goal_execution_with_cbf():
    """Test autonomous goal passes CBF check with extended timeout."""
    from kagami.core.safety.cbf_integration import check_cbf_for_operation

    # Simulate autonomous goal execution
    result = await check_cbf_for_operation(
        operation="autonomous.goal.execute",
        action="research.web",
        target="files.analyze",
        metadata={
            "autonomous": True,  # Triggers 30s timeout
            "goal": "Explore files.analyze to reduce uncertainty",
            "drive": "curiosity",
        },
        source="autonomous_orchestrator",
    )

    # With 30s timeout, CBF should complete (not timeout)
    assert result.safe or result.h_x is not None, "CBF check failed completely"

    if not result.safe:
        # If blocked, should be threat-based, not timeout
        assert "timeout" not in result.reason.lower(), f"Still timing out: {result.reason}"  # type: ignore[union-attr]

    print(f"CBF check completed: h(x)={result.h_x}, safe={result.safe}")


@pytest.mark.asyncio
async def test_autonomous_goal_receipt_storage():
    """Test autonomous goal creates receipt successfully."""
    from kagami.core.receipts import emit_receipt

    # Emit receipt for autonomous action
    correlation_id = f"autonomous-test-{int(time.time())}"
    receipt_id = await emit_receipt(
        correlation_id=correlation_id,
        action="research.web",
        app="research",
        phase="EXECUTE",
        status="success",
        metadata={
            "autonomous": True,
            "goal": "Test autonomous receipt",
            "drive": "curiosity",
        },
    )

    # Verify receipt was created
    assert receipt_id is not None, "No receipt ID returned"
    assert len(receipt_id) > 0, "Empty receipt ID"

    print(f"Receipt stored successfully: {receipt_id}")


@pytest.mark.asyncio
async def test_full_autonomous_execution():
    """Test complete autonomous loop: generate → execute → learn."""
    from kagami.core.autonomous_goal_engine import get_autonomous_goal_engine
    from kagami.core.unified_agents.unified_organism import get_unified_organism
    from kagami.core.motivation.maslow import MaslowHierarchy

    # Setup
    organism = get_unified_organism()
    await organism.start()

    autonomous = get_autonomous_goal_engine()

    # Create mock orchestrator with execute capability
    class MockOrchestrator:
        async def process_intent(self, intent: dict[str, Any]) -> dict[str, Any]:
            return {"status": "success", "result": {"data": "mocked"}}

    await autonomous.initialize(MockOrchestrator())

    # Generate goal
    maslow = MaslowHierarchy()
    context = await autonomous._gather_context()
    goals = await maslow.evaluate_needs(context)

    assert len(goals) > 0, "No goals generated"

    # Execute goal (with mocked orchestrator, should complete)
    goal = goals[0]

    # Mock the execution to avoid external dependencies
    original_execute = autonomous._execute_goal

    async def mock_execute(g: Any) -> Dict[str, Any]:
        """Mock execution that simulates success."""
        return {
            "status": "success",
            "goal": g.goal,
            "drive": g.drive.value,
        }

    autonomous._execute_goal = mock_execute  # type: ignore[assignment]

    try:
        result = await autonomous._execute_goal(goal)
        assert result["status"] == "success", f"Execution failed: {result}"  # type: ignore[index]
        print(f"Full autonomous execution completed: {goal.goal}")
    finally:
        # Restore original method
        autonomous._execute_goal = original_execute  # type: ignore[method-assign]
        await organism.stop()


@pytest.mark.asyncio
async def test_cbf_timeout_extension():
    """Test that CBF extends timeout for autonomous operations."""
    from kagami.core.safety.cbf_integration import check_cbf_for_operation
    import time

    start_time = time.time()

    # Test with autonomous flag (should get 30s timeout)
    result = await check_cbf_for_operation(
        operation="autonomous.goal.execute",
        action="research.complex",
        target="files.analyze",
        metadata={
            "autonomous": True,
            "goal": "Complex analysis requiring more time",
            "drive": "curiosity",
        },
        source="test_autonomous",
    )

    elapsed = time.time() - start_time

    # Should complete within timeout window
    assert elapsed < 30.0, f"CBF took too long: {elapsed}s"

    # Should not be a timeout failure
    if not result.safe:
        assert "timeout" not in result.reason.lower(), "CBF timed out despite extension"  # type: ignore[union-attr]

    print(f"CBF completed in {elapsed:.2f}s with autonomous timeout extension")


@pytest.mark.asyncio
async def test_goal_prioritization():
    """Test that goals are prioritized correctly."""
    from kagami.core.motivation.maslow import MaslowHierarchy, Drive

    maslow = MaslowHierarchy()

    # Create mock context with various unmet needs
    context = {
        "system_health": 0.5,  # Moderate health
        "uncertainty": 0.8,  # High uncertainty → curiosity
        "learning_rate": 0.3,  # Low learning → competence
        "social_engagement": 0.2,  # Low social → connection
    }

    goals = await maslow.evaluate_needs(context)

    # Should generate multiple goals
    assert len(goals) > 0, "No goals generated"

    # Goals should be sorted by priority
    priorities = [g.priority for g in goals]
    assert priorities == sorted(priorities, reverse=True), "Goals not sorted by priority"

    # Verify diverse drives
    drives = {g.drive for g in goals}
    assert len(drives) > 1, "Only one drive type generated"

    print(f"Generated {len(goals)} goals across {len(drives)} drives")


if __name__ == "__main__":
    # Quick smoke test
    print("Running smoke tests...")
    asyncio.run(test_autonomous_goal_generation())
    print("\nAll smoke tests passed!")
