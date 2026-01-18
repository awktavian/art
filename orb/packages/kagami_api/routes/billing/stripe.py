"""Stripe Billing API Routes.

Endpoints for subscription management, gifting, and household billing.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from kagami_api.routes.user.auth import get_current_user


def get_router() -> APIRouter:
    """Create billing router with all Stripe endpoints."""
    router = APIRouter(tags=["billing"])

    # ==========================================================================
    # REQUEST/RESPONSE MODELS
    # ==========================================================================

    class CheckoutRequest(BaseModel):
        tier: str = "personal"
        annual: bool = False

    class CheckoutResponse(BaseModel):
        ok: bool
        url: str | None = None
        session_id: str | None = None
        error: str | None = None
        disabled: bool = False

    class GiftCheckoutRequest(BaseModel):
        tier: str = "personal"
        months: int = 1  # 1, 3, 6, or 12
        recipient_email: EmailStr | None = None
        recipient_name: str | None = None

    class GiftCheckoutResponse(BaseModel):
        ok: bool
        url: str | None = None
        session_id: str | None = None
        gift_code: str | None = None
        error: str | None = None

    class RedeemGiftRequest(BaseModel):
        gift_code: str

    class HouseholdMemberRequest(BaseModel):
        email: EmailStr
        name: str
        role: str = "adult"  # adult, child, guest

    class SubscriptionStatusResponse(BaseModel):
        ok: bool
        tier: str | None = None
        status: str | None = None
        current_period_end: int | None = None
        cancel_at_period_end: bool = False
        error: str | None = None

    class PricingResponse(BaseModel):
        tiers: list[dict[str, Any]]
        gifts: list[dict[str, Any]]
        overage: dict[str, str]

    # ==========================================================================
    # WEBHOOK ENDPOINT
    # ==========================================================================

    @router.post("/webhook")
    async def stripe_webhook(request: Request) -> dict[str, Any]:
        """Handle Stripe webhook events."""
        from kagami_integrations.stripe_billing import (
            stripe_enabled,
            verify_webhook_event,
        )

        if not stripe_enabled():
            return {"ok": True, "disabled": True}

        payload = await request.body()
        sig = (
            request.headers.get("Stripe-Signature")
            or request.headers.get("stripe-signature")
        )

        verified = verify_webhook_event(payload=payload, signature=sig)
        if not verified.get("ok"):
            if verified.get("disabled"):
                return {"ok": True, "disabled": True}
            raise HTTPException(
                status_code=400,
                detail=verified.get("error") or "invalid_webhook",
            )

        # Dispatch to handler
        from kagami_api.routes.billing.stripe_handlers import get_handler

        event_type = verified.get("type", "")
        event_id = verified.get("id", "")

        class _Event:
            def __init__(self, eid: str, etype: str) -> None:
                self.id = eid
                self.type = etype
                self.data: dict[str, Any] = {}

        handler = get_handler(event_type)
        return handler.handle(_Event(event_id, event_type), payload)

    # ==========================================================================
    # SUBSCRIPTION ENDPOINTS
    # ==========================================================================

    @router.post("/checkout", response_model=CheckoutResponse)
    async def create_checkout(
        payload: CheckoutRequest,
        user: Any = Depends(get_current_user),
    ) -> CheckoutResponse:
        """Create subscription checkout session."""
        from kagami_integrations.stripe_billing import (
            create_checkout_session,
            stripe_enabled,
        )

        if not stripe_enabled():
            return CheckoutResponse(ok=False, disabled=True)

        result = create_checkout_session(
            user=user if isinstance(user, dict) else {},
            tier=payload.tier,
            annual=payload.annual,
        )

        return CheckoutResponse(**result)

    @router.post("/portal")
    async def create_portal(
        user: Any = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Create billing portal session."""
        from kagami_integrations.stripe_billing import (
            create_billing_portal_session,
            stripe_enabled,
        )

        if not stripe_enabled():
            return {"ok": False, "disabled": True}

        result = create_billing_portal_session(
            user=user if isinstance(user, dict) else {}
        )

        if not result.get("ok"):
            raise HTTPException(
                status_code=503,
                detail=result.get("error") or "stripe_unavailable",
            )

        return result

    @router.get("/status", response_model=SubscriptionStatusResponse)
    async def get_status(
        user: Any = Depends(get_current_user),
    ) -> SubscriptionStatusResponse:
        """Get current subscription status."""
        from kagami_integrations.stripe_billing import (
            get_subscription_status,
            stripe_enabled,
        )

        if not stripe_enabled():
            return SubscriptionStatusResponse(
                ok=True,
                tier="free",
                status="disabled",
            )

        result = get_subscription_status(
            user=user if isinstance(user, dict) else {}
        )

        return SubscriptionStatusResponse(**result)

    @router.post("/cancel")
    async def cancel_subscription(
        immediate: bool = False,
        user: Any = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Cancel subscription."""
        from kagami_integrations.stripe_billing import (
            cancel_subscription as do_cancel,
        )
        from kagami_integrations.stripe_billing import (
            stripe_enabled,
        )

        if not stripe_enabled():
            return {"ok": False, "disabled": True}

        return do_cancel(
            user=user if isinstance(user, dict) else {},
            immediate=immediate,
        )

    # ==========================================================================
    # GIFT ENDPOINTS
    # ==========================================================================

    @router.post("/gift/checkout", response_model=GiftCheckoutResponse)
    async def create_gift_checkout(
        payload: GiftCheckoutRequest,
        user: Any = Depends(get_current_user),
    ) -> GiftCheckoutResponse:
        """Create gift subscription checkout."""
        from kagami_integrations.stripe_billing import (
            create_gift_checkout as do_gift,
        )
        from kagami_integrations.stripe_billing import (
            stripe_enabled,
        )

        if not stripe_enabled():
            return GiftCheckoutResponse(ok=False, error="disabled")

        if payload.months not in (1, 3, 6, 12):
            return GiftCheckoutResponse(
                ok=False,
                error="invalid_gift_duration",
            )

        result = do_gift(
            purchaser=user if isinstance(user, dict) else {},
            tier=payload.tier,
            gift_months=payload.months,
            recipient_email=payload.recipient_email,
            recipient_name=payload.recipient_name,
        )

        return GiftCheckoutResponse(**result)

    @router.post("/gift/redeem")
    async def redeem_gift(
        payload: RedeemGiftRequest,
        user: Any = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Redeem a gift subscription code."""
        from kagami_integrations.stripe_billing import (
            redeem_gift_code,
            stripe_enabled,
        )

        if not stripe_enabled():
            return {"ok": False, "disabled": True}

        return redeem_gift_code(
            user=user if isinstance(user, dict) else {},
            gift_code=payload.gift_code,
        )

    # ==========================================================================
    # HOUSEHOLD ENDPOINTS
    # ==========================================================================

    @router.post("/household/member")
    async def add_member(
        payload: HouseholdMemberRequest,
        user: Any = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Add a member to household subscription."""
        from kagami_integrations.stripe_billing import (
            add_household_member,
            stripe_enabled,
        )

        if not stripe_enabled():
            return {"ok": False, "disabled": True}

        return add_household_member(
            owner=user if isinstance(user, dict) else {},
            member_email=payload.email,
            member_name=payload.name,
            role=payload.role,
        )

    @router.delete("/household/member/{member_id}")
    async def remove_member(
        member_id: str,
        user: Any = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Remove a member from household subscription."""
        from kagami_integrations.stripe_billing import (
            remove_household_member,
            stripe_enabled,
        )

        if not stripe_enabled():
            return {"ok": False, "disabled": True}

        return remove_household_member(
            owner=user if isinstance(user, dict) else {},
            member_id=member_id,
        )

    # ==========================================================================
    # PRICING ENDPOINT
    # ==========================================================================

    @router.get("/pricing", response_model=PricingResponse)
    async def get_pricing() -> PricingResponse:
        """Get pricing information (public endpoint)."""
        from kagami_api.subscription_tiers import get_pricing_summary

        return PricingResponse(**get_pricing_summary())

    return router
