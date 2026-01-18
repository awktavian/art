"""Room Scenes — Activity-Based Environment Presets.

Each scene defines the target state for all room systems:
- Lights (level, color temperature)
- Shades (position)
- Audio (volume, source)
- HVAC (temperature, mode)

Scenes are context-aware, adapting to:
- Time of day (morning/afternoon/evening/night)
- Day of week (weekday/weekend)
- Season (heating/cooling)
- Special events (movie night, guests, party)

Philosophy:
The home should feel right without manual adjustment.
Scenes encode the "feeling" of an activity, not just device states.

Created: December 29, 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TimeOfDay(str, Enum):
    """Time of day for scene adjustments."""

    DAWN = "dawn"  # 5am-7am
    MORNING = "morning"  # 7am-12pm
    AFTERNOON = "afternoon"  # 12pm-5pm
    EVENING = "evening"  # 5pm-9pm
    NIGHT = "night"  # 9pm-12am
    LATE_NIGHT = "late_night"  # 12am-5am

    @classmethod
    def from_hour(cls, hour: int) -> TimeOfDay:
        """Get time of day from hour (0-23)."""
        if 5 <= hour < 7:
            return cls.DAWN
        elif 7 <= hour < 12:
            return cls.MORNING
        elif 12 <= hour < 17:
            return cls.AFTERNOON
        elif 17 <= hour < 21:
            return cls.EVENING
        elif 21 <= hour < 24:
            return cls.NIGHT
        else:  # 0-5
            return cls.LATE_NIGHT

    @classmethod
    def current(cls) -> TimeOfDay:
        """Get current time of day."""
        return cls.from_hour(datetime.now().hour)


class Season(str, Enum):
    """Season for temperature/lighting adjustments."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

    @classmethod
    def current(cls) -> Season:
        """Get current season (Northern Hemisphere)."""
        month = datetime.now().month
        if month in (3, 4, 5):
            return cls.SPRING
        elif month in (6, 7, 8):
            return cls.SUMMER
        elif month in (9, 10, 11):
            return cls.AUTUMN
        else:
            return cls.WINTER


@dataclass
class LightingPreset:
    """Lighting settings for a scene."""

    level: int = 50  # Brightness 0-100
    warm_white: bool = True  # Warm (true) vs cool white
    color_temp_k: int | None = None  # Kelvin if tunable (2700-6500)

    # Per-fixture overrides (name_pattern -> level)
    overrides: dict[str, int] = field(default_factory=dict)

    # Time-of-day adjustments
    dawn_modifier: int = -20  # Darker in early morning
    evening_modifier: int = -10  # Slightly dimmer in evening
    night_modifier: int = -30  # Much dimmer at night

    def get_level(self, time_of_day: TimeOfDay | None = None) -> int:
        """Get adjusted level for time of day."""
        tod = time_of_day or TimeOfDay.current()

        modifier = 0
        if tod == TimeOfDay.DAWN:
            modifier = self.dawn_modifier
        elif tod in (TimeOfDay.EVENING, TimeOfDay.NIGHT):
            modifier = self.evening_modifier
        elif tod == TimeOfDay.LATE_NIGHT:
            modifier = self.night_modifier

        return max(0, min(100, self.level + modifier))


@dataclass
class ShadePreset:
    """Shade settings for a scene."""

    position: int = 0  # 0=open, 100=closed

    # Orientation-specific (south windows might need more coverage)
    south_override: int | None = None
    east_override: int | None = None
    west_override: int | None = None

    # Time-based auto-adjust
    follow_sun: bool = False  # Auto-adjust for glare
    blackout: bool = False  # Full closure for movies/sleep


@dataclass
class AudioPreset:
    """Audio settings for a scene."""

    volume: int = 30  # 0-100
    muted: bool = False
    source: str | None = None  # Source name or None for current

    # Content type hint for EQ
    content_type: str = "ambient"  # ambient, music, podcast, movie


@dataclass
class HVACPreset:
    """HVAC settings for a scene."""

    target_temp_f: float = 72.0
    mode: str = "auto"  # auto, heat, cool, fan

    # Season adjustments
    summer_offset: float = -1.0  # Cooler in summer
    winter_offset: float = 1.0  # Warmer in winter

    # Activity adjustments
    active_offset: float = -2.0  # Cooler when exercising
    sleep_offset: float = -4.0  # Much cooler for sleep

    def get_temp(self, season: Season | None = None) -> float:
        """Get adjusted temperature for season."""
        s = season or Season.current()

        offset = 0.0
        if s == Season.SUMMER:
            offset = self.summer_offset
        elif s == Season.WINTER:
            offset = self.winter_offset

        return self.target_temp_f + offset


@dataclass
class Scene:
    """A complete scene definition.

    Scenes define the desired "feeling" for an activity:
    - Waking up should feel gradual, warm, energizing
    - Working should feel focused, neutral, comfortable
    - Relaxing should feel cozy, dimmer, ambient
    - Movie watching should feel immersive, dark, surround
    - Sleeping should feel peaceful, dark, quiet, cool
    """

    name: str  # Scene identifier
    display_name: str  # Human-readable name
    description: str = ""  # What this scene is for

    # System presets
    lighting: LightingPreset = field(default_factory=LightingPreset)
    shades: ShadePreset = field(default_factory=ShadePreset)
    audio: AudioPreset = field(default_factory=AudioPreset)
    hvac: HVACPreset = field(default_factory=HVACPreset)

    # Additional device actions
    fireplace_on: bool | None = None  # None = don't change
    tv_on: bool | None = None

    # Transition timing
    transition_seconds: int = 5  # Fade duration

    # Applicability
    room_types: list[str] = field(default_factory=list)  # Empty = all rooms

    def __repr__(self) -> str:
        return f"Scene({self.name})"


# =============================================================================
# Predefined Scenes
# =============================================================================

SCENE_MORNING = Scene(
    name="morning",
    display_name="Morning",
    description="Gradual wake-up lighting with energizing settings",
    lighting=LightingPreset(
        level=60,
        warm_white=True,
        color_temp_k=3000,  # Warm but not dim
    ),
    shades=ShadePreset(
        position=0,  # Open for natural light
    ),
    audio=AudioPreset(
        volume=25,
        content_type="ambient",
    ),
    hvac=HVACPreset(
        target_temp_f=70.0,
        mode="auto",
    ),
    transition_seconds=30,  # Slow transition for wake-up
)

SCENE_WORKING = Scene(
    name="working",
    display_name="Working",
    description="Focused work environment with task lighting",
    lighting=LightingPreset(
        level=80,
        warm_white=False,  # Neutral/cool for focus
        color_temp_k=4000,
    ),
    shades=ShadePreset(
        position=30,  # Partial for glare control
        follow_sun=True,
    ),
    audio=AudioPreset(
        volume=15,  # Background only
        content_type="ambient",
    ),
    hvac=HVACPreset(
        target_temp_f=72.0,
    ),
    room_types=["office", "bedroom"],  # Where work happens
)

SCENE_COOKING = Scene(
    name="cooking",
    display_name="Cooking",
    description="Bright lighting for food preparation",
    lighting=LightingPreset(
        level=100,  # Full brightness for safety
        warm_white=False,
        color_temp_k=4500,  # Neutral for true color
    ),
    shades=ShadePreset(
        position=0,  # Open
    ),
    audio=AudioPreset(
        volume=35,
        content_type="music",
    ),
    hvac=HVACPreset(
        target_temp_f=70.0,  # Cooler, kitchen gets hot
    ),
    room_types=["kitchen"],
)

SCENE_DINING = Scene(
    name="dining",
    display_name="Dining",
    description="Pleasant atmosphere for meals",
    lighting=LightingPreset(
        level=70,
        warm_white=True,
        color_temp_k=2700,  # Warm and inviting
    ),
    shades=ShadePreset(
        position=0,
    ),
    audio=AudioPreset(
        volume=30,
        content_type="ambient",
    ),
    hvac=HVACPreset(
        target_temp_f=72.0,
    ),
    room_types=["dining", "kitchen"],
)

SCENE_RELAXING = Scene(
    name="relaxing",
    display_name="Relaxing",
    description="Cozy evening atmosphere",
    lighting=LightingPreset(
        level=40,
        warm_white=True,
        color_temp_k=2700,  # Very warm
        evening_modifier=0,  # Already dimmed
    ),
    shades=ShadePreset(
        position=50,  # Partial privacy
    ),
    audio=AudioPreset(
        volume=40,
        content_type="music",
    ),
    hvac=HVACPreset(
        target_temp_f=72.0,
    ),
    fireplace_on=True,  # Cozy!
)

SCENE_WATCHING = Scene(
    name="watching",
    display_name="TV Watching",
    description="Comfortable TV viewing with bias lighting",
    lighting=LightingPreset(
        level=10,  # Bias lighting only
        warm_white=True,
        overrides={"bias": 20, "ambient": 5},  # Named fixtures
    ),
    shades=ShadePreset(
        position=80,  # Mostly closed
    ),
    audio=AudioPreset(
        volume=0,  # Use TV audio
        muted=True,
    ),
    hvac=HVACPreset(
        target_temp_f=72.0,
    ),
    tv_on=True,
    room_types=["living", "family", "bedroom"],
)

SCENE_MOVIE = Scene(
    name="movie",
    display_name="Movie Night",
    description="Immersive home theater experience",
    lighting=LightingPreset(
        level=5,  # Near-dark, just bias
        warm_white=True,
        overrides={"bias": 5},  # Only TV bias light
    ),
    shades=ShadePreset(
        position=100,  # Full blackout
        blackout=True,
    ),
    audio=AudioPreset(
        volume=0,  # AVR controls audio
        muted=True,
    ),
    hvac=HVACPreset(
        target_temp_f=70.0,  # Slightly cooler
    ),
    tv_on=True,
    fireplace_on=False,  # Off during movies (visual distraction)
    transition_seconds=10,
    room_types=["living"],  # Home theater only
)

SCENE_ENTERTAINING = Scene(
    name="entertaining",
    display_name="Entertaining",
    description="Social gathering atmosphere",
    lighting=LightingPreset(
        level=70,
        warm_white=True,
        color_temp_k=3000,
    ),
    shades=ShadePreset(
        position=0,  # Open, show off the view
    ),
    audio=AudioPreset(
        volume=45,
        content_type="music",
    ),
    hvac=HVACPreset(
        target_temp_f=71.0,  # Account for body heat
    ),
    fireplace_on=True,
)

SCENE_SLEEPING = Scene(
    name="sleeping",
    display_name="Sleeping",
    description="Peaceful sleep environment",
    lighting=LightingPreset(
        level=0,  # Off
    ),
    shades=ShadePreset(
        position=100,  # Full blackout
        blackout=True,
    ),
    audio=AudioPreset(
        volume=0,
        muted=True,
    ),
    hvac=HVACPreset(
        target_temp_f=68.0,  # Cool for better sleep
        sleep_offset=0,  # Already at sleep temp
    ),
    tv_on=False,
    fireplace_on=False,
    transition_seconds=60,  # Slow fade to darkness
    room_types=["bedroom"],
)

SCENE_AWAY = Scene(
    name="away",
    display_name="Away",
    description="Energy-saving mode when nobody home",
    lighting=LightingPreset(
        level=0,
    ),
    shades=ShadePreset(
        position=50,  # Neutral
    ),
    audio=AudioPreset(
        volume=0,
        muted=True,
    ),
    hvac=HVACPreset(
        target_temp_f=65.0,  # Setback
        mode="auto",
    ),
    tv_on=False,
    fireplace_on=False,
)

SCENE_GOODNIGHT = Scene(
    name="goodnight",
    display_name="Good Night",
    description="House-wide shutdown for bedtime",
    lighting=LightingPreset(
        level=0,
    ),
    shades=ShadePreset(
        position=100,
        blackout=True,
    ),
    audio=AudioPreset(
        volume=0,
        muted=True,
    ),
    hvac=HVACPreset(
        target_temp_f=68.0,
    ),
    tv_on=False,
    fireplace_on=False,
    transition_seconds=30,
)

SCENE_WELCOME_HOME = Scene(
    name="welcome_home",
    display_name="Welcome Home",
    description="Automatic scene when arriving home",
    lighting=LightingPreset(
        level=70,
        warm_white=True,
    ),
    shades=ShadePreset(
        position=0,
    ),
    audio=AudioPreset(
        volume=25,
        content_type="ambient",
    ),
    hvac=HVACPreset(
        target_temp_f=72.0,
    ),
)


# =============================================================================
# Scene Registry
# =============================================================================


class SceneRegistry:
    """Registry of all available scenes."""

    def __init__(self):
        self._scenes: dict[str, Scene] = {}

        # Register built-in scenes
        for scene in [
            SCENE_MORNING,
            SCENE_WORKING,
            SCENE_COOKING,
            SCENE_DINING,
            SCENE_RELAXING,
            SCENE_WATCHING,
            SCENE_MOVIE,
            SCENE_ENTERTAINING,
            SCENE_SLEEPING,
            SCENE_AWAY,
            SCENE_GOODNIGHT,
            SCENE_WELCOME_HOME,
        ]:
            self._scenes[scene.name] = scene

    def get(self, name: str) -> Scene | None:
        """Get scene by name."""
        return self._scenes.get(name)

    def register(self, scene: Scene) -> None:
        """Register a custom scene."""
        self._scenes[scene.name] = scene

    def all(self) -> list[Scene]:
        """Get all registered scenes."""
        return list(self._scenes.values())

    def for_room_type(self, room_type: str) -> list[Scene]:
        """Get scenes applicable to a room type."""
        applicable = []
        for scene in self._scenes.values():
            if not scene.room_types or room_type in scene.room_types:
                applicable.append(scene)
        return applicable


# Global registry instance
SCENES = SceneRegistry()


def get_scene(name: str) -> Scene | None:
    """Get a scene by name."""
    return SCENES.get(name)


def get_all_scenes() -> list[Scene]:
    """Get all scenes."""
    return SCENES.all()
