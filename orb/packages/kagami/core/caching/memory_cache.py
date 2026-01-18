"""In-memory cache with LRU eviction and TTL support.

Consolidation (Dec 26, 2025): Moved from kagami/forge/utils/cache.py
to provide unified caching across the codebase.

Features:
- LRU eviction when max_size reached
- TTL-based expiration
- Both sync and async interfaces
- Cache statistics tracking
- Dict-style access (cache[key] = value)
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any

# Sentinel for cache misses vs cached None values
_MISSING = object()


def _generate_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Generate a cache key from arguments."""
    key_parts = [prefix]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()


class MemoryCache:
    """Simple in-memory cache with LRU eviction and TTL support.

    Thread-safe for single-threaded async usage. For multi-threaded
    usage, external synchronization is required.

    Uses OrderedDict for O(1) LRU operations instead of O(n) list operations.

    Example:
        cache = MemoryCache(name="my_cache", max_size=100, default_ttl=3600)
        await cache.set("key", "value")
        value = await cache.get("key")
    """

    def __init__(
        self,
        name: str | None = None,
        max_size: int = 1000,
        default_ttl: float | None = None,
    ) -> None:
        """Initialize memory cache with size limit.

        Args:
            name: Name of the cache (for stats/debugging)
            max_size: Maximum number of items in cache
            default_ttl: Default time to live for cache entries in seconds
        """
        self.name = name or "default"
        # OrderedDict maintains insertion order and provides O(1) move_to_end
        self.cache: OrderedDict[str, tuple[Any, float | None]] = OrderedDict()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    # -------------------------------------------------------------------------
    # Async interface (primary)
    # -------------------------------------------------------------------------

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache (async version for compatibility)."""
        return self.get_sync(key, default)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        """Set value in cache with LRU eviction (async version)."""
        self.set_sync(key, value, ttl)
        return True

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache (async version)."""
        return bool(self.exists_sync(key))

    async def delete(self, key: str) -> bool:
        """Delete key from cache (async version)."""
        return bool(self.delete_sync(key))

    async def clear(self) -> bool:
        """Clear all cache entries (async version)."""
        self.clear_sync()
        return True

    # -------------------------------------------------------------------------
    # Sync interface
    # -------------------------------------------------------------------------

    def get_sync(self, key: str, default: Any = None) -> Any:
        """Get value from cache synchronously."""
        if key in self.cache:
            value, expiry = self.cache[key]
            # Check TTL expiry
            if expiry is not None and time.time() > expiry:
                del self.cache[key]
                self.misses += 1
                return default

            # Update LRU order - O(1) with OrderedDict.move_to_end()
            self.cache.move_to_end(key)

            self.hits += 1
            return value
        self.misses += 1
        return default

    def set_sync(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set value in cache with LRU eviction synchronously."""
        # Use provided TTL or default
        ttl_to_use = self.default_ttl if ttl is None else ttl

        # Non-positive TTL means don't cache / expire immediately
        if ttl_to_use is not None and ttl_to_use <= 0:
            if key in self.cache:
                del self.cache[key]
            return

        expiry = time.time() + ttl_to_use if ttl_to_use is not None else None

        # Handle zero max_size - don't store anything
        if self.max_size <= 0:
            return

        # LRU eviction: remove least recently used (first item in OrderedDict)
        if len(self.cache) >= self.max_size and key not in self.cache:
            # popitem(last=False) removes FIFO order (oldest/LRU first) - O(1)
            if self.cache:  # Only pop if cache is non-empty
                self.cache.popitem(last=False)
                self.evictions += 1

        # Set value and move to end (most recently used) - O(1)
        self.cache[key] = (value, expiry)
        self.cache.move_to_end(key)

    def exists_sync(self, key: str) -> bool:
        """Check if key exists in cache synchronously."""
        if key in self.cache:
            _, expiry = self.cache[key]
            if expiry is not None and time.time() > expiry:
                del self.cache[key]
                return False
            return True
        return False

    def delete_sync(self, key: str) -> bool:
        """Delete key from cache synchronously."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear_sync(self) -> None:
        """Clear all cache entries synchronously."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    # -------------------------------------------------------------------------
    # Dict-style access (for compatibility)
    # -------------------------------------------------------------------------

    def __contains__(self, key: object) -> bool:
        try:
            return self.exists_sync(str(key))
        except Exception:
            return False

    def __getitem__(self, key: str) -> Any:
        value = self.get_sync(key, default=_MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self.set_sync(key, value)

    def __delitem__(self, key: str) -> None:
        if not self.delete_sync(key):
            raise KeyError(key)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = float(self.hits) / float(total_requests) if total_requests > 0 else 0.0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": hit_rate,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics with memory usage (alias for tests)."""
        memory_usage_bytes = sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.cache.items())
        memory_usage_mb = memory_usage_bytes / (1024 * 1024)

        return {
            "type": "memory",
            "size": len(self.cache),
            "max_size": self.max_size,
            "memory_usage_mb": memory_usage_mb,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
        }


class CacheManager:
    """Centralized cache manager for named caches.

    Provides a registry of named caches with a shared default TTL and size.

    Example:
        manager = CacheManager()
        cache = manager.get_cache("my_feature")
        cache.set_sync("key", "value")
    """

    def __init__(self) -> None:
        """Initialize cache manager."""
        self.caches: dict[str, MemoryCache] = {}
        self.default_ttl = 3600  # 1 hour default TTL
        self.default_max_size = 1000
        self.backend = MemoryCache(
            name="default", max_size=self.default_max_size, default_ttl=self.default_ttl
        )
        self._default_cache: MemoryCache = self.backend
        self.caches["default"] = self._default_cache

    def get_cache(self, cache_name: str) -> MemoryCache:
        """Get or create a named cache."""
        if cache_name not in self.caches:
            self.caches[cache_name] = MemoryCache(
                name=cache_name,
                max_size=self.default_max_size,
                default_ttl=self.default_ttl,
            )
        return self.caches[cache_name]

    def get_value(self, cache_name: str, key: str, default: Any = None) -> Any:
        """Get value from a specific named cache synchronously."""
        cache = self.get_cache(cache_name)
        return cache.get_sync(key, default)

    def set_value(self, cache_name: str, key: str, value: Any, ttl: float | None = None) -> None:
        """Set value in a specific named cache synchronously."""
        cache = self.get_cache(cache_name)
        cache.set_sync(key, value, ttl)

    def clear(self, cache_name: str | None = None) -> None:
        """Clear specific cache or all caches."""
        if cache_name:
            if cache_name == "default":
                self._default_cache.clear_sync()
            cache = self.caches.get(cache_name)
            if cache is not None:
                cache.clear_sync()
            return

        # Clear all caches, deduplicating instances
        seen: set[int] = set()
        for cache in [self._default_cache, *self.caches.values()]:
            cache_id = id(cache)
            if cache_id in seen:
                continue
            seen.add(cache_id)
            cache.clear_sync()

    def stats(self, cache_name: str | None = None) -> dict[str, Any]:
        """Get cache statistics."""
        if cache_name:
            cache = self.get_cache(cache_name)
            return cache.stats()

        return {name: cache.stats() for name, cache in self.caches.items()}

    # Async methods for default cache
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from default cache (async)."""
        return await self._default_cache.get(key, default)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        """Set value in default cache (async)."""
        return await self._default_cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete key from default cache (async)."""
        return await self._default_cache.delete(key)

    def cached(self, cache_name: str, ttl: float | None = None) -> Callable[[Callable], Callable]:
        """Decorator to cache function results."""

        def decorator(func: Callable) -> Callable:
            cache = self.get_cache(cache_name)

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _generate_cache_key(func.__name__, *args, **kwargs)
                cached_value = await cache.get(key, default=_MISSING)
                if cached_value is not _MISSING:
                    return cached_value
                result = await func(*args, **kwargs)
                await cache.set(key, result, ttl)
                return result

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _generate_cache_key(func.__name__, *args, **kwargs)
                cached_value = cache.get_sync(key, default=_MISSING)
                if cached_value is not _MISSING:
                    return cached_value
                result = func(*args, **kwargs)
                cache.set_sync(key, result, ttl)
                return result

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator


__all__ = ["_MISSING", "CacheManager", "MemoryCache", "_generate_cache_key"]
