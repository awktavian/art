"""Minimal Polling Stub — Replaces AdaptivePollingManager.

This is a thin stub that satisfies the SmartHomeController interface
without the heavy adaptive polling machinery. Actual polling is handled
by UnifiedSensoryIntegration in the core.

For new code, use:
    from kagami.core.integrations import get_unified_sensory
    sensory = get_unified_sensory()
    sensory.update_activity_level(ActivityLevel.HIGH)
    sensory.set_presence(True)

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class PollingStub:
    """Minimal stub replacing AdaptivePollingManager.

    Provides the interface expected by SmartHomeController without
    the heavyweight adaptive polling implementation. All actual
    polling is delegated to UnifiedSensoryIntegration.
    """

    def __init__(self, performance_monitor: Any = None) -> None:
        """Initialize polling stub.

        Args:
            performance_monitor: Ignored (kept for API compatibility)
        """
        self._profiles: dict[str, Any] = {}
        self._callbacks: list[Callable[[str, float], None]] = []
        self._presence = True
        self._running = False
        logger.debug("PollingStub initialized (delegating to UnifiedSensory)")

    def set_presence(self, present: bool) -> None:
        """Set presence state (no-op, handled by UnifiedSensory)."""
        self._presence = present

    async def start_polling(self) -> None:
        """Start polling (no-op, handled by UnifiedSensory)."""
        self._running = True
        logger.debug("PollingStub: start_polling() called (no-op)")

    async def stop_polling(self) -> None:
        """Stop polling (no-op, handled by UnifiedSensory)."""
        self._running = False
        logger.debug("PollingStub: stop_polling() called (no-op)")

    async def stop(self) -> None:
        """Stop the polling stub (alias for stop_polling)."""
        await self.stop_polling()

    def on_optimization_change(self, callback: Callable[[str, float], None]) -> None:
        """Register optimization callback (stored but not invoked)."""
        self._callbacks.append(callback)

    def record_activity(self, integration: str) -> None:
        """Record activity for integration (no-op)."""
        pass

    def get_polling_status(self, integration: str) -> dict[str, Any]:
        """Get polling status for integration.

        Returns:
            Minimal status dict with default values
        """
        return {
            "integration": integration,
            "current_interval": 30.0,
            "status": "delegated_to_unified_sensory",
        }

    def adjust_polling_interval(self, integration: str, interval: float) -> None:
        """Adjust polling interval (no-op)."""
        pass

    def get_optimization_summary(self) -> dict[str, Any]:
        """Get optimization summary.

        Returns:
            Summary indicating delegation to UnifiedSensory
        """
        return {
            "status": "delegated",
            "message": "Polling handled by UnifiedSensoryIntegration",
            "running": self._running,
            "presence": self._presence,
        }

    def get_all_polling_status(self) -> dict[str, dict[str, Any]]:
        """Get all polling statuses.

        Returns:
            Empty dict (polling delegated to UnifiedSensory)
        """
        return {}

    def force_poll(self, integration: str) -> bool:
        """Force poll integration (no-op).

        Returns:
            False (not implemented in stub)
        """
        return False


# Alias for backwards compatibility
AdaptivePollingManager = PollingStub


__all__ = ["AdaptivePollingManager", "PollingStub"]
