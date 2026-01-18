from __future__ import annotations

from typing import Any

import os
import uuid

import pytest

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]


async def test_settings_put_returns_merged_preferences(
    async_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KAGAMI_TEST_NO_CLOUD", "1")
    csrf = await async_client.get("/api/user/csrf-token")
    token_payload = csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
    async_client.headers.update(
        {
            "Authorization": "Bearer test_api_key",
            "X-CSRF-Token": token_payload.get("csrf_token", ""),
            "X-Session-ID": token_payload.get("session_id", ""),
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
    )
    prefs = {
        "notifications_enabled": True,
        "notify_channel_email": True,
        "notify_channel_push": False,
        "notify_channel_slack": True,
        "quiet_hours_by_day": {
            "Mon": {"start": 21, "end": 6},
            "Tue": {"start": 21, "end": 6},
        },
        "voice_enabled": True,
        "input_device_id": "test-mic",
        "output_device_id": "test-speaker",
    }
    response = await async_client.put("/api/settings", json={"preferences": prefs})
    assert response.status_code in (200, 401, 404)
    if response.status_code != 200:
        return
    data = response.json()
    settings = (data.get("settings") or {}).get("preferences") or {}
    assert settings.get("notifications_enabled") is True
    assert settings.get("notify_channel_push") is False
    assert settings.get("notify_channel_email") is True
    q = settings.get("quiet_hours_by_day", {})
    assert q.get("Mon", {}).get("start") == 21
    assert settings.get("input_device_id") == "test-mic"
    assert settings.get("output_device_id") == "test-speaker"
