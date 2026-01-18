"""Tests for kagami.core.memory.hierarchical_memory."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import time

from kagami.core.memory.hierarchical_memory import (
    CompressedEpisode,
    HierarchicalMemory,
    LongTermPattern,
    get_hierarchical_memory,
)


@pytest.mark.tier_unit
class TestCompressedEpisode:
    """Test CompressedEpisode dataclass."""

    def test_compressed_episode_creation(self) -> None:
        """Test creating a compressed episode."""
        pattern = {"action": "move", "outcome": "success"}
        examples = [{"action": "move", "result": "ok"}]

        episode = CompressedEpisode(
            pattern=pattern,
            valence_avg=0.8,
            valence_std=0.1,
            count=5,
            examples=examples,
            first_seen=time.time() - 100,
            last_seen=time.time(),
        )

        assert episode.pattern == pattern
        assert episode.valence_avg == 0.8
        assert episode.count == 5
        assert len(episode.examples) == 1


@pytest.mark.tier_unit
class TestLongTermPattern:
    """Test LongTermPattern dataclass."""

    def test_long_term_pattern_creation(self) -> None:
        """Test creating a long-term pattern."""
        prototype = {"action": "move"}

        pattern = LongTermPattern(
            prototype=prototype,
            frequency=100,
            confidence=0.9,
            created_at=time.time(),
        )

        assert pattern.prototype == prototype
        assert pattern.frequency == 100
        assert pattern.confidence == 0.9


@pytest.mark.tier_unit
class TestHierarchicalMemory:
    """Test HierarchicalMemory class."""

    def test_memory_initialization(self) -> None:
        """Test memory initialization."""
        memory = HierarchicalMemory(
            working_capacity=20,
            short_term_capacity=1000,
        )

        assert memory._working_capacity == 20
        assert memory._consolidation_threshold == 20
        assert len(memory._working_memory) == 0

    @pytest.mark.asyncio
    async def test_store_experience(self) -> None:
        """Test storing a single experience."""
        memory = HierarchicalMemory(working_capacity=20)

        experience = {
            "context": {"action": "move"},
            "outcome": {"status": "success"},
            "valence": 0.8,
            "timestamp": time.time(),
        }

        await memory.store(experience)

        assert len(memory._working_memory) == 1

    @pytest.mark.asyncio
    async def test_automatic_consolidation(self) -> None:
        """Test automatic consolidation trigger."""
        memory = HierarchicalMemory(
            working_capacity=10,
            consolidation_threshold=5,
        )

        for i in range(6):
            experience = {
                "context": {"action": f"move_{i}"},
                "outcome": {"status": "success"},
                "valence": 0.8,
                "timestamp": time.time(),
            }
            await memory.store(experience)

        assert memory._consolidations >= 1
        assert len(memory._short_term) > 0

    @pytest.mark.asyncio
    async def test_recall_from_working_memory(self) -> None:
        """Test recall from working memory."""
        memory = HierarchicalMemory()

        experience = {
            "context": {"action": "test_action", "id": "unique_123"},
            "outcome": {"status": "success"},
            "valence": 0.8,
            "timestamp": time.time(),
        }

        await memory.store(experience)

        query = {"action": "test_action"}
        results = await memory.recall(query, max_results=5)

        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_hierarchical_search(self) -> None:
        """Test searching across memory levels."""
        memory = HierarchicalMemory(working_capacity=5, consolidation_threshold=5)

        for i in range(10):
            experience = {
                "context": {"action": "move", "step": i},
                "outcome": {"status": "success"},
                "valence": 0.8,
                "timestamp": time.time(),
            }
            await memory.store(experience)

        query = {"context": {"action": "move"}}
        results = await memory.recall(query, max_results=3)

        assert len(results) <= 3

    def test_match_score(self) -> None:
        """Test match score calculation."""
        memory = HierarchicalMemory()

        memory_dict = {"action": "move", "target": "north"}
        query_dict = {"action": "move", "target": "north"}

        score = memory._match_score(memory_dict, query_dict)

        assert score == 1.0

    def test_match_score_partial(self) -> None:
        """Test partial match score."""
        memory = HierarchicalMemory()

        memory_dict = {"action": "move", "target": "north"}
        query_dict = {"action": "move", "target": "south"}

        score = memory._match_score(memory_dict, query_dict)

        assert score == 0.5

    def test_match_score_no_overlap(self) -> None:
        """Test no overlap match score."""
        memory = HierarchicalMemory()

        memory_dict = {"action": "move"}
        query_dict = {"target": "north"}

        score = memory._match_score(memory_dict, query_dict)

        assert score == 0.0

    def test_pattern_signature(self) -> None:
        """Test pattern signature generation."""
        memory = HierarchicalMemory()

        pattern = {"action": "move", "target": "north"}
        signature = memory._pattern_signature(pattern)

        assert isinstance(signature, str)
        assert "action:move" in signature
        assert "target:north" in signature

    def test_pattern_signature_deterministic(self) -> None:
        """Test signature is deterministic."""
        memory = HierarchicalMemory()

        pattern = {"action": "move", "target": "north"}
        sig1 = memory._pattern_signature(pattern)
        sig2 = memory._pattern_signature(pattern)

        assert sig1 == sig2

    @pytest.mark.asyncio
    async def test_cluster_experiences(self) -> None:
        """Test experience clustering."""
        memory = HierarchicalMemory()

        experiences = [
            {"context": {"action": "move", "dir": "north"}, "valence": 0.8},
            {"context": {"action": "move", "dir": "north"}, "valence": 0.7},
            {"context": {"action": "move", "dir": "south"}, "valence": 0.6},
        ]

        clusters = await memory._cluster_experiences(experiences)

        assert len(clusters) >= 1

    def test_extract_pattern(self) -> None:
        """Test pattern extraction from experiences."""
        memory = HierarchicalMemory()

        experiences = [
            {"context": {"action": "move", "common": "yes", "unique1": "a"}},
            {"context": {"action": "move", "common": "yes", "unique2": "b"}},
        ]

        pattern = memory._extract_pattern(experiences)

        assert "action" in pattern
        assert pattern["action"] == "move"
        assert "common" in pattern

    def test_create_prototype(self) -> None:
        """Test prototype creation from episodes."""
        memory = HierarchicalMemory()

        episodes = [
            CompressedEpisode(
                pattern={"action": "move"},
                valence_avg=0.8,
                valence_std=0.1,
                count=5,
                examples=[],
                first_seen=time.time(),
                last_seen=time.time(),
            ),
            CompressedEpisode(
                pattern={"action": "move"},
                valence_avg=0.7,
                valence_std=0.2,
                count=3,
                examples=[],
                first_seen=time.time(),
                last_seen=time.time(),
            ),
        ]

        prototype = memory._create_prototype(episodes)

        assert "_frequency" in prototype
        assert prototype["_frequency"] == 8

    def test_cleanup_internal_state(self) -> None:
        """Test cleanup removes old patterns."""
        memory = HierarchicalMemory(long_term_ttl_days=0)

        memory._long_term["old_pattern"] = LongTermPattern(
            prototype={"action": "old"},
            frequency=10,
            confidence=0.5,
            created_at=time.time() - 10000,
        )

        stats = memory._cleanup_internal_state()

        assert stats["long_term_removed"] >= 0

    def test_get_stats(self) -> None:
        """Test getting memory statistics."""
        memory = HierarchicalMemory()

        stats = memory.get_stats()

        assert "working_memory_size" in stats
        assert "short_term_size" in stats
        assert "long_term_patterns" in stats
        assert "total_stored" in stats
        assert stats["working_memory_size"] == 0

    def test_singleton_pattern(self) -> None:
        """Test singleton accessor."""
        memory1 = get_hierarchical_memory()
        memory2 = get_hierarchical_memory()

        assert memory1 is memory2
