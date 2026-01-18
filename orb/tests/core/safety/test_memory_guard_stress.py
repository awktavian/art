
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


import asyncio
import time
from unittest.mock import MagicMock, patch
from kagami.core.safety.agent_memory_guard import AgentMemoryGuard, MemoryLimit


@pytest.mark.asyncio
async def test_memory_guard_stress_simulation():
    """
    Stress test for AgentMemoryGuard using simulated memory pressure.
    Note: Guard enforces minimum soft limit of 1.0 GB.
    """
    # 1. Setup
    guard = AgentMemoryGuard()
    guard.enabled = True
    agent_name = "chaos_test_agent"

    # Set limits (enforced min: soft >= 1.0, hard >= soft + 1.0)
    guard.register_agent(agent_name=agent_name, soft_limit_gb=1.5, hard_limit_gb=3.0)

    with patch.object(AgentMemoryGuard, "get_agent_memory_usage") as mock_usage:
        # Scenario 1: Safe usage (1.0 < 1.5)
        mock_usage.return_value = 1.0
        assert not guard.should_abort(agent_name), "Should not abort on safe usage"

        # Scenario 2: Soft limit breach (2.0 > 1.5)
        mock_usage.return_value = 2.0
        assert not guard.should_abort(agent_name), "Should not abort immediately on soft limit"
        assert (
            guard.soft_violation_time[agent_name] is not None
        ), "Soft violation time should be set"

        # Scenario 3: Hard limit breach (4.0 > 3.0)
        mock_usage.return_value = 4.0
        assert guard.should_abort(agent_name), "MUST abort on hard limit violation"


@pytest.mark.asyncio
async def test_grace_period_enforcement():
    """Test that soft limit violations enforce grace period."""
    guard = AgentMemoryGuard()
    guard.enabled = True
    name = "grace_test"
    guard.register_agent(name, soft_limit_gb=1.5, hard_limit_gb=3.0)

    with patch.object(AgentMemoryGuard, "get_agent_memory_usage", return_value=2.0):
        # 1. First check - starts grace period
        assert not guard.should_abort(name)
        start_time = guard.soft_violation_time[name]
        assert start_time is not None

        # 2. Check immediately - should still be safe (within grace)
        assert not guard.should_abort(name)

        # 3. Fast forward time past grace period
        guard.soft_violation_time[name] = time.time() - 6.0

        # 4. Check again - should abort now
        assert guard.should_abort(name), "Should abort after grace period expiration"
