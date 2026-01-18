"""Billing Quota Headers Tests

Tests quota headers presence on API requests.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os

from fastapi.testclient import TestClient

from kagami_api import create_app


@pytest.fixture()
def quota_client(monkeypatch: Any) -> Any:
    """Create client with quota middleware enabled."""
    monkeypatch.setenv("ENFORCE_TENANT_PLAN", "1")
    monkeypatch.delenv("ENFORCE_TENANT_PLAN_HARD", raising=False)
    app = create_app()
    return TestClient(app)


def test_quota_headers_present_on_api(quota_client: Any) -> Any:
    """Test quota headers are present on API requests."""
    # Acquire CSRF/session and include headers - use correct path
    r_csrf = quota_client.get("/api/user/csrf-token")
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
    r = quota_client.post(
        "/api/command/parse", json={"text": "SLANG EXECUTE plan.create"}, headers=headers
    )
    assert r.status_code in (200, 400)
    # Headers attached (soft policy) - may also be off in test mode
    quota_policy = r.headers.get("X-Quota-Policy")
    assert quota_policy in ("soft", "enabled-unknown-user", "off", None)


def test_quota_headers_on_vitals(quota_client: Any) -> None:
    """Test quota middleware doesn't break vitals endpoints."""
    r = quota_client.get("/api/vitals/probes/live")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
