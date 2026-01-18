"""Tests for GeometricWorker - Unified Agent Implementation.

Validates:
1. Worker initialization and configuration
2. Task execution
3. Lifecycle management
4. S⁷ and H¹⁴ geometric state
5. Performance metrics

Created: December 2, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio
import torch

from kagami.core.unified_agents.geometric_worker import (
    GeometricWorker,
    WorkerConfig,
    WorkerState,
    WorkerStatus,
    TaskResult,
    create_worker,
    COLONY_NAMES,
    CATASTROPHE_TYPES,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def worker() -> GeometricWorker:
    """Create a basic geometric worker."""
    return create_worker(colony_idx=0)


@pytest.fixture
def config() -> WorkerConfig:
    """Create custom worker config."""
    return WorkerConfig(
        colony_idx=3,
        max_concurrent=3,
        idle_timeout=60.0,
        max_operations=100,
    )


# =============================================================================
# TEST INITIALIZATION
# =============================================================================


class TestInitialization:
    """Test worker initialization."""

    def test_default_initialization(self, worker: GeometricWorker) -> None:
        """Worker should initialize with defaults."""
        assert worker.state.status == WorkerStatus.ACTIVE
        assert worker.state.colony_idx == 0
        assert worker.state.colony_name == "spark"
        assert worker.state.completed_tasks == 0
        assert worker.state.failed_tasks == 0

    def test_custom_colony(self) -> None:
        """Worker should accept custom colony index."""
        worker = create_worker(colony_idx=4)

        assert worker.state.colony_idx == 4
        assert worker.state.colony_name == "beacon"
        assert worker.state.catastrophe_type == "hyperbolic"

    def test_custom_config(self, config: WorkerConfig) -> None:
        """Worker should accept custom config."""
        worker = GeometricWorker(config=config)

        assert worker.config.max_concurrent == 3
        assert worker.config.idle_timeout == 60.0
        assert worker.config.max_operations == 100

    def test_s7_section_initialization(self, worker: GeometricWorker) -> None:
        """S⁷ section should be unit vector for colony."""
        s7 = worker.state.s7_section

        assert s7.shape == (8,)
        assert s7[worker.state.colony_idx + 1] == 1.0
        assert s7.sum() == 1.0

    def test_h14_position_initialization(self, worker: GeometricWorker) -> None:
        """H¹⁴ position should be small offset from origin."""
        h14 = worker.state.h14_position

        assert h14.shape == (14,)
        assert h14.abs().max() < 1.0  # Near origin

    def test_all_colonies_valid(self) -> None:
        """All 7 colonies should be valid."""
        for i in range(7):
            worker = create_worker(colony_idx=i)

            assert worker.state.colony_name == COLONY_NAMES[i]
            assert worker.state.catastrophe_type == CATASTROPHE_TYPES[i]


# =============================================================================
# TEST EXECUTION
# =============================================================================


class TestExecution:
    """Test task execution."""

    @pytest.mark.asyncio
    async def test_execute_success(self, worker: GeometricWorker) -> None:
        """Successful execution should return result."""
        result = await worker.execute(
            action="test.action",
            params={"key": "value"},
        )

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.error is None
        assert result.latency > 0

    @pytest.mark.asyncio
    async def test_execute_updates_metrics(self, worker: GeometricWorker) -> None:
        """Execution should update completion metrics."""
        initial_completed = worker.state.completed_tasks

        await worker.execute(action="test", params={})

        assert worker.state.completed_tasks == initial_completed + 1

    @pytest.mark.asyncio
    async def test_execute_concurrent(self, worker: GeometricWorker) -> None:
        """Worker should handle concurrent executions."""
        tasks = [worker.execute(action=f"task.{i}", params={}) for i in range(3)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_respects_concurrency_limit(self) -> None:
        """Worker should respect max_concurrent limit."""
        config = WorkerConfig(max_concurrent=1)
        worker = GeometricWorker(config=config)

        # Start 3 tasks, only 1 should run at a time
        tasks = [worker.execute(action=f"task.{i}", params={}) for i in range(3)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_execute_returns_metadata(self, worker: GeometricWorker) -> None:
        """Result should include worker metadata."""
        result = await worker.execute(action="test", params={})

        assert "worker_id" in result.metadata
        assert "colony" in result.metadata
        assert result.metadata["worker_id"] == worker.worker_id
        assert result.metadata["colony"] == worker.colony_name


# =============================================================================
# TEST LIFECYCLE
# =============================================================================


class TestLifecycle:
    """Test worker lifecycle management."""

    def test_is_available(self, worker: GeometricWorker) -> None:
        """Worker should be available when active/idle."""
        assert worker.is_available is True

    @pytest.mark.asyncio
    async def test_hibernation(self, worker: GeometricWorker) -> None:
        """Worker should hibernate."""
        await worker.hibernate()

        assert worker.state.status == WorkerStatus.HIBERNATING
        assert worker.is_available is False

    @pytest.mark.asyncio
    async def test_wake_from_hibernation(self, worker: GeometricWorker) -> None:
        """Worker should wake from hibernation."""
        await worker.hibernate()
        await worker.wake()

        assert worker.state.status == WorkerStatus.IDLE
        assert worker.is_available is True

    @pytest.mark.asyncio
    async def test_retirement(self, worker: GeometricWorker) -> None:
        """Worker should retire gracefully."""
        await worker.retire()

        assert worker.state.status == WorkerStatus.DEAD
        assert worker.is_available is False

    def test_should_retire_by_operations(self) -> None:
        """Worker should retire after max operations."""
        config = WorkerConfig(max_operations=10)
        worker = GeometricWorker(config=config)

        # Simulate many operations
        worker.state.completed_tasks = 11

        assert worker.should_retire() is True

    def test_should_retire_by_fitness(self) -> None:
        """Worker should retire with very low fitness."""
        worker = create_worker()

        worker.state.fitness = 0.05
        worker.state.completed_tasks = 100

        assert worker.should_retire() is True

    def test_should_not_retire_healthy(self, worker: GeometricWorker) -> None:
        """Healthy worker should not retire."""
        worker.state.fitness = 0.9
        worker.state.completed_tasks = 50

        assert worker.should_retire() is False


# =============================================================================
# TEST STATE
# =============================================================================


class TestState:
    """Test worker state properties."""

    def test_success_rate_initial(self, worker: GeometricWorker) -> None:
        """Initial success rate should be None (no tasks yet) or 0.0 for display."""
        # Real implementation: success_rate returns None when no tasks executed
        # This is correct behavior - don't fake statistics
        assert worker.state.success_rate is None
        # Display version returns 0.0 for UI/metrics (not fake 0.5)
        assert worker.state.success_rate_display == 0.0

    @pytest.mark.asyncio
    async def test_success_rate_after_tasks(self, worker: GeometricWorker) -> None:
        """Success rate should reflect task outcomes."""
        # Execute some successful tasks
        for _ in range(5):
            await worker.execute(action="test", params={})

        assert worker.state.success_rate == 1.0

    def test_fitness_increases_on_success(self, worker: GeometricWorker) -> None:
        """Fitness should increase on success."""
        initial = worker.state.fitness
        worker._update_success(0.01)

        assert worker.state.fitness > initial

    def test_fitness_decreases_on_failure(self, worker: GeometricWorker) -> None:
        """Fitness should decrease on failure (or stay at 0 if already 0)."""
        # Set initial fitness > 0 to test decrease
        worker.state.fitness = 0.5
        initial = worker.state.fitness
        worker._update_failure(0.01)

        assert worker.state.fitness < initial

    def test_avg_latency_updated(self, worker: GeometricWorker) -> None:
        """Average latency should be updated via EMA."""
        worker._update_success(0.1)
        lat1 = worker.state.avg_latency

        worker._update_success(0.2)
        lat2 = worker.state.avg_latency

        # Should be moving toward 0.2
        assert lat2 > lat1


# =============================================================================
# TEST GEOMETRIC STATE
# =============================================================================


class TestGeometricState:
    """Test S⁷ and H¹⁴ geometric state."""

    def test_s7_section_is_on_sphere(self, worker: GeometricWorker) -> None:
        """S⁷ section should be on unit sphere."""
        s7 = worker.state.s7_section
        norm = torch.norm(s7)

        assert torch.isclose(norm, torch.tensor(1.0), atol=1e-5)

    def test_h14_position_updates_on_execution(self, worker: GeometricWorker) -> None:
        """H¹⁴ position should update after execution."""
        initial = worker.state.h14_position.clone()

        worker._update_h14_position({"status": "completed"})

        # Position should have changed
        assert not torch.equal(initial, worker.state.h14_position)

    def test_h14_moves_toward_origin_on_success(self, worker: GeometricWorker) -> None:
        """H¹⁴ should move toward origin on success."""
        worker.state.h14_position = torch.ones(14) * 0.1
        initial_norm = worker.state.h14_position.norm()

        worker._update_h14_position({"status": "completed"})

        final_norm = worker.state.h14_position.norm()
        assert final_norm < initial_norm

    def test_h14_moves_away_from_origin_on_failure(self, worker: GeometricWorker) -> None:
        """H¹⁴ should move away from origin on failure."""
        worker.state.h14_position = torch.ones(14) * 0.1
        initial_norm = worker.state.h14_position.norm()

        worker._update_h14_position({"status": "failed"})

        final_norm = worker.state.h14_position.norm()
        assert final_norm > initial_norm


# =============================================================================
# TEST STATISTICS
# =============================================================================


class TestStatistics:
    """Test worker statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, worker: GeometricWorker) -> None:
        """Stats should include all relevant metrics."""
        await worker.execute(action="test", params={})

        stats = worker.get_stats()

        assert "worker_id" in stats
        assert "colony" in stats
        assert "catastrophe" in stats
        assert "status" in stats
        assert "completed" in stats
        assert "failed" in stats
        assert "success_rate" in stats
        assert "fitness" in stats
        assert "avg_latency" in stats
        assert "current_tasks" in stats
        assert "age_seconds" in stats

    @pytest.mark.asyncio
    async def test_stats_reflect_work(self, worker: GeometricWorker) -> None:
        """Stats should reflect completed work."""
        for _ in range(3):
            await worker.execute(action="test", params={})

        stats = worker.get_stats()

        assert stats["completed"] == 3
        assert stats["success_rate"] == 1.0


# =============================================================================
# TEST FACTORY
# =============================================================================


class TestFactory:
    """Test factory function."""

    def test_create_default(self) -> None:
        """Factory should create worker with defaults."""
        worker = create_worker()

        assert worker.state.colony_idx == 0
        assert worker.state.colony_name == "spark"

    def test_create_with_colony(self) -> None:
        """Factory should accept colony index."""
        worker = create_worker(colony_idx=6)

        assert worker.state.colony_idx == 6
        assert worker.state.colony_name == "crystal"

    def test_create_with_config(self) -> None:
        """Factory should accept config."""
        config = WorkerConfig(colony_idx=2)
        worker = GeometricWorker(config=config)

        assert worker.state.colony_idx == 2
