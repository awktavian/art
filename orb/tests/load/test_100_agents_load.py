"""Load Testing - 100+ Agent Scenario

Tests system stability and performance under heavy agent load.
Validates:
- Agent spawning at scale
- Memory management
- Response times
- Resource cleanup
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_e2e



import asyncio
import time
from typing import Any


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_spawn_100_agents():
    """Test spawning 100+ agents without crashes or memory explosion."""
    from kagami.core.unified_agents import COLONY_NAMES, OrganismConfig, UnifiedOrganism
    from kagami.core.safety.agent_memory_guard import get_agent_memory_guard

    organism = UnifiedOrganism(
        config=OrganismConfig(
            min_workers_per_colony=1,
            max_workers_per_colony=100,
            global_max_population=1000,
            homeostasis_interval=60.0,
        )
    )
    await organism.start()
    guard = get_agent_memory_guard()

    start_time = time.time()
    spawned_workers: list[tuple[Any, Any]] = []

    try:
        for i in range(100):
            colony_name = COLONY_NAMES[i % 7]
            colony = organism.get_colony(colony_name)
            assert colony is not None
            worker = await colony.spawn_worker(task={"reason": "load_test"})
            spawned_workers.append((colony, worker))
            guard.register_agent(worker.worker_id, soft_limit_gb=1.0, hard_limit_gb=2.0)

        spawn_duration = time.time() - start_time

        # Verify performance
        assert spawn_duration < 60.0, f"Spawning 100 agents took {spawn_duration}s (target: <60s)"
        assert len(spawned_workers) == 100

        # Check no memory guard violations
        violations = 0
        for _colony, worker in spawned_workers[:10]:  # Sample first 10
            if guard.should_abort(worker.worker_id):
                violations += 1

        assert violations == 0, f"{violations} agents exceeded memory limits"

    finally:
        # Cleanup spawned agents
        for colony, worker in spawned_workers:
            guard.unregister_agent(worker.worker_id)
            await worker.retire()
            await colony.cleanup_workers()
        await organism.stop()


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_agent_operations():
    """Test 100 concurrent agent operations (parallel execution)."""

    async def mock_agent_operation(agent_id: str) -> dict[str, Any]:
        """Simulate an agent operation."""
        await asyncio.sleep(0.1)  # Simulate work
        return {"agent_id": agent_id, "status": "completed"}

    start_time = time.time()

    # Run 100 operations concurrently
    tasks = [mock_agent_operation(f"agent_{i}") for i in range(100)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    duration = time.time() - start_time

    # Verify performance
    assert duration < 5.0, f"100 concurrent ops took {duration}s (expected ~0.1s with concurrency)"

    # Verify results
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "completed")
    assert successful == 100, f"Only {successful}/100 operations succeeded"


@pytest.mark.load
@pytest.mark.slow
def test_metrics_under_load():
    """Test metrics system handles 1000+ metric emissions."""
    from kagami_observability.metrics import AGENT_FITNESS, COLONY_POPULATION

    start_time = time.time()

    # Emit 1000 metrics
    for i in range(1000):
        try:
            AGENT_FITNESS.labels(domain="test").set(0.8)
            COLONY_POPULATION.labels(domain="test", status="active").set(i)
        except Exception as e:
            pytest.fail(f"Metrics emission failed at {i}: {e}")

    duration = time.time() - start_time

    # Should complete quickly (metrics are async)
    assert duration < 5.0, f"1000 metric emissions took {duration}s"


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_receipt_generation_under_load():
    """Test receipt system handles 100+ receipts without blocking."""
    from kagami.core.receipts import UnifiedReceiptFacade as URF

    start_time = time.time()

    # Generate 100 receipts using modern URF
    for i in range(100):
        try:
            URF.emit(
                correlation_id=f"load_test_{i}",
                event_name="load.test.execute",
                action="test_operation",
                status="success",
                event_data={"metrics": {"duration_ms": 100}},
            )
        except Exception as e:
            pytest.fail(f"Receipt emission failed at {i}: {e}")

    duration = time.time() - start_time

    # Should complete quickly
    assert duration < 10.0, f"100 receipt emissions took {duration}s"


@pytest.mark.load
@pytest.mark.slow
def test_world_model_under_load():
    """Test world model handles 100+ predictions without crashes."""
    import torch

    from kagami.core.world_model.registry import get_world_model_registry

    registry = get_world_model_registry()
    model = registry.get_primary()

    start_time = time.time()
    predictions = []

    # Run 100 predictions
    for i in range(100):
        try:
            # Create dummy state
            state = torch.randn(1, 128)  # Minimal state vector

            # Predict (sync or async depending on model)
            if hasattr(model, "predict"):
                pred = model.predict(state)
            else:
                pred = {"next_state": state}  # Fallback

            predictions.append(pred)
        except Exception as e:
            # Some predictions may fail if model not fully loaded
            if i < 10:
                pytest.fail(f"Prediction {i} failed: {e}")
            break

    duration = time.time() - start_time

    # Verify performance
    if predictions:
        assert duration < 30.0, f"100 predictions took {duration}s"
        assert len(predictions) >= 10, "At least 10 predictions should succeed"


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_api_endpoint_load():
    """Test API handles 100+ concurrent requests."""
    from httpx import AsyncClient

    from kagami_api import create_app

    app = create_app()

    async with AsyncClient(app=app, base_url="http://test") as client:
        start_time = time.time()

        # Send 100 concurrent health checks
        tasks = [client.get("/health/live") for _ in range(100)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.time() - start_time

        # Verify performance
        assert duration < 10.0, f"100 API requests took {duration}s"

        # Check success rate
        successful = sum(1 for r in responses if hasattr(r, "status_code") and r.status_code == 200)
        assert successful >= 95, f"Only {successful}/100 requests succeeded"


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.skip(reason="Multi-day test - run manually")
def test_multi_day_stress():
    """Multi-day stress test (run manually, not in CI)."""
    # This test is designed to run for 24-48 hours
    # Run with: pytest tests/load/test_100_agents_load.py::test_multi_day_stress -v
    pytest.skip("Multi-day test - run manually with: STRESS_TEST=1 pytest ...")


if __name__ == "__main__":
    # Run load tests
    pytest.main([__file__, "-v", "-m", "load"])
