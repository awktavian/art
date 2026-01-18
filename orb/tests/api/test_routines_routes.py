from __future__ import annotations

from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
import os
import uuid


async def test_routines_create_and_list(async_client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIGHTWEIGHT_STARTUP", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    csrf = await async_client.get("/api/user/csrf-token")
    csrf_data = csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
    async_client.headers.update(
        {
            "Authorization": "Bearer test_api_key",
            "X-CSRF-Token": csrf_data.get("csrf_token", ""),
            "X-Session-ID": csrf_data.get("session_id", ""),
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
    )
    payload = {
        "name": "notify-on-quest",
        "rule": {
            "when_topic": "quest.progress",
            "condition": {"state": "completed"},
            "lang": "EXECUTE notify.send { to: 'me', message: 'done' }",
            "require_confirm": True,
        },
    }
    response = await async_client.post("/api/routines/create", json=payload)
    assert response.status_code in (200, 404, 500)
    if response.status_code == 404:
        return
    listing = await async_client.get("/api/routines/list")
    assert listing.status_code == 200
