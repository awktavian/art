"""Tests for kagami.core.memory.types."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import time

from kagami.core.memory.types import Experience, MemorySnapshot, ReplayConfig


@pytest.mark.tier_unit
class TestExperience:
    """Test Experience dataclass."""

    def test_experience_creation(self) -> None:
        """Test creating an experience."""
        state = [1, 2, 3]
        action = {"type": "move"}
        exp = Experience(
            state=state,
            action=action,
            reward=1.0,
            next_state=[2, 3, 4],
            done=False,
            timestamp=time.time(),
        )

        assert exp.state == state
        assert exp.action == action
        assert exp.reward == 1.0
        assert exp.done is False
        assert exp.priority == 1.0

    def test_experience_with_metadata(self) -> None:
        """Test experience with metadata."""
        metadata = {"source": "test", "episode": 1}
        exp = Experience(
            state=[1],
            action={"move": 1},
            reward=1.0,
            next_state=[2],
            done=False,
            timestamp=time.time(),
            metadata=metadata,
        )

        assert exp.metadata == metadata
        assert exp.metadata["source"] == "test"

    def test_experience_with_priority(self) -> None:
        """Test experience with custom priority."""
        exp = Experience(
            state=[1],
            action={"move": 1},
            reward=1.0,
            next_state=[2],
            done=False,
            timestamp=time.time(),
            priority=2.5,
        )

        assert exp.priority == 2.5

    def test_experience_with_embedding(self) -> None:
        """Test experience with embedding."""
        embedding = [0.1, 0.2, 0.3]
        exp = Experience(
            state=[1],
            action={"move": 1},
            reward=1.0,
            next_state=[2],
            done=False,
            timestamp=time.time(),
            embedding=embedding,
        )

        assert exp.embedding == embedding


@pytest.mark.tier_unit
class TestMemorySnapshot:
    """Test MemorySnapshot dataclass."""

    def test_snapshot_creation(self) -> None:
        """Test creating a memory snapshot."""
        experiences = [
            Experience(
                state=[1],
                action={"move": 1},
                reward=1.0,
                next_state=[2],
                done=False,
                timestamp=time.time(),
            )
        ]
        snapshot = MemorySnapshot(
            experiences=experiences,
            metadata={"source": "test"},
            timestamp=time.time(),
            total_count=1,
        )

        assert len(snapshot.experiences) == 1
        assert snapshot.total_count == 1
        assert snapshot.metadata["source"] == "test"

    def test_snapshot_empty(self) -> None:
        """Test empty snapshot."""
        snapshot = MemorySnapshot(
            experiences=[],
            metadata={},
            timestamp=time.time(),
            total_count=0,
        )

        assert len(snapshot.experiences) == 0
        assert snapshot.total_count == 0


@pytest.mark.tier_unit
class TestReplayConfig:
    """Test ReplayConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default replay config."""
        config = ReplayConfig()

        assert config.capacity == 10000
        assert config.prioritized is True
        assert config.alpha == 0.6
        assert config.beta == 0.4
        assert config.beta_increment == 0.001
        assert config.min_priority == 1e-6

    def test_custom_config(self) -> None:
        """Test custom replay config."""
        config = ReplayConfig(
            capacity=50000,
            prioritized=False,
            alpha=0.8,
            beta=0.5,
        )

        assert config.capacity == 50000
        assert config.prioritized is False
        assert config.alpha == 0.8
        assert config.beta == 0.5

    def test_config_validation(self) -> None:
        """Test config with valid ranges."""
        config = ReplayConfig(
            alpha=0.0,
            beta=1.0,
            beta_increment=0.01,
        )

        assert config.alpha == 0.0
        assert config.beta == 1.0
        assert config.beta_increment == 0.01
