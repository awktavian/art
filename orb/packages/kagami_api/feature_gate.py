from __future__ import annotations

"""Feature gating middleware and dependencies for subscription tiers.

Enforces feature access based on user's subscription tier.
"""
import logging
from typing import Any

from fastapi import Depends, HTTPException, Request
from kagami.core.database.connection import get_db
from kagami.core.database.models import TenantPlan
from sqlalchemy.orm import Session

from kagami_api.routes.user.auth import get_current_user
from kagami_api.subscription_tiers import (
    SubscriptionTier,
    get_tier_config,
    has_feature,
    map_stripe_plan_to_tier,
)

logger = logging.getLogger(__name__)


async def get_user_tier(
    user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionTier:
    """Get the subscription tier for the current user.

    Args:
        user: Current authenticated user
        db: Database session

    Returns:
        User's subscription tier, defaults to FREE
    """
    # Resolve user ID
    user_id = None
    if isinstance(user, dict):
        try:
            user_id = int(user.get("user_id", 0))
        except (ValueError, TypeError):
            pass

    if not user_id:
        return SubscriptionTier.FREE

    try:
        # Get latest plan for user
        plan = (
            db.query(TenantPlan)
            .filter(TenantPlan.user_id == user_id)
            .order_by(TenantPlan.valid_from.desc())
            .first()
        )

        if plan and plan.plan_name:
            return map_stripe_plan_to_tier(plan.plan_name)  # type: ignore[arg-type]
    except Exception as e:
        logger.warning(f"Failed to get user tier: {e}")

    return SubscriptionTier.FREE


def require_feature(feature: str) -> None:
    """Dependency that requires a specific feature flag.

    Usage:
        @router.get("/enterprise-only", dependencies=[Depends(require_feature("sso_saml"))])  # noqa: B008
        async def enterprise_endpoint():
            ...

    Args:
        feature: Feature flag name from TierLimits.features

    Raises:
        HTTPException: 403 if user's tier doesn't have the feature
    """

    async def _check_feature(tier: SubscriptionTier = Depends(get_user_tier)) -> bool:
        if not has_feature(tier, feature):
            config = get_tier_config(tier)
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_not_available",
                    "feature": feature,
                    "current_tier": config.name,
                    "required_tiers": _get_tiers_with_feature(feature),
                    "upgrade_url": "/api/billing/upgrade",
                },
            )
        return True

    return _check_feature  # type: ignore[return-value]


def require_tier(minimum_tier: SubscriptionTier) -> None:
    """Dependency that requires a minimum subscription tier.

    Usage:
        @router.get("/pro-only", dependencies=[Depends(require_tier(SubscriptionTier.PRO))])  # noqa: B008
        async def pro_endpoint():
            ...

    Args:
        minimum_tier: Minimum required tier

    Raises:
        HTTPException: 403 if user's tier is below minimum
    """
    # Tier hierarchy
    tier_order = [
        SubscriptionTier.FREE,
        SubscriptionTier.PERSONAL,
        SubscriptionTier.FAMILY,
        SubscriptionTier.POWER,
    ]

    async def _check_tier(tier: SubscriptionTier = Depends(get_user_tier)) -> bool:
        user_tier_level = tier_order.index(tier) if tier in tier_order else 0
        required_level = tier_order.index(minimum_tier) if minimum_tier in tier_order else 0

        if user_tier_level < required_level:
            config = get_tier_config(tier)
            required_config = get_tier_config(minimum_tier)
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "tier_insufficient",
                    "current_tier": config.name,
                    "required_tier": required_config.name,
                    "upgrade_url": "/api/billing/upgrade",
                },
            )
        return True

    return _check_tier  # type: ignore[return-value]


def _get_tiers_with_feature(feature: str) -> list[str]:
    """Get list of tier names that have a specific feature."""
    from kagami_api.subscription_tiers import TIER_CONFIGS

    tiers = []
    for _tier, config in TIER_CONFIGS.items():
        if feature in config.features:
            tiers.append(config.name)
    return tiers


async def feature_gate_middleware(request: Request, call_next: Any) -> None:
    """Middleware to attach tier information to request state.

    Adds request.state.subscription_tier for easy access in handlers.
    """
    # Skip for public endpoints
    path = str(request.url.path)
    if (
        path.startswith("/metrics")
        or path.startswith("/health")
        or path.startswith("/static")
        or path.startswith("/docs")
        or path.startswith("/openapi.json")
    ):
        return await call_next(request)  # type: ignore[no-any-return]

    # Try to resolve tier and attach to state
    try:
        # Simple auth resolution (best-effort, no exceptions)
        user = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            try:
                from kagami_api.security import get_token_manager

                token = auth_header.split(" ", 1)[1].strip()
                tm = get_token_manager()
                user = tm.verify_token(token) if tm else None
            except Exception:
                pass

        if user:
            from kagami.core.database.connection import SessionLocal  # type: ignore[attr-defined]

            db = SessionLocal()
            try:
                user_id = None
                if hasattr(user, "sub"):
                    try:
                        user_id = int(user.sub)
                    except (ValueError, TypeError):
                        pass

                if user_id:
                    plan = (
                        db.query(TenantPlan)
                        .filter(TenantPlan.user_id == user_id)
                        .order_by(TenantPlan.valid_from.desc())
                        .first()
                    )

                    if plan and plan.plan_name:
                        tier = map_stripe_plan_to_tier(plan.plan_name)

                        request.state.subscription_tier = tier
            finally:
                db.close()
    except Exception as e:
        logger.debug(f"Feature gate middleware tier resolution failed: {e}")

    # Set default if not resolved
    if not hasattr(request.state, "subscription_tier"):
        request.state.subscription_tier = SubscriptionTier.FREE

    return await call_next(request)  # type: ignore[no-any-return]


__all__ = [
    "feature_gate_middleware",
    "get_user_tier",
    "require_feature",
    "require_tier",
]
