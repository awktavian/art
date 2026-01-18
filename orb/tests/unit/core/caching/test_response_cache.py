"""Unit Tests: ResponseCache

Tests two-tier caching (L1 memory + L2 Redis), TTL support, rate limiting,
pattern-based invalidation, and key generation.

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
import json
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_response_cache_l1_hit():
    """Test L1 (memory) cache hit.

    Scenario:
        - Set value in cache
        - Get value (should hit L1)
        - Verify no Redis access
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, max_size=100, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test-l1")

    # Set value
    await cache.set("test-key", "test-value")

    # Get value - should hit L1
    result = await cache.get("test-key")
    assert result == "test-value"


@pytest.mark.asyncio
async def test_response_cache_l1_l2_promotion():
    """Test L2 (Redis) hit promotes to L1.

    Scenario:
        - Pre-populate L2 (Redis) only
        - Get value (L1 miss, L2 hit)
        - Verify value promoted to L1
        - Second get should hit L1
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=True)
    cache = ResponseCache(config=config, namespace="test-l2-promotion")

    # Mock Redis with pre-populated value
    mock_redis = AsyncMock()
    redis_storage = {"test-key": json.dumps("redis-value")}
    mock_redis.get.side_effect = lambda k: redis_storage.get(k)
    mock_redis.setex = AsyncMock()

    # Inject mock Redis
    cache._redis_client = mock_redis

    # Clear L1
    cache._memory_cache.clear()
    cache._access_times.clear()

    # Get value - L2 hit
    result = await cache.get("test-key")
    assert result == "redis-value"

    # Verify L1 promoted
    assert "test-key" in cache._memory_cache

    # Second get should hit L1 (no Redis call)
    mock_redis.get.reset_mock()
    result2 = await cache.get("test-key")
    assert result2 == "redis-value"
    mock_redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_response_cache_ttl_expiration():
    """Test TTL expiration in L1 cache.

    Scenario:
        - Set value with short TTL
        - Get immediately (hit)
        - Wait for expiration
        - Get again (miss)
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=0.1, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test-ttl")

    # Set value
    await cache.set("ttl-key", "ttl-value")

    # Immediate get - hit
    result1 = await cache.get("ttl-key")
    assert result1 == "ttl-value"

    # Wait for expiration
    await asyncio.sleep(0.15)

    # Get after expiration - miss
    result2 = await cache.get("ttl-key")
    assert result2 is None


@pytest.mark.asyncio
async def test_response_cache_lru_eviction():
    """Test LRU eviction in L1 cache.

    Scenario:
        - Create cache with max_size=3
        - Add 4 items
        - Verify least recently used evicted
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, max_size=3, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test-lru")

    # Add 3 items
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Access key1 to make it recently used
    await cache.get("key1")

    # Add 4th item - should evict key2 (least recent)
    await cache.set("key4", "value4")

    # Verify key2 evicted
    assert await cache.get("key2") is None

    # Verify others remain
    assert await cache.get("key1") == "value1"
    assert await cache.get("key3") == "value3"
    assert await cache.get("key4") == "value4"


@pytest.mark.asyncio
async def test_response_cache_delete():
    """Test cache deletion across L1 and L2.

    Scenario:
        - Set value (populates L1 and L2)
        - Delete key
        - Verify removed from both L1 and L2
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=True)
    cache = ResponseCache(config=config, namespace="test-delete")

    # Mock Redis
    mock_redis = AsyncMock()
    redis_storage: dict[str, str] = {}

    async def mock_setex(key: str, ttl: int, value: str) -> None:
        redis_storage[key] = value

    async def mock_delete(key: str) -> None:
        redis_storage.pop(key, None)

    mock_redis.setex = mock_setex
    mock_redis.delete = mock_delete
    cache._redis_client = mock_redis

    # Set value
    await cache.set("delete-key", "delete-value")

    # Verify in L1
    assert "delete-key" in cache._memory_cache

    # Delete
    await cache.delete("delete-key")

    # Verify removed from L1
    assert "delete-key" not in cache._memory_cache

    # Verify delete called on Redis
    assert "delete-key" not in redis_storage


@pytest.mark.asyncio
async def test_response_cache_clear():
    """Test cache clearing.

    Scenario:
        - Populate cache with multiple keys
        - Clear cache
        - Verify all keys removed from L1 and L2
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=True)
    cache = ResponseCache(config=config, namespace="test-clear")

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=["test-clear:key1", "test-clear:key2"])
    mock_redis.delete = AsyncMock()
    cache._redis_client = mock_redis

    # Populate L1
    cache._memory_cache["key1"] = ("value1", float("inf"))
    cache._memory_cache["key2"] = ("value2", float("inf"))

    # Clear
    await cache.clear()

    # Verify L1 cleared
    assert len(cache._memory_cache) == 0

    # Verify Redis keys/delete called
    mock_redis.keys.assert_called_once()
    mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_response_cache_pattern_invalidation():
    """Test pattern-based cache invalidation.

    Scenario:
        - Populate cache with multiple keys
        - Invalidate keys matching pattern
        - Verify matching keys removed, others remain
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=True)
    cache = ResponseCache(config=config, namespace="test-invalidate")

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(
        return_value=["test-invalidate:user:123", "test-invalidate:user:456"]
    )
    mock_redis.delete = AsyncMock()
    cache._redis_client = mock_redis

    # Populate L1 with various keys
    cache._memory_cache["user:123"] = ("user-data-123", float("inf"))
    cache._memory_cache["user:456"] = ("user-data-456", float("inf"))
    cache._memory_cache["product:789"] = ("product-data", float("inf"))
    cache._access_times = {
        "user:123": 1.0,
        "user:456": 1.0,
        "product:789": 1.0,
    }

    # Invalidate pattern "user:"
    await cache.invalidate("user:")

    # Verify user keys removed
    assert "user:123" not in cache._memory_cache
    assert "user:456" not in cache._memory_cache

    # Verify product key remains
    assert "product:789" in cache._memory_cache


@pytest.mark.asyncio
async def test_response_cache_intent_to_key():
    """Test intent-based cache key generation.

    Scenario:
        - Convert intent dict to stable key
        - Verify same intent produces same key
        - Verify different intent produces different key
    """
    from kagami.core.caching.response_cache import ResponseCache

    cache = ResponseCache(namespace="test-intent")

    intent1 = {"action": "translate", "language": "en", "text": "hello"}
    intent2 = {"action": "translate", "language": "en", "text": "hello"}
    intent3 = {"action": "translate", "language": "fr", "text": "hello"}

    key1 = cache.intent_to_key(intent1)
    key2 = cache.intent_to_key(intent2)
    key3 = cache.intent_to_key(intent3)

    # Same intent → same key
    assert key1 == key2

    # Different intent → different key
    assert key1 != key3


@pytest.mark.asyncio
async def test_response_cache_get_cache_key():
    """Test LLM request parameter-based key generation.

    Scenario:
        - Generate cache key from LLM parameters
        - Verify same parameters produce same key
        - Verify different parameters produce different key
    """
    from kagami.core.caching.response_cache import ResponseCache

    cache = ResponseCache(namespace="test-llm-key")

    key1 = cache.get_cache_key(
        prompt="What is AI?",
        app_name="test-app",
        task_type="qa",
        max_tokens=100,
        temperature=0.7,
        model="gpt-4",
    )

    key2 = cache.get_cache_key(
        prompt="What is AI?",
        app_name="test-app",
        task_type="qa",
        max_tokens=100,
        temperature=0.7,
        model="gpt-4",
    )

    key3 = cache.get_cache_key(
        prompt="What is ML?",  # Different prompt
        app_name="test-app",
        task_type="qa",
        max_tokens=100,
        temperature=0.7,
        model="gpt-4",
    )

    # Same parameters → same key
    assert key1 == key2

    # Different prompt → different key
    assert key1 != key3


@pytest.mark.asyncio
async def test_response_cache_stats():
    """Test cache statistics.

    Scenario:
        - Populate cache
        - Get stats
        - Verify correct statistics returned
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=1800, max_size=50, enable_redis=True)
    cache = ResponseCache(config=config, namespace="test-stats")

    # Mock Redis
    mock_redis = AsyncMock()
    cache._redis_client = mock_redis

    # Populate
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    stats = cache.get_stats()

    assert stats["namespace"] == "test-stats"
    assert stats["memory_entries"] == 2
    assert stats["max_size"] == 50
    assert stats["ttl"] == 1800
    assert stats["redis_enabled"] is True


@pytest.mark.asyncio
async def test_response_cache_json_serialization():
    """Test JSON serialization for complex objects.

    Scenario:
        - Set dict value
        - Set list value
        - Retrieve and verify deserialization
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=True)
    cache = ResponseCache(config=config, namespace="test-json")

    # Mock Redis
    mock_redis = AsyncMock()
    redis_storage: dict[str, str] = {}

    async def mock_setex(key: str, ttl: int, value: str) -> None:
        redis_storage[key] = value

    async def mock_get(key: str) -> str | None:
        return redis_storage.get(key)

    mock_redis.setex = mock_setex
    mock_redis.get = mock_get
    cache._redis_client = mock_redis

    # Set dict
    dict_value = {"name": "test", "count": 42, "active": True}
    await cache.set("dict-key", dict_value)

    # Set list
    list_value = ["a", "b", "c", 1, 2, 3]
    await cache.set("list-key", list_value)

    # Clear L1 to force L2 fetch
    cache._memory_cache.clear()
    cache._access_times.clear()

    # Get dict - should deserialize correctly
    result_dict = await cache.get("dict-key")
    assert result_dict == dict_value

    # Get list - should deserialize correctly
    result_list = await cache.get("list-key")
    assert result_list == list_value


@pytest.mark.asyncio
async def test_response_cache_rate_limiting():
    """Test rate limiting integration.

    Scenario:
        - Mock rate limiter to block
        - Attempt cache get
        - Verify RateLimitError raised
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache
    from kagami.core.unified_rate_limiter import RateLimitError

    config = CacheConfig(ttl=3600, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test-rate-limit")

    # Mock rate limiter to block
    mock_limiter = AsyncMock()
    mock_limiter.check_limit = AsyncMock(return_value=(False, 1.0))
    mock_limiter.strategy = "block"
    cache._rate_limiter = mock_limiter

    # Attempt get - should raise RateLimitError
    with pytest.raises(RateLimitError, match="Rate limit exceeded"):
        await cache.get("test-key")


@pytest.mark.asyncio
async def test_response_cache_rate_limiting_delay():
    """Test rate limiting with delay strategy.

    Scenario:
        - Mock rate limiter with delay strategy
        - Attempt cache get
        - Verify delay applied (no exception)
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test-rate-delay")

    # Mock rate limiter with delay strategy
    mock_limiter = AsyncMock()
    mock_limiter.check_limit = AsyncMock(return_value=(False, 0.05))
    mock_limiter.strategy = "delay"
    cache._rate_limiter = mock_limiter

    # Set value
    cache._memory_cache["test-key"] = ("test-value", float("inf"))

    # Attempt get - should delay but succeed
    import time

    start = time.time()
    result = await cache.get("test-key")
    elapsed = time.time() - start

    assert result == "test-value"
    assert elapsed >= 0.05  # Delay was applied


@pytest.mark.asyncio
async def test_response_cache_custom_ttl():
    """Test custom TTL override.

    Scenario:
        - Create cache with default TTL=3600
        - Set value with custom TTL=0.1
        - Verify custom TTL used
    """
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(ttl=3600, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test-custom-ttl")

    # Set with custom TTL
    await cache.set("custom-key", "custom-value", ttl=0.1)

    # Should exist immediately
    assert await cache.get("custom-key") == "custom-value"

    # Wait for custom TTL expiration
    await asyncio.sleep(0.15)

    # Should be expired
    assert await cache.get("custom-key") is None
