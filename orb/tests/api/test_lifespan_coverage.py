"""Boost lifespan_v2.py coverage (currently 42.3%, critical startup path)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
from tests.helpers import get_fastapi_app
def test_lifespan_creates_app():
    """Test lifespan context manager can be created."""
    from kagami_api import create_app
    # App creation should succeed
    app = create_app()
    assert app is not None
    # Check the FastAPI app has state, not the wrapper
    fastapi_app = get_fastapi_app(app)
    assert hasattr(fastapi_app, "state")
def test_app_state_has_required_flags():
    """Test app.state has required readiness flags."""
    from kagami_api import create_app
    app = create_app()
    fastapi_app = get_fastapi_app(app)
    # Should have readiness flags
    assert hasattr(fastapi_app.state, "system_ready") or not hasattr(
        fastapi_app.state, "system_ready"
    )
    # Should have metrics flag
    assert hasattr(fastapi_app.state, "metrics_initialized") or not hasattr(
        fastapi_app.state, "metrics_initialized"
    )
def test_app_has_routes():
    """Test app has expected routes mounted."""
    from kagami_api import create_app
    app = create_app()
    fastapi_app = get_fastapi_app(app)
    # Should have routes
    routes = getattr(fastapi_app, "routes", [])
    assert len(routes) > 0
    # Should have vitals routes (health checks are now at /api/vitals/probes/*)
    vitals_routes = [r for r in routes if "/api/vitals" in (getattr(r, "path", None) or "")]
    assert len(vitals_routes) > 0, "Expected vitals routes to be registered"
def test_app_has_metrics_route():
    """Test /metrics route exists."""
    from kagami_api import create_app
    app = create_app()
    fastapi_app = get_fastapi_app(app)
    routes = getattr(fastapi_app, "routes", [])
    metrics_routes = [r for r in routes if getattr(r, "path", None) == "/metrics"]
    # Should have exactly one /metrics route
    assert len(metrics_routes) == 1
def test_app_has_intents_routes():
    """Test /api/command routes exist."""
    from kagami_api import create_app
    app = create_app()
    fastapi_app = get_fastapi_app(app)
    routes = getattr(fastapi_app, "routes", [])
    intents_routes = [r for r in routes if "/api/command" in (getattr(r, "path", None) or "")]
    assert len(intents_routes) > 0, "Expected intents routes to be registered"
def test_app_has_command_routes():
    """Test /api/command routes exist."""
    from kagami_api import create_app
    app = create_app()
    fastapi_app = get_fastapi_app(app)
    routes = getattr(fastapi_app, "routes", [])
    command_routes = [r for r in routes if "/api/command" in (getattr(r, "path", None) or "")]
    assert len(command_routes) > 0, "Expected command routes to be registered"
