"""Smart Home Webhook Routes — No Authentication Required.

These endpoints are called by Control4/Lutron programming and do not require
JWT/API key authentication. They are protected by network-level security
(only accessible from local network where Control4 Director resides).

Use case: Keypad button → Control4 Programming → HTTP webhook → Kagami API

Security:
- IP whitelist validation for Control4 Director and local network
- Defense-in-depth: network-level access control + application-level validation

Created: January 6, 2026
Updated: January 12, 2026 - Added IP whitelist validation
h(x) >= 0 always.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from kagami_api.routes.home.core import get_controller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/home/webhook", tags=["Smart Home Webhooks"])


# =============================================================================
# IP Whitelist for Control4 Webhooks
# =============================================================================

# Allowed IP ranges for home automation webhooks
# These are typical private network ranges where Control4 Director lives
_ALLOWED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),  # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private Class C
    ipaddress.ip_network("127.0.0.0/8"),  # Localhost
]

# Specific trusted IPs can be added here (e.g., Control4 Director IP)
# Format: Set of IP address strings
_TRUSTED_IPS: set[str] = {
    "127.0.0.1",
    "::1",  # IPv6 localhost
}


def _is_ip_allowed(client_ip: str) -> bool:
    """Check if client IP is in the allowed whitelist.

    Args:
        client_ip: Client IP address string.

    Returns:
        True if IP is allowed, False otherwise.
    """
    # Check explicit trusted IPs first
    if client_ip in _TRUSTED_IPS:
        return True

    try:
        ip = ipaddress.ip_address(client_ip)

        # Check against allowed ranges
        for network in _ALLOWED_IP_RANGES:
            if ip in network:
                return True

    except ValueError:
        # Invalid IP address format
        logger.warning(f"Invalid IP address format: {client_ip}")
        return False

    return False


def _validate_home_webhook_request(request: Request) -> None:
    """Validate that a home webhook request is from a trusted source.

    SECURITY: Only trusts X-Forwarded-For if the direct connection is from
    a trusted proxy (localhost or known reverse proxy IPs). This prevents
    IP spoofing attacks via forged X-Forwarded-For headers.

    Args:
        request: FastAPI request object.

    Raises:
        HTTPException: 403 if request is not from an allowed IP.
    """
    # Get direct connection IP first
    direct_ip = request.client.host if request.client else "unknown"

    # Trusted proxy IPs that we accept X-Forwarded-For from
    _TRUSTED_PROXY_IPS = {
        "127.0.0.1",
        "::1",
        "10.0.0.1",  # Common router/gateway
    }

    # SECURITY: Only trust X-Forwarded-For from known trusted proxies
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for and direct_ip in _TRUSTED_PROXY_IPS:
        # Direct connection is from trusted proxy, trust the forwarded IP
        client_ip = forwarded_for.split(",")[0].strip()
        logger.debug(f"Using forwarded IP {client_ip} from trusted proxy {direct_ip}")
    elif forwarded_for and direct_ip not in _TRUSTED_PROXY_IPS:
        # SECURITY: Direct connection is NOT from trusted proxy - reject X-Forwarded-For spoofing
        logger.warning(
            f"SECURITY: Rejecting X-Forwarded-For from untrusted source {direct_ip}. "
            f"Spoofed header: {forwarded_for}"
        )
        client_ip = direct_ip  # Use direct IP only
    else:
        client_ip = direct_ip

    if not _is_ip_allowed(client_ip):
        logger.warning(f"Home webhook rejected - unauthorized IP: {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Request must originate from local network",
        )

    logger.debug(f"Home webhook accepted from IP: {client_ip}")


# =============================================================================
# SHADE CONTROL (IP Whitelist Protected)
# =============================================================================


@router.post("/shades/open")
async def webhook_open_shades(request: Request, rooms: list[str] | None = None) -> dict[str, Any]:
    """Open shades via webhook (IP whitelist protected).

    Called by Control4 programming when keypad button is pressed.
    Only accepts requests from local network IPs.
    """
    _validate_home_webhook_request(request)
    controller = await get_controller()
    result = await controller.open_shades(rooms)
    return {"success": result, "action": "open", "rooms": rooms}


@router.post("/shades/close")
async def webhook_close_shades(request: Request, rooms: list[str] | None = None) -> dict[str, Any]:
    """Close shades via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    result = await controller.close_shades(rooms)
    return {"success": result, "action": "close", "rooms": rooms}


@router.post("/shades/set")
async def webhook_set_shades(
    request: Request, level: int, rooms: list[str] | None = None
) -> dict[str, Any]:
    """Set shade level via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    result = await controller.set_shades(level, rooms)
    return {"success": result, "level": level, "rooms": rooms}


# =============================================================================
# LIGHT CONTROL (IP Whitelist Protected)
# =============================================================================


@router.post("/lights/set")
async def webhook_set_lights(
    request: Request, level: int, rooms: list[str] | None = None
) -> dict[str, Any]:
    """Set light level via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    result = await controller.set_lights(level, rooms)
    return {"success": result, "level": level, "rooms": rooms}


@router.post("/lights/off")
async def webhook_lights_off(request: Request, rooms: list[str] | None = None) -> dict[str, Any]:
    """Turn off lights via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    result = await controller.set_lights(0, rooms)
    return {"success": result, "action": "off", "rooms": rooms}


# =============================================================================
# SCENE CONTROL (IP Whitelist Protected)
# =============================================================================


@router.post("/scene")
async def webhook_scene(request: Request, room: str, scene: str) -> dict[str, Any]:
    """Apply scene via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    result = await controller.set_room_scene(room, scene)
    return {"success": result, "room": room, "scene": scene}


@router.post("/movie-mode/enter")
async def webhook_movie_mode_enter(request: Request) -> dict[str, Any]:
    """Enter movie mode via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    await controller.enter_movie_mode()
    return {"success": True, "mode": "movie"}


@router.post("/movie-mode/exit")
async def webhook_movie_mode_exit(request: Request) -> dict[str, Any]:
    """Exit movie mode via webhook (IP whitelist protected)."""
    _validate_home_webhook_request(request)
    controller = await get_controller()
    await controller.exit_movie_mode()
    return {"success": True, "mode": "normal"}


def get_router() -> APIRouter:
    """Get the webhook router."""
    return router
