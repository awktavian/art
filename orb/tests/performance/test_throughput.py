"""Performance benchmark: Receipt throughput.

Verifies claim: ~50 receipts/second throughput

Tests measure sustained throughput under various conditions:
- Single-threaded processing
- Concurrent processing
- Batch processing
- Real-world load patterns

Statistical validation with 95% confidence intervals.
"""

from __future__ import annotations

import asyncio
import time
from statistics import mean, stdev
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.tier_e2e


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_receipt_throughput_sustained(benchmark):
    """Measure sustained receipt processing throughput.

    Claim: ~50 receipts/second
    Success criteria: Mean throughput >= 50 receipts/sec over 10 seconds
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

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
        poll_interval=0.001,
        batch_size=5,
    )

    # Warmup
    for i in range(20):
        receipt = _create_mock_receipt(i)
        await daemon._learn_from_receipt(receipt)

    # Sustained throughput test
    duration_seconds = 10.0
    receipts_processed = 0
    start_time = time.perf_counter()

    while (time.perf_counter() - start_time) < duration_seconds:
        receipt = _create_mock_receipt(receipts_processed)
        await daemon._learn_from_receipt(receipt)
        receipts_processed += 1

    end_time = time.perf_counter()
    elapsed = end_time - start_time

    throughput = receipts_processed / elapsed

    print("\n" + "=" * 70)
    print("SUSTAINED RECEIPT THROUGHPUT")
    print("=" * 70)
    print(f"Duration:             {elapsed:.2f}s")
    print(f"Receipts processed:   {receipts_processed}")
    print(f"Throughput:           {throughput:.2f} receipts/sec")
    print(f"Avg latency:          {1000.0 / throughput:.2f}ms per receipt")
    print("=" * 70)

    # Verify claim
    claim_threshold = 50.0
    if throughput >= claim_threshold:
        print(f"✓ PASS: Throughput {throughput:.2f} >= {claim_threshold} receipts/sec")
    else:
        print(f"✗ FAIL: Throughput {throughput:.2f} < {claim_threshold} receipts/sec")

    benchmark.extra_info.update({
        "receipts_per_sec": throughput,
        "receipts_processed": receipts_processed,
        "duration_sec": elapsed,
        "claim_met": throughput >= claim_threshold,
    })

    assert throughput >= claim_threshold, (
        f"Throughput {throughput:.2f} receipts/sec < {claim_threshold} receipts/sec. "
        f"Processed {receipts_processed} receipts in {elapsed:.2f}s"
    )


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_receipt_throughput_concurrent(benchmark):
    """Measure concurrent receipt processing throughput.

    Tests parallel processing with multiple concurrent receipts.
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

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

    # Warmup
    tasks = [daemon._learn_from_receipt(_create_mock_receipt(i)) for i in range(20)]
    await asyncio.gather(*tasks)

    # Concurrent throughput test
    n_receipts = 500
    concurrency = 10  # Process 10 receipts concurrently

    start_time = time.perf_counter()

    # Process in batches of 'concurrency'
    for batch_start in range(0, n_receipts, concurrency):
        batch_tasks = [
            daemon._learn_from_receipt(_create_mock_receipt(i))
            for i in range(batch_start, min(batch_start + concurrency, n_receipts))
        ]
        await asyncio.gather(*batch_tasks)

    end_time = time.perf_counter()
    elapsed = end_time - start_time

    throughput = n_receipts / elapsed

    print("\n" + "=" * 70)
    print("CONCURRENT RECEIPT THROUGHPUT")
    print("=" * 70)
    print(f"Receipts:             {n_receipts}")
    print(f"Concurrency:          {concurrency}")
    print(f"Duration:             {elapsed:.2f}s")
    print(f"Throughput:           {throughput:.2f} receipts/sec")
    print("=" * 70)

    # With concurrency, should exceed single-threaded throughput
    assert throughput >= 50.0, f"Concurrent throughput {throughput:.2f} < 50 receipts/sec"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_receipt_batch_throughput(benchmark):
    """Measure batch processing throughput.

    Tests throughput when processing receipts in batches.
    """
    from kagami.core.learning import (
        create_continuous_mind,
        ReceiptLearningEngine,
        ReceiptBatch,
    )
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

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
        batch_size=20,
    )

    # Warmup
    warmup_batch = ReceiptBatch(receipts=[_create_mock_receipt(i) for i in range(20)])
    await daemon._process_batch(warmup_batch)

    # Batch throughput test
    batch_size = 20
    n_batches = 25
    total_receipts = batch_size * n_batches

    start_time = time.perf_counter()

    for batch_idx in range(n_batches):
        batch = ReceiptBatch(
            receipts=[
                _create_mock_receipt(batch_idx * batch_size + i)
                for i in range(batch_size)
            ]
        )
        await daemon._process_batch(batch)

    end_time = time.perf_counter()
    elapsed = end_time - start_time

    throughput = total_receipts / elapsed

    print("\n" + "=" * 70)
    print("BATCH RECEIPT THROUGHPUT")
    print("=" * 70)
    print(f"Batch size:           {batch_size}")
    print(f"Number of batches:    {n_batches}")
    print(f"Total receipts:       {total_receipts}")
    print(f"Duration:             {elapsed:.2f}s")
    print(f"Throughput:           {throughput:.2f} receipts/sec")
    print(f"Batch latency:        {1000.0 * elapsed / n_batches:.2f}ms per batch")
    print("=" * 70)

    # Batch processing should be more efficient
    assert throughput >= 50.0, f"Batch throughput {throughput:.2f} < 50 receipts/sec"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_receipt_throughput_statistical_validation(benchmark):
    """Validate throughput claim with statistical rigor.

    Runs multiple trials and computes 95% confidence interval.
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

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
        batch_size=5,
    )

    # Warmup
    for i in range(20):
        receipt = _create_mock_receipt(i)
        await daemon._learn_from_receipt(receipt)

    # Run multiple trials
    n_trials = 10
    receipts_per_trial = 100
    throughputs = []

    for trial in range(n_trials):
        start_time = time.perf_counter()

        for i in range(receipts_per_trial):
            receipt = _create_mock_receipt(trial * receipts_per_trial + i)
            await daemon._learn_from_receipt(receipt)

        end_time = time.perf_counter()
        elapsed = end_time - start_time
        throughput = receipts_per_trial / elapsed
        throughputs.append(throughput)

    # Statistical analysis
    mean_throughput = mean(throughputs)
    std_throughput = stdev(throughputs)
    stderr = std_throughput / np.sqrt(n_trials)
    ci_95 = 1.96 * stderr

    p5 = np.percentile(throughputs, 5)
    p50 = np.percentile(throughputs, 50)
    p95 = np.percentile(throughputs, 95)

    print("\n" + "=" * 70)
    print("STATISTICAL THROUGHPUT VALIDATION")
    print("=" * 70)
    print(f"Trials:               {n_trials}")
    print(f"Receipts per trial:   {receipts_per_trial}")
    print(f"Mean throughput:      {mean_throughput:.2f} ± {ci_95:.2f} receipts/sec (95% CI)")
    print(f"Std dev:              {std_throughput:.2f}")
    print(f"P5:                   {p5:.2f} receipts/sec")
    print(f"P50 (median):         {p50:.2f} receipts/sec")
    print(f"P95:                  {p95:.2f} receipts/sec")
    print(f"Min:                  {min(throughputs):.2f} receipts/sec")
    print(f"Max:                  {max(throughputs):.2f} receipts/sec")
    print("=" * 70)

    # Verify claim with statistical confidence
    claim_threshold = 50.0
    lower_bound = mean_throughput - ci_95

    if lower_bound >= claim_threshold:
        print(f"✓ PASS: 95% CI lower bound {lower_bound:.2f} >= {claim_threshold} receipts/sec")
    else:
        print(f"✗ FAIL: 95% CI lower bound {lower_bound:.2f} < {claim_threshold} receipts/sec")

    benchmark.extra_info.update({
        "mean_receipts_per_sec": mean_throughput,
        "ci_95": ci_95,
        "p5": p5,
        "p50": p50,
        "p95": p95,
        "claim_met": lower_bound >= claim_threshold,
    })

    assert lower_bound >= claim_threshold, (
        f"95% CI lower bound {lower_bound:.2f} receipts/sec < {claim_threshold} receipts/sec. "
        f"Mean throughput: {mean_throughput:.2f} ± {ci_95:.2f} receipts/sec"
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
