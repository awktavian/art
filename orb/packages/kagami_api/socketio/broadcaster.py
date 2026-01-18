from __future__ import annotations

import logging
from typing import Any

from kagami.core.di.container import register_service, unregister_service
from kagami.core.interfaces import EventBroadcaster, RealtimeBroadcaster

import socketio

logger = logging.getLogger(__name__)

_EVENT_BROADCASTER_KEY = EventBroadcaster
_REALTIME_BROADCASTER_KEY = RealtimeBroadcaster


class _SocketIOEventBroadcaster(RealtimeBroadcaster):
    """Adapter that exposes Socket.IO broadcasting via the DI container."""

    def __init__(self, sio: socketio.AsyncServer) -> None:
        self._sio = sio

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        # Root namespace broadcast.
        try:
            await self._sio.emit(event_type, data, namespace="/")
        except Exception:
            pass

    async def emit(
        self,
        event: str,
        data: Any,
        room: str | None = None,
        skip_sid: str | None = None,
        namespace: str | None = None,
        callback: Any | None = None,
        **kwargs: Any,
    ) -> None:
        await self._sio.emit(
            event,
            data,
            room=room,
            skip_sid=skip_sid,
            namespace=namespace,
            callback=callback,
            **kwargs,
        )


def register_event_broadcaster(sio: socketio.AsyncServer) -> None:
    """Register Socket.IO broadcaster in DI container."""
    try:
        broadcaster = _SocketIOEventBroadcaster(sio)
        register_service(_EVENT_BROADCASTER_KEY, lambda: broadcaster, singleton=True, replace=True)
        register_service(
            _REALTIME_BROADCASTER_KEY,
            lambda: broadcaster,
            singleton=True,
            replace=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to register Socket.IO broadcaster: %s", exc)


def unregister_event_broadcaster() -> None:
    try:
        unregister_service(_EVENT_BROADCASTER_KEY)
    except Exception:
        pass


__all__ = [
    "_SocketIOEventBroadcaster",
    "register_event_broadcaster",
    "unregister_event_broadcaster",
]
