"""Socket.IO server public facade.

The implementation lives in `kagami_api.socketio.*`.
This module remains as a stable import path for the rest of the codebase.
"""

from __future__ import annotations

from kagami_api.socketio.app import create_socketio_app
from kagami_api.socketio.broadcaster import _SocketIOEventBroadcaster
from kagami_api.socketio.broadcaster import (
    register_event_broadcaster as _register_event_broadcaster,
)
from kagami_api.socketio.broadcaster import (
    unregister_event_broadcaster as _unregister_event_broadcaster,
)
from kagami_api.socketio.event_bus import EventBus
from kagami_api.socketio.namespaces.agents import AgentsNamespace
from kagami_api.socketio.namespaces.forge import ForgeNamespace
from kagami_api.socketio.namespaces.intents import IntentNamespace
from kagami_api.socketio.namespaces.metrics import MetricsNamespace
from kagami_api.socketio.namespaces.root import KagamiOSNamespace
from kagami_api.socketio.registry import (
    broadcast_event,
    get_rooms_summary,
    get_socketio_health,
    get_socketio_server,
    set_socketio_server,
)
from kagami_api.socketio.telemetry import add_span_attributes, traced_operation

__all__ = [
    "AgentsNamespace",
    # Legacy exports used by tests / compatibility
    "EventBus",
    "ForgeNamespace",
    "IntentNamespace",
    # Namespaces
    "KagamiOSNamespace",
    "MetricsNamespace",
    "_SocketIOEventBroadcaster",
    "_register_event_broadcaster",
    "_unregister_event_broadcaster",
    "add_span_attributes",
    "broadcast_event",
    # App
    "create_socketio_app",
    "get_rooms_summary",
    "get_socketio_health",
    "get_socketio_server",
    # Global registry
    "set_socketio_server",
    # Telemetry helpers
    "traced_operation",
]
