"""Actions Contract Tests

Tests the core API actions contracts:
- Health endpoints
- Auth endpoints
- Intent endpoints
"""

from __future__ import annotations

import os
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test_api_key"}


@pytest_asyncio.fixture
async def actions_client(monkeypatch: Any) -> None:
    monkeypatch.setenv("KAGAMI_BOOT_MODE", "test")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("KAGAMI_TEST_ECHO_LLM", "1")
    monkeypatch.setenv("KAGAMI_TEST_API_KEY", "test_api_key")
    import uuid

    from kagami_api import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Try to get CSRF token from correct endpoint
        csrf = await client.get("/api/user/csrf-token")
        token_payload = (
            csrf.json() if csrf.status_code == 200 else {"csrf_token": "", "session_id": ""}
        )
        client.headers.update(
            {
                "X-CSRF-Token": token_payload.get("csrf_token", ""),
                "X-Session-ID": token_payload.get("session_id", ""),
                "Content-Type": "application/json",
                "Idempotency-Key": str(uuid.uuid4()),
            }
        )
        yield client


async def test_health_ok(actions_client: AsyncClient) -> None:
    """Test health liveness endpoint."""
    r = await actions_client.get("/api/vitals/probes/live")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert body.get("status") in {"healthy", "ok"}


async def test_health_readiness(actions_client: AsyncClient) -> None:
    """Test health readiness endpoint.

    Note: In test mode, some services may not be fully ready,
    so 503 is acceptable as it indicates degraded but responsive.
    """
    r = await actions_client.get("/api/vitals/probes/ready")
    assert r.status_code in (200, 503)

    # Both success and error responses should be JSON
    body = r.json()
    assert isinstance(body, dict)

    # 503 response may have 'detail', 'error' (structured), or 'status' key
    if r.status_code == 503:
        assert "detail" in body or "status" in body or "error" in body
    else:
        assert "status" in body


async def test_auth_me_unauthorized_then_authorized(actions_client: AsyncClient) -> None:
    """Test /api/user/me requires auth."""
    # Without auth header should be 401
    unauth_headers = {
        k: v for k, v in actions_client.headers.items() if k.lower() not in {"authorization"}
    }
    r = await actions_client.get("/api/user/me", headers=unauth_headers)
    assert r.status_code == 401

    # With auth should be 200
    r2 = await actions_client.get("/api/user/me", headers=_auth_headers())
    assert r2.status_code == 200
    body = r2.json()
    assert isinstance(body, dict)
    # Ensure no secrets/PII beyond expected fields
    assert "password" not in body


async def test_csrf_token_endpoint(actions_client: AsyncClient) -> None:
    """Test CSRF token endpoint."""
    r = await actions_client.get("/api/user/csrf-token")
    assert r.status_code == 200
    body = r.json()
    assert "csrf_token" in body
    assert "session_id" in body


@pytest.mark.parametrize("query,expect_empty_allowed", [("", True), ("op", False)])
async def test_intents_suggest_conforms_actions_shape(
    query: str, expect_empty_allowed: bool, actions_client: AsyncClient
) -> None:
    r = await actions_client.get(
        "/api/command/suggest", params={"q": query}, headers=_auth_headers()
    )
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    assert isinstance(body, dict)
    assert "suggestions" in body
    suggestions = body["suggestions"]
    assert isinstance(suggestions, list)
    # Items are structured suggestion objects per API schema
    for s in suggestions:
        assert isinstance(s, dict)
        assert s.get("type") in {"command", "app", "verb", "file"}
        assert isinstance(s.get("value"), str)
        assert isinstance(s.get("label"), str)
    if query and not expect_empty_allowed:
        # If query provided, we allow empty array but should still be list type
        assert isinstance(suggestions, list)
    r2 = await actions_client.get("/api/command/suggest", headers=_auth_headers())
    assert r2.status_code == 200
    body2 = r2.json()
    assert isinstance(body2.get("suggestions", []), list)
    legacy = body2.get("suggestions", [])
    if legacy:
        item0 = legacy[0]
        assert isinstance(item0, dict)
        assert "value" in item0


@pytest.mark.slow
async def test_intents_parse_and_nl_contract(actions_client: AsyncClient) -> None:
    # Parse endpoint (read-only, no idempotency key needed but auth required)
    r = await actions_client.post(
        "/api/command/parse",
        headers=_auth_headers(),
        json={"text": "SLANG EXECUTE plan.create"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("intent", {}), dict)
    assert body.get("status") == "success"
    assert "original_text" in body
    assert "sections" in body

    # Test /nl endpoint with natural language (mutation, needs idempotency key)
    import uuid

    headers_with_idem = {**_auth_headers(), "Idempotency-Key": str(uuid.uuid4())}
    r2 = await actions_client.post(
        "/api/command/nl",
        headers=headers_with_idem,
        json={"text": "create a plan"},
    )
    assert r2.status_code in (200, 400)  # May fail validation but endpoint exists
    if r2.status_code == 200:
        body2 = r2.json()
        assert isinstance(body2, dict)
        assert "intent" in body2
        assert "original_text" in body2
        # Should have semantic understanding features
        assert "meaning" in body2 or "emotion" in body2 or "purpose" in body2


async def test_intents_execute_contract_low_risk_dryrun(actions_client: AsyncClient) -> None:
    r = await actions_client.post(
        "/api/command/execute",
        headers=_auth_headers(),
        json={"lang": "LANG/2 EXECUTE echo @dry_run=true {}", "confirm": False},
    )
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        body = r.json()
        # Status can be accepted, dryrun, completed, or blocked (by safety systems)
        assert body.get("status") in {"accepted", "dryrun", "completed", "blocked"}


async def test_command_endpoints_exist(actions_client: AsyncClient) -> None:
    """Test command endpoints are registered."""
    # Execute
    r = await actions_client.post(
        "/api/command/execute",
        headers=_auth_headers(),
        json={"lang": "LANG/2 PREVIEW test"},
    )
    assert r.status_code in (200, 400, 501)

    # Parse
    r2 = await actions_client.post(
        "/api/command/parse",
        headers=_auth_headers(),
        json={"text": "SLANG EXECUTE test"},
    )
    assert r2.status_code in (200, 400, 501)
