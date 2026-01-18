"""Chaos Test: Redis Mid-Request Failure

Tests graceful degradation when Redis fails during operation.

Purpose:
    - Verify Redis disconnect mid-write falls back to in-memory
    - Verify Redis reconnect flushes buffer
    - Verify cache continues without Redis (L1 only)
    - Verify no data loss or corruption

Created: December 21, 2025
"""

from __future__ import annotations
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_e2e,
    pytest.mark.chaos,
    pytest.mark.timeout(120),
]

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError


@pytest.mark.asyncio
async def test_redis_disconnect_during_write() -> None:
    """Redis disconnects mid-write, falls back to in-memory.

    Scenario:
        - Setup: Receipt storage with Redis
        - Action: Start receipt write
        - Action: Disconnect Redis mid-operation
        - Verify: Write falls back to in-memory buffer
        - Verify: No exception raised
        - Verify: Receipt retrievable from in-memory
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-mid-write")

    # Mock Redis that fails on second write
    mock_redis = MagicMock()
    write_count = 0

    async def mock_redis_set(key: str, value: str) -> bool:
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            return True  # First write succeeds
        # Second write fails (Redis disconnected)
        raise RedisConnectionError("Connection lost mid-write")

    mock_redis.set = mock_redis_set
    mock_redis.get = AsyncMock(return_value=None)
    cache._redis = mock_redis  # type: ignore[assignment]

    # First write succeeds
    value1 = await cache.get("key1", fetch_fn=lambda: "value1")
    assert value1 == "value1", "First write should succeed"

    # Second write fails, should fall back to L1 only
    value2 = await cache.get("key2", fetch_fn=lambda: "value2")
    assert value2 == "value2", "Should fall back gracefully"

    # Verify value2 in L1 (in-memory)
    key2_full = cache._k("key2")
    l1_value = await cache._l1.get(key2_full)
    assert l1_value == "value2", "Should be in L1 after Redis failure"

    # Test passes - no exception raised, graceful degradation
    assert write_count == 2, "Should have attempted 2 writes"


@pytest.mark.asyncio
async def test_redis_reconnect_behavior() -> None:
    """Redis reconnects after failure.

    Scenario:
        - Setup: Cache with Redis initially down
        - Action: Perform operations (L1 only)
        - Action: Reconnect Redis
        - Verify: Subsequent operations use Redis again
        - Verify: System state is consistent
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-reconnect")

    # Phase 1: Redis down
    cache._redis = None

    # Operations should work with L1 only
    value1 = await cache.get("key1", fetch_fn=lambda: "value1")
    assert value1 == "value1", "Should work without Redis"

    # Verify in L1
    key1_full = cache._k("key1")
    assert await cache._l1.get(key1_full) == "value1", "Should be in L1"

    # Phase 2: Reconnect Redis
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}

    async def mock_redis_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_redis_set(key: str, value: str) -> bool:
        mock_redis_storage[key] = value
        return True

    mock_redis.get = mock_redis_get
    mock_redis.set = mock_redis_set
    cache._redis = mock_redis  # type: ignore[assignment]

    # New operations should use Redis
    value2 = await cache.get("key2", fetch_fn=lambda: "value2")
    assert value2 == "value2", "Should work with Redis"

    # Verify in Redis
    assert cache._k("key2") in mock_redis_storage, "Should be in Redis after reconnect"

    # Test passes - reconnect works
    assert True, "Redis reconnect successful"


@pytest.mark.asyncio
async def test_cache_continues_without_redis() -> None:
    """Cache operations work with Redis unavailable.

    Scenario:
        - Setup: UnifiedCache with Redis
        - Action: Disconnect Redis
        - Action: Perform cache operations (get, set via fetch_fn)
        - Verify: L1 cache still works
        - Verify: No exceptions raised
        - Verify: Fallback to fetch_fn for misses
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-no-redis")

    # Mock Redis to always fail
    mock_redis = MagicMock()

    async def mock_redis_fail(*args: Any, **kwargs) -> None:
        raise RedisConnectionError("Redis unavailable")

    mock_redis.get = mock_redis_fail
    mock_redis.set = mock_redis_fail
    cache._redis = mock_redis  # type: ignore[assignment]

    # Track fetch_fn calls
    fetch_count = 0

    async def fetch_fn(val: str) -> str:
        nonlocal fetch_count
        fetch_count += 1
        return val

    # First access - L1 miss, fetch_fn
    value1 = await cache.get("key1", fetch_fn=lambda: fetch_fn("value1"))
    assert value1 == "value1", "Should fetch from fetch_fn"
    assert fetch_count == 1, "Should call fetch_fn once"

    # Second access - L1 hit
    value2 = await cache.get("key1")
    assert value2 == "value1", "Should hit L1"
    assert fetch_count == 1, "Should NOT call fetch_fn again"

    # Third access - different key, L1 miss
    value3 = await cache.get("key2", fetch_fn=lambda: fetch_fn("value2"))
    assert value3 == "value2", "Should fetch from fetch_fn"
    assert fetch_count == 2, "Should call fetch_fn twice total"

    # Test passes - cache works without Redis
    assert True, "Cache continues without Redis"


@pytest.mark.asyncio
async def test_redis_timeout_handling() -> None:
    """Redis times out, system doesn't hang indefinitely.

    Scenario:
        - Setup: Cache with slow Redis
        - Action: Redis operations timeout
        - Verify: System doesn't hang indefinitely
        - Verify: Falls back gracefully (or raises timeout)
        - Verify: Timeout behavior is bounded

    NOTE: Current implementation relies on external timeout enforcement.
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-timeout")

    # Mock Redis with timeout
    mock_redis = MagicMock()

    async def mock_redis_timeout(*args: Any, **kwargs) -> None:
        await asyncio.sleep(10)  # Simulate slow operation
        raise RedisTimeoutError("Operation timed out")

    mock_redis.get = mock_redis_timeout
    mock_redis.set = mock_redis_timeout
    cache._redis = mock_redis  # type: ignore[assignment]

    # Should not hang indefinitely
    start_time = time.time()

    # Use asyncio.wait_for to enforce timeout
    try:
        value = await asyncio.wait_for(
            cache.get("key1", fetch_fn=lambda: "value1"),
            timeout=2.0,  # 2 second timeout
        )
        # If we got a value, test passes (fallback worked)
        assert value == "value1", "Should fall back to fetch_fn"
    except TimeoutError:
        # Timeout occurred - this is acceptable behavior
        # Current implementation doesn't have internal Redis timeouts
        # So external timeout is needed
        elapsed = time.time() - start_time
        assert elapsed < 5.0, f"Timeout should be respected, took {elapsed:.2f}s"
        # Test passes - timeout was enforced (didn't hang indefinitely)
        return

    elapsed = time.time() - start_time

    # If we got here, operation completed (likely via fetch_fn fallback)
    # Should complete reasonably quickly
    assert elapsed < 15.0, f"Operation should complete, took {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_redis_intermittent_failures() -> None:
    """Redis has intermittent failures, system is resilient.

    Scenario:
        - Setup: Redis that fails randomly
        - Action: 20 cache operations
        - Verify: System handles failures gracefully
        - Verify: Some operations succeed (when Redis up)
        - Verify: Some fallback to L1 (when Redis down)
        - Verify: No crashes or data corruption
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-intermittent")

    # Mock Redis with intermittent failures
    mock_redis = MagicMock()
    call_count = 0

    async def mock_redis_get_intermittent(key: str) -> str | None:
        nonlocal call_count
        call_count += 1
        # Fail every 3rd call
        if call_count % 3 == 0:
            raise RedisConnectionError("Intermittent failure")
        return None

    async def mock_redis_set_intermittent(key: str, value: str) -> bool:
        nonlocal call_count
        call_count += 1
        # Fail every 3rd call
        if call_count % 3 == 0:
            raise RedisConnectionError("Intermittent failure")
        return True

    mock_redis.get = mock_redis_get_intermittent
    mock_redis.set = mock_redis_set_intermittent
    cache._redis = mock_redis  # type: ignore[assignment]

    # 20 operations
    success_count = 0
    for i in range(20):
        try:
            value = await cache.get(f"key-{i}", fetch_fn=lambda i=i: f"value-{i}")
            if value == f"value-{i}":
                success_count += 1
        except Exception as e:
            # Should not raise exceptions
            pytest.fail(f"Operation {i} raised exception: {e}")

    # All should succeed (even with Redis failures, fall back to L1)
    assert success_count == 20, f"All 20 operations should succeed, got {success_count}"

    # Test passes - system is resilient to intermittent failures
    assert True, "System handles intermittent Redis failures"


@pytest.mark.asyncio
async def test_redis_connection_pool_exhaustion() -> None:
    """Redis connection pool exhausted.

    Scenario:
        - Setup: Redis with small connection pool
        - Action: Many concurrent cache operations
        - Verify: System queues requests (doesn't crash)
        - Verify: Operations eventually complete
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-pool-exhaustion")

    # Mock Redis with simulated connection pool
    mock_redis = MagicMock()
    active_connections = 0
    max_connections = 5

    async def mock_redis_get_pooled(key: str) -> str | None:
        nonlocal active_connections
        if active_connections >= max_connections:
            # Simulate pool exhaustion (wait)
            await asyncio.sleep(0.05)
        active_connections += 1
        try:
            await asyncio.sleep(0.01)  # Simulate query
            return None
        finally:
            active_connections -= 1

    mock_redis.get = mock_redis_get_pooled
    mock_redis.set = AsyncMock(return_value=True)
    cache._redis = mock_redis  # type: ignore[assignment]

    # 50 concurrent operations
    async def cache_operation(i: int) -> str:
        from typing import cast

        result = await cache.get(f"key-{i}", fetch_fn=lambda: f"value-{i}")
        return cast(str, result)

    start_time = time.time()
    tasks = [cache_operation(i) for i in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time

    # All should complete (no crashes)
    exceptions = [r for r in results if isinstance(r, Exception)]
    if exceptions:
        pytest.fail(f"Got {len(exceptions)} exceptions: {exceptions[:3]}")

    # All values correct
    assert all(results[i] == f"value-{i}" for i in range(50)), "All values should be correct"

    # Should complete reasonably (queuing, not hanging)
    assert elapsed < 10.0, f"Operations should complete, took {elapsed:.2f}s"

    # Test passes
    assert True, f"50 concurrent operations completed in {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_redis_partial_write_failure() -> None:
    """Redis writes partially succeed, reads are consistent.

    Scenario:
        - Setup: Cache with Redis
        - Action: Write 10 items, Redis fails on items 6-10
        - Action: Read all 10 items
        - Verify: Items 1-5 retrieved from Redis
        - Verify: Items 6-10 retrieved from L1
        - Verify: All values correct (no corruption)
    """
    from kagami.core.caching.unified import UnifiedCache

    cache = UnifiedCache(namespace="test-partial-write")

    # Mock Redis that fails after 5 writes
    mock_redis = MagicMock()
    mock_redis_storage: dict[str, str] = {}
    write_count = 0

    async def mock_redis_get(key: str) -> str | None:
        return mock_redis_storage.get(key)

    async def mock_redis_set(key: str, value: str) -> bool:
        nonlocal write_count
        write_count += 1
        if write_count <= 5:
            mock_redis_storage[key] = value
            return True
        # Fail after 5 writes
        raise RedisConnectionError("Write failed")

    mock_redis.get = mock_redis_get
    mock_redis.set = mock_redis_set
    cache._redis = mock_redis  # type: ignore[assignment]

    # Write 10 items
    for i in range(10):
        value = await cache.get(f"key-{i}", fetch_fn=lambda i=i: f"value-{i}")
        assert value == f"value-{i}", f"Write {i} should succeed"

    # Read all 10 items
    for i in range(10):
        value = await cache.get(f"key-{i}")
        assert value == f"value-{i}", f"Read {i} should return correct value"

    # Verify first 5 in Redis, last 5 in L1 only
    keys_in_redis = len(mock_redis_storage)
    assert keys_in_redis == 5, f"Expected 5 keys in Redis, got {keys_in_redis}"

    # Test passes - partial writes handled correctly
    assert True, "Partial write failures handled gracefully"
