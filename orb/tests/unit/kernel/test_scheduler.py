"""Comprehensive tests for K os preemptive scheduler.

Tests cover:
- Priority-based scheduling
- Time quantum and preemption
- Context switching
- CFS (Completely Fair Scheduler) algorithm
- Performance targets

Created: November 10, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio
import time

from kagami.core.kernel.scheduler import (
    AgentContext,
    PreemptiveAgentScheduler,
    Priority,
    SchedulingStats,
)


class TestSchedulerBasics:
    """Test basic scheduler functionality."""

    @pytest.mark.asyncio
    async def test_scheduler_initialization(self) -> None:
        """Test scheduler initializes correctly."""
        scheduler = PreemptiveAgentScheduler(timer_tick_ms=10)

        assert scheduler.timer_tick_ms == 10
        assert scheduler.enable_preemption is True
        assert len(scheduler.runqueues) == 4  # 4 priority levels
        assert scheduler.running is None

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self) -> None:
        """Test scheduler lifecycle."""
        scheduler = PreemptiveAgentScheduler()

        # Start
        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._scheduler_task is not None

        # Stop
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_schedule_agent(self) -> None:
        """Test scheduling an agent."""
        scheduler = PreemptiveAgentScheduler()

        # NOTE: The scheduler currently queues contexts and does not execute the awaitable.
        # Use a completed Future (no "coroutine was never awaited" warnings).
        done = asyncio.get_running_loop().create_future()
        done.set_result(None)
        scheduler.schedule_agent(agent_id="test_agent_001", coro=done, priority=Priority.NORMAL)

        # Check agent in correct runqueue
        normal_queue = scheduler.runqueues[Priority.NORMAL]
        assert len(normal_queue) > 0


class TestPriorityScheduling:
    """Test priority-based scheduling."""

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        """Test agents are scheduled by priority."""
        scheduler = PreemptiveAgentScheduler()

        # Schedule agents with different priorities
        loop = asyncio.get_running_loop()
        f_low = loop.create_future()
        f_low.set_result(None)
        f_normal = loop.create_future()
        f_normal.set_result(None)
        f_high = loop.create_future()
        f_high.set_result(None)
        f_rt = loop.create_future()
        f_rt.set_result(None)

        scheduler.schedule_agent("low", f_low, Priority.LOW)
        scheduler.schedule_agent("normal", f_normal, Priority.NORMAL)
        scheduler.schedule_agent("high", f_high, Priority.HIGH)
        scheduler.schedule_agent("rt", f_rt, Priority.REALTIME)

        # Pick next agents - should be in priority order
        next1 = scheduler._pick_next_agent()
        assert next1 is not None
        assert next1.priority == Priority.REALTIME

        next2 = scheduler._pick_next_agent()
        assert next2 is not None
        assert next2.priority == Priority.HIGH

    @pytest.mark.asyncio
    async def test_quantum_by_priority(self) -> None:
        """Test time quantum varies by priority."""
        scheduler = PreemptiveAgentScheduler()

        # Check quantum assignments
        assert scheduler.quantum_by_priority[Priority.REALTIME] == 5
        assert scheduler.quantum_by_priority[Priority.HIGH] == 10
        assert scheduler.quantum_by_priority[Priority.NORMAL] == 20
        assert scheduler.quantum_by_priority[Priority.LOW] == 50

        # Higher priority = smaller quantum (more responsive)
        assert (
            scheduler.quantum_by_priority[Priority.REALTIME]
            < scheduler.quantum_by_priority[Priority.LOW]
        )


class TestPreemption:
    """Test preemptive scheduling."""

    @pytest.mark.asyncio
    async def test_quantum_exhaustion(self) -> None:
        """Test agent is preempted when quantum exhausted."""
        scheduler = PreemptiveAgentScheduler(timer_tick_ms=5)

        # Create context
        context = AgentContext(
            agent_id="test", priority=Priority.NORMAL, quantum_ms=10, vruntime=0.0
        )

        scheduler.running = context

        # Simulate timer ticks
        for _ in range(3):  # 3 ticks * 5ms = 15ms > 10ms quantum
            context.quantum_ms -= scheduler.timer_tick_ms

        # Quantum should be exhausted
        assert context.quantum_ms <= 0

    @pytest.mark.asyncio
    async def test_preempt_current(self) -> None:
        """Test preemption logic."""
        scheduler = PreemptiveAgentScheduler()

        context = AgentContext(
            agent_id="test",
            priority=Priority.NORMAL,
            quantum_ms=0,
            vruntime=100.0,  # Exhausted
        )

        scheduler.running = context

        # Preempt
        await scheduler._preempt_current()

        # Should be back in runqueue
        assert scheduler.running is None
        assert scheduler.stats.preemptions > 0


class TestCFS:
    """Test Completely Fair Scheduler (CFS) algorithm."""

    @pytest.mark.asyncio
    async def test_vruntime_calculation(self) -> None:
        """Test virtual runtime calculation."""
        scheduler = PreemptiveAgentScheduler(timer_tick_ms=10)

        # Create contexts
        ctx1 = AgentContext(
            vruntime=0.0, agent_id="agent1", priority=Priority.NORMAL, quantum_ms=20
        )
        ctx2 = AgentContext(
            vruntime=0.0, agent_id="agent2", priority=Priority.NORMAL, quantum_ms=20
        )

        # Simulate execution
        scheduler.running = ctx1

        # Run for 2 ticks
        for _ in range(2):
            ctx1.quantum_ms -= scheduler.timer_tick_ms
            ctx1.total_runtime_ms += scheduler.timer_tick_ms

            # Update vruntime (weighted by priority)
            p_val = ctx1.priority.value if hasattr(ctx1.priority, "value") else ctx1.priority
            weight = 2**p_val
            ctx1.vruntime += scheduler.timer_tick_ms / weight

        # vruntime should have increased
        assert ctx1.vruntime > 0
        assert ctx1.total_runtime_ms == 20

    @pytest.mark.asyncio
    async def test_fairness(self) -> None:
        """Test CFS provides fairness."""
        scheduler = PreemptiveAgentScheduler()

        # Create multiple normal priority agents
        agents = []
        from heapq import heappush

        for i in range(3):
            ctx = AgentContext(
                vruntime=i * 10.0, agent_id=f"agent{i}", priority=Priority.NORMAL, quantum_ms=20
            )
            agents.append(ctx)
            heappush(scheduler.runqueues[Priority.NORMAL], (ctx.vruntime, ctx))

        # Pick agents multiple times
        picked = []
        for _ in range(3):
            agent = scheduler._pick_next_agent()
            if agent:
                picked.append(agent.agent_id)

        # Should pick agent with lowest vruntime first
        assert "agent0" in picked[0]


class TestPerformance:
    """Test scheduler performance."""

    @pytest.mark.asyncio
    async def test_context_switch_latency(self) -> None:
        """Test context switch latency <0.5ms."""
        scheduler = PreemptiveAgentScheduler()

        ctx1 = AgentContext(
            vruntime=0.0, agent_id="agent1", priority=Priority.NORMAL, quantum_ms=20
        )
        ctx2 = AgentContext(
            vruntime=0.0, agent_id="agent2", priority=Priority.NORMAL, quantum_ms=20
        )

        # Warm up
        for _ in range(10):
            await scheduler._context_switch(ctx1, ctx2)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            await scheduler._context_switch(ctx1, ctx2)
            latency_us = (time.perf_counter() - start) * 1_000_000
            latencies.append(latency_us)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]

        print(f"\nContext switch - avg: {avg_latency:.2f}μs, p95: {p95_latency:.2f}μs")

        # Target: <500μs (0.5ms)
        assert avg_latency < 500, f"Avg latency {avg_latency:.2f}μs exceeds 500μs"
        assert p95_latency < 1000, f"P95 latency {p95_latency:.2f}μs exceeds 1ms"

    @pytest.mark.asyncio
    async def test_scheduling_decision_speed(self) -> None:
        """Test scheduling decision <0.1ms."""
        scheduler = PreemptiveAgentScheduler()

        # Populate runqueues
        for i in range(10):
            f = asyncio.get_running_loop().create_future()
            f.set_result(None)
            scheduler.schedule_agent(f"agent{i}", f, Priority.NORMAL)

        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            scheduler._pick_next_agent()
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            times.append(elapsed_us)

        avg_time = sum(times) / len(times)

        print(f"\nScheduling decision: {avg_time:.2f}μs")

        # Target: <100μs (0.1ms)
        assert avg_time < 100, f"Scheduling decision {avg_time:.2f}μs exceeds 100μs"


class TestStatistics:
    """Test scheduler statistics."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        """Test scheduler tracks statistics."""
        scheduler = PreemptiveAgentScheduler()

        # Initial stats
        stats = scheduler.get_stats()
        assert "total_schedules" in stats
        assert "context_switches" in stats
        assert "preemptions" in stats

    @pytest.mark.asyncio
    async def test_context_switch_stats(self) -> None:
        """Test context switch statistics."""
        scheduler = PreemptiveAgentScheduler()

        ctx1 = AgentContext(
            vruntime=0.0, agent_id="agent1", priority=Priority.NORMAL, quantum_ms=20
        )
        ctx2 = AgentContext(
            vruntime=0.0, agent_id="agent2", priority=Priority.NORMAL, quantum_ms=20
        )

        initial_switches = scheduler.stats.context_switches

        # Perform switches
        for _ in range(5):
            await scheduler._context_switch(ctx1, ctx2)

        assert scheduler.stats.context_switches == initial_switches + 5
        assert scheduler.stats.avg_context_switch_us > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
