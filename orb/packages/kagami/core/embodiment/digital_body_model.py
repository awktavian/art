"""Digital Body Model - K os's Digital Embodiment.

Note: Consolidated from kagami.core.embodied.digital_body_model
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class DigitalBodyModel:
    """Model of K os's digital body (sensors + actuators)."""

    def __init__(self) -> None:
        self.sensors = {
            "api_latency": lambda: np.random.uniform(5, 50),
            "error_rate": lambda: np.random.uniform(0, 0.05),
            "memory_usage": lambda: np.random.uniform(10, 30),
            "agent_activity": lambda: np.random.randint(0, 23),
        }

        self.actuators = {
            "code_modification": self._code_actuator,
            "api_response": self._api_actuator,
            "database_write": self._db_actuator,
            "event_emission": self._event_actuator,
        }

        self.body_schema = {
            "size": "large",
            "capabilities": list(self.actuators.keys()),
            "boundaries": "filesystem + api + db",
        }

    async def _code_actuator(self, action: dict[str, Any]) -> dict[str, Any]:
        """Simulate code modification action."""
        return {"type": "code_modification", "success": True, "latency_ms": 15}

    async def _api_actuator(self, action: dict[str, Any]) -> dict[str, Any]:
        """Simulate API response action."""
        return {"type": "api_response", "success": True, "latency_ms": 10}

    async def _db_actuator(self, action: dict[str, Any]) -> dict[str, Any]:
        """Simulate database write action."""
        return {"type": "database_write", "success": True, "latency_ms": 25}

    async def _event_actuator(self, action: dict[str, Any]) -> dict[str, Any]:
        """Simulate event emission action."""
        return {"type": "event_emission", "success": True, "latency_ms": 5}

    async def imagine_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Simulate action in body model (mental imagery)."""
        predicted_sensations = {}
        for sensor_name, sensor_fn in self.sensors.items():
            predicted_sensations[sensor_name] = sensor_fn()

        actuator_type = action.get("type", "api_response")
        actuator_fn = self.actuators.get(actuator_type, self._api_actuator)
        predicted_feedback = await actuator_fn(action)

        return {
            "sensations": predicted_sensations,
            "feedback": predicted_feedback,
            "success_probability": 0.85,
        }


_body_model: DigitalBodyModel | None = None


def get_digital_body_model() -> DigitalBodyModel:
    global _body_model
    if _body_model is None:
        _body_model = DigitalBodyModel()
        logger.info("🤖 Digital Body Model initialized (Embodied Cognition)")
    return _body_model


__all__ = ["DigitalBodyModel", "get_digital_body_model"]
