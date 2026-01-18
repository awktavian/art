"""Situation Action Orchestrator — ACTION LAYER of the Predictive Hierarchy.

OPTIMAL ARCHITECTURE (4-Layer Predictive Hierarchy):
=====================================================
Based on OODA, Predictive Processing, and Active Inference research.

┌────────────────────────────────────────────────────────────────────────┐
│                      PREDICTIVE HIERARCHY                              │
│                                                                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│  │  SENSE   │◄──►│ PATTERN  │◄──►│ CONTEXT  │◄──►│  ACTION  │        │
│  │  Layer   │    │  Layer   │    │  Layer   │    │  (THIS)  │        │
│  │          │    │          │    │          │    │          │        │
│  │ Raw data │    │ Temporal │    │ Meaning  │    │ Goals    │        │
│  │ polling  │    │ predict  │    │ & state  │    │ & drives │        │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│        │               │               │               │              │
│        └───────────────┴───────────────┴───────────────┘              │
│                     Shared State (OrganismRSSM)                        │
└────────────────────────────────────────────────────────────────────────┘

This module is the ACTION LAYER:
    - Receives: Context (phase, urgency) + Pattern predictions
    - Produces: Physical/digital actions
    - Feeds back to: Sense layer (actions change environment)

TRIGGERS (multiple sources, not just phase changes):
1. Phase transitions (SLEEPING → WAKING)
2. Pattern predictions (predict departure → prepare car)
3. Urgency changes (NORMAL → URGENT)
4. Explicit goals from AutonomousGoalEngine

Actions:
    - WAKING: Open shades, gentle lights, start morning playlist
    - WORKING: Focus lighting, close shades, mute audio
    - RELAXING: Dim lights, fireplace on, relax playlist
    - SLEEPING: Goodnight scene (all off, locks engaged)

Philosophy:
    The home anticipates needs. The right automation at the right moment
    feels like magic — because it's predicted, not commanded.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

from .situation_awareness import SituationPhase

logger = logging.getLogger(__name__)


@dataclass
class AutomationAction:
    """A single automation action."""

    name: str
    execute: Callable[[SmartHomeController], Coroutine[Any, Any, Any]]
    description: str = ""
    requires_presence: bool = True  # Only execute if Tim is home
    time_window: tuple[int, int] | None = None  # (hour_start, hour_end) or None for any time


@dataclass
class PhaseAutomation:
    """Automation triggered by entering a phase."""

    phase: SituationPhase
    actions: list[AutomationAction]
    cooldown_seconds: int = 300  # Minimum time between triggers
    enabled: bool = True


@dataclass
class PhaseTransitionEvent:
    """Record of a phase transition."""

    from_phase: SituationPhase
    to_phase: SituationPhase
    timestamp: float
    actions_executed: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


# =============================================================================
# PHASE AUTOMATION DEFINITIONS
# =============================================================================


def _define_phase_automations() -> dict[SituationPhase, PhaseAutomation]:
    """Define automations for each phase.

    These are the default automations — Tim can customize via preferences.
    """
    return {
        SituationPhase.WAKING: PhaseAutomation(
            phase=SituationPhase.WAKING,
            actions=[
                AutomationAction(
                    name="open_bedroom_shades",
                    execute=lambda c: c.open_shades(rooms=["Primary Bedroom"]),
                    description="Let in natural light",
                    time_window=(5, 10),  # Only 5am-10am
                ),
                AutomationAction(
                    name="gentle_bedroom_lights",
                    execute=lambda c: c.set_lights(30, rooms=["Primary Bedroom"]),
                    description="Gentle wake-up lighting",
                    time_window=(5, 8),  # Only 5am-8am
                ),
                AutomationAction(
                    name="morning_playlist",
                    execute=lambda c: c.spotify_play_playlist("morning"),
                    description="Start morning playlist",
                    time_window=(6, 9),
                ),
            ],
            cooldown_seconds=14400,  # 4 hours (once per wake cycle)
        ),
        SituationPhase.MORNING_ROUTINE: PhaseAutomation(
            phase=SituationPhase.MORNING_ROUTINE,
            actions=[
                AutomationAction(
                    name="kitchen_lights",
                    execute=lambda c: c.set_lights(70, rooms=["Kitchen"]),
                    description="Bright kitchen for breakfast",
                    time_window=(5, 10),
                ),
            ],
            cooldown_seconds=14400,
        ),
        SituationPhase.WORKING: PhaseAutomation(
            phase=SituationPhase.WORKING,
            actions=[
                AutomationAction(
                    name="office_focus_lighting",
                    execute=lambda c: c.set_lights(70, rooms=["Office"]),
                    description="Focus lighting for work",
                ),
                AutomationAction(
                    name="close_office_shades",
                    execute=lambda c: c.close_shades(rooms=["Office"]),
                    description="Reduce glare on screens",
                    time_window=(9, 17),
                ),
            ],
            cooldown_seconds=7200,  # 2 hours
        ),
        SituationPhase.FOCUSED: PhaseAutomation(
            phase=SituationPhase.FOCUSED,
            actions=[
                AutomationAction(
                    name="focus_playlist",
                    execute=lambda c: c.spotify_play_playlist("focus"),
                    description="Start focus playlist",
                ),
            ],
            cooldown_seconds=3600,  # 1 hour
        ),
        SituationPhase.BREAK: PhaseAutomation(
            phase=SituationPhase.BREAK,
            actions=[
                AutomationAction(
                    name="relax_lights_slightly",
                    execute=lambda c: c.set_lights(50, rooms=["Office"]),
                    description="Slightly dimmer for break",
                ),
            ],
            cooldown_seconds=1800,  # 30 min
        ),
        SituationPhase.RELAXING: PhaseAutomation(
            phase=SituationPhase.RELAXING,
            actions=[
                AutomationAction(
                    name="dim_living_room",
                    execute=lambda c: c.set_lights(40, rooms=["Living Room"]),
                    description="Cozy ambient lighting",
                    time_window=(17, 23),
                ),
                # DISABLED: Fireplace should be manual only - auto-on is unsafe
                # AutomationAction(
                #     name="fireplace_on",
                #     execute=lambda c: c.fireplace_on(),
                #     description="Cozy fireplace",
                #     time_window=(17, 22),
                # ),
            ],
            cooldown_seconds=7200,  # 2 hours
        ),
        SituationPhase.WINDING_DOWN: PhaseAutomation(
            phase=SituationPhase.WINDING_DOWN,
            actions=[
                AutomationAction(
                    name="dim_all_lights",
                    execute=lambda c: c.set_lights(20),
                    description="Prepare for sleep",
                    time_window=(20, 24),
                ),
                AutomationAction(
                    name="evening_playlist",
                    execute=lambda c: c.spotify_play_playlist("evening"),
                    description="Relaxing evening music",
                    time_window=(19, 23),
                ),
            ],
            cooldown_seconds=14400,  # 4 hours
        ),
        SituationPhase.SLEEPING: PhaseAutomation(
            phase=SituationPhase.SLEEPING,
            actions=[
                AutomationAction(
                    name="goodnight_scene",
                    execute=lambda c: c.goodnight(),
                    description="Full goodnight scene",
                    time_window=(21, 6),  # 9pm-6am (wraps around midnight)
                ),
            ],
            cooldown_seconds=21600,  # 6 hours (once per night)
        ),
    }


# =============================================================================
# SITUATION ACTION ORCHESTRATOR
# =============================================================================


class SituationActionOrchestrator:
    """Execute automations on situation phase changes.

    This is the proactive layer — making the home anticipatory.

    Usage:
        orchestrator = SituationActionOrchestrator()
        await orchestrator.initialize()

        # When situation changes:
        await orchestrator.on_phase_change(old_phase, new_phase)

        # Or integrate with SituationAwarenessEngine
        await orchestrator.subscribe_to_situation_engine(engine)
    """

    def __init__(self) -> None:
        self._controller: SmartHomeController | None = None
        self._automations: dict[SituationPhase, PhaseAutomation] = {}
        self._last_triggers: dict[SituationPhase, float] = {}  # Phase → last trigger time
        self._history: list[PhaseTransitionEvent] = []
        self._max_history = 100
        self._presence: str = "home"  # Assumed presence
        self._enabled = True

        # Statistics
        self._total_triggers = 0
        self._total_actions = 0
        self._skipped_cooldown = 0
        self._skipped_presence = 0
        self._skipped_time = 0

    async def initialize(self, controller: SmartHomeController | None = None) -> bool:
        """Initialize the orchestrator.

        Args:
            controller: SmartHomeController (or lazy-load)

        Returns:
            True if initialization successful
        """
        # Load automations
        self._automations = _define_phase_automations()

        # Load controller
        if controller is not None:
            self._controller = controller
        else:
            try:
                from kagami_smarthome import get_smart_home

                self._controller = await get_smart_home()
            except Exception as e:
                logger.warning(f"SmartHome not available: {e}")
                return False

        logger.info(
            f"✅ SituationActionOrchestrator initialized: "
            f"{len(self._automations)} phase automations"
        )
        return True

    def update_presence(self, presence: str) -> None:
        """Update presence state.

        Args:
            presence: "home", "away", "sleeping", etc.
        """
        self._presence = presence

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable all automations."""
        self._enabled = enabled
        logger.info(f"🎚️ SituationActionOrchestrator {'enabled' if enabled else 'disabled'}")

    async def on_phase_change(
        self,
        old_phase: SituationPhase,
        new_phase: SituationPhase,
        force: bool = False,
    ) -> PhaseTransitionEvent:
        """Handle phase transition and trigger automations.

        Args:
            old_phase: Previous situation phase
            new_phase: New situation phase
            force: Bypass cooldowns and preconditions

        Returns:
            PhaseTransitionEvent with execution details
        """
        event = PhaseTransitionEvent(
            from_phase=old_phase,
            to_phase=new_phase,
            timestamp=time.time(),
        )

        # Check if orchestrator is enabled
        if not self._enabled and not force:
            event.skipped_reason = "orchestrator_disabled"
            self._history.append(event)
            return event

        # Get automation for new phase
        automation = self._automations.get(new_phase)
        if not automation or not automation.enabled:
            event.skipped_reason = "no_automation_defined"
            self._history.append(event)
            return event

        # Check cooldown
        if not force:
            last_trigger = self._last_triggers.get(new_phase, 0)
            time_since = time.time() - last_trigger
            if time_since < automation.cooldown_seconds:
                event.skipped_reason = (
                    f"cooldown ({automation.cooldown_seconds - time_since:.0f}s remaining)"
                )
                self._skipped_cooldown += 1
                self._history.append(event)
                logger.debug(f"⏰ Skipping {new_phase.value}: {event.skipped_reason}")
                return event

        self._total_triggers += 1
        self._last_triggers[new_phase] = time.time()

        # Execute actions
        executed = await self._execute_automation(automation, force)
        event.actions_executed = executed

        # Trim history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        logger.info(
            f"🏠 Phase change: {old_phase.value} → {new_phase.value} | "
            f"Executed: {len(executed)} actions"
        )

        return event

    async def _execute_automation(
        self, automation: PhaseAutomation, force: bool = False
    ) -> list[str]:
        """Execute all actions in an automation.

        Args:
            automation: PhaseAutomation to execute
            force: Bypass preconditions

        Returns:
            List of executed action names
        """
        if self._controller is None:
            logger.warning("No controller available for automation")
            return []

        executed: list[str] = []
        current_hour = datetime.now().hour

        for action in automation.actions:
            # Check presence
            if action.requires_presence and self._presence == "away" and not force:
                self._skipped_presence += 1
                continue

            # Check time window
            if action.time_window and not force:
                start_hour, end_hour = action.time_window
                if start_hour <= end_hour:
                    in_window = start_hour <= current_hour < end_hour
                else:
                    # Wraps around midnight (e.g., 21-6)
                    in_window = current_hour >= start_hour or current_hour < end_hour

                if not in_window:
                    self._skipped_time += 1
                    continue

            # Execute action
            try:
                await action.execute(self._controller)
                executed.append(action.name)
                self._total_actions += 1
                logger.debug(f"  ✅ {action.name}: {action.description}")
            except Exception as e:
                logger.error(f"  ❌ {action.name} failed: {e}")

        return executed

    async def subscribe_to_situation_engine(
        self,
        engine: Any,  # SituationAwarenessEngine
    ) -> None:
        """Subscribe to SituationAwarenessEngine for automatic phase change handling.

        Args:
            engine: SituationAwarenessEngine instance
        """
        if hasattr(engine, "subscribe"):
            await engine.subscribe(self._on_situation_update)
            logger.info("📡 Subscribed to SituationAwarenessEngine")

    async def _on_situation_update(self, old_situation: Any, new_situation: Any) -> None:
        """Handle situation update from engine."""
        if hasattr(old_situation, "phase") and hasattr(new_situation, "phase"):
            if old_situation.phase != new_situation.phase:
                await self.on_phase_change(old_situation.phase, new_situation.phase)

    def get_automation(self, phase: SituationPhase) -> PhaseAutomation | None:
        """Get automation for a phase."""
        return self._automations.get(phase)

    def set_automation_enabled(self, phase: SituationPhase, enabled: bool) -> None:
        """Enable/disable automation for a specific phase."""
        if phase in self._automations:
            self._automations[phase].enabled = enabled
            logger.info(f"🎚️ {phase.value} automation {'enabled' if enabled else 'disabled'}")

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "enabled": self._enabled,
            "presence": self._presence,
            "controller_connected": self._controller is not None,
            "total_triggers": self._total_triggers,
            "total_actions": self._total_actions,
            "skipped_cooldown": self._skipped_cooldown,
            "skipped_presence": self._skipped_presence,
            "skipped_time": self._skipped_time,
            "automations_defined": len(self._automations),
            "history_size": len(self._history),
        }

    def get_history(self, limit: int = 10) -> list[PhaseTransitionEvent]:
        """Get recent phase transition history."""
        return self._history[-limit:]


# Singleton
_situation_orchestrator: SituationActionOrchestrator | None = None


async def get_situation_orchestrator() -> SituationActionOrchestrator:
    """Get global SituationActionOrchestrator instance."""
    global _situation_orchestrator
    if _situation_orchestrator is None:
        _situation_orchestrator = SituationActionOrchestrator()
        await _situation_orchestrator.initialize()
    return _situation_orchestrator


def reset_situation_orchestrator() -> None:
    """Reset singleton (for testing)."""
    global _situation_orchestrator
    _situation_orchestrator = None


__all__ = [
    "AutomationAction",
    "PhaseAutomation",
    "PhaseTransitionEvent",
    "SituationActionOrchestrator",
    "get_situation_orchestrator",
    "reset_situation_orchestrator",
]
