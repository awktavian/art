"""Colony Activation Bridge - Gesture → Colony Routing.

Bridges HAL gesture recognition to Kagami's colony routing system.
When a gesture activates a colony intent, this bridge translates it
into the organism's colony state machine.

This is where embodiment meets cognition.

Created: December 20, 2025
Status: Production-ready
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

from kagami_hal.adapters.common.gestural_interface import (
    ColonyActivation,
    ColonyIntent,
)
from kagami_hal.adapters.common.gesture import GestureEvent, GestureType

logger = logging.getLogger(__name__)


# Colony mapping from gesture system to Kagami routing
GESTURE_TO_COLONY_E: dict[GestureType, int] = {
    GestureType.COLONY_SPARK: 1,  # e₁ - Fold catastrophe
    GestureType.COLONY_FORGE: 2,  # e₂ - Cusp catastrophe
    GestureType.COLONY_FLOW: 3,  # e₃ - Swallowtail catastrophe
    GestureType.COLONY_NEXUS: 4,  # e₄ - Butterfly catastrophe
    GestureType.COLONY_BEACON: 5,  # e₅ - Hyperbolic umbilic
    GestureType.COLONY_GROVE: 6,  # e₆ - Elliptic umbilic
    GestureType.COLONY_CRYSTAL: 7,  # e₇ - Parabolic umbilic
}

INTENT_TO_COLONY_E: dict[ColonyIntent, int] = {
    ColonyIntent.SPARK: 1,
    ColonyIntent.FORGE: 2,
    ColonyIntent.FLOW: 3,
    ColonyIntent.NEXUS: 4,
    ColonyIntent.BEACON: 5,
    ColonyIntent.GROVE: 6,
    ColonyIntent.CRYSTAL: 7,
    ColonyIntent.KAGAMI: 0,  # e₀ - Unified self
}

# Colony names for logging
COLONY_NAMES = {
    0: "Kagami",
    1: "Spark",
    2: "Forge",
    3: "Flow",
    4: "Nexus",
    5: "Beacon",
    6: "Grove",
    7: "Crystal",
}


class OrganismProtocol(Protocol):
    """Protocol for organism colony state machine."""

    async def activate_colony(self, colony_idx: int, strength: float = 1.0) -> None:
        """Activate a colony by E-index."""
        ...

    def get_active_colony(self) -> int:
        """Get currently active colony index."""
        ...


class ColonyActivationBridge:
    """Bridge between HAL gestures and Kagami colony routing.

    This component watches for gesture-based colony activations and
    routes them to the organism's colony state machine.

    Usage:
        # Connect to HAL and organism
        bridge = ColonyActivationBridge(organism)
        hal_manager.register_colony_callback(bridge.on_colony_activation)

        # Now gestures will activate colonies
        # e.g., drawing a circle activates Nexus (e₄)
    """

    def __init__(
        self,
        organism: Any | None = None,
        confidence_threshold: float = 0.6,
        sustain_required: bool = False,
    ) -> None:
        """Initialize the bridge.

        Args:
            organism: The organism to route activations to
            confidence_threshold: Minimum confidence to trigger activation
            sustain_required: Whether sustained gesture is required
        """
        self._organism = organism
        self._confidence_threshold = confidence_threshold
        self._sustain_required = sustain_required

        # Callbacks for custom routing
        self._pre_activation_hooks: list[Callable[[int, float], bool]] = []
        self._post_activation_hooks: list[Callable[[int, float], None]] = []

        # State
        self._current_colony: int = 0
        self._activation_count: int = 0

        logger.info("ColonyActivationBridge initialized")

    def connect_organism(self, organism: Any) -> None:
        """Connect to an organism instance."""
        self._organism = organism
        logger.info("Bridge connected to organism")

    async def on_gesture_event(self, event: GestureEvent) -> None:
        """Handle IMU gesture events.

        Maps gesture types to colony indices and triggers activation.
        """
        gesture_type = event.gesture.gesture_type

        if gesture_type in GESTURE_TO_COLONY_E:
            colony_idx = GESTURE_TO_COLONY_E[gesture_type]
            strength = event.gesture.confidence

            await self._trigger_activation(colony_idx, strength)

    async def on_colony_activation(self, activation: ColonyActivation) -> None:
        """Handle sEMG colony activations from gestural interface.

        This is the primary entry point from HAL.
        """
        # Check threshold
        if activation.confidence < self._confidence_threshold:
            return

        # Check sustain requirement
        if self._sustain_required and not activation.sustain:
            return

        colony_idx = INTENT_TO_COLONY_E.get(activation.colony, 0)
        strength = activation.activation

        await self._trigger_activation(colony_idx, strength)

    async def _trigger_activation(self, colony_idx: int, strength: float) -> None:
        """Internal activation trigger with hooks and logging."""
        colony_name = COLONY_NAMES.get(colony_idx, f"e{colony_idx}")

        # Pre-activation hooks
        for hook in self._pre_activation_hooks:
            try:
                if not hook(colony_idx, strength):
                    logger.debug(f"Activation blocked by pre-hook: {colony_name}")
                    return
            except Exception as e:
                logger.warning(f"Pre-hook error: {e}")

        # Log activation
        logger.info(f"🎯 Colony activation: {colony_name} (e{colony_idx}) strength={strength:.2f}")

        # Route to organism
        if self._organism is not None:
            try:
                if hasattr(self._organism, "activate_colony"):
                    await self._organism.activate_colony(colony_idx, strength)
                elif hasattr(self._organism, "set_active_colony"):
                    self._organism.set_active_colony(colony_idx)
                else:
                    logger.warning("Organism has no colony activation method")
            except Exception as e:
                logger.error(f"Colony activation failed: {e}")

        self._current_colony = colony_idx
        self._activation_count += 1

        # Post-activation hooks
        for hook in self._post_activation_hooks:  # type: ignore[assignment]
            try:
                hook(colony_idx, strength)
            except Exception as e:
                logger.warning(f"Post-hook error: {e}")

    def get_current_colony(self) -> int:
        """Get the most recently activated colony."""
        return self._current_colony

    def get_activation_count(self) -> int:
        """Get total activation count."""
        return self._activation_count

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics."""
        return {
            "current_colony": self._current_colony,
            "current_colony_name": COLONY_NAMES.get(self._current_colony),
            "activation_count": self._activation_count,
            "confidence_threshold": self._confidence_threshold,
            "sustain_required": self._sustain_required,
            "organism_connected": self._organism is not None,
        }


# Singleton for easy access
_bridge: ColonyActivationBridge | None = None


def get_colony_bridge() -> ColonyActivationBridge:
    """Get or create the global colony activation bridge."""
    global _bridge
    if _bridge is None:
        _bridge = ColonyActivationBridge()
    return _bridge


async def setup_gesture_colony_routing(
    hal_manager: Any, organism: Any = None
) -> ColonyActivationBridge:
    """Set up gesture-based colony routing.

    Convenience function that:
    1. Gets/creates the bridge
    2. Connects to organism (if provided)
    3. Registers with HAL manager

    Args:
        hal_manager: HAL manager instance
        organism: Optional organism to connect

    Returns:
        Configured bridge
    """
    bridge = get_colony_bridge()

    if organism is not None:
        bridge.connect_organism(organism)

    # Register for colony activations from gestural interface
    if hasattr(hal_manager, "register_colony_callback"):
        hal_manager.register_colony_callback(bridge.on_colony_activation)

    # Register for IMU gesture events
    if hal_manager.gesture is not None:
        hal_manager.gesture.register_callback(bridge.on_gesture_event)

    logger.info("Gesture → Colony routing configured")
    return bridge
