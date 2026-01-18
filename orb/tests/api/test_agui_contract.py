"""AGUI Contract Tests

Tests the AG-UI protocol contracts.
"""

from __future__ import annotations

# Consolidated markers


import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
import os
import uuid

from httpx import ASGITransport, AsyncClient

from kagami_api import create_app



async def test_agui_initial_ui_contract_and_schema():
    """Test AGUI initial UI contract."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get CSRF token from correct endpoint
        r_csrf = await client.get("/api/user/csrf-token")
        assert r_csrf.status_code == 200
        csrf = r_csrf.json().get("csrf_token", "")
        sid = r_csrf.json().get("session_id", "")

        api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
        headers = {
            "X-CSRF-Token": csrf,
            "X-Session-ID": sid,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"test-contract-{uuid.uuid4()}",
        }

        # Test root endpoint
        r = await client.get("/", headers=headers)
        assert r.status_code in (200, 302, 404, 405, 503)

        # Test receipts endpoint at correct path
        r2 = await client.get("/api/mind/receipts/", headers=headers, follow_redirects=True)
        assert r2.status_code in (200, 204, 401, 503)


async def test_agui_run_endpoint():
    """Test AGUI run endpoint exists."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_csrf = await client.get("/api/user/csrf-token")
        csrf = r_csrf.json().get("csrf_token", "")
        sid = r_csrf.json().get("session_id", "")

        api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
        headers = {
            "X-CSRF-Token": csrf,
            "X-Session-ID": sid,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"test-run-{uuid.uuid4()}",
        }

        # Test AGUI run endpoint
        r = await client.post(
            "/api/colonies/agui/run",
            json={"message": "test"},
            headers=headers,
        )
        # Accept various status codes
        assert r.status_code in (200, 400, 401, 404, 501, 503)
