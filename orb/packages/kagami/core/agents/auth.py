"""Agent Authentication — Require Kagami account with upsell.

Provides authentication and entitlement enforcement for the agent runtime:
- Require Kagami account for all agent access
- Upsell messaging for unauthenticated users
- Tiered access (free/pro) for agent features
- WebSocket authentication

Colony: Crystal (e7) — Verification
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

from fastapi import Depends, HTTPException, Query, Request, WebSocket, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Entitlements
# =============================================================================


class AgentTier(str, Enum):
    """Agent access tiers."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AgentEntitlement(str, Enum):
    """Agent feature entitlements."""

    # Free tier
    AGENT_VIEW = "agent:view"  # View agent state
    AGENT_QUERY = "agent:query"  # Query agent (limited)
    AGENT_RENDER = "agent:render"  # Render HTML

    # Pro tier
    AGENT_ACTION = "agent:action"  # Execute actions
    AGENT_VOICE = "agent:voice"  # Voice interaction
    AGENT_WEBSOCKET = "agent:websocket"  # Real-time WebSocket
    AGENT_SECRETS = "agent:secrets"  # pragma: allowlist secret  # Access secrets

    # Enterprise tier
    AGENT_VIDEO = "agent:video"  # OBS video production
    AGENT_LEARNING = "agent:learning"  # Learning/evolution
    AGENT_CUSTOM = "agent:custom"  # Custom agents


# Entitlements by tier
AGENT_TIER_ENTITLEMENTS: dict[AgentTier, set[AgentEntitlement]] = {
    AgentTier.FREE: {
        AgentEntitlement.AGENT_VIEW,
        AgentEntitlement.AGENT_QUERY,
        AgentEntitlement.AGENT_RENDER,
    },
    AgentTier.PRO: {
        # Free
        AgentEntitlement.AGENT_VIEW,
        AgentEntitlement.AGENT_QUERY,
        AgentEntitlement.AGENT_RENDER,
        # Pro
        AgentEntitlement.AGENT_ACTION,
        AgentEntitlement.AGENT_VOICE,
        AgentEntitlement.AGENT_WEBSOCKET,
        AgentEntitlement.AGENT_SECRETS,
    },
    AgentTier.ENTERPRISE: {
        # Free
        AgentEntitlement.AGENT_VIEW,
        AgentEntitlement.AGENT_QUERY,
        AgentEntitlement.AGENT_RENDER,
        # Pro
        AgentEntitlement.AGENT_ACTION,
        AgentEntitlement.AGENT_VOICE,
        AgentEntitlement.AGENT_WEBSOCKET,
        AgentEntitlement.AGENT_SECRETS,
        # Enterprise
        AgentEntitlement.AGENT_VIDEO,
        AgentEntitlement.AGENT_LEARNING,
        AgentEntitlement.AGENT_CUSTOM,
    },
}

# Minimum tier required for each entitlement
ENTITLEMENT_MIN_TIER: dict[AgentEntitlement, AgentTier] = {
    AgentEntitlement.AGENT_VIEW: AgentTier.FREE,
    AgentEntitlement.AGENT_QUERY: AgentTier.FREE,
    AgentEntitlement.AGENT_RENDER: AgentTier.FREE,
    AgentEntitlement.AGENT_ACTION: AgentTier.PRO,
    AgentEntitlement.AGENT_VOICE: AgentTier.PRO,
    AgentEntitlement.AGENT_WEBSOCKET: AgentTier.PRO,
    AgentEntitlement.AGENT_SECRETS: AgentTier.PRO,
    AgentEntitlement.AGENT_VIDEO: AgentTier.ENTERPRISE,
    AgentEntitlement.AGENT_LEARNING: AgentTier.ENTERPRISE,
    AgentEntitlement.AGENT_CUSTOM: AgentTier.ENTERPRISE,
}


# =============================================================================
# Upsell Messaging
# =============================================================================


@dataclass
class UpsellMessage:
    """Upsell message for feature access."""

    feature: str
    required_tier: AgentTier
    message: str
    cta: str
    signup_url: str
    pricing_url: str


def get_upsell_message(
    entitlement: AgentEntitlement,
    feature_description: str | None = None,
) -> UpsellMessage:
    """Get upsell message for a feature.

    Args:
        entitlement: Required entitlement.
        feature_description: Optional custom description.

    Returns:
        UpsellMessage with upgrade info.
    """
    required_tier = ENTITLEMENT_MIN_TIER.get(entitlement, AgentTier.PRO)

    base_url = os.environ.get("KAGAMI_BASE_URL", "https://kagami.ai")

    descriptions = {
        AgentEntitlement.AGENT_VIEW: "view agent state",
        AgentEntitlement.AGENT_QUERY: "query agents",
        AgentEntitlement.AGENT_RENDER: "render agent HTML",
        AgentEntitlement.AGENT_ACTION: "execute agent actions",
        AgentEntitlement.AGENT_VOICE: "voice interaction with agents",
        AgentEntitlement.AGENT_WEBSOCKET: "real-time agent communication",
        AgentEntitlement.AGENT_SECRETS: "access agent secrets",  # pragma: allowlist secret
        AgentEntitlement.AGENT_VIDEO: "OBS video production",
        AgentEntitlement.AGENT_LEARNING: "agent learning & evolution",
        AgentEntitlement.AGENT_CUSTOM: "custom agent creation",
    }

    desc = feature_description or descriptions.get(entitlement, "this feature")

    if required_tier == AgentTier.FREE:
        message = f"Create a free Kagami account to {desc}."
        cta = "Sign Up Free"
    elif required_tier == AgentTier.PRO:
        message = f"Upgrade to Kagami Pro to {desc}. Unlock voice interaction, real-time WebSocket, and powerful actions."
        cta = "Upgrade to Pro"
    else:
        message = f"Upgrade to Kagami Enterprise to {desc}. Get video production, AI learning, and custom agents."
        cta = "Contact Sales"

    return UpsellMessage(
        feature=entitlement.value,
        required_tier=required_tier,
        message=message,
        cta=cta,
        signup_url=f"{base_url}/signup",
        pricing_url=f"{base_url}/pricing",
    )


def upsell_response(
    entitlement: AgentEntitlement,
    feature_description: str | None = None,
) -> JSONResponse:
    """Create upsell JSON response.

    Args:
        entitlement: Required entitlement.
        feature_description: Optional custom description.

    Returns:
        JSONResponse with upsell content and 402 status.
    """
    upsell = get_upsell_message(entitlement, feature_description)

    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={
            "error": {
                "type": "payment_required",
                "code": 402,
                "message": upsell.message,
            },
            "upsell": {
                "feature": upsell.feature,
                "required_tier": upsell.required_tier.value,
                "cta": upsell.cta,
                "signup_url": upsell.signup_url,
                "pricing_url": upsell.pricing_url,
            },
            "kagami": {
                "tagline": "Your AI presence in every space.",
                "benefits": [
                    "Voice-powered smart home control",
                    "Real-time agent communication",
                    "Beautiful, interactive experiences",
                    "Privacy-first architecture",
                ],
            },
        },
        headers={
            "X-Required-Tier": upsell.required_tier.value,
            "X-Signup-URL": upsell.signup_url,
        },
    )


def unauthenticated_response() -> JSONResponse:
    """Create response for unauthenticated users with signup upsell.

    Returns:
        JSONResponse with 401 status and signup CTA.
    """
    base_url = os.environ.get("KAGAMI_BASE_URL", "https://kagami.ai")

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "type": "authentication_required",
                "code": 401,
                "message": "Kagami account required to access this feature.",
            },
            "upsell": {
                "message": "Create a free Kagami account to get started with AI agents.",
                "cta": "Sign Up Free",
                "signup_url": f"{base_url}/signup",
                "login_url": f"{base_url}/login",
                "pricing_url": f"{base_url}/pricing",
            },
            "kagami": {
                "tagline": "Your AI presence in every space.",
                "free_features": [
                    "View agent state",
                    "Query agents (limited)",
                    "Render beautiful HTML",
                ],
                "pro_features": [
                    "Execute powerful actions",
                    "Voice interaction",
                    "Real-time WebSocket",
                    "Access secrets",
                ],
            },
        },
        headers={
            "WWW-Authenticate": 'Bearer realm="kagami"',
            "X-Signup-URL": f"{base_url}/signup",
        },
    )


# =============================================================================
# User & Tier Resolution
# =============================================================================


class AgentUser(BaseModel):
    """Authenticated user for agent access."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    username: str
    email: str
    tier: AgentTier
    entitlements: set[str]
    is_admin: bool = False

    def has_entitlement(self, entitlement: AgentEntitlement) -> bool:
        """Check if user has entitlement."""
        return entitlement.value in self.entitlements

    def can_access(self, entitlement: AgentEntitlement) -> bool:
        """Check if user can access feature (has required tier)."""
        tier_entitlements = AGENT_TIER_ENTITLEMENTS.get(self.tier, set())
        return entitlement in tier_entitlements or self.is_admin


async def get_user_agent_tier(user_id: str) -> AgentTier:
    """Get agent tier for a user.

    Args:
        user_id: User account ID.

    Returns:
        AgentTier based on subscription.
    """
    try:
        from kagami_api.entitlements import get_user_tier

        tier_str = await get_user_tier(user_id)

        if tier_str == "enterprise":
            return AgentTier.ENTERPRISE
        elif tier_str == "pro":
            return AgentTier.PRO
        else:
            return AgentTier.FREE

    except Exception as e:
        logger.debug(f"Failed to get user tier: {e}")
        return AgentTier.FREE


async def resolve_agent_user(request: Request) -> AgentUser | None:
    """Resolve authenticated agent user from request.

    Args:
        request: FastAPI request.

    Returns:
        AgentUser if authenticated, None otherwise.
    """
    try:
        # Get user from auth system
        from fastapi.security import HTTPBearer
        from kagami_api.auth import get_current_user_optional

        security = HTTPBearer(auto_error=False)
        credentials = await security(request)

        if not credentials:
            return None

        user = await get_current_user_optional(credentials)

        if not user:
            return None

        # Get tier
        tier = await get_user_agent_tier(user.id)

        # Get entitlements for tier
        tier_entitlements = AGENT_TIER_ENTITLEMENTS.get(tier, set())

        return AgentUser(
            id=user.id,
            username=user.username,
            email=user.email,
            tier=tier,
            entitlements={e.value for e in tier_entitlements},
            is_admin=user.is_admin,
        )

    except Exception as e:
        logger.debug(f"Failed to resolve agent user: {e}")
        return None


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def require_agent_auth(request: Request) -> AgentUser:
    """Require authenticated Kagami account.

    Args:
        request: FastAPI request.

    Returns:
        Authenticated AgentUser.

    Raises:
        HTTPException: 401 with upsell if not authenticated.
    """
    user = await resolve_agent_user(request)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kagami account required",
            headers={"WWW-Authenticate": 'Bearer realm="kagami"'},
        )

    return user


async def require_agent_entitlement(
    entitlement: AgentEntitlement,
) -> Callable:
    """Create dependency requiring specific entitlement.

    Args:
        entitlement: Required entitlement.

    Returns:
        Dependency function.
    """

    async def dependency(user: AgentUser = Depends(require_agent_auth)) -> AgentUser:
        if not user.can_access(entitlement):
            upsell = get_upsell_message(entitlement)
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=upsell.message,
                headers={"X-Required-Tier": upsell.required_tier.value},
            )
        return user

    return dependency


def agent_auth_required(
    entitlement: AgentEntitlement | None = None,
) -> Callable:
    """Decorator for routes requiring agent auth.

    Args:
        entitlement: Optional specific entitlement required.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find request in args/kwargs
            request = kwargs.get("request") or kwargs.get("req")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                raise HTTPException(
                    status_code=500,
                    detail="Request not found in handler",
                )

            # Resolve user
            user = await resolve_agent_user(request)

            if not user:
                return unauthenticated_response()

            # Check entitlement if specified
            if entitlement and not user.can_access(entitlement):
                return upsell_response(entitlement)

            # Inject user into kwargs
            kwargs["agent_user"] = user

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# WebSocket Authentication
# =============================================================================


async def authenticate_websocket(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> AgentUser | None:
    """Authenticate WebSocket connection.

    Token can be provided via:
    1. Query parameter: ?token=xxx
    2. Subprotocol: Sec-WebSocket-Protocol header

    Args:
        websocket: WebSocket connection.
        token: Optional token from query.

    Returns:
        AgentUser if authenticated, None otherwise.
    """
    # Try query parameter first
    auth_token = token

    # Try subprotocol if no query token
    if not auth_token:
        subprotocols = websocket.headers.get("sec-websocket-protocol", "")
        for proto in subprotocols.split(","):
            proto = proto.strip()
            if proto.startswith("kagami.auth."):
                auth_token = proto.replace("kagami.auth.", "")
                break

    if not auth_token:
        return None

    try:
        from kagami_api.auth import get_user_from_token

        user = await get_user_from_token(auth_token)
        tier = await get_user_agent_tier(user.id)
        tier_entitlements = AGENT_TIER_ENTITLEMENTS.get(tier, set())

        return AgentUser(
            id=user.id,
            username=user.username,
            email=user.email,
            tier=tier,
            entitlements={e.value for e in tier_entitlements},
            is_admin=user.is_admin,
        )

    except Exception as e:
        logger.debug(f"WebSocket auth failed: {e}")
        return None


async def require_websocket_auth(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> AgentUser:
    """Require authenticated WebSocket connection.

    Args:
        websocket: WebSocket connection.
        token: Optional token from query.

    Returns:
        Authenticated AgentUser.

    Raises:
        WebSocket close if not authenticated.
    """
    user = await authenticate_websocket(websocket, token)

    if not user:
        await websocket.close(
            code=4001,
            reason="Authentication required. Get token from /api/user/token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebSocket authentication required",
        )

    if not user.can_access(AgentEntitlement.AGENT_WEBSOCKET):
        await websocket.close(
            code=4002,
            reason="Pro subscription required for WebSocket access",
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Pro subscription required",
        )

    return user


# =============================================================================
# Rate Limiting by Tier
# =============================================================================


TIER_RATE_LIMITS: dict[AgentTier, dict[str, int]] = {
    AgentTier.FREE: {
        "queries_per_minute": 10,
        "actions_per_minute": 0,  # No actions for free
        "ws_messages_per_minute": 0,  # No WebSocket for free
    },
    AgentTier.PRO: {
        "queries_per_minute": 60,
        "actions_per_minute": 30,
        "ws_messages_per_minute": 300,
    },
    AgentTier.ENTERPRISE: {
        "queries_per_minute": 300,
        "actions_per_minute": 150,
        "ws_messages_per_minute": 1500,
    },
}


def get_tier_rate_limit(tier: AgentTier, limit_type: str) -> int:
    """Get rate limit for tier.

    Args:
        tier: User's tier.
        limit_type: Type of limit (queries_per_minute, etc.).

    Returns:
        Rate limit value.
    """
    limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[AgentTier.FREE])
    return limits.get(limit_type, 0)


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Entitlements
    "AGENT_TIER_ENTITLEMENTS",
    "ENTITLEMENT_MIN_TIER",
    # Rate limiting
    "TIER_RATE_LIMITS",
    # Enums
    "AgentEntitlement",
    "AgentTier",
    # Models
    "AgentUser",
    "UpsellMessage",
    # Dependencies
    "agent_auth_required",
    "authenticate_websocket",
    "get_tier_rate_limit",
    # Upsell
    "get_upsell_message",
    # User resolution
    "get_user_agent_tier",
    "require_agent_auth",
    "require_agent_entitlement",
    "require_websocket_auth",
    "resolve_agent_user",
    "unauthenticated_response",
    "upsell_response",
]
