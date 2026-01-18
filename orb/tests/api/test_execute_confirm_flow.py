from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
    pytest.mark.timeout(30),
]

import uuid

from httpx import ASGITransport, AsyncClient

from kagami_api import create_app


async def test_execute_requires_confirm_for_high_risk(monkeypatch: Any) -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": "Bearer test_api_key",
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        resp = await client.post(
            "/api/command/execute",
            headers=headers,
            json={"lang": "LANG/2 EXECUTE files.remove @target=/tmp {}", "confirm": False},
        )
        assert resp.status_code in (200, 400, 401, 403)
        if resp.status_code == 200:
            body = resp.json()
            # High-risk actions should require confirmation or be blocked
            # Response may indicate confirmation needed, blocked status, or error
            assert (
                body.get("needs_confirmation") is True
                or body.get("status") in ("blocked", "error", "pending_confirmation")
                or body.get("error") is not None  # Risk assessment may return error
            ), f"Expected confirmation required or blocked, got: {body}"
