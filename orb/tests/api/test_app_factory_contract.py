"""App Factory Contract Tests

Tests the core contracts of the application factory.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import os

from fastapi import FastAPI

from tests.helpers import get_fastapi_app


def _make_app() -> tuple[FastAPI, object]:
    """Create app and return both the wrapper and inner FastAPI app.

    Returns:
        tuple: (inner FastAPI app, outer Socket.IO wrapper or None)
    """
    os.environ.setdefault("LIGHTWEIGHT_STARTUP", "1")
    os.environ.setdefault("ENVIRONMENT", "development")
    from kagami_api import create_app

    app = create_app()
    # Use helper to unwrap FastAPI app from Socket.IO if needed
    fastapi_app = get_fastapi_app(app)
    socketio_wrapper = app if hasattr(app, "other_asgi_app") else None
    return fastapi_app, socketio_wrapper


def test_app_factory_core_contract():
    """Test core factory contracts are met."""
    app, socketio_wrapper = _make_app()

    # Lifespan is set via factory
    assert app.router.lifespan_context is not None

    # Security and rate/input middlewares present (order not strictly enforced here)
    middleware_names = {mw.cls.__name__ for mw in app.user_middleware}
    # Security middleware class name comes from get_security_middleware() type
    assert any("Security" in name or "CSRFMiddleware" in name for name in middleware_names)
    assert any("GZipMiddleware" == name for name in middleware_names)

    # CORS configured
    assert any("CORSMiddleware" == name for name in middleware_names)

    # Static mount exists (either built dist or dev web) - optional in lightweight mode
    mount_names = {r.name for r in app.routes if getattr(r, "name", None)}
    # In lightweight startup mode, static routes may not be mounted
    if os.environ.get("LIGHTWEIGHT_STARTUP") != "1":
        assert "static" in mount_names or "static-dev" in mount_names

    # WebSocket/Realtime handler registered (Socket.IO wraps FastAPI)
    # Socket.IO handles /socket.io/* paths at the wrapper level, not as FastAPI routes
    assert socketio_wrapper is not None, "Socket.IO wrapper should be present"
    # Verify it has Socket.IO interface
    assert hasattr(socketio_wrapper, "other_asgi_app"), "Wrapper should have inner FastAPI app"


def test_health_and_metrics_surfaces_singleton():
    """Test health and metrics surfaces are registered."""
    app, _ = _make_app()
    paths = [getattr(r, "path", None) for r in app.routes]

    # Vitals/health routes exist (now at /api/vitals)
    assert any("/api/vitals" in (p or "") for p in paths), f"Expected vitals routes, got: {paths}"

    # Metrics single surface only
    assert paths.count("/metrics") == 1


def test_vitals_routes_registered():
    """Test vitals routes are properly registered."""
    app, _ = _make_app()
    paths = [getattr(r, "path", None) for r in app.routes]

    # Check for vitals probe routes
    vitals_paths = [p for p in paths if p and "/api/vitals" in p]
    assert len(vitals_paths) > 0, "Expected vitals routes to be registered"


def test_intents_routes_registered():
    """Test intents routes are properly registered."""
    app, _ = _make_app()
    paths = [getattr(r, "path", None) for r in app.routes]

    # Check for intents routes
    intents_paths = [p for p in paths if p and "/api/command" in p]
    assert len(intents_paths) > 0, "Expected intents routes to be registered"


def test_command_routes_registered():
    """Test command routes are properly registered."""
    app, _ = _make_app()
    paths = [getattr(r, "path", None) for r in app.routes]

    # Check for command routes
    command_paths = [p for p in paths if p and "/api/command" in p]
    assert len(command_paths) > 0, "Expected command routes to be registered"
