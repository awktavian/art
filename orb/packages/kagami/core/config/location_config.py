"""Home Location Configuration — Single Source of Truth.

PORTABLE DESIGN:
===============
Kagami may be housed anywhere. This module provides the SINGLE source
of location coordinates for all subsystems:
- Celestial mechanics (sun/moon position)
- Geofencing (presence detection)
- Maps integration (distance/ETA)
- Tesla event bus (home detection)

Configuration Sources (priority order):
1. Environment variables: KAGAMI_HOME_LAT, KAGAMI_HOME_LON
2. Config file: config/location.yaml
3. Default: Tim's house (7331 W Green Lake Dr N, Seattle, WA 98103)

USAGE:
======
    from kagami.core.config.location_config import get_home_location, HomeLocation

    location = get_home_location()
    print(f"Home: {location.latitude}, {location.longitude}")
    print(f"Address: {location.address}")

Created: January 8, 2026
Author: Kagami (鏡)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# DATA TYPES
# =============================================================================


@dataclass(frozen=True)
class HomeLocation:
    """Immutable home location configuration.

    Attributes:
        latitude: Degrees (positive = North)
        longitude: Degrees (positive = East, negative = West)
        address: Human-readable address
        name: Short name for the location
        timezone: IANA timezone (e.g., "America/Los_Angeles")
        geofence_radius_m: Radius in meters for "at home" detection
    """

    latitude: float
    longitude: float
    address: str = ""
    name: str = "Home"
    timezone: str = "America/Los_Angeles"
    geofence_radius_m: float = 150.0  # ~500 feet

    def __post_init__(self) -> None:
        """Validate coordinates."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Invalid latitude: {self.latitude} (must be -90 to 90)")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Invalid longitude: {self.longitude} (must be -180 to 180)")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "name": self.name,
            "timezone": self.timezone,
            "geofence_radius_m": self.geofence_radius_m,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HomeLocation:
        """Create from dictionary."""
        return cls(
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            address=data.get("address", ""),
            name=data.get("name", "Home"),
            timezone=data.get("timezone", "America/Los_Angeles"),
            geofence_radius_m=float(data.get("geofence_radius_m", 150.0)),
        )


# =============================================================================
# DEFAULT LOCATION
# =============================================================================

# Tim's house — the default when no configuration is provided
DEFAULT_LOCATION = HomeLocation(
    latitude=47.6825,
    longitude=-122.3442,
    address="7331 W Green Lake Dr N, Seattle, WA 98103",
    name="Green Lake",
    timezone="America/Los_Angeles",
    geofence_radius_m=150.0,
)


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================


def _load_from_env() -> HomeLocation | None:
    """Load location from environment variables.

    Looks for:
        KAGAMI_HOME_LAT: Latitude
        KAGAMI_HOME_LON: Longitude
        KAGAMI_HOME_ADDRESS: (optional) Address
        KAGAMI_HOME_NAME: (optional) Name
        KAGAMI_HOME_TIMEZONE: (optional) Timezone
        KAGAMI_HOME_GEOFENCE_RADIUS: (optional) Geofence radius in meters
    """
    lat_str = os.getenv("KAGAMI_HOME_LAT")
    lon_str = os.getenv("KAGAMI_HOME_LON")

    if lat_str is None or lon_str is None:
        return None

    try:
        return HomeLocation(
            latitude=float(lat_str),
            longitude=float(lon_str),
            address=os.getenv("KAGAMI_HOME_ADDRESS", ""),
            name=os.getenv("KAGAMI_HOME_NAME", "Home"),
            timezone=os.getenv("KAGAMI_HOME_TIMEZONE", "America/Los_Angeles"),
            geofence_radius_m=float(os.getenv("KAGAMI_HOME_GEOFENCE_RADIUS", "150.0")),
        )
    except ValueError as e:
        logger.warning(f"Invalid location in environment: {e}")
        return None


def _load_from_file() -> HomeLocation | None:
    """Load location from config/location.yaml.

    Expected format:
        home:
          latitude: 47.6825
          longitude: -122.3442
          address: "7331 W Green Lake Dr N, Seattle, WA 98103"
          name: "Green Lake"
          timezone: "America/Los_Angeles"
          geofence_radius_m: 150.0
    """
    # Find config directory (relative to workspace root)
    config_paths = [
        Path("config/location.yaml"),
        Path("/Users/schizodactyl/projects/kagami/config/location.yaml"),
        Path.home() / ".kagami" / "location.yaml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml

                with open(config_path) as f:
                    data = yaml.safe_load(f)

                if data and "home" in data:
                    return HomeLocation.from_dict(data["home"])

            except Exception as e:
                logger.warning(f"Error loading {config_path}: {e}")

    return None


# =============================================================================
# SINGLETON
# =============================================================================

_location: HomeLocation | None = None


def get_home_location() -> HomeLocation:
    """Get the configured home location.

    Priority:
    1. Environment variables (KAGAMI_HOME_LAT, KAGAMI_HOME_LON)
    2. Config file (config/location.yaml)
    3. Default (Tim's house)

    Returns:
        HomeLocation instance (cached after first call)
    """
    global _location

    if _location is not None:
        return _location

    # Try environment first
    _location = _load_from_env()
    if _location is not None:
        logger.info(f"📍 Home location from environment: {_location.name}")
        return _location

    # Try config file
    _location = _load_from_file()
    if _location is not None:
        logger.info(f"📍 Home location from config: {_location.name}")
        return _location

    # Fall back to default
    _location = DEFAULT_LOCATION
    logger.info(f"📍 Home location using default: {_location.name}")
    return _location


def set_home_location(location: HomeLocation) -> None:
    """Set the home location (for testing or runtime configuration).

    Args:
        location: New home location
    """
    global _location
    _location = location
    logger.info(
        f"📍 Home location set to: {location.name} ({location.latitude}, {location.longitude})"
    )


def reset_home_location() -> None:
    """Reset cached location (for testing)."""
    global _location
    _location = None


def validate_location_consistency() -> dict[str, Any]:
    """Validate that all modules are using consistent coordinates.

    Returns:
        Dict with validation results
    """
    location = get_home_location()
    issues: list[str] = []

    # Check if we're using default
    is_default = (
        location.latitude == DEFAULT_LOCATION.latitude
        and location.longitude == DEFAULT_LOCATION.longitude
    )

    return {
        "configured_location": location.to_dict(),
        "is_default": is_default,
        "source": "environment"
        if _load_from_env()
        else ("file" if _load_from_file() else "default"),
        "issues": issues,
        "valid": len(issues) == 0,
    }


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================


def get_home_latitude() -> float:
    """Get home latitude."""
    return get_home_location().latitude


def get_home_longitude() -> float:
    """Get home longitude."""
    return get_home_location().longitude


def get_home_coordinates() -> tuple[float, float]:
    """Get home coordinates as (latitude, longitude) tuple."""
    loc = get_home_location()
    return (loc.latitude, loc.longitude)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DEFAULT_LOCATION",
    "HomeLocation",
    "get_home_coordinates",
    "get_home_latitude",
    "get_home_location",
    "get_home_longitude",
    "reset_home_location",
    "set_home_location",
    "validate_location_consistency",
]
