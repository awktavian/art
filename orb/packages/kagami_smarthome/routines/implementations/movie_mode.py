"""Movie Mode Routine — Home theater setup based on context.

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

from kagami_smarthome.context.context_engine import HomeContext
from kagami_smarthome.execution.receipted_executor import Action
from kagami_smarthome.routines.adaptive_routine import AdaptiveRoutine


class MovieModeRoutine(AdaptiveRoutine):
    """Home theater mode with adaptive lighting and AV setup."""

    id = "movie_mode"
    name = "Movie Mode"
    description = "Set up living room for movie watching with optimal lighting and AV"
    safety_critical = False

    params = {
        "light_level": 5,
        "close_shades": True,
        "lower_tv": True,
        "announce": False,
    }

    param_ranges = {
        "light_level": (0, 20),
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Movie mode is manually triggered only."""
        # This routine is manually invoked, not auto-triggered
        return False, ""

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute movie mode actions."""
        actions: list[Action] = []

        # Dim living room lights
        actions.append(
            Action(
                "set_lights",
                {"level": self.params["light_level"], "rooms": ["Living Room"]},
            )
        )

        # Turn off adjacent room lights
        actions.append(
            Action(
                "set_lights",
                {"level": 0, "rooms": ["Kitchen", "Dining", "Entry"]},
            )
        )

        # Close shades for darkness
        if self.params["close_shades"]:
            actions.append(Action("close_shades", {"rooms": ["Living Room"]}))

        # Lower TV mount
        if self.params["lower_tv"]:
            actions.append(Action("lower_tv", {"preset": 1}))

        # Optionally announce
        if self.params["announce"]:
            actions.append(
                Action(
                    "announce",
                    {"text": "Movie mode activated", "rooms": ["Living Room"], "volume": 30},
                )
            )

        return actions

    def get_rollback_action(self, action: Action) -> Action | None:
        """Get rollback action to exit movie mode."""
        if action.type == "set_lights":
            rooms = action.params.get("rooms", [])
            if "Living Room" in rooms:
                return Action("set_lights", {"level": 60, "rooms": rooms})
            return Action("set_lights", {"level": 0, "rooms": rooms})
        if action.type == "close_shades":
            return Action("open_shades", {"rooms": action.params.get("rooms", [])})
        if action.type == "lower_tv":
            return Action("raise_tv", {})
        return None


class ExitMovieModeRoutine(AdaptiveRoutine):
    """Exit home theater mode."""

    id = "exit_movie_mode"
    name = "Exit Movie Mode"
    description = "Restore normal lighting after movie"
    safety_critical = False

    params = {
        "restore_light_level": 60,
        "open_shades": True,
        "raise_tv": True,
    }

    param_ranges = {
        "restore_light_level": (30, 100),
    }

    async def should_trigger(self, context: HomeContext) -> tuple[bool, str]:
        """Exit movie mode is manually triggered only."""
        return False, ""

    async def compute_actions(self, context: HomeContext) -> list[Action]:
        """Compute exit movie mode actions."""
        actions: list[Action] = []

        # Restore living room lights
        actions.append(
            Action(
                "set_lights",
                {
                    "level": self.params["restore_light_level"],
                    "rooms": ["Living Room"],
                },
            )
        )

        # Open shades if daytime
        if self.params["open_shades"] and context.circadian_phase.value in (
            "morning",
            "midday",
            "afternoon",
        ):
            actions.append(Action("open_shades", {"rooms": ["Living Room"]}))

        # Raise TV
        if self.params["raise_tv"]:
            actions.append(Action("raise_tv", {}))

        return actions


__all__ = ["ExitMovieModeRoutine", "MovieModeRoutine"]
