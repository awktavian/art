"""Kagami SmartHome Schemas — Single Source of Truth.

All command schemas are defined here. Import from this module to ensure
consistency across the codebase.

Created: January 11, 2026
"""

from kagami_smarthome.schemas.commands import (
    VALID_ROOMS,
    VALID_SCENES,
    AnnounceCommand,
    LightCommand,
    LockCommand,
    SceneCommand,
    ShadeCommand,
    SpotifyCommand,
    TemperatureCommand,
    TVMountCommand,
    VolumeCommand,
    validate_command,
    validate_rooms,
)

__all__ = [
    # Constants
    "VALID_ROOMS",
    "VALID_SCENES",
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
]
