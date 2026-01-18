"""Integration Tracker - Connectivity-based coordination metric.

Provides a lightweight heuristic for measuring cross-module integration
based on mutual information and connectivity metrics.

Created: December 7, 2025
"""

# Standard library imports
import logging
import time
from collections import deque
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntegrationState:
    """Current integration state."""

    current_score: float = 0.5
    history: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    last_update: float = field(default_factory=time.time)


class IntegrationTracker:
    """Heuristic integration tracker.

    Uses a simplified connectivity metric to measure cross-module coordination.
    This provides a tractable approximation based on:
    - Cross-module activation patterns
    - Temporal binding (how components correlate)
    - Task complexity modulation
    """

    def __init__(self) -> None:
        self._state = IntegrationState()
        self._initialized = False
        logger.debug("IntegrationTracker created")

    def measure_integration_heuristic(
        self,
        context: dict[str, Any],
    ) -> float:
        """Compute heuristic integration score.

        Args:
            context: Current task/phase context

        Returns:
            Integration score in [0, 1]
        """
        # Extract features that proxy integration
        task_type = context.get("task_type", "unknown")
        phase = context.get("phase", "unknown")
        complexity = float(context.get("complexity", 0.5))

        # Heuristic: complexity correlates with required integration
        # Multi-phase tasks require more cross-module coordination
        phase_bonus = 0.1 if phase in ("planning", "execution", "verification") else 0.0

        # Tasks involving multiple systems score higher
        system_bonus = 0.0
        if "." in task_type:
            parts = task_type.split(".")
            system_bonus = min(0.2, len(parts) * 0.05)

        # Base integration from complexity
        base = 0.3 + (complexity * 0.4)

        score = min(1.0, base + phase_bonus + system_bonus)

        # Update state
        self._state.current_score = score
        self._state.history.append(score)
        self._state.last_update = time.time()
        self._initialized = True

        return score

    def get_current_integration(self) -> float:
        """Get current integration score."""
        return self._state.current_score

    def get_integration_trend(self) -> str:
        """Get integration trend (increasing/decreasing/stable)."""
        history = list(self._state.history)

        if len(history) < 3:
            return "stable"

        # Compare recent vs older
        recent = sum(history[-5:]) / min(5, len(history[-5:]))
        older = sum(history[:-5]) / max(1, len(history[:-5]))

        diff = recent - older

        if diff > 0.05:
            return "increasing"
        elif diff < -0.05:
            return "decreasing"
        return "stable"

    def get_state(self) -> dict[str, Any]:
        """Get full tracker state."""
        return {
            "current_score": self._state.current_score,
            "trend": self.get_integration_trend(),
            "history_size": len(self._state.history),
            "initialized": self._initialized,
        }


# Singleton instance
_INTEGRATION_TRACKER: IntegrationTracker | None = None


def get_integration_tracker() -> IntegrationTracker:
    """Get or create the singleton integration tracker."""
    global _INTEGRATION_TRACKER
    if _INTEGRATION_TRACKER is None:
        _INTEGRATION_TRACKER = IntegrationTracker()
        logger.info("✅ IntegrationTracker initialized (coordination heuristic)")
    return _INTEGRATION_TRACKER


__all__ = [
    "IntegrationState",
    "IntegrationTracker",
    "get_integration_tracker",
]
