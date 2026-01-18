"""Lighting Routes — Lights, Shades, Scenes.

~150 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

# Import command schemas from single source of truth
from kagami_smarthome.schemas.commands import (
    LightCommand,
    SceneCommand,
    ShadeCommand,
)

from .core import get_controller

router = APIRouter()


# =============================================================================
# SHADE CONTROL
# =============================================================================


@router.post("/shades/open")
async def open_shades(cmd: ShadeCommand | None = None) -> dict[str, Any]:
    """Open shades (raise them up)."""
    controller = await get_controller()
    rooms = cmd.rooms if cmd else None
    result = await controller.open_shades(rooms)
    return {"success": result, "action": "open", "rooms": rooms}


@router.post("/shades/close")
async def close_shades(cmd: ShadeCommand | None = None) -> dict[str, Any]:
    """Close shades (lower them down)."""
    controller = await get_controller()
    rooms = cmd.rooms if cmd else None
    result = await controller.close_shades(rooms)
    return {"success": result, "action": "close", "rooms": rooms}


@router.post("/shades/set")
async def set_shades(cmd: ShadeCommand) -> dict[str, Any]:
    """Set shades to specific level (0=closed, 100=open)."""
    controller = await get_controller()
    if cmd.level is None:
        raise HTTPException(status_code=400, detail="level is required")
    result = await controller.set_shades(cmd.level, cmd.rooms)
    return {"success": result, "level": cmd.level, "rooms": cmd.rooms}


# =============================================================================
# LIGHT CONTROL
# =============================================================================


@router.post("/lights/set")
async def set_lights(cmd: LightCommand) -> dict[str, Any]:
    """Set light level."""
    controller = await get_controller()
    result = await controller.set_lights(cmd.level, cmd.rooms)
    return {"success": result, "level": cmd.level, "rooms": cmd.rooms}


@router.post("/lights/off")
async def lights_off(
    rooms: list[str] | None = Query(None, description="Rooms to turn off"),
) -> dict[str, Any]:
    """Turn off lights."""
    controller = await get_controller()
    result = await controller.set_lights(0, rooms)
    return {"success": result, "action": "off", "rooms": rooms}


# =============================================================================
# SCENES
# =============================================================================


@router.post("/scene")
async def apply_scene(cmd: SceneCommand) -> dict[str, Any]:
    """Apply a scene to a room."""
    controller = await get_controller()
    # Support both API patterns: room+scene or scene_name+rooms
    room = cmd.room
    scene = cmd.scene or cmd.scene_name

    if not room:
        raise HTTPException(status_code=400, detail="room is required")
    if not scene:
        raise HTTPException(status_code=400, detail="scene is required")

    result = await controller.set_room_scene(room, scene)
    return {"success": result, "room": room, "scene": scene}


@router.post("/movie-mode/enter")
async def enter_movie_mode() -> dict[str, Any]:
    """Enter home theater movie mode."""
    controller = await get_controller()
    await controller.enter_movie_mode()
    return {"success": True, "mode": "movie"}


@router.post("/movie-mode/exit")
async def exit_movie_mode() -> dict[str, Any]:
    """Exit home theater movie mode."""
    controller = await get_controller()
    await controller.exit_movie_mode()
    return {"success": True, "mode": "normal"}
