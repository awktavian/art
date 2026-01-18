"""Tests for kagami.core.memory.consolidation."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.memory.consolidation import MemoryConsolidation, get_memory_consolidation


@pytest.mark.tier_unit
class TestMemoryConsolidation:
    """Test MemoryConsolidation class."""

    def test_consolidation_initialization(self) -> None:
        """Test consolidation initialization."""
        consolidation = MemoryConsolidation()

        assert consolidation._consolidation_history == []
        assert consolidation._cleanup_interval == 7200.0
        assert consolidation._room_subscription_active is False

    @pytest.mark.asyncio
    async def test_consolidate_memories_insufficient_data(self) -> None:
        """Test consolidation with insufficient data."""
        consolidation = MemoryConsolidation()

        result = await consolidation.consolidate_memories()

        assert result["status"] == "insufficient_data"
        assert result["experiences"] < 5

    def test_cleanup_internal_state(self) -> None:
        """Test cleanup removes old history."""
        consolidation = MemoryConsolidation()

        consolidation._consolidation_history = [{"id": i} for i in range(200)]

        stats = consolidation._cleanup_internal_state()

        assert stats["history_removed"] == 100
        assert stats["history_remaining"] == 100
        assert len(consolidation._consolidation_history) == 100

    def test_cleanup_no_removal_needed(self) -> None:
        """Test cleanup when under limit."""
        consolidation = MemoryConsolidation()

        consolidation._consolidation_history = [{"id": i} for i in range(50)]

        stats = consolidation._cleanup_internal_state()

        assert stats["history_removed"] == 0
        assert stats["history_remaining"] == 50

    def test_singleton_pattern(self) -> None:
        """Test singleton accessor."""
        consolidation1 = get_memory_consolidation()
        consolidation2 = get_memory_consolidation()

        assert consolidation1 is consolidation2

    @pytest.mark.asyncio
    async def test_subscribe_to_room_events_idempotent(self) -> None:
        """Test that subscribing multiple times is safe."""
        consolidation = MemoryConsolidation()

        consolidation._room_subscription_active = True

        await consolidation.subscribe_to_room_events()

        assert consolidation._room_subscription_active is True
