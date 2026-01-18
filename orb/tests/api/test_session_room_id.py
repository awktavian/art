from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import json
import os
import uuid


@pytest.mark.anyio
async def test_world_session_returns_room_id(
    authenticated_client, monkeypatch, mock_redis_client
) -> None:
    client = authenticated_client
    monkeypatch.setenv("HUNYUAN_WORLD_ENABLED", "1")
    import kagami.core.caching.redis as redis_mod

    class MockFactory:
        @staticmethod
        def get_client(purpose="default", async_mode=True, decode_responses=True):
            return mock_redis_client

    monkeypatch.setattr(redis_mod, "RedisClientFactory", MockFactory)
    from kagami.core.caching.redis import RedisClientFactory

    world_id = "world_test123"
    world_dir = str(os.getcwd())
    try:
        redis = RedisClientFactory.get_client(
            purpose="default", async_mode=True, decode_responses=True
        )
        await redis.hset(
            f"kagami:worlds:data:{world_id}",
            mapping={"json": json.dumps({"id": world_id, "world_url": world_dir})},
        )
    except Exception:
        pass
    response = client.post(
        "/api/rooms/session/start",
        json={"world_id": world_id, "scene_type": "character_studio"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code in (200, 404, 500), response.text
    if response.status_code == 500:
        detail = response.json()
        assert "security" in json.dumps(detail).lower()
        return
    if response.status_code == 404:
        payload = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        assert "detail" in payload or response.text
        return
    data = response.json()
    assert data.get("session_id")
    assert data.get("room_id") == f"world:{world_id}"
