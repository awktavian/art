"""Unit tests for rooms CRDT/compression/reconnection helpers."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_rooms_compression_roundtrip_via_fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test compression roundtrip using mocked Redis client."""
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    monkeypatch.setenv("KAGAMI_ALLOW_FAKE_REDIS", "1")

    import kagami.core.rooms.compression as comp

    # Create a mock Redis client that stores data in memory
    storage: dict[str, str] = {}

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(side_effect=lambda k, v: storage.update({k: v}))
    mock_redis.get = AsyncMock(side_effect=lambda k: storage.get(k))

    # Patch the RedisClientFactory to return our mock
    import kagami.core.caching.redis as redis_module

    original_get_client = getattr(redis_module.RedisClientFactory, "get_client", None)
    monkeypatch.setattr(
        redis_module.RedisClientFactory,
        "get_client",
        lambda **kwargs: mock_redis,
    )

    room_id = "unit_room_compress_1"
    state = {"k": "v", "n": 1}

    await comp.persist_snapshot_compressed(room_id, state)
    out = await comp.get_snapshot_compressed(room_id)
    assert out.get("k") == "v"
    assert out.get("n") == 1


def test_rooms_compression_fallback_when_msgpack_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kagami.core.rooms.compression as comp

    monkeypatch.setattr(comp, "AVAILABLE", False)
    monkeypatch.setattr(comp, "msgpack", None)

    b = comp.compress_state({"a": 1})
    assert isinstance(b, bytes | bytearray)
    d = comp.decompress_state(b)
    assert d == {"a": 1}


def test_rooms_compression_decode_bad_mpk_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import kagami.core.rooms.compression as comp

    # Even if msgpack is installed, this should safely return {}.
    out = comp.decompress_state("mpk:not-base64")
    assert out == {}


def test_rooms_crdt_set_lww_and_increment() -> None:
    from kagami.core.rooms.crdt import OperationType, RoomStateCRDT, create_operation

    crdt = RoomStateCRDT("room")

    op1 = create_operation(
        op_type=OperationType.SET,
        path="foo.bar",
        value="v1",
        client_id="c1",
        version=1,
        timestamp_ms=1000,
    )
    crdt.apply_operation(op1)

    # Older timestamp should be ignored.
    op_old = create_operation(
        op_type=OperationType.SET,
        path="foo.bar",
        value="v0",
        client_id="c2",
        version=1,
        timestamp_ms=900,
    )
    crdt.apply_operation(op_old)
    # CRDT materializes clean state: {"foo": {"bar": "v1"}}, not wrapped in metadata
    assert crdt.get_state()["foo"]["bar"] == "v1"

    # Newer timestamp overwrites.
    op_new = create_operation(
        op_type=OperationType.SET,
        path="foo.bar",
        value="v2",
        client_id="c2",
        version=2,
        timestamp_ms=2000,
    )
    crdt.apply_operation(op_new)
    assert crdt.get_state()["foo"]["bar"] == "v2"

    # Increment is commutative and stores a numeric value at path.
    inc1 = create_operation(
        op_type=OperationType.INCREMENT,
        path="counter",
        value=2,
        client_id="c1",
        version=2,
        timestamp_ms=3000,
    )
    inc2 = create_operation(
        op_type=OperationType.INCREMENT,
        path="counter",
        value=3,
        client_id="c2",
        version=3,
        timestamp_ms=3001,
    )
    crdt.apply_operation(inc1)
    crdt.apply_operation(inc2)
    assert crdt.get_state()["counter"] == 5


@pytest.mark.asyncio
async def test_rooms_reconnection_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from kagami.core.rooms.reconnection import ReconnectionManager

    mgr = ReconnectionManager()

    import kagami.core.rooms.state_service as svc

    async def _boom(_room_id: str) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(svc, "get_current_seq", _boom)

    res = await mgr.handle_reconnection("room", "client", 0)
    d = res.to_dict()
    assert d["status"] == "error"
    assert d["current_seq"] == 0
    assert "failed" in (d.get("message") or "").lower()

    stats = mgr.get_stats()
    assert stats["total_reconnections"] >= 1
