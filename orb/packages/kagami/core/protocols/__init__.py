"""Typed Protocol classes for Kagami core subsystems.

This package contains Protocol interfaces that replace dict[str, Any]
patterns with explicit, documented, type-checkable interfaces.

Usage:
    from kagami.core.protocols import ConstellationUpdate, SensoryDataProtocol

    # Use in type hints
    def process_update(update: ConstellationUpdate) -> None:
        print(f"Breath phase: {update.breath_phase}")

    # Runtime checking (protocols are @runtime_checkable)
    if isinstance(data, SensoryDataProtocol):
        print(f"Heart rate: {data.heart_rate}")

Created: January 12, 2026
"""

from kagami.core.protocols.ambient_protocols import (
    # Specialized trigger contexts
    CalendarTriggerContext,
    # Core protocols
    ConstellationUpdate,
    EmailTriggerContext,
    GitHubTriggerContext,
    SensoryDataProtocol,
    SleepTriggerContext,
    # Type aliases
    TriggerAction,
    TriggerCondition,
    TriggerContextProtocol,
    VehicleTriggerContext,
    WeatherTriggerContext,
)

__all__ = [
    "CalendarTriggerContext",
    "ConstellationUpdate",
    "EmailTriggerContext",
    "GitHubTriggerContext",
    "SensoryDataProtocol",
    "SleepTriggerContext",
    "TriggerAction",
    "TriggerCondition",
    "TriggerContextProtocol",
    "VehicleTriggerContext",
    "WeatherTriggerContext",
]
