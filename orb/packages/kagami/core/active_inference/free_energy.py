"""Free Energy Coordinator - Active Inference Integration.

This module provides the free energy coordinator interface for action selection
via Expected Free Energy (EFE) minimization.

DESIGN (Dec 2, 2025):
=====================
This is the ONLY action selection path. There are NO fallbacks.
EFE-based action selection is mandatory for all decision making.

The free energy coordinator wraps the ActiveInferenceEngine to provide
a consistent interface for the RL loop and other components.

References:
- Friston, K. (2010). "The free-energy principle: a unified brain theory?"
- Parr et al. (2022). "Active Inference: The Free Energy Principle"
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.active_inference.engine import (
    ActiveInferenceConfig,
    get_active_inference_engine,
    reset_active_inference_engine,
)

logger = logging.getLogger(__name__)


class FreeEnergyCoordinator:
    """Coordinator for free energy-based action selection.

    Wraps ActiveInferenceEngine to provide the standard interface
    expected by the RL loop and other components.

    MANDATORY (Dec 2, 2025):
    This is the ONLY action selection path. EFE is always enabled.
    """

    def __init__(self, config: ActiveInferenceConfig | None = None) -> None:
        """Initialize free energy coordinator.

        Args:
            config: Optional configuration for ActiveInferenceEngine
        """
        self._engine = get_active_inference_engine(config)
        logger.info("✅ FreeEnergyCoordinator initialized (EFE mandatory)")

    async def perceive(self, observations: dict[str, Any]) -> Any:
        """Update beliefs from observations.

        Args:
            observations: Dict with observation data

        Returns:
            Updated belief state
        """
        return await self._engine.perceive(observations)

    async def select_action(
        self,
        candidates: list[dict[str, Any]] | None = None,
        goals: Any = None,
        plan_tic: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Select action via Expected Free Energy minimization.

        This is the ONLY action selection path. There are NO fallbacks.

        Args:
            candidates: Optional pre-generated action candidates
            goals: Optional goal specification
            plan_tic: Optional TIC data for imagination-based filtering

        Returns:
            Selected action with metadata including:
            - action: The selected action tensor
            - policy: Full policy sequence
            - G: Expected free energy value
            - epistemic_value: Information gain component
            - pragmatic_value: Goal achievement component
            - method: Always "active_inference"
        """
        return await self._engine.select_action(
            candidates=candidates,
            goals=goals,
            plan_tic=plan_tic,
        )

    def set_goal(self, goal: Any) -> None:
        """Set goal for pragmatic value computation.

        Args:
            goal: Goal observation or embedding
        """
        self._engine.set_goal(goal)

    def get_diagnostics(self) -> dict[str, Any]:
        """Get diagnostic information.

        Returns:
            Dict with free energy, belief entropy, etc.
        """
        return self._engine.get_diagnostics()


# Singleton instance
_free_energy_coordinator: FreeEnergyCoordinator | None = None


def get_free_energy_coordinator(
    config: ActiveInferenceConfig | None = None,
) -> FreeEnergyCoordinator:
    """Get or create the global FreeEnergyCoordinator instance.

    This is the ONLY action selection coordinator. EFE is always enabled.

    Args:
        config: Optional configuration for first-time initialization

    Returns:
        Global FreeEnergyCoordinator instance
    """
    global _free_energy_coordinator
    if _free_energy_coordinator is None:
        _free_energy_coordinator = FreeEnergyCoordinator(config)
    return _free_energy_coordinator


def reset_free_energy_coordinator() -> None:
    """Reset the global coordinator (for testing)."""
    global _free_energy_coordinator
    _free_energy_coordinator = None
    reset_active_inference_engine()


__all__ = [
    "FreeEnergyCoordinator",
    "get_free_energy_coordinator",
    "reset_free_energy_coordinator",
]
