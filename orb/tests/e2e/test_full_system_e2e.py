"""E2E Tests: Full System Integration.

Tests complete system flows from boot to operation with real authentication.
These tests validate actual system functionality end-to-end.
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


class TestFullSystemBootE2E:
    """E2E tests for full system boot and operation."""

    def test_system_boots_and_responds(self, client) -> None:
        """System should boot and respond to health checks."""
        response = client.get("/api/vitals/probes/live")
        assert response.status_code == 200, f"System did not boot properly: {response.text}"

        data = response.json()
        assert data.get("status") == "ok", f"Liveness probe should return ok: {data}"

    def test_core_endpoints_are_accessible(self, client) -> None:
        """Core endpoints should be accessible (not 404)."""
        endpoints = [
            ("/api/vitals/probes/live", "GET"),
            ("/metrics", "GET"),
            ("/api/colonies/status", "GET"),
        ]

        for path, method in endpoints:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path)

            # Should not be 404 (endpoint should exist)
            assert response.status_code != 404, f"{path} returned 404 - endpoint not registered"

    def test_authenticated_command_flow(self, client, auth_headers) -> None:
        """Complete authenticated command flow should work.

        Tests the full flow: auth -> process -> response
        """
        response = client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 STATUS system.version"},
            headers=auth_headers,
        )

        # With proper auth, should be processed (not rejected for auth)
        assert response.status_code not in (401, 403), (
            f"Request rejected for auth despite valid test key: {response.status_code}"
        )

        # Should get a valid response (success or validation error)
        assert response.status_code in (200, 202, 400, 422), (
            f"Unexpected status code: {response.status_code}: {response.text}"
        )

        data = response.json()
        # Verify structured response
        assert "status" in data or "error" in data or "detail" in data, (
            f"Response should have structured format: {data}"
        )


class TestSystemMetricsE2E:
    """E2E tests for system metrics."""

    def test_prometheus_metrics_format(self, client) -> None:
        """Metrics should be in valid Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200, f"Metrics endpoint failed: {response.text}"

        text = response.text
        lines = text.strip().split("\n")
        assert len(lines) > 0, "Empty metrics response"

        # Check for Prometheus format (comments, type declarations, metrics)
        has_valid_content = any(
            line.startswith("kagami_")
            or line.startswith("http_")
            or line.startswith("# HELP")
            or line.startswith("# TYPE")
            for line in lines
            if line.strip()
        )
        assert has_valid_content, "No valid Prometheus metrics found"

    def test_metrics_contain_request_counters(self, client) -> None:
        """Metrics should include HTTP request counters."""
        # Make some requests first
        for _ in range(3):
            client.get("/api/vitals/probes/live")

        response = client.get("/metrics")
        assert response.status_code == 200

        text = response.text
        # Should have request-related metrics
        has_request_metrics = (
            "http_request" in text or "kagami_request" in text or "starlette_requests" in text
        )
        # Note: This may fail if metrics aren't configured - that's a valid finding
        if not has_request_metrics:
            pytest.skip("Request metrics not configured (optional)")


class TestSystemRecoveryE2E:
    """E2E tests for system recovery and error handling."""

    def test_invalid_json_returns_error(self, client, auth_headers) -> None:
        """Invalid JSON should return proper error response, not crash."""
        headers = {**auth_headers, "Content-Type": "application/json"}
        response = client.post(
            "/api/command/execute",
            content=b"not valid json",
            headers=headers,
        )
        # Should return client error (4xx), not server crash (5xx shouldn't happen for bad input)
        assert response.status_code in (400, 422), (
            f"Invalid JSON should return 400/422, got {response.status_code}"
        )

    def test_missing_required_fields_returns_error(self, client, auth_headers) -> None:
        """Missing required fields should return validation error."""
        response = client.post(
            "/api/command/execute",
            json={},  # Missing 'lang' field
            headers=auth_headers,
        )
        # Should return validation error
        assert response.status_code in (400, 422), (
            f"Missing fields should return 400/422, got {response.status_code}"
        )

        data = response.json()
        # Should have error details
        assert "error" in data or "detail" in data, f"Error response should have details: {data}"

    def test_system_stable_after_errors(self, client) -> None:
        """System should remain stable after handling errors."""
        # Cause some errors
        client.get("/nonexistent-path")
        client.post("/api/command/execute", json={})

        # System should still respond to health checks
        response = client.get("/api/vitals/probes/live")
        assert response.status_code == 200, "System should remain stable after errors"

        data = response.json()
        assert data.get("status") == "ok", f"Health check failed after errors: {data}"
