"""API tests for enabling rooms encryption (irreversible)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
import base64
import uuid
@pytest.mark.asyncio
async def test_rooms_encryption_enable_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")
    # Deterministic encryption key for provider
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("KAGAMI_ENCRYPTION_KEYS", f"t1:{key}")
    from kagami_api import create_app
    app = create_app()
    try:
        import httpx
        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")
    # Patch unified bus to capture HAL publish.
    published: list[tuple[str, dict]] = []
    class _Bus:
        async def publish(self, topic: str, payload: dict):
            published.append((topic, payload))
    import kagami.core.events as events_mod
    monkeypatch.setattr(events_mod, "get_unified_bus", lambda *a, **k: _Bus())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # CSRF/session headers
        r_csrf = await client.get("/api/user/csrf-token")
        assert r_csrf.status_code == 200
        d = r_csrf.json()
        headers = {
            "Authorization": "Bearer test_api_key",
            "X-CSRF-Token": d["csrf_token"],
            "X-Session-ID": d["session_id"],
            "Idempotency-Key": str(uuid.uuid4()),
        }
        room_id = "api_room_encrypt_1"
        # Seed a snapshot so we can assert encrypted-at-rest after enabling.
        from kagami_api.rooms.state_service import persist_snapshot
        await persist_snapshot(room_id, {"hello": "world"})
        # Missing confirm
        r0 = await client.post(
            "/api/rooms/encryption/enable", headers=headers, json={"room_id": room_id}
        )
        assert r0.status_code == 400
        # Enable
        r1 = await client.post(
            "/api/rooms/encryption/enable",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            json={"room_id": room_id, "confirm": True},
        )
        assert r1.status_code == 200, r1.text
        body = r1.json()
        assert body["success"] is True
        assert body["room_id"] == room_id
        assert body["encryption"]["enabled"] is True
        assert body["encryption"]["immutable"] is True
        # Verify latch is enabled and snapshot is encrypted-at-rest.
        from kagami_api.rooms.state_service import get_snapshot, is_room_encryption_enabled
        from kagami.core.caching.redis import RedisClientFactory
        assert await is_room_encryption_enabled(room_id) is True
        snap = await get_snapshot(room_id)
        assert snap.state == {"hello": "world"}
        r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
        raw = await r.get(f"kagami:rooms:{room_id}:snapshot")
        assert isinstance(raw, str)
        assert raw.startswith("enc:")
    # HAL wiring: we should publish a display control event.
    assert any(
        t == "hal.display.control" and p.get("command") == "room_encryption_enabled"
        for t, p in published
    )
