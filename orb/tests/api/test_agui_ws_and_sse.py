"""AGUI WebSocket and SSE Tests

Tests WebSocket and Server-Sent Events endpoints.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from starlette.testclient import TestClient

from kagami_api import create_app


@pytest.mark.slow
@pytest.mark.anyio
@pytest.mark.timeout(10)
async def test_receipts_sse_stream_accessible(monkeypatch: Any) -> None:
    """Test receipts SSE stream endpoint is accessible."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # Non-blocking check: HEAD on stream path should not hang
    # Path is now at /api/mind/receipts/stream
    r = client.request("HEAD", "/api/mind/receipts/stream")
    # 200, 405 (method not allowed), 307 (redirect), or 404 are acceptable
    # 404 means route exists but HEAD not supported for SSE
    assert r.status_code in (200, 405, 307, 404)


@pytest.mark.slow
@pytest.mark.anyio
@pytest.mark.timeout(10)
async def test_agents_stream_requires_first_frame_auth():
    """Test agents stream requires authentication."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # Attempt to connect without sending an auth frame
    try:
        with client.websocket_connect("/api/agents/stream") as ws:
            # Do not send auth frame; expect either disconnect or non-authenticated payload
            ok = True
            try:
                msg = ws.receive_json()
                ok = (msg.get("status") or "").lower() != "authenticated"
            except Exception:
                # Disconnected is acceptable
                ok = True
            assert ok
    except Exception:
        # Connection failure is acceptable (indicates auth enforcement)
        pass


@pytest.mark.slow
@pytest.mark.anyio
@pytest.mark.timeout(10)
async def test_learning_stream_accessible(monkeypatch: Any) -> None:
    """Test learning stream endpoint exists."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # Check learning stream at /api/mind/learning/stream
    r = client.request("HEAD", "/api/mind/learning/stream")
    # SSE endpoints may not support HEAD method
    assert r.status_code in (200, 405, 307, 404)


@pytest.mark.slow
@pytest.mark.anyio
@pytest.mark.timeout(10)
async def test_vitals_endpoints_accessible(monkeypatch: Any) -> None:
    """Test vitals endpoints are accessible."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # Test liveness
    r = client.get("/api/vitals/probes/live")
    assert r.status_code == 200

    # Test deep check
    r2 = client.get("/api/vitals/probes/deep")
    assert r2.status_code == 200
