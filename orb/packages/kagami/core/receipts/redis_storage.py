"""Redis-based receipt storage for cross-process sharing.

Enables background agents to learn from operations across all processes.
"""

import json
import logging
import time
from typing import Any

from kagami.core.caching.redis_keys import RedisKeys

logger = logging.getLogger(__name__)


class RedisReceiptStorage:
    """Store receipts in Redis for cross-process access."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        """Initialize Redis receipt storage.

        Args:
            ttl_seconds: TTL for receipt keys (default: 300 = 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._redis: Any | None = None
        self._available = False
        # In-memory fallback ring buffer (best-effort)
        self._mem_buffer: list[dict[str, Any]] = []
        self._mem_max: int = 1000
        self._mem_ttl_seconds: int = ttl_seconds
        self._last_redis_ok: bool = False

    async def _ensure_redis(self) -> Any:
        """Lazy initialization of Redis client."""
        if self._redis is not None:
            return self._redis  # Defensive/fallback code

        try:
            from kagami.core.caching.redis import RedisClientFactory

            self._redis = RedisClientFactory.get_client(
                purpose="default",
                async_mode=True,
                decode_responses=True,
            )
            self._available = True
            # Transition: if Redis just became available, attempt to flush in-memory buffer
            if not self._last_redis_ok:
                try:
                    await self._flush_mem_to_redis()
                    # Emit reconnect event (best-effort)
                    try:
                        from kagami.core.events import get_unified_bus as _get_bus

                        bus = _get_bus()
                        await bus.publish(
                            "system.redis.reconnected",
                            {
                                "component": "receipts",
                                "ts": int(time.time() * 1000),
                            },
                        )
                    except Exception as e:
                        logger.debug(f"Failed to publish reconnect event: {e}")
                except Exception as e:
                    logger.debug(f"Failed to flush memory buffer to Redis: {e}")
            self._last_redis_ok = True
            return self._redis
        except Exception as e:
            logger.warning(f"Redis not available for receipts: {e}")
            try:
                from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="redis_unavailable").inc()
            except Exception:
                pass
            self._available = False
            self._last_redis_ok = False
            return None

    async def store(self, receipt: dict[str, Any]) -> bool:
        """Store receipt in Redis.

        Args:
            receipt: Receipt dict[str, Any] with correlation_id and phase

        Returns:
            True if stored, False if Redis unavailable
        """
        try:
            redis = await self._ensure_redis()

            correlation_id = receipt.get("correlation_id", "")
            phase = receipt.get("phase", "")

            if not correlation_id:
                return False

            # Create key: kagami:receipts:{correlation}:{phase}
            # Allows multiple receipts per correlation (PLAN/EXECUTE/VERIFY)
            key = (
                RedisKeys.receipt(correlation_id, phase)
                if phase
                else RedisKeys.receipt(correlation_id, str(int(time.time() * 1000)))
            )

            # Ensure timestamp (ms) for TTL filtering
            try:
                if not receipt.get("ts"):
                    receipt["ts"] = int(time.time() * 1000)
            except Exception as e:
                logger.debug(f"Failed to set[Any] timestamp on receipt: {e}")

            stored_any = False

            # Store in Redis when available (dedup via set[Any])
            try:
                if redis is not None:
                    rid = self._compose_id(receipt)
                    if rid:
                        # Dedup: Add to set[Any] with TTL (CRITICAL FIX: prevent unbounded growth)
                        dedup_key = RedisKeys.receipt_ids()
                        added = await redis.sadd(dedup_key, rid)
                        if int(added) == 1:
                            # Set TTL on dedup set[Any] (2x TTL for safety margin)
                            await redis.expire(dedup_key, self.ttl_seconds * 2)
                            # Store receipt with TTL
                            await redis.setex(key, self.ttl_seconds, json.dumps(receipt))
                            # Add to list[Any] with TTL (CRITICAL FIX: prevent unbounded growth)
                            list_key = RedisKeys.receipt_list()
                            await redis.lpush(list_key, json.dumps(receipt))
                            await redis.ltrim(list_key, 0, self._mem_max - 1)
                            # Set TTL on list[Any] (2x TTL for safety margin)
                            await redis.expire(list_key, self.ttl_seconds * 2)
                            stored_any = True
                    else:
                        # Fallback without dedup id
                        await redis.setex(key, self.ttl_seconds, json.dumps(receipt))
                        list_key = RedisKeys.receipt_list()
                        await redis.lpush(list_key, json.dumps(receipt))
                        await redis.ltrim(list_key, 0, self._mem_max - 1)
                        # Set TTL on list[Any] (CRITICAL FIX: prevent unbounded growth)
                        await redis.expire(list_key, self.ttl_seconds * 2)
                        stored_any = True
            except Exception as e:
                logger.warning(f"Failed to store receipt in Redis: {e}")
                try:
                    from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                    RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="redis_store_failed").inc()
                except Exception:
                    pass

            # Always append to in-memory fallback (best-effort)
            try:
                self._append_mem(receipt)
                stored_any = True
            except Exception as e:
                logger.debug(f"Failed to append receipt to memory buffer: {e}")

            return stored_any

        except Exception as e:
            logger.warning(f"Failed to store receipt in Redis: {e}")
            try:
                from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="redis_store_exception").inc()
            except Exception:
                pass
            return False

    async def query_since(self, since_timestamp: float) -> list[dict[str, Any]]:
        """Query receipts created after a given timestamp.

        Args:
            since_timestamp: Unix timestamp (seconds)

        Returns:
            List of receipt dicts
        """
        try:
            receipts: list[dict[str, Any]] = []

            # Redis path (best-effort)
            try:
                redis = await self._ensure_redis()
                if redis is not None:
                    receipts_json = await redis.lrange(RedisKeys.receipt_list(), 0, -1)
                    for receipt_json in receipts_json:
                        try:
                            r = json.loads(receipt_json)
                            ts_ms = r.get("ts", 0)
                            ts_seconds = ts_ms / 1000.0 if ts_ms else 0
                            if ts_seconds >= since_timestamp:
                                receipts.append(r)
                        except Exception:
                            continue
            except Exception as e:
                logger.warning(f"Redis receipts query failed: {e}")
                try:
                    from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                    RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="redis_query_failed").inc()
                except Exception:
                    pass

            # Merge with in-memory fallback (avoid duplicates by correlation_id+phase+ts)
            try:
                memory_results = [
                    r
                    for r in list(self._mem_buffer)
                    if (r.get("ts", 0) / 1000.0) >= since_timestamp
                ]
                if memory_results:
                    # Deduplicate
                    seen: set[tuple[Any, ...]] = set()
                    merged: list[dict[str, Any]] = []
                    for r in receipts + memory_results:
                        key = (
                            r.get("correlation_id"),
                            r.get("phase"),
                            r.get("ts"),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        merged.append(r)
                    receipts = merged
            except Exception as e:
                logger.debug(f"Failed to merge memory buffer with Redis results: {e}")

            return receipts

        except Exception as e:
            logger.warning(f"Failed to query receipts from Redis: {e}")
            try:
                from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="redis_query_exception").inc()
            except Exception:
                pass
            return []

    async def query_time_range(self, start_ts: float, end_ts: float) -> list[dict[str, Any]]:
        """Query receipts within a time range.

        Args:
            start_ts: Start timestamp (seconds)
            end_ts: End timestamp (seconds)

        Returns:
            List of receipt dicts
        """
        # Reuse query_since for start_ts, then filter by end_ts
        receipts = await self.query_since(start_ts)
        return [r for r in receipts if (r.get("ts", 0) / 1000.0) <= end_ts]

    @property
    def available(self) -> bool:
        """Check if Redis storage is available."""
        return self._available

    # ---------------- In-memory fallback helpers ----------------

    def _append_mem(self, receipt: dict[str, Any]) -> None:
        try:
            # Enforce TTL by dropping old entries
            now_s = time.time()
            ttl_s = float(self._mem_ttl_seconds)
            # Ensure ts
            ts_ms = receipt.get("ts") or int(now_s * 1000)
            receipt["ts"] = ts_ms
            # Append
            self._mem_buffer.append(dict(receipt))
            # Trim size
            if len(self._mem_buffer) > self._mem_max:
                self._mem_buffer = self._mem_buffer[-self._mem_max :]
            # Prune expired
            cutoff = now_s - ttl_s
            self._mem_buffer = [r for r in self._mem_buffer if (r.get("ts", 0) / 1000.0) >= cutoff]
        except Exception as e:
            logger.debug(f"Failed to append to memory buffer: {e}")

    def _compose_id(self, receipt: dict[str, Any]) -> str | None:
        try:
            cid = str(receipt.get("correlation_id") or "").strip()
            phase = str(receipt.get("phase") or "").strip()
            ts = int(receipt.get("ts") or 0)
            if not cid or not phase or not ts:
                return None
            return f"{cid}:{phase}:{ts}"
        except Exception:
            return None

    async def _flush_mem_to_redis(self) -> None:
        """Best-effort sync of in-memory receipts to Redis once available.

        Uses etcd to take a short-lived lock to avoid multi-instance stampede.
        Relies on Redis set[Any]-based dedup to prevent duplicates regardless of locks.
        """
        # Nothing to flush
        if not self._mem_buffer:
            return
        # Try to acquire a soft lock via etcd (optional)
        lease_id: int | None = None
        try:
            from kagami.core.consensus.etcd_client import (
                get_etcd_client,
            )

            etcd = get_etcd_client()
            lease_id = etcd.create_lease(15)
            lock_key = RedisKeys.flush_lock()
            if etcd.get(lock_key) is None:
                etcd.put(lock_key, b"1", lease=lease_id)
                locked = True
            else:
                locked = False
        except Exception:
            locked = True  # proceed relying on Redis dedup

        if not locked:
            return

        try:
            redis = await self._ensure_redis()
            if redis is None:
                return
            # Flush a snapshot of current buffer
            snapshot = list(self._mem_buffer)
            for r in snapshot:
                try:
                    rid = self._compose_id(r)
                    if rid:
                        added = await redis.sadd(RedisKeys.receipt_ids(), rid)
                        if int(added) != 1:
                            continue
                    key = (
                        RedisKeys.receipt(r.get("correlation_id", ""), r.get("phase", ""))
                        if r.get("phase")
                        else RedisKeys.receipt(
                            r.get("correlation_id", ""), str(int(time.time() * 1000))
                        )
                    )
                    await redis.setex(key, self.ttl_seconds, json.dumps(r))
                    await redis.lpush(RedisKeys.receipt_list(), json.dumps(r))
                    await redis.ltrim(RedisKeys.receipt_list(), 0, self._mem_max - 1)
                except Exception:
                    continue
            # Emit flushed event
            try:
                from kagami.core.events import get_unified_bus

                await get_unified_bus().publish(
                    "system.receipts.flushed",
                    {
                        "count": len(snapshot),
                        "ts": int(time.time() * 1000),
                    },
                )
            except Exception as e:
                logger.debug(f"Failed to publish flush event: {e}")
        finally:
            # Release etcd lease if acquired
            try:
                if lease_id is not None:
                    from kagami.core.consensus.etcd_client import (
                        get_etcd_client,
                    )

                    get_etcd_client().revoke_lease(lease_id)
            except Exception as e:
                logger.debug(f"Failed to revoke etcd lease: {e}")


# Global instance
_redis_storage: RedisReceiptStorage | None = None


def get_redis_receipt_storage() -> RedisReceiptStorage:
    """Get or create the global Redis receipt storage."""
    global _redis_storage

    if _redis_storage is None:
        _redis_storage = RedisReceiptStorage()

    return _redis_storage


__all__ = ["RedisReceiptStorage", "get_redis_receipt_storage"]
