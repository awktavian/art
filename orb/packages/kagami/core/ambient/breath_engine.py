"""Breath Engine for Ambient OS.

The breath is the fundamental rhythm of Kagami.
PLAN → EXECUTE → VERIFY maps to INHALE → HOLD → EXHALE.

This engine provides:
- Continuous breath cycle generation
- Sync with receipt phases
- Modality-agnostic rhythm output
- Adaptive BPM based on system state

Created: December 5, 2025
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from kagami.core.ambient.data_types import BreathPhase, BreathState

logger = logging.getLogger(__name__)


@dataclass
class BreathConfig:
    """Breath engine configuration."""

    base_bpm: float = 6.0  # 6 breaths per minute = 10s cycle (calm)
    min_bpm: float = 4.0  # Slowest (deep rest)
    max_bpm: float = 15.0  # Fastest (high activity)

    # Phase ratios (must sum to 1.0)
    inhale_ratio: float = 0.35  # 35% inhale
    hold_ratio: float = 0.30  # 30% hold
    exhale_ratio: float = 0.30  # 30% exhale
    rest_ratio: float = 0.05  # 5% rest between breaths

    # Intensity range
    min_intensity: float = 0.2  # Minimum breath depth
    max_intensity: float = 1.0  # Maximum breath depth


class BreathEngine:
    """Generates the ambient breath rhythm.

    The breath cycle is the heartbeat of the ambient system.
    All modalities (light, sound, haptic) sync to this rhythm.
    """

    def __init__(self, config: BreathConfig | None = None):
        """Initialize breath engine.

        Args:
            config: Breath configuration
        """
        self.config = config or BreathConfig()
        self._validate_config()

        # Current state
        self._state = BreathState(
            phase=BreathPhase.REST,
            phase_progress=0.0,
            cycle_count=0,
            bpm=self.config.base_bpm,
            intensity=0.5,
        )

        # Phase boundaries (cumulative)
        self._phase_boundaries = self._compute_phase_boundaries()

        # Subscribers
        self._phase_callbacks: list[Callable[[BreathState], Awaitable[None]]] = []
        self._tick_callbacks: list[Callable[[BreathState], Awaitable[None]]] = []

        # Control
        self._running = False
        self._task: asyncio.Task | None = None
        self._cycle_start_time: float = 0.0

    def _validate_config(self) -> None:
        """Validate configuration."""
        ratios = (
            self.config.inhale_ratio
            + self.config.hold_ratio
            + self.config.exhale_ratio
            + self.config.rest_ratio
        )
        if not (0.99 <= ratios <= 1.01):
            raise ValueError(f"Phase ratios must sum to 1.0, got {ratios}")

    def _compute_phase_boundaries(self) -> dict[BreathPhase, tuple[float, float]]:
        """Compute phase start/end boundaries."""
        boundaries = {}
        cursor = 0.0

        boundaries[BreathPhase.INHALE] = (cursor, cursor + self.config.inhale_ratio)
        cursor += self.config.inhale_ratio

        boundaries[BreathPhase.HOLD] = (cursor, cursor + self.config.hold_ratio)
        cursor += self.config.hold_ratio

        boundaries[BreathPhase.EXHALE] = (cursor, cursor + self.config.exhale_ratio)
        cursor += self.config.exhale_ratio

        boundaries[BreathPhase.REST] = (cursor, 1.0)

        return boundaries

    @property
    def state(self) -> BreathState:
        """Get current breath state."""
        return self._state

    def get_breath_value(self) -> float:
        """Get current breath value (0-1) for modulation.

        Returns:
            Float from 0 (empty) to 1 (full breath)
        """
        phase = self._state.phase
        progress = self._state.phase_progress
        intensity = self._state.intensity

        if phase == BreathPhase.INHALE:
            # Ease-in: slow start, accelerate
            # Using sine curve for natural feel
            value = math.sin(progress * math.pi / 2)
        elif phase == BreathPhase.HOLD:
            # Hold at peak
            value = 1.0
        elif phase == BreathPhase.EXHALE:
            # Ease-out: fast start, decelerate
            value = math.cos(progress * math.pi / 2)
        else:  # REST
            # Bottomed out
            value = 0.0

        # Scale by intensity
        return value * intensity

    def set_bpm(self, bpm: float) -> None:
        """Set breath rate.

        Args:
            bpm: Breaths per minute
        """
        self._state.bpm = max(self.config.min_bpm, min(self.config.max_bpm, bpm))
        logger.debug(f"Breath BPM: {self._state.bpm:.1f}")

    def set_intensity(self, intensity: float) -> None:
        """Set breath intensity/depth.

        Args:
            intensity: 0.0 to 1.0
        """
        self._state.intensity = max(
            self.config.min_intensity, min(self.config.max_intensity, intensity)
        )

    def adapt_to_activity(self, activity_level: float) -> None:
        """Adapt breath to activity level.

        Args:
            activity_level: 0.0 (resting) to 1.0 (high activity)
        """
        # Higher activity = faster, shallower breaths
        bpm_range = self.config.max_bpm - self.config.min_bpm
        target_bpm = self.config.min_bpm + (activity_level * bpm_range * 0.5)
        self.set_bpm(target_bpm)

        # Inverse relationship for intensity
        target_intensity = 1.0 - (activity_level * 0.5)
        self.set_intensity(target_intensity)

    def sync_to_receipt(self, phase: str) -> None:
        """Sync breath to receipt phase.

        Args:
            phase: Receipt phase (PLAN, EXECUTE, VERIFY)
        """
        phase_map = {
            "PLAN": BreathPhase.INHALE,
            "EXECUTE": BreathPhase.HOLD,
            "VERIFY": BreathPhase.EXHALE,
        }
        if phase in phase_map:
            target_phase = phase_map[phase]
            if self._state.phase != target_phase:
                self._state.phase = target_phase
                self._state.phase_progress = 0.0
                logger.debug(f"Breath synced to {phase} → {target_phase.value}")

    def on_phase_change(self, callback: Callable[[BreathState], Awaitable[None]]) -> None:
        """Subscribe to phase changes.

        Args:
            callback: Async callback receiving breath state
        """
        self._phase_callbacks.append(callback)

    def on_tick(self, callback: Callable[[BreathState], Awaitable[None]]) -> None:
        """Subscribe to breath ticks (every update).

        Args:
            callback: Async callback receiving breath state
        """
        self._tick_callbacks.append(callback)

    async def _notify_phase_change(self) -> None:
        """Notify phase change subscribers."""
        for callback in self._phase_callbacks:
            try:
                await callback(self._state)
            except Exception as e:
                logger.error(f"Phase callback error: {e}")

    async def _notify_tick(self) -> None:
        """Notify tick subscribers."""
        for callback in self._tick_callbacks:
            try:
                await callback(self._state)
            except Exception as e:
                logger.error(f"Tick callback error: {e}")

    async def _breath_loop(self) -> None:
        """Main breath generation loop."""
        logger.info("🌬️ Breath engine started")

        tick_interval = 1.0 / 30.0  # 30 Hz update rate
        self._cycle_start_time = time.time()

        while self._running:
            try:
                # Calculate cycle progress
                cycle_duration = 60.0 / self._state.bpm
                elapsed = time.time() - self._cycle_start_time
                cycle_progress = (elapsed % cycle_duration) / cycle_duration

                # Check for new cycle
                if elapsed >= cycle_duration:
                    self._cycle_start_time = time.time()
                    self._state.cycle_count += 1
                    cycle_progress = 0.0

                # Determine current phase
                prev_phase = self._state.phase
                new_phase = BreathPhase.REST

                for phase, (start, end) in self._phase_boundaries.items():
                    if start <= cycle_progress < end:
                        new_phase = phase
                        phase_duration = end - start
                        self._state.phase_progress = (
                            (cycle_progress - start) / phase_duration if phase_duration > 0 else 0.0
                        )
                        break

                self._state.phase = new_phase
                self._state.timestamp = time.time()

                # Notify on phase change
                if new_phase != prev_phase:
                    await self._notify_phase_change()

                # Always notify tick
                await self._notify_tick()

                await asyncio.sleep(tick_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Breath loop error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

        logger.info("🌬️ Breath engine stopped")

    async def start(self) -> None:
        """Start breath engine."""
        if self._running:
            return

        self._running = True

        from kagami.core.async_utils import safe_create_task

        self._task = safe_create_task(
            self._breath_loop(),
            name="breath_engine",
            error_callback=lambda e: logger.error(f"Breath engine crashed: {e}"),
        )

    async def stop(self) -> None:
        """Stop breath engine."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# =============================================================================
# Global Instance
# =============================================================================

_BREATH_ENGINE: BreathEngine | None = None


async def get_breath_engine() -> BreathEngine:
    """Get global breath engine instance."""
    global _BREATH_ENGINE
    if _BREATH_ENGINE is None:
        _BREATH_ENGINE = BreathEngine()
        await _BREATH_ENGINE.start()
    return _BREATH_ENGINE
