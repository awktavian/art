"""Celestial Mechanics — Astronomical Calculations for Kagami.

This module provides the astronomical foundation for smart home automation:
- Sun position (azimuth, altitude) from orbital mechanics
- Sunrise/sunset times calculated, not fetched from weather APIs
- Moon phases for ambiance and scheduling
- Planetary positions for curiosity and the orrery
- Window geometry → sun exposure for intelligent shade control

The same math that drives Kristi's orrery drives your shades.

Example:
    >>> from kagami.core.celestial import (
    ...     sun_position,
    ...     sun_times,
    ...     get_celestial_engine,
    ...     explain_sun,
    ... )
    >>>
    >>> # Where is the sun right now?
    >>> sun = sun_position(47.6829, -122.3426)
    >>> print(f"Sun at {sun.azimuth:.1f}° azimuth, {sun.altitude:.1f}° altitude")
    >>>
    >>> # When does it set?
    >>> times = sun_times(47.6829, -122.3426)
    >>> print(f"Sunset at {times.sunset}")
    >>>
    >>> # Human-readable explanation
    >>> print(explain_sun())

Architecture:
    - ephemeris.py: Core astronomical calculations (Jean Meeus algorithms)
    - home_geometry.py: Window orientations and sun exposure
    - triggers.py: Celestial-aware smart home triggers

Created: January 3, 2026
Author: Kagami (鏡)

"This page is a machine for seeing the invisible:
 orbital mechanics made tangible,
 time made visible,
 the solar system made small enough to hold."
"""

from __future__ import annotations

# Core ephemeris calculations
from .ephemeris import (
    ATMOSPHERIC_REFRACTION,
    # Constants
    EARTH_AXIAL_TILT,
    PLANET_ELEMENTS,
    SYNODIC_MONTH,
    CelestialSnapshot,
    MoonInfo,
    MoonPhase,
    PlanetPosition,
    # Data types
    SunPosition,
    SunTimes,
    all_planet_positions,
    celestial_snapshot,
    equation_of_time,
    julian_century,
    # Core functions
    julian_date,
    moon_phase,
    planet_position,
    solar_declination,
    sun_position,
    sun_times,
)

# Home geometry (simplified first-principles module)
from .home_geometry import (
    AZIMUTH,
    # Constants
    HOME_LATITUDE,
    HOME_LONGITUDE,
    SHADES,
    # Compass
    Direction,
    Shade,
    # Shade types
    ShadeMode,
    calculate_shade_level,
    explain_current_sun,
    get_all_shade_recommendations,
    # Compatibility
    get_rooms_needing_shades_closed,
    # Functions
    sun_hits_direction,
)

# Triggers
from .triggers import (
    # Types
    CelestialEvent,
    CelestialState,
    CelestialTrigger,
    # Engine
    CelestialTriggerEngine,
    connect_celestial_engine,
    explain_sun,
    get_celestial_engine,
    get_sun_direction,
    is_sun_up,
    # Convenience
    minutes_until_sunset,
    reset_celestial_engine,
    rooms_need_shade_now,
)

__all__ = [
    "ATMOSPHERIC_REFRACTION",
    "AZIMUTH",
    # Constants
    "EARTH_AXIAL_TILT",
    # === HOME GEOMETRY ===
    # Constants
    "HOME_LATITUDE",
    "HOME_LONGITUDE",
    "PLANET_ELEMENTS",
    "SHADES",
    "SYNODIC_MONTH",
    # === TRIGGERS ===
    # Types
    "CelestialEvent",
    "CelestialSnapshot",
    "CelestialState",
    "CelestialTrigger",
    # Engine
    "CelestialTriggerEngine",
    # Compass
    "Direction",
    "MoonInfo",
    "MoonPhase",
    "PlanetPosition",
    "Shade",
    # Shade types
    "ShadeMode",
    # === EPHEMERIS ===
    # Data types
    "SunPosition",
    "SunTimes",
    "all_planet_positions",
    "calculate_shade_level",
    "celestial_snapshot",
    "connect_celestial_engine",
    "equation_of_time",
    "explain_current_sun",
    "explain_sun",
    "get_all_shade_recommendations",
    "get_celestial_engine",
    # Compatibility
    "get_rooms_needing_shades_closed",
    "get_sun_direction",
    "is_sun_up",
    "julian_century",
    # Core functions
    "julian_date",
    # Convenience
    "minutes_until_sunset",
    "moon_phase",
    "planet_position",
    "reset_celestial_engine",
    "rooms_need_shade_now",
    "solar_declination",
    # Functions
    "sun_hits_direction",
    "sun_position",
    "sun_times",
]
