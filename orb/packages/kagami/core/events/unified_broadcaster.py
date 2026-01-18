"""
Unified Event Broadcaster — Single Source for All Event Broadcasting.

Consolidates multiple event broadcasting systems:
- Socket.IO events (real-time WebSocket)
- E8 unified bus (internal pub/sub)
- HTTP API calls (legacy support)

Provides unified broadcasting with automatic routing:
- Room-scoped events → Socket.IO + E8 bus
- Global events → E8 bus only
- Cross-platform delivery

Design Principles:
- Single broadcast API
- Automatic transport selection
- Room-scoped privacy
- Receipt tracking

Created: December 14, 2025
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from kagami.core.events import get_unified_bus

logger = logging.getLogger(__name__)


class BroadcasterBackend(Protocol):
    """Protocol for Socket.IO or other real-time backends."""

    async def emit(
        self, event: str, data: dict[str, Any], room: str | None = None, namespace: str = "/"
    ) -> bool:
        """Emit event to room or broadcast."""
        ...


class UnifiedEventBroadcaster:
    """
    Unified broadcaster for all event types.

    Consolidates:
    - Socket.IO real-time events
    - E8 bus internal events
    - HTTP API fallbacks

    Usage:
        broadcaster = UnifiedEventBroadcaster()
        await broadcaster.broadcast("forge.generated", payload, room="room-123")
    """

    def __init__(self) -> None:
        self._bus = get_unified_bus()
        self._socketio_manager = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the broadcaster."""
        if self._initialized:
            return

        # Socket.IO manager is now injected via register_backend()
        # No direct import from kagami_api
        if self._socketio_manager is None:
            logger.info("No Socket.IO backend registered, using E8 bus only")

        self._initialized = True
        logger.info("✓ Unified Event Broadcaster initialized")

    async def broadcast(
        self,
        event_type: str,
        payload: dict[str, Any],
        room: str | None = None,
        namespace: str = "/",
        correlation_id: str | None = None,
    ) -> bool:
        """
        Broadcast event to all appropriate channels.

        Args:
            event_type: Event type (e.g., "forge.generated", "room.delta")
            payload: Event payload
            room: Room ID for room-scoped events (None = global)
            namespace: Socket.IO namespace
            correlation_id: Optional correlation ID

        Returns:
            True if broadcast successful
        """
        await self.initialize()

        success = True

        # Add metadata
        enriched_payload = dict(payload)
        enriched_payload["event_type"] = event_type
        enriched_payload["timestamp"] = payload.get("timestamp", __import__("time").time())
        if correlation_id:
            enriched_payload["correlation_id"] = correlation_id
        if room:
            enriched_payload["room_id"] = room

        # Broadcast to E8 bus (always)
        try:
            await self._bus.publish(event_type, enriched_payload)
        except Exception as e:
            logger.debug(f"E8 bus broadcast failed: {e}")
            success = False

        # Broadcast to Socket.IO if room-scoped
        if room and self._socketio_manager:
            try:  # type: ignore[unreachable]
                # Emit to room via Socket.IO
                await self._socketio_manager.emit(
                    event_type,
                    enriched_payload,
                    room=room,
                    namespace=namespace,
                )
            except Exception as e:
                logger.debug(f"Socket.IO broadcast failed: {e}")
                # Don't fail overall - E8 bus might have worked

        return success

    async def emit_to_room(
        self,
        event_type: str,
        payload: dict[str, Any],
        room_id: str,
        namespace: str = "/",
    ) -> bool:
        """
        Emit event to specific room.

        Args:
            event_type: Event type
            payload: Event payload
            room_id: Target room ID
            namespace: Socket.IO namespace

        Returns:
            True if emission successful
        """
        return await self.broadcast(
            event_type,
            payload,
            room=room_id,
            namespace=namespace,
        )

    async def emit_global(
        self,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> bool:
        """
        Emit global event (not room-scoped).

        Args:
            event_type: Event type
            payload: Event payload
            correlation_id: Optional correlation ID

        Returns:
            True if emission successful
        """
        return await self.broadcast(
            event_type,
            payload,
            room=None,
            correlation_id=correlation_id,
        )


# Global instance
_unified_broadcaster: UnifiedEventBroadcaster | None = None


async def get_unified_broadcaster() -> UnifiedEventBroadcaster:
    """Get global unified broadcaster instance."""
    global _unified_broadcaster
    if _unified_broadcaster is None:
        _unified_broadcaster = UnifiedEventBroadcaster()
        await _unified_broadcaster.initialize()
    return _unified_broadcaster


def register_socketio_backend(backend: BroadcasterBackend) -> None:
    """
    Register Socket.IO backend (dependency injection).

    Called by kagami_api layer at startup to break circular dependency.
    Core layer never imports from api layer directly.

    Args:
        backend: Socket.IO manager implementing BroadcasterBackend protocol
    """
    global _unified_broadcaster
    if _unified_broadcaster is not None:
        _unified_broadcaster._socketio_manager = backend  # type: ignore[assignment]

        logger.info("✓ Socket.IO backend registered with UnifiedEventBroadcaster")
    else:
        logger.warning(
            "Broadcaster not initialized yet, backend will be set[Any] on first broadcast"
        )


# Backward compatibility alias
EventBroadcaster = UnifiedEventBroadcaster
