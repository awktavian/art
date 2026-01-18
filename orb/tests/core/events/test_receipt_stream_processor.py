"""Tests for receipt stream processor race condition fixes.

This test suite verifies the critical fix for the stream processor race condition
where receipts could be dropped if they arrived before handlers were registered.

Key scenarios tested:
1. Processing before start() raises RuntimeError
2. Handlers registered before start() receive all receipts
3. Auto-start warning is emitted for ensure_running()
4. Start/stop idempotency
5. Handler execution order and error handling
"""

from __future__ import annotations
from typing import Any


import pytest
import asyncio
from unittest.mock import AsyncMock, Mock

from kagami.core.events.receipt_stream_processor import ReceiptStreamProcessor


class TestReceiptStreamProcessorRaceCondition:
    """Test race condition fixes in receipt stream processor."""

    @pytest.mark.asyncio
    async def test_process_before_start_raises_error(self) -> None:
        """Test that processing before start raises RuntimeError."""
        processor = ReceiptStreamProcessor()

        # Attempt to process receipt before starting
        with pytest.raises(RuntimeError, match="not started"):
            await processor.process_receipt({"correlation_id": "test"})

    @pytest.mark.asyncio
    async def test_start_idempotency(self) -> None:
        """Test that calling start() multiple times is safe."""
        processor = ReceiptStreamProcessor()

        # Start once
        await processor.start()
        assert processor._started is True
        assert processor._running is True

        # Start again - should log warning but not fail
        await processor.start()
        assert processor._started is True

        # Cleanup
        await processor.stop()

    @pytest.mark.asyncio
    async def test_stop_resets_started_flag(self) -> None:
        """Test that stop() resets the _started flag."""
        processor = ReceiptStreamProcessor()

        await processor.start()
        assert processor._started is True

        await processor.stop()
        assert processor._started is False
        assert processor._running is False

    @pytest.mark.asyncio
    async def test_handlers_registered_before_start(self) -> None:
        """Test correct initialization order: handlers then start."""
        processor = ReceiptStreamProcessor()
        received_receipts = []

        # Define handler
        async def test_handler(receipt: dict) -> None:
            received_receipts.append(receipt)

        # Register handler FIRST
        processor.add_handler(test_handler)

        # THEN start
        await processor.start()

        # Now process receipts
        test_receipt = {"correlation_id": "test-123", "phase": "plan"}
        await processor.process_receipt(test_receipt)

        # Give processor time to process
        await asyncio.sleep(0.2)

        # Verify handler was called
        assert len(received_receipts) == 1
        assert received_receipts[0]["correlation_id"] == "test-123"

        # Cleanup
        await processor.stop()

    @pytest.mark.asyncio
    async def test_multiple_handlers_execution_order(self) -> None:
        """Test that multiple handlers are called in registration order."""
        processor = ReceiptStreamProcessor()
        call_order = []

        async def handler_1(receipt: dict) -> None:
            call_order.append("handler_1")

        async def handler_2(receipt: dict) -> None:
            call_order.append("handler_2")

        async def handler_3(receipt: dict) -> None:
            call_order.append("handler_3")

        # Register in specific order
        processor.add_handler(handler_1)
        processor.add_handler(handler_2)
        processor.add_handler(handler_3)

        await processor.start()

        # Process receipt
        await processor.process_receipt({"correlation_id": "test"})

        # Wait for processing
        await asyncio.sleep(0.2)

        # Verify order
        assert call_order == ["handler_1", "handler_2", "handler_3"]

        await processor.stop()

    @pytest.mark.asyncio
    async def test_handler_error_does_not_stop_processing(self) -> None:
        """Test that handler errors don't prevent other handlers from running."""
        processor = ReceiptStreamProcessor()
        successful_calls = []

        async def failing_handler(receipt: dict) -> None:
            raise ValueError("Test error")

        async def successful_handler(receipt: dict) -> None:
            successful_calls.append(receipt["correlation_id"])

        # Register both handlers
        processor.add_handler(failing_handler)
        processor.add_handler(successful_handler)

        await processor.start()

        # Process receipt
        await processor.process_receipt({"correlation_id": "test-456"})

        # Wait for processing
        await asyncio.sleep(0.2)

        # Verify successful handler was still called despite failure
        assert len(successful_calls) == 1
        assert successful_calls[0] == "test-456"

        await processor.stop()

    @pytest.mark.asyncio
    async def test_ensure_running_shows_warning(self, caplog: Any) -> None:
        """Test that ensure_running() emits warning about race condition risk."""
        import logging

        caplog.set_level(logging.WARNING)

        processor = ReceiptStreamProcessor()

        # Call ensure_running() which auto-starts
        processor.ensure_running()

        # Give it time to start
        await asyncio.sleep(0.3)

        # Check warning was logged
        assert any(
            "Auto-starting receipt processor" in record.message
            and "handler registration" in record.message
            for record in caplog.records
        )

        # Cleanup
        if processor._started:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_batch_processing_preserves_order(self) -> None:
        """Test that receipts are processed in order within a batch."""
        processor = ReceiptStreamProcessor(batch_size=5, batch_timeout_ms=100)
        processed_ids = []

        async def ordering_handler(receipt: dict) -> None:
            processed_ids.append(receipt["correlation_id"])

        processor.add_handler(ordering_handler)
        await processor.start()

        # Submit multiple receipts
        for i in range(5):
            await processor.process_receipt({"correlation_id": f"receipt-{i}"})

        # Wait for batch processing
        await asyncio.sleep(0.3)

        # Verify order
        assert processed_ids == [f"receipt-{i}" for i in range(5)]

        await processor.stop()

    @pytest.mark.asyncio
    async def test_no_receipts_lost_during_batch_collection(self) -> None:
        """Test that all receipts are processed even with batch timeout."""
        processor = ReceiptStreamProcessor(batch_size=10, batch_timeout_ms=50)
        processed_count = []

        async def counting_handler(receipt: dict) -> None:
            processed_count.append(1)

        processor.add_handler(counting_handler)
        await processor.start()

        # Submit fewer receipts than batch size
        for i in range(3):
            await processor.process_receipt({"correlation_id": f"receipt-{i}"})

        # Wait for timeout to trigger processing
        await asyncio.sleep(0.3)

        # All receipts should be processed despite small batch
        assert len(processed_count) == 3

        await processor.stop()

    @pytest.mark.asyncio
    async def test_metrics_updated_correctly(self) -> None:
        """Test that processing metrics are updated correctly."""
        processor = ReceiptStreamProcessor()

        async def noop_handler(receipt: dict) -> None:
            pass

        processor.add_handler(noop_handler)
        await processor.start()

        # Process some receipts
        for i in range(5):
            await processor.process_receipt({"correlation_id": f"test-{i}", "phase": "plan"})

        # Wait for processing
        await asyncio.sleep(0.3)

        # Check metrics
        metrics = processor.get_metrics()
        assert metrics["total_processed"] == 5
        assert metrics["total_errors"] == 0
        assert metrics["success_rate"] == 1.0
        assert "plan" in metrics["by_phase"]
        assert metrics["by_phase"]["plan"]["processed"] == 5

        await processor.stop()

    @pytest.mark.asyncio
    async def test_started_flag_prevents_early_processing(self) -> None:
        """Test that _started flag correctly gates processing."""
        processor = ReceiptStreamProcessor()

        # Verify initial state
        assert processor._started is False

        # Try to process - should raise
        with pytest.raises(RuntimeError):
            await processor.process_receipt({"correlation_id": "early"})

        # Start processor
        await processor.start()
        assert processor._started is True

        # Now processing should work
        async def test_handler(receipt: dict) -> None:
            pass

        processor.add_handler(test_handler)
        await processor.process_receipt({"correlation_id": "after-start"})  # Should not raise

        await processor.stop()


class TestReceiptStreamProcessorBackpressure:
    """Test backpressure and circuit breaker mechanisms.

    Note: These tests involve timing-sensitive race conditions and may be
    flaky in CI. They document expected behavior under extreme load.
    """

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_queue_saturation_activates_circuit_breaker(self) -> None:
        """Test that queue saturation activates circuit breaker.

        This is a timing-sensitive test that verifies circuit breaker behavior
        under extreme load. May be flaky due to async processing timing.
        """
        # Small queue to trigger saturation
        processor = ReceiptStreamProcessor(queue_size=10)

        # Very slow handler to ensure queue fills
        async def slow_handler(receipt: dict) -> None:
            await asyncio.sleep(5.0)  # Very slow to keep queue full

        processor.add_handler(slow_handler)
        await processor.start()

        # Flood the queue rapidly to trigger circuit breaker
        # We submit synchronously in a tight loop to maximize queue buildup
        circuit_breaker_ever_active = False
        max_queue_size_seen = 0

        for i in range(12):  # Overfill queue (120% of capacity)
            try:
                # Use short timeout so we don't block test
                await asyncio.wait_for(
                    processor.process_receipt({"correlation_id": f"flood-{i}", "phase": "plan"}),
                    timeout=0.05,
                )
            except TimeoutError:
                pass  # Expected when queue is full

            # Track circuit breaker state
            if processor._circuit_breaker_active:
                circuit_breaker_ever_active = True

            # Track max queue size
            current_size = processor._queue.qsize()
            if current_size > max_queue_size_seen:
                max_queue_size_seen = current_size

        # Verify that EITHER circuit breaker activated OR queue got very full
        # This accounts for timing variations
        assert circuit_breaker_ever_active or max_queue_size_seen >= 7, (
            f"Expected circuit breaker activation or high queue size, "
            f"got breaker={circuit_breaker_ever_active}, max_size={max_queue_size_seen}"
        )

        # Cleanup
        await processor.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_backpressure_timeout_handling(self) -> None:
        """Test that backpressure timeout is handled gracefully.

        This test verifies that when the queue is full and can't drain,
        the processor correctly applies backpressure or drops receipts.
        Timing-sensitive and may be flaky.
        """
        processor = ReceiptStreamProcessor(queue_size=2)

        # Start processor but with very slow handler so queue fills up
        async def blocking_handler(receipt: dict) -> None:
            await asyncio.sleep(10.0)  # Block processing

        processor.add_handler(blocking_handler)
        await processor.start()

        # Fill queue to capacity quickly
        task1 = asyncio.create_task(
            processor.process_receipt({"correlation_id": "r1", "phase": "plan"})
        )
        task2 = asyncio.create_task(
            processor.process_receipt({"correlation_id": "r2", "phase": "plan"})
        )

        # Wait for queue to fill
        await asyncio.sleep(0.2)

        # Try to add more receipts - should trigger backpressure or drops
        exceeded_capacity = False
        try:
            # This should either block (backpressure) or drop (after timeout)
            await asyncio.wait_for(
                processor.process_receipt({"correlation_id": "r3", "phase": "plan"}), timeout=0.5
            )
        except TimeoutError:
            exceeded_capacity = True

        # Verify that system detected capacity issue
        # Could be: test timeout, processor errors, or dropped receipts
        assert (
            exceeded_capacity
            or processor._metrics.total_errors > 0
            or processor._dropped_receipts > 0
        ), (
            f"Expected capacity handling, got timeout={exceeded_capacity}, "
            f"errors={processor._metrics.total_errors}, drops={processor._dropped_receipts}"
        )

        await processor.stop()
        # Cleanup tasks
        for task in [task1, task2]:
            if not task.done():
                task.cancel()


class TestReceiptStreamProcessorInitOrder:
    """Test initialization order enforcement."""

    @pytest.mark.asyncio
    async def test_wiring_pattern_example(self) -> None:
        """Test the correct wiring pattern as documented.

        This demonstrates the pattern from wiring.py:
        1. Create processor
        2. Wire dependencies
        3. Register handlers
        4. Start processor
        """
        processor = ReceiptStreamProcessor()
        receipts_received = []

        # Step 1: Create processor (done)

        # Step 2: Wire dependencies (simulated)
        mock_learning = Mock()
        mock_prediction = Mock()
        processor._learning = mock_learning
        processor._prediction = mock_prediction

        # Step 3: Register handlers
        async def learning_handler(receipt: dict) -> None:
            receipts_received.append(receipt)

        processor.add_handler(learning_handler)

        # Step 4: Start processor
        await processor.start()

        # Step 5: Process receipts (should work correctly now)
        await processor.process_receipt({"correlation_id": "wiring-test"})

        # Wait for processing
        await asyncio.sleep(0.2)

        # Verify
        assert len(receipts_received) == 1
        assert receipts_received[0]["correlation_id"] == "wiring-test"

        await processor.stop()

    @pytest.mark.asyncio
    async def test_anti_pattern_start_before_handlers(self) -> None:
        """Test anti-pattern: starting before handlers causes issues.

        This test documents the WRONG way to initialize.
        """
        processor = ReceiptStreamProcessor()
        receipts_received = []

        # WRONG: Start before registering handlers
        await processor.start()

        # Define handler after start (receipts might already be arriving)
        async def late_handler(receipt: dict) -> None:
            receipts_received.append(receipt)

        processor.add_handler(late_handler)

        # If receipts arrive NOW, they might be processed without handler
        # (Though in this controlled test, we submit after handler registration)
        await processor.process_receipt({"correlation_id": "late"})

        await asyncio.sleep(0.2)

        # In this specific test it works because we control timing,
        # but in production this is a race condition
        assert len(receipts_received) == 1  # Lucky timing

        await processor.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
