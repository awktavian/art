"""Unit Test: Cache Stampede Protection

Tests that UnifiedCache prevents cache stampede (thundering herd) on concurrent
cache misses for the same key.

Created: December 21, 2025
"""

from __future__ import annotations

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_unit,
    pytest.mark.unit,
    pytest.mark.timeout(30),
]

import asyncio
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_cache_stampede_prevention():
    """100 concurrent requests for same uncached item.

    Scenario:
        - Setup: UnifiedCache with cache enabled
        - Action: Clear cache
        - Action: 100 concurrent get() calls for same key
        - Verify: Only 1 fetch_fn call executed (stampede prevented)
        - Verify: All 100 requests return correct value

    Expected:
        - Without stampede protection: 100 fetch calls
        - With stampede protection: 1 fetch call
        - Performance improvement: 100x reduction in database load
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-stampede")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}

    async def mock_redis_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_redis_set(key: str, value: str, ex: int | None = None) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_redis_get
    mock_redis.set = mock_redis_set
    cache._redis = mock_redis

    # Clear cache
    cache._l1.cache.clear()
    mock_redis_storage.clear()

    # Track fetch_fn calls
    fetch_count = 0
    fetch_lock = asyncio.Lock()

    async def expensive_fetch() -> str:
        nonlocal fetch_count
        async with fetch_lock:
            fetch_count += 1
        # Simulate expensive database query
        await asyncio.sleep(0.05)
        return "expensive-result"

    # 100 concurrent requests for same key
    tasks = [cache.get("stampede-key", fetch_fn=expensive_fetch) for _ in range(100)]
    results = await asyncio.gather(*tasks)

    # All should return same value
    assert all(r == "expensive-result" for r in results), "All requests should get same value"

    # With stampede protection: Only 1 fetch should execute
    assert fetch_count == 1, f"Expected 1 fetch call (stampede prevented), got {fetch_count}"

    # All 100 requests should complete
    assert len(results) == 100, "All 100 requests should complete"


@pytest.mark.asyncio
async def test_stampede_protection_different_keys():
    """Verify stampede protection is per-key (different keys can fetch in parallel).

    Scenario:
        - 50 concurrent requests for key A
        - 50 concurrent requests for key B
        - Verify: 1 fetch for key A, 1 fetch for key B (2 total)
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-stampede-multi")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}

    async def mock_redis_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_redis_set(key: str, value: str, ex: int | None = None) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_redis_get
    mock_redis.set = mock_redis_set
    cache._redis = mock_redis

    # Clear cache
    cache._l1.cache.clear()
    mock_redis_storage.clear()

    # Track fetch_fn calls per key
    fetch_counts: dict[str, int] = {"key-a": 0, "key-b": 0}
    fetch_locks: dict[str, asyncio.Lock] = {"key-a": asyncio.Lock(), "key-b": asyncio.Lock()}

    async def fetch_factory(key: str):
        """Create a fetch function for a specific key."""

        async def fetch() -> str:
            async with fetch_locks[key]:
                fetch_counts[key] += 1
            await asyncio.sleep(0.05)
            return f"result-{key}"

        return fetch

    # 50 concurrent requests for each key
    tasks_a = [cache.get("key-a", fetch_fn=await fetch_factory("key-a")) for _ in range(50)]
    tasks_b = [cache.get("key-b", fetch_fn=await fetch_factory("key-b")) for _ in range(50)]

    # Run all tasks concurrently
    results = await asyncio.gather(*tasks_a, *tasks_b)

    # Verify results
    assert len(results) == 100, "All 100 requests should complete"
    assert sum(1 for r in results if r == "result-key-a") == 50, "50 results for key-a"
    assert sum(1 for r in results if r == "result-key-b") == 50, "50 results for key-b"

    # Each key should have exactly 1 fetch (stampede prevention per key)
    assert fetch_counts["key-a"] == 1, f"Expected 1 fetch for key-a, got {fetch_counts['key-a']}"
    assert fetch_counts["key-b"] == 1, f"Expected 1 fetch for key-b, got {fetch_counts['key-b']}"


@pytest.mark.asyncio
async def test_stampede_protection_lock_cleanup():
    """Verify fetch locks are cleaned up after requests complete.

    Scenario:
        - Issue request for key (creates lock)
        - Wait for lock cleanup (1 second delay)
        - Verify lock is removed from _fetch_locks dict
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-cleanup")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.get = lambda k: None
    mock_redis.set = lambda k, v, ex=None: True
    cache._redis = mock_redis  # type: ignore[assignment]

    # Clear cache
    cache._l1.cache.clear()

    # Fetch function
    async def fetch() -> str:
        return "test-value"

    # Issue request
    result = await cache.get("cleanup-key", fetch_fn=fetch)
    assert result == "test-value"

    # Lock should exist immediately after fetch
    namespaced_key = cache._k("cleanup-key")
    assert namespaced_key in cache._fetch_locks, "Lock should exist immediately after fetch"

    # Wait for cleanup (1 second + small buffer)
    await asyncio.sleep(1.2)

    # Lock should be cleaned up
    assert namespaced_key not in cache._fetch_locks, "Lock should be cleaned up after 1 second"


@pytest.mark.asyncio
async def test_stampede_protection_fetch_error():
    """Verify locks are cleaned up even when fetch_fn raises an exception.

    Scenario:
        - Issue request with failing fetch_fn
        - Verify exception propagates
        - Verify lock is still cleaned up
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-error")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.get = lambda k: None
    mock_redis.set = lambda k, v, ex=None: True
    cache._redis = mock_redis  # type: ignore[assignment]

    # Clear cache
    cache._l1.cache.clear()

    # Failing fetch function
    async def failing_fetch() -> str:
        raise ValueError("Simulated fetch error")

    # Issue request (should fail)
    namespaced_key = cache._k("error-key")
    with pytest.raises(ValueError, match="Simulated fetch error"):
        await cache.get("error-key", fetch_fn=failing_fetch)

    # Wait for cleanup
    await asyncio.sleep(1.2)

    # Lock should still be cleaned up despite error
    assert namespaced_key not in cache._fetch_locks, "Lock should be cleaned up even on error"


@pytest.mark.asyncio
async def test_stampede_with_redis_backend():
    """Verify stampede protection works with Redis L2 cache.

    Scenario:
        - Setup cache with Redis backend
        - 50 concurrent requests for same uncached key
        - Verify only 1 fetch executes
        - Verify value stored in both L1 and L2
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-redis-stampede")

    # Mock Redis with proper async interface
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}

    async def mock_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_set(key: str, value: str, ex: int | None = None) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_get
    mock_redis.set = mock_set
    cache._redis = mock_redis  # type: ignore[assignment]

    # Clear caches
    cache._l1.cache.clear()
    mock_redis_storage.clear()

    # Track fetch calls
    fetch_count = 0
    fetch_lock = asyncio.Lock()

    async def fetch() -> str:
        nonlocal fetch_count
        async with fetch_lock:
            fetch_count += 1
        await asyncio.sleep(0.05)
        return "redis-cached-value"

    # 50 concurrent requests
    tasks = [cache.get("redis-key", fetch_fn=fetch) for _ in range(50)]
    results = await asyncio.gather(*tasks)

    # Verify stampede prevention
    assert fetch_count == 1, f"Expected 1 fetch with Redis L2, got {fetch_count}"
    assert all(r == "redis-cached-value" for r in results)

    # Verify L1 cache populated
    namespaced_key = cache._k("redis-key")
    assert cache._l1.get_sync(namespaced_key) == "redis-cached-value"

    # Verify L2 (Redis) cache populated
    assert mock_redis_storage.get(namespaced_key) == "redis-cached-value"


@pytest.mark.asyncio
async def test_stampede_with_l1_hit():
    """Verify stampede protection skips fetch when L1 cache hits.

    Scenario:
        - Pre-populate L1 cache
        - Issue concurrent requests
        - Verify no fetch_fn calls (L1 hit)
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-l1-hit")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.get = lambda k: None
    mock_redis.set = lambda k, v, ex=None: True
    cache._redis = mock_redis  # type: ignore[assignment]

    # Pre-populate L1
    cache._l1.cache.clear()
    namespaced_key = cache._k("cached-key")
    cache._l1.set_sync(namespaced_key, "l1-cached-value")

    # Track fetch calls (should be 0)
    fetch_count = 0

    async def fetch() -> str:
        nonlocal fetch_count
        fetch_count += 1
        return "fetched-value"

    # 30 concurrent requests
    tasks = [cache.get("cached-key", fetch_fn=fetch) for _ in range(30)]
    results = await asyncio.gather(*tasks)

    # Verify L1 hit, no fetches
    assert fetch_count == 0, f"Expected 0 fetches (L1 hit), got {fetch_count}"
    assert all(r == "l1-cached-value" for r in results)


@pytest.mark.asyncio
async def test_stampede_with_l2_hit():
    """Verify stampede protection promotes L2 hits to L1.

    Scenario:
        - Pre-populate L2 (Redis) cache only
        - Issue concurrent requests
        - Verify single fetch from L2, promoted to L1
        - Verify no fetch_fn calls
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-l2-hit")

    # Mock Redis with pre-populated value
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}
    namespaced_key = cache._k("l2-cached-key")
    mock_redis_storage[namespaced_key] = "l2-cached-value"

    async def mock_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_set(key: str, value: str, ex: int | None = None) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_get
    mock_redis.set = mock_set
    cache._redis = mock_redis  # type: ignore[assignment]

    # Clear L1 (L2 has value)
    cache._l1.cache.clear()

    # Track fetch calls (should be 0)
    fetch_count = 0

    async def fetch() -> str:
        nonlocal fetch_count
        fetch_count += 1
        return "fetched-value"

    # 30 concurrent requests
    tasks = [cache.get("l2-cached-key", fetch_fn=fetch) for _ in range(30)]
    results = await asyncio.gather(*tasks)

    # Verify L2 hit, no fetches
    assert fetch_count == 0, f"Expected 0 fetches (L2 hit), got {fetch_count}"
    assert all(r == "l2-cached-value" for r in results)

    # Verify L1 promoted
    assert cache._l1.get_sync(namespaced_key) == "l2-cached-value"


@pytest.mark.asyncio
async def test_stampede_concurrent_different_namespaces():
    """Verify stampede protection is namespace-isolated.

    Scenario:
        - Two caches with different namespaces
        - Same key in both namespaces
        - Verify separate stampede protection per namespace
    """
    from kagami.core.caching.unified import UnifiedCache

    cache_a = UnifiedCache(namespace="ns-a")
    cache_b = UnifiedCache(namespace="ns-b")

    # Mock Redis for both
    for cache in [cache_a, cache_b]:
        mock_redis = MagicMock()
        mock_redis.get = lambda k: None
        mock_redis.set = lambda k, v, ex=None: True
        cache._redis = mock_redis  # type: ignore[assignment]
        cache._l1.cache.clear()

    # Track fetch calls per namespace
    fetch_counts = {"ns-a": 0, "ns-b": 0}

    async def fetch_factory(ns: str):
        async def fetch() -> str:
            fetch_counts[ns] += 1
            await asyncio.sleep(0.05)
            return f"value-{ns}"

        return fetch

    # 25 concurrent requests per namespace, same key
    tasks_a = [cache_a.get("shared-key", fetch_fn=await fetch_factory("ns-a")) for _ in range(25)]
    tasks_b = [cache_b.get("shared-key", fetch_fn=await fetch_factory("ns-b")) for _ in range(25)]

    results = await asyncio.gather(*tasks_a, *tasks_b)

    # Verify stampede protection per namespace
    assert fetch_counts["ns-a"] == 1, f"Expected 1 fetch for ns-a, got {fetch_counts['ns-a']}"
    assert fetch_counts["ns-b"] == 1, f"Expected 1 fetch for ns-b, got {fetch_counts['ns-b']}"

    # Verify correct values returned
    assert sum(1 for r in results if r == "value-ns-a") == 25
    assert sum(1 for r in results if r == "value-ns-b") == 25


@pytest.mark.asyncio
async def test_stampede_sequential_requests():
    """Verify stampede locks don't affect sequential requests.

    Scenario:
        - Issue request 1 (cache miss, fetch)
        - Wait for completion
        - Issue request 2 (cache hit, no fetch)
        - Verify lock cleanup doesn't break caching
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-sequential")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}

    async def mock_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_set(key: str, value: str, ex: int | None = None) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_get
    mock_redis.set = mock_set
    cache._redis = mock_redis  # type: ignore[assignment]

    cache._l1.cache.clear()
    mock_redis_storage.clear()

    fetch_count = 0

    async def fetch() -> str:
        nonlocal fetch_count
        fetch_count += 1
        return "sequential-value"

    # Request 1: cache miss
    result1 = await cache.get("seq-key", fetch_fn=fetch)
    assert result1 == "sequential-value"
    assert fetch_count == 1

    # Wait for lock cleanup
    await asyncio.sleep(1.3)

    # Request 2: cache hit (L1)
    result2 = await cache.get("seq-key", fetch_fn=fetch)
    assert result2 == "sequential-value"
    assert fetch_count == 1  # No additional fetch

    # Verify lock was cleaned up
    namespaced_key = cache._k("seq-key")
    assert namespaced_key not in cache._fetch_locks


@pytest.mark.asyncio
async def test_stampede_with_slow_fetch():
    """Verify stampede protection with slow fetch functions.

    Scenario:
        - Fetch function takes 200ms
        - 100 concurrent requests arrive during fetch
        - Verify all requests wait for single fetch
        - Verify all get same result
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-slow-fetch")

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.get = lambda k: None
    mock_redis.set = lambda k, v, ex=None: True
    cache._redis = mock_redis  # type: ignore[assignment]
    cache._l1.cache.clear()

    fetch_count = 0
    fetch_start_time = None

    async def slow_fetch() -> str:
        nonlocal fetch_count, fetch_start_time
        fetch_count += 1
        fetch_start_time = asyncio.get_event_loop().time()
        await asyncio.sleep(0.2)  # Slow fetch
        return "slow-result"

    # 100 concurrent requests
    start_time = asyncio.get_event_loop().time()
    tasks = [cache.get("slow-key", fetch_fn=slow_fetch) for _ in range(100)]
    results = await asyncio.gather(*tasks)
    end_time = asyncio.get_event_loop().time()

    # Verify stampede prevention
    assert fetch_count == 1, f"Expected 1 fetch, got {fetch_count}"
    assert all(r == "slow-result" for r in results)

    # Verify total time is ~200ms, not 100 * 200ms
    total_time = end_time - start_time
    assert total_time < 0.5, f"Expected <500ms total time, got {total_time * 1000:.0f}ms"
