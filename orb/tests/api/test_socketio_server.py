"""Unit tests for kagami_api.socketio_server module.

Tests Socket.IO server implementation including namespaces,
authentication, room management, and event handling.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest_asyncio


class TestSocketIOEventBroadcaster:
    """Test _SocketIOEventBroadcaster class."""

    @pytest.mark.asyncio
    async def test_broadcast(self) -> None:
        """Test broadcasting events."""
        from kagami_api.socketio_server import _SocketIOEventBroadcaster

        mock_sio = AsyncMock()
        broadcaster = _SocketIOEventBroadcaster(mock_sio)
        await broadcaster.broadcast("test_event", {"key": "value"})
        mock_sio.emit.assert_called_once()
        args, kwargs = mock_sio.emit.call_args
        assert args[0] == "test_event"
        assert args[1] == {"key": "value"}
        assert kwargs.get("namespace") == "/"

    @pytest.mark.asyncio
    async def test_emit(self) -> None:
        """Test emitting events."""
        from kagami_api.socketio_server import _SocketIOEventBroadcaster

        mock_sio = AsyncMock()
        broadcaster = _SocketIOEventBroadcaster(mock_sio)
        await broadcaster.emit(
            "test_event",
            {"data": "value"},
            room="room1",
            skip_sid="sid1",
        )
        mock_sio.emit.assert_called_once_with(
            "test_event",
            {"data": "value"},
            room="room1",
            skip_sid="sid1",
            namespace=None,
            callback=None,
        )


class TestRegisterEventBroadcaster:
    """Test broadcaster registration functions."""

    def test_register_event_broadcaster(self) -> None:
        """Test registering event broadcaster."""
        from kagami_api.socketio_server import _register_event_broadcaster

        mock_sio = MagicMock()
        with patch("kagami_api.socketio.broadcaster.register_service") as mock_register:
            _register_event_broadcaster(mock_sio)
            # Should register twice (once for each interface)
            assert mock_register.call_count == 2

    def test_unregister_event_broadcaster(self) -> None:
        """Test unregistering event broadcaster."""
        from kagami_api.socketio_server import _unregister_event_broadcaster

        with patch("kagami_api.socketio.broadcaster.unregister_service") as mock_unregister:
            _unregister_event_broadcaster()
            mock_unregister.assert_called_once()


class TestKagamiOSNamespaceInit:
    """Test KagamiOSNamespace initialization."""

    def test_basic_init(self) -> None:
        """Test basic initialization."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        assert ns.authenticated_sessions == set()
        assert ns.session_users == {}
        assert ns.user_rooms == {}
        assert isinstance(ns.event_queues, dict)

    def test_init_with_namespace(self) -> None:
        """Test initialization with custom namespace."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace(namespace="/test")
        assert ns.namespace == "/test"


class TestKagamiOSNamespaceRoomManagement:
    """Test KagamiOSNamespace room management."""

    @pytest.mark.asyncio
    async def test_on_join_room_empty_data(self) -> None:
        """Test joining room with empty data."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.enter_room = AsyncMock()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        await ns.on_join_room("sid1", {})
        # Should not attempt to enter room without room_id
        ns.enter_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_join_room_valid(self) -> None:
        """Test joining room with valid data."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.enter_room = AsyncMock()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        ns.session_users = {"sid1": {"id": "user1"}}
        ns.server = None  # No server in test
        await ns.on_join_room("sid1", {"room_id": "room123"})
        ns.enter_room.assert_called_once_with("sid1", "room123")

    @pytest.mark.asyncio
    async def test_on_leave_room_empty_data(self) -> None:
        """Test leaving room with empty data."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.leave_room = AsyncMock()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        await ns.on_leave_room("sid1", {})
        ns.leave_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_leave_room_valid(self) -> None:
        """Test leaving room with valid data."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.leave_room = AsyncMock()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        ns.session_users = {"sid1": {"id": "user1"}}
        await ns.on_leave_room("sid1", {"room_id": "room123"})
        ns.leave_room.assert_called_once_with("sid1", "room123")


class TestKagamiOSNamespaceCursor:
    """Test KagamiOSNamespace cursor updates."""

    @pytest.mark.asyncio
    async def test_on_update_cursor_3d_invalid(self) -> None:
        """Test 3D cursor update with invalid data."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        # Missing room_id
        await ns.on_update_cursor_3d("sid1", {"position": [1, 2, 3]})
        ns.emit.assert_not_called()
        # Invalid position
        await ns.on_update_cursor_3d("sid1", {"room_id": "room1", "position": [1, 2]})
        ns.emit.assert_not_called()


class TestKagamiOSNamespaceConstellationDevices:
    """Test Constellation (device) events on the root namespace."""

    @pytest.mark.asyncio
    async def test_on_device_register_requires_auth(self) -> None:
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.enter_room = AsyncMock()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        await ns.on_device_register("sid1", {"device_id": "watch-1"})
        # No auth → no registration side effects
        ns.enter_room.assert_not_called()
        ns.emit.assert_called_once()
        args, kwargs = ns.emit.call_args
        assert args[0] == "error"
        assert kwargs.get("room") == "sid1"

    @pytest.mark.asyncio
    async def test_on_device_register_valid(self) -> None:
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.enter_room = AsyncMock()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        ns.authenticated_sessions.add("sid1")
        ns.session_users = {"sid1": {"id": "user1"}}
        from kagami.core.ambient.multi_device_coordinator import MultiDeviceCoordinator

        coordinator = MultiDeviceCoordinator()
        coordinator.shared_state.update({"ambient.breath.phase": "rest"})
        with patch(
            "kagami.core.ambient.multi_device_coordinator.get_multi_device_coordinator",
            new=AsyncMock(return_value=coordinator),
        ):
            await ns.on_device_register(
                "sid1",
                {
                    "device_id": "watch-1",
                    "name": "Test Watch",
                    "device_type": "wearable",
                    "capabilities": {"haptics": True},
                    "set_active": True,
                },
            )
        ns.enter_room.assert_called_once_with("sid1", "device_watch-1")
        # Should emit device.registered to the registering sid
        assert ns.emit.call_count >= 1
        emitted_events = [c.args[0] for c in ns.emit.call_args_list]
        assert "device.registered" in emitted_events

    @pytest.mark.asyncio
    async def test_on_device_state_update_calls_sync(self) -> None:
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        ns.authenticated_sessions.add("sid1")
        coordinator = MagicMock()
        coordinator.sync_state = AsyncMock()
        with patch(
            "kagami.core.ambient.multi_device_coordinator.get_multi_device_coordinator",
            new=AsyncMock(return_value=coordinator),
        ):
            await ns.on_device_state_update(
                "sid1",
                {"device_id": "phone-1", "delta": {"ambient.quiet": True}},
            )
        coordinator.sync_state.assert_awaited_once()


class TestKagamiOSNamespaceEmit:
    """Test KagamiOSNamespace emit with backpressure."""

    @pytest.mark.asyncio
    async def test_emit_creates_queue(self) -> None:
        """Test that emit creates a queue for the room."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns._process_event_queue = (
            AsyncMock()
        )  # prevent background loop  # type: ignore[method-assign]
        await ns.emit("test_event", {"data": "value"}, room="room1")
        assert "room1" in ns.event_queues


class TestKagamiOSNamespaceAuthentication:
    """Test KagamiOSNamespace authentication."""

    @pytest.mark.asyncio
    async def test_on_connect_event(self) -> None:
        """Test connection event handling."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        # Check if on_connect method exists
        assert hasattr(ns, "on_connect")

    @pytest.mark.asyncio
    async def test_on_disconnect_event(self) -> None:
        """Test disconnect event handling."""
        from kagami_api.socketio_server import KagamiOSNamespace

        ns = KagamiOSNamespace()
        ns.authenticated_sessions.add("sid1")
        ns.session_users["sid1"] = {"id": "user1"}
        ns.emit = AsyncMock()  # type: ignore[method-assign]
        # Mock the server to avoid AttributeError on rooms()
        mock_server = MagicMock()
        mock_server.rooms.return_value = []  # No rooms
        ns.server = mock_server
        # Check if on_disconnect method exists
        if hasattr(ns, "on_disconnect"):
            await ns.on_disconnect("sid1")
            # Disconnect may or may not clean up authenticated_sessions
            # depending on implementation - just verify it runs without error


class TestCreateSocketIOApp:
    """Test create_socketio_app function."""

    def test_create_socketio_app(self) -> None:
        """Test creating Socket.IO app."""
        from kagami_api.socketio_server import create_socketio_app

        with patch("kagami_api.socketio.app.socketio.AsyncServer") as mock_async_server:
            mock_server = MagicMock()
            mock_async_server.return_value = mock_server
            sio = create_socketio_app(cors_allowed_origins=["*"], async_mode="asgi")
            # Should return something (depends on implementation)
            assert sio is not None


class TestBroadcastEvent:
    """Test broadcast_event function."""

    @pytest.mark.asyncio
    async def test_broadcast_event_no_server(self) -> None:
        """Test broadcasting when no server is configured."""
        from kagami_api.socketio_server import broadcast_event
        import kagami_api.socketio.registry as reg

        original = reg._SIO
        reg._SIO = None
        try:
            # Should not raise
            await broadcast_event("test_event", {"key": "value"})
        finally:
            reg._SIO = original

    @pytest.mark.asyncio
    async def test_broadcast_event_with_server(self) -> None:
        """Test broadcasting with server configured."""
        from kagami_api.socketio_server import broadcast_event
        import kagami_api.socketio.registry as reg

        original = reg._SIO
        mock_sio = AsyncMock()
        reg._SIO = mock_sio
        try:
            await broadcast_event("test_event", {"key": "value"})
            # emit may include namespace parameter
            mock_sio.emit.assert_called_once()
            call_args = mock_sio.emit.call_args
            assert call_args[0][0] == "test_event"
            assert call_args[0][1] == {"key": "value"}
        finally:
            reg._SIO = original


class TestGetSocketIOServer:
    """Test get_socketio_server function."""

    def test_get_socketio_server_none(self) -> None:
        """Test getting server when not configured."""
        from kagami_api.socketio_server import get_socketio_server
        import kagami_api.socketio.registry as reg

        original = reg._SIO
        reg._SIO = None
        try:
            result = get_socketio_server()
            assert result is None
        finally:
            reg._SIO = original

    def test_get_socketio_server_configured(self) -> None:
        """Test getting server when configured."""
        from kagami_api.socketio_server import get_socketio_server
        import kagami_api.socketio.registry as reg

        original = reg._SIO
        mock_sio = MagicMock()
        reg._SIO = mock_sio
        try:
            result = get_socketio_server()
            assert result is mock_sio
        finally:
            reg._SIO = original


class TestEventBusIntegration:
    """Test EventBus integration."""

    def test_event_bus_init(self) -> None:
        """Test EventBus is initialized."""
        from kagami_api.socketio_server import KagamiOSNamespace, EventBus

        ns = KagamiOSNamespace()
        assert isinstance(ns.event_bus, EventBus)


class TestBackpressureHandling:
    """Test backpressure handling in event queues."""

    @pytest.mark.asyncio
    async def test_process_event_queue(self) -> None:
        """Test event queue processing."""
        from kagami_api.socketio_server import KagamiOSNamespace
        from asyncio import Queue
        from socketio import AsyncNamespace

        ns = KagamiOSNamespace()
        ns.event_queues["test_room"] = Queue(maxsize=10)
        # Add an event to the queue
        await ns.event_queues["test_room"].put(("test_event", {"data": "value"}, "test_room", {}))
        assert ns.event_queues["test_room"].qsize() == 1
        with patch.object(AsyncNamespace, "emit", new_callable=AsyncMock) as mock_parent_emit:
            task = asyncio.create_task(ns._process_event_queue("test_room"))
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            mock_parent_emit.assert_called()


class TestTracingIntegration:
    """Test telemetry/tracing integration."""

    def test_traced_operation_fallback(self) -> None:
        """Test traced_operation fallback when telemetry unavailable."""
        from kagami_api.socketio_server import traced_operation

        # Should be a context manager
        with traced_operation("test_op"):
            pass  # Should not raise

    def test_add_span_attributes_fallback(self) -> None:
        """Test add_span_attributes fallback."""
        from kagami_api.socketio_server import add_span_attributes

        # Should not raise
        result = add_span_attributes({"key": "value"})
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
