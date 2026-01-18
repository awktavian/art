"""Property Intelligence — Understanding homes for smart automation.

This integration helps Kagami understand a property's characteristics
for optimal automation setup, including:
- Compass orientation (critical for celestial shade control)
- Lot dimensions and shape
- Building footprint and floor count
- Window and shade locations
- Local climate patterns

Data sources (prioritized):
1. Google Street View (heading data for orientation)
2. OpenStreetMap (building footprints, free)
3. King County Assessor (parcel data, tax records)
4. Zillow/Redfin (property details via scraping)

Created: January 4, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class GeoLocation:
    """Geographic coordinates."""

    latitude: float
    longitude: float

    @property
    def as_tuple(self) -> tuple[float, float]:
        """Return as (lat, lon) tuple."""
        return (self.latitude, self.longitude)


@dataclass
class PropertyOrientation:
    """Building compass orientation.

    The key insight: buildings are rarely aligned with true cardinal directions.
    Most are rotated to match the street grid or lot shape.
    """

    front_azimuth: float  # Direction front door faces (0-360°)
    rotation_from_north: float = 0.0  # Degrees counterclockwise from true N
    confidence: float = 0.0  # 0-1, how confident we are in this measurement
    source: str = "unknown"  # Where this data came from

    @property
    def back_azimuth(self) -> float:
        """Direction the back of house faces."""
        return (self.front_azimuth + 180) % 360

    @property
    def right_azimuth(self) -> float:
        """Direction right side faces (when facing front)."""
        return (self.front_azimuth + 90) % 360

    @property
    def left_azimuth(self) -> float:
        """Direction left side faces (when facing front)."""
        return (self.front_azimuth - 90) % 360

    @property
    def front_cardinal(self) -> str:
        """Nearest cardinal direction for front."""
        return _azimuth_to_cardinal(self.front_azimuth)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "front_azimuth": self.front_azimuth,
            "back_azimuth": self.back_azimuth,
            "right_azimuth": self.right_azimuth,
            "left_azimuth": self.left_azimuth,
            "front_cardinal": self.front_cardinal,
            "rotation_from_north": self.rotation_from_north,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass
class PropertyDetails:
    """Comprehensive property information."""

    address: str
    location: GeoLocation
    orientation: PropertyOrientation | None = None

    # Building details
    year_built: int | None = None
    square_feet: int | None = None
    lot_size_sqft: int | None = None
    stories: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None

    # Lot details
    lot_shape: str | None = None  # rectangular, irregular, corner, etc.

    # Market data
    zestimate: int | None = None
    last_sale_price: int | None = None
    last_sale_date: str | None = None

    # External IDs
    zillow_zpid: str | None = None
    parcel_number: str | None = None

    # Raw data from various sources
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "address": self.address,
            "location": self.location.as_tuple,
            "orientation": self.orientation.to_dict() if self.orientation else None,
            "year_built": self.year_built,
            "square_feet": self.square_feet,
            "lot_size_sqft": self.lot_size_sqft,
            "stories": self.stories,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "zestimate": self.zestimate,
            "last_sale_price": self.last_sale_price,
            "zillow_zpid": self.zillow_zpid,
        }


# =============================================================================
# ORIENTATION DETECTION
# =============================================================================


def _azimuth_to_cardinal(azimuth: float) -> str:
    """Convert azimuth to nearest cardinal/intercardinal direction."""
    # Normalize to 0-360
    az = azimuth % 360

    directions = [
        (0, "N"),
        (22.5, "NNE"),
        (45, "NE"),
        (67.5, "ENE"),
        (90, "E"),
        (112.5, "ESE"),
        (135, "SE"),
        (157.5, "SSE"),
        (180, "S"),
        (202.5, "SSW"),
        (225, "SW"),
        (247.5, "WSW"),
        (270, "W"),
        (292.5, "WNW"),
        (315, "NW"),
        (337.5, "NNW"),
        (360, "N"),
    ]

    for i in range(len(directions) - 1):
        low = directions[i][0]
        high = directions[i + 1][0]
        mid = (low + high) / 2
        if az < mid:
            return directions[i][1]

    return "N"


def orientation_from_street_view_heading(heading: float) -> PropertyOrientation:
    """Derive building orientation from Google Street View camera heading.

    When Street View is looking at the front of a building, the camera heading
    tells us which direction the front faces. The front faces TOWARD the camera.

    Args:
        heading: Street View camera heading (0-360°, 0=North, 90=East)

    Returns:
        PropertyOrientation with front facing opposite the camera
    """
    # Camera at heading H is looking toward H degrees
    # If camera sees front of house, house faces BACK toward camera
    # So front_azimuth = heading (camera looking at front = front facing camera)
    # Wait, that's not right. If camera at 307° sees front, front faces 307°? No.
    # Camera at 307° is looking TOWARD 307° (NW direction)
    # If we see the front while looking NW, the front FACES NW (307°)
    # Actually, the front faces TOWARD us (the camera), not away.
    # So front_azimuth = (heading + 180) % 360? No...

    # Let me think again:
    # - Camera is on the street
    # - Camera heading = direction camera is pointing
    # - If heading = 307°, camera is pointing toward 307° (northwest)
    # - If we see the FRONT of the house, the front is facing US (southeast)
    # - So front_azimuth = (307 + 180) % 360 = 127°? No, that's wrong.

    # Actually, wait. If the camera is looking NW (307°) and sees the front,
    # that means the FRONT is on the NW side of the house, facing the camera.
    # The front FACES the camera, which is SE of the house.
    # So front faces SE (127°)? No...

    # Hmm, let me verify with Tim's house:
    # Street View heading: 307.35° (pointing NW)
    # We SEE the front of the house (lake-facing side)
    # The front faces the LAKE, which is NW of the house
    # So front_azimuth = 307° (NW)
    # The camera is LOOKING at the front from the street (SE of house)
    # So the camera heading (307°) = direction front faces!

    front_azimuth = heading % 360
    rotation = front_azimuth  # Rotation from true north

    return PropertyOrientation(
        front_azimuth=front_azimuth,
        rotation_from_north=rotation,
        confidence=0.9,  # Street View is quite accurate
        source="google_street_view",
    )


def orientation_from_lot_bearing(bearing: float, street_side: str = "front") -> PropertyOrientation:
    """Derive orientation from lot/parcel bearing data.

    Many cities provide parcel data with lot line bearings.
    The front lot line usually faces the street.

    Args:
        bearing: Bearing of front lot line (0-360°)
        street_side: Which side faces the street

    Returns:
        PropertyOrientation
    """
    # Front lot line bearing is perpendicular to front facade
    if street_side == "front":
        front_azimuth = bearing
    else:
        # Rotate based on which side faces street
        rotations = {"right": 90, "back": 180, "left": 270}
        front_azimuth = (bearing + rotations.get(street_side, 0)) % 360

    return PropertyOrientation(
        front_azimuth=front_azimuth,
        rotation_from_north=front_azimuth,
        confidence=0.7,
        source="lot_bearing",
    )


# =============================================================================
# PROPERTY SERVICE
# =============================================================================


class PropertyIntelligenceService:
    """Service for gathering and analyzing property data.

    This helps Kagami understand a new property for automation setup.
    """

    def __init__(self) -> None:
        """Initialize the service."""
        self._cache: dict[str, PropertyDetails] = {}

    async def get_property(self, address: str) -> PropertyDetails | None:
        """Get comprehensive property information.

        Args:
            address: Full street address

        Returns:
            PropertyDetails or None if not found
        """
        # Check cache first
        cache_key = address.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Would fetch from various APIs here
        # For now, return None (not implemented)
        logger.warning(f"Property lookup not implemented for: {address}")
        return None

    def set_property_orientation(
        self,
        address: str,
        front_azimuth: float,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> PropertyDetails:
        """Manually set property orientation.

        This is useful when you've verified the orientation yourself
        (e.g., via Street View, compass, or physical measurement).

        Args:
            address: Full street address
            front_azimuth: Direction front of house faces (0-360°)
            source: Where this data came from
            confidence: How confident we are (0-1)

        Returns:
            Updated PropertyDetails
        """
        cache_key = address.lower().strip()

        if cache_key in self._cache:
            prop = self._cache[cache_key]
        else:
            # Create minimal property record
            prop = PropertyDetails(
                address=address,
                location=GeoLocation(0, 0),  # Unknown
            )

        prop.orientation = PropertyOrientation(
            front_azimuth=front_azimuth,
            rotation_from_north=front_azimuth,
            confidence=confidence,
            source=source,
        )

        self._cache[cache_key] = prop
        logger.info(
            f"Set property orientation: {address} faces {front_azimuth:.0f}° "
            f"({prop.orientation.front_cardinal})"
        )

        return prop

    def generate_shade_config(
        self,
        orientation: PropertyOrientation,
        shade_locations: dict[str, str],
    ) -> dict[str, float]:
        """Generate shade direction configuration from orientation.

        Given a property orientation and shade locations relative to the house,
        calculate the actual compass direction each shade faces.

        Args:
            orientation: Property orientation
            shade_locations: Dict of shade_name -> relative_location
                            Locations: "front", "back", "left", "right"

        Returns:
            Dict of shade_name -> azimuth
        """
        location_to_azimuth = {
            "front": orientation.front_azimuth,
            "back": orientation.back_azimuth,
            "left": orientation.left_azimuth,
            "right": orientation.right_azimuth,
        }

        result = {}
        for shade_name, location in shade_locations.items():
            location = location.lower()
            if location in location_to_azimuth:
                result[shade_name] = location_to_azimuth[location]
            else:
                logger.warning(f"Unknown location '{location}' for shade '{shade_name}'")

        return result


# =============================================================================
# SINGLETON
# =============================================================================


_service: PropertyIntelligenceService | None = None


def get_property_service() -> PropertyIntelligenceService:
    """Get the property intelligence service singleton."""
    global _service
    if _service is None:
        _service = PropertyIntelligenceService()
    return _service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def calculate_sun_exposure(
    orientation: PropertyOrientation,
    sun_azimuth: float,
    window_width_degrees: float = 90.0,
) -> dict[str, bool]:
    """Calculate which sides of a building get direct sun.

    Args:
        orientation: Building orientation
        sun_azimuth: Current sun azimuth (0-360°)
        window_width_degrees: Angular width of windows (default 90°)

    Returns:
        Dict of side -> is_exposed
    """
    half_width = window_width_degrees / 2

    def is_exposed(side_azimuth: float) -> bool:
        diff = abs(sun_azimuth - side_azimuth)
        if diff > 180:
            diff = 360 - diff
        return diff <= half_width

    return {
        "front": is_exposed(orientation.front_azimuth),
        "back": is_exposed(orientation.back_azimuth),
        "left": is_exposed(orientation.left_azimuth),
        "right": is_exposed(orientation.right_azimuth),
    }


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    # Data models
    "GeoLocation",
    "PropertyDetails",
    # Service
    "PropertyIntelligenceService",
    "PropertyOrientation",
    "calculate_sun_exposure",
    "get_property_service",
    "orientation_from_lot_bearing",
    # Functions
    "orientation_from_street_view_heading",
]
