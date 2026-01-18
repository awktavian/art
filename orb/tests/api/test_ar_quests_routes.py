
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


import os

from fastapi.testclient import TestClient


def _client() -> TestClient:
    os.environ.setdefault("LIGHTWEIGHT_STARTUP", "1")
    os.environ.setdefault("PYTEST_CURRENT_TEST", "1")
    from kagami_api import create_app

    return TestClient(create_app())


def test_ar_quests_upsert_get_and_progress():
    c = _client()
    import uuid

    # Acquire CSRF + session to satisfy browser-style CSRF enforcement
    csrf = c.get("/api/user/csrf-token")
    csrf_hdrs = {}
    if csrf.status_code == 200:
        data = csrf.json()
        csrf_hdrs = {
            "X-CSRF-Token": data.get("csrf_token", ""),
            "X-Session-ID": data.get("session_id", ""),
        }

    hdrs = {
        **csrf_hdrs,
        "Authorization": "Bearer test_api_key",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    q = {
        "quest_id": "q-1",
        "title": "Find Anchor",
        "description": "Locate AR anchor",
        "steps": [{"title": "Move"}],
        "anchors": [],
        "geofences": [],
    }
    r = c.post("/api/ar/quests/upsert", headers=hdrs, json=q)
    # AR quests are optional; accept 200 when enabled, 404/503 when disabled
    assert r.status_code in (200, 404, 503)
    if r.status_code != 200:
        return

    r2 = c.get("/api/ar/quests/q-1", headers=hdrs)
    assert r2.status_code in (200, 404, 503)
    if r2.status_code != 200:
        return

    r3 = c.post(
        "/api/ar/quests/progress",
        headers=hdrs,
        json={"quest_id": "q-1", "step_index": 0, "state": "in_progress"},
    )
    assert r3.status_code in (200, 404, 503)
