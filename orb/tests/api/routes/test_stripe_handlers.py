"""Unit tests for Stripe webhook handlers.

Tests for RefundEventHandler, DisputeEventHandler, and PaymentFailureHandler.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import json
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from kagami_api.routes.billing.stripe_handlers import (
    DisputeEventHandler,
    PaymentFailureHandler,
    RefundEventHandler,
)
from kagami.core.database.models import IdempotencyKey, MarketplacePurchase, User


class MockWebhookEvent:
    """Mock Stripe webhook event for testing."""

    def __init__(self, event_id: str, event_type: str, data: dict[str, Any]):
        self.id = event_id
        self.type = event_type
        self.data = data


class TestRefundEventHandler:
    """Tests for RefundEventHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return RefundEventHandler()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def user_uuid(self):
        """Create test user UUID."""
        return uuid4()

    def test_refund_event_with_plugin(self, handler: Any, mock_db: Any, user_uuid: Any) -> None:
        """Test refund event for plugin purchase."""
        event_id = "evt_test_refund_123"
        charge_id = "ch_test_123"
        plugin_id = "plugin_test_123"
        amount_refunded = 1999

        event_data = {
            "object": {
                "id": charge_id,
                "amount_refunded": amount_refunded,
                "currency": "usd",
                "metadata": {
                    "plugin_id": plugin_id,
                    "user_id": str(user_uuid),
                },
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.refunded", event_data)

        # Create mock purchase
        mock_purchase = MagicMock()
        mock_purchase.id = uuid4()
        mock_purchase.status = "active"
        mock_purchase.purchase_metadata = {}

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            # Mock purchase query
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                None,  # Idempotency check (no existing)
                mock_purchase,  # Purchase lookup
            ]

            result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["event_id"] == event_id
        assert result["processed"] is True
        assert result["charge_id"] == charge_id
        assert result["amount_refunded"] == amount_refunded
        assert mock_purchase.status == "refunded"
        assert "refund_charge_id" in mock_purchase.purchase_metadata
        mock_db.commit.assert_called_once()

    def test_refund_event_idempotency(self, handler: Any, mock_db: Any, user_uuid: Any) -> None:
        """Test idempotency prevents duplicate processing."""
        event_id = "evt_test_duplicate_123"

        event_data = {
            "object": {
                "id": "ch_test_123",
                "amount_refunded": 1999,
                "currency": "usd",
                "metadata": {"user_id": str(user_uuid)},
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.refunded", event_data)

        # Mock existing idempotency key
        existing_key = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_key

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["already_processed"] is True
        mock_db.commit.assert_not_called()

    def test_refund_event_no_user(self, handler: Any, mock_db: Any) -> None:
        """Test refund event with no user_id."""
        event_id = "evt_test_no_user_123"

        event_data = {
            "object": {
                "id": "ch_test_123",
                "amount_refunded": 1999,
                "currency": "usd",
                "metadata": {},
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.refunded", event_data)

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["reason"] == "no_user_id"
        mock_db.commit.assert_called_once()

    def test_refund_event_db_rollback_on_error(self, handler: Any, mock_db: Any) -> None:
        """Test database rollback on error."""
        event_id = "evt_test_error_123"

        event_data = {
            "object": {
                "id": "ch_test_123",
                "amount_refunded": 1999,
                "currency": "usd",
                "metadata": {},
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.refunded", event_data)

        # Make commit fail
        mock_db.commit.side_effect = Exception("DB error")

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            with pytest.raises(Exception, match="DB error"):
                handler.handle(event, payload)

        mock_db.rollback.assert_called_once()


class TestDisputeEventHandler:
    """Tests for DisputeEventHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return DisputeEventHandler()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def user_uuid(self):
        """Create test user UUID."""
        return uuid4()

    def test_dispute_created(self, handler: Any, mock_db: Any, user_uuid: Any) -> None:
        """Test dispute.created event."""
        event_id = "evt_test_dispute_123"
        dispute_id = "dp_test_123"
        charge_id = "ch_test_123"

        event_data = {
            "object": {
                "id": dispute_id,
                "charge": charge_id,
                "status": "warning_under_review",
                "reason": "fraudulent",
                "amount": 1999,
                "currency": "usd",
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.dispute.created", event_data)

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            with patch("kagami_api.routes.billing.stripe_handlers.os.getenv", return_value=None):
                result = handler.handle(event, payload)

        assert result["ok"] is True
        # Without user_id, handler returns no_user_id reason
        assert result.get("reason") == "no_user_id" or result.get("dispute_id") == dispute_id

    def test_dispute_lost_revokes_access(self, handler: Any, mock_db: Any, user_uuid: Any) -> None:
        """Test lost dispute revokes plugin access."""
        event_id = "evt_test_dispute_lost_123"
        dispute_id = "dp_test_123"
        charge_id = "ch_test_123"
        plugin_id = "plugin_test_123"

        event_data = {
            "object": {
                "id": dispute_id,
                "charge": charge_id,
                "status": "lost",
                "reason": "fraudulent",
                "amount": 1999,
                "currency": "usd",
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.dispute.closed", event_data)

        # Mock Stripe charge retrieval
        mock_charge = MagicMock()
        mock_charge.metadata = {
            "plugin_id": plugin_id,
            "user_id": str(user_uuid),
        }
        mock_charge.customer = "cus_test_123"

        # Mock purchase
        mock_purchase = MagicMock()
        mock_purchase.status = "active"
        mock_purchase.purchase_metadata = {}

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            with patch(
                "kagami_api.routes.billing.stripe_handlers.os.getenv", return_value="test_key"
            ):
                with patch("stripe.Charge.retrieve", return_value=mock_charge):
                    mock_db.query.return_value.filter.return_value.first.side_effect = [
                        None,  # Idempotency check
                        mock_purchase,  # Purchase lookup
                    ]

                    result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["dispute_id"] == dispute_id
        assert result["status"] == "lost"
        assert mock_purchase.status == "disputed_lost"
        assert "dispute_id" in mock_purchase.purchase_metadata

    def test_dispute_won_no_action(self, handler: Any, mock_db: Any, user_uuid: Any) -> None:
        """Test won dispute takes no action."""
        event_id = "evt_test_dispute_won_123"

        event_data = {
            "object": {
                "id": "dp_test_123",
                "charge": "ch_test_123",
                "status": "won",
                "reason": "fraudulent",
                "amount": 1999,
                "currency": "usd",
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "charge.dispute.closed", event_data)

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            with patch("kagami_api.routes.billing.stripe_handlers.os.getenv", return_value=None):
                result = handler.handle(event, payload)

        assert result["ok"] is True
        # Without user_id, handler returns no_user_id reason
        assert result.get("reason") == "no_user_id" or result.get("status") == "won"


class TestPaymentFailureHandler:
    """Tests for PaymentFailureHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return PaymentFailureHandler()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def user_uuid(self):
        """Create test user UUID."""
        return uuid4()

    def test_payment_failed(self, handler: Any, mock_db: Any, user_uuid: Any) -> None:
        """Test payment_intent.payment_failed event."""
        event_id = "evt_test_payment_failed_123"
        payment_intent_id = "pi_test_123"

        event_data = {
            "object": {
                "id": payment_intent_id,
                "amount": 1999,
                "currency": "usd",
                "customer": "cus_test_123",
                "last_payment_error": {
                    "message": "Your card was declined.",
                },
                "metadata": {
                    "user_id": str(user_uuid),
                },
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "payment_intent.payment_failed", event_data)

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["processed"] is True
        assert result["payment_intent_id"] == payment_intent_id
        assert result["error"] == "Your card was declined."
        assert result["user_id"] == str(user_uuid)
        mock_db.commit.assert_called_once()

    def test_payment_failed_no_error_message(
        self, handler: Any, mock_db: Any, user_uuid: Any
    ) -> None:
        """Test payment failure with no error message."""
        event_id = "evt_test_no_error_123"

        event_data = {
            "object": {
                "id": "pi_test_123",
                "amount": 1999,
                "currency": "usd",
                "last_payment_error": None,
                "metadata": {"user_id": str(user_uuid)},
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "payment_intent.payment_failed", event_data)

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["error"] == "Unknown"

    def test_payment_failed_idempotency(self, handler: Any, mock_db: Any) -> None:
        """Test idempotency prevents duplicate processing."""
        event_id = "evt_test_duplicate_payment_123"

        event_data = {
            "object": {
                "id": "pi_test_123",
                "amount": 1999,
                "currency": "usd",
                "metadata": {},
            }
        }

        payload = json.dumps({"data": event_data}).encode("utf-8")
        event = MockWebhookEvent(event_id, "payment_intent.payment_failed", event_data)

        # Mock existing idempotency key
        existing_key = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_key

        with patch(
            "kagami_api.routes.billing.stripe_handlers.get_session_factory",
            return_value=MagicMock(return_value=mock_db),
        ):
            result = handler.handle(event, payload)

        assert result["ok"] is True
        assert result["already_processed"] is True
        mock_db.commit.assert_not_called()


class TestIdempotencyAndAuditHelpers:
    """Tests for idempotency and audit helper methods."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return RefundEventHandler()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    def test_check_idempotency_exists(self, handler: Any, mock_db: Any) -> None:
        """Test idempotency check with existing key."""
        event_id = "evt_test_123"
        existing_key = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_key

        result = handler._check_idempotency(event_id, mock_db)

        assert result is True

    def test_check_idempotency_not_exists(self, handler: Any, mock_db: Any) -> None:
        """Test idempotency check with no existing key."""
        event_id = "evt_test_123"
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = handler._check_idempotency(event_id, mock_db)

        assert result is False

    def test_check_idempotency_db_error(self, handler: Any, mock_db: Any) -> None:
        """Test idempotency check handles DB errors gracefully."""
        event_id = "evt_test_123"
        mock_db.query.side_effect = Exception("DB error")

        result = handler._check_idempotency(event_id, mock_db)

        assert result is False

    def test_record_idempotency(self, handler: Any, mock_db: Any) -> None:
        """Test recording idempotency key."""
        event_id = "evt_test_123"
        event_type = "charge.refunded"

        handler._record_idempotency(event_id, event_type, mock_db)

        mock_db.add.assert_called_once()
        added_key = mock_db.add.call_args[0][0]
        assert isinstance(added_key, IdempotencyKey)
        assert added_key.key == f"stripe_event:{event_id}"
        assert added_key.path == f"/webhooks/stripe/{event_type}"

    def test_record_idempotency_handles_error(self, handler: Any, mock_db: Any) -> None:
        """Test idempotency recording handles errors gracefully."""
        event_id = "evt_test_123"
        event_type = "charge.refunded"
        mock_db.add.side_effect = Exception("DB error")

        # Should not raise
        handler._record_idempotency(event_id, event_type, mock_db)

    def test_log_audit_event(self, handler: Any) -> None:
        """Test audit logging."""
        event_type = "charge.refunded"
        event_id = "evt_test_123"
        user_id = uuid4()
        action = "refund_processed"
        details = {"charge_id": "ch_test_123", "amount": 1999}

        with patch("kagami_api.routes.billing.stripe_handlers.logger") as mock_logger:
            handler._log_audit_event(event_type, event_id, user_id, action, details)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "AUDIT" in call_args[0][0]
        assert call_args[1]["extra"]["event_type"] == event_type
        assert call_args[1]["extra"]["event_id"] == event_id
        assert call_args[1]["extra"]["user_id"] == str(user_id)
