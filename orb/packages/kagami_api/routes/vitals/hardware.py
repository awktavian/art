"""Hardware Vitals - HAL subsystem health.

Reports on hardware abstraction layer adapters:
- Display, audio, input, sensors, power
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/hal", tags=["vitals"])

    @router.get("/")
    async def hal_health(request: Request) -> dict[str, Any]:
        """Get HAL subsystem health."""
        try:
            hal = getattr(request.app.state, "hal_manager", None)
            if not hal:
                return {"status": "unavailable", "message": "HAL not initialized"}

            status = hal.get_status()
            available_count = sum(
                [
                    status.display_available,
                    status.audio_available,
                    status.input_available,
                    status.sensors_available,
                    status.power_available,
                ]
            )

            overall = "healthy"
            if available_count == 0:
                overall = "unavailable"
            elif status.adapters_failed > 0:
                overall = "degraded"

            return {
                "status": overall,
                "platform": status.platform.value,
                "mock_mode": status.mock_mode,
                "adapters": {
                    "display": status.display_available,
                    "audio": status.audio_available,
                    "input": status.input_available,
                    "sensors": status.sensors_available,
                    "power": status.power_available,
                },
                "initialized": status.adapters_initialized,
                "failed": status.adapters_failed,
            }
        except Exception as e:
            logger.error(f"HAL health check failed: {e}")
            return {"status": "error", "error": str(e)}

    @router.get("/adapters")
    async def list_adapters(request: Request) -> dict[str, Any]:
        """List all HAL adapters with details."""
        try:
            hal = getattr(request.app.state, "hal_manager", None)
            if not hal:
                return {"error": "HAL not initialized"}

            adapters = {}

            # Display
            if hal.display:
                try:
                    info = await hal.display.get_info()
                    adapters["display"] = {
                        "available": True,
                        "width": info.width,
                        "height": info.height,
                        "refresh_rate": info.refresh_rate,
                    }
                except Exception as e:
                    adapters["display"] = {"available": False, "error": str(e)}
            else:
                adapters["display"] = {"available": False}

            # Audio
            if hal.audio:
                try:
                    volume = await hal.audio.get_volume()
                    adapters["audio"] = {"available": True, "volume": volume}
                except Exception as e:
                    adapters["audio"] = {"available": False, "error": str(e)}
            else:
                adapters["audio"] = {"available": False}

            # Input
            if hal.input:
                adapters["input"] = {"available": True}
            else:
                adapters["input"] = {"available": False}

            # Sensors
            if hal.sensors:
                try:
                    sensors = await hal.sensors.list_sensors()
                    adapters["sensors"] = {
                        "available": True,
                        "sensors": [s.value for s in sensors],
                    }
                except Exception as e:
                    adapters["sensors"] = {"available": False, "error": str(e)}
            else:
                adapters["sensors"] = {"available": False}

            # Power
            if hal.power:
                try:
                    battery = await hal.power.get_battery_status()
                    adapters["power"] = {
                        "available": True,
                        "battery_level": battery.level,
                        "charging": battery.charging,
                    }
                except Exception as e:
                    adapters["power"] = {"available": False, "error": str(e)}
            else:
                adapters["power"] = {"available": False}

            return {"adapters": adapters}
        except Exception as e:
            logger.error(f"List adapters failed: {e}")
            return {"error": str(e)}

    return router
