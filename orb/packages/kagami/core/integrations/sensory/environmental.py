"""Environmental sensors - weather, world state, situation awareness.

These sensors provide context about the external environment and
overall situational awareness.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import CachedSense, SenseType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EnvironmentalSensors:
    """Environmental sensing capabilities."""

    def __init__(self, cache: dict[SenseType, CachedSense], stats: dict[str, Any]):
        self._cache = cache
        self._stats = stats
        self._situation_engine: Any = None

    def _get_cached(self, sense_type: SenseType) -> CachedSense | None:
        """Get cached data if valid."""
        cached = self._cache.get(sense_type)
        if cached and cached.is_valid:
            self._stats["cache_hits"] += 1
            return cached
        self._stats["cache_misses"] += 1
        return None

    async def poll_weather(self) -> dict[str, Any]:
        """Poll weather from OpenWeatherMap via SmartHome weather service."""
        cached = self._get_cached(SenseType.WEATHER)
        if cached:
            return cached.data

        try:
            from kagami_smarthome import get_current_weather

            weather = await get_current_weather()

            if weather:
                data = weather.to_dict()
            else:
                data = {
                    "temp_f": 45,
                    "condition": "unknown",
                    "description": "Weather unavailable",
                    "is_daytime": True,
                    "location": "Seattle",
                    "offline": True,
                    "timestamp": datetime.now().isoformat(),
                }

            return data

        except Exception as e:
            logger.debug(f"Weather poll failed: {e}")
            return {"condition": "unknown", "error": str(e)}

    async def poll_world_state(self) -> dict[str, Any]:
        """Poll world state - time context, forecast, traffic, trends."""
        cached = self._get_cached(SenseType.WORLD_STATE)
        if cached:
            return cached.data

        try:
            from kagami.core.integrations.world_state import get_world_state

            world = await get_world_state()

            data = world.to_dict()
            data["perception_vector"] = world.encode_to_perception()

            return data

        except Exception as e:
            logger.debug(f"World state poll failed: {e}")
            from kagami.core.integrations.world_state import get_time_context

            time_ctx = get_time_context()
            return {
                "time": time_ctx.to_dict(),
                "error": str(e),
            }

    async def poll_situation(
        self,
        get_cached_sense: Any,
    ) -> dict[str, Any]:
        """Poll situation awareness - THE answer to 'what's going on?'

        Args:
            get_cached_sense: Function to get cached sense data
        """
        cached = self._get_cached(SenseType.SITUATION)
        if cached:
            return cached.data

        try:
            from kagami.core.integrations.situation_awareness import (
                SituationPhase,
                get_situation_engine,
            )

            engine = get_situation_engine()

            # Get current sensory state
            sensory_state = {}
            for sense_type in [
                SenseType.CALENDAR,
                SenseType.GMAIL,
                SenseType.LINEAR,
                SenseType.WEATHER,
                SenseType.PRESENCE,
                SenseType.LIGHTS,
                SenseType.CLIMATE,
                SenseType.SECURITY,
                SenseType.SLEEP,
                SenseType.VEHICLE,
            ]:
                cached_sense = get_cached_sense(sense_type)
                if cached_sense:
                    sensory_state[sense_type.value] = cached_sense.data

            # Get world state
            world_state = {}
            world_cached = get_cached_sense(SenseType.WORLD_STATE)
            if world_cached:
                world_state = world_cached.data

            # Get previous phase
            old_phase = SituationPhase.UNKNOWN
            prev_cached = self._cache.get(SenseType.SITUATION)
            if prev_cached and "phase" in prev_cached.data:
                try:
                    old_phase = SituationPhase(prev_cached.data["phase"])
                except (ValueError, KeyError):
                    old_phase = SituationPhase.UNKNOWN

            # Assess situation
            situation = await engine.assess(sensory_state, world_state)

            data = situation.to_dict()
            data["perception_vector"] = situation.encode_to_perception()
            data["_old_phase"] = old_phase.value
            data["_new_phase"] = situation.phase.value

            logger.debug(
                f"Situation: {situation.phase.value}, "
                f"urgency={situation.urgency.value}, "
                f"summary={situation.summary[:50]}"
            )

            return data

        except Exception as e:
            logger.debug(f"Situation poll failed: {e}")
            return {"phase": "unknown", "error": str(e)}


__all__ = ["EnvironmentalSensors"]
