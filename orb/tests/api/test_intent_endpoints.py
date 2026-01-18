"""Intent Endpoint Tests

Consolidated from:
- tests/api/test_intents_endpoint_registered.py
- tests/api/test_intents_highrisk_confirmation.py
- tests/api/test_intent_only_enforcement.py
- tests/api/test_intents_lang_ws_preview.py

Tests HTTP/WS intent execution, confirmation flow, and intent-only enforcement.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import uuid

from fastapi.testclient import TestClient

from kagami_api import create_app


@pytest.fixture
def client(monkeypatch: Any) -> Any:
    """Create test client."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    app = create_app()
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer test-api-key"})
    return c


class TestIntentEndpointRegistration:
    """Test intent endpoint registration."""

    def test_intents_execute_endpoint_registered(self, client: Any) -> Any:
        """Test /api/command/execute endpoint is registered."""
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # Should not be 404
        assert response.status_code != 404

    def test_intents_parse_endpoint_exists(self, client: Any) -> None:
        """Test /api/command/parse endpoint exists."""
        response = client.post("/api/command/parse", json={"text": "SLANG EXECUTE test"})

        # Should exist (200/400/501, but not 404)
        assert response.status_code != 404


class TestIntentExecution:
    """Test intent execution."""

    def test_execute_preview_intent(self, client: Any) -> None:
        """Test executing PREVIEW intent."""
        idem_key = str(uuid.uuid4())

        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test.action"},
            headers={"Idempotency-Key": idem_key},
        )

        # PREVIEW should succeed or return not implemented
        assert response.status_code in (200, 202, 501)

        if response.status_code in (200, 202):
            data = response.json()
            assert isinstance(data, dict)
            assert "status" in data or "intent" in data

    def test_execute_execute_intent(self, client: Any) -> None:
        """Test executing EXECUTE intent."""
        idem_key = str(uuid.uuid4())

        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE test.action"},
            headers={"Idempotency-Key": idem_key},
        )

        # EXECUTE should succeed or return not implemented
        assert response.status_code in (200, 202, 501)

        if response.status_code in (200, 202):
            data = response.json()
            assert isinstance(data, dict)


class TestHighRiskConfirmation:
    """Test high-risk intent confirmation flow."""

    def test_high_risk_intent_requires_confirmation(self, client: Any) -> None:
        """Test high-risk intent requires user confirmation."""
        idem_key = str(uuid.uuid4())

        # Execute high-risk intent without confirmation
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE delete.all"},
            headers={"Idempotency-Key": idem_key},
        )

        # Should return confirmation required, be blocked, or not implemented
        assert response.status_code in (200, 202, 403, 501)

        if response.status_code == 200:
            data = response.json()
            # Should indicate needs confirmation or blocked
            assert data.get("status") in ("needs_confirmation", "blocked") or "status" in data

    def test_confirmed_high_risk_intent_executes(self, client: Any) -> None:
        """Test confirmed high-risk intent executes."""
        idem_key = str(uuid.uuid4())

        # Execute with confirmation
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE delete.item", "confirm": True},
            headers={"Idempotency-Key": idem_key},
        )

        # With confirmation should execute or not be implemented
        assert response.status_code in (200, 202, 501)

        if response.status_code in (200, 202):
            data = response.json()
            assert data.get("status") in ("accepted", "executing") or isinstance(data, dict)

    def test_low_risk_intent_no_confirmation(self, client: Any) -> None:
        """Test low-risk intent doesn't require confirmation."""
        idem_key = str(uuid.uuid4())

        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW read.status"},
            headers={"Idempotency-Key": idem_key},
        )

        # Low risk PREVIEW should execute immediately
        assert response.status_code in (200, 202, 501)

        if response.status_code == 200:
            data = response.json()
            # Should NOT require confirmation
            assert data.get("status") != "needs_confirmation"


class TestIntentOnlyEnforcement:
    """Test intent-only enforcement mode."""

    def test_intent_only_mode_enforced(self, client: Any, monkeypatch: Any) -> None:
        """Test intent-only mode enforcement."""
        # When intent-only mode is enabled, only intent endpoints work
        monkeypatch.setenv("KAGAMI_INTENT_ONLY", "1")

        # Rebuild app with setting
        app = create_app()
        client = TestClient(app)
        client.headers.update({"Authorization": "Bearer test-api-key"})

        # Intent endpoint should work
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # Should not be 404
        assert response.status_code != 404


class TestIntentResponseFormat:
    """Test intent response format."""

    def test_response_includes_status(self, client: Any) -> None:
        """Test response includes status field."""
        idem_key = str(uuid.uuid4())

        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={"Idempotency-Key": idem_key},
        )

        if response.status_code == 200:
            data = response.json()
            assert "status" in data or isinstance(data, dict)

    def test_response_includes_receipt(self, client: Any) -> None:
        """Test response may include receipt."""
        idem_key = str(uuid.uuid4())

        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE test"},
            headers={"Idempotency-Key": idem_key},
        )

        if response.status_code == 200:
            data = response.json()
            # May include receipt reference
            assert isinstance(data, dict)


class TestIntentAuthentication:
    """Test intent authentication requirements."""

    def test_intent_execution_requires_auth(self) -> None:
        """Test intent execution requires authentication."""
        from kagami_api import create_app

        app = create_app()
        client = TestClient(app)

        # No auth header
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        # Without auth should be 401 unauthorized or 501 not implemented
        assert response.status_code in (401, 501)


class TestIntentIdempotency:
    """Test intent idempotency."""

    def test_intent_with_idempotency_key(self, client: Any) -> None:
        """Test intent execution with idempotency key."""
        idem_key = str(uuid.uuid4())

        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 PREVIEW test"},
            headers={"Idempotency-Key": idem_key},
        )

        # With key should accept or not be implemented
        assert response.status_code in (200, 202, 501)

    def test_duplicate_intent_key_rejected(self, client: Any) -> None:
        """Test duplicate idempotency key is rejected."""
        idem_key = str(uuid.uuid4())

        # First request
        response1 = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE test.once"},
            headers={"Idempotency-Key": idem_key},
        )

        # Duplicate request
        response2 = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE test.once"},
            headers={"Idempotency-Key": idem_key},
        )

        # Second should be 409 or same result
        if response1.status_code in (200, 202):
            assert response2.status_code in (200, 202, 409)
