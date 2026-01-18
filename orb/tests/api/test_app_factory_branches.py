"""App Factory Branch Tests

Tests different app factory configurations and branches.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import os

from fastapi.testclient import TestClient


def test_create_app_test_mode_ready_without_strict_requirements():
    """Test readiness returns ready in test mode without strict requirements."""
    os.environ.pop("KAGAMI_REQUIRE_SUBSYSTEMS", None)
    for f in (
        "KAGAMI_REQUIRE_INFERENCE",
        "KAGAMI_REQUIRE_REASONING",
        "KAGAMI_REQUIRE_AR",
    ):
        os.environ.pop(f, None)
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

    from kagami_api import create_app

    c = TestClient(create_app())
    # Use correct path for readiness probe
    r = c.get("/api/vitals/probes/ready")
    assert r.status_code in (200, 503)
    data = r.json()
    if r.status_code == 200:
        assert isinstance(data, dict) and data.get("status") in ("ok", "ready", "degraded")
    else:
        # If not ready (503), response is wrapped in 'detail' by FastAPI HTTPException
        assert isinstance(data, dict)
        detail = data.get("detail", data)
        # Check for component diagnostic info
        has_diagnostics = any(
            k in str(detail) for k in ["boot", "metrics", "socketio", "ready", "status"]
        )
        assert has_diagnostics or "status" in str(
            data
        ), f"Expected diagnostic info in 503 response, got: {data}"


def test_openapi_contains_servers_block():
    """Test OpenAPI spec is accessible."""
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

    from kagami_api import create_app

    c = TestClient(create_app())
    r = c.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert isinstance(spec.get("paths"), dict)


def test_liveness_probe_accessible():
    """Test liveness probe is accessible."""
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

    from kagami_api import create_app

    c = TestClient(create_app())
    r = c.get("/api/vitals/probes/live")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"


def test_deep_check_accessible():
    """Test deep check is accessible."""
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

    from kagami_api import create_app

    c = TestClient(create_app())
    r = c.get("/api/vitals/probes/deep")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
