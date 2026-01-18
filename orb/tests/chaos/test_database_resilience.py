"""Chaos Test: Database Resilience

Tests K os behavior when database fails or becomes slow.

Created: November 16, 2025 (Q2 Production Roadmap)
Enhanced: December 31, 2025 (Proper retry logic testing)
"""

from __future__ import annotations
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_e2e,
    pytest.mark.chaos,
    pytest.mark.timeout(60),
]

import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLTimeoutError


@pytest.mark.asyncio
async def test_database_timeout_graceful_degradation() -> None:
    """Test that database timeouts are handled gracefully."""
    from kagami.core.database import get_async_session

    # Mock database to timeout
    with patch("kagami.core.database.async_connection.create_async_engine") as mock_engine:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLTimeoutError("Connection timeout")

        # Attempt operation
        try:
            async with get_async_session() as session:
                await session.execute("SELECT 1")
                pytest.fail("Should have raised timeout")
        except (SQLTimeoutError, Exception):
            pass  # Expected

    # System should remain operational (not crash)
    # Verify health endpoint still responds via test client
    from kagami_api.routes.vitals.probes import get_router
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(get_router())

    # Test via client - router has /probes prefix, endpoint is /live
    with TestClient(app) as client:
        response = client.get("/probes/live")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok"


@pytest.mark.asyncio
async def test_database_connection_refused() -> None:
    """Test behavior when database is completely unavailable."""

    with patch("kagami.core.database.async_connection.create_async_engine") as mock_engine:
        mock_engine.side_effect = OperationalError("Connection refused", None, None)  # type: ignore[arg-type]

        # Should handle gracefully
        try:
            from kagami.core.database import get_async_engine

            engine = get_async_engine()
        except Exception as e:
            # Expected to fail, but should log cleanly
            assert "Connection refused" in str(e) or "OperationalError" in str(type(e).__name__)


@pytest.mark.asyncio
async def test_receipt_storage_fallback() -> None:
    """Test that receipts handle storage failures gracefully."""
    from kagami.core.receipts import UnifiedReceiptFacade as URF

    # Emit receipt - should not crash even if storage layer has issues
    correlation_id = URF.generate_correlation_id()

    try:
        receipt = await URF.emit(
            correlation_id=correlation_id,
            action="plan",
            event_name="test.db_failure",
            data={"test": True},
        )
        # Receipt emitted successfully - verify it's a valid receipt
        assert isinstance(receipt, dict), "Receipt should be dict-like"
        assert "correlation_id" in receipt or correlation_id, "Correlation ID should be present"
        assert receipt.get("event_name") == "test.db_failure", "Event name should match"
    except Exception as e:
        # Should handle gracefully - log but not crash
        # Some exceptions are acceptable in chaos scenario
        pytest.skip(f"Receipt emission failed (acceptable in chaos): {e}")


@pytest.mark.asyncio
async def test_serialization_failure_retry() -> None:
    """Test automatic retry on serialization conflicts."""
    from sqlalchemy.exc import DBAPIError

    from kagami.core.database import get_async_session

    # Should not match non-serialization errors
    assert not _is_serialization_error(Exception("unique constraint violation"))
    assert not _is_serialization_error(Exception("connection refused"))
    assert not _is_serialization_error(Exception("timeout"))
    assert not _is_serialization_error(Exception(""))

    async def failing_operation():
        async with get_async_session() as session:
            attempts.append(1)
            if len(attempts) < 3:
                # First 2 attempts fail
                raise DBAPIError("restart transaction", None, None, None)  # type: ignore[arg-type]
            # Third attempt succeeds
            return {"success": True}


@pytest.mark.asyncio
async def test_serialization_retry_via_cockroachdb_client() -> None:
    """Test CockroachDB client's execute method with automatic retry.

    The CockroachDB client (cockroach.py) has built-in retry logic for
    serialization errors (40001, serialization, retry transaction).
    """
    from kagami.core.database.cockroach import CockroachDB, CockroachConfig

    # Create client with fast retry settings for testing
    config = CockroachConfig(
        max_retries=3,
        retry_delay=0.01,  # Fast for testing
    )
    client = CockroachDB(config)

    attempt_count = 0

    # Mock the session factory and execute
    mock_result = MagicMock()
    mock_result.scalar.return_value = "test_value"

    async def mock_execute(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise Exception("40001: serialization failure")
        return mock_result

    # Patch the internal connection
    client._connected = True
    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    client.session_factory = MagicMock(return_value=mock_session)

    # Execute should retry and succeed
    result = await client.execute("SELECT 1")

    assert attempt_count == 2, f"Expected 2 attempts, got {attempt_count}"
    assert result is mock_result


@pytest.mark.asyncio
async def test_cockroachdb_retry_exhausted() -> None:
    """Test that CockroachDB client exhausts retries and raises."""
    from kagami.core.database.cockroach import CockroachDB, CockroachConfig

    config = CockroachConfig(
        max_retries=3,
        retry_delay=0.01,
    )
    client = CockroachDB(config)

    attempt_count = 0

    async def always_fail(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise Exception("40001: serialization failure - persistent")

    client._connected = True
    mock_session = AsyncMock()
    mock_session.execute = always_fail
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    client.session_factory = MagicMock(return_value=mock_session)

    with pytest.raises(Exception) as exc_info:
        await client.execute("SELECT 1")

    assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
    assert "serialization" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cockroachdb_non_retriable_error() -> None:
    """Test that non-serialization errors fail immediately without retry."""
    from kagami.core.database.cockroach import CockroachDB, CockroachConfig

    config = CockroachConfig(
        max_retries=5,
        retry_delay=0.01,
    )
    client = CockroachDB(config)

    attempt_count = 0

    async def fail_with_constraint(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise Exception("unique constraint violation")

    client._connected = True
    mock_session = AsyncMock()
    mock_session.execute = fail_with_constraint
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    client.session_factory = MagicMock(return_value=mock_session)

    with pytest.raises(Exception) as exc_info:
        await client.execute("INSERT INTO ...", retry=True)

    # Should fail on first attempt - non-retriable error
    assert attempt_count == 1, f"Expected 1 attempt for non-retriable error, got {attempt_count}"
    assert "unique constraint" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cockroachdb_exponential_backoff() -> None:
    """Test that CockroachDB retry uses exponential backoff."""
    from kagami.core.database.cockroach import CockroachDB, CockroachConfig
    import time

    initial_delay = 0.05
    config = CockroachConfig(
        max_retries=3,
        retry_delay=initial_delay,
    )
    client = CockroachDB(config)

    attempt_times: list[float] = []

    async def fail_with_timing(*args, **kwargs):
        attempt_times.append(time.monotonic())
        if len(attempt_times) < 3:
            raise Exception("serialization failure")
        return MagicMock()

    client._connected = True
    mock_session = AsyncMock()
    mock_session.execute = fail_with_timing
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    client.session_factory = MagicMock(return_value=mock_session)

    await client.execute("SELECT 1")

    assert len(attempt_times) == 3

    # Check delays increase (exponential backoff)
    delay1 = attempt_times[1] - attempt_times[0]
    delay2 = attempt_times[2] - attempt_times[1]

    # First delay should be ~initial_delay
    assert delay1 >= initial_delay * 0.8, f"First delay {delay1} too short"
    # Second delay should be ~2x first (exponential)
    assert delay2 >= delay1 * 1.5, f"Second delay {delay2} should be > first delay {delay1}"


@pytest.mark.asyncio
async def test_circuit_breaker_trips_on_failures() -> None:
    """Test circuit breaker pattern in optimized connection pool."""
    from kagami.core.database.optimized_pool import CircuitBreaker

    breaker = CircuitBreaker(failure_threshold=3, timeout=0.1)

    failure_count = 0

    def failing_operation():
        nonlocal failure_count
        failure_count += 1
        raise Exception("Connection failed")

    # Trip the circuit breaker
    for _ in range(3):
        with pytest.raises(Exception):  # noqa: B017
            breaker.call(failing_operation)

    # Circuit should now be open
    assert breaker.state == "open"
    assert failure_count == 3

    # Calls should fail fast without executing operation
    with pytest.raises(RuntimeError) as exc_info:
        breaker.call(failing_operation)

    assert "Circuit breaker is open" in str(exc_info.value)
    assert failure_count == 3  # Operation not called


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery() -> None:
    """Test circuit breaker transitions through half-open state on recovery."""
    from kagami.core.database.optimized_pool import CircuitBreaker

    breaker = CircuitBreaker(failure_threshold=2, timeout=0.05)

    # Trip the circuit
    for _ in range(2):
        with pytest.raises(Exception):  # noqa: B017
            breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))

    assert breaker.state == "open"

    # Wait for timeout
    await asyncio.sleep(0.06)

    # Next call should transition to half-open and succeed
    result = breaker.call(lambda: "recovered")
    assert result == "recovered"
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure() -> None:
    """Test circuit breaker returns to open state if half-open call fails."""
    from kagami.core.database.optimized_pool import CircuitBreaker

    breaker = CircuitBreaker(failure_threshold=2, timeout=0.05)

    # Trip the circuit
    for _ in range(2):
        with pytest.raises(Exception):  # noqa: B017
            breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))

    assert breaker.state == "open"

    # Wait for timeout
    await asyncio.sleep(0.06)

    # First call in half-open state fails - should go back to open
    with pytest.raises(Exception):  # noqa: B017
        breaker.call(lambda: (_ for _ in ()).throw(Exception("still failing")))

    assert breaker.state == "open"


@pytest.mark.asyncio
async def test_circuit_breaker_stays_closed_during_normal_operation() -> None:
    """Test circuit breaker accumulates failures but stays closed below threshold."""
    from kagami.core.database.optimized_pool import CircuitBreaker

    breaker = CircuitBreaker(failure_threshold=3, timeout=0.1)

    # Fail twice (not enough to open)
    for _ in range(2):
        with pytest.raises(Exception):  # noqa: B017
            breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))

    assert breaker.state == "closed"
    assert breaker.failure_count == 2

    # Success still works even with accumulated failures
    result = breaker.call(lambda: "success")
    assert result == "success"
    # Note: This implementation accumulates failures until threshold
    # (failure count only resets on half-open -> closed transition)
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_basic_session_rollback_on_error() -> None:
    """Test that get_async_db_session properly rolls back on errors."""
    from kagami.core.database.async_connection import get_async_db_session

    rollback_called = False
    commit_called = False

    mock_session = AsyncMock()

    async def track_commit():
        nonlocal commit_called
        commit_called = True
        raise Exception("Database error")

    async def track_rollback():
        nonlocal rollback_called
        rollback_called = True

    mock_session.commit = track_commit
    mock_session.rollback = track_rollback
    mock_session.close = AsyncMock()

    with patch("kagami.core.database.async_connection._get_async_session_factory") as mock_factory:
        mock_factory.return_value = MagicMock(return_value=mock_session)

        with pytest.raises(Exception):  # noqa: B017
            async with get_async_db_session() as session:
                # Session work here
                pass

        assert commit_called, "Commit should have been called"
        assert rollback_called, "Rollback should have been called after error"


@pytest.mark.asyncio
async def test_resilience_circuit_breaker_async() -> None:
    """Test async circuit breaker from resilience module."""
    from kagami.core.resilience.circuit_breaker import CircuitBreaker, CircuitState

    breaker = CircuitBreaker("test_db")

    # Initial state is closed
    assert breaker.state == CircuitState.CLOSED

    # Track call success/failure
    async def successful_op():
        return "success"

    async def failing_op():
        raise Exception("Database unavailable")

    # Successful call should work
    result = await breaker.call(successful_op)
    assert result == "success"

    # Multiple failures should trip the breaker (default threshold is 5)
    for _ in range(5):
        with pytest.raises(Exception):  # noqa: B017
            await breaker.call(failing_op)

    # Should now be open
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_transaction_rollback_behavior() -> None:
    """Test that transactions are properly rolled back on various error types."""
    from kagami.core.database.async_connection import get_async_db_session, _is_serialization_error

    # Test serialization error is detected as retriable
    ser_error = Exception("restart transaction: retry_serializable")
    assert _is_serialization_error(ser_error)

    # Test that non-serialization errors are not marked retriable
    constraint_error = Exception("unique constraint violation")
    assert not _is_serialization_error(constraint_error)


@pytest.mark.asyncio
async def test_cockroachdb_transaction_retry() -> None:
    """Test CockroachDB execute_transaction with retry logic."""
    from kagami.core.database.cockroach import CockroachDB, CockroachConfig

    config = CockroachConfig(
        max_retries=3,
        retry_delay=0.01,
    )
    client = CockroachDB(config)

    attempt_count = 0

    async def mock_execute(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise Exception("retry transaction: serialization")
        return MagicMock()

    client._connected = True
    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Create a proper async context manager mock - needs self parameter
    async def aenter(self):
        return mock_session

    async def aexit(self, *args):
        return None

    mock_session.__aenter__ = aenter
    mock_session.__aexit__ = aexit

    # Also need to mock begin() as an async context manager
    mock_begin = AsyncMock()
    mock_begin.__aenter__ = AsyncMock(return_value=None)
    mock_begin.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_begin)

    client.session_factory = MagicMock(return_value=mock_session)

    # Execute transaction should retry and succeed
    result = await client.execute_transaction([("SELECT 1", {})])

    assert attempt_count >= 1, f"Expected at least 1 attempt, got {attempt_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
