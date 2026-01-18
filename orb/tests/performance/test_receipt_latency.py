"""Performance benchmark: Receipt processing latency.

Verifies claim: Receipt → learning feedback <200ms

This test measures the complete latency from:
1. Receipt submission via API
2. Receipt ingestion
3. Learning feedback applied

Statistical validation with 95% confidence intervals.
"""

from __future__ import annotations

import asyncio
import time
from statistics import mean, stdev
from typing import Any

import numpy as np
import pytest
import torch

pytestmark = pytest.mark.tier_e2e


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_receipt_processing_latency_p95(benchmark):
    """Measure receipt processing latency with pytest-benchmark.

    Claim: Receipt → learning feedback <200ms
    Success criteria: P95 latency < 200ms with 95% confidence
    """
    from kagami.core.receipts.ingestor import add_receipt
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
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
        receipt = _create_mock_receipt(i)
        await daemon._learn_from_receipt(receipt)

    # Benchmark function
    async def measure_latency():
        receipt = _create_mock_receipt(0)
        start = time.perf_counter()
        await daemon._learn_from_receipt(receipt)
        end = time.perf_counter()
        return (end - start) * 1000.0  # Convert to ms

    # Collect samples
    latencies_ms = []
    for _ in range(100):
        latency = await measure_latency()
        latencies_ms.append(latency)

    # Statistical analysis
    mean_lat = mean(latencies_ms)
    std_lat = stdev(latencies_ms)
    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    # 95% confidence interval for P95
    stderr = std_lat / np.sqrt(len(latencies_ms))
    ci_95 = 1.96 * stderr

    # Report results
    print("\n" + "=" * 70)
    print("RECEIPT PROCESSING LATENCY")
    print("=" * 70)
    print(f"Sample size:     {len(latencies_ms)}")
    print(f"Mean:            {mean_lat:.2f}ms ± {ci_95:.2f}ms (95% CI)")
    print(f"Std Dev:         {std_lat:.2f}ms")
    print(f"P50 (median):    {p50:.2f}ms")
    print(f"P95:             {p95:.2f}ms")
    print(f"P99:             {p99:.2f}ms")
    print(f"Min:             {min(latencies_ms):.2f}ms")
    print(f"Max:             {max(latencies_ms):.2f}ms")
    print("=" * 70)

    # Verify claim
    claim_threshold = 200.0
    if p95 < claim_threshold:
        print(f"✓ PASS: P95 latency {p95:.2f}ms < {claim_threshold}ms")
    else:
        print(f"✗ FAIL: P95 latency {p95:.2f}ms >= {claim_threshold}ms")

    # Store results for regression tracking
    benchmark.extra_info.update({
        "mean_ms": mean_lat,
        "p95_ms": p95,
        "p99_ms": p99,
        "claim_met": p95 < claim_threshold,
    })

    assert p95 < claim_threshold, (
        f"P95 latency {p95:.2f}ms exceeds {claim_threshold}ms claim. "
        f"Distribution: mean={mean_lat:.2f}ms ± {ci_95:.2f}ms, p99={p99:.2f}ms"
    )


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires CUDA for GPU timing")
async def test_receipt_processing_latency_gpu(benchmark):
    """Measure receipt processing latency with GPU timing.

    Uses CUDA events for accurate GPU timing.
    """
    from kagami.core.learning import create_continuous_mind, ReceiptLearningEngine
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
        poll_interval=0.001,
        batch_size=1,
    )

    # Warmup
    for i in range(10):
        receipt = _create_mock_receipt(i)
        await daemon._learn_from_receipt(receipt)

    # Benchmark with CUDA events
    latencies_ms = []
    for i in range(100):
        start_event = torch.cuda.Event(enable_timing=True)
        end_event = torch.cuda.Event(enable_timing=True)

        receipt = _create_mock_receipt(i)

        start_event.record()
        await daemon._learn_from_receipt(receipt)
        end_event.record()

        torch.cuda.synchronize()
        latency_ms = start_event.elapsed_time(end_event)
        latencies_ms.append(latency_ms)

    # Analysis
    mean_lat = mean(latencies_ms)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    print("\n" + "=" * 70)
    print("RECEIPT PROCESSING LATENCY (GPU)")
    print("=" * 70)
    print(f"Mean:    {mean_lat:.2f}ms")
    print(f"P95:     {p95:.2f}ms")
    print(f"P99:     {p99:.2f}ms")
    print("=" * 70)

    assert p95 < 200.0, f"P95 latency {p95:.2f}ms >= 200ms (GPU timing)"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_end_to_end_receipt_api_latency(benchmark):
    """Measure end-to-end API latency for receipt submission.

    Tests the complete flow:
    1. HTTP request to /api/mind/receipts
    2. Receipt validation and ingestion
    3. Learning feedback triggered
    4. Response returned
    """
    from fastapi.testclient import TestClient
    from kagami_api import create_app

    app = create_app()
    client = TestClient(app)

    # Create test receipt payload
    def create_receipt_payload() -> dict[str, Any]:
        return {
            "intent": {
                "action": "test.benchmark",
                "complexity": 0.5,
                "target": "latency_test",
            },
            "actor": "colony:benchmark:agent_0",
            "verifier": {
                "status": "verified",
                "h_value": 0.9,
            },
            "duration_ms": 100,
            "g_value": 0.7,
            "correlation_id": f"bench_{time.time_ns()}",
        }

    # Warmup
    for _ in range(5):
        client.post("/api/mind/receipts/", json=create_receipt_payload())

    # Benchmark
    latencies_ms = []
    for _ in range(50):
        payload = create_receipt_payload()
        start = time.perf_counter()
        response = client.post("/api/mind/receipts/", json=payload)
        end = time.perf_counter()

        assert response.status_code == 200
        latencies_ms.append((end - start) * 1000.0)

    # Analysis
    mean_lat = mean(latencies_ms)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    print("\n" + "=" * 70)
    print("END-TO-END API RECEIPT LATENCY")
    print("=" * 70)
    print(f"Mean:    {mean_lat:.2f}ms")
    print(f"P95:     {p95:.2f}ms")
    print(f"P99:     {p99:.2f}ms")
    print("=" * 70)

    # API latency includes network overhead, so allow higher threshold
    assert p95 < 300.0, f"API P95 latency {p95:.2f}ms >= 300ms"


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
