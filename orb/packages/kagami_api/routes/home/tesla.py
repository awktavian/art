"""Tesla Vehicle Routes.

~200 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .core import get_controller

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================


class TeslaStatus(BaseModel):
    """Tesla vehicle status."""

    connected: bool
    is_home: bool
    battery_level: int
    charging: bool
    climate_on: bool
    locked: bool
    inside_temp: float | None = None
    outside_temp: float | None = None


class TeslaClimateCommand(BaseModel):
    """Command to control Tesla climate."""

    temp_c: float = Field(default=21.0, ge=15, le=28, description="Temperature in Celsius")


# =============================================================================
# ROUTES
# =============================================================================


@router.get("/tesla/status", response_model=TeslaStatus)
async def get_tesla_status() -> TeslaStatus:
    """Get Tesla vehicle status."""
    controller = await get_controller()

    try:
        tesla = controller._tesla
        if not tesla or not tesla.is_connected:
            return TeslaStatus(
                connected=False,
                is_home=False,
                battery_level=0,
                charging=False,
                climate_on=False,
                locked=True,
            )

        state = tesla.get_state()
        return TeslaStatus(
            connected=True,
            is_home=tesla.is_home(),
            battery_level=state.battery_level if state else 0,
            charging=tesla.is_charging(),
            climate_on=state.climate_on if state else False,
            locked=state.locked if state else True,
            inside_temp=state.inside_temp if state else None,
            outside_temp=state.outside_temp if state else None,
        )
    except Exception as e:
        logger.error(f"Tesla status error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/tesla/climate/start")
async def start_tesla_climate(cmd: TeslaClimateCommand | None = None) -> dict[str, Any]:
    """Start Tesla climate preconditioning."""
    controller = await get_controller()
    temp = cmd.temp_c if cmd else 21.0
    result = await controller.precondition_car(temp)
    return {"success": result, "temp_c": temp}


@router.post("/tesla/climate/stop")
async def stop_tesla_climate() -> dict[str, Any]:
    """Stop Tesla climate."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        result = await tesla.stop_climate()
        return {"success": result}
    return {"success": False, "error": "Tesla not connected"}


@router.post("/tesla/charge/start")
async def start_tesla_charging() -> dict[str, Any]:
    """Start Tesla charging."""
    controller = await get_controller()
    result = await controller.start_car_charging()
    return {"success": result}


@router.post("/tesla/charge/stop")
async def stop_tesla_charging() -> dict[str, Any]:
    """Stop Tesla charging."""
    controller = await get_controller()
    result = await controller.stop_car_charging()
    return {"success": result}


@router.post("/tesla/charge/limit")
async def set_tesla_charge_limit(percent: int = Query(..., ge=50, le=100)) -> dict[str, Any]:
    """Set Tesla charge limit percentage."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        result = await tesla.set_charge_limit(percent)
        return {"success": result, "limit": percent}
    return {"success": False, "error": "Tesla not connected"}


@router.post("/tesla/lock")
async def lock_tesla() -> dict[str, Any]:
    """Lock Tesla doors."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        result = await tesla.lock()
        return {"success": result}
    return {"success": False, "error": "Tesla not connected"}


@router.post("/tesla/unlock")
async def unlock_tesla() -> dict[str, Any]:
    """Unlock Tesla doors (requires CBF check if moving)."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        # Check safety barrier
        try:
            from kagami_smarthome.integrations.tesla import TeslaSafetyBarrier

            barrier = TeslaSafetyBarrier(tesla)
            allowed, reason = barrier.check_command("door_unlock")
            if not allowed:
                return {"success": False, "error": f"Blocked: {reason}"}
        except ImportError:
            pass

        result = await tesla.unlock()
        return {"success": result}
    return {"success": False, "error": "Tesla not connected"}


@router.post("/tesla/trunk")
async def open_tesla_trunk(which: str = Query("rear", enum=["rear", "front"])) -> dict[str, Any]:
    """Open Tesla trunk or frunk."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        if which == "front":
            result = await tesla.open_frunk()
        else:
            result = await tesla.open_trunk()
        return {"success": result, "which": which}
    return {"success": False, "error": "Tesla not connected"}


@router.post("/tesla/flash")
async def flash_tesla_lights() -> dict[str, Any]:
    """Flash Tesla lights."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        result = await tesla.flash_lights()
        return {"success": result}
    return {"success": False, "error": "Tesla not connected"}


@router.post("/tesla/honk")
async def honk_tesla_horn() -> dict[str, Any]:
    """Honk Tesla horn."""
    controller = await get_controller()
    tesla = controller._tesla
    if tesla and tesla.is_connected:
        result = await tesla.honk()
        return {"success": result}
    return {"success": False, "error": "Tesla not connected"}
