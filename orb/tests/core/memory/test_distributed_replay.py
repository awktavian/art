"""Tests for kagami.core.memory.distributed_replay."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.memory.distributed_replay import DistributedExperience, DistributedReplayBuffer


@pytest.mark.tier_unit
class TestDistributedExperience:
    """Test DistributedExperience dataclass."""

    def test_experience_creation(self) -> None:
        """Test creating a distributed experience."""
        exp = DistributedExperience(
            context={"action": "move"},
            action={"type": "navigate"},
            outcome={"status": "success"},
            valence=0.8,
            importance=0.9,
        )

        assert exp.context == {"action": "move"}
        assert exp.action == {"type": "navigate"}
        assert exp.valence == 0.8
        assert exp.importance == 0.9


@pytest.mark.tier_unit
class TestDistributedReplayBuffer:
    """Test DistributedReplayBuffer class."""

    def test_buffer_initialization(self) -> None:
        """Test buffer initialization without database."""
        buffer = DistributedReplayBuffer(db_session=None, capacity=1000)

        assert buffer.capacity == 1000
        assert buffer._initialized is False

    def test_add_experience_no_db(self) -> None:
        """Test adding experience when no database is available."""
        buffer = DistributedReplayBuffer(db_session=None, capacity=1000)

        exp = DistributedExperience(
            context={"action": "test"},
            action={"type": "test"},
            outcome={"status": "ok"},
            valence=0.5,
            importance=0.5,
        )

        buffer.add(exp)

    def test_get_replay_stats_no_db(self) -> None:
        """Test getting stats when no database is available."""
        buffer = DistributedReplayBuffer(db_session=None, capacity=1000)

        stats = buffer.get_replay_stats()

        assert "size" in stats
        assert "avg_importance" in stats
        assert stats["size"] == 0
