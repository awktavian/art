"""Property Intelligence Service.

Provides comprehensive property data aggregation from multiple sources:
- Google Maps Platform (Geocoding, Places, Solar, Street View, 3D Tiles)
- County assessor records
- Public listing data

All API keys are secured server-side. Frontend receives pre-signed URLs
and cached property blobs with no exposed credentials.

Example:
    >>> from kagami_api.property import get_property_service
    >>> service = get_property_service()
    >>> blob = await service.get_property("7331 W Green Lake Dr N, Seattle, WA")
"""

from kagami_api.property.models import (
    CountyData,
    FloorplanData,
    GeoLocation,
    PropertyBlob,
    PropertyPhotos,
    RoofSegment,
    SolarData,
    StreetViewData,
)
from kagami_api.property.router import router as property_router
from kagami_api.property.service import PropertyService, get_property_service

__all__ = [
    "CountyData",
    "FloorplanData",
    "GeoLocation",
    "PropertyBlob",
    "PropertyPhotos",
    "PropertyService",
    "RoofSegment",
    "SolarData",
    "StreetViewData",
    "get_property_service",
    "property_router",
]
