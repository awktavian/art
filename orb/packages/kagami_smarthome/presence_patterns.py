"""Presence Pattern Learning — Time-based behavior learning.

Provides pattern learning for presence inference:
- TimeSlot: 30-minute granularity time slots
- RoomOccupancy: Per-room occupancy tracking
- PatternRecord: Learned patterns for time slots
- PatternLearner: EMA-based pattern learning

Created: December 29, 2025
Split from presence.py: January 2, 2026
"""

from __future__ import annotations

import datetime
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from kagami_smarthome.types import ActivityContext

logger = logging.getLogger(__name__)


@dataclass
class TimeSlot:
    """Time slot for pattern learning (30-minute granularity)."""

    hour: int
    half: int  # 0 or 1
    weekday: bool  # True = Mon-Fri

    @classmethod
    def current(cls) -> TimeSlot:
        now = datetime.datetime.now()
        return cls(
            hour=now.hour,
            half=0 if now.minute < 30 else 1,
            weekday=now.weekday() < 5,
        )

    @classmethod
    def from_timestamp(cls, ts: float) -> TimeSlot:
        dt = datetime.datetime.fromtimestamp(ts)
        return cls(
            hour=dt.hour,
            half=0 if dt.minute < 30 else 1,
            weekday=dt.weekday() < 5,
        )

    def __hash__(self) -> int:
        return hash((self.hour, self.half, self.weekday))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeSlot):
            return False
        return self.hour == other.hour and self.half == other.half and self.weekday == other.weekday


@dataclass
class RoomOccupancy:
    """Tracks occupancy for a single room."""

    room_name: str
    occupied: bool = False
    last_motion: float = 0.0
    motion_count: int = 0

    # Time spent in room (rolling 24h)
    time_in_room: float = 0.0
    entry_time: float | None = None

    # Activity inference
    current_activity: ActivityContext = ActivityContext.UNKNOWN

    def enter(self, timestamp: float | None = None) -> None:
        """Mark room as entered."""
        ts = timestamp or time.time()
        if not self.occupied:
            self.occupied = True
            self.entry_time = ts
        self.last_motion = ts
        self.motion_count += 1

    def exit(self, timestamp: float | None = None) -> None:
        """Mark room as exited."""
        ts = timestamp or time.time()
        if self.occupied and self.entry_time:
            self.time_in_room += ts - self.entry_time
        self.occupied = False
        self.entry_time = None

    def time_since_motion(self) -> float:
        """Seconds since last motion."""
        return time.time() - self.last_motion if self.last_motion else float("inf")


@dataclass
class PatternRecord:
    """A learned pattern for a time slot."""

    # Room presence probabilities (learned)
    room_probabilities: dict[str, float] = field(default_factory=dict)

    # Activity probabilities
    activity_probabilities: dict[str, float] = field(default_factory=dict)

    # Transition probabilities (from_room -> to_room -> probability)
    transitions: dict[str, dict[str, float]] = field(default_factory=lambda: defaultdict(dict))

    # Sample count (for confidence)
    samples: int = 0


class PatternLearner:
    """Learns daily PRESENCE patterns from observed behavior.

    NOTE (Dec 30, 2025): This is distinct from kagami.core.learning.PatternLearner.
    - This class: Room/activity/transition probabilities (presence-specific)
    - Core class: General-purpose binary/continuous value patterns

    Tracks:
    - Where Tim is at what time (room probabilities)
    - What Tim does at what time (activity probabilities)
    - Where Tim goes next (transition probabilities)
    - Preferred settings per activity

    Uses exponential moving average for learning.
    """

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate

        # Pattern storage by time slot
        self._patterns: dict[TimeSlot, PatternRecord] = defaultdict(PatternRecord)

        # Recent transitions for learning
        self._last_room: str | None = None
        self._last_room_time: float = 0.0

        # Preference adjustments (room -> activity -> setting -> value)
        self._preferences: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )

    def observe_room(self, room_name: str, timestamp: float | None = None) -> None:
        """Record observation of being in a room."""
        ts = timestamp or time.time()
        slot = TimeSlot.from_timestamp(ts)
        pattern = self._patterns[slot]

        # Update room probability
        alpha = self.learning_rate
        for room in pattern.room_probabilities:
            # Decay other rooms
            pattern.room_probabilities[room] *= 1 - alpha

        # Increase observed room
        current = pattern.room_probabilities.get(room_name, 0.0)
        pattern.room_probabilities[room_name] = current + alpha * (1 - current)

        # Learn transition
        if self._last_room and self._last_room != room_name:
            # Only count transitions within 30 minutes
            if ts - self._last_room_time < 1800:
                transitions = pattern.transitions[self._last_room]
                current_prob = transitions.get(room_name, 0.0)
                transitions[room_name] = current_prob + alpha * (1 - current_prob)

        self._last_room = room_name
        self._last_room_time = ts
        pattern.samples += 1

    def observe_activity(self, activity: ActivityContext, timestamp: float | None = None) -> None:
        """Record observation of activity."""
        ts = timestamp or time.time()
        slot = TimeSlot.from_timestamp(ts)
        pattern = self._patterns[slot]

        alpha = self.learning_rate
        for act in pattern.activity_probabilities:
            pattern.activity_probabilities[act] *= 1 - alpha

        current = pattern.activity_probabilities.get(activity.value, 0.0)
        pattern.activity_probabilities[activity.value] = current + alpha * (1 - current)

    def learn_preference(
        self,
        room_name: str,
        activity: ActivityContext,
        setting: str,
        value: float,
    ) -> None:
        """Learn preference from manual adjustment."""
        alpha = self.learning_rate
        prefs = self._preferences[room_name][activity.value]
        current = prefs.get(setting, value)
        prefs[setting] = current * (1 - alpha) + value * alpha

    def predict_next_room(self, current_room: str) -> tuple[str, float] | None:
        """Predict most likely next room from current.

        Returns:
            (room_name, probability) or None
        """
        slot = TimeSlot.current()
        pattern = self._patterns.get(slot)

        if not pattern or current_room not in pattern.transitions:
            return None

        transitions = pattern.transitions[current_room]
        if not transitions:
            return None

        # Get most probable next room
        best_room = max(transitions.keys(), key=lambda r: transitions[r])
        return (best_room, transitions[best_room])

    def predict_room_at_time(self, slot: TimeSlot) -> tuple[str, float] | None:
        """Predict most likely room at a time slot.

        Returns:
            (room_name, probability) or None
        """
        pattern = self._patterns.get(slot)

        if not pattern or not pattern.room_probabilities:
            return None

        best_room = max(
            pattern.room_probabilities.keys(), key=lambda r: pattern.room_probabilities[r]
        )
        return (best_room, pattern.room_probabilities[best_room])

    def predict_activity_at_time(self, slot: TimeSlot) -> tuple[ActivityContext, float] | None:
        """Predict most likely activity at a time slot."""
        pattern = self._patterns.get(slot)

        if not pattern or not pattern.activity_probabilities:
            return None

        best_activity = max(
            pattern.activity_probabilities.keys(), key=lambda a: pattern.activity_probabilities[a]
        )
        try:
            return (ActivityContext(best_activity), pattern.activity_probabilities[best_activity])
        except ValueError:
            return None

    def get_preferred_setting(
        self,
        room_name: str,
        activity: ActivityContext,
        setting: str,
        default: float,
    ) -> float:
        """Get learned preference for a setting."""
        prefs = self._preferences.get(room_name, {}).get(activity.value, {})
        return prefs.get(setting, default)

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def save_to_file(self, path: str) -> bool:
        """Save learned patterns to disk.

        Args:
            path: Path to save file (JSON format)

        Returns:
            True if saved successfully
        """
        import json

        try:
            # Convert patterns to serializable format
            patterns_data = {}
            for slot, pattern in self._patterns.items():
                slot_key = f"{slot.hour}:{slot.half}:{'wd' if slot.weekday else 'we'}"
                patterns_data[slot_key] = {
                    "room_probabilities": dict(pattern.room_probabilities),
                    "activity_probabilities": dict(pattern.activity_probabilities),
                    "transitions": {
                        from_room: dict(to_rooms)
                        for from_room, to_rooms in pattern.transitions.items()
                    },
                    "samples": pattern.samples,
                }

            # Convert preferences to serializable format
            preferences_data = {}
            for room, activities in self._preferences.items():
                preferences_data[room] = {}
                for activity, settings in activities.items():
                    preferences_data[room][activity] = dict(settings)

            data = {
                "version": 1,
                "learning_rate": self.learning_rate,
                "patterns": patterns_data,
                "preferences": preferences_data,
                "last_room": self._last_room,
                "last_room_time": self._last_room_time,
            }

            with open(path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"📊 PatternLearner saved to {path} ({len(patterns_data)} slots)")
            return True

        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
            return False

    @classmethod
    def load_from_file(cls, path: str) -> PatternLearner | None:
        """Load learned patterns from disk.

        Args:
            path: Path to saved file

        Returns:
            PatternLearner instance or None if failed
        """
        import json
        import os

        if not os.path.exists(path):
            logger.debug(f"No saved patterns at {path}")
            return None

        try:
            with open(path) as f:
                data = json.load(f)

            version = data.get("version", 1)
            if version != 1:
                logger.warning(f"Unknown pattern version: {version}")
                return None

            # Create instance
            learner = cls(learning_rate=data.get("learning_rate", 0.1))

            # Restore patterns
            patterns_data = data.get("patterns", {})
            for slot_key, pattern_data in patterns_data.items():
                # Parse slot key
                parts = slot_key.split(":")
                hour = int(parts[0])
                half = int(parts[1])
                weekday = parts[2] == "wd"
                slot = TimeSlot(hour=hour, half=half, weekday=weekday)

                # Create pattern record
                pattern = PatternRecord(
                    room_probabilities=pattern_data.get("room_probabilities", {}),
                    activity_probabilities=pattern_data.get("activity_probabilities", {}),
                    transitions=defaultdict(
                        dict,
                        {
                            from_room: dict(to_rooms)
                            for from_room, to_rooms in pattern_data.get("transitions", {}).items()
                        },
                    ),
                    samples=pattern_data.get("samples", 0),
                )
                learner._patterns[slot] = pattern

            # Restore preferences
            preferences_data = data.get("preferences", {})
            for room, activities in preferences_data.items():
                for activity, settings in activities.items():
                    learner._preferences[room][activity] = dict(settings)

            # Restore state
            learner._last_room = data.get("last_room")
            learner._last_room_time = data.get("last_room_time", 0.0)

            logger.info(f"📊 PatternLearner loaded from {path} ({len(patterns_data)} slots)")
            return learner

        except Exception as e:
            logger.error(f"Failed to load patterns: {e}")
            return None

    def get_pattern_stats(self) -> dict[str, Any]:
        """Get statistics about learned patterns."""
        total_samples = sum(p.samples for p in self._patterns.values())
        rooms_learned = set()
        activities_learned = set()

        for pattern in self._patterns.values():
            rooms_learned.update(pattern.room_probabilities.keys())
            activities_learned.update(pattern.activity_probabilities.keys())

        return {
            "total_time_slots": len(self._patterns),
            "total_samples": total_samples,
            "rooms_learned": list(rooms_learned),
            "activities_learned": list(activities_learned),
            "preference_rooms": list(self._preferences.keys()),
        }


__all__ = [
    "PatternLearner",
    "PatternRecord",
    "RoomOccupancy",
    "TimeSlot",
]
