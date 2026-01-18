"""Unit Tests: MemoryCache

Tests LRU eviction, TTL expiration, statistics tracking, and dict-style access.

Created: December 27, 2025
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
import time
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_memory_cache_basic_set_get() -> None:
    """Test basic set/get operations.

    Scenario:
        - Set a key-value pair
        - Get the value back
        - Verify correct value returned
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-basic", max_size=100)

    # Set and get
    await cache.set("key1", "value1")
    result = await cache.get("key1")

    assert result == "value1"


@pytest.mark.asyncio
async def test_memory_cache_ttl_expiration() -> None:
    """Test TTL-based cache expiration.

    Scenario:
        - Set key with 0.1s TTL
        - Get immediately (should hit)
        - Wait 0.2s
        - Get again (should miss - expired)
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-ttl", max_size=100)

    # Set with 0.1s TTL
    await cache.set("ttl-key", "ttl-value", ttl=0.1)

    # Immediate get should hit
    result1 = await cache.get("ttl-key")
    assert result1 == "ttl-value"

    # Wait for expiration
    await asyncio.sleep(0.15)

    # Should be expired
    result2 = await cache.get("ttl-key", default="default")
    assert result2 == "default"


@pytest.mark.asyncio
async def test_memory_cache_lru_eviction() -> None:
    """Test LRU eviction when max_size reached.

    Scenario:
        - Create cache with max_size=3
        - Add 4 items
        - Verify oldest item evicted
        - Verify eviction counter incremented
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-lru", max_size=3)

    # Add 3 items (at capacity)
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Verify all present
    assert await cache.get("key1") == "value1"
    assert await cache.get("key2") == "value2"
    assert await cache.get("key3") == "value3"

    # Add 4th item - should evict key1 (least recently used)
    await cache.set("key4", "value4")

    # key1 should be evicted
    assert await cache.get("key1", default="missing") == "missing"

    # Others should remain
    assert await cache.get("key2") == "value2"
    assert await cache.get("key3") == "value3"
    assert await cache.get("key4") == "value4"

    # Verify eviction counter
    stats = cache.stats()
    assert stats["evictions"] == 1


@pytest.mark.asyncio
async def test_memory_cache_lru_access_order() -> None:
    """Test LRU eviction respects access order.

    Scenario:
        - Add 3 items (at capacity)
        - Access key1 (makes it most recent)
        - Add 4th item
        - Verify key2 evicted (not key1)
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-lru-order", max_size=3)

    # Add 3 items
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Access key1 - makes it most recent
    _ = await cache.get("key1")

    # Add 4th item - should evict key2 (least recent)
    await cache.set("key4", "value4")

    # key1 should still be present (was accessed recently)
    assert await cache.get("key1") == "value1"

    # key2 should be evicted
    assert await cache.get("key2", default="missing") == "missing"

    # key3 and key4 should remain
    assert await cache.get("key3") == "value3"
    assert await cache.get("key4") == "value4"


@pytest.mark.asyncio
async def test_memory_cache_stats_tracking() -> None:
    """Test cache statistics tracking.

    Scenario:
        - Perform hits and misses
        - Trigger evictions
        - Verify stats correctly tracked
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-stats", max_size=2)

    # Initial stats
    stats = cache.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["evictions"] == 0
    assert stats["size"] == 0
    assert stats["hit_rate"] == 0.0

    # Add items
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    # Cache hit
    _ = await cache.get("key1")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    assert stats["size"] == 2

    # Cache miss
    _ = await cache.get("key3", default="missing")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5  # 1 hit / 2 total

    # Trigger eviction
    await cache.set("key3", "value3")
    stats = cache.stats()
    assert stats["evictions"] == 1
    assert stats["size"] == 2


@pytest.mark.asyncio
async def test_memory_cache_dict_style_access() -> None:
    """Test dict-style access (cache[key]).

    Scenario:
        - Use __setitem__, __getitem__, __delitem__
        - Use 'in' operator (__contains__)
        - Verify all work correctly
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-dict", max_size=100)

    # __setitem__
    cache["dict-key"] = "dict-value"

    # __contains__
    assert "dict-key" in cache
    assert "missing-key" not in cache

    # __getitem__
    assert cache["dict-key"] == "dict-value"

    # __delitem__
    del cache["dict-key"]
    assert "dict-key" not in cache

    # KeyError on missing key
    with pytest.raises(KeyError):
        _ = cache["missing-key"]


@pytest.mark.asyncio
async def test_memory_cache_delete() -> None:
    """Test explicit cache deletion.

    Scenario:
        - Set key
        - Delete key
        - Verify key no longer exists
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-delete", max_size=100)

    # Set key
    await cache.set("delete-key", "delete-value")
    assert await cache.exists("delete-key")

    # Delete key
    deleted = await cache.delete("delete-key")
    assert deleted is True

    # Verify deleted
    assert not await cache.exists("delete-key")
    assert await cache.get("delete-key", default="missing") == "missing"

    # Delete non-existent key
    deleted2 = await cache.delete("missing-key")
    assert deleted2 is False


@pytest.mark.asyncio
async def test_memory_cache_clear() -> None:
    """Test cache clearing.

    Scenario:
        - Add multiple keys
        - Clear cache
        - Verify all keys removed
        - Verify stats reset
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-clear", max_size=100)

    # Add items
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Trigger stats
    _ = await cache.get("key1")
    _ = await cache.get("missing", default="x")

    # Clear
    await cache.clear()

    # Verify stats reset BEFORE checking keys (checking increments misses)
    stats = cache.stats()
    assert stats["size"] == 0
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Verify all gone (this will increment misses, which is expected)
    assert await cache.get("key1", default="missing") == "missing"
    assert await cache.get("key2", default="missing") == "missing"
    assert await cache.get("key3", default="missing") == "missing"

    # After checking missing keys, misses should be incremented
    stats_after = cache.stats()
    assert stats_after["misses"] == 3


@pytest.mark.asyncio
async def test_memory_cache_zero_ttl() -> None:
    """Test zero/negative TTL behavior (immediate expiration).

    Scenario:
        - Set key with TTL=0
        - Verify key not cached
        - Set key with TTL=-1
        - Verify key not cached
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-zero-ttl", max_size=100)

    # TTL=0 should not cache
    await cache.set("zero-ttl", "value", ttl=0)
    assert await cache.get("zero-ttl", default="missing") == "missing"

    # TTL=-1 should not cache
    await cache.set("neg-ttl", "value", ttl=-1)
    assert await cache.get("neg-ttl", default="missing") == "missing"

    # Verify size is 0
    stats = cache.stats()
    assert stats["size"] == 0


@pytest.mark.asyncio
async def test_memory_cache_default_ttl() -> None:
    """Test default TTL from constructor.

    Scenario:
        - Create cache with default_ttl=0.1s
        - Set key without explicit TTL
        - Verify default TTL applied
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-default-ttl", max_size=100, default_ttl=0.1)

    # Set without explicit TTL - should use default
    await cache.set("default-key", "default-value")

    # Should exist immediately
    assert await cache.get("default-key") == "default-value"

    # Wait for default TTL expiration
    await asyncio.sleep(0.15)

    # Should be expired
    assert await cache.get("default-key", default="missing") == "missing"


@pytest.mark.asyncio
async def test_memory_cache_override_default_ttl() -> None:
    """Test explicit TTL overrides default TTL.

    Scenario:
        - Create cache with default_ttl=0.1s
        - Set key with explicit ttl=1.0s
        - Verify explicit TTL used
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-override-ttl", max_size=100, default_ttl=0.1)

    # Set with explicit TTL (overrides default)
    await cache.set("override-key", "override-value", ttl=1.0)

    # Wait past default TTL but before explicit TTL
    await asyncio.sleep(0.15)

    # Should still exist (explicit TTL=1.0s)
    assert await cache.get("override-key") == "override-value"


@pytest.mark.asyncio
async def test_cache_manager_multiple_caches() -> None:
    """Test CacheManager with multiple named caches.

    Scenario:
        - Create manager
        - Get multiple named caches
        - Verify isolation
    """
    from kagami.core.caching.memory_cache import CacheManager

    manager = CacheManager()

    # Get named caches
    cache_a = manager.get_cache("cache-a")
    cache_b = manager.get_cache("cache-b")

    # Set in cache A
    cache_a.set_sync("key", "value-a")

    # Set in cache B
    cache_b.set_sync("key", "value-b")

    # Verify isolation
    assert cache_a.get_sync("key") == "value-a"
    assert cache_b.get_sync("key") == "value-b"


@pytest.mark.asyncio
async def test_cache_manager_clear_specific() -> None:
    """Test CacheManager clearing specific cache.

    Scenario:
        - Populate cache A and cache B
        - Clear cache A only
        - Verify cache B unaffected
    """
    from kagami.core.caching.memory_cache import CacheManager

    manager = CacheManager()

    # Populate caches
    manager.set_value("cache-a", "key1", "value-a1")
    manager.set_value("cache-a", "key2", "value-a2")
    manager.set_value("cache-b", "key1", "value-b1")

    # Clear cache A
    manager.clear("cache-a")

    # Verify cache A cleared
    assert manager.get_value("cache-a", "key1", default="missing") == "missing"
    assert manager.get_value("cache-a", "key2", default="missing") == "missing"

    # Verify cache B unaffected
    assert manager.get_value("cache-b", "key1") == "value-b1"


@pytest.mark.asyncio
async def test_cache_manager_clear_all() -> None:
    """Test CacheManager clearing all caches.

    Scenario:
        - Populate multiple caches
        - Clear all (no cache_name specified)
        - Verify all caches cleared
    """
    from kagami.core.caching.memory_cache import CacheManager

    manager = CacheManager()

    # Populate caches
    manager.set_value("cache-a", "key", "value-a")
    manager.set_value("cache-b", "key", "value-b")
    await manager.set("default-key", "default-value")

    # Clear all
    manager.clear()

    # Verify all cleared
    assert manager.get_value("cache-a", "key", default="missing") == "missing"
    assert manager.get_value("cache-b", "key", default="missing") == "missing"
    assert await manager.get("default-key", default="missing") == "missing"


@pytest.mark.asyncio
async def test_cache_manager_decorator() -> None:
    """Test CacheManager @cached decorator.

    Scenario:
        - Decorate function with @cached
        - Call function twice with same args
        - Verify second call uses cache (no re-execution)
    """
    from kagami.core.caching.memory_cache import CacheManager

    manager = CacheManager()

    call_count = 0

    @manager.cached("test-cache", ttl=60)
    async def expensive_function(x: int, y: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate expensive operation
        return x + y

    # First call - executes function
    result1 = await expensive_function(10, 20)
    assert result1 == 30
    assert call_count == 1

    # Second call - uses cache
    result2 = await expensive_function(10, 20)
    assert result2 == 30
    assert call_count == 1  # Not re-executed

    # Different args - executes again
    result3 = await expensive_function(5, 10)
    assert result3 == 15
    assert call_count == 2


# =============================================================================
# EDGE CASES - Added for 100/100 test quality
# =============================================================================


@pytest.mark.asyncio
async def test_memory_cache_empty_key() -> None:
    """Edge case: Empty string as key.

    Scenario:
        - Set value with empty string key
        - Verify retrieval works
        - Verify stats track correctly
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-empty-key", max_size=10)

    # Empty string key should work
    await cache.set("", "empty-key-value")
    result = await cache.get("")
    assert result == "empty-key-value"

    # Stats should reflect this
    stats = cache.stats()
    assert stats["size"] == 1


@pytest.mark.asyncio
async def test_memory_cache_none_value() -> None:
    """Edge case: None as value.

    Scenario:
        - Set None as value
        - Verify retrieval distinguishes None from missing
        - Verify default only used for missing keys
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-none-value", max_size=10)

    # Store None explicitly
    await cache.set("key-none", None)

    # Should get None back (not default)
    result = await cache.get("key-none", default="not-none")
    assert result is None

    # Missing key should return default
    result2 = await cache.get("missing-key", default="default-value")
    assert result2 == "default-value"


@pytest.mark.asyncio
async def test_memory_cache_unicode_key() -> None:
    """Edge case: Unicode characters in key.

    Scenario:
        - Use various unicode keys (emoji, CJK, RTL)
        - Verify all work correctly
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-unicode", max_size=10)

    unicode_keys = [
        ("emoji-🎮", "game-value"),
        ("cjk-日本語", "japanese-value"),
        ("rtl-مرحبا", "arabic-value"),
        ("special-\n\t", "whitespace-value"),
        ("long-" + "x" * 1000, "long-key-value"),
    ]

    for key, value in unicode_keys:
        await cache.set(key, value)
        result = await cache.get(key)
        assert result == value, f"Failed for key: {key!r}"


@pytest.mark.asyncio
async def test_memory_cache_concurrent_access() -> None:
    """Edge case: Concurrent reads and writes.

    Scenario:
        - Launch 100 concurrent operations
        - Mix of reads and writes
        - Verify no crashes or data corruption
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-concurrent", max_size=50)

    async def writer(i: int) -> None:
        await cache.set(f"key-{i}", f"value-{i}")

    async def reader(i: int) -> str | None:
        return await cache.get(f"key-{i % 20}")  # Read from subset

    # Launch concurrent operations
    tasks = []
    for i in range(50):
        tasks.append(writer(i))
        tasks.append(reader(i))

    await asyncio.gather(*tasks)

    # Verify cache is in consistent state
    stats = cache.stats()
    assert stats["size"] <= 50  # max_size respected
    assert stats["size"] > 0


@pytest.mark.asyncio
async def test_memory_cache_overwrite_updates_access_time() -> None:
    """Edge case: Overwriting value should update access time.

    Scenario:
        - Add items to fill cache
        - Overwrite oldest item
        - Add new item
        - Verify overwritten item survives (not evicted)
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-overwrite-lru", max_size=3)

    # Fill cache
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Overwrite key1 - should update its access time
    await cache.set("key1", "updated-value1")

    # Add new item - should evict key2 (oldest not-updated)
    await cache.set("key4", "value4")

    # key1 should survive (was updated recently)
    assert await cache.get("key1") == "updated-value1"

    # key2 should be evicted
    assert await cache.get("key2", default="gone") == "gone"


@pytest.mark.asyncio
async def test_memory_cache_zero_max_size() -> None:
    """Edge case: Zero max_size (should still work).

    Scenario:
        - Create cache with max_size=0
        - Verify behavior is defined (likely no storage or error)
    """
    from kagami.core.caching.memory_cache import MemoryCache

    # This should not crash
    cache = MemoryCache(name="test-zero-size", max_size=0)

    # Set should be a no-op or raise gracefully
    try:
        await cache.set("key", "value")
        # If it accepts, get should return None or raise
        result = await cache.get("key", default="default")
        # Either default (not stored) or value (if 0 means unlimited)
        assert result in ["value", "default"]
    except (ValueError, RuntimeError):
        pass  # Acceptable to reject zero size


@pytest.mark.asyncio
async def test_memory_cache_negative_ttl() -> None:
    """Edge case: Negative TTL (should expire immediately or error).

    Scenario:
        - Set with negative TTL
        - Verify defined behavior
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-negative-ttl", max_size=10)

    try:
        await cache.set("key", "value", ttl=-1)
        # If accepted, should expire immediately
        await asyncio.sleep(0.01)
        result = await cache.get("key", default="expired")
        assert result == "expired"
    except (ValueError, RuntimeError):
        pass  # Acceptable to reject negative TTL


@pytest.mark.asyncio
async def test_memory_cache_large_value() -> None:
    """Edge case: Very large values.

    Scenario:
        - Store 1MB value
        - Verify retrieval works
    """
    from kagami.core.caching.memory_cache import MemoryCache

    cache = MemoryCache(name="test-large-value", max_size=10)

    large_value = "x" * (1024 * 1024)  # 1MB string

    await cache.set("large-key", large_value)
    result = await cache.get("large-key")

    assert result == large_value
    assert len(result) == 1024 * 1024
