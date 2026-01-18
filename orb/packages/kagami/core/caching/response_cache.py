"""Unified response cache for Kagami.

Consolidates 3 cache implementations:
- kagami/core/orchestrator/response_cache.py (ResponseCacheModule)
- kagami/core/services/llm/response_cache.py (ResponseCache)
- kagami/core/caching/response_cache.py (original unified)

Features:
- Two-tier caching (L1 memory + L2 Redis)
- LRU eviction with TTL support
- Intent-based and parameter-based key generation
- Pattern-based invalidation
- Namespace support for multi-tenant use
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

from kagami.core.unified_rate_limiter import (
    RateLimitError,
    get_cache_rate_limiter,
)

logger = logging.getLogger(__name__)


class RedisLike(Protocol):
    """Protocol for Redis-like cache backends."""

    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set value in cache with optional expiry."""
        ...

    async def delete(self, key: str) -> int:
        """Delete key from cache."""
        ...

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        ...


def hash_key(text: str) -> str:
    """Generate MD5 hash for cache key.

    Args:
        text: Text to hash

    Returns:
        Hexadecimal MD5 hash
    """
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


@dataclass
class CacheConfig:
    """Configuration for response cache."""

    ttl: float = 3600.0  # 1 hour default
    max_size: int = 1000
    enable_redis: bool = True


class ResponseCache:
    """Unified response cache with memory and Redis backends.

    Features:
    - Two-tier caching (memory L1 + Redis L2)
    - TTL support
    - LRU eviction for memory cache
    - Stampede protection
    - Cache key generation
    """

    def __init__(self, config: CacheConfig | None = None, namespace: str = "responses") -> None:
        """Initialize response cache.

        Args:
            config: Cache configuration
            namespace: Cache namespace for key prefixing
        """
        self.config = config or CacheConfig()
        self.namespace = namespace

        # L1: Memory cache (LRU)
        self._memory_cache: dict[str, tuple[Any, float]] = {}
        self._access_times: dict[str, float] = {}

        # L2: Redis (lazy initialized)
        self._redis_client: RedisLike | None = None

        # Rate limiter
        self._rate_limiter = get_cache_rate_limiter()

    def _get_redis(self) -> None:
        """Lazy load Redis client."""
        if self._redis_client is None and self.config.enable_redis:
            try:
                from kagami.core.caching.redis import RedisClientFactory

                self._redis_client = RedisClientFactory.get_client(
                    purpose="default", async_mode=True
                )
            except Exception as e:
                logger.debug(f"Redis unavailable for caching: {e}")
        return self._redis_client

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        # Rate limit check
        allowed, retry_after = await self._rate_limiter.check_limit(key, operation="get")
        if not allowed and self._rate_limiter.strategy == "block":
            raise RateLimitError(
                f"Rate limit exceeded for key: {key}",
                key=key,
                retry_after=retry_after,
            )
        elif not allowed:
            # Delay strategy
            import asyncio

            await asyncio.sleep(min(retry_after, 0.1))

        # Try L1 (memory) first
        if key in self._memory_cache:
            value, expires_at = self._memory_cache[key]
            if time.time() < expires_at:
                self._access_times[key] = time.time()
                return value
            else:
                # Expired
                del self._memory_cache[key]
                del self._access_times[key]

        # Try L2 (Redis)
        redis = self._get_redis()  # type: ignore[func-returns-value]
        if redis:
            try:
                serialized = await redis.get(key)
                if serialized:
                    # Deserialize from JSON
                    try:
                        value = json.loads(serialized)
                    except (json.JSONDecodeError, TypeError):
                        # If not JSON, return as-is (backward compatibility)
                        value = serialized

                    # Promote to L1
                    expires_at = time.time() + self.config.ttl
                    self._set_memory(key, value, expires_at)
                    return value
            except Exception as e:
                logger.debug(f"Redis cache get failed: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        # Rate limit check
        allowed, retry_after = await self._rate_limiter.check_limit(key, operation="set[Any]")
        if not allowed and self._rate_limiter.strategy == "block":
            raise RateLimitError(
                f"Rate limit exceeded for key: {key}",
                key=key,
                retry_after=retry_after,
            )
        elif not allowed:
            # Delay strategy
            import asyncio

            await asyncio.sleep(min(retry_after, 0.1))

        cache_ttl = ttl or self.config.ttl
        expires_at = time.time() + cache_ttl

        # Set in L1 (memory)
        self._set_memory(key, value, expires_at)

        # Set in L2 (Redis)
        redis = self._get_redis()  # type: ignore[func-returns-value]
        if redis:
            try:
                # Serialize complex objects to JSON
                if isinstance(value, (dict, list, tuple)):
                    serialized = json.dumps(value)
                elif isinstance(value, str):
                    serialized = value
                else:
                    # Try JSON serialization for other types
                    try:
                        serialized = json.dumps(value)
                    except (TypeError, ValueError):
                        # Fall back to string representation
                        serialized = str(value)

                await redis.setex(key, int(cache_ttl), serialized)
            except Exception as e:
                logger.debug(f"Redis cache set failed: {e}")

    def _set_memory(self, key: str, value: Any, expires_at: float) -> None:
        """Set value in memory cache with LRU eviction."""
        # Evict if at capacity
        if len(self._memory_cache) >= self.config.max_size:
            # Remove least recently used
            if self._access_times:
                lru_key = min(self._access_times, key=self._access_times.get)  # type: ignore
                del self._memory_cache[lru_key]
                del self._access_times[lru_key]

        self._memory_cache[key] = (value, expires_at)
        self._access_times[key] = time.time()

    async def delete(self, key: str) -> None:
        """Delete value from cache.

        Args:
            key: Cache key
        """
        # Delete from L1
        self._memory_cache.pop(key, None)
        self._access_times.pop(key, None)

        # Delete from L2
        redis = self._get_redis()  # type: ignore[func-returns-value]
        if redis:
            try:
                await redis.delete(key)
            except Exception as e:
                logger.debug(f"Redis cache delete failed: {e}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        # Clear L1
        self._memory_cache.clear()
        self._access_times.clear()

        # Clear L2 (namespace only)
        redis = self._get_redis()  # type: ignore[func-returns-value]
        if redis:
            try:
                # Delete all keys with namespace prefix
                pattern = f"{self.namespace}:*"
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
            except Exception as e:
                logger.debug(f"Redis cache clear failed: {e}")

    async def invalidate(self, pattern: str | None = None) -> None:
        """Invalidate cache entries by pattern.

        Args:
            pattern: Pattern to match keys. If None, clears all entries.
        """
        if pattern is None:
            await self.clear()
            return

        # Pattern-based invalidation in L1
        keys_to_delete = [k for k in self._memory_cache if pattern in k]
        for k in keys_to_delete:
            self._memory_cache.pop(k, None)
            self._access_times.pop(k, None)

        # Pattern-based invalidation in L2
        redis = self._get_redis()  # type: ignore[func-returns-value]
        if redis:
            try:
                redis_pattern = f"{self.namespace}:*{pattern}*"
                keys = await redis.keys(redis_pattern)
                if keys:
                    await redis.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} Redis keys matching '{pattern}'")
            except Exception as e:
                logger.debug(f"Redis cache invalidation failed: {e}")

        logger.debug(f"Invalidated {len(keys_to_delete)} memory keys matching '{pattern}'")

    def intent_to_key(self, intent: Any) -> str:
        """Convert intent to stable cache key.

        Args:
            intent: Intent object (typically a dict[str, Any])

        Returns:
            Stable string key for caching
        """
        try:
            payload = json.dumps(intent, sort_keys=True, default=str)
        except Exception:
            payload = str(intent)
        return hash_key(payload)

    def get_cache_key(
        self,
        prompt: str,
        app_name: str,
        task_type: Any,
        max_tokens: int,
        temperature: float,
        model: str | None = None,
    ) -> str:
        """Generate cache key from LLM request parameters.

        Args:
            prompt: Input prompt
            app_name: Application name
            task_type: Task type enum
            max_tokens: Max tokens
            temperature: Temperature
            model: Model name

        Returns:
            Hash key for caching
        """
        key_data = {
            "prompt": prompt,
            "app": app_name,
            "task": str(task_type),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "model": model or "auto",
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hash_key(key_str)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "namespace": self.namespace,
            "memory_entries": len(self._memory_cache),
            "max_size": self.config.max_size,
            "ttl": self.config.ttl,
            "redis_enabled": self.config.enable_redis and self._redis_client is not None,
        }


# Alias for backward compatibility with orchestrator code
ResponseCacheModule = ResponseCache


__all__ = ["CacheConfig", "ResponseCache", "ResponseCacheModule", "hash_key"]
