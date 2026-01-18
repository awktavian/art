from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio(loop_scope="function")]


async def _csrf_headers(client: Any) -> dict[str, str]:
    last: dict[str, Any] = {}
    for _ in range(2):
        response = await client.get("/api/user/csrf-token")
        if response.status_code == 200:
            data = response.json()
            if data.get("csrf_token"):
                return {
                    "X-CSRF-Token": data.get("csrf_token", ""),
                    "X-Session-ID": data.get("session_id", ""),
                }
            last = data
    return {
        "X-CSRF-Token": last.get("csrf_token", ""),
        "X-Session-ID": last.get("session_id", ""),
    }


@pytest_asyncio.fixture(loop_scope="function")
async def settings_client(async_client: Any) -> Any:
    headers = await _csrf_headers(async_client)
    async_client.headers.update(
        {
            **headers,
            "Authorization": "Bearer test-api-key-for-testing-only",
            "Content-Type": "application/json",
        }
    )
    return async_client


async def test_settings_defaults_public(async_client: Any) -> None:
    response = await async_client.get("/api/settings/defaults")
    assert response.status_code in (200, 404)
    if response.status_code == 404:
        return
    payload = response.json()
    assert payload.get("version") == 1
    assert payload.get("theme") == "dark"


async def test_settings_get_create_and_update(settings_client: Any) -> None:
    response = await settings_client.get("/api/settings")
    assert response.status_code in (200, 404)
    if response.status_code == 404:
        return
    data = response.json()
    assert data.get("version") >= 1, f"Expected version >= 1, got {data.get('version')}"
    assert data.get("theme") in ("dark", "light", "auto")
    prefs = (data.get("settings") or {}).get("preferences") or {}
    assert "notifications_enabled" in prefs

    original_version = data.get("version", 1)
    update_response = await settings_client.put(
        "/api/settings",
        json={
            "theme": "light",
            "preferences": {
                "reduce_motion": True,
                "notifications_enabled": False,
            },
        },
    )
    assert update_response.status_code == 200, update_response.text
    data2 = update_response.json()
    new_version = data2.get("version", 0)
    assert new_version >= original_version, "settings version should not regress"

    if new_version == original_version:
        refreshed = await settings_client.get("/api/settings")
        assert refreshed.status_code == 200
        data2 = refreshed.json()

    prefs2 = (data2.get("settings") or {}).get("preferences") or {}
    assert prefs2.get("reduce_motion") is True
    assert prefs2.get("notifications_enabled") is False
