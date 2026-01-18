"""Light Command Debouncer — Prevents Flickering.

Coalesces rapid light commands to prevent flickering caused by:
- Multiple systems trying to control the same light
- High-frequency breath sync loops (30Hz!)
- Presence changes triggering multiple scene updates
- Weather/circadian adaptations

The debouncer:
1. Buffers incoming light level changes
2. Uses "last write wins" for the same device
3. Flushes buffered commands after a short delay
4. Rate-limits commands per device (min 200ms between changes)

Created: January 7, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.control4 import Control4Integration

logger = logging.getLogger(__name__)


@dataclass
class PendingLightChange:
    """A buffered light level change."""

    light_id: int
    level: int
    queued_at: float
    source: str  # For debugging: who requested this change


@dataclass
class LightState:
    """Tracks state for a single light to prevent redundant commands."""

    last_level: int | None = None
    last_command_time: float = 0.0
    pending_level: int | None = None


class LightCommandDebouncer:
    """Coalesces rapid light commands to prevent flickering.

    Usage:
        debouncer = LightCommandDebouncer(control4)

        # Instead of: await control4.set_light_level(light_id, level)
        # Use: await debouncer.set_level(light_id, level, source="device_service")

        # The debouncer will:
        # 1. Skip if level hasn't changed
        # 2. Rate-limit to max 1 command per 200ms per light
        # 3. Coalesce rapid changes (last write wins)
    """

    # Configuration
    MIN_INTERVAL_MS: int = 200  # Minimum ms between commands per light
    FLUSH_DELAY_MS: int = 50  # Wait this long before flushing (coalesce window)
    LEVEL_TOLERANCE: int = 2  # Skip if level change is <= this (noise filter)

    def __init__(self, control4: Control4Integration | None = None) -> None:
        """Initialize debouncer.

        Args:
            control4: Control4 integration for executing commands
        """
        self._control4 = control4

        # Per-light state tracking
        self._light_states: dict[int, LightState] = {}

        # Pending changes buffer: light_id -> PendingLightChange
        self._pending: dict[int, PendingLightChange] = {}

        # Flush task
        self._flush_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "commands_received": 0,
            "commands_executed": 0,
            "commands_skipped_unchanged": 0,
            "commands_skipped_rate_limit": 0,
            "commands_coalesced": 0,
        }

    def set_control4(self, control4: Control4Integration) -> None:
        """Set or update Control4 integration."""
        self._control4 = control4

    async def set_level(
        self,
        light_id: int,
        level: int,
        source: str = "unknown",
    ) -> bool:
        """Queue a light level change with debouncing.

        Args:
            light_id: Control4 light device ID
            level: Target brightness (0-100)
            source: Who requested this change (for debugging)

        Returns:
            True if command was queued/executed, False if skipped
        """
        self._stats["commands_received"] += 1
        now = time.time()

        # Get or create light state
        state = self._light_states.setdefault(light_id, LightState())

        # Skip if level hasn't changed significantly
        if state.last_level is not None:
            if abs(state.last_level - level) <= self.LEVEL_TOLERANCE:
                self._stats["commands_skipped_unchanged"] += 1
                logger.debug(
                    f"🔦 SKIP (unchanged): light {light_id} already at {state.last_level}% "
                    f"(requested {level}% from {source})"
                )
                return False

        # Check rate limit
        time_since_last = (now - state.last_command_time) * 1000  # ms
        if time_since_last < self.MIN_INTERVAL_MS:
            # Rate limited - buffer for later
            if light_id in self._pending:
                self._stats["commands_coalesced"] += 1
                logger.debug(
                    f"🔦 COALESCE: light {light_id} {self._pending[light_id].level}% → {level}% "
                    f"(from {source})"
                )
            self._pending[light_id] = PendingLightChange(
                light_id=light_id,
                level=level,
                queued_at=now,
                source=source,
            )
            self._schedule_flush()
            return True

        # Execute immediately
        success = await self._execute_command(light_id, level, source)
        if success:
            state.last_level = level
            state.last_command_time = now

        return success

    async def set_room_levels(
        self,
        light_ids: list[int],
        level: int,
        source: str = "unknown",
    ) -> list[bool]:
        """Set multiple lights to same level with debouncing.

        Args:
            light_ids: List of Control4 light device IDs
            level: Target brightness (0-100)
            source: Who requested this change

        Returns:
            List of success flags for each light
        """
        # Process all lights, collecting results
        results = []
        for light_id in light_ids:
            result = await self.set_level(light_id, level, source)
            results.append(result)
        return results

    def _schedule_flush(self) -> None:
        """Schedule a flush of pending commands."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_pending())

    async def _flush_pending(self) -> None:
        """Flush all pending commands after debounce delay."""
        await asyncio.sleep(self.FLUSH_DELAY_MS / 1000)

        async with self._flush_lock:
            if not self._pending:
                return

            # Copy and clear pending
            to_execute = dict(self._pending)
            self._pending.clear()

            now = time.time()

            # Execute all pending commands
            tasks = []
            for light_id, change in to_execute.items():
                state = self._light_states.get(light_id, LightState())

                # Check rate limit again (in case time passed)
                time_since_last = (now - state.last_command_time) * 1000
                if time_since_last < self.MIN_INTERVAL_MS:
                    # Still rate limited - re-queue
                    self._pending[light_id] = change
                    continue

                # Execute
                task = asyncio.create_task(
                    self._execute_command(change.light_id, change.level, change.source)
                )
                tasks.append((light_id, change.level, task))

            # Wait for all executions
            if tasks:
                results = await asyncio.gather(
                    *[t for _, _, t in tasks],
                    return_exceptions=True,
                )

                # Update states
                for (light_id, level, _), result in zip(tasks, results, strict=False):
                    if result is True:
                        state = self._light_states.setdefault(light_id, LightState())
                        state.last_level = level
                        state.last_command_time = now

            # If there are still pending commands, schedule another flush
            if self._pending:
                self._schedule_flush()

    async def _execute_command(
        self,
        light_id: int,
        level: int,
        source: str,
    ) -> bool:
        """Execute a single light command."""
        if not self._control4:
            logger.warning(f"🔦 SKIP (no control4): light {light_id} → {level}%")
            return False

        try:
            logger.info(f"🔦 SET: light {light_id} → {level}% (source: {source})")
            success = await self._control4.set_light_level(light_id, level)
            if success:
                self._stats["commands_executed"] += 1
            return success
        except Exception as e:
            logger.error(f"🔦 ERROR: light {light_id} → {level}%: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get debouncer statistics."""
        return {
            **self._stats,
            "pending_count": len(self._pending),
            "tracked_lights": len(self._light_states),
            "efficiency": (
                f"{100 * (1 - self._stats['commands_executed'] / max(1, self._stats['commands_received'])):.1f}%"
                " commands saved"
            ),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "commands_received": 0,
            "commands_executed": 0,
            "commands_skipped_unchanged": 0,
            "commands_skipped_rate_limit": 0,
            "commands_coalesced": 0,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_debouncer_instance: LightCommandDebouncer | None = None


def get_light_debouncer() -> LightCommandDebouncer:
    """Get singleton LightCommandDebouncer instance."""
    global _debouncer_instance
    if _debouncer_instance is None:
        _debouncer_instance = LightCommandDebouncer()
    return _debouncer_instance


__all__ = [
    "LightCommandDebouncer",
    "get_light_debouncer",
]
