from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
import uuid

from fastapi.testclient import TestClient

from kagami_api import create_app


def test_api_keys_create_with_metadata_and_revoke(monkeypatch: Any) -> None:
    os.environ.setdefault("KAGAMI_TEST_NO_CLOUD", "1")
    app = create_app()
    client = TestClient(app)
    payload = {
        "label": "CI key",
        "scopes": ["read", "write"],
        "expires_at": "2099-01-01T00:00:00Z",
    }
    r = client.post("/api/keys", json=payload, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code in (200, 401, 403)
    if r.status_code != 200:
        return
    data = r.json()
    assert data.get("label") == "CI key"
    kid = data.get("key_id")
    # list
    r2 = client.get("/api/keys")
    assert r2.status_code == 200
    arr = r2.json()
    found = [x for x in arr if x.get("key_id") == kid]
    assert len(found) == 1
    assert found[0].get("scopes") == ["read", "write"]
    # revoke
    r3 = client.delete(f"/api/keys/{kid}", headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r3.status_code == 200
    assert r3.json().get("revoked") is True
