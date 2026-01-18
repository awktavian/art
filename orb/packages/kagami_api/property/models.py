"""Property Intelligence data models.

Pydantic schemas for property data from multiple sources.
These models define the PropertyBlob that gets cached and
served to frontends without exposing API keys.

Example:
    >>> blob = PropertyBlob(
    ...     address="123 Main St",
    ...     location=GeoLocation(lat=47.6, lng=-122.3),
    ...     ...
    ... )
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PropertyType(str, Enum):
    """Property classification types."""

    SINGLE_FAMILY = "single_family_residential"
    MULTI_FAMILY = "multi_family_residential"
    CONDO = "condominium"
    TOWNHOUSE = "townhouse"
    COMMERCIAL = "commercial"
    LAND = "land"
    OTHER = "other"


class GeoLocation(BaseModel):
    """Geographic coordinates with metadata.

    Attributes:
        lat: Latitude in decimal degrees.
        lng: Longitude in decimal degrees.
        altitude: Elevation above sea level in meters.
        accuracy: Geocoding accuracy level.
        place_id: Google Place ID for this location.
        plus_code: Open Location Code (Plus Code).
    """

    lat: float = Field(..., description="Latitude in decimal degrees")
    lng: float = Field(..., description="Longitude in decimal degrees")
    altitude: float | None = Field(None, description="Elevation in meters")
    accuracy: str | None = Field(None, description="Geocoding accuracy")
    place_id: str | None = Field(None, description="Google Place ID")
    plus_code: str | None = Field(None, description="Plus Code")


class Viewport(BaseModel):
    """Bounding box for map viewport.

    Attributes:
        northeast: Northeast corner coordinates.
        southwest: Southwest corner coordinates.
    """

    northeast: GeoLocation
    southwest: GeoLocation


class RoofSegment(BaseModel):
    """Individual roof segment from Solar API.

    Contains geometry and solar potential for one roof facet.

    Attributes:
        pitch_degrees: Roof pitch angle in degrees.
        azimuth_degrees: Direction roof faces (0=North, 90=East).
        area_sqm: Surface area in square meters.
        yearly_energy_kwh: Estimated annual solar energy potential.
        panel_count: Maximum solar panels that fit.
        center: Center point of segment.
    """

    pitch_degrees: float = Field(..., description="Roof pitch in degrees")
    azimuth_degrees: float = Field(..., description="Azimuth (0=N, 90=E)")
    area_sqm: float = Field(..., description="Area in square meters")
    yearly_energy_kwh: float | None = Field(None, description="Annual kWh potential")
    panel_count: int | None = Field(None, description="Max panel count")
    center: GeoLocation | None = Field(None, description="Segment centroid")


class SolarData(BaseModel):
    """Building insights from Google Solar API.

    Provides roof geometry, solar potential, and imagery metadata.
    Critical for shade calculations and energy modeling.

    Attributes:
        imagery_date: When aerial imagery was captured.
        building_center: Building centroid.
        building_bbox: Building bounding box.
        roof_segments: Individual roof facets.
        max_sunshine_hours: Peak annual sun hours.
        max_array_panels: Total panels possible.
        yearly_energy_kwh: Total annual potential.
        carbon_offset_kg: Annual CO2 offset.
    """

    imagery_date: datetime | None = Field(None, description="Imagery capture date")
    building_center: GeoLocation | None = Field(None, description="Building center")
    building_bbox: Viewport | None = Field(None, description="Building bounds")
    roof_segments: list[RoofSegment] = Field(default_factory=list)
    max_sunshine_hours: float | None = Field(None, description="Peak sun hours/year")
    max_array_panels: int | None = Field(None, description="Max panels")
    yearly_energy_kwh: float | None = Field(None, description="Total annual kWh")
    carbon_offset_kg: float | None = Field(None, description="Annual CO2 offset kg")


class StreetViewPano(BaseModel):
    """Single Street View panorama.

    Attributes:
        pano_id: Unique panorama identifier.
        url: Pre-signed URL for static image.
        heading: Camera heading in degrees.
        pitch: Camera pitch in degrees.
        fov: Field of view in degrees.
        date: When panorama was captured.
    """

    pano_id: str | None = Field(None, description="Panorama ID")
    url: str = Field(..., description="Pre-signed image URL")
    heading: float = Field(..., description="Camera heading degrees")
    pitch: float = Field(0, description="Camera pitch degrees")
    fov: float = Field(90, description="Field of view degrees")
    date: str | None = Field(None, description="Capture date")


class StreetViewData(BaseModel):
    """Street View imagery from multiple angles.

    Attributes:
        available: Whether Street View coverage exists.
        front: View from street (property-facing).
        angles: Additional views at 90° intervals.
        nearest_pano_distance: Distance to nearest panorama in meters.
    """

    available: bool = Field(True, description="Coverage exists")
    front: StreetViewPano | None = Field(None, description="Front view")
    angles: list[StreetViewPano] = Field(default_factory=list, description="Multi-angle")
    nearest_pano_distance: float | None = Field(None, description="Distance to pano")


class PropertyPhoto(BaseModel):
    """Single property photo from Places API.

    Attributes:
        url: Pre-signed URL (no API key exposed).
        width: Image width in pixels.
        height: Image height in pixels.
        attribution: Required attribution text.
    """

    url: str = Field(..., description="Pre-signed photo URL")
    width: int = Field(..., description="Width in pixels")
    height: int = Field(..., description="Height in pixels")
    attribution: str | None = Field(None, description="Attribution text")


class PropertyPhotos(BaseModel):
    """Collection of property photos.

    Attributes:
        google_places: Photos from Places API.
        zillow: Photos scraped from Zillow listing.
        satellite: Aerial/satellite imagery URLs.
    """

    google_places: list[PropertyPhoto] = Field(default_factory=list)
    zillow: list[str] = Field(default_factory=list, description="Zillow photo URLs")
    satellite: list[str] = Field(default_factory=list, description="Satellite URLs")


class FloorplanData(BaseModel):
    """Floor plan information.

    Attributes:
        available: Whether floor plan data exists.
        total_sqft: Total living area.
        lot_sqft: Lot size.
        floors: Number of stories.
        bedrooms: Bedroom count.
        bathrooms: Bathroom count.
        rooms: Individual room list with sizes.
        image_url: Floor plan image if available.
    """

    available: bool = Field(False, description="Floor plan available")
    total_sqft: int | None = Field(None, description="Living area sq ft")
    lot_sqft: int | None = Field(None, description="Lot size sq ft")
    floors: int | None = Field(None, description="Number of floors")
    bedrooms: int | None = Field(None, description="Bedroom count")
    bathrooms: float | None = Field(None, description="Bathroom count")
    rooms: list[dict] = Field(default_factory=list, description="Room details")
    image_url: str | None = Field(None, description="Floor plan image")


class CountyData(BaseModel):
    """County assessor records.

    Attributes:
        parcel_id: County parcel number.
        assessed_value: Tax assessed value.
        land_value: Land-only value.
        improvement_value: Building value.
        year_built: Construction year.
        effective_year: Effective build year.
        zoning: Zoning classification.
        legal_description: Legal property description.
        owner_name: Current owner (if public).
        last_sale_date: Most recent sale date.
        last_sale_price: Most recent sale price.
    """

    parcel_id: str | None = Field(None, description="Parcel number")
    assessed_value: int | None = Field(None, description="Assessed value")
    land_value: int | None = Field(None, description="Land value")
    improvement_value: int | None = Field(None, description="Building value")
    year_built: int | None = Field(None, description="Year built")
    effective_year: int | None = Field(None, description="Effective year")
    zoning: str | None = Field(None, description="Zoning code")
    legal_description: str | None = Field(None, description="Legal description")
    owner_name: str | None = Field(None, description="Owner name")
    last_sale_date: str | None = Field(None, description="Last sale date")
    last_sale_price: int | None = Field(None, description="Last sale price")


class TilesetSession(BaseModel):
    """3D Tiles session for CesiumJS.

    Provides authenticated access to Google Photorealistic 3D Tiles
    without exposing API keys to the frontend.

    Attributes:
        tileset_url: Root tileset.json URL with session.
        session_token: Session token for tile requests.
        expires_at: Session expiration time.
        attribution: Required attribution HTML.
    """

    tileset_url: str = Field(..., description="Tileset URL with session")
    session_token: str = Field(..., description="Session token")
    expires_at: datetime = Field(..., description="Expiration time")
    attribution: str = Field(..., description="Attribution HTML")


class PropertyBlob(BaseModel):
    """Complete property intelligence blob.

    Aggregates all property data from multiple sources into a single
    cacheable blob. Frontend receives this without any API keys.

    Attributes:
        address: Formatted address string.
        location: Geographic coordinates.
        viewport: Map viewport bounds.
        property_type: Classification.
        solar: Solar API building insights.
        street_view: Street View imagery.
        photos: Property photos.
        floorplan: Floor plan data.
        county: County assessor records.
        tileset: 3D Tiles session (if available).
        cached_at: When blob was created.
        cache_ttl_hours: Cache validity period.
        sources: Data source attributions.
    """

    # Identity
    address: str = Field(..., description="Formatted address")
    location: GeoLocation = Field(..., description="Coordinates")
    viewport: Viewport | None = Field(None, description="Map bounds")
    property_type: PropertyType = Field(PropertyType.OTHER, description="Type")

    # Data from APIs
    solar: SolarData | None = Field(None, description="Solar API data")
    street_view: StreetViewData | None = Field(None, description="Street View")
    photos: PropertyPhotos = Field(default_factory=PropertyPhotos)
    floorplan: FloorplanData = Field(default_factory=FloorplanData)
    county: CountyData | None = Field(None, description="County records")
    tileset: TilesetSession | None = Field(None, description="3D Tiles session")

    # Metadata
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    cache_ttl_hours: int = Field(168, description="Cache TTL (default 1 week)")
    sources: list[str] = Field(default_factory=list, description="Data sources")

    @property
    def is_expired(self) -> bool:
        """Check if cache has expired."""
        from datetime import timedelta

        age = datetime.utcnow() - self.cached_at
        return age > timedelta(hours=self.cache_ttl_hours)

    @property
    def orientation_degrees(self) -> float | None:
        """Estimate building orientation from Street View heading.

        Returns the direction the front of the building faces,
        derived from the Street View camera heading.
        """
        if self.street_view and self.street_view.front:
            # Street View heading points AT the building
            # So building faces 180° opposite
            heading = self.street_view.front.heading
            return (heading + 180) % 360
        return None
