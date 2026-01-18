"""Focused integration tests for production subsystems using real logic."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import numpy as np


class TestUnifiedReplay:
    """Validate unified replay buffer behavior."""

    def test_add_and_len(self) -> None:
        from kagami.core.memory.unified_replay import UnifiedReplayBuffer, UnifiedExperience
        import torch

        replay = UnifiedReplayBuffer(capacity=3)
        replay.add(
            UnifiedExperience(state=torch.zeros(4), action={}, reward=0.0, done=False), priority=0.1
        )
        replay.add(
            UnifiedExperience(state=torch.ones(4), action={}, reward=0.0, done=False), priority=0.5
        )
        assert len(replay) == 2

    def test_sampling_prefers_high_priority(self) -> None:
        from kagami.core.memory.unified_replay import UnifiedReplayBuffer, UnifiedExperience
        import torch

        replay = UnifiedReplayBuffer(capacity=10, alpha=0.9)
        replay.add(
            UnifiedExperience(
                state=torch.zeros(4), action={}, reward=0.0, done=False, metadata={"label": "low"}
            ),
            priority=0.01,
        )
        replay.add(
            UnifiedExperience(
                state=torch.ones(4), action={}, reward=1.0, done=False, metadata={"label": "high"}
            ),
            priority=1.0,
        )

        high_count = 0
        for _ in range(20):
            experiences, _weights, _indices = replay.sample(1)
            if (
                experiences
                and experiences[0].metadata
                and experiences[0].metadata.get("label") == "high"
            ):
                high_count += 1
        assert high_count > 10  # High-priority item sampled most of the time
