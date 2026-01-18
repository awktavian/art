"""Enhanced Context Tracker for Ambient OS.

Tracks comprehensive context:
- Location (GPS, WiFi triangulation)
- Activity (stationary, walking, running, driving)
- Time (time of day, day of week)
- Environment (home, work, commute)
- User state (focused, idle, sleeping)

Created: November 10, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Activity(Enum):
    """User activity states."""

    STATIONARY = "stationary"
    WALKING = "walking"
    RUNNING = "running"
    DRIVING = "driving"
    CYCLING = "cycling"
    UNKNOWN = "unknown"


class Environment(Enum):
    """User environment contexts."""

    HOME = "home"
    WORK = "work"
    COMMUTE = "commute"
    GYM = "gym"
    OUTDOORS = "outdoors"
    UNKNOWN = "unknown"


@dataclass
class UserContext:
    """Complete user context snapshot."""

    # Location
    latitude: float
    longitude: float
    altitude: float
    location_accuracy: float

    # Activity
    activity: Activity
    activity_confidence: float
    steps_today: int

    # Time
    hour: int
    day_of_week: int  # 0=Monday
    is_weekend: bool

    # Environment
    environment: Environment
    environment_confidence: float

    # User state
    is_focused: bool
    is_idle: bool
    is_sleeping: bool

    # Device
    battery_level: float
    is_charging: bool

    timestamp: float = field(default_factory=time.time)


class ContextTracker:
    """Tracks comprehensive user context.

    NOTE: No internal loop. Celery Beat calls update_context() periodically.
    """

    def __init__(self) -> None:
        """Initialize context tracker."""
        self._current_context: UserContext | None = None
        self._context_history: list[UserContext] = []

        # Known locations (for environment detection)
        self._known_locations = {
            "home": (0.0, 0.0, 100.0),  # (lat, lon, radius_m)
            "work": (0.0, 0.0, 100.0),
        }

    async def update_context(self) -> dict[str, Any]:
        """Update context (called by Celery Beat).

        Returns:
            Context update results
        """
        try:
            context = await self._gather_context()
            self._current_context = context
            self._context_history.append(context)

            # Keep history bounded
            if len(self._context_history) > 1000:
                self._context_history = self._context_history[-500:]

            return {
                "status": "success",
                "activity": context.activity.value,
                "environment": context.environment.value,
                "history_size": len(self._context_history),
            }
        except Exception as e:
            logger.error(f"Context update error: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def _gather_context(self) -> UserContext:
        """Gather complete context snapshot."""
        # Get location
        location = await self._get_location()

        # Get activity
        activity, activity_conf = await self._detect_activity()

        # Get time context
        now = datetime.now()
        hour = now.hour
        day_of_week = now.weekday()
        is_weekend = day_of_week >= 5

        # Get environment
        environment, env_conf = await self._detect_environment(
            location["latitude"], location["longitude"]
        )

        # Get user state
        user_state = await self._detect_user_state()

        # Get device state
        device_state = await self._get_device_state()

        return UserContext(
            latitude=location["latitude"],
            longitude=location["longitude"],
            altitude=location["altitude"],
            location_accuracy=location["accuracy"],
            activity=activity,
            activity_confidence=activity_conf,
            steps_today=user_state["steps"],
            hour=hour,
            day_of_week=day_of_week,
            is_weekend=is_weekend,
            environment=environment,
            environment_confidence=env_conf,
            is_focused=user_state["focused"],
            is_idle=user_state["idle"],
            is_sleeping=user_state["sleeping"],
            battery_level=device_state["battery"],
            is_charging=device_state["charging"],
        )

    async def _get_location(self) -> dict[str, float]:
        """Get current location."""
        try:
            from kagami.core.drivers.sensors.gps import (
                GPSDriver,  # pyright: ignore[reportMissingImports]
            )

            driver = GPSDriver()
            if not driver.initialized:
                await driver.probe()
                await driver.initialize()

            reading = await driver.read_position()

            return {
                "latitude": reading.latitude,
                "longitude": reading.longitude,
                "altitude": reading.altitude,
                "accuracy": reading.accuracy,
            }

        except (ImportError, Exception) as e:
            logger.debug(f"GPS unavailable: {e}")
            return {
                "latitude": 0.0,
                "longitude": 0.0,
                "altitude": 0.0,
                "accuracy": 9999.0,
            }

    async def _detect_activity(self) -> tuple[Activity, float]:
        """Detect user activity from accelerometer."""
        try:
            from kagami.core.drivers.sensors.imu import (
                IMUDriver,  # pyright: ignore[reportMissingImports]
            )

            driver = IMUDriver()
            if not driver.initialized:
                await driver.probe()
                await driver.initialize()

            # Read accelerometer
            accel = await driver.read_accelerometer()

            # Calculate magnitude
            import math

            magnitude = math.sqrt(accel.x**2 + accel.y**2 + accel.z**2)

            # Classify activity (simplified)
            if magnitude < 0.5:
                return (Activity.STATIONARY, 0.9)
            elif magnitude < 2.0:
                return (Activity.WALKING, 0.7)
            elif magnitude < 5.0:
                return (Activity.RUNNING, 0.6)
            else:
                return (Activity.UNKNOWN, 0.3)

        except Exception as e:
            logger.debug(f"Activity detection unavailable: {e}")
            return (Activity.UNKNOWN, 0.0)

    async def _detect_environment(self, lat: float, lon: float) -> tuple[Environment, float]:
        """Detect environment from location."""
        # Check known locations
        for name, (known_lat, known_lon, radius_m) in self._known_locations.items():
            import math

            # Simple distance (not accurate for long distances)
            lat_diff = (lat - known_lat) * 111000  # ~111km per degree
            lon_diff = (lon - known_lon) * 111000 * math.cos(math.radians(lat))
            distance = math.sqrt(lat_diff**2 + lon_diff**2)

            if distance < radius_m:
                if name == "home":
                    return (Environment.HOME, 0.9)
                elif name == "work":
                    return (Environment.WORK, 0.9)

        return (Environment.UNKNOWN, 0.3)

    async def _detect_user_state(self) -> dict[str, Any]:
        """Detect user state."""
        # Would use:
        # - Screen on/off
        # - Keyboard/mouse activity
        # - Heart rate
        # - Time of day

        now = datetime.now()
        hour = now.hour

        # Simple heuristics
        is_sleeping = 0 <= hour < 7 or 22 <= hour < 24
        is_idle = False  # Would check last activity time
        is_focused = not is_idle and not is_sleeping

        return {
            "focused": is_focused,
            "idle": is_idle,
            "sleeping": is_sleeping,
            "steps": 0,  # Would integrate pedometer
        }

    async def _get_device_state(self) -> dict[str, Any]:
        """Get device state."""
        try:
            from kagami_hal.power_manager import get_power_manager

            pm = await get_power_manager()
            status = await pm.get_battery_status()

            return {
                "battery": status.level,
                "charging": status.charging,
            }
        except Exception:
            return {"battery": 1.0, "charging": True}

    def get_current_context(self) -> UserContext | None:
        """Get current context snapshot."""
        return self._current_context

    def set_known_location(
        self, name: str, latitude: float, longitude: float, radius_m: float = 100.0
    ) -> None:
        """Register known location.

        Args:
            name: Location name (home, work, etc)
            latitude: Latitude
            longitude: Longitude
            radius_m: Radius in meters
        """
        self._known_locations[name] = (latitude, longitude, radius_m)
        logger.info(f"📍 Known location registered: {name}")


# Global context tracker
_CONTEXT_TRACKER: ContextTracker | None = None


def get_context_tracker() -> ContextTracker:
    """Get global context tracker singleton."""
    global _CONTEXT_TRACKER
    if _CONTEXT_TRACKER is None:
        _CONTEXT_TRACKER = ContextTracker()
    return _CONTEXT_TRACKER
