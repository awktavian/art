"""Tests for DLQ recovery background job."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from kagami.core.receipts.dlq_recovery import (
    DLQ_KEY,
    process_dlq_loop,
    start_dlq_recovery_background,
)


@pytest.fixture
def sample_receipts():
    """Sample receipts for DLQ testing."""
    return [
        {
            "correlation_id": f"dlq-test-{i}",
            "phase": "EXECUTE",
            "event": {"name": "test.event"},
        }
        for i in range(3)
    ]


@pytest.mark.asyncio
async def test_dlq_recovery_processes_items(sample_receipts: Any, monkeypatch: Any) -> None:
    """Test DLQ recovery processes items successfully."""
    # Mock Redis client
    mock_redis = MagicMock()
    mock_redis.rpop.side_effect = [
        json.dumps(sample_receipts[0]),
        json.dumps(sample_receipts[1]),
        None,  # DLQ empty
    ]

    def mock_get_client(**kwargs) -> str:
        return mock_redis

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    # Mock DB persistence (success) - async function
    call_count = 0

    async def mock_db_persist(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return True

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_db_persist,
    )

    # Mock sleep to speed up test
    sleep_calls = 0

    async def mock_sleep(seconds: Any) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    try:
        await process_dlq_loop()
    except asyncio.CancelledError:
        pass

    # Verify items were processed
    assert call_count == 2
    mock_redis.lpush.assert_not_called()  # No re-queue on success


@pytest.mark.asyncio
async def test_dlq_recovery_requeues_on_failure(sample_receipts: Any, monkeypatch: Any) -> None:
    """Test DLQ recovery re-queues items on persistence failure."""
    receipt_json = json.dumps(sample_receipts[0])

    # Mock Redis client
    mock_redis = MagicMock()
    mock_redis.rpop.side_effect = [
        receipt_json,
        None,  # Stop after first item
    ]

    def mock_get_client(**kwargs) -> str:
        return mock_redis

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    # Mock DB persistence (failure) - async function
    async def mock_db_persist(*args, **kwargs):
        return False

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_db_persist,
    )

    # Mock sleep: first call completes (recovery interval), second raises to exit loop
    sleep_counter = 0

    async def mock_sleep(seconds: Any) -> None:
        nonlocal sleep_counter
        sleep_counter += 1
        if sleep_counter > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    try:
        await process_dlq_loop()
    except asyncio.CancelledError:
        pass

    # Verify item was re-queued
    mock_redis.lpush.assert_called_once_with(DLQ_KEY, receipt_json)


@pytest.mark.asyncio
async def test_dlq_recovery_handles_invalid_json(monkeypatch: Any) -> None:
    """Test DLQ recovery discards invalid JSON."""
    # Mock Redis client with invalid JSON
    mock_redis = MagicMock()
    mock_redis.rpop.side_effect = [
        "invalid{json",  # Invalid JSON (should be discarded)
        json.dumps({"correlation_id": "valid"}),  # Valid receipt
        None,  # DLQ empty
    ]

    def mock_get_client(**kwargs) -> str:
        return mock_redis

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    # Mock DB persistence (success) - async function
    call_count = 0

    async def mock_db_persist(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return True

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_db_persist,
    )

    # Mock sleep: first call completes (recovery interval), second raises to exit loop
    sleep_counter = 0

    async def mock_sleep(seconds: Any) -> None:
        nonlocal sleep_counter
        sleep_counter += 1
        if sleep_counter > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    try:
        await process_dlq_loop()
    except asyncio.CancelledError:
        pass

    # Verify only valid receipt was processed
    assert call_count == 1
    # Invalid JSON should not be re-queued
    mock_redis.lpush.assert_not_called()


@pytest.mark.asyncio
async def test_dlq_recovery_stops_on_exception(sample_receipts: Any, monkeypatch: Any) -> None:
    """Test DLQ recovery stops batch processing on exception."""
    receipt_json = json.dumps(sample_receipts[0])

    # Mock Redis client
    mock_redis = MagicMock()
    mock_redis.rpop.side_effect = [
        receipt_json,
        None,  # Should not reach here
    ]

    def mock_get_client(**kwargs) -> str:
        return mock_redis

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    # Mock DB persistence (exception) - async function
    async def mock_db_persist(*args, **kwargs):
        raise Exception("DB connection lost")

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_db_persist,
    )

    # Mock sleep: first call completes (recovery interval), second raises to exit loop
    sleep_counter = 0

    async def mock_sleep(seconds: Any) -> None:
        nonlocal sleep_counter
        sleep_counter += 1
        if sleep_counter > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    try:
        await process_dlq_loop()
    except asyncio.CancelledError:
        pass

    # Verify item was re-queued and processing stopped
    mock_redis.lpush.assert_called_once_with(DLQ_KEY, receipt_json)
    assert mock_redis.rpop.call_count == 1  # Only one attempt


@pytest.mark.asyncio
async def test_dlq_recovery_continues_after_loop_error(monkeypatch: Any) -> None:
    """Test DLQ recovery loop continues after error."""
    # Mock Redis client
    mock_redis = MagicMock()

    def mock_get_client(**kwargs) -> str:
        return mock_redis

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    # Mock rpop to raise error on first call, then return None (empty DLQ)
    mock_redis.rpop.side_effect = [
        Exception("Redis timeout"),  # First rpop in first iteration fails
    ]

    # Mock sleep with controlled timing
    sleep_counter = 0

    async def controlled_sleep(seconds: Any) -> None:
        nonlocal sleep_counter
        sleep_counter += 1
        # First sleep: recovery interval (normal)
        # After first iteration has rpop error, loop catches it and sleeps 10s (error backoff)
        # On second loop iteration, we exit
        if sleep_counter >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr("asyncio.sleep", controlled_sleep)

    try:
        await process_dlq_loop()
    except asyncio.CancelledError:
        pass

    # Verify rpop was called (once from first iteration where it raised)
    assert mock_redis.rpop.call_count >= 1


def test_start_dlq_recovery_background(monkeypatch: Any) -> None:
    """Test starting DLQ recovery as background task."""
    mock_create_task = Mock()
    monkeypatch.setattr("asyncio.create_task", mock_create_task)

    start_dlq_recovery_background()

    mock_create_task.assert_called_once()


def test_start_dlq_recovery_background_no_event_loop(monkeypatch: Any) -> None:
    """Test starting DLQ recovery without event loop raises error."""
    monkeypatch.setattr(
        "asyncio.create_task", Mock(side_effect=RuntimeError("no running event loop"))
    )

    with pytest.raises(RuntimeError, match="no running event loop"):
        start_dlq_recovery_background()
