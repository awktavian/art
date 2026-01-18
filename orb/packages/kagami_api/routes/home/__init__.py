"""Smart Home API Routes — Modular Organization.

Provides REST endpoints for controlling the smart home via Kagami.
Split into focused modules for maintainability (<500 LOC each).

Created: December 29, 2025
Refactored: January 2, 2026
Updated: January 6, 2026 — Added webhook_router for Control4/Lutron integration (no auth)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kagami_api.auth import require_auth

# Create parent router with auth dependency (for web/mobile clients)
router = APIRouter(prefix="/home", tags=["Smart Home"], dependencies=[Depends(require_auth)])

# Create webhook router WITHOUT auth (for Control4/Lutron/HomeKit webhooks)
# These are internal network calls from smart home controllers
webhook_router = APIRouter(prefix="/home/webhook", tags=["Smart Home Webhooks"])


def get_router() -> APIRouter:
    """Get the assembled home router with all sub-routers."""
    # Import sub-routers (lazy to avoid circular imports)
    from . import (
        audio,
        climate,
        core,
        devices,
        findmy,
        health,
        lighting,
        tesla,
        voice_input,
        weather,
    )

    # Include all sub-routers (no prefix - they define their own route paths)
    router.include_router(core.router)
    router.include_router(lighting.router)
    router.include_router(devices.router)
    router.include_router(climate.router)
    router.include_router(audio.router)
    router.include_router(weather.router)
    router.include_router(findmy.router)
    router.include_router(health.router)
    router.include_router(tesla.router)

    # Also add lighting routes to webhook_router (no auth for Control4 integration)
    webhook_router.include_router(lighting.router)

    # Voice input webhook (no auth - local network only, physical presence auth)
    webhook_router.include_router(voice_input.router)

    return router


def get_webhook_router() -> APIRouter:
    """Get the webhook router for unauthenticated smart home webhooks.

    This is used by Control4/Lutron programming to trigger Kagami actions.
    Only accessible from local network (enforced by network config).
    """
    from . import lighting

    # Re-include lighting to ensure it's available
    # Note: webhook_router is already populated in get_router()
    return webhook_router


__all__ = ["get_router", "get_webhook_router", "router", "webhook_router"]
