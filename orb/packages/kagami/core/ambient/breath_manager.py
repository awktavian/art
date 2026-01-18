"""Breath Manager - Coordinates breath rhythm with ambient systems.

Extracted from controller.py (January 2026) to isolate breath synchronization
logic from the main orchestrator.

The BreathManager handles:
- Breath tick callbacks (30Hz) with rate-limited light sync
- Phase change callbacks with haptic feedback
- Receipt phase synchronization
- Subsystem updates (renderer, soundscape, voice)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Protocol

from kagami.core.ambient.data_types import BreathPhase, BreathState

if TYPE_CHECKING:
    from kagami.core.ambient.breath_engine import BreathEngine
    from kagami.core.ambient.soundscape import Soundscape
    from kagami.core.ambient.unified_colony_renderer import UnifiedColonyRenderer
    from kagami.core.ambient.voice_interface import VoiceInterface

logger = logging.getLogger(__name__)


class BreathManagerConfig:
    """Configuration for breath manager."""

    def __init__(
        self,
        *,
        breath_bpm: float = 6.0,
        light_breath_sync: bool = False,
        light_base_brightness: float = 0.3,
        light_breath_sync_interval: float = 10.0,
        sound_breath_sync: bool = True,
    ):
        self.breath_bpm = breath_bpm
        self.light_breath_sync = light_breath_sync
        self.light_base_brightness = light_base_brightness
        self.light_breath_sync_interval = light_breath_sync_interval
        self.sound_breath_sync = sound_breath_sync


class StateUpdateCallback(Protocol):
    """Protocol for state update callbacks."""

    def __call__(self, breath: BreathState) -> None: ...


class ConstellationSyncCallback(Protocol):
    """Protocol for constellation sync callback."""

    async def __call__(self, *, force: bool = False) -> None: ...


class BreathManager:
    """Manages breath rhythm synchronization with ambient systems.

    This class handles the high-frequency breath callbacks and coordinates
    updates to various subsystems (lights, sound, haptics) with appropriate
    rate limiting to prevent flickering or overwhelming the systems.
    """

    def __init__(self, config: BreathManagerConfig | None = None):
        """Initialize breath manager.

        Args:
            config: Breath manager configuration
        """
        self.config = config or BreathManagerConfig()

        # Subsystem references (set via connect_* methods)
        self._breath_engine: BreathEngine | None = None
        self._colony_renderer: UnifiedColonyRenderer | None = None
        self._soundscape: Soundscape | None = None
        self._voice: VoiceInterface | None = None
        self._haptic: Any = None
        self._smart_home: Any = None

        # Rate limiting
        self._last_breath_light_update: float = 0.0

        # Callbacks
        self._state_callback: StateUpdateCallback | None = None
        self._constellation_sync: ConstellationSyncCallback | None = None

        # Statistics
        self._stats = {
            "breath_cycles": 0,
            "light_syncs": 0,
        }

    def connect_breath_engine(self, engine: BreathEngine) -> None:
        """Connect to breath engine and register callbacks.

        Args:
            engine: BreathEngine instance
        """
        self._breath_engine = engine
        engine.set_bpm(self.config.breath_bpm)
        engine.on_tick(self._on_breath_tick)
        engine.on_phase_change(self._on_breath_phase_change)

    def connect_colony_renderer(self, renderer: UnifiedColonyRenderer) -> None:
        """Connect colony renderer for breath visualization.

        Args:
            renderer: UnifiedColonyRenderer instance
        """
        self._colony_renderer = renderer

    def connect_soundscape(self, soundscape: Soundscape) -> None:
        """Connect soundscape for breath audio.

        Args:
            soundscape: Soundscape instance
        """
        self._soundscape = soundscape

    def connect_voice(self, voice: VoiceInterface) -> None:
        """Connect voice interface for breath pacing.

        Args:
            voice: VoiceInterface instance
        """
        self._voice = voice

    def connect_haptic(self, haptic: Any) -> None:
        """Connect haptic controller for tactile feedback.

        Args:
            haptic: Haptic controller instance
        """
        self._haptic = haptic

    def connect_smart_home(self, smart_home: Any) -> None:
        """Connect smart home for light synchronization.

        Args:
            smart_home: SmartHomeController instance
        """
        self._smart_home = smart_home

    def set_state_callback(self, callback: StateUpdateCallback) -> None:
        """Set callback for state updates.

        Args:
            callback: Function to call with breath state updates
        """
        self._state_callback = callback

    def set_constellation_sync(self, callback: ConstellationSyncCallback) -> None:
        """Set callback for constellation synchronization.

        Args:
            callback: Async function to trigger constellation sync
        """
        self._constellation_sync = callback

    def set_bpm(self, bpm: float) -> None:
        """Set breath rate.

        Args:
            bpm: Breaths per minute
        """
        self.config.breath_bpm = bpm
        if self._breath_engine:
            self._breath_engine.set_bpm(bpm)

    def sync_to_receipt(self, phase: str) -> None:
        """Sync breath to receipt phase.

        Args:
            phase: Receipt phase (PLAN, EXECUTE, VERIFY)
        """
        if self._breath_engine:
            self._breath_engine.sync_to_receipt(phase)

    def get_breath_value(self) -> float:
        """Get current breath value (0-1).

        Returns:
            Current breath intensity
        """
        if self._breath_engine:
            return self._breath_engine.get_breath_value()
        return 0.5

    async def _on_breath_tick(self, breath: BreathState) -> None:
        """Handle breath tick (30Hz).

        NOTE: Light sync is THROTTLED to prevent flickering.
        Even though this callback runs at 30Hz, lights only update every
        light_breath_sync_interval seconds.

        Args:
            breath: Current breath state
        """
        # Update state via callback
        if self._state_callback:
            self._state_callback(breath)

        breath_value = self.get_breath_value()

        # Update unified renderer with breath state
        if self._colony_renderer:
            self._colony_renderer.update_breath(breath.phase, breath.phase_progress)

        # Sync lights to breath (THROTTLED to prevent flickering)
        if self.config.light_breath_sync:
            now = time.time()
            if now - self._last_breath_light_update >= self.config.light_breath_sync_interval:
                self._last_breath_light_update = now
                brightness = self.config.light_base_brightness + (0.2 * breath_value)
                if self._smart_home and getattr(self._smart_home, "_initialized", False):
                    level = int(brightness * 100)
                    await self._smart_home.set_lights(level, source="breath_sync")
                    self._stats["light_syncs"] += 1

        # Sync soundscape to breath
        if self.config.sound_breath_sync and self._soundscape:
            self._soundscape.set_breath(breath_value)

        # Sync voice to breath
        if self._voice:
            self._voice.set_breath_state(breath.phase, breath_value)

    async def _on_breath_phase_change(self, breath: BreathState) -> None:
        """Handle breath phase change.

        Args:
            breath: Current breath state
        """
        phase = breath.phase

        logger.debug(f"Breath: {phase.value} (cycle {breath.cycle_count})")

        if phase == BreathPhase.INHALE:
            self._stats["breath_cycles"] += 1

        # Haptic on phase change (subtle, every 4th cycle)
        if self._haptic and breath.cycle_count % 4 == 0:
            if phase == BreathPhase.INHALE:
                await self._haptic.notification()

        # Constellation sync on phase change
        if self._constellation_sync is not None:
            await self._constellation_sync(force=True)

    def get_stats(self) -> dict[str, int]:
        """Get breath manager statistics.

        Returns:
            Statistics dictionary
        """
        return dict(self._stats)
