"""Tests for kagami.core.memory.unified_replay."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.memory.unified_replay import (
    UnifiedExperience,
    UnifiedReplayBuffer,
    UnifiedReplayConfig,
    create_goal_experience,
    create_rl_experience,
    create_tic_triplet,
    get_unified_replay,
    reset_unified_replay,
)


@pytest.mark.tier_unit
class TestUnifiedExperience:
    """Test UnifiedExperience dataclass."""

    def test_rl_experience_creation(self) -> None:
        """Test creating an RL experience."""
        exp = UnifiedExperience(
            experience_type="rl",
            state=torch.randn(8),
            action={"type": "move"},
            next_state=torch.randn(8),
            reward=1.0,
            done=False,
        )

        assert exp.experience_type == "rl"
        assert exp.reward == 1.0
        assert exp.done is False

    def test_tic_experience_creation(self) -> None:
        """Test creating a TIC experience."""
        exp = UnifiedExperience(
            experience_type="tic",
            tic_data={"task": "test"},
            plan_state=torch.randn(8),
            execute_state=torch.randn(8),
            verify_state=torch.randn(8),
            actual_success=True,
        )

        assert exp.experience_type == "tic"
        assert exp.actual_success is True

    def test_goal_experience_creation(self) -> None:
        """Test creating a goal-conditioned experience."""
        exp = UnifiedExperience(
            experience_type="goal",
            state=torch.randn(8),
            goal={"target": "A"},
            achieved_goal={"target": "B"},
            reward=0.5,
        )

        assert exp.experience_type == "goal"
        assert exp.goal == {"target": "A"}

    def test_to_dict_rl(self) -> None:
        """Test converting RL experience to dict."""
        exp = UnifiedExperience(
            experience_type="rl",
            reward=1.0,
            done=False,
        )

        data = exp.to_dict()

        assert data["experience_type"] == "rl"
        assert data["reward"] == 1.0
        assert data["done"] is False

    def test_to_dict_tic(self) -> None:
        """Test converting TIC experience to dict."""
        exp = UnifiedExperience(
            experience_type="tic",
            tic_data={"task": "test"},
            actual_success=True,
        )

        data = exp.to_dict()

        assert data["experience_type"] == "tic"
        assert data["actual_success"] is True


@pytest.mark.tier_unit
class TestUnifiedReplayConfig:
    """Test UnifiedReplayConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = UnifiedReplayConfig()

        assert config.capacity == 100_000
        assert config.alpha == 0.6
        assert config.replay_ratio == 16
        assert config.batch_size == 32

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = UnifiedReplayConfig(
            capacity=50000,
            alpha=0.8,
            replay_ratio=32,
        )

        assert config.capacity == 50000
        assert config.alpha == 0.8
        assert config.replay_ratio == 32


@pytest.mark.tier_unit
class TestUnifiedReplayBuffer:
    """Test UnifiedReplayBuffer class."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        reset_unified_replay()

    def test_buffer_initialization(self) -> None:
        """Test buffer initialization."""
        buffer = UnifiedReplayBuffer()

        assert len(buffer) == 0
        assert buffer.config.capacity == 100_000

    def test_buffer_custom_config(self) -> None:
        """Test buffer with custom config."""
        config = UnifiedReplayConfig(capacity=1000, alpha=0.7)
        buffer = UnifiedReplayBuffer(config)

        assert buffer.config.capacity == 1000
        assert buffer.config.alpha == 0.7

    def test_add_rl_experience(self) -> None:
        """Test adding RL experience."""
        buffer = UnifiedReplayBuffer()

        exp = create_rl_experience(
            state=torch.randn(8),
            action={"type": "move"},
            next_state=torch.randn(8),
            reward=1.0,
            done=False,
        )

        buffer.add(exp)

        assert len(buffer) == 1

    def test_add_tic_experience(self) -> None:
        """Test adding TIC experience."""
        buffer = UnifiedReplayBuffer()

        exp = create_tic_triplet(
            tic_data={"task": "test"},
            plan_state=torch.randn(8),
            execute_state=torch.randn(8),
            verify_state=torch.randn(8),
            actual_success=True,
        )

        buffer.add(exp)

        assert len(buffer) == 1

    def test_buffer_respects_capacity(self) -> None:
        """Test buffer respects capacity limit."""
        config = UnifiedReplayConfig(capacity=10)
        buffer = UnifiedReplayBuffer(config)

        for i in range(20):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"step": i},
                next_state=torch.randn(8),
                reward=float(i),
                done=False,
            )
            buffer.add(exp)

        assert len(buffer) <= 10

    def test_sample_basic(self) -> None:
        """Test basic sampling."""
        buffer = UnifiedReplayBuffer()

        for _ in range(50):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        experiences, weights, indices = buffer.sample(batch_size=10)

        assert len(experiences) == 10
        assert len(weights) == 10
        assert len(indices) == 10

    def test_sample_with_type_filter(self) -> None:
        """Test sampling with experience type filter."""
        buffer = UnifiedReplayBuffer()

        for _ in range(10):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        for _ in range(10):
            exp = create_tic_triplet(
                tic_data={"task": "test"},
                plan_state=torch.randn(8),
                execute_state=torch.randn(8),
                verify_state=torch.randn(8),
                actual_success=True,
            )
            buffer.add(exp)

        experiences, _, _ = buffer.sample(batch_size=5, experience_type="rl")

        assert all(exp.experience_type == "rl" for exp in experiences)

    def test_prioritized_sampling(self) -> None:
        """Test prioritized sampling."""
        config = UnifiedReplayConfig(alpha=1.0)
        buffer = UnifiedReplayBuffer(config)

        low_priority = create_rl_experience(
            state=torch.randn(8),
            action={"type": "move"},
            next_state=torch.randn(8),
            reward=0.1,
            done=False,
            td_error=0.1,
        )
        buffer.add(low_priority, priority=0.1)

        for _ in range(20):
            high_priority = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
                td_error=10.0,
            )
            buffer.add(high_priority, priority=10.0)

        experiences, _, _ = buffer.sample(batch_size=10)

        avg_priority = sum(exp.priority for exp in experiences) / len(experiences)
        assert avg_priority > 1.0

    def test_update_priorities(self) -> None:
        """Test updating priorities."""
        buffer = UnifiedReplayBuffer()

        for _ in range(10):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        _, _, indices = buffer.sample(batch_size=5)
        new_priorities = [2.0] * 5

        buffer.update_priorities(indices, new_priorities)

        for idx in indices:
            assert buffer._buffer[idx].td_error == 2.0

    def test_beta_annealing(self) -> None:
        """Test beta annealing."""
        config = UnifiedReplayConfig(
            beta_start=0.4,
            beta_end=1.0,
            beta_frames=1000,
        )
        buffer = UnifiedReplayBuffer(config)

        initial_beta = buffer.beta
        assert initial_beta == 0.4

        buffer._frame = 500
        mid_beta = buffer.beta
        assert 0.4 < mid_beta < 1.0

        buffer._frame = 1000
        final_beta = buffer.beta
        assert final_beta == 1.0

    def test_sample_by_state(self) -> None:
        """Test sampling by state similarity."""
        buffer = UnifiedReplayBuffer()

        target_state = torch.ones(8)

        for _ in range(10):
            exp = create_rl_experience(
                state=torch.ones(8) + torch.randn(8) * 0.1,
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        experiences, _, _ = buffer.sample_by_state(target_state, k=5)

        assert len(experiences) <= 5

    def test_sample_for_replay_ratio(self) -> None:
        """Test sampling for replay ratio."""
        config = UnifiedReplayConfig(replay_ratio=4)
        buffer = UnifiedReplayBuffer(config)

        for _ in range(100):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        batches = buffer.sample_for_replay_ratio(batch_size=10)

        assert len(batches) == 4
        assert all(len(batch[0]) == 10 for batch in batches)

    def test_get_stats(self) -> None:
        """Test getting buffer statistics."""
        buffer = UnifiedReplayBuffer()

        for _ in range(10):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        stats = buffer.get_stats()

        assert stats["size"] == 10
        assert "capacity" in stats
        assert "current_beta" in stats
        assert "type_counts" in stats

    def test_clear(self) -> None:
        """Test clearing buffer."""
        buffer = UnifiedReplayBuffer()

        for _ in range(10):
            exp = create_rl_experience(
                state=torch.randn(8),
                action={"type": "move"},
                next_state=torch.randn(8),
                reward=1.0,
                done=False,
            )
            buffer.add(exp)

        assert len(buffer) == 10

        buffer.clear()

        assert len(buffer) == 0

    def test_singleton_pattern(self) -> None:
        """Test singleton accessor."""
        buffer1 = get_unified_replay()
        buffer2 = get_unified_replay()

        assert buffer1 is buffer2


@pytest.mark.tier_unit
class TestHelperFunctions:
    """Test helper functions."""

    def test_create_rl_experience(self) -> None:
        """Test creating RL experience."""
        exp = create_rl_experience(
            state=torch.randn(8),
            action={"type": "move"},
            next_state=torch.randn(8),
            reward=1.0,
            done=False,
        )

        assert exp.experience_type == "rl"
        assert exp.reward == 1.0

    def test_create_tic_triplet(self) -> None:
        """Test creating TIC triplet."""
        exp = create_tic_triplet(
            tic_data={"task": "test"},
            plan_state=torch.randn(8),
            execute_state=torch.randn(8),
            verify_state=torch.randn(8),
            actual_success=True,
        )

        assert exp.experience_type == "tic"
        assert exp.actual_success is True

    def test_create_goal_experience(self) -> None:
        """Test creating goal experience."""
        exp = create_goal_experience(
            state=torch.randn(8),
            action={"type": "move"},
            next_state=torch.randn(8),
            goal={"target": "A"},
            achieved_goal={"target": "B"},
            reward=0.5,
            done=False,
        )

        assert exp.experience_type == "goal"
        assert exp.goal == {"target": "A"}
