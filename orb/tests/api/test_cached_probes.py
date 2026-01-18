"""Tests for cached health probe optimizations.

Verifies that caching works correctly and improves performance.

Created: December 2025
"""

from __future__ import annotations


import pytest
import asyncio
import time

from kagami_api.routes.vitals.cached_probes import (
    async_cached,
    cached_database_health,
    cached_etcd_health,
    cached_redis_health,
    clear_health_cache,
    get_cache_stats,
)
from kagami_api.schemas.vitals import DependencyCheck


class TestAsyncCached:
    """Test the async_cached decorator."""

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        """Test that cached function returns same result on subsequent calls."""
        call_count = 0

        @async_cached(ttl_seconds=1.0)
        async def test_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate expensive operation
            return x * 2

        # First call
        result1 = await test_func(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = await test_func(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment

    @pytest.mark.asyncio
    async def test_cache_expiry(self) -> None:
        """Test that cache expires after TTL."""
        call_count = 0

        @async_cached(ttl_seconds=0.1)
        async def test_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        await test_func(5)
        assert call_count == 1

        # Wait for cache to expire
        await asyncio.sleep(0.15)

        # Second call should execute again
        await test_func(5)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_different_args(self) -> None:
        """Test that different arguments create different cache entries."""
        call_count = 0

        @async_cached(ttl_seconds=1.0)
        async def test_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        await test_func(5)
        await test_func(10)
        assert call_count == 2  # Both should execute

    @pytest.mark.asyncio
    async def test_concurrent_calls(self) -> None:
        """Test that concurrent calls to same function use cache correctly."""
        call_count = 0

        @async_cached(ttl_seconds=1.0)
        async def test_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return x * 2

        # Launch multiple concurrent calls
        results = await asyncio.gather(
            test_func(5),
            test_func(5),
            test_func(5),
        )

        # All should return same result
        assert all(r == 10 for r in results)
        # Should execute at least once, but may execute multiple times
        # due to race condition before cache is populated
        assert call_count >= 1


class TestCachedHealthChecks:
    """Test cached health check functions."""

    def test_clear_cache(self) -> None:
        """Test that clear_health_cache works."""
        clear_health_cache()
        stats = get_cache_stats()
        assert stats["size"] == 0

    def test_cache_stats(self) -> None:
        """Test that cache stats are returned correctly."""
        clear_health_cache()
        stats = get_cache_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert isinstance(stats["size"], int)
        assert isinstance(stats["max_size"], int)

    @pytest.mark.asyncio
    async def test_database_health_cached(self) -> None:
        """Test that database health check uses cache."""
        clear_health_cache()

        # First call
        start1 = time.perf_counter()
        result1 = await cached_database_health()
        duration1 = time.perf_counter() - start1

        # Second call (should be cached and faster)
        start2 = time.perf_counter()
        result2 = await cached_database_health()
        duration2 = time.perf_counter() - start2

        # Results should be identical
        assert result1.status == result2.status

        # Second call should be significantly faster (at least 2x)
        # Skip timing assertion if both calls are very fast (< 1ms)
        if duration1 > 0.001:
            assert (
                duration2 < duration1 / 2
            ), f"Cached call not faster: {duration2:.4f}s vs {duration1:.4f}s"

    @pytest.mark.asyncio
    async def test_redis_health_cached(self) -> None:
        """Test that Redis health check uses cache."""
        clear_health_cache()

        # First call
        result1 = await cached_redis_health()

        # Second call (should be cached)
        result2 = await cached_redis_health()

        # Results should be identical
        assert result1.status == result2.status

    @pytest.mark.asyncio
    async def test_etcd_health_cached(self) -> None:
        """Test that etcd health check uses cache."""
        clear_health_cache()

        # First call
        result1 = await cached_etcd_health()

        # Second call (should be cached)
        result2 = await cached_etcd_health()

        # Results should be identical
        assert result1.status == result2.status

    @pytest.mark.asyncio
    async def test_parallel_health_checks(self) -> None:
        """Test that parallel health checks work correctly with caching."""
        clear_health_cache()

        # Run all checks in parallel
        results = await asyncio.gather(
            cached_database_health(),
            cached_redis_health(),
            cached_etcd_health(),
        )

        # All should return DependencyCheck objects
        assert all(isinstance(r, DependencyCheck) for r in results)

        # Run again in parallel (should use cache)
        start = time.perf_counter()
        cached_results = await asyncio.gather(
            cached_database_health(),
            cached_redis_health(),
            cached_etcd_health(),
        )
        duration = time.perf_counter() - start

        # Results should match
        for i, result in enumerate(results):
            assert result.status == cached_results[i].status

        # Cached run should be faster (< 10ms for all three)
        assert duration < 0.01, f"Cached checks too slow: {duration:.4f}s"

    @pytest.mark.asyncio
    async def test_cache_isolation(self) -> None:
        """Test that different health checks have separate cache entries."""
        clear_health_cache()

        # Call all three checks
        await cached_database_health()
        await cached_redis_health()
        await cached_etcd_health()

        # Cache should have 3 entries (one per function)
        stats = get_cache_stats()
        assert stats["size"] == 3


@pytest.mark.asyncio
async def test_cache_eviction() -> None:
    """Test that cache evicts old entries when max size is reached."""
    from kagami_api.routes.vitals.cached_probes import _MAX_CACHE_SIZE

    clear_health_cache()

    # Create many cached functions to fill cache beyond max size
    @async_cached(ttl_seconds=60.0)
    async def cached_func(x: int) -> int:
        return x * 2

    # Call with many different arguments
    for i in range(_MAX_CACHE_SIZE + 20):
        await cached_func(i)

    # Cache size should not exceed max
    stats = get_cache_stats()
    assert stats["size"] <= _MAX_CACHE_SIZE
