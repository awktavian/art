"""Adaptive Routines for SmartHome.

This package contains context-aware, intelligent routines that
replace the static scenes system. Each routine:
- Uses ContextEngine to understand the current state
- Adapts its behavior based on time, presence, activity, etc.
- Executes via ReceiptedExecutor for full auditability
- Can be optimized by the organism based on user feedback
"""

from kagami_smarthome.routines.adaptive_routine import (
    AdaptiveRoutine,
    RoutineResult,
)
from kagami_smarthome.routines.registry import (
    RoutineRegistry,
    get_routine_registry,
)

__all__ = [
    "AdaptiveRoutine",
    "RoutineRegistry",
    "RoutineResult",
    "get_routine_registry",
]
