"""Database Connection Pool Monitoring.

Monitors database connection pool health and emits metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class DBPoolMonitor:
    """Monitor database connection pool health."""

    def __init__(self, engine: Any, database_name: str = "kagami") -> None:
        """Initialize pool monitor.

        Args:
            engine: SQLAlchemy engine
            database_name: Database name for metrics
        """
        self.engine = engine
        self.database_name = database_name
        self._last_update = 0.0
        self._update_interval = 10.0  # Update every 10 seconds

    def update_metrics(self) -> None:
        """Update pool metrics (call periodically)."""
        current_time = time.time()

        # Rate limit updates
        if current_time - self._last_update < self._update_interval:
            return

        self._last_update = current_time

        try:
            pool = self.engine.pool

            stats = {
                "size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "waits": 0,  # Not directly available, would need event tracking
            }

            from kagami_observability.metrics.infrastructure import update_db_pool_stats

            update_db_pool_stats(self.database_name, stats)

            # Log warnings if pool is stressed
            if stats["checked_out"] >= stats["size"] * 0.9:
                logger.warning(
                    f"DB pool stressed: {stats['checked_out']}/{stats['size']} connections in use"
                )

        except Exception as e:
            logger.debug(f"Failed to update DB pool metrics: {e}")

    def check_health(self) -> dict[str, Any]:
        """Check pool health.

        Returns:
            Health status dict[str, Any]
        """
        try:
            pool = self.engine.pool

            size = pool.size()
            checked_out = pool.checkedout()
            overflow = pool.overflow()

            # Health score: 1.0 = healthy, 0.0 = saturated
            utilization = checked_out / max(1, size)
            health_score = 1.0 - min(1.0, utilization)

            return {
                "healthy": health_score > 0.5,
                "health_score": health_score,
                "size": size,
                "checked_out": checked_out,
                "overflow": overflow,
                "utilization": utilization,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }


__all__ = ["DBPoolMonitor"]
