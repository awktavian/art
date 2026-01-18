"""HAL Display Server - Real-time WebSocket display integration.

Usage:
    from kagami_hal.display_server import start_display_server

    server = await start_display_server()
    await server.show_qr("https://example.com", label="Scan me")
"""

import asyncio
import base64
import io
import json
import logging
import os
import uuid
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DISPLAY_SERVER_PORT = int(os.environ.get("KAGAMI_DISPLAY_PORT", "8765"))

# Find kagami-client path
_PATHS = [
    Path(__file__).parent.parent.parent.parent / "apps/desktop/kagami-client/src",
    Path.home() / "projects/kagami/apps/desktop/kagami-client/src",
]
KAGAMI_CLIENT_PATH: Path | None = next((p for p in _PATHS if p.exists()), None)


class DisplayEventType(str, Enum):
    """Event types."""

    SHOW_QR = "show_qr"
    SHOW_IMAGE = "show_image"
    SHOW_NOTIFICATION = "show_notification"
    SHOW_TOAST = "show_toast"
    SHOW_MODAL = "show_modal"
    CLOSE_MODAL = "close_modal"
    SHOW_PROGRESS = "show_progress"
    UPDATE_PROGRESS = "update_progress"
    HIDE_PROGRESS = "hide_progress"
    STREAM_FRAME = "stream_frame"
    CLEAR = "clear"
    STATE_SYNC = "state_sync"


@dataclass
class DisplayEvent:
    """Event payload."""

    type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {"type": self.type, "id": self.id, "timestamp": self.timestamp, "data": self.data}
        )

    @classmethod
    def from_json(cls, data: str) -> "DisplayEvent":
        p = json.loads(data)
        return cls(
            type=p.get("type", "unknown"),
            id=p.get("id", str(uuid.uuid4())),
            timestamp=p.get("timestamp", datetime.now().isoformat()),
            data=p.get("data", {}),
        )


class DisplayServer:
    """WebSocket display server."""

    def __init__(self, port: int = DISPLAY_SERVER_PORT):
        self.port = port
        self.clients: set = set()
        self._running = False
        self._task = None
        self._state: dict[str, Any] = {}
        self._modal_callbacks: dict[str, Callable] = {}
        self._connected = asyncio.Event()

    async def start(self, open_browser: bool = True) -> None:
        """Start server."""
        import uvicorn
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        app = FastAPI()
        srv = self

        @app.get("/")
        @app.get("/display")
        async def index():
            if KAGAMI_CLIENT_PATH:
                html = KAGAMI_CLIENT_PATH / "hal-display.html"
                if html.exists():
                    return FileResponse(html)
            return {"error": "not found"}

        @app.websocket("/ws")
        async def ws(websocket: WebSocket):
            await websocket.accept()
            srv.clients.add(websocket)
            srv._connected.set()
            logger.info(f"Client connected: {len(srv.clients)}")

            if srv._state:
                await websocket.send_text(
                    DisplayEvent(type="state_sync", data=srv._state).to_json()
                )

            try:
                while True:
                    data = await websocket.receive_text()
                    event = DisplayEvent.from_json(data)

                    if event.type == "ping":
                        await websocket.send_text(DisplayEvent(type="pong", id=event.id).to_json())
                    elif event.type == "modal_response":
                        mid = event.data.get("modal_id")
                        if mid in srv._modal_callbacks:
                            cb = srv._modal_callbacks.pop(mid)
                            r = cb(event.data.get("action"))
                            if asyncio.iscoroutine(r):
                                await r
                    elif event.type == "client_ready" and srv._state:
                        await websocket.send_text(
                            DisplayEvent(type="state_sync", data=srv._state).to_json()
                        )
            except WebSocketDisconnect:
                srv.clients.discard(websocket)
                logger.info(f"Client disconnected: {len(srv.clients)}")
                if not srv.clients:
                    srv._connected.clear()

        @app.get("/health")
        async def health():
            return {"status": "ok", "clients": len(srv.clients)}

        if KAGAMI_CLIENT_PATH and KAGAMI_CLIENT_PATH.exists():
            app.mount("/static", StaticFiles(directory=str(KAGAMI_CLIENT_PATH)), name="static")

        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        self._running = True
        self._task = asyncio.create_task(server.serve())

        logger.info(f"Display server: http://127.0.0.1:{self.port}/display")

        if open_browser:
            await asyncio.sleep(0.5)
            webbrowser.open(f"http://127.0.0.1:{self.port}/display")

    async def stop(self) -> None:
        """Stop server."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Close all clients in parallel
        if self.clients:
            await asyncio.gather(*[c.close() for c in list(self.clients)], return_exceptions=True)
        self.clients.clear()
        self._connected.clear()

    async def wait_for_client(self, timeout: float = 10.0) -> bool:
        """Wait for client connection."""
        if self.clients:
            return True
        try:
            await asyncio.wait_for(self._connected.wait(), timeout)
            return True
        except TimeoutError:
            return False

    async def broadcast(self, event: DisplayEvent) -> None:
        """Broadcast to all clients."""
        if not self.clients:
            return
        msg = event.to_json()
        # Broadcast to all clients in parallel
        results = await asyncio.gather(
            *[c.send_text(msg) for c in self.clients], return_exceptions=True
        )
        # Remove failed clients
        bad = {c for c, r in zip(self.clients, results, strict=False) if isinstance(r, Exception)}
        self.clients -= bad
        if bad and not self.clients:
            self._connected.clear()

    async def show_qr(
        self, data: str, label: str | None = None, sublabel: str | None = None
    ) -> str:
        """Show QR code."""
        try:
            import qrcode
        except ImportError:
            logger.error("qrcode not installed")
            return ""

        qr = qrcode.QRCode(
            version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        ev_data = {
            "qr_data": data,
            "qr_image": f"data:image/png;base64,{b64}",
            "label": label,
            "sublabel": sublabel or (data[:50] + "..." if len(data) > 50 else data),
        }
        self._state["qr"] = ev_data
        ev = DisplayEvent(type="show_qr", data=ev_data)
        await self.broadcast(ev)
        return ev.id

    async def show_image(
        self, image: str | Path | bytes, title: str | None = None, caption: str | None = None
    ) -> str:
        """Show image."""
        if isinstance(image, bytes):
            img_b64 = f"data:image/png;base64,{base64.b64encode(image).decode()}"
        elif isinstance(image, (str, Path)):
            p = Path(image)
            if p.exists():
                mime = {
                    "png": "image/png",
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "gif": "image/gif",
                }.get(p.suffix[1:].lower(), "image/png")
                img_b64 = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
            else:
                img_b64 = str(image)
        else:
            img_b64 = str(image)

        ev_data = {"image": img_b64, "title": title, "caption": caption}
        self._state["image"] = ev_data
        ev = DisplayEvent(type="show_image", data=ev_data)
        await self.broadcast(ev)
        return ev.id

    async def show_notification(
        self,
        message: str,
        title: str | None = None,
        level: str = "info",
        auto_dismiss_ms: int = 5000,
    ) -> str:
        """Show notification."""
        ev = DisplayEvent(
            type="show_notification",
            data={
                "message": message,
                "title": title,
                "level": level,
                "auto_dismiss_ms": auto_dismiss_ms,
            },
        )
        await self.broadcast(ev)
        return ev.id

    async def show_toast(self, message: str, auto_dismiss_ms: int = 3000) -> str:
        """Show toast."""
        ev = DisplayEvent(
            type="show_toast", data={"message": message, "auto_dismiss_ms": auto_dismiss_ms}
        )
        await self.broadcast(ev)
        return ev.id

    async def show_modal(
        self,
        title: str,
        content: str,
        actions: list[dict] | None = None,
        callback: Callable | None = None,
    ) -> str:
        """Show modal."""
        ev = DisplayEvent(
            type="show_modal",
            data={
                "title": title,
                "content": content,
                "actions": actions or [{"id": "close", "label": "Close"}],
            },
        )
        if callback:
            self._modal_callbacks[ev.id] = callback
        self._state["modal"] = {"id": ev.id, **ev.data}
        await self.broadcast(ev)
        return ev.id

    async def close_modal(self, modal_id: str) -> None:
        """Close modal."""
        self._state.pop("modal", None)
        await self.broadcast(DisplayEvent(type="close_modal", data={"modal_id": modal_id}))

    async def show_progress(
        self, title: str, message: str | None = None, value: float = 0.0
    ) -> str:
        """Show progress."""
        ev = DisplayEvent(
            type="show_progress", data={"title": title, "message": message, "value": value}
        )
        self._state["progress"] = {"id": ev.id, **ev.data}
        await self.broadcast(ev)
        return ev.id

    async def update_progress(
        self, progress_id: str, value: float, message: str | None = None
    ) -> None:
        """Update progress."""
        await self.broadcast(
            DisplayEvent(
                type="update_progress",
                data={"progress_id": progress_id, "value": value, "message": message},
            )
        )

    async def hide_progress(self, progress_id: str) -> None:
        """Hide progress."""
        self._state.pop("progress", None)
        await self.broadcast(DisplayEvent(type="hide_progress", data={"progress_id": progress_id}))

    async def clear(self) -> None:
        """Clear display."""
        self._state.clear()
        await self.broadcast(DisplayEvent(type="clear"))


# Global instance
_server: DisplayServer | None = None


async def get_display_server() -> DisplayServer:
    """Get global server."""
    global _server
    if _server is None:
        _server = DisplayServer()
    return _server


async def start_display_server(open_browser: bool = True) -> DisplayServer:
    """Start and return server."""
    srv = await get_display_server()
    if not srv._running:
        await srv.start(open_browser=open_browser)
    return srv


class DisplayProxy:
    """Easy access proxy."""

    async def _srv(self) -> DisplayServer:
        s = await get_display_server()
        if not s._running:
            await s.start()
            await s.wait_for_client(5.0)
        return s

    async def show_qr(self, *a, **kw):
        return await (await self._srv()).show_qr(*a, **kw)

    async def show_image(self, *a, **kw):
        return await (await self._srv()).show_image(*a, **kw)

    async def show_notification(self, *a, **kw):
        return await (await self._srv()).show_notification(*a, **kw)

    async def show_toast(self, *a, **kw):
        return await (await self._srv()).show_toast(*a, **kw)

    async def show_modal(self, *a, **kw):
        return await (await self._srv()).show_modal(*a, **kw)

    async def show_progress(self, *a, **kw):
        return await (await self._srv()).show_progress(*a, **kw)

    async def clear(self):
        s = await get_display_server()
        s._running and await s.clear()


display = DisplayProxy()

__all__ = [
    "DisplayEvent",
    "DisplayEventType",
    "DisplayServer",
    "display",
    "get_display_server",
    "start_display_server",
]
