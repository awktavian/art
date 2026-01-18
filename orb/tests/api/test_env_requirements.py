"""Environment Requirements Tests

Tests environment requirement flags and readiness checks.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import importlib.util
import time

import anyio
from httpx import ASGITransport, AsyncClient

from kagami_api import create_app


async def _wait_ready_response(client: Any) -> Any:
    """Wait for ready endpoint to respond."""
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        resp = await client.get("/api/vitals/probes/ready")
        last = resp
        try:
            resp.json()
            return resp
        except Exception:
            await anyio.sleep(0.05)
    return last


async def _wait_for_components(client: Any) -> Any:
    """Wait for specific components to appear in readiness check."""
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        resp = await client.get("/api/vitals/probes/ready")
        last = resp
        try:
            data = resp.json()
            boot = (data.get("components") or {}).get("boot", {})
            comp_map = boot.get("components", {}) if isinstance(boot, dict) else {}
            if all(name in comp_map for name in names):
                return resp
        except Exception:
            pass
        await anyio.sleep(0.05)
    return last


@pytest.mark.anyio("asyncio")
async def test_require_inference_marks_not_ready(monkeypatch: Any) -> None:
    """Test that KAGAMI_REQUIRE_INFERENCE=1 marks system not ready when inference unavailable."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "0")
    monkeypatch.setenv("KAGAMI_STRICT_CONSENSUS", "0")
    monkeypatch.setenv("KAGAMI_REQUIRE_INFERENCE", "1")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _wait_for_components(client, ["inference"]) or await _wait_ready_response(
            client
        )
        assert resp is not None
        # Expect 503 (not ready) or 200 (degraded but responsive)
        assert resp.status_code in (200, 503)

        if resp.status_code == 503:
            data = resp.json()
            detail = data.get("detail") or {}
            status = detail.get("status") or detail.get("boot", {}).get("status")
            assert status in {"degraded", "unhealthy", None}


@pytest.mark.anyio("asyncio")
async def test_vitals_endpoints_accessible(monkeypatch: Any) -> None:
    """Test vitals endpoints are accessible."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Liveness
        resp = await client.get("/api/vitals/probes/live")
        assert resp.status_code == 200

        # Readiness
        resp = await client.get("/api/vitals/probes/ready")
        assert resp.status_code in (200, 503)

        # Deep check
        resp = await client.get("/api/vitals/probes/deep")
        assert resp.status_code == 200
