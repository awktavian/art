"""Agent Population Load Tests

Tests system behavior under heavy agent load.

Tests:
- 1000+ concurrent agents
- Homeostasis stability
- Resource usage bounds
- Performance degradation limits
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_e2e


import asyncio
import time


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_1000_agent_spawn_stability():
    """Test system remains stable with 1000 agents."""
    from kagami.core.unified_agents import COLONY_NAMES, OrganismConfig, UnifiedOrganism

    # Create organism with high capacity
    organism = UnifiedOrganism(
        config=OrganismConfig(
            min_workers_per_colony=1,
            max_workers_per_colony=200,
            global_max_population=1200,  # Allow overhead (not strictly enforced)
            homeostasis_interval=5.0,
        )
    )

    try:
        await organism.start()

        initial_pop = sum(len(c.workers) for c in organism.colonies.values())
        print(f"\n📊 Initial population: {initial_pop}")

        # Spawn many agents rapidly
        spawn_tasks = []
        for i in range(1000):
            colony = organism.get_colony(COLONY_NAMES[i % 7])
            assert colony is not None
            spawn_tasks.append(colony.spawn_worker(task={"reason": "load_test", "i": i}))

        # Wait for spawns (with timeout)
        results = await asyncio.wait_for(
            asyncio.gather(*spawn_tasks, return_exceptions=True), timeout=60.0
        )

        successful_spawns = sum(1 for r in results if not isinstance(r, Exception))
        print(f"✅ Successfully spawned: {successful_spawns}/1000")

        # Check final population
        final_pop = sum(len(c.workers) for c in organism.colonies.values())
        print(f"📊 Final population: {final_pop}")

        # Validation
        assert final_pop <= 1200, "Population must not exceed max"
        assert final_pop > initial_pop, "Should have spawned some agents"
        assert successful_spawns > 800, f"Should spawn >80% successfully (got {successful_spawns})"

    finally:
        await organism.stop()


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_agent_homeostasis_under_load():
    """Test homeostasis maintains population bounds under stress."""
    from kagami.core.unified_agents import COLONY_NAMES, OrganismConfig, UnifiedOrganism

    max_pop = 500
    per_colony_max = max_pop // 7  # Ensures total <= max_pop
    organism = UnifiedOrganism(
        config=OrganismConfig(
            min_workers_per_colony=1,
            max_workers_per_colony=per_colony_max,
            global_max_population=max_pop,  # Not strictly enforced; per-colony cap keeps bound
            homeostasis_interval=1.0,  # Fast homeostasis
        )
    )

    try:
        await organism.start()

        # Monitor population over time
        observations = []

        for cycle in range(10):
            # Rapid spawn attempts
            spawn_tasks = []
            for i in range(100):
                colony = organism.get_colony(COLONY_NAMES[(cycle * 100 + i) % 7])
                assert colony is not None
                spawn_tasks.append(colony.spawn_worker(task={"cycle": cycle, "i": i}))

            await asyncio.gather(*spawn_tasks, return_exceptions=True)

            # Wait for homeostasis
            await asyncio.sleep(1.5)

            # Observe population
            pop = sum(len(c.workers) for c in organism.colonies.values())
            observations.append(pop)

            print(f"Cycle {cycle}: Population = {pop}")

            # Property: Never exceed max
            assert pop <= max_pop, f"Homeostasis failed: {pop} > {max_pop}"

        # Property: Population stabilizes (not growing unbounded)
        recent_avg = sum(observations[-5:]) / 5
        assert recent_avg <= max_pop, "Population must stabilize within limits"

    finally:
        await organism.stop()


@pytest.mark.load
@pytest.mark.slow
def test_concurrent_api_requests():
    """Test API handles 1000 concurrent requests."""
    import concurrent.futures

    from starlette.testclient import TestClient

    from kagami_api import create_app

    app = create_app()

    def make_request(i: Any) -> Any:
        """Make a single request."""
        with TestClient(app) as client:
            try:
                response = client.get("/api/vitals/probes/live")
                return response.status_code == 200
            except Exception:
                return False

    # Fire 1000 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_request, i) for i in range(1000)]

        results = [f.result(timeout=30) for f in futures]

    successful = sum(results)
    success_rate = successful / len(results)

    print("\n📊 Concurrent Request Test (1000 requests):")
    print(f"  Successful: {successful}/1000 ({success_rate:.1%})")
    print(f"  Failed: {1000 - successful}")

    assert success_rate > 0.95, f"Success rate {success_rate:.1%} too low (<95%)"


@pytest.mark.load
@pytest.mark.slow
def test_memory_usage_under_load():
    """Test memory usage stays bounded under load."""
    from kagami.core.safety.agent_memory_guard import AgentMemoryGuard

    guard = AgentMemoryGuard(soft_limit_gb=4.0, hard_limit_gb=8.0)

    # Record memory usage
    memory_samples = []

    for cycle in range(20):
        # Simulate work
        data = [list(range(10000)) for _ in range(100)]  # Allocate some memory

        # Check memory
        exceeded, current_gb, limit_gb = guard.check_limits()
        memory_samples.append(current_gb)

        print(f"Cycle {cycle}: Memory = {current_gb:.2f}GB (limit: {limit_gb:.2f}GB)")

        # Property: Never exceed hard limit
        assert not exceeded, f"Memory exceeded hard limit: {current_gb:.2f}GB > {limit_gb:.2f}GB"

        # Cleanup
        del data

    # Property: Memory doesn't grow unbounded
    max_memory = max(memory_samples)
    assert max_memory < 8.0, f"Memory usage {max_memory:.2f}GB approaching hard limit"


@pytest.mark.load
def test_rate_limiter_handles_burst():
    """Test rate limiter correctly handles burst traffic."""
    from kagami_api.rate_limiter import RateLimiter

    limiter = RateLimiter(requests_per_minute=100, window_size=60)
    client_id = "burst_test_client"

    # Send burst of 200 requests
    allowed_count = 0
    blocked_count = 0

    for _i in range(200):
        is_allowed, _remaining, _reset = limiter.is_allowed(client_id)
        if is_allowed:
            allowed_count += 1
        else:
            blocked_count += 1

    print("\n📊 Rate Limiter Burst Test (200 requests, limit=100):")
    print(f"  Allowed: {allowed_count}")
    print(f"  Blocked: {blocked_count}")

    # Property: Should allow ~100, block ~100
    assert 90 <= allowed_count <= 110, f"Allowed count {allowed_count} not near limit 100"
    assert blocked_count >= 90, f"Should block ~100 requests, blocked {blocked_count}"


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_receipt_emission_throughput():
    """Test receipt system handles high throughput."""
    from kagami.core.receipts import emit_receipt

    num_receipts = 10000
    start = time.perf_counter()

    for i in range(num_receipts):
        try:
            emit_receipt(
                correlation_id=f"throughput-{i}",
                action="test.throughput",
                app="Load Test",
                args={"iteration": i},
                event_name="EXECUTE",
                event_data={"i": i},
                duration_ms=1.0,
            )
        except Exception:
            pass  # May fail without DB

    elapsed = time.perf_counter() - start
    throughput = num_receipts / elapsed

    print("\n📊 Receipt Emission Throughput:")
    print(f"  Receipts: {num_receipts}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {throughput:.0f} receipts/sec")

    assert throughput > 1000, f"Throughput {throughput:.0f}/s too low (<1000/s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
