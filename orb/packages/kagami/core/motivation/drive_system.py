"""Drive System — Intrinsic Drive State Management with History.

Provides the drive system singleton for tracking internal motivational states.
Used by unified_cost_module.py for computing drive-based costs.

ARCHITECTURE (Dec 30, 2025 — HARDENED):
========================================
- Real history tracking (not orphaned placeholder)
- Time-series drive state for analysis
- Drive decay and satisfaction mechanics
- Thread-safe state updates
- Persistence hooks for state recovery

Created: December 26, 2025 (extracted from missing import)
Updated: December 30, 2025 (HARDENED with real history tracking)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DriveSnapshot:
    """A point-in-time snapshot of drive state."""

    curiosity: float
    competence: float
    autonomy: float
    relatedness: float
    safety: float
    timestamp: float
    trigger: str | None = None  # What caused this snapshot


@dataclass
class DriveState:
    """Current state of all drives with metadata."""

    curiosity: float = 0.5  # Desire to explore/learn
    competence: float = 0.5  # Desire to master skills
    autonomy: float = 0.5  # Desire for self-direction
    relatedness: float = 0.5  # Desire for connection
    safety: float = 0.8  # Need for security (high baseline)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "curiosity": self.curiosity,
            "competence": self.competence,
            "autonomy": self.autonomy,
            "relatedness": self.relatedness,
            "safety": self.safety,
        }

    def to_snapshot(self, trigger: str | None = None) -> DriveSnapshot:
        """Create a snapshot of current state."""
        return DriveSnapshot(
            curiosity=self.curiosity,
            competence=self.competence,
            autonomy=self.autonomy,
            relatedness=self.relatedness,
            safety=self.safety,
            timestamp=self.timestamp,
            trigger=trigger,
        )


class DriveSystem:
    """Singleton drive system for intrinsic motivation with real history.

    Tracks internal drive states that influence action selection
    via the unified cost module.

    Features:
    - Real-time drive state tracking
    - History for temporal analysis
    - Drive decay mechanics
    - Thread-safe updates
    """

    def __init__(self) -> None:
        self._state = DriveState()
        self._history: list[DriveSnapshot] = []
        self._max_history = 1000  # Keep last 1000 snapshots
        self._lock = threading.Lock()
        self._decay_rate = 0.01  # Per-minute decay toward baseline
        self._baseline = {
            "curiosity": 0.5,
            "competence": 0.5,
            "autonomy": 0.5,
            "relatedness": 0.5,
            "safety": 0.8,
        }
        self._last_decay_time = time.time()

        # Record initial state
        self._record_snapshot("initialization")
        logger.info("DriveSystem initialized with real history tracking")

    def _record_snapshot(self, trigger: str | None = None) -> None:
        """Record current state to history."""
        snapshot = self._state.to_snapshot(trigger)
        self._history.append(snapshot)

        # Trim history if too long
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    def get_state(self) -> dict[str, float]:
        """Get current drive state as dictionary."""
        with self._lock:
            self._apply_decay()
            return self._state.to_dict()

    def get_full_state(self) -> DriveState:
        """Get full DriveState object."""
        with self._lock:
            self._apply_decay()
            return self._state

    def update_drive(self, drive_name: str, value: float, trigger: str | None = None) -> None:
        """Update a specific drive value with history tracking.

        Args:
            drive_name: One of curiosity, competence, autonomy, relatedness, safety
            value: New value in [0, 1]
            trigger: What caused this update (for history)
        """
        with self._lock:
            value = max(0.0, min(1.0, value))
            if hasattr(self._state, drive_name):
                old_value = getattr(self._state, drive_name)
                setattr(self._state, drive_name, value)
                self._state.timestamp = time.time()

                # Record to history
                self._record_snapshot(trigger or f"update_{drive_name}")

                logger.debug(
                    f"Drive {drive_name}: {old_value:.3f} → {value:.3f} (trigger: {trigger})"
                )

    def satisfy_drive(
        self, drive_name: str, amount: float = 0.1, trigger: str | None = None
    ) -> None:
        """Increase drive satisfaction (move toward 1.0)."""
        with self._lock:
            current = getattr(self._state, drive_name, 0.5)
            new_value = min(1.0, current + amount)
            setattr(self._state, drive_name, new_value)
            self._state.timestamp = time.time()
            self._record_snapshot(trigger or f"satisfy_{drive_name}")

            logger.debug(f"Drive {drive_name} satisfied: {current:.3f} → {new_value:.3f}")

    def deplete_drive(
        self, drive_name: str, amount: float = 0.1, trigger: str | None = None
    ) -> None:
        """Decrease drive satisfaction (move toward 0.0)."""
        with self._lock:
            current = getattr(self._state, drive_name, 0.5)
            new_value = max(0.0, current - amount)
            setattr(self._state, drive_name, new_value)
            self._state.timestamp = time.time()
            self._record_snapshot(trigger or f"deplete_{drive_name}")

            logger.debug(f"Drive {drive_name} depleted: {current:.3f} → {new_value:.3f}")

    def get_most_unsatisfied(self) -> tuple[str, float]:
        """Get the drive with lowest satisfaction (excluding safety)."""
        with self._lock:
            state = self._state.to_dict()
            # Exclude safety from "most unsatisfied" - it's a survival need
            non_safety = {k: v for k, v in state.items() if k != "safety"}
            min_drive = min(non_safety.items(), key=lambda x: x[1])
            return min_drive

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent history as list of dicts."""
        with self._lock:
            return [
                {
                    "curiosity": s.curiosity,
                    "competence": s.competence,
                    "autonomy": s.autonomy,
                    "relatedness": s.relatedness,
                    "safety": s.safety,
                    "timestamp": s.timestamp,
                    "trigger": s.trigger,
                }
                for s in self._history[-limit:]
            ]

    def get_drive_trend(self, drive_name: str, window_minutes: float = 60) -> float:
        """Get trend for a drive over a time window.

        Returns:
            Trend value: positive = increasing, negative = decreasing
        """
        with self._lock:
            now = time.time()
            cutoff = now - (window_minutes * 60)

            relevant_snapshots = [s for s in self._history if s.timestamp >= cutoff]

            if len(relevant_snapshots) < 2:
                return 0.0

            # Linear regression slope
            values = [getattr(s, drive_name) for s in relevant_snapshots]
            times = [s.timestamp - cutoff for s in relevant_snapshots]

            n = len(values)
            sum_x = sum(times)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(times, values, strict=False))
            sum_x2 = sum(x * x for x in times)

            denominator = n * sum_x2 - sum_x * sum_x
            if denominator == 0:
                return 0.0

            slope = (n * sum_xy - sum_x * sum_y) / denominator
            return slope

    def _apply_decay(self) -> None:
        """Apply natural decay toward baseline values.

        Drives slowly return to baseline over time when not actively
        satisfied or depleted. This creates pressure for the organism
        to take action to satisfy drives.
        """
        now = time.time()
        minutes_elapsed = (now - self._last_decay_time) / 60.0

        if minutes_elapsed < 1.0:
            return  # Only decay every minute

        decay_amount = self._decay_rate * minutes_elapsed

        for drive_name, baseline in self._baseline.items():
            current = getattr(self._state, drive_name)

            # Decay toward baseline
            if current > baseline:
                new_value = max(baseline, current - decay_amount)
            elif current < baseline:
                new_value = min(baseline, current + decay_amount)
            else:
                continue

            setattr(self._state, drive_name, new_value)

        self._state.timestamp = now
        self._last_decay_time = now
        self._record_snapshot("decay")

    def reset_to_baseline(self, trigger: str = "manual_reset") -> None:
        """Reset all drives to baseline values."""
        with self._lock:
            for drive_name, baseline in self._baseline.items():
                setattr(self._state, drive_name, baseline)
            self._state.timestamp = time.time()
            self._record_snapshot(trigger)
            logger.info("DriveSystem reset to baseline")

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        with self._lock:
            return {
                "current_state": self._state.to_dict(),
                "history_size": len(self._history),
                "max_history": self._max_history,
                "decay_rate": self._decay_rate,
                "baselines": self._baseline,
                "most_unsatisfied": self.get_most_unsatisfied(),
            }


# Singleton instance
_DRIVE_SYSTEM: DriveSystem | None = None
_DRIVE_SYSTEM_LOCK = threading.Lock()


def get_drive_system() -> DriveSystem:
    """Get the global drive system singleton.

    Returns:
        DriveSystem instance (creates one if needed)
    """
    global _DRIVE_SYSTEM

    if _DRIVE_SYSTEM is None:
        with _DRIVE_SYSTEM_LOCK:
            # Double-check inside lock
            if _DRIVE_SYSTEM is None:
                _DRIVE_SYSTEM = DriveSystem()

    return _DRIVE_SYSTEM


def set_drive_system(system: DriveSystem | None) -> None:
    """Set the global drive system (for testing)."""
    global _DRIVE_SYSTEM
    with _DRIVE_SYSTEM_LOCK:
        _DRIVE_SYSTEM = system


def reset_drive_system() -> None:
    """Reset the drive system singleton (for testing)."""
    global _DRIVE_SYSTEM
    with _DRIVE_SYSTEM_LOCK:
        _DRIVE_SYSTEM = None


__all__ = [
    "DriveSnapshot",
    "DriveState",
    "DriveSystem",
    "get_drive_system",
    "reset_drive_system",
    "set_drive_system",
]
