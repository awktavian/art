"""Presence Manager - Handles presence detection, tracking, and adaptation.

Extracted from controller.py (January 2026) to isolate presence logic
from the main orchestrator.

The PresenceManager handles:
- Presence state updates and tracking
- Adaptation to presence levels (audio, lights, breath)
- UnifiedSensory event processing
- Explainability logging for presence decisions
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Protocol

from kagami.core.ambient.data_types import PresenceLevel, PresenceState

if TYPE_CHECKING:
    from kagami.core.ambient.breath_engine import BreathEngine
    from kagami.core.ambient.explainability import ExplainabilityEngine
    from kagami.core.ambient.soundscape import Soundscape
    from kagami.core.ambient.unified_colony_renderer import UnifiedColonyRenderer

logger = logging.getLogger(__name__)


class PresenceManagerConfig:
    """Configuration for presence manager."""

    def __init__(
        self,
        *,
        idle_timeout_s: float = 300.0,
        sleep_hours: tuple[int, int] = (23, 7),
        sound_master_volume: float = 0.2,
    ):
        self.idle_timeout_s = idle_timeout_s
        self.sleep_hours = sleep_hours
        self.sound_master_volume = sound_master_volume


class ConstellationSyncCallback(Protocol):
    """Protocol for constellation sync callback."""

    async def __call__(self, *, force: bool = False) -> None: ...


class PresenceManager:
    """Manages presence detection and ambient adaptation.

    This class processes presence events from UnifiedSensory and adapts
    ambient behavior (lights, audio, breath) to match the user's
    engagement level.
    """

    def __init__(self, config: PresenceManagerConfig | None = None):
        """Initialize presence manager.

        Args:
            config: Presence manager configuration
        """
        self.config = config or PresenceManagerConfig()

        # Current state
        self._presence = PresenceState(
            level=PresenceLevel.PERIPHERAL,
            confidence=0.5,
            attention_target=None,
            activity_type=None,
            location=None,
        )

        # Subsystem references
        self._breath_engine: BreathEngine | None = None
        self._colony_renderer: UnifiedColonyRenderer | None = None
        self._soundscape: Soundscape | None = None
        self._smart_home: Any = None
        self._explainability: ExplainabilityEngine | None = None

        # Callbacks
        self._constellation_sync: ConstellationSyncCallback | None = None

        # Statistics
        self._stats = {
            "presence_changes": 0,
        }

    @property
    def presence(self) -> PresenceState:
        """Get current presence state."""
        return self._presence

    def connect_breath_engine(self, engine: BreathEngine) -> None:
        """Connect breath engine for presence-based BPM adaptation.

        Args:
            engine: BreathEngine instance
        """
        self._breath_engine = engine

    def connect_colony_renderer(self, renderer: UnifiedColonyRenderer) -> None:
        """Connect colony renderer for presence visualization.

        Args:
            renderer: UnifiedColonyRenderer instance
        """
        self._colony_renderer = renderer

    def connect_soundscape(self, soundscape: Soundscape) -> None:
        """Connect soundscape for presence-based volume.

        Args:
            soundscape: Soundscape instance
        """
        self._soundscape = soundscape

    def connect_smart_home(self, smart_home: Any) -> None:
        """Connect smart home for presence-based control.

        Args:
            smart_home: SmartHomeController instance
        """
        self._smart_home = smart_home

    def connect_explainability(self, engine: ExplainabilityEngine) -> None:
        """Connect explainability engine for decision logging.

        Args:
            engine: ExplainabilityEngine instance
        """
        self._explainability = engine

    def set_constellation_sync(self, callback: ConstellationSyncCallback) -> None:
        """Set callback for constellation synchronization.

        Args:
            callback: Async function to trigger constellation sync
        """
        self._constellation_sync = callback

    def update_presence(self, presence: PresenceState) -> None:
        """Update presence state.

        Args:
            presence: New presence state
        """
        prev_level = self._presence.level
        self._presence = presence

        # Update colony renderer
        if self._colony_renderer:
            self._colony_renderer.update_presence(presence)

        if prev_level != presence.level:
            self._stats["presence_changes"] += 1
            asyncio.create_task(self._adapt_to_presence(presence))

            # Trigger constellation sync
            if self._constellation_sync is not None:
                asyncio.create_task(self._constellation_sync(force=True))

    async def on_sense_event(
        self,
        sense_type: Any,
        data: dict,
        delta: dict,
    ) -> None:
        """Handle sensory events from UnifiedSensory.

        Args:
            sense_type: Type of sense that changed
            data: Full current data
            delta: Changed fields only
        """
        # Handle presence events
        if sense_type.value == "presence":
            presence_map = {
                "away": PresenceLevel.ABSENT,
                "arriving": PresenceLevel.PERIPHERAL,
                "home": PresenceLevel.AWARE,
                "active": PresenceLevel.ENGAGED,
                "sleeping": PresenceLevel.PERIPHERAL,
            }

            new_level = presence_map.get(data.get("presence", "home"), PresenceLevel.PERIPHERAL)

            # Update presence state
            self._presence = PresenceState(
                level=new_level,
                confidence=0.9,
                attention_target=data.get("location"),
                activity_type=data.get("activity"),
                location=data.get("location"),
            )

            # Update colony renderer
            if self._colony_renderer:
                self._colony_renderer.update_presence(self._presence)

            self._stats["presence_changes"] += 1

            # Log presence explanation
            if self._explainability:
                from kagami.core.ambient.explainability import DecisionType, TriggerType

                self._explainability.log_decision(
                    decision_type=DecisionType.PRESENCE,
                    trigger=TriggerType.SENSOR_DATA,
                    input_context={"sense_type": "presence", "data": data},
                    output_action=f"presence_level_{new_level.value}",
                    reasoning="UnifiedSensory presence event",
                )

    async def _adapt_to_presence(self, presence: PresenceState) -> None:
        """Adapt ambient behavior to presence level.

        Args:
            presence: Current presence state
        """
        level = presence.level

        # Volume multiplier based on presence
        volume_multipliers = {
            PresenceLevel.ABSENT: 0.0,
            PresenceLevel.PERIPHERAL: 0.3,
            PresenceLevel.AWARE: 0.6,
            PresenceLevel.ENGAGED: 1.0,
            PresenceLevel.FOCUSED: 0.2,  # Recede during focus
        }
        vol_mult = volume_multipliers.get(level, 0.5)

        # Breath BPM based on presence
        breath_bpm = {
            PresenceLevel.ABSENT: 4.0,
            PresenceLevel.PERIPHERAL: 4.0,
            PresenceLevel.AWARE: 6.0,
            PresenceLevel.ENGAGED: 8.0,
            PresenceLevel.FOCUSED: 4.0,
        }
        if self._breath_engine:
            self._breath_engine.set_bpm(breath_bpm.get(level, 6.0))

        # Smart home audio
        if self._smart_home and getattr(self._smart_home, "_initialized", False):
            volume = int(vol_mult * 100)
            await self._smart_home.set_audio(volume)

        # Soundscape fallback
        if self._soundscape:
            self._soundscape.set_volume(self.config.sound_master_volume * vol_mult)

        # Lighting adaptation
        if level == PresenceLevel.ABSENT:
            if self._smart_home and getattr(self._smart_home, "_initialized", False):
                await self._smart_home.set_lights(0)
        elif level == PresenceLevel.FOCUSED:
            if self._smart_home and getattr(self._smart_home, "_initialized", False):
                await self._smart_home.set_lights(20)

        logger.info(f"Presence adapted: {level.value}")

    def get_stats(self) -> dict[str, int]:
        """Get presence manager statistics.

        Returns:
            Statistics dictionary
        """
        return dict(self._stats)
