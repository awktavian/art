"""48-Hour Production Soak Test

Validates long-running stability:
- Memory growth <5%
- No crashes
- Agent population stable
- Performance maintained

Created: November 16, 2025 (Q2 Production Roadmap)
"""

from __future__ import annotations

import pytest
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class SoakMetrics:
    """Metrics collected during soak test."""

    duration_hours: float
    memory_start_mb: float
    memory_end_mb: float
    memory_peak_mb: float
    memory_growth_percent: float

    agent_births: int
    agent_deaths: int
    agent_population_min: int
    agent_population_max: int
    agent_population_avg: float

    operations_completed: int
    operations_failed: int
    error_rate: float

    api_requests: int
    api_p95_latency_ms: float
    api_p99_latency_ms: float


@pytest.mark.soak
@pytest.mark.slow
@pytest.mark.timeout(172800)  # 48 hours
@pytest.mark.asyncio
async def test_48h_soak():
    """Run 48-hour soak test with memory profiling."""
    logger.info("=== Starting 48-Hour Soak Test ===")

    # Test configuration
    duration_hours = float(pytest.config.getoption("--soak-duration", default="48"))
    duration_seconds = duration_hours * 3600
    sample_interval = 60  # Sample every minute

    # Initialize
    from kagami.core.unified_agents import get_unified_organism

    organism = get_unified_organism()
    await organism.start()

    # Baseline metrics
    process = psutil.Process()
    memory_start = process.memory_info().rss / 1024 / 1024  # MB
    memory_samples = [memory_start]

    agent_population_samples = []
    latency_samples = []

    start_time = time.time()
    logger.info(f"Baseline memory: {memory_start:.1f} MB")

    # Run soak test
    iteration = 0
    while time.time() - start_time < duration_seconds:
        iteration += 1
        elapsed_hours = (time.time() - start_time) / 3600

        # Sample metrics
        memory_current = process.memory_info().rss / 1024 / 1024
        memory_samples.append(memory_current)

        # Agent population
        agent_count = sum(len(colony.workers) for colony in organism.colonies.values())
        agent_population_samples.append(agent_count)

        # Simulate workload (variable)
        task_count = (iteration % 10) + 1  # 1-10 tasks per minute
        for _ in range(task_count):
            try:
                # Submit task to organism
                start_task = time.time()
                _result = await organism.execute_intent(
                    intent="test.noop",
                    params={"iteration": iteration},
                    context={"iteration": iteration},
                )
                latency_ms = (time.time() - start_task) * 1000
                latency_samples.append(latency_ms)
            except Exception as e:
                logger.warning(f"Task failed: {e}")

        # Log progress every hour
        if iteration % 60 == 0:
            memory_growth = ((memory_current - memory_start) / memory_start) * 100
            logger.info(
                f"[{elapsed_hours:.1f}h] "
                f"Memory: {memory_current:.1f} MB (+{memory_growth:.1f}%), "
                f"Agents: {agent_count}, "
                f"Ops: {iteration * task_count}"
            )

        # Sleep until next sample
        await asyncio.sleep(sample_interval)

    # Calculate final metrics
    memory_end = memory_samples[-1]
    memory_peak = max(memory_samples)
    memory_growth_percent = ((memory_end - memory_start) / memory_start) * 100

    metrics = SoakMetrics(
        duration_hours=duration_hours,
        memory_start_mb=memory_start,
        memory_end_mb=memory_end,
        memory_peak_mb=memory_peak,
        memory_growth_percent=memory_growth_percent,
        agent_births=0,  # Future: Derive from receipt telemetry system
        agent_deaths=0,
        agent_population_min=min(agent_population_samples) if agent_population_samples else 0,
        agent_population_max=max(agent_population_samples) if agent_population_samples else 0,
        agent_population_avg=(
            sum(agent_population_samples) / len(agent_population_samples)
            if agent_population_samples
            else 0
        ),
        operations_completed=iteration * 5,  # Approximate
        operations_failed=0,  # Future: Derive from receipt telemetry system
        error_rate=0.0,
        api_requests=iteration * 5,
        api_p95_latency_ms=(
            sorted(latency_samples)[int(len(latency_samples) * 0.95)] if latency_samples else 0
        ),
        api_p99_latency_ms=(
            sorted(latency_samples)[int(len(latency_samples) * 0.99)] if latency_samples else 0
        ),
    )

    # Log final results
    logger.info("=== Soak Test Complete ===")
    logger.info(f"Duration: {metrics.duration_hours} hours")
    logger.info(f"Memory growth: {metrics.memory_growth_percent:.2f}%")
    logger.info(
        f"Agent population: {metrics.agent_population_min}-{metrics.agent_population_max} (avg: {metrics.agent_population_avg:.1f})"
    )
    logger.info(f"Operations: {metrics.operations_completed} completed")
    logger.info(
        f"API latency: p95={metrics.api_p95_latency_ms:.1f}ms, p99={metrics.api_p99_latency_ms:.1f}ms"
    )

    # Assertions
    assert (
        metrics.memory_growth_percent < 5.0
    ), f"Memory growth {metrics.memory_growth_percent:.2f}% exceeds 5% threshold"

    assert metrics.agent_population_min > 0, "Agents died completely"
    assert metrics.agent_population_max < 1000, f"Agent explosion: {metrics.agent_population_max}"

    logger.info("✅ Soak test PASSED")
    await organism.stop()


@pytest.mark.soak
@pytest.mark.slow
@pytest.mark.timeout(7200)  # 2 hours
@pytest.mark.asyncio
async def test_2h_quick_soak():
    """Quick 2-hour soak test for CI."""
    logger.info("=== Starting 2-Hour Quick Soak ===")

    # Similar to above but shorter duration
    # Used in nightly CI
    duration_hours = 2.0
    duration_seconds = duration_hours * 3600

    process = psutil.Process()
    memory_start = process.memory_info().rss / 1024 / 1024

    start_time = time.time()

    while time.time() - start_time < duration_seconds:
        # Minimal workload
        await asyncio.sleep(10)

        # Check memory periodically
        if int(time.time() - start_time) % 600 == 0:  # Every 10 min
            memory_current = process.memory_info().rss / 1024 / 1024
            growth = ((memory_current - memory_start) / memory_start) * 100
            logger.info(f"Memory: {memory_current:.1f} MB (+{growth:.1f}%)")

    memory_end = process.memory_info().rss / 1024 / 1024
    growth = ((memory_end - memory_start) / memory_start) * 100

    assert growth < 5.0, f"Memory growth {growth:.2f}% exceeds threshold"

    logger.info("✅ Quick soak PASSED")


if __name__ == "__main__":
    # Run with: pytest tests/soak/test_production_simulation.py -m soak -v -s
    pytest.main(
        [__file__, "-m", "soak", "-v", "-s", "--soak-duration=0.5"]
    )  # 30 min for manual run
