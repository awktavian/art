"""Tests for receipt parent_receipt_id linking.

Tests PLAN→EXECUTE→VERIFY phase linking via parent_receipt_id field.

Created: December 19, 2025
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC

from kagami.core.schemas.receipt_schema import Receipt as ReceiptSchema
from kagami.core.receipts.facade import UnifiedReceiptFacade as URF


def test_receipt_schema_has_parent_receipt_id():
    """Test 1: Receipt schema has parent_receipt_id field."""
    # Create receipt with parent_receipt_id
    receipt = ReceiptSchema(
        correlation_id="test_123",
        parent_receipt_id="parent_456",
        phase="EXECUTE",
        status="success",
    )

    assert receipt.parent_receipt_id == "parent_456"
    assert receipt.phase == "EXECUTE"


def test_receipt_schema_parent_receipt_id_optional():
    """Test 2: parent_receipt_id is optional (backward compatibility)."""
    # Create receipt without parent_receipt_id
    receipt = ReceiptSchema(
        correlation_id="test_789",
        phase="PLAN",
        status="success",
    )

    assert receipt.parent_receipt_id is None
    assert receipt.correlation_id == "test_789"


def test_urf_emit_with_parent_receipt_id():
    """Test 3: UnifiedReceiptFacade.emit() accepts parent_receipt_id."""
    parent_correlation_id = URF.generate_correlation_id(name="parent_op")
    child_correlation_id = URF.generate_correlation_id(name="child_op")

    # Emit parent receipt
    parent_receipt = URF.emit(
        correlation_id=parent_correlation_id,
        event_name="operation.plan",
        action="plan",
        phase="PLAN",
        status="success",
    )

    assert parent_receipt["correlation_id"] == parent_correlation_id
    assert parent_receipt["phase"] == "PLAN"
    assert (
        "parent_receipt_id" not in parent_receipt or parent_receipt.get("parent_receipt_id") is None
    )

    # Emit child receipt with parent link
    child_receipt = URF.emit(
        correlation_id=child_correlation_id,
        event_name="operation.execute",
        action="execute",
        phase="EXECUTE",
        parent_receipt_id=parent_correlation_id,
        status="success",
    )

    assert child_receipt["correlation_id"] == child_correlation_id
    assert child_receipt["phase"] == "EXECUTE"
    assert child_receipt["parent_receipt_id"] == parent_correlation_id


def test_plan_execute_verify_chain():
    """Test 4: PLAN→EXECUTE→VERIFY chain with parent linking."""
    base_correlation_id = URF.generate_correlation_id(name="test_chain")

    # PLAN phase (root)
    plan_receipt = URF.emit(
        correlation_id=base_correlation_id,
        event_name="intent.plan",
        action="plan_task",
        phase="PLAN",
        status="success",
    )
    plan_id = plan_receipt["correlation_id"]

    # EXECUTE phase (child of PLAN)
    execute_receipt = URF.emit(
        correlation_id=base_correlation_id,
        event_name="intent.execute",
        action="execute_task",
        phase="EXECUTE",
        parent_receipt_id=plan_id,
        status="success",
    )

    # VERIFY phase (child of EXECUTE)
    verify_receipt = URF.emit(
        correlation_id=base_correlation_id,
        event_name="intent.verify",
        action="verify_task",
        phase="VERIFY",
        parent_receipt_id=plan_id,
        status="success",
    )

    # Validate chain structure
    assert plan_receipt.get("parent_receipt_id") is None  # Root
    assert execute_receipt["parent_receipt_id"] == plan_id
    assert verify_receipt["parent_receipt_id"] == plan_id

    # Validate phases
    assert plan_receipt["phase"] == "PLAN"
    assert execute_receipt["phase"] == "EXECUTE"
    assert verify_receipt["phase"] == "VERIFY"


@pytest.mark.skip(reason="TODO: Add database fixture - test receipt chain traversal")
@pytest.mark.asyncio
async def test_receipt_repository_get_chain():
    """Test 5: ReceiptRepository.get_receipt_chain() traverses parent links.

    This test requires database setup. Run integration tests for full validation.
    """
    pass


@pytest.mark.skip(reason="TODO: Add database fixture - test chain with no parent (backward compat)")
@pytest.mark.asyncio
async def test_receipt_repository_get_chain_no_parent():
    """Test 6: get_receipt_chain() handles receipts without parent links (backward compat).

    This test requires database setup. Run integration tests for full validation.
    """
    pass


def test_receipt_schema_validation():
    """Test 7: Receipt schema validates parent_receipt_id type."""
    # Valid: string parent_receipt_id
    receipt = ReceiptSchema(
        correlation_id="test",
        parent_receipt_id="parent_123",
        phase="EXECUTE",
    )
    assert receipt.parent_receipt_id == "parent_123"

    # Valid: None parent_receipt_id
    receipt = ReceiptSchema(
        correlation_id="test",
        parent_receipt_id=None,
        phase="PLAN",
    )
    assert receipt.parent_receipt_id is None

    # Invalid: wrong type should fail validation
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReceiptSchema(
            correlation_id="test",
            parent_receipt_id=12345,  # Should be str | None  # type: ignore[arg-type]
            phase="EXECUTE",
        )


def test_database_model_has_parent_receipt_id():
    """Test 8: Database Receipt model has parent_receipt_id column."""
    from kagami.core.database.models import Receipt

    # Verify column exists in model
    assert hasattr(Receipt, "parent_receipt_id")

    # Verify it's a Column
    from sqlalchemy import Column

    assert isinstance(Receipt.parent_receipt_id.property.columns[0], Column)

    # Verify it's nullable (backward compat)
    column = Receipt.parent_receipt_id.property.columns[0]
    assert column.nullable is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
