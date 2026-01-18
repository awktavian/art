from __future__ import annotations

from kagami.boot import BootNode
from kagami.boot.actions import startup_socketio
from kagami.boot.nodes import health_flag


def get_network_nodes() -> list[BootNode]:
    """Return FAST network boot nodes.

    OPTIMIZED (Dec 28, 2025): SocketIO moved to fast boot - it just mounts
    an ASGI app, no orchestrator dependency needed.
    """
    return [
        BootNode(
            name="socketio",
            start=startup_socketio,
            dependencies=("redis",),  # Just needs Redis for pub/sub
            health_check=health_flag("socketio_ready", "socketio_ready"),
            timeout_s=3.0,  # Fast - just ASGI mount
        ),
    ]


def get_deferred_network_nodes() -> list[BootNode]:
    """Return deferred network boot nodes (none - socketio moved to fast)."""
    return []
