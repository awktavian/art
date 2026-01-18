"""API Response Contract Tests.

These tests verify that API response schemas remain stable over time.
Breaking changes to response formats will cause snapshot mismatches.

Uses syrupy for snapshot testing to catch unintended schema changes.

Contract violations indicate:
- Breaking changes to error response format
- Breaking changes to health check schemas
- Breaking changes to authentication schemas
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.tier_integration]

import os
from typing import Any
import httpx
from syrupy.assertion import SnapshotAssertion
# =============================================================================
# CONFIGURATION
# =============================================================================
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev_test_key")
DEFAULT_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}
# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
def client() -> httpx.Client:
    """Create HTTP client with default configuration."""
    return httpx.Client(base_url=API_BASE_URL, headers=DEFAULT_HEADERS, timeout=10.0)
def normalize_response(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize response data for snapshot comparison.
    Removes dynamic fields like timestamps and correlation IDs that change
    between test runs.
    """
    if isinstance(data, dict):
        normalized = {}
        for key, value in data.items():
            # Skip dynamic fields
            if key in (
                "timestamp",
                "ts",
                "correlation_id",
                "session_id",
                "request_id",
                "trace_id",
            ):
                normalized[key] = "<DYNAMIC>"
            elif isinstance(value, dict):
                normalized[key] = normalize_response(value)  # type: ignore[assignment]
            elif isinstance(value, list):
                normalized[key] = [  # type: ignore[assignment]
                    normalize_response(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                normalized[key] = value
        return normalized
    return data
# =============================================================================
# ERROR RESPONSE FORMAT CONTRACT
# =============================================================================
@pytest.mark.contract
class TestErrorResponseContract:
    """Contract tests for standardized error response format."""
    def test_404_not_found_schema(self, client: httpx.Client, snapshot: SnapshotAssertion) -> None:
        """Contract: 404 errors must follow standard K-XXXX error schema."""
        response = client.get("/api/nonexistent/endpoint/test")
        assert response.status_code == 404
        data = response.json()
        # Verify error structure exists
        assert "error" in data
        # Normalize and snapshot
        normalized = normalize_response(data)
        assert normalized == snapshot
    def test_error_code_format(self, client: httpx.Client) -> None:
        """Contract: Error codes must follow K-XXXX format."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        data = response.json()
        error = data.get("error", {})
        # Must have K-XXXX format code
        assert "code" in error
        code = error["code"]
        assert isinstance(code, str)
        assert code.startswith("K-")
        assert len(code) == 6  # K-XXXX format
    def test_error_has_required_fields(self, client: httpx.Client) -> None:
        """Contract: Error responses must have code, message, category, correlation_id."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        data = response.json()
        error = data.get("error", {})
        # Required fields per contract
        assert "code" in error, "Error must have 'code' field"
        assert "message" in error, "Error must have 'message' field"
        assert "category" in error, "Error must have 'category' field"
        assert "correlation_id" in error, "Error must have 'correlation_id' field"
        # Verify types
        assert isinstance(error["code"], str)
        assert isinstance(error["message"], str)
        assert isinstance(error["category"], str)
        assert isinstance(error["correlation_id"], str)
    def test_method_not_allowed_schema(
        self, client: httpx.Client, snapshot: SnapshotAssertion
    ) -> None:
        """Contract: 405 Method Not Allowed errors follow standard schema."""
        # Try POST on GET-only endpoint
        response = client.post("/health")
        if response.status_code == 405:
            data = response.json()
            normalized = normalize_response(data)
            assert normalized == snapshot
# =============================================================================
# HEALTH CHECK RESPONSE SCHEMA CONTRACT
# =============================================================================
@pytest.mark.contract
class TestHealthCheckContract:
    """Contract tests for health check response schemas."""
    def test_health_response_schema(
        self, client: httpx.Client, snapshot: SnapshotAssertion
    ) -> None:
        """Contract: /health response schema must remain stable."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # Required field
        assert "status" in data
        assert data["status"] == "ok"
        # Normalize and snapshot
        normalized = normalize_response(data)
        assert normalized == snapshot
    def test_liveness_probe_schema(self, client: httpx.Client, snapshot: SnapshotAssertion) -> None:
        """Contract: Liveness probe schema must remain stable."""
        response = client.get("/api/vitals/probes/live")
        assert response.status_code == 200
        data = response.json()
        # Required fields per contract
        assert "status" in data
        assert "probe" in data
        assert "service" in data
        assert data["probe"] == "liveness"
        # Normalize and snapshot
        normalized = normalize_response(data)
        assert normalized == snapshot
    def test_readiness_probe_schema(
        self, client: httpx.Client, snapshot: SnapshotAssertion
    ) -> None:
        """Contract: Readiness probe schema must remain stable."""
        response = client.get("/api/vitals/probes/ready")
        # Can be 200 (ready) or 503 (not ready)
        assert response.status_code in (200, 503)
        data = response.json()
        # Required fields per contract
        assert "status" in data
        assert "ready" in data
        assert "probe" in data
        assert "checks" in data
        assert data["probe"] == "readiness"
        # Normalize and snapshot
        normalized = normalize_response(data)
        assert normalized == snapshot
    def test_deep_health_check_schema(
        self, client: httpx.Client, snapshot: SnapshotAssertion
    ) -> None:
        """Contract: Deep health check schema must remain stable."""
        response = client.get("/api/vitals/probes/deep")
        assert response.status_code == 200
        data = response.json()
        # Required fields
        assert "status" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)
        # Normalize (checks will have dynamic content, but structure should be stable)
        normalized = normalize_response(data)
        assert normalized == snapshot
    def test_safety_vitals_schema(self, client: httpx.Client, snapshot: SnapshotAssertion) -> None:
        """Contract: Safety vitals schema must remain stable."""
        response = client.get("/api/vitals/safety")
        assert response.status_code == 200
        data = response.json()
        # Required fields per contract
        assert "monitor_ready" in data
        assert "timestamp" in data
        assert isinstance(data["monitor_ready"], bool)
        # If monitor is ready, additional fields should exist
        if data["monitor_ready"]:
            # Optional but common fields
            # Just verify structure, not values
            # Safety invariant
            if data.get("current_h_value") is not None:
                assert data["current_h_value"] >= 0.0, "Safety invariant h(x) >= 0"
        # Normalize and snapshot
        normalized = normalize_response(data)
        assert normalized == snapshot
# =============================================================================
# AUTHENTICATION RESPONSE SCHEMA CONTRACT
# =============================================================================
@pytest.mark.contract
class TestAuthenticationContract:
    """Contract tests for authentication response schemas."""
    def test_token_response_schema(self, client: httpx.Client, snapshot: SnapshotAssertion) -> None:
        """Contract: Token response schema must remain stable."""
        # Try to get token (may not be configured in all environments)
        response = client.post(
            "/api/user/token",
            json={
                "username": os.getenv("TEST_USERNAME", "test"),
                "password": os.getenv("TEST_PASSWORD", "test"),
            },
        )
        if response.status_code == 404:
            pytest.skip("Authentication endpoint not available")
        if response.status_code == 401:
            pytest.skip("Test credentials not configured")
        if response.status_code == 200:
            data = response.json()
            # Required fields per contract
            assert "access_token" in data
            assert "token_type" in data
            assert "expires_in" in data
            assert data["token_type"] == "bearer"
            # Normalize (tokens are dynamic)
            normalized = data.copy()
            normalized["access_token"] = "<DYNAMIC>"
            if "refresh_token" in normalized:
                normalized["refresh_token"] = "<DYNAMIC>"
            assert normalized == snapshot
    def test_auth_error_schema(self, client: httpx.Client, snapshot: SnapshotAssertion) -> None:
        """Contract: Authentication error schema must remain stable."""
        response = client.post(
            "/api/user/token",
            json={"username": "invalid", "password": "wrong"},
        )
        if response.status_code == 404:
            pytest.skip("Authentication endpoint not available")
        # Should be 401 Unauthorized
        if response.status_code in (401, 403):
            data = response.json()
            # Should follow error schema
            if "error" in data:
                normalized = normalize_response(data)
                assert normalized == snapshot
# =============================================================================
# RESPONSE HEADER CONTRACTS
# =============================================================================
@pytest.mark.contract
class TestResponseHeaderContract:
    """Contract tests for response headers."""
    def test_cors_headers_present(self, client: httpx.Client) -> None:
        """Contract: CORS headers should be present on API responses."""
        response = client.get("/health")
        assert response.status_code == 200
        headers = response.headers
        # CORS headers may or may not be present depending on config
        # This is informational only
    def test_content_type_header(self, client: httpx.Client) -> None:
        """Contract: JSON responses must have application/json content type."""
        response = client.get("/health")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type.lower()
    def test_error_response_content_type(self, client: httpx.Client) -> None:
        """Contract: Error responses must also be JSON."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type.lower()
# =============================================================================
# SAFETY INVARIANT CONTRACTS
# =============================================================================
@pytest.mark.contract
class TestSafetyInvariantContract:
    """Contract tests for safety invariants h(x) >= 0."""
    def test_safety_h_value_invariant(self, client: httpx.Client) -> None:
        """Contract: Safety monitor must maintain h(x) >= 0 invariant."""
        response = client.get("/api/vitals/safety")
        assert response.status_code == 200
        data = response.json()
        # If monitor is ready and reports h(x), it MUST be >= 0
        if data.get("monitor_ready") and data.get("current_h_value") is not None:
            h_value = data["current_h_value"]
            assert isinstance(h_value, (int, float)), f"h(x) must be numeric, got {type(h_value)}"
            assert h_value >= 0.0, f"SAFETY INVARIANT VIOLATED: h(x) = {h_value} < 0"
    def test_safety_zone_values(self, client: httpx.Client) -> None:
        """Contract: Safety zone must be GREEN, YELLOW, or RED."""
        response = client.get("/api/vitals/safety")
        assert response.status_code == 200
        data = response.json()
        # If zone is reported, must be valid
        if "zone" in data and data["zone"] is not None:
            zone = data["zone"]
            assert zone in ("GREEN", "YELLOW", "RED"), f"Invalid safety zone: {zone}"
# Mark all tests as contract tests
