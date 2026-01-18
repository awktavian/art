from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
import os
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kagami_api.security import SecurityFramework


@pytest_asyncio.fixture
async def intents_client(monkeypatch: Any) -> None:
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("KAGAMI_BOOT_MODE", "test")
    from kagami_api import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        csrf = await client.get("/api/user/csrf-token")
        payload = csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
        client.headers.update(
            {
                "Authorization": "Bearer test-api-key-for-testing",
                "X-CSRF-Token": payload.get("csrf_token", ""),
                "X-Session-ID": payload.get("session_id", ""),
                "Content-Type": "application/json",
            }
        )
        yield client


async def test_require_auth_allows_api_key_bypass_for_intents(intents_client: AsyncClient) -> None:
    r = await intents_client.post("/api/command/parse", json={"text": "SLANG EXECUTE noop {}"})
    assert r.status_code in (200, 400)


async def test_jwt_create_and_verify_token(monkeypatch: Any) -> None:
    monkeypatch.setenv("JWT_SECRET", "secret")
    tok = SecurityFramework.create_access_token("u1", scopes=["read"])

    principal = SecurityFramework.verify_token(tok)
    assert principal.sub == "u1"
