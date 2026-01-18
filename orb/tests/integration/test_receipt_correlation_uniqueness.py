"""Tests for correlation ID uniqueness constraint on receipts.

Tests the database-level uniqueness constraint on (correlation_id, phase, ts)
and the repository's handling of duplicate receipt attempts.

Created: December 16, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.tier2,  # Integration tests with external services
]

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from kagami.core.database.models import Receipt
from kagami.core.receipts.facade import UnifiedReceiptFacade as URF
from kagami.core.storage.receipt_repository import ReceiptRepository


class TestCorrelationIDValidation:
    """Test correlation_id validation in UnifiedReceiptFacade."""

    def test_emit_with_valid_correlation_id(self) -> None:
        """Test emission with valid correlation_id succeeds."""
        correlation_id = URF.generate_correlation_id()
        receipt = URF.emit(
            correlation_id=correlation_id,
            event_name="test.event",
            action="test_action",
        )
        assert receipt["correlation_id"] == correlation_id

    def test_emit_with_empty_correlation_id_raises_error(self) -> None:
        """Test emission with empty correlation_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid correlation_id"):
            URF.emit(
                correlation_id="",
                event_name="test.event",
            )

    def test_emit_with_none_correlation_id_raises_error(self) -> None:
        """Test emission with None correlation_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid correlation_id"):
            URF.emit(
                correlation_id=None,  # type: ignore
                event_name="test.event",
            )

    def test_emit_with_whitespace_correlation_id_raises_error(self) -> None:
        """Test emission with whitespace-only correlation_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid correlation_id"):
            URF.emit(
                correlation_id="   ",
                event_name="test.event",
            )

    def test_emit_with_non_string_correlation_id_raises_error(self) -> None:
        """Test emission with non-string correlation_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid correlation_id"):
            URF.emit(
                correlation_id=12345,  # type: ignore
                event_name="test.event",
            )


@pytest.mark.asyncio
class TestReceiptDuplicateHandling:
    """Test receipt repository's handling of duplicate receipts."""

    async def test_save_receipt_succeeds_with_unique_correlation(self) -> None:
        """Test saving receipt with unique correlation_id succeeds."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        receipt = Receipt(
            id=uuid4(),
            correlation_id="test-123",
            phase="PLAN",
            ts=datetime.utcnow(),
            intent={},
        )

        # Mock the set method to succeed
        repo.set = AsyncMock(return_value=None)  # type: ignore[method-assign]
        repo._index_in_weaviate = AsyncMock()  # type: ignore[method-assign]

        # Execute
        result = await repo.save_receipt(receipt)

        # Assert
        assert result == receipt
        repo.set.assert_called_once()

    async def test_save_receipt_handles_duplicate_gracefully(self) -> None:
        """Test duplicate receipt (same correlation+phase+ts) is handled gracefully."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        correlation_id = "test-456"
        phase = "EXECUTE"
        ts = datetime.utcnow()

        new_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=ts,
            intent={},
        )

        existing_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=ts,
            intent={"existing": True},
        )

        # Mock set to raise IntegrityError (simulating duplicate constraint violation)
        integrity_error = IntegrityError(
            'duplicate key value violates unique constraint "idx_receipts_correlation_uniqueness"',
            params=None,
            orig=Exception("duplicate key"),
        )
        repo.set = AsyncMock(side_effect=integrity_error)  # type: ignore[method-assign]

        # Mock get_by_correlation_id to return existing receipt
        repo.get_by_correlation_id = AsyncMock(return_value=[existing_receipt])  # type: ignore[method-assign]

        # Execute
        result = await repo.save_receipt(new_receipt)

        # Assert - should return existing receipt, not raise error
        assert result == existing_receipt
        assert result.id == existing_receipt.id
        repo.get_by_correlation_id.assert_called_once_with(correlation_id)

    async def test_save_receipt_with_different_phase_succeeds(self) -> None:
        """Test receipts with same correlation_id but different phase succeed."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        correlation_id = "test-789"
        ts = datetime.utcnow()

        plan_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase="PLAN",
            ts=ts,
            intent={},
        )

        execute_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase="EXECUTE",
            ts=ts,
            intent={},
        )

        # Mock set to succeed for both
        repo.set = AsyncMock()  # type: ignore[method-assign]
        repo._index_in_weaviate = AsyncMock()  # type: ignore[method-assign]

        # Execute - save both receipts
        result1 = await repo.save_receipt(plan_receipt)
        result2 = await repo.save_receipt(execute_receipt)

        # Assert - both should succeed
        assert result1 == plan_receipt
        assert result2 == execute_receipt
        assert repo.set.call_count == 2

    async def test_save_receipt_with_different_timestamp_succeeds(self) -> None:
        """Test receipts with same correlation_id+phase but different ts succeed."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        correlation_id = "test-abc"
        phase = "VERIFY"

        receipt1 = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=datetime.utcnow(),
            intent={},
        )

        receipt2 = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=datetime.utcnow() + timedelta(seconds=1),
            intent={},
        )

        # Mock set to succeed for both
        repo.set = AsyncMock()  # type: ignore[method-assign]
        repo._index_in_weaviate = AsyncMock()  # type: ignore[method-assign]

        # Execute
        result1 = await repo.save_receipt(receipt1)
        result2 = await repo.save_receipt(receipt2)

        # Assert
        assert result1 == receipt1
        assert result2 == receipt2
        assert repo.set.call_count == 2

    async def test_save_receipt_reraises_non_duplicate_integrity_error(self) -> None:
        """Test IntegrityError for non-duplicate violations is re-raised."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        receipt = Receipt(
            id=uuid4(),
            correlation_id="test-xyz",
            phase="PLAN",
            ts=datetime.utcnow(),
            intent={},
        )

        # Mock set to raise different IntegrityError
        other_error = IntegrityError(
            "foreign key violation",
            params=None,
            orig=Exception("fk error"),
        )
        repo.set = AsyncMock(side_effect=other_error)  # type: ignore[method-assign]

        # Execute & Assert - should re-raise
        with pytest.raises(IntegrityError, match="foreign key violation"):
            await repo.save_receipt(receipt)

    async def test_duplicate_receipt_logs_warning(self) -> None:
        """Test duplicate receipt logs warning message."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        correlation_id = "test-warn"
        phase = "EXECUTE"
        ts = datetime.utcnow()

        new_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=ts,
            intent={},
        )

        existing_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=ts,
            intent={},
        )

        # Mock set to raise IntegrityError
        integrity_error = IntegrityError(
            "duplicate key",
            params=None,
            orig=Exception("duplicate"),
        )
        repo.set = AsyncMock(side_effect=integrity_error)  # type: ignore[method-assign]
        repo.get_by_correlation_id = AsyncMock(return_value=[existing_receipt])  # type: ignore[method-assign]

        # Execute with logging capture
        with patch("kagami.core.storage.receipt_repository.logger") as mock_logger:
            await repo.save_receipt(new_receipt)
            # Assert warning was logged
            mock_logger.warning.assert_called_once()
            assert "Duplicate receipt detected" in str(mock_logger.warning.call_args)


@pytest.mark.asyncio
class TestReceiptUniquenessEndToEnd:
    """End-to-end tests for receipt uniqueness constraint."""

    async def test_plan_execute_verify_cycle_with_same_correlation_id(self) -> None:
        """Test full PLAN-EXECUTE-VERIFY cycle with same correlation_id succeeds."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        correlation_id = URF.generate_correlation_id()
        base_ts = datetime.utcnow()

        # Create PLAN, EXECUTE, VERIFY receipts
        plan_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase="PLAN",
            ts=base_ts,
            intent={},
        )

        execute_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase="EXECUTE",
            ts=base_ts + timedelta(milliseconds=100),
            intent={},
        )

        verify_receipt = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase="VERIFY",
            ts=base_ts + timedelta(milliseconds=200),
            intent={},
        )

        # Mock set to succeed for all
        repo.set = AsyncMock()  # type: ignore[method-assign]
        repo._index_in_weaviate = AsyncMock()  # type: ignore[method-assign]

        # Execute
        result_plan = await repo.save_receipt(plan_receipt)
        result_execute = await repo.save_receipt(execute_receipt)
        result_verify = await repo.save_receipt(verify_receipt)

        # Assert all three succeed
        assert result_plan == plan_receipt
        assert result_execute == execute_receipt
        assert result_verify == verify_receipt
        assert repo.set.call_count == 3

    async def test_concurrent_duplicate_insert_returns_same_receipt(self) -> None:
        """Test concurrent inserts of same receipt return consistent result."""
        # Setup
        db_session = AsyncMock()
        repo = ReceiptRepository(db_session=db_session)

        correlation_id = "concurrent-test"
        phase = "PLAN"
        ts = datetime.utcnow()

        # First receipt succeeds
        receipt1 = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=ts,
            intent={"first": True},
        )

        # Second receipt (concurrent) gets IntegrityError
        receipt2 = Receipt(
            id=uuid4(),
            correlation_id=correlation_id,
            phase=phase,
            ts=ts,
            intent={"second": True},
        )

        # Mock: first succeeds, second raises IntegrityError
        call_count = 0

        async def mock_set(key: Any, value: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # First succeeds
            else:
                raise IntegrityError(
                    "idx_receipts_correlation_uniqueness",
                    params=None,
                    orig=Exception("duplicate"),
                )

        repo.set = AsyncMock(side_effect=mock_set)  # type: ignore[method-assign]
        repo.get_by_correlation_id = AsyncMock(return_value=[receipt1])  # type: ignore[method-assign]
        repo._index_in_weaviate = AsyncMock()  # type: ignore[method-assign]

        # Execute
        result1 = await repo.save_receipt(receipt1)
        result2 = await repo.save_receipt(receipt2)

        # Assert - both return the first receipt
        assert result1 == receipt1
        assert result2 == receipt1  # Returns existing, not the new one
        assert result1.id == result2.id
