"""Cache Backend Implementations for K OS.

This module provides concrete cache backend implementations:
- MemoryBackend: Fast in-memory LRU cache with TTL
- RedisBackend: Redis-backed distributed cache
- CompositeBackend: Multi-tier caching (L1 memory + L2 Redis)

USAGE:
======
    # Simple memory cache
    from kagami.core.caching.backends import MemoryBackend, MemoryCacheConfig

    cache = MemoryBackend(MemoryCacheConfig(max_size=1000, default_ttl=3600))
    await cache.set("key", "value")
    value = await cache.get("key")

    # Redis-backed cache
    from kagami.core.caching.backends import RedisBackend, RedisCacheConfig

    cache = RedisBackend(RedisCacheConfig(host="localhost", port=6379))
    await cache.initialize()
    await cache.set("key", "value", ttl=3600)

    # Composite cache (memory + redis)
    from kagami.core.caching.backends import CompositeBackend, CompositeCacheConfig

    cache = CompositeBackend(CompositeCacheConfig())
    await cache.initialize()
    await cache.set("key", "value")  # Stored in both L1 and L2

PERFORMANCE CHARACTERISTICS:
============================
| Backend       | Get (hot)  | Get (cold) | Set     | Memory   | Shared  |
|---------------|------------|------------|---------|----------|---------|
| Memory        | ~100ns     | ~100ns     | ~200ns  | High     | No      |
| Redis         | ~200us     | ~200us     | ~300us  | Low      | Yes     |
| Composite L1  | ~100ns     | ~200us     | ~300us  | Medium   | Yes     |

Created: January 11, 2026
Colony: Forge (e2) - Infrastructure
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, TypeVar

from kagami.core.caching.base import (
    BaseCache,
    BaseCacheConfig,
    CacheEntry,
    CacheStats,
    EvictionPolicy,
)

logger = logging.getLogger(__name__)

# Type variables
V = TypeVar("V")


# =============================================================================
# MEMORY BACKEND
# =============================================================================


@dataclass
class MemoryCacheConfig(BaseCacheConfig):
    """Configuration for memory-only cache backend."""

    # Memory-specific options
    cleanup_interval: float = 60.0  # Interval for expired entry cleanup (seconds)
    enable_cleanup_task: bool = False  # Auto-start cleanup task


class MemoryBackend(BaseCache[str, Any]):
    """High-performance in-memory cache with LRU eviction.

    Features:
    - O(1) get/set operations
    - LRU, LFU, or FIFO eviction
    - TTL-based expiration
    - Thread-safe implementation
    - Periodic cleanup of expired entries

    Thread Safety:
    - Uses threading.RLock for synchronization
    - Safe for concurrent access from multiple threads
    - Async operations are also thread-safe

    Example:
        cache = MemoryBackend(MemoryCacheConfig(max_size=1000))
        await cache.set("user:123", {"name": "Tim"}, ttl=3600)
        user = await cache.get("user:123")
    """

    def __init__(self, config: MemoryCacheConfig | None = None) -> None:
        """Initialize memory backend.

        Args:
            config: Cache configuration (uses defaults if None)
        """
        super().__init__(config or MemoryCacheConfig())
        self.config: MemoryCacheConfig = self.config  # type: ignore

        # OrderedDict maintains insertion order for LRU tracking
        self._cache: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._access_counts: dict[str, int] = {}  # For LFU

        # Thread safety
        self._lock = threading.RLock() if self.config.thread_safe else None

        # Background cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """Start background cleanup task if enabled."""
        if self.config.enable_cleanup_task and self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.debug("Memory cache cleanup task started")

    async def close(self) -> None:
        """Stop background tasks and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    def _acquire_lock(self) -> bool:
        """Acquire lock if thread-safe mode is enabled."""
        if self._lock:
            return self._lock.acquire()
        return True

    def _release_lock(self) -> None:
        """Release lock if thread-safe mode is enabled."""
        if self._lock:
            self._lock.release()

    async def _get_impl(self, key: str) -> CacheEntry[Any] | None:
        """Get cache entry implementation."""
        self._acquire_lock()
        try:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired:
                del self._cache[key]
                self._access_counts.pop(key, None)
                self._update_stats(size_delta=-1)  # Track expired entry removal
                return None

            # Update LRU order (move to end)
            if self.config.eviction_policy == EvictionPolicy.LRU:
                self._cache.move_to_end(key)

            # Update access count for LFU
            self._access_counts[key] = self._access_counts.get(key, 0) + 1

            return entry

        finally:
            self._release_lock()

    async def _set_impl(self, key: str, entry: CacheEntry[Any]) -> None:
        """Set cache entry implementation."""
        self._acquire_lock()
        try:
            # Check if key already exists
            is_new = key not in self._cache

            # Evict while at or over capacity (for new keys)
            if is_new:
                while len(self._cache) >= self.config.max_size:
                    self._evict_one()

            # Store entry
            self._cache[key] = entry
            self._access_counts[key] = 0

            # Move to end for LRU tracking
            self._cache.move_to_end(key)

            # Update stats
            if is_new:
                self._update_stats(size_delta=1)

        finally:
            self._release_lock()

    async def _delete_impl(self, key: str) -> bool:
        """Delete cache entry implementation."""
        self._acquire_lock()
        try:
            if key in self._cache:
                del self._cache[key]
                self._access_counts.pop(key, None)
                return True
            return False
        finally:
            self._release_lock()

    async def _exists_impl(self, key: str) -> bool:
        """Check if key exists implementation."""
        self._acquire_lock()
        try:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            if entry.is_expired:
                del self._cache[key]
                self._access_counts.pop(key, None)
                return False

            return True
        finally:
            self._release_lock()

    async def _clear_impl(self) -> None:
        """Clear all entries implementation."""
        self._acquire_lock()
        try:
            self._cache.clear()
            self._access_counts.clear()
        finally:
            self._release_lock()

    def _evict_one(self) -> None:
        """Evict one entry based on eviction policy.

        Must be called with lock held.
        """
        if not self._cache:
            return

        key_to_evict: str | None = None

        if self.config.eviction_policy == EvictionPolicy.LRU:
            # Evict first item (least recently used)
            key_to_evict = next(iter(self._cache))

        elif self.config.eviction_policy == EvictionPolicy.LFU:
            # Evict least frequently used
            if self._access_counts:
                key_to_evict = min(self._access_counts, key=self._access_counts.get)  # type: ignore
            else:
                key_to_evict = next(iter(self._cache))

        elif self.config.eviction_policy == EvictionPolicy.FIFO:
            # Evict first item (first in)
            key_to_evict = next(iter(self._cache))

        elif self.config.eviction_policy == EvictionPolicy.TTL:
            # Evict entry with shortest remaining TTL
            entries_with_ttl = [(k, e) for k, e in self._cache.items() if e.expires_at is not None]
            if entries_with_ttl:
                key_to_evict = min(entries_with_ttl, key=lambda x: x[1].expires_at or 0)[0]
            else:
                key_to_evict = next(iter(self._cache))

        if key_to_evict:
            del self._cache[key_to_evict]
            self._access_counts.pop(key_to_evict, None)
            self._update_stats(eviction=True, size_delta=-1)
            logger.debug(f"Evicted key: {key_to_evict}")

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        self._acquire_lock()
        try:
            now = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if entry.expires_at is not None and entry.expires_at < now
            ]

            for key in expired_keys:
                del self._cache[key]
                self._access_counts.pop(key, None)

            if expired_keys:
                self._update_stats(size_delta=-len(expired_keys))
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)
        finally:
            self._release_lock()

    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup."""
        while True:
            await asyncio.sleep(self.config.cleanup_interval)
            try:
                self.cleanup_expired()
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")

    # Optimized sync methods for performance-critical paths
    def get_sync(self, key: str, default: Any = None) -> Any:
        """Synchronous get (avoids async overhead)."""
        internal_key = self._make_key(key)

        self._acquire_lock()
        try:
            if internal_key not in self._cache:
                self._update_stats(miss=True)
                return default

            entry = self._cache[internal_key]

            if entry.is_expired:
                del self._cache[internal_key]
                self._access_counts.pop(internal_key, None)
                self._update_stats(miss=True, size_delta=-1)  # Track expired entry removal
                return default

            # Update LRU
            if self.config.eviction_policy == EvictionPolicy.LRU:
                self._cache.move_to_end(internal_key)

            self._access_counts[internal_key] = self._access_counts.get(internal_key, 0) + 1
            entry.touch()
            self._update_stats(hit=True)

            return entry.value

        finally:
            self._release_lock()

    def set_sync(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Synchronous set (avoids async overhead)."""
        internal_key = self._make_key(key)

        # Calculate expiration
        effective_ttl = ttl if ttl is not None else self.config.default_ttl
        if effective_ttl is not None:
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

        self._acquire_lock()
        try:
            is_new = internal_key not in self._cache

            if is_new:
                while len(self._cache) >= self.config.max_size:
                    self._evict_one()

            self._cache[internal_key] = entry
            self._access_counts[internal_key] = 0
            self._cache.move_to_end(internal_key)

            if is_new:
                self._update_stats(size_delta=1)

        finally:
            self._release_lock()


# =============================================================================
# REDIS BACKEND
# =============================================================================


@dataclass
class RedisCacheConfig(BaseCacheConfig):
    """Configuration for Redis cache backend."""

    # Connection settings
    host: str = ""  # Empty = use env var
    port: int = 6379
    db: int = 0
    password: str | None = None
    ssl: bool = False

    # Pool settings
    pool_size: int = 10
    socket_timeout: float = 5.0
    connect_timeout: float = 5.0

    # Serialization
    serialize_json: bool = True  # Use JSON for values (vs pickle)

    def __post_init__(self) -> None:
        """Initialize from environment variables."""
        if not self.host:
            self.host = os.getenv("REDIS_HOST", "localhost")
        if self.password is None:
            self.password = os.getenv("REDIS_PASSWORD")
        if not self.ssl:
            self.ssl = os.getenv("REDIS_SSL", "false").lower() in ("true", "1", "yes")


class RedisBackend(BaseCache[str, Any]):
    """Redis-backed cache for distributed caching.

    Features:
    - Distributed cache shared across instances
    - Native TTL support via Redis SETEX
    - Connection pooling
    - Automatic reconnection
    - JSON or pickle serialization

    Example:
        cache = RedisBackend(RedisCacheConfig(host="localhost"))
        await cache.initialize()
        await cache.set("session:123", {"user": "tim"}, ttl=3600)
    """

    def __init__(self, config: RedisCacheConfig | None = None) -> None:
        """Initialize Redis backend.

        Args:
            config: Redis configuration (uses defaults if None)
        """
        super().__init__(config or RedisCacheConfig())
        self.config: RedisCacheConfig = self.config  # type: ignore

        self._redis: Any = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        if self._initialized:
            return

        async with self._init_lock:
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
                    max_connections=self.config.pool_size,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.connect_timeout,
                )
                self._redis = aioredis.Redis(connection_pool=pool)

                # Test connection
                await self._redis.ping()
                self._initialized = True
                logger.info(f"Redis backend initialized: {self.config.host}:{self.config.port}")

            except ImportError:
                logger.error("redis-py not installed. Install with: pip install redis")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            await self._redis.connection_pool.disconnect()
            self._redis = None
            self._initialized = False
            logger.info("Redis backend closed")

    def _serialize(self, value: Any) -> str:
        """Serialize value for Redis storage."""
        if self.config.serialize_json:
            return json.dumps(value, default=str)
        else:
            import base64
            import pickle

            return base64.b64encode(pickle.dumps(value)).decode()

    def _deserialize(self, data: str | bytes) -> Any:
        """Deserialize value from Redis."""
        if isinstance(data, bytes):
            data = data.decode()

        if self.config.serialize_json:
            return json.loads(data)
        else:
            import base64
            import pickle

            return pickle.loads(base64.b64decode(data))

    async def _get_impl(self, key: str) -> CacheEntry[Any] | None:
        """Get cache entry from Redis."""
        if not self._initialized:
            await self.initialize()

        try:
            data = await self._redis.get(key)
            if data is None:
                return None

            value = self._deserialize(data)

            # Redis handles TTL natively, so no expiration check needed
            return CacheEntry(
                value=value,
                created_at=time.time(),  # Unknown, use current
                expires_at=None,  # Managed by Redis
            )

        except Exception as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return None

    async def _set_impl(self, key: str, entry: CacheEntry[Any]) -> None:
        """Set cache entry in Redis."""
        if not self._initialized:
            await self.initialize()

        try:
            serialized = self._serialize(entry.value)

            # Calculate TTL from entry
            if entry.expires_at is not None:
                ttl_seconds = int(entry.expires_at - time.time())
                if ttl_seconds > 0:
                    await self._redis.setex(key, ttl_seconds, serialized)
                # If TTL <= 0, entry is already expired, don't store
            else:
                # No expiration
                await self._redis.set(key, serialized)

            self._update_stats(size_delta=1)

        except Exception as e:
            logger.error(f"Redis set failed for key {key}: {e}")

    async def _delete_impl(self, key: str) -> bool:
        """Delete cache entry from Redis."""
        if not self._initialized:
            await self.initialize()

        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete failed for key {key}: {e}")
            return False

    async def _exists_impl(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self._initialized:
            await self.initialize()

        try:
            result = await self._redis.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis exists check failed for key {key}: {e}")
            return False

    async def _clear_impl(self) -> None:
        """Clear all entries with namespace prefix."""
        if not self._initialized:
            await self.initialize()

        try:
            if self.config.namespace:
                # Delete only keys with our namespace
                pattern = f"{self.config.namespace}:*"
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self._redis.delete(*keys)
                    if cursor == 0:
                        break
            else:
                # Clear entire database (careful!)
                await self._redis.flushdb()

            logger.info("Redis cache cleared")

        except Exception as e:
            logger.error(f"Redis clear failed: {e}")

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Args:
            pattern: Glob-style pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        if not self._initialized:
            await self.initialize()

        try:
            full_pattern = self._make_key(pattern)
            count = 0
            cursor = 0

            while True:
                cursor, keys = await self._redis.scan(cursor, match=full_pattern, count=100)
                if keys:
                    count += await self._redis.delete(*keys)
                if cursor == 0:
                    break

            logger.debug(f"Invalidated {count} keys matching {pattern}")
            return count

        except Exception as e:
            logger.error(f"Redis pattern invalidation failed: {e}")
            return 0


# =============================================================================
# COMPOSITE BACKEND
# =============================================================================


@dataclass
class CompositeCacheConfig(BaseCacheConfig):
    """Configuration for composite (multi-tier) cache backend."""

    # L1 (Memory) configuration
    l1_max_size: int = 1000
    l1_default_ttl: float | None = 300.0  # 5 minutes

    # L2 (Redis) configuration
    l2_enabled: bool = True
    l2_host: str = ""  # Empty = use env var
    l2_port: int = 6379
    l2_default_ttl: float | None = 3600.0  # 1 hour

    # Promotion policy
    promote_on_l2_hit: bool = True  # Copy L2 hits to L1


class CompositeBackend(BaseCache[str, Any]):
    """Multi-tier cache combining memory and Redis.

    Architecture:
        L1 (Memory) ─── fastest, local ───────────┐
                                                  ├─→ value
        L2 (Redis)  ─── fast, distributed ────────┘

    On GET:
        1. Check L1 (memory) - O(1), ~100ns
        2. If miss, check L2 (Redis) - ~200us
        3. If L2 hit, optionally promote to L1

    On SET:
        1. Store in L1 (memory)
        2. Store in L2 (Redis) - async, non-blocking

    Benefits:
        - Hot data served from memory (microseconds)
        - Large capacity via Redis
        - Shared state across instances via Redis
        - Graceful degradation if Redis unavailable

    Example:
        cache = CompositeBackend(CompositeCacheConfig())
        await cache.initialize()

        # First access: L2 hit, promoted to L1
        await cache.set("key", "value")

        # Subsequent accesses: L1 hit (fast!)
        value = await cache.get("key")
    """

    def __init__(self, config: CompositeCacheConfig | None = None) -> None:
        """Initialize composite backend.

        Args:
            config: Composite configuration (uses defaults if None)
        """
        super().__init__(config or CompositeCacheConfig())
        self.config: CompositeCacheConfig = self.config  # type: ignore

        # L1: Memory backend
        l1_config = MemoryCacheConfig(
            max_size=self.config.l1_max_size,
            default_ttl=self.config.l1_default_ttl,
            namespace=self.config.namespace,
            eviction_policy=self.config.eviction_policy,
            thread_safe=self.config.thread_safe,
            enable_stats=self.config.enable_stats,
        )
        self._l1 = MemoryBackend(l1_config)

        # L2: Redis backend (optional)
        self._l2: RedisBackend | None = None
        if self.config.l2_enabled:
            l2_config = RedisCacheConfig(
                host=self.config.l2_host,
                port=self.config.l2_port,
                default_ttl=self.config.l2_default_ttl,
                namespace=self.config.namespace,
                enable_stats=self.config.enable_stats,
            )
            self._l2 = RedisBackend(l2_config)

        # Combined stats
        self._l1_stats = CacheStats()
        self._l2_stats = CacheStats()

    async def initialize(self) -> None:
        """Initialize all cache tiers."""
        await self._l1.initialize()
        if self._l2:
            try:
                await self._l2.initialize()
            except Exception as e:
                logger.warning(f"L2 (Redis) initialization failed, running L1-only: {e}")
                self._l2 = None

    async def close(self) -> None:
        """Close all cache tiers."""
        await self._l1.close()
        if self._l2:
            await self._l2.close()

    async def _get_impl(self, key: str) -> CacheEntry[Any] | None:
        """Get from cache tiers (L1 first, then L2)."""
        # Try L1 first
        entry = await self._l1._get_impl(key)
        if entry is not None:
            self._l1_stats.hits += 1
            return entry

        self._l1_stats.misses += 1

        # Try L2 if available
        if self._l2:
            entry = await self._l2._get_impl(key)
            if entry is not None:
                self._l2_stats.hits += 1

                # Promote to L1
                if self.config.promote_on_l2_hit:
                    # Create L1-specific entry with shorter TTL
                    l1_entry = CacheEntry(
                        value=entry.value,
                        created_at=time.time(),
                        expires_at=(
                            time.time() + self.config.l1_default_ttl
                            if self.config.l1_default_ttl
                            else None
                        ),
                    )
                    await self._l1._set_impl(key, l1_entry)

                return entry

            self._l2_stats.misses += 1

        return None

    async def _set_impl(self, key: str, entry: CacheEntry[Any]) -> None:
        """Set in all cache tiers."""
        # Set in L1 with L1-specific TTL
        l1_entry = CacheEntry(
            value=entry.value,
            created_at=time.time(),
            expires_at=(
                time.time() + self.config.l1_default_ttl
                if self.config.l1_default_ttl
                else entry.expires_at
            ),
        )
        await self._l1._set_impl(key, l1_entry)

        # Set in L2 (with original TTL, async)
        if self._l2:
            # Fire-and-forget for performance
            asyncio.create_task(self._l2._set_impl(key, entry))

    async def _delete_impl(self, key: str) -> bool:
        """Delete from all cache tiers."""
        l1_deleted = await self._l1._delete_impl(key)

        l2_deleted = False
        if self._l2:
            l2_deleted = await self._l2._delete_impl(key)

        return l1_deleted or l2_deleted

    async def _exists_impl(self, key: str) -> bool:
        """Check if key exists in any tier."""
        if await self._l1._exists_impl(key):
            return True
        if self._l2:
            return await self._l2._exists_impl(key)
        return False

    async def _clear_impl(self) -> None:
        """Clear all cache tiers."""
        await self._l1._clear_impl()
        if self._l2:
            await self._l2._clear_impl()

    @property
    def stats(self) -> CacheStats:
        """Get combined statistics."""
        l1_stats = self._l1.stats
        l2_stats = self._l2.stats if self._l2 else CacheStats()

        return CacheStats(
            hits=l1_stats.hits + l2_stats.hits,
            misses=l2_stats.misses,  # Final miss count
            evictions=l1_stats.evictions + l2_stats.evictions,
            size=l1_stats.size,  # L1 size (L2 size not easily available)
            max_size=l1_stats.max_size,
            total_get_time_ns=l1_stats.total_get_time_ns + l2_stats.total_get_time_ns,
            total_set_time_ns=l1_stats.total_set_time_ns + l2_stats.total_set_time_ns,
        )

    def get_tier_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics broken down by tier.

        Returns:
            Dict with L1 and L2 stats
        """
        result = {
            "l1": self._l1.stats.to_dict(),
            "l1_internal": self._l1_stats.to_dict(),
        }
        if self._l2:
            result["l2"] = self._l2.stats.to_dict()
            result["l2_internal"] = self._l2_stats.to_dict()
        return result

    # Optimized sync methods
    def get_sync(self, key: str, default: Any = None) -> Any:
        """Synchronous get from L1 only (for hot path performance)."""
        return self._l1.get_sync(key, default)

    def set_sync(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Synchronous set to L1 (L2 update happens async)."""
        self._l1.set_sync(key, value, ttl or self.config.l1_default_ttl)

        # Schedule L2 update
        if self._l2:
            internal_key = self._make_key(key)
            effective_ttl = ttl or self.config.l2_default_ttl
            expires_at = time.time() + effective_ttl if effective_ttl else None

            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                expires_at=expires_at,
            )

            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._l2._set_impl(internal_key, entry))
            except RuntimeError:
                # No event loop - skip L2 update
                pass


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_memory_cache(
    max_size: int = 1000,
    default_ttl: float | None = 3600.0,
    namespace: str = "",
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
) -> MemoryBackend:
    """Create a configured memory cache.

    Args:
        max_size: Maximum number of entries
        default_ttl: Default TTL in seconds (None = no expiration)
        namespace: Key namespace prefix
        eviction_policy: Eviction strategy

    Returns:
        Configured MemoryBackend
    """
    config = MemoryCacheConfig(
        max_size=max_size,
        default_ttl=default_ttl,
        namespace=namespace,
        eviction_policy=eviction_policy,
    )
    return MemoryBackend(config)


async def create_redis_cache(
    host: str = "",
    port: int = 6379,
    default_ttl: float | None = 3600.0,
    namespace: str = "",
) -> RedisBackend:
    """Create a configured and initialized Redis cache.

    Args:
        host: Redis host (empty = use env var)
        port: Redis port
        default_ttl: Default TTL in seconds
        namespace: Key namespace prefix

    Returns:
        Initialized RedisBackend
    """
    config = RedisCacheConfig(
        host=host,
        port=port,
        default_ttl=default_ttl,
        namespace=namespace,
    )
    cache = RedisBackend(config)
    await cache.initialize()
    return cache


async def create_composite_cache(
    l1_max_size: int = 1000,
    l1_ttl: float | None = 300.0,
    l2_ttl: float | None = 3600.0,
    namespace: str = "",
) -> CompositeBackend:
    """Create a configured and initialized composite cache.

    Args:
        l1_max_size: L1 (memory) max entries
        l1_ttl: L1 TTL in seconds
        l2_ttl: L2 (Redis) TTL in seconds
        namespace: Key namespace prefix

    Returns:
        Initialized CompositeBackend
    """
    config = CompositeCacheConfig(
        l1_max_size=l1_max_size,
        l1_default_ttl=l1_ttl,
        l2_default_ttl=l2_ttl,
        namespace=namespace,
    )
    cache = CompositeBackend(config)
    await cache.initialize()
    return cache


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Composite backend
    "CompositeBackend",
    "CompositeCacheConfig",
    # Memory backend
    "MemoryBackend",
    "MemoryCacheConfig",
    # Redis backend
    "RedisBackend",
    "RedisCacheConfig",
    "create_composite_cache",
    # Factory functions
    "create_memory_cache",
    "create_redis_cache",
]
