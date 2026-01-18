"""Kagami Orb — Unified State Model.

The Orb is Kagami's primary visual identity across all platforms.
This module provides the canonical state model, colors, and events
for cross-client synchronization.

Implementations:
    - VisionOS: Spatial 3D orb with particles
    - Hub: LED ring with colony colors
    - Desktop: Ambient display orb
    - Hardware (future): Levitating infinity mirror

Colony: Nexus (e₄) — Integration and unification

Example:
    >>> from kagami.core.orb import OrbState, OrbInteraction, ColonyColor
    >>> state = OrbState(active_colony="forge", safety_score=0.85)
    >>> color = ColonyColor.for_colony("forge")
    >>> print(color.hex)  # #FFB347

Created: January 5, 2026
Author: Kagami / Byzantine Consensus
License: MIT
"""

from kagami.core.orb.colors import ColonyColor, get_colony_color
from kagami.core.orb.constants import (
    LED_ZONE_MAPPING,
    SPATIAL_ZONES,
    SpatialZone,
)
from kagami.core.orb.events import (
    OrbInteractionEvent,
    OrbStateChangedEvent,
    create_orb_interaction,
    create_state_changed_event,
)
from kagami.core.orb.state import (
    OrbActivity,
    OrbPosition,
    OrbState,
    create_orb_state,
    get_orb_state,
)
from kagami.core.orb.state_machine import (
    InvalidTransitionError,
    OrbStateMachine,
    TransitionResult,
)

__all__ = [
    "LED_ZONE_MAPPING",
    "SPATIAL_ZONES",
    "ColonyColor",
    "InvalidTransitionError",
    "OrbActivity",
    "OrbInteractionEvent",
    "OrbPosition",
    "OrbState",
    "OrbStateChangedEvent",
    "OrbStateMachine",
    "SpatialZone",
    "TransitionResult",
    "create_orb_interaction",
    "create_orb_state",
    "create_state_changed_event",
    "get_colony_color",
    "get_orb_state",
]
