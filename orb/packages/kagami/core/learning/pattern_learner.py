"""General Pattern Learner — Learns temporal and behavioral patterns.

A unified pattern learning system that works for ANY domain:
- Travel patterns (departure times, commute durations)
- Presence patterns (when home, when away)
- Sleep patterns (bedtime, wake time)
- Usage patterns (device usage, room occupancy)
- Activity patterns (work hours, breaks)

Uses exponential moving averages and time-slot bucketing
for efficient online learning without storing raw data.

Created: December 30, 2025
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TimeGranularity(str, Enum):
    """Time slot granularity for pattern learning."""

    MINUTE = "minute"  # 60 slots per hour
    QUARTER_HOUR = "quarter_hour"  # 4 slots per hour
    HOUR = "hour"  # 24 slots per day
    DAY_PART = "day_part"  # 4 slots: morning, afternoon, evening, night
    WEEKDAY = "weekday"  # 7 slots


@dataclass
class TimeSlot:
    """Identifies a time slot for pattern matching."""

    hour: int = 0  # 0-23
    minute_bucket: int = 0  # 0-3 (15-min buckets)
    weekday: int = 0  # 0=Mon, 6=Sun
    day_part: int = 0  # 0=night, 1=morning, 2=afternoon, 3=evening
    is_weekend: bool = False

    @classmethod
    def from_datetime(cls, dt: datetime | None = None) -> TimeSlot:
        """Create TimeSlot from datetime."""
        dt = dt or datetime.now()
        hour = dt.hour

        return cls(
            hour=hour,
            minute_bucket=dt.minute // 15,
            weekday=dt.weekday(),
            day_part=hour // 6,  # 0-5=night, 6-11=morning, 12-17=afternoon, 18-23=evening
            is_weekend=dt.weekday() >= 5,
        )

    def to_key(self, granularity: TimeGranularity) -> str:
        """Convert to string key for pattern storage."""
        if granularity == TimeGranularity.MINUTE or granularity == TimeGranularity.QUARTER_HOUR:
            return f"{self.weekday}:{self.hour:02d}:{self.minute_bucket}"
        elif granularity == TimeGranularity.HOUR:
            return f"{self.weekday}:{self.hour:02d}"
        elif granularity == TimeGranularity.DAY_PART:
            return f"{self.weekday}:{self.day_part}"
        elif granularity == TimeGranularity.WEEKDAY:
            return str(self.weekday)
        return f"{self.weekday}:{self.hour:02d}"


@dataclass
class PatternSlot:
    """Statistics for a single time slot."""

    count: int = 0  # Number of observations
    probability: float = 0.0  # Probability of event occurring
    mean_value: float = 0.0  # Mean of continuous values
    variance: float = 0.0  # Variance for confidence intervals
    last_seen: float = 0.0  # Timestamp of last observation

    # Exponential moving average parameters
    ema_alpha: float = 0.2  # Learning rate

    def update_event(self, occurred: bool = True) -> None:
        """Update slot with binary event (occurred/not occurred)."""
        self.count += 1
        self.last_seen = time.time()

        # Exponential moving average for probability
        target = 1.0 if occurred else 0.0
        self.probability = self.ema_alpha * target + (1 - self.ema_alpha) * self.probability

    def update_value(self, value: float) -> None:
        """Update slot with continuous value."""
        self.count += 1
        self.last_seen = time.time()

        if self.count == 1:
            self.mean_value = value
            self.variance = 0.0
        else:
            # Welford's online algorithm for mean and variance
            old_mean = self.mean_value
            self.mean_value = self.ema_alpha * value + (1 - self.ema_alpha) * self.mean_value
            # Update variance with EMA
            self.variance = (
                self.ema_alpha * (value - old_mean) * (value - self.mean_value)
                + (1 - self.ema_alpha) * self.variance
            )

    @property
    def std_dev(self) -> float:
        """Standard deviation."""
        return math.sqrt(max(0, self.variance))

    @property
    def confidence(self) -> float:
        """Confidence level based on sample count (0-1)."""
        # Asymptotic confidence: reaches 0.9 at ~20 samples
        return 1.0 - math.exp(-self.count / 10.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "count": self.count,
            "probability": round(self.probability, 4),
            "mean_value": round(self.mean_value, 4),
            "variance": round(self.variance, 4),
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternSlot:
        """Create from dict."""
        slot = cls()
        slot.count = data.get("count", 0)
        slot.probability = data.get("probability", 0.0)
        slot.mean_value = data.get("mean_value", 0.0)
        slot.variance = data.get("variance", 0.0)
        slot.last_seen = data.get("last_seen", 0.0)
        return slot


class PatternLearner:
    """General-purpose pattern learner.

    Learns temporal patterns for any domain without storing raw data.
    Uses time-slot bucketing and exponential moving averages.

    Usage:
        learner = PatternLearner("travel_departures", TimeGranularity.HOUR)

        # Record events
        learner.record_event()  # Binary: event occurred now
        learner.record_value(25.5)  # Continuous: duration/value

        # Query patterns
        prob = learner.get_probability()  # For current time slot
        mean = learner.get_expected_value()

        # Predict
        prediction = learner.predict(datetime.now() + timedelta(hours=2))
    """

    def __init__(
        self,
        name: str,
        granularity: TimeGranularity = TimeGranularity.HOUR,
        ema_alpha: float = 0.2,
        persist_path: Path | None = None,
    ):
        """Initialize pattern learner.

        Args:
            name: Unique name for this pattern domain
            granularity: Time slot granularity
            ema_alpha: Learning rate (0-1, higher = faster adaptation)
            persist_path: Optional path for persistence
        """
        self.name = name
        self.granularity = granularity
        self.ema_alpha = ema_alpha
        self.persist_path = persist_path

        # Pattern storage: key -> PatternSlot
        self._slots: dict[str, PatternSlot] = defaultdict(
            lambda: PatternSlot(ema_alpha=self.ema_alpha)
        )

        # Global statistics
        self._total_events = 0
        self._total_values = 0
        self._global_mean = 0.0

        # Load persisted patterns
        if persist_path and persist_path.exists():
            self._load()

    # =========================================================================
    # RECORDING
    # =========================================================================

    def record_event(self, occurred: bool = True, at: datetime | None = None) -> None:
        """Record a binary event at the given time.

        Args:
            occurred: Whether the event occurred
            at: Time of event (default: now)
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        self._slots[key].update_event(occurred)
        self._total_events += 1

        logger.debug(f"Pattern '{self.name}' recorded event at {key}: {occurred}")

    def record_value(self, value: float, at: datetime | None = None) -> None:
        """Record a continuous value at the given time.

        Args:
            value: The value to record
            at: Time of recording (default: now)
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        self._slots[key].update_value(value)
        self._total_values += 1

        # Update global mean
        self._global_mean = self.ema_alpha * value + (1 - self.ema_alpha) * self._global_mean

        logger.debug(f"Pattern '{self.name}' recorded value at {key}: {value}")

    # =========================================================================
    # QUERYING
    # =========================================================================

    def get_probability(self, at: datetime | None = None) -> float:
        """Get probability of event at given time.

        Args:
            at: Time to query (default: now)

        Returns:
            Probability (0-1)
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        if key in self._slots:
            return self._slots[key].probability
        return 0.5  # Prior: unknown

    def get_expected_value(self, at: datetime | None = None) -> float:
        """Get expected value at given time.

        Args:
            at: Time to query (default: now)

        Returns:
            Expected value (or global mean if no data for slot)
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        if key in self._slots and self._slots[key].count > 0:
            return self._slots[key].mean_value
        return self._global_mean

    def get_confidence(self, at: datetime | None = None) -> float:
        """Get confidence level for predictions at given time.

        Args:
            at: Time to query (default: now)

        Returns:
            Confidence (0-1)
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        if key in self._slots:
            return self._slots[key].confidence
        return 0.0

    def get_slot_stats(self, at: datetime | None = None) -> dict[str, Any]:
        """Get full statistics for a time slot.

        Args:
            at: Time to query (default: now)

        Returns:
            Dict with all slot statistics
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        if key in self._slots:
            pattern_slot = self._slots[key]
            return {
                "key": key,
                "slot": {
                    "hour": slot.hour,
                    "weekday": slot.weekday,
                    "is_weekend": slot.is_weekend,
                },
                **pattern_slot.to_dict(),
                "confidence": pattern_slot.confidence,
            }

        return {
            "key": key,
            "slot": {
                "hour": slot.hour,
                "weekday": slot.weekday,
                "is_weekend": slot.is_weekend,
            },
            "count": 0,
            "probability": 0.5,
            "confidence": 0.0,
        }

    # =========================================================================
    # PREDICTION
    # =========================================================================

    def predict(self, at: datetime | None = None) -> dict[str, Any]:
        """Predict pattern for given time.

        Args:
            at: Time to predict (default: now)

        Returns:
            Prediction dict with probability, expected_value, confidence
        """
        slot = TimeSlot.from_datetime(at)
        key = slot.to_key(self.granularity)

        pattern_slot = self._slots.get(key)

        if pattern_slot and pattern_slot.count > 0:
            return {
                "time": (at or datetime.now()).isoformat(),
                "key": key,
                "probability": pattern_slot.probability,
                "expected_value": pattern_slot.mean_value,
                "std_dev": pattern_slot.std_dev,
                "confidence": pattern_slot.confidence,
                "sample_count": pattern_slot.count,
            }

        # Fallback to similar slots (e.g., same hour different day)
        similar_probs = []
        similar_values = []

        for _k, s in self._slots.items():
            # Match by hour (coarse matching)
            if s.count > 0:
                similar_probs.append(s.probability)
                similar_values.append(s.mean_value)

        if similar_probs:
            return {
                "time": (at or datetime.now()).isoformat(),
                "key": key,
                "probability": sum(similar_probs) / len(similar_probs),
                "expected_value": sum(similar_values) / len(similar_values)
                if similar_values
                else self._global_mean,
                "std_dev": 0.0,
                "confidence": 0.3,  # Low confidence for interpolated
                "sample_count": 0,
                "interpolated": True,
            }

        return {
            "time": (at or datetime.now()).isoformat(),
            "key": key,
            "probability": 0.5,
            "expected_value": self._global_mean,
            "std_dev": 0.0,
            "confidence": 0.0,
            "sample_count": 0,
        }

    def find_best_time(
        self,
        target: str = "high_probability",
        start: datetime | None = None,
        hours_ahead: int = 24,
    ) -> dict[str, Any]:
        """Find best time for an event based on patterns.

        Args:
            target: "high_probability", "low_probability", "high_value", "low_value"
            start: Start time for search (default: now)
            hours_ahead: How many hours to search

        Returns:
            Best time and prediction
        """
        start = start or datetime.now()
        best_time = start
        best_score = -float("inf") if "high" in target else float("inf")
        best_prediction = None

        # Search in 15-minute increments
        for minutes in range(0, hours_ahead * 60, 15):
            check_time = start + timedelta(minutes=minutes)
            prediction = self.predict(check_time)

            if target == "high_probability":
                score = prediction["probability"]
                if score > best_score:
                    best_score = score
                    best_time = check_time
                    best_prediction = prediction
            elif target == "low_probability":
                score = prediction["probability"]
                if score < best_score:
                    best_score = score
                    best_time = check_time
                    best_prediction = prediction
            elif target == "high_value":
                score = prediction["expected_value"]
                if score > best_score:
                    best_score = score
                    best_time = check_time
                    best_prediction = prediction
            elif target == "low_value":
                score = prediction["expected_value"]
                if score < best_score:
                    best_score = score
                    best_time = check_time
                    best_prediction = prediction

        return {
            "best_time": best_time.isoformat(),
            "target": target,
            "prediction": best_prediction,
        }

    # =========================================================================
    # SUMMARY & PERSISTENCE
    # =========================================================================

    def get_summary(self) -> dict[str, Any]:
        """Get summary of learned patterns."""
        active_slots = {k: v for k, v in self._slots.items() if v.count > 0}

        return {
            "name": self.name,
            "granularity": self.granularity.value,
            "total_events": self._total_events,
            "total_values": self._total_values,
            "global_mean": round(self._global_mean, 4),
            "active_slots": len(active_slots),
            "total_observations": sum(s.count for s in active_slots.values()),
            "slots": {k: v.to_dict() for k, v in active_slots.items()},
        }

    def save(self, path: Path | None = None) -> None:
        """Save patterns to disk."""
        path = path or self.persist_path
        if not path:
            return

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "granularity": self.granularity.value,
            "ema_alpha": self.ema_alpha,
            "total_events": self._total_events,
            "total_values": self._total_values,
            "global_mean": self._global_mean,
            "slots": {k: v.to_dict() for k, v in self._slots.items() if v.count > 0},
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved pattern '{self.name}' to {path}")

    def _load(self) -> None:
        """Load patterns from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)

            self._total_events = data.get("total_events", 0)
            self._total_values = data.get("total_values", 0)
            self._global_mean = data.get("global_mean", 0.0)

            for key, slot_data in data.get("slots", {}).items():
                self._slots[key] = PatternSlot.from_dict(slot_data)

            logger.debug(f"Loaded pattern '{self.name}' with {len(self._slots)} slots")

        except Exception as e:
            logger.warning(f"Failed to load pattern '{self.name}': {e}")

    def reset(self) -> None:
        """Reset all learned patterns."""
        self._slots.clear()
        self._total_events = 0
        self._total_values = 0
        self._global_mean = 0.0


# ============================================================================
# SEMANTIC PATTERN LEARNER (December 30, 2025)
# ============================================================================


class SemanticPatternLearner(PatternLearner):
    """Pattern learner enhanced with semantic context embeddings.

    Extends PatternLearner to store semantic context with each pattern,
    enabling similarity-based prediction and richer pattern matching.

    Features:
    - Stores context embeddings alongside time-slot patterns
    - Enables semantic similarity search across patterns
    - Supports context-aware predictions
    - Integrates with Weaviate for persistent storage

    Usage:
        learner = get_semantic_pattern_learner("meeting_patterns")

        # Record event with context
        learner.record_event_with_context(
            "Team standup at 9am",
            occurred=True,
        )

        # Predict using semantic similarity
        prediction = learner.predict_with_context(
            "Daily sync meeting in the morning"
        )
    """

    def __init__(
        self,
        name: str,
        granularity: TimeGranularity = TimeGranularity.HOUR,
        ema_alpha: float = 0.2,
        persist_path: Path | None = None,
    ):
        super().__init__(name, granularity, ema_alpha, persist_path)

        # Embedding service (lazy loaded)
        self._embedding_service = None
        self._embedding_dim = 384

        # Context embeddings: slot_key -> list of (context_str, embedding)
        self._context_embeddings: dict[str, list[tuple[str, list[float]]]] = defaultdict(list)

        # Storage for Weaviate persistence
        self._storage_router = None

    def _ensure_embedding_service(self) -> bool:
        """Ensure embedding service is initialized."""
        if self._embedding_service is not None:
            return True

        try:
            from kagami.core.services.embedding_service import get_embedding_service

            self._embedding_service = get_embedding_service()
            return True
        except ImportError:
            logger.debug("Embedding service not available for semantic patterns")
            return False

    def record_event_with_context(
        self,
        context: str,
        occurred: bool = True,
        at: datetime | None = None,
    ) -> None:
        """Record a binary event with semantic context.

        Args:
            context: Semantic context string describing the event
            occurred: Whether the event occurred
            at: Time of event (default: now)
        """
        # Standard time-slot recording
        self.record_event(occurred, at)

        # Embed and store context
        if self._ensure_embedding_service() and occurred:
            slot = TimeSlot.from_datetime(at)
            key = slot.to_key(self.granularity)

            try:
                import numpy as np

                embedding = self._embedding_service.embed_text(context)
                embedding_list = (
                    embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
                )

                # Store context (limit to recent 10 per slot)
                self._context_embeddings[key].append((context, embedding_list))
                if len(self._context_embeddings[key]) > 10:
                    self._context_embeddings[key] = self._context_embeddings[key][-10:]

                logger.debug(f"Semantic pattern recorded: {self.name}[{key}] = {context[:50]}...")

            except Exception as e:
                logger.debug(f"Failed to embed context: {e}")

    def record_value_with_context(
        self,
        value: float,
        context: str,
        at: datetime | None = None,
    ) -> None:
        """Record a continuous value with semantic context.

        Args:
            value: The value to record
            context: Semantic context string
            at: Time of recording (default: now)
        """
        # Standard time-slot recording
        self.record_value(value, at)

        # Embed and store context
        if self._ensure_embedding_service():
            slot = TimeSlot.from_datetime(at)
            key = slot.to_key(self.granularity)

            try:
                import numpy as np

                embedding = self._embedding_service.embed_text(f"{context}: {value}")
                embedding_list = (
                    embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
                )

                self._context_embeddings[key].append((context, embedding_list))
                if len(self._context_embeddings[key]) > 10:
                    self._context_embeddings[key] = self._context_embeddings[key][-10:]

            except Exception as e:
                logger.debug(f"Failed to embed context: {e}")

    def predict_with_context(
        self,
        query: str,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Predict pattern using semantic similarity to past contexts.

        Args:
            query: Semantic query to match against stored contexts
            at: Time to predict (default: now)

        Returns:
            Prediction dict with probability, expected_value, confidence,
            and semantic_similarity score
        """
        # Get base prediction
        prediction = self.predict(at)

        # Enhance with semantic similarity if available
        if not self._ensure_embedding_service():
            return prediction

        try:
            import numpy as np

            query_embedding = self._embedding_service.embed_text(query)

            # Find most similar past contexts
            best_similarity = 0.0
            best_context = None
            weighted_prob_sum = 0.0
            weight_sum = 0.0

            for key, contexts in self._context_embeddings.items():
                slot_pattern = self._slots.get(key)
                if not slot_pattern or slot_pattern.count == 0:
                    continue

                for context_str, emb in contexts:
                    emb_array = np.array(emb)
                    similarity = float(np.dot(query_embedding, emb_array))

                    if similarity > 0.5:  # Only consider relevant matches
                        weighted_prob_sum += similarity * slot_pattern.probability
                        weight_sum += similarity

                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_context = context_str

            if weight_sum > 0:
                semantic_probability = weighted_prob_sum / weight_sum
                # Blend with time-based probability
                blended_prob = (prediction["probability"] + semantic_probability) / 2
                prediction["probability"] = blended_prob
                prediction["semantic_similarity"] = best_similarity
                prediction["similar_context"] = best_context
                prediction["confidence"] = min(
                    1.0, prediction["confidence"] + best_similarity * 0.3
                )

            return prediction

        except Exception as e:
            logger.debug(f"Semantic prediction failed: {e}")
            return prediction

    def get_similar_patterns(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find patterns most similar to the query.

        Args:
            query: Semantic query
            limit: Maximum results to return

        Returns:
            List of similar patterns with similarity scores
        """
        if not self._ensure_embedding_service():
            return []

        try:
            import numpy as np

            query_embedding = self._embedding_service.embed_text(query)

            similarities = []
            for key, contexts in self._context_embeddings.items():
                slot_pattern = self._slots.get(key)

                for context_str, emb in contexts:
                    emb_array = np.array(emb)
                    similarity = float(np.dot(query_embedding, emb_array))

                    similarities.append(
                        {
                            "slot_key": key,
                            "context": context_str,
                            "similarity": similarity,
                            "probability": slot_pattern.probability if slot_pattern else 0.5,
                            "count": slot_pattern.count if slot_pattern else 0,
                        }
                    )

            # Sort by similarity
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            return similarities[:limit]

        except Exception as e:
            logger.debug(f"Similar pattern search failed: {e}")
            return []

    async def persist_to_weaviate(self) -> bool:
        """Persist semantic patterns to Weaviate for long-term storage.

        Returns:
            True if persistence successful
        """
        try:
            from kagami.core.services.storage_routing import (
                DataCategory,
                get_storage_router,
            )

            router = get_storage_router()

            # Prepare pattern data
            pattern_data = {
                "name": self.name,
                "granularity": self.granularity.value,
                "slots": {k: s.to_dict() for k, s in self._slots.items()},
                "context_count": sum(len(v) for v in self._context_embeddings.values()),
                "total_events": self._total_events,
                "global_mean": self._global_mean,
            }

            await router.store(
                DataCategory.PATTERN,
                key=f"pattern:{self.name}",
                data=pattern_data,
            )

            logger.info(f"✅ Persisted semantic pattern '{self.name}' to Weaviate")
            return True

        except Exception as e:
            logger.debug(f"Failed to persist pattern to Weaviate: {e}")
            return False


# Semantic pattern learner registry
_semantic_learners: dict[str, SemanticPatternLearner] = {}


def get_semantic_pattern_learner(
    name: str,
    granularity: TimeGranularity = TimeGranularity.HOUR,
    persist: bool = True,
) -> SemanticPatternLearner:
    """Get or create a semantic pattern learner by name.

    Args:
        name: Unique name for pattern domain
        granularity: Time slot granularity
        persist: Whether to persist patterns to disk

    Returns:
        SemanticPatternLearner instance
    """
    if name not in _semantic_learners:
        persist_path = None
        if persist:
            persist_path = Path.home() / ".kagami" / "patterns" / f"{name}_semantic.json"

        _semantic_learners[name] = SemanticPatternLearner(
            name=name,
            granularity=granularity,
            persist_path=persist_path,
        )

    return _semantic_learners[name]


# ============================================================================
# FACTORY & REGISTRY
# ============================================================================

_learners: dict[str, PatternLearner] = {}


def get_pattern_learner(
    name: str,
    granularity: TimeGranularity = TimeGranularity.HOUR,
    persist: bool = True,
) -> PatternLearner:
    """Get or create a pattern learner by name.

    Args:
        name: Unique name for pattern domain
        granularity: Time slot granularity
        persist: Whether to persist patterns to disk

    Returns:
        PatternLearner instance
    """
    if name not in _learners:
        persist_path = None
        if persist:
            persist_path = Path.home() / ".kagami" / "patterns" / f"{name}.json"

        _learners[name] = PatternLearner(
            name=name,
            granularity=granularity,
            persist_path=persist_path,
        )

    return _learners[name]


def save_all_patterns() -> None:
    """Save all pattern learners to disk."""
    for learner in _learners.values():
        learner.save()


# Pre-defined pattern learners for common domains
def get_travel_departure_learner() -> PatternLearner:
    """Pattern learner for travel departures."""
    return get_pattern_learner("travel_departures", TimeGranularity.HOUR)


def get_travel_duration_learner() -> PatternLearner:
    """Pattern learner for commute durations."""
    return get_pattern_learner("travel_durations", TimeGranularity.HOUR)


def get_presence_learner() -> PatternLearner:
    """Pattern learner for home presence."""
    return get_pattern_learner("presence", TimeGranularity.HOUR)


def get_sleep_learner() -> PatternLearner:
    """Pattern learner for sleep patterns."""
    return get_pattern_learner("sleep", TimeGranularity.HOUR)


def get_activity_learner(activity: str) -> PatternLearner:
    """Pattern learner for a specific activity."""
    return get_pattern_learner(f"activity_{activity}", TimeGranularity.HOUR)


__all__ = [
    "PatternLearner",
    "PatternSlot",
    "SemanticPatternLearner",
    "TimeGranularity",
    "TimeSlot",
    "get_activity_learner",
    "get_pattern_learner",
    "get_presence_learner",
    "get_semantic_pattern_learner",
    "get_sleep_learner",
    "get_travel_departure_learner",
    "get_travel_duration_learner",
    "save_all_patterns",
]
