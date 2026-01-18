"""Tests for kagami.core.memory.brain_consolidation."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.memory.brain_consolidation import (
    BrainConsolidation,
    BrainExperience,
    BrainReplayBuffer,
    SchemaExtractor,
    get_brain_consolidation,
)


@pytest.mark.tier_unit
class TestBrainExperience:
    """Test BrainExperience dataclass."""

    def test_experience_creation(self) -> None:
        """Test creating a brain experience."""
        state = torch.randn(8)
        action = torch.randn(8)
        next_state = torch.randn(8)

        exp = BrainExperience(
            state=state,
            action=action,
            reward=1.0,
            next_state=next_state,
            done=False,
            td_error=0.5,
            emotional_salience=0.3,
            novelty=0.2,
        )

        assert exp.reward == 1.0
        assert exp.td_error == 0.5
        assert exp.emotional_salience == 0.3
        assert exp.novelty == 0.2
        assert exp.replay_count == 0
        assert exp.schema_id == -1

    def test_priority_calculation(self) -> None:
        """Test priority calculation."""
        state = torch.randn(8)
        action = torch.randn(8)

        exp = BrainExperience(
            state=state,
            action=action,
            reward=1.0,
            next_state=torch.randn(8),
            td_error=1.0,
            emotional_salience=0.5,
            novelty=0.3,
        )

        priority = exp.priority
        assert priority > 0
        assert priority >= 0.01

    def test_priority_decay_with_replay(self) -> None:
        """Test priority decays with replay count."""
        state = torch.randn(8)
        exp = BrainExperience(
            state=state,
            action=torch.randn(8),
            reward=1.0,
            next_state=torch.randn(8),
            td_error=1.0,
        )

        initial_priority = exp.priority
        exp.replay_count = 5
        decayed_priority = exp.priority

        assert decayed_priority < initial_priority


@pytest.mark.tier_unit
class TestSchemaExtractor:
    """Test SchemaExtractor neural module."""

    def test_schema_initialization(self) -> None:
        """Test schema extractor initialization."""
        extractor = SchemaExtractor(
            state_dim=8,
            num_schemas=16,
            learning_rate=0.01,
        )

        assert extractor.state_dim == 8
        assert extractor.num_schemas == 16
        assert extractor.lr == 0.01
        assert extractor.centroids.shape == (16, 8)

    def test_assign_state_to_schema(self) -> None:
        """Test assigning state to nearest schema."""
        extractor = SchemaExtractor(state_dim=8, num_schemas=16)
        state = torch.randn(8)

        schema_idx, distance = extractor.assign(state)

        assert isinstance(schema_idx, int)
        assert 0 <= schema_idx < 16
        assert distance >= 0

    def test_assign_batch(self) -> None:
        """Test assigning batch of states."""
        extractor = SchemaExtractor(state_dim=8, num_schemas=16)
        states = torch.randn(5, 8)

        schema_idx, distance = extractor.assign(states)

        assert isinstance(schema_idx, int)
        assert distance >= 0

    def test_update_schema(self) -> None:
        """Test updating schema with experience."""
        extractor = SchemaExtractor(state_dim=8, num_schemas=16)
        state = torch.randn(8)
        schema_idx = 5

        old_centroid = extractor.centroids[schema_idx].clone()
        old_count = extractor.counts[schema_idx].item()

        extractor.update(schema_idx, state, reward=1.0)

        assert extractor.counts[schema_idx] == old_count + 1
        assert not torch.equal(extractor.centroids[schema_idx], old_centroid)

    def test_normalize_schemas(self) -> None:
        """Test synaptic homeostasis normalization."""
        extractor = SchemaExtractor(state_dim=8, num_schemas=16)

        extractor.centroids.data = torch.randn(16, 8) * 10

        extractor.normalize()

        norms = extractor.centroids.norm(dim=-1)
        assert torch.all(norms <= 10.0)

    def test_get_active_schemas(self) -> None:
        """Test getting active schemas."""
        extractor = SchemaExtractor(state_dim=8, num_schemas=16)

        assert len(extractor.get_active_schemas()) == 0

        extractor.update(5, torch.randn(8), reward=1.0)
        extractor.update(10, torch.randn(8), reward=1.0)

        active = extractor.get_active_schemas()
        assert len(active) == 2
        assert 5 in active
        assert 10 in active

    def test_get_stats(self) -> None:
        """Test getting schema statistics."""
        extractor = SchemaExtractor(state_dim=8, num_schemas=16)

        stats = extractor.get_stats()
        assert stats["num_active"] == 0
        assert stats["total_experiences"] == 0

        extractor.update(5, torch.randn(8), reward=1.0)

        stats = extractor.get_stats()
        assert stats["num_active"] == 1
        assert stats["total_experiences"] == 1


@pytest.mark.tier_unit
class TestBrainReplayBuffer:
    """Test BrainReplayBuffer."""

    def test_buffer_initialization(self) -> None:
        """Test buffer initialization."""
        buffer = BrainReplayBuffer(capacity=1000, alpha=0.6)

        assert buffer.capacity == 1000
        assert buffer.alpha == 0.6
        assert len(buffer) == 0

    def test_add_experience(self) -> None:
        """Test adding experience to buffer."""
        buffer = BrainReplayBuffer(capacity=100)

        exp = BrainExperience(
            state=torch.randn(8),
            action=torch.randn(8),
            reward=1.0,
            next_state=torch.randn(8),
            td_error=0.5,
        )

        buffer.add(exp)

        assert len(buffer) == 1

    def test_buffer_capacity(self) -> None:
        """Test buffer respects capacity limit."""
        buffer = BrainReplayBuffer(capacity=10)

        for i in range(20):
            exp = BrainExperience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=float(i),
                next_state=torch.randn(8),
            )
            buffer.add(exp)

        assert len(buffer) == 10

    def test_sample_batch(self) -> None:
        """Test sampling batch from buffer."""
        buffer = BrainReplayBuffer(capacity=100)

        for _ in range(50):
            exp = BrainExperience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=1.0,
                next_state=torch.randn(8),
                td_error=1.0,
            )
            buffer.add(exp)

        experiences, weights, indices = buffer.sample(batch_size=10)

        assert len(experiences) == 10
        assert len(weights) == 10
        assert len(indices) == 10
        assert all(w > 0 for w in weights)

    def test_prioritized_sampling(self) -> None:
        """Test that high priority experiences are sampled more."""
        buffer = BrainReplayBuffer(capacity=100, alpha=1.0)

        low_priority = BrainExperience(
            state=torch.randn(8),
            action=torch.randn(8),
            reward=0.1,
            next_state=torch.randn(8),
            td_error=0.1,
        )
        buffer.add(low_priority)

        for _ in range(10):
            high_priority = BrainExperience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=1.0,
                next_state=torch.randn(8),
                td_error=10.0,
            )
            buffer.add(high_priority)

        experiences, _, _ = buffer.sample(batch_size=5)
        avg_priority = sum(e.priority for e in experiences) / len(experiences)

        assert avg_priority > 1.0

    def test_update_priorities(self) -> None:
        """Test updating priorities after sampling."""
        buffer = BrainReplayBuffer(capacity=100)

        for _ in range(10):
            exp = BrainExperience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=1.0,
                next_state=torch.randn(8),
                td_error=1.0,
            )
            buffer.add(exp)

        _, _, indices = buffer.sample(batch_size=5)
        new_td_errors = [2.0] * 5

        buffer.update_priorities(indices, new_td_errors)

        for idx in indices:
            assert buffer.buffer[idx].td_error == 2.0

    def test_replay_count_increments(self) -> None:
        """Test replay count increments on sampling."""
        buffer = BrainReplayBuffer(capacity=100)

        exp = BrainExperience(
            state=torch.randn(8),
            action=torch.randn(8),
            reward=1.0,
            next_state=torch.randn(8),
        )
        buffer.add(exp)

        assert buffer.buffer[0].replay_count == 0

        buffer.sample(batch_size=1)

        assert buffer.buffer[0].replay_count == 1


@pytest.mark.tier_unit
class TestBrainConsolidation:
    """Test BrainConsolidation system."""

    def test_consolidation_initialization(self) -> None:
        """Test consolidation system initialization."""
        consolidation = BrainConsolidation(
            state_dim=8,
            buffer_capacity=1000,
            num_schemas=32,
        )

        assert consolidation.state_dim == 8
        assert len(consolidation.replay_buffer) == 0
        assert consolidation.steps == 0

    def test_add_experience(self) -> None:
        """Test adding experience to consolidation system."""
        consolidation = BrainConsolidation(state_dim=8)

        state = torch.randn(8)
        action = torch.randn(8)
        next_state = torch.randn(8)

        consolidation.add_experience(
            state=state,
            action=action,
            reward=1.0,
            next_state=next_state,
            done=False,
            td_error=0.5,
        )

        assert len(consolidation.replay_buffer) == 1
        assert consolidation.steps == 1

    def test_experience_schema_assignment(self) -> None:
        """Test that experiences are assigned to schemas."""
        consolidation = BrainConsolidation(state_dim=8, num_schemas=16)

        state = torch.randn(8)

        consolidation.add_experience(
            state=state,
            action=torch.randn(8),
            reward=1.0,
            next_state=torch.randn(8),
            td_error=0.5,
        )

        exp = consolidation.replay_buffer.buffer[0]
        assert exp.schema_id >= 0
        assert exp.schema_id < 16

    def test_replay_sampling(self) -> None:
        """Test replay sampling."""
        consolidation = BrainConsolidation(state_dim=8)

        for _ in range(100):
            consolidation.add_experience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=1.0,
                next_state=torch.randn(8),
                td_error=1.0,
            )

        experiences, weights = consolidation.replay(batch_size=32)

        assert len(experiences) == 32
        assert len(weights) == 32

    def test_consolidation_cycle(self) -> None:
        """Test periodic consolidation."""
        consolidation = BrainConsolidation(
            state_dim=8,
            consolidation_interval=10,
        )

        for _i in range(15):
            consolidation.add_experience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=1.0,
                next_state=torch.randn(8),
                td_error=1.0,
            )

        assert consolidation.consolidation_count >= 1

    def test_sleep_consolidation(self) -> None:
        """Test sleep-like consolidation cycle."""
        consolidation = BrainConsolidation(state_dim=8)

        for _ in range(100):
            consolidation.add_experience(
                state=torch.randn(8),
                action=torch.randn(8),
                reward=1.0,
                next_state=torch.randn(8),
                td_error=1.0,
            )

        stats = consolidation.sleep_consolidate(num_replays=10)

        assert "replayed" in stats
        assert "consolidation_count" in stats
        assert stats["replayed"] > 0

    def test_get_stats(self) -> None:
        """Test getting consolidation statistics."""
        consolidation = BrainConsolidation(state_dim=8)

        stats = consolidation.get_stats()

        assert "buffer_size" in stats
        assert "steps" in stats
        assert "consolidation_count" in stats
        assert "num_active" in stats

    def test_singleton_pattern(self) -> None:
        """Test singleton accessor."""
        consolidation1 = get_brain_consolidation()
        consolidation2 = get_brain_consolidation()

        assert consolidation1 is consolidation2
