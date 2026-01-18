"""Vehicle sensors - Tesla integration with location and ETA.

Provides vehicle state, location, battery, and ETA using Google Maps.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import CachedSense, SenseType

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


class VehicleSensors:
    """Vehicle sensing capabilities via Tesla integration."""

    def __init__(
        self,
        cache: dict[SenseType, CachedSense],
        stats: dict[str, Any],
        smart_home: Any = None,
    ):
        self._cache = cache
        self._stats = stats
        self._smart_home: SmartHomeController | None = smart_home

    def set_smart_home(self, smart_home: Any) -> None:
        """Set the smart home controller."""
        self._smart_home = smart_home

    def _get_cached(self, sense_type: SenseType) -> CachedSense | None:
        """Get cached data if valid."""
        cached = self._cache.get(sense_type)
        if cached and cached.is_valid:
            self._stats["cache_hits"] += 1
            return cached
        self._stats["cache_misses"] += 1
        return None

    async def poll_vehicle(self) -> dict[str, Any]:
        """Poll Tesla vehicle for location, ETA, battery.

        Uses Google Maps Distance Matrix API for accurate ETA with traffic.
        """
        cached = self._get_cached(SenseType.VEHICLE)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"available": False}

        try:
            devices = self._smart_home.get_devices()
            tesla = devices.get("tesla", {})

            if not tesla:
                return {"available": False}

            lat = tesla.get("latitude")
            lon = tesla.get("longitude")

            distance_miles = None
            eta_minutes = None
            eta_text = None
            is_home = True
            is_near = True
            is_arriving = False
            is_driving = tesla.get("shift_state") in ["D", "R"]

            if lat and lon:
                try:
                    from kagami_smarthome.integrations.maps import get_distance_to_home

                    location_info = await get_distance_to_home(lat, lon)

                    distance_miles = location_info.distance_miles
                    eta_minutes = (
                        location_info.duration_in_traffic_minutes or location_info.duration_minutes
                    )
                    eta_text = location_info.duration_in_traffic_text or location_info.duration_text
                    is_home = location_info.is_home
                    is_near = location_info.is_near
                    is_arriving = location_info.is_arriving and is_driving

                except Exception as e:
                    logger.debug(f"Maps service unavailable, using estimate: {e}")
                    import math

                    home_lat, home_lon = 47.6762, -122.3405
                    lat_diff = abs(lat - home_lat)
                    lon_diff = abs(lon - home_lon)
                    distance_miles = math.sqrt(lat_diff**2 + lon_diff**2) * 69
                    is_home = distance_miles < 0.1
                    is_near = distance_miles < 2.0
                    eta_minutes = int(distance_miles / 25 * 60 * 1.3) if distance_miles > 0.1 else 0
                    eta_text = f"{eta_minutes} mins (est.)"
                    is_arriving = is_driving and eta_minutes <= 10

            data = {
                "available": True,
                "battery_level": tesla.get("battery_level"),
                "charging": tesla.get("charging_state") == "Charging",
                "range_miles": tesla.get("range_miles"),
                "latitude": lat,
                "longitude": lon,
                "distance_miles": round(distance_miles, 1) if distance_miles else None,
                "eta_minutes": eta_minutes,
                "eta_text": eta_text,
                "is_home": is_home,
                "is_near": is_near,
                "is_driving": is_driving,
                "is_arriving": is_arriving,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Vehicle poll failed: {e}")
            return {"available": False, "error": str(e)}


__all__ = ["VehicleSensors"]
