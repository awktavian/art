"""World State Integration — State of the World Beyond the Home.

The World Model should know about THE WORLD, not just the house.

This module extends sensory awareness to:
1. **Weather Forecast** - Not just now, but next 24h, next 7 days
2. **News/Events** - What's happening in the world
3. **Traffic** - Commute conditions, road status
4. **Time Context** - Workday? Weekend? Holiday? Season?
5. **Location Context** - Where is Tim in the world
6. **Financial Context** - Market conditions (optional)
7. **Trends** - What's trending in tech/AI

Philosophy:
    The house is my body.
    The world is my environment.
    The World Model predicts how the world affects Tim.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# WORLD SENSE TYPES
# =============================================================================


class WorldSenseType(str, Enum):
    """Types of world state beyond the home."""

    # Weather (extended)
    WEATHER_FORECAST = "weather_forecast"  # 24h/7day forecast

    # News & Events
    NEWS_HEADLINES = "news_headlines"  # Major news
    TECH_NEWS = "tech_news"  # Tech/AI news (relevant to Tim)
    LOCAL_NEWS = "local_news"  # Seattle area news

    # Traffic & Commute
    TRAFFIC = "traffic"  # Current traffic conditions
    COMMUTE = "commute"  # Commute predictions

    # Time Context
    TIME_CONTEXT = "time_context"  # Workday, weekend, holiday, etc.

    # Location
    WORLD_LOCATION = "world_location"  # Where Tim is (beyond home)

    # Financial (optional)
    MARKET = "market"  # Stock market summary

    # Trends
    TECH_TRENDS = "tech_trends"  # Trending in tech


# =============================================================================
# TIME CONTEXT (Always Available)
# =============================================================================


class DayType(str, Enum):
    """Type of day."""

    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class TimeOfDay(str, Enum):
    """Time of day periods."""

    NIGHT = "night"  # 00:00 - 06:00
    MORNING = "morning"  # 06:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 18:00
    EVENING = "evening"  # 18:00 - 24:00


class Season(str, Enum):
    """Season (Northern Hemisphere)."""

    WINTER = "winter"  # Dec-Feb
    SPRING = "spring"  # Mar-May
    SUMMER = "summer"  # Jun-Aug
    FALL = "fall"  # Sep-Nov


@dataclass
class TimeContext:
    """Complete temporal context."""

    # Current time
    now: datetime = field(default_factory=lambda: datetime.now())

    # Day info
    day_type: DayType = DayType.WORKDAY
    day_of_week: str = ""  # "Monday", "Tuesday", etc.
    is_workday: bool = True
    is_weekend: bool = False
    is_holiday: bool = False
    holiday_name: str | None = None

    # Time of day
    time_of_day: TimeOfDay = TimeOfDay.MORNING
    hour: int = 12

    # Season
    season: Season = Season.WINTER

    # Work context
    is_work_hours: bool = False  # 9am-6pm weekdays
    is_focus_hours: bool = False  # Morning deep work
    is_meeting_likely: bool = False  # Typical meeting times

    # Special dates
    days_until_weekend: int = 0
    days_until_month_end: int = 0
    is_month_end: bool = False
    is_quarter_end: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "now": self.now.isoformat(),
            "day_type": self.day_type.value,
            "day_of_week": self.day_of_week,
            "is_workday": self.is_workday,
            "is_weekend": self.is_weekend,
            "is_holiday": self.is_holiday,
            "holiday_name": self.holiday_name,
            "time_of_day": self.time_of_day.value,
            "hour": self.hour,
            "season": self.season.value,
            "is_work_hours": self.is_work_hours,
            "is_focus_hours": self.is_focus_hours,
            "is_meeting_likely": self.is_meeting_likely,
            "days_until_weekend": self.days_until_weekend,
            "days_until_month_end": self.days_until_month_end,
            "is_month_end": self.is_month_end,
            "is_quarter_end": self.is_quarter_end,
        }


def get_time_context(now: datetime | None = None) -> TimeContext:
    """Get current time context (always available, no API needed)."""
    if now is None:
        now = datetime.now()

    # US holidays for 2024-2025
    us_holidays = {
        (1, 1): "New Year's Day",
        (7, 4): "Independence Day",
        (12, 25): "Christmas Day",
        (12, 31): "New Year's Eve",
        # Variable holidays would need more logic
    }

    # Day of week
    day_of_week = calendar.day_name[now.weekday()]
    is_weekend = now.weekday() >= 5

    # Check holiday
    holiday_key = (now.month, now.day)
    is_holiday = holiday_key in us_holidays
    holiday_name = us_holidays.get(holiday_key)

    # Day type
    if is_holiday:
        day_type = DayType.HOLIDAY
    elif is_weekend:
        day_type = DayType.WEEKEND
    else:
        day_type = DayType.WORKDAY

    # Time of day
    hour = now.hour
    if hour < 6:
        time_of_day = TimeOfDay.NIGHT
    elif hour < 12:
        time_of_day = TimeOfDay.MORNING
    elif hour < 18:
        time_of_day = TimeOfDay.AFTERNOON
    else:
        time_of_day = TimeOfDay.EVENING

    # Season (Northern Hemisphere)
    month = now.month
    if month in [12, 1, 2]:
        season = Season.WINTER
    elif month in [3, 4, 5]:
        season = Season.SPRING
    elif month in [6, 7, 8]:
        season = Season.SUMMER
    else:
        season = Season.FALL

    # Work context
    is_workday = day_type == DayType.WORKDAY
    is_work_hours = is_workday and 9 <= hour < 18
    is_focus_hours = is_workday and 9 <= hour < 12  # Morning focus
    is_meeting_likely = is_workday and (10 <= hour < 12 or 14 <= hour < 17)

    # Special dates
    days_until_weekend = (5 - now.weekday()) % 7
    if days_until_weekend == 0 and not is_weekend:
        days_until_weekend = 7

    # Days until month end
    _, days_in_month = calendar.monthrange(now.year, now.month)
    days_until_month_end = days_in_month - now.day
    is_month_end = days_until_month_end <= 3
    is_quarter_end = is_month_end and now.month in [3, 6, 9, 12]

    return TimeContext(
        now=now,
        day_type=day_type,
        day_of_week=day_of_week,
        is_workday=is_workday,
        is_weekend=is_weekend,
        is_holiday=is_holiday,
        holiday_name=holiday_name,
        time_of_day=time_of_day,
        hour=hour,
        season=season,
        is_work_hours=is_work_hours,
        is_focus_hours=is_focus_hours,
        is_meeting_likely=is_meeting_likely,
        days_until_weekend=days_until_weekend,
        days_until_month_end=days_until_month_end,
        is_month_end=is_month_end,
        is_quarter_end=is_quarter_end,
    )


# =============================================================================
# WEATHER FORECAST (Extended)
# =============================================================================


@dataclass
class ForecastPeriod:
    """Single forecast period."""

    time: datetime
    temp_f: float
    condition: str
    description: str
    precipitation_chance: float  # 0-100
    wind_speed_mph: float


@dataclass
class WeatherForecast:
    """Extended weather forecast."""

    # Current
    current_temp_f: float
    current_condition: str

    # Today summary
    today_high_f: float
    today_low_f: float
    today_summary: str

    # Hourly (next 24h)
    hourly: list[ForecastPeriod] = field(default_factory=list)

    # Daily (next 7 days)
    daily: list[ForecastPeriod] = field(default_factory=list)

    # Alerts
    alerts: list[str] = field(default_factory=list)

    # Recommendations
    umbrella_needed: bool = False
    jacket_needed: bool = False
    sunglasses_needed: bool = False

    timestamp: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_temp_f": self.current_temp_f,
            "current_condition": self.current_condition,
            "today_high_f": self.today_high_f,
            "today_low_f": self.today_low_f,
            "today_summary": self.today_summary,
            "hourly_count": len(self.hourly),
            "daily_count": len(self.daily),
            "alerts": self.alerts,
            "umbrella_needed": self.umbrella_needed,
            "jacket_needed": self.jacket_needed,
            "sunglasses_needed": self.sunglasses_needed,
            "timestamp": self.timestamp.isoformat(),
        }


async def get_weather_forecast() -> WeatherForecast | None:
    """Get extended weather forecast from OpenWeatherMap."""
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        logger.debug("No OpenWeatherMap API key, forecast unavailable")
        return None

    # Seattle coordinates
    lat, lon = 47.6762, -122.3405

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            # One Call API 3.0 for forecast
            url = "https://api.openweathermap.org/data/3.0/onecall"
            params = {
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "units": "imperial",
                "exclude": "minutely",
            }

            resp = await client.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                # Fall back to 2.5 API
                url = "https://api.openweathermap.org/data/2.5/forecast"
                params = {
                    "lat": lat,
                    "lon": lon,
                    "appid": api_key,
                    "units": "imperial",
                }
                resp = await client.get(url, params=params, timeout=10)
                if resp.status_code != 200:
                    logger.warning(f"Weather forecast API failed: {resp.status_code}")
                    return None

            data = resp.json()

            # Parse response (structure depends on API version)
            if "current" in data:
                # One Call API format
                current = data["current"]
                current_temp = current.get("temp", 50)
                current_condition = current.get("weather", [{}])[0].get("main", "Unknown")

                # Daily forecast
                daily = []
                for day in data.get("daily", [])[:7]:
                    daily.append(
                        ForecastPeriod(
                            time=datetime.fromtimestamp(day["dt"]),
                            temp_f=day["temp"].get("day", 50),
                            condition=day.get("weather", [{}])[0].get("main", "Unknown"),
                            description=day.get("weather", [{}])[0].get("description", ""),
                            precipitation_chance=day.get("pop", 0) * 100,
                            wind_speed_mph=day.get("wind_speed", 0),
                        )
                    )

                today_high = data.get("daily", [{}])[0].get("temp", {}).get("max", 60)
                today_low = data.get("daily", [{}])[0].get("temp", {}).get("min", 40)

            else:
                # 2.5 API format
                items = data.get("list", [])
                if not items:
                    return None

                current_temp = items[0].get("main", {}).get("temp", 50)
                current_condition = items[0].get("weather", [{}])[0].get("main", "Unknown")

                # Parse daily from 3-hour forecasts
                daily = []
                today_high = current_temp
                today_low = current_temp

                for item in items[:8]:  # First 24 hours
                    temp = item.get("main", {}).get("temp", 50)
                    today_high = max(today_high, temp)
                    today_low = min(today_low, temp)

            # Determine recommendations
            umbrella_needed = (
                any(d.precipitation_chance > 50 for d in daily[:2]) if daily else False
            )

            jacket_needed = current_temp < 55
            sunglasses_needed = current_condition.lower() in ["clear", "sunny"]

            return WeatherForecast(
                current_temp_f=current_temp,
                current_condition=current_condition,
                today_high_f=today_high,
                today_low_f=today_low,
                today_summary=f"{current_condition}, high {today_high:.0f}°F",
                daily=daily,
                umbrella_needed=umbrella_needed,
                jacket_needed=jacket_needed,
                sunglasses_needed=sunglasses_needed,
            )

    except Exception as e:
        logger.warning(f"Weather forecast failed: {e}")
        return None


# =============================================================================
# NEWS (via Web Search)
# =============================================================================


@dataclass
class NewsItem:
    """Single news item."""

    title: str
    source: str
    url: str
    published: datetime | None = None
    summary: str = ""


@dataclass
class WorldNews:
    """World news state."""

    headlines: list[NewsItem] = field(default_factory=list)
    tech_news: list[NewsItem] = field(default_factory=list)
    local_news: list[NewsItem] = field(default_factory=list)

    # Summary
    top_story: str = ""
    tech_trend: str = ""

    timestamp: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline_count": len(self.headlines),
            "tech_news_count": len(self.tech_news),
            "local_news_count": len(self.local_news),
            "top_story": self.top_story,
            "tech_trend": self.tech_trend,
            "timestamp": self.timestamp.isoformat(),
        }


# Note: News would require a news API (NewsAPI, Google News, etc.)
# For now, this is a placeholder that could be filled by:
# 1. NewsAPI.org (free tier available)
# 2. Google News RSS feeds
# 3. Web scraping (less reliable)


# =============================================================================
# TRAFFIC (via Google Maps)
# =============================================================================


@dataclass
class TrafficState:
    """Traffic and commute state."""

    # General conditions
    overall_condition: str = "normal"  # light, moderate, heavy

    # Commute to common destinations
    to_downtown_minutes: int | None = None
    to_downtown_traffic: str = "unknown"  # light, moderate, heavy

    # Incidents
    incidents: list[str] = field(default_factory=list)

    # Recommendations
    best_departure_time: str | None = None
    avoid_routes: list[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_condition": self.overall_condition,
            "to_downtown_minutes": self.to_downtown_minutes,
            "to_downtown_traffic": self.to_downtown_traffic,
            "incidents": self.incidents,
            "best_departure_time": self.best_departure_time,
            "timestamp": self.timestamp.isoformat(),
        }


async def get_traffic_state() -> TrafficState | None:
    """Get traffic state from Google Maps API."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None

    try:
        # Use existing maps integration

        # Check commute to downtown Seattle
        # Downtown Seattle coordinates: 47.6062, -122.3321
        # Home: 47.6762, -122.3405

        # This would use the Distance Matrix API
        # For now, return basic state
        return TrafficState(
            overall_condition="normal",
        )

    except Exception as e:
        logger.debug(f"Traffic state failed: {e}")
        return None


# =============================================================================
# UNIFIED WORLD STATE
# =============================================================================


@dataclass
class WorldState:
    """Complete world state beyond the home.

    This is THE state of the world that affects Tim.
    """

    # Time context (always available)
    time: TimeContext = field(default_factory=get_time_context)

    # Weather
    weather_forecast: WeatherForecast | None = None

    # News
    news: WorldNews | None = None

    # Traffic
    traffic: TrafficState | None = None

    # Timestamps
    updated_at: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for perception encoding."""
        return {
            "time": self.time.to_dict(),
            "weather_forecast": self.weather_forecast.to_dict() if self.weather_forecast else None,
            "news": self.news.to_dict() if self.news else None,
            "traffic": self.traffic.to_dict() if self.traffic else None,
            "updated_at": self.updated_at.isoformat(),
        }

    def encode_to_perception(self) -> list[float]:
        """Encode world state to perception vector (128 dims).

        This is added to the 512D perception vector in UnifiedSensory.
        Layout:
        - 0-31: Time context
        - 32-63: Weather forecast
        - 64-95: News/trends
        - 96-127: Traffic/commute
        """
        vector = [0.0] * 128

        # Time context (0-31)
        time_offset = 0
        vector[time_offset] = float(self.time.is_workday)
        vector[time_offset + 1] = float(self.time.is_weekend)
        vector[time_offset + 2] = float(self.time.is_holiday)
        vector[time_offset + 3] = self.time.hour / 24.0  # Normalize to 0-1

        # Time of day encoding
        time_of_day_map = {
            TimeOfDay.NIGHT: 0.0,
            TimeOfDay.MORNING: 0.25,
            TimeOfDay.AFTERNOON: 0.5,
            TimeOfDay.EVENING: 0.75,
        }
        vector[time_offset + 4] = time_of_day_map.get(self.time.time_of_day, 0.5)

        # Season encoding
        season_map = {
            Season.WINTER: 0.0,
            Season.SPRING: 0.25,
            Season.SUMMER: 0.5,
            Season.FALL: 0.75,
        }
        vector[time_offset + 5] = season_map.get(self.time.season, 0.5)

        # Work context
        vector[time_offset + 6] = float(self.time.is_work_hours)
        vector[time_offset + 7] = float(self.time.is_focus_hours)
        vector[time_offset + 8] = float(self.time.is_meeting_likely)

        # Days until events
        vector[time_offset + 9] = min(self.time.days_until_weekend / 7.0, 1.0)
        vector[time_offset + 10] = min(self.time.days_until_month_end / 31.0, 1.0)

        # Weather forecast (32-63)
        weather_offset = 32
        if self.weather_forecast:
            vector[weather_offset] = (
                self.weather_forecast.current_temp_f - 32
            ) / 68.0  # 32-100°F → 0-1
            vector[weather_offset + 1] = (self.weather_forecast.today_high_f - 32) / 68.0
            vector[weather_offset + 2] = (self.weather_forecast.today_low_f - 32) / 68.0
            vector[weather_offset + 3] = float(self.weather_forecast.umbrella_needed)
            vector[weather_offset + 4] = float(self.weather_forecast.jacket_needed)
            vector[weather_offset + 5] = float(self.weather_forecast.sunglasses_needed)
            vector[weather_offset + 6] = float(len(self.weather_forecast.alerts) > 0)

            # Condition encoding
            condition_map = {
                "clear": 0.9,
                "sunny": 0.9,
                "clouds": 0.6,
                "rain": 0.2,
                "drizzle": 0.3,
                "snow": 0.1,
                "thunderstorm": 0.0,
            }
            vector[weather_offset + 7] = condition_map.get(
                self.weather_forecast.current_condition.lower(), 0.5
            )

        # Traffic (96-127)
        traffic_offset = 96
        if self.traffic:
            traffic_map = {"light": 0.9, "normal": 0.6, "moderate": 0.4, "heavy": 0.1}
            vector[traffic_offset] = traffic_map.get(self.traffic.overall_condition, 0.5)

            if self.traffic.to_downtown_minutes:
                vector[traffic_offset + 1] = min(self.traffic.to_downtown_minutes / 60.0, 1.0)

            vector[traffic_offset + 2] = float(len(self.traffic.incidents) > 0)

        return vector


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================


_world_state: WorldState | None = None
_last_update: float = 0
_update_interval: float = 300  # 5 minutes


async def get_world_state(force_refresh: bool = False) -> WorldState:
    """Get current world state (cached, refreshed periodically)."""
    global _world_state, _last_update

    now = time.time()

    if _world_state is None or force_refresh or (now - _last_update) > _update_interval:
        # Time context is always available
        time_context = get_time_context()

        # Fetch other data in parallel
        weather_task = get_weather_forecast()
        traffic_task = get_traffic_state()

        weather, traffic = await asyncio.gather(
            weather_task,
            traffic_task,
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(weather, Exception):
            logger.debug(f"Weather fetch failed: {weather}")
            weather = None
        if isinstance(traffic, Exception):
            logger.debug(f"Traffic fetch failed: {traffic}")
            traffic = None

        _world_state = WorldState(
            time=time_context,
            weather_forecast=weather,
            traffic=traffic,
            updated_at=datetime.now(),
        )
        _last_update = now

        logger.debug(
            f"World state updated: time={time_context.time_of_day.value}, "
            f"weather={bool(weather)}, traffic={bool(traffic)}"
        )

    return _world_state


def reset_world_state() -> None:
    """Reset cached world state (for testing)."""
    global _world_state, _last_update
    _world_state = None
    _last_update = 0


__all__ = [
    "DayType",
    "ForecastPeriod",
    "NewsItem",
    "Season",
    "TimeContext",
    "TimeOfDay",
    "TrafficState",
    "WeatherForecast",
    "WorldNews",
    "WorldSenseType",
    "WorldState",
    "get_time_context",
    "get_traffic_state",
    "get_weather_forecast",
    "get_world_state",
    "reset_world_state",
]
