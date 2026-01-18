
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


import asyncio
from unittest.mock import patch, MagicMock

from kagami.core.tasks.background_task_manager import BackgroundTaskManager


@pytest.mark.asyncio
async def test_background_task_manager_success_and_timeout():
    # Mock URF to verify receipt emission
    with patch("kagami.core.receipts.UnifiedReceiptFacade.emit") as mock_emit:
        mgr = BackgroundTaskManager()
        await mgr.start()

        async def quick_task():
            await asyncio.sleep(0.01)
            return "ok"

        name = await mgr.create_task("quick", quick_task())

        # Verify PLAN receipt
        assert mock_emit.call_count >= 1
        plan_call = mock_emit.call_args_list[0]
        assert plan_call.kwargs["action"] == "background_task.plan"
        assert plan_call.kwargs["event_name"] == "PLAN"

        correlation_id = plan_call.kwargs["correlation_id"]
        assert correlation_id is not None

        # Wait for completion (same loop)
        res = await mgr.wait_for_task(name, timeout=1.0)
        assert res == "ok"

        # Verify EXECUTE and VERIFY receipts
        calls = mock_emit.call_args_list
        execute_calls = [c for c in calls if c.kwargs.get("event_name") == "EXECUTE"]
        verify_calls = [c for c in calls if c.kwargs.get("event_name") == "VERIFY"]

        assert len(execute_calls) >= 1
        assert len(verify_calls) >= 1

        assert execute_calls[0].kwargs["correlation_id"] == correlation_id
        assert verify_calls[0].kwargs["correlation_id"] == correlation_id
        assert verify_calls[0].kwargs["status"] == "success"

        # Create a long task and enforce timeout in wait_for_task (poll branch)
        async def long_task():
            await asyncio.sleep(0.2)
            return "late"

        name2 = await mgr.create_task("slow", long_task())
        with pytest.raises(TimeoutError):
            await mgr.wait_for_task(name2, timeout=0.01)

        await mgr.stop()
