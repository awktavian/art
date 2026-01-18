"""Base Cache Infrastructure for K OS.

This module provides the foundation for all cache implementations:
- CacheProtocol: Abstract interface that all caches must implement
- BaseCacheConfig: Configuration dataclass with common options
- CacheStats: Unified statistics tracking
- Decorators: @cached, @async_cached for easy caching of functions

DESIGN PRINCIPLES:
==================
1. **Protocol-based**: All caches implement CacheProtocol for interoperability
2. **Async-first**: Primary interface is async, with sync wrappers
3. **Statistics**: All caches track hits/misses/evictions uniformly
4. **Thread-safe**: All implementations must be thread-safe
5. **TTL support**: All caches support time-to-live expiration

CACHE TAXONOMY:
===============
After analyzing 10+ cache implementations, we identified these patterns:

| Type              | Backend      | TTL  | LRU  | Semantic | Thread-Safe | Use Case                |
|-------------------|--------------|------|------|----------|-------------|-------------------------|
| MemoryCache       | dict         | Yes  | Yes  | No       | Yes         | General in-memory       |
| RedisCache        | Redis        | Yes  | No   | No       | Yes         | Distributed caching     |
| ResponseCache     | Memory+Redis | Yes  | Yes  | No       | Yes         | LLM responses           |
| SemanticCache     | Memory+Embed | Yes  | No   | Yes      | Yes         | Similarity matching     |
| E8Cache           | OrderedDict  | No   | Yes  | No       | Yes         | Tensor quantization     |
| SafetyCache       | OrderedDict  | Yes  | Yes  | No       | Yes         | Safety classifications  |
| SenseCache        | dict         | Yes  | No   | No       | No          | Sensory data TTL        |
| EarconCache       | dict         | No   | No   | No       | Yes         | Audio file preload      |
| ModelCache        | Disk+Memory  | No   | Yes  | No       | Yes         | ML model checkpoints    |

CONSOLIDATION STRATEGY:
=======================
1. Memory-only caches -> Use MemoryBackend (base.py)
2. Redis-backed caches -> Use RedisBackend (backends.py)
3. Composite caches -> Use CompositeBackend (L1 memory + L2 Redis)
4. Specialized caches -> Keep specialized but implement CacheProtocol

Created: January 11, 2026
Colony: Forge (e2) - Infrastructure
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, ParamSpec, Protocol, TypeVar, runtime_checkable

logger = logging.getLogger(__name__)

# Type variables for generic caching
T = TypeVar("T")
P = ParamSpec("P")
K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type

# Sentinel for cache misses vs cached None values
_MISSING = object()


class EvictionPolicy(str, Enum):
    """Cache eviction policy."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time-based only (no size limit)
    FIFO = "fifo"  # First In First Out


class CacheTier(str, Enum):
    """Cache tier for multi-level caching."""

    MEMORY = "memory"  # L1: In-memory (fastest)
    REDIS = "redis"  # L2: Redis (fast, shared)
    DISK = "disk"  # L3: Disk (persistent)


@dataclass
class CacheStats:
    """Unified cache statistics.

    All cache implementations should use this for consistency.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0

    # Timing stats (optional)
    total_get_time_ns: int = 0
    total_set_time_ns: int = 0

    # Memory tracking (optional)
    memory_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_get_time_us(self) -> float:
        """Average get time in microseconds."""
        total = self.hits + self.misses
        return (self.total_get_time_ns / total / 1000) if total > 0 else 0.0

    @property
    def avg_set_time_us(self) -> float:
        """Average set time in microseconds."""
        total = self.evictions + self.size  # Approximate total sets
        return (self.total_set_time_ns / total / 1000) if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "max_size": self.max_size,
            "hit_rate": round(self.hit_rate, 4),
            "avg_get_time_us": round(self.avg_get_time_us, 2),
            "avg_set_time_us": round(self.avg_set_time_us, 2),
            "memory_mb": round(self.memory_bytes / 1024 / 1024, 2),
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_get_time_ns = 0
        self.total_set_time_ns = 0


@dataclass
class BaseCacheConfig:
    """Base configuration for all cache implementations.

    Extend this for specialized cache configs.
    """

    # Size limits
    max_size: int = 1000
    max_memory_bytes: int | None = None  # None = no memory limit

    # TTL configuration
    default_ttl: float | None = 3600.0  # None = no expiration
    min_ttl: float = 0.0
    max_ttl: float = 86400.0  # 24 hours

    # Eviction policy
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU

    # Thread safety
    thread_safe: bool = True

    # Statistics
    enable_stats: bool = True

    # Namespace for key prefixing
    namespace: str = ""

    def validate(self) -> None:
        """Validate configuration."""
        if self.max_size < 0:
            raise ValueError("max_size must be non-negative")
        if self.default_ttl is not None and self.default_ttl < 0:
            raise ValueError("default_ttl must be non-negative")
        if self.min_ttl < 0:
            raise ValueError("min_ttl must be non-negative")
        if self.max_ttl < self.min_ttl:
            raise ValueError("max_ttl must be >= min_ttl")


@dataclass
class CacheEntry(Generic[V]):
    """A single cache entry with metadata."""

    value: V
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def age(self) -> float:
        """Get age in seconds."""
        return time.time() - self.created_at

    @property
    def ttl_remaining(self) -> float | None:
        """Get remaining TTL in seconds, or None if no expiration."""
        if self.expires_at is None:
            return None
        return max(0.0, self.expires_at - time.time())

    def touch(self) -> None:
        """Update access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1


# =============================================================================
# CACHE PROTOCOL
# =============================================================================


@runtime_checkable
class CacheProtocol(Protocol[K, V]):
    """Protocol defining the cache interface.

    All cache implementations should satisfy this protocol for interoperability.
    This enables type-safe polymorphism across different cache backends.

    Key design decisions:
    - Async-first: Primary interface is async for compatibility with Redis/network
    - Optional sync: Sync methods provided for convenience
    - Stats: All caches track statistics uniformly
    - Clear/invalidate: Both full clear and pattern-based invalidation
    """

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        ...

    async def get(self, key: K, default: V | None = None) -> V | None:
        """Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        ...

    async def set(self, key: K, value: V, ttl: float | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override (None = use default)
        """
        ...

    async def delete(self, key: K) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key existed and was deleted
        """
        ...

    async def exists(self, key: K) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        ...

    async def clear(self) -> None:
        """Clear all cache entries."""
        ...

    def get_sync(self, key: K, default: V | None = None) -> V | None:
        """Synchronous get (for use outside async context)."""
        ...

    def set_sync(self, key: K, value: V, ttl: float | None = None) -> None:
        """Synchronous set (for use outside async context)."""
        ...


class BaseCache(ABC, Generic[K, V]):
    """Abstract base class implementing common cache functionality.

    Extend this class for new cache implementations. Provides:
    - Thread-safe statistics tracking
    - Namespace-based key prefixing
    - Common utility methods

    Subclasses must implement:
    - _get_impl(key) -> CacheEntry | None
    - _set_impl(key, entry)
    - _delete_impl(key) -> bool
    - _clear_impl()
    - _exists_impl(key) -> bool
    """

    def __init__(self, config: BaseCacheConfig | None = None) -> None:
        """Initialize base cache.

        Args:
            config: Cache configuration (uses defaults if None)
        """
        self.config = config or BaseCacheConfig()
        self.config.validate()

        self._stats = CacheStats(max_size=self.config.max_size)
        self._stats_lock = threading.Lock() if self.config.thread_safe else None

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics (thread-safe copy)."""
        if self._stats_lock:
            with self._stats_lock:
                return CacheStats(
                    hits=self._stats.hits,
                    misses=self._stats.misses,
                    evictions=self._stats.evictions,
                    size=self._stats.size,
                    max_size=self._stats.max_size,
                    total_get_time_ns=self._stats.total_get_time_ns,
                    total_set_time_ns=self._stats.total_set_time_ns,
                    memory_bytes=self._stats.memory_bytes,
                )
        return self._stats

    def _make_key(self, key: K) -> str:
        """Create namespaced key string.

        Args:
            key: Original key

        Returns:
            Namespaced key string
        """
        key_str = str(key) if not isinstance(key, str) else key
        if self.config.namespace:
            return f"{self.config.namespace}:{key_str}"
        return key_str

    def _update_stats(
        self,
        hit: bool = False,
        miss: bool = False,
        eviction: bool = False,
        size_delta: int = 0,
    ) -> None:
        """Update statistics (thread-safe).

        Args:
            hit: Increment hit count
            miss: Increment miss count
            eviction: Increment eviction count
            size_delta: Change in cache size
        """
        if not self.config.enable_stats:
            return

        if self._stats_lock:
            with self._stats_lock:
                if hit:
                    self._stats.hits += 1
                if miss:
                    self._stats.misses += 1
                if eviction:
                    self._stats.evictions += 1
                self._stats.size += size_delta
        else:
            if hit:
                self._stats.hits += 1
            if miss:
                self._stats.misses += 1
            if eviction:
                self._stats.evictions += 1
            self._stats.size += size_delta

    # Abstract methods to implement
    @abstractmethod
    async def _get_impl(self, key: str) -> CacheEntry[V] | None:
        """Get cache entry (implementation)."""
        ...

    @abstractmethod
    async def _set_impl(self, key: str, entry: CacheEntry[V]) -> None:
        """Set cache entry (implementation)."""
        ...

    @abstractmethod
    async def _delete_impl(self, key: str) -> bool:
        """Delete cache entry (implementation)."""
        ...

    @abstractmethod
    async def _exists_impl(self, key: str) -> bool:
        """Check if key exists (implementation)."""
        ...

    @abstractmethod
    async def _clear_impl(self) -> None:
        """Clear all entries (implementation)."""
        ...

    # Public interface
    async def get(self, key: K, default: V | None = None) -> V | None:
        """Get value from cache."""
        start_ns = time.time_ns()

        internal_key = self._make_key(key)
        entry = await self._get_impl(internal_key)

        if entry is None or entry.is_expired:
            self._update_stats(miss=True)
            if self.config.enable_stats:
                self._stats.total_get_time_ns += time.time_ns() - start_ns
            return default

        entry.touch()
        self._update_stats(hit=True)

        if self.config.enable_stats:
            self._stats.total_get_time_ns += time.time_ns() - start_ns

        return entry.value

    async def set(self, key: K, value: V, ttl: float | None = None) -> None:
        """Set value in cache."""
        start_ns = time.time_ns()

        internal_key = self._make_key(key)

        # Calculate expiration
        effective_ttl = ttl if ttl is not None else self.config.default_ttl
        if effective_ttl is not None:
            # Clamp to configured bounds
            effective_ttl = max(self.config.min_ttl, min(effective_ttl, self.config.max_ttl))
            expires_at = time.time() + effective_ttl
        else:
            expires_at = None

        entry = CacheEntry(
            value=value,
            created_at=time.time(),
            expires_at=expires_at,
            access_count=0,
            last_accessed=time.time(),
        )

        await self._set_impl(internal_key, entry)

        if self.config.enable_stats:
            self._stats.total_set_time_ns += time.time_ns() - start_ns

    async def delete(self, key: K) -> bool:
        """Delete key from cache."""
        internal_key = self._make_key(key)
        deleted = await self._delete_impl(internal_key)
        if deleted:
            self._update_stats(size_delta=-1)
        return deleted

    async def exists(self, key: K) -> bool:
        """Check if key exists in cache."""
        internal_key = self._make_key(key)
        return await self._exists_impl(internal_key)

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._clear_impl()
        if self._stats_lock:
            with self._stats_lock:
                self._stats.size = 0
        else:
            self._stats.size = 0

    def get_sync(self, key: K, default: V | None = None) -> V | None:
        """Synchronous get (runs async in new event loop if needed)."""
        try:
            asyncio.get_running_loop()
            # Already in async context - create task
            future = asyncio.ensure_future(self.get(key, default))
            return asyncio.get_event_loop().run_until_complete(future)
        except RuntimeError:
            # No running loop - run synchronously
            return asyncio.run(self.get(key, default))

    def set_sync(self, key: K, value: V, ttl: float | None = None) -> None:
        """Synchronous set (runs async in new event loop if needed)."""
        try:
            asyncio.get_running_loop()
            # In async context - just schedule without awaiting
            asyncio.create_task(self.set(key, value, ttl))
        except RuntimeError:
            # No running loop - run synchronously
            asyncio.run(self.set(key, value, ttl))


# =============================================================================
# DECORATORS
# =============================================================================


def generate_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Generate a deterministic cache key from function arguments.

    Args:
        prefix: Key prefix (usually function name)
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        MD5 hash of the arguments
    """
    key_parts = [prefix]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()


def cached(
    cache: BaseCache[str, Any] | None = None,
    ttl: float | None = None,
    key_fn: Callable[..., str] | None = None,
    key_prefix: str = "",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for caching synchronous function results.

    Args:
        cache: Cache instance (uses global if None)
        ttl: Time to live override
        key_fn: Custom key generation function
        key_prefix: Prefix for cache keys

    Returns:
        Decorated function

    Example:
        @cached(ttl=3600)
        def expensive_computation(x: int, y: int) -> int:
            return x ** y
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            nonlocal cache

            # Generate cache key
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                prefix = key_prefix or func.__name__
                cache_key = generate_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            if cache is not None:
                cached_value = cache.get_sync(cache_key, default=_MISSING)
                if cached_value is not _MISSING:
                    return cached_value  # type: ignore

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            if cache is not None:
                cache.set_sync(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def async_cached(
    cache: BaseCache[str, Any] | None = None,
    ttl: float | None = None,
    key_fn: Callable[..., str] | None = None,
    key_prefix: str = "",
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Decorator for caching async function results.

    Args:
        cache: Cache instance (uses global if None)
        ttl: Time to live override
        key_fn: Custom key generation function
        key_prefix: Prefix for cache keys

    Returns:
        Decorated async function

    Example:
        @async_cached(ttl=3600)
        async def fetch_user(user_id: int) -> dict:
            return await db.get_user(user_id)
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            nonlocal cache

            # Generate cache key
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                prefix = key_prefix or func.__name__
                cache_key = generate_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            if cache is not None:
                cached_value = await cache.get(cache_key, default=_MISSING)
                if cached_value is not _MISSING:
                    return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            if cache is not None:
                await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Sentinel
    "_MISSING",
    "BaseCache",
    # Configuration
    "BaseCacheConfig",
    "CacheEntry",
    # Protocols and base classes
    "CacheProtocol",
    "CacheStats",
    "CacheTier",
    # Enums
    "EvictionPolicy",
    "async_cached",
    # Decorators
    "cached",
    "generate_cache_key",
]
