"""Predictive Presence — ML-driven presence forecasting and anticipation.

This module implements predictive presence capabilities that anticipate
where household members will be based on learned patterns.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PREDICTIVE PRESENCE SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Data Sources                      Prediction Model                     │
│   ───────────────                   ────────────────                     │
│   • Historical patterns             • Time-of-day features               │
│   • Calendar events                 • Day-of-week features               │
│   • Work schedule                   • Weather features                   │
│   • Weather data                    • Calendar features                  │
│   • Time-of-day                     • Markov chain transitions           │
│                                                                          │
│   ┌─────────────────┐   predict()   ┌─────────────────┐                 │
│   │  PresenceHistory │─────────────►│   PredictedState │                 │
│   │   (Redis/etcd)   │              │   (room, prob)   │                 │
│   └─────────────────┘              └─────────────────┘                 │
│                                                                          │
│   Anticipatory Actions:                                                  │
│   • Pre-warm HVAC before arrival                                        │
│   • Pre-heat/cool rooms on predicted path                               │
│   • Adjust lighting before entry                                        │
│   • Prepare coffee maker timing                                         │
│                                                                          │
│   Colony: Flow (A₄) — Anticipation and smooth transitions               │
│   h(x) ≥ 0. Always.                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from kagami.core.caching.redis import RedisClientFactory

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


class ActivityState(str, Enum):
    """High-level activity states for prediction."""

    ASLEEP = "asleep"
    WAKING = "waking"
    MORNING_ROUTINE = "morning_routine"
    WORKING = "working"
    BREAK = "break"
    LUNCH = "lunch"
    AFTERNOON_WORK = "afternoon_work"
    EVENING = "evening"
    RELAXING = "relaxing"
    PREPARING_BED = "preparing_bed"
    AWAY = "away"
    UNKNOWN = "unknown"


@dataclass
class RoomPrediction:
    """Prediction for a specific room."""

    room_id: str
    probability: float  # 0.0 - 1.0
    confidence: float  # Confidence in prediction
    expected_duration_minutes: float
    reason: str = ""  # Why this prediction

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "room_id": self.room_id,
            "probability": self.probability,
            "confidence": self.confidence,
            "expected_duration_minutes": self.expected_duration_minutes,
            "reason": self.reason,
        }


@dataclass
class PresencePrediction:
    """Full presence prediction for a user."""

    user_id: str
    current_room: str | None
    predicted_room: str | None
    activity_state: ActivityState
    room_predictions: list[RoomPrediction]
    time_horizon_minutes: int
    timestamp: float = field(default_factory=time.time)

    @property
    def top_prediction(self) -> RoomPrediction | None:
        """Get highest probability room prediction."""
        if not self.room_predictions:
            return None
        return max(self.room_predictions, key=lambda p: p.probability)

    @property
    def likely_transition(self) -> bool:
        """Check if transition is likely soon."""
        top = self.top_prediction
        if not top:
            return False
        return top.room_id != self.current_room and top.probability > 0.5

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "current_room": self.current_room,
            "predicted_room": self.predicted_room,
            "activity_state": self.activity_state.value,
            "room_predictions": [p.to_dict() for p in self.room_predictions],
            "time_horizon_minutes": self.time_horizon_minutes,
            "timestamp": self.timestamp,
        }


@dataclass
class PresenceTransition:
    """Record of a room transition."""

    user_id: str
    from_room: str
    to_room: str
    timestamp: float
    day_of_week: int  # 0=Monday, 6=Sunday
    hour_of_day: int  # 0-23
    minute_of_hour: int  # 0-59
    duration_in_from_minutes: float  # How long in previous room


# =============================================================================
# Transition Matrix (Markov Chain)
# =============================================================================


class TransitionMatrix:
    """Markov chain transition matrix for room predictions.

    Tracks transition probabilities between rooms based on:
    - Time of day
    - Day of week
    - Previous room
    - Duration in current room
    """

    def __init__(self) -> None:
        # transitions[from_room][to_room][time_bucket] = count
        self._transitions: dict[str, dict[str, dict[int, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        self._room_visits: dict[str, int] = defaultdict(int)
        self._total_transitions = 0

    def add_transition(self, transition: PresenceTransition) -> None:
        """Add a transition to the matrix.

        Args:
            transition: Transition record.
        """
        time_bucket = self._get_time_bucket(transition.hour_of_day, transition.day_of_week)
        self._transitions[transition.from_room][transition.to_room][time_bucket] += 1
        self._room_visits[transition.to_room] += 1
        self._total_transitions += 1

    def get_transition_probability(
        self,
        from_room: str,
        to_room: str,
        hour: int,
        day_of_week: int,
    ) -> float:
        """Get probability of transitioning from one room to another.

        Args:
            from_room: Current room.
            to_room: Target room.
            hour: Hour of day (0-23).
            day_of_week: Day of week (0=Monday).

        Returns:
            Probability (0.0 - 1.0).
        """
        time_bucket = self._get_time_bucket(hour, day_of_week)

        # Get counts for this time bucket
        from_transitions = self._transitions.get(from_room, {})
        to_counts = from_transitions.get(to_room, {})
        specific_count = to_counts.get(time_bucket, 0)

        # Total transitions from this room at this time
        total_from_room = sum(counts.get(time_bucket, 0) for counts in from_transitions.values())

        if total_from_room == 0:
            # No data for this time, use global room probability
            if self._total_transitions == 0:
                return 0.1  # Default low probability
            return self._room_visits.get(to_room, 0) / self._total_transitions

        return specific_count / total_from_room

    def get_likely_next_rooms(
        self,
        from_room: str,
        hour: int,
        day_of_week: int,
        top_k: int = 3,
    ) -> list[tuple[str, float]]:
        """Get most likely next rooms from current room.

        Args:
            from_room: Current room.
            hour: Hour of day.
            day_of_week: Day of week.
            top_k: Number of top rooms to return.

        Returns:
            List of (room_id, probability) tuples.
        """
        from_transitions = self._transitions.get(from_room, {})
        if not from_transitions:
            # No transitions recorded from this room
            return []

        self._get_time_bucket(hour, day_of_week)

        # Calculate probabilities for all target rooms
        probabilities: list[tuple[str, float]] = []
        for to_room in from_transitions.keys():
            prob = self.get_transition_probability(from_room, to_room, hour, day_of_week)
            if prob > 0:
                probabilities.append((to_room, prob))

        # Sort by probability descending
        probabilities.sort(key=lambda x: x[1], reverse=True)

        return probabilities[:top_k]

    def _get_time_bucket(self, hour: int, day_of_week: int) -> int:
        """Get time bucket for indexing.

        Buckets: 4-hour windows × 2 (weekday/weekend) = 12 buckets
        """
        hour_bucket = hour // 4  # 0-5 (6 buckets per day type)
        is_weekend = 1 if day_of_week >= 5 else 0
        return is_weekend * 6 + hour_bucket

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "transitions": {
                from_room: {to_room: dict(counts) for to_room, counts in to_rooms.items()}
                for from_room, to_rooms in self._transitions.items()
            },
            "room_visits": dict(self._room_visits),
            "total_transitions": self._total_transitions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransitionMatrix:
        """Deserialize from dictionary."""
        matrix = cls()
        for from_room, to_rooms in data.get("transitions", {}).items():
            for to_room, counts in to_rooms.items():
                for time_bucket_str, count in counts.items():
                    matrix._transitions[from_room][to_room][int(time_bucket_str)] = count
        matrix._room_visits = defaultdict(int, data.get("room_visits", {}))
        matrix._total_transitions = data.get("total_transitions", 0)
        return matrix


# =============================================================================
# Activity State Predictor
# =============================================================================


class ActivityStatePredictor:
    """Predicts current activity state based on time and context."""

    # Default schedule (can be customized per user)
    DEFAULT_SCHEDULE = {
        # weekday
        (0, 5): {  # 12am-6am weekday
            (0, 4): ActivityState.ASLEEP,
            (5, 6): ActivityState.WAKING,
        },
        (0, 6): {  # 6am-7am weekday
            (0, 59): ActivityState.MORNING_ROUTINE,
        },
        (0, 7): {  # 7am-8am weekday
            (0, 59): ActivityState.MORNING_ROUTINE,
        },
        (0, 8): {  # 8am onwards weekday
            (0, 11): ActivityState.WORKING,
        },
        (0, 12): {  # noon weekday
            (0, 0): ActivityState.LUNCH,
        },
        (0, 13): {  # 1pm onwards weekday
            (0, 17): ActivityState.AFTERNOON_WORK,
        },
        (0, 18): {  # 6pm onwards weekday
            (0, 21): ActivityState.EVENING,
        },
        (0, 22): {  # 10pm onwards weekday
            (0, 23): ActivityState.PREPARING_BED,
        },
    }

    def predict_activity(
        self,
        hour: int,
        minute: int,
        day_of_week: int,
        is_home: bool,
        current_room: str | None = None,
    ) -> ActivityState:
        """Predict activity state based on time and context.

        Args:
            hour: Hour (0-23).
            minute: Minute (0-59).
            day_of_week: Day of week (0=Monday).
            is_home: Whether user is home.
            current_room: Current room if known.

        Returns:
            Predicted ActivityState.
        """
        if not is_home:
            return ActivityState.AWAY

        is_weekend = day_of_week >= 5

        # Simple heuristic based on time
        if 0 <= hour < 5:
            return ActivityState.ASLEEP
        elif 5 <= hour < 6:
            return ActivityState.WAKING
        elif 6 <= hour < 8:
            return ActivityState.MORNING_ROUTINE
        elif 8 <= hour < 12:
            if is_weekend:
                return ActivityState.RELAXING
            return ActivityState.WORKING
        elif 12 <= hour < 13:
            return ActivityState.LUNCH
        elif 13 <= hour < 17:
            if is_weekend:
                return ActivityState.RELAXING
            return ActivityState.AFTERNOON_WORK
        elif 17 <= hour < 21:
            return ActivityState.EVENING
        elif 21 <= hour < 23:
            return ActivityState.RELAXING
        else:
            return ActivityState.PREPARING_BED


# =============================================================================
# Predictive Presence Manager
# =============================================================================


class PredictivePresenceManager:
    """Manages predictive presence with learning and anticipation.

    Features:
    - Learns from historical transitions
    - Predicts next room with probability
    - Suggests anticipatory actions
    - Integrates with calendar and weather

    Example:
        >>> manager = PredictivePresenceManager()
        >>> await manager.initialize()
        >>> prediction = await manager.predict("tim", horizon_minutes=15)
        >>> print(prediction.predicted_room)
    """

    REDIS_HISTORY_KEY = "kagami:presence:history"
    REDIS_MATRIX_KEY = "kagami:presence:matrix"

    def __init__(self) -> None:
        self._redis = RedisClientFactory.get_client()
        self._transition_matrix = TransitionMatrix()
        self._activity_predictor = ActivityStatePredictor()
        self._current_positions: dict[str, str] = {}
        self._position_timestamps: dict[str, float] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the predictive presence manager."""
        if self._initialized:
            return

        logger.info("Initializing PredictivePresenceManager...")

        # Load transition matrix from Redis
        try:
            matrix_data = await self._redis.get(self.REDIS_MATRIX_KEY)
            if matrix_data:
                data = json.loads(matrix_data.decode())
                self._transition_matrix = TransitionMatrix.from_dict(data)
                logger.info(
                    f"Loaded transition matrix "
                    f"({self._transition_matrix._total_transitions} transitions)"
                )
        except Exception as e:
            logger.warning(f"Could not load transition matrix: {e}")

        self._initialized = True
        logger.info("✅ PredictivePresenceManager initialized")

    async def shutdown(self) -> None:
        """Shutdown and save state."""
        # Save transition matrix
        await self._save_matrix()
        self._initialized = False
        logger.info("🛑 PredictivePresenceManager shutdown")

    async def record_position(self, user_id: str, room_id: str) -> None:
        """Record user's current position.

        Args:
            user_id: User identifier.
            room_id: Room they're in.
        """
        now = time.time()
        previous_room = self._current_positions.get(user_id)
        previous_timestamp = self._position_timestamps.get(user_id, now)

        # Update current position
        self._current_positions[user_id] = room_id
        self._position_timestamps[user_id] = now

        # Record transition if room changed
        if previous_room and previous_room != room_id:
            dt = datetime.fromtimestamp(now)
            duration_minutes = (now - previous_timestamp) / 60

            transition = PresenceTransition(
                user_id=user_id,
                from_room=previous_room,
                to_room=room_id,
                timestamp=now,
                day_of_week=dt.weekday(),
                hour_of_day=dt.hour,
                minute_of_hour=dt.minute,
                duration_in_from_minutes=duration_minutes,
            )

            self._transition_matrix.add_transition(transition)

            # Persist matrix periodically (every 10 transitions)
            if self._transition_matrix._total_transitions % 10 == 0:
                await self._save_matrix()

            logger.debug(
                f"Recorded transition: {previous_room} → {room_id} "
                f"(duration: {duration_minutes:.1f}min)"
            )

    async def predict(
        self,
        user_id: str,
        horizon_minutes: int = 15,
        current_room: str | None = None,
    ) -> PresencePrediction:
        """Predict user's presence for the next period.

        Args:
            user_id: User identifier.
            horizon_minutes: How far ahead to predict.
            current_room: Override current room (uses tracked if None).

        Returns:
            PresencePrediction with probabilities.
        """
        if current_room is None:
            current_room = self._current_positions.get(user_id)

        now = datetime.now()
        hour = now.hour
        day_of_week = now.weekday()

        # Predict activity state
        is_home = current_room is not None
        activity_state = self._activity_predictor.predict_activity(
            hour, now.minute, day_of_week, is_home, current_room
        )

        # Get likely next rooms
        room_predictions: list[RoomPrediction] = []
        predicted_room = current_room

        if current_room:
            likely_rooms = self._transition_matrix.get_likely_next_rooms(
                current_room, hour, day_of_week, top_k=5
            )

            for room_id, probability in likely_rooms:
                # Adjust probability based on activity state
                adjusted_prob = self._adjust_probability_for_activity(
                    probability, room_id, activity_state
                )

                # Estimate duration
                expected_duration = self._estimate_duration(room_id, activity_state)

                room_predictions.append(
                    RoomPrediction(
                        room_id=room_id,
                        probability=adjusted_prob,
                        confidence=min(0.9, self._transition_matrix._total_transitions / 100),
                        expected_duration_minutes=expected_duration,
                        reason=self._get_prediction_reason(activity_state, room_id),
                    )
                )

            # Get top prediction
            if room_predictions:
                predicted_room = max(room_predictions, key=lambda p: p.probability).room_id

        return PresencePrediction(
            user_id=user_id,
            current_room=current_room,
            predicted_room=predicted_room,
            activity_state=activity_state,
            room_predictions=room_predictions,
            time_horizon_minutes=horizon_minutes,
        )

    def _adjust_probability_for_activity(
        self,
        base_probability: float,
        room_id: str,
        activity_state: ActivityState,
    ) -> float:
        """Adjust probability based on activity state.

        Args:
            base_probability: Base transition probability.
            room_id: Target room.
            activity_state: Current activity state.

        Returns:
            Adjusted probability.
        """
        # Room-activity mappings (simplified)
        room_activity_boost = {
            ActivityState.ASLEEP: {"primary_bed": 1.5, "primary_bath": 0.3},
            ActivityState.MORNING_ROUTINE: {"primary_bath": 1.3, "kitchen": 1.2},
            ActivityState.WORKING: {"office": 1.5, "living_room": 0.8},
            ActivityState.LUNCH: {"kitchen": 1.4, "dining": 1.3},
            ActivityState.EVENING: {"living_room": 1.3, "kitchen": 1.2},
            ActivityState.PREPARING_BED: {"primary_bed": 1.4, "primary_bath": 1.2},
        }

        boosts = room_activity_boost.get(activity_state, {})
        multiplier = boosts.get(room_id, 1.0)

        return min(1.0, base_probability * multiplier)

    def _estimate_duration(
        self,
        room_id: str,
        activity_state: ActivityState,
    ) -> float:
        """Estimate expected duration in a room.

        Args:
            room_id: Room identifier.
            activity_state: Current activity state.

        Returns:
            Expected duration in minutes.
        """
        # Default durations by activity state
        activity_durations = {
            ActivityState.ASLEEP: 480,  # 8 hours
            ActivityState.WAKING: 15,
            ActivityState.MORNING_ROUTINE: 45,
            ActivityState.WORKING: 120,
            ActivityState.BREAK: 15,
            ActivityState.LUNCH: 30,
            ActivityState.AFTERNOON_WORK: 120,
            ActivityState.EVENING: 120,
            ActivityState.RELAXING: 60,
            ActivityState.PREPARING_BED: 30,
        }

        return activity_durations.get(activity_state, 30)

    def _get_prediction_reason(
        self,
        activity_state: ActivityState,
        room_id: str,
    ) -> str:
        """Get human-readable reason for prediction.

        Args:
            activity_state: Current activity state.
            room_id: Predicted room.

        Returns:
            Reason string.
        """
        reasons = {
            ActivityState.ASLEEP: "Sleep time - bedroom expected",
            ActivityState.WAKING: "Waking up - bathroom/kitchen likely",
            ActivityState.MORNING_ROUTINE: "Morning routine - bathroom/kitchen",
            ActivityState.WORKING: "Work hours - office expected",
            ActivityState.LUNCH: "Lunch time - kitchen/dining",
            ActivityState.EVENING: "Evening - living room expected",
            ActivityState.PREPARING_BED: "Bedtime - bedroom soon",
        }

        return reasons.get(activity_state, f"Historical pattern suggests {room_id}")

    async def _save_matrix(self) -> None:
        """Save transition matrix to Redis."""
        try:
            data = json.dumps(self._transition_matrix.to_dict())
            await self._redis.set(self.REDIS_MATRIX_KEY, data)
        except Exception as e:
            logger.error(f"Failed to save transition matrix: {e}")

    def get_anticipatory_actions(
        self,
        prediction: PresencePrediction,
    ) -> list[dict[str, Any]]:
        """Get suggested anticipatory actions based on prediction.

        Args:
            prediction: Presence prediction.

        Returns:
            List of suggested actions.
        """
        actions: list[dict[str, Any]] = []

        if not prediction.likely_transition:
            return actions

        top = prediction.top_prediction
        if not top or top.probability < 0.6:
            return actions

        target_room = top.room_id

        # HVAC anticipation
        if prediction.activity_state == ActivityState.WAKING:
            actions.append(
                {
                    "type": "hvac",
                    "action": "pre_heat" if self._is_cold_season() else "pre_cool",
                    "target_room": target_room,
                    "lead_time_minutes": 15,
                    "reason": "Pre-condition room before wake time",
                }
            )

        # Lighting anticipation
        if prediction.activity_state in (ActivityState.WAKING, ActivityState.EVENING):
            actions.append(
                {
                    "type": "lighting",
                    "action": "prepare_scene",
                    "target_room": target_room,
                    "scene": "morning"
                    if prediction.activity_state == ActivityState.WAKING
                    else "evening",
                    "reason": f"Prepare {target_room} lighting",
                }
            )

        # Coffee maker anticipation
        if prediction.activity_state == ActivityState.MORNING_ROUTINE and target_room in (
            "kitchen",
            "dining",
        ):
            actions.append(
                {
                    "type": "appliance",
                    "action": "start_coffee",
                    "lead_time_minutes": 5,
                    "reason": "Prepare coffee for morning routine",
                }
            )

        return actions

    def _is_cold_season(self) -> bool:
        """Check if it's cold season (October - April)."""
        month = datetime.now().month
        return month >= 10 or month <= 4


# =============================================================================
# Singleton Factory
# =============================================================================

_manager: PredictivePresenceManager | None = None
_manager_lock = asyncio.Lock()


async def get_predictive_presence() -> PredictivePresenceManager:
    """Get or create the PredictivePresenceManager.

    Returns:
        PredictivePresenceManager singleton.
    """
    global _manager

    async with _manager_lock:
        if _manager is None:
            _manager = PredictivePresenceManager()
            await _manager.initialize()

    return _manager


async def shutdown_predictive_presence() -> None:
    """Shutdown the PredictivePresenceManager."""
    global _manager

    if _manager:
        await _manager.shutdown()
        _manager = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ActivityState",
    "ActivityStatePredictor",
    "PredictivePresenceManager",
    "PresencePrediction",
    "PresenceTransition",
    "RoomPrediction",
    "TransitionMatrix",
    "get_predictive_presence",
    "shutdown_predictive_presence",
]


# =============================================================================
# 鏡
# Presence flows. Patterns emerge. Anticipation guides.
# h(x) ≥ 0. Always.
# =============================================================================
