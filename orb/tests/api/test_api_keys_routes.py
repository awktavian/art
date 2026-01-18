from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
import uuid

from fastapi.testclient import TestClient

from kagami_api import create_app


def test_api_keys_create_list_revoke(monkeypatch: Any) -> None:
    os.environ.setdefault("KAGAMI_TEST_NO_CLOUD", "1")
    app = create_app()
    client = TestClient(app)
    r = client.post("/api/keys", headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code in (200, 401, 403)
    if r.status_code != 200:
        return
    data = r.json()
    assert data.get("api_key")
    kid = data.get("key_id")
    r2 = client.get("/api/keys")
    assert r2.status_code == 200
    arr = r2.json()
    assert isinstance(arr, list)
    r3 = client.delete(f"/api/keys/{kid}", headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r3.status_code == 200
    j = r3.json()
    assert j.get("revoked") is True
