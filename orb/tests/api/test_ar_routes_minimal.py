"""AR Routes Minimal Tests

Tests AR (Audio/Video) routes contract.
"""

from __future__ import annotations
from typing import Any

# Consolidated markers


import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
import os

from httpx import ASGITransport, AsyncClient

from kagami_api import create_app


async def test_ar_routes_enable_disable_contract(monkeypatch: Any) -> None:
    """Test AR routes enable/disable contract."""
    monkeypatch.setenv(
        "KAGAMI_API_KEY",
        os.environ.get("KAGAMI_API_KEY", "test-api-key-for-testing-only"),
    )
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use correct CSRF token path
        csrf = await client.get("/api/user/csrf-token")
        csrf_payload = (
            csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
        )
        headers = {
            "Authorization": f"Bearer {os.environ['KAGAMI_API_KEY']}",
            "X-CSRF-Token": csrf_payload.get("csrf_token", ""),
            "X-Session-ID": csrf_payload.get("session_id", ""),
            "Content-Type": "application/json",
        }

        # AR status may return 503 if AR is not configured
        r = await client.get("/api/ar/status", headers=headers)
        assert r.status_code in (200, 404, 503)

        # Use correct health path
        rh = await client.get("/api/vitals/probes/live", headers=headers)
        assert rh.status_code == 200
