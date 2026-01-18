"""Typed Protocol classes for the Ambient subsystem.

Replaces dict[str, Any] patterns with explicit, documented interfaces.

These protocols define the shape of data flowing through:
- Constellation (multi-device state sync)
- Sensory data (health, motion, audio from devices)
- Trigger callbacks (cross-domain bridge events)

Created: January 12, 2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


# =============================================================================
# CONSTELLATION UPDATE PROTOCOL
# =============================================================================


@runtime_checkable
class ConstellationUpdate(Protocol):
    """Protocol for the ambient state snapshot synced across devices.

    This is the canonical format for multi-device constellation sync,
    returned by AmbientController._build_constellation_updates().

    The data flows from AmbientController -> MultiDeviceCoordinator -> devices
    via Socket.IO state_sync events.

    Attributes:
        timestamp: Wall clock timestamp for external clients (time.time())
        breath_phase: Current breath phase value (PLAN/EXECUTE/VERIFY/REST)
        breath_progress: Progress through current phase (0.0-1.0)
        breath_cycle: Number of complete breath cycles
        breath_bpm: Breaths per minute
        presence_level: Current presence level (ABSENT/PERIPHERAL/AWARE/ENGAGED/FOCUSED)
        presence_confidence: Confidence in presence detection (0.0-1.0)
        safety_h: Safety barrier h(x) value (h >= 0 is safe)
        safety_safe: Boolean indicating if h(x) >= 0
        colony_active: Active colony name or None if no dominant colony
        colony_activation: Activation level of the active colony (0.0-1.0)
        quiet: Whether Kagami should recede (ma/negative space)
        quiet_reason: Reason for quiet mode ("paused", "focused", or None)
    """

    @property
    def timestamp(self) -> float:
        """Wall clock timestamp (time.time())."""
        ...

    @property
    def breath_phase(self) -> str:
        """Current breath phase (PLAN/EXECUTE/VERIFY/REST)."""
        ...

    @property
    def breath_progress(self) -> float:
        """Progress through current phase (0.0-1.0)."""
        ...

    @property
    def breath_cycle(self) -> int:
        """Number of complete breath cycles."""
        ...

    @property
    def breath_bpm(self) -> float:
        """Breaths per minute."""
        ...

    @property
    def presence_level(self) -> str:
        """Presence level value (ABSENT/PERIPHERAL/AWARE/ENGAGED/FOCUSED)."""
        ...

    @property
    def presence_confidence(self) -> float:
        """Confidence in presence detection (0.0-1.0)."""
        ...

    @property
    def safety_h(self) -> float:
        """Safety barrier h(x) value."""
        ...

    @property
    def safety_safe(self) -> bool:
        """Whether the safety barrier is satisfied (h >= 0)."""
        ...

    @property
    def colony_active(self) -> str | None:
        """Active colony name or None."""
        ...

    @property
    def colony_activation(self) -> float:
        """Activation level of the active colony (0.0-1.0)."""
        ...

    @property
    def quiet(self) -> bool:
        """Whether Kagami should recede (ma/negative space)."""
        ...

    @property
    def quiet_reason(self) -> str | None:
        """Reason for quiet mode ('paused', 'focused', or None)."""
        ...


# =============================================================================
# SENSORY DATA PROTOCOL
# =============================================================================


@runtime_checkable
class SensoryDataProtocol(Protocol):
    """Protocol for sensory data from devices (health, motion, audio).

    Used by MultiDeviceCoordinator.update_sensory_data() to receive
    health metrics, motion data, and audio levels from connected devices.

    Devices (watch, phone, tablet) report this data which is then
    aggregated and forwarded to UnifiedSensoryIntegration.

    Attributes:
        heart_rate: Current heart rate in BPM (from HealthKit/Health Connect)
        resting_heart_rate: Resting heart rate in BPM
        hrv: Heart rate variability in ms
        steps: Step count (daily)
        active_calories: Active calories burned
        exercise_minutes: Exercise duration in minutes
        blood_oxygen: Blood oxygen saturation (0.0-1.0)
        sleep_hours: Hours of sleep (from previous night)
        motion_intensity: Motion intensity (0.0-1.0 scale)
        is_moving: Whether device detects movement
        activity_type: Activity classification (walking/running/stationary)
        ambient_noise_level: Ambient noise level in dB
        is_speaking: Whether user is currently speaking
        latitude: GPS latitude if available
        longitude: GPS longitude if available
        timestamp: Data collection timestamp
    """

    @property
    def heart_rate(self) -> float | None:
        """Current heart rate in BPM."""
        ...

    @property
    def resting_heart_rate(self) -> float | None:
        """Resting heart rate in BPM."""
        ...

    @property
    def hrv(self) -> float | None:
        """Heart rate variability in ms."""
        ...

    @property
    def steps(self) -> int | None:
        """Step count (daily)."""
        ...

    @property
    def active_calories(self) -> int | None:
        """Active calories burned."""
        ...

    @property
    def exercise_minutes(self) -> int | None:
        """Exercise duration in minutes."""
        ...

    @property
    def blood_oxygen(self) -> float | None:
        """Blood oxygen saturation (0.0-1.0)."""
        ...

    @property
    def sleep_hours(self) -> float | None:
        """Hours of sleep (from previous night)."""
        ...

    @property
    def motion_intensity(self) -> float | None:
        """Motion intensity (0.0-1.0 scale)."""
        ...

    @property
    def is_moving(self) -> bool | None:
        """Whether device detects movement."""
        ...

    @property
    def activity_type(self) -> str | None:
        """Activity classification (walking/running/stationary)."""
        ...

    @property
    def ambient_noise_level(self) -> float | None:
        """Ambient noise level in dB."""
        ...

    @property
    def is_speaking(self) -> bool | None:
        """Whether user is currently speaking."""
        ...

    @property
    def latitude(self) -> float | None:
        """GPS latitude if available."""
        ...

    @property
    def longitude(self) -> float | None:
        """GPS longitude if available."""
        ...

    @property
    def timestamp(self) -> float:
        """Data collection timestamp (time.time())."""
        ...


# =============================================================================
# TRIGGER CONTEXT PROTOCOL
# =============================================================================


@runtime_checkable
class TriggerContextProtocol(Protocol):
    """Protocol for trigger context data in CrossDomainBridge.

    This defines the shape of data passed to trigger condition functions
    and action callbacks. Different sense types have different fields,
    but all share a common base structure.

    The context is built from UnifiedSensoryIntegration sense events
    and passed through CrossDomainTrigger.condition() and .action().

    Common Fields (all triggers):
        source: The sense type that triggered (gmail/calendar/weather/etc)
        timestamp: Event timestamp

    Weather-specific:
        condition: Weather condition (clear/clouds/rain/snow)
        description: Human-readable weather description
        temp_f: Temperature in Fahrenheit
        feels_like_f: Feels-like temperature in Fahrenheit
        humidity: Humidity percentage (0-100)
        wind_speed: Wind speed
        is_daytime: Whether it's currently daytime
        sunset: Unix timestamp of sunset
        sunrise: Unix timestamp of sunrise

    Email-specific:
        urgency: Email urgency score (0.0-1.0)
        unread_important: Count of unread important emails
        important_from: List of important senders

    Calendar-specific:
        minutes_to_next: Minutes until next event
        next_event: Next calendar event details

    Sleep-specific:
        state: Sleep state (asleep/awake/restless)

    Vehicle-specific:
        is_home: Whether vehicle is at home
        eta_minutes: Estimated arrival time in minutes

    GitHub-specific:
        events: List of GitHub events
        pr_merged: Whether a PR was merged
        pr_title: Title of merged PR
    """

    @property
    def source(self) -> str:
        """The sense type that triggered this event."""
        ...

    @property
    def timestamp(self) -> float:
        """Event timestamp."""
        ...


@runtime_checkable
class WeatherTriggerContext(Protocol):
    """Protocol for weather-specific trigger context.

    Extended context for weather sense events, used by triggers like:
    - rain_protection
    - celestial_shade
    - sunset_preparation
    - cold_weather_alert
    """

    @property
    def condition(self) -> str:
        """Weather condition (clear/clouds/rain/snow/thunderstorm)."""
        ...

    @property
    def description(self) -> str:
        """Human-readable weather description."""
        ...

    @property
    def temp_f(self) -> float:
        """Temperature in Fahrenheit."""
        ...

    @property
    def feels_like_f(self) -> float:
        """Feels-like temperature in Fahrenheit."""
        ...

    @property
    def humidity(self) -> int:
        """Humidity percentage (0-100)."""
        ...

    @property
    def wind_speed(self) -> float:
        """Wind speed."""
        ...

    @property
    def is_daytime(self) -> bool:
        """Whether it's currently daytime."""
        ...

    @property
    def sunset(self) -> int:
        """Unix timestamp of sunset."""
        ...

    @property
    def sunrise(self) -> int:
        """Unix timestamp of sunrise."""
        ...


@runtime_checkable
class EmailTriggerContext(Protocol):
    """Protocol for email-specific trigger context.

    Extended context for Gmail sense events, used by triggers like:
    - urgent_email
    """

    @property
    def urgency(self) -> float:
        """Email urgency score (0.0-1.0)."""
        ...

    @property
    def unread_important(self) -> int:
        """Count of unread important emails."""
        ...

    @property
    def important_from(self) -> list[str | dict]:
        """List of important senders (strings or dicts with 'from' key)."""
        ...


@runtime_checkable
class CalendarTriggerContext(Protocol):
    """Protocol for calendar-specific trigger context.

    Extended context for calendar sense events, used by triggers like:
    - meeting_prep
    """

    @property
    def minutes_to_next(self) -> float | None:
        """Minutes until next event, or None/inf if no upcoming events."""
        ...

    @property
    def next_event(self) -> dict | None:
        """Next calendar event details, or None."""
        ...


@runtime_checkable
class SleepTriggerContext(Protocol):
    """Protocol for sleep-specific trigger context.

    Extended context for Eight Sleep sense events, used by triggers like:
    - goodnight
    """

    @property
    def state(self) -> str:
        """Sleep state (asleep/awake/restless)."""
        ...


@runtime_checkable
class VehicleTriggerContext(Protocol):
    """Protocol for vehicle-specific trigger context.

    Extended context for Tesla/vehicle sense events, used by triggers like:
    - welcome_home
    """

    @property
    def is_home(self) -> bool:
        """Whether vehicle is at home."""
        ...

    @property
    def eta_minutes(self) -> float:
        """Estimated arrival time in minutes."""
        ...


@runtime_checkable
class GitHubTriggerContext(Protocol):
    """Protocol for GitHub-specific trigger context.

    Extended context for GitHub sense events, used by triggers like:
    - pr_celebration
    """

    @property
    def events(self) -> list[dict]:
        """List of GitHub events."""
        ...

    @property
    def pr_merged(self) -> bool:
        """Whether a PR was merged."""
        ...

    @property
    def pr_title(self) -> str:
        """Title of merged PR."""
        ...


# =============================================================================
# TYPE ALIASES
# =============================================================================

# Callback types for CrossDomainTrigger
TriggerCondition = Callable[[dict], bool]
"""Type alias for trigger condition functions."""

TriggerAction = Callable[[dict], "Awaitable[None]"]
"""Type alias for async trigger action functions."""


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CalendarTriggerContext",
    "ConstellationUpdate",
    "EmailTriggerContext",
    "GitHubTriggerContext",
    "SensoryDataProtocol",
    "SleepTriggerContext",
    "TriggerAction",
    "TriggerCondition",
    "TriggerContextProtocol",
    "VehicleTriggerContext",
    "WeatherTriggerContext",
]
