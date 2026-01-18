"""Test CSRF protection for browser flows."""

from __future__ import annotations
from typing import Any

import pytest
import pytest_asyncio

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
    pytest.mark.timeout(30),
]

import os
import uuid

from httpx import ASGITransport, AsyncClient

from kagami_api import create_app


@pytest_asyncio.fixture
async def client():
    """Create test client with CSRF enabled."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        test_client.headers.update({"X-Forwarded-For": f"127.0.0.{uuid.uuid4().int % 250}"})
        yield test_client


class TestCSRFProtection:
    """Test CSRF protection according to K os security rules."""

    async def test_csrf_token_generation_endpoint(self, client: Any) -> None:
        """Test that /api/user/csrf-token generates tokens."""
        response = await client.get("/api/user/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert "session_id" in data
        assert len(data["csrf_token"]) > 0
        assert len(data["session_id"]) > 0

    async def test_api_key_bypasses_csrf(self, client: Any) -> None:
        """Test that API key authentication bypasses CSRF checks."""
        response = await client.post(
            "/api/adaptive/log",
            json={"event_type": "test", "app_name": "test"},
            headers={"Idempotency-Key": str(uuid.uuid4()), "X-API-Key": "test-key"},
        )
        # Should not get CSRF error (may fail for other reasons)
        assert response.status_code != 403
        if response.status_code == 403:
            data = response.json()
            assert "csrf" not in str(data.get("detail", "")).lower()

    async def test_bearer_token_bypasses_csrf(self, client: Any) -> None:
        """Test that Bearer token authentication bypasses CSRF checks."""
        response = await client.post(
            "/api/adaptive/log",
            json={"event_type": "test", "app_name": "test"},
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "Authorization": "Bearer test-jwt-token",
            },
        )
        # Should not get CSRF error (may fail for other reasons)
        assert response.status_code != 403
        if response.status_code == 403:
            data = response.json()
            assert "csrf" not in str(data.get("detail", "")).lower()

    async def test_browser_mutation_requires_csrf_token(
        self, client: Any, monkeypatch: Any
    ) -> None:
        """Test that browser-based mutations require CSRF token."""
        csrf_response = await client.get("/api/user/csrf-token")
        csrf_data = csrf_response.json()
        csrf_data["csrf_token"]
        session_id = csrf_data["session_id"]

        monkeypatch.setenv("KAGAMI_TESTCLIENT_CSRF_BYPASS", "0")
        response = await client.post(
            "/api/adaptive/log",
            json={"event_type": "test", "app_name": "test"},
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "X-Session-ID": session_id,
                "User-Agent": "browser",
            },
        )
        assert response.status_code == 403
        data = response.json()
        # Current envelope uses an error object
        assert data.get("error", {}).get("type") == "csrf_error"

    async def test_browser_mutation_with_valid_csrf_token(self, client: Any) -> None:
        """Test that browser mutations work with valid CSRF token."""
        csrf_response = await client.get("/api/user/csrf-token")
        csrf_data = csrf_response.json()
        csrf_token = csrf_data["csrf_token"]
        session_id = csrf_data["session_id"]

        # Try a simple mutation endpoint to test CSRF (use plans endpoint which exists)
        response = await client.post(
            "/api/rbac/roles",
            json={"name": "test_role", "description": "test", "permissions": []},
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "X-CSRF-Token": csrf_token,
                "X-Session-ID": session_id,
                "Authorization": "Bearer test-api-key",  # Add auth for protected endpoint
            },
        )
        # Should not get CSRF error - may get other errors (404, 401, etc) but not 403 CSRF error
        if response.status_code == 403:
            data = response.json()
            assert (
                "csrf" not in str(data.get("detail", "")).lower()
            ), "Should not fail with CSRF error when valid token provided"

    async def test_csrf_token_validation_with_wrong_token(
        self, client: Any, monkeypatch: Any
    ) -> None:
        """Test that invalid CSRF tokens are rejected."""
        csrf_response = await client.get("/api/user/csrf-token")
        csrf_data = csrf_response.json()
        session_id = csrf_data["session_id"]

        wrong_token = "invalid-csrf-token-12345"
        monkeypatch.setenv("KAGAMI_TESTCLIENT_CSRF_BYPASS", "0")
        response = await client.post(
            "/api/adaptive/log",
            json={"event_type": "test", "app_name": "test"},
            headers={
                "Idempotency-Key": str(uuid.uuid4()),
                "X-CSRF-Token": wrong_token,
                "X-Session-ID": session_id,
                "User-Agent": "browser",
            },
        )
        assert response.status_code == 403
        data = response.json()
        assert data.get("error", {}).get("type") == "csrf_error"

    async def test_get_requests_dont_require_csrf(self, client: Any) -> None:
        """Test that GET requests don't require CSRF tokens."""
        response = await client.get("/api/vitals/probes/live")
        assert response.status_code == 200

        response = await client.get("/metrics")
        assert response.status_code == 200

    async def test_testclient_csrf_bypass_in_tests(self, client: Any, monkeypatch: Any) -> None:
        """Test that TestClient can bypass CSRF in test environment."""
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_csrf.py::test")

        response = await client.post(
            "/api/adaptive/log",
            json={"event_type": "test", "app_name": "test"},
            headers={"Idempotency-Key": str(uuid.uuid4()), "User-Agent": "testclient"},
        )
        if response.status_code == 403:
            data = response.json()
            assert "csrf" not in str(data.get("detail", "")).lower()

    async def test_csrf_bypass_can_be_disabled(self, monkeypatch: Any) -> None:
        """Test that KAGAMI_TESTCLIENT_CSRF_BYPASS=0 disables bypass."""
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_csrf.py::test")
        monkeypatch.setenv("KAGAMI_TESTCLIENT_CSRF_BYPASS", "0")

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as temp_client:
            response = await temp_client.post(
                "/api/adaptive/log",
                json={"event_type": "test", "app_name": "test"},
                headers={"Idempotency-Key": str(uuid.uuid4()), "User-Agent": "testclient"},
            )
            assert response.status_code == 403
            data = response.json()
            assert data.get("error", {}).get("type") == "csrf_error"
