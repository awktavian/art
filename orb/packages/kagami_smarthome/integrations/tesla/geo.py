"""Tesla Geolocation Utilities — Consolidated Module.

Provides geofencing and distance calculations for Tesla integrations.
Single source of truth for geo functions used by:
- tesla.py (TeslaIntegration.is_home, is_away, get_location)
- tesla_event_bus.py (_is_at_home, _distance_to_home, _haversine, _bearing)

All location constants are sourced from the central location_config module
for portability.

Created: January 11, 2026
Author: Kagami
"""

from __future__ import annotations

import math

from kagami.core.config.location_config import get_home_location

# =============================================================================
# CONSTANTS — Derived from central config
# =============================================================================

_location = get_home_location()

#: Home latitude in degrees (positive = North)
HOME_LAT: float = _location.latitude

#: Home longitude in degrees (positive = East, negative = West)
HOME_LON: float = _location.longitude

#: Home geofence radius in miles (for haversine-based calculations)
HOME_RADIUS_MILES: float = _location.geofence_radius_m / 1609.34

#: Home geofence radius in meters
HOME_RADIUS_METERS: float = _location.geofence_radius_m


# =============================================================================
# HAVERSINE FORMULA
# =============================================================================


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in miles.

    Uses the haversine formula for accurate distance on a sphere.

    Args:
        lat1: Latitude of point 1 in degrees
        lon1: Longitude of point 1 in degrees
        lat2: Latitude of point 2 in degrees
        lon2: Longitude of point 2 in degrees

    Returns:
        Distance in miles

    Example:
        >>> haversine(47.6825, -122.3442, 47.6062, -122.3321)  # Green Lake to Space Needle
        5.32...
    """
    earth_radius_miles = 3959

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return earth_radius_miles * c


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters.

    Args:
        lat1: Latitude of point 1 in degrees
        lon1: Longitude of point 1 in degrees
        lat2: Latitude of point 2 in degrees
        lon2: Longitude of point 2 in degrees

    Returns:
        Distance in meters
    """
    return haversine(lat1, lon1, lat2, lon2) * 1609.34


# =============================================================================
# BEARING CALCULATION
# =============================================================================


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing from point 1 to point 2.

    Returns the azimuth angle in degrees (0-360), where:
    - 0/360 = North
    - 90 = East
    - 180 = South
    - 270 = West

    Args:
        lat1: Latitude of start point in degrees
        lon1: Longitude of start point in degrees
        lat2: Latitude of end point in degrees
        lon2: Longitude of end point in degrees

    Returns:
        Bearing in degrees (0-360)

    Example:
        >>> bearing(47.6825, -122.3442, 47.6062, -122.3321)  # Green Lake to Space Needle
        171.5...  # Roughly South
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(dlon)

    bearing_rad = math.atan2(x, y)
    return (math.degrees(bearing_rad) + 360) % 360


# =============================================================================
# HOME GEOFENCING
# =============================================================================


def is_at_home(lat: float, lon: float, radius_miles: float | None = None) -> bool:
    """Check if coordinates are within the home geofence.

    Args:
        lat: Latitude to check
        lon: Longitude to check
        radius_miles: Custom radius in miles (default: HOME_RADIUS_MILES)

    Returns:
        True if within geofence, False otherwise

    Example:
        >>> is_at_home(47.6825, -122.3442)  # At home
        True
        >>> is_at_home(47.6062, -122.3321)  # At Space Needle
        False
    """
    if radius_miles is None:
        radius_miles = HOME_RADIUS_MILES

    distance = haversine(lat, lon, HOME_LAT, HOME_LON)
    return distance < radius_miles


def distance_to_home(lat: float, lon: float) -> float:
    """Calculate distance to home in miles.

    Args:
        lat: Current latitude
        lon: Current longitude

    Returns:
        Distance to home in miles

    Example:
        >>> distance_to_home(47.6062, -122.3321)  # Space Needle
        5.32...
    """
    return haversine(lat, lon, HOME_LAT, HOME_LON)


def distance_to_home_meters(lat: float, lon: float) -> float:
    """Calculate distance to home in meters.

    Args:
        lat: Current latitude
        lon: Current longitude

    Returns:
        Distance to home in meters
    """
    return haversine_meters(lat, lon, HOME_LAT, HOME_LON)


def is_heading_home(
    lat: float, lon: float, heading: float, tolerance_degrees: float = 45.0
) -> bool:
    """Check if the vehicle is heading toward home.

    Compares the vehicle's current heading to the bearing toward home.
    Returns True if heading is within tolerance of the home bearing.

    Args:
        lat: Current latitude
        lon: Current longitude
        heading: Current heading in degrees (0-360)
        tolerance_degrees: Maximum deviation from home bearing (default: 45)

    Returns:
        True if heading toward home within tolerance

    Example:
        >>> is_heading_home(47.6062, -122.3321, 0.0)  # Heading North from Space Needle
        True  # Home is roughly North
    """
    bearing_to_home = bearing(lat, lon, HOME_LAT, HOME_LON)

    # Calculate angular difference
    diff = abs(heading - bearing_to_home)
    if diff > 180:
        diff = 360 - diff

    return diff < tolerance_degrees


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    "HOME_LAT",
    "HOME_LON",
    "HOME_RADIUS_MILES",
    "HOME_RADIUS_METERS",
    # Distance functions
    "haversine",
    "haversine_meters",
    "bearing",
    # Home geofencing
    "is_at_home",
    "distance_to_home",
    "distance_to_home_meters",
    "is_heading_home",
]
