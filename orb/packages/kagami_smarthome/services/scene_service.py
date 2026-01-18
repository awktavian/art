"""Scene Service — Intent-Based Home Routines and Modes.

Handles scene activation and home modes using the intent automation system:
- Movie mode / Game mode → AutomationIntent.MOVIE_MODE
- Goodnight → AutomationIntent.PREPARE_SLEEP
- Welcome home → AutomationIntent.WELCOME_HOME
- Away mode → AutomationIntent.GOODBYE

MIGRATED: January 2, 2026 — Household-agnostic intent-based architecture.
No more hardcoded device checks (Denon, Control4, etc).

Created: December 30, 2025
Updated: January 2, 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from kagami_smarthome.intent_automation import (
    AutomationIntent,
    IntentExecution,
    get_intent_automation,
)

if TYPE_CHECKING:
    from kagami_smarthome.orchestrator import RoomOrchestrator

logger = logging.getLogger(__name__)


class SceneService:
    """Service for scene activation and home modes.

    NOW USES INTENT-BASED AUTOMATION:
    - No hardcoded device checks
    - Discovers capabilities dynamically
    - Works with any household configuration

    Usage:
        scene_svc = SceneService()
        await scene_svc.movie_mode()
        await scene_svc.goodnight()
    """

    def __init__(
        self,
        orchestrator: RoomOrchestrator | None = None,
    ) -> None:
        """Initialize scene service."""
        self._orchestrator = orchestrator
        self._intent_engine = None  # Lazy init

    def set_orchestrator(self, orchestrator: RoomOrchestrator) -> None:
        """Set or update orchestrator."""
        self._orchestrator = orchestrator

    async def _get_intent_engine(self):
        """Get or initialize intent automation engine."""
        if self._intent_engine is None:
            self._intent_engine = get_intent_automation()
            # Initialize if controller available via orchestrator
            if self._orchestrator and hasattr(self._orchestrator, "controller"):
                controller = self._orchestrator.controller
                if not self._intent_engine._running:
                    await self._intent_engine.initialize(controller)
        return self._intent_engine

    # =========================================================================
    # Home Theater Modes (Intent-Based)
    # =========================================================================

    async def movie_mode(self, context: dict[str, Any] | None = None) -> IntentExecution:
        """Set up for movie watching using intent system.

        Uses capability discovery — works with ANY AV setup:
        - HAS_THEATER → Uses available theater system
        - HAS_SPEAKERS → Uses available audio
        - HAS_LIGHTS → Dims lights

        Returns:
            IntentExecution with capabilities used and actions taken
        """
        engine = await self._get_intent_engine()
        return await engine.execute_intent(
            AutomationIntent.MOVIE_MODE,
            context or {"sound_mode": "movie", "light_level": 10},
        )

    async def game_mode(self, context: dict[str, Any] | None = None) -> IntentExecution:
        """Set up for gaming using intent system.

        Uses same capabilities as movie mode but with gaming settings.
        """
        engine = await self._get_intent_engine()
        # Use MOVIE_MODE intent with gaming context
        return await engine.execute_intent(
            AutomationIntent.MOVIE_MODE,
            context or {"sound_mode": "game", "light_level": 20},
        )

    async def enter_movie_mode(self) -> IntentExecution:
        """Enter comprehensive home theater movie mode.

        Coordinates lights, shades, TV mount, AVR, and HVAC via intent system.
        """
        return await self.movie_mode({"comprehensive": True})

    async def exit_movie_mode(self) -> bool:
        """Exit home theater movie mode."""
        # Still use orchestrator for exit (state management)
        if self._orchestrator:
            await self._orchestrator.exit_movie_mode()
            return True
        return False

    @property
    def is_movie_mode(self) -> bool:
        """Check if movie mode is active."""
        return self._orchestrator.is_movie_mode if self._orchestrator else False

    # =========================================================================
    # House-Wide Routines (Intent-Based)
    # =========================================================================

    async def goodnight(self, context: dict[str, Any] | None = None) -> IntentExecution:
        """Execute house-wide goodnight routine via intent system.

        Uses capability discovery:
        - HAS_LIGHTS → Turns off lights
        - HAS_LOCKS → Locks doors
        - HAS_ALARM → Arms security
        - HAS_SHADES → Closes shades
        - HAS_HVAC → Sets sleep temperature
        """
        engine = await self._get_intent_engine()
        return await engine.execute_intent(
            AutomationIntent.PREPARE_SLEEP,
            context or {},
        )

    async def welcome_home(self, context: dict[str, Any] | None = None) -> IntentExecution:
        """Execute welcome home routine via intent system.

        Uses capability discovery:
        - HAS_LIGHTS → Sets welcome lighting
        - HAS_VOICE_ANNOUNCE → Announces welcome
        - HAS_ALARM → (Does NOT auto-disarm for security)
        """
        engine = await self._get_intent_engine()
        return await engine.execute_intent(
            AutomationIntent.WELCOME_HOME,
            context or {},
        )

    async def set_away_mode(self, context: dict[str, Any] | None = None) -> IntentExecution:
        """Set house to away mode via intent system.

        Uses capability discovery:
        - HAS_LIGHTS → Turns off all lights
        - HAS_LOCKS → Locks all doors
        - HAS_ALARM → Arms away mode
        - HAS_HVAC → Sets setback temperature
        """
        engine = await self._get_intent_engine()
        return await engine.execute_intent(
            AutomationIntent.GOODBYE,
            context or {},
        )

    # =========================================================================
    # Direct Intent Execution
    # =========================================================================

    async def execute_intent(
        self,
        intent: AutomationIntent,
        context: dict[str, Any] | None = None,
    ) -> IntentExecution:
        """Execute any automation intent directly.

        Args:
            intent: The automation intent to execute
            context: Optional context parameters

        Returns:
            IntentExecution result with capabilities used
        """
        engine = await self._get_intent_engine()
        return await engine.execute_intent(intent, context)

    async def execute(
        self, natural_language: str, context: dict[str, Any] | None = None
    ) -> IntentExecution:
        """Execute from natural language.

        Args:
            natural_language: e.g., "movie time", "goodnight", "lock up"
            context: Optional context parameters

        Returns:
            IntentExecution result
        """
        engine = await self._get_intent_engine()
        return await engine.execute(natural_language, context)


__all__ = ["SceneService"]
