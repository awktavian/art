# pyright: reportGeneralTypeIssues=false
"""Cached Repository Pattern — Eliminate Repository Caching Duplication.

CONSOLIDATES: 7 repositories with similar L1/L2 caching logic
REDUCES: ~35KB → ~25KB caching boilerplate
PROVIDES: Decorator pattern for cache strategies

All repositories reimplement similar caching logic:
- ColonyRepository
- ReceiptRepository
- TrainingRepository
- WorldModelRepository
- SafetyRepository
- UserRepository
- KnowledgeRepository

This generic wrapper eliminates the duplication.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

from kagami.core.caching import MemoryCache, UnifiedCache

# Avoid circular import - define Protocol inline instead of importing
if TYPE_CHECKING:
    from kagami.core.storage.protocols import Repository
else:
    # Runtime Protocol for Repository interface
    class Repository(Protocol):
        """Minimal Repository protocol to avoid circular import."""

        async def get(self, id: str) -> Any: ...

        async def save(self, entity: Any) -> None: ...


logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheStrategy(Enum):
    """Cache strategies for repository operations."""

    NONE = "none"  # No caching
    READ_THROUGH = "read_through"  # Cache on read, direct write
    WRITE_THROUGH = "write_through"  # Cache on read, write to cache+storage
    WRITE_BEHIND = "write_behind"  # Cache on read, async write to storage
    WRITE_AROUND = "write_around"  # Direct storage, cache on read
    REFRESH_AHEAD = "refresh_ahead"  # Proactive cache refresh before expiry


@dataclass
class RepositoryCache:
    """Cache configuration for repository operations."""

    # L1 Cache (Memory)
    l1_size: int = 1000
    l1_ttl_seconds: int = 300  # 5 minutes

    # L2 Cache (Redis)
    l2_enabled: bool = True
    l2_ttl_seconds: int = 3600  # 1 hour

    # Strategies
    read_strategy: CacheStrategy = CacheStrategy.READ_THROUGH
    write_strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH

    # Performance
    batch_size: int = 100
    max_concurrent: int = 10


class CachedRepository(Generic[T]):
    """Generic caching wrapper for repositories.

    Wraps any Repository[T] with configurable L1/L2 caching strategies.
    Eliminates duplication across 7+ repository implementations.

    Usage:
        base_repo = ConcreteRepository()
        cached_repo = CachedRepository(
            base_repo,
            cache_config=RepositoryCache(l1_size=2000, l1_ttl_seconds=600)
        )

        # Use exactly like base repository
        item = await cached_repo.get("key")
        await cached_repo.set("key", item)
    """

    def __init__(
        self,
        base_repository: Repository[T],
        cache_config: RepositoryCache | None = None,
        cache_prefix: str = "repo",
    ) -> None:
        self._base = base_repository
        self.config = cache_config or RepositoryCache()
        self.cache_prefix = cache_prefix

        # L1 Cache (Memory)
        self._l1_cache = MemoryCache(
            name=f"{cache_prefix}_l1",
            max_size=self.config.l1_size,
            default_ttl=float(self.config.l1_ttl_seconds),
        )

        # L2 Cache (Redis) - Unified cache handles Redis fallback
        if self.config.l2_enabled:
            self._l2_cache = UnifiedCache(
                memory_cache=self._l1_cache,
                redis_ttl=self.config.l2_ttl_seconds,
                redis_prefix=f"{cache_prefix}_l2",
            )
        else:
            self._l2_cache = None

        # Metrics
        self._read_hits = 0
        self._read_misses = 0
        self._write_count = 0

        logger.debug(
            f"CachedRepository created: {cache_prefix} "
            f"(L1: {self.config.l1_size}, L2: {self.config.l2_enabled})"
        )

    def _cache_key(self, key: str) -> str:
        """Generate cache key."""
        return f"{self.cache_prefix}:{key}"

    def _get_cache(self) -> MemoryCache | UnifiedCache:
        """Get appropriate cache instance."""
        return self._l2_cache if self._l2_cache else self._l1_cache

    # =========================================================================
    # REPOSITORY INTERFACE IMPLEMENTATION
    # =========================================================================

    async def get(self, key: str) -> T | None:
        """Get item with caching."""
        cache_key = self._cache_key(key)
        cache = self._get_cache()

        if self.config.read_strategy == CacheStrategy.READ_THROUGH:
            # Try cache first
            cached = cache.get(cache_key)
            if cached is not None:
                self._read_hits += 1
                return cached

        # Cache miss - get from base repository
        self._read_misses += 1
        item = await self._base.get(key)

        # Cache the result
        if item is not None and self.config.read_strategy != CacheStrategy.NONE:
            cache.set(cache_key, item)

        return item

    async def set(self, key: str, item: T) -> bool:
        """Set item with caching."""
        cache_key = self._cache_key(key)
        cache = self._get_cache()
        self._write_count += 1

        strategy = self.config.write_strategy

        if strategy == CacheStrategy.WRITE_THROUGH:
            # Write to both cache and storage
            result = await self._base.set(key, item)
            if result:
                cache.set(cache_key, item)
            return result

        elif strategy == CacheStrategy.WRITE_BEHIND:
            # Write to cache immediately, storage asynchronously
            cache.set(cache_key, item)
            asyncio.create_task(self._base.set(key, item))
            return True

        elif strategy == CacheStrategy.WRITE_AROUND:
            # Write directly to storage, invalidate cache
            result = await self._base.set(key, item)
            cache.delete(cache_key)
            return result

        else:  # CacheStrategy.NONE
            # Direct write to storage
            return await self._base.set(key, item)

    async def delete(self, key: str) -> bool:
        """Delete item with cache invalidation."""
        cache_key = self._cache_key(key)
        cache = self._get_cache()

        # Delete from storage
        result = await self._base.delete(key)

        # Invalidate cache
        cache.delete(cache_key)

        return result

    async def exists(self, key: str) -> bool:
        """Check existence with caching."""
        cache_key = self._cache_key(key)
        cache = self._get_cache()

        # Check cache first for existence
        if cache.get(cache_key) is not None:
            return True

        # Check base repository
        exists = await self._base.exists(key)

        # Note: We don't cache negative existence results
        # to avoid cache invalidation complexity

        return exists

    async def list_keys(self, prefix: str = "") -> list[str]:
        """List keys (bypass cache for consistency)."""
        # Key listing bypasses cache for consistency
        return await self._base.list_keys(prefix)

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    async def get_many(self, keys: list[str]) -> dict[str, T]:
        """Get multiple items with batch caching."""
        cache = self._get_cache()
        result = {}
        uncached_keys = []

        # Check cache for each key
        for key in keys:
            cache_key = self._cache_key(key)
            cached = cache.get(cache_key)
            if cached is not None:
                result[key] = cached
                self._read_hits += 1
            else:
                uncached_keys.append(key)
                self._read_misses += 1

        # Batch fetch uncached keys
        if uncached_keys:
            # Use base repository batch operation if available
            if hasattr(self._base, "get_many"):
                batch_result = await self._base.get_many(uncached_keys)
            else:
                # Fallback to individual gets with concurrency limit
                batch_result = {}
                semaphore = asyncio.Semaphore(self.config.max_concurrent)

                async def get_with_semaphore(k):
                    async with semaphore:
                        return await self._base.get(k)

                tasks = [get_with_semaphore(k) for k in uncached_keys]
                values = await asyncio.gather(*tasks, return_exceptions=True)

                for key, value in zip(uncached_keys, values, strict=False):
                    if not isinstance(value, Exception) and value is not None:
                        batch_result[key] = value

            # Cache the results
            for key, value in batch_result.items():
                cache_key = self._cache_key(key)
                cache.set(cache_key, value)

            result.update(batch_result)

        return result

    async def set_many(self, items: dict[str, T]) -> dict[str, bool]:
        """Set multiple items with batch caching."""
        cache = self._get_cache()
        self._write_count += len(items)

        # Use base repository batch operation if available
        if hasattr(self._base, "set_many"):
            result = await self._base.set_many(items)
        else:
            # Fallback to individual sets with concurrency limit
            semaphore = asyncio.Semaphore(self.config.max_concurrent)

            async def set_with_semaphore(k, v):
                async with semaphore:
                    return await self._base.set(k, v)

            tasks = [set_with_semaphore(k, v) for k, v in items.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            result = {}
            for (key, _), success in zip(items.items(), results, strict=False):
                result[key] = not isinstance(success, Exception) and success

        # Update cache based on write strategy
        if self.config.write_strategy in [CacheStrategy.WRITE_THROUGH, CacheStrategy.WRITE_BEHIND]:
            for key, value in items.items():
                if result.get(key, False):  # Only cache successful writes
                    cache_key = self._cache_key(key)
                    cache.set(cache_key, value)

        return result

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    def invalidate_cache(self, key: str | None = None) -> None:
        """Invalidate cache entries."""
        cache = self._get_cache()

        if key is None:
            # Clear all cache
            cache.clear()
            logger.debug(f"Cleared all cache for {self.cache_prefix}")
        else:
            # Clear specific key
            cache_key = self._cache_key(key)
            cache.delete(cache_key)
            logger.debug(f"Invalidated cache key: {cache_key}")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        total_reads = self._read_hits + self._read_misses
        hit_rate = self._read_hits / total_reads if total_reads > 0 else 0.0

        cache = self._get_cache()
        cache_size = len(cache._cache) if hasattr(cache, "_cache") else 0

        return {
            "repository": self.cache_prefix,
            "cache_strategy": {
                "read": self.config.read_strategy.value,
                "write": self.config.write_strategy.value,
            },
            "performance": {
                "read_hits": self._read_hits,
                "read_misses": self._read_misses,
                "hit_rate": hit_rate,
                "write_count": self._write_count,
            },
            "cache": {
                "l1_size": cache_size,
                "l1_max": self.config.l1_size,
                "l2_enabled": self.config.l2_enabled,
            },
        }

    def refresh_cache(self, key: str) -> None:
        """Proactively refresh cache entry."""
        if self.config.read_strategy == CacheStrategy.REFRESH_AHEAD:
            # Schedule async refresh
            asyncio.create_task(self._refresh_key_async(key))

    async def _refresh_key_async(self, key: str) -> None:
        """Async cache refresh."""
        try:
            item = await self._base.get(key)
            if item is not None:
                cache_key = self._cache_key(key)
                cache = self._get_cache()
                cache.set(cache_key, item)
                logger.debug(f"Refreshed cache key: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to refresh cache key {key}: {e}")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def get_cached_repository(
    base_repository: Repository[T],
    cache_config: RepositoryCache | None = None,
    cache_prefix: str | None = None,
) -> CachedRepository[T]:
    """Create cached repository wrapper.

    Args:
        base_repository: Repository to wrap
        cache_config: Cache configuration
        cache_prefix: Cache key prefix (defaults to base class name)

    Returns:
        Cached repository wrapper
    """
    if cache_prefix is None:
        cache_prefix = base_repository.__class__.__name__.lower().replace("repository", "")

    return CachedRepository(base_repository, cache_config, cache_prefix)
