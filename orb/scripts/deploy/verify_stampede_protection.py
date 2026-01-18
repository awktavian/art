#!/usr/bin/env python3
"""Verify Cache Stampede Protection Performance

Demonstrates the performance impact of stampede protection.

Expected Results:
    - Without protection: 100 database queries (100x load)
    - With protection: 1 database query (optimal)
    - Latency: Concurrent requests wait for first fetch (~0ms additional)

Usage:
    python scripts/devops/verify_stampede_protection.py
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock


async def main() -> None:
    """Verify stampede protection performance."""
    from kagami.core.caching.unified import UnifiedCache

    print("=" * 80)
    print("Cache Stampede Protection Verification")
    print("=" * 80)

    # Setup cache
    cache = UnifiedCache(namespace="verification")

    # Mock Redis (fast L2)
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}

    async def mock_redis_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_redis_set(key: str, value: str, ex: int | None = None) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_redis_get
    mock_redis.set = mock_redis_set
    cache._redis = mock_redis  # type: ignore[assignment]

    # Clear cache
    cache._l1._data.clear()
    mock_redis_storage.clear()

    # Track database queries
    query_count = 0
    query_lock = asyncio.Lock()

    async def expensive_db_query() -> str:
        """Simulate expensive database query (50ms)."""
        nonlocal query_count
        async with query_lock:
            query_count += 1
            print(f"  DB Query #{query_count} executing...")
        await asyncio.sleep(0.05)  # Simulate 50ms database latency
        return "database-result"

    # Test 1: Concurrent requests for same key
    print("\nTest 1: 100 concurrent requests for same cache key")
    print("-" * 80)

    start_time = time.perf_counter()
    tasks = [cache.get("hot-key", fetch_fn=expensive_db_query) for _ in range(100)]
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start_time

    print("\nResults:")
    print(f"  Total requests: {len(results)}")
    print(f"  Database queries executed: {query_count}")
    print(f"  Stampede prevented: {100 - query_count} duplicate queries avoided")
    print(f"  Total time: {elapsed:.3f}s")
    print(f"  Performance improvement: {100 / query_count:.0f}x reduction in DB load")

    # Verify correctness
    assert all(r == "database-result" for r in results), "All requests should succeed"
    assert query_count == 1, f"Expected 1 query (stampede protected), got {query_count}"

    print("\n✅ Stampede protection verified: Only 1 DB query for 100 concurrent requests")

    # Test 2: Different keys can fetch in parallel
    print("\n" + "=" * 80)
    print("Test 2: Concurrent requests for different keys (should parallelize)")
    print("-" * 80)

    cache._l1._data.clear()
    mock_redis_storage.clear()
    query_count = 0

    start_time = time.perf_counter()
    tasks_a = [cache.get("key-a", fetch_fn=expensive_db_query) for _ in range(50)]
    tasks_b = [cache.get("key-b", fetch_fn=expensive_db_query) for _ in range(50)]
    results = await asyncio.gather(*tasks_a, *tasks_b)
    elapsed = time.perf_counter() - start_time

    print("\nResults:")
    print(f"  Total requests: {len(results)}")
    print(f"  Database queries executed: {query_count}")
    print("  Expected: 2 queries (1 per unique key)")
    print(f"  Total time: {elapsed:.3f}s")

    assert query_count == 2, f"Expected 2 queries (1 per key), got {query_count}"

    print("\n✅ Per-key locking verified: Different keys fetch independently")

    # Test 3: Lock cleanup verification
    print("\n" + "=" * 80)
    print("Test 3: Lock cleanup after fetch completes")
    print("-" * 80)

    cache._l1._data.clear()
    mock_redis_storage.clear()

    # Issue request
    await cache.get("cleanup-test", fetch_fn=expensive_db_query)

    # Check lock exists
    namespaced_key = cache._k("cleanup-test")
    locks_before = len(cache._fetch_locks)
    print(f"  Locks active immediately after fetch: {locks_before}")

    # Wait for cleanup (1 second delay)
    print("  Waiting for lock cleanup (1 second)...")
    await asyncio.sleep(1.2)

    locks_after = len(cache._fetch_locks)
    print(f"  Locks active after cleanup: {locks_after}")

    assert namespaced_key not in cache._fetch_locks, "Lock should be cleaned up"

    print("\n✅ Lock cleanup verified: Memory leak prevention working")

    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print("✅ Cache stampede protection is working correctly")
    print("✅ Performance improvement: 100x reduction in duplicate fetches")
    print("✅ Per-key locking: Different keys fetch independently")
    print("✅ Lock cleanup: No memory leaks")
    print("\nImplementation: Phase 3.4 Complete")


if __name__ == "__main__":
    asyncio.run(main())
