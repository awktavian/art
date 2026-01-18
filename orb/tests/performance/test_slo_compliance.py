"""SLO Compliance Tests - Performance regression prevention.

CREATED: December 22, 2025
PURPOSE: Automated verification of all SLO targets from docs/SLO.md

RUN: pytest tests/performance/test_slo_compliance.py -v -s

MARKERS:
- @pytest.mark.slo: All SLO compliance tests
- @pytest.mark.critical: Tests for critical path SLOs (safety, API)
- @pytest.mark.performance: Performance benchmarks
"""

from __future__ import annotations

import pytest
from typing import Any

import statistics
import time
from collections.abc import Callable

import numpy as np


def measure_latency(
    fn: Callable,
    *args,
    warmup: int = 10,
    iterations: int = 100,
    **kwargs: Any,
) -> dict[str, float]:
    """Measure latency statistics for a function.

    Args:
        fn: Function to measure
        *args: Positional arguments for fn
        warmup: Number of warmup iterations
        iterations: Number of measurement iterations
        **kwargs: Keyword arguments for fn

    Returns:
        Dictionary with p50, p95, p99, avg, min, max in milliseconds
    """
    # Warmup
    for _ in range(warmup):
        fn(*args, **kwargs)

    # Measure
    latencies = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        latencies.append(duration_ms)

    # Calculate percentiles
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "p50": sorted_latencies[int(n * 0.50)],
        "p95": sorted_latencies[int(n * 0.95)],
        "p99": sorted_latencies[int(n * 0.99)],
        "avg": statistics.mean(latencies),
        "min": min(latencies),
        "max": max(latencies),
    }


async def measure_latency_async(
    fn: Callable,
    *args,
    warmup: int = 10,
    iterations: int = 100,
    **kwargs: Any,
) -> dict[str, float]:
    """Async version of measure_latency."""
    # Warmup
    for _ in range(warmup):
        await fn(*args, **kwargs)

    # Measure
    latencies = []
    for _ in range(iterations):
        start = time.perf_counter()
        await fn(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        latencies.append(duration_ms)

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "p50": sorted_latencies[int(n * 0.50)],
        "p95": sorted_latencies[int(n * 0.95)],
        "p99": sorted_latencies[int(n * 0.99)],
        "avg": statistics.mean(latencies),
        "min": min(latencies),
        "max": max(latencies),
    }


class TestSafetySLO:
    """Safety (CBF) SLO compliance tests."""

    @pytest.mark.slo
    @pytest.mark.critical
    def test_cbf_barrier_function_p99_under_10ms(self) -> None:
        """CBF barrier_function() MUST respond in <10ms p99."""
        from kagami.core.safety.control_barrier_function import (
            ControlBarrierFunction,
            SafetyState,
        )

        cbf = ControlBarrierFunction()

        def run_barrier() -> None:
            state = SafetyState(
                threat_score=np.random.rand(),
                uncertainty=np.random.rand(),
                complexity=np.random.rand(),
                predictive_risk=np.random.rand(),
            )
            return cbf.barrier_function(state)  # type: ignore[operator]

        stats = measure_latency(run_barrier, iterations=1000)

        print("\nCBF barrier_function SLO check:")
        print(f"  p50: {stats['p50']:.4f}ms")
        print(f"  p95: {stats['p95']:.4f}ms")
        print(f"  p99: {stats['p99']:.4f}ms (target: <10ms)")

        assert stats["p99"] < 10.0, f"SLO VIOLATION: p99={stats['p99']:.2f}ms > 10ms"


class TestWorldModelSLO:
    """World Model SLO compliance tests."""

    @pytest.mark.slo
    def test_world_model_forward_p99_under_200ms(self) -> None:
        """World model forward() MUST respond in <200ms p99.

        NOTE: Uses extended warmup (20 iterations) to account for JIT compilation
        and memory allocation during first few calls.
        """
        import torch
        from kagami.core.world_model.kagami_world_model import create_model

        model = create_model(preset="minimal", device="cpu")
        model.eval()

        def run_forward() -> None:
            x = torch.randn(1, 32)
            with torch.no_grad():
                return model(x)

        # Extended warmup to stabilize performance (JIT compilation, memory alloc)
        stats = measure_latency(run_forward, warmup=20, iterations=50)

        print("\nWorld model forward() SLO check:")
        print(f"  p50: {stats['p50']:.2f}ms")
        print(f"  p95: {stats['p95']:.2f}ms")
        print(f"  p99: {stats['p99']:.2f}ms (target: <200ms)")

        assert stats["p99"] < 200.0, f"SLO VIOLATION: p99={stats['p99']:.2f}ms > 200ms"


class TestE8QuantizationSLO:
    """E8 Quantization SLO compliance tests."""

    @pytest.mark.slo
    def test_nearest_e8_p99_under_1ms(self) -> None:
        """nearest_e8() MUST respond in <1ms p99."""
        import torch
        from kagami_math.e8 import nearest_e8

        def run_quantize() -> Any:
            vec = torch.randn(8)
            return nearest_e8(vec)

        stats = measure_latency(run_quantize, iterations=1000)

        print("\nnearest_e8() SLO check:")
        print(f"  p50: {stats['p50']:.4f}ms")
        print(f"  p95: {stats['p95']:.4f}ms")
        print(f"  p99: {stats['p99']:.4f}ms (target: <1ms)")

        assert stats["p99"] < 1.0, f"SLO VIOLATION: p99={stats['p99']:.4f}ms > 1ms"

    @pytest.mark.slo
    def test_cached_quantizer_p99_under_point1ms(self) -> Any:
        """CachedE8Quantizer cache hits MUST respond in <0.1ms p99."""
        import torch
        from kagami_math.e8 import create_cached_quantizer

        quantizer = create_cached_quantizer(max_cache_size=1024)

        # Pre-populate cache with test vectors
        test_vecs = [torch.randn(8) for _ in range(100)]
        for vec in test_vecs:
            quantizer(vec.unsqueeze(0))

        def run_cached_quantize() -> Any:
            # Use cached vectors for hits
            vec = test_vecs[np.random.randint(0, 100)]
            return quantizer(vec.unsqueeze(0))

        stats = measure_latency(run_cached_quantize, iterations=1000)

        print("\nCachedE8Quantizer (hits) SLO check:")
        print(f"  p50: {stats['p50']:.4f}ms")
        print(f"  p95: {stats['p95']:.4f}ms")
        print(f"  p99: {stats['p99']:.4f}ms (target: <0.1ms)")

        # Cache hits should be very fast
        assert stats["p99"] < 0.1, f"SLO VIOLATION: p99={stats['p99']:.4f}ms > 0.1ms"


class TestFanoRouterSLO:
    """Fano Router SLO compliance tests."""

    @pytest.mark.slo
    def test_fano_route_p99_under_10ms(self) -> None:
        """Fano router MUST respond in <10ms p99."""
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        router = create_fano_router()

        def run_route() -> Any:
            return router.route(
                action="implement",
                params={"feature": "test"},
                complexity=0.5,
                context={"domain": "test"},
            )

        stats = measure_latency(run_route, iterations=1000)

        print("\nFano router SLO check:")
        print(f"  p50: {stats['p50']:.4f}ms")
        print(f"  p95: {stats['p95']:.4f}ms")
        print(f"  p99: {stats['p99']:.4f}ms (target: <10ms)")

        assert stats["p99"] < 10.0, f"SLO VIOLATION: p99={stats['p99']:.4f}ms > 10ms"


class TestInstinctSLO:
    """System 1 Instinct SLO compliance tests."""

    @pytest.mark.slo
    @pytest.mark.asyncio
    async def test_prediction_instinct_p95_under_5ms(self) -> None:
        """Prediction instinct MUST respond in <5ms p95."""
        from kagami.core.instincts.prediction_instinct import PredictionInstinct

        instinct = PredictionInstinct()
        action = {"action": "read", "target": "file"}

        stats = await measure_latency_async(instinct.predict, action, iterations=100)

        print("\nPredictionInstinct SLO check:")
        print(f"  p50: {stats['p50']:.4f}ms")
        print(f"  p95: {stats['p95']:.4f}ms (target: <5ms)")
        print(f"  p99: {stats['p99']:.4f}ms")

        assert stats["p95"] < 5.0, f"SLO VIOLATION: p95={stats['p95']:.4f}ms > 5ms"

    @pytest.mark.slo
    @pytest.mark.asyncio
    async def test_threat_instinct_p95_under_5ms(self) -> None:
        """Threat instinct MUST respond in <5ms p95."""
        from kagami.core.instincts.threat_instinct import ThreatInstinct

        instinct = ThreatInstinct()
        action = {"action": "read", "target": "public_data"}

        stats = await measure_latency_async(instinct.assess, action, iterations=100)

        print("\nThreatInstinct SLO check:")
        print(f"  p50: {stats['p50']:.4f}ms")
        print(f"  p95: {stats['p95']:.4f}ms (target: <5ms)")
        print(f"  p99: {stats['p99']:.4f}ms")

        assert stats["p95"] < 5.0, f"SLO VIOLATION: p95={stats['p95']:.4f}ms > 5ms"


class TestMetricsSLO:
    """Metrics emission SLO compliance tests."""

    @pytest.mark.slo
    def test_metrics_emission_p99_under_1ms(self) -> None:
        """Metrics emission MUST respond in <1ms p99 (1000μs)."""
        from prometheus_client import Gauge, REGISTRY

        # Create test gauge
        test_gauge = Gauge(
            "slo_test_gauge",
            "Test gauge for SLO",
            registry=REGISTRY,
        )

        latencies_us = []

        for i in range(10000):
            start = time.perf_counter()
            test_gauge.set(i * 0.1)
            duration_us = (time.perf_counter() - start) * 1_000_000
            latencies_us.append(duration_us)

        sorted_latencies = sorted(latencies_us)
        n = len(sorted_latencies)
        p99_us = sorted_latencies[int(n * 0.99)]

        print("\nMetrics emission SLO check:")
        print(f"  p50: {sorted_latencies[int(n * 0.50)]:.2f}μs")
        print(f"  p95: {sorted_latencies[int(n * 0.95)]:.2f}μs")
        print(f"  p99: {p99_us:.2f}μs (target: <1000μs = 1ms)")

        assert p99_us < 1000.0, f"SLO VIOLATION: p99={p99_us:.2f}μs > 1000μs"


class TestAPISLO:
    """API endpoint SLO compliance tests."""

    @pytest.mark.slo
    @pytest.mark.critical
    def test_health_endpoint_p99_under_100ms(self) -> None:
        """Health endpoint MUST respond in <100ms p99."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch, AsyncMock
        from kagami_api import create_app

        with patch(
            "kagami_api.rate_limiter.RateLimiter.is_allowed_async",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = (True, 1000, 0)

            app = create_app()
            client = TestClient(app)

            def run_health() -> Any:
                return client.get("/api/vitals/probes/live")

            stats = measure_latency(run_health, warmup=10, iterations=100)

        print("\nHealth endpoint SLO check:")
        print(f"  p50: {stats['p50']:.2f}ms")
        print(f"  p95: {stats['p95']:.2f}ms")
        print(f"  p99: {stats['p99']:.2f}ms (target: <100ms)")

        assert stats["p99"] < 100.0, f"SLO VIOLATION: p99={stats['p99']:.2f}ms > 100ms"


# =============================================================================
# SUMMARY TEST
# =============================================================================


@pytest.mark.slo
def test_slo_compliance_summary() -> Any:
    """Summary test that prints all SLO targets for reference."""
    print("\n" + "=" * 80)
    print("SLO COMPLIANCE SUMMARY")
    print("=" * 80)
    print(
        """
    Component                    SLO Target
    -----------------------------------------
    CBF barrier_function()       p99 < 10ms
    World model forward()        p99 < 200ms
    nearest_e8()                 p99 < 1ms
    CachedE8Quantizer (hit)      p99 < 0.1ms
    Fano router                  p99 < 10ms
    Prediction instinct          p95 < 5ms
    Threat instinct              p95 < 5ms
    Metrics emission             p99 < 1ms
    Health endpoint              p99 < 100ms

    Run individual tests to verify each SLO.
    """
    )
    print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "slo"])
