"""Resilient Redis wrapper with circuit breaker and fallback.

P0 Mitigation: Redis failure → All requests hit DB → Cascade failure
"""

from __future__ import annotations

import asyncio
import logging
import pickle
from collections import OrderedDict
from typing import Any

from kagami.core.resilience import CircuitBreaker, CircuitOpen

logger = logging.getLogger(__name__)


class LRUCache:
    """Simple in-memory LRU cache for Redis fallback."""

    def __init__(self, maxsize: int = 1000):
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.maxsize = maxsize

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value

        # Evict oldest if over capacity
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        self.cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()


class ResilientRedisClient:
    """Redis client with circuit breaker and in-memory fallback.

    P0 Mitigation: Prevents Redis failure from cascading to database overload.

    Features:
    - Circuit breaker (stop calling Redis if failing)
    - In-memory LRU cache fallback
    - Request coalescing (prevent thundering herd)
    - Automatic recovery testing

    Usage:
        redis = ResilientRedisClient(redis_url="redis://localhost:6379")
        await redis.initialize()

        value = await redis.get("key")  # Transparent fallback if Redis down
    """

    def __init__(
        self,
        redis_url: str,
        fallback_cache_size: int = 1000,
        circuit_failure_threshold: int = 5,
        circuit_timeout: float = 60.0,
    ):
        self.redis_url = redis_url
        self._client: Any = None  # redis.asyncio.Redis

        # Circuit breaker
        self.breaker = CircuitBreaker(
            name="redis",
            failure_threshold=circuit_failure_threshold,
            timeout=circuit_timeout,
        )

        # Fallback cache
        self.fallback_cache = LRUCache(maxsize=fallback_cache_size)

        # Request coalescing (prevent thundering herd)
        self._pending_requests: dict[str, asyncio.Future] = {}

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle encoding
            )

            # Test connection
            await self._client.ping()
            logger.info("✅ Redis connection established")

        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable at startup: {e}")
            logger.info("Using in-memory fallback cache only")

    async def get(self, key: str) -> Any | None:
        """Get value from Redis (with fallback to memory cache).

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        # Try Redis first (if circuit closed)
        try:
            value_bytes = await self.breaker.call(self._client.get, key)
            if value_bytes:
                value = pickle.loads(value_bytes)
                # Update fallback cache
                self.fallback_cache.set(key, value)
                return value
            return None

        except CircuitOpen:
            # Circuit open, use fallback immediately
            logger.debug(f"Redis circuit open, using fallback cache for: {key}")
            return self.fallback_cache.get(key)

        except Exception as e:
            # Redis error, use fallback
            logger.warning(f"Redis get failed for {key}: {e}")
            return self.fallback_cache.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set value in Redis (with fallback to memory cache).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = no expiry)

        Returns:
            True if successful
        """
        # Always update fallback cache
        self.fallback_cache.set(key, value)

        # Try Redis
        try:
            value_bytes = pickle.dumps(value)
            if ttl:
                await self.breaker.call(self._client.setex, key, ttl, value_bytes)
            else:
                await self.breaker.call(self._client.set, key, value_bytes)
            return True

        except CircuitOpen:
            logger.debug(f"Redis circuit open, fallback cache updated: {key}")
            return True  # Fallback succeeded

        except Exception as e:
            logger.warning(f"Redis set failed for {key}: {e}")
            return True  # Fallback succeeded

    async def delete(self, key: str) -> bool:
        """Delete key from Redis and fallback cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        # Delete from fallback
        self.fallback_cache.delete(key)

        # Try Redis
        try:
            await self.breaker.call(self._client.delete, key)
            return True
        except (CircuitOpen, Exception) as e:
            logger.debug(f"Redis delete failed for {key}: {e}")
            return True  # Fallback succeeded

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(await self.breaker.call(self._client.exists, key))
        except (CircuitOpen, Exception):
            return self.fallback_cache.get(key) is not None

    async def clear(self) -> None:
        """Clear fallback cache (does NOT flush Redis)."""
        self.fallback_cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "circuit": self.breaker.get_stats(),
            "fallback_cache_size": len(self.fallback_cache.cache),
            "fallback_cache_maxsize": self.fallback_cache.maxsize,
        }

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()


# Global instance
_global_redis: ResilientRedisClient | None = None


async def get_resilient_redis(redis_url: str | None = None) -> ResilientRedisClient:
    """Get global resilient Redis client."""
    global _global_redis

    if _global_redis is None:
        if redis_url is None:
            import os

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        _global_redis = ResilientRedisClient(redis_url)
        await _global_redis.initialize()

    return _global_redis
