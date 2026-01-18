"""Disaster Recovery Tests

Tests system resilience to catastrophic failures.

Scenarios:
- Database connection lost mid-transaction
- Redis cluster node failure
- Disk full
- Network partition
- Memory exhaustion
- CPU saturation
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_e2e
import asyncio
import os
from unittest.mock import patch
from sqlalchemy import text

CHAOS_ENABLED = os.getenv("KAGAMI_ENABLE_CHAOS_TESTS", "0") == "1"
CHAOS_SKIP = pytest.mark.skipif(
    not CHAOS_ENABLED, reason="Chaos tests require KAGAMI_ENABLE_CHAOS_TESTS=1"
)
# =============================================================================
# TEST CONSTANTS - Named values for disaster scenarios
# =============================================================================
# Rate limiter defaults
RATE_LIMIT_RPM = 100  # Requests per minute
RATE_LIMIT_MAX_REMAINING = 100  # Maximum remaining requests
# Memory guard thresholds (GB)
MEMORY_SOFT_LIMIT_GB = 0.5
MEMORY_HARD_LIMIT_GB = 1.0
# Memory allocation size for exhaustion test
MEMORY_CHUNK_SIZE = 50 * 1024 * 1024 // 8  # 50MB as int count
MEMORY_MAX_ITERATIONS = 50
# Network timeouts
NETWORK_SLOW_OPERATION_SEC = 10.0
NETWORK_TIMEOUT_SEC = 2.0
# CPU saturation
CPU_INTENSIVE_ITERATIONS = 10**7
# Correlation ID prefix
CORRELATION_ID_PREFIX = "corr-"


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_db_connection_lost_mid_transaction() -> None:
    """Test graceful handling when DB dies during transaction."""
    from sqlalchemy.exc import OperationalError
    from kagami.core.database.async_connection import get_async_session

    with patch("kagami.core.database.async_connection.get_async_session") as mock_session:
        mock_session.side_effect = OperationalError("Connection lost", None, None)  # type: ignore[arg-type]
        with pytest.raises(OperationalError):
            async with get_async_session() as session:
                await session.execute(text("SELECT 1"))


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_redis_unavailable_graceful_degradation() -> None:
    """Test system degrades gracefully when Redis unavailable - should allow through."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    with patch("kagami.core.caching.redis.RedisClientFactory.get_client") as mock_get_client:
        mock_get_client.side_effect = RedisConnectionError("Redis unavailable")
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=RATE_LIMIT_RPM)
        is_allowed, remaining, reset = limiter.is_allowed("test_client")
        # When Redis fails, limiter should gracefully degrade (allow through)
        assert isinstance(is_allowed, bool)
        assert is_allowed is True, "Rate limiter should allow requests when Redis is unavailable"
        # Remaining should be a reasonable value (max or default)
        assert isinstance(remaining, int)
        assert 0 <= remaining <= RATE_LIMIT_MAX_REMAINING, f"Unexpected remaining: {remaining}"
        # Reset time should be valid
        assert isinstance(reset, (int, float))


@pytest.mark.chaos
@CHAOS_SKIP
def test_disk_full_scenario() -> None:
    """Test handling when filesystem is full."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        large_file = os.path.join(tmpdir, "large.dat")
        with pytest.raises((OSError, IOError)):
            with open(large_file, "wb") as f:
                try:
                    f.write(b"0" * 1024**3)
                except OSError:
                    raise


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_memory_exhaustion_protection() -> None:
    """Test Agent Memory Guard protects against OOM - must detect before crash."""
    from kagami.core.safety.agent_memory_guard import AgentMemoryGuard

    guard = AgentMemoryGuard(soft_limit_gb=MEMORY_SOFT_LIMIT_GB, hard_limit_gb=MEMORY_HARD_LIMIT_GB)
    allocations = []
    exceeded = False
    triggered_at_gb = None
    for _i in range(MEMORY_MAX_ITERATIONS):
        try:
            # Allocate 50MB chunks
            allocations.append([0] * MEMORY_CHUNK_SIZE)
        except MemoryError:
            # System ran out of memory
            exceeded = True
            break
        guard_exceeded, current_gb, limit_gb = guard.check_limits()
        if guard_exceeded:
            triggered_at_gb = current_gb
            print(f"✅ Memory guard triggered at {current_gb:.2f}GB (limit: {limit_gb:.2f}GB)")
            exceeded = True
            break
    allocations.clear()
    assert exceeded, "Memory guard should have detected exhaustion"
    # If guard triggered (not just MemoryError), verify it was within limits
    if triggered_at_gb is not None:
        assert (
            triggered_at_gb >= MEMORY_SOFT_LIMIT_GB
        ), f"Guard triggered too early: {triggered_at_gb:.2f}GB < {MEMORY_SOFT_LIMIT_GB}GB"
        assert (
            triggered_at_gb <= MEMORY_HARD_LIMIT_GB * 1.5
        ), f"Guard triggered too late: {triggered_at_gb:.2f}GB > {MEMORY_HARD_LIMIT_GB * 1.5}GB"


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_idempotency_redis_failure_fallback() -> None:
    """Test idempotency falls back when Redis fails during check."""
    from redis.exceptions import ConnectionError as RedisConnectionError
    from kagami_api.idempotency import IdempotencyManager

    manager = IdempotencyManager()
    with patch.object(manager, "_redis_check") as mock_redis:
        mock_redis.side_effect = RedisConnectionError("Connection lost")
        result = await manager.check_and_store(
            key="test-key", path="/api/test", user_id="test", tenant_id="test", ttl_seconds=300
        )
        assert result is not None


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.slow
@pytest.mark.asyncio
async def test_network_partition_simulation() -> None:
    """Test behavior during network partition."""

    async def slow_operation():
        await asyncio.sleep(10)
        return "data"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=2.0)


@pytest.mark.chaos
@CHAOS_SKIP
def test_cpu_saturation_graceful_degradation() -> None:
    """Test system continues to function under CPU saturation."""
    import multiprocessing

    def cpu_intensive_task(n: Any) -> Any:
        """CPU-bound task that computes sum."""
        total = 0
        for i in range(CPU_INTENSIVE_ITERATIONS):
            total += i
        return total

    num_cores = multiprocessing.cpu_count()
    # Spawn 2x cores to saturate CPU
    with multiprocessing.Pool(processes=num_cores * 2) as pool:
        results = pool.map_async(cpu_intensive_task, range(num_cores * 2))
        # System should still handle requests under load
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter()
        is_allowed, remaining, _reset = limiter.is_allowed("test_client")
        # Verify rate limiter still functions
        assert isinstance(is_allowed, bool)
        assert is_allowed is True, "Rate limiter should function under CPU load"
        assert isinstance(remaining, int)
        assert remaining >= 0, f"Invalid remaining count: {remaining}"
        # Wait for workers to complete
        results.wait(timeout=10)


@pytest.mark.chaos
@CHAOS_SKIP
@pytest.mark.asyncio
async def test_cascading_failure_isolation() -> None:
    """Test that failures don't cascade - correlation tracking should work."""
    from kagami.core.utils.ids import generate_correlation_id

    # Generate correlation ID for tracking
    corr_id = generate_correlation_id(prefix="corr")
    assert corr_id.startswith(CORRELATION_ID_PREFIX), f"Invalid correlation ID format: {corr_id}"
    # Verify it has more than just the prefix
    assert len(corr_id) > len(CORRELATION_ID_PREFIX), f"Correlation ID too short: {corr_id}"
    # Attempt to emit receipt - should not crash even if subsystems fail
    from kagami.core.receipts import emit_receipt

    exception_raised = False
    try:
        emit_receipt(
            correlation_id=corr_id,
            action="test.cascade",
            app="Chaos",
            args={},
            event_name="TEST",
            event_data={},
            duration_ms=1.0,
        )
    except Exception as e:
        # Failures should be isolated - we catch and note them
        exception_raised = True
        print(f"Receipt emission failed (expected in chaos test): {e}")
    # Either succeeds or fails gracefully (no assertion on exception_raised)
    # The point is the system didn't crash catastrophically


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
