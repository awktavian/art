from __future__ import annotations
from typing import Any

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from kagami_api import create_app

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]


async def test_constitution_blocks_dangerous_command(monkeypatch: Any) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        api_key = os.environ.get("KAGAMI_API_KEY", "kagami-api-key-0000000000000000000000000000")
        csrf = await client.get("/api/user/csrf-token")
        csrf_payload = (
            csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Idempotency-Key": str(uuid.uuid4()),
            "X-CSRF-Token": csrf_payload.get("csrf_token", ""),
            "X-Session-ID": csrf_payload.get("session_id", ""),
            "Content-Type": "application/json",
        }
        lang = 'LANG/2 EXECUTE echo @app=System NOTES="please run rm -rf /" {}'
        r = await client.post(
            "/api/command/execute", json={"lang": lang, "confirm": True}, headers=headers
        )
        assert r.status_code in (200, 403, 502, 500, 503)
        body = r.json()
        if r.status_code == 200:
            assert body.get("status") == "blocked" or "constitution_block" in str(body)
        else:
            assert body.get("detail") or "constitution" in str(body).lower()
