"""Redis Caching Layer for Performance Optimization.

This module provides a comprehensive caching layer using Redis to optimize:
1. Database query results
2. LLM responses
3. Embedding vectors
4. Configuration data
5. Computation results

Target: 50%+ speedup on repeated operations with <20% memory overhead.

Colony: Nexus (e₄) - Integration
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pickle
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar, cast

import numpy as np

logger = logging.getLogger(__name__)

# Type variable for generic caching
T = TypeVar("T")


class CacheStrategy(str, Enum):
    """Cache invalidation strategy."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    ADAPTIVE = "adaptive"  # Adaptive based on access patterns


class CacheTier(str, Enum):
    """Cache tier for multi-level caching."""

    MEMORY = "memory"  # In-memory (fastest)
    REDIS = "redis"  # Redis (fast, persistent)
    DISK = "disk"  # Disk (slowest, largest)


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_get_time: float = 0.0
    total_set_time: float = 0.0
    memory_used: int = 0
    entries: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_get_time(self) -> float:
        """Average time to get from cache."""
        total = self.hits + self.misses
        return self.total_get_time / total if total > 0 else 0.0

    @property
    def avg_set_time(self) -> float:
        """Average time to set[Any] in cache."""
        return self.total_set_time / self.evictions if self.evictions > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": self.hit_rate,
            "avg_get_time_ms": self.avg_get_time * 1000,
            "avg_set_time_ms": self.avg_set_time * 1000,
            "memory_used_mb": self.memory_used / (1024 * 1024),
            "entries": self.entries,
        }


def _get_redis_host() -> str:
    """Get Redis host from environment or default."""
    return os.getenv(
        "REDIS_HOST",
        os.getenv("REDIS_URL", "localhost").split("://")[-1].split(":")[0].split("/")[0],
    )


def _get_redis_port() -> int:
    """Get Redis port from environment or default."""
    port_str = os.getenv("REDIS_PORT", "6379")
    return int(port_str)


@dataclass
class CacheConfig:
    """Configuration for Redis cache.

    Environment variables:
        REDIS_HOST: Redis host (default: localhost)
        REDIS_PORT: Redis port (default: 6379)
        REDIS_PASSWORD: Redis password (default: None)
        REDIS_SSL: Enable SSL (default: false)
    """

    # Redis connection - use env vars with fallback defaults
    host: str = ""  # Set in __post_init__
    port: int = 6379
    db: int = 0
    password: str | None = None
    ssl: bool = False

    # Cache behavior
    default_ttl: int = 3600  # 1 hour
    max_memory_mb: int = 1024  # 1 GB
    strategy: CacheStrategy = CacheStrategy.LRU

    # Multi-tier caching
    enable_memory_tier: bool = True
    memory_max_entries: int = 1000
    enable_disk_tier: bool = False
    disk_cache_dir: str = ""  # Set in __post_init__ to use central path

    # Performance tuning
    connection_pool_size: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0

    # Compression
    compress_threshold: int = 1024  # Compress values > 1KB
    compression_level: int = 6

    # Monitoring
    enable_stats: bool = True
    stats_interval: int = 60  # Log stats every 60s

    def __post_init__(self) -> None:
        """Initialize from environment variables."""
        if not self.host:
            self.host = _get_redis_host()
        if self.password is None:
            self.password = os.getenv("REDIS_PASSWORD")
        if not self.ssl:
            self.ssl = os.getenv("REDIS_SSL", "false").lower() in ("true", "1", "yes")


class RedisCache:
    """High-performance Redis cache with multi-tier support."""

    def __init__(self, config: CacheConfig | None = None, namespace: str = "kagami"):
        """Initialize Redis cache.

        Args:
            config: Cache configuration
            namespace: Namespace prefix for all keys
        """
        self.config = config or CacheConfig()
        self.namespace = namespace

        # Set default disk cache directory if not specified
        if not self.config.disk_cache_dir:
            from kagami.core.utils.paths import get_kagami_cache_dir

            self.config.disk_cache_dir = str(get_kagami_cache_dir() / "redis")
        self._redis_client: Any = None
        self._memory_cache: dict[str, tuple[Any, float]] = {}
        self._access_counts: dict[str, int] = {}
        self._stats = CacheStats()
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._initialized:
            return

        try:
            import redis.asyncio as aioredis

            pool = aioredis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                ssl=self.config.ssl,
                max_connections=self.config.connection_pool_size,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
            )
            self._redis_client = aioredis.Redis(connection_pool=pool)

            # Test connection
            await self._redis_client.ping()
            logger.info(f"Redis cache initialized: {self.config.host}:{self.config.port}")

        except ImportError:
            logger.warning("redis-py not installed, using memory-only cache")
            self._redis_client = None
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}, falling back to memory-only")
            self._redis_client = None

        self._initialized = True

        # Start stats monitoring if enabled
        if self.config.enable_stats:
            asyncio.create_task(self._monitor_stats())

    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        return f"{self.namespace}:{key}"

    def _hash_key(self, data: Any) -> str:
        """Create hash key from data."""
        if isinstance(data, str):
            key_str = data
        elif isinstance(data, (list, tuple, dict)):
            key_str = json.dumps(data, sort_keys=True)
        else:
            key_str = str(data)

        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        serialized = pickle.dumps(value)

        # Compress if over threshold
        if len(serialized) > self.config.compress_threshold:
            import zlib

            serialized = zlib.compress(serialized, self.config.compression_level)

        return serialized

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            # Try to decompress first
            import zlib

            try:
                data = zlib.decompress(data)
            except zlib.error:
                pass  # Not compressed

            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize cache data: {e}")
            return None

    async def get(
        self, key: str, default: T | None = None, tier: CacheTier = CacheTier.REDIS
    ) -> T | None:
        """Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found
            tier: Cache tier to check

        Returns:
            Cached value or default
        """
        start_time = time.time()

        try:
            # Check memory tier first if enabled
            if self.config.enable_memory_tier and tier == CacheTier.REDIS:
                if key in self._memory_cache:
                    value, expiry = self._memory_cache[key]
                    if expiry > time.time():
                        self._stats.hits += 1
                        self._access_counts[key] = self._access_counts.get(key, 0) + 1
                        return cast(T, value)
                    else:
                        # Expired
                        del self._memory_cache[key]

            # Check Redis
            if self._redis_client:
                redis_key = self._make_key(key)
                data = await self._redis_client.get(redis_key)

                if data:
                    value = self._deserialize(data)
                    if value is not None:
                        self._stats.hits += 1

                        # Update memory cache
                        if self.config.enable_memory_tier:
                            await self._update_memory_cache(key, value)

                        return cast(T, value)

            self._stats.misses += 1
            return default

        finally:
            self._stats.total_get_time += time.time() - start_time

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        tier: CacheTier = CacheTier.REDIS,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = default)
            tier: Cache tier to use

        Returns:
            True if successful
        """
        start_time = time.time()
        ttl = ttl or self.config.default_ttl

        try:
            # Update memory cache if enabled
            if self.config.enable_memory_tier:
                await self._update_memory_cache(key, value, ttl)

            # Update Redis
            if self._redis_client:
                redis_key = self._make_key(key)
                serialized = self._serialize(value)
                await self._redis_client.setex(redis_key, ttl, serialized)

            self._stats.entries += 1
            return True

        except Exception as e:
            logger.error(f"Failed to set[Any] cache key {key}: {e}")
            return False

        finally:
            self._stats.total_set_time += time.time() - start_time

    async def _update_memory_cache(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Update memory cache with eviction."""
        ttl = ttl or self.config.default_ttl
        expiry = time.time() + ttl

        # Evict if at capacity
        if len(self._memory_cache) >= self.config.memory_max_entries:
            await self._evict_from_memory()

        self._memory_cache[key] = (value, expiry)
        self._access_counts[key] = self._access_counts.get(key, 0) + 1

    async def _evict_from_memory(self) -> None:
        """Evict entries from memory cache based on strategy."""
        if not self._memory_cache:
            return

        # Remove expired entries first
        now = time.time()
        expired = [k for k, (_, exp) in self._memory_cache.items() if exp <= now]
        for k in expired:
            del self._memory_cache[k]
            self._access_counts.pop(k, None)

        if len(self._memory_cache) < self.config.memory_max_entries:
            return

        # Apply eviction strategy
        if self.config.strategy == CacheStrategy.LRU:
            # Evict oldest (lowest expiry)
            key_to_evict = min(self._memory_cache.items(), key=lambda x: x[1][1])[0]
        elif self.config.strategy == CacheStrategy.LFU:
            # Evict least frequently used
            key_to_evict = min(self._access_counts.items(), key=lambda x: x[1])[0]
        else:
            # Default to LRU
            key_to_evict = min(self._memory_cache.items(), key=lambda x: x[1][1])[0]

        del self._memory_cache[key_to_evict]
        self._access_counts.pop(key_to_evict, None)
        self._stats.evictions += 1

    async def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key existed
        """
        deleted = False

        # Remove from memory cache
        if key in self._memory_cache:
            del self._memory_cache[key]
            self._access_counts.pop(key, None)
            deleted = True

        # Remove from Redis
        if self._redis_client:
            redis_key = self._make_key(key)
            result = await self._redis_client.delete(redis_key)
            deleted = deleted or result > 0

        if deleted:
            self._stats.entries = max(0, self._stats.entries - 1)

        return deleted

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries.

        Args:
            pattern: Optional pattern to match keys (e.g., "llm:*")

        Returns:
            Number of keys deleted
        """
        count = 0

        if pattern:
            # Clear matching keys
            if self._redis_client:
                redis_pattern = self._make_key(pattern)
                cursor = 0
                while True:
                    cursor, keys = await self._redis_client.scan(
                        cursor, match=redis_pattern, count=100
                    )
                    if keys:
                        count += await self._redis_client.delete(*keys)
                    if cursor == 0:
                        break

            # Clear from memory cache
            prefix = pattern.replace("*", "")
            keys_to_delete = [k for k in self._memory_cache if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._memory_cache[k]
                self._access_counts.pop(k, None)
            count += len(keys_to_delete)

        else:
            # Clear all
            if self._redis_client:
                count = await self._redis_client.flushdb()

            count += len(self._memory_cache)
            self._memory_cache.clear()
            self._access_counts.clear()

        self._stats.entries = max(0, self._stats.entries - count)
        return count

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        stats = self._stats.to_dict()

        # Add Redis info if available
        if self._redis_client:
            try:
                info = await self._redis_client.info("memory")
                stats["redis_memory_used_mb"] = info.get("used_memory", 0) / (1024 * 1024)
                stats["redis_peak_memory_mb"] = info.get("used_memory_peak", 0) / (1024 * 1024)
            except Exception:
                pass

        stats["memory_cache_entries"] = len(self._memory_cache)
        return stats

    async def _monitor_stats(self) -> None:
        """Background task to monitor and log cache statistics."""
        while True:
            await asyncio.sleep(self.config.stats_interval)
            stats = await self.get_stats()
            logger.info(f"Cache stats: {json.dumps(stats, indent=2)}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            await self._redis_client.connection_pool.disconnect()
            logger.info("Redis cache closed")


class CachedFunction(Generic[T]):
    """Decorator for caching function results."""

    def __init__(
        self,
        cache: RedisCache,
        ttl: int | None = None,
        key_prefix: str = "",
        key_fn: Callable[..., str] | None = None,
    ):
        """Initialize cached function.

        Args:
            cache: Redis cache instance
            ttl: Time to live in seconds
            key_prefix: Prefix for cache keys
            key_fn: Function to generate cache key from arguments
        """
        self.cache = cache
        self.ttl = ttl
        self.key_prefix = key_prefix
        self.key_fn = key_fn

    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Wrap function with caching."""

        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            if self.key_fn:
                cache_key = self.key_fn(*args, **kwargs)
            else:
                key_data = {"args": args, "kwargs": kwargs}
                cache_key = self.cache._hash_key(key_data)

            full_key = f"{self.key_prefix}:{cache_key}" if self.key_prefix else cache_key

            # Try to get from cache
            cached = await self.cache.get(full_key)
            if cached is not None:
                return cast(T, cached)

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await self.cache.set(full_key, result, self.ttl)

            return result

        return wrapper


# Specialized cache instances


class LLMResponseCache:
    """Cache for LLM responses."""

    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.prefix = "llm"

    async def get(self, prompt: str, model: str, temperature: float = 0.0) -> str | None:
        """Get cached LLM response."""
        key_data = {"prompt": prompt, "model": model, "temperature": temperature}
        cache_key = f"{self.prefix}:{self.cache._hash_key(key_data)}"
        return await self.cache.get(cache_key)

    async def set(
        self, prompt: str, model: str, response: str, temperature: float = 0.0, ttl: int = 3600
    ) -> None:
        """Cache LLM response."""
        key_data = {"prompt": prompt, "model": model, "temperature": temperature}
        cache_key = f"{self.prefix}:{self.cache._hash_key(key_data)}"
        await self.cache.set(cache_key, response, ttl)


class EmbeddingCache:
    """Cache for embedding vectors."""

    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.prefix = "embedding"

    async def get(self, text: str, model: str) -> np.ndarray[Any, Any] | None:
        """Get cached embedding."""
        cache_key = f"{self.prefix}:{model}:{self.cache._hash_key(text)}"
        data = await self.cache.get(cache_key)
        if data:
            return np.frombuffer(data, dtype=np.float32)
        return None

    async def set(
        self, text: str, model: str, embedding: np.ndarray[Any, Any], ttl: int = 7200
    ) -> None:
        """Cache embedding."""
        cache_key = f"{self.prefix}:{model}:{self.cache._hash_key(text)}"
        # Store as bytes for efficiency
        data = embedding.astype(np.float32).tobytes()
        await self.cache.set(cache_key, data, ttl)


class DatabaseQueryCache:
    """Cache for database query results."""

    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.prefix = "db"

    async def get(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]] | None:
        """Get cached query result."""
        key_data = {"query": query, "params": params}
        cache_key = f"{self.prefix}:{self.cache._hash_key(key_data)}"
        return await self.cache.get(cache_key)

    async def set(
        self,
        query: str,
        params: tuple[Any, ...] | None,
        result: list[dict[str, Any]],
        ttl: int = 300,
    ) -> None:
        """Cache query result."""
        key_data = {"query": query, "params": params}
        cache_key = f"{self.prefix}:{self.cache._hash_key(key_data)}"
        await self.cache.set(cache_key, result, ttl)

    async def invalidate_table(self, table_name: str) -> int:
        """Invalidate all cached queries for a table."""
        return await self.cache.clear(f"{self.prefix}:*{table_name}*")


# Global cache instance
_global_cache: RedisCache | None = None


async def get_global_cache() -> RedisCache:
    """Get or create global cache instance."""
    global _global_cache

    if _global_cache is None:
        _global_cache = RedisCache()
        await _global_cache.initialize()

    return _global_cache


# Convenience decorators


def cached(
    ttl: int | None = None, key_prefix: str = "", key_fn: Callable[..., str] | None = None
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to cache function results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys
        key_fn: Function to generate cache key from arguments

    Example:
        @cached(ttl=3600, key_prefix="user")
        async def get_user(user_id: int) -> dict[str, Any]:
            return await db.fetch_user(user_id)
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            cache = await get_global_cache()
            cached_fn = CachedFunction(cache, ttl, key_prefix, key_fn)
            return await cached_fn(func)(*args, **kwargs)

        return wrapper

    return decorator
