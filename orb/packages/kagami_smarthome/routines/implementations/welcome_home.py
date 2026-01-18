"""Welcome Home Routine — Intent-Based Greeting.

MIGRATED: January 2, 2026 — Uses intent automation system.
No more hardcoded room lists or device assumptions.

Created: December 31, 2025
Updated: January 2, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

from kagami_smarthome.context.context_engine import CircadianPhase, HomeContext
from kagami_smarthome.execution.receipted_executor import Action
from kagami_smarthome.intent_automation import AutomationIntent, Capability
from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine


class WelcomeHomeRoutine(AdaptiveRoutine):
    """Adaptive welcome routine using intent-based automation.

    NOW USES CAPABILITY DISCOVERY:
    - Only sets lights if HAS_LIGHTS exists
    - Only announces if HAS_VOICE_ANNOUNCE exists
    - Does NOT auto-disarm security (safety constraint)
    - Skips gracefully for missing capabilities

    No hardcoded room lists — discovers rooms dynamically.
    """

    id = "welcome_home"
    name = "Welcome Home"
    description = "Greet owner using intent automation"
    safety_critical = False

    # Intent to execute
    intent = AutomationIntent.WELCOME_HOME

    # Required capabilities (at minimum)
    required_capabilities = [Capability.HAS_LIGHTS]

    # Optional capabilities that enhance the routine
    optional_capabilities = [
        Capability.HAS_VOICE_ANNOUNCE,
        Capability.HAS_PRESENCE_DETECTION,
    ]

    params = {
        "dawn_level": 30,
        "day_level": 0,  # Natural light
        "evening_level": 60,
        "night_level": 20,
        "late_night_level": 10,
        "announce": True,
        # NOTE: disarm_security removed for safety — always require manual disarm
    }

    param_ranges = {
        "dawn_level": (10, 50),
        "day_level": (0, 30),
        "evening_level": (40, 80),
        "night_level": (10, 40),
        "late_night_level": (5, 20),
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger on owner arrival."""
        if context.owner_just_arrived:
            return True, "owner_arrived"
        return False, ""

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute welcome actions using intent system.

        Instead of hardcoded room lists, we emit a single intent action
        that the IntentExecutor handles with capability discovery.
        """
        actions: list[Action] = []

        # Determine light level based on circadian phase
        phase = context.circadian_phase
        level = {
            CircadianPhase.DAWN: self.params["dawn_level"],
            CircadianPhase.MORNING: self.params["day_level"],
            CircadianPhase.MIDDAY: self.params["day_level"],
            CircadianPhase.AFTERNOON: self.params["evening_level"],
            CircadianPhase.EVENING: self.params["evening_level"],
            CircadianPhase.NIGHT: self.params["night_level"],
            CircadianPhase.LATE_NIGHT: self.params["late_night_level"],
        }.get(phase, 50)

        # Adjust for weather (darker outside = brighter inside)
        if context.outdoor_light_level < 30:
            level = min(100, level + 20)

        # Adjust for guests
        if context.guests_present:
            level = min(100, level + 10)

        # Build context for intent execution
        intent_context = {
            "light_level": level,
            "announce": self.params["announce"],
            "circadian_phase": phase.value if phase else "unknown",
            "guests_present": context.guests_present,
        }

        # Single intent action that handles everything capability-aware
        actions.append(
            Action(
                "execute_intent",
                {
                    "intent": AutomationIntent.WELCOME_HOME.value,
                    "context": intent_context,
                },
            )
        )

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """Get rollback action."""
        if action.type == "execute_intent":
            # Rollback: turn lights off
            return Action(
                "execute_intent",
                {
                    "intent": AutomationIntent.GOODBYE.value,
                    "context": {"preserve_locks": True, "skip_arm": True},
                },
            )
        return None


__all__ = ["WelcomeHomeRoutine"]
