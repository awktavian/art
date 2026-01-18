"""Jill Welcome Home — Person-specific welcome with path lighting to bedroom.

When Jill arrives home (detected by face recognition at entry cameras),
lights up a welcoming path from the door to the bedroom.

The sequence:
1. Entry lights up immediately (she's detected here)
2. Living Room follows (wayfinding)
3. Hallway illuminates (transition)
4. Primary Bedroom awaits (destination)

Created: January 2, 2026
For Jill Campbell — warmth expressed differently, but warm.
h(x) >= 0 always.
"""

from __future__ import annotations

import logging

from kagami_smarthome.context.context_engine import CircadianPhase, HomeContext
from kagami_smarthome.execution.receipted_executor import Action
from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine

logger = logging.getLogger(__name__)


class JillWelcomeHomeRoutine(AdaptiveRoutine):
    """Person-specific welcome routine for Jill with path lighting.

    Detects Jill's arrival via identity detection and creates
    a warm, lit path from entry to bedroom.

    Path: Entry → Living Room → Hallway → Primary Bedroom
    Timing: Staggered activation for elegant flow
    Lighting: Warm tones, adaptive to time of day
    """

    id = "jill_welcome_home"
    name = "Jill Welcome Home"
    description = "Light a warm path for Jill from entry to bedroom"
    safety_critical = False

    params = {
        # Light levels per room (adaptive to time)
        "entry_level": 60,
        "living_room_level": 50,
        "hallway_level": 40,
        "bedroom_level": 35,
        # Late night levels (softer)
        "late_night_entry_level": 30,
        "late_night_living_room_level": 20,
        "late_night_hallway_level": 15,
        "late_night_bedroom_level": 15,
        # Timing
        "stagger_delay_ms": 400,  # Delay between room activations
        # Behavior
        "announce": False,  # Jill prefers quiet arrival
        "open_bedroom_shades": False,  # Keep closed if late
    }

    param_ranges = {
        "entry_level": (30, 80),
        "living_room_level": (20, 70),
        "hallway_level": (20, 60),
        "bedroom_level": (20, 60),
        "stagger_delay_ms": (100, 1000),
    }

    # Jill's identity
    JILL_IDENTITY_ID = "jill_campbell"

    # Path from entry to bedroom
    PATH_ROOMS = ["Entry", "Living Room", "Hallway", "Primary Bedroom"]

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Trigger when Jill arrives home.

        Uses identity detection to specifically recognize Jill.
        """
        # Need controller to check identity detection
        if not hasattr(context, "_controller"):
            return False, ""

        try:
            # Check if Jill just arrived (via presence engine)
            controller = context._controller
            if not controller:
                return False, ""

            # Check presence engine for Jill's identity
            presence_engine = getattr(controller, "_presence_engine", None)
            if not presence_engine:
                # Fallback: check generic arrival
                if context.owner_just_arrived:
                    # Could be Jill, use generic welcome
                    return False, "generic_arrival"
                return False, ""

            # Check if Jill is detected and just arrived
            people = presence_engine.get_people_home()
            jill_detected = any(p.get("identity_id") == self.JILL_IDENTITY_ID for p in people)

            if not jill_detected:
                return False, ""

            # Check if she's at an entry point (just arrived)
            jill_location = presence_engine.get_person_location(self.JILL_IDENTITY_ID)
            if jill_location not in ("Entry", "Deck", "Garage", "Front Door"):
                return False, ""

            # Check if this is a fresh arrival (not already home)
            # Use arrival timestamp if available
            for person in people:
                if person.get("identity_id") == self.JILL_IDENTITY_ID:
                    last_seen = person.get("last_seen", 0)
                    # Only trigger if seen within last 30 seconds (fresh arrival)
                    import time

                    if (time.time() - last_seen) > 30:
                        return False, "not_fresh_arrival"
                    break

            logger.info(f"Jill detected at {jill_location} - triggering welcome path")
            return True, f"jill_arrived_at_{jill_location}"

        except Exception as e:
            logger.debug(f"Jill welcome check error: {e}")
            return False, ""

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute path lighting sequence for Jill.

        Creates staggered light activations from entry to bedroom.
        """
        actions: list[Action] = []

        # Determine light levels based on time
        is_late = context.circadian_phase in (
            CircadianPhase.LATE_NIGHT,
            CircadianPhase.NIGHT,
        )

        # Select levels
        if is_late:
            levels = {
                "Entry": self.params["late_night_entry_level"],
                "Living Room": self.params["late_night_living_room_level"],
                "Hallway": self.params["late_night_hallway_level"],
                "Primary Bedroom": self.params["late_night_bedroom_level"],
            }
        else:
            levels = {
                "Entry": self.params["entry_level"],
                "Living Room": self.params["living_room_level"],
                "Hallway": self.params["hallway_level"],
                "Primary Bedroom": self.params["bedroom_level"],
            }

        # Create staggered lighting actions
        # Note: The executor will run these sequentially;
        # we embed the stagger timing in metadata for the executor to handle
        stagger_ms = self.params["stagger_delay_ms"]

        for i, room in enumerate(self.PATH_ROOMS):
            level = levels.get(room, 40)

            # Add action with stagger timing hint
            action = Action(
                "set_lights",
                {
                    "level": level,
                    "rooms": [room],
                    # Color temperature: warm (3000K) for welcoming feel
                    "color_temp": 3000 if not is_late else 2700,
                    # Timing hint for smart execution
                    "_stagger_delay_ms": i * stagger_ms,
                },
            )
            actions.append(action)

        # Optional: open bedroom shades if morning
        if self.params["open_bedroom_shades"] and context.circadian_phase == CircadianPhase.MORNING:
            actions.append(Action("open_shades", {"rooms": ["Primary Bedroom"]}))

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """Rollback: dim the lights."""
        if action.type == "set_lights":
            return Action("set_lights", {"level": 10, "rooms": action.params.get("rooms", [])})
        return None


__all__ = ["JillWelcomeHomeRoutine"]
