"""Kagami Subscription Tiers & Pricing Model.

Optimal pricing strategy with:
- Consumer-friendly tiers (Free → Personal → Family)
- Power user pay-as-you-go
- Gifting support
- Household sharing

Pricing Philosophy:
- Low barrier to entry (generous free tier)
- Clear value at each step
- Usage-based for heavy users
- Family-first for households

Tier Hierarchy:
    FREE → PERSONAL → FAMILY → POWER

Stripe Integration:
    Price IDs loaded from environment:
    - STRIPE_PRICE_PERSONAL=price_xxx
    - STRIPE_PRICE_FAMILY=price_yyy
    - STRIPE_PRICE_USAGE=price_zzz (metered)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SubscriptionTier(str, Enum):
    """Available subscription tiers.

    Ordered by capability: FREE < PERSONAL < FAMILY < POWER.
    """

    FREE = "free"
    PERSONAL = "personal"
    FAMILY = "family"
    POWER = "power"

    # Legacy mappings (for backward compat)
    PRO = "personal"  # Alias
    TEAM = "family"  # Alias
    ENTERPRISE = "power"  # Alias


class GiftType(str, Enum):
    """Gift subscription types."""

    ONE_MONTH = "1_month"
    THREE_MONTHS = "3_months"
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"


@dataclass
class TierLimits:
    """Feature limits and capabilities per tier.

    Attributes:
        name: Display name
        monthly_ops: Operations limit (None = unlimited)
        daily_ops: Daily operations limit (soft cap)
        household_members: Max family members (1 = individual)
        api_rate_limit_rpm: Requests per minute
        storage_gb: Storage quota
        model_access: Accessible models
        features: Feature flags
        price_monthly_usd: Monthly price
        price_annual_usd: Annual price (discounted)
        overage_per_1k_ops: Price per 1K ops over limit
    """

    name: str
    monthly_ops: int | None
    daily_ops: int | None
    household_members: int
    api_rate_limit_rpm: int
    storage_gb: int | None
    model_access: list[str]
    features: set[str]
    price_monthly_usd: int
    price_annual_usd: int
    overage_per_1k_ops: float = 0.0


# =============================================================================
# TIER CONFIGURATIONS - Optimized for Consumer Value
# =============================================================================

TIER_CONFIGS: dict[SubscriptionTier, TierLimits] = {
    # FREE: Generous trial, hooks users
    SubscriptionTier.FREE: TierLimits(
        name="Free",
        monthly_ops=5_000,  # ~150/day
        daily_ops=500,
        household_members=1,
        api_rate_limit_rpm=30,
        storage_gb=1,
        model_access=["kagami-lite"],
        features={
            "basic_assistant",
            "voice_commands",
            "smart_home_basic",
            "community_support",
        },
        price_monthly_usd=0,
        price_annual_usd=0,
        overage_per_1k_ops=0.0,  # No overage on free
    ),
    # PERSONAL: Core offering for individuals ($20/mo - matches ChatGPT Plus, Claude Pro)
    SubscriptionTier.PERSONAL: TierLimits(
        name="Personal",
        monthly_ops=100_000,  # ~3,300/day
        daily_ops=10_000,
        household_members=1,
        api_rate_limit_rpm=120,
        storage_gb=25,
        model_access=[
            "kagami-lite",  # Fast queries
            "kagami-pro",  # Standard quality
            "claude-sonnet",  # Anthropic Sonnet (best balance)
            "gpt-4o",  # OpenAI flagship
        ],
        features={
            "basic_assistant",
            "voice_commands",
            "smart_home_basic",
            "smart_home_advanced",
            "priority_support",
            "custom_routines",
            "voice_profiles",
            "calendar_integration",
            "email_integration",
        },
        price_monthly_usd=20,
        price_annual_usd=200,  # 2 months free
        overage_per_1k_ops=0.20,
    ),
    # FAMILY: Household plan with sharing ($40/mo - 2x Personal for 6 people)
    SubscriptionTier.FAMILY: TierLimits(
        name="Family",
        monthly_ops=500_000,  # ~16,500/day shared across family
        daily_ops=50_000,
        household_members=6,  # Primary + 5 family
        api_rate_limit_rpm=300,
        storage_gb=100,
        model_access=[
            "kagami-lite",  # Fast queries
            "kagami-pro",  # Standard quality
            "claude-sonnet",  # Anthropic Sonnet
            "claude-opus",  # Anthropic best (for complex tasks)
            "gpt-4o",  # OpenAI flagship
            "gpt-4-turbo",  # OpenAI extended context
        ],
        features={
            "basic_assistant",
            "voice_commands",
            "smart_home_basic",
            "smart_home_advanced",
            "priority_support",
            "custom_routines",
            "voice_profiles",
            "calendar_integration",
            "email_integration",
            "family_sharing",
            "per_member_preferences",
            "shared_automations",
            "parental_controls",
            "guest_access",
        },
        price_monthly_usd=40,
        price_annual_usd=400,  # 2 months free
        overage_per_1k_ops=0.15,
    ),
    # POWER: Unlimited for power users ($200/mo - matches ChatGPT Pro, Perplexity Max)
    SubscriptionTier.POWER: TierLimits(
        name="Power",
        monthly_ops=None,  # Unlimited
        daily_ops=None,
        household_members=6,
        api_rate_limit_rpm=1000,
        storage_gb=None,  # Unlimited
        model_access=[
            "*",  # All models, including:
            "kagami-lite",
            "kagami-pro",
            "claude-sonnet",
            "claude-opus",  # Best Anthropic
            "gpt-4o",
            "gpt-4-turbo",
            "o1",  # OpenAI reasoning
            "o1-pro",  # OpenAI best reasoning
            "gemini-2-ultra",  # Google best
            "deep-research",  # Extended research mode
        ],
        features={
            "basic_assistant",
            "voice_commands",
            "smart_home_basic",
            "smart_home_advanced",
            "priority_support",
            "custom_routines",
            "voice_profiles",
            "calendar_integration",
            "email_integration",
            "family_sharing",
            "per_member_preferences",
            "shared_automations",
            "parental_controls",
            "guest_access",
            "api_access",
            "webhook_integrations",
            "custom_models",
            "dedicated_support",
            "sla_guarantee",
            "early_access",  # Beta features
            "priority_inference",  # No queue
        },
        price_monthly_usd=200,
        price_annual_usd=2000,  # 2 months free
        overage_per_1k_ops=0.0,  # Included in unlimited
    ),
}

# Legacy tier aliases
TIER_CONFIGS[SubscriptionTier.PRO] = TIER_CONFIGS[SubscriptionTier.PERSONAL]
TIER_CONFIGS[SubscriptionTier.TEAM] = TIER_CONFIGS[SubscriptionTier.FAMILY]
TIER_CONFIGS[SubscriptionTier.ENTERPRISE] = TIER_CONFIGS[SubscriptionTier.POWER]


# =============================================================================
# GIFT CONFIGURATIONS
# =============================================================================

@dataclass
class GiftConfig:
    """Gift subscription configuration."""

    gift_type: GiftType
    months: int
    discount_percent: int
    price_usd: int


GIFT_CONFIGS: dict[GiftType, dict[SubscriptionTier, GiftConfig]] = {
    GiftType.ONE_MONTH: {
        SubscriptionTier.PERSONAL: GiftConfig(GiftType.ONE_MONTH, 1, 0, 20),
        SubscriptionTier.FAMILY: GiftConfig(GiftType.ONE_MONTH, 1, 0, 40),
    },
    GiftType.THREE_MONTHS: {
        SubscriptionTier.PERSONAL: GiftConfig(GiftType.THREE_MONTHS, 3, 10, 54),  # $18/mo
        SubscriptionTier.FAMILY: GiftConfig(GiftType.THREE_MONTHS, 3, 10, 108),  # $36/mo
    },
    GiftType.SIX_MONTHS: {
        SubscriptionTier.PERSONAL: GiftConfig(GiftType.SIX_MONTHS, 6, 15, 102),  # $17/mo
        SubscriptionTier.FAMILY: GiftConfig(GiftType.SIX_MONTHS, 6, 15, 204),  # $34/mo
    },
    GiftType.ONE_YEAR: {
        SubscriptionTier.PERSONAL: GiftConfig(GiftType.ONE_YEAR, 12, 17, 200),  # $16.67/mo
        SubscriptionTier.FAMILY: GiftConfig(GiftType.ONE_YEAR, 12, 17, 400),  # $33.33/mo
    },
}


# =============================================================================
# HOUSEHOLD MEMBER CONFIGURATION
# =============================================================================

@dataclass
class HouseholdMember:
    """Household member with individual settings."""

    user_id: str
    display_name: str
    role: str  # owner, adult, child, guest
    voice_profile_id: str | None = None
    preferences: dict[str, Any] = field(default_factory=dict)
    daily_ops_limit: int | None = None  # Per-member daily cap


@dataclass
class Household:
    """Household billing entity."""

    id: str
    name: str
    owner_id: str
    tier: SubscriptionTier
    members: list[HouseholdMember] = field(default_factory=list)
    stripe_subscription_id: str | None = None
    created_at: str | None = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tier_config(tier: SubscriptionTier | str) -> TierLimits:
    """Get configuration for a subscription tier."""
    if isinstance(tier, str):
        tier_lower = tier.lower()
        # Handle legacy names
        if tier_lower == "pro":
            tier = SubscriptionTier.PERSONAL
        elif tier_lower == "team":
            tier = SubscriptionTier.FAMILY
        elif tier_lower == "enterprise":
            tier = SubscriptionTier.POWER
        else:
            try:
                tier = SubscriptionTier(tier_lower)
            except ValueError:
                tier = SubscriptionTier.FREE
    return TIER_CONFIGS.get(tier, TIER_CONFIGS[SubscriptionTier.FREE])


def has_feature(tier: SubscriptionTier | str, feature: str) -> bool:
    """Check if a tier has access to a specific feature."""
    config = get_tier_config(tier)
    return feature in config.features


def get_rate_limit(tier: SubscriptionTier | str) -> int:
    """Get API rate limit for tier (requests per minute)."""
    return get_tier_config(tier).api_rate_limit_rpm


def get_ops_limit(tier: SubscriptionTier | str) -> int | None:
    """Get monthly operations limit (None = unlimited)."""
    return get_tier_config(tier).monthly_ops


def get_daily_ops_limit(tier: SubscriptionTier | str) -> int | None:
    """Get daily operations limit (None = unlimited)."""
    return get_tier_config(tier).daily_ops


def get_household_limit(tier: SubscriptionTier | str) -> int:
    """Get max household members for tier."""
    return get_tier_config(tier).household_members


def get_overage_rate(tier: SubscriptionTier | str) -> float:
    """Get overage rate per 1K operations."""
    return get_tier_config(tier).overage_per_1k_ops


def calculate_overage_cost(tier: SubscriptionTier | str, ops_over: int) -> float:
    """Calculate overage cost for operations over limit.

    Args:
        tier: Subscription tier
        ops_over: Number of operations over the monthly limit

    Returns:
        Cost in USD for overage
    """
    if ops_over <= 0:
        return 0.0
    rate = get_overage_rate(tier)
    return (ops_over / 1000) * rate


def get_gift_config(
    tier: SubscriptionTier, gift_type: GiftType
) -> GiftConfig | None:
    """Get gift configuration for a tier and duration."""
    tier_gifts = GIFT_CONFIGS.get(gift_type, {})
    return tier_gifts.get(tier)


def get_gift_price(tier: SubscriptionTier, gift_type: GiftType) -> int | None:
    """Get gift price for a tier and duration."""
    config = get_gift_config(tier, gift_type)
    return config.price_usd if config else None


# =============================================================================
# STRIPE PRICE ID MAPPING
# =============================================================================

STRIPE_TIER_MAP: dict[str, SubscriptionTier] = {}


def _load_stripe_tier_map_from_env() -> None:
    """Load Stripe price ID mappings from environment."""
    mappings = [
        ("STRIPE_PRICE_PERSONAL", SubscriptionTier.PERSONAL),
        ("STRIPE_PRICE_PERSONAL_ANNUAL", SubscriptionTier.PERSONAL),
        ("STRIPE_PRICE_FAMILY", SubscriptionTier.FAMILY),
        ("STRIPE_PRICE_FAMILY_ANNUAL", SubscriptionTier.FAMILY),
        ("STRIPE_PRICE_POWER", SubscriptionTier.POWER),
        ("STRIPE_PRICE_POWER_ANNUAL", SubscriptionTier.POWER),
        # Legacy mappings
        ("STRIPE_PRICE_PRO", SubscriptionTier.PERSONAL),
        ("STRIPE_PRICE_TEAM", SubscriptionTier.FAMILY),
        ("STRIPE_PRICE_ENTERPRISE", SubscriptionTier.POWER),
    ]
    for env_key, tier in mappings:
        price_id = (os.getenv(env_key) or "").strip()
        if price_id:
            STRIPE_TIER_MAP[price_id] = tier


_load_stripe_tier_map_from_env()


def map_stripe_plan_to_tier(stripe_plan_name: str | None) -> SubscriptionTier:
    """Map Stripe plan name or price ID to subscription tier."""
    if not stripe_plan_name:
        return SubscriptionTier.FREE

    plan_lower = str(stripe_plan_name).lower()

    # Direct name matching
    if "power" in plan_lower or "enterprise" in plan_lower:
        return SubscriptionTier.POWER
    if "family" in plan_lower or "team" in plan_lower or "household" in plan_lower:
        return SubscriptionTier.FAMILY
    if "personal" in plan_lower or "pro" in plan_lower:
        return SubscriptionTier.PERSONAL

    # Price ID lookup
    if stripe_plan_name in STRIPE_TIER_MAP:
        return STRIPE_TIER_MAP[stripe_plan_name]

    return SubscriptionTier.FREE


# =============================================================================
# PRICING SUMMARY (for display)
# =============================================================================

def get_pricing_summary() -> dict[str, Any]:
    """Get pricing summary for display in UI/API."""
    return {
        "tiers": [
            {
                "id": SubscriptionTier.FREE.value,
                "name": "Free",
                "price_monthly": 0,
                "price_annual": 0,
                "description": "Get started with Kagami",
                "highlights": [
                    "5,000 operations/month",
                    "Basic AI model",
                    "Voice commands",
                    "Smart home essentials",
                ],
            },
            {
                "id": SubscriptionTier.PERSONAL.value,
                "name": "Personal",
                "price_monthly": 20,
                "price_annual": 200,
                "popular": True,
                "description": "Same price as ChatGPT Plus",
                "highlights": [
                    "100,000 operations/month",
                    "Claude Sonnet + GPT-4o",
                    "Custom routines & voice profiles",
                    "Priority support",
                ],
            },
            {
                "id": SubscriptionTier.FAMILY.value,
                "name": "Family",
                "price_monthly": 40,
                "price_annual": 400,
                "description": "Share with your household",
                "highlights": [
                    "500,000 operations/month",
                    "Up to 6 family members",
                    "Claude Opus + GPT-4 Turbo",
                    "Per-person preferences",
                ],
            },
            {
                "id": SubscriptionTier.POWER.value,
                "name": "Power",
                "price_monthly": 200,
                "price_annual": 2000,
                "description": "Same as ChatGPT Pro",
                "highlights": [
                    "Unlimited operations",
                    "All models: o1-pro, Opus, Ultra",
                    "API access + webhooks",
                    "Priority inference & SLA",
                ],
            },
        ],
        "competitive_comparison": {
            "chatgpt_plus": {"price": 20, "comparable_tier": "personal"},
            "chatgpt_pro": {"price": 200, "comparable_tier": "power"},
            "claude_pro": {"price": 20, "comparable_tier": "personal"},
            "claude_max": {"price": 100, "comparable_tier": "family"},
            "perplexity_pro": {"price": 20, "comparable_tier": "personal"},
            "perplexity_max": {"price": 200, "comparable_tier": "power"},
        },
        "gifts": [
            {"id": "1_month", "name": "1 Month", "discount": "0%"},
            {"id": "3_months", "name": "3 Months", "discount": "10%"},
            {"id": "6_months", "name": "6 Months", "discount": "15%"},
            {"id": "1_year", "name": "1 Year", "discount": "17%"},
        ],
        "overage": {
            "personal": "$0.20 per 1K ops",
            "family": "$0.15 per 1K ops",
            "power": "Unlimited (included)",
        },
    }


__all__ = [
    "GIFT_CONFIGS",
    "STRIPE_TIER_MAP",
    "TIER_CONFIGS",
    "GiftConfig",
    "GiftType",
    "Household",
    "HouseholdMember",
    "SubscriptionTier",
    "TierLimits",
    "calculate_overage_cost",
    "get_daily_ops_limit",
    "get_gift_config",
    "get_gift_price",
    "get_household_limit",
    "get_ops_limit",
    "get_overage_rate",
    "get_pricing_summary",
    "get_rate_limit",
    "get_tier_config",
    "has_feature",
    "map_stripe_plan_to_tier",
]
