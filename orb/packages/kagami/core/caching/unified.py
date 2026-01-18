from __future__ import annotations

"""Unified cache facade for K os.

Presents a single interface while selecting the appropriate backend tier:
 - L1: In‑process LRU (via MemoryCache)
 - L2: Redis (if available)
 - L3: DB (optional, not used in fast paths)
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Protocol

from kagami_observability.metrics import (
    CACHE_HITS_TOTAL,
    CACHE_MISSES_TOTAL,
)
from kagami_observability.metrics.infrastructure import CACHE_STAMPEDE_PREVENTED_TOTAL

from kagami.core.caching.memory_cache import MemoryCache
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

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        ...


class UnifiedCache:
    def __init__(self, namespace: str = "kagami") -> None:
        self.ns = namespace
        # L1: In-process LRU cache (no TTL for fast access)
        self._l1 = MemoryCache(name="unified_l1", max_size=1024, default_ttl=None)
        self._redis: RedisLike | None = None
        self._init_lock = asyncio.Lock()
        self._rate_limiter = get_cache_rate_limiter()
        # Stampede protection: per-key locks
        self._fetch_locks: dict[str, asyncio.Lock] = {}
        self._fetch_lock_cleanup: asyncio.Lock = asyncio.Lock()

    async def _ensure_redis(self) -> None:
        if self._redis is not None:
            return  # type: ignore  # Defensive/fallback code
        async with self._init_lock:
            if self._redis is not None:
                return  # type: ignore  # Defensive/fallback code
            try:
                from kagami.core.caching.redis import RedisClientFactory

                self._redis = RedisClientFactory.get_client(
                    purpose="default",
                    async_mode=True,
                    decode_responses=True,
                )
            except Exception:
                self._redis = None

    def _k(self, key: str) -> str:
        return f"{self.ns}:{key}"

    async def get(self, key: str, fetch_fn: Callable[[], Any] | None = None) -> Any:
        """Get value with stampede protection.

        Args:
            key: Cache key
            fetch_fn: Optional function to fetch value on cache miss

        Returns:
            Cached or fetched value, or None if not found and no fetch_fn

        Raises:
            RateLimitError: If rate limit exceeded with block strategy
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
            await asyncio.sleep(min(retry_after, 0.1))

        k = self._k(key)

        # L1 cache check
        v = self._l1.get_sync(k)
        if v is not None:
            try:
                CACHE_HITS_TOTAL.labels("l1").inc()
            except Exception:
                pass
            return v

        # L2 cache check
        await self._ensure_redis()
        if self._redis is not None:
            try:  # type: ignore  # Defensive/fallback code
                raw = await self._redis.get(k)
                if raw is not None:
                    self._l1.set_sync(k, raw)
                    CACHE_HITS_TOTAL.labels("l2").inc()
                    return raw
            except Exception:
                pass

        # Cache miss - check if fetch_fn provided
        if fetch_fn is None:
            try:
                CACHE_MISSES_TOTAL.labels("unified").inc()
            except Exception:
                pass
            return None

        # Stampede protection: get or create lock for this key
        async with self._fetch_lock_cleanup:
            if k not in self._fetch_locks:
                self._fetch_locks[k] = asyncio.Lock()
            lock = self._fetch_locks[k]

        # Only one task per key executes fetch_fn
        async with lock:
            # Double-check cache after acquiring lock
            # (another task may have populated it while we waited)
            v = self._l1.get_sync(k)
            if v is not None:
                # Stampede prevented - another task populated cache
                try:
                    CACHE_STAMPEDE_PREVENTED_TOTAL.labels("l1").inc()
                except Exception:
                    pass
                return v

            # Check L2 again (might have been populated)
            if self._redis is not None:
                try:  # type: ignore  # Defensive/fallback code
                    raw = await self._redis.get(k)
                    if raw is not None:
                        self._l1.set_sync(k, raw)
                        try:
                            CACHE_STAMPEDE_PREVENTED_TOTAL.labels("l2").inc()
                        except Exception:
                            pass
                        return raw
                except Exception:
                    pass

            # Actually fetch (only one task reaches here per key)
            try:
                val = fetch_fn()
                if asyncio.iscoroutine(val):
                    val = await val

                # Populate caches
                self._l1.set_sync(k, val)
                if self._redis is not None:
                    try:  # type: ignore  # Defensive/fallback code
                        await self._redis.set(k, val)
                    except Exception:
                        pass

                try:
                    CACHE_MISSES_TOTAL.labels("unified").inc()
                except Exception:
                    pass

                # Schedule lock cleanup (after 1 second)
                asyncio.create_task(self._cleanup_fetch_lock(k))

                return val

            except Exception as e:
                logger.error(f"Fetch function failed for key {k}: {e}")
                # Schedule lock cleanup even on error
                asyncio.create_task(self._cleanup_fetch_lock(k))
                raise

    async def _cleanup_fetch_lock(self, key: str) -> None:
        """Remove fetch lock after short delay.

        Args:
            key: Namespaced cache key
        """
        await asyncio.sleep(1.0)  # Keep lock for 1s to coalesce requests
        async with self._fetch_lock_cleanup:
            self._fetch_locks.pop(key, None)


_singleton: UnifiedCache | None = None


def get_cache(namespace: str = "kagami") -> UnifiedCache:
    global _singleton
    if _singleton is None:
        _singleton = UnifiedCache(namespace)
    return _singleton


# Alias for backwards compatibility
get_unified_cache = get_cache
