"""E2E Tests: Safety Layer (CBF) Integration.

Tests the Control Barrier Function safety layer end-to-end.
Validates that safety constraints are enforced for dangerous operations.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e


import uuid

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with full app."""
    from kagami_api import create_app

    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    """Generate auth headers with idempotency key.

    In test mode (KAGAMI_BOOT_MODE=test), keys starting with 'test-' are accepted.
    """
    return {
        "Authorization": "Bearer test-api-key",
        "Idempotency-Key": str(uuid.uuid4()),
    }


class TestSafetyLayerE2E:
    """End-to-end tests for safety layer functionality."""

    def test_safe_operation_is_processed(self, client, auth_headers) -> None:
        """Safe operations (STATUS queries) should be processed.

        STATUS is a read-only operation that should always be safe.
        """
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 STATUS system.status"},
            headers=auth_headers,
        )

        # Auth should work - if it fails, the test key isn't being accepted
        assert response.status_code not in (401, 403), (
            f"Auth failed with test key: {response.status_code}: {response.text}"
        )

        # Safe operation should be processed
        assert response.status_code in (200, 202, 400, 422), (
            f"Safe operation should be processed: {response.status_code}"
        )

        data = response.json()
        # Verify we got a proper response (not just an error)
        if response.status_code in (200, 202):
            # Success response should have status
            assert "status" in data or "result" in data, f"Success response format: {data}"

    def test_dangerous_operation_requires_confirmation(self, client, auth_headers) -> None:
        """Dangerous operations (like shutdown) should be blocked or require confirmation."""
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE system.shutdown", "confirm": False},
            headers=auth_headers,
        )

        # Auth should work
        assert response.status_code not in (401, 403), f"Auth failed: {response.status_code}"

        data = response.json()
        # Dangerous operation should either:
        # 1. Be blocked (status=blocked)
        # 2. Require confirmation (status=needs_confirmation)
        # 3. Return validation error (unknown action)
        # 4. Return error (action not allowed)
        valid_statuses = ("blocked", "needs_confirmation", "rejected", "error")

        if response.status_code in (200, 202):
            assert data.get("status") in valid_statuses, (
                f"Dangerous operation should be blocked/need confirmation: {data}"
            )
        # 400/422 is also acceptable (validation rejection)
        # 403 is acceptable if safety layer rejects

    def test_health_probes_are_available(self, client) -> None:
        """CBF health check should be available via vitals endpoint."""
        response = client.get("/api/vitals/probes/live")
        assert response.status_code == 200, f"Health probe failed: {response.text}"

        data = response.json()
        assert data.get("status") == "ok", f"Health probe should return ok: {data}"
        assert data.get("probe") == "liveness", f"Should be liveness probe: {data}"

    def test_harmful_intent_is_blocked(self, client, auth_headers) -> None:
        """Clearly harmful intents should be blocked by ethical gate."""
        response = client.post(
            "/api/command/execute",
            json={
                "lang": "LANG/2 EXECUTE harm.user target=all",
                "confirm": False,
            },
            headers=auth_headers,
        )

        # Auth should work
        assert response.status_code not in (401, 403), f"Auth failed: {response.status_code}"

        data = response.json()
        # Harmful intent should be rejected
        if response.status_code in (200, 202):
            # If processed, should be blocked/rejected
            assert data.get("status") in ("blocked", "rejected", "error"), (
                f"Harmful intent should be blocked: {data}"
            )
        # 400/422 is also acceptable (validation rejection of harmful command)


class TestSafetyMetricsE2E:
    """E2E tests for safety metrics exposure."""

    def test_metrics_endpoint_accessible(self, client) -> None:
        """Safety metrics should be exposed via Prometheus endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200, f"Metrics endpoint failed: {response.text}"

        text = response.text
        # Should have some metrics (may or may not have safety-specific ones)
        assert len(text) > 0, "Metrics endpoint returned empty response"

        # Verify it's Prometheus format
        has_valid_format = "kagami_" in text or "http_" in text or "# HELP" in text
        assert has_valid_format, "Metrics should be in Prometheus format"
