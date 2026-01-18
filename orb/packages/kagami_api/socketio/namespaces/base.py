from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from kagami_api.socketio.event_bus import EventBus
from kagami_api.socketio.telemetry import traced_operation
from socketio import AsyncNamespace

# OPTIMIZED (Dec 30, 2025): Lazy import SecurityFramework to reduce boot time
# SecurityFramework import triggers kagami.core.config (850ms) and database.connection (335ms)
if TYPE_CHECKING:
    from kagami_api.security import SecurityFramework as _SecurityFramework

_security_framework: type[_SecurityFramework] | None = None


def _get_security_framework() -> type[_SecurityFramework]:
    """Lazy import SecurityFramework on first use."""
    global _security_framework
    if _security_framework is None:
        from kagami_api.security import SecurityFramework

        _security_framework = SecurityFramework
    return _security_framework


logger = logging.getLogger(__name__)


class BaseNamespace(AsyncNamespace):
    """Common Socket.IO namespace behavior (auth + backpressure emit)."""

    def __init__(self, namespace: str | None = None):
        super().__init__(namespace)
        self.event_bus = EventBus()
        self.authenticated_sessions: set[str] = set()
        self.session_users: dict[str, dict[str, Any]] = {}
        self.user_rooms: dict[str, set[str]] = {}

        # Backpressure queues per room
        from asyncio import Queue

        self.event_queues: dict[str, Queue] = {}
        self._queue_processors: dict[str, Any] = {}

    async def emit(self, event: str, data: Any, room: str | None = None, **kwargs: Any) -> None:
        """Emit with backpressure handling (head-drop)."""
        import os as _os
        from asyncio import Queue, QueueFull, create_task

        max_queue = int((_os.getenv("KAGAMI_WS_MAX_QUEUE") or "500").strip() or 500)

        room_key = room or "broadcast"
        if room_key not in self.event_queues:
            self.event_queues[room_key] = Queue(maxsize=max_queue)
            create_task(self._process_event_queue(room_key))

        queue = self.event_queues[room_key]

        try:
            queue.put_nowait((event, data, room, kwargs))
        except QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait((event, data, room, kwargs))
                try:
                    from kagami.observability.metrics import SOCKETIO_BACKPRESSURE_DROPS

                    SOCKETIO_BACKPRESSURE_DROPS.labels(room=room_key).inc()
                except Exception:
                    pass
            except Exception as e:
                logger.warning("Event queue error for %s: %s", room_key, e)

    async def _process_event_queue(self, room_key: str) -> None:
        queue = self.event_queues.get(room_key)
        if not queue:
            return

        while True:
            try:
                event, data, room, kwargs = await queue.get()
                try:
                    await super().emit(event, data, room=room, **kwargs)
                except Exception as e:
                    logger.warning("Failed to emit %s to %s: %s", event, room_key, e)
                finally:
                    queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Event queue processor error for %s: %s", room_key, e)
                await asyncio.sleep(1.0)

    async def on_connect(  # type: ignore[no-untyped-def]
        self, sid: str, environ: dict[str, Any], auth: dict[str, Any] | None = None
    ):
        """Handle client connection with first-frame auth."""
        with traced_operation("socketio.connect", attributes={"sid": sid, "ns": self.namespace}):
            # Require authentication on connect (JWT token or API key)
            token = (auth or {}).get("token") if auth else None
            api_key = (auth or {}).get("api_key") if auth else None

            try:
                from kagami.observability.metrics import SOCKETIO_AUTH_DURATION_SECONDS
            except Exception:
                SOCKETIO_AUTH_DURATION_SECONDS = None

            import time as _t

            t0 = _t.perf_counter()

            if token:
                user = await self._authenticate(str(token))
                if user:
                    self._mark_authenticated(sid, user)
                    if SOCKETIO_AUTH_DURATION_SECONDS:
                        try:
                            SOCKETIO_AUTH_DURATION_SECONDS.labels("token").observe(
                                max(0.0, _t.perf_counter() - t0)
                            )
                        except Exception:
                            pass
                    await self.emit(
                        "authenticated",
                        {"status": "authenticated", "user_id": user["id"], "session_id": sid},
                        room=sid,
                    )
                    return True

            if api_key:
                try:
                    if _get_security_framework().validate_api_key(str(api_key)):
                        user = {"id": f"apikey:{str(api_key)[:8]}", "type": "api_key"}
                        self._mark_authenticated(sid, user)
                        if SOCKETIO_AUTH_DURATION_SECONDS:
                            try:
                                SOCKETIO_AUTH_DURATION_SECONDS.labels("api_key").observe(
                                    max(0.0, _t.perf_counter() - t0)
                                )
                            except Exception:
                                pass
                        await self.emit(
                            "authenticated",
                            {"status": "authenticated", "user_id": user["id"], "session_id": sid},
                            room=sid,
                        )
                        return True
                except Exception as e:
                    logger.error("API key authentication failed for %s: %s", sid, e)

            try:
                from kagami.observability.metrics import SOCKETIO_AUTH_FAILURES_TOTAL

                SOCKETIO_AUTH_FAILURES_TOTAL.labels("missing_credentials").inc()
            except Exception:
                pass

            logger.warning("Client %s connection rejected - no auth", sid)
            return False

    def _mark_authenticated(self, sid: str, user: dict[str, Any]) -> None:
        self.authenticated_sessions.add(sid)
        self.session_users[sid] = user

        # Join user-specific room
        user_room = f"user:{user['id']}"
        try:
            # This is async, but the underlying server queues it; best-effort.
            asyncio.create_task(self.enter_room(sid, user_room))
        except Exception:
            pass

        self.user_rooms.setdefault(user["id"], set()).add(sid)

    async def on_disconnect(self, sid: str) -> None:
        """Handle client disconnection."""
        with traced_operation("socketio.disconnect", attributes={"sid": sid, "ns": self.namespace}):
            if sid in self.authenticated_sessions:
                self.authenticated_sessions.remove(sid)

            if sid in self.session_users:
                user = self.session_users[sid]
                user_id = user.get("id")
                if user_id and user_id in self.user_rooms:
                    self.user_rooms[user_id].discard(sid)
                    if not self.user_rooms[user_id]:
                        del self.user_rooms[user_id]
                del self.session_users[sid]

            # Leave all rooms in parallel
            try:
                rooms_to_leave = list(self.rooms(sid))
                if rooms_to_leave:
                    await asyncio.gather(
                        *[self.leave_room(sid, room) for room in rooms_to_leave],
                        return_exceptions=True,
                    )
            except Exception:
                pass

    async def on_subscribe(self, sid: str, data: dict[str, Any]) -> None:
        if not await self._require_auth(sid):
            return
        channels = (data or {}).get("channels", [])
        user = self.session_users.get(sid, {})
        for channel in channels:
            if await self._can_subscribe(user, str(channel)):
                await self.enter_room(sid, f"channel:{channel}")
            else:
                await self.emit(
                    "error",
                    {"code": "PERMISSION_DENIED", "message": f"Cannot subscribe to {channel}"},
                    room=sid,
                )

        subscribed = [
            r.replace("channel:", "")
            for r in self.rooms(sid)
            if isinstance(r, str) and r.startswith("channel:")
        ]
        await self.emit("subscribed", {"channels": subscribed}, room=sid)

    async def on_unsubscribe(self, sid: str, data: dict[str, Any]) -> None:
        if not await self._require_auth(sid):
            return
        channels = (data or {}).get("channels", [])
        # Leave all channels in parallel
        if channels:
            await asyncio.gather(
                *[self.leave_room(sid, f"channel:{channel}") for channel in channels],
                return_exceptions=True,
            )
        await self.emit("unsubscribed", {"channels": channels}, room=sid)

    async def on_ping(self, sid: str, data: dict[str, Any] | None = None) -> None:
        await self.emit(
            "pong", {"timestamp": datetime.utcnow().isoformat(), "data": data}, room=sid
        )

    async def _authenticate(self, token: str) -> dict[str, Any] | None:
        try:
            sf = _get_security_framework()
            principal = sf.verify_token(token)
            return {"id": principal.sub, "roles": principal.roles}
        except Exception:
            try:
                if _get_security_framework().validate_api_key(token):
                    return {"id": "api_key_user", "roles": ["api_user"]}
            except Exception:
                pass
            return None

    async def _require_auth(self, sid: str) -> bool:
        if sid not in self.authenticated_sessions:
            await self.emit(
                "error",
                {"code": "AUTH_REQUIRED", "message": "Authentication required"},
                room=sid,
            )
            return False
        return True

    async def _can_subscribe(self, _user: dict[str, Any], _channel: str) -> bool:
        # Future: Add channel-level permission checks (RBAC integration)
        # Currently all authenticated users can subscribe to any channel
        return True

    async def broadcast_to_user(self, user_id: str, event: str, data: Any) -> None:
        await self.emit(event, data, room=f"user:{user_id}")

    async def broadcast_to_channel(self, channel: str, event: str, data: Any) -> None:
        await self.emit(event, data, room=f"channel:{channel}")


__all__ = ["BaseNamespace"]
