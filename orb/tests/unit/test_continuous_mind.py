"""Unit tests for Continuous Mind system."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio

from kagami.core.continuous import (
    ContinuousMind,
    Goal,
    SharedWorkingMemory,
    Thought,
    ThoughtType,
)


@pytest.mark.unit
def test_shared_working_memory_storage():
    """Test that working memory stores and retrieves correctly."""
    memory = SharedWorkingMemory(max_size_mb=10)

    # Store value
    memory.store("test_key", "test_value")

    # Retrieve
    value = memory.retrieve("test_key")
    assert value == "test_value"


@pytest.mark.unit
def test_working_memory_lru_eviction():
    """Test that LRU eviction works when memory full."""
    memory = SharedWorkingMemory(max_size_mb=0.001)  # Very small (1KB)  # type: ignore[arg-type]

    # Store multiple values (will exceed limit)
    memory.store("key1", "value1" * 1000)  # Large value
    memory.store("key2", "value2" * 1000)

    # First key should be evicted
    assert memory.retrieve("key1") is None
    assert memory.retrieve("key2") is not None


@pytest.mark.unit
def test_working_memory_persistence(tmp_path: Any) -> None:
    """Test save/load to disk."""
    persist_path = tmp_path / "working_memory.json"

    # Create memory and store data
    memory1 = SharedWorkingMemory(max_size_mb=10, persist_path=str(persist_path))
    memory1.store("persistent_key", "persistent_value")

    # Save
    memory1.save_to_disk()

    # Create new instance (simulating restart)
    memory2 = SharedWorkingMemory(max_size_mb=10, persist_path=str(persist_path))

    # Should load from disk
    assert memory2.retrieve("persistent_key") == "persistent_value"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_continuous_mind_goal_submission():
    """Test submitting goals to continuous mind."""
    mind = ContinuousMind()

    goal = Goal(
        id="test_goal_1",
        description="Test goal description",
        priority=0.8,
        source="user",
        context={},
    )

    # Submit goal
    await mind.submit_goal(goal)

    # Queue should have goal
    assert mind._goal_queue.qsize() == 1


@pytest.mark.unit
def test_continuous_mind_stats():
    """Test getting mind statistics."""
    mind = ContinuousMind()

    stats = mind.get_stats()

    assert "running" in stats
    assert "thoughts_count" in stats
    assert "working_memory" in stats
    assert not stats["running"]  # Not started yet


@pytest.mark.unit
@pytest.mark.asyncio
async def test_continuous_mind_start_stop():
    """Test starting and stopping continuous mind."""
    mind = ContinuousMind()

    # Start in background
    task = asyncio.create_task(mind.run_forever())

    # Let it run briefly
    await asyncio.sleep(0.1)

    assert mind._running

    # Stop
    mind.stop()
    await asyncio.sleep(0.1)

    assert not mind._running

    # Cancel task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.unit
def test_thought_creation():
    """Test creating thought objects."""
    thought = Thought(
        id="test_thought_1",
        type=ThoughtType.USER_REQUEST,
        content="What is AI safety?",
        context={},
        priority=0.9,
    )

    assert thought.id == "test_thought_1"
    assert thought.conclusion is None
    assert not thought.actionable
    assert thought.confidence == 0.5


@pytest.mark.unit
def test_goal_creation():
    """Test creating goal objects."""
    goal = Goal(
        id="test_goal_1",
        description="Research topic X",
        priority=0.7,
        source="intrinsic",
        context={"drive": "curiosity"},
    )

    assert goal.id == "test_goal_1"
    assert goal.progress == 0.0
    assert not goal.completed
