"""Goodnight Routine — Intent-Based Bedtime Sequence.

MIGRATED: January 2, 2026 — Uses intent automation system.
No more hardcoded room lists or device assumptions.

Created: December 31, 2025
Updated: January 2, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

from kagami_smarthome.context.context_engine import HomeContext
from kagami_smarthome.execution.receipted_executor import Action
from kagami_smarthome.intent_automation import AutomationIntent, Capability
from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine


class GoodnightRoutine(AdaptiveRoutine):
    """Adaptive bedtime routine using intent-based automation.

    NOW USES CAPABILITY DISCOVERY:
    - Only locks if HAS_LOCKS capability exists
    - Only dims lights if HAS_LIGHTS exists
    - Only closes shades if HAS_SHADES exists
    - Skips gracefully for missing capabilities

    No hardcoded room lists — discovers rooms dynamically.
    """

    id = "goodnight"
    name = "Goodnight"
    description = "Prepare house for sleep using intent automation"
    safety_critical = True  # Involves locking doors

    # Intent to execute
    intent = AutomationIntent.PREPARE_SLEEP

    # Required capabilities (at minimum)
    required_capabilities = [Capability.HAS_LIGHTS]

    # Optional capabilities that enhance the routine
    optional_capabilities = [
        Capability.HAS_LOCKS,
        Capability.HAS_SHADES,
        Capability.HAS_ALARM,
        Capability.HAS_HVAC,
        Capability.HAS_BED_CLIMATE,
        Capability.HAS_VOICE_ANNOUNCE,
    ]

    params = {
        "lock_doors": True,
        "arm_security": True,
        "turn_off_lights": True,
        "close_shades": True,
        "bedroom_light_level": 5,
        "hvac_sleep_temp_f": 68,
        "announce": True,
    }

    param_ranges = {
        "bedroom_light_level": (0, 20),
        "hvac_sleep_temp_f": (65, 72),
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger when owner goes to bed."""
        if context.owner_in_bed and context.circadian_phase.value in ("night", "late_night"):
            return True, "owner_in_bed"
        return False, ""

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute goodnight actions using intent system.

        Instead of hardcoded room lists, we emit a single intent action
        that the IntentExecutor handles with capability discovery.
        """
        actions: list[Action] = []

        # Build context for intent execution
        intent_context = {
            "bedroom_light_level": self.params["bedroom_light_level"],
            "hvac_sleep_temp_f": self.params["hvac_sleep_temp_f"],
            "lock_doors": self.params["lock_doors"],
            "arm_security": self.params["arm_security"] and not context.guests_present,
            "close_shades": self.params["close_shades"],
            "announce": self.params["announce"],
        }

        # Single intent action that handles everything capability-aware
        actions.append(
            Action(
                "execute_intent",
                {
                    "intent": AutomationIntent.PREPARE_SLEEP.value,
                    "context": intent_context,
                },
            )
        )

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """Get rollback action - limited for safety."""
        if action.type == "execute_intent":
            # Rollback: wake up mode (lights on, but don't unlock)
            return Action(
                "execute_intent",
                {
                    "intent": AutomationIntent.WAKE_UP.value,
                    "context": {"preserve_locks": True},
                },
            )
        return None


__all__ = ["GoodnightRoutine"]
