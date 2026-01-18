from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
from kagami_api.security_middleware import SecurityMiddleware
def test_sanitize_html_basic():
    mw = SecurityMiddleware(app=None, enable_xss_protection=True)
    dirty = "<script>alert(1)</script><b>ok</b>"
    cleaned = mw.sanitize_html(dirty)
    assert "<script" not in cleaned
    assert "<b>ok</b>" in cleaned
from fastapi import FastAPI
from fastapi.testclient import TestClient
def test_security_middleware_integration_headers(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)
    @app.get("/ping")
    def ping():
        return {"ok": True}
    client = TestClient(app)
    r = client.get("/ping")
    # Core security headers present
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") in {"DENY", "SAMEORIGIN"}
    assert r.json()["ok"] is True
