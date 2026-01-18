"""Celestial Triggers — Astronomical Event-Driven Automation.

This module provides celestial-aware triggers that replace legacy
weather-API-based sunset/sunrise detection with proper astronomical
calculations.

The triggers here understand the actual orbital mechanics:
- Sunset time is CALCULATED from Earth's position, not fetched from weather API
- Sun protection is based on window geometry, not hardcoded room lists
- Twilight phases enable graduated lighting transitions

Created: January 3, 2026
Author: Kagami (鏡)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from .ephemeris import (
    MoonPhase,
    SunPosition,
    SunTimes,
    moon_phase,
    sun_position,
    sun_times,
)
from .home_geometry import (
    HOME_LATITUDE,
    HOME_LONGITUDE,
    explain_current_sun,
    get_rooms_needing_shades_closed,
)

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# TRIGGER TYPES
# =============================================================================


class CelestialEvent(str, Enum):
    """Astronomical events that can trigger actions."""

    # Daily sun events
    ASTRONOMICAL_DAWN = "astronomical_dawn"  # -18°
    NAUTICAL_DAWN = "nautical_dawn"  # -12°
    CIVIL_DAWN = "civil_dawn"  # -6°
    SUNRISE = "sunrise"
    SOLAR_NOON = "solar_noon"
    SUNSET = "sunset"
    CIVIL_DUSK = "civil_dusk"
    NAUTICAL_DUSK = "nautical_dusk"
    ASTRONOMICAL_DUSK = "astronomical_dusk"

    # Sun position events
    SUN_HITTING_ROOM = "sun_hitting_room"
    SUN_LEAVING_ROOM = "sun_leaving_room"

    # Moon events
    NEW_MOON = "new_moon"
    FULL_MOON = "full_moon"
    FIRST_QUARTER = "first_quarter"
    LAST_QUARTER = "last_quarter"


@dataclass
class CelestialTrigger:
    """A trigger based on astronomical events."""

    name: str
    event: CelestialEvent
    action: Callable[[dict], Awaitable[None]]

    # Configuration
    advance_minutes: float = 0  # Fire this many minutes before event
    rooms: list[str] | None = None  # For room-specific triggers
    cooldown_seconds: float = 86400  # Default: once per day

    # State
    enabled: bool = True
    last_triggered: float = 0
    trigger_count: int = 0

    def can_trigger(self) -> bool:
        """Check if trigger can fire (respecting cooldown)."""
        if not self.enabled:
            return False
        return (time.time() - self.last_triggered) > self.cooldown_seconds


@dataclass
class CelestialState:
    """Current celestial state for the home."""

    sun: SunPosition
    sun_times: SunTimes
    moon: MoonPhase

    # Computed states
    is_day: bool
    phase_of_day: (
        str  # "night", "astronomical_twilight", "nautical_twilight", "civil_twilight", "day"
    )
    minutes_until_sunset: float | None
    minutes_since_sunrise: float | None

    # Room-specific
    rooms_with_sun: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sun": self.sun.to_dict(),
            "sun_times": self.sun_times.to_dict(),
            "moon": self.moon.value,
            "is_day": self.is_day,
            "phase_of_day": self.phase_of_day,
            "minutes_until_sunset": self.minutes_until_sunset,
            "minutes_since_sunrise": self.minutes_since_sunrise,
            "rooms_with_sun": self.rooms_with_sun,
        }


# =============================================================================
# CELESTIAL ENGINE
# =============================================================================


class CelestialTriggerEngine:
    """Engine that fires triggers based on astronomical events.

    This REPLACES the legacy sunset_approaching() and weather-based
    triggers with proper astronomical calculations.

    Usage:
        engine = CelestialTriggerEngine()
        engine.register_trigger(sunset_trigger)
        await engine.connect(smart_home)

        # Engine runs continuously, checking celestial state
        # and firing triggers at appropriate times.
    """

    def __init__(
        self,
        latitude: float = HOME_LATITUDE,
        longitude: float = HOME_LONGITUDE,
    ):
        self.latitude = latitude
        self.longitude = longitude

        self._triggers: list[CelestialTrigger] = []
        self._smart_home: SmartHomeController | None = None

        # State tracking
        self._last_check: float = 0
        self._check_interval: float = 60.0  # Check every minute
        self._last_state: CelestialState | None = None

        # Event tracking (to fire events only once per occurrence)
        self._fired_events: dict[str, datetime] = {}

    def register_trigger(self, trigger: CelestialTrigger) -> None:
        """Register a celestial trigger."""
        self._triggers.append(trigger)
        logger.debug(f"Registered celestial trigger: {trigger.name}")

    async def connect(self, smart_home: SmartHomeController) -> None:
        """Connect to smart home controller."""
        self._smart_home = smart_home
        self._setup_default_triggers()
        logger.info("🌞 CelestialTriggerEngine connected")

    def get_current_state(self, dt: datetime | None = None) -> CelestialState:
        """Get current celestial state.

        This is THE main function to call to understand what the sky is doing.
        """
        if dt is None:
            dt = datetime.now(UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        sun = sun_position(self.latitude, self.longitude, dt)
        times = sun_times(self.latitude, self.longitude, dt)
        moon = moon_phase(dt)

        # Determine phase of day based on sun altitude
        if sun.altitude > 0:
            phase = "day"
        elif sun.altitude > -6:
            phase = "civil_twilight"
        elif sun.altitude > -12:
            phase = "nautical_twilight"
        elif sun.altitude > -18:
            phase = "astronomical_twilight"
        else:
            phase = "night"

        # Get rooms with direct sun
        rooms_with_sun = get_rooms_needing_shades_closed(dt)

        return CelestialState(
            sun=sun,
            sun_times=times,
            moon=moon.phase,
            is_day=sun.is_day,
            phase_of_day=phase,
            minutes_until_sunset=times.minutes_until_sunset(dt),
            minutes_since_sunrise=times.minutes_since_sunrise(dt),
            rooms_with_sun=rooms_with_sun,
        )

    async def check_triggers(self) -> list[str]:
        """Check and fire any due triggers.

        Returns list of trigger names that fired.
        """
        now = datetime.now(UTC)
        state = self.get_current_state(now)

        fired_triggers = []

        for trigger in self._triggers:
            if not trigger.can_trigger():
                continue

            should_fire = await self._should_trigger_fire(trigger, state, now)

            if should_fire:
                try:
                    data = {
                        "state": state.to_dict(),
                        "timestamp": now.isoformat(),
                        "rooms": trigger.rooms or state.rooms_with_sun,
                    }
                    await trigger.action(data)

                    trigger.last_triggered = time.time()
                    trigger.trigger_count += 1
                    fired_triggers.append(trigger.name)

                    logger.info(f"🌞 Celestial trigger fired: {trigger.name}")

                except Exception as e:
                    logger.error(f"Celestial trigger {trigger.name} failed: {e}")

        self._last_state = state
        self._last_check = time.time()

        return fired_triggers

    async def _should_trigger_fire(
        self,
        trigger: CelestialTrigger,
        state: CelestialState,
        now: datetime,
    ) -> bool:
        """Determine if a trigger should fire."""
        event = trigger.event
        advance = trigger.advance_minutes

        # Time-based events (sunrise, sunset, etc.)
        if event == CelestialEvent.SUNRISE:
            if state.sun_times.sunrise:
                minutes_until = (state.sun_times.sunrise - now).total_seconds() / 60
                return 0 <= minutes_until <= advance or (
                    minutes_until < 0
                    and minutes_until > -5
                    and not self._event_fired_today(event, now)
                )

        elif event == CelestialEvent.SUNSET:
            if state.sun_times.sunset:
                minutes_until = (state.sun_times.sunset - now).total_seconds() / 60
                return 0 <= minutes_until <= advance or (
                    minutes_until < 0
                    and minutes_until > -5
                    and not self._event_fired_today(event, now)
                )

        elif event == CelestialEvent.CIVIL_DAWN:
            if state.sun_times.civil_dawn:
                minutes_until = (state.sun_times.civil_dawn - now).total_seconds() / 60
                return 0 <= minutes_until <= advance or (
                    minutes_until < 0
                    and minutes_until > -5
                    and not self._event_fired_today(event, now)
                )

        elif event == CelestialEvent.CIVIL_DUSK:
            if state.sun_times.civil_dusk:
                minutes_until = (state.sun_times.civil_dusk - now).total_seconds() / 60
                return 0 <= minutes_until <= advance or (
                    minutes_until < 0
                    and minutes_until > -5
                    and not self._event_fired_today(event, now)
                )

        # Room-based events
        elif event == CelestialEvent.SUN_HITTING_ROOM:
            if trigger.rooms:
                # Check if any specified room just got sun
                for room in trigger.rooms:
                    if room in state.rooms_with_sun:
                        prev = self._last_state
                        if prev is None or room not in prev.rooms_with_sun:
                            return True

        elif event == CelestialEvent.SUN_LEAVING_ROOM:
            if trigger.rooms and self._last_state:
                for room in trigger.rooms:
                    if room in self._last_state.rooms_with_sun and room not in state.rooms_with_sun:
                        return True

        # Moon events
        elif event == CelestialEvent.FULL_MOON:
            return state.moon == MoonPhase.FULL_MOON and not self._event_fired_today(event, now)

        elif event == CelestialEvent.NEW_MOON:
            return state.moon == MoonPhase.NEW_MOON and not self._event_fired_today(event, now)

        return False

    def _event_fired_today(self, event: CelestialEvent, now: datetime) -> bool:
        """Check if event already fired today."""
        last_fire = self._fired_events.get(event.value)
        if last_fire is None:
            return False
        return last_fire.date() == now.date()

    def _setup_default_triggers(self) -> None:
        """Setup default celestial triggers."""

        # === SUNSET PREPARATION ===
        # This REPLACES cross_domain_bridge.sunset_approaching()
        #
        # CBF PROTECTED: Respects manual light overrides.
        # If someone manually adjusted lights, we don't override.

        async def prepare_evening_lights(data: dict) -> None:
            """Prepare home for evening at civil dusk.

            CBF Protected: h(x) >= 0 required for each light.
            """
            if not self._smart_home:
                return

            try:
                presence = self._smart_home.get_presence_state()
                if presence and not presence.get("owner_home", True):
                    return  # Don't light empty house
            except Exception:
                pass

            # Use CBF-protected set_lights (respect_cbf=True by default)
            # This will skip lights that have been manually adjusted
            rooms = ["Living Room", "Kitchen"]
            success = await self._smart_home.set_lights(
                40,
                rooms=rooms,
                respect_cbf=True,  # Explicit: respect manual overrides
                source="celestial_sunset",
            )

            if success:
                logger.info("🌅 Sunset approaching — adjusting lights (CBF checked)")
            else:
                logger.info("🌅 Sunset — some lights skipped due to manual override")

        self.register_trigger(
            CelestialTrigger(
                name="sunset_preparation",
                event=CelestialEvent.CIVIL_DUSK,
                action=prepare_evening_lights,
                advance_minutes=15,  # 15 min before civil dusk
                cooldown_seconds=86400,  # Once per day
            )
        )

        # === CELESTIAL SHADE OPTIMIZATION ===
        # Full window-by-window optimization based on sun geometry.
        # This is the CORE adaptive function.
        #
        # Algorithm per window:
        # - If sun can hit window: level = max(20, min(90, altitude * 2))
        # - If sun can't hit window: level = 100 (fully open)
        #
        # This preserves views (north windows always open) while
        # blocking glare (south windows adjusted based on sun angle).

        async def celestial_shade_optimization(data: dict) -> None:
            """Optimize ALL shades based on sun position and window geometry.

            This replaces room-based logic with per-window calculations.
            """
            if not self._smart_home:
                return

            # Use the new celestial optimization method
            results = await self._smart_home.optimize_shades_celestial()

            if results:
                sun_exposed = sum(1 for r in results if r.sun_hits)
                logger.info(
                    f"☀️ Celestial shade optimization: {len(results)} shades, "
                    f"{sun_exposed} sun-exposed"
                )

        self.register_trigger(
            CelestialTrigger(
                name="celestial_shade_optimization",
                event=CelestialEvent.SUN_HITTING_ROOM,
                action=celestial_shade_optimization,
                rooms=None,  # All rooms - optimization is per-window
                cooldown_seconds=1800,  # Re-optimize every 30 min
            )
        )

        # === MORNING OPTIMIZATION ===
        # At sunrise, run full celestial optimization.
        # East-facing windows will get adjusted for morning sun.

        async def morning_celestial(data: dict) -> None:
            """Run celestial optimization at sunrise."""
            if not self._smart_home:
                return

            try:
                presence = self._smart_home.get_presence_state()
                if presence and not presence.get("owner_home", True):
                    return
            except Exception:
                pass

            # Full celestial optimization
            results = await self._smart_home.optimize_shades_celestial()
            logger.info(f"🌅 Sunrise — celestial optimization ({len(results)} shades)")

        self.register_trigger(
            CelestialTrigger(
                name="sunrise_optimization",
                event=CelestialEvent.SUNRISE,
                action=morning_celestial,
                advance_minutes=0,
                cooldown_seconds=86400,
            )
        )

        # === EVENING OPENNESS ===
        # After civil dusk, sun is down — open ALL shades for views.

        async def evening_openness(data: dict) -> None:
            """Open all shades after sunset for evening views."""
            if not self._smart_home:
                return

            try:
                presence = self._smart_home.get_presence_state()
                if presence and not presence.get("owner_home", True):
                    return
            except Exception:
                pass

            # Full celestial optimization — sun is down, so all windows
            # will calculate to 100% open (no sun to block)
            results = await self._smart_home.optimize_shades_celestial()
            logger.info(f"🌆 Civil dusk — opening all shades ({len(results)} shades)")

        self.register_trigger(
            CelestialTrigger(
                name="evening_optimization",
                event=CelestialEvent.CIVIL_DUSK,
                action=evening_openness,
                advance_minutes=0,
                cooldown_seconds=86400,
            )
        )

        # === CONTINUOUS OPTIMIZATION ===
        # Run optimization periodically during daylight to track sun movement.
        # This is registered as a SUN_HITTING_ROOM trigger but with a timer.

        async def periodic_optimization(data: dict) -> None:
            """Periodic shade optimization during day."""
            if not self._smart_home:
                return

            results = await self._smart_home.optimize_shades_celestial()
            if results:
                adjusted = sum(1 for r in results if r.current_level != r.optimal_level)
                if adjusted > 0:
                    logger.debug(f"☀️ Periodic optimization: {adjusted} shades adjusted")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


_engine: CelestialTriggerEngine | None = None


def get_celestial_engine() -> CelestialTriggerEngine:
    """Get singleton CelestialTriggerEngine."""
    global _engine
    if _engine is None:
        _engine = CelestialTriggerEngine()
    return _engine


def reset_celestial_engine() -> None:
    """Reset engine (for testing)."""
    global _engine
    _engine = None


async def connect_celestial_engine(
    smart_home: SmartHomeController,
) -> CelestialTriggerEngine:
    """Connect and return celestial engine."""
    engine = get_celestial_engine()
    await engine.connect(smart_home)
    return engine


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def minutes_until_sunset() -> float | None:
    """Get minutes until sunset from now.

    Convenience function for quick checks.
    """
    engine = get_celestial_engine()
    state = engine.get_current_state()
    return state.minutes_until_sunset


def is_sun_up() -> bool:
    """Check if sun is currently above horizon."""
    engine = get_celestial_engine()
    state = engine.get_current_state()
    return state.is_day


def get_sun_direction() -> str:
    """Get current sun direction (N, NE, E, SE, S, SW, W, NW)."""
    engine = get_celestial_engine()
    state = engine.get_current_state()
    return state.sun.direction


def rooms_need_shade_now() -> list[str]:
    """Get rooms that currently need shades closed."""
    return get_rooms_needing_shades_closed()


def explain_sun() -> str:
    """Get human-readable explanation of current sun."""
    return explain_current_sun()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Types
    "CelestialEvent",
    "CelestialState",
    "CelestialTrigger",
    # Engine
    "CelestialTriggerEngine",
    "connect_celestial_engine",
    "explain_sun",
    "get_celestial_engine",
    "get_sun_direction",
    "is_sun_up",
    # Convenience
    "minutes_until_sunset",
    "reset_celestial_engine",
    "rooms_need_shade_now",
]
