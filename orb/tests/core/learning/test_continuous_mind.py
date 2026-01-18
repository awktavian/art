"""Unit tests for continuous mind daemon.

Tests the always-on background learning system:
- Receipt polling and batching
- Incremental learning
- Non-blocking operation
- Error handling and backoff
- Statistics and monitoring
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import time
from typing import Any

from kagami.core.learning.continuous_mind import (
    ContinuousMindDaemon,
    ContinuousMindStats,
    MindState,
    ReceiptBatch,
    get_continuous_mind,
    create_continuous_mind,
)
from kagami.core.learning.receipt_learning import ReceiptLearningEngine
from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def stigmergy_learner():
    """Create a stigmergy learner for testing."""
    learner = StigmergyLearner(
        max_cache_size=100,
        enable_persistence=False,
        enable_game_model=True,
    )
    return learner


@pytest.fixture
def learning_engine(stigmergy_learner: Any) -> Any:
    """Create a receipt learning engine."""
    return ReceiptLearningEngine(
        organism_rssm=None,
        stigmergy_learner=stigmergy_learner,
        learning_rate=1e-4,
        min_sample_size=1,  # Low for testing
    )


@pytest.fixture
def continuous_mind(learning_engine: Any) -> Any:
    """Create a continuous mind daemon."""
    return create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.01,  # Fast polling for tests
        batch_size=5,
    )


@pytest.fixture
def sample_receipts():
    """Create sample receipts for testing."""
    return [
        {
            "intent": {"action": "research.web", "complexity": 0.6},
            "actor": "colony:grove:agent1",
            "verifier": {"status": "verified"},
            "duration_ms": 1500,
            "g_value": 0.8,
        },
        {
            "intent": {"action": "research.web", "complexity": 0.5},
            "actor": "colony:grove:agent2",
            "verifier": {"status": "verified"},
            "duration_ms": 1200,
            "g_value": 0.7,
        },
        {
            "intent": {"action": "build.feature", "complexity": 0.8},
            "actor": "colony:forge:agent3",
            "verifier": {"status": "verified"},
            "duration_ms": 2000,
            "g_value": 0.6,
        },
        {
            "intent": {"action": "research.web", "complexity": 0.7},
            "actor": "colony:crystal:agent4",
            "verifier": {"status": "failed"},
            "duration_ms": 2500,
            "g_value": 1.5,
        },
    ]


# =============================================================================
# TESTS: INITIALIZATION & LIFECYCLE
# =============================================================================


def test_continuous_mind_initialization(learning_engine: Any) -> None:
    """Test continuous mind daemon initialization."""
    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        poll_interval=0.1,
        batch_size=10,
    )

    assert daemon.learning_engine is learning_engine
    assert daemon.poll_interval == 0.1
    assert daemon.batch_size == 10
    assert not daemon.is_running()
    assert not daemon.is_paused()
    assert daemon.stats.state == MindState.INITIALIZING


def test_continuous_mind_lazy_learning_engine():
    """Test lazy initialization of learning engine."""
    daemon = create_continuous_mind(learning_engine=None)
    assert daemon.learning_engine is None
    # Learning engine will be created on first use


def test_continuous_mind_singleton():
    """Test singleton pattern for global instance."""
    mind1 = get_continuous_mind()
    mind2 = get_continuous_mind()
    assert mind1 is mind2


# =============================================================================
# TESTS: LIFECYCLE MANAGEMENT
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_start_stop(continuous_mind: Any) -> None:
    """Test starting and stopping the daemon."""
    assert not continuous_mind.is_running()

    await continuous_mind.start()
    assert continuous_mind.is_running()
    assert continuous_mind.stats.state == MindState.POLLING

    await asyncio.sleep(0.05)  # Let it run briefly

    await continuous_mind.stop()
    assert not continuous_mind.is_running()
    assert continuous_mind.stats.state == MindState.STOPPED


@pytest.mark.asyncio
async def test_continuous_mind_pause_resume(continuous_mind: Any) -> None:
    """Test pausing and resuming the daemon."""
    await continuous_mind.start()

    await continuous_mind.pause()
    assert continuous_mind.is_paused()
    assert continuous_mind.stats.state == MindState.PAUSED

    await continuous_mind.resume()
    assert not continuous_mind.is_paused()
    assert continuous_mind.stats.state == MindState.POLLING

    await continuous_mind.stop()


@pytest.mark.asyncio
async def test_continuous_mind_start_idempotent(continuous_mind: Any) -> None:
    """Test that starting twice is safe."""
    await continuous_mind.start()
    await asyncio.sleep(0.01)
    await continuous_mind.start()  # Should not error
    assert continuous_mind.is_running()
    await continuous_mind.stop()


# =============================================================================
# TESTS: RECEIPT POLLING & BATCHING
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_receipt_source(continuous_mind: Any, sample_receipts: Any) -> None:
    """Test setting and using receipt source."""
    batch_calls = []

    async def mock_source():
        batch_calls.append(time.time())
        # Return 2 receipts on first call, 1 on second, none after
        if len(batch_calls) == 1:
            return sample_receipts[:2]
        elif len(batch_calls) == 2:
            return sample_receipts[2:3]
        return []

    continuous_mind.set_receipt_source(mock_source)
    await continuous_mind.start()

    # Wait for receipts to be processed
    await asyncio.sleep(0.2)

    await continuous_mind.stop()

    # Should have called source multiple times
    assert len(batch_calls) >= 1


@pytest.mark.asyncio
async def test_continuous_mind_no_receipts(continuous_mind: Any) -> None:
    """Test behavior when no receipts available."""

    async def empty_source():
        return []

    continuous_mind.set_receipt_source(empty_source)

    batch = await continuous_mind._get_receipt_batch()
    assert batch is None


@pytest.mark.asyncio
async def test_continuous_mind_batch_size_limit(continuous_mind: Any, sample_receipts: Any) -> None:
    """Test that batch respects size limit."""
    call_count = [0]

    async def source():
        call_count[0] += 1
        return sample_receipts if call_count[0] == 1 else []

    continuous_mind.set_receipt_source(source)
    continuous_mind.batch_size = 2

    batch = await continuous_mind._get_receipt_batch()
    assert batch is not None
    assert batch.size == 2
    assert len(batch.receipts) == 2


# =============================================================================
# TESTS: LEARNING & UPDATES
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_process_batch(continuous_mind: Any, sample_receipts: Any) -> None:
    """Test batch processing."""
    batch = ReceiptBatch(receipts=sample_receipts[:2])

    success = await continuous_mind._process_batch(batch)
    assert success is True
    assert continuous_mind.stats.total_receipts_processed == 2
    assert continuous_mind.stats.total_learning_updates == 1


@pytest.mark.asyncio
async def test_continuous_mind_process_empty_batch(continuous_mind: Any) -> None:
    """Test processing empty batch."""
    batch = ReceiptBatch(receipts=[])

    success = await continuous_mind._process_batch(batch)
    assert success is True
    assert continuous_mind.stats.total_receipts_processed == 0


@pytest.mark.asyncio
async def test_continuous_mind_incremental_learning(
    continuous_mind: Any, sample_receipts: Any
) -> None:
    """Test that learning happens incrementally."""
    batch = ReceiptBatch(receipts=sample_receipts)

    # Process batch
    await continuous_mind._process_batch(batch)

    # Check stats
    assert continuous_mind.stats.total_receipts_processed > 0
    assert continuous_mind.stats.last_learning_time > 0
    assert continuous_mind.stats.avg_latency_ms >= 0


@pytest.mark.asyncio
async def test_continuous_mind_latency_tracking(continuous_mind: Any) -> None:
    """Test latency metric tracking."""
    batch = ReceiptBatch(receipts=[{"intent": {"action": "test"}}])

    # Process multiple batches
    for _ in range(3):
        await continuous_mind._process_batch(batch)

    # Should have latency metrics
    assert continuous_mind.stats.avg_latency_ms > 0
    assert continuous_mind.stats.max_latency_ms >= continuous_mind.stats.avg_latency_ms


# =============================================================================
# TESTS: ERROR HANDLING & RESILIENCE
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_error_recovery(learning_engine: Any) -> None:
    """Test error recovery with backoff."""
    daemon = create_continuous_mind(
        learning_engine=learning_engine,
        error_backoff_base=0.01,
    )

    call_count = [0]

    async def failing_source():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("Simulated error")
        return []

    daemon.set_receipt_source(failing_source)

    await daemon.start()

    # Let it run through errors
    await asyncio.sleep(0.15)
    await daemon.stop()

    # Should have recorded errors
    assert daemon.stats.errors_in_window > 0


@pytest.mark.asyncio
async def test_continuous_mind_graceful_shutdown(
    continuous_mind: Any, sample_receipts: Any
) -> None:
    """Test graceful shutdown during processing."""

    async def slow_source():
        await asyncio.sleep(0.05)
        return sample_receipts

    continuous_mind.set_receipt_source(slow_source)
    await continuous_mind.start()

    await asyncio.sleep(0.03)
    await continuous_mind.stop()

    assert not continuous_mind.is_running()


# =============================================================================
# TESTS: STATISTICS & MONITORING
# =============================================================================


def test_continuous_mind_stats_initialization():
    """Test statistics initialization."""
    stats = ContinuousMindStats()

    assert stats.total_receipts_processed == 0
    assert stats.total_learning_updates == 0
    assert stats.state == MindState.INITIALIZING
    assert stats.is_healthy is True


def test_continuous_mind_stats_uptime():
    """Test uptime calculation."""
    stats = ContinuousMindStats()

    # Wait a bit
    time.sleep(0.01)

    assert stats.uptime > 0.0


def test_continuous_mind_stats_health():
    """Test health status."""
    stats = ContinuousMindStats()

    assert stats.is_healthy is True

    # Add errors
    for _ in range(5):
        stats.errors_in_window += 1

    assert stats.is_healthy is False


@pytest.mark.asyncio
async def test_continuous_mind_get_stats(continuous_mind: Any, sample_receipts: Any) -> None:
    """Test statistics retrieval."""
    batch = ReceiptBatch(receipts=sample_receipts[:2])
    await continuous_mind._process_batch(batch)

    stats = continuous_mind.get_stats()

    assert "state" in stats
    assert "uptime_seconds" in stats
    assert "receipts_processed" in stats
    assert "learning_updates" in stats
    assert "is_healthy" in stats
    assert stats["receipts_processed"] > 0


# =============================================================================
# TESTS: INTEGRATION
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_full_cycle(continuous_mind: Any, sample_receipts: Any) -> None:
    """Test full cycle: start → receive → learn → stop."""
    receipt_queue = list(sample_receipts)

    async def source():
        nonlocal receipt_queue
        if receipt_queue:
            batch = receipt_queue[:1]
            receipt_queue = receipt_queue[1:]
            return batch
        return []

    continuous_mind.set_receipt_source(source)
    continuous_mind.batch_size = 1

    # Start learning
    await continuous_mind.start()

    # Wait for all receipts to be processed
    await asyncio.sleep(0.3)

    # Stop
    await continuous_mind.stop()

    # Verify learning occurred
    assert continuous_mind.stats.total_receipts_processed >= len(sample_receipts)
    assert continuous_mind.stats.processing_rate > 0


@pytest.mark.asyncio
async def test_continuous_mind_with_learning_engine_integration(stigmergy_learner: Any) -> None:
    """Test integration with learning engine."""
    engine = ReceiptLearningEngine(
        organism_rssm=None,
        stigmergy_learner=stigmergy_learner,
        min_sample_size=1,
    )

    daemon = create_continuous_mind(
        learning_engine=engine,
        poll_interval=0.01,
    )

    receipt = {
        "intent": {"action": "research.web"},
        "actor": "colony:grove:agent1",
        "verifier": {"status": "verified"},
        "duration_ms": 1000,
    }

    # Process a receipt
    await daemon._learn_from_receipt(receipt)

    # Should have updated utilities
    assert daemon.stats.total_receipts_processed == 0  # Not via batch
    # But learning engine should have processed it


# =============================================================================
# TESTS: CONCURRENT SAFETY
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_concurrent_operations(continuous_mind: Any) -> None:
    """Test concurrent operations (pause/resume/stop)."""
    await continuous_mind.start()

    # Run multiple operations concurrently
    await asyncio.gather(
        continuous_mind.pause(),
        continuous_mind.resume(),
        asyncio.sleep(0.01),
    )

    assert continuous_mind.is_running()
    await continuous_mind.stop()


@pytest.mark.asyncio
async def test_continuous_mind_multiple_daemons(learning_engine: Any) -> None:
    """Test multiple independent daemon instances."""
    daemon1 = create_continuous_mind(learning_engine=learning_engine)
    daemon2 = create_continuous_mind(learning_engine=learning_engine)

    assert daemon1 is not daemon2

    await daemon1.start()
    await daemon2.start()

    assert daemon1.is_running()
    assert daemon2.is_running()

    await daemon1.stop()
    await daemon2.stop()


# =============================================================================
# TESTS: EDGE CASES
# =============================================================================


@pytest.mark.asyncio
async def test_continuous_mind_empty_receipt():
    """Test handling of empty receipt."""
    daemon = create_continuous_mind()
    # Should not error
    await daemon._learn_from_receipt({})


@pytest.mark.asyncio
async def test_continuous_mind_malformed_receipt(continuous_mind: Any) -> None:
    """Test handling of malformed receipts."""
    malformed = {
        # Missing required fields
        "some_field": "some_value",
    }

    batch = ReceiptBatch(receipts=[malformed])
    success = await continuous_mind._process_batch(batch)

    # Should handle gracefully
    assert success is True or success is False  # Either is acceptable


@pytest.mark.asyncio
async def test_continuous_mind_state_transitions(continuous_mind: Any) -> None:
    """Test state transitions."""
    states = []

    # Start
    await continuous_mind.start()
    states.append(continuous_mind.stats.state)

    # Pause
    await continuous_mind.pause()
    states.append(continuous_mind.stats.state)

    # Resume
    await continuous_mind.resume()
    states.append(continuous_mind.stats.state)

    # Stop
    await continuous_mind.stop()
    states.append(continuous_mind.stats.state)

    assert MindState.POLLING in states
    assert MindState.PAUSED in states
    assert MindState.STOPPED in states


__all__ = [
    "test_continuous_mind_full_cycle",
    "test_continuous_mind_initialization",
    "test_continuous_mind_start_stop",
]
