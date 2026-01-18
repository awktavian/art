"""Performance validation for receipt → learning feedback loop latency.

Documentation claims <200ms for receipt → learning feedback loop.
This test validates that claim with statistical rigor.

TEST METHODOLOGY:
- Use CUDA events for accurate GPU timing (wall clock as fallback)
- Warmup iterations to stabilize caches
- Statistical validation: P95 latency must be < 200ms
- Measure full cycle: receipt submission → learning update applied

WHEN TO RUN:
- Marked as @pytest.mark.benchmark (excluded from regular CI)
- Run manually: pytest tests/performance/test_receipt_learning_latency.py -v -s -n 0
- Run on GPU: Requires CUDA for most accurate timing (fallback works on CPU)
- Part of Tier 3 (E2E) test suite

REFERENCES:
- Grove research: scripts/benchmark/benchmark_world_model.py
- Implementation: kagami/core/learning/continuous_mind.py
- Claim source: Documentation states <200ms learning feedback loop

Created: December 16, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_e2e



import asyncio
import time
from statistics import mean, stdev

import numpy as np
import torch


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.tier_e2e
@pytest.mark.asyncio
@pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires CUDA for accurate timing")
async def test_receipt_learning_latency_under_200ms():
    """Validate <200ms claim for receipt → learning feedback loop.

    This test measures the FULL latency from receipt submission to learning
    update applied. Uses CUDA events for accurate GPU timing.

    Success criteria: P95 latency < 200ms
    """
    from kagami.core.learning import (
        ContinuousMindDaemon,
        ReceiptLearningEngine,
        create_continuous_mind,
    )
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    # Setup learning infrastructure
    stigmergy_learner = StigmergyLearner(
        max_cache_size=100,
        enable_persistence=False,
        enable_game_model=True,
    )

    learning_engine = ReceiptLearningEngine(
        organism_rssm=None,  # Not needed for latency test
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=1,
    )

    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.001,  # Fast polling for latency test
        batch_size=1,  # Process receipts individually
    )

    # Warmup: stabilize caches and JIT compilation
    print("\n[Warmup] Running 10 warmup iterations...")
    for i in range(10):
        receipt = create_mock_receipt(iteration=i)
        await daemon._learn_from_receipt(receipt)

    # Benchmark with CUDA events for accurate timing
    latencies_ms = []
    n_iterations = 100

    print(f"[Benchmark] Running {n_iterations} measurement iterations...")

    for i in range(n_iterations):
        # Create CUDA events
        start_event = torch.cuda.Event(enable_timing=True)
        end_event = torch.cuda.Event(enable_timing=True)

        receipt = create_mock_receipt(iteration=i)

        # Measure full learning cycle
        start_event.record()
        await daemon._learn_from_receipt(receipt)
        end_event.record()

        # Wait for GPU operations to complete
        torch.cuda.synchronize()

        # Get elapsed time in milliseconds
        latency_ms = start_event.elapsed_time(end_event)
        latencies_ms.append(latency_ms)

    # Statistical analysis
    mean_lat = mean(latencies_ms)
    std_lat = stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0
    min_lat = min(latencies_ms)
    max_lat = max(latencies_ms)

    # Percentiles
    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    # Report results
    print("\n" + "=" * 60)
    print("Receipt → Learning Feedback Loop Latency")
    print("=" * 60)
    print(f"Iterations:  {n_iterations}")
    print(f"Mean:        {mean_lat:.2f}ms")
    print(f"Std Dev:     {std_lat:.2f}ms")
    print(f"Min:         {min_lat:.2f}ms")
    print(f"Max:         {max_lat:.2f}ms")
    print(f"P50:         {p50:.2f}ms")
    print(f"P95:         {p95:.2f}ms")
    print(f"P99:         {p99:.2f}ms")
    print("=" * 60)

    # SLO validation
    if p95 < 200.0:
        print(f"✓ PASS: P95 latency {p95:.2f}ms < 200ms")
    else:
        print(f"✗ FAIL: P95 latency {p95:.2f}ms >= 200ms")

    # Assert P95 < 200ms (primary SLO)
    assert p95 < 200.0, (
        f"P95 latency {p95:.2f}ms exceeds 200ms SLO. "
        f"Distribution: mean={mean_lat:.2f}ms, std={std_lat:.2f}ms, max={max_lat:.2f}ms"
    )

    # Sanity check: P99 should also be reasonable
    assert p99 < 500.0, f"P99 latency {p99:.2f}ms is unreasonably high (sanity check)"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.tier_e2e
@pytest.mark.asyncio
async def test_receipt_learning_latency_cpu_fallback():
    """CPU fallback test for receipt → learning latency.

    Uses wall clock timing (less accurate than CUDA events).
    This test always runs, even without GPU.

    Success criteria: P95 latency < 200ms (may be less reliable on CPU)
    """
    from kagami.core.learning import (
        ReceiptLearningEngine,
        create_continuous_mind,
    )
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    # Setup learning infrastructure
    stigmergy_learner = StigmergyLearner(
        max_cache_size=100,
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
        batch_size=1,
    )

    # Warmup
    for i in range(10):
        receipt = create_mock_receipt(iteration=i)
        await daemon._learn_from_receipt(receipt)

    # Benchmark with wall clock timing
    latencies_ms = []
    n_iterations = 100

    for i in range(n_iterations):
        receipt = create_mock_receipt(iteration=i)

        # Measure with perf_counter (high resolution)
        start = time.perf_counter()
        await daemon._learn_from_receipt(receipt)
        end = time.perf_counter()

        latency_ms = (end - start) * 1000.0
        latencies_ms.append(latency_ms)

    # Statistical analysis
    mean_lat = mean(latencies_ms)
    std_lat = stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0
    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    # Report results
    print("\n" + "=" * 60)
    print("Receipt → Learning Feedback Loop Latency (CPU)")
    print("=" * 60)
    print(f"Iterations:  {n_iterations}")
    print(f"Mean:        {mean_lat:.2f}ms")
    print(f"Std Dev:     {std_lat:.2f}ms")
    print(f"P50:         {p50:.2f}ms")
    print(f"P95:         {p95:.2f}ms")
    print(f"P99:         {p99:.2f}ms")
    print("=" * 60)

    # Note: CPU timing may be less reliable, so we're more lenient
    if p95 < 200.0:
        print(f"✓ PASS: P95 latency {p95:.2f}ms < 200ms")
    else:
        print(f"⚠ WARNING: P95 latency {p95:.2f}ms >= 200ms (CPU timing, may be inaccurate)")

    # Assert with warning
    assert p95 < 200.0, (
        f"P95 latency {p95:.2f}ms exceeds 200ms SLO (CPU timing). "
        f"Distribution: mean={mean_lat:.2f}ms, std={std_lat:.2f}ms"
    )


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.tier_e2e
@pytest.mark.asyncio
async def test_receipt_batch_processing_latency():
    """Test batch processing latency (multiple receipts).

    Validates that batch processing maintains <200ms P95 per receipt
    even when processing multiple receipts in a batch.

    Success criteria: P95 latency per receipt < 200ms
    """
    from kagami.core.learning import (
        ReceiptBatch,
        create_continuous_mind,
    )
    from kagami.core.learning.receipt_learning import ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

    # Setup
    stigmergy_learner = StigmergyLearner(
        max_cache_size=100,
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
        batch_size=5,
    )

    # Warmup
    warmup_batch = ReceiptBatch(receipts=[create_mock_receipt(iteration=i) for i in range(5)])
    await daemon._process_batch(warmup_batch)

    # Benchmark batch processing
    latencies_per_receipt_ms = []
    n_iterations = 20  # Fewer iterations since we process 5 receipts each time

    for i in range(n_iterations):
        batch = ReceiptBatch(receipts=[create_mock_receipt(iteration=i * 5 + j) for j in range(5)])

        start = time.perf_counter()
        await daemon._process_batch(batch)
        end = time.perf_counter()

        total_latency_ms = (end - start) * 1000.0
        latency_per_receipt_ms = total_latency_ms / len(batch.receipts)
        latencies_per_receipt_ms.append(latency_per_receipt_ms)

    # Statistical analysis
    mean_lat = mean(latencies_per_receipt_ms)
    p95 = np.percentile(latencies_per_receipt_ms, 95)

    print("\n" + "=" * 60)
    print("Receipt Batch Processing Latency (per receipt)")
    print("=" * 60)
    print("Batch size:  5 receipts")
    print(f"Iterations:  {n_iterations}")
    print(f"Mean:        {mean_lat:.2f}ms per receipt")
    print(f"P95:         {p95:.2f}ms per receipt")
    print("=" * 60)

    assert p95 < 200.0, f"P95 latency per receipt {p95:.2f}ms exceeds 200ms in batch processing"


def create_mock_receipt(iteration: int = 0) -> dict:
    """Create a realistic mock receipt for testing.

    Args:
        iteration: Iteration number for variation

    Returns:
        Mock receipt dictionary with realistic structure
    """
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
        "correlation_id": f"receipt_{iteration}",
    }


if __name__ == "__main__":
    # Allow running test directly for quick validation
    pytest.main([__file__, "-v", "-s"])
