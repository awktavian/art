"""Presence Intent Prediction — Multi-signal fusion for intent inference.

Provides intent prediction by fusing multiple signals:
- Time of day
- Current room
- Recent activity
- Device states
- Historical patterns

Created: December 29, 2025
Split from presence.py: January 2, 2026
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from kagami_smarthome.presence_patterns import PatternLearner, TimeSlot
from kagami_smarthome.types import ActivityContext

if TYPE_CHECKING:
    pass


class IntentPredictor:
    """Predicts user intent from multi-signal fusion.

    Combines:
    - Time of day
    - Current room
    - Recent activity
    - Device states
    - Historical patterns

    To predict:
    - What activity is starting
    - What room is next
    - What automation should trigger
    """

    def __init__(self, pattern_learner: PatternLearner):
        self.patterns = pattern_learner

        # Signal weights
        self._signal_weights = {
            "time": 0.3,
            "location": 0.25,
            "pattern": 0.25,
            "device": 0.2,
        }

    def predict_intent(
        self,
        current_room: str | None,
        current_activity: ActivityContext,
        device_states: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Predict user intent.

        Args:
            current_room: Current room name or None
            current_activity: Current activity context
            device_states: Optional dict of device states

        Returns:
            Dict with predicted activity, room, confidence, and reasoning
        """
        now = datetime.datetime.now()
        hour = now.hour

        # Collect evidence
        evidence = {
            "time_activity": self._activity_from_time(hour),
            "pattern_activity": None,
            "pattern_room": None,
            "device_hints": [],
        }

        # Pattern-based prediction
        slot = TimeSlot.current()
        pattern_activity = self.patterns.predict_activity_at_time(slot)
        if pattern_activity:
            evidence["pattern_activity"] = pattern_activity[0]

        pattern_room = self.patterns.predict_room_at_time(slot)
        if pattern_room:
            evidence["pattern_room"] = pattern_room[0]

        # Device state hints
        if device_states:
            if device_states.get("eight_sleep_awake"):
                evidence["device_hints"].append("waking")
            if device_states.get("denon_on"):
                evidence["device_hints"].append("watching")
            if device_states.get("car_home"):
                evidence["device_hints"].append("home")
            if device_states.get("car_away"):
                evidence["device_hints"].append("arriving_or_leaving")

        # Fuse evidence
        predicted_activity = self._fuse_activity_evidence(evidence)

        # Predict next room
        next_room = None
        if current_room:
            transition = self.patterns.predict_next_room(current_room)
            if transition:
                next_room = transition[0]

        confidence = 0.7 if pattern_activity else 0.5

        return {
            "predicted_activity": predicted_activity,
            "predicted_next_room": next_room,
            "confidence": confidence,
            "evidence": evidence,
            "reasoning": self._generate_reasoning(evidence, predicted_activity),
        }

    def _activity_from_time(self, hour: int) -> ActivityContext:
        """Get activity from time of day.

        Args:
            hour: Hour of day (0-23)

        Returns:
            Most likely activity for this time
        """
        if 5 <= hour < 8:
            return ActivityContext.WAKING
        elif 8 <= hour < 12:
            return ActivityContext.WORKING
        elif 12 <= hour < 14:
            return ActivityContext.COOKING  # Lunch
        elif 14 <= hour < 17:
            return ActivityContext.WORKING
        elif 17 <= hour < 19:
            return ActivityContext.COOKING  # Dinner
        elif 19 <= hour < 22:
            return ActivityContext.RELAXING
        else:
            return ActivityContext.SLEEPING

    def _fuse_activity_evidence(self, evidence: dict) -> ActivityContext:
        """Fuse multiple evidence sources.

        Priority: device hints > pattern > time
        """
        hints = evidence.get("device_hints", [])

        if "waking" in hints:
            return ActivityContext.WAKING
        if "watching" in hints:
            return ActivityContext.WATCHING

        pattern_act = evidence.get("pattern_activity")
        if pattern_act:
            return pattern_act

        return evidence.get("time_activity", ActivityContext.UNKNOWN)

    def _generate_reasoning(
        self,
        evidence: dict,
        predicted: ActivityContext,
    ) -> str:
        """Generate human-readable reasoning.

        Args:
            evidence: Collected evidence dict
            predicted: Final predicted activity

        Returns:
            Human-readable explanation string
        """
        parts = []

        if evidence.get("device_hints"):
            parts.append(f"Device signals: {', '.join(evidence['device_hints'])}")

        if evidence.get("pattern_activity"):
            parts.append(f"Pattern suggests: {evidence['pattern_activity'].value}")

        if evidence.get("time_activity"):
            parts.append(f"Time suggests: {evidence['time_activity'].value}")

        parts.append(f"Predicted: {predicted.value}")

        return "; ".join(parts)


__all__ = ["IntentPredictor"]
