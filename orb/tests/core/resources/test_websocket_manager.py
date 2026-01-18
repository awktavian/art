"""Comprehensive tests for WebSocket management.

Tests WebSocket connection lifecycle, heartbeat/ping-pong, message sending/receiving,
connection cleanup, error handling, and metrics collection.
"""

import asyncio
import json
import pytest
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from kagami.core.resources.websocket_manager import (
    WebSocketManager,
    WebSocketConnectionError,
    send_websocket_message,
    receive_websocket_message,
)
from kagami.core.resources.tracker import get_resource_tracker, reset_tracker


@pytest.fixture(autouse=True)
def reset_resource_tracker():
    """Reset tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket connection."""
    ws = Mock()
    ws.send = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.receive_bytes = AsyncMock()
    ws.close = AsyncMock()
    ws.ping = AsyncMock()
    ws.remote_address = ("127.0.0.1", 8000)
    return ws


class TestWebSocketManager:
    """Test WebSocketManager class."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self, mock_websocket):
        """Test basic WebSocket lifecycle."""
        async with WebSocketManager(mock_websocket) as ws:
            assert not ws.closed
            assert ws.websocket is mock_websocket

        assert ws.closed
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_resource_tracking(self, mock_websocket):
        """Test that WebSocket connections are tracked."""
        tracker = get_resource_tracker()

        async with WebSocketManager(mock_websocket) as ws:
            # Should be tracked
            resources = tracker.get_resources("websocket")
            assert len(resources) == 1

        # Should be untracked after exit
        resources = tracker.get_resources("websocket")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_send_text(self, mock_websocket):
        """Test sending text message."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.send("Hello, World!")

        mock_websocket.send.assert_called_once_with("Hello, World!")

    @pytest.mark.asyncio
    async def test_send_bytes(self, mock_websocket):
        """Test sending binary message."""
        data = b"\x00\x01\x02\x03"

        async with WebSocketManager(mock_websocket) as ws:
            await ws.send(data)

        mock_websocket.send.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_send_json(self, mock_websocket):
        """Test sending JSON message."""
        data = {"type": "message", "content": "hello"}

        async with WebSocketManager(mock_websocket) as ws:
            await ws.send_json(data)

        mock_websocket.send_json.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_send_dict_with_send_json_method(self, mock_websocket):
        """Test sending dict when send_json is available."""
        data = {"type": "message"}

        async with WebSocketManager(mock_websocket) as ws:
            await ws.send(data)

        mock_websocket.send_json.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_send_dict_without_send_json_method(self):
        """Test sending dict when send_json is not available."""
        ws_conn = Mock()
        ws_conn.send = AsyncMock()
        ws_conn.close = AsyncMock()
        # No send_json method

        data = {"type": "message"}

        async with WebSocketManager(ws_conn) as ws:
            await ws.send(data)

        # Should convert to JSON and call send
        ws_conn.send.assert_called_once()
        sent_data = ws_conn.send.call_args[0][0]
        assert json.loads(sent_data) == data

    @pytest.mark.asyncio
    async def test_receive_json(self, mock_websocket):
        """Test receiving JSON message."""
        mock_websocket.receive_json.return_value = {"type": "response"}

        async with WebSocketManager(mock_websocket) as ws:
            data = await ws.receive()

        assert data == {"type": "response"}
        mock_websocket.receive_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_text(self):
        """Test receiving text message."""
        ws_conn = Mock()
        ws_conn.receive_text = AsyncMock(return_value="Hello")
        ws_conn.close = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            data = await ws.receive()

        assert data == "Hello"
        ws_conn.receive_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_bytes(self):
        """Test receiving binary message."""
        ws_conn = Mock()
        ws_conn.receive_bytes = AsyncMock(return_value=b"\x00\x01")
        ws_conn.close = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            data = await ws.receive()

        assert data == b"\x00\x01"
        ws_conn.receive_bytes.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping(self, mock_websocket):
        """Test sending ping."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.ping(b"ping")

        mock_websocket.ping.assert_called_once_with(b"ping")

    @pytest.mark.asyncio
    async def test_ping_without_method(self):
        """Test ping when method not available."""
        ws_conn = Mock(spec=["send", "close"])
        ws_conn.close = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            # Should not raise
            await ws.ping()

    @pytest.mark.asyncio
    async def test_heartbeat(self, mock_websocket):
        """Test automatic heartbeat."""
        async with WebSocketManager(mock_websocket, heartbeat_interval=0.1) as ws:
            # Wait for heartbeat
            await asyncio.sleep(0.15)

        # Should have sent at least one ping
        mock_websocket.ping.assert_called()

    @pytest.mark.asyncio
    async def test_heartbeat_stops_on_close(self, mock_websocket):
        """Test heartbeat stops when connection closes."""
        ws = WebSocketManager(mock_websocket, heartbeat_interval=0.1)
        await ws.initialize()

        # Wait for heartbeat task to start
        await asyncio.sleep(0.05)

        # Close connection
        await ws.close()

        # Heartbeat task should be cancelled
        assert ws._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_heartbeat_failure(self, mock_websocket):
        """Test heartbeat handles ping failures."""
        mock_websocket.ping.side_effect = RuntimeError("Ping failed")

        async with WebSocketManager(mock_websocket, heartbeat_interval=0.05) as ws:
            # Wait for heartbeat to fail
            await asyncio.sleep(0.1)

        # Should not crash

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, mock_websocket):
        """Test that metrics are tracked."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.send("Hello")
            await ws.send(b"\x00\x01\x02")

            assert ws._messages_sent == 2
            assert ws._bytes_sent == 5 + 3  # "Hello" + 3 bytes

    @pytest.mark.asyncio
    async def test_metrics_on_receive(self):
        """Test metrics on receive."""
        ws_conn = Mock()
        ws_conn.receive_text = AsyncMock(return_value="Hello")
        ws_conn.close = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            await ws.receive()

            assert ws._messages_received == 1
            assert ws._bytes_received == 5

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_websocket):
        """Test getting connection statistics."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.send("test")
            mock_websocket.receive_text.return_value = "response"

            stats = ws.get_stats()

            assert stats["closed"] is False
            assert stats["messages_sent"] == 1
            assert stats["bytes_sent"] == 4

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, mock_websocket):
        """Test cleanup happens even on error."""
        tracker = get_resource_tracker()

        try:
            async with WebSocketManager(mock_websocket) as ws:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should be cleaned up
        resources = tracker.get_resources("websocket")
        assert len(resources) == 0
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_timeout(self):
        """Test close operation timeout."""
        ws_conn = Mock()

        async def hang():
            await asyncio.sleep(10)

        ws_conn.close = hang

        ws = WebSocketManager(ws_conn, close_timeout=0.1)
        await ws.initialize()

        # Close should timeout
        with pytest.raises(asyncio.TimeoutError):
            await ws.close()

    @pytest.mark.asyncio
    async def test_close_error_handling(self, mock_websocket):
        """Test close error handling."""
        mock_websocket.close.side_effect = RuntimeError("Close failed")

        ws = WebSocketManager(mock_websocket)
        await ws.initialize()

        with pytest.raises(RuntimeError, match="Close failed"):
            await ws.close()

        # Should still be marked as closed
        assert ws.closed

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self, mock_websocket):
        """Test that double close doesn't error."""
        ws = WebSocketManager(mock_websocket)
        await ws.initialize()
        await ws.close()
        await ws.close()  # Should not raise

        # Should only close once
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_on_closed_connection(self, mock_websocket):
        """Test sending on closed connection raises error."""
        ws = WebSocketManager(mock_websocket)
        await ws.initialize()
        await ws.close()

        with pytest.raises(WebSocketConnectionError, match="WebSocket is closed"):
            await ws.send("test")

    @pytest.mark.asyncio
    async def test_receive_on_closed_connection(self, mock_websocket):
        """Test receiving on closed connection raises error."""
        ws = WebSocketManager(mock_websocket)
        await ws.initialize()
        await ws.close()

        with pytest.raises(WebSocketConnectionError, match="WebSocket is closed"):
            await ws.receive()

    @pytest.mark.asyncio
    async def test_send_error(self, mock_websocket):
        """Test send error handling."""
        mock_websocket.send.side_effect = RuntimeError("Send failed")

        with pytest.raises(WebSocketConnectionError, match="Send failed"):
            async with WebSocketManager(mock_websocket) as ws:
                await ws.send("test")

    @pytest.mark.asyncio
    async def test_receive_error(self, mock_websocket):
        """Test receive error handling."""
        mock_websocket.receive_json.side_effect = RuntimeError("Receive failed")

        with pytest.raises(WebSocketConnectionError, match="Receive failed"):
            async with WebSocketManager(mock_websocket) as ws:
                await ws.receive()

    @pytest.mark.asyncio
    async def test_send_text_convenience(self, mock_websocket):
        """Test send_text convenience method."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.send_text("Hello")

        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_bytes_convenience(self, mock_websocket):
        """Test send_bytes convenience method."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.send_bytes(b"\x00\x01")

        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_aclose_method(self):
        """Test WebSocket with aclose method."""
        ws_conn = Mock()
        ws_conn.aclose = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            pass

        ws_conn.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_with_generic_receive(self):
        """Test receive with generic receive method."""
        ws_conn = Mock()
        ws_conn.receive = AsyncMock(return_value="data")
        ws_conn.close = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            data = await ws.receive()

        assert data == "data"
        ws_conn.receive.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_with_recv_fallback(self):
        """Test receive with recv fallback."""
        ws_conn = Mock(spec=["recv", "close"])
        ws_conn.recv = AsyncMock(return_value="data")
        ws_conn.close = AsyncMock()

        async with WebSocketManager(ws_conn) as ws:
            data = await ws.receive()

        assert data == "data"
        ws_conn.recv.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_send_websocket_message(self, mock_websocket):
        """Test send_websocket_message function."""
        await send_websocket_message(mock_websocket, "test")

        mock_websocket.send.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_receive_websocket_message(self, mock_websocket):
        """Test receive_websocket_message function."""
        mock_websocket.receive_json.return_value = {"data": "test"}

        result = await receive_websocket_message(mock_websocket)

        assert result == {"data": "test"}
        mock_websocket.receive_json.assert_called_once()


class TestConcurrency:
    """Test concurrent WebSocket operations."""

    @pytest.mark.asyncio
    async def test_concurrent_connections(self):
        """Test multiple concurrent WebSocket connections."""
        websockets = []
        for i in range(5):
            ws = Mock()
            ws.send = AsyncMock()
            ws.close = AsyncMock()
            ws.remote_address = (f"127.0.0.{i}", 8000)
            websockets.append(ws)

        async def use_websocket(ws):
            async with WebSocketManager(ws) as mgr:
                await mgr.send("message")

        # Run concurrently
        await asyncio.gather(*[use_websocket(ws) for ws in websockets])

        # All should send and close
        for ws in websockets:
            ws.send.assert_called_once()
            ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_send_receive(self, mock_websocket):
        """Test concurrent send/receive operations."""
        mock_websocket.receive_json.return_value = {"response": "ok"}

        async def send_task(ws):
            for i in range(10):
                await ws.send(f"message {i}")
                await asyncio.sleep(0.01)

        async def receive_task(ws):
            for _i in range(10):
                await ws.receive()
                await asyncio.sleep(0.01)

        async with WebSocketManager(mock_websocket) as ws:
            await asyncio.gather(send_task(ws), receive_task(ws))

        assert ws._messages_sent == 10
        assert ws._messages_received == 10


class TestHeartbeat:
    """Test heartbeat functionality."""

    @pytest.mark.asyncio
    async def test_no_heartbeat_by_default(self, mock_websocket):
        """Test no heartbeat when not configured."""
        async with WebSocketManager(mock_websocket) as ws:
            await asyncio.sleep(0.1)

        # Should not ping without heartbeat configured
        mock_websocket.ping.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_interval(self, mock_websocket):
        """Test heartbeat respects interval."""
        async with WebSocketManager(mock_websocket, heartbeat_interval=0.05) as ws:
            await asyncio.sleep(0.15)

        # Should ping multiple times
        assert mock_websocket.ping.call_count >= 2

    @pytest.mark.asyncio
    async def test_heartbeat_cleanup_on_exit(self, mock_websocket):
        """Test heartbeat task is cleaned up on exit."""
        ws = WebSocketManager(mock_websocket, heartbeat_interval=0.1)
        await ws.initialize()

        assert ws._heartbeat_task is not None
        task = ws._heartbeat_task

        await ws.close()

        # Task should be cancelled
        assert task.cancelled() or task.done()


class TestRobustness:
    """Test robustness and edge cases."""

    @pytest.mark.asyncio
    async def test_cleanup_on_keyboard_interrupt(self, mock_websocket):
        """Test cleanup happens on KeyboardInterrupt."""
        tracker = get_resource_tracker()

        try:
            async with WebSocketManager(mock_websocket) as ws:
                raise KeyboardInterrupt()
        except KeyboardInterrupt:
            pass

        # Should still cleanup
        resources = tracker.get_resources("websocket")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_cleanup_on_system_exit(self, mock_websocket):
        """Test cleanup happens on SystemExit."""
        tracker = get_resource_tracker()

        try:
            async with WebSocketManager(mock_websocket) as ws:
                raise SystemExit(1)
        except SystemExit:
            pass

        # Should still cleanup
        resources = tracker.get_resources("websocket")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_heartbeat_after_close(self, mock_websocket):
        """Test heartbeat doesn't ping after close."""
        ws = WebSocketManager(mock_websocket, heartbeat_interval=0.05)
        await ws.initialize()

        # Let heartbeat run
        await asyncio.sleep(0.1)
        initial_ping_count = mock_websocket.ping.call_count

        # Close connection
        await ws.close()

        # Wait a bit
        await asyncio.sleep(0.1)

        # Should not ping more
        assert mock_websocket.ping.call_count == initial_ping_count

    @pytest.mark.asyncio
    async def test_bytes_tracking_accuracy(self, mock_websocket):
        """Test bytes tracking is accurate."""
        async with WebSocketManager(mock_websocket) as ws:
            await ws.send("test")  # 4 bytes
            await ws.send("hello world")  # 11 bytes
            await ws.send(b"\x00\x01\x02")  # 3 bytes

            assert ws._bytes_sent == 4 + 11 + 3


class TestPerformance:
    """Test WebSocket manager performance."""

    @pytest.mark.asyncio
    async def test_overhead_is_minimal(self):
        """Test that manager overhead is minimal."""
        import time

        ws_conn = Mock()
        ws_conn.send = AsyncMock()
        ws_conn.close = AsyncMock()

        start = time.perf_counter()

        for _ in range(100):
            async with WebSocketManager(ws_conn) as ws:
                await ws.send("test")

        elapsed = time.perf_counter() - start

        # Should be fast (< 1 second for 100 iterations)
        assert elapsed < 1.0
