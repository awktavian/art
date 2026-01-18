"""Adaptive Routine Implementations.

All intelligent, context-aware routines for the SmartHome.
"""

from kagami_smarthome.routines.implementations.goodnight import GoodnightRoutine
from kagami_smarthome.routines.implementations.holiday_lights import (
    HolidayLightsOffRoutine,
    HolidayLightsRoutine,
    MusicReactiveLightsRoutine,
)
from kagami_smarthome.routines.implementations.movie_mode import (
    ExitMovieModeRoutine,
    MovieModeRoutine,
)
from kagami_smarthome.routines.implementations.welcome_home import WelcomeHomeRoutine


def register_all_routines(registry) -> None:
    """Register all built-in routines with the registry."""
    registry.register(WelcomeHomeRoutine())
    registry.register(GoodnightRoutine())
    registry.register(MovieModeRoutine())
    registry.register(ExitMovieModeRoutine())
    registry.register(HolidayLightsRoutine())
    registry.register(HolidayLightsOffRoutine())
    registry.register(MusicReactiveLightsRoutine())


__all__ = [
    "ExitMovieModeRoutine",
    "GoodnightRoutine",
    "HolidayLightsOffRoutine",
    "HolidayLightsRoutine",
    "MovieModeRoutine",
    "MusicReactiveLightsRoutine",
    "WelcomeHomeRoutine",
    "register_all_routines",
]
