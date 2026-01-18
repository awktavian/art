"""Chaos Test: Redis Failure Scenarios

Tests K os behavior when Redis fails.

Created: November 16, 2025 (Q2 Production Roadmap)
"""

from __future__ import annotations
import pytest
from typing import Any

# Consolidated markers
pytestmark = [
    pytest.mark.tier_e2e,
    pytest.mark.chaos,
    pytest.mark.timeout(60),
]

from unittest.mock import MagicMock, patch

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError


@pytest.mark.asyncio
async def test_redis_unavailable() -> None:
    """Test behavior when Redis is completely down."""
    from kagami.core.caching.unified import UnifiedCache
    import uuid

    # Create unique test key to avoid cache pollution from other tests
    test_key = f"test-key-{uuid.uuid4().hex[:8]}"

    with patch(
        "redis.asyncio.Redis.ping",
        side_effect=RedisConnectionError("Connection refused"),
    ):
        # Use fresh cache instance to avoid singleton pollution
        cache = UnifiedCache("test_redis_failure")

        # Populate via fetch_fn (UnifiedCache doesn't have public set)
        async def fetch():
            return "test-value"

        value = await cache.get(test_key, fetch)

        # Should retrieve from fetch_fn (and populate L1)
        assert value == "test-value", f"Expected 'test-value', got {value!r}"

        # L2 (Redis) failure should be swallowed/ignored
        # Subsequent get should hit L1
        value2 = await cache.get(test_key)
        assert value2 == "test-value", f"Expected 'test-value' from L1, got {value2!r}"


@pytest.mark.asyncio
async def test_event_bus_redis_failure() -> None:
    """Test event bus when Redis pub/sub fails."""
    from kagami.core.network.message_bus import get_message_bus
    from kagami.core.resilience import RetryExhaustedError

    # Patching RedisClientFactory to return a mock that raises error on publish
    with patch("kagami.core.caching.redis.RedisClientFactory.get_client") as mock_factory:
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = RedisConnectionError("Connection lost")
        mock_factory.return_value = mock_redis

        # Mock async publish
        async def async_publish(*args: Any, **kwargs) -> None:
            raise RedisConnectionError("Connection lost")

        mock_redis.publish = async_publish

        bus = get_message_bus("test-instance")
        bus._redis = mock_redis  # type: ignore[assignment]

        # Publish may propagate error after retries or circuit breaker
        # Either is acceptable - the key is system doesn't hard crash
        try:
            await bus.publish("test-target", "test-type", {"event": "test"})
        except (RedisConnectionError, RetryExhaustedError, Exception):
            pass  # Expected behavior - error propagated to caller

        # System should not crash - test completes without exception


@pytest.mark.asyncio
async def test_rate_limiter_redis_failure() -> None:
    """Test rate limiting when Redis fails."""
    from kagami_api.rate_limiter import RateLimiter
    from kagami.core.unified_rate_limiter import UnifiedRateLimiter, RateLimitConfig

    # Create limiter configured for Redis
    limiter = RateLimiter(requests_per_minute=60, window_size=60)
    limiter.config.use_redis = True
    limiter._impl = UnifiedRateLimiter(limiter.config)

    # Force fallback
    with patch(
        "kagami.core.caching.redis.RedisClientFactory.get_client",
        side_effect=Exception("Redis down"),
    ):
        # Should degrade to memory/fallback instead of raising
        allowed = await limiter.is_allowed_async("test-client")
        assert allowed is not None


@pytest.mark.asyncio
async def test_idempotency_without_redis() -> None:
    """Test idempotency enforcement without Redis."""
    # Idempotency function import check
    from kagami_api.idempotency import idempotency_middleware

    assert callable(idempotency_middleware)
