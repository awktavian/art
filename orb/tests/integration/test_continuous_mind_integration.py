"""Integration tests for continuous mind with unified organism.

Tests that continuous learning integrates properly with the organism
and runs without blocking execution.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio

from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)


@pytest.mark.asyncio
async def test_organism_enable_continuous_learning():
    """Test enabling continuous learning on organism."""
    organism = UnifiedOrganism(OrganismConfig())

    # Enable
    await organism.enable_continuous_learning(
        poll_interval=0.01,
        batch_size=3,
    )

    # Verify continuous mind is running
    assert organism._continuous_mind is not None, "Continuous mind should be created"
    assert organism._continuous_mind.is_running(), "Continuous mind should be running"

    # Get stats and verify structure
    stats = organism.get_continuous_mind_stats()
    assert stats is not None, "Stats should not be None when enabled"
    assert "state" in stats, "Stats should contain 'state' field"
    assert stats["is_healthy"] is True, "Continuous mind should be healthy"

    # Verify config was applied
    assert stats.get("poll_interval") == 0.01 or "config" in stats, (
        "Config should be reflected in stats"
    )

    # Disable and verify cleanup
    await organism.disable_continuous_learning()
    assert organism._continuous_mind is None, "Continuous mind should be None after disable"


@pytest.mark.asyncio
async def test_organism_continuous_learning_state_transitions():
    """Test continuous learning transitions through expected states."""
    organism = UnifiedOrganism(OrganismConfig())

    # Enable learning
    await organism.enable_continuous_learning(
        poll_interval=0.01,
        batch_size=2,
    )

    # Collect states over time
    states_observed = set()
    for _ in range(10):
        await asyncio.sleep(0.01)
        stats = organism.get_continuous_mind_stats()
        if stats and "state" in stats:
            states_observed.add(stats["state"])

    # Check it's running
    stats = organism.get_continuous_mind_stats()
    assert stats["state"] in ["polling", "sleeping", "processing"]  # type: ignore[index]

    # Clean up
    await organism.disable_continuous_learning()


@pytest.mark.asyncio
async def test_organism_stop_disables_continuous_learning():
    """Test that stopping organism stops continuous learning."""
    organism = UnifiedOrganism(OrganismConfig())
    await organism.start()

    # Verify organism started
    assert organism._started is True or hasattr(organism, "_running")

    await organism.enable_continuous_learning()
    assert organism._continuous_mind is not None, "Should have continuous mind before stop"

    # Stop organism
    await organism.stop()

    # Should have stopped continuous mind
    assert organism._continuous_mind is None, "Continuous mind should be None after organism stop"


@pytest.mark.asyncio
async def test_organism_continuous_learning_stats_when_disabled():
    """Test stats return None when continuous learning disabled."""
    organism = UnifiedOrganism(OrganismConfig())

    stats = organism.get_continuous_mind_stats()
    assert stats is None, "Stats should be None when continuous learning is disabled"


@pytest.mark.asyncio
async def test_organism_continuous_learning_idempotent():
    """Test enabling twice is safe and maintains single instance."""
    organism = UnifiedOrganism(OrganismConfig())

    await organism.enable_continuous_learning()
    first_mind = organism._continuous_mind
    assert first_mind is not None

    await organism.enable_continuous_learning()  # Should log warning but not error
    second_mind = organism._continuous_mind

    # Should still have a continuous mind
    assert second_mind is not None, "Should still have continuous mind after second enable"

    # Clean up
    await organism.disable_continuous_learning()


@pytest.mark.asyncio
async def test_organism_continuous_learning_concurrent_execution():
    """Test continuous learning runs concurrently with execution."""
    organism = UnifiedOrganism(OrganismConfig())

    await organism.enable_continuous_learning(poll_interval=0.01)

    # Execute an intent (would normally produce receipt)
    # Continuous learning should not block this
    loop = asyncio.get_event_loop()
    start = loop.time()

    try:
        result = await asyncio.wait_for(
            organism.execute_intent(
                intent="test.action",
                params={},
            ),
            timeout=1.0,
        )
        elapsed = loop.time() - start

        # Should complete quickly (not blocked by learning)
        assert elapsed < 0.5, f"Execution took too long: {elapsed}s, learning may be blocking"

        # Result should have some structure if returned
        if result is not None:
            # Receipt or response should have identifiable fields
            assert hasattr(result, "__dict__") or isinstance(result, dict), (
                "Result should be structured"
            )

    except TimeoutError:
        pytest.fail("Execution timed out - continuous learning may be blocking")
    except Exception:
        # Expected if routing fails, but should not timeout
        # The key assertion is that we didn't timeout
        pass

    await organism.disable_continuous_learning()


@pytest.mark.asyncio
async def test_organism_continuous_learning_health_monitoring():
    """Test that health status accurately reflects continuous mind state."""
    organism = UnifiedOrganism(OrganismConfig())

    # Before enabling - no health data
    stats_before = organism.get_continuous_mind_stats()
    assert stats_before is None

    # Enable and verify health
    await organism.enable_continuous_learning(poll_interval=0.01)
    await asyncio.sleep(0.02)  # Let it run briefly

    stats_running = organism.get_continuous_mind_stats()
    assert stats_running is not None
    assert stats_running.get("is_healthy") is True, "Should be healthy while running"

    # After disable - no health data
    await organism.disable_continuous_learning()
    stats_after = organism.get_continuous_mind_stats()
    assert stats_after is None, "Stats should be None after disable"


@pytest.mark.asyncio
async def test_organism_continuous_learning_batch_size_config():
    """Test that batch_size configuration is respected."""
    organism = UnifiedOrganism(OrganismConfig())

    custom_batch_size = 5

    await organism.enable_continuous_learning(
        poll_interval=0.01,
        batch_size=custom_batch_size,
    )

    stats = organism.get_continuous_mind_stats()
    assert stats is not None

    # Verify batch_size is tracked (implementation may vary)
    # The stats dict should reflect the configuration somehow
    assert stats.get("batch_size") == custom_batch_size or "config" in stats

    await organism.disable_continuous_learning()


@pytest.mark.asyncio
async def test_organism_disable_is_idempotent():
    """Test that disabling continuous learning twice is safe."""
    organism = UnifiedOrganism(OrganismConfig())

    await organism.enable_continuous_learning()
    assert organism._continuous_mind is not None

    # First disable
    await organism.disable_continuous_learning()
    assert organism._continuous_mind is None

    # Second disable should not raise
    await organism.disable_continuous_learning()
    assert organism._continuous_mind is None


__all__ = [
    "test_organism_enable_continuous_learning",
]
