"""Biometric sensors - sleep, health, Apple Health integration.

These sensors track physiological data from Eight Sleep and Apple Health.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import CachedSense, SenseType

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


class BiometricSensors:
    """Biometric sensing capabilities."""

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

    async def poll_sleep(self) -> dict[str, Any]:
        """Poll sleep state from Eight Sleep."""
        cached = self._get_cached(SenseType.SLEEP)
        if cached:
            return cached.data

        if not self._smart_home:
            return {"state": "unknown"}

        try:
            devices = self._smart_home.get_devices()
            eight_sleep = devices.get("eight_sleep", {})

            state = eight_sleep.get("bed_state", "unknown")
            occupied = eight_sleep.get("occupied", False)

            data = {
                "state": state,
                "bed_occupied": occupied,
                "sleep_score": eight_sleep.get("sleep_score"),
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Sleep poll failed: {e}")
            return {"state": "unknown", "error": str(e)}

    async def poll_health(self) -> dict[str, Any]:
        """Poll biometric data from Apple Health integration."""
        cached = self._get_cached(SenseType.HEALTH)
        if cached:
            return cached.data

        try:
            data: dict[str, Any] = {
                "heart_rate": None,
                "resting_heart_rate": None,
                "hrv": None,
                "hrv_status": "unknown",
                "steps": 0,
                "active_calories": 0,
                "exercise_minutes": 0,
                "blood_oxygen": None,
                "sleep_quality": "unknown",
                "all_rings_closed": False,
                "timestamp": datetime.now().isoformat(),
            }

            # Try Apple Health integration
            try:
                from kagami_smarthome.integrations.apple_health import get_apple_health

                health = get_apple_health()
                if health.is_connected:
                    state = health.get_state()

                    data["heart_rate"] = state.heart.heart_rate
                    data["resting_heart_rate"] = state.heart.resting_heart_rate
                    data["hrv"] = state.heart.hrv
                    data["hrv_status"] = state.heart.hrv_status
                    data["is_heart_elevated"] = state.heart.is_elevated

                    data["steps"] = state.activity.steps
                    data["active_calories"] = state.activity.active_calories
                    data["exercise_minutes"] = state.activity.exercise_minutes
                    data["distance_miles"] = state.activity.distance_miles
                    data["all_rings_closed"] = state.activity.all_rings_closed
                    data["move_progress"] = round(state.activity.move_ring_progress, 2)
                    data["exercise_progress"] = round(state.activity.exercise_ring_progress, 2)

                    data["blood_oxygen"] = state.respiratory.blood_oxygen
                    data["oxygen_status"] = state.respiratory.oxygen_status

                    data["sleep_quality"] = state.sleep.sleep_quality
                    data["sleep_score"] = state.sleep.quality_score

            except ImportError:
                logger.debug("Apple Health integration not available")
            except Exception as e:
                logger.debug(f"Apple Health poll failed: {e}")

            # Supplement with Eight Sleep data
            if self._smart_home:
                try:
                    devices = self._smart_home.get_devices()
                    eight_sleep = devices.get("eight_sleep", {})

                    if eight_sleep.get("heart_rate") and data["heart_rate"] is None:
                        data["heart_rate"] = eight_sleep.get("heart_rate")
                    if eight_sleep.get("hrv") and data["hrv"] is None:
                        data["hrv"] = eight_sleep.get("hrv")
                except Exception:
                    pass

            return data

        except Exception as e:
            logger.debug(f"Health poll failed: {e}")
            return {"error": str(e)}

    async def emit_health_alert(self, title: str, message: str, priority: int = 2) -> None:
        """Emit health-related alert to AlertHierarchy."""
        try:
            from kagami.core.integrations.alert_hierarchy import (
                Alert,
                AlertCategory,
                AlertPriority,
                get_alert_hierarchy,
            )

            alert_hierarchy = get_alert_hierarchy()
            alert = Alert(
                id=f"health_{int(time.time())}",
                title=title,
                message=message,
                priority=AlertPriority(priority),
                category=AlertCategory.HEALTH,
                source="apple_health",
            )
            await alert_hierarchy.submit(alert)
        except Exception as e:
            logger.debug(f"Failed to emit health alert: {e}")

    def classify_hrv(self, hrv: float | None) -> str:
        """Classify HRV status based on value."""
        if hrv is None:
            return "unknown"
        if hrv >= 50:
            return "good"
        if hrv >= 30:
            return "normal"
        if hrv >= 20:
            return "low"
        return "very_low"

    def classify_sleep(self, hours: float | None) -> str:
        """Classify sleep quality based on duration."""
        if hours is None:
            return "unknown"
        if hours >= 7 and hours <= 9:
            return "good"
        if hours >= 6:
            return "fair"
        if hours >= 4:
            return "poor"
        return "very_poor"

    def check_rings_closed(self, data: dict[str, Any]) -> bool:
        """Check if activity rings are closed based on goals."""
        move_goal = 500
        exercise_goal = 30

        calories = data.get("active_calories", 0) or 0
        exercise = data.get("exercise_minutes", 0) or 0

        return calories >= move_goal and exercise >= exercise_goal


__all__ = ["BiometricSensors"]
