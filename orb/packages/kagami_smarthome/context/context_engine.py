"""Context Engine — Unified context gathering from all integrations.

Provides a complete context snapshot for adaptive routine decisions.
Gathers data from all integrations in parallel for minimal latency.

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)

# Global context engine instance
_context_engine: ContextEngine | None = None


class CircadianPhase(Enum):
    """Circadian lighting phases."""

    DAWN = "dawn"  # 5-7am
    MORNING = "morning"  # 7-10am
    MIDDAY = "midday"  # 10am-3pm
    AFTERNOON = "afternoon"  # 3-6pm
    EVENING = "evening"  # 6-9pm
    NIGHT = "night"  # 9-11pm
    LATE_NIGHT = "late_night"  # 11pm-5am


class GuestMode(Enum):
    """Guest mode states."""

    NONE = "none"
    GUEST_PRESENT = "guest_present"
    PARTY = "party"
    AIRBNB = "airbnb"


@dataclass
class HomeContext:
    """Complete context snapshot for routine decisions."""

    # Time
    time: datetime
    circadian_phase: CircadianPhase
    day_of_week: int  # 0=Monday, 6=Sunday
    is_weekend: bool
    is_holiday: bool

    # Presence
    owner_home: bool
    owner_location: str | None  # Room name
    owner_just_arrived: bool = False
    owner_just_left: bool = False
    guests_present: bool = False
    guest_count: int = 0

    # Activity
    detected_activity: str | None = None  # sleeping, working, cooking, etc.
    time_in_activity: float = 0.0  # seconds

    # Environment
    outdoor_light_level: float = 50.0  # 0-100
    weather: str = "clear"
    outdoor_temp_f: float = 70.0

    # State
    vacation_mode: bool = False
    guest_mode: GuestMode = GuestMode.NONE
    security_armed: bool = False

    # Sleep
    owner_in_bed: bool = False
    sleep_stage: str | None = None

    # History
    last_manual_override: float | None = None  # timestamp
    last_routine_execution: dict[str, float] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """Get a summary of the context for logging."""
        return {
            "time": self.time.isoformat(),
            "phase": self.circadian_phase.value,
            "owner_home": self.owner_home,
            "owner_location": self.owner_location,
            "activity": self.detected_activity,
            "guest_mode": self.guest_mode.value,
            "vacation_mode": self.vacation_mode,
            "owner_in_bed": self.owner_in_bed,
        }


def get_circadian_phase(dt: datetime | None = None) -> CircadianPhase:
    """Get circadian phase for a given time."""
    if dt is None:
        dt = datetime.now()

    hour = dt.hour

    if 5 <= hour < 7:
        return CircadianPhase.DAWN
    elif 7 <= hour < 10:
        return CircadianPhase.MORNING
    elif 10 <= hour < 15:
        return CircadianPhase.MIDDAY
    elif 15 <= hour < 18:
        return CircadianPhase.AFTERNOON
    elif 18 <= hour < 21:
        return CircadianPhase.EVENING
    elif 21 <= hour < 23:
        return CircadianPhase.NIGHT
    else:
        return CircadianPhase.LATE_NIGHT


def get_circadian_color_temp(phase: CircadianPhase | None = None) -> int:
    """Get recommended color temperature (Kelvin) for circadian phase."""
    if phase is None:
        phase = get_circadian_phase()

    color_temps = {
        CircadianPhase.DAWN: 2400,
        CircadianPhase.MORNING: 3500,
        CircadianPhase.MIDDAY: 4500,
        CircadianPhase.AFTERNOON: 4000,
        CircadianPhase.EVENING: 3000,
        CircadianPhase.NIGHT: 2700,
        CircadianPhase.LATE_NIGHT: 2200,
    }
    return color_temps.get(phase, 3500)


def get_circadian_max_brightness(phase: CircadianPhase | None = None) -> int:
    """Get recommended max brightness (0-100) for circadian phase."""
    if phase is None:
        phase = get_circadian_phase()

    brightness = {
        CircadianPhase.DAWN: 40,
        CircadianPhase.MORNING: 100,
        CircadianPhase.MIDDAY: 100,
        CircadianPhase.AFTERNOON: 100,
        CircadianPhase.EVENING: 80,
        CircadianPhase.NIGHT: 50,
        CircadianPhase.LATE_NIGHT: 20,
    }
    return brightness.get(phase, 100)


def _get_easter_date(year: int) -> date:
    """Calculate Easter Sunday for a given year using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month = (h + el - 7 * m + 114) // 31
    day = ((h + el - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month.

    Args:
        year: The year
        month: The month (1-12)
        weekday: Day of week (0=Monday, 6=Sunday)
        n: Which occurrence (1=first, 2=second, etc.)

    Returns:
        The date of the nth weekday in that month
    """
    first_day = date(year, month, 1)
    # Days until first occurrence of target weekday
    days_until = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day.replace(day=1 + days_until)
    # Add weeks for nth occurrence
    return first_occurrence.replace(day=first_occurrence.day + 7 * (n - 1))


def _get_last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Get the last occurrence of a weekday in a month."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    # Go back one day to last day of target month
    last_day = next_month.replace(day=1)
    from datetime import timedelta

    last_day = last_day - timedelta(days=1)
    # Find last occurrence of weekday
    days_back = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_back)


def is_us_holiday(check_date: date | None = None) -> bool:
    """Check if a date is a US federal holiday.

    Includes major US holidays that typically affect work schedules:
    - New Year's Day (Jan 1)
    - Martin Luther King Jr. Day (3rd Monday of January)
    - Presidents' Day (3rd Monday of February)
    - Good Friday (Friday before Easter)
    - Memorial Day (Last Monday of May)
    - Juneteenth (June 19)
    - Independence Day (July 4)
    - Labor Day (1st Monday of September)
    - Columbus Day (2nd Monday of October)
    - Veterans Day (November 11)
    - Thanksgiving (4th Thursday of November)
    - Day after Thanksgiving (4th Friday of November)
    - Christmas Eve (December 24)
    - Christmas Day (December 25)
    - New Year's Eve (December 31)

    Args:
        check_date: Date to check. Defaults to today.

    Returns:
        True if the date is a holiday
    """
    if check_date is None:
        check_date = date.today()

    year = check_date.year
    month = check_date.month
    day = check_date.day

    # Fixed date holidays
    fixed_holidays = [
        (1, 1),  # New Year's Day
        (6, 19),  # Juneteenth
        (7, 4),  # Independence Day
        (11, 11),  # Veterans Day
        (12, 24),  # Christmas Eve
        (12, 25),  # Christmas Day
        (12, 31),  # New Year's Eve
    ]

    if (month, day) in fixed_holidays:
        return True

    # Floating holidays (weekday-based)
    floating_holidays = [
        _get_nth_weekday_of_month(year, 1, 0, 3),  # MLK Day: 3rd Monday Jan
        _get_nth_weekday_of_month(year, 2, 0, 3),  # Presidents' Day: 3rd Monday Feb
        _get_last_weekday_of_month(year, 5, 0),  # Memorial Day: Last Monday May
        _get_nth_weekday_of_month(year, 9, 0, 1),  # Labor Day: 1st Monday Sep
        _get_nth_weekday_of_month(year, 10, 0, 2),  # Columbus Day: 2nd Monday Oct
        _get_nth_weekday_of_month(year, 11, 3, 4),  # Thanksgiving: 4th Thursday Nov
    ]

    if check_date in floating_holidays:
        return True

    # Day after Thanksgiving (4th Friday of November)
    thanksgiving = _get_nth_weekday_of_month(year, 11, 3, 4)
    from datetime import timedelta

    if check_date == thanksgiving + timedelta(days=1):
        return True

    # Good Friday (Friday before Easter)
    easter = _get_easter_date(year)
    good_friday = easter - timedelta(days=2)
    if check_date == good_friday:
        return True

    return False


class ContextEngine:
    """Unified context gathering from all integrations.

    Gathers data from all available integrations in parallel
    to build a complete HomeContext snapshot.

    Usage:
        engine = ContextEngine(controller)
        context = await engine.get_context()
    """

    def __init__(self, controller: SmartHomeController | None = None):
        """Initialize context engine."""
        self._controller = controller
        self._last_context: HomeContext | None = None
        self._last_context_time: float = 0.0
        self._cache_ttl_seconds = 5.0  # Cache context for 5 seconds

    def set_controller(self, controller: SmartHomeController) -> None:
        """Set or update controller reference."""
        self._controller = controller

    async def get_context(self, force_refresh: bool = False) -> HomeContext:
        """Gather complete context snapshot.

        Args:
            force_refresh: Force refresh even if cache is valid

        Returns:
            HomeContext with all available data
        """
        import time

        # Return cached context if still valid
        if (
            not force_refresh
            and self._last_context is not None
            and (time.time() - self._last_context_time) < self._cache_ttl_seconds
        ):
            return self._last_context

        now = datetime.now()

        # Build base context
        context = HomeContext(
            time=now,
            circadian_phase=get_circadian_phase(now),
            day_of_week=now.weekday(),
            is_weekend=now.weekday() >= 5,
            is_holiday=is_us_holiday(now.date()),
            owner_home=False,
            owner_location=None,
        )

        if not self._controller:
            self._last_context = context
            self._last_context_time = time.time()
            return context

        # Gather context from integrations in parallel
        tasks = [
            self._gather_presence_context(context),
            self._gather_environment_context(context),
            self._gather_sleep_context(context),
            self._gather_activity_context(context),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        # Cache and return
        self._last_context = context
        self._last_context_time = time.time()

        return context

    async def _gather_presence_context(self, context: HomeContext) -> None:
        """Gather presence-related context."""
        try:
            state = self._controller.get_state()
            if state:
                from kagami_smarthome.types import PresenceState

                # Check presence state - HOME, ACTIVE, or ARRIVING all mean "home"
                context.owner_home = state.presence in (
                    PresenceState.HOME,
                    PresenceState.ACTIVE,
                    PresenceState.ARRIVING,
                )
                context.owner_location = state.owner_room

                # Check for arrival (set by PresenceEngine on WiFi connect)
                context.owner_just_arrived = state.just_arrived

                # Occupied rooms for guest detection
                if state.occupied_rooms:
                    context.guest_count = max(0, len(state.occupied_rooms) - 1)
                    context.guests_present = context.guest_count > 0

        except Exception as e:
            logger.debug(f"Failed to gather presence context: {e}")

    async def _gather_environment_context(self, context: HomeContext) -> None:
        """Gather environment-related context."""
        try:
            # Get weather if available
            from kagami_smarthome.integrations import get_current_weather

            weather = await get_current_weather()
            if weather:
                context.weather = weather.condition.value if weather.condition else "clear"
                context.outdoor_temp_f = weather.temperature_f or 70.0

                # Estimate outdoor light level from weather and time
                hour = context.time.hour
                if 6 <= hour <= 18:
                    base_light = 80
                    if weather.condition and "cloud" in weather.condition.value.lower():
                        base_light -= 30
                    if weather.condition and "rain" in weather.condition.value.lower():
                        base_light -= 20
                    context.outdoor_light_level = max(0, base_light)
                else:
                    context.outdoor_light_level = 0

        except Exception as e:
            logger.debug(f"Failed to gather environment context: {e}")

    async def _gather_sleep_context(self, context: HomeContext) -> None:
        """Gather sleep-related context."""
        try:
            if self._controller._eight_sleep and self._controller._eight_sleep.is_connected:
                sleep_state = await self._controller._eight_sleep.get_sleep_state("left")
                if sleep_state:
                    context.owner_in_bed = sleep_state.in_bed
                    context.sleep_stage = (
                        sleep_state.sleep_stage.value if sleep_state.sleep_stage else None
                    )

        except Exception as e:
            logger.debug(f"Failed to gather sleep context: {e}")

    async def _gather_activity_context(self, context: HomeContext) -> None:
        """Gather activity-related context."""
        try:
            # Infer activity from room and time
            if context.owner_in_bed:
                context.detected_activity = "sleeping"
            elif context.owner_location == "Office":
                context.detected_activity = "working"
            elif context.owner_location == "Kitchen":
                context.detected_activity = "cooking"
            elif context.owner_location == "Living Room":
                hour = context.time.hour
                if 18 <= hour <= 23:
                    context.detected_activity = "relaxing"
                else:
                    context.detected_activity = "lounging"
            elif context.owner_location == "Gym":
                context.detected_activity = "exercising"

        except Exception as e:
            logger.debug(f"Failed to gather activity context: {e}")


def get_context_engine(controller: SmartHomeController | None = None) -> ContextEngine:
    """Get or create global context engine instance."""
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextEngine(controller)
    elif controller is not None:
        _context_engine.set_controller(controller)
    return _context_engine


__all__ = [
    "CircadianPhase",
    "ContextEngine",
    "GuestMode",
    "HomeContext",
    "get_circadian_color_temp",
    "get_circadian_max_brightness",
    "get_circadian_phase",
    "get_context_engine",
    "is_us_holiday",
]
