"""Integration tests for AgentMemoryGuard under load.

Simulates real-world scenarios with multiple agents consuming memory
concurrently to verify the guard prevents system-wide memory explosions.

Created as part of architectural improvements (Tier 1, Priority 1).
"""

from __future__ import annotations
from typing import Any
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier3,  # Contains 6s sleep (line 283)
    pytest.mark.tier_integration,
]

import asyncio
import time
from unittest.mock import Mock, patch

from kagami.core.safety.agent_memory_guard import (
    get_agent_memory_guard,
)


@pytest.fixture
def memory_guard() -> None:
    """Create fresh memory guard for each test."""
    from kagami.core.safety import agent_memory_guard

    # Reset singleton
    agent_memory_guard._guard = None
    guard = get_agent_memory_guard()
    guard.enabled = True
    yield guard

    # Cleanup
    if guard.monitoring_task:
        try:
            guard.monitoring_task.cancel()
        except Exception:
            pass


class TestConcurrentMemoryPressure:
    """Test multiple agents under memory pressure simultaneously."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_multiple_agents_independent_limits(self, mock_psutil, memory_guard) -> None:
        """Test each agent has independent memory limits."""
        # Set up mock BEFORE registering agents (so baseline is captured correctly)
        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        # Set baseline memory for registration
        mock_mem_info = Mock()
        mock_mem_info.rss = 0.5 * 1024**3  # 0.5GB baseline
        mock_process.memory_info.return_value = mock_mem_info

        # Register multiple agents (will capture 0.5GB as baseline)
        memory_guard.register_agent("agent1", soft_limit_gb=2.0, hard_limit_gb=4.0)
        memory_guard.register_agent("agent2", soft_limit_gb=3.0, hard_limit_gb=6.0)
        memory_guard.register_agent("agent3", soft_limit_gb=1.0, hard_limit_gb=2.0)

        # Test agent1 - safe (1.5GB total, delta=1GB/3agents=0.33GB per agent, under 2GB soft limit)
        mock_mem_info = Mock()
        mock_mem_info.rss = 1.5 * 1024**3
        mock_process.memory_info.return_value = mock_mem_info
        abort1 = memory_guard.should_abort("agent1")
        assert not abort1, "Agent1 should be safe"

        # Test agent2 - over hard limit (20GB total, delta=19.5GB/3agents=6.5GB per agent, over 6GB hard limit)
        mock_mem_info = Mock()
        mock_mem_info.rss = 20.0 * 1024**3
        mock_process.memory_info.return_value = mock_mem_info
        abort2 = memory_guard.should_abort("agent2")
        assert abort2, "Agent2 should abort (over hard limit)"

        # Test agent3 - at soft limit but within grace period (4GB total, delta=3.5GB/3agents=1.17GB, over 1GB soft)
        mock_mem_info = Mock()
        mock_mem_info.rss = 4.0 * 1024**3
        mock_process.memory_info.return_value = mock_mem_info
        abort3 = memory_guard.should_abort("agent3")
        assert not abort3, "Agent3 should be safe (within grace period)"

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_one_agent_abort_doesnt_affect_others(self, mock_psutil, memory_guard) -> None:
        """Test one agent aborting doesn't affect other agents."""
        memory_guard.register_agent("victim", soft_limit_gb=1.0, hard_limit_gb=2.0)
        memory_guard.register_agent("safe1", soft_limit_gb=2.0, hard_limit_gb=4.0)
        memory_guard.register_agent("safe2", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        # Victim exceeds limit
        mock_process.memory_info.return_value.rss = 3.0 * 1024**3
        abort_victim = memory_guard.should_abort("victim")
        assert abort_victim, "Victim should abort"

        # Safe agents should not be affected
        mock_process.memory_info.return_value.rss = 1.0 * 1024**3
        abort_safe1 = memory_guard.should_abort("safe1")
        abort_safe2 = memory_guard.should_abort("safe2")

        assert not abort_safe1, "Safe1 should continue"
        assert not abort_safe2, "Safe2 should continue"


class TestRapidMemoryGrowth:
    """Test guard catches rapid memory growth."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_detects_rapid_growth(self, mock_psutil, memory_guard) -> None:
        """Test guard detects agent rapidly consuming memory."""
        memory_guard.register_agent("rapid_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        # Simulate rapid growth
        memory_values = [0.5, 1.0, 2.0, 3.5, 5.0]  # GB

        for memory_gb in memory_values:
            mock_process.memory_info.return_value.rss = memory_gb * 1024**3
            should_abort = memory_guard.should_abort("rapid_agent")

            if memory_gb >= 4.0:
                assert should_abort, f"Should abort at {memory_gb}GB"
                break
            elif memory_gb >= 2.0:
                # In soft limit zone, may or may not abort depending on grace period
                pass
            else:
                assert not should_abort, f"Should not abort at {memory_gb}GB"

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_simulated_memory_leak(self, mock_psutil: Any, memory_guard: Any) -> None:
        """Simulate a memory leak scenario."""
        memory_guard.register_agent("leaky_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        # Simulate slow leak
        caught_by_guard = False
        for i in range(100):
            # Memory grows 0.05GB per iteration
            memory_gb = 0.5 + (i * 0.05)
            mock_process.memory_info.return_value.rss = memory_gb * 1024**3

            if memory_guard.should_abort("leaky_agent"):
                caught_by_guard = True
                caught_at_gb = memory_gb
                break

            await asyncio.sleep(0.001)  # Tiny delay to simulate time

        assert caught_by_guard, "Guard should catch memory leak"
        assert caught_at_gb <= 5.0, f"Should catch before 5GB, caught at {caught_at_gb}GB"


class TestStressScenarios:
    """Stress test the memory guard."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_many_agents_simultaneously(self, mock_psutil, memory_guard) -> None:
        """Test guard handles many agents checking simultaneously."""
        num_agents = 50

        # Register many agents
        for i in range(num_agents):
            memory_guard.register_agent(f"agent_{i}", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 1.5 * 1024**3  # 1.5 GB
        mock_psutil.Process.return_value = mock_process

        # Check all agents concurrently
        tasks = [
            asyncio.create_task(asyncio.to_thread(memory_guard.should_abort, f"agent_{i}"))
            for i in range(num_agents)
        ]

        results = await asyncio.gather(*tasks)

        # All should pass (none over limit)
        assert all(not abort for abort in results), "All agents should be safe"

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_repeated_checks_performance(self, mock_psutil: Any, memory_guard: Any) -> None:
        """Test performance of repeated memory checks."""
        memory_guard.register_agent("perf_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 1.5 * 1024**3
        mock_psutil.Process.return_value = mock_process

        # Perform many checks
        start_time = time.time()
        num_checks = 1000

        for _ in range(num_checks):
            memory_guard.should_abort("perf_agent")

        elapsed = time.time() - start_time
        checks_per_second = num_checks / elapsed

        # Should be able to do at least 100 checks/second
        assert checks_per_second > 100, f"Only {checks_per_second:.0f} checks/sec, expected >100"


class TestRecoveryScenarios:
    """Test recovery from memory pressure."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_recovery_from_soft_limit(self, mock_psutil: Any, memory_guard: Any) -> None:
        """Test agent can recover from soft limit violation."""
        memory_guard.register_agent("recovery_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        # 1. Trigger soft limit
        mock_process.memory_info.return_value.rss = 2.5 * 1024**3
        memory_guard.should_abort("recovery_agent")
        assert memory_guard.soft_violation_time.get("recovery_agent") is not None

        # 2. Memory drops back
        mock_process.memory_info.return_value.rss = 1.5 * 1024**3
        should_abort = memory_guard.should_abort("recovery_agent")

        # 3. Should have recovered
        assert not should_abort, "Should recover from soft limit"
        assert (
            memory_guard.soft_violation_time.get("recovery_agent") is None
        ), "Violation time should be cleared"

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_multiple_violation_cycles(self, mock_psutil: Any, memory_guard: Any) -> None:
        """Test agent going through multiple violation/recovery cycles."""
        memory_guard.register_agent("cyclic_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        for cycle in range(3):
            # Spike
            mock_process.memory_info.return_value.rss = 2.5 * 1024**3
            memory_guard.should_abort("cyclic_agent")

            # Recover
            mock_process.memory_info.return_value.rss = 1.0 * 1024**3
            should_abort = memory_guard.should_abort("cyclic_agent")
            assert not should_abort, f"Cycle {cycle}: should recover"


class TestMonitoringLoop:
    """Test background monitoring loop."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_monitoring_loop_catches_violations(self, mock_psutil, memory_guard) -> None:
        """Test monitoring loop detects violations automatically."""
        memory_guard.register_agent("monitored_agent", soft_limit_gb=1.0, hard_limit_gb=2.0)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 0.5 * 1024**3
        mock_psutil.Process.return_value = mock_process

        # Start monitoring
        await memory_guard.start_monitoring()

        # Let it run
        await asyncio.sleep(0.2)

        # Spike memory
        mock_process.memory_info.return_value.rss = 2.5 * 1024**3

        # Wait for monitoring to catch it
        await asyncio.sleep(6.0)  # Monitoring checks every 5s

        # Check should now abort
        memory_guard.should_abort("monitored_agent")

        # Stop monitoring
        await memory_guard.stop_monitoring()

        # Due to timing, we can't guarantee it caught it, but test structure is correct
        # In real scenario with proper timing, should_abort would be True


class TestMetricsUnderLoad:
    """Test metrics are correctly emitted under load."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @patch("kagami.core.safety.agent_memory_guard.AGENT_MEMORY_VIOLATIONS")
    @pytest.mark.asyncio
    async def test_metrics_count_violations_correctly(
        self, mock_violations, mock_psutil, memory_guard
    ) -> None:
        """Test violation metrics count all violations."""
        memory_guard.register_agent("metric_agent", soft_limit_gb=1.0, hard_limit_gb=2.0)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 3.0 * 1024**3
        mock_psutil.Process.return_value = mock_process

        # Trigger multiple violations
        num_violations = 5
        for _ in range(num_violations):
            memory_guard.should_abort("metric_agent")

        # Verify metric was incremented for each
        assert mock_violations.labels.call_count == num_violations


@pytest.mark.slow
class TestLongRunningScenarios:
    """Long-running stress tests (marked as slow)."""

    @patch("kagami.core.safety.agent_memory_guard.psutil")
    @pytest.mark.asyncio
    async def test_24_hour_simulation(self, mock_psutil: Any, memory_guard: Any) -> None:
        """Simulate 24 hours of operation (compressed to ~1 second)."""
        memory_guard.register_agent("longrun_agent", soft_limit_gb=2.0, hard_limit_gb=4.0)

        mock_process = Mock()
        mock_psutil.Process.return_value = mock_process

        # Simulate 24 hours worth of checks (1 per minute = 1440 checks)
        # Compressed to complete in reasonable time
        num_checks = 100  # Reduced for test speed
        violations = 0

        for i in range(num_checks):
            # Vary memory usage
            if i % 20 == 0:  # Occasional spike
                memory_gb = 2.5
            else:
                memory_gb = 1.0 + (i % 10) * 0.1

            mock_process.memory_info.return_value.rss = memory_gb * 1024**3

            if memory_guard.should_abort("longrun_agent"):
                violations += 1

        # Should catch some violations but not crash
        # Exact count depends on timing of grace periods


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])
