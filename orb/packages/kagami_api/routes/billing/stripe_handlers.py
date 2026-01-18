"""Stripe webhook event handlers using Strategy pattern.

Each handler processes a specific event type from Stripe webhooks.
Reduces cyclomatic complexity by decomposing the giant switch statement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from kagami.core.database.connection import get_session_factory
from kagami.core.database.models import (
    IdempotencyKey,
    MarketplacePurchase,
    TenantPlan,
    User,
)

from kagami_api.subscription_tiers import (
    SubscriptionTier,
    get_tier_config,
    map_stripe_plan_to_tier,
)

logger = logging.getLogger(__name__)


class WebhookEvent(Protocol):
    """Protocol for verified webhook events."""

    id: str
    type: str
    data: dict[str, Any]


class StripeEventHandler(ABC):
    """Base handler for Stripe webhook events."""

    @abstractmethod
    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        """Process the event and return response dict.

        Args:
            event: Verified Stripe event object
            payload: Raw webhook payload

        Returns:
            Response dictionary with status info
        """
        ...

    def _check_idempotency(self, event_id: str, db: Any) -> bool:
        """Check if event has already been processed.

        Args:
            event_id: Stripe event ID
            db: Database session

        Returns:
            True if event already processed, False otherwise
        """
        try:
            existing = (
                db.query(IdempotencyKey)
                .filter(IdempotencyKey.key == f"stripe_event:{event_id}")
                .first()
            )
            return existing is not None
        except Exception:
            return False

    def _record_idempotency(self, event_id: str, event_type: str, db: Any) -> None:
        """Record event as processed for idempotency.

        Args:
            event_id: Stripe event ID
            event_type: Event type string
            db: Database session
        """
        try:
            idem_key = IdempotencyKey(
                key=f"stripe_event:{event_id}",
                path=f"/webhooks/stripe/{event_type}",
                status_code=200,
                response_hash=hashlib.sha256(event_id.encode()).hexdigest(),
            )
            db.add(idem_key)
        except Exception as e:
            logger.warning(f"Failed to record idempotency for {event_id}: {e}")

    def _log_audit_event(
        self,
        event_type: str,
        event_id: str,
        user_id: UUID | None,
        action: str,
        details: dict[str, Any],
    ) -> None:
        """Log audit event for webhook processing.

        Args:
            event_type: Stripe event type
            event_id: Stripe event ID
            user_id: User ID if available
            action: Action description
            details: Additional context
        """
        logger.info(
            f"AUDIT: {action}",
            extra={
                "event_type": event_type,
                "event_id": event_id,
                "user_id": str(user_id) if user_id else None,
                "details": details,
            },
        )

    def _extract_metadata(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata safely from event object."""
        metadata = obj.get("metadata") if isinstance(obj, dict) else None
        return metadata if isinstance(metadata, dict) else {}

    def _resolve_user_id(
        self, metadata: dict[str, Any], stripe_customer_id: str | None
    ) -> str | None:
        """Resolve user_id from metadata or customer metadata."""
        user_id_str = self._extract_user_id_from_metadata(metadata)
        if not user_id_str and stripe_customer_id:
            user_id_str = self._fetch_user_id_from_stripe_customer(stripe_customer_id)
        return user_id_str

    def _extract_user_id_from_metadata(self, metadata: dict[str, Any]) -> str | None:
        """Extract user_id from event metadata."""
        return (
            metadata.get("user_id") or metadata.get("uid") or metadata.get("kagami_user_id") or None
        )

    def _fetch_user_id_from_stripe_customer(self, customer_id: str) -> str | None:
        """Fetch user_id from Stripe customer metadata."""
        if not os.getenv("STRIPE_API_KEY"):
            return None
        try:
            from kagami_integrations.stripe_billing import _stripe_request

            result = _stripe_request("GET", f"customers/{customer_id}")
            if result.get("ok"):
                cust_meta = result.get("data", {}).get("metadata", {})
                if isinstance(cust_meta, dict):
                    return cust_meta.get("kagami_user_id")
        except Exception:
            pass
        return None

    def _parse_user_uuid(self, user_id_str: str | None) -> UUID | None:
        """Parse user_id string to UUID."""
        if not user_id_str:
            return None
        try:
            return UUID(str(user_id_str))
        except Exception:
            return None

    def _extract_price_ids(
        self, evt_type: str, obj: dict[str, Any], stripe_subscription_id: str | None
    ) -> list[str]:
        """Extract price IDs from event for tier mapping."""
        try:
            if evt_type.startswith("customer.subscription."):
                price_ids = self._extract_from_subscription_event(obj)
            elif stripe_subscription_id:
                price_ids = self._extract_from_subscription_api(stripe_subscription_id)
            elif evt_type == "checkout.session.completed":
                price_ids = self._extract_from_checkout_session(obj)
            else:
                price_ids = []
        except Exception:
            price_ids = []
        return self._filter_metered_prices(price_ids)

    def _extract_from_subscription_event(self, obj: dict[str, Any]) -> list[str]:
        """Extract price IDs from subscription event object."""
        price_ids: list[str] = []
        if not isinstance(obj, dict):
            return price_ids  # type: ignore[unreachable]
        items = obj.get("items") or {}
        data = items.get("data") if isinstance(items, dict) else None
        if isinstance(data, list):
            for it in data:
                price = (it or {}).get("price") if isinstance(it, dict) else None
                pid = (price or {}).get("id") if isinstance(price, dict) else None
                if pid:
                    price_ids.append(str(pid))
        return price_ids

    def _extract_from_subscription_api(self, subscription_id: str) -> list[str]:
        """Extract price IDs from Stripe subscription API."""
        price_ids: list[str] = []
        if not os.getenv("STRIPE_API_KEY"):
            return price_ids
        try:
            from kagami_integrations.stripe_billing import _stripe_request

            result = _stripe_request(
                "GET", f"subscriptions/{subscription_id}", {"expand[]": "items"}
            )
            if result.get("ok"):
                sub = result.get("data", {})
                items = sub.get("items", {}).get("data", [])
                for it in items:
                    price = it.get("price", {})
                    pid = price.get("id")
                    if pid:
                        price_ids.append(str(pid))
        except Exception:
            pass
        return price_ids

    def _extract_from_checkout_session(self, obj: dict[str, Any]) -> list[str]:
        """Extract price IDs from checkout session."""
        price_ids: list[str] = []
        if not os.getenv("STRIPE_API_KEY"):
            return price_ids
        try:
            from kagami_integrations.stripe_billing import _stripe_request

            sess_id = obj.get("id") if isinstance(obj, dict) else None
            if sess_id:
                result = _stripe_request(
                    "GET", f"checkout/sessions/{sess_id}/line_items", {"limit": "25"}
                )
                if result.get("ok"):
                    for item in result.get("data", {}).get("data", []):
                        price = item.get("price", {})
                        pid = price.get("id")
                        if pid:
                            price_ids.append(str(pid))
        except Exception:
            pass
        return price_ids

    def _filter_metered_prices(self, price_ids: list[str]) -> list[str]:
        """Filter out metered addon prices."""
        ignore_prices = {
            (os.getenv("STRIPE_PRICE_OPS") or "").strip(),
            (os.getenv("STRIPE_PRICE_ATTEST") or "").strip(),
        }
        return [p for p in price_ids if p and p not in ignore_prices]

    def _determine_tier(self, evt_type: str, price_ids: list[str]) -> SubscriptionTier:
        """Determine subscription tier from price IDs."""
        tier_candidates: list[SubscriptionTier] = []
        for pid in price_ids:
            tier_candidates.append(map_stripe_plan_to_tier(pid))
        if not tier_candidates:
            tier_candidates = [map_stripe_plan_to_tier(evt_type)]

        def _rank(t: SubscriptionTier) -> int:
            if t == SubscriptionTier.POWER:
                return 3
            if t == SubscriptionTier.FAMILY:
                return 2
            if t == SubscriptionTier.PERSONAL:
                return 1
            return 0

        return (
            sorted(tier_candidates, key=_rank, reverse=True)[0]
            if tier_candidates
            else SubscriptionTier.FREE
        )

    def _sync_plan_to_db(
        self,
        user_uuid: UUID,
        stripe_customer_id: str | None,
        tier: SubscriptionTier,
    ) -> str:
        """Sync subscription plan to database."""
        db = get_session_factory()()
        try:
            tenant_id = self._update_user_stripe_customer(db, user_uuid, stripe_customer_id)
            self._close_existing_plan(db, tenant_id)
            self._create_new_plan(db, user_uuid, tenant_id, tier)
            db.commit()
            return tenant_id
        except Exception:
            db.rollback()
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass

    def _update_user_stripe_customer(
        self, db: Any, user_uuid: UUID, stripe_customer_id: str | None
    ) -> str:
        """Update user's Stripe customer ID and return tenant_id."""
        user_row = db.query(User).filter(User.id == user_uuid).first()
        if user_row and stripe_customer_id:
            try:
                user_row.stripe_customer_id = str(stripe_customer_id)
            except Exception:
                pass
        tenant_id = None
        if user_row:
            tenant_id = getattr(user_row, "tenant_id", None)
        return str(tenant_id or user_uuid)

    def _close_existing_plan(self, db: Any, tenant_id: str) -> None:
        """Close existing active plan for tenant."""
        now_dt = datetime.utcnow()
        try:
            current = (
                db.query(TenantPlan)
                .filter(TenantPlan.tenant_id == tenant_id)
                .order_by(TenantPlan.valid_from.desc())
                .first()
            )
            if current and getattr(current, "valid_to", None) is None:
                current.valid_to = now_dt
        except Exception:
            pass

    def _create_new_plan(
        self, db: Any, user_uuid: UUID, tenant_id: str, tier: SubscriptionTier
    ) -> None:
        """Create new plan in database."""
        cfg = get_tier_config(tier)
        now_dt = datetime.utcnow()
        db.add(
            TenantPlan(
                tenant_id=tenant_id,
                user_id=user_uuid,
                plan_name=str(cfg.name),
                ops_monthly_cap=cfg.monthly_ops,
                settlement_monthly_cap=cfg.monthly_settlements,
                valid_from=now_dt,
            )
        )


class SubscriptionEventHandler(StripeEventHandler):
    """Handler for customer.subscription.* events."""

    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        raw_evt = json.loads(payload.decode("utf-8"))
        obj = (raw_evt.get("data") or {}).get("object") or {}
        metadata = self._extract_metadata(obj)

        if metadata.get("plugin_id"):
            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "note": "plugin_checkout",
            }

        stripe_customer_id = obj.get("customer") if isinstance(obj, dict) else None
        stripe_subscription_id = obj.get("subscription") if isinstance(obj, dict) else None

        user_id_str = self._resolve_user_id(metadata, stripe_customer_id)
        user_uuid = self._parse_user_uuid(user_id_str)

        if not user_uuid:
            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "synced": False,
                "reason": "no_user" if not user_id_str else "invalid_user_id",
            }

        price_ids = self._extract_price_ids(event.type, obj, stripe_subscription_id)
        tier = self._determine_tier(event.type, price_ids)

        if event.type == "customer.subscription.deleted":
            tier = SubscriptionTier.FREE

        tenant_id = self._sync_plan_to_db(user_uuid, stripe_customer_id, tier)

        return {
            "ok": True,
            "event_id": event.id,
            "type": event.type,
            "synced": True,
            "tier": str(tier.value),
            "tenant_id": tenant_id,
            "user_id": str(user_uuid),
        }


class CheckoutSessionEventHandler(StripeEventHandler):
    """Handler for checkout.session.completed events."""

    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        raw_evt = json.loads(payload.decode("utf-8"))
        obj = (raw_evt.get("data") or {}).get("object") or {}
        metadata = self._extract_metadata(obj)

        if metadata.get("plugin_id"):
            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "note": "plugin_checkout",
            }

        stripe_customer_id = obj.get("customer") if isinstance(obj, dict) else None
        stripe_subscription_id = obj.get("subscription") if isinstance(obj, dict) else None

        user_id_str = self._resolve_user_id(metadata, stripe_customer_id)
        user_uuid = self._parse_user_uuid(user_id_str)

        if not user_uuid:
            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "synced": False,
                "reason": "no_user" if not user_id_str else "invalid_user_id",
            }

        price_ids = self._extract_price_ids(event.type, obj, stripe_subscription_id)
        tier = self._determine_tier(event.type, price_ids)
        tenant_id = self._sync_plan_to_db(user_uuid, stripe_customer_id, tier)

        return {
            "ok": True,
            "event_id": event.id,
            "type": event.type,
            "synced": True,
            "tier": str(tier.value),
            "tenant_id": tenant_id,
            "user_id": str(user_uuid),
        }


class DefaultEventHandler(StripeEventHandler):
    """Handler for unhandled or unknown event types."""

    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        return {
            "ok": True,
            "event_id": event.id,
            "type": event.type,
        }


class RefundEventHandler(StripeEventHandler):
    """Handler for charge.refunded events."""

    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        raw_evt = json.loads(payload.decode("utf-8"))
        obj = (raw_evt.get("data") or {}).get("object") or {}

        charge_id = obj.get("id") if isinstance(obj, dict) else None
        amount_refunded = obj.get("amount_refunded", 0)
        currency = obj.get("currency", "usd")
        metadata = self._extract_metadata(obj)

        db = get_session_factory()()
        try:
            # Check idempotency
            if self._check_idempotency(event.id, db):
                return {
                    "ok": True,
                    "event_id": event.id,
                    "type": event.type,
                    "already_processed": True,
                }

            # Extract user and purchase info
            plugin_id = metadata.get("plugin_id")
            user_id_str = metadata.get("user_id") or metadata.get("kagami_user_id")
            user_uuid = self._parse_user_uuid(user_id_str)

            if not user_uuid:
                self._log_audit_event(
                    event.type,
                    event.id,
                    None,
                    "refund_no_user",
                    {"charge_id": charge_id, "amount": amount_refunded},
                )
                self._record_idempotency(event.id, event.type, db)
                db.commit()
                return {
                    "ok": True,
                    "event_id": event.id,
                    "type": event.type,
                    "reason": "no_user_id",
                }

            # Update marketplace purchase status if applicable
            if plugin_id:
                purchase = (
                    db.query(MarketplacePurchase)
                    .filter(
                        MarketplacePurchase.user_id == user_uuid,
                        MarketplacePurchase.item_id == plugin_id,
                        MarketplacePurchase.status == "active",
                    )
                    .first()
                )

                if purchase:
                    purchase.status = "refunded"
                    purchase.purchase_metadata = purchase.purchase_metadata or {}
                    purchase.purchase_metadata["refund_charge_id"] = charge_id
                    purchase.purchase_metadata["refund_amount"] = amount_refunded
                    purchase.purchase_metadata["refund_currency"] = currency
                    purchase.purchase_metadata["refund_timestamp"] = datetime.utcnow().isoformat()

                    self._log_audit_event(
                        event.type,
                        event.id,
                        user_uuid,
                        "purchase_refunded",
                        {
                            "purchase_id": str(purchase.id),
                            "plugin_id": plugin_id,
                            "charge_id": charge_id,
                            "amount": amount_refunded,
                            "currency": currency,
                        },
                    )

            self._record_idempotency(event.id, event.type, db)
            db.commit()

            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "processed": True,
                "user_id": str(user_uuid),
                "charge_id": charge_id,
                "amount_refunded": amount_refunded,
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing refund event {event.id}: {e}", exc_info=True)
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass


class DisputeEventHandler(StripeEventHandler):
    """Handler for charge.dispute.* events."""

    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        raw_evt = json.loads(payload.decode("utf-8"))
        obj = (raw_evt.get("data") or {}).get("object") or {}

        dispute_id = obj.get("id") if isinstance(obj, dict) else None
        charge_id = obj.get("charge") if isinstance(obj, dict) else None
        status = obj.get("status", "unknown")
        reason = obj.get("reason", "unknown")
        amount = obj.get("amount", 0)
        currency = obj.get("currency", "usd")

        db = get_session_factory()()
        try:
            # Check idempotency
            if self._check_idempotency(event.id, db):
                return {
                    "ok": True,
                    "event_id": event.id,
                    "type": event.type,
                    "already_processed": True,
                }

            # Fetch charge metadata to identify user/purchase
            stripe_customer_id = None
            metadata: dict[str, Any] = {}
            if charge_id and os.getenv("STRIPE_API_KEY"):
                try:
                    from kagami_integrations.stripe_billing import _stripe_request

                    result = _stripe_request("GET", f"charges/{charge_id}")
                    if result.get("ok"):
                        charge = result.get("data", {})
                        metadata = charge.get("metadata", {}) or {}
                        stripe_customer_id = charge.get("customer")
                except Exception as e:
                    logger.warning(f"Failed to fetch charge {charge_id}: {e}")

            user_id_str = self._resolve_user_id(metadata, stripe_customer_id)
            user_uuid = self._parse_user_uuid(user_id_str)

            if not user_uuid:
                self._log_audit_event(
                    event.type,
                    event.id,
                    None,
                    "dispute_no_user",
                    {
                        "dispute_id": dispute_id,
                        "charge_id": charge_id,
                        "status": status,
                        "reason": reason,
                    },
                )
                self._record_idempotency(event.id, event.type, db)
                db.commit()
                return {
                    "ok": True,
                    "event_id": event.id,
                    "type": event.type,
                    "reason": "no_user_id",
                }

            # Handle dispute status changes
            plugin_id = metadata.get("plugin_id")
            if plugin_id and status in ["lost", "warning_closed"]:
                # Revoke access on lost disputes
                purchase = (
                    db.query(MarketplacePurchase)
                    .filter(
                        MarketplacePurchase.user_id == user_uuid,
                        MarketplacePurchase.item_id == plugin_id,
                        MarketplacePurchase.status == "active",
                    )
                    .first()
                )

                if purchase:
                    purchase.status = "disputed_lost"
                    purchase.purchase_metadata = purchase.purchase_metadata or {}
                    purchase.purchase_metadata["dispute_id"] = dispute_id
                    purchase.purchase_metadata["dispute_reason"] = reason
                    purchase.purchase_metadata["dispute_status"] = status
                    purchase.purchase_metadata["dispute_timestamp"] = datetime.utcnow().isoformat()

            self._log_audit_event(
                event.type,
                event.id,
                user_uuid,
                f"dispute_{status}",
                {
                    "dispute_id": dispute_id,
                    "charge_id": charge_id,
                    "status": status,
                    "reason": reason,
                    "amount": amount,
                    "currency": currency,
                },
            )

            self._record_idempotency(event.id, event.type, db)
            db.commit()

            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "processed": True,
                "dispute_id": dispute_id,
                "status": status,
                "user_id": str(user_uuid) if user_uuid else None,
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing dispute event {event.id}: {e}", exc_info=True)
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass


class PaymentFailureHandler(StripeEventHandler):
    """Handler for payment_intent.payment_failed events."""

    def handle(self, event: WebhookEvent, payload: bytes) -> dict[str, Any]:
        raw_evt = json.loads(payload.decode("utf-8"))
        obj = (raw_evt.get("data") or {}).get("object") or {}

        payment_intent_id = obj.get("id") if isinstance(obj, dict) else None
        amount = obj.get("amount", 0)
        currency = obj.get("currency", "usd")
        last_error = obj.get("last_payment_error")

        # Extract error message, handling None and empty dict
        if last_error and isinstance(last_error, dict):
            error_message = last_error.get("message", "Unknown")
        else:
            error_message = "Unknown"

        metadata = self._extract_metadata(obj)

        db = get_session_factory()()
        try:
            # Check idempotency
            if self._check_idempotency(event.id, db):
                return {
                    "ok": True,
                    "event_id": event.id,
                    "type": event.type,
                    "already_processed": True,
                }

            stripe_customer_id = obj.get("customer") if isinstance(obj, dict) else None
            user_id_str = self._resolve_user_id(metadata, stripe_customer_id)
            user_uuid = self._parse_user_uuid(user_id_str)

            self._log_audit_event(
                event.type,
                event.id,
                user_uuid,
                "payment_failed",
                {
                    "payment_intent_id": payment_intent_id,
                    "amount": amount,
                    "currency": currency,
                    "error": error_message,
                },
            )

            self._record_idempotency(event.id, event.type, db)
            db.commit()

            return {
                "ok": True,
                "event_id": event.id,
                "type": event.type,
                "processed": True,
                "payment_intent_id": payment_intent_id,
                "error": error_message,
                "user_id": str(user_uuid) if user_uuid else None,
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing payment failure event {event.id}: {e}", exc_info=True)
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass


HANDLERS: dict[str, StripeEventHandler] = {
    "customer.subscription.created": SubscriptionEventHandler(),
    "customer.subscription.updated": SubscriptionEventHandler(),
    "customer.subscription.deleted": SubscriptionEventHandler(),
    "checkout.session.completed": CheckoutSessionEventHandler(),
    "charge.refunded": RefundEventHandler(),
    "charge.dispute.created": DisputeEventHandler(),
    "charge.dispute.updated": DisputeEventHandler(),
    "charge.dispute.closed": DisputeEventHandler(),
    "payment_intent.payment_failed": PaymentFailureHandler(),
}


def get_handler(event_type: str) -> StripeEventHandler:
    """Get appropriate handler for event type.

    Args:
        event_type: Stripe event type (e.g., "customer.subscription.updated")

    Returns:
        Handler instance for the event type
    """
    return HANDLERS.get(event_type, DefaultEventHandler())
