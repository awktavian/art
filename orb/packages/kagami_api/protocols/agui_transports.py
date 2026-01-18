from __future__ import annotations

"""
AG-UI Transport Implementations for K os
Provides SSE, WebSocket, and webhook transports for AG-UI protocol.
"""
import asyncio
import json
from typing import Any

from fastapi import WebSocket

from kagami_api.protocols.agui import AGUIEvent, AGUIEventType, AGUITransport


def _event_from_payload(data: dict[str, Any]) -> AGUIEvent:
    """Parse an AG-UI event from a dict payload (shared across transports)."""
    event_type: AGUIEventType | str = data.get("type", "message")
    if isinstance(event_type, str):
        try:
            event_type = AGUIEventType(event_type)
        except ValueError:
            event_type = AGUIEventType.MESSAGE

    return AGUIEvent(
        id=data.get("id"),  # type: ignore[arg-type]
        type=event_type,
        timestamp=data.get("timestamp"),  # type: ignore[arg-type]
        correlation_id=data.get("correlation_id"),
        agent_id=data.get("agent_id"),
        session_id=data.get("session_id"),
        data=data.get("data", {}),
        metadata=data.get("metadata", {}),
    )


class _QueueReceiveMixin:
    """Mixin for transports backed by an asyncio receive queue."""

    receive_queue: asyncio.Queue

    async def receive_event(self) -> AGUIEvent | None:
        try:
            data = await asyncio.wait_for(self.receive_queue.get(), timeout=0.1)
            if not isinstance(data, dict):
                return None
            return _event_from_payload(data)
        except TimeoutError:
            return None


class WebSocketTransport(AGUITransport):
    """WebSocket transport for AG-UI events."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._connected = False

    async def connect(self) -> None:
        """Accept WebSocket connection."""
        if not self._connected:
            await self.websocket.accept()
            self._connected = True

    async def send_event(self, event: AGUIEvent) -> None:
        """Send an event via WebSocket."""
        if not self._connected:
            await self.connect()

        await self.websocket.send_json(event.to_dict())

    async def receive_event(self) -> AGUIEvent | None:
        """Receive an event from WebSocket."""
        if not self._connected:
            await self.connect()

        try:
            data = await self.websocket.receive_json()
            if not isinstance(data, dict):
                return None
            return _event_from_payload(data)
        except Exception:
            return None

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self._connected:
            await self.websocket.close()
            self._connected = False


class SSETransport(_QueueReceiveMixin, AGUITransport):
    """Server-Sent Events transport for AG-UI events.

    Supports bounded queues and best-effort backpressure/drop policy for
    low-priority event types (e.g., STREAM_CHUNK, STATE_UPDATE).
    """

    def __init__(self, event_queue: asyncio.Queue | None = None, maxsize: int = 1024):
        # Allow caller to pass an existing queue for compatibility; otherwise create bounded
        self.event_queue = event_queue or asyncio.Queue(maxsize=maxsize)
        self.receive_queue: asyncio.Queue = asyncio.Queue()

    async def send_event(self, event: AGUIEvent) -> None:
        """Send an event via SSE with drop policy for low-priority updates when full."""
        payload = {
            "event": (event.type.value if isinstance(event.type, AGUIEventType) else event.type),
            "data": json.dumps(event.to_dict()),
            "id": event.id,
        }
        try:
            self.event_queue.put_nowait(payload)
        except Exception:
            # Queue is full. Drop low-priority event types; block for important ones.
            low_priority = {
                AGUIEventType.STREAM_CHUNK,
                AGUIEventType.STATE_UPDATE,
                AGUIEventType.MESSAGE,
            }
            et = event.type if isinstance(event.type, AGUIEventType) else None
            if et in low_priority:
                # Best-effort drop
                return
            # For critical events (UI_UPDATE, ACTION_RESULT, CONFIRMATION_REQUEST, etc.), await space
            await self.event_queue.put(payload)

    async def close(self) -> None:
        """Close SSE transport."""
        # Put sentinel value to close SSE stream
        await self.event_queue.put(None)

    async def event_generator(self) -> None:  # type: ignore[misc]
        """Generator for SSE events."""
        while True:
            event = await self.event_queue.get()
            if event is None:
                break
            yield event


class WebhookTransport(_QueueReceiveMixin, AGUITransport):
    """Webhook transport for AG-UI events."""

    def __init__(self, webhook_url: str, client_id: str):
        self.webhook_url = webhook_url
        self.client_id = client_id
        self.receive_queue: asyncio.Queue = asyncio.Queue()

    async def send_event(self, event: AGUIEvent) -> None:
        """Send an event via webhook with optional HMAC signature."""
        import hashlib
        import hmac
        import os

        import httpx

        body = {
            "client_id": self.client_id,
            "event": event.to_dict(),
        }
        # Compute deterministic signature over client_id:event.id using shared secret
        secret = (os.getenv("AGUI_WEBHOOK_SECRET") or "").encode("utf-8")
        msg = f"{self.client_id}:{event.id}".encode()
        signature = hmac.new(secret, msg, hashlib.sha256).hexdigest() if secret else None

        headers = {
            "Content-Type": "application/json",
            "X-AGUI-Event-Type": (
                event.type.value if isinstance(event.type, AGUIEventType) else event.type
            ),
        }
        if signature:
            headers["X-AGUI-Signature"] = signature

        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                await client.post(self.webhook_url, json=body, headers=headers)
            except Exception:
                # Non-fatal: webhook delivery failures should not break server flows
                pass

    async def close(self) -> None:
        """Close webhook transport."""
        # No persistent connection to close (webhook is stateless).
        return None

    async def handle_webhook(self, data: dict[str, Any]) -> None:
        """Handle incoming webhook data."""
        await self.receive_queue.put(data)


class HybridTransport(AGUITransport):
    """
    Hybrid transport that can switch between multiple transports.
    Useful for fallback scenarios and multi-channel communication.
    """

    def __init__(self, primary: AGUITransport, fallback: AGUITransport | None = None):
        self.primary = primary
        self.fallback = fallback
        self.use_fallback = False

    async def send_event(self, event: AGUIEvent) -> None:
        """Send event via primary or fallback transport."""
        transport = self.fallback if self.use_fallback and self.fallback else self.primary

        try:
            await transport.send_event(event)
        except Exception as e:
            if not self.use_fallback and self.fallback:
                # Switch to fallback
                self.use_fallback = True
                await self.fallback.send_event(event)
            else:
                raise e

    async def receive_event(self) -> AGUIEvent | None:
        """Receive event from active transport."""
        transport = self.fallback if self.use_fallback and self.fallback else self.primary
        return await transport.receive_event()

    async def close(self) -> None:
        """Close all transports."""
        await self.primary.close()
        if self.fallback:
            await self.fallback.close()
