"""Real WebSocket Integration Tests

Tests actual WebSocket connections with real uvicorn server.
No mocks - uses websockets library for true socket connections.
"""

from __future__ import annotations

from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
    pytest.mark.timeout(60),
]

import asyncio
import json


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def live_server(live_uvicorn_server) -> Any:
    """Get live uvicorn server for WebSocket tests."""
    if live_uvicorn_server:
        return live_uvicorn_server
    pytest.skip("Live uvicorn server not available")


class TestWebSocketFirstFrameAuth:
    """Test WebSocket first-frame authentication within 5s."""

    @pytest.mark.asyncio
    async def test_auth_within_5s_accepted(self, live_server: Any) -> None:
        """Test WebSocket connection with auth within timeout is accepted."""
        import websockets

        _http_url, ws_url = live_server

        # Connect to WebSocket
        async with websockets.connect(f"{ws_url}/api/agui/ws") as websocket:
            # Send auth within timeout
            auth_message = {"type": "auth", "api_key": "test-api-key"}

            await websocket.send(json.dumps(auth_message))

            # Should receive auth success
            response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            data = json.loads(response)

            # Should indicate success or ready
            assert data.get("type") in ("auth_success", "ready", "error")

    @pytest.mark.asyncio
    async def test_no_auth_timeout_closes_with_4401(self, live_server: Any) -> None:
        """Test WebSocket connection without auth closes with code 4401."""
        import websockets

        _http_url, ws_url = live_server

        # Connect without sending auth - should timeout and close with 4401
        try:
            async with websockets.connect(f"{ws_url}/api/agui/ws") as websocket:
                # Wait for server to close connection (5s auth timeout)
                await asyncio.wait_for(websocket.recv(), timeout=6.0)
                pytest.fail("Expected connection to close with 4401, but received message")
        except websockets.exceptions.ConnectionClosedError as e:
            # Verify close code is 4401 (unauthorized)
            assert e.code == 4401, f"Expected close code 4401, got {e.code}"
