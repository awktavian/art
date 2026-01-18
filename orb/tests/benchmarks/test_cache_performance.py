"""Cache performance benchmarks.

Measures performance of the unified caching layer:
- L1 (memory) cache operations
- L2 (Redis) cache operations
- Cache throughput and latency
- ResponseCache and ModelCache performance

Target metrics:
- L1 cache hit: < 1ms
- L2 cache hit: < 5ms
- Throughput: > 10,000 ops/sec (L1), > 2,000 ops/sec (L2)

Created: December 15, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e

import asyncio
import time
from typing import Any


@pytest.mark.benchmark
class TestL1CachePerformance:
    """L1 (memory) cache performance benchmarks."""

    @pytest.mark.asyncio
    async def test_l1_cache_hit_latency(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure L1 cache hit latency.

        Target: < 1ms per operation
        """
        # Warmup
        await response_cache.set("warmup", "data")
        await response_cache.get("warmup")

        # Benchmark L1 hits
        times = []
        for i in range(1000):
            key = f"bench-l1-{i % 100}"  # Reuse 100 keys
            await response_cache.set(key, f"value-{i}")

            start = time.perf_counter()
            result = await response_cache.get(key)
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            assert result == f"value-{i}"

        stats = benchmark_stats(times)

        # Assertions
        assert stats["mean"] < 0.001, f"L1 mean latency {stats['mean'] * 1000:.2f}ms > 1ms"
        assert stats["p95"] < 0.002, f"L1 p95 latency {stats['p95'] * 1000:.2f}ms > 2ms"
        assert stats["p99"] < 0.005, f"L1 p99 latency {stats['p99'] * 1000:.2f}ms > 5ms"

        print("\nL1 Cache Hit Latency:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")
        print(f"  P99:    {stats['p99'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_l1_cache_miss_latency(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure L1 cache miss latency.

        Target: < 0.5ms per operation
        """
        times = []
        for i in range(1000):
            key = f"missing-{i}"

            start = time.perf_counter()
            result = await response_cache.get(key)
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            assert result is None

        stats = benchmark_stats(times)

        assert stats["mean"] < 0.0005, f"L1 miss latency {stats['mean'] * 1000:.2f}ms > 0.5ms"

        print("\nL1 Cache Miss Latency:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_l1_cache_write_latency(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure L1 cache write latency.

        Target: < 1ms per operation
        """
        times = []
        for i in range(1000):
            key = f"write-{i}"
            value = {"data": f"value-{i}", "index": i}

            start = time.perf_counter()
            await response_cache.set(key, value)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        stats = benchmark_stats(times)

        assert stats["mean"] < 0.001, f"L1 write latency {stats['mean'] * 1000:.2f}ms > 1ms"

        print("\nL1 Cache Write Latency:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")


@pytest.mark.benchmark
class TestL2CachePerformance:
    """L2 (Redis) cache performance benchmarks."""

    @pytest.mark.asyncio
    async def test_l2_redis_cache_hit_latency(
        self, response_cache: Any, benchmark_stats: Any
    ) -> None:
        """Measure L2 (Redis) cache hit latency.

        Target: < 5ms per operation
        """
        # Warmup
        await response_cache.set("warmup-l2", "data", ttl=60)
        # Clear L1 to force L2 lookup
        response_cache._memory_cache.clear()

        # Benchmark L2 hits
        times = []
        for i in range(100):
            key = f"bench-l2-{i}"
            await response_cache.set(key, f"value-{i}", ttl=60)

            # Clear L1 to force L2 lookup
            if key in response_cache._memory_cache:
                del response_cache._memory_cache[key]

            start = time.perf_counter()
            result = await response_cache.get(key)
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            assert result == f"value-{i}"

        stats = benchmark_stats(times)

        # Redis mock adds 0.5ms latency
        assert stats["mean"] < 0.005, f"L2 mean latency {stats['mean'] * 1000:.2f}ms > 5ms"
        assert stats["p95"] < 0.010, f"L2 p95 latency {stats['p95'] * 1000:.2f}ms > 10ms"

        print("\nL2 Cache Hit Latency:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")
        print(f"  P99:    {stats['p99'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_l2_cache_write_latency(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure L2 cache write latency.

        Target: < 10ms per operation
        """
        times = []
        for i in range(100):
            key = f"write-l2-{i}"
            value = {"data": f"value-{i}", "timestamp": time.time()}

            start = time.perf_counter()
            await response_cache.set(key, value, ttl=60)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        stats = benchmark_stats(times)

        assert stats["mean"] < 0.010, f"L2 write latency {stats['mean'] * 1000:.2f}ms > 10ms"

        print("\nL2 Cache Write Latency:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")


@pytest.mark.benchmark
class TestCacheThroughput:
    """Cache throughput benchmarks."""

    @pytest.mark.asyncio
    async def test_l1_cache_throughput(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure L1 cache throughput (ops/sec).

        Target: > 10,000 ops/sec
        """

        async def workload():
            """100 read + 100 write operations."""
            for i in range(100):
                await response_cache.set(f"key-{i}", f"value-{i}")
                await response_cache.get(f"key-{i}")

        # Warmup
        await workload()

        # Benchmark
        times = []
        for _ in range(50):
            start = time.perf_counter()
            await workload()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        stats = benchmark_stats(times)
        ops_per_sec = 200 / stats["mean"]  # 200 ops per workload

        assert ops_per_sec > 10000, f"L1 throughput {ops_per_sec:.0f} < 10,000 ops/sec"

        print("\nL1 Cache Throughput:")
        print(f"  Mean:     {ops_per_sec:.0f} ops/sec")
        print(f"  P50:      {200 / stats['p50']:.0f} ops/sec")
        print(f"  Best:     {200 / stats['min']:.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_l2_cache_throughput(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure L2 cache throughput (ops/sec).

        Target: > 2,000 ops/sec
        """

        async def workload():
            """50 read + 50 write operations."""
            for i in range(50):
                await response_cache.set(f"l2-key-{i}", f"value-{i}", ttl=60)

                # Clear L1 to force L2 lookup
                if f"l2-key-{i}" in response_cache._memory_cache:
                    del response_cache._memory_cache[f"l2-key-{i}"]

                await response_cache.get(f"l2-key-{i}")

        # Warmup
        await workload()

        # Benchmark
        times = []
        for _ in range(20):
            start = time.perf_counter()
            await workload()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        stats = benchmark_stats(times)
        ops_per_sec = 100 / stats["mean"]  # 100 ops per workload

        assert ops_per_sec > 2000, f"L2 throughput {ops_per_sec:.0f} < 2,000 ops/sec"

        print("\nL2 Cache Throughput:")
        print(f"  Mean:     {ops_per_sec:.0f} ops/sec")
        print(f"  P50:      {100 / stats['p50']:.0f} ops/sec")


@pytest.mark.benchmark
class TestCacheConcurrency:
    """Cache concurrency benchmarks."""

    @pytest.mark.asyncio
    async def test_concurrent_l1_reads(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure concurrent read performance.

        Target: Linear scaling up to 10 concurrent tasks
        """
        # Prepare data
        for i in range(100):
            await response_cache.set(f"concurrent-{i}", f"value-{i}")

        async def read_task(task_id: int):
            """Single task reading 100 keys."""
            times = []
            for i in range(100):
                start = time.perf_counter()
                await response_cache.get(f"concurrent-{i}")
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            return times

        # Test with 1, 5, 10 concurrent tasks
        for num_tasks in [1, 5, 10]:
            start = time.perf_counter()
            results = await asyncio.gather(*[read_task(i) for i in range(num_tasks)])
            total_time = time.perf_counter() - start

            all_times = [t for task_times in results for t in task_times]
            stats = benchmark_stats(all_times)
            total_ops = num_tasks * 100
            ops_per_sec = total_ops / total_time

            print(f"\nConcurrent Reads ({num_tasks} tasks):")
            print(f"  Total time:  {total_time * 1000:.2f}ms")
            print(f"  Throughput:  {ops_per_sec:.0f} ops/sec")
            print(f"  Mean latency: {stats['mean'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_l1_writes(self, response_cache: Any, benchmark_stats: Any) -> None:
        """Measure concurrent write performance.

        Target: No contention for different keys
        """

        async def write_task(task_id: int):
            """Single task writing 100 keys."""
            times = []
            for i in range(100):
                key = f"write-task-{task_id}-{i}"
                start = time.perf_counter()
                await response_cache.set(key, f"value-{i}")
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            return times

        # Test with 1, 5, 10 concurrent tasks
        for num_tasks in [1, 5, 10]:
            start = time.perf_counter()
            results = await asyncio.gather(*[write_task(i) for i in range(num_tasks)])
            total_time = time.perf_counter() - start

            all_times = [t for task_times in results for t in task_times]
            stats = benchmark_stats(all_times)
            total_ops = num_tasks * 100
            ops_per_sec = total_ops / total_time

            print(f"\nConcurrent Writes ({num_tasks} tasks):")
            print(f"  Total time:  {total_time * 1000:.2f}ms")
            print(f"  Throughput:  {ops_per_sec:.0f} ops/sec")
            print(f"  Mean latency: {stats['mean'] * 1000:.3f}ms")


@pytest.mark.benchmark
class TestModelCachePerformance:
    """ModelCache performance benchmarks."""

    @pytest.mark.asyncio
    async def test_model_cache_key_generation(
        self, model_cache: Any, sample_model_config: Any, benchmark_stats: Any
    ) -> None:
        """Measure cache key generation performance.

        Target: < 0.1ms per operation
        """
        times = []
        for i in range(1000):
            model_id = f"model-{i % 10}"

            start = time.perf_counter()
            cache_key = model_cache._make_cache_key(model_id, sample_model_config)
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            assert isinstance(cache_key, str)
            assert len(cache_key) == 64  # SHA256 hash

        stats = benchmark_stats(times)

        assert stats["mean"] < 0.0001, f"Key generation {stats['mean'] * 1000:.2f}ms > 0.1ms"

        print("\nModel Cache Key Generation:")
        print(f"  Mean:   {stats['mean'] * 1000000:.1f}µs")
        print(f"  Median: {stats['median'] * 1000000:.1f}µs")
        print(f"  P95:    {stats['p95'] * 1000000:.1f}µs")

    @pytest.mark.asyncio
    async def test_model_cache_metadata_read(self, model_cache: Any, benchmark_stats: Any) -> None:
        """Measure metadata read performance.

        Target: < 5ms per operation
        """
        # Create sample metadata
        model_cache._metadata["test-model-1"] = {
            "model_id": "test-model-1",
            "cache_key": "abc123",
            "size_bytes": 1000000,
            "created_at": time.time(),
            "last_access": time.time(),
            "hit_count": 0,
        }

        times = []
        for _ in range(100):
            start = time.perf_counter()
            metadata = model_cache._metadata.get("test-model-1")
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            assert metadata is not None

        stats = benchmark_stats(times)

        assert stats["mean"] < 0.005, f"Metadata read {stats['mean'] * 1000:.2f}ms > 5ms"

        print("\nModel Cache Metadata Read:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")
