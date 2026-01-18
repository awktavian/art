"""Rooms Module — Backwards Compatibility Re-export.

This module re-exports all symbols from kagami_smarthome.room for backwards
compatibility. New code should import from kagami_smarthome.room directly.

DEPRECATION NOTICE (January 12, 2026):
    Use `from kagami_smarthome.room import ...` instead of
    `from kagami_smarthome.rooms import ...`

The singular `room` module is the canonical source for room-related types.
"""

from kagami_smarthome.orchestrator import RoomOrchestrator
from kagami_smarthome.room import (
    ActivityContext,
    AudioZone,
    Light,
    Room,
    RoomPreferences,
    RoomRegistry,
    RoomState,
    RoomType,
    Shade,
)

__all__ = [
    # Room types
    "Room",
    "RoomRegistry",
    "RoomState",
    "RoomType",
    "RoomPreferences",
    "ActivityContext",
    # Device types
    "Light",
    "Shade",
    "AudioZone",
    # Orchestrator
    "RoomOrchestrator",
]
