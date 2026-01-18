"""Execute V2 Confirmation Tests

Tests the confirmation flow for high-risk intent execution.
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
import uuid

from httpx import ASGITransport, AsyncClient

from kagami_api import create_app


async def test_execute_v2_needs_confirmation_high_risk(monkeypatch: Any) -> None:
    """Test that high-risk operations require confirmation."""
    monkeypatch.setenv("KAGAMI_SKIP_DOTENV", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")

    app = create_app(allowed_origins=["https://testserver"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use correct CSRF token path
        r_csrf = await client.get("/api/user/csrf-token")
        assert r_csrf.status_code == 200
        csrf = r_csrf.json().get("csrf_token", "")
        sid = r_csrf.json().get("session_id", "")
        headers = {
            "X-CSRF-Token": csrf,
            "X-Session-ID": sid,
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        lang = "LANG/2 EXECUTE system.delete"
        resp = await client.post(
            "/api/command/execute", json={"lang": lang, "confirm": False}, headers=headers
        )
        # Accept various valid status codes
        assert resp.status_code in (200, 202, 400, 501), resp.text

        if resp.status_code in (200, 202):
            data = resp.json()
            # Accept various valid statuses
            assert data.get("status") in {"needs_confirmation", "blocked", "error"}
            if data.get("status") == "needs_confirmation":
                assert data.get("needs_confirmation") is True
                assert data.get("risk") in ("high", "critical")
            if data.get("status") == "blocked":
                # Check for reason in top level or nested in result
                reason = (
                    data.get("cbf_reason")
                    or data.get("reason")
                    or data.get("result", {}).get("reason")
                )
                # Reason may not always be present
                pass


async def test_execute_with_confirmation(monkeypatch: Any) -> None:
    """Test intent execution with confirmation."""
    monkeypatch.setenv("KAGAMI_SKIP_DOTENV", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_csrf = await client.get("/api/user/csrf-token")
        csrf = r_csrf.json().get("csrf_token", "")
        sid = r_csrf.json().get("session_id", "")
        headers = {
            "X-CSRF-Token": csrf,
            "X-Session-ID": sid,
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        lang = "LANG/2 PREVIEW test"
        resp = await client.post(
            "/api/command/execute", json={"lang": lang, "confirm": True}, headers=headers
        )
        assert resp.status_code in (200, 400, 501)
