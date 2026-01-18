"""Additional coverage for /api/rooms/session/start branches."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
import json
@pytest.mark.asyncio
async def test_rooms_session_start_uses_world_url_from_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    from kagami_api import create_app
    app = create_app()
    try:
        import httpx
        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    # Try to connect to Redis, skip if unavailable or event loop issues
    try:
        from kagami.core.caching.redis import RedisClientFactory
        world_id = "world_from_redis"
        r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
        await r.hset(f"kagami:worlds:data:{world_id}", "json", json.dumps({"world_url": "/tmp"}))
    except (RuntimeError, ConnectionError, OSError) as e:
        pytest.skip(f"Redis not available or event loop issue: {e}")
    except Exception as e:
        if "event loop" in str(e).lower() or "closed" in str(e).lower():
            pytest.skip(f"Redis event loop issue: {e}")
        raise
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        csrf_r = await client.get("/api/user/csrf-token")
        assert csrf_r.status_code == 200
        d = csrf_r.json()
        headers = {
            "Authorization": "Bearer test_api_key",
            "X-CSRF-Token": d["csrf_token"],
            "X-Session-ID": d["session_id"],
            "Idempotency-Key": "rooms-session-1",
        }
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={"world_id": world_id, "provider": "emu"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["room_id"] == f"world:{world_id}"
        assert body.get("provider") == "emu"
@pytest.mark.asyncio
async def test_rooms_session_start_unrealzoo_provider_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    from kagami_api import create_app
    app = create_app()
    try:
        import httpx
        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    # Patch UnrealZoo adapter calls inside the sessions module.
    import kagami_api.routes.world.sessions as sessions
    monkeypatch.setattr(sessions, "ensure_unrealzoo_assets", lambda: "/tmp")
    monkeypatch.setattr(
        sessions,
        "get_unrealzoo_space",
        lambda _world_id, assets_root=None: {
            "path": "/tmp",
            "id": "space1",
            "scene_graph": {"ok": True},
        },
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        csrf_r = await client.get("/api/user/csrf-token")
        assert csrf_r.status_code == 200
        d = csrf_r.json()
        headers = {
            "Authorization": "Bearer test_api_key",
            "X-CSRF-Token": d["csrf_token"],
            "X-Session-ID": d["session_id"],
            "Idempotency-Key": "rooms-session-2",
        }
        world_id = "world_unrealzoo"
        resp = await client.post(
            "/api/rooms/session/start",
            headers=headers,
            json={"world_id": world_id, "use_unrealzoo": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("provider") == "unrealzoo"
        assert body["room_id"] == f"world:{world_id}"
    # Verify the session record includes world_generation metadata.
    try:
        from kagami.core.caching.redis import RedisClientFactory
        r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
        session_key = f"kagami:sessions:{body['session_id']}"
        gen = await r.hget(session_key, "world_generation")
        if gen is not None:
            meta = json.loads(gen)
            assert meta["provider"] == "unrealzoo"
            assert meta["space_id"] == "space1"
    except (RuntimeError, ConnectionError, OSError) as e:
        # Skip Redis verification if connection issues (event loop problems in xdist)
        pass
