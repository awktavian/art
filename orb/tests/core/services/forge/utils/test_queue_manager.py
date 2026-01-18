"""Tests for forge utils queue_manager module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio

from kagami.forge.utils.queue_manager import (
    QueuedRequest,
    QueuePriority,
    RequestQueue,
    RequestStatus,
)


class TestQueuePriority:
    """Tests for QueuePriority enum."""

    def test_priority_values(self) -> None:
        """Test priority values are ordered."""
        assert QueuePriority.LOW.value < QueuePriority.NORMAL.value
        assert QueuePriority.NORMAL.value < QueuePriority.HIGH.value
        assert QueuePriority.HIGH.value < QueuePriority.URGENT.value


class TestRequestStatus:
    """Tests for RequestStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test all expected statuses exist."""
        assert RequestStatus.PENDING
        assert RequestStatus.RUNNING
        assert RequestStatus.COMPLETED
        assert RequestStatus.FAILED
        assert RequestStatus.CANCELLED
        assert RequestStatus.TIMEOUT


class TestQueuedRequest:
    """Tests for QueuedRequest dataclass."""

    def test_creation(self) -> None:
        """Test request creation."""

        async def dummy_func() -> str:
            return "result"

        request = QueuedRequest(
            request_id="req-123",
            func=dummy_func,
            args=(),
            kwargs={},
            priority=QueuePriority.NORMAL,
            timestamp=1000.0,
        )

        assert request.request_id == "req-123"
        assert request.priority == QueuePriority.NORMAL
        assert request.status == RequestStatus.PENDING
        assert request.result is None

    def test_comparison_by_priority(self) -> None:
        """Test requests are compared by priority."""
        req_low = QueuedRequest(
            request_id="1",
            func=lambda: None,
            args=(),
            kwargs={},
            priority=QueuePriority.LOW,
            timestamp=1000.0,
        )
        req_high = QueuedRequest(
            request_id="2",
            func=lambda: None,
            args=(),
            kwargs={},
            priority=QueuePriority.HIGH,
            timestamp=1000.0,
        )

        # Higher priority should come first (< returns True for higher priority)
        assert req_high < req_low

    def test_comparison_by_timestamp_same_priority(self) -> None:
        """Test requests with same priority compared by timestamp."""
        req_older = QueuedRequest(
            request_id="1",
            func=lambda: None,
            args=(),
            kwargs={},
            priority=QueuePriority.NORMAL,
            timestamp=1000.0,
        )
        req_newer = QueuedRequest(
            request_id="2",
            func=lambda: None,
            args=(),
            kwargs={},
            priority=QueuePriority.NORMAL,
            timestamp=2000.0,
        )

        # Older should come first
        assert req_older < req_newer


class TestRequestQueue:
    """Tests for RequestQueue class."""

    def test_creation(self) -> None:
        """Test queue creation."""
        queue = RequestQueue(max_concurrent=5, max_queue_size=100, worker_count=3)

        assert queue.max_concurrent == 5
        assert queue.max_queue_size == 100
        assert queue.worker_count == 3
        assert queue.running is False

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Test starting and stopping queue."""
        queue = RequestQueue(worker_count=2)

        await queue.start()
        assert queue.running is True
        assert len(queue.workers) == 2

        await queue.stop()
        assert queue.running is False

    @pytest.mark.asyncio
    async def test_submit_request(self) -> None:
        """Test submitting a request."""
        queue = RequestQueue()

        async def dummy_task() -> str:
            return "result"

        request_id = await queue.submit(dummy_task, priority=QueuePriority.NORMAL)

        assert request_id is not None
        assert request_id in queue.requests
        assert queue.requests[request_id].status == RequestStatus.PENDING

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_submit_request_queue_full(self) -> None:
        """Test submitting when queue is full raises error."""
        queue = RequestQueue(max_queue_size=1)

        async def dummy_task() -> None:
            await asyncio.sleep(10)

        await queue.submit(dummy_task)

        with pytest.raises(RuntimeError, match="Queue is full"):
            await queue.submit(dummy_task)

    @pytest.mark.asyncio
    async def test_process_request(self) -> None:
        """Test processing a request."""
        queue = RequestQueue(max_concurrent=1, worker_count=1)
        await queue.start()

        result_value = "processed"

        async def test_task() -> str:
            return result_value

        try:
            request_id = await queue.submit(test_task)

            # Wait for processing
            success, result = await queue.get_result(request_id, wait=True, timeout=5.0)

            assert success is True
            assert result == result_value
            assert queue.requests[request_id].status == RequestStatus.COMPLETED
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_get_result_not_found(self) -> None:
        """Test getting result for unknown request."""
        queue = RequestQueue()

        success, result = await queue.get_result("unknown-id")

        assert success is False
        assert "not found" in str(result).lower()

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        """Test getting request status."""
        queue = RequestQueue()

        async def dummy_task() -> str:
            return "result"

        request_id = await queue.submit(dummy_task)

        status = await queue.get_status(request_id)

        assert status["status"] == "pending"
        assert "created_at" in status

    @pytest.mark.asyncio
    async def test_get_status_not_found(self) -> None:
        """Test getting status for unknown request."""
        queue = RequestQueue()

        status = await queue.get_status("unknown-id")

        assert status["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_process_sync_function(self) -> None:
        """Test processing synchronous function."""
        queue = RequestQueue(worker_count=1)
        await queue.start()

        def sync_task() -> str:
            return "sync result"

        try:
            request_id = await queue.submit(sync_task)
            success, result = await queue.get_result(request_id, wait=True, timeout=5.0)

            assert success is True
            assert result == "sync result"
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_request_timeout(self) -> None:
        """Test request timeout handling."""
        queue = RequestQueue(worker_count=1)
        await queue.start()

        async def slow_task() -> str:
            await asyncio.sleep(10)
            return "result"

        try:
            request_id = await queue.submit(slow_task, timeout=0.1)
            success, _result = await queue.get_result(request_id, wait=True, timeout=5.0)

            assert success is False
            assert queue.requests[request_id].status == RequestStatus.TIMEOUT
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_request_failure(self) -> None:
        """Test request failure handling."""
        queue = RequestQueue(worker_count=1)
        await queue.start()

        async def failing_task() -> None:
            raise ValueError("Task failed")

        try:
            request_id = await queue.submit(failing_task)
            success, _result = await queue.get_result(request_id, wait=True, timeout=5.0)

            assert success is False
            assert queue.requests[request_id].status == RequestStatus.FAILED
        finally:
            await queue.stop()
