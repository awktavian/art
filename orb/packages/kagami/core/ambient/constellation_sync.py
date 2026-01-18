"""Constellation Sync - Multi-device state synchronization.

Extracted from controller.py (January 2026) to isolate constellation
synchronization logic from the main orchestrator.

The ConstellationSync handles:
- Building minimal ambient state snapshots
- Rate-limited synchronization to MultiDeviceCoordinator
- Delta detection to minimize network traffic
- Quiet mode (ma) determination
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Protocol

from kagami.core.ambient.data_types import (
    AmbientState,
    Colony,
    ColonyState,
    PresenceLevel,
)

if TYPE_CHECKING:
    from kagami.core.ambient.consent import ConsentManager

logger = logging.getLogger(__name__)


class ColonyExpressorProtocol(Protocol):
    """Protocol for colony expressor interface."""

    def get_dominant_colony(
        self, colonies: dict[Colony, ColonyState]
    ) -> tuple[Colony, float] | None: ...


class ConstellationSyncConfig:
    """Configuration for constellation sync."""

    def __init__(
        self,
        *,
        sync_interval_s: float = 2.0,
        enabled: bool = True,
    ):
        self.sync_interval_s = sync_interval_s
        self.enabled = enabled


class ConstellationSync:
    """Manages multi-device state synchronization.

    This class handles rate-limited synchronization of ambient state
    to the MultiDeviceCoordinator, building minimal JSON-friendly
    snapshots and detecting deltas to minimize network traffic.
    """

    def __init__(self, config: ConstellationSyncConfig | None = None):
        """Initialize constellation sync.

        Args:
            config: Constellation sync configuration
        """
        self.config = config or ConstellationSyncConfig()

        # Coordinator reference
        self._coordinator: Any = None  # MultiDeviceCoordinator

        # State references
        self._state: AmbientState | None = None
        self._expressor: ColonyExpressorProtocol | None = None
        self._consent: ConsentManager | None = None

        # Rate limiting
        self._last_sync: float = 0.0
        self._last_state: dict[str, Any] = {}
        self._sync_lock: asyncio.Lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "syncs": 0,
            "skipped": 0,
        }

    def set_coordinator(self, coordinator: Any) -> None:
        """Set the MultiDeviceCoordinator.

        Args:
            coordinator: MultiDeviceCoordinator instance
        """
        self._coordinator = coordinator

    def set_state_source(self, state: AmbientState) -> None:
        """Set the ambient state source.

        Args:
            state: AmbientState to sync from
        """
        self._state = state

    def set_expressor(self, expressor: ColonyExpressorProtocol) -> None:
        """Set colony expressor for dominant colony detection.

        Args:
            expressor: ColonyExpressor instance
        """
        self._expressor = expressor

    def set_consent(self, consent: ConsentManager) -> None:
        """Set consent manager for quiet mode detection.

        Args:
            consent: ConsentManager instance
        """
        self._consent = consent

    def _build_updates(self) -> dict[str, Any]:
        """Build a minimal, JSON-friendly ambient snapshot.

        Returns:
            Dictionary of ambient state for constellation sync
        """
        if self._state is None:
            return {}

        # Dominant colony (single voice)
        active_colony: Colony | None = None
        active_activation: float = 0.0
        if self._expressor and self._state.colonies:
            dominant = self._expressor.get_dominant_colony(self._state.colonies)
            if dominant:
                active_colony, active_activation = dominant

        # Quiet mode heuristic
        quiet = False
        quiet_reason: str | None = None
        if self._consent and self._consent.is_paused:
            quiet = True
            quiet_reason = "paused"
        elif self._state.presence.level == PresenceLevel.FOCUSED:
            quiet = True
            quiet_reason = "focused"

        return {
            # Timestamp
            "ambient.timestamp": float(getattr(self._state, "timestamp", time.time())),
            # Breath
            "ambient.breath.phase": self._state.breath.phase.value,
            "ambient.breath.progress": round(float(self._state.breath.phase_progress), 4),
            "ambient.breath.cycle": int(self._state.breath.cycle_count),
            "ambient.breath.bpm": float(self._state.breath.bpm),
            # Presence
            "ambient.presence.level": self._state.presence.level.value,
            "ambient.presence.confidence": round(float(self._state.presence.confidence), 3),
            # Safety
            "ambient.safety.h": round(float(self._state.safety.h_value), 4),
            "ambient.safety.safe": bool(self._state.safety.is_safe),
            # Colony expression
            "ambient.colony.active": active_colony.value if active_colony else None,
            "ambient.colony.activation": round(float(active_activation), 4),
            # Quiet mode ("ma")
            "ambient.quiet": bool(quiet),
            "ambient.quiet.reason": quiet_reason,
        }

    async def sync(self, *, force: bool = False) -> None:
        """Rate-limited sync of ambient state to constellation.

        Args:
            force: Force sync even if rate limited
        """
        if self._coordinator is None or not self.config.enabled:
            return

        # Rate limit check
        now = time.monotonic()
        if (
            not force
            and self.config.sync_interval_s > 0
            and (now - self._last_sync) < self.config.sync_interval_s
        ):
            self._stats["skipped"] += 1
            return

        updates = self._build_updates()
        delta = {k: v for k, v in updates.items() if self._last_state.get(k) != v}
        if not delta and not force:
            self._stats["skipped"] += 1
            return

        async with self._sync_lock:
            # Recheck under lock
            now2 = time.monotonic()
            if (
                not force
                and self.config.sync_interval_s > 0
                and (now2 - self._last_sync) < self.config.sync_interval_s
            ):
                return

            updates2 = self._build_updates()
            delta2 = {k: v for k, v in updates2.items() if self._last_state.get(k) != v}

            payload = delta2 if delta2 else updates2
            try:
                await self._coordinator.sync_state(payload)
                self._last_state.update(payload)
                self._last_sync = time.monotonic()
                self._stats["syncs"] += 1
            except Exception as e:
                logger.debug(f"Constellation sync failed: {e}")

    def get_stats(self) -> dict[str, int]:
        """Get constellation sync statistics.

        Returns:
            Statistics dictionary
        """
        return dict(self._stats)
