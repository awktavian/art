"""Tests for receipt persistence optimization (Phase 1).

Tests the consolidated storage backend (6→5 backends):
- JSONL guard raises error in production mode
- DLQ fallback when DB unavailable in production
- Retry logic with exponential backoff (async version)
- Test mode uses JSONL fallback
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from kagami.core.receipts.persistence_helpers import (
    _persist_to_dlq,
    persist_to_storage_async,
)


@pytest.fixture
def sample_receipt():
    """Sample receipt for testing."""
    return {
        "correlation_id": "test-123",
        "phase": "EXECUTE",
        "event": {"name": "test.event"},
        "intent": {"action": "test_action"},
        "timestamp": time.time() * 1000,
    }


def test_persist_to_dlq_success(sample_receipt: Any, monkeypatch: Any) -> None:
    """Test successful DLQ write."""
    mock_redis = MagicMock()

    def mock_get_client(**kwargs) -> str:
        return mock_redis

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    result = _persist_to_dlq(sample_receipt)

    from kagami.core.caching.redis_keys import RedisKeys

    assert result is True
    mock_redis.lpush.assert_called_once()
    args = mock_redis.lpush.call_args[0]
    assert args[0] == RedisKeys.dlq()
    # Verify JSON is valid
    receipt_json = args[1]
    parsed = json.loads(receipt_json)
    assert parsed["correlation_id"] == "test-123"


def test_persist_to_dlq_redis_failure(sample_receipt: Any, monkeypatch: Any) -> None:
    """Test DLQ write when Redis unavailable."""

    def mock_get_client(**kwargs) -> str:
        raise Exception("Redis connection failed")

    monkeypatch.setattr(
        "kagami.core.caching.redis.factory.RedisClientFactory.get_client",
        mock_get_client,
    )

    result = _persist_to_dlq(sample_receipt)

    assert result is False


@pytest.mark.asyncio
async def test_persist_to_storage_async_production_dlq_fallback(
    sample_receipt: Any, monkeypatch: Any
) -> None:
    """Test production mode uses DLQ on DB failure."""
    # Mock production mode
    monkeypatch.setattr("kagami.core.boot_mode.is_test_mode", lambda: False)

    # Mock DB failure
    async def mock_retry_async(*args, **kwargs):
        return False

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_retry_async,
    )

    # Mock DLQ
    mock_dlq = Mock()
    mock_alert = Mock()
    monkeypatch.setattr("kagami.core.receipts.persistence_helpers._persist_to_dlq", mock_dlq)
    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._send_pagerduty_alert", mock_alert
    )

    result = await persist_to_storage_async(sample_receipt)

    assert result is False
    mock_dlq.assert_called_once_with(sample_receipt)
    mock_alert.assert_called_once_with(sample_receipt)


@pytest.mark.asyncio
async def test_persist_to_storage_async_test_mode_jsonl_fallback(
    sample_receipt: Any, monkeypatch: Any
) -> None:
    """Test test mode uses JSONL on DB failure."""
    # Mock test mode
    monkeypatch.setattr("kagami.core.boot_mode.is_test_mode", lambda: True)

    # Mock DB failure
    async def mock_retry_async(*args, **kwargs):
        return False

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_retry_async,
    )

    # Mock JSONL fallback
    mock_jsonl = Mock(return_value=True)
    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_to_jsonl_fallback",
        mock_jsonl,
    )

    result = await persist_to_storage_async(sample_receipt)

    assert result is True
    mock_jsonl.assert_called_once_with(sample_receipt)


@pytest.mark.asyncio
async def test_persist_to_storage_async_db_success_no_fallback(
    sample_receipt: Any, monkeypatch: Any
) -> None:
    """Test successful DB persistence skips fallback."""
    monkeypatch.setattr("kagami.core.boot_mode.is_test_mode", lambda: False)

    # Mock successful DB write
    async def mock_retry_async(*args, **kwargs):
        return True

    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_receipt_db_with_retry_async",
        mock_retry_async,
    )

    # Mock fallback (should not be called)
    mock_dlq = Mock()
    mock_jsonl = Mock()
    monkeypatch.setattr("kagami.core.receipts.persistence_helpers._persist_to_dlq", mock_dlq)
    monkeypatch.setattr(
        "kagami.core.receipts.persistence_helpers._persist_to_jsonl_fallback", mock_jsonl
    )

    result = await persist_to_storage_async(sample_receipt)

    assert result is True
    mock_dlq.assert_not_called()
    mock_jsonl.assert_not_called()


def test_jsonl_storage_raises_in_production(sample_receipt: Any, monkeypatch: Any) -> None:
    """Test JSONL storage guard raises error in production."""
    from kagami.core.receipts.service import JSONLReceiptStorage

    # Mock production mode
    monkeypatch.setattr("kagami.core.boot_mode.is_test_mode", lambda: False)

    storage = JSONLReceiptStorage()

    with pytest.raises(RuntimeError, match="JSONL storage is disabled in production"):
        storage.store(sample_receipt)


def test_jsonl_storage_allowed_in_test_mode(
    sample_receipt: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    """Test JSONL storage works in test mode."""
    from kagami.core.receipts.service import JSONLReceiptStorage

    # Mock test mode
    monkeypatch.setattr("kagami.core.boot_mode.is_test_mode", lambda: True)

    # Mock JSONL writer (correct import path)
    mock_writer = Mock()
    monkeypatch.setattr("kagami.utils.jsonl_writer.append_jsonl_locked", mock_writer)

    storage = JSONLReceiptStorage(file_path=str(tmp_path / "test.jsonl"))
    result = storage.store(sample_receipt)

    assert result is True
    mock_writer.assert_called_once()
