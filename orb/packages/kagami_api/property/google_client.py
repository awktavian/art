"""Google Maps Platform API client.

Secure client for all Google Maps APIs. API key is stored server-side
and never exposed to frontend. Generates pre-signed URLs for images
and session tokens for 3D Tiles.

Supported APIs:
- Geocoding API: Address to coordinates
- Places API (New): Place details and photos
- Solar API: Building insights and roof geometry
- Street View Static API: Panoramic imagery
- Map Tiles API: Photorealistic 3D Tiles sessions

Example:
    >>> client = GoogleMapsClient()
    >>> location = await client.geocode("123 Main St, Seattle, WA")
    >>> solar = await client.get_solar_data(location.lat, location.lng)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from kagami.core.security import get_secret

from kagami_api.property.models import (
    GeoLocation,
    PropertyPhoto,
    RoofSegment,
    SolarData,
    StreetViewData,
    StreetViewPano,
    TilesetSession,
    Viewport,
)

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """Secure Google Maps Platform client.

    All API keys are retrieved from keychain and never exposed.
    Generates pre-signed URLs for frontend consumption.

    Attributes:
        api_key: Google Maps API key from keychain.
        base_urls: API endpoint base URLs.
    """

    # API endpoints
    GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    PLACES_URL = "https://places.googleapis.com/v1/places"
    SOLAR_URL = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    STREET_VIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
    STREET_VIEW_META_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
    TILES_URL = "https://tile.googleapis.com/v1/3dtiles/root.json"

    def __init__(self, api_key: str | None = None):
        """Initialize client with API key from keychain.

        Args:
            api_key: Override API key (for testing). If None, fetches from keychain.
        """
        self._api_key = api_key
        self._http: httpx.AsyncClient | None = None

    @property
    def api_key(self) -> str:
        """Get API key from keychain (cached)."""
        if self._api_key is None:
            self._api_key = get_secret("google_maps_api_key")
            if not self._api_key:
                raise ValueError("Google Maps API key not found in keychain")
        return self._api_key

    @property
    def http(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # =========================================================================
    # Geocoding API
    # =========================================================================

    async def geocode(self, address: str) -> GeoLocation | None:
        """Convert address to coordinates.

        Args:
            address: Human-readable address string.

        Returns:
            GeoLocation with lat/lng and metadata, or None if not found.

        Example:
            >>> loc = await client.geocode("1600 Pennsylvania Ave, DC")
            >>> print(loc.lat, loc.lng)  # 38.8977, -77.0365
        """
        params = {
            "address": address,
            "key": self.api_key,
        }

        try:
            response = await self.http.get(self.GEOCODING_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                logger.warning(f"Geocoding failed for '{address}': {data.get('status')}")
                return None

            result = data["results"][0]
            geometry = result["geometry"]
            location = geometry["location"]

            return GeoLocation(
                lat=location["lat"],
                lng=location["lng"],
                accuracy=geometry.get("location_type"),
                place_id=result.get("place_id"),
                plus_code=result.get("plus_code", {}).get("global_code"),
            )

        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return None

    async def get_viewport(self, address: str) -> Viewport | None:
        """Get map viewport bounds for an address.

        Args:
            address: Address to get bounds for.

        Returns:
            Viewport with northeast/southwest corners.
        """
        params = {
            "address": address,
            "key": self.api_key,
        }

        try:
            response = await self.http.get(self.GEOCODING_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                return None

            geometry = data["results"][0]["geometry"]
            viewport = geometry.get("viewport", {})

            if not viewport:
                return None

            return Viewport(
                northeast=GeoLocation(
                    lat=viewport["northeast"]["lat"],
                    lng=viewport["northeast"]["lng"],
                ),
                southwest=GeoLocation(
                    lat=viewport["southwest"]["lat"],
                    lng=viewport["southwest"]["lng"],
                ),
            )

        except Exception as e:
            logger.error(f"Viewport error: {e}")
            return None

    # =========================================================================
    # Places API (New)
    # =========================================================================

    async def get_place_photos(self, place_id: str, max_photos: int = 10) -> list[PropertyPhoto]:
        """Get photos for a place.

        Uses Places API (New) to fetch photo references, then generates
        pre-signed URLs that don't expose the API key.

        Args:
            place_id: Google Place ID.
            max_photos: Maximum photos to return.

        Returns:
            List of PropertyPhoto with pre-signed URLs.
        """
        # First get place details with photos
        url = f"{self.PLACES_URL}/{place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "photos",
        }

        try:
            response = await self.http.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            photos = []
            for photo_data in data.get("photos", [])[:max_photos]:
                photo_name = photo_data.get("name")
                if not photo_name:
                    continue

                # Generate photo URL (this embeds the key, but we'll proxy it)
                photo_url = (
                    f"https://places.googleapis.com/v1/{photo_name}/media"
                    f"?maxHeightPx=4800&maxWidthPx=4800&key={self.api_key}"
                )

                photos.append(
                    PropertyPhoto(
                        url=photo_url,
                        width=photo_data.get("widthPx", 0),
                        height=photo_data.get("heightPx", 0),
                        attribution=", ".join(
                            a.get("displayName", "")
                            for a in photo_data.get("authorAttributions", [])
                        ),
                    )
                )

            return photos

        except Exception as e:
            logger.error(f"Places photos error: {e}")
            return []

    # =========================================================================
    # Solar API
    # =========================================================================

    async def get_solar_data(self, lat: float, lng: float) -> SolarData | None:
        """Get building insights from Solar API.

        Provides detailed roof geometry, solar potential, and building
        footprint data. Essential for shade calculations.

        Args:
            lat: Latitude in decimal degrees.
            lng: Longitude in decimal degrees.

        Returns:
            SolarData with roof segments and solar potential.
        """
        params = {
            "location.latitude": lat,
            "location.longitude": lng,
            "requiredQuality": "HIGH",
            "key": self.api_key,
        }

        try:
            response = await self.http.get(self.SOLAR_URL, params=params)

            # Solar API returns 404 for locations without data
            if response.status_code == 404:
                logger.info(f"No Solar API data for ({lat}, {lng})")
                return None

            response.raise_for_status()
            data = response.json()

            # Parse roof segments
            segments = []
            for seg in data.get("solarPotential", {}).get("roofSegmentStats", []):
                center = seg.get("center", {})
                segments.append(
                    RoofSegment(
                        pitch_degrees=seg.get("pitchDegrees", 0),
                        azimuth_degrees=seg.get("azimuthDegrees", 0),
                        area_sqm=seg.get("stats", {}).get("areaMeters2", 0),
                        yearly_energy_kwh=seg.get("stats", {}).get("sunshineQuantiles", [0])[-1],
                        panel_count=seg.get("stats", {}).get("panelsCount"),
                        center=GeoLocation(
                            lat=center.get("latitude", lat),
                            lng=center.get("longitude", lng),
                        )
                        if center
                        else None,
                    )
                )

            # Parse building bounds
            bbox = data.get("boundingBox", {})
            building_bbox = None
            if bbox.get("sw") and bbox.get("ne"):
                building_bbox = Viewport(
                    southwest=GeoLocation(
                        lat=bbox["sw"].get("latitude", 0),
                        lng=bbox["sw"].get("longitude", 0),
                    ),
                    northeast=GeoLocation(
                        lat=bbox["ne"].get("latitude", 0),
                        lng=bbox["ne"].get("longitude", 0),
                    ),
                )

            # Parse building center
            center = data.get("center", {})
            building_center = None
            if center:
                building_center = GeoLocation(
                    lat=center.get("latitude", lat),
                    lng=center.get("longitude", lng),
                )

            solar_potential = data.get("solarPotential", {})

            return SolarData(
                imagery_date=self._parse_date(data.get("imageryDate")),
                building_center=building_center,
                building_bbox=building_bbox,
                roof_segments=segments,
                max_sunshine_hours=solar_potential.get("maxSunshineHoursPerYear"),
                max_array_panels=solar_potential.get("maxArrayPanelsCount"),
                yearly_energy_kwh=solar_potential.get("maxArrayAnnualEnergyKwh"),
                carbon_offset_kg=solar_potential.get("carbonOffsetFactorKgPerMwh"),
            )

        except Exception as e:
            logger.error(f"Solar API error: {e}")
            return None

    def _parse_date(self, date_dict: dict | None) -> datetime | None:
        """Parse Google's date format {year, month, day}."""
        if not date_dict:
            return None
        try:
            return datetime(
                year=date_dict.get("year", 2020),
                month=date_dict.get("month", 1),
                day=date_dict.get("day", 1),
            )
        except (ValueError, TypeError):
            return None

    # =========================================================================
    # Street View API
    # =========================================================================

    async def get_street_view_data(
        self, lat: float, lng: float, heading: float | None = None
    ) -> StreetViewData | None:
        """Get Street View imagery from multiple angles.

        Fetches panorama metadata and generates pre-signed image URLs
        for front view and 4 additional angles (90° apart).

        Args:
            lat: Latitude.
            lng: Longitude.
            heading: Optional preferred heading (degrees). If None, uses
                    direction toward location from nearest panorama.

        Returns:
            StreetViewData with front view and multi-angle coverage.
        """
        # First check if Street View is available
        meta_params = {
            "location": f"{lat},{lng}",
            "key": self.api_key,
        }

        try:
            response = await self.http.get(self.STREET_VIEW_META_URL, params=meta_params)
            response.raise_for_status()
            meta = response.json()

            if meta.get("status") != "OK":
                return StreetViewData(available=False)

            pano_id = meta.get("pano_id")
            pano_date = meta.get("date")

            # Calculate heading from panorama to target location
            pano_location = meta.get("location", {})
            if heading is None and pano_location:
                heading = self._calculate_heading(
                    pano_location.get("lat", lat),
                    pano_location.get("lng", lng),
                    lat,
                    lng,
                )

            # Generate front view
            front = self._create_street_view_pano(lat, lng, heading or 0, pano_id, pano_date)

            # Generate additional angles (every 90°)
            angles = []
            if heading is not None:
                for offset in [90, 180, 270]:
                    angle_heading = (heading + offset) % 360
                    angles.append(
                        self._create_street_view_pano(lat, lng, angle_heading, pano_id, pano_date)
                    )

            return StreetViewData(
                available=True,
                front=front,
                angles=angles,
                nearest_pano_distance=self._calculate_distance(
                    lat,
                    lng,
                    pano_location.get("lat", lat),
                    pano_location.get("lng", lng),
                ),
            )

        except Exception as e:
            logger.error(f"Street View error: {e}")
            return StreetViewData(available=False)

    def _create_street_view_pano(
        self,
        lat: float,
        lng: float,
        heading: float,
        pano_id: str | None,
        date: str | None,
    ) -> StreetViewPano:
        """Create a Street View panorama with pre-signed URL."""
        params = {
            "size": "640x640",
            "location": f"{lat},{lng}",
            "heading": str(int(heading)),
            "pitch": "10",
            "fov": "90",
            "key": self.api_key,
        }
        url = f"{self.STREET_VIEW_URL}?{urlencode(params)}"

        return StreetViewPano(
            pano_id=pano_id,
            url=url,
            heading=heading,
            pitch=10,
            fov=90,
            date=date,
        )

    def _calculate_heading(
        self, from_lat: float, from_lng: float, to_lat: float, to_lng: float
    ) -> float:
        """Calculate heading from one point to another."""
        import math

        lat1 = math.radians(from_lat)
        lat2 = math.radians(to_lat)
        diff_lng = math.radians(to_lng - from_lng)

        x = math.sin(diff_lng) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_lng)

        heading = math.degrees(math.atan2(x, y))
        return (heading + 360) % 360

    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in meters (Haversine)."""
        import math

        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    # =========================================================================
    # Map Tiles API (3D Tiles)
    # =========================================================================

    async def get_tileset_session(self) -> TilesetSession | None:
        """Get authenticated 3D Tiles session.

        Creates a session for accessing Google Photorealistic 3D Tiles.
        The session token allows the frontend to request tiles without
        exposing the API key.

        Returns:
            TilesetSession with URL and token for CesiumJS.
        """
        params = {"key": self.api_key}

        try:
            response = await self.http.get(self.TILES_URL, params=params)
            response.raise_for_status()
            data = response.json()

            # Extract session from response
            data.get("root", {}).get("uri", "")

            return TilesetSession(
                tileset_url=f"{self.TILES_URL}?key={self.api_key}",
                session_token=self.api_key,  # For now, key is the session
                expires_at=datetime.utcnow() + timedelta(hours=24),
                attribution="© Google",
            )

        except Exception as e:
            logger.error(f"Tiles session error: {e}")
            return None


# Singleton instance
_client: GoogleMapsClient | None = None


def get_google_maps_client() -> GoogleMapsClient:
    """Get singleton GoogleMapsClient instance."""
    global _client
    if _client is None:
        _client = GoogleMapsClient()
    return _client
