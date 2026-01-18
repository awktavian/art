"""Health Service — Apple Health Biometrics.

Handles Apple Health integration:
- Heart rate and HRV
- Activity tracking (steps, rings)
- Sleep quality

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.apple_health import AppleHealthIntegration

logger = logging.getLogger(__name__)


class HealthService:
    """Service for Apple Health biometrics.

    Usage:
        health_svc = HealthService(apple_health_integration)
        hr = health_svc.get_heart_rate()
        rings = health_svc.get_activity_rings()
    """

    def __init__(self, apple_health: AppleHealthIntegration | None = None) -> None:
        """Initialize health service."""
        self._apple_health = apple_health

    def set_integration(self, apple_health: AppleHealthIntegration) -> None:
        """Set or update Apple Health integration."""
        self._apple_health = apple_health

    @property
    def is_available(self) -> bool:
        """Check if health service is available."""
        return self._apple_health is not None

    def get_health_state(self) -> dict[str, Any]:
        """Get current health/biometric state."""
        if not self._apple_health:
            return {"available": False}
        state = self._apple_health.get_state()
        return state.to_dict()

    def get_heart_rate(self) -> float | None:
        """Get current heart rate in bpm."""
        if not self._apple_health:
            return None
        return self._apple_health.get_state().heart.heart_rate

    def get_hrv(self) -> float | None:
        """Get current HRV (heart rate variability) in ms."""
        if not self._apple_health:
            return None
        return self._apple_health.get_state().heart.hrv

    def get_steps(self) -> int:
        """Get steps for today."""
        if not self._apple_health:
            return 0
        return self._apple_health.get_state().activity.steps

    def get_activity_rings(self) -> dict[str, float]:
        """Get Apple Activity ring progress (0-1 for each ring)."""
        if not self._apple_health:
            return {"move": 0, "exercise": 0, "stand": 0}

        activity = self._apple_health.get_state().activity
        return {
            "move": round(activity.move_ring_progress, 2),
            "exercise": round(activity.exercise_ring_progress, 2),
            "stand": round(activity.stand_ring_progress, 2),
            "all_closed": activity.all_rings_closed,
        }

    def get_sleep_quality(self) -> str:
        """Get last night's sleep quality assessment."""
        if not self._apple_health:
            return "unknown"
        return self._apple_health.get_state().sleep.sleep_quality

    async def process_health_webhook(self, payload: dict) -> None:
        """Process incoming health webhook data."""
        if self._apple_health:
            await self._apple_health.process_webhook(payload)


__all__ = ["HealthService"]
