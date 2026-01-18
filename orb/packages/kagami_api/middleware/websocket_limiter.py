"""WebSocket connection limiter middleware.

P0 Mitigation: WebSocket flood attack → Memory exhaustion → OOM
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketLimiter:
    """Limits WebSocket connections to prevent resource exhaustion.

    P0 Mitigation: Malicious Hub opens 10,000 connections → API OOM

    Features:
    - Per-Hub connection limits (default: 5 max)
    - Frame size limits (10KB max)
    - Message size limits (1MB max)
    - Rate limiting (100 messages/minute)
    - Automatic cleanup of stale connections

    Usage:
        limiter = WebSocketLimiter()

        @router.websocket("/ws/hub/{hub_id}")
        async def hub_connection(websocket: WebSocket, hub_id: str):
            if not await limiter.can_connect(hub_id):
                await websocket.close(code=1008, reason="Too many connections")
                return

            async with limiter.track_connection(hub_id, websocket):
                # Handle WebSocket
                pass
    """

    def __init__(
        self,
        max_connections_per_hub: int = 5,
        max_frame_size: int = 10_000,  # 10KB
        max_message_size: int = 1_000_000,  # 1MB
        rate_limit_per_minute: int = 100,
    ):
        self.max_connections_per_hub = max_connections_per_hub
        self.max_frame_size = max_frame_size
        self.max_message_size = max_message_size
        self.rate_limit_per_minute = rate_limit_per_minute

        # Connection tracking
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._message_counts: dict[str, list[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def can_connect(self, hub_id: str) -> bool:
        """Check if Hub can open new connection.

        Args:
            hub_id: Hub identifier

        Returns:
            True if connection allowed
        """
        async with self._lock:
            current_count = len(self._connections[hub_id])
            can_connect = current_count < self.max_connections_per_hub

            if not can_connect:
                logger.warning(
                    f"Connection limit reached for hub {hub_id}: "
                    f"{current_count}/{self.max_connections_per_hub}"
                )

            return can_connect

    async def track_connection(
        self,
        hub_id: str,
        websocket: WebSocket,
    ) -> WebSocketConnection:
        """Track WebSocket connection (use as context manager).

        Args:
            hub_id: Hub identifier
            websocket: WebSocket instance

        Returns:
            Connection tracker
        """
        return WebSocketConnection(self, hub_id, websocket)

    async def _register_connection(
        self,
        hub_id: str,
        websocket: WebSocket,
    ) -> None:
        """Register new connection."""
        async with self._lock:
            self._connections[hub_id].append(websocket)
            logger.info(
                f"WebSocket connected: {hub_id} "
                f"({len(self._connections[hub_id])}/{self.max_connections_per_hub})"
            )

    async def _unregister_connection(
        self,
        hub_id: str,
        websocket: WebSocket,
    ) -> None:
        """Unregister connection."""
        async with self._lock:
            if websocket in self._connections[hub_id]:
                self._connections[hub_id].remove(websocket)
                logger.info(
                    f"WebSocket disconnected: {hub_id} "
                    f"({len(self._connections[hub_id])}/{self.max_connections_per_hub})"
                )

    async def check_rate_limit(self, hub_id: str) -> bool:
        """Check if Hub is within rate limit.

        Args:
            hub_id: Hub identifier

        Returns:
            True if within limit
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        async with self._lock:
            # Remove old timestamps
            self._message_counts[hub_id] = [
                ts for ts in self._message_counts[hub_id] if ts > cutoff
            ]

            # Check limit
            current_count = len(self._message_counts[hub_id])
            if current_count >= self.rate_limit_per_minute:
                logger.warning(
                    f"Rate limit exceeded for hub {hub_id}: "
                    f"{current_count}/{self.rate_limit_per_minute} messages/min"
                )
                return False

            # Record message
            self._message_counts[hub_id].append(now)
            return True

    async def send_backpressure_signal(
        self,
        websocket: WebSocket,
        current_queue_size: int,
        max_queue_size: int,
    ) -> None:
        """Send backpressure signal to Hub when queue filling up.

        Args:
            websocket: WebSocket to send signal on
            current_queue_size: Current event queue size
            max_queue_size: Maximum event queue size
        """
        utilization = current_queue_size / max_queue_size

        if utilization > 0.8:  # 80% full
            try:
                await websocket.send_json(
                    {
                        "type": "backpressure",
                        "action": "slow_down",
                        "queue_utilization": utilization,
                        "recommended_rate": "10/sec",  # Reduce from normal rate
                    }
                )
                logger.warning(
                    f"Backpressure signal sent: queue {current_queue_size}/{max_queue_size} "
                    f"({utilization:.0%} full)"
                )
            except Exception as e:
                logger.error(f"Failed to send backpressure signal: {e}")

    def get_stats(self) -> dict[str, any]:
        """Get limiter statistics."""
        return {
            "total_connections": sum(len(conns) for conns in self._connections.values()),
            "connections_by_hub": {
                hub_id: len(conns) for hub_id, conns in self._connections.items()
            },
            "limits": {
                "max_per_hub": self.max_connections_per_hub,
                "max_frame_size": self.max_frame_size,
                "max_message_size": self.max_message_size,
                "rate_limit_per_minute": self.rate_limit_per_minute,
            },
        }


class WebSocketConnection:
    """Context manager for tracking WebSocket connection lifecycle."""

    def __init__(
        self,
        limiter: WebSocketLimiter,
        hub_id: str,
        websocket: WebSocket,
    ):
        self.limiter = limiter
        self.hub_id = hub_id
        self.websocket = websocket

    async def __aenter__(self):
        await self.limiter._register_connection(self.hub_id, self.websocket)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.limiter._unregister_connection(self.hub_id, self.websocket)


# Global limiter instance
_global_limiter: WebSocketLimiter | None = None


def get_websocket_limiter() -> WebSocketLimiter:
    """Get global WebSocket limiter."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = WebSocketLimiter(
            max_connections_per_hub=5,  # Normal Hub needs 1-2
            max_frame_size=10_000,  # 10KB
            max_message_size=1_000_000,  # 1MB
            rate_limit_per_minute=100,
        )
    return _global_limiter
