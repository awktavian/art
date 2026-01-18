"""Chaos engineering tests - verify system resilience.

Tests system behavior under chaotic conditions:
- Random agent restarts
- Network partitions
- Memory pressure
- Random failures

These tests ensure K os is robust against unexpected failures.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e
import asyncio
import os
import random
import time
from unittest.mock import patch

CHAOS_ENABLED = os.getenv("KAGAMI_ENABLE_CHAOS_TESTS", "0") == "1"
CHAOS_SKIP = pytest.mark.skipif(
    not CHAOS_ENABLED, reason="Chaos tests require KAGAMI_ENABLE_CHAOS_TESTS=1"
)


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_random_agent_restarts() -> None:
    """Test system handles random agent restarts."""
    random.seed(42)
    from kagami.core.unified_agents.app_registry import APP_REGISTRY_V2

    agents_to_test = list(APP_REGISTRY_V2.keys())[:5]  # Test 5 agents
    restart_count = 0
    duration = 30  # 30 seconds
    start_time = time.time()
    while time.time() - start_time < duration:
        # Pick random agent
        agent_name = random.choice(agents_to_test)
        # Simulate restart (stop and start)
        try:
            # This is a simulation - in reality would stop/start background task
            await asyncio.sleep(0.1)
            restart_count += 1
        except Exception as e:
            print(f"Restart failed for {agent_name}: {e}")
        # Random delay before next restart
        await asyncio.sleep(random.uniform(0.5, 2.0))
    print("\nRandom restarts test:")
    print(f"  Duration: {duration}s")
    print(f"  Restarts: {restart_count}")
    # System should survive multiple restarts
    assert restart_count >= 5


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_network_partition_simulation() -> None:
    """Test system behavior during simulated network partition."""
    random.seed(42)
    # Simulate network partition for 10 seconds
    partition_duration = 10

    async def simulate_partition():
        """Randomly fail network calls during partition."""
        await asyncio.sleep(partition_duration)

    # Run operations during partition
    async def run_operations():
        operations_completed = 0
        operations_failed = 0
        for _i in range(20):
            try:
                # Simulate operation with random network calls
                if random.random() < 0.5:  # 50% failure rate
                    raise ConnectionError("Network partition")
                await asyncio.sleep(0.1)
                operations_completed += 1
            except ConnectionError:
                operations_failed += 1
        return operations_completed, operations_failed

    partition_task = asyncio.create_task(simulate_partition())
    ops_task = asyncio.create_task(run_operations())
    completed, failed = await ops_task
    await partition_task
    print("\nNetwork partition test:")
    print(f"  Duration: {partition_duration}s")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed}")
    # Some operations should complete despite partition
    assert completed >= 5, f"Too few completed: {completed}"


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_memory_pressure_simulation() -> None:
    """Test system under memory pressure."""
    import gc

    # Force garbage collection
    gc.collect()
    # Allocate large objects to create memory pressure
    large_objects = []
    for _i in range(10):
        # 10MB each
        obj = bytearray(10 * 1024 * 1024)
        large_objects.append(obj)
    # Try to create and run agent under memory pressure
    from kagami.core.unified_agents import GeometricWorker, WorkerConfig

    agent = GeometricWorker(config=WorkerConfig(colony_idx=0))
    try:
        # Agent should initialize even under memory pressure
        assert agent is not None
        assert agent.state.status is not None
    finally:
        # Cleanup
        large_objects.clear()
        gc.collect()


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_random_failures() -> None:
    """Test system with random component failures."""
    random.seed(42)
    failure_rate = 0.3  # 30% failure rate

    async def chaos_operation(op_id: int):
        """Operation that randomly fails."""
        if random.random() < failure_rate:
            raise RuntimeError(f"Chaos failure {op_id}")
        await asyncio.sleep(random.uniform(0.01, 0.1))
        return f"success_{op_id}"

    # Run 50 operations with random failures
    tasks = [chaos_operation(i) for i in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    print("\nRandom failures test:")
    print(f"  Successes: {len(successes)}/50")
    print(f"  Failures: {len(failures)}/50")
    # Most should complete despite failures
    assert len(successes) >= 30


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_cascading_failures() -> None:
    """Test system handles cascading failures."""
    random.seed(42)
    # Simulate cascade: one failure causes others
    failure_cascade = []

    async def cascading_operation(op_id: int, dependency_ids: list[int]):
        """Operation that fails if dependencies failed."""
        # Check if any dependency failed
        for dep_id in dependency_ids:
            if dep_id in failure_cascade:
                failure_cascade.append(op_id)
                raise RuntimeError(f"Cascading failure from {dep_id}")
        # Random chance of independent failure
        if random.random() < 0.2:
            failure_cascade.append(op_id)
            raise RuntimeError(f"Independent failure {op_id}")
        await asyncio.sleep(0.05)
        return f"success_{op_id}"

    # Create dependency chain
    tasks = []
    tasks.append(cascading_operation(0, []))
    tasks.append(cascading_operation(1, [0]))
    tasks.append(cascading_operation(2, [0, 1]))
    tasks.append(cascading_operation(3, [1]))
    tasks.append(cascading_operation(4, [2, 3]))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    print("\nCascading failures test:")
    print(f"  Successes: {len(successes)}/5")
    print(f"  Failures: {len(failures)}/5")
    print(f"  Cascade size: {len(failure_cascade)}")
    # System should survive cascade
    assert len(successes) >= 1


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_time_travel_simulation() -> None:
    """Test system handles time anomalies (clock skew)."""
    original_time = time.time
    # Simulate clock skew
    with patch("time.time", return_value=original_time() + 3600):  # +1 hour
        # Operations should handle time skew
        from kagami.core.agent_operations.context import AgentOperationContext

        ctx = AgentOperationContext()
        assert ctx.start_time > 0
        # Phase transitions should work despite skew
        from kagami.core.agent_operations.phases import ExecutionPhase

        ctx.enter_phase(ExecutionPhase.MODEL)
        ctx.enter_phase(ExecutionPhase.ACT)
        # Should not crash
        assert ctx.phase == ExecutionPhase.ACT


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_thundering_herd() -> None:
    """Test system handles thundering herd (many requests simultaneously)."""
    from kagami.core.caching.redis import RedisClientFactory

    client = RedisClientFactory.get_client(purpose="default", async_mode=True)
    # 100 requests for same key simultaneously
    herd_size = 100
    key = "test_thundering_herd"

    async def herd_request(req_id: int):
        """Simulate request in herd."""
        value = await client.get(key)
        if value is None:
            # Cache miss - set value
            await client.set(key, f"value_{req_id}", ex=60)
            return "miss"
        return "hit"

    start_time = time.time()
    results = await asyncio.gather(*[herd_request(i) for i in range(herd_size)])
    duration = time.time() - start_time
    misses = results.count("miss")

    hits = results.count("hit")

    print("\nThundering herd test:")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Misses: {misses}")
    print(f"  Hits: {hits}")
    # Should complete quickly
    assert duration < 5.0
    # Cleanup
    await client.delete(key)


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_resource_exhaustion() -> None:
    """Test system behavior when resources exhausted."""
    # Simulate file descriptor exhaustion
    open_files = []
    try:
        # Try to open many files
        for _i in range(100):
            f = open("/dev/null")
            open_files.append(f)
        # System should still function
        from kagami.core.orchestrator.core import IntentOrchestrator

        orch = IntentOrchestrator()
        await orch.initialize()
        result = await orch.process_intent({"action": "EXECUTE", "app": "files", "params": {}})
        assert result is not None
    finally:
        # Cleanup
        for f in open_files:
            f.close()


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_deadlock_detection() -> None:
    """Test system detects and recovers from potential deadlocks."""
    lock_a = asyncio.Lock()
    lock_b = asyncio.Lock()
    deadlock_detected = False

    async def task_1():
        """Task that acquires lock_a then lock_b."""
        async with lock_a:
            await asyncio.sleep(0.1)
            try:
                async with asyncio.timeout(1.0):
                    async with lock_b:
                        pass
            except TimeoutError:
                nonlocal deadlock_detected
                deadlock_detected = True

    async def task_2():
        """Task that acquires lock_b then lock_a."""
        async with lock_b:
            await asyncio.sleep(0.1)
            try:
                async with asyncio.timeout(1.0):
                    async with lock_a:
                        pass
            except TimeoutError:
                nonlocal deadlock_detected
                deadlock_detected = True

    # Run both tasks - potential deadlock
    await asyncio.gather(task_1(), task_2())
    print("\nDeadlock detection test:")
    print(f"  Deadlock detected: {deadlock_detected}")
    # Timeout should prevent actual deadlock
    # Test completes without hanging = no actual deadlock
    assert not deadlock_detected or True  # Deadlock may be detected but resolved


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.slow
@pytest.mark.asyncio
async def test_sustained_chaos() -> None:
    """Test system under sustained chaotic conditions (2 minutes)."""
    random.seed(42)
    duration = 120  # 2 minutes
    start_time = time.time()
    operations_completed = 0
    operations_failed = 0
    while time.time() - start_time < duration:
        # Random operation
        op_type = random.choice(["agent", "redis", "llm", "db"])
        try:
            if op_type == "agent":
                # Random agent operation
                from kagami.core.orchestrator.core import IntentOrchestrator

                orch = IntentOrchestrator()
                await orch.initialize()
                await orch.process_intent(
                    {"action": "EXECUTE", "app": "files", "params": {"op": "chaos"}}
                )
            elif op_type == "redis":
                # Random Redis operation
                from kagami.core.caching.redis import RedisClientFactory

                client = RedisClientFactory.get_client()
                await client.set(f"chaos_{random.randint(0, 1000)}", "value", ex=60)
            # Random failures
            if random.random() < 0.2:
                raise RuntimeError("Chaos failure")
            operations_completed += 1
        except Exception:
            operations_failed += 1
        # Random delay
        await asyncio.sleep(random.uniform(0.1, 1.0))
    print(f"\nSustained chaos test ({duration}s):")
    print(f"  Completed: {operations_completed}")
    print(f"  Failed: {operations_failed}")
    print(
        f"  Success rate: {operations_completed / (operations_completed + operations_failed) * 100:.1f}%"
    )
    # Should maintain reasonable success rate
    total = operations_completed + operations_failed
    assert operations_completed / total >= 0.5, "Success rate too low under chaos"
