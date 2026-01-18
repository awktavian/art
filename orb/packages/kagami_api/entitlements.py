"""Entitlements — Feature Access Control by Subscription Tier.

Provides decorators and utilities for enforcing feature entitlements
based on user subscription tier (free, pro, enterprise).

Usage:
    from kagami_api.entitlements import require_entitlement, Entitlement

    @router.get("/advanced-feature")
    @require_entitlement(Entitlement.ADVANCED_ANALYTICS)
    async def advanced_feature(user = Depends(get_current_user)):
        return {"feature": "enabled"}

Colony: Crystal (D₅) — Verification
h(x) ≥ 0. Privacy IS safety.

Created: January 2026
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

from fastapi import Depends, HTTPException, status

from kagami_api.auth import get_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# Entitlement Definitions
# =============================================================================


class Entitlement(Enum):
    """Feature entitlements by subscription tier.

    Tiers:
    - free: Basic features only
    - pro: All free + biometric, recognition, multi-device
    - enterprise: All pro + analytics, audit export, SSO, branding
    """

    # Free tier
    BASIC_PRESENCE = "basic_presence"
    BASIC_AUTOMATION = "basic_automation"
    BASIC_VOICE = "basic_voice"

    # Pro tier
    BIOMETRIC_AUTH = "biometric_auth"
    FACE_RECOGNITION = "face_recognition"
    VOICE_RECOGNITION = "voice_recognition"
    MULTI_DEVICE = "multi_device"
    ADVANCED_AUTOMATION = "advanced_automation"
    VOICE_CLONING = "voice_cloning"

    # Enterprise tier
    ADVANCED_ANALYTICS = "advanced_analytics"
    AUDIT_EXPORT = "audit_export"
    SSO_INTEGRATION = "sso_integration"
    CUSTOM_BRANDING = "custom_branding"
    MULTI_TENANT = "multi_tenant"
    DEDICATED_SUPPORT = "dedicated_support"


# Entitlements by subscription tier
TIER_ENTITLEMENTS: dict[str, set[Entitlement]] = {
    "free": {
        Entitlement.BASIC_PRESENCE,
        Entitlement.BASIC_AUTOMATION,
        Entitlement.BASIC_VOICE,
    },
    "personal": {
        # Free tier
        Entitlement.BASIC_PRESENCE,
        Entitlement.BASIC_AUTOMATION,
        Entitlement.BASIC_VOICE,
        # Personal tier
        Entitlement.BIOMETRIC_AUTH,
        Entitlement.FACE_RECOGNITION,
        Entitlement.VOICE_RECOGNITION,
        Entitlement.MULTI_DEVICE,
        Entitlement.ADVANCED_AUTOMATION,
        Entitlement.VOICE_CLONING,
    },
    "family": {
        # Free tier
        Entitlement.BASIC_PRESENCE,
        Entitlement.BASIC_AUTOMATION,
        Entitlement.BASIC_VOICE,
        # Personal tier
        Entitlement.BIOMETRIC_AUTH,
        Entitlement.FACE_RECOGNITION,
        Entitlement.VOICE_RECOGNITION,
        Entitlement.MULTI_DEVICE,
        Entitlement.ADVANCED_AUTOMATION,
        Entitlement.VOICE_CLONING,
        # Family tier (same as personal for now)
    },
    "power": {
        # Free tier
        Entitlement.BASIC_PRESENCE,
        Entitlement.BASIC_AUTOMATION,
        Entitlement.BASIC_VOICE,
        # Personal tier
        Entitlement.BIOMETRIC_AUTH,
        Entitlement.FACE_RECOGNITION,
        Entitlement.VOICE_RECOGNITION,
        Entitlement.MULTI_DEVICE,
        Entitlement.ADVANCED_AUTOMATION,
        Entitlement.VOICE_CLONING,
        # Power tier
        Entitlement.ADVANCED_ANALYTICS,
        Entitlement.AUDIT_EXPORT,
        Entitlement.SSO_INTEGRATION,
        Entitlement.CUSTOM_BRANDING,
        Entitlement.MULTI_TENANT,
        Entitlement.DEDICATED_SUPPORT,
    },
}

# Minimum tier required for each entitlement
ENTITLEMENT_MIN_TIER: dict[Entitlement, str] = {
    # Free
    Entitlement.BASIC_PRESENCE: "free",
    Entitlement.BASIC_AUTOMATION: "free",
    Entitlement.BASIC_VOICE: "free",
    # Personal
    Entitlement.BIOMETRIC_AUTH: "personal",
    Entitlement.FACE_RECOGNITION: "personal",
    Entitlement.VOICE_RECOGNITION: "personal",
    Entitlement.MULTI_DEVICE: "personal",
    Entitlement.ADVANCED_AUTOMATION: "personal",
    Entitlement.VOICE_CLONING: "personal",
    # Power
    Entitlement.ADVANCED_ANALYTICS: "power",
    Entitlement.AUDIT_EXPORT: "power",
    Entitlement.SSO_INTEGRATION: "power",
    Entitlement.CUSTOM_BRANDING: "power",
    Entitlement.MULTI_TENANT: "power",
    Entitlement.DEDICATED_SUPPORT: "power",
}


# =============================================================================
# Entitlement Checking
# =============================================================================


async def get_user_tier(user_id: str) -> str:
    """Get subscription tier for a user.

    Checks Stripe subscription status via billing service.

    Args:
        user_id: User account UUID.

    Returns:
        Tier string (free, pro, enterprise).
    """
    try:
        # Try to get from unified identity service (cached)
        from kagami.core.identity import get_unified_identity_service

        service = await get_unified_identity_service()
        return await service._get_user_tier(user_id)
    except Exception:
        pass

    # Fallback: Check Stripe directly
    try:
        from kagami_integrations.stripe_billing import stripe_enabled

        from kagami_api.user_store import get_user_store

        if stripe_enabled():
            user_store = get_user_store()
            user = user_store.get_user(user_id)
            if user and user.get("stripe_customer_id"):
                # Has Stripe customer = at least personal tier
                return "personal"
    except Exception as e:
        logger.debug(f"Failed to check Stripe tier: {e}")

    return "free"


async def check_entitlement(user_id: str, entitlement: Entitlement) -> bool:
    """Check if a user has a specific entitlement.

    Args:
        user_id: User account UUID.
        entitlement: Entitlement to check.

    Returns:
        True if user has entitlement.
    """
    tier = await get_user_tier(user_id)
    tier_entitlements = TIER_ENTITLEMENTS.get(tier, set())
    return entitlement in tier_entitlements


async def get_user_entitlements(user_id: str) -> set[Entitlement]:
    """Get all entitlements for a user.

    Args:
        user_id: User account UUID.

    Returns:
        Set of entitlements.
    """
    tier = await get_user_tier(user_id)
    return TIER_ENTITLEMENTS.get(tier, set())


# =============================================================================
# Dependency Injection
# =============================================================================


class EntitlementChecker:
    """FastAPI dependency for checking entitlements.

    Usage:
        @router.get("/feature")
        async def feature(
            user = Depends(get_current_user),
            _ = Depends(EntitlementChecker(Entitlement.BIOMETRIC_AUTH))
        ):
            return {"feature": "enabled"}
    """

    def __init__(self, entitlement: Entitlement) -> None:
        """Initialize checker.

        Args:
            entitlement: Required entitlement.
        """
        self.entitlement = entitlement

    async def __call__(self, user: Any = Depends(get_current_user)) -> bool:
        """Check entitlement.

        Args:
            user: Current user from auth.

        Returns:
            True if entitled.

        Raises:
            HTTPException: If not entitled (403).
        """
        user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not determine user ID",
            )

        has_entitlement = await check_entitlement(user_id, self.entitlement)

        if not has_entitlement:
            min_tier = ENTITLEMENT_MIN_TIER.get(self.entitlement, "enterprise")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {min_tier} subscription",
                headers={"X-Required-Tier": min_tier},
            )

        return True


def require_entitlement(entitlement: Entitlement) -> EntitlementChecker:
    """Create an entitlement checker dependency.

    Usage:
        @router.get("/feature")
        async def feature(
            user = Depends(get_current_user),
            _ = Depends(require_entitlement(Entitlement.BIOMETRIC_AUTH))
        ):
            return {"feature": "enabled"}

    Args:
        entitlement: Required entitlement.

    Returns:
        EntitlementChecker dependency.
    """
    return EntitlementChecker(entitlement)


# =============================================================================
# Decorator (Alternative to Dependency)
# =============================================================================


def entitlement_required(entitlement: Entitlement) -> Callable:
    """Decorator to require entitlement for endpoint.

    Usage:
        @router.get("/feature")
        @entitlement_required(Entitlement.BIOMETRIC_AUTH)
        async def feature(user = Depends(get_current_user)):
            return {"feature": "enabled"}

    Note: The decorated function MUST have a `user` parameter
    that is the result of `get_current_user`.

    Args:
        entitlement: Required entitlement.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find user in kwargs
            user = kwargs.get("user")
            if not user:
                # Try to find in args by name
                import inspect

                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                for i, param_name in enumerate(params):
                    if param_name == "user" and i < len(args):
                        user = args[i]
                        break

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not determine user ID",
                )

            has_entitlement = await check_entitlement(user_id, entitlement)

            if not has_entitlement:
                min_tier = ENTITLEMENT_MIN_TIER.get(entitlement, "enterprise")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This feature requires {min_tier} subscription",
                    headers={"X-Required-Tier": min_tier},
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Utility Functions
# =============================================================================


def get_tier_features(tier: str) -> dict[str, bool]:
    """Get feature flags for a tier.

    Args:
        tier: Subscription tier.

    Returns:
        Dict of feature names to enabled status.
    """
    entitlements = TIER_ENTITLEMENTS.get(tier, set())

    return {
        "basic_presence": Entitlement.BASIC_PRESENCE in entitlements,
        "basic_automation": Entitlement.BASIC_AUTOMATION in entitlements,
        "basic_voice": Entitlement.BASIC_VOICE in entitlements,
        "biometric_auth": Entitlement.BIOMETRIC_AUTH in entitlements,
        "face_recognition": Entitlement.FACE_RECOGNITION in entitlements,
        "voice_recognition": Entitlement.VOICE_RECOGNITION in entitlements,
        "multi_device": Entitlement.MULTI_DEVICE in entitlements,
        "advanced_automation": Entitlement.ADVANCED_AUTOMATION in entitlements,
        "voice_cloning": Entitlement.VOICE_CLONING in entitlements,
        "advanced_analytics": Entitlement.ADVANCED_ANALYTICS in entitlements,
        "audit_export": Entitlement.AUDIT_EXPORT in entitlements,
        "sso_integration": Entitlement.SSO_INTEGRATION in entitlements,
        "custom_branding": Entitlement.CUSTOM_BRANDING in entitlements,
        "multi_tenant": Entitlement.MULTI_TENANT in entitlements,
        "dedicated_support": Entitlement.DEDICATED_SUPPORT in entitlements,
    }


def compare_tiers(tier_a: str, tier_b: str) -> int:
    """Compare two tiers.

    Args:
        tier_a: First tier.
        tier_b: Second tier.

    Returns:
        -1 if tier_a < tier_b, 0 if equal, 1 if tier_a > tier_b.
    """
    tier_order = {"free": 0, "personal": 1, "family": 2, "power": 3}
    a = tier_order.get(tier_a, 0)
    b = tier_order.get(tier_b, 0)

    if a < b:
        return -1
    elif a > b:
        return 1
    else:
        return 0


__all__ = [
    "ENTITLEMENT_MIN_TIER",
    "TIER_ENTITLEMENTS",
    "Entitlement",
    "EntitlementChecker",
    "check_entitlement",
    "compare_tiers",
    "entitlement_required",
    "get_tier_features",
    "get_user_entitlements",
    "get_user_tier",
    "require_entitlement",
]
