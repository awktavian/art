"""Tests for Receipt Model UUID type fix (Dec 21, 2025).

CIRCUIT TRACE discovered schema mismatch:
- Migration: parent_receipt_id UUID
- Model: parent_receipt_id String(100)

This caused: "value type varchar doesn't match type uuid of column parent_receipt_id"

Fix: Changed model to use UUID(as_uuid=True) to match migration.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import uuid

from sqlalchemy import UUID as SQLAlchemyUUID, Column


class TestReceiptModelUUID:
    """Verify Receipt model uses correct UUID type for parent_receipt_id."""

    def test_parent_receipt_id_is_uuid_type(self) -> None:
        """parent_receipt_id column should be UUID, not String."""
        from kagami.core.database.models import Receipt

        # Get the column
        parent_col = Receipt.__table__.columns["parent_receipt_id"]

        # Check type
        assert isinstance(
            parent_col.type, SQLAlchemyUUID
        ), f"Expected UUID type, got {type(parent_col.type).__name__}"

    def test_parent_receipt_id_allows_none(self) -> None:
        """parent_receipt_id should be nullable."""
        from kagami.core.database.models import Receipt

        parent_col = Receipt.__table__.columns["parent_receipt_id"]
        assert parent_col.nullable is True

    def test_receipt_id_is_uuid_type(self) -> None:
        """id (primary key) should also be UUID."""
        from kagami.core.database.models import Receipt

        id_col = Receipt.__table__.columns["id"]
        assert isinstance(
            id_col.type, SQLAlchemyUUID
        ), f"Expected UUID type, got {type(id_col.type).__name__}"

    def test_receipt_can_be_instantiated_with_uuid_parent(self) -> None:
        """Receipt should accept UUID for parent_receipt_id."""
        from kagami.core.database.models import Receipt

        parent_id = uuid.uuid4()
        receipt = Receipt(
            correlation_id="test_correlation",
            parent_receipt_id=parent_id,
            phase="EXECUTE",
            action="test",
            intent={},
            event={},
            data={},
            metrics={},
        )

        assert receipt.parent_receipt_id == parent_id

    def test_receipt_can_be_instantiated_with_none_parent(self) -> None:
        """Receipt should accept None for parent_receipt_id."""
        from kagami.core.database.models import Receipt

        receipt = Receipt(
            correlation_id="test_correlation",
            parent_receipt_id=None,
            phase="EXECUTE",
            action="test",
            intent={},
            event={},
            data={},
            metrics={},
        )

        assert receipt.parent_receipt_id is None
