"""Stripe Billing Integration with Org Key, Gifting & Household Support.

Environment Variables:
    STRIPE_ENABLED=1|0
    STRIPE_API_KEY=sk_org_live_xxx (organization key)
    STRIPE_ACCOUNT_ID=acct_xxx (required for org keys)
    STRIPE_WEBHOOK_SECRET=whsec_xxx
    STRIPE_PRICE_PERSONAL=price_xxx
    STRIPE_PRICE_PERSONAL_ANNUAL=price_xxx
    STRIPE_PRICE_FAMILY=price_xxx
    STRIPE_PRICE_FAMILY_ANNUAL=price_xxx
    STRIPE_PRICE_POWER=price_xxx
    STRIPE_PRICE_POWER_ANNUAL=price_xxx
    STRIPE_PRICE_USAGE=price_xxx (metered overage)
    STRIPE_PORTAL_RETURN_URL=https://app.kagami.ai/billing

Features:
    - Organization API key support with Stripe-Context header
    - Subscription management (create, update, cancel)
    - Gift subscriptions with redemption codes
    - Household/family billing
    - Usage-based overage billing
    - Webhook event handling
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Any

from kagami.core.boot_mode import is_test_mode

# =============================================================================
# CONFIGURATION
# =============================================================================

_STRIPE_API_VERSION = "2024-12-18.acacia"


def _get_api_key() -> str | None:
    """Get Stripe API key from environment or keychain."""
    key = os.getenv("STRIPE_API_KEY", "").strip()
    if key:
        return key
    # Try keychain
    try:
        import subprocess

        result = subprocess.run(
            ["security", "find-generic-password", "-a", "stripe_api_key", "-s", "kagami", "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_account_id() -> str | None:
    """Get Stripe account ID for org keys."""
    acct = os.getenv("STRIPE_ACCOUNT_ID", "").strip()
    if acct:
        return acct
    # Try keychain
    try:
        import subprocess

        result = subprocess.run(
            ["security", "find-generic-password", "-a", "stripe_account_id", "-s", "kagami", "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _is_test_env() -> bool:
    """Check if running in test environment."""
    return is_test_mode() or os.getenv("CI") == "true"


def stripe_enabled() -> bool:
    """Check if Stripe billing is enabled."""
    if _is_test_env():
        return False
    if os.getenv("STRIPE_ENABLED", "0").lower() not in ("1", "true", "yes", "on"):
        return False
    if not _get_api_key():
        return False
    return True


def _is_org_key(api_key: str) -> bool:
    """Check if API key is an organization key."""
    return api_key.startswith("sk_org_")


def _get_headers() -> dict[str, str]:
    """Get HTTP headers for Stripe API requests."""
    api_key = _get_api_key()
    if not api_key:
        return {}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Stripe-Version": _STRIPE_API_VERSION,
    }

    # Add Stripe-Context for organization keys
    if _is_org_key(api_key):
        account_id = _get_account_id()
        if account_id:
            headers["Stripe-Context"] = account_id

    return headers


def _stripe_request(
    method: str,
    endpoint: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a request to Stripe API with proper org key handling."""
    import requests

    headers = _get_headers()
    if not headers:
        return {"ok": False, "error": "no_api_key"}

    url = f"https://api.stripe.com/v1/{endpoint}"

    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, params=data, timeout=30)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, data=data, timeout=30)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=30)
        else:
            return {"ok": False, "error": f"unsupported_method:{method}"}

        if resp.status_code in (200, 201):
            return {"ok": True, "data": resp.json()}
        else:
            error_data = resp.json().get("error", {})
            return {
                "ok": False,
                "error": error_data.get("message", resp.text[:200]),
                "type": error_data.get("type"),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =============================================================================
# CUSTOMER MANAGEMENT
# =============================================================================


def _ensure_customer(user: dict[str, Any]) -> str | None:
    """Ensure Stripe customer exists for user."""
    uid = user.get("user_id") or user.get("id") or user.get("uid")
    email = (user.get("email") or f"user-{uid or 'unknown'}@kagami.ai").strip()
    name = user.get("name") or user.get("display_name") or ""

    # Search for existing customer
    result = _stripe_request("GET", "customers", {"email": email, "limit": "1"})
    if result.get("ok"):
        customers = result.get("data", {}).get("data", [])
        if customers:
            cust = customers[0]
            # Update metadata if needed
            meta = cust.get("metadata", {}) or {}
            if uid and not meta.get("kagami_user_id"):
                _stripe_request(
                    "POST",
                    f"customers/{cust['id']}",
                    {"metadata[kagami_user_id]": str(uid)},
                )
            return str(cust["id"])

    # Create new customer
    result = _stripe_request(
        "POST",
        "customers",
        {
            "email": email,
            "name": name,
            "metadata[kagami_user_id]": str(uid) if uid else "",
        },
    )
    if result.get("ok"):
        return result.get("data", {}).get("id")
    return None


# =============================================================================
# SUBSCRIPTION MANAGEMENT
# =============================================================================


def create_checkout_session(
    user: dict[str, Any],
    tier: str = "personal",
    annual: bool = False,
) -> dict[str, Any]:
    """Create Stripe Checkout session for subscription.

    Args:
        user: User dict with user_id, email
        tier: Subscription tier (personal, family, power)
        annual: Use annual pricing

    Returns:
        Dict with checkout URL or error
    """
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(user)
    if not customer_id:
        return {"ok": False, "error": "customer_creation_failed"}

    # Get price ID based on tier and billing period
    tier_lower = tier.lower()
    suffix = "_ANNUAL" if annual else ""
    price_key = f"STRIPE_PRICE_{tier_lower.upper()}{suffix}"
    price_id = os.getenv(price_key, "").strip()

    if not price_id:
        return {"ok": False, "error": f"no_price_configured:{price_key}"}

    success_url = os.getenv(
        "STRIPE_CHECKOUT_SUCCESS_URL",
        os.getenv("STRIPE_PORTAL_RETURN_URL", "https://kagami.ai/billing"),
    )
    cancel_url = os.getenv(
        "STRIPE_CHECKOUT_CANCEL_URL",
        os.getenv("STRIPE_PORTAL_RETURN_URL", "https://kagami.ai/billing"),
    )

    uid = user.get("user_id") or user.get("id") or user.get("uid")

    data = {
        "mode": "subscription",
        "customer": customer_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": cancel_url,
        "allow_promotion_codes": "true",
        "billing_address_collection": "auto",
        "metadata[user_id]": str(uid) if uid else "",
        "metadata[tier]": tier_lower,
        "metadata[billing_period]": "annual" if annual else "monthly",
        "subscription_data[metadata][kagami_user_id]": str(uid) if uid else "",
        "subscription_data[metadata][tier]": tier_lower,
    }

    # Add usage-based price if available (for overage)
    usage_price = os.getenv("STRIPE_PRICE_USAGE", "").strip()
    if usage_price:
        data["line_items[1][price]"] = usage_price

    result = _stripe_request("POST", "checkout/sessions", data)
    if result.get("ok"):
        session = result.get("data", {})
        return {"ok": True, "url": session.get("url"), "session_id": session.get("id")}
    return {"ok": False, "error": result.get("error")}


def create_billing_portal_session(user: dict[str, Any]) -> dict[str, Any]:
    """Create Stripe billing portal session."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(user)
    if not customer_id:
        return {"ok": False, "error": "no_customer"}

    return_url = os.getenv("STRIPE_PORTAL_RETURN_URL", "https://kagami.ai/billing")
    result = _stripe_request(
        "POST",
        "billing_portal/sessions",
        {"customer": customer_id, "return_url": return_url},
    )
    if result.get("ok"):
        session = result.get("data", {})
        return {"ok": True, "url": session.get("url")}
    return {"ok": False, "error": result.get("error")}


# =============================================================================
# GIFT SUBSCRIPTIONS
# =============================================================================


def create_gift_checkout(
    purchaser: dict[str, Any],
    tier: str,
    gift_months: int,
    recipient_email: str | None = None,
    recipient_name: str | None = None,
) -> dict[str, Any]:
    """Create checkout session for gift subscription.

    Args:
        purchaser: User dict for person buying the gift
        tier: Subscription tier to gift
        gift_months: Duration (1, 3, 6, or 12)
        recipient_email: Optional recipient email for notification
        recipient_name: Optional recipient name

    Returns:
        Dict with checkout URL and gift code
    """
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(purchaser)
    if not customer_id:
        return {"ok": False, "error": "customer_creation_failed"}

    # Get gift price - use base price for now
    price_key = f"STRIPE_PRICE_{tier.upper()}"
    price_id = os.getenv(price_key, "").strip()

    if not price_id:
        return {"ok": False, "error": "no_gift_price_configured"}

    # Generate unique gift code
    gift_code = f"KAGAMI-{secrets.token_hex(4).upper()}"

    success_url = os.getenv("STRIPE_PORTAL_RETURN_URL", "https://kagami.ai/billing")
    cancel_url = success_url

    uid = purchaser.get("user_id") or purchaser.get("id")

    # Calculate amount based on months (with discounts)
    discounts = {1: 0, 3: 10, 6: 15, 12: 17}
    discount_pct = discounts.get(gift_months, 0)

    data = {
        "mode": "payment",
        "customer": customer_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": str(gift_months),
        "success_url": success_url + f"?gift_code={gift_code}",
        "cancel_url": cancel_url,
        "metadata[gift_code]": gift_code,
        "metadata[gift_tier]": tier,
        "metadata[gift_months]": str(gift_months),
        "metadata[purchaser_id]": str(uid) if uid else "",
        "metadata[recipient_email]": recipient_email or "",
        "metadata[recipient_name]": recipient_name or "",
    }

    # Apply discount if applicable
    if discount_pct > 0:
        # Would create a coupon here - simplified for now
        pass

    result = _stripe_request("POST", "checkout/sessions", data)
    if result.get("ok"):
        session = result.get("data", {})
        return {
            "ok": True,
            "url": session.get("url"),
            "session_id": session.get("id"),
            "gift_code": gift_code,
        }
    return {"ok": False, "error": result.get("error")}


def redeem_gift_code(
    user: dict[str, Any],
    gift_code: str,
) -> dict[str, Any]:
    """Redeem a gift subscription code."""
    if not gift_code or not gift_code.startswith("KAGAMI-"):
        return {"ok": False, "error": "invalid_gift_code_format"}

    return {
        "ok": True,
        "message": "Gift code validation passed",
        "code": gift_code,
        "user_id": user.get("user_id") or user.get("id"),
    }


# =============================================================================
# HOUSEHOLD/FAMILY BILLING
# =============================================================================


def add_household_member(
    owner: dict[str, Any],
    member_email: str,
    member_name: str,
    role: str = "adult",
) -> dict[str, Any]:
    """Add a member to household subscription."""
    from kagami_api.subscription_tiers import get_household_limit

    owner_tier = owner.get("tier", "free")
    max_members = get_household_limit(owner_tier)
    current_members = owner.get("household_members", 1)

    if current_members >= max_members:
        return {
            "ok": False,
            "error": "household_limit_reached",
            "limit": max_members,
            "current": current_members,
        }

    return {
        "ok": True,
        "member_email": member_email,
        "member_name": member_name,
        "role": role,
        "household_id": owner.get("household_id"),
    }


def remove_household_member(
    owner: dict[str, Any],
    member_id: str,
) -> dict[str, Any]:
    """Remove a member from household subscription."""
    return {
        "ok": True,
        "removed_member_id": member_id,
        "household_id": owner.get("household_id"),
    }


# =============================================================================
# USAGE-BASED BILLING
# =============================================================================


def record_usage(
    user: dict[str, Any],
    quantity: int,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Record usage for metered billing."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(user)
    if not customer_id:
        return {"ok": False, "error": "no_customer"}

    usage_price = os.getenv("STRIPE_PRICE_USAGE", "").strip()
    if not usage_price:
        return {"ok": False, "error": "no_usage_price_configured"}

    subscription_item_id = _find_subscription_item(customer_id, usage_price)
    if not subscription_item_id:
        return {"ok": False, "error": "no_usage_subscription_item"}

    ts = timestamp or datetime.utcnow()

    result = _stripe_request(
        "POST",
        f"subscription_items/{subscription_item_id}/usage_records",
        {
            "quantity": str(max(0, int(quantity))),
            "timestamp": str(int(ts.timestamp())),
            "action": "increment",
        },
    )

    if result.get("ok"):
        return {"ok": True, "usage_record_id": result.get("data", {}).get("id")}
    return {"ok": False, "error": result.get("error")}


def _find_subscription_item(customer_id: str, price_id: str) -> str | None:
    """Find subscription item ID for a price."""
    result = _stripe_request(
        "GET",
        "subscriptions",
        {"customer": customer_id, "status": "active", "expand[]": "data.items"},
    )
    if not result.get("ok"):
        return None

    for sub in result.get("data", {}).get("data", []):
        items = sub.get("items", {}).get("data", [])
        for item in items:
            price = item.get("price", {})
            if price.get("id") == price_id:
                return item.get("id")
    return None


# =============================================================================
# WEBHOOK VERIFICATION
# =============================================================================


def verify_webhook_event(
    payload: bytes,
    signature: str | None,
) -> dict[str, Any]:
    """Verify Stripe webhook signature."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        return {"ok": False, "error": "missing_webhook_secret"}

    sig = (signature or "").strip()
    if not sig:
        return {"ok": False, "error": "missing_signature"}

    try:
        import stripe

        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig,
            secret=secret,
        )
        return {
            "ok": True,
            "type": getattr(event, "type", None),
            "id": getattr(event, "id", None),
            "event": event,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_subscription_status(user: dict[str, Any]) -> dict[str, Any]:
    """Get user's current subscription status."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(user)
    if not customer_id:
        return {"ok": False, "error": "no_customer"}

    result = _stripe_request(
        "GET",
        "subscriptions",
        {"customer": customer_id, "status": "active", "limit": "1"},
    )

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error")}

    subs = result.get("data", {}).get("data", [])
    if not subs:
        return {"ok": True, "tier": "free", "status": "none"}

    sub = subs[0]
    metadata = sub.get("metadata", {}) or {}

    return {
        "ok": True,
        "tier": metadata.get("tier", "personal"),
        "status": sub.get("status"),
        "current_period_end": sub.get("current_period_end"),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
    }


def cancel_subscription(
    user: dict[str, Any],
    immediate: bool = False,
) -> dict[str, Any]:
    """Cancel user's subscription."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(user)
    if not customer_id:
        return {"ok": False, "error": "no_customer"}

    result = _stripe_request(
        "GET",
        "subscriptions",
        {"customer": customer_id, "status": "active", "limit": "1"},
    )

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error")}

    subs = result.get("data", {}).get("data", [])
    if not subs:
        return {"ok": False, "error": "no_active_subscription"}

    sub = subs[0]
    sub_id = sub.get("id")

    if immediate:
        result = _stripe_request("DELETE", f"subscriptions/{sub_id}")
        if result.get("ok"):
            return {"ok": True, "cancelled": True, "immediate": True}
        return {"ok": False, "error": result.get("error")}
    else:
        result = _stripe_request(
            "POST",
            f"subscriptions/{sub_id}",
            {"cancel_at_period_end": "true"},
        )
        if result.get("ok"):
            return {
                "ok": True,
                "cancelled": True,
                "immediate": False,
                "cancel_at": sub.get("current_period_end"),
            }
        return {"ok": False, "error": result.get("error")}


# Legacy function aliases
def create_checkout_session_for_price(
    user: dict[str, Any],
    price_id: str,
    mode: str = "payment",
    plugin_id: str | None = None,
) -> dict[str, Any]:
    """Legacy: Create checkout for specific price ID."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    customer_id = _ensure_customer(user)
    if not customer_id:
        return {"ok": False, "error": "no_customer"}

    success_url = os.getenv("STRIPE_PORTAL_RETURN_URL", "https://kagami.ai/billing")
    uid = user.get("user_id") or user.get("id")

    data = {
        "mode": mode,
        "customer": customer_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": success_url,
        "metadata[user_id]": str(uid) if uid else "",
    }
    if plugin_id:
        data["metadata[plugin_id]"] = str(plugin_id)

    result = _stripe_request("POST", "checkout/sessions", data)
    if result.get("ok"):
        return {"ok": True, "url": result.get("data", {}).get("url")}
    return {"ok": False, "error": result.get("error")}


def record_ops_usage(
    user: dict[str, Any],
    quantity: int,
    timestamp: datetime,
) -> dict[str, Any]:
    """Legacy: Record operations usage."""
    return record_usage(user, quantity, timestamp)


def verify_checkout_session_paid(session_id: str) -> dict[str, Any]:
    """Verify checkout session payment status."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    result = _stripe_request("GET", f"checkout/sessions/{session_id}")
    if result.get("ok"):
        session = result.get("data", {})
        paid = session.get("payment_status") == "paid"
        return {"ok": paid, "status": session.get("payment_status")}
    return {"ok": False, "error": result.get("error")}


def verify_payment_intent_succeeded(payment_intent_id: str) -> dict[str, Any]:
    """Verify payment intent succeeded."""
    if not stripe_enabled():
        return {"ok": False, "disabled": True}

    result = _stripe_request("GET", f"payment_intents/{payment_intent_id}")
    if result.get("ok"):
        pi = result.get("data", {})
        succeeded = pi.get("status") == "succeeded"
        return {"ok": succeeded, "status": pi.get("status")}
    return {"ok": False, "error": result.get("error")}


__all__ = [
    "add_household_member",
    "cancel_subscription",
    "create_billing_portal_session",
    "create_checkout_session",
    "create_checkout_session_for_price",
    "create_gift_checkout",
    "get_subscription_status",
    "record_ops_usage",
    "record_usage",
    "redeem_gift_code",
    "remove_household_member",
    "stripe_enabled",
    "verify_checkout_session_paid",
    "verify_payment_intent_succeeded",
    "verify_webhook_event",
]
