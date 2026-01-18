"""Input Validation — Re-exports from schemas.commands.

This module re-exports command schemas from the canonical source in schemas/commands.py.
All schema definitions have been consolidated there. This module exists for backwards
compatibility - prefer importing from kagami_smarthome.schemas.commands directly.

Created: January 2, 2026
Updated: January 11, 2026 — Consolidated to schemas/commands.py
"""

from __future__ import annotations

# Re-export everything from the canonical source
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
    validate_room,
    validate_rooms,
)

__all__ = [
    "VALID_ROOMS",
    "VALID_SCENES",
    "AnnounceCommand",
    "LightCommand",
    "LockCommand",
    "SceneCommand",
    "ShadeCommand",
    "SpotifyCommand",
    "TVMountCommand",
    "TemperatureCommand",
    "VolumeCommand",
    "validate_command",
    "validate_room",
    "validate_rooms",
]
