from __future__ import annotations

from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
import os


async def test_settings_get_put_defaults(async_client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "KAGAMI_API_KEY",
        os.environ.get("KAGAMI_API_KEY", "test-api-key-for-testing-only"),
    )
    transport_headers = {"Authorization": f"Bearer {os.environ['KAGAMI_API_KEY']}"}
    csrf = await async_client.get("/api/user/csrf-token")
    csrf_data = csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
    async_client.headers.update(
        {
            **transport_headers,
            "X-CSRF-Token": csrf_data.get("csrf_token", ""),
            "X-Session-ID": csrf_data.get("session_id", ""),
            "Content-Type": "application/json",
        }
    )
    r = await async_client.get("/api/settings")
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        return
    body = r.json()
    assert isinstance(body, dict)
    payload = {
        "theme": body.get("theme", "dark"),
        "preferences": {
            **((body.get("settings") or {}).get("preferences") or {}),
            "reducedMotion": True,
        },
    }
    response = await async_client.put("/api/settings", json=payload)
    assert response.status_code in (200, 204)
