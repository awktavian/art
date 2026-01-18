"""Home Geometry — Window Orientations and Sun Exposure.

GROUND TRUTH (from Tim, January 8, 2026):
=========================================
- GREEN LAKE is at the FRONT of the house (SOUTH)
- ALLEY/DRIVEWAY/BACKYARD is at the BACK (NORTH)
- PRIMARY BEDROOM is at the BACK above the GARAGE
- Basement PATIO opens to BACKYARD (north)

VERIFIED FROM ARCHITECTURAL PLANS (Thomas James Homes):
=======================================================
Address: 7331 W Green Lake Dr N, Seattle, WA 98103
Style: The Crescent Collection - Farmhouse Elevation

Floor plan orientation (from electrical plans):
- TOP of plan = NORTH (back, alley, garage)
- BOTTOM of plan = SOUTH (front, lake, porch)
- LEFT of plan = WEST
- RIGHT of plan = EAST

Room positions:
- GARAGE: Back-left (NW corner)
- PRIMARY BEDROOM: Back (above garage, N side)
- LIVING ROOM: Front-center (S side, lake views)
- ENTRY/PORCH: Front (S side)
- BED 4: Basement west side

CARDINAL DIRECTIONS (True North = 0°):
- SOUTH (180°) = FRONT = toward Green Lake
- NORTH (0°) = BACK = toward alley/backyard
- EAST (90°) = right side when facing lake
- WEST (270°) = left side when facing lake

Created: January 3, 2026
CORRECTED: January 8, 2026 — Verified against architectural plans
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# LOCATION (from central config)
# =============================================================================

from kagami.core.config.location_config import (
    get_home_latitude,
    get_home_longitude,
)

HOME_LATITUDE = get_home_latitude()
HOME_LONGITUDE = get_home_longitude()


# =============================================================================
# HOUSE ORIENTATION
# =============================================================================


class Direction(str, Enum):
    """Cardinal directions."""

    SOUTH = "S"  # 180° — FRONT, toward Green Lake
    NORTH = "N"  # 0° — BACK, toward alley/backyard
    EAST = "E"  # 90° — Right side (when facing lake)
    WEST = "W"  # 270° — Left side (when facing lake)


AZIMUTH = {
    Direction.SOUTH: 180.0,
    Direction.NORTH: 0.0,
    Direction.EAST: 90.0,
    Direction.WEST: 270.0,
}

DIRECTION_NAMES = {
    Direction.SOUTH: "South (Front/Lake)",
    Direction.NORTH: "North (Back/Alley)",
    Direction.EAST: "East",
    Direction.WEST: "West",
}


def sun_hits_direction(sun_azimuth: float, direction: Direction) -> bool:
    """Check if sun can enter windows facing this direction.

    Sun enters when within ±60° of window facing (accounts for window depth).
    """
    window_azimuth = AZIMUTH[direction]
    diff = abs(sun_azimuth - window_azimuth)
    if diff > 180:
        diff = 360 - diff
    return diff <= 60


def get_sun_intensity(sun_azimuth: float, sun_altitude: float, direction: Direction) -> float:
    """Calculate sun intensity on window (0.0-1.0).

    Higher = more glare. Considers angular alignment and sun altitude.
    """
    if sun_altitude <= 0:
        return 0.0

    window_azimuth = AZIMUTH[direction]
    diff = abs(sun_azimuth - window_azimuth)
    if diff > 180:
        diff = 360 - diff

    if diff > 60:
        return 0.0

    # Alignment: 1.0 when direct, 0.0 at 60°
    alignment = 1.0 - (diff / 60.0)

    # Altitude: lower sun = more glare
    if sun_altitude < 15:
        altitude_factor = 1.0
    elif sun_altitude < 45:
        altitude_factor = 1.0 - ((sun_altitude - 15) / 45)
    else:
        altitude_factor = max(0, 0.33 - ((sun_altitude - 45) / 135))

    return alignment * altitude_factor


# =============================================================================
# SHADES — All 11 motorized shades
# =============================================================================


class ShadeMode(str, Enum):
    """Shade control mode."""

    ANALOG = "analog"  # 0-100%
    BINARY = "binary"  # 0% or 100% (doors)


@dataclass
class Shade:
    """Motorized shade with Control4 ID and orientation."""

    id: int
    name: str
    room: str
    facing: Direction
    mode: ShadeMode = ShadeMode.ANALOG

    @property
    def azimuth(self) -> float:
        return AZIMUTH[self.facing]


# Complete inventory from Control4
# Verified against architectural floor plans
SHADES: dict[int, Shade] = {
    # =========================================================================
    # FIRST FLOOR — Front of house (SOUTH toward lake)
    # =========================================================================
    # Living Room: Front-center, lake views
    235: Shade(235, "Living South", "Living Room", Direction.SOUTH),
    237: Shade(237, "Living East", "Living Room", Direction.EAST),
    # Dining Room: Center, with slider to deck
    243: Shade(243, "Dining South", "Dining", Direction.SOUTH),
    241: Shade(241, "Dining Slider", "Dining", Direction.SOUTH, ShadeMode.BINARY),
    # Entry: Front of house
    229: Shade(229, "Entry", "Entry", Direction.SOUTH),
    # =========================================================================
    # SECOND FLOOR — Primary suite at BACK (NORTH above garage)
    # =========================================================================
    # Primary Bedroom: Back of house above garage
    66: Shade(66, "Primary North", "Primary Bed", Direction.NORTH),
    68: Shade(68, "Primary West", "Primary Bed", Direction.WEST),
    # Primary Bath: Back of house
    353: Shade(353, "Primary Bath Right", "Primary Bath", Direction.NORTH),
    355: Shade(355, "Primary Bath Left", "Primary Bath", Direction.NORTH),
    # =========================================================================
    # BASEMENT — West side
    # =========================================================================
    # Bed 4: West side of basement (AADU BR4 in plans)
    359: Shade(359, "Bed 4 Right", "Bed 4", Direction.WEST),
    361: Shade(361, "Bed 4 Left", "Bed 4", Direction.WEST),
}


# =============================================================================
# SHADE CALCULATION
# =============================================================================


def calculate_shade_level(
    shade: Shade,
    sun_azimuth: float,
    sun_altitude: float,
    is_day: bool,
) -> tuple[int, str]:
    """Calculate optimal shade level.

    Rules:
    1. Night → OPEN (100%)
    2. No sun on window → OPEN (100%)
    3. Sun on window → Close proportional to glare
    4. BINARY (doors) → OPEN unless severe glare
    """
    if not is_day:
        return 100, "Night"

    intensity = get_sun_intensity(sun_azimuth, sun_altitude, shade.facing)

    if intensity == 0:
        return 100, f"No sun on {shade.facing.value}"

    if shade.mode == ShadeMode.BINARY:
        if intensity > 0.7 and sun_altitude < 15:
            return 0, f"Severe glare ({intensity:.0%})"
        return 100, "Open for access"

    # ANALOG: proportional
    level = int(100 - (intensity * 80))
    level = max(20, min(100, level))

    return level, f"Sun {sun_azimuth:.0f}° → {shade.facing.value} ({intensity:.0%})"


def get_all_shade_recommendations(
    sun_azimuth: float,
    sun_altitude: float,
    is_day: bool,
) -> dict[int, tuple[int, str]]:
    """Get recommendations for all shades."""
    return {
        sid: calculate_shade_level(s, sun_azimuth, sun_altitude, is_day)
        for sid, s in SHADES.items()
    }


# =============================================================================
# CONVENIENCE
# =============================================================================


def get_rooms_needing_shades_closed(dt=None) -> list[str]:
    """Get rooms with significant glare right now."""
    from .ephemeris import sun_position

    sun = sun_position(HOME_LATITUDE, HOME_LONGITUDE, dt)
    if not sun.is_day:
        return []

    rooms = set()
    for shade in SHADES.values():
        if get_sun_intensity(sun.azimuth, sun.altitude, shade.facing) > 0.3:
            rooms.add(shade.room)
    return list(rooms)


def explain_current_sun(dt=None) -> str:
    """Human-readable sun/glare explanation."""
    from .ephemeris import sun_position

    sun = sun_position(HOME_LATITUDE, HOME_LONGITUDE, dt)

    if not sun.is_day:
        return "☾ Sun below horizon"

    affected = []
    for d in Direction:
        intensity = get_sun_intensity(sun.azimuth, sun.altitude, d)
        if intensity > 0:
            affected.append(f"{DIRECTION_NAMES[d]} ({intensity:.0%})")

    msg = f"☀ Sun: {sun.azimuth:.0f}° az, {sun.altitude:.0f}° alt"
    if affected:
        msg += f"\n   Glare: {', '.join(affected)}"
    return msg


def get_house_diagram() -> str:
    """ASCII diagram matching architectural floor plans."""
    return """
    ══════════════════════════════════════════════════════════════════
                        NORTH (0°) — ALLEY / BACKYARD
    ══════════════════════════════════════════════════════════════════
                                    ↑
           ┌────────────────────────┴────────────────────────┐
           │                    SECOND FLOOR                 │
           │  ┌─────────────┬─────────────┬────────────────┐ │
           │  │PRIMARY BATH │PRIMARY BED  │                │ │
           │  │ (353,355):N │  (66):N     │     LOFT       │ │
           │  │             │  (68):W     │                │ │
           │  ├─────────────┼─────────────┼────────────────┤ │
           │  │   LAUNDRY   │    BR3      │     BR2        │ │
           │  └─────────────┴─────────────┴────────────────┘ │
           │                                                 │
    WEST ──┤                    FIRST FLOOR                  ├── EAST
    270°   │  ┌─────────────┬─────────────┬────────────────┐ │   90°
           │  │   GARAGE    │   KITCHEN   │                │ │
           │  │             │             │   LIVING RM    │ │
           │  │   MUDROOM   │   DINING    │   (235):S      │ │
           │  │             │  (243):S    │   (237):E      │ │
           │  │   ENTRY     │  (241):S    │                │ │
           │  │   (229):S   │   slider    │                │ │
           │  ├─────────────┴─────────────┴────────────────┤ │
           │  │   PORCH            DECK (main)             │ │
           │  └────────────────────────────────────────────┘ │
           │                                                 │
           │                    BASEMENT                     │
           │  ┌─────────────┬─────────────┬────────────────┐ │
           │  │    BED 4    │    GYM      │    PATIO       │ │
           │  │  (359):W    │             │  → backyard    │ │
           │  │  (361):W    │   GAME RM   │                │ │
           │  │    BATH 4   │             │                │ │
           │  └─────────────┴─────────────┴────────────────┘ │
           └────────────────────────┬────────────────────────┘
                                    ↓
    ══════════════════════════════════════════════════════════════════
                        SOUTH (180°) — GREEN LAKE
    ══════════════════════════════════════════════════════════════════

    SHADE SUMMARY:
    ┌──────────────────┬──────┬─────────┬────────────────────────────┐
    │ Shade            │  ID  │ Facing  │ Notes                      │
    ├──────────────────┼──────┼─────────┼────────────────────────────┤
    │ Living South     │ 235  │ S 180°  │ Lake view                  │
    │ Living East      │ 237  │ E  90°  │ Side windows               │
    │ Dining South     │ 243  │ S 180°  │ Lake view                  │
    │ Dining Slider    │ 241  │ S 180°  │ To deck (BINARY)           │
    │ Entry            │ 229  │ S 180°  │ Front door side            │
    │ Primary North    │  66  │ N   0°  │ Backyard view              │
    │ Primary West     │  68  │ W 270°  │ Side windows               │
    │ Primary Bath L   │ 355  │ N   0°  │ Back of house              │
    │ Primary Bath R   │ 353  │ N   0°  │ Back of house              │
    │ Bed 4 Left       │ 361  │ W 270°  │ Basement west              │
    │ Bed 4 Right      │ 359  │ W 270°  │ Basement west              │
    └──────────────────┴──────┴─────────┴────────────────────────────┘
    """


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AZIMUTH",
    "DIRECTION_NAMES",
    "HOME_LATITUDE",
    "HOME_LONGITUDE",
    "SHADES",
    "Direction",
    "Shade",
    "ShadeMode",
    "calculate_shade_level",
    "explain_current_sun",
    "get_all_shade_recommendations",
    "get_house_diagram",
    "get_rooms_needing_shades_closed",
    "get_sun_intensity",
    "sun_hits_direction",
]
