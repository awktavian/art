"""WebSocket Test Fixtures

Provides mock WebSocket infrastructure for testing without live server.

Usage:
    # For unit tests (no live server needed)
    def test_ws_feature(mock_websocket) -> None:
        mock_websocket.send_json({"type": "auth", "api_key": "test"})
        response = mock_websocket.receive_json()
        assert response["status"] == "authenticated"

    # For integration tests (requires live server)
    def test_ws_integration(live_uvicorn_server) -> None:
        base_http, base_ws = live_uvicorn_server
        # Use real WebSocket connection
"""

import asyncio
import json

import pytest
import pytest_asyncio


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.receive_queue = []
        self.closed = False
        self.accepted = False

    def send_json(self, data):
        """Mock send_json."""
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.sent_messages.append(data)

    def receive_json(self):
        """Mock receive_json."""
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        if not self.receive_queue:
            # Auto-respond based on sent messages
            if self.sent_messages:
                last_sent = self.sent_messages[-1]
                if last_sent.get("type") == "auth":
                    return {"status": "authenticated", "session_id": "mock-session"}
                else:
                    return {"status": "ok", "echo": last_sent}
            return {"status": "ok"}
        return self.receive_queue.pop(0)

    async def send(self, message):
        """Mock async send."""
        if isinstance(message, str):
            data = json.loads(message)
        else:
            data = message
        self.send_json(data)

    async def receive(self):
        """Mock async receive."""
        return json.dumps(self.receive_json())

    def close(self, code: int = 1000) -> None:
        """Mock close."""
        self.closed = True

    def queue_response(self, data: dict) -> None:
        """Queue a response to be received."""
        self.receive_queue.append(data)


class MockAsyncWebSocket:
    """Mock async WebSocket for testing with K os-specific behavior."""

    def __init__(self, auto_respond: bool = True, valid_api_key: str = "test-key"):
        self.sent_messages = []
        self.receive_queue = []
        self.closed = False
        self.authenticated = False
        self.session_id = None
        self.auto_respond = auto_respond
        self.valid_api_key = valid_api_key
        self._auth_timeout_task = None

    async def send_json(self, data):
        """Mock async send_json."""
        if self.closed:
            from starlette.websockets import WebSocketDisconnect

            raise WebSocketDisconnect(code=1000)
        self.sent_messages.append(data)

    async def send_text(self, text: str):
        """Mock async send_text."""
        data = json.loads(text)
        await self.send_json(data)

    async def receive_json(self):
        """Mock async receive_json with K os-specific responses."""
        if self.closed:
            from starlette.websockets import WebSocketDisconnect

            raise WebSocketDisconnect(code=1000)

        # Check queued responses first
        if self.receive_queue:
            return self.receive_queue.pop(0)

        # Auto-respond if enabled
        if self.auto_respond and self.sent_messages:
            last_sent = self.sent_messages[-1]

            # Handle authentication
            if last_sent.get("type") == "auth":
                api_key = last_sent.get("api_key") or last_sent.get("token")
                if api_key == self.valid_api_key or api_key == f"Bearer {self.valid_api_key}":
                    self.authenticated = True
                    self.session_id = f"mock-session-{len(self.sent_messages)}"  # type: ignore[assignment]
                    # Return connection + state_snapshot messages
                    self.queue_response({"type": "state_snapshot", "state": {}})
                    return {
                        "type": "connection",
                        "status": "authenticated",
                        "session_id": self.session_id,
                    }
                else:
                    self.closed = True
                    from starlette.websockets import WebSocketDisconnect

                    raise WebSocketDisconnect(code=4401, reason="Invalid credentials")

            # Handle other message types
            elif last_sent.get("type") == "message":
                return {
                    "type": "response",
                    "text": f"Echo: {last_sent.get('text', '')}",
                    "correlation_id": last_sent.get("correlation_id"),
                }

            # Generic response
            return {"status": "ok", "echo": last_sent}

        # No messages to respond to
        return {"status": "ok"}

    async def receive_text(self):
        """Mock async receive_text."""
        response = await self.receive_json()
        return json.dumps(response)

    async def close(self, code=1000):
        """Mock async close."""
        self.closed = True
        if self._auth_timeout_task:
            self._auth_timeout_task.cancel()

    def queue_response(self, data):
        """Queue a response."""
        self.receive_queue.append(data)

    def reset(self):
        """Reset the mock WebSocket state."""
        self.sent_messages = []
        self.receive_queue = []
        self.closed = False
        self.authenticated = False
        self.session_id = None


# Pytest fixtures


@pytest.fixture
def mock_websocket():
    """Provide a mock WebSocket for sync tests."""
    return MockWebSocket()


@pytest.fixture
def mock_async_websocket():
    """Provide a mock async WebSocket."""
    return MockAsyncWebSocket()


# Example usage in tests


@pytest.mark.asyncio
async def test_example_ws_auth(mock_async_websocket) -> None:
    """Example: Test WebSocket authentication."""
    # Send auth
    await mock_async_websocket.send_json({"type": "auth", "api_key": "test-key"})

    # Receive response
    response = await mock_async_websocket.receive_json()

    # Validate
    assert response["status"] == "authenticated"
    assert "session_id" in response


@pytest.mark.asyncio
async def test_example_ws_reject_invalid_auth(mock_async_websocket) -> None:
    """Example: Test WebSocket rejects invalid auth."""
    from starlette.websockets import WebSocketDisconnect

    # Send invalid auth
    await mock_async_websocket.send_json({"type": "auth", "api_key": "invalid"})

    # Should disconnect
    with pytest.raises(WebSocketDisconnect) as exc_info:
        await mock_async_websocket.receive_json()

    assert exc_info.value.code == 4401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
