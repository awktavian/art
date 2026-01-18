"""Climate Routes — HVAC, Locks, House-Wide Scenes.

~120 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .core import get_controller

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class TempCommand(BaseModel):
    """Command to set temperature."""

    room: str = Field(..., description="Room name")
    temp_f: float = Field(..., ge=60, le=85, description="Temperature in Fahrenheit")


# =============================================================================
# HOUSE-WIDE SCENES
# =============================================================================


@router.post("/goodnight")
async def goodnight() -> dict[str, Any]:
    """Execute goodnight routine (all lights off, doors locked, etc.)."""
    controller = await get_controller()
    await controller.goodnight()
    return {"success": True, "action": "goodnight"}


@router.post("/welcome-home")
async def welcome_home() -> dict[str, Any]:
    """Execute welcome home routine."""
    controller = await get_controller()
    await controller.welcome_home()
    return {"success": True, "action": "welcome_home"}


@router.post("/away")
async def set_away() -> dict[str, Any]:
    """Set house to away mode."""
    controller = await get_controller()
    await controller.set_away_mode()
    return {"success": True, "action": "away"}


# =============================================================================
# HVAC
# =============================================================================


@router.post("/temp/set")
async def set_temp(cmd: TempCommand) -> dict[str, Any]:
    """Set room temperature."""
    controller = await get_controller()
    result = await controller.set_room_temp(cmd.room, cmd.temp_f)
    return {"success": result, "room": cmd.room, "temp_f": cmd.temp_f}


@router.get("/temp")
async def get_temps() -> dict[str, Any]:
    """Get all HVAC temperatures."""
    controller = await get_controller()
    return {
        "zones": controller.get_hvac_temps(),
        "average": controller.get_average_temp(),
    }


# =============================================================================
# LOCKS
# =============================================================================


@router.post("/locks/lock-all")
async def lock_all() -> dict[str, Any]:
    """Lock all doors."""
    controller = await get_controller()
    result = await controller.lock_all()
    return {"success": result, "action": "lock_all"}


@router.post("/locks/unlock")
async def unlock_door(door: str = Query(..., description="Door name")) -> dict[str, Any]:
    """Unlock a specific door."""
    controller = await get_controller()
    result = await controller.unlock_door(door)
    return {"success": result, "door": door}


@router.get("/locks")
async def get_locks() -> dict[str, Any]:
    """Get lock states."""
    controller = await get_controller()
    states = await controller.get_lock_states()
    return {"locks": states}
