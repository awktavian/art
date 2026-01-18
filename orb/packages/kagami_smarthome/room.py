"""Room Model — First-Class Room Representation.

Each room is a living environment that coordinates:
- Lights (Lutron LEAP dimmers/switches)
- Shades (Lutron LEAP roller shades)
- Audio (Triad AMS zone)
- HVAC (Mitsubishi mini-split zone)

Rooms track their own state and learn preferences over time.

Philosophy:
The room anticipates needs based on:
- WHO is present
- WHAT they're doing (activity context)
- WHEN (time of day, season)
- WHY (inferred intent)

Created: December 29, 2025
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class ActivityContext(str, Enum):
    """What someone is doing in a room."""

    UNKNOWN = "unknown"
    WAKING = "waking"  # Morning routine
    WORKING = "working"  # Focused work
    COOKING = "cooking"  # Kitchen activity
    DINING = "dining"  # Eating
    RELAXING = "relaxing"  # Casual leisure
    WATCHING = "watching"  # TV/Movie
    EXERCISING = "exercising"  # Workout
    SLEEPING = "sleeping"  # Night/nap
    AWAY = "away"  # Room unoccupied
    ENTERTAINING = "entertaining"  # Guests


class RoomType(str, Enum):
    """Room categories for default behavior."""

    LIVING = "living"  # Main gathering space
    FAMILY = "family"  # Secondary gathering
    KITCHEN = "kitchen"  # Food prep
    DINING = "dining"  # Eating area
    BEDROOM = "bedroom"  # Sleep space
    BATHROOM = "bathroom"  # Bath/shower
    OFFICE = "office"  # Work space
    GARAGE = "garage"  # Vehicle/storage
    ENTRY = "entry"  # Foyer/mudroom
    HALLWAY = "hallway"  # Circulation
    UTILITY = "utility"  # Laundry/mechanical
    OUTDOOR = "outdoor"  # Patio/deck
    OTHER = "other"


@dataclass
class Light:
    """A light fixture in a room."""

    id: int  # Control4 item ID
    name: str  # "Kitchen Cans"
    level: int = 0  # 0-100 brightness
    is_dimmable: bool = True
    color_temp: int | None = None  # Kelvin, if tunable


@dataclass
class Shade:
    """A window shade in a room."""

    id: int  # Control4 item ID
    name: str  # "Living Room Shade 1"
    level: int = 0  # 0=open, 100=closed
    is_moving: bool = False
    orientation: str = "south"  # For solar gain awareness


@dataclass
class AudioZone:
    """An audio zone (Triad AMS output)."""

    id: int  # Control4 room ID (zones are rooms)
    name: str  # "Kitchen"
    volume: int = 0  # 0-100
    muted: bool = False
    source_id: int | None = None
    source_name: str | None = None
    is_playing: bool = False


@dataclass
class RoomPreferences:
    """Learned preferences for a room by activity."""

    # Light levels by activity (0-100)
    light_levels: dict[ActivityContext, int] = field(
        default_factory=lambda: {
            ActivityContext.WAKING: 60,
            ActivityContext.WORKING: 80,
            ActivityContext.COOKING: 100,
            ActivityContext.DINING: 70,
            ActivityContext.RELAXING: 40,
            ActivityContext.WATCHING: 10,
            ActivityContext.SLEEPING: 0,
            ActivityContext.AWAY: 0,
            ActivityContext.ENTERTAINING: 70,
        }
    )

    # Temperature by activity (°F)
    temperatures: dict[ActivityContext, float] = field(
        default_factory=lambda: {
            ActivityContext.WAKING: 70.0,
            ActivityContext.WORKING: 72.0,
            ActivityContext.COOKING: 72.0,
            ActivityContext.DINING: 72.0,
            ActivityContext.RELAXING: 72.0,
            ActivityContext.WATCHING: 70.0,
            ActivityContext.SLEEPING: 68.0,
            ActivityContext.AWAY: 65.0,  # Setback
            ActivityContext.ENTERTAINING: 71.0,
        }
    )

    # Audio volume by activity (0-100)
    audio_volumes: dict[ActivityContext, int] = field(
        default_factory=lambda: {
            ActivityContext.WAKING: 25,
            ActivityContext.WORKING: 15,
            ActivityContext.COOKING: 35,
            ActivityContext.DINING: 30,
            ActivityContext.RELAXING: 40,
            ActivityContext.WATCHING: 0,  # Use TV/AVR instead
            ActivityContext.SLEEPING: 0,
            ActivityContext.AWAY: 0,
            ActivityContext.ENTERTAINING: 45,
        }
    )

    # Shade positions by activity (0=open, 100=closed)
    shade_positions: dict[ActivityContext, int] = field(
        default_factory=lambda: {
            ActivityContext.WAKING: 0,  # Let light in
            ActivityContext.WORKING: 30,  # Glare control
            ActivityContext.COOKING: 0,
            ActivityContext.DINING: 0,
            ActivityContext.RELAXING: 50,
            ActivityContext.WATCHING: 100,  # Blackout for movies
            ActivityContext.SLEEPING: 100,
            ActivityContext.AWAY: 50,  # Neutral
            ActivityContext.ENTERTAINING: 30,
        }
    )


@dataclass
class RoomState:
    """Current state of a room."""

    occupied: bool = False
    activity: ActivityContext = ActivityContext.UNKNOWN
    occupant_count: int = 0
    last_motion: float = 0.0
    last_activity_change: float = 0.0

    # Aggregate device states
    avg_light_level: int = 0
    avg_shade_position: int = 0
    current_temp: float | None = None
    target_temp: float | None = None
    audio_playing: bool = False


@dataclass
class Room:
    """A room in the home — first-class citizen.

    Each room coordinates its own:
    - Lights (multiple fixtures)
    - Shades (multiple windows)
    - Audio (single zone from Triad AMS)
    - HVAC (single zone from Mitsubishi)

    Rooms learn preferences and anticipate needs.
    """

    # Identity
    id: int  # Control4 room ID
    name: str  # "Living Room"
    room_type: RoomType = RoomType.OTHER
    floor: str = "Main"  # "Main", "Upper", "Lower"

    # Devices
    lights: list[Light] = field(default_factory=list)
    shades: list[Shade] = field(default_factory=list)
    audio_zone: AudioZone | None = None
    hvac_zone_id: str | None = None  # Mitsubishi zone ID (mapped later)

    # State
    state: RoomState = field(default_factory=RoomState)

    # Learned preferences
    preferences: RoomPreferences = field(default_factory=RoomPreferences)

    # Special flags
    is_home_theater: bool = False  # Has AVR/projector
    has_fireplace: bool = False
    has_tv: bool = False
    is_guest_room: bool = False  # Lights OFF unless occupied (Bed 3, Bath 3, Bed 4, Bath 4)

    # Metadata
    area_sqft: int | None = None

    def get_preferred_light_level(self, activity: ActivityContext | None = None) -> int:
        """Get preferred light level for current or specified activity."""
        act = activity or self.state.activity
        return self.preferences.light_levels.get(act, 50)

    def get_preferred_temp(self, activity: ActivityContext | None = None) -> float:
        """Get preferred temperature for current or specified activity."""
        act = activity or self.state.activity
        return self.preferences.temperatures.get(act, 72.0)

    def get_preferred_audio_volume(self, activity: ActivityContext | None = None) -> int:
        """Get preferred audio volume for current or specified activity."""
        act = activity or self.state.activity
        return self.preferences.audio_volumes.get(act, 0)

    def get_preferred_shade_position(self, activity: ActivityContext | None = None) -> int:
        """Get preferred shade position for current or specified activity."""
        act = activity or self.state.activity
        return self.preferences.shade_positions.get(act, 50)

    def update_preference(
        self,
        what: str,
        activity: ActivityContext,
        value: int | float,
    ) -> None:
        """Learn from manual adjustment.

        When Tim manually adjusts something, we learn that preference.
        Uses exponential moving average to adapt gradually.
        """
        alpha = 0.3  # Learning rate

        if what == "light":
            old = self.preferences.light_levels.get(activity, 50)
            self.preferences.light_levels[activity] = int(old * (1 - alpha) + value * alpha)
        elif what == "temp":
            old = self.preferences.temperatures.get(activity, 72.0)
            self.preferences.temperatures[activity] = old * (1 - alpha) + float(value) * alpha
        elif what == "audio":
            old = self.preferences.audio_volumes.get(activity, 0)
            self.preferences.audio_volumes[activity] = int(old * (1 - alpha) + value * alpha)
        elif what == "shade":
            old = self.preferences.shade_positions.get(activity, 50)
            self.preferences.shade_positions[activity] = int(old * (1 - alpha) + value * alpha)

    def mark_occupied(self, activity: ActivityContext = ActivityContext.UNKNOWN) -> None:
        """Mark room as occupied."""
        now = time.time()
        self.state.occupied = True
        self.state.last_motion = now

        if activity != self.state.activity:
            self.state.activity = activity
            self.state.last_activity_change = now

    def mark_vacant(self) -> None:
        """Mark room as vacant."""
        self.state.occupied = False
        self.state.activity = ActivityContext.AWAY
        self.state.occupant_count = 0

    def time_since_motion(self) -> float:
        """Seconds since last motion."""
        return time.time() - self.state.last_motion if self.state.last_motion else float("inf")

    def time_in_activity(self) -> float:
        """Seconds in current activity."""
        return (
            time.time() - self.state.last_activity_change
            if self.state.last_activity_change
            else 0.0
        )

    def __repr__(self) -> str:
        status = "occupied" if self.state.occupied else "vacant"
        return f"Room({self.name}, {status}, {self.state.activity.value})"


class RoomRegistry:
    """Registry of all rooms in the home.

    Builds rooms from Control4 discovery and maintains state.
    """

    def __init__(self):
        self._rooms: dict[int, Room] = {}  # id -> Room
        self._by_name: dict[str, Room] = {}  # lowercase name -> Room

    def add_room(self, room: Room) -> None:
        """Add a room to the registry."""
        self._rooms[room.id] = room
        self._by_name[room.name.lower()] = room

    def get_by_id(self, room_id: int) -> Room | None:
        """Get room by Control4 ID."""
        return self._rooms.get(room_id)

    def get_by_name(self, name: str) -> Room | None:
        """Get room by name (case-insensitive)."""
        return self._by_name.get(name.lower())

    def get_all(self) -> list[Room]:
        """Get all rooms."""
        return list(self._rooms.values())

    def get_occupied(self) -> list[Room]:
        """Get all occupied rooms."""
        return [r for r in self._rooms.values() if r.state.occupied]

    def get_by_floor(self, floor: str) -> list[Room]:
        """Get rooms on a specific floor."""
        return [r for r in self._rooms.values() if r.floor.lower() == floor.lower()]

    def get_by_type(self, room_type: RoomType) -> list[Room]:
        """Get rooms of a specific type."""
        return [r for r in self._rooms.values() if r.room_type == room_type]

    def get_home_theater(self) -> Room | None:
        """Get the home theater room."""
        for room in self._rooms.values():
            if room.is_home_theater:
                return room
        return None

    def get_guest_rooms(self) -> list[Room]:
        """Get guest rooms (Bed 3, Bath 3, Bed 4, Bath 4).

        These stay dark unless occupied.
        """
        return [r for r in self._rooms.values() if r.is_guest_room]

    def get_non_guest_rooms(self) -> list[Room]:
        """Get non-guest rooms (main living areas).

        These can be lit during welcome_home, sunset prep, etc.
        """
        return [r for r in self._rooms.values() if not r.is_guest_room]

    @classmethod
    def from_control4(
        cls,
        rooms: dict[int, dict[str, Any]],
        lights: dict[int, dict[str, Any]],
        shades: dict[int, dict[str, Any]],
        audio_zones: dict[int, dict[str, Any]],
    ) -> RoomRegistry:
        """Build registry from Control4 discovered items."""
        registry = cls()

        for room_id, room_data in rooms.items():
            name = room_data.get("name", f"Room {room_id}")

            # Infer room type from name
            room_type = cls._infer_room_type(name)

            # Infer floor from name
            floor = cls._infer_floor(name)

            # Create room
            room = Room(
                id=room_id,
                name=name,
                room_type=room_type,
                floor=floor,
            )

            # Add lights in this room
            for light_id, light_data in lights.items():
                if light_data.get("room_id") == room_id:
                    room.lights.append(
                        Light(
                            id=light_id,
                            name=light_data.get("name", f"Light {light_id}"),
                        )
                    )

            # Add shades in this room
            for shade_id, shade_data in shades.items():
                if shade_data.get("room_id") == room_id:
                    room.shades.append(
                        Shade(
                            id=shade_id,
                            name=shade_data.get("name", f"Shade {shade_id}"),
                        )
                    )

            # Add audio zone (room ID = audio zone ID in Control4)
            if room_id in audio_zones:
                zone_data = audio_zones[room_id]
                room.audio_zone = AudioZone(
                    id=room_id,
                    name=zone_data.get("name", name),
                )

            # Set special flags based on room type/name
            name_lower = name.lower()
            if "living" in name_lower:
                room.is_home_theater = True
                room.has_tv = True
            if "family" in name_lower:
                room.has_tv = True
            if "fireplace" in name_lower or "living" in name_lower:
                room.has_fireplace = True

            # Guest rooms: lights stay OFF unless occupied
            # Front bedrooms (Bed 3) and their bathrooms
            # Basement guest areas (Bed 4, Bath 4)
            guest_room_patterns = ["bed 3", "bath 3", "bed 4", "bath 4"]
            if any(pattern in name_lower for pattern in guest_room_patterns):
                room.is_guest_room = True

            registry.add_room(room)

        return registry

    @staticmethod
    def _infer_room_type(name: str) -> RoomType:
        """Infer room type from name."""
        name_lower = name.lower()

        if "living" in name_lower:
            return RoomType.LIVING
        elif "family" in name_lower:
            return RoomType.FAMILY
        elif "kitchen" in name_lower:
            return RoomType.KITCHEN
        elif "dining" in name_lower:
            return RoomType.DINING
        elif "bed" in name_lower or "master" in name_lower or "primary" in name_lower:
            return RoomType.BEDROOM
        elif "bath" in name_lower:
            return RoomType.BATHROOM
        elif "office" in name_lower or "study" in name_lower or "den" in name_lower:
            return RoomType.OFFICE
        elif "garage" in name_lower:
            return RoomType.GARAGE
        elif "entry" in name_lower or "foyer" in name_lower or "mudroom" in name_lower:
            return RoomType.ENTRY
        elif "hall" in name_lower or "stair" in name_lower:
            return RoomType.HALLWAY
        elif "laundry" in name_lower or "utility" in name_lower or "mechanical" in name_lower:
            return RoomType.UTILITY
        elif "patio" in name_lower or "deck" in name_lower or "outdoor" in name_lower:
            return RoomType.OUTDOOR
        else:
            return RoomType.OTHER

    @staticmethod
    def _infer_floor(name: str) -> str:
        """Infer floor from room name."""
        name_lower = name.lower()

        if "upper" in name_lower or "upstairs" in name_lower or "2nd" in name_lower:
            return "Upper"
        elif "lower" in name_lower or "basement" in name_lower or "downstairs" in name_lower:
            return "Lower"
        elif "garage" in name_lower:
            return "Garage"
        elif "outdoor" in name_lower or "patio" in name_lower or "deck" in name_lower:
            return "Outdoor"
        else:
            return "Main"
