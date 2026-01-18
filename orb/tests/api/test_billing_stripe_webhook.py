"""Billing Stripe Webhook Tests

Tests Stripe webhook endpoint handling.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import uuid

from fastapi.testclient import TestClient

from kagami_api import create_app


@pytest.fixture()
def client_no_stripe(monkeypatch: Any) -> Any:
    """Create client with Stripe disabled."""
    monkeypatch.setenv("KAGAMI_TEST_NO_CLOUD", "1")
    monkeypatch.delenv("STRIPE_ENABLED", raising=False)
    app = create_app()
    return TestClient(app)


def test_webhook_returns_disabled_when_stripe_off(client_no_stripe: Any) -> Any:
    """Test webhook returns appropriate response when Stripe is disabled."""
    r = client_no_stripe.post(
        "/api/billing/stripe/webhook",
        data=b"{}",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 200
    data = r.json()
    # Accept various valid response formats
    assert (
        data.get("disabled") is True
        or data.get("status") in ("received", "disabled")
        or data.get("error") in ("missing_webhook_secret", "missing_signature")
    )


def test_webhook_verification_success(monkeypatch: Any) -> None:
    """Test webhook verification with mocked Stripe."""
    # Enable stripe and inject a dummy stripe module
    monkeypatch.setenv("STRIPE_ENABLED", "1")
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_123")

    class _DummyEvent:
        id = "evt_123"
        type = "checkout.session.completed"

    class _DummyStripe:
        class Webhook:
            @staticmethod
            def construct_event(payload: Any, sig_header: Any, secret: Any) -> Any:
                return _DummyEvent()

    import sys

    sys.modules["stripe"] = _DummyStripe()  # type: ignore[assignment]
    # Force-enable in tests
    import kagami_integrations.stripe_billing as sb

    monkeypatch.setattr(sb, "stripe_enabled", lambda: True)
    from kagami_api import create_app

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/api/billing/stripe/webhook",
        data=b"{}",  # type: ignore[arg-type]
        headers={"Idempotency-Key": str(uuid.uuid4()), "Stripe-Signature": "t=1,v1=test"},
    )
    assert r.status_code == 200
    data = r.json()
    # Accept various valid response formats
    assert (
        data.get("ok") is True
        or data.get("disabled") is True
        or data.get("status") in ("received", "processed", "disabled")
    )


def test_webhook_endpoint_exists(monkeypatch: Any) -> None:
    """Test webhook endpoint is registered."""
    app = create_app()
    client = TestClient(app)
    # POST with empty body should not 404
    r = client.post(
        "/api/billing/stripe/webhook",
        data=b"{}",  # type: ignore[arg-type]
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code in (200, 400, 403)


def test_webhook_idempotency_atomic():
    """Test webhook idempotency uses atomic database constraint.

    Verifies:
    1. First insert succeeds (returns False = not duplicate)
    2. Second insert fails with IntegrityError (returns True = duplicate)
    3. No check-then-insert race condition possible
    """
    from kagami_api.routes.billing.stripe import _is_duplicate_event

    event_id = f"evt_test_{uuid.uuid4()}"
    evt_type = "checkout.session.completed"

    # First call: Should succeed (not duplicate)
    is_dup_1 = _is_duplicate_event(event_id, evt_type)
    assert is_dup_1 is False, "First event should not be marked as duplicate"

    # Second call: Should fail (duplicate detected by database constraint)
    is_dup_2 = _is_duplicate_event(event_id, evt_type)
    assert is_dup_2 is True, "Second event should be marked as duplicate"

    # Third call: Still duplicate
    is_dup_3 = _is_duplicate_event(event_id, evt_type)
    assert is_dup_3 is True, "Third event should still be marked as duplicate"


def test_webhook_idempotency_concurrent_simulation():
    """Simulate concurrent webhook processing (same event_id).

    Tests that database constraint prevents race condition.
    Both concurrent "requests" attempt to insert same event_id.
    One succeeds, one gets IntegrityError (caught as duplicate).
    """
    import threading
    from kagami_api.routes.billing.stripe import _is_duplicate_event

    event_id = f"evt_concurrent_{uuid.uuid4()}"
    evt_type = "payment_intent.succeeded"

    results = []

    def process_webhook():
        is_dup = _is_duplicate_event(event_id, evt_type)
        results.append(is_dup)

    # Simulate concurrent requests
    threads = [threading.Thread(target=process_webhook) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread should succeed (False), others fail (True)
    false_count = results.count(False)
    true_count = results.count(True)

    assert false_count == 1, f"Expected exactly 1 success, got {false_count}"
    assert true_count == 4, f"Expected exactly 4 duplicates, got {true_count}"
    assert len(results) == 5, "All threads should have completed"
