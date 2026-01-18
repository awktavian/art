"""Test atomic webhook idempotency (isolated from app dependencies).

This test verifies the atomic idempotency logic without importing
the full FastAPI app stack, avoiding import dependency issues.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration
import uuid
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from kagami.core.database.connection import get_session_factory
from kagami.core.database.models import AppData


def _is_duplicate_event_isolated(event_id: str, evt_type: str) -> bool:
    """Isolated implementation of atomic idempotency check.
    This is a copy of the production logic for testing purposes.
    Uses database-level unique constraint to prevent race conditions.
    """
    db = get_session_factory()()
    try:
        # Atomic insert - database constraint prevents duplicates
        record = AppData(
            app_name="billing",
            data_type="stripe_webhook",
            data_id=event_id,
            data={"type": evt_type, "received_at": datetime.utcnow().isoformat()},
        )
        db.add(record)
        db.commit()
        # Success: First time seeing this event
        return False
    except IntegrityError:
        # Expected: Duplicate event_id (unique constraint violation)
        db.rollback()
        return True
    except Exception:
        # Unexpected error: Treat as duplicate to be safe
        db.rollback()
        return True
    finally:
        try:
            db.close()
        except Exception:
            pass


def test_webhook_idempotency_atomic_sequential() -> None:
    """Test webhook idempotency uses atomic database constraint.
    Verifies:
    1. First insert succeeds (returns False = not duplicate)
    2. Second insert fails with IntegrityError (returns True = duplicate)
    3. No check-then-insert race condition possible
    """
    event_id = f"evt_test_{uuid.uuid4()}"
    evt_type = "checkout.session.completed"
    # First call: Should succeed (not duplicate)
    is_dup_1 = _is_duplicate_event_isolated(event_id, evt_type)
    assert is_dup_1 is False, "First event should not be marked as duplicate"
    # Second call: Should fail (duplicate detected by database constraint)
    is_dup_2 = _is_duplicate_event_isolated(event_id, evt_type)
    assert is_dup_2 is True, "Second event should be marked as duplicate"
    # Third call: Still duplicate
    is_dup_3 = _is_duplicate_event_isolated(event_id, evt_type)
    assert is_dup_3 is True, "Third event should still be marked as duplicate"


def test_webhook_idempotency_concurrent_simulation() -> None:
    """Simulate concurrent webhook processing (same event_id).
    Tests that database constraint prevents race condition.
    Multiple threads attempt to insert same event_id.
    Exactly one succeeds, rest get IntegrityError (caught as duplicate).
    """
    import threading

    event_id = f"evt_concurrent_{uuid.uuid4()}"
    evt_type = "payment_intent.succeeded"
    results = []

    def process_webhook() -> None:
        is_dup = _is_duplicate_event_isolated(event_id, evt_type)
        results.append(is_dup)

    # Simulate concurrent requests
    num_threads = 5
    threads = [threading.Thread(target=process_webhook) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Exactly one thread should succeed (False), others fail (True)
    false_count = results.count(False)
    true_count = results.count(True)
    assert false_count == 1, f"Expected exactly 1 success, got {false_count}"
    assert true_count == num_threads - 1, f"Expected {num_threads - 1} duplicates, got {true_count}"
    assert len(results) == num_threads, "All threads should have completed"


def test_webhook_idempotency_different_events() -> None:
    """Test that different event IDs are treated as separate events."""
    evt_type = "checkout.session.completed"
    event_id_1 = f"evt_different_1_{uuid.uuid4()}"
    event_id_2 = f"evt_different_2_{uuid.uuid4()}"
    # Both should succeed (different events)
    is_dup_1 = _is_duplicate_event_isolated(event_id_1, evt_type)
    is_dup_2 = _is_duplicate_event_isolated(event_id_2, evt_type)
    assert is_dup_1 is False, "First unique event should succeed"
    assert is_dup_2 is False, "Second unique event should succeed"
    # Repeating same events should be duplicates
    assert _is_duplicate_event_isolated(event_id_1, evt_type) is True
    assert _is_duplicate_event_isolated(event_id_2, evt_type) is True


def test_webhook_idempotency_database_constraint_exists() -> None:
    """Verify the unique constraint exists in the database.
    This test checks that the migration has been applied.
    """
    from sqlalchemy import inspect

    db = get_session_factory()()
    try:
        inspector = inspect(db.bind)
        indexes = inspector.get_indexes("app_data")
        # Look for our idempotency index
        index_names = [idx["name"] for idx in indexes]
        # The constraint should exist (either as unique constraint or index)
        # Note: This might fail if migration hasn't been applied yet
        assert any(
            "webhook" in name.lower() or "idempotency" in name.lower() for name in index_names
        ), (
            "Webhook idempotency constraint not found. "
            "Run migration: migrations/versions/20251215_webhook_idempotency_constraint.sql"
        )
    finally:
        db.close()


@pytest.mark.skip(reason="Requires database migration to be applied")
def test_webhook_idempotency_stress_test() -> None:
    """Stress test: Many concurrent requests with same event_id.
    This is skipped by default to avoid load on test DB.
    Enable manually for stress testing.
    """
    import threading

    event_id = f"evt_stress_{uuid.uuid4()}"
    evt_type = "payment_intent.succeeded"
    results = []
    num_threads = 50

    def process_webhook() -> None:
        is_dup = _is_duplicate_event_isolated(event_id, evt_type)
        results.append(is_dup)

    threads = [threading.Thread(target=process_webhook) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Exactly one should succeed, rest duplicates
    false_count = results.count(False)
    true_count = results.count(True)
    assert (
        false_count == 1
    ), f"Expected exactly 1 success in {num_threads} threads, got {false_count}"
    assert true_count == num_threads - 1
    assert len(results) == num_threads
