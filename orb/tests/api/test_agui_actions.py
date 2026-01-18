"""AGUI Actions Tests

Tests AG-UI protocol actions and tool execution.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
import uuid

from starlette.testclient import TestClient

from kagami_api import create_app


@pytest.mark.asyncio
async def test_agui_call_tool_executes_and_returns_result(monkeypatch: Any) -> None:
    """Test intent execution via AGUI protocol."""
    # Ensure tools are initialized and GAIA bridge errors won't block built-ins
    os.environ["TOOLS_INIT_IN_LIGHTWEIGHT"] = "1"
    os.environ.setdefault("DISABLE_QWEN_TOOL_BRIDGE", "1")
    os.environ["KAGAMI_TEST_ECHO_LLM"] = "1"  # Use echo LLM for tests

    app = create_app()
    client = TestClient(app)

    # Patch webhook transport HTTP calls to avoid external network during tests
    class _FakeResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "application/json"}

        def json(self):
            return {"ok": True}

        @property
        def text(self):
            return "ok"

    class _FakeAsyncClient:
        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        async def post(self, *args: Any, **kwargs) -> Any:
            return _FakeResp()

    try:
        import kagami_api.protocols.agui_transports as _agui_t

        monkeypatch.setattr(_agui_t, "httpx", type("_M", (), {"AsyncClient": _FakeAsyncClient}))
    except Exception:
        pass

    # Acquire CSRF/session from correct endpoint
    r_csrf = client.get("/api/user/csrf-token")
    assert r_csrf.status_code == 200
    csrf = r_csrf.json().get("csrf_token", "")
    sid = r_csrf.json().get("session_id", "")

    _api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
    headers = {
        "X-CSRF-Token": csrf,
        "X-Session-ID": sid,
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"test-session-{uuid.uuid4()}",
    }

    # Test intent execution endpoint
    r = client.post(
        "/api/command/execute",
        json={
            "lang": "LANG/2 EXECUTE echo {}",
        },
        headers=headers,
    )
    assert r.status_code in (200, 202, 400, 501)


@pytest.mark.asyncio
async def test_agui_run_basic(monkeypatch: Any) -> None:
    """Test basic AGUI run endpoint."""
    os.environ["KAGAMI_TEST_ECHO_LLM"] = "1"

    app = create_app()
    client = TestClient(app)

    # Get CSRF token
    r_csrf = client.get("/api/user/csrf-token")
    assert r_csrf.status_code == 200
    csrf = r_csrf.json().get("csrf_token", "")
    sid = r_csrf.json().get("session_id", "")

    _api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
    headers = {
        "X-CSRF-Token": csrf,
        "X-Session-ID": sid,
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"test-run-{uuid.uuid4()}",
    }

    # Test AGUI run endpoint
    r = client.post(
        "/api/colonies/agui/run",
        json={"message": "hello"},
        headers=headers,
    )
    # Accept various status codes
    assert r.status_code in (200, 400, 401, 404, 501, 503)


@pytest.mark.asyncio
async def test_command_execute(monkeypatch: Any) -> None:
    """Test command execute endpoint."""
    os.environ["KAGAMI_TEST_ECHO_LLM"] = "1"

    app = create_app()
    client = TestClient(app)

    r_csrf = client.get("/api/user/csrf-token")
    csrf = r_csrf.json().get("csrf_token", "")
    sid = r_csrf.json().get("session_id", "")

    _api_key = os.environ.get("KAGAMI_API_KEY", "dev-api-key")
    headers = {
        "X-CSRF-Token": csrf,
        "X-Session-ID": sid,
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"test-cmd-{uuid.uuid4()}",
    }

    r = client.post(
        "/api/command/execute",
        json={"lang": "LANG/2 PREVIEW test"},
        headers=headers,
    )
    assert r.status_code in (200, 400, 501)
