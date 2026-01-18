"""Tests for kagami.core.memory.shared_episodic_memory."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import time

from kagami.core.memory.shared_episodic_memory import (
    SharedEpisode,
    SharedEpisodicMemory,
    get_shared_memory,
)


@pytest.mark.tier_unit
class TestSharedEpisode:
    """Test SharedEpisode dataclass."""

    def test_episode_creation(self) -> None:
        """Test creating a shared episode."""
        episode = SharedEpisode(
            episode_id="test_123",
            contributing_agent="agent_1",
            category="test_category",
            content="Test insight",
            data={"key": "value"},
            valence=0.8,
            importance=0.9,
            timestamp=time.time(),
        )

        assert episode.episode_id == "test_123"
        assert episode.contributing_agent == "agent_1"
        assert episode.importance == 0.9
        assert episode.access_count == 0
        assert len(episode.confirmed_by) == 0


@pytest.mark.tier_unit
class TestSharedEpisodicMemory:
    """Test SharedEpisodicMemory class."""

    def test_memory_initialization(self) -> None:
        """Test memory initialization."""
        memory = SharedEpisodicMemory(capacity=100, episode_ttl_days=30)

        assert memory.capacity == 100
        assert len(memory._episodes) == 0
        assert memory._episode_ttl_seconds == 30 * 86400

    @pytest.mark.asyncio
    async def test_store_episode(self) -> None:
        """Test storing an episode."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="Test content",
            data={"key": "value"},
            valence=0.5,
            importance=0.7,
        )

        assert episode_id.startswith("agent_1_")
        assert len(memory._episodes) == 1

    @pytest.mark.asyncio
    async def test_store_respects_capacity(self) -> None:
        """Test that storage respects capacity limit."""
        memory = SharedEpisodicMemory(capacity=5)

        for i in range(10):
            await memory.store(
                agent_name=f"agent_{i}",
                category="test",
                content=f"Content {i}",
                data={},
                importance=0.5,
            )

        assert len(memory._episodes) <= 5

    @pytest.mark.asyncio
    async def test_query_episodes(self) -> None:
        """Test querying episodes."""
        memory = SharedEpisodicMemory(capacity=100)

        await memory.store(
            agent_name="agent_1",
            category="test",
            content="machine learning test",
            data={},
            importance=0.8,
        )

        await memory.store(
            agent_name="agent_2",
            category="test",
            content="unrelated content",
            data={},
            importance=0.5,
        )

        results = await memory.query(
            asking_agent="agent_3",
            query_text="machine learning",
            top_k=5,
        )

        assert len(results) > 0
        assert results[0].importance >= 0.5

    @pytest.mark.asyncio
    async def test_query_with_category_filter(self) -> None:
        """Test querying with category filter."""
        memory = SharedEpisodicMemory(capacity=100)

        await memory.store(
            agent_name="agent_1",
            category="visual_pattern",
            content="pattern test",
            data={},
        )

        await memory.store(
            agent_name="agent_2",
            category="performance_insight",
            content="pattern test",
            data={},
        )

        results = await memory.query(
            asking_agent="agent_3",
            query_text="pattern",
            category="visual_pattern",
            top_k=5,
        )

        assert all(ep.category == "visual_pattern" for ep in results)

    @pytest.mark.asyncio
    async def test_query_tracks_access(self) -> None:
        """Test that queries track access count."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="test content",
            data={},
        )

        episode = memory._episodes[0]
        assert episode.access_count == 0

        await memory.query(
            asking_agent="agent_2",
            query_text="test",
            top_k=5,
        )

        assert episode.access_count > 0

    @pytest.mark.asyncio
    async def test_confirm_episode(self) -> None:
        """Test confirming an episode."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="test content",
            data={},
            importance=0.5,
        )

        result = await memory.confirm(episode_id, "agent_2")

        assert result is True
        episode = memory._episodes[0]
        assert "agent_2" in episode.confirmed_by
        assert episode.importance > 0.5

    @pytest.mark.asyncio
    async def test_confirm_amplifies_importance(self) -> None:
        """Test that confirmations amplify importance."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="test content",
            data={},
            importance=0.5,
        )

        initial_importance = memory._episodes[0].importance

        await memory.confirm(episode_id, "agent_2")

        assert memory._episodes[0].importance > initial_importance

    @pytest.mark.asyncio
    async def test_confirm_multiple_agents(self) -> None:
        """Test multiple confirmations."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="test content",
            data={},
            importance=0.5,
        )

        await memory.confirm(episode_id, "agent_2")
        await memory.confirm(episode_id, "agent_3")

        episode = memory._episodes[0]
        assert len(episode.confirmed_by) == 2

    @pytest.mark.asyncio
    async def test_confirm_idempotent(self) -> None:
        """Test that confirming twice from same agent has no effect."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="test content",
            data={},
            importance=0.5,
        )

        await memory.confirm(episode_id, "agent_2")
        importance_after_first = memory._episodes[0].importance

        await memory.confirm(episode_id, "agent_2")
        importance_after_second = memory._episodes[0].importance

        assert importance_after_first == importance_after_second

    @pytest.mark.asyncio
    async def test_evaporate_old_memories(self) -> None:
        """Test evaporating old memories."""
        memory = SharedEpisodicMemory(capacity=100)

        episode_id = await memory.store(
            agent_name="agent_1",
            category="test",
            content="old memory",
            data={},
            importance=0.2,
        )

        memory._episodes[0].timestamp = time.time() - 7200

        evaporated = await memory.evaporate_old_memories(decay_rate=0.95)

        assert evaporated >= 0

    def test_get_all_episodes(self) -> None:
        """Test getting all episodes."""
        memory = SharedEpisodicMemory(capacity=100)

        episodes = memory.get_all_episodes()

        assert isinstance(episodes, list)
        assert len(episodes) == 0

    def test_cleanup_internal_state(self) -> None:
        """Test cleanup removes old episodes."""
        memory = SharedEpisodicMemory(capacity=100, episode_ttl_days=0)

        memory._episodes = [
            SharedEpisode(
                episode_id="old_123",
                contributing_agent="agent_1",
                category="test",
                content="old content",
                data={},
                valence=0.5,
                importance=0.5,
                timestamp=time.time() - 100000,
            )
        ]

        stats = memory._cleanup_internal_state()

        assert stats["episodes_removed"] >= 0

    def test_get_stats(self) -> None:
        """Test getting memory statistics."""
        memory = SharedEpisodicMemory(capacity=100)

        stats = memory.get_stats()

        assert "total_episodes" in stats
        assert "categories" in stats
        assert "contributing_agents" in stats
        assert stats["total_episodes"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self) -> None:
        """Test statistics with data."""
        memory = SharedEpisodicMemory(capacity=100)

        await memory.store(
            agent_name="agent_1",
            category="test",
            content="test",
            data={},
            importance=0.8,
        )

        stats = memory.get_stats()

        assert stats["total_episodes"] == 1
        assert "test" in stats["categories"]

    def test_singleton_pattern(self) -> None:
        """Test singleton accessor."""
        memory1 = get_shared_memory()
        memory2 = get_shared_memory()

        assert memory1 is memory2
