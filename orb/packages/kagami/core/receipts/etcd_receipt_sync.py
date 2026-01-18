"""Cross-instance receipt synchronization via etcd.

Enables multiple K os instances to share receipts for collective learning
without centralized coordination.

## Architecture

```
Instance A (edge)          Instance B (cloud)         Instance C (research)
    │                           │                           │
    ├─ Emit receipt             │                           │
    ├─ Publish to etcd ─────────┼───────────────────────────┤
    │                           │                           │
    │                       Watch etcd                  Watch etcd
    │                           │                           │
    │                       Receive receipt            Receive receipt
    │                       Store locally              Store locally
    │                       Learn from it              Learn from it
```

## Key Properties

1. **No Central Server**: etcd provides distributed coordination
2. **Eventual Consistency**: All instances eventually see all receipts
3. **Idempotency-Safe**: Receipts deduplicated by correlation_id
4. **Privacy-Preserving**: Only metadata shared, not raw data
5. **Rate Limited**: Prevents flooding (100/s per instance)

## Integration

```python
from kagami.core.receipts.etcd_receipt_sync import EtcdReceiptSync

# Initialize on startup
sync = EtcdReceiptSync()
await sync.start()

# Automatically called by UnifiedReceiptFacade.emit()
await sync.publish_receipt(receipt)

# Watch for receipts from other instances
async for receipt in sync.watch_receipts():
    # Process cross-instance receipt
    await handle_peer_receipt(receipt)
```
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from kagami.core.caching.redis_keys import RedisKeys
from kagami.core.task_registry import get_task_registry

logger = logging.getLogger(__name__)


class EtcdReceiptSync:
    """Cross-instance receipt synchronization via etcd.

    Attributes:
        instance_id: This instance's unique ID
        enabled: Whether sync is enabled (requires etcd)
        rate_limit: Max receipts/second to publish
        ttl: Receipt TTL in etcd (default: 300s)
    """

    def __init__(
        self,
        instance_id: str | None = None,
        rate_limit: float = 100.0,
        ttl: int = 300,
    ) -> None:
        """Initialize etcd receipt sync.

        Args:
            instance_id: Unique instance ID (auto-generated if None)
            rate_limit: Max receipts/second to publish
            ttl: Receipt TTL in seconds
        """
        self.instance_id = instance_id or self._generate_instance_id()
        self.rate_limit = rate_limit
        self.ttl = ttl

        self._etcd_client = None
        self._enabled = False
        self._watch_task: asyncio.Task | None = None
        self._replay_task: asyncio.Task | None = None
        self._running = False
        self._publish_count = 0
        self._last_publish_time = time.time()

        # Rate limiting
        self._rate_window_start = time.time()
        self._rate_window_count = 0

        # Deduplication cache
        self._recent_max = 4096
        self._recent_receipts: deque[str] = deque()
        self._recent_index: set[str] = set()

        # Thread pool for watch_receipts() generator
        self._watch_executor: ThreadPoolExecutor | None = None
        self._watch_future = None
        self._watch_queue: asyncio.Queue | None = None
        self._watch_stop_event: threading.Event | None = None

        logger.info(
            f"Initialized EtcdReceiptSync for instance {self.instance_id} "
            f"(rate_limit={rate_limit}/s, ttl={ttl}s)"
        )

    def _generate_instance_id(self) -> str:
        """Generate unique instance ID."""
        import os
        import socket
        import uuid

        hostname = socket.gethostname()
        pid = os.getpid()
        unique = uuid.uuid4().hex[:8]
        return f"kagami-{hostname}-{pid}-{unique}"

    async def _ensure_etcd(self) -> bool:
        """Ensure etcd client is available."""
        if self._etcd_client is not None:
            return True  # type: ignore[unreachable]

        try:
            from kagami.core.consensus import get_etcd_client

            self._etcd_client = get_etcd_client()
            self._enabled = True
            return True

        except Exception as e:
            logger.warning(f"etcd unavailable for receipt sync: {e}")
            self._enabled = False
            return False

    async def start(self) -> bool:
        """Start receipt synchronization.

        Returns:
            True if started successfully
        """
        if not await self._ensure_etcd():
            logger.info("Receipt sync disabled (etcd unavailable)")
            return False

        if self._running:
            logger.info("Receipt sync already running")
            return True

        self._running = True

        # Register background tasks with TaskRegistry to prevent unbounded task creation
        registry = get_task_registry()

        # Create and register watch task
        self._watch_task = asyncio.create_task(self._watch_loop(), name="etcd_receipt_watch")
        if not registry.register_task(self._watch_task, "etcd_receipt_watch"):
            # Task limit exceeded - cancel and fail
            self._watch_task.cancel()
            self._running = False
            self._watch_task = None
            raise RuntimeError(
                "🚨 CRITICAL: Cannot start receipt watch - task limit exceeded. "
                "System may be experiencing task leak."
            )

        # Create and register replay task
        self._replay_task = asyncio.create_task(self._replay_loop(), name="etcd_receipt_replay")
        if not registry.register_task(self._replay_task, "etcd_receipt_replay"):
            # Task limit exceeded - cancel both tasks and fail
            self._replay_task.cancel()
            if self._watch_task:
                self._watch_task.cancel()
            self._running = False
            self._watch_task = None
            self._replay_task = None
            raise RuntimeError(
                "🚨 CRITICAL: Cannot start receipt replay - task limit exceeded. "
                "System may be experiencing task leak."
            )

        logger.info(f"📡 Started receipt sync for instance {self.instance_id}")

        # Emit metric
        try:
            from kagami_observability.metrics import _gauge

            sync_status = _gauge(
                "kagami_receipt_sync_status",
                "Receipt sync status (1=active, 0=inactive)",
                ["instance"],
            )
            sync_status.labels(instance=self.instance_id).set(1)
        except Exception as e:
            logger.debug(f"Optional component unavailable: {e}")

        return True

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop receipt synchronization and cleanup threads.

        Args:
            timeout: Maximum time to wait for cleanup (seconds)
        """
        self._running = False

        # Signal watch_receipts() generator to stop
        if self._watch_stop_event:
            self._watch_stop_event.set()

        # Send sentinel to queue to unblock consumer
        if self._watch_queue:
            try:
                self._watch_queue.put_nowait(None)
            except asyncio.QueueFull as e:
                logger.debug(f"Queue full during shutdown: {e}")

        # Cancel async tasks
        for task in (self._watch_task, self._replay_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._watch_task = None
        self._replay_task = None

        # Wait for watch thread to complete
        if self._watch_future:
            try:  # type: ignore[unreachable]
                # Use asyncio.wait_for to enforce timeout
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self._watch_future.result, timeout
                    ),
                    timeout=timeout,
                )
            except TimeoutError:
                logger.warning(f"Watch thread did not complete within {timeout}s timeout")
            except Exception as e:
                logger.debug(f"Watch thread shutdown error: {e}")
            finally:
                self._watch_future = None

        # Shutdown executor
        if self._watch_executor:
            try:
                self._watch_executor.shutdown(wait=True, timeout=timeout)  # type: ignore[call-arg]
            except Exception as e:
                logger.debug(f"Executor shutdown error: {e}")
            finally:
                self._watch_executor = None

        # Clear queue and stop event
        self._watch_queue = None
        self._watch_stop_event = None

        logger.info(f"Stopped receipt sync for instance {self.instance_id}")

        # Emit metric
        try:
            from kagami_observability.metrics import _gauge

            sync_status = _gauge(
                "kagami_receipt_sync_status",
                "Receipt sync status",
                ["instance"],
            )
            sync_status.labels(instance=self.instance_id).set(0)
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows publishing.

        Implements token bucket algorithm for smooth rate limiting.

        Returns:
            True if under rate limit, False if rate limited
        """
        now = time.time()

        # Reset window if > 1 second passed
        if now - self._rate_window_start >= 1.0:
            self._rate_window_start = now
            self._rate_window_count = 0

        # Check limit
        if self._rate_window_count >= self.rate_limit:
            # Rate limited - emit metric
            try:
                from kagami_observability.metrics import _counter

                rate_limited = _counter(
                    "kagami_receipt_sync_rate_limited_total",
                    "Receipt publishes blocked by rate limit",
                    ["instance"],
                )
                rate_limited.labels(instance=self.instance_id).inc()
            except Exception as e:
                logger.debug(f"Metric recording failed: {e}")
                # Metrics are non-critical

            return False

        self._rate_window_count += 1
        return True

    async def publish_receipt(self, receipt: dict[str, Any]) -> bool:
        """Publish receipt to etcd for cross-instance sync.

        Args:
            receipt: Receipt dict[str, Any] with correlation_id

        Returns:
            True if published successfully
        """
        if not self._enabled:
            return False

        # Rate limit check
        if not self._check_rate_limit():
            logger.debug("Receipt publish rate limited")

            try:
                from kagami_observability.metrics import _counter

                rate_limited = _counter(
                    "kagami_receipt_sync_rate_limited_total",
                    "Receipt publishes blocked by rate limit",
                )
                rate_limited.inc()
            except Exception as e:
                logger.debug(f"Metric recording failed: {e}")
                # Metrics are non-critical

            return False

        try:
            correlation_id = receipt.get("correlation_id")
            if not correlation_id:
                logger.warning("Receipt missing correlation_id, cannot sync")
                return False

            # Key format: kagami:receipts:{instance_id}:{correlation_id}
            key = RedisKeys.receipt_with_instance(self.instance_id, correlation_id)

            # Add instance_id to receipt
            receipt_with_instance = {
                **receipt,
                "from_instance": self.instance_id,
                "synced_at": time.time(),
            }

            # Publish to etcd with TTL
            value = json.dumps(receipt_with_instance).encode()

            # Use lease for TTL
            if self._etcd_client is None:
                # etcd unavailable - silently skip (expected in single-instance mode)
                logger.debug("etcd client unavailable, skipping receipt sync")
                return False

            lease = self._etcd_client.lease(self.ttl)  # type: ignore
            self._etcd_client.put(key, value, lease=lease)

            self._publish_count += 1

            logger.debug(f"Published receipt {correlation_id} from instance {self.instance_id}")

            # Emit metric
            try:
                from kagami_observability.metrics import _counter

                published = _counter(
                    "kagami_receipt_sync_published_total",
                    "Receipts published for cross-instance sync",
                    ["from_instance"],
                )
                published.labels(from_instance=self.instance_id).inc()
            except Exception as e:
                logger.debug(f"Metric recording failed: {e}")
                # Metrics are non-critical

            return True

        except Exception as e:
            # Only log as error if it's an unexpected exception
            err_msg = str(e) if str(e) else type(e).__name__
            logger.debug(f"Failed to publish receipt: {err_msg}")
            return False

    async def _watch_loop(self) -> None:
        """Watch etcd for receipts from other instances."""
        prefix = RedisKeys.receipt_prefix()
        backoff = 1.0
        cancel_func = None  # Track cancel function for cleanup

        while self._running:
            try:
                if self._etcd_client is None:
                    # etcd unavailable - wait and retry
                    logger.debug("etcd client unavailable for receipt watch, retrying...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    continue

                logger.info(f"Watching etcd for receipts (prefix: {prefix})")  # type: ignore[unreachable]
                events_iterator, cancel_func = self._etcd_client.watch_prefix(prefix)

                # etcd3 watch returns synchronous blocking generator
                # Run in thread pool to avoid blocking event loop
                loop = asyncio.get_running_loop()

                def process_events() -> int:
                    """Process events synchronously in thread pool."""
                    events_count = 0
                    for event in events_iterator:
                        if not self._running:
                            break
                        try:
                            # Skip empty events
                            if not event.value:
                                continue

                            receipt_json = event.value.decode()
                            if not receipt_json.strip():
                                continue

                            receipt = json.loads(receipt_json)
                            from_instance = receipt.get("from_instance")
                            if from_instance == self.instance_id:
                                continue
                            # Queue for async processing with captured loop
                            asyncio.run_coroutine_threadsafe(
                                self._handle_peer_receipt(receipt), loop
                            )
                            events_count += 1
                        except Exception as e:
                            logger.debug(f"Error processing receipt event: {e}")
                            continue
                    return events_count

                # Run in thread pool to avoid blocking
                events_processed = await asyncio.to_thread(process_events)

                if events_processed > 0:
                    backoff = 1.0  # reset if we successfully processed events

            except asyncio.CancelledError:
                logger.info("Receipt watch cancelled")
                # Properly cancel the etcd watch to release gRPC resources
                if cancel_func:
                    try:  # type: ignore[unreachable]
                        cancel_func()
                        logger.debug("etcd watch cancelled successfully")
                    except Exception as e:
                        logger.debug(f"Error cancelling etcd watch: {e}")
                raise

            except Exception as e:
                # Only log as debug - etcd unavailable is expected in single-instance mode
                err_msg = str(e) if str(e) else type(e).__name__
                logger.debug(f"Receipt watch error: {err_msg}")
                # Cancel current watch before retry
                if cancel_func:
                    try:  # type: ignore[unreachable]
                        cancel_func()
                    except Exception:
                        pass
                    cancel_func = None

                try:
                    from kagami_observability.metrics import _counter

                    failures = _counter(
                        "kagami_receipt_sync_watch_failures_total",
                        "Receipt sync watch loop failures",
                        ["instance"],
                    )
                    failures.labels(instance=self.instance_id).inc()
                except Exception as e:
                    logger.debug(f"Metric recording failed: {e}")
                    # Metrics are non-critical
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _replay_loop(self) -> None:
        """Periodically replay receipts to ensure learning stays in sync."""
        interval = max(30.0, self.ttl / 2)
        while self._running:
            try:
                await self._replay_existing_receipts()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug(f"Receipt replay loop error: {exc}")
                await asyncio.sleep(interval)

    async def _replay_existing_receipts(self) -> int:
        """Fetch existing etcd receipts to backfill Redis/learning."""
        if not self._enabled or self._etcd_client is None:
            return 0

        loop = asyncio.get_running_loop()  # type: ignore[unreachable]
        prefix = RedisKeys.receipt_prefix()

        try:
            entries = await loop.run_in_executor(
                None, lambda: list(self._etcd_client.get_prefix(prefix))
            )
        except Exception as exc:
            logger.debug(f"Receipt replay fetch failed: {exc}")
            return 0

        replayed = 0
        for value, _metadata in entries:
            try:
                receipt = json.loads(value.decode())
            except Exception:
                continue
            if receipt.get("from_instance") == self.instance_id:
                continue
            if await self._handle_peer_receipt(receipt, replayed=True):
                replayed += 1

        if replayed:
            logger.info(f"Replayed {replayed} receipts from etcd backlog")
        return replayed

    async def force_replay(self) -> int:
        """Public hook for triggering backlog replay (used by API)."""
        return await self._replay_existing_receipts()

    def _dedup_key(self, receipt: dict[str, Any]) -> str | None:
        correlation_id = receipt.get("correlation_id")
        phase = receipt.get("phase") or "unknown"
        timestamp = receipt.get("ts") or receipt.get("synced_at")
        if not correlation_id:
            return None
        if isinstance(timestamp, int | float):
            ts_val = float(timestamp)
            if ts_val > 1e12:
                ts_val = ts_val / 1000.0
            timestamp = f"{ts_val:.6f}"
        return f"{correlation_id}:{phase}:{timestamp}"

    def _seen_recent(self, key: str | None) -> bool:
        if not key:
            return False
        if key in self._recent_index:
            return True
        self._recent_receipts.append(key)
        self._recent_index.add(key)
        if len(self._recent_receipts) > self._recent_max:
            old = self._recent_receipts.popleft()
            self._recent_index.discard(old)
        return False

    async def _handle_peer_receipt(self, receipt: dict[str, Any], replayed: bool = False) -> bool:
        """Handle receipt from peer instance.

        Args:
            receipt: Receipt from another instance
            replayed: Whether this came from backlog replay
        """
        from_instance = receipt.get("from_instance", "unknown")
        correlation_id = receipt.get("correlation_id", "unknown")

        dedup_key = self._dedup_key(receipt)
        if self._seen_recent(dedup_key):
            logger.debug(
                "Skipping duplicate receipt %s from %s (replayed=%s)",
                correlation_id,
                from_instance,
                replayed,
            )
            return False

        logger.debug(f"Received receipt {correlation_id} from instance {from_instance}")

        # Store in local Redis for learning (ephemeral)
        try:
            from kagami.core.receipts.redis_storage import get_redis_receipt_storage

            storage = get_redis_receipt_storage()
            await storage.store(receipt)

        except Exception as e:
            logger.error(f"Failed to store peer receipt in Redis: {e}")
            try:
                from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="peer_receipt_redis_failed").inc()
            except Exception as e:
                logger.debug(f"Metric recording failed: {e}")
                # Metrics are non-critical

        # Store in Weaviate for semantic search (persistent)
        # This enables cross-instance learning via similarity search
        try:
            from kagami.core.services.storage_routing import get_storage_router

            router = get_storage_router()
            await router.store_receipt_to_weaviate(receipt)
            logger.debug(f"Stored peer receipt {correlation_id} to Weaviate for semantic search")

        except Exception as e:
            logger.debug(f"Failed to store peer receipt in Weaviate: {e}")

        # Emit metric
        try:
            from kagami_observability.metrics import _counter

            received = _counter(
                "kagami_receipt_sync_received_total",
                "Receipts received from other instances",
                ["from_instance", "to_instance"],
            )
            received.labels(
                from_instance=from_instance,
                to_instance=self.instance_id,
            ).inc()
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

        # Lag metric
        try:
            ts = receipt.get("synced_at") or receipt.get("ts")
            lag_seconds = None
            if isinstance(ts, int | float):
                ts_val = float(ts)
                if ts_val > 1e12:
                    ts_val = ts_val / 1000.0
                lag_seconds = max(0.0, time.time() - ts_val)
            if lag_seconds is not None:
                from kagami_observability.metrics import _histogram

                lag_metric = _histogram(
                    "kagami_receipt_sync_lag_seconds",
                    "Lag between publication and peer receipt processing",
                    ["from_instance", "to_instance"],
                )
                lag_metric.labels(
                    from_instance=from_instance, to_instance=self.instance_id
                ).observe(lag_seconds)
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

        # Publish to event bus for learning systems
        try:
            from kagami.core.events import get_unified_bus

            await get_unified_bus().publish(
                "receipts.peer_received",
                {
                    "from_instance": from_instance,
                    "correlation_id": correlation_id,
                    "receipt": receipt,
                },
            )
        except Exception:
            pass

        return True

    async def watch_receipts(self) -> AsyncIterator[dict[str, Any]]:
        """Watch for receipts from other instances.

        Yields:
            Receipts from peer instances
        """
        if not self._enabled:
            logger.debug("Receipt sync not enabled")
            return

        if self._etcd_client is None:
            logger.debug("etcd client unavailable for watch_receipts")
            return

        # Initialize executor if needed (lazy initialization)
        if self._watch_executor is None:  # type: ignore[unreachable]
            self._watch_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="etcd_watch_receipts"
            )

        # Use a queue to bridge sync thread -> async generator
        self._watch_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        self._watch_stop_event = threading.Event()
        etcd_client = self._etcd_client  # Capture for thread

        def producer() -> None:
            """Producer function running in thread pool."""
            try:
                prefix = RedisKeys.receipt_prefix()
                if etcd_client is None:
                    return
                events_iterator, cancel = etcd_client.watch_prefix(prefix)

                try:
                    for event in events_iterator:
                        if (
                            self._watch_stop_event is None
                            or self._watch_stop_event.is_set()
                            or not self._running
                        ):
                            cancel()
                            break

                        try:
                            if not event.value:
                                continue

                            receipt_json = event.value.decode()
                            if not receipt_json.strip():
                                continue

                            receipt = json.loads(receipt_json)
                            from_instance = receipt.get("from_instance")

                            # Skip own receipts
                            if from_instance == self.instance_id:
                                continue

                            if self._watch_queue:
                                loop.call_soon_threadsafe(self._watch_queue.put_nowait, receipt)
                        except Exception as e:
                            logger.debug(f"Error parsing receipt: {e}")

                finally:
                    # Ensure watch is cancelled
                    try:
                        cancel()
                    except Exception:
                        pass

            except Exception as e:
                if self._watch_queue:
                    loop.call_soon_threadsafe(self._watch_queue.put_nowait, e)

        # Submit producer to executor (not daemon thread)
        self._watch_future = self._watch_executor.submit(producer)

        try:
            while self._running and self._watch_queue:
                item = await self._watch_queue.get()

                # Sentinel value signals shutdown
                if item is None:
                    logger.debug("Watch receipts received shutdown sentinel")
                    break

                if isinstance(item, Exception):
                    logger.error(f"Watch error: {item}")
                    try:
                        from kagami_observability.metrics.receipts import (
                            RECEIPT_WRITE_ERRORS_TOTAL,
                        )

                        RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="etcd_watch_error").inc()
                    except Exception as e:
                        logger.debug(f"Metric recording failed: {e}")
                        # Metrics are non-critical
                    break

                yield item
        finally:
            # Signal thread to stop
            if self._watch_stop_event:
                self._watch_stop_event.set()


# Global instance
_etcd_sync: EtcdReceiptSync | None = None


def get_etcd_receipt_sync() -> EtcdReceiptSync:
    """Get or create global etcd receipt sync."""
    global _etcd_sync

    if _etcd_sync is None:
        import os

        instance_id = os.getenv("KAGAMI_INSTANCE_ID")
        _etcd_sync = EtcdReceiptSync(instance_id=instance_id)

    return _etcd_sync


__all__ = ["EtcdReceiptSync", "get_etcd_receipt_sync"]
