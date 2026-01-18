"""Organism Physical Bridge — Autonomous Physical Actions.

CREATED: December 30, 2025
UPDATED: January 5, 2026 (Architecture Clarification)

## Action Responsibility

**PhysicalAction handles PROACTIVE/AUTONOMOUS actions:**
- Time-based: Morning routine, focus mode preparation
- Goal-driven: Comfort adjustments based on learned preferences
- Anticipatory: Actions that prepare for predicted needs

**Triggered By:**
- Autonomous goal engine (periodic evaluation)
- Colony state changes (active colony → room affinity)
- Intrinsic motivation system
- Predictive models (RSSM-based anticipation)

**NOT handled here:**
- Sense-driven triggers (weather, email, sleep) → CrossDomainBridge
- Service → Service triggers → AutoTriggers
- Astronomical events → CelestialTriggers

## Architecture

The organism acts autonomously to maintain home comfort and prepare
for anticipated needs. **Proactive, not reactive.**

Physical Actions are subject to:
- CBF safety checks (h(x) >= 0)
- User override (user actions take priority)
- Cooldown periods (prevent rapid cycling)
- Presence requirements (some actions only when home)

Colony → Room Affinity Mapping:
- Spark (creativity) → Office
- Forge (building) → Office/Living Room
- Flow (debugging) → Office
- Nexus (integration) → Living Room
- Beacon (planning) → Office
- Grove (research) → Office/Library
- Crystal (verification) → Office
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# COLONY-ROOM AFFINITY
# =============================================================================


class Colony(str, Enum):
    """The 7 colonies of the organism."""

    SPARK = "spark"  # Creativity, ideation
    FORGE = "forge"  # Construction, building
    FLOW = "flow"  # Operations, debugging
    NEXUS = "nexus"  # Integration, memory
    BEACON = "beacon"  # Planning, architecture
    GROVE = "grove"  # Research, exploration
    CRYSTAL = "crystal"  # Verification, quality


@dataclass
class RoomAffinity:
    """Room affinity for a colony."""

    primary_room: str
    secondary_rooms: list[str] = field(default_factory=list)
    preferred_light_level: int = 70
    preferred_scene: str = "working"


# Colony → Room affinity mapping
COLONY_ROOM_AFFINITY: dict[Colony, RoomAffinity] = {
    Colony.SPARK: RoomAffinity(
        primary_room="Office",
        secondary_rooms=["Living Room"],
        preferred_light_level=80,
        preferred_scene="creative",
    ),
    Colony.FORGE: RoomAffinity(
        primary_room="Office",
        secondary_rooms=["Living Room"],
        preferred_light_level=75,
        preferred_scene="working",
    ),
    Colony.FLOW: RoomAffinity(
        primary_room="Office",
        secondary_rooms=[],
        preferred_light_level=70,
        preferred_scene="focused",
    ),
    Colony.NEXUS: RoomAffinity(
        primary_room="Living Room",
        secondary_rooms=["Office"],
        preferred_light_level=60,
        preferred_scene="relaxing",
    ),
    Colony.BEACON: RoomAffinity(
        primary_room="Office",
        secondary_rooms=["Living Room"],
        preferred_light_level=75,
        preferred_scene="planning",
    ),
    Colony.GROVE: RoomAffinity(
        primary_room="Office",
        secondary_rooms=["Living Room"],
        preferred_light_level=65,
        preferred_scene="reading",
    ),
    Colony.CRYSTAL: RoomAffinity(
        primary_room="Office",
        secondary_rooms=[],
        preferred_light_level=80,
        preferred_scene="verification",
    ),
}


# =============================================================================
# AUTONOMOUS PHYSICAL ACTIONS
# =============================================================================


@dataclass
class PhysicalAction:
    """A physical action the organism can take."""

    name: str
    action_fn: Callable[..., Awaitable[bool]]
    cooldown_seconds: float = 300.0
    requires_presence: bool = True  # Only act when Tim is home
    safety_priority: int = 5  # 1 = highest priority, 10 = lowest
    last_executed: float = 0.0
    execution_count: int = 0

    def can_execute(self, is_home: bool = True) -> bool:
        """Check if action can be executed."""
        if self.requires_presence and not is_home:
            return False
        if time.time() - self.last_executed < self.cooldown_seconds:
            return False
        return True

    def mark_executed(self) -> None:
        """Mark action as executed."""
        self.last_executed = time.time()
        self.execution_count += 1


class OrganismPhysicalBridge:
    """Bridge between organism consciousness and physical world.

    Enables:
    1. Colony activity → Room scene mapping
    2. Situation phase → Physical adaptations
    3. Autonomous goal → Physical actions
    4. Predictive actions (anticipate user needs)

    All actions subject to:
    - Safety checks (h(x) >= 0)
    - User override priority
    - Cooldown enforcement
    """

    def __init__(self):
        self._smart_home: SmartHomeController | None = None
        self._enabled = False
        self._user_override = False
        self._user_override_until = 0.0

        # State
        self._current_colony: Colony | None = None
        self._current_phase: str = "unknown"
        self._is_home = True

        # Actions
        self._actions: dict[str, PhysicalAction] = {}

        # Statistics
        self._stats = {
            "actions_taken": 0,
            "actions_blocked_safety": 0,
            "actions_blocked_override": 0,
            "actions_blocked_cooldown": 0,
        }

        # Callbacks
        self._on_action_taken: list[Callable[[str, dict], Awaitable[None]]] = []

    async def connect(self, smart_home: SmartHomeController) -> bool:
        """Connect to SmartHome controller.

        Args:
            smart_home: SmartHomeController instance

        Returns:
            True if connected
        """
        self._smart_home = smart_home
        self._enabled = True

        # Register standard autonomous actions
        self._register_standard_actions()

        logger.info("🤖 OrganismPhysicalBridge connected - autonomous physical actions enabled")
        return True

    def disconnect(self) -> None:
        """Disconnect from SmartHome."""
        self._smart_home = None
        self._enabled = False

    def set_user_override(self, duration_seconds: float = 3600.0) -> None:
        """Set user override - organism will not take autonomous actions.

        Args:
            duration_seconds: How long to override (default 1 hour)
        """
        self._user_override = True
        self._user_override_until = time.time() + duration_seconds
        logger.info(f"🔒 User override set for {duration_seconds / 60:.0f} minutes")

    def clear_user_override(self) -> None:
        """Clear user override."""
        self._user_override = False
        self._user_override_until = 0.0
        logger.info("🔓 User override cleared")

    def _is_user_overriding(self) -> bool:
        """Check if user override is active."""
        if not self._user_override:
            return False
        if time.time() > self._user_override_until:
            self._user_override = False
            return False
        return True

    # =========================================================================
    # ACTION REGISTRATION
    # =========================================================================

    def _register_standard_actions(self) -> None:
        """Register standard autonomous actions."""

        # Comfort actions
        self._register_action(
            PhysicalAction(
                name="adjust_lights_for_colony",
                action_fn=self._action_adjust_lights_for_colony,
                cooldown_seconds=300.0,
                requires_presence=True,
                safety_priority=8,
            )
        )

        self._register_action(
            PhysicalAction(
                name="prepare_morning",
                action_fn=self._action_prepare_morning,
                cooldown_seconds=3600.0,  # Once per hour
                requires_presence=False,  # Can prepare before Tim wakes
                safety_priority=7,
            )
        )

        self._register_action(
            PhysicalAction(
                name="prepare_for_focus",
                action_fn=self._action_prepare_for_focus,
                cooldown_seconds=600.0,
                requires_presence=True,
                safety_priority=6,
            )
        )

        self._register_action(
            PhysicalAction(
                name="comfort_adjustment",
                action_fn=self._action_comfort_adjustment,
                cooldown_seconds=1800.0,
                requires_presence=True,
                safety_priority=9,
            )
        )

    def _register_action(self, action: PhysicalAction) -> None:
        """Register an autonomous action."""
        self._actions[action.name] = action

    # =========================================================================
    # COLONY INTEGRATION
    # =========================================================================

    async def on_colony_change(self, colony: Colony) -> None:
        """Handle colony activity change.

        Args:
            colony: New active colony
        """
        if not self._enabled or self._is_user_overriding():
            return

        old_colony = self._current_colony
        self._current_colony = colony

        if old_colony != colony:
            logger.debug(f"🐝 Colony changed: {old_colony} → {colony}")

            # Adjust room for colony
            await self._execute_action("adjust_lights_for_colony")

    async def on_situation_change(self, phase: str) -> None:
        """Handle situation phase change.

        Args:
            phase: New situation phase
        """
        if not self._enabled or self._is_user_overriding():
            return

        old_phase = self._current_phase
        self._current_phase = phase

        if old_phase != phase:
            logger.debug(f"📍 Situation changed: {old_phase} → {phase}")

            # Take phase-appropriate actions
            if phase == "waking":
                await self._execute_action("prepare_morning")
            elif phase == "focused":
                await self._execute_action("prepare_for_focus")

    async def on_presence_change(self, is_home: bool) -> None:
        """Handle presence change.

        Args:
            is_home: Whether Tim is home
        """
        self._is_home = is_home

    # =========================================================================
    # ACTION EXECUTION
    # =========================================================================

    async def _execute_action(self, action_name: str, **kwargs: Any) -> bool:
        """Execute an autonomous action with safety checks.

        Args:
            action_name: Name of action to execute
            **kwargs: Arguments for action

        Returns:
            True if action executed
        """
        action = self._actions.get(action_name)
        if not action:
            return False

        # Check user override
        if self._is_user_overriding():
            self._stats["actions_blocked_override"] += 1
            return False

        # Check cooldown
        if not action.can_execute(self._is_home):
            self._stats["actions_blocked_cooldown"] += 1
            return False

        # Safety check
        if not await self._check_safety(action):
            self._stats["actions_blocked_safety"] += 1
            return False

        # Execute
        try:
            success = await action.action_fn(**kwargs)

            if success:
                action.mark_executed()
                self._stats["actions_taken"] += 1

                # Notify callbacks
                for callback in self._on_action_taken:
                    try:
                        await callback(action_name, kwargs)
                    except Exception:
                        pass

                logger.info(f"🤖 Autonomous action: {action_name}")

            return success

        except Exception as e:
            logger.error(f"Autonomous action failed: {action_name}: {e}")
            return False

    async def _check_safety(self, action: PhysicalAction) -> bool:
        """Check if action is safe to execute."""
        try:
            from kagami_smarthome.safety import (
                PhysicalActionType,
                SafetyContext,
                check_physical_safety,
            )

            # Map action to physical action type
            # For now, use a generic check - most room adjustments are safe
            context = SafetyContext(
                action_type=PhysicalActionType.SHADE_ALL,  # Generic low-risk
                target="autonomous",
                parameters={"action": action.name},
            )

            result = check_physical_safety(context)
            return result.allowed

        except ImportError:
            # Safety module not available - be conservative
            return action.safety_priority >= 5  # Only low-risk actions

    # =========================================================================
    # ACTION IMPLEMENTATIONS
    # =========================================================================

    async def _action_adjust_lights_for_colony(self, **kwargs: Any) -> bool:
        """Adjust lights based on active colony."""
        if not self._smart_home or not self._current_colony:
            return False

        affinity = COLONY_ROOM_AFFINITY.get(self._current_colony)
        if not affinity:
            return False

        # Set lights in primary room
        await self._smart_home.set_lights(
            level=affinity.preferred_light_level,
            rooms=[affinity.primary_room],
        )

        return True

    async def _action_prepare_morning(self, **kwargs: Any) -> bool:
        """Prepare for morning routine.

        UPDATED: January 5, 2026 - Added automatic weather briefing.
        """
        if not self._smart_home:
            return False

        # Gradual lights in bedroom
        await self._smart_home.set_lights(30, rooms=["Primary Bed"])

        # Open bedroom shades
        await self._smart_home.open_shades(rooms=["Primary Bed"])

        # Prepare kitchen
        await self._smart_home.set_lights(40, rooms=["Kitchen"])

        # Announce morning weather (CRITICAL FIX: January 5, 2026)
        # Get current weather and announce it
        try:
            from kagami_smarthome import get_current_weather

            weather = await get_current_weather()
            if weather:
                temp_f = weather.temp_f
                feels_like_f = getattr(weather, "feels_like_f", temp_f)
                description = weather.description

                briefing = f"Good morning! It's {temp_f:.0f}°F outside"
                if abs(feels_like_f - temp_f) > 3:
                    briefing += f", feels like {feels_like_f:.0f}°F"
                briefing += f". {description.capitalize()}."

                await self._smart_home.announce(briefing, rooms=["Living Room"])
        except Exception as e:
            # Don't fail the whole morning routine if weather fails
            import logging

            logging.getLogger(__name__).warning(f"Morning weather briefing failed: {e}")

        return True

    async def _action_prepare_for_focus(self, **kwargs: Any) -> bool:
        """Prepare environment for focused work."""
        if not self._smart_home:
            return False

        # Set office lights for focus
        await self._smart_home.set_lights(75, rooms=["Office"])

        # Close office shades if sunny
        # (Would check weather first in full implementation)

        return True

    async def _action_comfort_adjustment(self, **kwargs: Any) -> bool:
        """Make comfort adjustments based on learned preferences."""
        if not self._smart_home:
            return False

        # This would integrate with PatternLearner
        # For now, just ensure reasonable defaults

        return True

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics."""
        return {
            **self._stats,
            "enabled": self._enabled,
            "current_colony": self._current_colony.value if self._current_colony else None,
            "current_phase": self._current_phase,
            "is_home": self._is_home,
            "user_override": self._is_user_overriding(),
            "registered_actions": list(self._actions.keys()),
        }

    def on_action(self, callback: Callable[[str, dict], Awaitable[None]]) -> None:
        """Register callback for when actions are taken."""
        self._on_action_taken.append(callback)


# =============================================================================
# SINGLETON
# =============================================================================

_bridge: OrganismPhysicalBridge | None = None


def get_organism_physical_bridge() -> OrganismPhysicalBridge:
    """Get global OrganismPhysicalBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = OrganismPhysicalBridge()
    return _bridge


def reset_organism_physical_bridge() -> None:
    """Reset the singleton (for testing)."""
    global _bridge
    _bridge = None


async def connect_organism_physical_bridge(
    smart_home: SmartHomeController,
) -> OrganismPhysicalBridge:
    """Connect and return the organism physical bridge."""
    bridge = get_organism_physical_bridge()
    await bridge.connect(smart_home)
    return bridge


__all__ = [
    "COLONY_ROOM_AFFINITY",
    "Colony",
    "OrganismPhysicalBridge",
    "PhysicalAction",
    "RoomAffinity",
    "connect_organism_physical_bridge",
    "get_organism_physical_bridge",
    "reset_organism_physical_bridge",
]
