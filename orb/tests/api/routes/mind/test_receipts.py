"""Receipt API Route Tests

Tests the receipt API endpoints at /api/mind/receipts/*.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import get_fastapi_app


def _make_app() -> FastAPI:
    """Create app for testing receipt routes.

    Returns:
        FastAPI app (unwrapped from Socket.IO if needed)
    """
    os.environ.setdefault("LIGHTWEIGHT_STARTUP", "1")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("KAGAMI_TEST_MODE", "1")
    from kagami_api import create_app

    app = create_app()
    # Use helper to unwrap FastAPI app from Socket.IO if needed
    return get_fastapi_app(app)


@pytest.fixture
def app() -> FastAPI:
    """Fixture providing FastAPI app instance."""
    return _make_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Fixture providing test client."""
    return TestClient(app)


def test_receipt_routes_registered(app: FastAPI) -> None:
    """Test that receipt routes are registered in the app."""
    paths = [getattr(r, "path", None) for r in app.routes]

    # Check for receipt routes
    receipt_paths = [p for p in paths if p and "/api/mind/receipts" in p]
    assert len(receipt_paths) > 0, f"Expected receipt routes to be registered, got paths: {paths}"

    # Check for specific endpoints
    expected_paths = [
        "/api/mind/receipts/",
        "/api/mind/receipts/stream",
        "/api/mind/receipts/search",
    ]

    for expected in expected_paths:
        assert any(
            expected == p for p in receipt_paths
        ), f"Expected {expected} to be registered, got: {receipt_paths}"


def test_list_receipts_endpoint_exists(client: TestClient) -> None:
    """Test GET /api/mind/receipts/ endpoint exists and returns proper structure."""
    response = client.get("/api/mind/receipts/")

    # Should not return 404
    assert response.status_code != 404, "Receipt list endpoint should be registered"

    # Should return 200 (even if empty)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Check response structure
    data = response.json()
    assert "receipts" in data, f"Expected 'receipts' key in response: {data}"
    assert "count" in data, f"Expected 'count' key in response: {data}"
    assert "has_more" in data, f"Expected 'has_more' key in response: {data}"

    assert isinstance(data["receipts"], list), "receipts should be a list"
    assert isinstance(data["count"], int), "count should be an integer"
    assert isinstance(data["has_more"], bool), "has_more should be a boolean"


def test_list_receipts_with_limit(client: TestClient) -> None:
    """Test GET /api/mind/receipts/ with limit parameter."""
    response = client.get("/api/mind/receipts/?limit=10")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert len(data["receipts"]) <= 10, "Should respect limit parameter"


def test_search_receipts_endpoint_exists(client: TestClient) -> None:
    """Test GET /api/mind/receipts/search endpoint exists."""
    response = client.get("/api/mind/receipts/search")

    # Should not return 404
    assert response.status_code != 404, "Receipt search endpoint should be registered"

    # Should return 200 (even if empty)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Check response structure
    data = response.json()
    assert "receipts" in data, f"Expected 'receipts' key in response: {data}"
    assert "total" in data, f"Expected 'total' key in response: {data}"
    assert "page" in data, f"Expected 'page' key in response: {data}"
    assert "pages" in data, f"Expected 'pages' key in response: {data}"
    assert "has_more" in data, f"Expected 'has_more' key in response: {data}"


def test_search_receipts_with_filters(client: TestClient) -> None:
    """Test GET /api/mind/receipts/search with filter parameters."""
    response = client.get("/api/mind/receipts/search?app=test&limit=5&page=1")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert isinstance(data["receipts"], list), "receipts should be a list"
    assert data["page"] == 1, "Should return requested page"


@pytest.mark.timeout(5)
def test_stream_receipts_endpoint_exists(app: FastAPI) -> None:
    """Test GET /api/mind/receipts/stream endpoint exists."""
    # For SSE streams, just verify the route is registered
    # We can't easily test streaming without hanging, so just check registration
    paths = [getattr(r, "path", None) for r in app.routes]

    # Check that the stream endpoint is registered
    assert any(
        "/api/mind/receipts/stream" in (p or "") for p in paths
    ), "Receipt stream endpoint should be registered"


def test_ingest_receipt_endpoint_exists(client: TestClient) -> None:
    """Test POST /api/mind/receipts/ endpoint exists (requires auth and idempotency)."""
    # Try without auth - should return 401, 403, or 400 (idempotency key), not 404
    response = client.post(
        "/api/mind/receipts/",
        json={"test": "data"},
        headers={"Idempotency-Key": "test-key-123"},
    )

    assert response.status_code != 404, "Receipt ingest endpoint should be registered"
    assert (
        response.status_code
        in (
            400,
            401,
            403,
        )
    ), f"Expected 400/401/403 (auth/validation required), got {response.status_code}: {response.text}"


def test_receipt_response_schema(client: TestClient) -> None:
    """Test that receipt responses match expected schema."""
    # Add a test receipt first (if we have access)
    # For now, just verify empty response has correct schema
    response = client.get("/api/mind/receipts/")
    assert response.status_code == 200

    data = response.json()

    # Verify top-level schema
    assert set(data.keys()) == {"receipts", "count", "has_more"}

    # If receipts exist, verify their schema
    if data["receipts"]:
        receipt = data["receipts"][0]
        required_fields = {
            "id",
            "correlation_id",
            "phase",
            "status",
            "timestamp",
            "duration_ms",
            "metadata",
        }
        assert required_fields.issubset(
            set(receipt.keys())
        ), f"Missing required fields in receipt: {receipt}"

        # Verify types
        assert isinstance(receipt["id"], str)
        assert isinstance(receipt["correlation_id"], str)
        assert receipt["phase"] in ("PLAN", "EXECUTE", "VERIFY")
        assert receipt["status"] in ("success", "failure", "partial")
        assert isinstance(receipt["duration_ms"], int)
        assert isinstance(receipt["metadata"], dict)


def test_search_receipt_response_schema(client: TestClient) -> None:
    """Test that search responses match expected schema."""
    response = client.get("/api/mind/receipts/search")
    assert response.status_code == 200

    data = response.json()

    # Verify search response schema
    assert set(data.keys()) == {"receipts", "total", "page", "pages", "has_more"}
    assert isinstance(data["receipts"], list)
    assert isinstance(data["total"], int)
    assert isinstance(data["page"], int)
    assert isinstance(data["pages"], int)
    assert isinstance(data["has_more"], bool)


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
