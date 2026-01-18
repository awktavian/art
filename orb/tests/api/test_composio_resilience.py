from __future__ import annotations
from typing import Any, Dict

import pytest

pytestmark = pytest.mark.tier_integration


import os
from unittest.mock import MagicMock

from kagami.core.services.composio import ComposioIntegrationService


class MockEntity:
    def __init__(self, fail_times: int):
        self.fail_times = fail_times

    def execute(self, action: Any, params: Any) -> dict[str, Any]:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("boom")
        return {"ok": True}


@pytest.mark.asyncio
async def test_composio_action_resilience(monkeypatch: Any) -> Any:
    svc = ComposioIntegrationService()
    # Fix initialization check in ActionExecutor
    svc.client.initialized = True

    # Mock the SDK client
    mock_entity = MockEntity(fail_times=2)
    mock_sdk = MagicMock()
    mock_sdk.entity.return_value = mock_entity
    svc.client.client = mock_sdk

    # Lower retries to 3 (default is often 3, but let's be explicit)
    monkeypatch.setenv("COMPOSIO_RETRY_ATTEMPTS", "3")
    # Ensure timeouts don't make test slow
    monkeypatch.setenv("COMPOSIO_TOOL_TIMEOUT_MS", "1000")

    # Should succeed after retries
    # Re-initialize executor to pick up env vars if needed, but they are read in __init__
    # So we should monkeypatch BEFORE creating service or create service after patching.
    # But we already created service. ActionExecutor reads env vars in its __init__.
    # So we need to manually update the executor's config or recreate it.
    svc.executor._retry_attempts = 3
    svc.executor._timeout_ms = 1000

    out = await svc.execute_action("github:create_issue", {"title": "t"}, user_id="user1")

    assert out.get("success") is True
    assert out.get("result", {}).get("ok") is True
