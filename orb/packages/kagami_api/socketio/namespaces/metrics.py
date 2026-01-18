from __future__ import annotations

"""Socket.IO /metrics namespace for real-time system metrics streaming.

This namespace provides efficient real-time metrics updates to connected
clients using delta-only transmission — only changed metrics are sent
after the initial snapshot.

Events Emitted:
    - initial_snapshot: Full metrics snapshot on connect
    - metric_update: Delta updates (only changed metrics)

Architecture:
    Connect → Send initial snapshot → Start monitor task
                                   → Emit delta updates (1s interval)
                                   → Client disconnects → Task cancelled

Delta Efficiency:
    By tracking last values per client, we avoid sending unchanged metrics.
    This significantly reduces bandwidth for dashboards with many metrics.

Usage:
    >>> # Client-side (JavaScript)
    >>> socket = io('/metrics')
    >>> socket.on('initial_snapshot', (data) => {
    ...     initializeMetrics(data.metrics)
    ... })
    >>> socket.on('metric_update', (data) => {
    ...     updateMetrics(data.metrics)  // Only changed metrics
    ... })
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio  # Async I/O for monitor tasks
import logging  # Error and debug logging
from typing import Any  # Type hints

# =============================================================================
# INTERNAL IMPORTS
# =============================================================================
from kagami_api.socketio.namespaces.root import KagamiOSNamespace  # Base namespace

logger = logging.getLogger(__name__)


class MetricsNamespace(KagamiOSNamespace):
    """Socket.IO namespace for real-time metrics streaming.

    Provides efficient delta-only metrics updates to connected clients.
    Each client receives an initial snapshot, then periodic delta updates.

    Attributes:
        _monitor_tasks: Dict mapping session ID to monitor task.
        _last_values: Dict mapping session ID to last metric values (for delta).

    Events:
        initial_snapshot: Full metrics snapshot on connect.
        metric_update: Delta updates (only changed metrics).
    """

    def __init__(self) -> None:
        """Initialize metrics namespace with delta tracking."""
        super().__init__(namespace="/metrics")
        self._monitor_tasks: dict[str, asyncio.Task] = {}  # SID → monitor task
        self._last_values: dict[str, dict[str, float]] = {}  # SID → metric_name → value

    async def on_connect(  # type: ignore[no-untyped-def]
        self, sid: str, environ: dict[str, Any], auth: dict[str, Any] | None = None
    ):
        """Handle client connection to /metrics namespace.

        Sends initial metrics snapshot and starts monitor task for deltas.

        Args:
            sid: Socket.IO session ID.
            environ: WSGI environment dict.
            auth: Optional authentication data.

        Returns:
            True if connection allowed, False otherwise.
        """
        # Delegate to base class for auth
        result = await super().on_connect(sid, environ, auth)
        if not result:
            return False

        # Update metrics (best-effort)
        try:
            from kagami.observability.metrics import (
                SOCKETIO_CONNECTIONS_ACTIVE,
                SOCKETIO_CONNECTIONS_TOTAL,
            )

            SOCKETIO_CONNECTIONS_TOTAL.labels(namespace="/metrics", status="connected").inc()
            SOCKETIO_CONNECTIONS_ACTIVE.labels(namespace="/metrics").inc()
        except Exception:
            pass  # Metrics optional

        # Send initial snapshot
        await self._send_initial_snapshot(sid)

        # Start monitor task for delta updates
        task = asyncio.create_task(self._monitor_metrics(sid))
        self._monitor_tasks[sid] = task

        return True

    async def on_disconnect(self, sid: str) -> None:
        """Handle client disconnection from /metrics namespace.

        Cancels monitor task and cleans up delta tracking state.

        Args:
            sid: Socket.IO session ID.
        """
        # Delegate to base class
        await super().on_disconnect(sid)

        # Cancel monitor task
        if sid in self._monitor_tasks:
            task = self._monitor_tasks.pop(sid)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected

        # Clean up delta tracking state
        if sid in self._last_values:
            del self._last_values[sid]

        # Update metrics (best-effort)
        try:
            from kagami.observability.metrics import SOCKETIO_CONNECTIONS_ACTIVE

            SOCKETIO_CONNECTIONS_ACTIVE.labels(namespace="/metrics").dec()
        except Exception:
            pass  # Metrics optional

    async def _send_initial_snapshot(self, sid: str) -> None:
        """Send full metrics snapshot to newly connected client.

        Also initializes delta tracking state for this client.

        Args:
            sid: Socket.IO session ID.
        """
        try:
            from kagami.observability.metrics import get_prometheus_metrics

            metrics = get_prometheus_metrics()
            await self.emit(
                "initial_snapshot",
                {
                    "metrics": metrics,
                    "count": len(metrics),
                    "timestamp": asyncio.get_running_loop().time(),
                },
                room=sid,
            )
            # Initialize delta tracking with current values
            self._last_values[sid] = {m["name"]: float(m.get("value", 0.0) or 0.0) for m in metrics}  # type: ignore[index, attr-defined]
        except Exception as e:
            logger.error("[/metrics] Error sending initial snapshot: %s", e)

    async def _monitor_metrics(self, sid: str) -> None:
        """Background task that periodically emits delta metric updates.

        Only sends metrics that have changed since last emit.
        Runs every 1 second until client disconnects.

        Args:
            sid: Socket.IO session ID to emit to.
        """
        try:
            from kagami.observability.metrics import get_prometheus_metrics

            while True:
                try:
                    current = get_prometheus_metrics()
                    last = self._last_values.get(sid, {})

                    changes = []
                    for metric in current:
                        name = metric["name"]  # type: ignore[index]
                        value = float(metric.get("value", 0.0) or 0.0)  # type: ignore[attr-defined]
                        if name not in last or abs(last[name] - value) > 1e-9:
                            changes.append(metric)
                            last[name] = value

                    if changes:
                        await self.emit(
                            "metric_update",
                            {
                                "metrics": changes,
                                "count": len(changes),
                                "timestamp": asyncio.get_running_loop().time(),
                            },
                            room=sid,
                        )

                        try:
                            from kagami.observability.metrics import SOCKETIO_EVENTS_TOTAL

                            SOCKETIO_EVENTS_TOTAL.labels(
                                namespace="/metrics",
                                event_type="metric_update",
                                direction="outbound",
                            ).inc()
                        except Exception:
                            pass

                except Exception as e:
                    logger.error("[/metrics] Error collecting metrics: %s", e)

                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("[/metrics] Monitoring error for %s: %s", sid, e)

    async def on_subscribe(self, sid: str, data: dict[str, Any]) -> None:
        """Handle client subscription request with optional filters.

        Currently logs subscription request. Future: apply metric filters.

        Args:
            sid: Socket.IO session ID.
            data: Subscription data with optional filters.
        """
        logger.info("[/metrics] Client %s subscribed with filters: %s", sid, data)


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = ["MetricsNamespace"]
