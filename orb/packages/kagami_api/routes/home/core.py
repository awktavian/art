"""Core Smart Home Routes — Status, Rooms, Devices.

~100 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class HomeStatus(BaseModel):
    """Smart home status response."""

    initialized: bool
    integrations: dict[str, bool]
    rooms: int
    occupied_rooms: int
    movie_mode: bool
    avg_temp: float | None = None


# =============================================================================
# HELPER
# =============================================================================


async def get_controller() -> Any:
    """Get the singleton SmartHomeController."""
    try:
        from kagami_smarthome import get_smart_home

        return await get_smart_home()
    except ImportError as e:
        raise HTTPException(status_code=503, detail="Smart home integration not available") from e
    except Exception as e:
        logger.error(f"Failed to get smart home controller: {e}")
        raise HTTPException(status_code=503, detail=f"Smart home initialization failed: {e}") from e


# =============================================================================
# ROUTES
# =============================================================================


@router.get("/status", response_model=HomeStatus)
async def get_status() -> HomeStatus:
    """Get smart home status."""
    controller = await get_controller()
    stats = controller.get_stats()

    return HomeStatus(
        initialized=stats.get("initialized", False),
        integrations=controller.get_integration_status(),
        rooms=stats.get("rooms", 0),
        occupied_rooms=stats.get("occupied_rooms", 0),
        movie_mode=stats.get("movie_mode", False),
        avg_temp=stats.get("avg_temp"),
    )


@router.get("/rooms")
async def get_rooms() -> dict[str, Any]:
    """Get all rooms and their states."""
    controller = await get_controller()
    return {
        "rooms": controller.get_room_states(),
        "count": len(controller.get_all_rooms()),
    }


@router.get("/devices")
async def get_devices() -> dict[str, Any]:
    """Get all discovered devices."""
    controller = await get_controller()
    return controller.get_devices()
