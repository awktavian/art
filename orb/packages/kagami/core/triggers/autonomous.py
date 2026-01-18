"""Autonomous action triggers (proactive, time-based, goal-driven).

CREATED: January 5, 2026
"""

from __future__ import annotations

from typing import Any

from .base import TriggerPriority, TriggerSourceType, UnifiedTrigger


def create_morning_routine_trigger(smart_home: Any) -> UnifiedTrigger:
    """Create morning routine trigger.

    Args:
        smart_home: SmartHomeController

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        # Always true - autonomous action
        # (Actual scheduling handled by autonomous goal engine)
        return True

    async def action(data: dict) -> None:
        """Prepare for morning routine."""
        # Gradual lights in bedroom
        await smart_home.set_lights(30, rooms=["Primary Bed"])

        # Open bedroom shades
        await smart_home.open_shades(rooms=["Primary Bed"])

        # Prepare kitchen
        await smart_home.set_lights(40, rooms=["Kitchen"])

        # Announce morning weather
        try:
            from kagami_smarthome import get_current_weather

            weather = await get_current_weather()
            if weather:
                temp_f = weather.temp_f
                feels_like_f = getattr(weather, "feels_like_f", temp_f)
                description = weather.description

                briefing = f"Good morning! It's {temp_f:.0f}°F outside"
                if abs(feels_like_f - temp_f) > 3:
                    briefing += f", feels like {feels_like_f:.0f}°F"
                briefing += f". {description.capitalize()}."

                await smart_home.announce(briefing, rooms=["Living Room"])
        except Exception:
            pass  # Don't fail routine if weather unavailable

    return UnifiedTrigger(
        name="prepare_morning",
        source_type=TriggerSourceType.AUTONOMOUS,
        source="autonomous_goals",
        condition=condition,
        action=action,
        cooldown=3600.0,  # 1 hour
        priority=TriggerPriority.NORMAL,
        requires_presence=False,  # Can prepare before Tim wakes
        safety_priority=7,
    )


def create_focus_mode_trigger(smart_home: Any) -> UnifiedTrigger:
    """Create focus mode preparation trigger.

    Args:
        smart_home: SmartHomeController

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        return True  # Autonomous

    async def action(data: dict) -> None:
        """Prepare environment for focused work."""
        # Set office lights for focus
        await smart_home.set_lights(75, rooms=["Office"])

        # Close office shades if sunny
        # (Would check weather first in full implementation)

    return UnifiedTrigger(
        name="prepare_for_focus",
        source_type=TriggerSourceType.AUTONOMOUS,
        source="autonomous_goals",
        condition=condition,
        action=action,
        cooldown=600.0,  # 10 minutes
        priority=TriggerPriority.NORMAL,
        requires_presence=True,
        safety_priority=6,
    )


def create_comfort_adjustment_trigger(smart_home: Any) -> UnifiedTrigger:
    """Create comfort adjustment trigger.

    Args:
        smart_home: SmartHomeController

    Returns:
        UnifiedTrigger
    """

    def condition(data: dict) -> bool:
        return True  # Autonomous

    async def action(data: dict) -> None:
        """Make comfort adjustments based on learned preferences."""
        # Placeholder - would use learned preferences
        pass

    return UnifiedTrigger(
        name="comfort_adjustment",
        source_type=TriggerSourceType.AUTONOMOUS,
        source="autonomous_goals",
        condition=condition,
        action=action,
        cooldown=1800.0,  # 30 minutes
        priority=TriggerPriority.LOW,
        requires_presence=True,
        safety_priority=9,
    )


def register_all_autonomous_actions(registry: Any, smart_home: Any) -> None:
    """Register all autonomous action triggers.

    Migrates PhysicalAction from OrganismPhysicalBridge to UnifiedTrigger system.

    Args:
        registry: TriggerRegistry
        smart_home: SmartHomeController
    """
    registry.register(create_morning_routine_trigger(smart_home))
    registry.register(create_focus_mode_trigger(smart_home))
    registry.register(create_comfort_adjustment_trigger(smart_home))
