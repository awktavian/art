"""Weather Integration — Live Weather Data.

PORTABLE: Uses central location config for any deployment location.

Provides real-time weather data from OpenWeatherMap API for:
- Current temperature and conditions
- Hourly forecast (48 hours)
- Cloud coverage for shade optimization
- Weather-based scene adaptations

Configuration:
- Set OPENWEATHERMAP_API_KEY in environment or Keychain
- Location auto-configured from kagami.core.config.location_config

Created: December 29, 2025
Updated: January 8, 2026 — Portable location support
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WeatherCondition(str, Enum):
    """Weather condition categories."""

    CLEAR = "clear"
    CLOUDS = "clouds"
    RAIN = "rain"
    DRIZZLE = "drizzle"
    SNOW = "snow"
    THUNDERSTORM = "thunderstorm"
    MIST = "mist"
    FOG = "fog"
    UNKNOWN = "unknown"

    @classmethod
    def from_openweathermap(cls, main: str) -> WeatherCondition:
        """Convert OpenWeatherMap main condition to enum."""
        mapping = {
            "clear": cls.CLEAR,
            "clouds": cls.CLOUDS,
            "rain": cls.RAIN,
            "drizzle": cls.DRIZZLE,
            "snow": cls.SNOW,
            "thunderstorm": cls.THUNDERSTORM,
            "mist": cls.MIST,
            "fog": cls.FOG,
            "haze": cls.MIST,
            "smoke": cls.MIST,
        }
        return mapping.get(main.lower(), cls.UNKNOWN)


@dataclass
class WeatherData:
    """Current weather data."""

    # Temperature
    temp_f: float  # Current temperature in Fahrenheit
    feels_like_f: float  # Feels like temperature
    humidity: int  # Humidity percentage

    # Conditions
    condition: WeatherCondition  # Main condition
    description: str  # Detailed description
    icon: str  # OpenWeatherMap icon code

    # Sun times (Unix timestamps)
    sunrise: int  # Sunrise timestamp
    sunset: int  # Sunset timestamp

    # Wind
    wind_speed_mph: float  # Wind speed in mph
    wind_direction: int  # Wind direction in degrees

    # Visibility
    visibility_miles: float  # Visibility in miles

    # Clouds
    cloud_coverage: int  # Cloud coverage percentage

    # Metadata
    timestamp: int  # Data timestamp
    location: str  # Location name

    @property
    def sunrise_time(self) -> datetime:
        """Get sunrise as datetime."""
        return datetime.fromtimestamp(self.sunrise, tz=UTC).astimezone()

    @property
    def sunset_time(self) -> datetime:
        """Get sunset as datetime."""
        return datetime.fromtimestamp(self.sunset, tz=UTC).astimezone()

    @property
    def day_length_hours(self) -> float:
        """Get day length in hours."""
        return (self.sunset - self.sunrise) / 3600

    @property
    def day_length_formatted(self) -> str:
        """Get day length as 'Xh Ym' string."""
        total_minutes = int((self.sunset - self.sunrise) / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}h {minutes}m"

    @property
    def is_daytime(self) -> bool:
        """Check if currently daytime."""
        now = int(time.time())
        return self.sunrise <= now <= self.sunset

    @property
    def emoji_icon(self) -> str:
        """Get emoji icon for condition."""
        # Map OpenWeatherMap icon codes to emoji
        icon_map = {
            "01d": "☀️",  # Clear day
            "01n": "🌙",  # Clear night
            "02d": "⛅",  # Few clouds day
            "02n": "☁️",  # Few clouds night
            "03d": "☁️",  # Scattered clouds
            "03n": "☁️",
            "04d": "☁️",  # Broken clouds
            "04n": "☁️",
            "09d": "🌧️",  # Shower rain
            "09n": "🌧️",
            "10d": "🌦️",  # Rain day
            "10n": "🌧️",  # Rain night
            "11d": "⛈️",  # Thunderstorm
            "11n": "⛈️",
            "13d": "🌨️",  # Snow
            "13n": "🌨️",
            "50d": "🌫️",  # Mist
            "50n": "🌫️",
        }
        return icon_map.get(self.icon, "🌡️")

    def get_scene_adaptation(self) -> dict[str, Any]:
        """Get scene adaptations based on weather.

        Returns adjustments to apply to scenes:
        - brightness_modifier: Added to base brightness (-20 to +20)
        - color_temp_modifier: Added to base color temp in Kelvin
        - shade_modifier: Added to base shade position
        """
        adaptations: dict[str, Any] = {
            "brightness_modifier": 0,
            "color_temp_modifier": 0,
            "shade_modifier": 0,
            "reason": [],
        }

        # Cloudy/dark conditions: boost brightness
        if self.condition in (WeatherCondition.CLOUDS, WeatherCondition.FOG, WeatherCondition.MIST):
            if self.cloud_coverage > 80:
                adaptations["brightness_modifier"] = 15
                adaptations["reason"].append("Heavy cloud cover (+15% brightness)")
            elif self.cloud_coverage > 50:
                adaptations["brightness_modifier"] = 10
                adaptations["reason"].append("Cloudy (+10% brightness)")

        # Rainy/stormy: warmer colors, more light
        if self.condition in (
            WeatherCondition.RAIN,
            WeatherCondition.DRIZZLE,
            WeatherCondition.THUNDERSTORM,
        ):
            adaptations["brightness_modifier"] = 10
            adaptations["color_temp_modifier"] = -300  # Warmer
            adaptations["reason"].append("Rainy day (warmer light)")

        # Snowy: cooler colors to match
        if self.condition == WeatherCondition.SNOW:
            adaptations["color_temp_modifier"] = 200  # Cooler
            adaptations["reason"].append("Snowy (cooler light)")

        # Very sunny: close shades more
        if self.condition == WeatherCondition.CLEAR and self.is_daytime:
            if self.temp_f > 75:  # Hot sunny day
                adaptations["shade_modifier"] = 20
                adaptations["reason"].append("Sunny and warm (glare reduction)")

        return adaptations

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "temp_f": self.temp_f,
            "feels_like_f": self.feels_like_f,
            "humidity": self.humidity,
            "condition": self.condition.value,
            "description": self.description,
            "icon": self.icon,
            "emoji": self.emoji_icon,
            "sunrise": self.sunrise,
            "sunset": self.sunset,
            "sunrise_formatted": self.sunrise_time.strftime("%I:%M %p"),
            "sunset_formatted": self.sunset_time.strftime("%I:%M %p"),
            "day_length": self.day_length_formatted,
            "day_length_hours": round(self.day_length_hours, 2),
            "is_daytime": self.is_daytime,
            "wind_speed_mph": self.wind_speed_mph,
            "wind_direction": self.wind_direction,
            "visibility_miles": self.visibility_miles,
            "cloud_coverage": self.cloud_coverage,
            "timestamp": self.timestamp,
            "location": self.location,
            "adaptations": self.get_scene_adaptation(),
        }


@dataclass
class HourlyForecast:
    """Single hour forecast data."""

    timestamp: int
    temp_f: float
    condition: WeatherCondition
    description: str
    cloud_coverage: int
    precipitation_probability: int  # 0-100%
    wind_speed_mph: float

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, tz=UTC)

    @property
    def is_cloudy(self) -> bool:
        """Cloud coverage > 50%."""
        return self.cloud_coverage > 50

    @property
    def is_rainy(self) -> bool:
        """Rain or high precipitation probability."""
        return (
            self.condition
            in (
                WeatherCondition.RAIN,
                WeatherCondition.DRIZZLE,
                WeatherCondition.THUNDERSTORM,
            )
            or self.precipitation_probability > 60
        )


@dataclass
class WeatherForecast:
    """48-hour forecast data."""

    hourly: list[HourlyForecast] = field(default_factory=list)
    timestamp: int = 0

    def get_next_hours(self, hours: int = 6) -> list[HourlyForecast]:
        """Get forecast for next N hours."""
        return self.hourly[:hours]

    def get_cloud_trend(self, hours: int = 6) -> str:
        """Get cloud coverage trend."""
        if not self.hourly:
            return "unknown"

        forecasts = self.get_next_hours(hours)
        avg_clouds = sum(f.cloud_coverage for f in forecasts) / len(forecasts)

        if avg_clouds < 20:
            return "clear"
        elif avg_clouds < 50:
            return "partly_cloudy"
        elif avg_clouds < 80:
            return "mostly_cloudy"
        else:
            return "overcast"

    def should_close_shades(self) -> bool:
        """Recommend closing shades based on forecast.

        Close shades if:
        - Currently sunny (low clouds)
        - Will stay sunny for next few hours
        - No rain expected
        """
        if not self.hourly:
            return True  # Default to sun protection

        next_hours = self.get_next_hours(4)
        avg_clouds = sum(f.cloud_coverage for f in next_hours) / len(next_hours)
        any_rain = any(f.is_rainy for f in next_hours)

        # If cloudy or rainy, no need to close shades
        if avg_clouds > 60 or any_rain:
            return False

        return True  # Sunny — recommend closing


class WeatherService:
    """Weather service using OpenWeatherMap API.

    PORTABLE: Uses central location config by default.

    Free tier: 1000 calls/day, 60 calls/minute
    One Call API 3.0: Required for forecast (separate subscription)

    Usage:
        service = WeatherService()
        weather = await service.get_current()
        print(f"Temperature: {weather.temp_f}°F")

        # With forecast
        forecast = await service.get_forecast()
        if forecast.should_close_shades():
            print("Sunny — close shades")
    """

    # Cache duration (5 minutes for current, 30 minutes for forecast)
    CACHE_TTL_SECONDS = 300
    FORECAST_CACHE_TTL_SECONDS = 1800

    def __init__(
        self,
        api_key: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ):
        """Initialize weather service.

        Args:
            api_key: OpenWeatherMap API key (or from Keychain/env)
            lat: Latitude (default: from central location config)
            lon: Longitude (default: from central location config)
        """
        self.api_key = api_key or self._get_api_key()

        # Use central location config if not specified
        if lat is None or lon is None:
            from kagami.core.config.location_config import get_home_location

            location = get_home_location()
            self.lat = lat if lat is not None else location.latitude
            self.lon = lon if lon is not None else location.longitude
            logger.debug(f"Weather using location: {location.name} ({self.lat}, {self.lon})")
        else:
            self.lat = lat
            self.lon = lon

        self._cache: WeatherData | None = None
        self._cache_time: float = 0
        self._forecast_cache: WeatherForecast | None = None
        self._forecast_cache_time: float = 0
        self._client: httpx.AsyncClient | None = None

    @staticmethod
    def _get_api_key() -> str | None:
        """Get API key from Keychain first, then environment."""
        # Try Keychain first (secure storage)
        try:
            from kagami_smarthome.secrets import secrets

            key = secrets.get("openweathermap_api_key")
            if key:
                return key
        except Exception:
            pass

        # Fallback to environment variable
        return os.getenv("OPENWEATHERMAP_API_KEY")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10)
        return self._client

    async def get_current(self, force_refresh: bool = False) -> WeatherData | None:
        """Get current weather data.

        Args:
            force_refresh: Bypass cache

        Returns:
            WeatherData or None if unavailable
        """
        # Check cache
        if not force_refresh and self._cache:
            if time.time() - self._cache_time < self.CACHE_TTL_SECONDS:
                return self._cache

        # No API key = return None
        if not self.api_key:
            logger.warning("No OpenWeatherMap API key configured")
            return self._get_fallback_data()

        try:
            client = await self._get_client()

            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": self.lat,
                "lon": self.lon,
                "appid": self.api_key,
                "units": "imperial",  # Fahrenheit
            }

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            weather = self._parse_response(data)

            # Cache result
            self._cache = weather
            self._cache_time = time.time()

            logger.debug(f"Weather updated: {weather.temp_f}°F, {weather.description}")
            return weather

        except httpx.HTTPError as e:
            logger.error(f"Weather API request failed: {e}")
            return self._cache or self._get_fallback_data()
        except Exception as e:
            logger.error(f"Weather parsing failed: {e}")
            return self._cache or self._get_fallback_data()

    def _parse_response(self, data: dict[str, Any]) -> WeatherData:
        """Parse OpenWeatherMap API response."""
        main = data.get("main", {})
        weather_list = data.get("weather", [{}])
        weather_info = weather_list[0] if weather_list else {}
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})
        sys = data.get("sys", {})

        return WeatherData(
            temp_f=main.get("temp", 50),
            feels_like_f=main.get("feels_like", 50),
            humidity=main.get("humidity", 50),
            condition=WeatherCondition.from_openweathermap(weather_info.get("main", "Unknown")),
            description=weather_info.get("description", "").title(),
            icon=weather_info.get("icon", "01d"),
            sunrise=sys.get("sunrise", 0),
            sunset=sys.get("sunset", 0),
            wind_speed_mph=wind.get("speed", 0),
            wind_direction=wind.get("deg", 0),
            visibility_miles=data.get("visibility", 10000) / 1609.34,  # meters to miles
            cloud_coverage=clouds.get("all", 0),
            timestamp=data.get("dt", int(time.time())),
            location=data.get("name", "Seattle"),
        )

    def _get_fallback_data(self) -> WeatherData:
        """Get fallback data when API unavailable.

        Uses reasonable Seattle December defaults.
        """
        now = int(time.time())
        # Approximate Seattle December sunrise/sunset
        today = datetime.now()
        sunrise = int(datetime(today.year, today.month, today.day, 7, 54).timestamp())
        sunset = int(datetime(today.year, today.month, today.day, 16, 20).timestamp())

        return WeatherData(
            temp_f=45,
            feels_like_f=42,
            humidity=75,
            condition=WeatherCondition.CLOUDS,
            description="Mostly Cloudy (Offline)",
            icon="04d" if sunrise <= now <= sunset else "04n",
            sunrise=sunrise,
            sunset=sunset,
            wind_speed_mph=5,
            wind_direction=180,
            visibility_miles=8,
            cloud_coverage=70,
            timestamp=now,
            location="Seattle (Offline)",
        )

    async def get_forecast(self, force_refresh: bool = False) -> WeatherForecast | None:
        """Get 48-hour forecast.

        Uses OpenWeatherMap One Call API 3.0 (requires subscription).
        Falls back to current conditions if unavailable.

        Args:
            force_refresh: Bypass cache

        Returns:
            WeatherForecast or None if unavailable
        """
        # Check cache
        if not force_refresh and self._forecast_cache:
            if time.time() - self._forecast_cache_time < self.FORECAST_CACHE_TTL_SECONDS:
                return self._forecast_cache

        if not self.api_key:
            logger.warning("No OpenWeatherMap API key configured")
            return None

        try:
            client = await self._get_client()

            # One Call API 3.0 for forecast
            url = "https://api.openweathermap.org/data/3.0/onecall"
            params = {
                "lat": self.lat,
                "lon": self.lon,
                "appid": self.api_key,
                "units": "imperial",
                "exclude": "minutely,daily,alerts",  # Only hourly
            }

            response = await client.get(url, params=params)

            # One Call API might not be available (requires subscription)
            if response.status_code == 401:
                logger.debug("One Call API 3.0 not available (subscription required)")
                return self._get_fallback_forecast()

            response.raise_for_status()
            data = response.json()

            forecast = self._parse_forecast(data)

            # Cache result
            self._forecast_cache = forecast
            self._forecast_cache_time = time.time()

            logger.debug(f"Forecast updated: {len(forecast.hourly)} hours")
            return forecast

        except httpx.HTTPError as e:
            logger.debug(f"Forecast API request failed: {e}")
            return self._forecast_cache or self._get_fallback_forecast()
        except Exception as e:
            logger.debug(f"Forecast parsing failed: {e}")
            return self._forecast_cache or self._get_fallback_forecast()

    def _parse_forecast(self, data: dict[str, Any]) -> WeatherForecast:
        """Parse One Call API forecast response."""
        hourly_data = data.get("hourly", [])

        hourly = []
        for h in hourly_data[:48]:  # 48 hours max
            weather_info = h.get("weather", [{}])[0] if h.get("weather") else {}

            hourly.append(
                HourlyForecast(
                    timestamp=h.get("dt", 0),
                    temp_f=h.get("temp", 50),
                    condition=WeatherCondition.from_openweathermap(
                        weather_info.get("main", "Unknown")
                    ),
                    description=weather_info.get("description", "").title(),
                    cloud_coverage=h.get("clouds", 0),
                    precipitation_probability=int(h.get("pop", 0) * 100),
                    wind_speed_mph=h.get("wind_speed", 0),
                )
            )

        return WeatherForecast(
            hourly=hourly,
            timestamp=int(time.time()),
        )

    def _get_fallback_forecast(self) -> WeatherForecast:
        """Get fallback forecast from current conditions."""
        # Create a simple forecast from current data
        if self._cache:
            # Repeat current conditions for 6 hours
            hourly = []
            now = int(time.time())
            for i in range(6):
                hourly.append(
                    HourlyForecast(
                        timestamp=now + (i * 3600),
                        temp_f=self._cache.temp_f,
                        condition=self._cache.condition,
                        description=self._cache.description,
                        cloud_coverage=self._cache.cloud_coverage,
                        precipitation_probability=0,
                        wind_speed_mph=self._cache.wind_speed_mph,
                    )
                )
            return WeatherForecast(hourly=hourly, timestamp=now)

        return WeatherForecast()

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_weather_service: WeatherService | None = None


def get_weather_service() -> WeatherService:
    """Get global weather service instance."""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service


def reset_weather_service() -> None:
    """Reset weather service (for testing/reconfiguration)."""
    global _weather_service
    _weather_service = None


async def get_current_weather() -> WeatherData | None:
    """Convenience function to get current weather."""
    service = get_weather_service()
    return await service.get_current()


async def get_weather_forecast() -> WeatherForecast | None:
    """Convenience function to get weather forecast."""
    service = get_weather_service()
    return await service.get_forecast()


def get_shade_recommendation() -> dict[str, Any]:
    """Get shade recommendation based on weather.

    Returns:
        dict with 'should_close', 'reason', 'cloud_coverage'
    """
    service = get_weather_service()

    if service._cache:
        weather = service._cache
        forecast = service._forecast_cache

        # Use forecast if available
        if forecast and forecast.hourly:
            should_close = forecast.should_close_shades()
            cloud_trend = forecast.get_cloud_trend()
            return {
                "should_close": should_close,
                "reason": f"Forecast: {cloud_trend}",
                "cloud_coverage": weather.cloud_coverage,
                "cloud_trend": cloud_trend,
            }

        # Fall back to current conditions
        should_close = weather.cloud_coverage < 50 and weather.condition == WeatherCondition.CLEAR
        return {
            "should_close": should_close,
            "reason": f"Current: {weather.description}",
            "cloud_coverage": weather.cloud_coverage,
        }

    return {
        "should_close": True,  # Default to sun protection
        "reason": "No weather data",
        "cloud_coverage": None,
    }


__all__ = [
    "HourlyForecast",
    "WeatherCondition",
    "WeatherData",
    "WeatherForecast",
    "WeatherService",
    "get_current_weather",
    "get_shade_recommendation",
    "get_weather_forecast",
    "get_weather_service",
    "reset_weather_service",
]
