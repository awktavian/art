"""Command Schemas — Single Source of Truth for SmartHome Commands.

This module defines all Pydantic v2 models for SmartHome API inputs.
Import from here to ensure consistent validation across:
- kagami_api routes
- kagami_smarthome validation
- kagami_smarthome internal components

Design Principles:
- Fields that can be None/optional in API routes remain optional here
- Strict validation uses validators; relaxed validation just uses Field constraints
- All room validation uses the shared VALID_ROOMS constant
- Pydantic v2 patterns: model_validator, field_validator, ConfigDict

Created: January 11, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# CONSTANTS
# =============================================================================

VALID_ROOMS = frozenset(
    [
        "Living Room",
        "Kitchen",
        "Dining",
        "Entry",
        "Mudroom",
        "Powder Room",
        "Stairway",
        "Garage",
        "Deck",
        "Porch",
        "Primary Bed",
        "Primary Bath",
        "Primary Closet",
        "Primary Hall",
        "Office",
        "Office Bath",
        "Bed 3",
        "Bath 3",
        "Loft",
        "Laundry",
        "Game Room",
        "Bed 4",
        "Bath 4",
        "Gym",
        "Rack Room",
        "Patio",
    ]
)

VALID_SCENES = frozenset(
    [
        "morning",
        "working",
        "relaxing",
        "cooking",
        "movie",
        "goodnight",
        "welcome_home",
        "away",
        "party",
        "focus",
    ]
)

VALID_COLONY_VOICES = frozenset(
    [
        "spark",
        "forge",
        "flow",
        "nexus",
        "beacon",
        "grove",
        "crystal",
        "kagami",
    ]
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def validate_rooms(rooms: list[str] | None, allow_empty: bool = True) -> list[str] | None:
    """Validate room names against VALID_ROOMS.

    Args:
        rooms: List of room names or None
        allow_empty: If True, empty list is valid. If False, requires at least one room.

    Returns:
        Validated rooms list or None

    Raises:
        ValueError: If any room is invalid
    """
    if rooms is None:
        return None

    if not allow_empty and len(rooms) == 0:
        raise ValueError("At least one room must be specified")

    invalid = set(rooms) - VALID_ROOMS
    if invalid:
        raise ValueError(f"Unknown rooms: {invalid}. Valid: {sorted(VALID_ROOMS)}")
    return rooms


def validate_room(room: str) -> str:
    """Validate a single room name.

    Args:
        room: Room name

    Returns:
        Validated room name

    Raises:
        ValueError: If room is invalid
    """
    if room not in VALID_ROOMS:
        raise ValueError(f"Unknown room: {room}. Valid: {sorted(VALID_ROOMS)}")
    return room


# =============================================================================
# LIGHT COMMAND
# =============================================================================


class LightCommand(BaseModel):
    """Command to control lights.

    Supports both API usage (optional rooms) and strict validation (required rooms).
    Use the appropriate factory method or validator for your use case.

    API usage:
        LightCommand(level=50)  # All rooms
        LightCommand(level=50, rooms=["Living Room"])

    Strict validation:
        LightCommand(level=50, rooms=["Living Room"])  # rooms required when validated
    """

    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=0, le=100, description="Brightness level (0-100)")
    rooms: list[str] | None = Field(default=None, description="Room names (None = all rooms)")
    fade_seconds: float = Field(default=0.5, ge=0, le=60, description="Fade duration in seconds")

    @field_validator("rooms")
    @classmethod
    def validate_rooms_field(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all rooms are valid."""
        return validate_rooms(v, allow_empty=True)


# =============================================================================
# SHADE COMMAND
# =============================================================================


class ShadeCommand(BaseModel):
    """Command to control shades.

    Supports both position (0-100) and named operations (open/close).

    API usage:
        ShadeCommand()  # Open/close endpoint, rooms optional
        ShadeCommand(level=50, rooms=["Living Room"])
    """

    model_config = ConfigDict(extra="forbid")

    level: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Shade level (0=closed, 100=open). Also accepts 'position' alias.",
    )
    position: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Alias for level (0=closed, 100=open)",
    )
    rooms: list[str] | None = Field(default=None, description="Room names (None = all rooms)")

    @field_validator("rooms")
    @classmethod
    def validate_rooms_field(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all rooms are valid."""
        return validate_rooms(v, allow_empty=True)

    @model_validator(mode="after")
    def resolve_level_position(self) -> ShadeCommand:
        """Resolve level from position alias if needed."""
        # If position is set but level is not, use position as level
        if self.level is None and self.position is not None:
            object.__setattr__(self, "level", self.position)
        return self


# =============================================================================
# SCENE COMMAND
# =============================================================================


class SceneCommand(BaseModel):
    """Command to apply a scene.

    Supports two naming conventions:
    - scene_name: Used by validation.py ("morning", "working", etc.)
    - scene + room: Used by API routes (room-specific scenes)

    API usage:
        SceneCommand(room="Living Room", scene="relaxing")
        SceneCommand(scene_name="morning", rooms=["Living Room", "Kitchen"])
    """

    model_config = ConfigDict(extra="forbid")

    # Primary fields (API routes style)
    room: str | None = Field(default=None, description="Single room name")
    scene: str | None = Field(default=None, description="Scene name")

    # Alternative fields (validation.py style)
    scene_name: str | None = Field(default=None, description="Scene name (alias for scene)")
    rooms: list[str] | None = Field(default=None, description="Multiple room names")

    @field_validator("room")
    @classmethod
    def validate_room_field(cls, v: str | None) -> str | None:
        """Ensure room is valid."""
        if v is not None:
            return validate_room(v)
        return v

    @field_validator("rooms")
    @classmethod
    def validate_rooms_field(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all rooms are valid."""
        return validate_rooms(v, allow_empty=True)

    @field_validator("scene", "scene_name")
    @classmethod
    def validate_scene_field(cls, v: str | None) -> str | None:
        """Ensure scene is valid."""
        if v is not None:
            normalized = v.lower()
            if normalized not in VALID_SCENES:
                raise ValueError(f"Unknown scene: {v}. Valid: {sorted(VALID_SCENES)}")
            return normalized
        return v

    @model_validator(mode="after")
    def resolve_scene_aliases(self) -> SceneCommand:
        """Resolve scene/scene_name aliases."""
        # Ensure at least one scene field is set
        scene_value = self.scene or self.scene_name
        if scene_value:
            # Normalize both fields
            object.__setattr__(self, "scene", scene_value)
            object.__setattr__(self, "scene_name", scene_value)
        return self


# =============================================================================
# ANNOUNCE COMMAND
# =============================================================================


class AnnounceCommand(BaseModel):
    """Command to announce/TTS a message.

    Supports colony voices for distinct personalities and volume control.

    API usage:
        AnnounceCommand(text="Hello!")
        AnnounceCommand(text="Dinner ready!", rooms=["Kitchen"], colony="spark")
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500, description="Text to announce")
    rooms: list[str] | None = Field(default=None, description="Target rooms (None = local only)")
    volume: float | None = Field(
        default=None,
        ge=0.1,
        le=5.0,
        description="Volume multiplier (1.0=normal, 2.0=2x gain)",
    )
    colony: str = Field(
        default="kagami",
        description="Colony voice (spark, forge, flow, nexus, beacon, grove, crystal, kagami)",
    )

    @field_validator("rooms")
    @classmethod
    def validate_rooms_field(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all rooms are valid (if specified)."""
        return validate_rooms(v, allow_empty=True)

    @field_validator("colony")
    @classmethod
    def validate_colony_field(cls, v: str) -> str:
        """Ensure colony voice is valid."""
        normalized = v.lower()
        if normalized not in VALID_COLONY_VOICES:
            raise ValueError(f"Unknown colony voice: {v}. Valid: {sorted(VALID_COLONY_VOICES)}")
        return normalized


# =============================================================================
# TV MOUNT COMMAND
# =============================================================================


class TVMountCommand(BaseModel):
    """Command to control the TV mount.

    Only preset positions are allowed - no arbitrary positions for safety.
    Presets:
        1: Viewing position
        2: Raised position
        3: Fireplace viewing
        4: Hidden/retracted
    """

    model_config = ConfigDict(extra="forbid")

    preset: int = Field(
        ge=1,
        le=4,
        description="Mount preset (1=viewing, 2=raised, 3=fireplace, 4=hidden)",
    )

    @field_validator("preset")
    @classmethod
    def validate_preset_field(cls, v: int) -> int:
        """Only presets allowed - no arbitrary positions."""
        if v not in (1, 2, 3, 4):
            raise ValueError("TV mount only supports presets 1-4. Arbitrary positions not allowed.")
        return v


# =============================================================================
# TEMPERATURE COMMAND
# =============================================================================


class TemperatureCommand(BaseModel):
    """Command to set room temperature.

    Temperature is in Fahrenheit with reasonable home range limits.
    """

    model_config = ConfigDict(extra="forbid")

    temp_f: float = Field(ge=60, le=85, description="Temperature in Fahrenheit")
    room: str = Field(description="Room name")

    @field_validator("room")
    @classmethod
    def validate_room_field(cls, v: str) -> str:
        """Ensure room is valid."""
        return validate_room(v)


# =============================================================================
# VOLUME COMMAND
# =============================================================================


class VolumeCommand(BaseModel):
    """Command to set audio volume.

    Can target a specific zone or default to the primary zone.
    """

    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=0, le=100, description="Volume level (0-100)")
    zone: str | None = Field(default=None, description="Audio zone (optional)")


# =============================================================================
# LOCK COMMAND
# =============================================================================


class LockCommand(BaseModel):
    """Command to control door locks.

    Actions: lock, unlock
    Can target a specific door or all doors.
    """

    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^(lock|unlock)$", description="Lock action")
    door_name: str | None = Field(default=None, description="Specific door (optional)")


# =============================================================================
# SPOTIFY COMMAND
# =============================================================================


class SpotifyCommand(BaseModel):
    """Command to control Spotify playback.

    Actions: play, pause, next, previous, volume
    """

    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^(play|pause|next|previous|volume)$")
    playlist: str | None = Field(default=None, min_length=1)
    volume: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_action_params(self) -> SpotifyCommand:
        """Ensure required params for action."""
        if self.action == "play" and not self.playlist:
            raise ValueError("play action requires playlist name")
        if self.action == "volume" and self.volume is None:
            raise ValueError("volume action requires volume level")
        return self


# =============================================================================
# UTILITIES
# =============================================================================


def validate_command(command_type: type[BaseModel], **kwargs: Any) -> BaseModel:
    """Validate a command and return the model.

    Args:
        command_type: Pydantic model class
        **kwargs: Command parameters

    Returns:
        Validated command model

    Raises:
        ValueError: If validation fails (with clear message)
    """
    try:
        return command_type(**kwargs)
    except Exception as e:
        # Re-raise with cleaner message
        raise ValueError(f"Invalid {command_type.__name__}: {e}") from e


__all__ = [
    # Constants
    "VALID_ROOMS",
    "VALID_SCENES",
    "VALID_COLONY_VOICES",
    # Commands
    "AnnounceCommand",
    "LightCommand",
    "LockCommand",
    "SceneCommand",
    "ShadeCommand",
    "SpotifyCommand",
    "TemperatureCommand",
    "TVMountCommand",
    "VolumeCommand",
    # Utilities
    "validate_command",
    "validate_rooms",
    "validate_room",
]
