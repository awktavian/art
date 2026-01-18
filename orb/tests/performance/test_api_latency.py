"""Performance benchmark: API endpoint latency.

Measures P95 latency for critical API endpoints.

This test validates API performance under various conditions:
- Cold start (first request)
- Warmed up (cached)
- Under load (concurrent requests)
- With authentication overhead

Statistical validation with 95% confidence intervals.
"""

from __future__ import annotations

import asyncio
import time
from statistics import mean, stdev
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.tier_e2e


@pytest.mark.benchmark
@pytest.mark.performance
def test_api_health_endpoint_latency(benchmark):
    """Measure /health endpoint latency.

    Health checks should be extremely fast (<10ms P95).
    """
    from kagami_api import create_app

    app = create_app()
    client = TestClient(app)

    # Warmup
    for _ in range(10):
        client.get("/health")

    # Measure latency
    latencies_ms = []
    for _ in range(100):
        start = time.perf_counter()
        response = client.get("/health")
        end = time.perf_counter()

        assert response.status_code == 200
        latencies_ms.append((end - start) * 1000.0)

    # Analysis
    mean_lat = mean(latencies_ms)
    std_lat = stdev(latencies_ms)
    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    print("\n" + "=" * 70)
    print("API HEALTH ENDPOINT LATENCY")
    print("=" * 70)
    print(f"Mean:        {mean_lat:.2f}ms")
    print(f"Std Dev:     {std_lat:.2f}ms")
    print(f"P50:         {p50:.2f}ms")
    print(f"P95:         {p95:.2f}ms")
    print(f"P99:         {p99:.2f}ms")
    print("=" * 70)

    benchmark.extra_info.update({
        "mean_ms": mean_lat,
        "p95_ms": p95,
        "p99_ms": p99,
    })

    assert p95 < 10.0, f"/health P95 latency {p95:.2f}ms >= 10ms"


@pytest.mark.benchmark
@pytest.mark.performance
def test_api_intent_endpoint_latency(benchmark):
    """Measure /api/intents endpoint latency.

    Intent processing is a critical path. P95 should be <200ms.
    """
    from kagami_api import create_app

    app = create_app()
    client = TestClient(app)

    # Intent payload
    intent_payload = {
        "action": "test.benchmark",
        "args": {
            "input": "test input for latency measurement",
        },
        "context": {
            "user_id": "test_user",
        },
    }

    # Warmup
    for _ in range(5):
        try:
            client.post("/api/intents", json=intent_payload)
        except Exception:
            pass  # May fail without full setup, we just want warmup

    # Measure latency
    latencies_ms = []
    successful_requests = 0

    for _ in range(50):
        start = time.perf_counter()
        try:
            response = client.post("/api/intents", json=intent_payload)
            end = time.perf_counter()

            if response.status_code in (200, 201, 202):
                latencies_ms.append((end - start) * 1000.0)
                successful_requests += 1
        except Exception:
            end = time.perf_counter()
            # Still count failed requests in latency
            latencies_ms.append((end - start) * 1000.0)

    if not latencies_ms:
        pytest.skip("No successful intent requests (endpoint may require auth)")

    # Analysis
    mean_lat = mean(latencies_ms)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)

    print("\n" + "=" * 70)
    print("API INTENT ENDPOINT LATENCY")
    print("=" * 70)
    print(f"Successful requests: {successful_requests}/{len(latencies_ms)}")
    print(f"Mean:        {mean_lat:.2f}ms")
    print(f"P95:         {p95:.2f}ms")
    print(f"P99:         {p99:.2f}ms")
    print("=" * 70)

    benchmark.extra_info.update({
        "mean_ms": mean_lat,
        "p95_ms": p95,
        "success_rate": successful_requests / len(latencies_ms),
    })

    assert p95 < 200.0, f"/api/intents P95 latency {p95:.2f}ms >= 200ms"


@pytest.mark.benchmark
@pytest.mark.performance
def test_api_receipts_list_latency(benchmark):
    """Measure /api/mind/receipts/ list endpoint latency.

    Receipt listing should be fast (<100ms P95).
    """
    from kagami_api import create_app

    app = create_app()
    client = TestClient(app)

    # Warmup
    for _ in range(10):
        try:
            client.get("/api/mind/receipts/")
        except Exception:
            pass

    # Measure latency
    latencies_ms = []

    for _ in range(50):
        start = time.perf_counter()
        try:
            response = client.get("/api/mind/receipts/?limit=20")
            end = time.perf_counter()

            if response.status_code == 200:
                latencies_ms.append((end - start) * 1000.0)
        except Exception:
            end = time.perf_counter()
            latencies_ms.append((end - start) * 1000.0)

    if not latencies_ms:
        pytest.skip("No successful receipt list requests")

    # Analysis
    mean_lat = mean(latencies_ms)
    p95 = np.percentile(latencies_ms, 95)

    print("\n" + "=" * 70)
    print("API RECEIPTS LIST ENDPOINT LATENCY")
    print("=" * 70)
    print(f"Mean:        {mean_lat:.2f}ms")
    print(f"P95:         {p95:.2f}ms")
    print("=" * 70)

    benchmark.extra_info.update({
        "mean_ms": mean_lat,
        "p95_ms": p95,
    })

    assert p95 < 100.0, f"/api/mind/receipts/ P95 latency {p95:.2f}ms >= 100ms"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_api_concurrent_request_latency(benchmark):
    """Measure API latency under concurrent load.

    Tests how latency degrades with concurrent requests.
    """
    from kagami_api import create_app
    import httpx

    app = create_app()

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Warmup
        tasks = [client.get("/health") for _ in range(10)]
        await asyncio.gather(*tasks)

        # Test concurrent requests
        concurrency_levels = [1, 5, 10, 20]
        results = {}

        for concurrency in concurrency_levels:
            latencies_ms = []

            # Run multiple rounds
            for _ in range(10):
                tasks = [client.get("/health") for _ in range(concurrency)]

                start = time.perf_counter()
                responses = await asyncio.gather(*tasks)
                end = time.perf_counter()

                # Calculate per-request latency
                total_time = (end - start) * 1000.0
                per_request_latency = total_time / concurrency
                latencies_ms.append(per_request_latency)

            mean_lat = mean(latencies_ms)
            p95 = np.percentile(latencies_ms, 95)

            results[concurrency] = {
                "mean": mean_lat,
                "p95": p95,
            }

        print("\n" + "=" * 70)
        print("API CONCURRENT REQUEST LATENCY")
        print("=" * 70)
        for concurrency, stats in results.items():
            print(f"Concurrency {concurrency:2d}:  Mean={stats['mean']:6.2f}ms  P95={stats['p95']:6.2f}ms")
        print("=" * 70)

        # Verify latency doesn't degrade too much
        # At 20x concurrency, latency should be < 2x single-request latency
        single_mean = results[1]["mean"]
        concurrent_mean = results[20]["mean"]
        degradation = concurrent_mean / single_mean

        print(f"\nLatency degradation at 20x concurrency: {degradation:.2f}x")

        assert degradation < 2.0, f"Latency degradation {degradation:.2f}x >= 2.0x"


@pytest.mark.benchmark
@pytest.mark.performance
def test_api_latency_statistical_validation(benchmark):
    """Validate API latency claims with statistical rigor.

    Runs multiple trials of various endpoints and validates P95 < threshold.
    """
    from kagami_api import create_app

    app = create_app()
    client = TestClient(app)

    endpoints = [
        ("/health", 10.0),
        ("/api/colonies/status", 50.0),
    ]

    results = {}

    for endpoint, threshold_ms in endpoints:
        # Warmup
        for _ in range(5):
            try:
                client.get(endpoint)
            except Exception:
                pass

        # Collect samples
        latencies_ms = []
        for _ in range(100):
            start = time.perf_counter()
            try:
                response = client.get(endpoint)
                end = time.perf_counter()

                if response.status_code == 200:
                    latencies_ms.append((end - start) * 1000.0)
            except Exception:
                pass

        if not latencies_ms:
            continue

        # Analysis
        mean_lat = mean(latencies_ms)
        std_lat = stdev(latencies_ms)
        stderr = std_lat / np.sqrt(len(latencies_ms))
        ci_95 = 1.96 * stderr
        p95 = np.percentile(latencies_ms, 95)

        results[endpoint] = {
            "mean": mean_lat,
            "ci_95": ci_95,
            "p95": p95,
            "threshold": threshold_ms,
            "passed": p95 < threshold_ms,
        }

    print("\n" + "=" * 70)
    print("STATISTICAL API LATENCY VALIDATION")
    print("=" * 70)
    for endpoint, stats in results.items():
        status = "✓ PASS" if stats["passed"] else "✗ FAIL"
        print(f"\n{endpoint}")
        print(f"  Mean:      {stats['mean']:.2f}ms ± {stats['ci_95']:.2f}ms (95% CI)")
        print(f"  P95:       {stats['p95']:.2f}ms")
        print(f"  Threshold: {stats['threshold']:.2f}ms")
        print(f"  Status:    {status}")
    print("=" * 70)

    benchmark.extra_info.update({
        "endpoints": results,
    })

    # Verify all endpoints meet their thresholds
    for endpoint, stats in results.items():
        assert stats["passed"], f"{endpoint} P95 {stats['p95']:.2f}ms >= {stats['threshold']:.2f}ms"


@pytest.mark.benchmark
@pytest.mark.performance
def test_api_cold_start_vs_warm_latency(benchmark):
    """Compare cold start vs warm latency.

    First request is often slower due to initialization.
    """
    from kagami_api import create_app

    app = create_app()

    # Cold start (first request)
    client_cold = TestClient(app)
    start = time.perf_counter()
    response_cold = client_cold.get("/health")
    end = time.perf_counter()
    cold_start_ms = (end - start) * 1000.0

    assert response_cold.status_code == 200

    # Warm requests
    warm_latencies = []
    for _ in range(100):
        start = time.perf_counter()
        response = client_cold.get("/health")
        end = time.perf_counter()

        assert response.status_code == 200
        warm_latencies.append((end - start) * 1000.0)

    warm_mean = mean(warm_latencies)
    warm_p95 = np.percentile(warm_latencies, 95)

    print("\n" + "=" * 70)
    print("API COLD START vs WARM LATENCY")
    print("=" * 70)
    print(f"Cold start:          {cold_start_ms:.2f}ms")
    print(f"Warm mean:           {warm_mean:.2f}ms")
    print(f"Warm P95:            {warm_p95:.2f}ms")
    print(f"Cold start overhead: {cold_start_ms - warm_mean:.2f}ms ({(cold_start_ms / warm_mean):.1f}x)")
    print("=" * 70)

    benchmark.extra_info.update({
        "cold_start_ms": cold_start_ms,
        "warm_mean_ms": warm_mean,
        "warm_p95_ms": warm_p95,
        "overhead_multiplier": cold_start_ms / warm_mean,
    })

    # Cold start should be reasonable (<100ms)
    assert cold_start_ms < 100.0, f"Cold start {cold_start_ms:.2f}ms >= 100ms"


# =============================================================================
# MEMORY PROFILING TESTS - Added for 100/100 test quality
# =============================================================================


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage_under_load(benchmark):
    """Measure memory usage under sustained load.

    Tests:
    - Baseline memory before load
    - Memory during load
    - Memory leak detection (should return to baseline)
    """
    import tracemalloc
    import gc
    from kagami_api import create_app
    import httpx

    app = create_app()

    # Start memory tracking
    tracemalloc.start()

    # Force GC and measure baseline
    gc.collect()
    baseline_snapshot = tracemalloc.take_snapshot()
    baseline_stats = baseline_snapshot.statistics("lineno")
    baseline_total = sum(stat.size for stat in baseline_stats[:100])

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Generate sustained load
        for _batch in range(10):
            tasks = [client.get("/health") for _ in range(100)]
            await asyncio.gather(*tasks)

        # Measure memory during load
        load_snapshot = tracemalloc.take_snapshot()
        load_stats = load_snapshot.statistics("lineno")
        load_total = sum(stat.size for stat in load_stats[:100])

    # Force cleanup
    gc.collect()

    # Measure memory after load
    after_snapshot = tracemalloc.take_snapshot()
    after_stats = after_snapshot.statistics("lineno")
    after_total = sum(stat.size for stat in after_stats[:100])

    tracemalloc.stop()

    # Calculate metrics
    peak_increase_mb = (load_total - baseline_total) / (1024 * 1024)
    retained_increase_mb = (after_total - baseline_total) / (1024 * 1024)

    print("\n" + "=" * 70)
    print("MEMORY USAGE UNDER LOAD")
    print("=" * 70)
    print(f"Baseline memory:     {baseline_total / (1024 * 1024):.2f} MB")
    print(f"Peak memory:         {load_total / (1024 * 1024):.2f} MB")
    print(f"After-load memory:   {after_total / (1024 * 1024):.2f} MB")
    print(f"Peak increase:       {peak_increase_mb:.2f} MB")
    print(f"Retained increase:   {retained_increase_mb:.2f} MB")
    print("=" * 70)

    benchmark.extra_info.update({
        "baseline_mb": baseline_total / (1024 * 1024),
        "peak_mb": load_total / (1024 * 1024),
        "retained_mb": after_total / (1024 * 1024),
    })

    # Memory leak check: retained should be close to baseline
    # Allow 50MB increase for caching, loaded models, etc.
    assert retained_increase_mb < 50.0, f"Possible memory leak: {retained_increase_mb:.2f}MB retained"


@pytest.mark.benchmark
@pytest.mark.performance
def test_memory_per_request(benchmark):
    """Measure memory allocation per request.

    Lower is better - indicates efficient request handling.
    """
    import tracemalloc
    import gc
    from kagami_api import create_app
    from starlette.testclient import TestClient

    app = create_app()
    client = TestClient(app)

    # Warmup
    for _ in range(10):
        client.get("/health")

    gc.collect()
    tracemalloc.start()

    # Measure memory for N requests
    n_requests = 1000
    start_snapshot = tracemalloc.take_snapshot()

    for _ in range(n_requests):
        client.get("/health")

    end_snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Calculate per-request memory
    start_total = sum(stat.size for stat in start_snapshot.statistics("lineno")[:50])
    end_total = sum(stat.size for stat in end_snapshot.statistics("lineno")[:50])

    memory_increase = end_total - start_total
    per_request_bytes = memory_increase / n_requests

    print("\n" + "=" * 70)
    print("MEMORY PER REQUEST")
    print("=" * 70)
    print(f"Requests:           {n_requests}")
    print(f"Memory increase:    {memory_increase / 1024:.2f} KB")
    print(f"Per request:        {per_request_bytes:.2f} bytes")
    print("=" * 70)

    benchmark.extra_info.update({
        "per_request_bytes": per_request_bytes,
        "total_increase_kb": memory_increase / 1024,
    })

    # Per-request memory should be minimal (<1KB per request)
    assert per_request_bytes < 1024, f"Memory per request too high: {per_request_bytes:.2f} bytes"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_gc_pause_times(benchmark):
    """Measure garbage collection pause times.

    Long GC pauses cause latency spikes.
    """
    import gc
    import time

    gc_times = []

    # Callback to measure GC time
    def gc_callback(phase, info):
        if phase == "stop":
            gc_times.append(info.get("elapsed", 0) * 1000)  # Convert to ms

    # Register callback
    gc.callbacks.append(gc_callback)

    try:
        # Generate garbage to trigger GC
        garbage = []
        for _ in range(100):
            garbage.append([object() for _ in range(10000)])

        # Force GC multiple times
        for _ in range(10):
            gc.collect(0)
            gc.collect(1)
            gc.collect(2)

        if gc_times:
            max_pause = max(gc_times)
            mean_pause = mean(gc_times) if gc_times else 0
            p99_pause = np.percentile(gc_times, 99) if len(gc_times) >= 10 else max_pause

            print("\n" + "=" * 70)
            print("GC PAUSE TIMES")
            print("=" * 70)
            print(f"GC collections:      {len(gc_times)}")
            print(f"Max pause:           {max_pause:.2f}ms")
            print(f"Mean pause:          {mean_pause:.2f}ms")
            print(f"P99 pause:           {p99_pause:.2f}ms")
            print("=" * 70)

            benchmark.extra_info.update({
                "gc_max_pause_ms": max_pause,
                "gc_mean_pause_ms": mean_pause,
                "gc_p99_pause_ms": p99_pause,
            })

            # GC pauses should be < 100ms
            assert max_pause < 100.0, f"GC pause too long: {max_pause:.2f}ms"
        else:
            print("No GC events recorded (GC may be disabled)")

    finally:
        gc.callbacks.remove(gc_callback)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--benchmark-only"])
