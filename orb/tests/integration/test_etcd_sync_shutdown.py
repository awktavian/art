"""Tests for EtcdReceiptSync thread lifecycle and cleanup.

Verifies that the etcd watch thread is properly managed with ThreadPoolExecutor
and that no thread leaks occur after shutdown.
"""

from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.tier2,  # Integration tests with external services
]

import asyncio
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest_asyncio

from kagami.core.receipts.etcd_receipt_sync import EtcdReceiptSync


class MockEtcdClient:
    """Mock etcd client for testing."""

    def __init__(self, watch_events: list | None = None):
        """Initialize mock with optional events to emit."""
        self.watch_events = watch_events or []
        self.watch_cancelled = False
        self.lease_created = False

    def watch_prefix(self, prefix: str):
        """Mock watch_prefix that yields events."""

        def cancel():
            self.watch_cancelled = True

        def event_iterator():
            for event in self.watch_events:
                if self.watch_cancelled:
                    break
                yield event

        return event_iterator(), cancel

    def lease(self, ttl: int):
        """Mock lease creation."""
        self.lease_created = True
        return MagicMock()

    def put(self, key: str, value: bytes, lease: Any = None) -> None:
        """Mock put operation."""
        pass


class MockEvent:
    """Mock etcd event."""

    def __init__(self, value: bytes | None):
        self.value = value


@pytest.fixture
def mock_etcd():
    """Provide a mock etcd client."""
    return MockEtcdClient()


@pytest_asyncio.fixture
async def sync_instance(mock_etcd: Any) -> None:
    """Provide an EtcdReceiptSync instance with mocked etcd."""
    sync = EtcdReceiptSync(instance_id="test-instance", rate_limit=100.0, ttl=300)

    # Inject mock etcd client
    sync._etcd_client = mock_etcd
    sync._enabled = True

    yield sync

    # Cleanup after test
    try:
        await sync.stop(timeout=2.0)
    except Exception:
        pass


def _get_etcd_watch_threads() -> list[threading.Thread]:
    """Get all threads with 'etcd_watch' in name."""
    return [t for t in threading.enumerate() if "etcd_watch" in t.name]


@pytest.mark.asyncio
async def test_sync_no_thread_leak_after_stop(sync_instance) -> None:
    """Test that stop() properly cleans up threads."""
    # Verify no threads initially
    initial_threads = _get_etcd_watch_threads()
    assert len(initial_threads) == 0, f"Unexpected threads at start: {initial_threads}"

    # Start watch_receipts generator (doesn't iterate yet)
    receipt_gen = sync_instance.watch_receipts()

    # Start consuming (this launches the thread)
    consume_task = asyncio.create_task(_consume_n_items(receipt_gen, 0))

    # Give thread time to start
    await asyncio.sleep(0.3)

    # Verify thread exists
    active_threads = _get_etcd_watch_threads()
    assert len(active_threads) > 0, "Watch thread should be running"

    # Stop the sync
    await sync_instance.stop(timeout=2.0)

    # Wait for consumer to finish
    try:
        await asyncio.wait_for(consume_task, timeout=2.0)
    except TimeoutError:
        pass

    # Give threads time to clean up
    await asyncio.sleep(0.5)

    # Verify no threads remain
    remaining_threads = _get_etcd_watch_threads()
    assert len(remaining_threads) == 0, f"Thread leak detected: {remaining_threads}"


@pytest.mark.asyncio
async def test_sync_executor_shutdown(sync_instance) -> None:
    """Test that ThreadPoolExecutor is properly shut down."""
    # Start watch_receipts generator
    receipt_gen = sync_instance.watch_receipts()

    # Consume one iteration to initialize executor
    consume_task = asyncio.create_task(_consume_n_items(receipt_gen, 0))
    await asyncio.sleep(0.3)

    # Verify executor exists
    assert sync_instance._watch_executor is not None
    assert not sync_instance._watch_executor._shutdown

    # Stop
    await sync_instance.stop(timeout=2.0)

    # Wait for consumer
    try:
        await asyncio.wait_for(consume_task, timeout=2.0)
    except TimeoutError:
        pass

    # Verify executor is shut down
    assert sync_instance._watch_executor is None or sync_instance._watch_executor._shutdown


@pytest.mark.asyncio
async def test_sync_stop_with_active_watch(mock_etcd) -> None:
    """Test stopping sync while watch is actively receiving events."""
    # Create mock events
    import json

    events = [
        MockEvent(
            json.dumps(
                {
                    "correlation_id": f"event-{i}",
                    "from_instance": "other-instance",
                    "phase": "EXECUTE",
                }
            ).encode()
        )
        for i in range(100)  # Many events to keep watch busy
    ]
    mock_etcd.watch_events = events

    sync = EtcdReceiptSync(instance_id="test-busy", rate_limit=100.0, ttl=300)
    sync._etcd_client = mock_etcd
    sync._enabled = True

    try:
        # Start consuming
        receipt_gen = sync.watch_receipts()
        consume_task = asyncio.create_task(_consume_n_items(receipt_gen, 5))

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Stop while consuming
        start_time = time.time()
        await sync.stop(timeout=2.0)
        stop_duration = time.time() - start_time

        # Should complete within timeout
        assert stop_duration < 3.0, f"Stop took too long: {stop_duration}s"

        # Cancel consumer
        consume_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            pass

        # Verify no threads remain
        await asyncio.sleep(0.5)
        remaining_threads = _get_etcd_watch_threads()
        assert len(remaining_threads) == 0, f"Thread leak: {remaining_threads}"

    finally:
        try:
            await sync.stop(timeout=1.0)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_sync_stop_idempotent(sync_instance) -> None:
    """Test that calling stop() multiple times is safe."""
    # Start and stop once
    receipt_gen = sync_instance.watch_receipts()
    consume_task = asyncio.create_task(_consume_n_items(receipt_gen, 0))
    await asyncio.sleep(0.2)

    await sync_instance.stop(timeout=2.0)

    try:
        await asyncio.wait_for(consume_task, timeout=1.0)
    except TimeoutError:
        pass

    # Call stop again (should be safe)
    await sync_instance.stop(timeout=1.0)

    # Call stop a third time
    await sync_instance.stop(timeout=1.0)

    # Verify no threads
    remaining_threads = _get_etcd_watch_threads()
    assert len(remaining_threads) == 0


@pytest.mark.asyncio
async def test_sync_watch_without_etcd(sync_instance) -> None:
    """Test that watch_receipts handles missing etcd gracefully."""
    # Disable etcd
    sync_instance._enabled = False
    sync_instance._etcd_client = None

    # Should not start any threads
    initial_threads = _get_etcd_watch_threads()

    receipt_gen = sync_instance.watch_receipts()

    # Try to consume (should return immediately)
    count = 0
    async for _ in receipt_gen:
        count += 1
        if count > 5:
            break

    # Should have consumed nothing
    assert count == 0

    # Should have no threads
    final_threads = _get_etcd_watch_threads()
    assert len(final_threads) == len(initial_threads)


@pytest.mark.asyncio
async def test_sync_sentinel_stops_consumer(sync_instance, mock_etcd) -> None:
    """Test that None sentinel properly stops the consumer."""
    # Create a few events
    import json

    events = [
        MockEvent(
            json.dumps(
                {
                    "correlation_id": f"evt-{i}",
                    "from_instance": "other",
                    "phase": "EXECUTE",
                }
            ).encode()
        )
        for i in range(3)
    ]
    mock_etcd.watch_events = events

    receipt_gen = sync_instance.watch_receipts()

    # Start consuming
    consume_task = asyncio.create_task(_consume_n_items(receipt_gen, 10))

    await asyncio.sleep(0.2)

    # Send sentinel via stop()
    await sync_instance.stop(timeout=2.0)

    # Consumer should finish quickly
    try:
        await asyncio.wait_for(consume_task, timeout=2.0)
    except TimeoutError:
        pytest.fail("Consumer did not stop after sentinel")

    # No threads should remain
    await asyncio.sleep(0.3)
    remaining = _get_etcd_watch_threads()
    assert len(remaining) == 0


async def _consume_n_items(async_gen, n: int) -> list:
    """Consume up to n items from async generator."""
    items = []
    try:
        async for item in async_gen:
            items.append(item)
            if len(items) >= n:
                break
    except asyncio.CancelledError:
        pass
    return items


@pytest.mark.asyncio
async def test_sync_stop_timeout_handling() -> None:
    """Test that stop() handles timeout gracefully if thread is stuck."""
    sync = EtcdReceiptSync(instance_id="test-timeout")

    # Create a mock that never completes
    class StuckFuture:
        def result(self, timeout: Any = None) -> None:
            time.sleep(timeout or 10)  # Sleep longer than timeout

    sync._watch_future = StuckFuture()  # type: ignore[assignment]
    sync._watch_executor = Mock()
    sync._watch_executor._shutdown = False

    # Stop with short timeout
    start = time.time()
    await sync.stop(timeout=0.5)
    duration = time.time() - start

    # Should timeout and continue (not hang forever)
    assert duration < 2.0, f"stop() hung for {duration}s"


def test_sync_init_no_threads() -> None:
    """Test that __init__ doesn't start any threads."""
    initial_threads = _get_etcd_watch_threads()
    initial_count = len(initial_threads)

    sync = EtcdReceiptSync(instance_id="test-init")

    after_threads = _get_etcd_watch_threads()
    assert len(after_threads) == initial_count, "Init should not start threads"

    # Verify internal state
    assert sync._watch_executor is None
    assert sync._watch_future is None
    assert sync._watch_queue is None
    assert sync._watch_stop_event is None
