"""Lifecycle Module - Initialization, shutdown, health monitoring.

Responsibilities:
- Organism start/stop
- Homeostasis monitoring
- Colony management
- Stats and health reporting
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LifecycleMixin:
    """Mixin providing lifecycle management for UnifiedOrganism."""

    # These attributes are set by the main UnifiedOrganism class
    config: Any
    _colonies: dict[str, Any]
    _homeostasis_monitor: Any
    _running: bool
    _continuous_mind: Any
    _consciousness_integrated: bool
    _consciousness_enabled: bool
    blanket: Any
    status: Any
    stats: Any
    homeostasis: Any
    phase_detector: Any
    _coupling_strength: float

    def _get_or_create_colony(self, colony_idx: int) -> Any:
        """Get or create a colony by index."""
        from kagami.core.unified_agents.geometric_worker import COLONY_NAMES
        from kagami.core.unified_agents.minimal_colony import (
            ColonyConfig,
            create_colony,
        )

        name = COLONY_NAMES[colony_idx]

        if name not in self._colonies:
            colony_config = ColonyConfig(
                colony_idx=colony_idx,
                min_workers=self.config.min_workers_per_colony,
                max_workers=self.config.max_workers_per_colony,
            )
            colony = create_colony(colony_idx, colony_config)

            # MARKOV BLANKET HIERARCHY
            if hasattr(colony, "blanket"):
                colony.blanket.parent_blanket = self.blanket

            self._colonies[name] = colony
            self.stats.active_colonies = len(self._colonies)
            logger.info(
                f"Bringing in {name} to help with this (blanket hierarchy: organism > colony)"
            )

        return self._colonies[name]

    def get_colony(self, name: str | None) -> Any | None:
        """Get colony by name.

        Colonies are lazily created; if a valid colony name is requested,
        this method will create it on-demand.
        """
        from kagami.core.unified_agents.geometric_worker import COLONY_NAMES

        if not name:
            return None

        key = str(name).strip().lower()
        if not key:
            return None

        existing = self._colonies.get(key)
        if existing is not None:
            return existing

        if key in COLONY_NAMES:
            return self._get_or_create_colony(COLONY_NAMES.index(key))

        return None

    def get_colony_by_index(self, idx: int) -> Any | None:
        """Get colony by index (0-6)."""
        if 0 <= idx < 7:
            return self._get_or_create_colony(idx)
        return None

    @property
    def colonies(self) -> dict[str, Any]:
        """Get all colonies."""
        for i in range(7):
            self._get_or_create_colony(i)
        return self._colonies

    def __iter__(self) -> Iterator[Any]:
        """Iterate over colonies."""
        return iter(self.colonies.values())

    async def start(self) -> None:
        """Start the organism (homeostasis loop)."""
        if self._running:
            return

        self._running = True

        # Initialize all colonies
        for i in range(7):
            self._get_or_create_colony(i)

        # Start homeostasis monitor
        await self._homeostasis_monitor.start(self._colonies)

        # Update local status references
        self.status = self._homeostasis_monitor.status
        self.stats = self._homeostasis_monitor.stats
        self.homeostasis = self._homeostasis_monitor.state

        # Enable perfect consciousness integration
        if self._consciousness_enabled and not self._consciousness_integrated:
            try:
                await self.enable_perfect_consciousness()
            except Exception as e:
                logger.warning(f"Perfect consciousness integration failed on startup: {e}")

        logger.info("Waking up. All colonies ready.")

    async def stop(self) -> None:
        """Stop the organism."""
        self._running = False

        # Stop continuous mind if enabled
        if self._continuous_mind is not None:
            await self.disable_continuous_learning()

        # Disable perfect consciousness if enabled
        if self._consciousness_integrated:
            await self.disable_perfect_consciousness()

        # Stop homeostasis monitor
        await self._homeostasis_monitor.stop()

        # Update local status reference
        self.status = self._homeostasis_monitor.status

        logger.info("Resting now. I'll be here when you need me.")

    def get_stats(self) -> dict[str, Any]:
        """Get organism statistics."""
        colony_stats = {name: colony.get_stats() for name, colony in self._colonies.items()}

        stats = {
            "status": self.status.value,
            "uptime": self.stats.uptime,
            "total_intents": self.stats.total_intents,
            "completed": self.stats.completed_intents,
            "failed": self.stats.failed_intents,
            "success_rate": self.stats.success_rate,
            "total_population": self.stats.total_population,
            "active_colonies": self.stats.active_colonies,
            "homeostasis_cycles": self.stats.homeostasis_cycles,
            "overall_health": self.homeostasis.overall_health,
            "colonies": colony_stats,
            "phase_detector": self.get_phase_stats(),
            "coupling_strength": self._coupling_strength,
        }

        # NEXUS COLONY INTEGRATION: Include consciousness statistics
        if self._consciousness_integrated:
            stats["consciousness"] = self.get_consciousness_summary()
        else:
            stats["consciousness"] = {
                "consciousness_enabled": self._consciousness_enabled,
                "consciousness_integrated": False,
                "message": "Perfect consciousness available but not integrated",
            }

        return stats

    def get_health(self) -> dict[str, Any]:
        """Get health status for API."""
        return {
            "status": self.status.value,
            "health": self.homeostasis.overall_health,
            "colony_health": self.homeostasis.colony_health,
            "population": self.stats.total_population,
        }

    def get_phase_stats(self) -> dict[str, Any]:
        """Get phase transition detector statistics.

        Returns:
            Phase detector stats dict
        """
        return self.phase_detector.get_stats()


__all__ = ["LifecycleMixin"]
