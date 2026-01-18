"""Property Intelligence API routes.

REST endpoints for property data. All responses are PropertyBlobs
with no exposed API keys - safe for frontend consumption.

Endpoints:
    POST /property/lookup - Get property data by address
    GET /property/orientation/{address} - Get building orientation
    GET /property/solar/{address} - Get solar potential
    DELETE /property/cache/{address} - Invalidate cached data
    GET /property/cache/stats - Get cache statistics

Example:
    POST /property/lookup
    {"address": "7331 W Green Lake Dr N, Seattle, WA"}

    Response: PropertyBlob JSON
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from kagami_api.property.models import PropertyBlob
from kagami_api.property.service import get_property_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/property", tags=["property"])


# Request/Response schemas
class LookupRequest(BaseModel):
    """Request to lookup property data.

    Attributes:
        address: Property address to look up.
        force_refresh: If True, bypass cache.
        include_3d_tiles: If True, include 3D Tiles session.
    """

    address: str = Field(..., description="Property address", min_length=5)
    force_refresh: bool = Field(False, description="Bypass cache")
    include_3d_tiles: bool = Field(True, description="Include 3D Tiles session")


class OrientationResponse(BaseModel):
    """Building orientation response.

    Attributes:
        address: Property address.
        orientation_degrees: Direction building faces (0=N, 90=E).
        cardinal: Cardinal direction (N, NE, E, etc).
    """

    address: str
    orientation_degrees: float | None = None
    cardinal: str | None = None


class SolarResponse(BaseModel):
    """Solar potential response.

    Attributes:
        address: Property address.
        max_sunshine_hours: Peak annual sun hours.
        max_panels: Maximum solar panels.
        yearly_kwh: Annual energy potential.
        roof_segments: Number of roof segments.
        primary_roof_azimuth: Main roof direction.
        imagery_date: When aerial was captured.
    """

    address: str
    max_sunshine_hours: float | None = None
    max_panels: int | None = None
    yearly_kwh: float | None = None
    roof_segments: int = 0
    primary_roof_azimuth: float | None = None
    imagery_date: str | None = None


class CacheStats(BaseModel):
    """Cache statistics response."""

    count: int
    total_size_bytes: int
    oldest: str | None = None
    newest: str | None = None
    cache_dir: str


# Routes


@router.post("/lookup", response_model=PropertyBlob)
async def lookup_property(request: LookupRequest) -> PropertyBlob:
    """Look up property data by address.

    Fetches data from Google Maps APIs, county records, and other sources.
    Results are cached for 1 week by default.

    Args:
        request: LookupRequest with address and options.

    Returns:
        PropertyBlob with all available data.

    Raises:
        HTTPException: 404 if address cannot be geocoded.
    """
    service = get_property_service()

    blob = await service.get_property(
        address=request.address,
        force_refresh=request.force_refresh,
        include_3d_tiles=request.include_3d_tiles,
    )

    if not blob:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find property: {request.address}",
        )

    return blob


@router.get("/orientation", response_model=OrientationResponse)
async def get_orientation(
    address: str = Query(..., description="Property address", min_length=5),
) -> OrientationResponse:
    """Get building orientation.

    Returns the direction the front of the building faces,
    derived from Street View camera heading.

    Args:
        address: Property address.

    Returns:
        OrientationResponse with degrees and cardinal direction.
    """
    service = get_property_service()
    degrees = await service.get_orientation(address)

    cardinal = None
    if degrees is not None:
        cardinals = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = int((degrees + 22.5) // 45) % 8
        cardinal = cardinals[index]

    return OrientationResponse(
        address=address,
        orientation_degrees=degrees,
        cardinal=cardinal,
    )


@router.get("/solar", response_model=SolarResponse)
async def get_solar(
    address: str = Query(..., description="Property address", min_length=5),
) -> SolarResponse:
    """Get solar potential for property.

    Uses Google Solar API to analyze roof geometry and sun exposure.

    Args:
        address: Property address.

    Returns:
        SolarResponse with solar potential metrics.

    Raises:
        HTTPException: 404 if solar data unavailable.
    """
    service = get_property_service()
    data = await service.get_solar_insights(address)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No solar data available for: {address}",
        )

    return SolarResponse(
        address=address,
        max_sunshine_hours=data.get("max_sunshine_hours"),
        max_panels=data.get("max_panels"),
        yearly_kwh=data.get("yearly_kwh"),
        roof_segments=data.get("roof_segments", 0),
        primary_roof_azimuth=data.get("primary_roof_azimuth"),
        imagery_date=data.get("imagery_date"),
    )


@router.delete("/cache")
async def invalidate_cache(
    address: str = Query(..., description="Property address", min_length=5),
) -> dict:
    """Invalidate cached property data.

    Forces fresh data to be fetched on next lookup.

    Args:
        address: Property address to invalidate.

    Returns:
        Confirmation message.
    """
    service = get_property_service()
    await service.invalidate(address)

    return {"status": "ok", "message": f"Cache invalidated for {address}"}


@router.get("/cache/stats", response_model=CacheStats)
async def get_cache_stats() -> CacheStats:
    """Get cache statistics.

    Returns:
        CacheStats with count, size, and age info.
    """
    service = get_property_service()
    stats = await service.cache.get_stats()

    return CacheStats(**stats)


@router.post("/cache/clear")
async def clear_cache() -> dict:
    """Clear all cached property data.

    Use with caution - forces all properties to be re-fetched.

    Returns:
        Count of cleared entries.
    """
    service = get_property_service()
    count = await service.cache.clear_all()

    return {"status": "ok", "cleared": count}
