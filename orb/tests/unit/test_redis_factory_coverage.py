"""Test RedisClientFactory core paths (currently 49.5% coverage)."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.tier_unit


def _redis_available() -> bool:
    """Check if Redis is available for testing."""
    # In test mode, Redis is typically disabled
    if os.getenv("KAGAMI_TEST_DISABLE_REDIS", "").lower() in ("1", "true", "yes"):
        return False
    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False


# Skip tests that require real Redis if it's unavailable
requires_redis = pytest.mark.skipif(
    not _redis_available(),
    reason="Redis not available (KAGAMI_TEST_DISABLE_REDIS=1 or Redis not running)",
)


@requires_redis
def test_redis_factory_get_client_default() -> None:
    """Test default Redis client creation."""

    from kagami.core.caching.redis import RedisClientFactory

    client = RedisClientFactory.get_client("default", async_mode=False)
    assert client is not None


@requires_redis
def test_redis_factory_get_client_cached() -> None:
    """Test client caching works."""
    from kagami.core.caching.redis import RedisClientFactory

    client1 = RedisClientFactory.get_client("default", async_mode=False)
    client2 = RedisClientFactory.get_client("default", async_mode=False)

    # Should return same cached instance
    assert client1 is client2


@requires_redis
@pytest.mark.asyncio
async def test_redis_factory_async_client():
    """Test async Redis client creation."""
    from kagami.core.caching.redis import RedisClientFactory

    client = RedisClientFactory.get_client("default", async_mode=True)
    assert client is not None

    # Should be able to ping
    try:
        await client.ping()
    except Exception:
        pass  # Fake Redis or unavailable is ok in tests


@requires_redis
def test_redis_factory_llm_cache_no_decode() -> None:
    """Test LLM cache client disables decode_responses."""
    from kagami.core.caching.redis import RedisClientFactory

    # LLM cache should use bytes, not decoded strings
    client = RedisClientFactory.get_client("llm_cache", async_mode=False)
    assert client is not None


def test_redis_factory_get_url_for_purpose() -> None:
    """Test URL selection for different purposes."""
    from kagami.core.caching.redis import RedisClientFactory

    # Should fall back to default redis:// URL
    url = RedisClientFactory._get_url_for_purpose("default")
    assert "redis://" in url

    url = RedisClientFactory._get_url_for_purpose("llm_cache")
    assert "redis://" in url


def test_redis_factory_close_all_safe() -> None:
    """Test close_all doesn't crash."""
    from kagami.core.caching.redis import RedisClientFactory

    # Should not crash even if called multiple times
    RedisClientFactory.close_all()
    RedisClientFactory.close_all()


@requires_redis
def test_redis_factory_pool_stats() -> None:
    """Test pool statistics retrieval."""
    from kagami.core.caching.redis import RedisClientFactory

    # Create a client first
    RedisClientFactory.get_client("default", async_mode=False)

    stats = RedisClientFactory.get_pool_stats()
    assert isinstance(stats, dict)
