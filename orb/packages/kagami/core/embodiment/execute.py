"""Unified Execution — THE Single Way to Execute Physical Actions.

CREATED: January 10, 2026

ALL physical actions in Kagami MUST route through this module:
- Triggers
- Bridges
- Orchestrators
- Autonomous actions

This ensures:
1. All actions are logged to RSSM for learning
2. CBF safety checks are applied
3. Single source of truth for execution statistics

Usage:
    from kagami.core.embodiment.execute import execute

    # Execute a SmartHome action
    await execute("smarthome", "set_lights", {"level": 50}, room="Office")

    # Execute a digital action
    await execute("digital", "GMAIL_SEND_EMAIL", {...})

    # Execute with explicit controller (for legacy code)
    await execute("smarthome", "announce", {"text": "Hello"}, controller=smart_home)

DO NOT:
    - Call SmartHomeController methods directly
    - Call Composio methods directly
    - Bypass this module for "efficiency"

All actions flow through UnifiedActionExecutor, which:
    - Routes to the correct backend
    - Logs to RSSM for world model learning
    - Tracks execution statistics
    - Applies any necessary safety checks
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)

# Singleton executor (lazy initialized)
_executor: Any = None


async def execute(
    action_type: str,
    action_name: str,
    parameters: dict[str, Any] | None = None,
    *,
    room: str | None = None,
    controller: SmartHomeController | None = None,
) -> dict[str, Any]:
    """Execute a physical action through the unified path.

    THE CANONICAL WAY to execute physical actions in Kagami.

    Args:
        action_type: Type of action ("smarthome", "digital", "desktop", "cli")
        action_name: Name of the action (e.g., "set_lights", "announce")
        parameters: Action parameters
        room: Target room (for smarthome actions)
        controller: Legacy: Explicit SmartHomeController (ignored, for compatibility)

    Returns:
        Dict with execution result:
        - success: bool
        - action_type: str
        - action_name: str
        - result: Any (action-specific)
        - error: str | None

    Example:
        # Turn on lights
        await execute("smarthome", "set_lights", {"level": 100}, room="Office")

        # Make announcement
        await execute("smarthome", "announce", {"text": "Hello"}, room="Living Room")

        # Send email
        await execute("digital", "GMAIL_SEND_EMAIL", {"to": "...", "body": "..."})
    """
    global _executor

    # Lazy initialize executor
    if _executor is None:
        from kagami.core.embodiment.unified_action_executor import (
            get_unified_action_executor,
        )

        _executor = get_unified_action_executor()

    if not _executor._initialized:
        await _executor.initialize()

    # Execute through unified path
    result = await _executor.execute_direct(
        action_type=action_type,
        action_name=action_name,
        parameters=parameters or {},
        room=room,
    )

    return {
        "success": result.success,
        "action_type": result.action_type,
        "action_name": result.action_name,
        "confidence": result.confidence,
        "result": result.result,
        "error": result.error,
    }


async def execute_smarthome(
    action_name: str,
    parameters: dict[str, Any] | None = None,
    *,
    room: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for SmartHome actions.

    Example:
        await execute_smarthome("set_lights", {"level": 50}, room="Office")
        await execute_smarthome("announce", {"text": "Hello"})
        await execute_smarthome("movie_mode")
    """
    return await execute("smarthome", action_name, parameters, room=room)


async def execute_digital(
    action_name: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for digital (Composio) actions.

    Example:
        await execute_digital("GMAIL_SEND_EMAIL", {"to": "...", "body": "..."})
        await execute_digital("SLACK_SEND_MESSAGE", {"channel": "...", "text": "..."})
    """
    return await execute("digital", action_name, parameters)


def reset_executor() -> None:
    """Reset the singleton executor (for testing)."""
    global _executor
    _executor = None
