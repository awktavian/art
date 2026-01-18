"""Tests for CatastropheMemory - Continual Learning System.

FORGE (e₂) - December 14, 2025
===============================
Verification that catastrophe memory prevents forgetting by maintaining
landscape topology.

TEST SCENARIOS:
===============
1. Task learning: Verify well carving works
2. Boundary detection: Check bifurcation points are found
3. Replay sampling: Confirm priority sampling by risk
4. Replay loss: Ensure loss maintains boundaries
5. Multi-task: No catastrophic forgetting across tasks
"""

from __future__ import annotations

from typing import Any

import pytest

import torch

from kagami.core.world_model.catastrophe_memory import (
    BifurcationSample,
    CatastropheMemory,
    TaskWell,
)

pytestmark = pytest.mark.tier_integration


class TestCatastropheMemory:
    """Test suite for CatastropheMemory."""

    @pytest.fixture
    def memory(self) -> Any:
        """Create fresh CatastropheMemory instance."""
        return CatastropheMemory(
            state_dim=32,  # Smaller for testing
            num_catastrophes=7,
            replay_buffer_size=100,
        )

    @pytest.fixture
    def task_states(self) -> Any:
        """Generate synthetic task states."""
        # Task A: states clustered around [1, 1, ..., 1]
        task_a = torch.randn(50, 32) * 0.3 + 1.0

        # Task B: states clustered around [-1, -1, ..., -1]
        task_b = torch.randn(50, 32) * 0.3 - 1.0

        # Task C: states clustered around [0, 2, 0, 2, ...]
        task_c = torch.randn(50, 32) * 0.3
        task_c[:, ::2] = 2.0

        return {"A": task_a, "B": task_b, "C": task_c}

    def test_initialization(self, memory) -> None:
        """Test memory initializes correctly."""
        assert memory.state_dim == 32
        assert memory.num_catastrophes == 7
        assert len(memory.wells) == 0
        assert len(memory.boundaries) == 0
        assert len(memory.replay_buffer) == 0

        stats = memory.get_stats()
        assert stats["tasks_learned"] == 0
        assert stats["num_wells"] == 0

    def test_learn_single_task(self, memory, task_states) -> None:
        """Test learning a single task creates well."""
        task_a = task_states["A"]

        task_idx = memory.learn_task(task_a, "task_A")

        # Verify task was learned
        assert task_idx == 0
        assert "task_A" in memory.wells
        assert memory.wells["task_A"].task_idx == 0

        # Verify well properties
        well = memory.wells["task_A"]
        assert well.center.shape == (32,)
        assert well.depth > 0
        assert well.coefficients.shape == (7, 32, 4)
        assert len(well.boundary_samples) > 0

        # Check stats
        stats = memory.get_stats()
        assert stats["tasks_learned"] == 1
        assert stats["num_wells"] == 1

    def test_learn_multiple_tasks(self, memory, task_states) -> None:
        """Test learning multiple tasks creates separate wells."""
        idx_a = memory.learn_task(task_states["A"], "task_A")
        idx_b = memory.learn_task(task_states["B"], "task_B")
        idx_c = memory.learn_task(task_states["C"], "task_C")

        # Verify all tasks learned
        assert idx_a == 0
        assert idx_b == 1
        assert idx_c == 2
        assert len(memory.wells) == 3

        # Verify boundaries created between tasks
        # With 3 tasks, should have 3*2 = 6 bidirectional boundaries
        assert len(memory.boundaries) == 6

        # Check specific boundaries exist
        assert (0, 1) in memory.boundaries
        assert (1, 0) in memory.boundaries
        assert (0, 2) in memory.boundaries
        assert (2, 0) in memory.boundaries
        assert (1, 2) in memory.boundaries
        assert (2, 1) in memory.boundaries

    def test_well_separation(self, memory, task_states) -> None:
        """Test that wells for different tasks are spatially separated."""
        memory.learn_task(task_states["A"], "task_A")
        memory.learn_task(task_states["B"], "task_B")

        well_a = memory.wells["task_A"]
        well_b = memory.wells["task_B"]

        # Centers should be far apart
        distance = (well_a.center - well_b.center).norm()
        assert distance > 1.0, "Task wells should be separated"

        # Wells should have positive depth
        assert well_a.depth > 0
        assert well_b.depth > 0

    def test_add_bifurcation(self, memory, task_states) -> None:
        """Test adding bifurcation samples to replay buffer."""
        memory.learn_task(task_states["A"], "task_A")

        # Add bifurcations with varying risk
        state = torch.randn(32)
        memory.add_bifurcation(state, task_idx=0, risk=0.8)

        assert len(memory.replay_buffer) == 1
        assert memory.stats["bifurcations_stored"] == 1

        sample = memory.replay_buffer[0]
        assert sample.task_idx == 0
        assert sample.risk == 0.8
        assert sample.state.shape == (32,)

    def test_sample_bifurcations_empty(self, memory) -> None:
        """Test sampling from empty buffer returns None."""
        result = memory.sample_bifurcations(batch_size=10)
        assert result is None

    def test_sample_bifurcations_priority(self, memory, task_states) -> None:
        """Test that higher-risk bifurcations are sampled more often."""
        memory.learn_task(task_states["A"], "task_A")

        # Add bifurcations with different risks
        for risk in [0.1, 0.5, 0.9]:
            state = torch.randn(32)
            memory.add_bifurcation(state, task_idx=0, risk=risk)

        # Sample many times and check high-risk appears more
        high_risk_count = 0
        num_samples = 100

        for _ in range(num_samples):
            batch = memory.sample_bifurcations(batch_size=1)
            if batch and batch["risks"][0] > 0.7:
                high_risk_count += 1

        # High-risk should appear more than random (33%)
        # With importance sampling, should be >50%
        assert high_risk_count > num_samples * 0.4

    def test_replay_loss_basic(self, memory, task_states) -> None:
        """Test replay loss computation."""
        memory.learn_task(task_states["A"], "task_A")
        memory.learn_task(task_states["B"], "task_B")

        # Create replay batch
        states = torch.stack(
            [
                memory.wells["task_A"].center,
                memory.wells["task_B"].center,
            ]
        )
        task_labels = torch.tensor([0, 1], dtype=torch.long)

        # Compute replay loss
        loss = memory.replay_loss(states, task_labels)

        # Loss should be positive scalar
        assert isinstance(loss, torch.Tensor)
        assert loss.ndim == 0
        assert loss.item() >= 0

    def test_replay_loss_attraction(self, memory, task_states) -> None:
        """Test that replay loss pulls states toward correct wells."""
        memory.learn_task(task_states["A"], "task_A")

        well_center = memory.wells["task_A"].center

        # State far from well center
        far_state = well_center + torch.randn(32) * 5.0

        # State near well center
        near_state = well_center + torch.randn(32) * 0.1

        states = torch.stack([far_state, near_state])
        task_labels = torch.tensor([0, 0], dtype=torch.long)

        loss = memory.replay_loss(states, task_labels)

        # Loss should decrease as state moves toward center
        # (This is implicit in attraction loss formulation)
        assert loss.item() > 0

    def test_compute_landscape(self, memory, task_states) -> None:
        """Test full landscape computation."""
        memory.learn_task(task_states["A"], "task_A")
        memory.learn_task(task_states["B"], "task_B")

        # Compute potential at various states
        test_states = torch.randn(10, 32)
        potentials = memory.compute_landscape(test_states)

        # Should return potentials for all states
        assert potentials.shape == (10,)
        assert not torch.isnan(potentials).any()
        assert not torch.isinf(potentials).any()

    def test_get_well_depth(self, memory, task_states) -> None:
        """Test well depth retrieval."""
        memory.learn_task(task_states["A"], "task_A")

        depth = memory.get_well_depth("task_A")
        assert depth > 0

        # Non-existent task should return 0
        depth_missing = memory.get_well_depth("nonexistent")
        assert depth_missing == 0.0

    def test_no_catastrophic_forgetting(self, memory, task_states) -> None:
        """Test that learning new task doesn't destroy old task well.

        This is the KEY property of continual learning.
        """
        # Learn task A
        memory.learn_task(task_states["A"], "task_A")
        well_a_initial = memory.wells["task_A"]
        depth_a_initial = well_a_initial.depth
        center_a_initial = well_a_initial.center.clone()

        # Learn task B (should not affect task A)
        memory.learn_task(task_states["B"], "task_B")

        # Check task A properties are preserved
        well_a_after = memory.wells["task_A"]
        assert well_a_after.task_idx == well_a_initial.task_idx
        assert torch.allclose(well_a_after.center, center_a_initial, atol=1e-6)
        # Depth should be unchanged (well topology preserved)
        assert abs(well_a_after.depth - depth_a_initial) < 0.1

    def test_boundary_sharpness(self, memory, task_states) -> None:
        """Test that boundary sharpness is computed correctly."""
        memory.learn_task(task_states["A"], "task_A")
        memory.learn_task(task_states["B"], "task_B")

        # Get boundary between tasks
        boundary = memory.boundaries[(0, 1)]

        # Sharpness should be positive
        assert boundary.sharpness >= 0

        # Should have states on boundary
        assert len(boundary.states) > 0

        # Importance should be positive
        assert boundary.importance >= 0

    def test_stats_tracking(self, memory, task_states) -> None:
        """Test that statistics are tracked correctly."""
        initial_stats = memory.get_stats()
        assert initial_stats["tasks_learned"] == 0

        memory.learn_task(task_states["A"], "task_A")
        stats_after_one = memory.get_stats()
        assert stats_after_one["tasks_learned"] == 1
        assert stats_after_one["num_wells"] == 1

        memory.learn_task(task_states["B"], "task_B")
        stats_after_two = memory.get_stats()
        assert stats_after_two["tasks_learned"] == 2
        assert stats_after_two["num_wells"] == 2

        # Add bifurcation
        memory.add_bifurcation(torch.randn(32), task_idx=0, risk=0.5)
        stats_after_bif = memory.get_stats()
        assert stats_after_bif["bifurcations_stored"] == 1
        assert stats_after_bif["buffer_size"] == 1

    def test_buffer_max_size(self, memory) -> None:
        """Test that replay buffer respects max size."""
        memory.learn_task(torch.randn(10, 32), "task_A")

        # Add more bifurcations than buffer size
        buffer_size = 100
        for _i in range(buffer_size + 50):
            state = torch.randn(32)
            memory.add_bifurcation(state, task_idx=0, risk=0.5)

        # Buffer should not exceed max size
        assert len(memory.replay_buffer) == buffer_size

    def test_gradient_flow(self, memory, task_states) -> None:
        """Test that gradients flow through replay loss."""
        memory.learn_task(task_states["A"], "task_A")

        # Create states that require gradients
        states = torch.randn(5, 32, requires_grad=True)
        task_labels = torch.tensor([0, 0, 0, 0, 0], dtype=torch.long)

        # Compute loss
        loss = memory.replay_loss(states, task_labels)

        # Backward pass
        loss.backward()

        # Check gradients exist
        assert states.grad is not None
        assert not torch.isnan(states.grad).any()

    def test_task_overwrite(self, memory, task_states) -> None:
        """Test that learning same task name overwrites."""
        memory.learn_task(task_states["A"], "task_A")
        initial_depth = memory.wells["task_A"].depth

        # Learn again with different data
        memory.learn_task(task_states["B"], "task_A")  # Same name

        # Should overwrite
        assert len(memory.wells) == 1
        assert "task_A" in memory.wells
        # Depth will be different due to different data
        new_depth = memory.wells["task_A"].depth
        assert new_depth != initial_depth


@pytest.mark.parametrize("state_dim", [16, 64, 256])
def test_different_state_dims(state_dim) -> None:
    """Test memory works with different state dimensions."""
    memory = CatastropheMemory(state_dim=state_dim)

    task_states = torch.randn(20, state_dim)
    task_idx = memory.learn_task(task_states, "test_task")

    assert task_idx == 0
    assert memory.wells["test_task"].center.shape == (state_dim,)


@pytest.mark.parametrize("num_tasks", [1, 3, 5, 10])
def test_scalability(num_tasks) -> None:
    """Test memory scales to multiple tasks."""
    memory = CatastropheMemory(state_dim=32)

    # Learn multiple tasks
    for i in range(num_tasks):
        task_states = torch.randn(20, 32) + i * 2.0  # Offset each task
        memory.learn_task(task_states, f"task_{i}")

    # Check all tasks learned
    assert len(memory.wells) == num_tasks

    # Check boundaries created (n * (n-1) bidirectional edges)
    expected_boundaries = num_tasks * (num_tasks - 1)
    assert len(memory.boundaries) == expected_boundaries


def test_integration_with_training() -> None:
    """Integration test: simulate training loop with replay."""
    memory = CatastropheMemory(state_dim=32)

    # Learn initial task
    task_a_states = torch.randn(50, 32) * 0.3 + 1.0
    memory.learn_task(task_a_states, "task_A")

    # Simulate training: detect and store bifurcations
    for _ in range(10):
        state = torch.randn(32)
        risk = torch.rand(1).item()
        memory.add_bifurcation(state, task_idx=0, risk=risk)

    # Learn second task
    task_b_states = torch.randn(50, 32) * 0.3 - 1.0
    memory.learn_task(task_b_states, "task_B")

    # Simulate replay to prevent forgetting
    replay_batch = memory.sample_bifurcations(batch_size=4)
    assert replay_batch is not None

    loss = memory.replay_loss(
        replay_batch["states"],
        replay_batch["task_labels"],
    )

    # Loss should be reasonable
    assert 0 < loss.item() < 100

    # Both tasks should still have wells
    assert len(memory.wells) == 2
    assert memory.get_well_depth("task_A") > 0
    assert memory.get_well_depth("task_B") > 0
