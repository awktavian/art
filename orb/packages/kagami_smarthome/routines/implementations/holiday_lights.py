"""Holiday Lights Routine — Adaptive Oelo Patterns + Spectrum-Aware Music.

LIGHT IS MUSIC IS SPECTRUM.

This routine provides two modes of operation:

1. **Holiday Mode**: Automatic holiday patterns based on date
   - Detects current holiday from is_us_holiday() and date ranges
   - Sets appropriate Oelo patterns (Christmas, Halloween, etc.)
   - Plays themed outdoor music on deck/porch/patio

2. **Adaptive Mode**: Real-time music-reactive lighting
   - Analyzes currently playing music (Spotify, MIDI)
   - Maps musical features to light via SpectrumEngine
   - Creates synchronized audio-visual experiences

The spectrum engine unifies:
- Audio frequencies (20Hz-20kHz) → Light hues (red to violet)
- Musical dynamics → Light brightness
- Musical articulation → Pattern types
- Musical mood → Color harmony

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
from datetime import date

from kagami_smarthome.context.context_engine import CircadianPhase, HomeContext, is_us_holiday
from kagami_smarthome.execution.receipted_executor import Action
from kagami_smarthome.intent_automation import AutomationIntent, Capability
from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine

logger = logging.getLogger(__name__)


# Holiday-to-Oelo pattern mapping
# Maps (month, day) ranges and specific holidays to Oelo patterns
HOLIDAY_PATTERNS: dict[str, dict] = {
    # === Christmas Season (Dec 1-31) ===
    "christmas": {
        "pattern": "christmas",
        "start": (12, 1),
        "end": (12, 31),
        "playlist": "christmas",
        "speed_override": 3,  # Gentle marching
    },
    # === Halloween (Oct 15-31) ===
    "halloween": {
        "pattern": "halloween",
        "start": (10, 15),
        "end": (10, 31),
        "playlist": "halloween",
        "speed_override": 5,  # Spooky twinkle
    },
    # === Thanksgiving (Nov, week of thanksgiving) ===
    "thanksgiving": {
        "pattern": "thanksgiving",
        "holiday_trigger": True,  # Uses is_us_holiday()
        "playlist": "acoustic",  # Warm acoustic vibes
    },
    # === July 4th (July 1-7) ===
    "july4th": {
        "pattern": "july4th",
        "start": (7, 1),
        "end": (7, 7),
        "playlist": "americana",
        "speed_override": 8,  # Patriotic chase
    },
    # === Valentine's Day (Feb 10-14) ===
    "valentines": {
        "pattern": "valentines",
        "start": (2, 10),
        "end": (2, 14),
        "playlist": "romantic",
        "speed_override": 2,  # Slow romantic fade
    },
    # === St. Patrick's Day (Mar 14-17) ===
    "stpatricks": {
        "pattern": "stpatricks",
        "start": (3, 14),
        "end": (3, 17),
        "playlist": "irish",
        "speed_override": 4,  # Irish river
    },
    # === Easter (dynamic, spring) ===
    "easter": {
        "pattern": "valentines",  # Soft pastels, similar vibe
        "holiday_trigger": True,  # Uses Easter detection
        "playlist": "spring",
    },
    # === New Year's Eve ===
    "newyear": {
        "pattern": "party",
        "start": (12, 31),
        "end": (1, 1),
        "playlist": "party",
        "speed_override": 15,  # High energy
    },
}

# Outdoor music playlist URIs (Spotify)
OUTDOOR_PLAYLISTS: dict[str, str] = {
    "christmas": "spotify:playlist:37i9dQZF1DX0Yxoavh5qJV",  # Christmas Hits
    "halloween": "spotify:playlist:37i9dQZF1DX0yyj7kWBdYs",  # Halloween Party
    "americana": "spotify:playlist:37i9dQZF1DXaXB8fQg7xif",  # American BBQ
    "romantic": "spotify:playlist:37i9dQZF1DX50QitC6Oqtn",  # Love Songs
    "irish": "spotify:playlist:37i9dQZF1DX4ZD8FU8C5UF",  # Irish Folk
    "spring": "spotify:playlist:37i9dQZF1DX4wta20PHgwo",  # Spring Acoustic
    "acoustic": "spotify:playlist:37i9dQZF1DX4E3UdUs7fUx",  # Acoustic Covers
    "party": "spotify:playlist:37i9dQZF1DX0IlCGIUGBsA",  # Party Starters
    "summer": "spotify:playlist:37i9dQZF1DX4SBhb3fqCJd",  # Summer Hits
    "chill": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",  # Chill Hits
}

# Outdoor audio zones
OUTDOOR_ZONES = ["deck", "porch", "patio"]


def get_current_holiday(check_date: date | None = None) -> str | None:
    """Determine which holiday pattern to use for a given date.

    Args:
        check_date: Date to check. Defaults to today.

    Returns:
        Holiday key from HOLIDAY_PATTERNS, or None if no holiday.
    """
    if check_date is None:
        check_date = date.today()

    month = check_date.month
    day = check_date.day

    for holiday_key, config in HOLIDAY_PATTERNS.items():
        # Check date range based holidays
        if "start" in config and "end" in config:
            start_month, start_day = config["start"]
            end_month, end_day = config["end"]

            # Handle year wrap (Dec 31 - Jan 1)
            if start_month > end_month:
                # December to January
                if (month == start_month and day >= start_day) or (
                    month == end_month and day <= end_day
                ):
                    return holiday_key
            else:
                # Same year range
                if start_month <= month <= end_month:
                    if start_month == end_month:
                        if start_day <= day <= end_day:
                            return holiday_key
                    elif (
                        month == start_month
                        and day >= start_day
                        or month == end_month
                        and day <= end_day
                        or start_month < month < end_month
                    ):
                        return holiday_key

        # Check holiday-triggered patterns (uses is_us_holiday)
        if config.get("holiday_trigger"):
            if is_us_holiday(check_date):
                # Match specific holidays
                if holiday_key == "thanksgiving":
                    if month == 11 and 22 <= day <= 29:  # Thanksgiving week
                        return holiday_key
                elif holiday_key == "easter":
                    # Easter is in spring (March-April)
                    if 3 <= month <= 4 and is_us_holiday(check_date):
                        return holiday_key

    return None


def get_holiday_pattern_config(holiday: str) -> dict | None:
    """Get Oelo pattern configuration for a holiday."""
    return HOLIDAY_PATTERNS.get(holiday)


class HolidayLightsRoutine(AdaptiveRoutine):
    """Automatic holiday outdoor lighting with optional music.

    Features:
    - Auto-detects current holiday from date
    - Sets appropriate Oelo pattern at sunset
    - Optionally plays themed outdoor music
    - Respects circadian phases (only evening/night)
    - Weather-aware (skips during rain/storms)
    """

    id = "holiday_lights"
    name = "Holiday Lights"
    description = "Automatic holiday Oelo patterns with outdoor music"
    safety_critical = False

    intent = AutomationIntent.SCENE_CHANGE

    required_capabilities = []  # Oelo is optional - fail gracefully
    optional_capabilities = [
        Capability.HAS_LIGHTS,  # Oelo outdoor lights
        Capability.HAS_PRESENCE_DETECTION,
    ]

    params = {
        "enable_music": True,  # Play themed outdoor music
        "music_volume": 50,  # Outdoor speaker volume (0-100)
        "start_at_sunset": True,  # Only activate after sunset
        "weather_aware": True,  # Skip in bad weather
        "auto_off_time": 23,  # Hour to turn off (11 PM)
    }

    param_ranges = {
        "music_volume": (20, 80),
        "auto_off_time": (21, 24),  # 9 PM - Midnight
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger at sunset during holiday periods."""
        # Only trigger in evening/night phases
        if context.circadian_phase not in (
            CircadianPhase.EVENING,
            CircadianPhase.NIGHT,
        ):
            return False, "not_evening"

        # Check for current holiday
        holiday = get_current_holiday(context.time.date())
        if not holiday:
            return False, "no_holiday"

        # Skip in bad weather if enabled
        if self.params["weather_aware"]:
            bad_weather = any(
                w in (context.weather or "").lower() for w in ["rain", "storm", "snow", "thunder"]
            )
            if bad_weather:
                return False, f"bad_weather_{context.weather}"

        # Check if we should turn off (late night)
        if context.time.hour >= self.params["auto_off_time"]:
            return False, "after_auto_off"

        # Trigger!
        return True, f"holiday_{holiday}"

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute holiday lighting and music actions."""
        actions: list[Action] = []

        holiday = get_current_holiday(context.time.date())
        if not holiday:
            return actions

        config = get_holiday_pattern_config(holiday)
        if not config:
            return actions

        pattern = config["pattern"]
        speed = config.get("speed_override")
        playlist_key = config.get("playlist")

        # Action 1: Set Oelo pattern
        oelo_params = {
            "pattern": pattern,
            "zone": None,  # All zones
        }
        if speed is not None:
            oelo_params["speed_override"] = speed

        actions.append(
            Action(
                "oelo_set_pattern",
                oelo_params,
            )
        )

        # Action 2: Optional outdoor music
        if self.params["enable_music"] and playlist_key:
            playlist_uri = OUTDOOR_PLAYLISTS.get(playlist_key)
            if playlist_uri:
                actions.append(
                    Action(
                        "outdoor_music",
                        {
                            "playlist_uri": playlist_uri,
                            "zones": OUTDOOR_ZONES,
                            "volume": self.params["music_volume"],
                            "shuffle": True,
                        },
                    )
                )

        logger.info(f"Holiday lights: {holiday} -> pattern={pattern}, music={playlist_key}")

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """Get rollback action."""
        if action.type == "oelo_set_pattern":
            return Action("oelo_off", {})
        elif action.type == "outdoor_music":
            return Action("outdoor_music_stop", {"zones": OUTDOOR_ZONES})
        return None


class HolidayLightsOffRoutine(AdaptiveRoutine):
    """Turn off holiday lights at configured time or on demand."""

    id = "holiday_lights_off"
    name = "Holiday Lights Off"
    description = "Turn off outdoor holiday lights"
    safety_critical = False

    intent = AutomationIntent.GOODBYE

    params = {
        "auto_off_time": 23,  # 11 PM
        "stop_music": True,
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger at auto-off time during late night."""
        if context.circadian_phase != CircadianPhase.LATE_NIGHT:
            return False, "not_late_night"

        if context.time.hour == self.params["auto_off_time"]:
            return True, "auto_off_time"

        return False, ""

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Turn off Oelo and stop outdoor music."""
        actions = [Action("oelo_off", {})]

        if self.params["stop_music"]:
            actions.append(Action("outdoor_music_stop", {"zones": OUTDOOR_ZONES}))

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """No rollback for off actions."""
        return None


class MusicReactiveLightsRoutine(AdaptiveRoutine):
    """Real-time music-reactive outdoor lighting.

    LIGHT IS MUSIC IS SPECTRUM.

    When music is playing, this routine activates the SpectrumEngine
    to create synchronized audio-visual experiences:

    - Analyzes Spotify audio features (tempo, key, energy, valence)
    - Maps musical context to light parameters
    - Updates Oelo in real-time (4 Hz update rate)
    - Respects circadian and weather constraints

    The spectrum engine creates a unified frequency space:
    - Bass frequencies → warm hues (red/orange)
    - Mid frequencies → green (spectrum center)
    - Treble frequencies → cool hues (blue/violet)
    """

    id = "music_reactive_lights"
    name = "Music Reactive Lights"
    description = "Real-time music-synchronized outdoor lighting"
    safety_critical = False

    intent = AutomationIntent.SCENE_CHANGE

    required_capabilities = []
    optional_capabilities = [
        Capability.HAS_LIGHTS,
        Capability.HAS_PRESENCE_DETECTION,
    ]

    params = {
        "update_rate_ms": 250,  # 4 Hz
        "transition_smoothing": 0.3,  # Smooth transitions
        "max_brightness": 1.0,  # Full brightness
        "max_pattern_speed": 15,  # Neighborhood courtesy
        "weather_aware": True,
    }

    param_ranges = {
        "update_rate_ms": (100, 1000),
        "transition_smoothing": (0.1, 0.9),
        "max_brightness": (0.3, 1.0),
        "max_pattern_speed": (5, 20),
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger when music is playing in evening/night."""
        # Only in evening/night
        if context.circadian_phase not in (
            CircadianPhase.EVENING,
            CircadianPhase.NIGHT,
        ):
            return False, "not_evening"

        # Skip in bad weather
        if self.params["weather_aware"]:
            bad_weather = any(
                w in (context.weather or "").lower() for w in ["rain", "storm", "thunder"]
            )
            if bad_weather:
                return False, "bad_weather"

        # Check if music is playing (would need Spotify state check)
        # For now, trigger based on time and let adaptive controller handle rest
        return True, "evening_ready"

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Start adaptive light controller."""
        return [
            Action(
                "start_adaptive_lights",
                {
                    "update_rate_ms": self.params["update_rate_ms"],
                    "transition_smoothing": self.params["transition_smoothing"],
                    "max_brightness": self.params["max_brightness"],
                    "max_pattern_speed": self.params["max_pattern_speed"],
                },
            )
        ]

    def get_rollback_action(self, action: Action) -> Action | None:
        """Stop adaptive lights."""
        if action.type == "start_adaptive_lights":
            return Action("stop_adaptive_lights", {})
        return None


__all__ = [
    "HOLIDAY_PATTERNS",
    "OUTDOOR_PLAYLISTS",
    "OUTDOOR_ZONES",
    "HolidayLightsOffRoutine",
    "HolidayLightsRoutine",
    "MusicReactiveLightsRoutine",
    "get_current_holiday",
    "get_holiday_pattern_config",
]
