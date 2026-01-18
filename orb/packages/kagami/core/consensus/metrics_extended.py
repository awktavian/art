"""Extended metrics for etcd operations.

Provides comprehensive observability beyond basic operation counts.
Created October 2025 as part of etcd monitoring improvements.
"""

import asyncio
import logging
from typing import Any

from kagami_observability.metrics.core import REGISTRY, Gauge

from kagami.core.caching.redis_keys import RedisKeys

logger = logging.getLogger(__name__)

# Cache for dynamically created metrics
_metrics_cache: dict[str, Any] = {}


class EtcdMetricsCollector:
    """Collects extended etcd metrics for comprehensive monitoring."""

    def __init__(self) -> None:
        self._collecting = False
        self._collection_task: asyncio.Task[None] | None = None
        self._collection_interval = 30.0  # 30s

    async def start_collection(self) -> None:
        """Start background metrics collection."""
        if self._collecting:
            return

        self._collecting = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info("✅ etcd metrics collector started")

    async def stop_collection(self) -> None:
        """Stop background metrics collection."""
        self._collecting = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("etcd metrics collector stopped")

    async def _collection_loop(self) -> None:
        """Background task for periodic metrics collection."""
        from kagami.core.consensus.etcd_client import get_etcd_client_pool

        while self._collecting:
            try:
                await asyncio.sleep(self._collection_interval)

                # Collect metrics
                pool = await get_etcd_client_pool()

                with pool.get_client() as client:
                    await self._collect_cluster_metrics(client)
                    await self._collect_key_metrics(client)
                    await self._collect_lease_metrics(client)

            except Exception as e:
                logger.debug(f"Metrics collection error: {e}")

    async def _collect_cluster_metrics(self, client: Any) -> None:
        """Collect cluster-level metrics."""
        try:
            # Get cluster status
            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(None, client.status)

            # Database size
            if "_etcd_db_size_bytes" not in _metrics_cache:
                _metrics_cache["_etcd_db_size_bytes"] = Gauge(
                    "kagami_etcd_db_size_bytes", "etcd database size in bytes", registry=REGISTRY
                )
            db_size_gauge = _metrics_cache["_etcd_db_size_bytes"]
            db_size_gauge.set(status.db_size)

            # Raft index (for compaction lag monitoring)
            if "_etcd_raft_index" not in _metrics_cache:
                _metrics_cache["_etcd_raft_index"] = Gauge(
                    "kagami_etcd_raft_index", "Current raft index", registry=REGISTRY
                )
                _metrics_cache["_etcd_raft_applied_index"] = Gauge(
                    "kagami_etcd_raft_applied_index", "Applied raft index", registry=REGISTRY
                )
            raft_index_gauge = _metrics_cache["_etcd_raft_index"]
            raft_applied_gauge = _metrics_cache["_etcd_raft_applied_index"]
            raft_index_gauge.set(status.raft_index)
            raft_applied_gauge.set(
                status.raft_applied_index
                if hasattr(status, "raft_applied_index")
                else status.raft_index
            )

            # Compaction lag (important for performance monitoring)
            compaction_lag = 0
            if hasattr(status, "raft_applied_index"):
                compaction_lag = status.raft_index - status.raft_applied_index

            if "_etcd_compaction_lag" not in _metrics_cache:
                _metrics_cache["_etcd_compaction_lag"] = Gauge(
                    "kagami_etcd_compaction_lag",
                    "Raft compaction lag (index difference)",
                    registry=REGISTRY,
                )
            compaction_lag_gauge = _metrics_cache["_etcd_compaction_lag"]
            compaction_lag_gauge.set(compaction_lag)

        except Exception as e:
            logger.debug(f"Cluster metrics collection failed: {e}")

    async def _collect_key_metrics(self, client: Any) -> None:
        """Collect key space metrics by prefix."""
        try:
            # Count keys by namespace prefix
            namespaces = {
                "receipts": RedisKeys.receipt_prefix(),
                "leader": "kagami:leader:",
                "locks": "kagami:locks:",
                "tasks_pending": "kagami:tasks:pending:",
                "tasks_claimed": "kagami:tasks:claimed:",
                "quorum": "kagami:quorum:",
                "services": "kagami:agents:",
                "federated": "kagami:federated:",
                "mesh": "kagami:mesh:instances:",
                "migrations": "kagami:migrations:",
            }

            if "_etcd_key_count" not in _metrics_cache:
                _metrics_cache["_etcd_key_count"] = Gauge(
                    "kagami_etcd_key_count",
                    "Number of keys by subsystem",
                    ["subsystem"],
                    registry=REGISTRY,
                )

            key_count_gauge = _metrics_cache["_etcd_key_count"]
            loop = asyncio.get_running_loop()

            for subsystem, prefix in namespaces.items():
                try:

                    def _get_keys(p: str) -> list[Any]:
                        return list(client.get_prefix(p))

                    keys = await loop.run_in_executor(None, _get_keys, prefix)
                    key_count_gauge.labels(subsystem=subsystem).set(len(keys))
                except Exception:
                    logger.debug(f"Failed to count keys for prefix {prefix}")

        except Exception as e:
            logger.debug(f"Key metrics collection failed: {e}")

    async def _collect_lease_metrics(self, client: Any) -> None:
        """Collect lease metrics."""
        try:
            # Get all leases
            loop = asyncio.get_running_loop()

            def _get_leases() -> list[Any]:
                return list(client.leases)

            leases = await loop.run_in_executor(None, _get_leases)

            if "_etcd_lease_count" not in _metrics_cache:
                _metrics_cache["_etcd_lease_count"] = Gauge(
                    "kagami_etcd_lease_count", "Number of active leases", registry=REGISTRY
                )
            lease_count_gauge = _metrics_cache["_etcd_lease_count"]
            lease_count_gauge.set(len(leases))

        except Exception as e:
            logger.debug(f"Lease metrics collection failed: {e}")


# Global collector instance
_metrics_collector: EtcdMetricsCollector | None = None


async def start_etcd_metrics_collection() -> None:
    """Start etcd metrics collection."""
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = EtcdMetricsCollector()

    await _metrics_collector.start_collection()


async def stop_etcd_metrics_collection() -> None:
    """Stop etcd metrics collection."""
    global _metrics_collector

    if _metrics_collector:
        await _metrics_collector.stop_collection()
