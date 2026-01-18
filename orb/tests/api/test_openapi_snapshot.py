"""OpenAPI Snapshot Tests

Tests that essential API paths exist in the OpenAPI spec.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
import os
from fastapi.testclient import TestClient
def _client() -> TestClient:
    os.environ.setdefault("LIGHTWEIGHT_STARTUP", "1")
    os.environ.setdefault("ENVIRONMENT", "development")
    from kagami_api import create_app
    return TestClient(create_app())
def test_actions_paths_exist_minimally():
    """Test that core API paths exist in OpenAPI spec."""
    c = _client()
    r = c.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = set((spec.get("paths") or {}).keys())
    # Minimal contract: ensure core paths exist
    # Vitals paths (health checks now at /api/vitals/probes/*)
    assert any("/api/vitals" in p for p in paths), f"Expected vitals paths in {paths}"
    # Auth paths (now at /api/user)
    assert any("/api/user" in p for p in paths), f"Expected user paths in {paths}"
    # Intents paths
    assert "/api/command/suggest" in paths
    assert "/api/command/parse" in paths
    assert "/api/command/nl" in paths
    assert "/api/command/execute" in paths
def test_openapi_has_metrics():
    """Test that /metrics is in OpenAPI or at least accessible."""
    c = _client()
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "kagami_" in r.text
def test_openapi_has_command_routes():
    """Test that command routes are in OpenAPI spec."""
    c = _client()
    r = c.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = set((spec.get("paths") or {}).keys())
    # Command paths
    assert any("/api/command" in p for p in paths), f"Expected command paths in {paths}"
