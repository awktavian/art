"""Orb Constants — Spatial Zones and LED Mappings.

This module defines the canonical spatial zones for orb positioning
and LED zone mappings for hardware implementations.

Based on proxemics research and visionOS spatial design guidelines:
    - Intimate: 0-45cm (notifications, alerts)
    - Personal: 45cm-1.2m (controls, interactions)
    - Social: 1.2m-3.6m (visualizations, models)
    - Ambient: 3.6m+ (presence, awareness)

Colony: Beacon (e₅) — Architecture and standards

Example:
    >>> from kagami.core.orb.constants import SpatialZone, SPATIAL_ZONES
    >>> zone = SPATIAL_ZONES["ambient"]
    >>> print(zone.min_distance)  # 3.6
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SpatialZoneType(str, Enum):
    """Spatial zone categories based on proxemics."""

    INTIMATE = "intimate"
    PERSONAL = "personal"
    SOCIAL = "social"
    AMBIENT = "ambient"


@dataclass(frozen=True)
class SpatialZone:
    """Spatial zone definition for orb positioning.

    Attributes:
        zone_type: Zone category (intimate, personal, social, ambient)
        min_distance: Minimum distance in meters
        max_distance: Maximum distance in meters
        description: Human-readable description
        typical_content: What typically appears in this zone

    Example:
        >>> zone = SpatialZone(
        ...     SpatialZoneType.AMBIENT, 3.6, 10.0,
        ...     "Background awareness", ["orb", "particles"]
        ... )
    """

    zone_type: SpatialZoneType
    min_distance: float
    max_distance: float
    description: str
    typical_content: list[str]

    def contains(self, distance: float) -> bool:
        """Check if a distance falls within this zone.

        Args:
            distance: Distance in meters

        Returns:
            True if distance is within zone bounds
        """
        return self.min_distance <= distance < self.max_distance


# =============================================================================
# Canonical Spatial Zones (from visionOS FullSpatialExperienceView)
# =============================================================================

SPATIAL_ZONES: dict[str, SpatialZone] = {
    "intimate": SpatialZone(
        zone_type=SpatialZoneType.INTIMATE,
        min_distance=0.0,
        max_distance=0.45,
        description="Private notifications and emergency alerts",
        typical_content=["notifications", "alerts", "confirmations"],
    ),
    "personal": SpatialZone(
        zone_type=SpatialZoneType.PERSONAL,
        min_distance=0.45,
        max_distance=1.2,
        description="Control panel and active interactions",
        typical_content=["controls", "buttons", "sliders", "quick_actions"],
    ),
    "social": SpatialZone(
        zone_type=SpatialZoneType.SOCIAL,
        min_distance=1.2,
        max_distance=3.6,
        description="Home model and room visualization",
        typical_content=["home_model", "room_cubes", "floor_plans"],
    ),
    "ambient": SpatialZone(
        zone_type=SpatialZoneType.AMBIENT,
        min_distance=3.6,
        max_distance=10.0,
        description="Kagami orb presence and ambient awareness",
        typical_content=["orb", "particles", "ambient_indicators"],
    ),
}


# =============================================================================
# Default Orb Positions (in meters, relative to head)
# =============================================================================


@dataclass(frozen=True)
class OrbPositionPreset:
    """Preset orb position for different contexts.

    Attributes:
        name: Preset name
        position: (x, y, z) position relative to head
        zone: Which spatial zone this position is in
    """

    name: str
    position: tuple[float, float, float]
    zone: SpatialZoneType


ORB_POSITION_PRESETS: dict[str, OrbPositionPreset] = {
    # VisionOS default - ambient zone, right side, slightly above eye level
    "visionos_default": OrbPositionPreset(
        name="visionos_default",
        position=(0.4, 1.4, -2.0),  # x=right, y=up, z=forward
        zone=SpatialZoneType.AMBIENT,
    ),
    # VisionOS presence view - closer, personal zone
    "visionos_presence": OrbPositionPreset(
        name="visionos_presence",
        position=(0.3, 1.2, -0.8),
        zone=SpatialZoneType.PERSONAL,
    ),
    # Desktop - center of ambient display
    "desktop_ambient": OrbPositionPreset(
        name="desktop_ambient",
        position=(0.0, 0.0, 0.0),  # 2D center
        zone=SpatialZoneType.INTIMATE,  # Screen is intimate
    ),
    # Hardware orb - on base station
    "hardware_docked": OrbPositionPreset(
        name="hardware_docked",
        position=(0.0, 0.015, 0.0),  # 15mm levitation
        zone=SpatialZoneType.SOCIAL,  # Tabletop distance
    ),
}


# =============================================================================
# LED Zone Mapping (for Hardware Orb SK6812 24-LED ring)
# =============================================================================


@dataclass(frozen=True)
class LEDZone:
    """LED zone mapping for hardware orb.

    The 24-LED ring is divided into 7 zones, one per colony.
    LEDs are numbered 0-23 counter-clockwise from top.

    Attributes:
        colony: Colony name
        led_start: First LED index (inclusive)
        led_end: Last LED index (inclusive)
        led_count: Number of LEDs in zone
    """

    colony: str
    led_start: int
    led_end: int

    @property
    def led_count(self) -> int:
        """Number of LEDs in this zone."""
        return self.led_end - self.led_start + 1

    @property
    def led_indices(self) -> list[int]:
        """List of LED indices in this zone."""
        return list(range(self.led_start, self.led_end + 1))


# From hardware orb spec: 24 LEDs divided into 7 zones
LED_ZONE_MAPPING: dict[str, LEDZone] = {
    "spark": LEDZone(colony="spark", led_start=0, led_end=2),  # 3 LEDs
    "forge": LEDZone(colony="forge", led_start=3, led_end=5),  # 3 LEDs
    "flow": LEDZone(colony="flow", led_start=6, led_end=9),  # 4 LEDs
    "nexus": LEDZone(colony="nexus", led_start=10, led_end=13),  # 4 LEDs
    "beacon": LEDZone(colony="beacon", led_start=14, led_end=17),  # 4 LEDs
    "grove": LEDZone(colony="grove", led_start=18, led_end=20),  # 3 LEDs
    "crystal": LEDZone(colony="crystal", led_start=21, led_end=23),  # 3 LEDs
}


def get_zone_for_distance(distance: float) -> SpatialZone:
    """Get the spatial zone for a given distance.

    Args:
        distance: Distance in meters

    Returns:
        SpatialZone containing that distance

    Example:
        >>> zone = get_zone_for_distance(2.0)
        >>> zone.zone_type
        SpatialZoneType.SOCIAL
    """
    for zone in SPATIAL_ZONES.values():
        if zone.contains(distance):
            return zone
    # Default to ambient for very far distances
    return SPATIAL_ZONES["ambient"]


def get_colony_led_indices(colony: str) -> list[int]:
    """Get LED indices for a colony on the hardware orb.

    Args:
        colony: Colony name (spark, forge, etc.)

    Returns:
        List of LED indices (0-23) for that colony

    Example:
        >>> get_colony_led_indices("spark")
        [0, 1, 2]
    """
    zone = LED_ZONE_MAPPING.get(colony.lower())
    if zone is None:
        return []
    return zone.led_indices
