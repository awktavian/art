"""Weather Routes.

~60 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/weather")
async def get_weather() -> dict[str, Any]:
    """Get current weather for the home location (Green Lake, Seattle).

    Uses OpenWeatherMap API with 5-minute caching.
    Includes scene adaptation recommendations based on conditions.

    Returns:
        Weather data including temp, conditions, sunrise/sunset, and adaptations.
    """
    try:
        from kagami_smarthome import get_current_weather

        weather = await get_current_weather()
        if weather:
            return weather.to_dict()

        # Return offline fallback
        return {
            "temp_f": 45,
            "condition": "unknown",
            "description": "Weather service unavailable",
            "emoji": "🌡️",
            "is_daytime": True,
            "location": "Seattle",
            "offline": True,
        }
    except Exception as e:
        logger.error(f"Weather endpoint error: {e}")
        return {
            "error": str(e),
            "offline": True,
        }
