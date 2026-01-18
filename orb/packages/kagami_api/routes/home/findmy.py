"""Find My Routes — Apple iCloud Device Location.

~150 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .core import get_controller

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class FindMyDevice(BaseModel):
    """Apple device info from Find My."""

    name: str
    device_type: str
    device_class: str
    battery_percent: int
    battery_status: str
    is_online: bool
    location: dict[str, Any] | None = None


class FindMySoundRequest(BaseModel):
    """Request to play sound on device."""

    device_name: str | None = Field(None, description="Device name (None = default iPhone)")


class FindMy2FARequest(BaseModel):
    """Request to submit 2FA code."""

    code: str = Field(..., min_length=6, max_length=6, description="6-digit 2FA code")


# =============================================================================
# ROUTES
# =============================================================================


@router.get("/findmy/devices")
async def get_findmy_devices() -> dict[str, Any]:
    """Get all Apple devices from Find My.

    Returns device locations, battery status, and online state.
    """
    controller = await get_controller()

    if not controller._apple_findmy or not controller._apple_findmy.is_connected:
        return {"devices": [], "connected": False, "error": "Find My not connected"}

    devices = await controller._apple_findmy.get_devices()
    return {
        "connected": True,
        "device_count": len(devices),
        "devices": [
            {
                "name": d.name,
                "device_type": d.device_type,
                "device_class": d.device_class,
                "battery_percent": d.battery_percent,
                "battery_status": d.battery_status,
                "is_online": d.is_online,
                "location": d.location,
            }
            for d in devices
        ],
    }


@router.get("/findmy/locate")
async def locate_device(
    device_name: str | None = Query(None, description="Device name (None = default iPhone)"),
) -> dict[str, Any]:
    """Get location of a specific Apple device.

    Returns latitude, longitude, accuracy, and timestamp.
    """
    controller = await get_controller()

    if not controller._apple_findmy or not controller._apple_findmy.is_connected:
        raise HTTPException(status_code=503, detail="Find My not connected")

    location = await controller._apple_findmy.get_device_location(device_name)
    if location:
        return {"success": True, **location}
    return {"success": False, "error": "Location not available"}


@router.post("/findmy/sound")
async def play_sound(cmd: FindMySoundRequest | None = None) -> dict[str, Any]:
    """Play sound on an Apple device to help locate it.

    If no device specified, plays on the first iPhone found.
    """
    controller = await get_controller()

    if not controller._apple_findmy or not controller._apple_findmy.is_connected:
        raise HTTPException(status_code=503, detail="Find My not connected")

    device_name = cmd.device_name if cmd else None
    result = await controller._apple_findmy.play_sound(device_name)
    return {"success": result, "device": device_name or "default"}


@router.post("/findmy/sound-all")
async def play_sound_all() -> dict[str, Any]:
    """Play sound on ALL Apple devices."""
    controller = await get_controller()

    if not controller._apple_findmy or not controller._apple_findmy.is_connected:
        raise HTTPException(status_code=503, detail="Find My not connected")

    results = await controller._apple_findmy.play_sound_all()
    return {"success": True, "results": results}


@router.get("/findmy/status")
async def get_findmy_status() -> dict[str, Any]:
    """Get Find My connection status."""
    controller = await get_controller()

    if not controller._apple_findmy:
        return {"available": False, "reason": "Not configured"}

    return {
        "available": True,
        "connected": controller._apple_findmy.is_connected,
        "requires_2fa": controller._apple_findmy.requires_2fa,
    }


@router.post("/findmy/2fa")
async def submit_2fa(cmd: FindMy2FARequest) -> dict[str, Any]:
    """Submit 2FA verification code for iCloud.

    Only needed on first login or after session expires (~60 days).
    """
    controller = await get_controller()

    if not controller._apple_findmy:
        raise HTTPException(status_code=503, detail="Find My not configured")

    result = await controller._apple_findmy.submit_2fa_code(cmd.code)
    return {
        "success": result,
        "connected": controller._apple_findmy.is_connected,
    }
