"""Device Routes — TV Mount, Fireplace.

~120 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from .core import get_controller

router = APIRouter()


# =============================================================================
# TV / MANTELMOUNT
# =============================================================================


@router.post("/tv/raise")
async def raise_tv() -> dict[str, Any]:
    """Raise the TV (MantelMount to home position)."""
    controller = await get_controller()
    result = await controller.raise_tv()
    return {"success": result, "action": "raise"}


@router.post("/tv/lower")
async def lower_tv(
    preset: int = Query(1, ge=1, le=3, description="Memory preset 1-3 (1=viewing)"),
) -> dict[str, Any]:
    """Lower the TV to viewing position using preset (safe, repeatable)."""
    controller = await get_controller()
    result = await controller.lower_tv(preset)
    return {"success": result, "action": "lower", "preset": preset}


@router.post("/tv/stop")
async def stop_tv() -> dict[str, Any]:
    """Stop TV mount movement."""
    controller = await get_controller()
    result = await controller.stop_tv()
    return {"success": result, "action": "stop"}


@router.post("/tv/preset")
async def tv_preset(
    preset: int = Query(1, ge=1, le=3, description="Memory preset 1-3"),
) -> dict[str, Any]:
    """Move TV to saved preset position."""
    controller = await get_controller()
    result = await controller.tv_preset(preset)
    return {"success": result, "action": "preset", "preset": preset}


@router.get("/tv/state")
async def get_tv_state() -> dict[str, Any]:
    """Get TV mount state."""
    controller = await get_controller()
    return await controller.get_tv_mount_state()


# =============================================================================
# FIREPLACE
# =============================================================================


@router.post("/fireplace/on")
async def fireplace_on() -> dict[str, Any]:
    """Turn on fireplace."""
    controller = await get_controller()
    result = await controller.fireplace_on()
    return {"success": result, "action": "on"}


@router.post("/fireplace/off")
async def fireplace_off() -> dict[str, Any]:
    """Turn off fireplace."""
    controller = await get_controller()
    result = await controller.fireplace_off()
    return {"success": result, "action": "off"}


@router.get("/fireplace")
async def get_fireplace_state() -> dict[str, Any]:
    """Get fireplace state."""
    controller = await get_controller()
    return await controller.get_fireplace_state()
