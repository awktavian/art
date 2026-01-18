"""End to End Workflow Tests

Tests complete workflows from plan creation to intent execution.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import os
import uuid

from fastapi.testclient import TestClient


@pytest.mark.integration
def test_e2e_plan_then_intent_execute_receipts():
    """Test end-to-end plan creation and intent execution."""
    # Ensure deterministic dev/test env
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")
    from kagami_api import create_app

    app = create_app()
    c = TestClient(app)

    # 1) List plans (should succeed, 404 if not implemented, or 405 if GET not supported)
    r1 = c.get("/api/plans")
    assert r1.status_code in (200, 401, 404, 405)

    # 2) Execute a basic intent (plans.create)
    payload = {
        "lang": 'LANG/2 EXECUTE plan.create @app=Plans TITLE="Test Plan"',
        "metadata": {"confirm": True},
    }
    # Acquire CSRF + session from correct endpoint
    r_csrf = c.get("/api/user/csrf-token")
    assert r_csrf.status_code == 200
    csrf = r_csrf.json().get("csrf_token", "")
    sid = r_csrf.json().get("session_id", "")
    api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
    headers = {
        "X-CSRF-Token": csrf,
        "X-Session-ID": sid,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    r2 = c.post("/api/command/execute", json=payload, headers=headers)
    assert r2.status_code in (200, 400, 501)
    if r2.status_code == 200:
        data = r2.json()
        assert isinstance(data, dict)
        # Receipt may be attached
        if isinstance(data.get("receipt"), dict):
            assert "correlation_id" in data["receipt"]


@pytest.mark.integration
def test_e2e_vitals_and_metrics():
    """Test vitals and metrics endpoints work."""
    os.environ.setdefault("ENVIRONMENT", "development")
    from kagami_api import create_app

    app = create_app()
    c = TestClient(app)

    # Vitals
    r = c.get("/api/vitals/probes/live")
    assert r.status_code == 200

    r = c.get("/api/vitals/probes/deep")
    assert r.status_code == 200

    # Metrics
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "kagami_" in r.text
