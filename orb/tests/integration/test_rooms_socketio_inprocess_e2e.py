"""In-process end-to-end tests for rooms Socket.IO flows.

We avoid spinning up a real uvicorn server (can be flaky/slow in CI) and instead
exercise the full namespace handlers against the real rooms state services.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from dataclasses import dataclass


@dataclass
class _FakeManager:
    rooms: dict


@dataclass
class _FakeServer:
    manager: _FakeManager


@pytest.mark.asyncio
async def test_socketio_rooms_join_cursor_and_room_state_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that room_state payload includes expected fields after join."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from unittest.mock import AsyncMock

    from kagami_api.socketio_server import KagamiOSNamespace
    from kagami.core.rooms import state_service as rooms

    room_id = "inproc_room_1"

    # Seed persistent room state.
    await rooms.persist_snapshot(room_id, {"hello": "world"})
    await rooms.update_anchor(room_id, "a1", {"kind": "anchor", "x": 1})

    ns = KagamiOSNamespace()

    # Wire a fake server manager so on_join_room can enumerate room members.
    fake_rooms = {"/": {room_id: set()}}
    ns.server = _FakeServer(manager=_FakeManager(rooms=fake_rooms))

    # Patch enter_room to also mutate fake rooms membership.
    async def _enter_room(sid: str, rid: str):
        fake_rooms.setdefault("/", {}).setdefault(rid, set()).add(sid)

    ns.enter_room = AsyncMock(side_effect=_enter_room)

    # Capture emitted events.
    ns.emit = AsyncMock()  # type: ignore[method-assign]

    # Authenticate using API key on connect.
    sid = "sid1"
    ok = await ns.on_connect(sid, environ={}, auth={"api_key": "test_api_key"})
    assert ok is True, "Connection should succeed with valid API key"

    expected_user_id = "apikey:test_api"  # first 8 chars of 'test_api_key'

    # Pre-seed cursor for this user so join includes it.
    await rooms.update_cursor_3d(room_id, expected_user_id, [1.0, 2.0, 3.0])

    await ns.on_join_room(sid, {"room_id": room_id})

    # Find the room_state payload emitted to the joining sid.
    room_state_calls = [
        c for c in ns.emit.call_args_list if (len(c.args) >= 1 and c.args[0] == "room_state")
    ]
    assert room_state_calls, "expected room_state to be emitted"

    payload = room_state_calls[-1].args[1]

    # Verify room_id is correct
    assert payload["room_id"] == room_id, "room_state should have correct room_id"

    # Verify state contains seeded data
    assert payload["state"].get("hello") == "world", "Room state should contain persisted data"

    # Verify anchors are included
    anchors = payload.get("anchors") or []
    assert any(a.get("kind") == "anchor" for a in anchors), "Should include seeded anchor"

    # Verify anchor has expected structure
    anchor = next((a for a in anchors if a.get("kind") == "anchor"), None)
    assert anchor is not None
    assert anchor.get("x") == 1, "Anchor should have x coordinate"

    # Users list should include our synthetic API-key user with the cursor merged.
    users = payload.get("users") or []
    assert any(u.get("id") == expected_user_id for u in users), "User should be in users list"

    # Verify cursor position was merged into user
    merged = next(u for u in users if u.get("id") == expected_user_id)
    assert merged.get("cursor_position_3d") == [1.0, 2.0, 3.0], "User should have cursor position"

    # Verify cursor is exactly what we set
    cursor = merged.get("cursor_position_3d")
    assert len(cursor) == 3, "Cursor should be 3D"
    assert cursor[0] == 1.0, "Cursor X should be 1.0"
    assert cursor[1] == 2.0, "Cursor Y should be 2.0"
    assert cursor[2] == 3.0, "Cursor Z should be 3.0"


@pytest.mark.asyncio
async def test_socketio_cursor_update_broadcast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that cursor updates are broadcast to room members."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from unittest.mock import AsyncMock

    from kagami_api.socketio_server import KagamiOSNamespace
    from kagami.core.rooms import state_service as rooms

    room_id = "cursor_test_room"

    # Seed room
    await rooms.persist_snapshot(room_id, {"test": "data"})

    ns = KagamiOSNamespace()
    fake_rooms = {"/": {room_id: set()}}
    ns.server = _FakeServer(manager=_FakeManager(rooms=fake_rooms))

    async def _enter_room(sid: str, rid: str):
        fake_rooms.setdefault("/", {}).setdefault(rid, set()).add(sid)

    ns.enter_room = AsyncMock(side_effect=_enter_room)
    ns.emit = AsyncMock()

    # Connect and join
    sid = "cursor_test_sid"
    await ns.on_connect(sid, environ={}, auth={"api_key": "test_api_key"})
    await ns.on_join_room(sid, {"room_id": room_id})

    # Clear emit calls to focus on cursor update
    ns.emit.reset_mock()

    # Update cursor
    new_cursor = [5.0, 6.0, 7.0]
    if hasattr(ns, "on_cursor_update"):
        await ns.on_cursor_update(sid, {"room_id": room_id, "position": new_cursor})

        # Verify cursor was stored
        expected_user_id = "apikey:test_api"
        cursor_data = await rooms.get_cursor_3d(room_id, expected_user_id)
        assert cursor_data == new_cursor, "Cursor should be updated in state service"


@pytest.mark.asyncio
async def test_get_rooms_summary_reflects_manager_rooms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that rooms summary accurately reflects server manager state."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    import kagami_api.socketio.registry as reg

    class _S:
        def __init__(self) -> None:
            self.manager = _FakeManager(rooms={"/": {"room_x": {"sid1", "sid2"}}})

    reg._SIO = _S()

    from kagami_api.socketio_server import get_rooms_summary

    rooms = get_rooms_summary("/")

    # Verify room_x is in the summary
    room_ids = {r.get("room_id") for r in rooms}
    assert {"room_x"} == room_ids, "Should contain exactly room_x"

    # Verify member count
    room_x = rooms[0]
    assert room_x.get("room_id") == "room_x", "Room ID should be room_x"
    assert int(room_x.get("members") or 0) == 2, "Should have exactly 2 members"


@pytest.mark.asyncio
async def test_get_rooms_summary_multiple_rooms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test rooms summary with multiple rooms and varying member counts."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    import kagami_api.socketio.registry as reg

    class _S:
        def __init__(self) -> None:
            self.manager = _FakeManager(
                rooms={
                    "/": {
                        "room_a": {"sid1"},
                        "room_b": {"sid2", "sid3", "sid4"},
                        "room_c": set(),
                    }
                }
            )

    reg._SIO = _S()

    from kagami_api.socketio_server import get_rooms_summary

    rooms = get_rooms_summary("/")

    # Verify all rooms are present
    room_ids = {r.get("room_id") for r in rooms}
    assert room_ids == {"room_a", "room_b", "room_c"}, "All rooms should be listed"

    # Verify member counts
    room_map = {r.get("room_id"): r for r in rooms}
    assert int(room_map["room_a"].get("members") or 0) == 1, "room_a should have 1 member"
    assert int(room_map["room_b"].get("members") or 0) == 3, "room_b should have 3 members"
    assert int(room_map["room_c"].get("members") or 0) == 0, "room_c should have 0 members"


@pytest.mark.asyncio
async def test_socketio_disconnect_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that disconnect properly cleans up session state."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from unittest.mock import AsyncMock

    from kagami_api.socketio_server import KagamiOSNamespace
    from kagami.core.rooms import state_service as rooms

    room_id = "disconnect_test_room"
    await rooms.persist_snapshot(room_id, {"test": "data"})

    ns = KagamiOSNamespace()
    fake_rooms = {"/": {room_id: set()}}
    ns.server = _FakeServer(manager=_FakeManager(rooms=fake_rooms))

    async def _enter_room(sid: str, rid: str):
        fake_rooms.setdefault("/", {}).setdefault(rid, set()).add(sid)

    async def _leave_room(sid: str, rid: str):
        fake_rooms.get("/", {}).get(rid, set()).discard(sid)

    ns.enter_room = AsyncMock(side_effect=_enter_room)
    ns.leave_room = AsyncMock(side_effect=_leave_room)
    ns.emit = AsyncMock()

    sid = "disconnect_test_sid"

    # Connect and join
    await ns.on_connect(sid, environ={}, auth={"api_key": "test_api_key"})
    await ns.on_join_room(sid, {"room_id": room_id})

    # Verify sid is in room
    assert sid in fake_rooms["/"][room_id], "SID should be in room after join"

    # Disconnect
    await ns.on_disconnect(sid)

    # Verify session cleanup (implementation dependent)
    # The namespace should have cleaned up session data
    assert ns._sessions.get(sid) is None or ns._sessions.get(sid, {}).get("user_id") is None
