from __future__ import annotations

import pytest
import gc
import statistics
import time
from typing import Any
from collections.abc import Callable

import torch

# =============================================================================
# TEST UTILITIES
# =============================================================================


def time_function(
    func: Callable[..., Any],
    iterations: int = 100,
    warmup: int = 10,
    *args: Any,
    **kwargs,
) -> dict[str, float]:
    """Time a function and return statistics.

    Args:
        func: Function to time
        iterations: Number of timed iterations
        warmup: Warmup iterations (not timed)
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Dict with mean_ms, p95_ms, p99_ms, min_ms, max_ms
    """
    # Warmup
    for _ in range(warmup):
        func(*args, **kwargs)

    gc.collect()

    # Time iterations
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        func(*args, **kwargs)
        end = time.perf_counter_ns()
        times.append((end - start) / 1_000_000)

    sorted_times = sorted(times)
    n = len(sorted_times)

    return {
        "mean_ms": statistics.mean(times),
        "std_ms": statistics.stdev(times) if n > 1 else 0.0,
        "min_ms": sorted_times[0],
        "max_ms": sorted_times[-1],
        "p50_ms": sorted_times[int(n * 0.5)],
        "p95_ms": sorted_times[int(n * 0.95)] if n >= 20 else sorted_times[-1],
        "p99_ms": sorted_times[int(n * 0.99)] if n >= 100 else sorted_times[-1],
    }


# =============================================================================
# E8 QUANTIZATION PERFORMANCE TESTS
# =============================================================================


class TestE8QuantizationPerformance:
    """Performance tests for E8 quantization operations."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup E8 quantizer."""
        from kagami_math.e8 import nearest_e8

        self.nearest_e8 = nearest_e8

    def test_e8_single_vector_latency(self) -> None:
        """E8 single vector quantization should be <1ms (p95)."""
        x = torch.randn(8)
        stats = time_function(self.nearest_e8, iterations=500, warmup=50, x=x)

        assert (
            stats["p95_ms"] < 1.0
        ), f"E8 single vector p95 latency {stats['p95_ms']:.3f}ms exceeds 1ms SLO"

    def test_e8_batch_latency(self) -> None:
        """E8 batch quantization should be <5ms (p95) for batch=32."""
        x = torch.randn(32, 8)
        stats = time_function(self.nearest_e8, iterations=200, warmup=20, x=x)

        assert (
            stats["p95_ms"] < 5.0
        ), f"E8 batch[32] p95 latency {stats['p95_ms']:.3f}ms exceeds 5ms SLO"

    def test_e8_large_batch_latency(self) -> None:
        """E8 large batch quantization should be <20ms (p95) for batch=256."""
        x = torch.randn(256, 8)
        stats = time_function(self.nearest_e8, iterations=100, warmup=10, x=x)

        assert (
            stats["p95_ms"] < 20.0
        ), f"E8 batch[256] p95 latency {stats['p95_ms']:.3f}ms exceeds 20ms SLO"


# =============================================================================
# FANO ROUTER PERFORMANCE TESTS
# =============================================================================


class TestFanoRouterPerformance:
    """Performance tests for Fano Action Router."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup Fano router."""
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        self.router = create_fano_router()

    def test_fano_simple_routing_latency(self) -> None:
        """Simple routing should be <1ms (p95)."""

        def route_simple() -> Self:
            return self.router.route("ping", {"target": "health"})

        stats = time_function(route_simple, iterations=1000, warmup=100)

        assert (
            stats["p95_ms"] < 1.0
        ), f"Fano simple routing p95 latency {stats['p95_ms']:.3f}ms exceeds 1ms SLO"

    def test_fano_complex_routing_latency(self) -> Any:
        """Complex routing (all colonies) should be <10ms (p95)."""

        def route_complex() -> Self:
            return self.router.route(
                "analyze_architecture",
                {"domain": "security", "modules": ["a", "b", "c"]},
                complexity=0.85,
            )

        stats = time_function(route_complex, iterations=500, warmup=50)

        assert (
            stats["p95_ms"] < 10.0
        ), f"Fano complex routing p95 latency {stats['p95_ms']:.3f}ms exceeds 10ms SLO"

    def test_fano_cache_hit_latency(self) -> Any:
        """Cache hits should be <0.5ms (p95)."""
        # Warm up cache
        for _ in range(100):
            self.router.route("cached_action", {})

        def route_cached() -> Self:
            return self.router.route("cached_action", {})

        stats = time_function(route_cached, iterations=500, warmup=0)

        assert (
            stats["p95_ms"] < 0.5
        ), f"Fano cache hit p95 latency {stats['p95_ms']:.3f}ms exceeds 0.5ms SLO"

    def test_fano_cache_hit_rate(self) -> Any:
        """Cache hit rate should be >90% for repeated queries."""
        # Warm up with various queries
        actions = ["action_a", "action_b", "action_c"]
        for action in actions:
            for _ in range(10):
                self.router.route(action, {})

        # Check cache stats
        stats = self.router.get_cache_stats()

        assert stats["hit_rate"] > 0.9, f"Fano cache hit rate {stats['hit_rate']:.1%} below 90% SLO"


# =============================================================================
# WORLD MODEL PERFORMANCE TESTS
# =============================================================================


class TestWorldModelPerformance:
    """Performance tests for KagamiWorldModel."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup world model."""
        from kagami.core.world_model import create_model

        self.model = create_model(preset="minimal")
        self.model.eval()
        self.bulk_dim = self.model.config.bulk_dim

    def test_world_model_encode_latency(self) -> None:
        """World model encode should be <100ms (p95)."""
        x = torch.randn(4, 8, self.bulk_dim)

        def encode() -> Self:
            with torch.no_grad():
                return self.model.encode(x)

        stats = time_function(encode, iterations=50, warmup=10)

        assert (
            stats["p95_ms"] < 100.0
        ), f"World model encode p95 latency {stats['p95_ms']:.2f}ms exceeds 100ms SLO"

    def test_world_model_forward_latency(self) -> Any:
        """World model forward should be <200ms (p95)."""
        x = torch.randn(4, 8, self.bulk_dim)

        def forward() -> None:
            with torch.no_grad():
                return self.model(x)

        stats = time_function(forward, iterations=30, warmup=5)

        assert (
            stats["p95_ms"] < 200.0
        ), f"World model forward p95 latency {stats['p95_ms']:.2f}ms exceeds 200ms SLO"


# =============================================================================
# SAFETY CACHE PERFORMANCE TESTS
# =============================================================================


class TestSafetyCachePerformance:
    """Performance tests for safety classification cache (LLM results only)."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup safety cache."""
        from kagami.core.safety.safety_cache import SafetyClassificationCache

        self.cache = SafetyClassificationCache(max_size=1000)

    def test_cache_lookup_latency(self) -> None:
        """Cache lookup should be <0.5ms (p95)."""
        # Populate cache
        for i in range(100):
            self.cache.put(f"test query {i}", h_value=1.0, is_safe=True)

        def cache_lookup() -> Self:
            return self.cache.get("test query 50")

        stats = time_function(cache_lookup, iterations=1000, warmup=100)

        assert (
            stats["p95_ms"] < 0.5
        ), f"Cache lookup p95 latency {stats['p95_ms']:.4f}ms exceeds 0.5ms SLO"

    def test_cache_insert_latency(self) -> Any:
        """Cache insert should be <0.5ms (p95)."""

        def cache_insert() -> None:
            import random

            key = f"query_{random.randint(0, 1000000)}"
            self.cache.put(key, h_value=1.0, is_safe=True)

        stats = time_function(cache_insert, iterations=1000, warmup=100)

        assert (
            stats["p95_ms"] < 0.5
        ), f"Cache insert p95 latency {stats['p95_ms']:.4f}ms exceeds 0.5ms SLO"


# =============================================================================
# THROUGHPUT TESTS
# =============================================================================


class TestThroughput:
    """Throughput tests for critical operations."""

    def test_e8_throughput(self) -> None:
        """E8 quantization should achieve >10,000 ops/sec."""
        from kagami_math.e8 import nearest_e8

        x = torch.randn(8)

        # Warmup
        for _ in range(100):
            nearest_e8(x)

        # Measure throughput
        start = time.perf_counter()
        iterations = 10000
        for _ in range(iterations):
            nearest_e8(x)
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        assert throughput > 10000, f"E8 throughput {throughput:.0f} ops/sec below 10,000 SLO"

    def test_fano_router_throughput(self) -> None:
        """Fano router should achieve >20,000 ops/sec."""
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        router = create_fano_router()

        # Warmup
        for _ in range(100):
            router.route("test", {})

        # Measure throughput
        start = time.perf_counter()
        iterations = 20000
        for _ in range(iterations):
            router.route("query", {"target": "status"})
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        assert (
            throughput > 20000
        ), f"Fano router throughput {throughput:.0f} ops/sec below 20,000 SLO"


# =============================================================================
# MEMORY EFFICIENCY TESTS
# =============================================================================


class TestMemoryEfficiency:
    """Memory efficiency tests to detect leaks and excessive allocation."""

    def test_e8_no_memory_leak(self) -> None:
        """E8 quantization should not leak memory over many iterations."""
        import gc
        from kagami_math.e8 import nearest_e8

        gc.collect()

        # Get baseline memory
        import tracemalloc

        tracemalloc.start()
        baseline = tracemalloc.get_traced_memory()[0]

        # Run many iterations
        for _ in range(10000):
            x = torch.randn(8)
            _ = nearest_e8(x)

        gc.collect()
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        # Memory growth should be <10MB
        growth_mb = (peak - baseline) / (1024 * 1024)

        assert growth_mb < 10.0, f"E8 memory growth {growth_mb:.1f}MB exceeds 10MB limit"

    def test_fano_cache_bounded_size(self) -> None:
        """Fano router cache should respect size limits."""
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        router = create_fano_router(cache_size=100)

        # Insert many entries
        for i in range(1000):
            router.route(f"action_{i}", {"param": i})

        stats = router.get_cache_stats()

        assert stats["cache_size"] <= 100, f"Fano cache size {stats['cache_size']} exceeds max 100"


# =============================================================================
# CONCURRENCY TESTS
# =============================================================================


class TestConcurrencyPerformance:
    """Concurrency performance tests."""

    def test_e8_thread_safety(self) -> None:
        """E8 quantization should be thread-safe and performant."""
        import concurrent.futures
        from kagami_math.e8 import nearest_e8

        def quantize_batch() -> Any:
            results = []
            for _ in range(100):
                x = torch.randn(8)
                results.append(nearest_e8(x))
            return results

        # Run in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            start = time.perf_counter()
            futures = [executor.submit(quantize_batch) for _ in range(4)]
            results = [f.result() for f in futures]
            elapsed = time.perf_counter() - start

        # 400 total operations should complete in <1 second
        assert elapsed < 1.0, f"Parallel E8 quantization took {elapsed:.2f}s, expected <1s"
        assert len(results) == 4
        assert all(len(r) == 100 for r in results)  # type: ignore[arg-type]


# =============================================================================
# CLI RUNNER
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
