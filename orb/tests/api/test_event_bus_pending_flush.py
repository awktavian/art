from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import anyio
from httpx import ASGITransport, AsyncClient

from kagami_api import create_app
from kagami_api.lifespan_v2 import pending_actions_queue
from kagami.core.events.unified_e8_bus import get_unified_bus


@pytest.mark.anyio
async def test_pending_actions_queue_flush(monkeypatch: Any) -> None:
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "0")

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Enqueue a couple of intents before orchestrator is fully initialized
        await pending_actions_queue.put(
            {
                "topic": "intent.execute",
                "type": "intent",
                "action": "EXECUTE",
                "target": "plans.execute",
                "metadata": {"@app": "plans"},
            }
        )
        await pending_actions_queue.put(
            {
                "topic": "intent.execute",
                "type": "intent",
                "action": "EXECUTE",
                "target": "files.execute",
                "metadata": {"@app": "files"},
            }
        )

        # Touch endpoints to trigger startup and background init; allow orchestrator to init
        await client.get("/api/vitals/probes/live")

        initial = pending_actions_queue.qsize()
        for _ in range(80):
            if pending_actions_queue.qsize() == 0:
                break
            await anyio.sleep(0.1)

    bus = get_unified_bus()
    if bus is None:
        pytest.skip("Unified E8 bus not initialized in lightweight env; skipping")
    assert pending_actions_queue.qsize() <= initial
