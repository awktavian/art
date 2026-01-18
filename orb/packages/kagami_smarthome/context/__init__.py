"""Context layer for SmartHome — Unified context gathering."""

from kagami_smarthome.context.context_engine import (
    CircadianPhase,
    ContextEngine,
    GuestMode,
    HomeContext,
    get_context_engine,
)

__all__ = [
    "CircadianPhase",
    "ContextEngine",
    "GuestMode",
    "HomeContext",
    "get_context_engine",
]
