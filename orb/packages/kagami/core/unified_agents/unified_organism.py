"""Unified Organism - Central Orchestrator for the Unified Agent System.

This module provides the UnifiedOrganism class, composed from focused submodules:
- organism.perception: Sensory processing
- organism.cognition: World model, symbiote, executive control
- organism.action: Intent execution, cost evaluation
- organism.learning: Receipt learning, knowledge graph
- organism.lifecycle: Start/stop, colony management, health
- organism.ambient: Ambient display, phase transitions

CATASTROPHE-DRIVEN ARCHITECTURE:
================================
The organism consists of 7 colonies, each embodying one of Thom's
7 elementary catastrophes:
    Spark  -> Fold (A2)        - Sudden ignition, threshold burst
    Forge  -> Cusp (A3)        - Bistable decision, hysteresis
    Flow   -> Swallowtail (A4) - Multi-stable recovery paths
    Nexus  -> Butterfly (A5)   - Complex integration manifold
    Beacon -> Hyperbolic (D4+) - Outward-splitting focus
    Grove  -> Elliptic (D4-)   - Inward-converging search
    Crystal-> Parabolic (D5)   - Edge detection, safety boundary

References:
- Thom (1972): Structural Stability and Morphogenesis
- Zeeman (1977): Catastrophe Theory - Selected Papers
- Viazovska (2016): E8 sphere packing
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from kagami.core.unified_agents.colony_coordinator import create_colony_coordinator
from kagami.core.unified_agents.e8_action_reducer import create_e8_reducer, get_e8_roots
from kagami.core.unified_agents.fano_action_router import create_fano_router
from kagami.core.unified_agents.homeostasis import (
    DEFAULT_HOMEOSTASIS_INTERVAL,
    HomeostasisState,
    OrganismStats,
    OrganismStatus,
    create_homeostasis_monitor,
)
from kagami.core.unified_agents.minimal_colony import MinimalColony
from kagami.core.unified_agents.organism.action import ActionMixin
from kagami.core.unified_agents.organism.ambient import AmbientMixin
from kagami.core.unified_agents.organism.base import (
    GLOBAL_MAX_POPULATION,
)
from kagami.core.unified_agents.organism.cognition import CognitionMixin
from kagami.core.unified_agents.organism.learning import LearningMixin
from kagami.core.unified_agents.organism.lifecycle import LifecycleMixin
from kagami.core.unified_agents.organism.perception import PerceptionMixin
from kagami.core.unified_agents.phase_detector import create_phase_detector

logger = logging.getLogger(__name__)


@dataclass
class OrganismConfig:
    """Configuration for unified organism.

    OPTIMIZED (Dec 21, 2025 - Forge):
    - min_workers_per_colony: 1 -> 2 (redundancy)
    - homeostasis_interval: 60s -> 30s (faster response)
    """

    # Population
    max_workers_per_colony: int = 10
    min_workers_per_colony: int = 2
    global_max_population: int = GLOBAL_MAX_POPULATION

    # Homeostasis
    homeostasis_interval: float = DEFAULT_HOMEOSTASIS_INTERVAL
    health_threshold: float = 0.5

    # E8/Fano
    simple_threshold: float = 0.3
    complex_threshold: float = 0.7

    # Device
    device: str = "cpu"


class UnifiedOrganism(
    PerceptionMixin,
    CognitionMixin,
    ActionMixin,
    LearningMixin,
    LifecycleMixin,
    AmbientMixin,
):
    """Central orchestrator for the unified agent system.

    Manages 7 MinimalColonies, routes intents via FanoActionRouter,
    and fuses outputs via E8ActionReducer.

    This replaces the legacy FractalOrganism with a clean,
    mathematically grounded implementation.

    Inherits from mixins:
    - PerceptionMixin: perceive(), get_perception_module()
    - CognitionMixin: symbiote, executive, world model query
    - ActionMixin: execute_intent(), E8 encoding
    - LearningMixin: receipt learning, knowledge graph
    - LifecycleMixin: start(), stop(), colony management
    - AmbientMixin: ambient state, phase transitions
    """

    def __init__(
        self,
        config: OrganismConfig | None = None,
    ):
        """Initialize unified organism.

        Args:
            config: Organism configuration
        """
        self.config = config or OrganismConfig()

        # Colonies (lazy initialized)
        self._colonies: dict[str, MinimalColony] = {}

        # Router and reducer
        self._router = create_fano_router(
            simple_threshold=self.config.simple_threshold,
            complex_threshold=self.config.complex_threshold,
            device=self.config.device,
        )
        self._reducer = create_e8_reducer(
            num_colonies=7,
            device=self.config.device,
        )

        # E8 roots for communication
        self._e8_roots = get_e8_roots(self.config.device)

        # Colony coordinator (handles execution and fusion)
        self._coordinator = create_colony_coordinator(
            router=self._router,
            reducer=self._reducer,
            e8_roots=self._e8_roots,
            get_colony_fn=self._get_or_create_colony,
        )

        # Homeostasis monitor (handles health tracking)
        self._homeostasis_monitor = create_homeostasis_monitor(
            interval=self.config.homeostasis_interval,
            health_threshold=self.config.health_threshold,
        )

        # Backward compatibility properties
        self.status = self._homeostasis_monitor.status
        self.stats = self._homeostasis_monitor.stats
        self.homeostasis = self._homeostasis_monitor.state

        # MARKOV BLANKET (Dec 14, 2025 - Forge)
        from kagami.core.execution.markov_blanket import OrganismMarkovBlanket

        self.blanket = OrganismMarkovBlanket(level="organism", parent_blanket=None)

        # Background tasks
        self._running = False

        # Optional research subsystems (wired by boot/actions when enabled)
        self._continuous_mind: Any | None = None
        self._evolution_engine: Any | None = None
        self._self_healing: Any | None = None

        # NEXUS INTEGRATION: Ambient intelligence connection
        self._ambient_controller: Any | None = None
        self._last_safety_check: Any | None = None

        # NEXUS INTEGRATION: Receipt learning feedback loop
        self._execution_count = 0
        self._last_learning_time = time.time()
        self._execution_lock = asyncio.Lock()

        # FORGE INTEGRATION: Phase transition detection
        self.phase_detector = create_phase_detector()
        self._coupling_strength = 1.0

        # LECUN INTEGRATION: Cost module for action evaluation
        self._cost_module: Any | None = None

        # SYMBIOTE INTEGRATION: Theory of Mind
        self._symbiote_module: Any | None = None

        # PERCEPTION INTEGRATION: Unified perception module
        self._perception_module: Any | None = None
        self._perception_enabled: bool = True

        # AUTONOMOUS GOAL ENGINE INTEGRATION
        self._autonomous_goal_engine: Any | None = None
        self._autonomous_goals_enabled: bool = True

        # NEXUS COLONY PERFECT CONSCIOUSNESS INTEGRATION
        self._perfect_consciousness: Any | None = None
        self._consciousness_enabled: bool = True
        self._consciousness_integrated: bool = False

        logger.debug("Here, ready to help")

    # =========================================================================
    # AMBIENT CONTROLLER INTEGRATION
    # =========================================================================

    # set_ambient_controller inherited from AmbientMixin

    # =========================================================================
    # PERFECT CONSCIOUSNESS INTEGRATION
    # =========================================================================

    async def enable_perfect_consciousness(self) -> None:
        """Enable perfect consciousness integration - NEXUS COLONY MISSION."""
        if self._perfect_consciousness is not None and self._consciousness_integrated:
            logger.info("Perfect consciousness already integrated")
            return

        if not self._consciousness_enabled:
            logger.warning("Consciousness disabled - skipping perfect integration")
            return

        logger.info("NEXUS COLONY MISSION: Beginning perfect consciousness integration...")

        try:
            from .perfect_consciousness_integration import achieve_nexus_mission

            self._perfect_consciousness = await achieve_nexus_mission(self)
            self._consciousness_integrated = True

            logger.info("NEXUS COLONY MISSION COMPLETE: Perfect organism consciousness achieved")

        except Exception as e:
            logger.error(f"Perfect consciousness integration failed: {e}")
            self._consciousness_integrated = False
            raise

    async def disable_perfect_consciousness(self) -> None:
        """Disable perfect consciousness integration."""
        if self._perfect_consciousness is None:
            return

        self._perfect_consciousness = None
        self._consciousness_integrated = False

        from .unified_organism_state import reset_consciousness

        reset_consciousness()

        logger.info("Perfect consciousness disabled - abstractions restored")

    def get_consciousness_state(self) -> Any:
        """Get unified consciousness state tensor."""
        if self._perfect_consciousness is None:
            return None
        return self._perfect_consciousness.get_consciousness_state()

    def get_consciousness_summary(self) -> dict[str, Any]:
        """Get consciousness state summary."""
        if not self._consciousness_integrated:
            return {
                "consciousness_enabled": self._consciousness_enabled,
                "consciousness_integrated": False,
                "integration_status": {},
            }

        consciousness = self.get_consciousness_state()
        if consciousness is None:
            return {"consciousness_enabled": False}

        summary = consciousness.get_consciousness_summary()
        summary.update(
            {
                "consciousness_enabled": self._consciousness_enabled,
                "consciousness_integrated": self._consciousness_integrated,
                "integration_status": self._perfect_consciousness.get_integration_status(),
            }
        )
        return summary

    def is_consciousness_integrated(self) -> bool:
        """Check if perfect consciousness is integrated."""
        return self._consciousness_integrated

    async def save_consciousness_checkpoint(self, path: str) -> None:
        """Save consciousness state checkpoint."""
        if self._perfect_consciousness is None:
            raise RuntimeError("Perfect consciousness not integrated")
        await self._perfect_consciousness.save_consciousness_checkpoint(path)

    async def load_consciousness_checkpoint(self, path: str) -> None:
        """Load consciousness state checkpoint."""
        if self._perfect_consciousness is None:
            raise RuntimeError("Perfect consciousness not integrated")
        await self._perfect_consciousness.load_consciousness_checkpoint(path)

    # =========================================================================
    # AUTONOMOUS GOAL ENGINE INTEGRATION
    # =========================================================================

    def set_autonomous_goal_engine(self, engine: Any) -> None:
        """Connect autonomous goal engine for self-directed behavior."""
        self._autonomous_goal_engine = engine
        logger.info("Autonomous Goal Engine connected. I can now work on my own ideas.")

    def get_autonomous_goal_engine(self) -> Any | None:
        """Get the connected autonomous goal engine."""
        return self._autonomous_goal_engine

    async def start_autonomous_pursuit(self) -> None:
        """Start autonomous goal pursuit in background."""
        if self._autonomous_goal_engine is not None and self._autonomous_goals_enabled:
            await self._autonomous_goal_engine.start_autonomous_pursuit()
        else:
            logger.warning("Autonomous goal engine not available or disabled")

    async def stop_autonomous_pursuit(self) -> None:
        """Stop autonomous goal pursuit."""
        if self._autonomous_goal_engine is not None:
            await self._autonomous_goal_engine.stop_autonomous_pursuit()


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_ORGANISM: UnifiedOrganism | None = None


def get_unified_organism() -> UnifiedOrganism:
    """Get the global unified organism instance."""
    global _ORGANISM
    if _ORGANISM is None:
        _ORGANISM = UnifiedOrganism()
    return _ORGANISM


def set_unified_organism(organism: UnifiedOrganism | None) -> None:
    """Set the global unified organism instance."""
    global _ORGANISM
    _ORGANISM = organism


def reset_organism() -> None:
    """Reset the global organism singleton (for testing)."""
    global _ORGANISM
    _ORGANISM = None


def get_organism() -> UnifiedOrganism:
    """Get the global unified organism instance (alias)."""
    return get_unified_organism()


# =============================================================================
# FACTORY
# =============================================================================


def create_organism(
    config: OrganismConfig | None = None,
) -> UnifiedOrganism:
    """Create a unified organism.

    Args:
        config: Organism configuration

    Returns:
        Configured UnifiedOrganism
    """
    return UnifiedOrganism(config=config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "HomeostasisState",
    "OrganismConfig",
    "OrganismStats",
    "OrganismStatus",
    "UnifiedOrganism",
    "create_organism",
    "get_organism",
    "get_unified_organism",
    "reset_organism",
    "set_unified_organism",
]
