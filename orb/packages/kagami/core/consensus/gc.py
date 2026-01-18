"""Garbage collection for old etcd keys with expired TTLs.

Prevents key space growth by cleaning up completed tasks, old quorum votes, etc.
Created October 2025 as part of etcd operational improvements.
"""

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class EtcdGarbageCollector:
    """Garbage collector for old etcd keys."""

    def __init__(self, interval: float = 3600.0) -> None:  # Run every hour
        """Initialize garbage collector.

        Args:
            interval: Collection interval in seconds (default 1 hour)
        """
        self.interval = interval
        self._running = False
        self._gc_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start garbage collection loop."""
        if self._running:
            return

        self._running = True
        self._gc_task = asyncio.create_task(self._gc_loop())
        logger.info("✅ etcd garbage collector started")

    async def stop(self) -> None:
        """Stop garbage collection loop."""
        self._running = False
        if self._gc_task:
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass
        logger.info("etcd garbage collector stopped")

    async def _gc_loop(self) -> None:
        """Background garbage collection loop."""
        from kagami.core.consensus.etcd_client import get_etcd_client_pool

        while self._running:
            try:
                await asyncio.sleep(self.interval)

                logger.info("🗑️  Running etcd garbage collection...")

                try:
                    pool = await get_etcd_client_pool()
                except Exception as e:
                    logger.warning(f"etcd pool unavailable, skipping GC: {e}")
                    continue

                total_deleted = 0

                # Run cleanup operations with individual error handling
                # to avoid one failure breaking the entire GC run
                try:
                    with pool.get_client(timeout=10.0) as client:
                        deleted = await self._cleanup_completed_tasks(client)
                        total_deleted += deleted
                except Exception as e:
                    logger.warning(f"Task cleanup failed: {e}")

                try:
                    with pool.get_client(timeout=10.0) as client:
                        deleted = await self._cleanup_old_quorums(client)
                        total_deleted += deleted
                except Exception as e:
                    logger.warning(f"Quorum cleanup failed: {e}")

                logger.info(f"✅ Garbage collection complete: {total_deleted} keys deleted")

                # Emit metric
                try:
                    from kagami_observability.metrics import REGISTRY, Counter

                    if not hasattr(REGISTRY, "_etcd_gc_keys_deleted_total"):
                        REGISTRY._etcd_gc_keys_deleted_total = Counter(
                            "kagami_etcd_gc_keys_deleted_total",
                            "Total keys deleted by garbage collector",
                            registry=REGISTRY,
                        )
                    gc_counter = REGISTRY._etcd_gc_keys_deleted_total
                    gc_counter.inc(total_deleted)
                except Exception:
                    pass

            except asyncio.CancelledError:
                raise  # Re-raise to properly handle shutdown
            except Exception as e:
                logger.error(f"Garbage collection error: {e}")

    async def _cleanup_completed_tasks(self, client: Any) -> int:
        """Cleanup completed tasks older than 24 hours.

        Returns:
            Number of keys deleted
        """
        try:
            import json

            loop = asyncio.get_running_loop()
            # NOTE: Use consistent "kagami:" prefix (no leading slash)
            # to match actual key patterns used throughout the codebase
            prefix = "kagami:tasks:completed:"
            cutoff = time.time() - 86400  # 24 hours ago

            # Get all completed tasks
            completed = await loop.run_in_executor(None, lambda: list(client.get_prefix(prefix)))

            deleted = 0
            for value, metadata in completed:
                try:
                    data = json.loads(value.decode())
                    if data.get("completed_at", 0) < cutoff:
                        # Delete old task
                        key = metadata.key.decode()
                        await loop.run_in_executor(None, client.delete, key)
                        deleted += 1
                except Exception:
                    continue

            if deleted > 0:
                logger.info(f"Deleted {deleted} old completed tasks")

            return deleted

        except Exception as e:
            logger.debug(f"Failed to cleanup completed tasks: {e}")
            return 0

    async def _cleanup_old_quorums(self, client: Any) -> int:
        """Cleanup old quorum votes older than 1 hour.

        Returns:
            Number of keys deleted
        """
        try:
            import json

            loop = asyncio.get_running_loop()
            # NOTE: Use consistent "kagami:" prefix (no leading slash)
            # to match actual key patterns used throughout the codebase
            prefix = "kagami:quorum:"
            cutoff = time.time() - 3600  # 1 hour ago

            # Get all quorums
            quorums = await loop.run_in_executor(None, lambda: list(client.get_prefix(prefix)))

            deleted = 0
            for value, metadata in quorums:
                try:
                    data = json.loads(value.decode())
                    created_at = data.get("created_at") or data.get("timestamp", 0)
                    if created_at < cutoff:
                        # Delete old quorum
                        key = metadata.key.decode()
                        await loop.run_in_executor(None, client.delete, key)
                        deleted += 1
                except Exception:
                    continue

            if deleted > 0:
                logger.info(f"Deleted {deleted} old quorum keys")

            return deleted

        except Exception as e:
            logger.debug(f"Failed to cleanup old quorums: {e}")
            return 0


# Global GC instance
_gc: EtcdGarbageCollector | None = None


async def start_etcd_gc() -> None:
    """Start etcd garbage collector."""
    global _gc

    if _gc is None:
        _gc = EtcdGarbageCollector()

    await _gc.start()


async def stop_etcd_gc() -> None:
    """Stop etcd garbage collector."""
    global _gc

    if _gc:
        await _gc.stop()
