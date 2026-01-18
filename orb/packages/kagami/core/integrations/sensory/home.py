"""Home sensors - presence, locks, climate, security, cameras.

These sensors integrate with smart home systems via SmartHomeController.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import CachedSense, SenseType

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


class HomeSensors:
    """Home sensing capabilities via SmartHomeController."""

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

    async def poll_presence(self) -> dict[str, Any]:
        """Poll presence state from SmartHome."""
        cached = self._get_cached(SenseType.PRESENCE)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"presence": "unknown"}

        try:
            home_state = self._smart_home.get_state()

            presence = home_state.presence.value if home_state.presence else "unknown"
            activity = home_state.activity.value if home_state.activity else "unknown"

            data = {
                "presence": presence,
                "activity": activity,
                "location": home_state.last_location,
                "wifi_devices": len(home_state.wifi_devices_home),
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Presence poll failed: {e}")
            return {"presence": "unknown", "error": str(e)}

    async def poll_locks(self) -> dict[str, Any]:
        """Poll lock states from SmartHome."""
        cached = self._get_cached(SenseType.LOCKS)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"all_locked": True}

        try:
            lock_states = await self._smart_home.get_lock_states()

            data = {
                "all_locked": all(lock_states.values()) if lock_states else True,
                "locks": lock_states,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Locks poll failed: {e}")
            return {"all_locked": True, "error": str(e)}

    async def poll_climate(self) -> dict[str, Any]:
        """Poll climate state from HVAC."""
        cached = self._get_cached(SenseType.CLIMATE)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"avg_temp": 72.0}

        try:
            avg_temp = self._smart_home.get_average_temp()
            hvac_temps = self._smart_home.get_hvac_temps()

            data = {
                "avg_temp": avg_temp,
                "zones": hvac_temps,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Climate poll failed: {e}")
            return {"avg_temp": 72.0, "error": str(e)}

    async def poll_security(self) -> dict[str, Any]:
        """Poll security system state."""
        cached = self._get_cached(SenseType.SECURITY)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"alarm_active": False}

        try:
            home_state = self._smart_home.get_state()

            data = {
                "security_state": home_state.security.value if home_state.security else "unknown",
                "alarm_active": False,
                "doors_locked": True,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Security poll failed: {e}")
            return {"alarm_active": False, "error": str(e)}

    async def poll_cameras(self) -> dict[str, Any]:
        """Poll camera states and snapshot availability."""
        cached = self._get_cached(SenseType.CAMERAS)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"cameras": [], "count": 0}

        try:
            unifi = getattr(self._smart_home, "_unifi", None)
            if not unifi or not hasattr(unifi, "get_cameras"):
                return {"cameras": [], "count": 0}

            cameras_info = unifi.get_cameras()

            cameras = []
            for cam_id, cam_data in cameras_info.items():
                features = cam_data.get("features", {})
                cameras.append(
                    {
                        "id": cam_id,
                        "name": cam_data.get("name", "Unknown"),
                        "online": cam_data.get("is_connected", False),
                        "has_motion": cam_data.get("last_motion") is not None,
                        "has_microphone": features.get("hasMic", False),
                        "has_speaker": features.get("hasSpeaker", False),
                        "type": cam_data.get("type", ""),
                    }
                )

            data = {
                "cameras": cameras,
                "count": len(cameras),
                "online_count": sum(1 for c in cameras if c["online"]),
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Cameras poll failed: {e}")
            return {"cameras": [], "count": 0, "error": str(e)}


__all__ = ["HomeSensors"]
