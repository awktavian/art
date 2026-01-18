from __future__ import annotations

import logging
import time
from typing import Any

import socketio
from kagami_api.socketio.broadcaster import register_event_broadcaster, unregister_event_broadcaster

logger = logging.getLogger(__name__)

# Global Socket.IO server reference for cross-module access
_SIO: socketio.AsyncServer | None = None

# Cache for socketio health to reduce overhead on frequent health checks
_HEALTH_CACHE: dict[str, Any] | None = None
_HEALTH_CACHE_EXPIRY: float = 0.0
_HEALTH_CACHE_TTL: float = 2.0  # 2 second TTL


def set_socketio_server(sio: socketio.AsyncServer | None) -> None:
    """Set the global Socket.IO server instance."""
    global _SIO
    _SIO = sio
    if sio is not None:
        register_event_broadcaster(sio)
    else:
        unregister_event_broadcaster()


def get_socketio_server() -> socketio.AsyncServer | None:
    """Get the global Socket.IO server instance, if initialized."""
    return _SIO


def get_socketio_health() -> dict[str, Any]:
    """Expose Socket.IO readiness data for health probes.

    Cached with 2s TTL to reduce overhead on frequent health checks.
    """
    global _HEALTH_CACHE, _HEALTH_CACHE_EXPIRY

    # Check cache
    now = time.time()
    if _HEALTH_CACHE is not None and now < _HEALTH_CACHE_EXPIRY:
        return _HEALTH_CACHE

    # Cache miss or expired - recompute
    server = get_socketio_server()
    if server is None:
        result = {"ready": False, "connected_clients": 0, "namespaces": []}
    else:
        try:
            rooms = getattr(server.manager, "rooms", {})
            namespaces = list(rooms.keys())
            connected = sum(len(members) for members in rooms.values() if isinstance(members, dict))
        except Exception:
            namespaces = []
            connected = 0

        result = {
            "ready": True,
            "connected_clients": int(connected),
            "namespaces": namespaces,
        }

    # Update cache
    _HEALTH_CACHE = result
    _HEALTH_CACHE_EXPIRY = now + _HEALTH_CACHE_TTL

    return result


async def broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast an event on the root namespace using Socket.IO (best-effort)."""
    try:
        if _SIO is not None:
            await _SIO.emit(event_type, data, namespace="/")
    except Exception:
        pass


def get_rooms_summary(namespace: str = "/") -> list[dict[str, Any]]:
    """Return a summary of rooms for diagnostics and UI."""
    try:
        if _SIO is None:
            return []
        ns_rooms = getattr(_SIO.manager, "rooms", {}).get(namespace, {})
        items: list[dict[str, Any]] = []
        for room_id, sids in ns_rooms.items():
            # Skip per-sid implicit rooms
            try:
                if isinstance(room_id, str) and room_id.startswith("sid:"):
                    continue
            except Exception:
                pass
            members_count = len(sids) if isinstance(sids, set | list) else 0
            items.append({"room_id": room_id, "members": members_count})
        return items
    except Exception:
        return []


__all__ = [
    "_SIO",
    "broadcast_event",
    "get_rooms_summary",
    "get_socketio_health",
    "get_socketio_server",
    "set_socketio_server",
]
