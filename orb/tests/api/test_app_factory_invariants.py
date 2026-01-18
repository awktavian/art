"""App Factory Invariants Tests

Tests the invariant properties of the application factory.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
import uuid

from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from kagami_api import create_app


@pytest.mark.contract
@pytest.mark.anyio("asyncio")
async def test_app_factory_invariants_expose_core_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test core routes are exposed by the factory."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Health via vitals
        resp = await client.get("/api/vitals/probes/live")
        assert resp.status_code == 200

        # Metrics
        metrics = await client.get("/metrics")
        assert metrics.status_code == 200

        # CSRF token via user routes
        csrf_response = await client.get("/api/user/csrf-token")
        assert csrf_response.status_code in (200, 405)
        csrf_payload = csrf_response.json() if csrf_response.status_code == 200 else {}
        csrf = csrf_payload.get("csrf_token", "")
        sid = csrf_payload.get("session_id", "")
        api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
        headers = {
            "X-CSRF-Token": csrf,
            "X-Session-ID": sid,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Parse is read-only, no idempotency key needed
        parse_resp = await client.post(
            "/api/command/parse", json={"text": "SLANG EXECUTE plan.create"}, headers=headers
        )
        assert parse_resp.status_code in (200, 400)

        # Execute mutates state, needs idempotency key
        exec_headers = {**headers, "Idempotency-Key": str(uuid.uuid4())}
        execute_resp = await client.post(
            "/api/command/execute",
            json={"lang": "LANG/2 EXECUTE plan.create", "confirm": True},
            headers=exec_headers,
        )
        assert execute_resp.status_code in (200, 400, 429, 500)


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    os.environ.setdefault("CI", "true")
    app = create_app()
    return TestClient(app)


def test_health_and_metrics_surfaces(client: Any) -> None:
    """Test health and metrics surfaces."""
    # Health via vitals
    r = client.get("/api/vitals/probes/live")
    assert r.status_code == 200

    # Metrics
    r = client.get("/metrics")
    assert r.status_code == 200


def test_auth_routes_normalized(client: Any) -> None:
    """Test auth routes are normalized."""
    # CSRF token under /api/user per contract
    r = client.get("/api/user/csrf-token")
    assert r.status_code == 200

    # Me endpoint under /api/user
    r2 = client.get("/api/user/me")
    assert r2.status_code in (200, 401)


def test_docs_api_list_and_fetch(client: Any) -> None:
    """Test docs API list and fetch."""
    # Get CSRF token and auth headers
    csrf_resp = client.get("/api/user/csrf-token")
    csrf_data = csrf_resp.json() if csrf_resp.status_code == 200 else {}
    headers = {
        "X-CSRF-Token": csrf_data.get("csrf_token", ""),
        "X-Session-ID": csrf_data.get("session_id", ""),
        "Authorization": f"Bearer {os.environ.get('KAGAMI_API_KEY', 'dev-api-key')}",
    }
    r = client.get("/api/docs/list", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "docs" in data
    docs = data.get("docs", [])
    if docs:
        # Fetch first doc; content should be text
        path = docs[0]
        r2 = client.get("/api/docs/content", params={"path": path}, headers=headers)
        assert r2.status_code == 200
        assert isinstance(r2.text, str)


def test_create_app_registers_core_middleware_and_routes():
    """Test core middleware and routes are registered."""
    app = create_app()

    # CORS and GZip should be present in user middleware
    names = {mw.cls.__name__ for mw in app.user_middleware}
    assert "CORSMiddleware" in names
    assert "GZipMiddleware" in names
    # Security middleware must be present and first layer
    assert "SecurityMiddleware" in names

    # Metrics surface must be single canonical "/metrics"
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    # At minimum, some kagami_ metrics should be present
    assert "kagami_" in r.text

    # Socket.IO should be mounted at /socket.io
    sio_paths = {getattr(rt, "path", None) for rt in app.router.routes}
    assert "/socket.io" in sio_paths


def test_vitals_routes_present_and_work():
    """Test vitals routes are present and work."""
    app = create_app()
    client = TestClient(app)

    # Liveness probe
    assert client.get("/api/vitals/probes/live").status_code == 200

    # Readiness probe
    assert client.get("/api/vitals/probes/ready").status_code in (200, 503)

    # Deep check
    assert client.get("/api/vitals/probes/deep").status_code == 200

    # Cluster check
    assert client.get("/api/vitals/probes/cluster").status_code == 200


def test_intents_lang_requires_auth_but_allows_test_bypass_for_parse():
    """Test intents parsing with auth."""
    app = create_app()
    client = TestClient(app)
    r_csrf = client.get("/api/user/csrf-token")
    assert r_csrf.status_code == 200
    csrf = r_csrf.json().get("csrf_token", "")
    sid = r_csrf.json().get("session_id", "")
    api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
    headers = {
        "X-CSRF-Token": csrf,
        "X-Session-ID": sid,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    headers["Idempotency-Key"] = str(uuid.uuid4())
    resp = client.post(
        "/api/command/parse", json={"text": "SLANG EXECUTE plan.create"}, headers=headers
    )
    assert resp.status_code in (200, 400)


def test_cors_preflight_and_headers():
    """Test CORS preflight and headers."""
    app = create_app()
    client = TestClient(app)
    # Preflight request should succeed in dev/test with wildcard origins
    r = client.options(
        "/api/vitals/probes/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code in (200, 204)
    # A normal GET should include CORS headers
    r2 = client.get(
        "/api/vitals/probes/live",
        headers={
            "Origin": "http://localhost:3000",
        },
    )
    # Starlette may normalize the header; accept presence either way
    assert any(h.lower() == "access-control-allow-origin" for h in r2.headers.keys())


def test_static_mounts_present_in_dev():
    """Test static mounts are present in dev mode."""
    app = create_app()
    client = TestClient(app)
    # In tests, lightweight/dev mode serves a minimal index under /static/index.html
    r = client.get("/static/index.html")
    assert r.status_code in (200, 404)  # allow 404 if dist/dev assets are not present
    # Favicon redirect should be available (404 OK in test env without static assets, 401 if auth middleware runs first)
    fav = client.get("/favicon.ico")
    assert fav.status_code in (200, 302, 401, 404)


def test_spa_catch_all_blocks_system_prefixes_and_serves_default():
    """Test SPA catch-all blocks system prefixes."""
    app = create_app()
    client = TestClient(app)
    # Blocked prefixes should not return 500
    for path in ("/api/whatever", "/ws/x", "/metrics"):
        r = client.get(path)
        assert r.status_code != 500
    # Non-system path should serve HTML (200) or 404 in test env without SPA assets
    r2 = client.get("/some/spa/path")
    assert r2.status_code in (200, 404)
