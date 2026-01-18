"""Base repository with multi-tier caching and storage routing.

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from enum import Enum
from typing import Any, Generic, TypeVar

# Metrics removed during cleanup Dec 2025 - using local counters
_cache_hits = 0
_cache_misses = 0
_cache_evictions = 0

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheStrategy(Enum):
    """Cache strategies for repository operations."""

    NONE = "none"  # No caching
    READ_THROUGH = "read"  # Cache on read
    WRITE_THROUGH = "write"  # Update cache on write
    WRITE_BEHIND = "behind"  # Async cache update
    INVALIDATE = "invalidate"  # Invalidate on write


class _LRU(Generic[T]):
    """LRU cache implementation for L1 in-memory caching."""

    def __init__(self, max_size: int = 1024) -> None:
        self._max = max_size
        self._data: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str, ttl: int | None = None) -> T | None:
        """Get value from cache with TTL check.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds (optional)

        Returns:
            Cached value or None
        """
        async with self._lock:
            if key in self._data:
                value, timestamp = self._data.pop(key)

                # Check TTL expiration
                if ttl is not None and (time.time() - timestamp) > ttl:
                    return None

                # Move to end (most recently used)
                self._data[key] = (value, timestamp)
                return value
        return None

    async def set(self, key: str, value: T) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        async with self._lock:
            if key in self._data:
                self._data.pop(key)

            self._data[key] = (value, time.time())

            # Evict oldest if over capacity
            if len(self._data) > self._max:
                self._data.popitem(last=False)
                global _cache_evictions
                _cache_evictions += 1

    async def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if key in self._data:
                self._data.pop(key)
                return True
        return False

    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            self._data.clear()


class BaseRepository(ABC, Generic[T]):
    """Base repository with multi-tier caching.

    Provides automatic caching across three tiers:
    - L1: In-memory LRU cache (fast, limited capacity)
    - L2: Redis cache (shared, larger capacity)
    - L3: Primary storage (persistent, authoritative)

    Cache strategies:
    - READ_THROUGH: Populate cache on read miss
    - WRITE_THROUGH: Update cache immediately on write
    - WRITE_BEHIND: Update cache asynchronously on write
    - INVALIDATE: Clear cache on write
    """

    def __init__(
        self,
        storage_backend: Any,
        cache_strategy: CacheStrategy = CacheStrategy.READ_THROUGH,
        ttl: int = 300,
        l1_max_size: int = 1000,
        redis_client: Any | None = None,
    ):
        """Initialize base repository.

        Args:
            storage_backend: Primary storage backend
            cache_strategy: Caching strategy to use
            ttl: Default TTL in seconds
            l1_max_size: Max entries in L1 cache
            redis_client: Optional Redis client for L2 cache
        """
        self.storage = storage_backend
        self.cache_strategy = cache_strategy
        self.ttl = ttl

        # L1: In-memory LRU cache
        self._l1_cache: _LRU[T] = _LRU(max_size=l1_max_size)

        # L2: Redis cache (optional)
        self._redis = redis_client

        logger.debug(
            f"BaseRepository initialized: strategy={cache_strategy.value}, "
            f"ttl={ttl}s, l1_max={l1_max_size}"
        )

    def _cache_key(self, key: str) -> str:
        """Generate namespaced cache key.

        Args:
            key: Raw key

        Returns:
            Namespaced cache key
        """
        return f"{self.__class__.__name__}:{key}"

    async def get(self, key: str) -> T | None:
        """Get entity with multi-tier cache lookup.

        Lookup order: L1 → L2 → L3 (storage)

        Args:
            key: Entity key

        Returns:
            Entity or None

        Raises:
            ValueError: If key is invalid
        """
        # Input validation
        if not key:
            raise ValueError("Key cannot be empty or None")

        if not isinstance(key, str):
            raise ValueError(f"Key must be a string, got {type(key).__name__}")

        # Sanitize key for cache safety
        key = key.strip()
        if len(key) > 255:  # Reasonable limit for keys
            raise ValueError(f"Key too long: {len(key)} characters (max: 255)")

        global _cache_hits, _cache_misses
        cache_key = self._cache_key(key)

        # L1: In-memory cache
        if self.cache_strategy != CacheStrategy.NONE:
            cached = await self._l1_cache.get(cache_key, ttl=self.ttl)
            if cached is not None:
                _cache_hits += 1
                return cached

        # L2: Redis cache
        if self._redis is not None and self.cache_strategy != CacheStrategy.NONE:
            try:
                cached = await self._get_from_redis(cache_key)
                if cached is not None:
                    # Populate L1
                    await self._l1_cache.set(cache_key, cached)
                    _cache_hits += 1
                    return cached
            except Exception as e:
                logger.debug(f"L2 cache miss: {e}")

        # L3: Primary storage
        _cache_misses += 1

        entity = await self._fetch_from_storage(key)

        # Populate caches on read (READ_THROUGH)
        if entity is not None and self.cache_strategy == CacheStrategy.READ_THROUGH:
            await self._populate_caches(cache_key, entity)

        return entity

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set entity with cache-aware write.

        Args:
            key: Entity key
            value: Entity to store
            ttl: Optional TTL override
        """
        cache_key = self._cache_key(key)
        ttl = ttl or self.ttl

        # Write to primary storage
        await self._write_to_storage(key, value)

        # Update caches based on strategy
        if self.cache_strategy == CacheStrategy.WRITE_THROUGH:
            # Immediate cache update
            await self._populate_caches(cache_key, value, ttl)

        elif self.cache_strategy == CacheStrategy.WRITE_BEHIND:
            # Async cache update
            asyncio.create_task(self._populate_caches(cache_key, value, ttl))

        elif self.cache_strategy == CacheStrategy.INVALIDATE:
            # Invalidate caches
            await self._invalidate_caches(cache_key)

    async def delete(self, key: str) -> bool:
        """Delete entity and invalidate caches.

        Args:
            key: Entity key

        Returns:
            True if deleted
        """
        cache_key = self._cache_key(key)

        # Delete from storage
        deleted = await self._delete_from_storage(key)

        # Invalidate caches
        if deleted:
            await self._invalidate_caches(cache_key)

        return deleted

    async def exists(self, key: str) -> bool:
        """Check if entity exists.

        Args:
            key: Entity key

        Returns:
            True if exists
        """
        # Check cache first
        entity = await self.get(key)
        return entity is not None

    # ========== Cache Management ==========

    async def _populate_caches(
        self,
        cache_key: str,
        value: T,
        ttl: int | None = None,
    ) -> None:
        """Populate L1 and L2 caches.

        Args:
            cache_key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        ttl = ttl or self.ttl

        # L1: In-memory
        await self._l1_cache.set(cache_key, value)

        # L2: Redis
        if self._redis is not None:
            try:
                await self._set_to_redis(cache_key, value, ttl)
            except Exception as e:
                logger.debug(f"L2 cache write failed: {e}")

    async def _invalidate_caches(self, cache_key: str) -> None:
        """Invalidate L1 and L2 caches.

        Args:
            cache_key: Cache key to invalidate
        """
        # L1: In-memory
        await self._l1_cache.delete(cache_key)

        # L2: Redis
        if self._redis is not None:
            try:
                await self._redis.delete(cache_key)
            except Exception as e:
                logger.debug(f"L2 cache invalidation failed: {e}")

    # ========== Redis Operations (L2) ==========

    async def _get_from_redis(self, key: str) -> T | None:
        """Get value from Redis cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if self._redis is None:
            return None

        try:
            raw = await self._redis.get(key)
            if raw is not None:
                return await self._deserialize(raw)
        except Exception as e:
            logger.debug(f"Redis get failed: {e}")

        return None

    async def _set_to_redis(self, key: str, value: T, ttl: int) -> None:
        """Set value in Redis cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        if self._redis is None:
            return

        try:
            serialized = await self._serialize(value)
            await self._redis.set(key, serialized, ex=ttl)
        except Exception as e:
            logger.debug(f"Redis set[Any] failed: {e}")

    # ========== Storage Operations (L3) - Override in Subclasses ==========

    @abstractmethod
    async def _fetch_from_storage(self, key: str) -> T | None:
        """Fetch entity from primary storage.

        Override in subclass to implement storage-specific logic.

        Args:
            key: Entity key

        Returns:
            Entity or None
        """
        ...

    @abstractmethod
    async def _write_to_storage(self, key: str, value: T) -> None:
        """Write entity to primary storage.

        Override in subclass to implement storage-specific logic.

        Args:
            key: Entity key
            value: Entity to store
        """
        ...

    @abstractmethod
    async def _delete_from_storage(self, key: str) -> bool:
        """Delete entity from primary storage.

        Override in subclass to implement storage-specific logic.

        Args:
            key: Entity key

        Returns:
            True if deleted
        """
        ...

    # ========== Serialization - Override if Needed ==========

    async def _serialize(self, value: T) -> str:
        """Serialize value for caching.

        Default: JSON serialization via Pydantic if available.
        Override for custom serialization.

        Args:
            value: Value to serialize

        Returns:
            Serialized string
        """
        import json

        # Try Pydantic model_dump_json
        if hasattr(value, "model_dump_json"):
            return str(value.model_dump_json())

        # Try Pydantic dict[str, Any]
        if hasattr(value, "model_dump"):
            return json.dumps(value.model_dump())

        # Fallback to standard JSON
        return json.dumps(value, default=str)

    async def _deserialize(self, data: str) -> T:
        """Deserialize value from cache.

        Override for custom deserialization.

        Args:
            data: Serialized data

        Returns:
            Deserialized value
        """
        import json
        from typing import cast

        return cast(T, json.loads(data))


class SQLAlchemyRepositoryMixin(Generic[T]):
    """Mixin for SQLAlchemy-based repository implementations.

    Provides standard CRUD operations using SQLAlchemy async sessions.
    Reduces boilerplate in repository implementations.

    Usage:
        class MyRepository(BaseRepository[MyModel], SQLAlchemyRepositoryMixin[MyModel]):
            _model_class = MyModel  # Set in subclass

            def __init__(self, db_session: AsyncSession, ...):
                self.db_session = db_session
                super().__init__(...)

    This mixin requires:
        - self.db_session: AsyncSession
        - self._model_class: Type[T] - the SQLAlchemy model class
        - Model must have an 'id' column as UUID primary key
    """

    db_session: Any  # AsyncSession
    _model_class: type[T]

    async def _fetch_from_storage(self, key: str) -> T | None:
        """Fetch entity from CockroachDB/PostgreSQL.

        Args:
            key: Entity ID (UUID string)

        Returns:
            Entity or None
        """
        try:
            from uuid import UUID as PyUUID

            from sqlalchemy import select

            entity_id = PyUUID(key)
            stmt = select(self._model_class).where(self._model_class.id == entity_id)  # type: ignore[attr-defined]
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"{self._model_class.__name__} fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: T) -> None:
        """Write entity to CockroachDB/PostgreSQL.

        Args:
            key: Entity ID (UUID string)
            value: Entity to store
        """
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"{self._model_class.__name__} write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete entity from CockroachDB/PostgreSQL.

        Args:
            key: Entity ID (UUID string)

        Returns:
            True if deleted
        """
        try:
            from uuid import UUID as PyUUID

            from sqlalchemy import select

            entity_id = PyUUID(key)
            stmt = select(self._model_class).where(self._model_class.id == entity_id)  # type: ignore[attr-defined]
            result = await self.db_session.execute(stmt)
            entity = result.scalar_one_or_none()

            if entity is not None:
                await self.db_session.delete(entity)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"{self._model_class.__name__} delete failed: {e}")
            return False


__all__ = [
    "BaseRepository",
    "CacheStrategy",
    "SQLAlchemyRepositoryMixin",
]
