"""Comprehensive Authentication Unit Tests

Tests for authentication, authorization, and token management.
Consolidates: test_auth_module_unit.py, test_auth_protected_paths.py, test_optional_auth_unit.py
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import os
import types
import uuid
from datetime import timedelta

import jwt as pyjwt
from fastapi import HTTPException, status
from kagami_api.security import ALGORITHM, SECRET_KEY, SecurityFramework

# ==============================================================================
# FIXTURES - Prevent test pollution
# ==============================================================================


@pytest.fixture(autouse=True)
def reset_security_state():
    """Reset security framework state before each test to prevent pollution.

    CRITICAL: This prevents token manager state from bleeding between tests,
    which was causing intermittent failures in tests/unit/api/test_auth.py.
    """
    from kagami_api.security.token_manager import reset_token_manager_for_testing

    # Reset singleton before test
    reset_token_manager_for_testing()

    yield

    # Reset singleton after test
    reset_token_manager_for_testing()


# ==============================================================================
# TOKEN MANAGEMENT TESTS
# ==============================================================================


def test_create_and_verify_token_success():
    """Test JWT token creation and verification with claims."""
    token = SecurityFramework.create_access_token(
        subject="user-123",
        scopes=["read", "write"],
        additional_claims={"tenant_id": "tenant-42", "roles": ["builder"]},
        expires_delta=timedelta(minutes=5),
    )

    principal = SecurityFramework.verify_token(token)
    assert principal.sub == "user-123"
    assert "read" in principal.scopes
    assert principal.tenant_id == "tenant-42"
    assert principal.roles == ["builder"]


def test_expired_token_rejected():
    """Test expired JWT tokens are rejected."""
    token = SecurityFramework.create_access_token(
        subject="user-expired",
        scopes=["read"],
        additional_claims={"roles": ["user"]},
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(HTTPException) as exc:
        SecurityFramework.verify_token(token)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_modified_token_signature_detected():
    """Test tampered JWT signature is detected."""
    token = SecurityFramework.create_access_token(subject="user-signature", scopes=[])
    header, payload, signature = token.split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join([header, tampered_payload, signature])

    with pytest.raises(HTTPException):
        SecurityFramework.verify_token(tampered)


def test_validate_api_key_accepts_reserved_prefix(monkeypatch: Any) -> None:
    """Test API key validation accepts test_ prefix in test boot mode."""
    # SECURITY: Test keys only accepted in actual test mode (KAGAMI_BOOT_MODE=test)
    # Not accepted in development or production
    monkeypatch.setenv("KAGAMI_BOOT_MODE", "test")
    assert SecurityFramework.validate_api_key("test_example_key")


def test_refresh_token_type_enforced():
    """Test refresh token type is enforced."""
    refresh = SecurityFramework.create_refresh_token(
        "refresh-user", additional_claims={"scopes": ["offline"]}
    )
    principal = SecurityFramework.verify_refresh_token(refresh)
    assert principal.sub == "refresh-user"

    # Verify scopes in token
    decoded = pyjwt.decode(refresh, SECRET_KEY, algorithms=[ALGORITHM])  # type: ignore[arg-type]
    assert decoded.get("scopes") == ["offline"]

    # Tamper token type
    decoded = pyjwt.decode(refresh, SECRET_KEY, algorithms=[ALGORITHM])  # type: ignore[arg-type]
    decoded["type"] = "access"
    tampered = pyjwt.encode(decoded, SECRET_KEY, algorithm=ALGORITHM)  # type: ignore[arg-type]

    with pytest.raises(HTTPException):
        SecurityFramework.verify_refresh_token(tampered)


# ==============================================================================
# ENDPOINT PROTECTION TESTS
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires database setup - move to integration tier")
async def test_api_key_auth_and_parse_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test API key authentication on protected parse endpoint."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Acquire CSRF/session
        r = await client.get("/api/user/csrf-token")
        assert r.status_code == 200
        data = r.json()
        csrf = data["csrf_token"]
        session_id = data["session_id"]

        client.headers.update(
            {
                "X-CSRF-Token": csrf,
                "X-Session-ID": session_id,
                "Authorization": "Bearer test_api_key",
            }
        )

        # Protected parse endpoint
        r2 = await client.post(
            "/api/command/parse",
            json={
                "text": 'SLANG EXECUTE plan.create state=IMMEDIATE @app=Plans {"name":"AuthParse"}'
            },
            timeout=5.0,
        )
        # Skip if route not registered
        if r2.status_code == 404:
            pytest.skip("Command parse route not registered in test app")
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert isinstance(body, dict) and "intent" in body


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires database setup - move to integration tier")
async def test_receipts_search_with_auth_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test receipts search endpoint with authentication."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/user/csrf-token")
        assert r.status_code == 200
        data = r.json()
        csrf = data["csrf_token"]
        session_id = data["session_id"]

        client.headers.update(
            {
                "X-CSRF-Token": csrf,
                "X-Session-ID": session_id,
                "Authorization": "Bearer test_api_key",
            }
        )

        # Search receipts
        rs = await client.get("/api/mind/receipts/search?limit=5")
        # Accept 404 if route not registered in test environment
        assert rs.status_code in (200, 401, 404, 503), rs.text


@pytest.mark.asyncio
async def test_auth_me_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /api/user/me requires authentication."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Without auth should be 401
        r = await client.get("/api/user/me")
        assert r.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires database setup - move to integration tier")
async def test_auth_me_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /api/user/me succeeds with valid API key."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # With auth should be 200
        r = await client.get("/api/user/me", headers={"Authorization": "Bearer test_api_key"})
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)


@pytest.mark.asyncio
async def test_csrf_token_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CSRF token generation endpoint."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/user/csrf-token")
        assert r.status_code == 200

        body = r.json()
        assert "csrf_token" in body
        assert "session_id" in body
        assert len(body["csrf_token"]) > 0
        assert len(body["session_id"]) > 0


@pytest.mark.asyncio
async def test_protected_endpoint_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test protected endpoint returns 401 without authentication."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Try protected endpoint without auth
        r = await client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        # Should be 401 without auth (or 404 if route not registered)
        if r.status_code == 404:
            pytest.skip("Command route not registered in test app")
        assert r.status_code == 401


@pytest.mark.skip(reason="Requires database setup - move to integration tier")
@pytest.mark.asyncio
async def test_protected_endpoint_with_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test protected endpoint succeeds with authentication."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Get CSRF token first
        csrf_r = await client.get("/api/user/csrf-token")
        csrf_data = csrf_r.json()

        # Try protected endpoint with auth
        r = await client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={
                "Authorization": "Bearer test_api_key",
                "Idempotency-Key": str(uuid.uuid4()),
                "X-CSRF-Token": csrf_data.get("csrf_token", ""),
                "X-Session-ID": csrf_data.get("session_id", ""),
            },
        )
        # Should succeed or return valid error (or 404 if route not registered)
        if r.status_code == 404:
            pytest.skip("Command route not registered in test app")
        assert r.status_code in (200, 400, 501)


# ==============================================================================
# OPTIONAL AUTHENTICATION TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_optional_auth_returns_none_without_credentials(monkeypatch: Any) -> None:
    """Test optional_auth returns None when no credentials provided."""
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")
    import kagami_api.security as sec

    # Build fake request with no credentials
    class DummyReq:
        def __init__(self):
            self.url = types.SimpleNamespace(path="/public")

    principal = await sec.optional_auth(DummyReq(), None)  # type: ignore[arg-type]
    assert principal is None


@pytest.mark.skip(reason="Requires database setup - move to integration tier")
@pytest.mark.asyncio
async def test_optional_auth_accepts_api_key(monkeypatch: Any) -> None:
    """Test optional_auth accepts valid API key."""
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")
    import kagami_api.security as sec

    class DummyCred:
        def __init__(self, token: str):
            self.credentials = token

    class DummyReq:
        def __init__(self):
            self.url = types.SimpleNamespace(path="/api/command/parse")

    cred = DummyCred("test_api_key")
    principal = await sec.optional_auth(DummyReq(), cred)  # type: ignore[arg-type]
    assert principal is not None
    assert principal.sub in ("api_key_user", "test_user")
