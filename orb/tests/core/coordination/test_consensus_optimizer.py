"""Tests for Consensus Optimizer.

Target latencies:
- p50: <50ms
- p99: <100ms

Created: December 15, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import asyncio
import time

from kagami.core.coordination.consensus_optimizer import (
    BatchedConsensus,
    ConsensusCache,
    ConsensusOptimizer,
    PredictiveConsensus,
    create_consensus_optimizer,
    detect_task_affinity,
    group_by_fano_affinity,
)
from kagami.core.coordination.kagami_consensus import (
    ColonyID,
    ConsensusState,
    CoordinationProposal,
    create_consensus_protocol,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def consensus():
    """Create KagamiConsensus instance."""
    return create_consensus_protocol(
        agreement_threshold=0.5,  # Lower threshold for testing
        enable_cot=False,  # Disable CoT for speed
    )


@pytest.fixture
def cache():
    """Create ConsensusCache instance."""
    return ConsensusCache(ttl=60, max_size=100)


@pytest.fixture
def predictor(consensus: Any) -> Any:
    """Create PredictiveConsensus instance."""
    return PredictiveConsensus(
        consensus=consensus,
        world_model=None,
        confidence_threshold=0.9,
    )


@pytest.fixture
def batcher(consensus: Any) -> Any:
    """Create BatchedConsensus instance."""
    return BatchedConsensus(
        consensus=consensus,
        batch_size=5,
        batch_timeout=0.05,
    )


@pytest.fixture
def optimizer(consensus: Any) -> Any:
    """Create ConsensusOptimizer with all layers."""
    return create_consensus_optimizer(
        consensus=consensus,
        enable_cache=True,
        enable_prediction=True,
        enable_batching=True,
        cache_ttl=60,
        batch_size=5,
    )


# =============================================================================
# FANO AFFINITY GROUPING TESTS
# =============================================================================


def test_detect_task_affinity_creative_flow():
    """Test detection of creative flow affinity."""
    task = "Brainstorm ideas and implement solution"
    affinity = detect_task_affinity(task)
    assert affinity == "creative_flow"


def test_detect_task_affinity_plan_build():
    """Test detection of plan-build affinity."""
    task = "Design architecture and implement system"
    affinity = detect_task_affinity(task)
    assert affinity == "plan_build"


def test_detect_task_affinity_research_verify():
    """Test detection of research-verify affinity."""
    task = "Research best practices and validate approach"
    affinity = detect_task_affinity(task)
    assert affinity == "research_verify"


def test_group_by_fano_affinity():
    """Test grouping tasks by Fano affinity."""
    tasks = [
        "Implement feature A",
        "Research pattern B",
        "Build component C",
        "Validate design D",
        "Debug issue E",
    ]

    batches = group_by_fano_affinity(tasks, batch_size=3)

    # Should create multiple batches
    assert len(batches) > 0
    assert all(len(batch) <= 3 for batch in batches)

    # All tasks should be included
    flattened = [task for batch in batches for task in batch]
    assert len(flattened) == len(tasks)


# =============================================================================
# CONSENSUS CACHE TESTS
# =============================================================================


def test_cache_miss(cache: Any) -> None:
    """Test cache miss."""
    result = cache.get("test task")
    assert result is None


def test_cache_put_and_get(cache: Any) -> None:
    """Test storing and retrieving from cache."""
    task = "implement feature"
    state = ConsensusState(
        proposals=[],
        agreement_matrix=None,  # type: ignore[arg-type]
        converged=True,
    )

    cache.put(task, state)
    cached = cache.get(task)

    assert cached is not None
    assert cached.converged is True


def test_cache_ttl_expiration(cache: Any, monkeypatch: Any) -> None:
    """Test cache TTL expiration."""
    cache.ttl = 0.1  # 100ms

    task = "test task"
    state = ConsensusState(proposals=[], agreement_matrix=None, converged=True)  # type: ignore[arg-type]

    # Track time progression
    current_time = [time.time()]

    def mock_time() -> float:
        """Mock time.time() to advance TTL."""
        return current_time[0]

    monkeypatch.setattr("time.time", mock_time)

    cache.put(task, state)

    # Immediately: cache hit
    assert cache.get(task) is not None

    # Advance time past TTL
    current_time[0] += 0.2

    # After TTL: cache miss
    assert cache.get(task) is None


def test_cache_lru_eviction(cache: Any) -> None:
    """Test LRU eviction."""
    cache.max_size = 3

    # Fill cache
    for i in range(3):
        cache.put(f"task_{i}", ConsensusState(proposals=[], agreement_matrix=None, converged=True))  # type: ignore[arg-type]

    # Add one more (should evict oldest)
    cache.put("task_3", ConsensusState(proposals=[], agreement_matrix=None, converged=True))  # type: ignore[arg-type]

    # task_0 should be evicted
    assert cache.get("task_0") is None
    assert cache.get("task_1") is not None
    assert cache.get("task_2") is not None
    assert cache.get("task_3") is not None


@pytest.mark.asyncio
async def test_cache_get_or_compute(cache: Any) -> None:
    """Test get_or_compute pattern."""
    call_count = 0

    async def compute_fn(task: str):
        nonlocal call_count
        call_count += 1
        return ConsensusState(proposals=[], agreement_matrix=None, converged=True)  # type: ignore[arg-type]

    task = "test task"

    # First call: compute
    result1 = await cache.get_or_compute(task, compute_fn)
    assert call_count == 1
    assert result1.converged is True

    # Second call: cached (no computation)
    result2 = await cache.get_or_compute(task, compute_fn)
    assert call_count == 1  # No additional computation
    assert result2.converged is True


def test_cache_stats(cache: Any) -> None:
    """Test cache statistics."""
    for i in range(5):
        cache.put(f"task_{i}", ConsensusState(proposals=[], agreement_matrix=None, converged=True))  # type: ignore[arg-type]

    stats = cache.get_stats()

    assert stats["size"] == 5
    assert stats["max_size"] == 100
    assert stats["ttl_seconds"] == 60


# =============================================================================
# PREDICTIVE CONSENSUS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_predictor_high_confidence(predictor: Any) -> None:
    """Test prediction with high confidence."""
    task = "implement feature"

    start = time.time()
    state = await predictor.predict_or_compute(task)
    duration = time.time() - start

    # Should have routing (predicted or computed)
    assert state.consensus_routing is not None
    assert len(state.consensus_routing) > 0

    # Should be fast (prediction should trigger)
    assert duration < 0.5  # <500ms (allow for fallback)


@pytest.mark.asyncio
async def test_predictor_keyword_matching(predictor: Any) -> None:
    """Test keyword-based routing prediction."""
    # Test different task types
    tasks = [
        ("implement new feature", ColonyID.FORGE),
        ("verify security", ColonyID.CRYSTAL),
        ("debug error", ColonyID.FLOW),
        ("plan architecture", ColonyID.BEACON),
        ("research patterns", ColonyID.GROVE),
    ]

    for task, expected_colony in tasks:
        state = await predictor.predict_or_compute(task)
        assert state.converged is True
        assert expected_colony in state.consensus_routing


# =============================================================================
# BATCHED CONSENSUS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_batcher_single_task(batcher: Any) -> None:
    """Test batching with single task."""
    task = "implement feature"

    start = time.time()
    state = await batcher.submit_task(task)
    duration = time.time() - start

    assert state.converged is True

    # Should wait for timeout (50ms) since batch not full
    assert duration >= 0.04  # ~50ms timeout


@pytest.mark.asyncio
async def test_batcher_full_batch(batcher: Any) -> None:
    """Test immediate processing when batch full."""
    batcher.batch_size = 3

    # Submit 3 tasks in parallel (fills batch immediately)
    tasks = ["task_1", "task_2", "task_3"]

    start = time.time()
    results = await asyncio.gather(*[batcher.submit_task(task) for task in tasks])
    duration = time.time() - start

    # Should get results (even if consensus didn't converge)
    assert len(results) == 3
    assert all(r is not None for r in results)

    # Should NOT wait for timeout (immediate processing)
    # Allow some overhead but should be faster than timeout
    assert duration < 0.5  # Much faster than timeout


@pytest.mark.asyncio
async def test_batcher_timeout_trigger(batcher: Any) -> None:
    """Test batch triggered by timeout."""
    batcher.batch_size = 10  # Large batch
    batcher.batch_timeout = 0.05  # 50ms

    task = "single task"

    start = time.time()
    state = await batcher.submit_task(task)
    duration = time.time() - start

    # Should get a result
    assert state is not None

    # Should wait for timeout
    assert duration >= 0.04
    assert duration < 0.2  # But not too long


# =============================================================================
# UNIFIED OPTIMIZER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_optimizer_cache_hit(optimizer: Any) -> None:
    """Test optimizer using cache."""
    task = "implement feature"

    # First call: compute and cache
    start1 = time.time()
    result1 = await optimizer.run_consensus(task)
    duration1 = time.time() - start1

    assert result1.converged is True

    # Second call: cache hit
    start2 = time.time()
    result2 = await optimizer.run_consensus(task)
    duration2 = time.time() - start2

    assert result2.converged is True

    # Cache hit should be MUCH faster
    assert duration2 < duration1 / 10  # At least 10x speedup


@pytest.mark.asyncio
async def test_optimizer_prediction_layer(optimizer: Any) -> None:
    """Test optimizer using prediction."""
    # Disable cache to isolate prediction
    optimizer.cache = None

    task = "verify security"

    start = time.time()
    state = await optimizer.run_consensus(task)
    duration = time.time() - start

    assert state.converged is True

    # Prediction should be fast
    assert duration < 0.1  # <100ms


@pytest.mark.asyncio
async def test_optimizer_stats(optimizer: Any) -> None:
    """Test optimizer statistics."""
    # Run a few tasks
    tasks = ["implement A", "verify B", "debug C"]

    for task in tasks:
        await optimizer.run_consensus(task)

    stats = optimizer.get_stats()

    # Should have cache stats
    assert "cache" in stats
    assert stats["cache"]["size"] >= 0

    # Should have predictor stats
    assert "predictor" in stats


@pytest.mark.asyncio
async def test_optimizer_latency_target_p50(optimizer: Any) -> None:
    """Test p50 latency target (<50ms) with cache."""
    task = "implement feature"

    # Prime cache
    await optimizer.run_consensus(task)

    # Measure cached latency
    latencies = []
    for _ in range(10):
        start = time.time()
        await optimizer.run_consensus(task)
        latencies.append(time.time() - start)

    p50 = sorted(latencies)[5]  # Median

    # p50 should be <50ms (cached)
    assert p50 < 0.05, f"p50 latency {p50 * 1000:.1f}ms exceeds 50ms target"


@pytest.mark.asyncio
async def test_optimizer_latency_target_p99(optimizer: Any) -> None:
    """Test p99 latency target (<100ms) with prediction."""
    # Disable cache to test prediction layer
    optimizer.cache = None

    latencies = []
    tasks = [f"implement feature {i}" for i in range(100)]

    for task in tasks:
        start = time.time()
        await optimizer.run_consensus(task)
        latencies.append(time.time() - start)

    p99 = sorted(latencies)[98]  # 99th percentile

    # p99 should be <100ms (prediction)
    assert p99 < 0.1, f"p99 latency {p99 * 1000:.1f}ms exceeds 100ms target"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_end_to_end_optimization(optimizer: Any) -> None:
    """Test full optimization pipeline."""
    tasks = [
        "implement authentication",
        "verify security",
        "debug login error",
        "implement authentication",  # Duplicate (cache hit)
        "research best practices",
    ]

    results = []
    for task in tasks:
        start = time.time()
        state = await optimizer.run_consensus(task)
        duration = time.time() - start
        results.append((task, state, duration))

    # All should converge
    assert all(state.converged for _, state, _ in results)

    # Duplicate task should be much faster (cache hit)
    auth_runs = [(i, d) for i, (t, _, d) in enumerate(results) if "authentication" in t]
    assert len(auth_runs) == 2

    first_duration = auth_runs[0][1]
    second_duration = auth_runs[1][1]

    # Second run should be >5x faster (cache speedup)
    assert second_duration < first_duration / 5


@pytest.mark.asyncio
async def test_optimizer_factory():
    """Test create_consensus_optimizer factory."""
    optimizer = create_consensus_optimizer(
        enable_cache=True,
        enable_prediction=True,
        enable_batching=True,
    )

    assert optimizer.cache is not None
    assert optimizer.predictor is not None
    assert optimizer.batcher is not None

    # Should work (get a result, even if consensus doesn't converge)
    state = await optimizer.run_consensus("test task")
    assert state is not None
    assert state.consensus_routing is not None
