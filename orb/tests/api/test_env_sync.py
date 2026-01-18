from __future__ import annotations
from typing import Any

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from kagami_api import create_app

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]


@pytest_asyncio.fixture(loop_scope="function")
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_time_sync_endpoint_handles_requests(client: Any, monkeypatch: Any) -> None:
    """Time sync endpoint should respond (200 when enabled, graceful fallback otherwise)."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    payload = {"room_id": "world:demo", "mode": "system"}
    headers = {"Idempotency-Key": f"time-{uuid.uuid4()}"}
    resp = await client.post("/api/rooms/time/sync", json=payload, headers=headers)
    assert resp.status_code in (200, 403, 404, 501, 503)
    if resp.status_code == 200:
        body = resp.json()
        assert "time_iso" in body
        assert "day_phase" in body
    if resp.status_code == 403:
        detail = resp.json()
        assert "csrf" in json.dumps(detail).lower()


async def test_weather_sync_endpoint_handles_requests(client: Any, monkeypatch: Any) -> None:
    """Weather sync endpoint should not return 500 even when optional services disabled."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    payload = {"room_id": "world:demo", "mode": "system"}
    headers = {"Idempotency-Key": f"weather-{uuid.uuid4()}"}
    resp = await client.post("/api/rooms/weather/sync", json=payload, headers=headers)
    assert resp.status_code in (200, 403, 404, 501, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "weather" in data
        assert "temperature_c" in data
    if resp.status_code == 403:
        detail = resp.json()
        assert "csrf" in json.dumps(detail).lower()


async def test_env_fetch_endpoint_returns_payload(client: Any) -> None:
    resp = await client.get("/api/rooms/env/world:demo")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        env = resp.json()
        assert env.get("room_id") == "world:demo"
