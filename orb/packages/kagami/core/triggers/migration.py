"""Migration helpers for consolidating legacy trigger systems.

CREATED: January 5, 2026
"""

from __future__ import annotations

import datetime
from typing import Any

from .base import TriggerPriority, TriggerSourceType, UnifiedTrigger


def create_morning_weather_trigger(announce_fn: Any) -> UnifiedTrigger:
    """Create morning weather briefing trigger.

    Args:
        announce_fn: Async function(message, rooms) for announcements

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        # Must be morning
        now = datetime.datetime.now()
        if not (6 <= now.hour < 10):
            return False
        # Must have weather data
        return data.get("temp_f") is not None

    async def action(data: dict) -> None:
        temp_f = data.get("temp_f", 45)
        feels_like_f = data.get("feels_like_f", temp_f)
        description = data.get("description", "")
        humidity = data.get("humidity", 50)

        parts = [f"Good morning! It's {temp_f:.0f}°F outside"]
        if abs(feels_like_f - temp_f) > 3:
            parts.append(f", feels like {feels_like_f:.0f}°F")
        parts.append(f". {description.capitalize()}.")

        if humidity > 70:
            parts.append(" Humidity is high.")
        elif humidity < 30:
            parts.append(" Air is dry.")

        briefing = "".join(parts)
        await announce_fn(briefing, ["Living Room"])

    return UnifiedTrigger(
        name="morning_weather_briefing",
        source_type=TriggerSourceType.SENSORY,
        source="weather",
        condition=condition,
        action=action,
        cooldown=21600.0,  # 6 hours
        priority=TriggerPriority.NORMAL,
    )


def create_weather_change_trigger(announce_fn: Any) -> UnifiedTrigger:
    """Create weather change detection trigger.

    Args:
        announce_fn: Async function(message, rooms) for announcements

    Returns:
        UnifiedTrigger
    """
    # Shared state for change detection
    last_weather: dict[str, Any] = {}

    def condition(data: dict) -> bool:
        if not last_weather:
            last_weather["temp_f"] = data.get("temp_f", 45)
            last_weather["condition"] = data.get("condition", "")
            return False

        temp_f = data.get("temp_f", 45)
        last_temp = last_weather.get("temp_f", temp_f)
        temp_delta = abs(temp_f - last_temp)

        condition_str = data.get("condition", "")
        last_condition = last_weather.get("condition", "")

        is_significant = temp_delta > 10 or (condition_str != last_condition and condition_str)

        if is_significant:
            last_weather["temp_f"] = temp_f
            last_weather["condition"] = condition_str

        return is_significant

    async def action(data: dict) -> None:
        temp_f = data.get("temp_f", 45)
        description = data.get("description", "")
        await announce_fn(
            f"Weather update: {description.capitalize()}. Current temperature {temp_f:.0f}°F.",
            ["Living Room"],
        )

    return UnifiedTrigger(
        name="weather_change_alert",
        source_type=TriggerSourceType.SENSORY,
        source="weather",
        condition=condition,
        action=action,
        cooldown=3600.0,  # 1 hour
        priority=TriggerPriority.NORMAL,
    )


def create_cold_weather_trigger(announce_fn: Any) -> UnifiedTrigger:
    """Create cold weather alert trigger.

    Args:
        announce_fn: Async function(message, rooms) for announcements

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        feels_like_f = data.get("feels_like_f", data.get("temp_f", 70))
        return feels_like_f < 45

    async def action(data: dict) -> None:
        feels_like_f = data.get("feels_like_f", data.get("temp_f", 45))
        await announce_fn(
            f"It's cold outside, feels like {feels_like_f:.0f}°F. "
            "Consider adjusting the thermostat.",
            ["Living Room"],
        )

    return UnifiedTrigger(
        name="cold_weather_alert",
        source_type=TriggerSourceType.SENSORY,
        source="weather",
        condition=condition,
        action=action,
        cooldown=14400.0,  # 4 hours
        priority=TriggerPriority.LOW,
    )


def create_rain_protection_trigger(announce_fn: Any, smart_home: Any) -> UnifiedTrigger:
    """Create rain protection trigger.

    Args:
        announce_fn: Async function(message, rooms) for announcements
        smart_home: SmartHomeController

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        condition_str = data.get("condition", "")
        description = data.get("description", "").lower()
        return condition_str == "rain" or "rain" in description

    async def action(data: dict) -> None:
        await smart_home.close_shades()
        await announce_fn("Rain detected. Closing shades.", ["Living Room"])

    return UnifiedTrigger(
        name="rain_protection",
        source_type=TriggerSourceType.SENSORY,
        source="weather",
        condition=condition,
        action=action,
        cooldown=3600.0,  # 1 hour
        priority=TriggerPriority.HIGH,
    )


def create_snow_alert_trigger(announce_fn: Any, smart_home: Any) -> UnifiedTrigger:
    """Create snow alert trigger.

    Args:
        announce_fn: Async function(message, rooms) for announcements
        smart_home: SmartHomeController

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        condition_str = data.get("condition", "")
        description = data.get("description", "").lower()
        return condition_str == "snow" or "snow" in description

    async def action(data: dict) -> None:
        await smart_home.close_shades()
        await announce_fn(
            "Snow detected. Closing shades for insulation. Drive carefully if heading out.",
            ["Living Room"],
        )

    return UnifiedTrigger(
        name="snow_alert",
        source_type=TriggerSourceType.SENSORY,
        source="weather",
        condition=condition,
        action=action,
        cooldown=7200.0,  # 2 hours
        priority=TriggerPriority.HIGH,
    )


def register_all_weather_triggers(registry: Any, announce_fn: Any, smart_home: Any) -> None:
    """Register all weather triggers.

    Migrates weather triggers from CrossDomainBridge to UnifiedTrigger system.

    Args:
        registry: TriggerRegistry
        announce_fn: Async function(message, rooms)
        smart_home: SmartHomeController
    """
    registry.register(create_morning_weather_trigger(announce_fn))
    registry.register(create_weather_change_trigger(announce_fn))
    registry.register(create_cold_weather_trigger(announce_fn))
    registry.register(create_rain_protection_trigger(announce_fn, smart_home))
    registry.register(create_snow_alert_trigger(announce_fn, smart_home))
