"""Unified IdempotencyStore - Single source of truth for idempotency state.

Consolidates:
- kagami_api/idempotency.py (HTTP middleware)
- kagami/core/idempotency/unified.py (core logic)
- kagami_api/idempotency_cache.py (response caching)

Design:
- Redis-first for cluster safety
- In-memory fallback for dev/test
- Single cleanup task (no per-request tasks)
- Unified key format: kagami:idem:{path}:{key}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyEntry:
    """Single idempotency entry."""

    key: str
    path: str
    created_at: float
    expires_at: float
    status_code: int | None = None
    response_body: dict[str, Any] | None = None
    replayed: bool = False

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class IdempotencyConfig:
    """Configuration for idempotency store."""

    default_ttl_seconds: int = 300
    max_response_bytes: int = 512 * 1024  # 512KB
    max_memory_entries: int = 10000
    cleanup_interval_seconds: float = 60.0
    redis_key_prefix: str = "kagami:idem"

    @classmethod
    def from_env(cls) -> IdempotencyConfig:
        """Load config from environment."""
        return cls(
            default_ttl_seconds=int(os.getenv("KAGAMI_IDEMPOTENCY_TTL", "300")),
            max_response_bytes=int(
                os.getenv("KAGAMI_IDEMPOTENCY_MAX_RESPONSE_BYTES", str(512 * 1024))
            ),
            max_memory_entries=int(os.getenv("KAGAMI_IDEMPOTENCY_MAX_ENTRIES", "10000")),
            cleanup_interval_seconds=float(os.getenv("KAGAMI_IDEMPOTENCY_CLEANUP_INTERVAL", "60")),
        )


class IdempotencyStore:
    """Unified idempotency store with Redis + in-memory fallback.

    Thread-safe, cluster-safe, single source of truth.
    """

    def __init__(self, config: IdempotencyConfig | None = None):
        self.config = config or IdempotencyConfig.from_env()

        # In-memory fallback (LRU with OrderedDict)
        self._memory: OrderedDict[str, IdempotencyEntry] = OrderedDict()
        self._memory_lock = asyncio.Lock()

        # Cleanup task state
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_running = False

        # Redis availability flag
        self._redis_available: bool | None = None
        self._redis_check_time: float = 0

    def _make_key(self, path: str, idempotency_key: str) -> str:
        """Create normalized cache key."""
        return f"{path}:{idempotency_key}"

    def _redis_key(self, normalized_key: str) -> str:
        """Create Redis key."""
        return f"{self.config.redis_key_prefix}:{normalized_key}"

    def _response_redis_key(self, normalized_key: str) -> str:
        """Create Redis key for response cache."""
        return f"{self.config.redis_key_prefix}:resp:{normalized_key}"

    async def _get_redis(self, check_available: bool = True) -> Any:
        """Get Redis client with availability caching."""
        if check_available:
            now = time.time()
            # Re-check availability every 30 seconds
            if self._redis_available is False and now - self._redis_check_time < 30:
                return None
            self._redis_check_time = now

        try:
            from typing import cast

            from kagami.core.caching.redis import RedisClientFactory

            client = RedisClientFactory.get_client(
                purpose="default", async_mode=True, decode_responses=True
            )
            self._redis_available = True
            return cast(Any, client)
        except Exception as e:
            logger.debug(f"Redis unavailable: {e}")
            self._redis_available = False
            return None

    async def check_and_acquire(
        self,
        path: str,
        idempotency_key: str,
        ttl_seconds: int | None = None,
    ) -> tuple[bool, IdempotencyEntry | None]:
        """Check if request is duplicate and acquire lock if not.

        Returns:
            (is_new, cached_entry):
            - (True, None) - New request, lock acquired
            - (False, entry) - Duplicate, entry contains cached response
        """
        normalized_key = self._make_key(path, idempotency_key)
        ttl = ttl_seconds or self.config.default_ttl_seconds
        now = time.time()

        # Try Redis first
        redis = await self._get_redis()
        if redis is not None:
            try:
                # Check for existing key
                existing = await redis.get(self._redis_key(normalized_key))

                if existing:
                    # Duplicate - check for cached response
                    response = await redis.get(self._response_redis_key(normalized_key))
                    entry = IdempotencyEntry(
                        key=normalized_key,
                        path=path,
                        created_at=now,
                        expires_at=now + ttl,
                        replayed=True,
                    )
                    if response:
                        try:
                            data = json.loads(response)
                            entry.status_code = data.get("status")
                            entry.response_body = data.get("body")
                        except Exception:
                            pass

                    self._emit_metric("duplicate")
                    return False, entry

                # New request - acquire lock
                ok = await redis.set(
                    self._redis_key(normalized_key),
                    "1",
                    ex=ttl,
                    nx=True,
                )

                if not ok:
                    # Race condition - someone else got there first
                    self._emit_metric("duplicate")
                    return False, IdempotencyEntry(
                        key=normalized_key,
                        path=path,
                        created_at=now,
                        expires_at=now + ttl,
                        replayed=True,
                    )

                self._emit_metric("accepted")
                return True, None

            except Exception as e:
                logger.debug(f"Redis idempotency check failed: {e}")
                # Fall through to in-memory

        # In-memory fallback
        async with self._memory_lock:
            existing = self._memory.get(normalized_key)

            if existing and not existing.is_expired:
                self._emit_metric("duplicate")
                return False, existing

            # Cleanup expired and enforce LRU limit
            await self._cleanup_memory_locked()

            # Create new entry
            entry = IdempotencyEntry(
                key=normalized_key,
                path=path,
                created_at=now,
                expires_at=now + ttl,
            )
            self._memory[normalized_key] = entry
            self._memory.move_to_end(normalized_key)

            self._emit_metric("accepted")
            return True, None

    async def store_response(
        self,
        path: str,
        idempotency_key: str,
        status_code: int,
        response_body: dict[str, Any] | None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store response for future replay.

        Only stores if response is under size limit.
        """
        if response_body is None:
            return

        try:
            serialized = json.dumps({"status": status_code, "body": response_body})
            if len(serialized.encode("utf-8")) > self.config.max_response_bytes:
                logger.debug(f"Response too large to cache: {len(serialized)} bytes")
                return
        except Exception as e:
            logger.debug(f"Failed to serialize response: {e}")
            return

        normalized_key = self._make_key(path, idempotency_key)
        ttl = ttl_seconds or self.config.default_ttl_seconds

        # Try Redis first
        redis = await self._get_redis()
        if redis is not None:
            try:
                await redis.setex(
                    self._response_redis_key(normalized_key),
                    ttl,
                    serialized,
                )
                return
            except Exception as e:
                logger.debug(f"Redis response cache failed: {e}")

        # In-memory fallback
        async with self._memory_lock:
            entry = self._memory.get(normalized_key)
            if entry:
                entry.status_code = status_code
                entry.response_body = response_body

    async def get_cached_response(
        self,
        path: str,
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]] | None:
        """Get cached response for replay.

        Returns:
            (status_code, response_body) or None if not cached
        """
        normalized_key = self._make_key(path, idempotency_key)

        # Try Redis first
        redis = await self._get_redis()
        if redis is not None:
            try:
                response = await redis.get(self._response_redis_key(normalized_key))
                if response:
                    data = json.loads(response)
                    return data.get("status", 200), data.get("body", {})
            except Exception as e:
                logger.debug(f"Redis response fetch failed: {e}")

        # In-memory fallback
        async with self._memory_lock:
            entry = self._memory.get(normalized_key)
            if entry and entry.status_code is not None and entry.response_body is not None:
                return entry.status_code, entry.response_body

        return None

    async def _cleanup_memory_locked(self) -> None:
        """Cleanup expired entries and enforce LRU limit. Must hold lock."""
        now = time.time()

        # Remove expired
        expired = [k for k, v in self._memory.items() if v.expires_at <= now]
        for k in expired:
            self._memory.pop(k, None)

        # LRU eviction
        while len(self._memory) >= self.config.max_memory_entries:
            oldest = next(iter(self._memory))
            self._memory.pop(oldest, None)

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        logger.info("Idempotency cleanup loop started")

        while self._cleanup_running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)

                async with self._memory_lock:
                    before = len(self._memory)
                    await self._cleanup_memory_locked()
                    after = len(self._memory)

                    if before != after:
                        logger.debug(f"Cleanup: removed {before - after} expired entries")

                # Update gauge metric
                try:
                    from kagami_observability.metrics import Gauge

                    gauge = Gauge(
                        "kagami_idempotency_active_keys",
                        "Number of active idempotency keys",
                    )
                    gauge.set(len(self._memory))
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(5)

        logger.info("Idempotency cleanup loop stopped")

    def ensure_cleanup_running(self) -> None:
        """Ensure cleanup loop is running."""
        if self._cleanup_running and self._cleanup_task and not self._cleanup_task.done():
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        self._cleanup_running = True
        self._cleanup_task = loop.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cleanup loop."""
        self._cleanup_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def _emit_metric(self, status: str) -> None:
        """Emit idempotency check metric."""
        try:
            from kagami_observability.metrics import IDEMPOTENCY_CHECKS_TOTAL

            IDEMPOTENCY_CHECKS_TOTAL.labels(status=status).inc()
        except Exception:
            pass


# Global singleton
_STORE: IdempotencyStore | None = None


def get_idempotency_store() -> IdempotencyStore:
    """Get the global idempotency store singleton."""
    global _STORE
    if _STORE is None:
        _STORE = IdempotencyStore()
    return _STORE


__all__ = [
    "IdempotencyConfig",
    "IdempotencyEntry",
    "IdempotencyStore",
    "get_idempotency_store",
]
