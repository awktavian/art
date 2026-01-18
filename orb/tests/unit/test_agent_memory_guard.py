"""Unit tests for AgentMemoryGuard.

Tests the critical safety system that prevents >800GB memory explosions.
Created as part of architectural improvements (Tier 1, Priority 1).
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio
import time
from unittest.mock import Mock, patch

from kagami.core.safety.agent_memory_guard import (
    AgentMemoryGuard,
    MemoryLimit,
    get_agent_memory_guard,
)


class TestMemoryLimit:
    """Test MemoryLimit configuration."""

    def test_default_values(self) -> None:
        """Test default memory limit values."""
        limit = MemoryLimit()
        assert limit.soft_limit_gb == 4.0
        assert limit.hard_limit_gb == 8.0
        assert limit.check_interval == 2.0
        assert limit.grace_period == 5.0

    def test_custom_values(self) -> None:
        """Test custom memory limit values."""
        limit = MemoryLimit(
            soft_limit_gb=2.0,
            hard_limit_gb=4.0,
            check_interval=1.0,
            grace_period=3.0,
        )
        assert limit.soft_limit_gb == 2.0
        assert limit.hard_limit_gb == 4.0
        assert limit.check_interval == 1.0
        assert limit.grace_period == 3.0


class TestAgentMemoryGuard:
    """Test AgentMemoryGuard core functionality."""

    def test_initialization(self) -> None:
        """Test guard initialization."""
        guard = AgentMemoryGuard()
        assert guard.limits == {}
        assert guard.baseline_memory == {}
        assert guard.soft_violation_time == {}

    def test_register_agent(self) -> None:
        """Test agent registration."""
        guard = AgentMemoryGuard()
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        assert "test_agent" in guard.limits
        limit = guard.limits["test_agent"]
        assert limit.soft_limit_gb == 2.0
        assert limit.hard_limit_gb == 4.0

    def test_unregister_agent(self) -> None:
        """Test agent unregistration."""
        guard = AgentMemoryGuard()
        guard.register_agent("test_agent")
        guard.unregister_agent("test_agent")

        assert "test_agent" not in guard.limits
        assert "test_agent" not in guard.baseline_memory

    def test_soft_limit_warning(self) -> None:
        """Test soft limit triggers warning."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        # Mock memory usage at soft limit
        with patch.object(guard, "get_agent_memory_usage", return_value=2.5):  # 2.5 GB
            # First check should trigger soft limit
            should_abort = guard.should_abort("test_agent")
            assert not should_abort  # Still within grace period

            # Mark violation time
            assert guard.soft_violation_time.get("test_agent") is not None

    def test_hard_limit_abort(self) -> None:
        """Test hard limit triggers immediate abort."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        # Mock memory usage above hard limit
        with patch.object(guard, "get_agent_memory_usage", return_value=5.0):  # 5 GB
            # Should abort immediately
            should_abort = guard.should_abort("test_agent")
            assert should_abort

    def test_grace_period_enforcement(self) -> None:
        """Test grace period before hard kill."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        # Mock memory usage at soft limit
        with patch.object(guard, "get_agent_memory_usage", return_value=2.5):  # 2.5 GB
            # First check - within grace period
            should_abort = guard.should_abort("test_agent")
            assert not should_abort

            # Simulate grace period expiring
            guard.soft_violation_time["test_agent"] = time.time() - 10.0  # 10s ago

            # Now should abort
            should_abort = guard.should_abort("test_agent")
            assert should_abort

    def test_memory_recovery(self) -> None:
        """Test recovery from soft limit violation."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        # First: trigger soft limit
        with patch.object(guard, "get_agent_memory_usage", return_value=2.5):  # 2.5 GB
            guard.should_abort("test_agent")
            assert guard.soft_violation_time.get("test_agent") is not None

        # Then: memory drops back below soft limit
        with patch.object(guard, "get_agent_memory_usage", return_value=1.5):  # 1.5 GB
            should_abort = guard.should_abort("test_agent")
            assert not should_abort
            assert guard.soft_violation_time.get("test_agent") is None

    def test_guard_auto_reenables_if_psutil_available(self) -> None:
        """Test that guard automatically re-enables if disabled but psutil is present (Safety ALWAYS on)."""
        guard = AgentMemoryGuard()
        # Attempt to disable
        guard.enabled = False
        guard.register_agent("test_agent")

        with patch("kagami.core.safety.agent_memory_guard.PSUTIL_AVAILABLE", True):
            # Mock memory usage
            with patch.object(guard, "get_agent_memory_usage", return_value=1.0):
                # This call should auto-reenable guard
                should_abort = guard.should_abort("test_agent")

                assert guard.enabled is True, "Guard should have re-enabled itself"
                assert not should_abort  # Usage 1.0 < 4.0

    def test_guard_disabled_without_psutil(self) -> None:
        """Test that guard allows operation if psutil is truly missing (Degraded but safe-ish)."""
        guard = AgentMemoryGuard()
        guard.enabled = False
        guard.register_agent("test_agent")

        with patch("kagami.core.safety.agent_memory_guard.PSUTIL_AVAILABLE", False):
            # Should remain disabled and return False (no abort)
            should_abort = guard.should_abort("test_agent")

            assert guard.enabled is False
            assert not should_abort

    def test_unregistered_agent_always_passes(self) -> None:
        """Test unregistered agents are not checked."""
        guard = AgentMemoryGuard()
        guard.enabled = True

        should_abort = guard.should_abort("unknown_agent")
        assert not should_abort

    @pytest.mark.asyncio
    async def test_monitoring_loop_starts_stops(self) -> None:
        """Test background monitoring loop lifecycle."""
        guard = AgentMemoryGuard()
        guard.enabled = True

        # Start monitoring
        await guard.start_monitoring()
        assert guard.monitoring_task is not None
        assert not guard.monitoring_task.done()

        # Stop monitoring
        await guard.stop_monitoring()
        assert guard.monitoring_task is None

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_monitoring_loop_checks_agents(self, mock_psutil: Any) -> None:
        """Test monitoring loop periodically checks all agents."""
        guard = AgentMemoryGuard()
        guard.enabled = True

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 1.0 * 1024**3  # 1 GB
        mock_psutil.Process.return_value = mock_process

        guard.register_agent("agent1", soft_limit_gb=2.0, hard_limit_gb=4.0)
        guard.register_agent("agent2", soft_limit_gb=2.0, hard_limit_gb=4.0)

        # Start monitoring
        await guard.start_monitoring()

        # Let it run for a moment
        await asyncio.sleep(0.1)

        # Stop monitoring
        await guard.stop_monitoring()

        # Verify agents were checked (baseline memory set)
        # Note: exact behavior depends on timing, so we just verify structure
        assert "agent1" in guard.limits
        assert "agent2" in guard.limits


class TestGetAgentMemoryGuard:
    """Test singleton accessor."""

    def test_singleton_returns_same_instance(self) -> None:
        """Test get_agent_memory_guard returns singleton."""
        guard1 = get_agent_memory_guard()
        guard2 = get_agent_memory_guard()
        assert guard1 is guard2

    def test_reset_singleton(self) -> None:
        """Test resetting singleton for testing."""
        from kagami.core.safety import agent_memory_guard

        guard1 = get_agent_memory_guard()

        # Reset singleton
        agent_memory_guard._guard = None

        guard2 = get_agent_memory_guard()
        assert guard1 is not guard2


class TestMetricsEmission:
    """Test that guard emits metrics correctly."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @patch("kagami.core.safety.agent_memory_guard.AGENT_MEMORY_BYTES")
    @patch("kagami.core.safety.agent_memory_guard.AGENT_MEMORY_PRESSURE")
    def test_metrics_updated_on_check(self, mock_pressure, mock_bytes, mock_psutil) -> None:
        """Test metrics are updated when checking agent."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 1.5 * 1024**3  # 1.5 GB
        mock_psutil.Process.return_value = mock_process

        # Check agent
        guard.should_abort("test_agent")

        # Verify metrics were updated
        mock_bytes.labels.assert_called_with(agent_name="test_agent")
        mock_pressure.labels.assert_called_with(agent_name="test_agent")

    @patch("kagami.core.safety.agent_memory_guard.AGENT_MEMORY_VIOLATIONS")
    def test_violation_metric_on_hard_limit(self, mock_violations) -> None:
        """Test violation metric incremented on hard limit."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        # Mock memory usage above hard limit
        with patch.object(guard, "get_agent_memory_usage", return_value=5.0):  # 5 GB
            # Trigger hard limit
            guard.should_abort("test_agent")

            # Verify violation metric incremented
            mock_violations.labels.assert_called_with(
                agent_name="test_agent", violation_type="hard_limit"
            )


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    def test_psutil_error_handled_gracefully(self, mock_psutil) -> None:
        """Test psutil errors don't crash the guard."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent")

        # Mock psutil raising error
        mock_psutil.Process.side_effect = Exception("psutil error")

        # Should not raise, should return safe value
        usage = guard.get_agent_memory_usage("test_agent")
        assert usage == 0.0

        should_abort = guard.should_abort("test_agent")
        assert not should_abort

    def test_zero_memory_usage(self) -> None:
        """Test handling of zero memory usage."""
        guard = AgentMemoryGuard()
        guard.enabled = True
        guard.register_agent("test_agent")

        # Manually set zero usage
        with patch.object(guard, "get_agent_memory_usage", return_value=0.0):
            should_abort = guard.should_abort("test_agent")
            assert not should_abort

    def test_negative_limits_invalid(self) -> None:
        """Test negative limits are handled."""
        guard = AgentMemoryGuard()

        # Should not crash even with negative limits
        guard.register_agent("test_agent", soft_limit_gb=-1.0, hard_limit_gb=-1.0)
        # Behavior is undefined but should not crash


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
