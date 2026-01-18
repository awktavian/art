"""Sleep Detected Routine — Turn off lights when owner gets in bed at night.

This routine solves the 3AM-lights-on problem:
- Eight Sleep detects bed entry
- If it's late night (11pm-5am) → turn off all lights except soft bedroom glow
- If owner is already asleep (light/deep/REM) → ensure lights stay off

Created: January 2, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

from kagami_smarthome.context.context_engine import CircadianPhase, HomeContext
from kagami_smarthome.execution.receipted_executor import Action
from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine


class SleepDetectedRoutine(AdaptiveRoutine):
    """Routine that dims/turns off lights when owner gets in bed at night.

    Triggers when:
    - owner_in_bed becomes True
    - circadian_phase is NIGHT or LATE_NIGHT
    - No recent manual override (respects user intent)

    Actions:
    - Turn off all lights except bedroom
    - Dim bedroom to sleep level (default 0-5%)
    - Close bedroom shades if not already closed
    """

    id = "sleep_detected"
    name = "Sleep Detected"
    description = "Automatically dim lights when getting into bed at night"
    safety_critical = False  # Lights only, no security actions

    params = {
        "bedroom_sleep_level": 0,  # 0-5% default (off or very dim)
        "turn_off_other_rooms": True,
        "close_shades": True,
        "manual_override_cooldown_seconds": 1800,  # 30 min respect for manual changes
    }

    param_ranges = {
        "bedroom_sleep_level": (0, 10),
        "manual_override_cooldown_seconds": (300, 7200),
    }

    # Track previous in_bed state to detect transitions
    _was_in_bed: bool = False

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger when owner ENTERS bed during night hours."""
        # Only trigger during night/late_night phases
        if context.circadian_phase not in (CircadianPhase.NIGHT, CircadianPhase.LATE_NIGHT):
            self._was_in_bed = context.owner_in_bed
            return False, ""

        # Check for bed ENTRY (transition from not-in-bed to in-bed)
        just_entered_bed = context.owner_in_bed and not self._was_in_bed
        self._was_in_bed = context.owner_in_bed

        if not just_entered_bed:
            return False, ""

        # Respect manual overrides
        if context.last_manual_override:
            import time

            cooldown = self.params["manual_override_cooldown_seconds"]
            if (time.time() - context.last_manual_override) < cooldown:
                return False, "manual_override_active"

        return True, "owner_entered_bed_at_night"

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute sleep-time light adjustments."""
        actions: list[Action] = []

        # Turn off lights in common areas
        if self.params["turn_off_other_rooms"]:
            actions.append(
                Action(
                    "set_lights",
                    {
                        "level": 0,
                        "rooms": [
                            "Living Room",
                            "Kitchen",
                            "Dining",
                            "Office",
                            "Entry",
                            "Hallway",
                            "Garage",
                            "Deck",
                        ],
                    },
                )
            )

        # Dim bedroom to sleep level
        bedroom_level = self.params["bedroom_sleep_level"]
        actions.append(
            Action(
                "set_lights",
                {
                    "level": bedroom_level,
                    "rooms": ["Primary Bedroom"],
                },
            )
        )

        # Close bedroom shades
        if self.params["close_shades"]:
            actions.append(
                Action(
                    "close_shades",
                    {"rooms": ["Primary Bedroom"]},
                )
            )

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """Get rollback action — restore lights to low level."""
        if action.type == "set_lights":
            # Rollback: restore to dim but visible level
            return Action("set_lights", {"level": 20, "rooms": action.params.get("rooms", [])})
        return None


__all__ = ["SleepDetectedRoutine"]
