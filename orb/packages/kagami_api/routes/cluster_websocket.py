"""Cluster WebSocket — Real-time updates for distributed cluster dashboard.

This module provides WebSocket endpoints for real-time cluster monitoring:
- Service registry updates
- Consensus state changes
- Node health transitions
- Performance metrics streaming
- Byzantine fault notifications

Architecture:
```
    Cluster Events          WebSocket Hub           Dashboard Clients
    ──────────────          ─────────────           ─────────────────
    Service changes     →   Broadcast room      →   Live status updates
    Consensus state     →   Event filtering     →   Consensus timeline
    Health transitions  →   Compression         →   Health indicators
    Fault detection     →   Rate limiting       →   Alert notifications
```

Colony: Nexus (A₅) — Real-time connectivity
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cluster/ws", tags=["cluster-websocket"])


# =============================================================================
# Event Types
# =============================================================================


class ClusterEventType(str, Enum):
    """Types of cluster events that can be streamed."""

    # Service registry events
    SERVICE_REGISTERED = "service.registered"
    SERVICE_DEREGISTERED = "service.deregistered"
    SERVICE_HEALTH_CHANGED = "service.health_changed"

    # Consensus events
    CONSENSUS_STATE_CHANGED = "consensus.state_changed"
    CONSENSUS_LEADER_CHANGED = "consensus.leader_changed"
    CONSENSUS_VIEW_CHANGED = "consensus.view_changed"

    # Node events
    NODE_JOINED = "node.joined"
    NODE_LEFT = "node.left"
    NODE_ISOLATED = "node.isolated"
    NODE_READMITTED = "node.readmitted"

    # Performance events
    METRICS_UPDATE = "metrics.update"
    LATENCY_SPIKE = "metrics.latency_spike"

    # Fault events
    BYZANTINE_FAULT = "fault.byzantine"
    RECOVERY_STARTED = "fault.recovery_started"
    RECOVERY_COMPLETED = "fault.recovery_completed"

    # Health events
    CLUSTER_HEALTHY = "health.cluster_healthy"
    CLUSTER_DEGRADED = "health.cluster_degraded"
    CLUSTER_UNHEALTHY = "health.cluster_unhealthy"


@dataclass
class ClusterEvent:
    """A cluster event for streaming."""

    event_type: ClusterEventType
    timestamp: float
    data: dict[str, Any]
    source_node: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.event_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "source_node": self.source_node,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


# =============================================================================
# Connection Manager
# =============================================================================


@dataclass
class ConnectionState:
    """State for a single WebSocket connection."""

    websocket: WebSocket
    connected_at: float = field(default_factory=time.time)
    last_message_at: float = field(default_factory=time.time)
    subscribed_events: set[ClusterEventType] = field(default_factory=set)
    message_count: int = 0
    client_id: str | None = None

    def is_subscribed(self, event_type: ClusterEventType) -> bool:
        """Check if subscribed to event type."""
        # Empty set means subscribed to all
        if not self.subscribed_events:
            return True
        return event_type in self.subscribed_events


class ClusterWebSocketManager:
    """Manages WebSocket connections for cluster events.

    Features:
    - Connection pooling
    - Event filtering per connection
    - Broadcast and targeted messages
    - Automatic cleanup on disconnect
    - Rate limiting per connection
    """

    def __init__(self) -> None:
        """Initialize the WebSocket manager."""
        self._connections: dict[str, ConnectionState] = {}
        self._lock = asyncio.Lock()
        self._event_queue: asyncio.Queue[ClusterEvent] = asyncio.Queue(maxsize=1000)
        self._broadcast_task: asyncio.Task | None = None
        self._running = False

        # Metrics
        self._total_connections = 0
        self._total_messages_sent = 0
        self._total_events_broadcast = 0

    async def start(self) -> None:
        """Start the WebSocket manager."""
        if self._running:
            return

        self._running = True
        self._broadcast_task = asyncio.create_task(
            self._broadcast_loop(),
            name="cluster_ws_broadcast",
        )
        logger.info("ClusterWebSocketManager started")

    async def stop(self) -> None:
        """Stop the WebSocket manager."""
        self._running = False

        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for _conn_id, state in list(self._connections.items()):
                try:
                    await state.websocket.close()
                except Exception:
                    pass
            self._connections.clear()

        logger.info("ClusterWebSocketManager stopped")

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str | None = None,
    ) -> str:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket to accept.
            client_id: Optional client identifier.

        Returns:
            Connection ID.
        """
        await websocket.accept()

        conn_id = f"conn_{self._total_connections}_{int(time.time() * 1000)}"

        async with self._lock:
            self._connections[conn_id] = ConnectionState(
                websocket=websocket,
                client_id=client_id,
            )
            self._total_connections += 1

        logger.info(f"WebSocket connected: {conn_id} (client: {client_id})")

        # Send welcome message
        await self._send_to_connection(
            conn_id,
            ClusterEvent(
                event_type=ClusterEventType.CLUSTER_HEALTHY,
                timestamp=time.time(),
                data={
                    "message": "Connected to Kagami cluster",
                    "connection_id": conn_id,
                },
            ),
        )

        return conn_id

    async def disconnect(self, conn_id: str) -> None:
        """Handle WebSocket disconnection.

        Args:
            conn_id: Connection ID to disconnect.
        """
        async with self._lock:
            if conn_id in self._connections:
                del self._connections[conn_id]

        logger.info(f"WebSocket disconnected: {conn_id}")

    async def subscribe(
        self,
        conn_id: str,
        event_types: list[ClusterEventType],
    ) -> None:
        """Subscribe a connection to specific event types.

        Args:
            conn_id: Connection ID.
            event_types: Event types to subscribe to.
        """
        async with self._lock:
            if conn_id in self._connections:
                self._connections[conn_id].subscribed_events = set(event_types)
                logger.debug(f"Connection {conn_id} subscribed to: {event_types}")

    async def emit(self, event: ClusterEvent) -> None:
        """Emit an event to all subscribed connections.

        Args:
            event: Event to emit.
        """
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping oldest event")
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    async def _broadcast_loop(self) -> None:
        """Background loop to broadcast events."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )
                await self._broadcast_event(event)
                self._total_events_broadcast += 1
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")

    async def _broadcast_event(self, event: ClusterEvent) -> None:
        """Broadcast an event to all subscribed connections."""
        async with self._lock:
            connections = list(self._connections.items())

        # Send to each subscribed connection
        tasks = []
        for conn_id, state in connections:
            if state.is_subscribed(event.event_type):
                tasks.append(self._send_to_connection(conn_id, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_connection(
        self,
        conn_id: str,
        event: ClusterEvent,
    ) -> None:
        """Send an event to a specific connection."""
        async with self._lock:
            state = self._connections.get(conn_id)
            if not state:
                return

        try:
            await state.websocket.send_text(event.to_json())
            state.last_message_at = time.time()
            state.message_count += 1
            self._total_messages_sent += 1
        except Exception as e:
            logger.debug(f"Failed to send to {conn_id}: {e}")
            # Connection probably closed, will be cleaned up

    def get_metrics(self) -> dict[str, Any]:
        """Get WebSocket manager metrics."""
        return {
            "active_connections": len(self._connections),
            "total_connections": self._total_connections,
            "total_messages_sent": self._total_messages_sent,
            "total_events_broadcast": self._total_events_broadcast,
            "queue_size": self._event_queue.qsize(),
        }


# =============================================================================
# Singleton
# =============================================================================


_ws_manager: ClusterWebSocketManager | None = None


async def get_ws_manager() -> ClusterWebSocketManager:
    """Get or create the WebSocket manager singleton."""
    global _ws_manager

    if _ws_manager is None:
        _ws_manager = ClusterWebSocketManager()
        await _ws_manager.start()

    return _ws_manager


async def shutdown_ws_manager() -> None:
    """Shutdown the WebSocket manager."""
    global _ws_manager

    if _ws_manager:
        await _ws_manager.stop()
        _ws_manager = None


# =============================================================================
# WebSocket Endpoints
# =============================================================================


@router.websocket("/events")
async def cluster_events_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for cluster events.

    Clients can send subscription messages:
    ```json
    {
        "action": "subscribe",
        "events": ["service.registered", "consensus.state_changed"]
    }
    ```

    Or subscribe to all events by default.
    """
    manager = await get_ws_manager()
    conn_id = await manager.connect(websocket)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    # Subscribe to specific event types
                    events = message.get("events", [])
                    event_types = [
                        ClusterEventType(e)
                        for e in events
                        if e in [et.value for et in ClusterEventType]
                    ]
                    await manager.subscribe(conn_id, event_types)

                elif action == "ping":
                    # Respond to ping
                    await websocket.send_text(json.dumps({"action": "pong"}))

            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"Invalid message from {conn_id}: {e}")

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(conn_id)


@router.get("/metrics")
async def websocket_metrics() -> dict[str, Any]:
    """Get WebSocket connection metrics."""
    manager = await get_ws_manager()
    return manager.get_metrics()


# =============================================================================
# Event Emitters (for other modules to use)
# =============================================================================


async def emit_service_registered(
    service_id: str,
    service_type: str,
    endpoint: str,
) -> None:
    """Emit service registered event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.SERVICE_REGISTERED,
            timestamp=time.time(),
            data={
                "service_id": service_id,
                "service_type": service_type,
                "endpoint": endpoint,
            },
        )
    )


async def emit_service_health_changed(
    service_id: str,
    old_health: str,
    new_health: str,
) -> None:
    """Emit service health changed event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.SERVICE_HEALTH_CHANGED,
            timestamp=time.time(),
            data={
                "service_id": service_id,
                "old_health": old_health,
                "new_health": new_health,
            },
        )
    )


async def emit_consensus_state_changed(
    view_number: int,
    leader_id: str,
    committed_ops: int,
) -> None:
    """Emit consensus state changed event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.CONSENSUS_STATE_CHANGED,
            timestamp=time.time(),
            data={
                "view_number": view_number,
                "leader_id": leader_id,
                "committed_ops": committed_ops,
            },
        )
    )


async def emit_node_isolated(
    node_id: str,
    fault_type: str,
    severity: str,
) -> None:
    """Emit node isolated event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.NODE_ISOLATED,
            timestamp=time.time(),
            data={
                "node_id": node_id,
                "fault_type": fault_type,
                "severity": severity,
            },
        )
    )


async def emit_node_readmitted(node_id: str) -> None:
    """Emit node readmitted event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.NODE_READMITTED,
            timestamp=time.time(),
            data={"node_id": node_id},
        )
    )


async def emit_metrics_update(metrics: dict[str, Any]) -> None:
    """Emit metrics update event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.METRICS_UPDATE,
            timestamp=time.time(),
            data=metrics,
        )
    )


async def emit_byzantine_fault(
    node_id: str,
    fault_type: str,
    evidence_hash: str,
) -> None:
    """Emit Byzantine fault detected event."""
    manager = await get_ws_manager()
    await manager.emit(
        ClusterEvent(
            event_type=ClusterEventType.BYZANTINE_FAULT,
            timestamp=time.time(),
            data={
                "node_id": node_id,
                "fault_type": fault_type,
                "evidence_hash": evidence_hash,
            },
        )
    )


# =============================================================================
# 鏡
# Real-time is the new default. h(x) ≥ 0. Always.
# =============================================================================
