"""Redis Connection Pool Monitoring.

Monitors Redis connection pool health and emits metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class RedisPoolMonitor:
    """Monitor Redis connection pool health."""

    def __init__(self) -> None:
        """Initialize Redis pool monitor."""
        self._last_update = 0.0
        self._update_interval = 10.0  # Update every 10 seconds

    def update_metrics(self) -> None:
        """Update pool metrics for all Redis clients."""
        current_time = time.time()

        # Rate limit updates
        if current_time - self._last_update < self._update_interval:
            return

        self._last_update = current_time

        try:
            from kagami_observability.metrics.infrastructure import update_redis_pool_stats

            from kagami.core.caching.redis.factory import RedisClientFactory

            pool_stats = RedisClientFactory.get_pool_stats()

            for client_key, stats in pool_stats.items():
                # Extract purpose from key (format: "purpose:async:decode")
                purpose = client_key.split(":")[0] if ":" in client_key else client_key

                if "error" not in stats:
                    update_redis_pool_stats(purpose, stats)

                    # Log warnings if pool is stressed
                    if "max_connections" in stats and "in_use_connections" in stats:
                        max_conn = stats["max_connections"]
                        in_use = len(stats["in_use_connections"])
                        if max_conn and in_use >= max_conn * 0.9:
                            logger.warning(
                                f"Redis pool '{purpose}' stressed: {in_use}/{max_conn} connections in use"
                            )

        except Exception as e:
            logger.debug(f"Failed to update Redis pool metrics: {e}")

    def check_health(self) -> dict[str, Any]:
        """Check Redis pool health across all clients.

        Returns:
            Health status dict[str, Any]
        """
        try:
            from kagami.core.caching.redis.factory import RedisClientFactory

            pool_stats = RedisClientFactory.get_pool_stats()

            # Aggregate health across all clients
            total_clients = len(pool_stats)
            healthy_clients = sum(1 for stats in pool_stats.values() if "error" not in stats)

            health_score = healthy_clients / max(1, total_clients)

            return {
                "healthy": health_score > 0.7,
                "health_score": health_score,
                "total_clients": total_clients,
                "healthy_clients": healthy_clients,
                "pool_stats": pool_stats,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }


def get_redis_pool_monitor() -> RedisPoolMonitor:
    """Get singleton Redis pool monitor.

    Returns:
        RedisPoolMonitor instance
    """
    global _redis_pool_monitor
    if _redis_pool_monitor is None:
        _redis_pool_monitor = RedisPoolMonitor()
    return _redis_pool_monitor


_redis_pool_monitor: RedisPoolMonitor | None = None

__all__ = ["RedisPoolMonitor", "get_redis_pool_monitor"]
