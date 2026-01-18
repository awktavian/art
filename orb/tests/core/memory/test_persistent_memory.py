"""Tests for kagami.core.memory.persistent_memory."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from datetime import datetime, timedelta

from kagami.core.memory.persistent_memory import (
    PersistentMemory,
    get_persistent_memory,
    reset_persistent_memory,
)


@pytest.mark.tier_unit
class TestPersistentMemory:
    """Test PersistentMemory class."""

    def setup_method(self) -> None:
        """Reset persistent memory before each test."""
        reset_persistent_memory()

    def test_memory_initialization(self) -> None:
        """Test memory initialization."""
        memory = PersistentMemory(agent_id="test_agent")

        assert memory.agent_id == "test_agent"
        assert memory._vector_store is None
        assert memory._sql_db is None

    def test_memory_initialization_default_agent(self) -> None:
        """Test memory initialization with default agent."""
        memory = PersistentMemory()

        assert memory.agent_id == "organism"

    @pytest.mark.asyncio
    async def test_remember_basic_event(self) -> None:
        """Test remembering a basic event."""
        memory = PersistentMemory(agent_id="test_agent")

        event = {
            "id": "test_123",
            "timestamp": datetime.now(),
            "description": "Test event",
            "data": {"key": "value"},
            "type": "test",
        }

        await memory.remember(event)

    @pytest.mark.asyncio
    async def test_store_event_compatibility(self) -> None:
        """Test store_event compatibility wrapper."""
        memory = PersistentMemory(agent_id="test_agent")

        await memory.store_event(
            event_type="test",
            description="Test description",
            data={"key": "value"},
        )

    @pytest.mark.asyncio
    async def test_recall_no_results(self) -> None:
        """Test recalling with no matching results."""
        memory = PersistentMemory(agent_id="test_agent")

        results = await memory.recall("nonexistent query", k=5)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_recall_temporal(self) -> None:
        """Test temporal recall."""
        memory = PersistentMemory(agent_id="test_agent")

        start = datetime.now() - timedelta(days=7)
        end = datetime.now()

        results = await memory.recall_temporal(start, end)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_recall_temporal_with_type(self) -> None:
        """Test temporal recall with event type filter."""
        memory = PersistentMemory(agent_id="test_agent")

        start = datetime.now() - timedelta(days=7)
        end = datetime.now()

        results = await memory.recall_temporal(start, end, event_type="test")

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_recall_recent(self) -> None:
        """Test recalling recent memories."""
        memory = PersistentMemory(agent_id="test_agent")

        results = await memory.recall_recent(hours=24, limit=50)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_create_embedding(self) -> None:
        """Test creating an embedding."""
        memory = PersistentMemory(agent_id="test_agent")

        embedding = await memory._create_embedding("test text")

        assert embedding is not None
        assert hasattr(embedding, "__len__") or hasattr(embedding, "shape")

    def test_get_statistics(self) -> None:
        """Test getting memory statistics."""
        memory = PersistentMemory(agent_id="test_agent")

        stats = memory.get_statistics()

        assert "agent_id" in stats
        assert stats["agent_id"] == "test_agent"

    def test_singleton_pattern(self) -> None:
        """Test singleton accessor."""
        memory1 = get_persistent_memory("test_agent")
        memory2 = get_persistent_memory("test_agent")

        assert memory1 is memory2

    def test_singleton_different_agents(self) -> None:
        """Test singleton with different agent IDs."""
        memory1 = get_persistent_memory("agent_1")
        memory2 = get_persistent_memory("agent_2")

        assert memory1 is not memory2
        assert memory1.agent_id == "agent_1"
        assert memory2.agent_id == "agent_2"

    def test_reset_persistent_memory_all(self) -> None:
        """Test resetting all persistent memories."""
        get_persistent_memory("agent_1")
        get_persistent_memory("agent_2")

        reset_persistent_memory()

        from kagami.core.memory.persistent_memory import _PERSISTENT_MEMORIES

        assert len(_PERSISTENT_MEMORIES) == 0

    def test_reset_persistent_memory_specific(self) -> None:
        """Test resetting specific agent memory."""
        get_persistent_memory("agent_1")
        get_persistent_memory("agent_2")

        reset_persistent_memory("agent_1")

        from kagami.core.memory.persistent_memory import _PERSISTENT_MEMORIES

        assert "agent_1" not in _PERSISTENT_MEMORIES
        assert "agent_2" in _PERSISTENT_MEMORIES
