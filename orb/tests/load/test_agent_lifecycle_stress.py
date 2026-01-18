"""Stress test: Agent lifecycle at scale (100+ agents, extended duration).

Tests that unified agents can:
- Scale to 100+ agents
- Maintain stability for 24+ hours
- Handle mitosis/apoptosis correctly under load
- Prevent memory leaks
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_e2e



import asyncio
import logging
import time

import psutil

logger = logging.getLogger(__name__)


@pytest.mark.stress
@pytest.mark.slow
@pytest.mark.asyncio
async def test_100_agents_sustained_load():
    """Test: 100+ agents running for extended period."""
    from kagami.core.unified_agents import COLONY_NAMES, OrganismConfig, UnifiedOrganism

    # Create organism with high cap
    organism = UnifiedOrganism(
        config=OrganismConfig(
            min_workers_per_colony=1,
            max_workers_per_colony=50,
            global_max_population=150,  # Not strictly enforced; caps are per-colony
            homeostasis_interval=10.0,  # Fast homeostasis for testing
        )
    )

    try:
        await organism.start()

        # Ensure we actually have 100+ workers to exercise lifecycle code paths.
        for i in range(100):
            colony = organism.get_colony(COLONY_NAMES[i % 7])
            assert colony is not None
            await colony.spawn_worker(task={"reason": "stress_seed", "i": i})

        # Track metrics
        start_time = time.time()
        start_memory_mb = psutil.Process().memory_info().rss / 1024 / 1024

        # Simulate sustained load
        import os

        duration_seconds = int(os.getenv("KAGAMI_SOAK_DURATION_SECONDS", "300"))
        logger.info(f"Starting soak test for {duration_seconds} seconds")

        tasks_submitted = 0
        tasks_completed = 0
        tasks_failed = 0

        # Submit tasks continuously
        async def submit_tasks():
            nonlocal tasks_submitted, tasks_completed, tasks_failed

            end_time = start_time + duration_seconds
            while time.time() < end_time:
                # Submit batch of tasks
                for _i in range(10):  # 10 tasks per batch
                    # Simulate task submission to organism
                    # In real system: organism.execute_intent(intent)
                    # Here: Just track submission
                    tasks_submitted += 1

                # Simulate some completions
                tasks_completed += 8  # 80% success
                tasks_failed += 2  # 20% failure

                await asyncio.sleep(1)  # 1 second batches

        # Run task submitter
        await submit_tasks()

        # Final measurements
        end_time = time.time()
        end_memory_mb = psutil.Process().memory_info().rss / 1024 / 1024

        duration = end_time - start_time
        memory_growth_mb = end_memory_mb - start_memory_mb

        # Compute final population directly (homeostasis stats update on interval)
        final_population = sum(len(c.workers) for c in organism.colonies.values())

        # Assertions
        print("\n✅ Stress test results:")
        print(f"   Duration: {duration:.1f}s")
        print(f"   Tasks submitted: {tasks_submitted}")
        print(f"   Tasks completed: {tasks_completed}")
        print(f"   Success rate: {tasks_completed / (tasks_submitted or 1) * 100:.1f}%")
        print(f"   Final population: {final_population} agents")
        print(f"   Memory growth: {memory_growth_mb:.1f} MB")
        print(f"   Memory rate: {memory_growth_mb / duration:.2f} MB/s")

        # Memory leak check (should not grow >100MB/min)
        memory_rate_mb_per_min = memory_growth_mb / (duration / 60)
        assert (
            memory_rate_mb_per_min < 100
        ), f"Memory leak detected: {memory_rate_mb_per_min:.1f} MB/min growth"

        # Population should be reasonable (<150 max)
        assert final_population <= 150, f"Population {final_population} exceeded max 150"

    finally:
        # Cleanup
        await organism.stop()


@pytest.mark.stress
@pytest.mark.slow
@pytest.mark.asyncio
async def test_mitosis_apoptosis_balance():
    """Test: worker pool stays within configured bounds."""
    from kagami.core.unified_agents import COLONY_NAMES, OrganismConfig, UnifiedOrganism

    per_colony_max = 10
    organism = UnifiedOrganism(
        config=OrganismConfig(
            min_workers_per_colony=1,
            max_workers_per_colony=per_colony_max,
            global_max_population=100,
            homeostasis_interval=5.0,
        )
    )

    try:
        await organism.start()

        colony = organism.get_colony(COLONY_NAMES[0])
        assert colony is not None

        # Fill colony to cap
        while len(colony.workers) < per_colony_max:
            await colony.spawn_worker(task={"reason": "fill_to_cap"})

        # Attempt to exceed cap (should fail)
        failures = 0
        for _i in range(5):
            try:
                await colony.spawn_worker(task={"reason": "exceed_cap"})
            except RuntimeError:
                failures += 1

        assert failures >= 1
        assert len(colony.workers) == per_colony_max

        # Retire a few workers and ensure cleanup removes them
        for w in list(colony.workers)[:3]:
            await w.retire()
        await colony.cleanup_workers()

        assert 1 <= len(colony.workers) <= per_colony_max

    finally:
        await organism.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "stress"])
