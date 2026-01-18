"""Targeted tests to cover session/start edge and physics branches."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import json
import types
import uuid


async def _csrf_headers(client, api_key: str, idem: str) -> dict[str, str]:
    r = await client.get("/api/user/csrf-token")
    assert r.status_code == 200
    d = r.json()
    return {
        "Authorization": f"Bearer {api_key}",
        "X-CSRF-Token": d["csrf_token"],
        "X-Session-ID": d["session_id"],
        "Idempotency-Key": idem,
    }


@pytest.mark.asyncio
async def test_rooms_session_start_world_not_found_when_not_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    monkeypatch.setenv("KAGAMI_TEST_MODE", "0")
    monkeypatch.setenv("PYTEST_RUNNING", "0")
    # Ensure no cached real Redis clients leak between tests.
    from kagami.core.caching.redis import RedisClientFactory

    RedisClientFactory._clients.clear()
    from kagami_api import create_app

    app = create_app()
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    # Force in-memory Redis for this request so we don't attempt real network I/O.
    class _FakeRedis:
        async def hget(self, *_a: Any, **_k) -> str:
            return None

    class _RF:
        @staticmethod
        def get_client(*_a: Any, **_k) -> str:
            return _FakeRedis()

    import kagami_api.routes.world.sessions as sessions

    monkeypatch.setattr(sessions, "RedisClientFactory", _RF)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_headers(
            client, "test_api_key", f"rooms-session-nontest-{uuid.uuid4()}"
        )
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={"world_id": "missing_world"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rooms_session_start_unrealzoo_space_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    from kagami_api import create_app

    app = create_app()
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    import kagami_api.routes.world.sessions as sessions

    monkeypatch.setattr(sessions, "ensure_unrealzoo_assets", lambda: "/tmp")
    monkeypatch.setattr(sessions, "get_unrealzoo_space", lambda *_a, **_k: None)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_headers(client, "test_api_key", "rooms-session-unrealzoo-missing")
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={"world_id": "w", "use_unrealzoo": True},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rooms_session_start_physics_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    monkeypatch.setenv("KAGAMI_ROOM_ENABLE_PHYSICS", "1")
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    monkeypatch.setenv("KAGAMI_ALLOW_FAKE_REDIS", "1")
    from kagami.core.caching.redis import RedisClientFactory

    RedisClientFactory._clients.clear()
    # Provide a fake GenesisPhysicsWrapper module to avoid importing heavy deps.
    calls: dict[str, int] = {"create": 0, "import": 0, "add": 0}

    class _FakePhysics:
        async def create_physics_scene(self, **_k) -> None:
            calls["create"] += 1

        async def import_world_environment(self, _path: str):
            calls["import"] += 1
            return {"success": True}

        async def add_character_to_scene(self, **_k) -> None:
            calls["add"] += 1

    fake_mod = types.ModuleType("genesis_physics_wrapper")
    fake_mod.GenesisPhysicsWrapper = _FakePhysics
    import sys

    sys.modules["kagami.forge.modules.genesis_physics_wrapper"] = fake_mod
    from kagami_api import create_app

    app = create_app()
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    from kagami.core.caching.redis import RedisClientFactory

    world_id = "world_physics"
    character_id = "char1"
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    await r.hset(f"kagami:worlds:data:{world_id}", "json", json.dumps({"world_url": "/tmp"}))
    await r.hset(
        f"kagami:characters:data:{character_id}",
        "json",
        json.dumps({"asset_url": "/tmp/mesh", "metadata": {"articulated": {"ok": True}}}),
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_headers(client, "test_api_key", "rooms-session-physics")
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={
                "world_id": world_id,
                "character_id": character_id,
                "scene_type": "character_studio",
            },
        )
        assert resp.status_code == 200, resp.text
    assert calls["create"] == 1
    assert calls["import"] == 1
    assert calls["add"] == 1


@pytest.mark.asyncio
async def test_rooms_session_start_missing_world_url_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    monkeypatch.setenv("KAGAMI_TEST_MODE", "0")
    monkeypatch.setenv("PYTEST_RUNNING", "0")
    from kagami.core.caching.redis import RedisClientFactory

    RedisClientFactory._clients.clear()

    # Fake Redis returns a world record missing world_url.
    class _FakeRedis:
        async def hget(self, *_a: Any, **_k) -> str:
            return json.dumps({"world_url": ""})

        async def hset(self, *_a: Any, **_k) -> Any:
            return 1

    class _RF:
        @staticmethod
        def get_client(*_a: Any, **_k) -> str:
            return _FakeRedis()

    import kagami_api.routes.world.sessions as sessions

    monkeypatch.setattr(sessions, "RedisClientFactory", _RF)
    from kagami_api import create_app

    app = create_app()
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_headers(
            client, "test_api_key", f"rooms-session-nopath-{uuid.uuid4()}"
        )
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={"world_id": "w_missing_path"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rooms_session_start_physics_import_failure_returns_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    monkeypatch.setenv("KAGAMI_ROOM_ENABLE_PHYSICS", "1")
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    monkeypatch.setenv("KAGAMI_ALLOW_FAKE_REDIS", "1")
    from kagami.core.caching.redis import RedisClientFactory

    RedisClientFactory._clients.clear()

    class _FailPhysics:
        async def create_physics_scene(self, **_k) -> None:
            return None

        async def import_world_environment(self, _path: str):
            return {"success": False}

    fake_mod = types.ModuleType("genesis_physics_wrapper")
    fake_mod.GenesisPhysicsWrapper = _FailPhysics
    import sys

    sys.modules["kagami.forge.modules.genesis_physics_wrapper"] = fake_mod
    from kagami_api import create_app

    app = create_app()
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    from kagami.core.caching.redis import RedisClientFactory as RF

    r = RF.get_client(purpose="default", async_mode=True, decode_responses=True)
    await r.hset("kagami:worlds:data:w_fail", "json", json.dumps({"world_url": "/tmp"}))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_headers(
            client, "test_api_key", f"rooms-session-phyfail-{uuid.uuid4()}"
        )
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={"world_id": "w_fail"},
        )
        assert resp.status_code == 500
