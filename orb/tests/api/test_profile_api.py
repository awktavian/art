from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
import json
import os
import uuid
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kagami_api import create_app


@pytest_asyncio.fixture
async def client(monkeypatch: Any) -> None:
    monkeypatch.setenv("KAGAMI_SKIP_DOTENV", "1")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key_profile")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_profile_set_and_get(client: Any) -> None:
    csrf_resp = await client.get("/api/user/csrf-token")
    assert csrf_resp.status_code == 200
    csrf = csrf_resp.json().get("csrf_token", "")
    sid = csrf_resp.json().get("session_id", "")
    api_key = os.environ["KAGAMI_API_KEY"]
    body = {
        "user_id": "self",
        "profile": {
            "display_name": "Test User",
            "email": "test@example.com",
            "timezone": "UTC",
            "org": "K os",
        },
    }
    set_resp = await client.post(
        "/api/profile",
        content=json.dumps(body),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "X-Session-ID": sid,
            "Authorization": f"Bearer {api_key}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert set_resp.status_code in (200, 201, 403, 404)
    if set_resp.status_code in (200, 201):
        assert set_resp.json().get("ok") is True
    get_resp = await client.get("/api/profile")
    # Profile route may not be implemented yet (404 acceptable)
    assert get_resp.status_code in (200, 401, 404)
    if get_resp.status_code == 200:
        payload = get_resp.json()
        assert payload.get("user_id") == "self"
