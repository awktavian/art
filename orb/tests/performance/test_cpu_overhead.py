"""Performance benchmark: CPU overhead for background learning.

Verifies claim: <2% CPU overhead for background learning

This test measures CPU utilization of the continuous learning daemon
relative to baseline system CPU usage.

Methodology:
- Measure baseline CPU usage
- Start continuous learning daemon
- Measure CPU usage with learning active
- Calculate overhead percentage

Statistical validation with 95% confidence intervals.
"""

from __future__ import annotations

import asyncio
import os
import time
from statistics import mean, stdev
from typing import Any

import numpy as np
import psutil
import pytest

pytestmark = pytest.mark.tier_e2e


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_background_learning_cpu_overhead(benchmark):
    """Measure CPU overhead of background learning daemon.

    Claim: <2% CPU overhead
    Success criteria: Mean CPU overhead < 2% with 95% confidence
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    # Get current process
    process = psutil.Process(os.getpid())

    # Measure baseline CPU usage
    print("\nMeasuring baseline CPU usage...")
    baseline_samples = []
    for _ in range(20):
        cpu_percent = process.cpu_percent(interval=0.1)
        baseline_samples.append(cpu_percent)
        await asyncio.sleep(0.05)

    baseline_mean = mean(baseline_samples)
    baseline_std = stdev(baseline_samples)

    print(f"Baseline CPU: {baseline_mean:.2f}% ± {baseline_std:.2f}%")

    # Setup learning infrastructure
    stigmergy_learner = StigmergyLearner(
        max_cache_size=1000,
        enable_persistence=False,
        enable_game_model=True,
    )

    learning_engine = ReceiptLearningEngine(
        organism_rssm=None,
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=1,
    )

    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.01,  # Poll every 10ms
        batch_size=5,
    )

    # Warmup
    for i in range(10):
        receipt = _create_mock_receipt(i)
        await daemon._learn_from_receipt(receipt)

    # Start background task that continuously processes receipts
    async def background_learning_task():
        counter = 0
        while True:
            receipt = _create_mock_receipt(counter)
            await daemon._learn_from_receipt(receipt)
            counter += 1
            await asyncio.sleep(0.02)  # ~50 receipts/sec

    learning_task = asyncio.create_task(background_learning_task())

    # Measure CPU usage with learning active
    print("\nMeasuring CPU usage with background learning...")
    learning_samples = []
    try:
        for _ in range(50):
            cpu_percent = process.cpu_percent(interval=0.1)
            learning_samples.append(cpu_percent)
            await asyncio.sleep(0.05)
    finally:
        learning_task.cancel()
        try:
            await learning_task
        except asyncio.CancelledError:
            pass

    learning_mean = mean(learning_samples)
    learning_std = stdev(learning_samples)

    # Calculate overhead
    cpu_overhead = learning_mean - baseline_mean
    cpu_overhead_percent = (cpu_overhead / max(baseline_mean, 1.0)) * 100.0

    # Statistical analysis
    stderr = learning_std / np.sqrt(len(learning_samples))
    ci_95 = 1.96 * stderr

    print("\n" + "=" * 70)
    print("BACKGROUND LEARNING CPU OVERHEAD")
    print("=" * 70)
    print(f"Baseline CPU:         {baseline_mean:.2f}% ± {baseline_std:.2f}%")
    print(f"Learning CPU:         {learning_mean:.2f}% ± {learning_std:.2f}%")
    print(f"Absolute overhead:    {cpu_overhead:.2f}%")
    print(f"Relative overhead:    {cpu_overhead_percent:.2f}%")
    print(f"95% CI:               ± {ci_95:.2f}%")
    print(f"Samples:              {len(learning_samples)}")
    print("=" * 70)

    # Verify claim
    claim_threshold = 2.0
    if cpu_overhead < claim_threshold:
        print(f"✓ PASS: CPU overhead {cpu_overhead:.2f}% < {claim_threshold}%")
    else:
        print(f"✗ FAIL: CPU overhead {cpu_overhead:.2f}% >= {claim_threshold}%")

    benchmark.extra_info.update({
        "baseline_cpu_percent": baseline_mean,
        "learning_cpu_percent": learning_mean,
        "cpu_overhead_percent": cpu_overhead,
        "relative_overhead_percent": cpu_overhead_percent,
        "claim_met": cpu_overhead < claim_threshold,
    })

    assert cpu_overhead < claim_threshold, (
        f"CPU overhead {cpu_overhead:.2f}% >= {claim_threshold}%. "
        f"Baseline: {baseline_mean:.2f}%, Learning: {learning_mean:.2f}%"
    )


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_overhead(benchmark):
    """Measure memory overhead of background learning.

    Ensures memory usage remains bounded during continuous learning.
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    process = psutil.Process(os.getpid())

    # Measure baseline memory
    baseline_mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"\nBaseline memory: {baseline_mem_mb:.2f} MB")

    # Setup learning infrastructure
    stigmergy_learner = StigmergyLearner(
        max_cache_size=1000,
        enable_persistence=False,
        enable_game_model=True,
    )

    learning_engine = ReceiptLearningEngine(
        organism_rssm=None,
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=1,
    )

    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.01,
        batch_size=5,
    )

    # Process many receipts
    print("Processing 1000 receipts...")
    memory_samples = []
    for i in range(1000):
        receipt = _create_mock_receipt(i)
        await daemon._learn_from_receipt(receipt)

        # Sample memory every 100 receipts
        if i % 100 == 0:
            mem_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(mem_mb)

    final_mem_mb = process.memory_info().rss / 1024 / 1024
    memory_overhead_mb = final_mem_mb - baseline_mem_mb
    max_mem_mb = max(memory_samples)
    memory_growth = max_mem_mb - memory_samples[0] if memory_samples else 0

    print("\n" + "=" * 70)
    print("BACKGROUND LEARNING MEMORY OVERHEAD")
    print("=" * 70)
    print(f"Baseline memory:      {baseline_mem_mb:.2f} MB")
    print(f"Final memory:         {final_mem_mb:.2f} MB")
    print(f"Memory overhead:      {memory_overhead_mb:.2f} MB")
    print(f"Max memory:           {max_mem_mb:.2f} MB")
    print(f"Memory growth:        {memory_growth:.2f} MB")
    print("=" * 70)

    # Memory overhead should be reasonable (<500 MB)
    assert memory_overhead_mb < 500.0, (
        f"Memory overhead {memory_overhead_mb:.2f} MB is excessive. "
        f"Possible memory leak."
    )


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_overhead_under_load(benchmark):
    """Measure CPU overhead under heavy load (50+ receipts/sec).

    Tests CPU usage when processing receipts at target throughput.
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    process = psutil.Process(os.getpid())

    # Measure baseline
    baseline_samples = []
    for _ in range(10):
        cpu_percent = process.cpu_percent(interval=0.1)
        baseline_samples.append(cpu_percent)
        await asyncio.sleep(0.05)

    baseline_mean = mean(baseline_samples)

    # Setup
    stigmergy_learner = StigmergyLearner(
        max_cache_size=1000,
        enable_persistence=False,
        enable_game_model=True,
    )

    learning_engine = ReceiptLearningEngine(
        organism_rssm=None,
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=1,
    )

    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.001,
        batch_size=10,
    )

    # Process receipts at high rate (>50/sec)
    async def high_load_task():
        counter = 0
        while True:
            receipt = _create_mock_receipt(counter)
            await daemon._learn_from_receipt(receipt)
            counter += 1
            await asyncio.sleep(0.015)  # ~66 receipts/sec

    task = asyncio.create_task(high_load_task())

    # Measure CPU under load
    load_samples = []
    try:
        for _ in range(30):
            cpu_percent = process.cpu_percent(interval=0.1)
            load_samples.append(cpu_percent)
            await asyncio.sleep(0.05)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    load_mean = mean(load_samples)
    cpu_overhead = load_mean - baseline_mean

    print("\n" + "=" * 70)
    print("CPU OVERHEAD UNDER LOAD (>50 receipts/sec)")
    print("=" * 70)
    print(f"Baseline CPU:         {baseline_mean:.2f}%")
    print(f"Load CPU:             {load_mean:.2f}%")
    print(f"CPU overhead:         {cpu_overhead:.2f}%")
    print("=" * 70)

    # Under load, allow slightly higher overhead (5%)
    assert cpu_overhead < 5.0, f"CPU overhead under load {cpu_overhead:.2f}% >= 5%"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_overhead_statistical_validation(benchmark):
    """Validate CPU overhead claim with statistical rigor.

    Runs multiple trials and computes 95% confidence interval.
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    process = psutil.Process(os.getpid())

    # Measure baseline
    baseline_samples = []
    for _ in range(20):
        cpu_percent = process.cpu_percent(interval=0.1)
        baseline_samples.append(cpu_percent)
        await asyncio.sleep(0.05)

    baseline_mean = mean(baseline_samples)

    # Setup
    stigmergy_learner = StigmergyLearner(
        max_cache_size=1000,
        enable_persistence=False,
        enable_game_model=True,
    )

    learning_engine = ReceiptLearningEngine(
        organism_rssm=None,
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=1,
    )

    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.01,
        batch_size=5,
    )

    # Run multiple trials
    n_trials = 5
    overhead_samples = []

    for _trial in range(n_trials):
        async def learning_task():
            counter = 0
            while True:
                receipt = _create_mock_receipt(counter)
                await daemon._learn_from_receipt(receipt)
                counter += 1
                await asyncio.sleep(0.02)

        task = asyncio.create_task(learning_task())

        trial_samples = []
        try:
            for _ in range(20):
                cpu_percent = process.cpu_percent(interval=0.1)
                trial_samples.append(cpu_percent)
                await asyncio.sleep(0.05)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        trial_mean = mean(trial_samples)
        overhead = trial_mean - baseline_mean
        overhead_samples.append(overhead)

    # Statistical analysis
    mean_overhead = mean(overhead_samples)
    std_overhead = stdev(overhead_samples)
    stderr = std_overhead / np.sqrt(n_trials)
    ci_95 = 1.96 * stderr

    upper_bound = mean_overhead + ci_95

    print("\n" + "=" * 70)
    print("STATISTICAL CPU OVERHEAD VALIDATION")
    print("=" * 70)
    print(f"Trials:               {n_trials}")
    print(f"Baseline CPU:         {baseline_mean:.2f}%")
    print(f"Mean overhead:        {mean_overhead:.2f}% ± {ci_95:.2f}% (95% CI)")
    print(f"Std dev:              {std_overhead:.2f}%")
    print(f"Upper bound (95%):    {upper_bound:.2f}%")
    print("=" * 70)

    # Verify claim with statistical confidence
    claim_threshold = 2.0

    if upper_bound < claim_threshold:
        print(f"✓ PASS: 95% CI upper bound {upper_bound:.2f}% < {claim_threshold}%")
    else:
        print(f"✗ FAIL: 95% CI upper bound {upper_bound:.2f}% >= {claim_threshold}%")

    benchmark.extra_info.update({
        "mean_overhead_percent": mean_overhead,
        "ci_95": ci_95,
        "upper_bound": upper_bound,
        "claim_met": upper_bound < claim_threshold,
    })

    assert upper_bound < claim_threshold, (
        f"95% CI upper bound {upper_bound:.2f}% >= {claim_threshold}%. "
        f"Mean overhead: {mean_overhead:.2f}% ± {ci_95:.2f}%"
    )


def _create_mock_receipt(iteration: int = 0) -> dict[str, Any]:
    """Create a realistic mock receipt for testing."""
    colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
    actions = ["research.web", "build.feature", "debug.error", "test.verify"]

    colony = colonies[iteration % len(colonies)]
    action = actions[iteration % len(actions)]

    return {
        "intent": {
            "action": action,
            "complexity": 0.5 + (iteration % 5) * 0.1,
            "target": f"task_{iteration}",
        },
        "actor": f"colony:{colony}:agent_{iteration}",
        "verifier": {
            "status": "verified" if iteration % 10 != 0 else "failed",
            "h_value": 0.8 if iteration % 10 != 0 else -0.2,
        },
        "duration_ms": 1000 + (iteration % 1000),
        "g_value": 0.5 + (iteration % 5) * 0.1,
        "timestamp": time.time(),
        "correlation_id": f"receipt_{iteration}_{time.time_ns()}",
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--benchmark-only"])
