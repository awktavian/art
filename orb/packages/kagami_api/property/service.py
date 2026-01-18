"""Property Intelligence Service.

Orchestrates property data aggregation from multiple sources:
- Google Maps Platform APIs
- County assessor records
- Public listing data

All data is cached as PropertyBlobs that can be served to frontends
without exposing any API keys.

Example:
    >>> service = get_property_service()
    >>> blob = await service.get_property("7331 W Green Lake Dr N, Seattle, WA")
    >>> print(blob.solar.roof_segments)  # Solar API data
    >>> print(blob.street_view.front.url)  # Pre-signed Street View URL
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from kagami_api.property.cache import PropertyCache, get_property_cache
from kagami_api.property.google_client import GoogleMapsClient, get_google_maps_client
from kagami_api.property.models import (
    CountyData,
    FloorplanData,
    PropertyBlob,
    PropertyPhotos,
    PropertyType,
)

logger = logging.getLogger(__name__)


class PropertyService:
    """Property intelligence aggregation service.

    Fetches and caches property data from multiple sources.
    All API calls are made server-side with keys secured in keychain.

    Attributes:
        google: Google Maps Platform client.
        cache: Property blob cache.
    """

    def __init__(
        self,
        google_client: GoogleMapsClient | None = None,
        cache: PropertyCache | None = None,
    ):
        """Initialize service with dependencies.

        Args:
            google_client: Google Maps client. Defaults to singleton.
            cache: Property cache. Defaults to singleton.
        """
        self.google = google_client or get_google_maps_client()
        self.cache = cache or get_property_cache()

    async def get_property(
        self,
        address: str,
        force_refresh: bool = False,
        include_3d_tiles: bool = True,
    ) -> PropertyBlob | None:
        """Get complete property intelligence blob.

        Fetches data from all sources and caches the result.
        Subsequent calls return cached data until TTL expires.

        Args:
            address: Property address string.
            force_refresh: If True, bypass cache and fetch fresh data.
            include_3d_tiles: If True, include 3D Tiles session.

        Returns:
            PropertyBlob with all available data, or None if geocoding fails.

        Example:
            >>> blob = await service.get_property("1600 Pennsylvania Ave NW, DC")
            >>> print(blob.location.lat)  # 38.8977
            >>> print(blob.solar.max_sunshine_hours)  # ~1800
        """
        # Check cache first
        if not force_refresh:
            cached = await self.cache.get(address)
            if cached:
                logger.info(f"Returning cached blob for {address}")
                return cached

        logger.info(f"Fetching property data for {address}")

        # Step 1: Geocode the address
        location = await self.google.geocode(address)
        if not location:
            logger.warning(f"Failed to geocode {address}")
            return None

        # Step 2: Fetch all data in parallel
        tasks = [
            self.google.get_viewport(address),
            self.google.get_solar_data(location.lat, location.lng),
            self.google.get_street_view_data(location.lat, location.lng),
        ]

        if location.place_id:
            tasks.append(self.google.get_place_photos(location.place_id))
        else:
            tasks.append(asyncio.sleep(0))  # Placeholder

        if include_3d_tiles:
            tasks.append(self.google.get_tileset_session())
        else:
            tasks.append(asyncio.sleep(0))  # Placeholder

        results = await asyncio.gather(*tasks, return_exceptions=True)

        viewport = results[0] if not isinstance(results[0], Exception) else None
        solar = results[1] if not isinstance(results[1], Exception) else None
        street_view = results[2] if not isinstance(results[2], Exception) else None
        photos_result = results[3] if not isinstance(results[3], Exception) else []
        tileset = results[4] if not isinstance(results[4], Exception) else None

        # Build photos object
        google_photos = photos_result if isinstance(photos_result, list) else []
        photos = PropertyPhotos(google_places=google_photos)

        # Try to get county data (async, non-blocking)
        county = await self._fetch_county_data(address, location.lat, location.lng)

        # Build floorplan from county data
        floorplan = FloorplanData()
        if county:
            floorplan = FloorplanData(
                available=bool(county.assessed_value),
                total_sqft=None,  # Not in basic county data
                lot_sqft=None,
                floors=None,
                bedrooms=None,
                bathrooms=None,
                year_built=county.year_built,
            )

        # Determine property type from solar data or default
        property_type = PropertyType.SINGLE_FAMILY
        if solar and solar.roof_segments:
            # Multiple roof segments often indicate larger building
            if len(solar.roof_segments) > 10:
                property_type = PropertyType.MULTI_FAMILY

        # Build the blob
        blob = PropertyBlob(
            address=address,
            location=location,
            viewport=viewport,
            property_type=property_type,
            solar=solar,
            street_view=street_view,
            photos=photos,
            floorplan=floorplan,
            county=county,
            tileset=tileset,
            cached_at=datetime.utcnow(),
            sources=self._get_sources(solar, street_view, county),
        )

        # Cache the result
        await self.cache.set(address, blob)

        return blob

    async def _fetch_county_data(self, address: str, lat: float, lng: float) -> CountyData | None:
        """Fetch county assessor data.

        Currently a stub - would integrate with county GIS APIs.

        Args:
            address: Property address.
            lat: Latitude.
            lng: Longitude.

        Returns:
            CountyData if available.
        """
        # TODO: Integrate with King County GIS API
        # https://gismaps.kingcounty.gov/parcelviewer2/
        #
        # For now, return None. Future implementation would:
        # 1. Query county parcel API by lat/lng
        # 2. Fetch assessment records
        # 3. Parse and return CountyData

        return None

    def _get_sources(
        self,
        solar: object | None,
        street_view: object | None,
        county: object | None,
    ) -> list[str]:
        """Build list of data sources used."""
        sources = ["Google Geocoding API"]

        if solar:
            sources.append("Google Solar API")

        if street_view and getattr(street_view, "available", False):
            sources.append("Google Street View API")

        if county:
            sources.append("County Assessor Records")

        return sources

    async def get_orientation(self, address: str) -> float | None:
        """Get building orientation in degrees.

        Uses cached property blob or fetches minimal data to
        determine which direction the front of the building faces.

        Args:
            address: Property address.

        Returns:
            Orientation in degrees (0=North, 90=East) or None.
        """
        # Try cached blob first
        blob = await self.cache.get(address)
        if blob:
            return blob.orientation_degrees

        # Fetch just what we need
        location = await self.google.geocode(address)
        if not location:
            return None

        street_view = await self.google.get_street_view_data(location.lat, location.lng)
        if street_view and street_view.front:
            # Building faces opposite of camera heading
            return (street_view.front.heading + 180) % 360

        return None

    async def get_solar_insights(self, address: str) -> dict | None:
        """Get solar potential summary.

        Args:
            address: Property address.

        Returns:
            Dict with solar potential metrics.
        """
        blob = await self.get_property(address, include_3d_tiles=False)
        if not blob or not blob.solar:
            return None

        solar = blob.solar
        return {
            "max_sunshine_hours": solar.max_sunshine_hours,
            "max_panels": solar.max_array_panels,
            "yearly_kwh": solar.yearly_energy_kwh,
            "roof_segments": len(solar.roof_segments),
            "primary_roof_azimuth": (
                solar.roof_segments[0].azimuth_degrees if solar.roof_segments else None
            ),
            "imagery_date": (solar.imagery_date.isoformat() if solar.imagery_date else None),
        }

    async def invalidate(self, address: str) -> None:
        """Invalidate cached property data.

        Args:
            address: Property address to invalidate.
        """
        await self.cache.invalidate(address)

    async def close(self) -> None:
        """Clean up resources."""
        await self.google.close()


# Singleton instance
_service: PropertyService | None = None


def get_property_service() -> PropertyService:
    """Get singleton PropertyService instance."""
    global _service
    if _service is None:
        _service = PropertyService()
    return _service
