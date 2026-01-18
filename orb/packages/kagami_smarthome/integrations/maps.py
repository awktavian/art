"""Maps & Location Service — Real Distance and ETA Calculation.

Uses Google Maps Distance Matrix API for:
- Accurate driving distance
- Real-time ETA with traffic
- Route duration estimates

Home Location: 7331 W Green Lake Dr N, Seattle, WA
Coordinates: 47.6762°N, 122.3405°W

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# Home coordinates — imported from central config for portability
# To change location, set KAGAMI_HOME_LAT/LON env vars or config/location.yaml
from kagami.core.config.location_config import get_home_location

_location = get_home_location()
HOME_LAT = _location.latitude
HOME_LON = _location.longitude
HOME_ADDRESS = _location.address or "7331 W Green Lake Dr N, Seattle, WA 98103"


@dataclass
class LocationInfo:
    """Information about a location relative to home."""

    # Input coordinates
    latitude: float
    longitude: float

    # Distance
    distance_miles: float
    distance_text: str  # "5.2 mi"

    # ETA
    duration_minutes: int
    duration_text: str  # "12 mins"
    duration_in_traffic_minutes: int | None = None
    duration_in_traffic_text: str | None = None

    # Status
    is_home: bool = False  # Within ~500 feet
    is_near: bool = False  # Within 2 miles
    is_arriving: bool = False  # Within 10 minutes

    # Raw API response
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_miles": self.distance_miles,
            "distance_text": self.distance_text,
            "duration_minutes": self.duration_minutes,
            "duration_text": self.duration_text,
            "duration_in_traffic_minutes": self.duration_in_traffic_minutes,
            "duration_in_traffic_text": self.duration_in_traffic_text,
            "is_home": self.is_home,
            "is_near": self.is_near,
            "is_arriving": self.is_arriving,
        }


class MapsService:
    """Google Maps Distance Matrix API service.

    Provides accurate driving distance and ETA with real-time traffic.

    Usage:
        service = MapsService()
        info = await service.get_distance_to_home(47.6097, -122.3331)
        print(f"ETA: {info.duration_text}")
    """

    # Cache duration (2 minutes - traffic changes)
    CACHE_TTL_SECONDS = 120

    # Home threshold (meters)
    HOME_RADIUS_METERS = 150  # ~500 feet
    NEAR_RADIUS_MILES = 2.0

    def __init__(self, api_key: str | None = None):
        """Initialize maps service.

        Args:
            api_key: Google Maps API key (or from Keychain/env)
        """
        self.api_key = api_key or self._get_api_key()
        self._client: httpx.AsyncClient | None = None

        # Cache: (lat, lon) -> (LocationInfo, timestamp)
        self._cache: dict[tuple[float, float], tuple[LocationInfo, float]] = {}

    @staticmethod
    def _get_api_key() -> str | None:
        """Get API key from Keychain first, then environment."""
        # Try Keychain first
        try:
            from kagami_smarthome.secrets import secrets

            key = secrets.get("google_maps_api_key")
            if key:
                return key
        except Exception:
            pass

        # Fallback to environment
        return os.getenv("GOOGLE_MAPS_API_KEY")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10)
        return self._client

    def _round_coords(self, lat: float, lon: float) -> tuple[float, float]:
        """Round coordinates for cache key (4 decimal places ≈ 11m precision)."""
        return (round(lat, 4), round(lon, 4))

    def _get_cached(self, lat: float, lon: float) -> LocationInfo | None:
        """Get cached result if valid."""
        key = self._round_coords(lat, lon)
        if key in self._cache:
            info, timestamp = self._cache[key]
            if time.time() - timestamp < self.CACHE_TTL_SECONDS:
                return info
        return None

    def _set_cached(self, lat: float, lon: float, info: LocationInfo) -> None:
        """Cache a result."""
        key = self._round_coords(lat, lon)
        self._cache[key] = (info, time.time())

    async def get_distance_to_home(
        self,
        latitude: float,
        longitude: float,
        with_traffic: bool = True,
    ) -> LocationInfo:
        """Get distance and ETA from a location to home.

        Args:
            latitude: Current latitude
            longitude: Current longitude
            with_traffic: Include real-time traffic (requires Premium)

        Returns:
            LocationInfo with distance and ETA
        """
        # Check cache
        cached = self._get_cached(latitude, longitude)
        if cached:
            return cached

        # Check if already home (save API call)
        if self._is_at_home(latitude, longitude):
            info = LocationInfo(
                latitude=latitude,
                longitude=longitude,
                distance_miles=0.0,
                distance_text="0 mi",
                duration_minutes=0,
                duration_text="0 mins",
                is_home=True,
                is_near=True,
                is_arriving=False,
            )
            self._set_cached(latitude, longitude, info)
            return info

        # No API key = fallback to haversine estimate
        if not self.api_key:
            return self._estimate_without_api(latitude, longitude)

        try:
            client = await self._get_client()

            # Build request
            origin = f"{latitude},{longitude}"
            destination = f"{HOME_LAT},{HOME_LON}"

            params = {
                "origins": origin,
                "destinations": destination,
                "mode": "driving",
                "units": "imperial",
                "key": self.api_key,
            }

            # Add departure_time for traffic (requires Premium plan)
            if with_traffic:
                params["departure_time"] = "now"

            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                logger.warning(f"Maps API error: {data.get('status')}")
                return self._estimate_without_api(latitude, longitude)

            # Parse response
            element = data["rows"][0]["elements"][0]

            if element.get("status") != "OK":
                logger.warning(f"Route not found: {element.get('status')}")
                return self._estimate_without_api(latitude, longitude)

            distance = element["distance"]
            duration = element["duration"]

            # Convert meters to miles
            distance_miles = distance["value"] / 1609.34
            duration_minutes = duration["value"] // 60

            # Traffic duration (if available)
            traffic_duration = element.get("duration_in_traffic")
            traffic_minutes = None
            traffic_text = None
            if traffic_duration:
                traffic_minutes = traffic_duration["value"] // 60
                traffic_text = traffic_duration["text"]

            info = LocationInfo(
                latitude=latitude,
                longitude=longitude,
                distance_miles=round(distance_miles, 1),
                distance_text=distance["text"],
                duration_minutes=duration_minutes,
                duration_text=duration["text"],
                duration_in_traffic_minutes=traffic_minutes,
                duration_in_traffic_text=traffic_text,
                is_home=distance_miles < 0.1,
                is_near=distance_miles < self.NEAR_RADIUS_MILES,
                is_arriving=(traffic_minutes or duration_minutes) <= 10,
                raw_response=data,
            )

            self._set_cached(latitude, longitude, info)
            logger.debug(f"Maps: {distance['text']} / {duration['text']} to home")

            return info

        except httpx.HTTPError as e:
            logger.warning(f"Maps API request failed: {e}")
            return self._estimate_without_api(latitude, longitude)
        except Exception as e:
            logger.warning(f"Maps API error: {e}")
            return self._estimate_without_api(latitude, longitude)

    def _is_at_home(self, lat: float, lon: float) -> bool:
        """Quick check if coordinates are at home."""
        import math

        # Haversine for small distance
        R = 6371000  # Earth radius in meters
        lat1, lat2 = math.radians(lat), math.radians(HOME_LAT)
        dlat = lat2 - lat1
        dlon = math.radians(lon - HOME_LON)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c

        return distance < self.HOME_RADIUS_METERS

    def _estimate_without_api(self, lat: float, lon: float) -> LocationInfo:
        """Estimate distance/ETA without API (fallback).

        Uses haversine distance and assumes 25 mph average for Seattle.
        """
        import math

        # Haversine distance
        R = 3959  # Earth radius in miles
        lat1, lat2 = math.radians(lat), math.radians(HOME_LAT)
        dlat = lat2 - lat1
        dlon = math.radians(lon - HOME_LON)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        distance_miles = R * c

        # Estimate driving time (25 mph average for Seattle, 1.3x for routing)
        duration_minutes = int(distance_miles / 25 * 60 * 1.3)

        return LocationInfo(
            latitude=lat,
            longitude=lon,
            distance_miles=round(distance_miles, 1),
            distance_text=f"{distance_miles:.1f} mi (est.)",
            duration_minutes=duration_minutes,
            duration_text=f"{duration_minutes} mins (est.)",
            is_home=distance_miles < 0.1,
            is_near=distance_miles < self.NEAR_RADIUS_MILES,
            is_arriving=duration_minutes <= 10,
        )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_maps_service: MapsService | None = None


def get_maps_service() -> MapsService:
    """Get global maps service instance."""
    global _maps_service
    if _maps_service is None:
        _maps_service = MapsService()
    return _maps_service


async def get_distance_to_home(lat: float, lon: float) -> LocationInfo:
    """Convenience function to get distance/ETA to home."""
    service = get_maps_service()
    return await service.get_distance_to_home(lat, lon)


__all__ = [
    "HOME_ADDRESS",
    "HOME_LAT",
    "HOME_LON",
    "LocationInfo",
    "MapsService",
    "get_distance_to_home",
    "get_maps_service",
]
