"""WebSocket connection management with automatic cleanup.

Provides safe WebSocket operations with guaranteed cleanup.
"""

import asyncio
import logging
from typing import Any, Literal

from kagami.core.resources.tracker import track_resource

logger = logging.getLogger(__name__)


class WebSocketConnectionError(Exception):
    """WebSocket connection error."""

    pass


class WebSocketManager:
    """Managed WebSocket connection with automatic cleanup.

    Features:
    - Automatic connection cleanup
    - Graceful disconnect
    - Message queue management
    - Heartbeat/ping support
    - Metrics collection

    Usage:
        async with WebSocketManager(websocket) as ws:
            await ws.send({"type": "message", "data": "hello"})
            message = await ws.receive()

        # With automatic heartbeat
        async with WebSocketManager(websocket, heartbeat_interval=30) as ws:
            await ws.send(data)
            # Heartbeat sent automatically
    """

    def __init__(
        self,
        websocket: Any,
        heartbeat_interval: float | None = None,
        close_timeout: float = 5.0,
    ) -> None:
        """Initialize WebSocket manager.

        Args:
            websocket: WebSocket connection object
            heartbeat_interval: Interval for heartbeat pings (None to disable)
            close_timeout: Timeout for close handshake
        """
        self.websocket = websocket
        self.heartbeat_interval = heartbeat_interval
        self.close_timeout = close_timeout
        self._resource_id: str | None = None
        self._closed = False
        self._messages_sent = 0
        self._messages_received = 0
        self._bytes_sent = 0
        self._bytes_received = 0
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "WebSocketManager":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Async context manager exit with cleanup."""
        await self.close()
        return False

    async def initialize(self) -> None:
        """Initialize WebSocket connection."""
        # Track resource
        self._resource_id = track_resource(
            resource_type="websocket",
            resource_id=str(id(self.websocket)),
            metadata={
                "remote_address": (
                    getattr(self.websocket, "remote_address", None)
                    if hasattr(self.websocket, "remote_address")
                    else None
                ),
            },
        )

        # Start heartbeat if configured
        if self.heartbeat_interval:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.debug("WebSocket manager initialized")

    async def close(self) -> None:
        """Close WebSocket connection with cleanup."""
        if self._closed:
            return

        cleanup_error = None
        try:
            # Stop heartbeat
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
                self._heartbeat_task = None

            # Close WebSocket
            if self.websocket:
                try:
                    # Try graceful close
                    if hasattr(self.websocket, "close"):
                        close_coro = self.websocket.close()
                        if asyncio.iscoroutine(close_coro):
                            await asyncio.wait_for(close_coro, timeout=self.close_timeout)
                    elif hasattr(self.websocket, "aclose"):
                        await asyncio.wait_for(self.websocket.aclose(), timeout=self.close_timeout)
                except TimeoutError:
                    logger.warning("WebSocket close timed out")
                except Exception as e:
                    cleanup_error = e
                    logger.error(f"Failed to close WebSocket: {e}")

            # Log metrics
            if self._messages_sent > 0 or self._messages_received > 0:
                logger.debug(
                    f"WebSocket closed: sent={self._messages_sent} msgs "
                    f"({self._bytes_sent} bytes), "
                    f"received={self._messages_received} msgs "
                    f"({self._bytes_received} bytes)"
                )

        finally:
            self._closed = True

            # Untrack resource
            if self._resource_id:
                from kagami.core.resources.tracker import get_resource_tracker

                tracker = get_resource_tracker()
                tracker.untrack(self._resource_id)
                self._resource_id = None

            if cleanup_error:
                raise cleanup_error

    async def send(self, data: Any) -> None:
        """Send data through WebSocket.

        Args:
            data: Data to send (str, bytes, or dict[str, Any] for JSON)
        """
        if self._closed:
            raise WebSocketConnectionError("WebSocket is closed")

        try:
            # Send based on type
            if isinstance(data, dict):
                # JSON data
                if hasattr(self.websocket, "send_json"):
                    await self.websocket.send_json(data)
                else:
                    import json

                    await self.websocket.send(json.dumps(data))
            elif isinstance(data, str):
                await self.websocket.send(data)
                self._bytes_sent += len(data.encode("utf-8"))
            elif isinstance(data, bytes):
                await self.websocket.send(data)
                self._bytes_sent += len(data)
            else:
                # Try to send as-is
                await self.websocket.send(data)

            self._messages_sent += 1

        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise WebSocketConnectionError(f"Send failed: {e}") from e

    async def receive(self) -> Any:
        """Receive data from WebSocket.

        Returns:
            Received data
        """
        if self._closed:
            raise WebSocketConnectionError("WebSocket is closed")

        try:
            # Receive based on available methods
            if hasattr(self.websocket, "receive_json"):
                data = await self.websocket.receive_json()
            elif hasattr(self.websocket, "receive_text"):
                data = await self.websocket.receive_text()
                self._bytes_received += len(data.encode("utf-8"))
            elif hasattr(self.websocket, "receive_bytes"):
                data = await self.websocket.receive_bytes()
                self._bytes_received += len(data)
            elif hasattr(self.websocket, "receive"):
                data = await self.websocket.receive()
                if isinstance(data, str):
                    self._bytes_received += len(data.encode("utf-8"))
                elif isinstance(data, bytes):
                    self._bytes_received += len(data)
            else:
                # Try recv as fallback
                data = await self.websocket.recv()

            self._messages_received += 1
            return data

        except Exception as e:
            logger.error(f"Failed to receive WebSocket message: {e}")
            raise WebSocketConnectionError(f"Receive failed: {e}") from e

    async def send_text(self, text: str) -> None:
        """Send text message.

        Args:
            text: Text to send
        """
        await self.send(text)

    async def send_bytes(self, data: bytes) -> None:
        """Send binary message.

        Args:
            data: Bytes to send
        """
        await self.send(data)

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send JSON message.

        Args:
            data: Dict to send as JSON
        """
        await self.send(data)

    async def ping(self, data: bytes = b"") -> None:
        """Send ping frame.

        Args:
            data: Ping payload
        """
        if self._closed:
            raise WebSocketConnectionError("WebSocket is closed")

        try:
            if hasattr(self.websocket, "ping"):
                await self.websocket.ping(data)
        except Exception as e:
            logger.warning(f"Failed to send ping: {e}")

    async def _heartbeat_loop(self) -> None:
        """Background task to send periodic pings."""
        try:
            while not self._closed:
                await asyncio.sleep(self.heartbeat_interval)  # type: ignore[arg-type]
                if not self._closed:
                    try:
                        await self.ping()
                    except Exception as e:
                        logger.warning(f"Heartbeat ping failed: {e}")
                        break
        except asyncio.CancelledError:
            pass

    @property
    def closed(self) -> bool:
        """Check if WebSocket is closed."""
        return self._closed

    def get_stats(self) -> dict[str, Any]:
        """Get WebSocket statistics.

        Returns:
            Stats dict[str, Any]
        """
        return {
            "closed": self._closed,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "bytes_sent": self._bytes_sent,
            "bytes_received": self._bytes_received,
        }


# Convenience functions


async def send_websocket_message(websocket: Any, data: Any) -> None:
    """Send a message through WebSocket with proper cleanup.

    Args:
        websocket: WebSocket connection
        data: Data to send
    """
    async with WebSocketManager(websocket) as ws:
        await ws.send(data)


async def receive_websocket_message(websocket: Any) -> Any:
    """Receive a message from WebSocket with proper cleanup.

    Args:
        websocket: WebSocket connection

    Returns:
        Received data
    """
    async with WebSocketManager(websocket) as ws:
        return await ws.receive()
