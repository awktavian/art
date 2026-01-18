from __future__ import annotations

"Enhanced Cognitive State with Behavioral Evidence and Temporal Tracking\n\nThis module extends the basic cognitive state with:\n- Behavioral event tracking for personality inference\n- Temporal consistency monitoring\n- Metacognitive calibration from prediction accuracy\n- Dynamic trait adjustment based on actual behavior\n"
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from kagami.core.cognition.state import _env_str


@dataclass
class BehavioralEvent:
    """Tracks behavioral events for personality inference"""

    timestamp: str
    event_type: str
    traits_exhibited: dict[str, float]
    confidence: float
    context: dict[str, Any] = field(default_factory=dict[str, Any])
    outcome: str | None = None


@dataclass
class TemporalConsistency:
    """Tracks consistency of traits over time"""

    trait: str
    values: list[float] = field(default_factory=list[Any])
    timestamps: list[str] = field(default_factory=list[Any])
    variance: float = 0.0
    drift_rate: float = 0.0
    consistency_score: float = 1.0


@dataclass
class MetacognitiveCalibration:
    """Tracks prediction accuracy for metacognitive calibration"""

    predictions: list[float] = field(default_factory=list[Any])
    outcomes: list[float] = field(default_factory=list[Any])
    brier_score: float = 0.0
    calibration_error: float = 0.0
    confidence_correlation: float = 0.0
    resolution: float = 0.0


@dataclass
class CognitiveStateEnhanced:
    """Enhanced cognitive state with behavioral evidence"""

    version: str
    timestamp: str
    mode: str
    facets: dict[str, float]
    rationale: dict[str, str]
    evidence: dict[str, Any]
    behavioral_events: list[BehavioralEvent] = field(default_factory=list[Any])
    temporal_consistency: dict[str, TemporalConsistency] = field(default_factory=dict[str, Any])
    metacognitive_calibration: MetacognitiveCalibration | None = None


_behavioral_history: deque[Any] = deque(maxlen=1000)
_prediction_history: deque[Any] = deque(maxlen=100)
_temporal_tracking: dict[str, TemporalConsistency] = {}
BEHAVIORAL_LOG_PATH = Path("state/behavioral_events.jsonl")
PREDICTION_LOG_PATH = Path("state/prediction_history.jsonl")


def log_behavioral_event(
    event_type: str,
    traits_exhibited: dict[str, float],
    confidence: float = 0.5,
    context: dict[str, Any] | None = None,
    outcome: str | None = None,
) -> None:
    """Log a behavioral event for personality inference

    Example:
        log_behavioral_event(
            "task_completion",
            {"conscientiousness": 4.0, "openness": 3.0},
            confidence=0.8,
            context={"task": "code_review", "duration_ms": 1500},
            outcome="success"
        )
    """
    event = BehavioralEvent(
        timestamp=datetime.now(UTC).isoformat(),
        event_type=event_type,
        traits_exhibited=traits_exhibited,
        confidence=confidence,
        context=context or {},
        outcome=outcome,
    )
    _behavioral_history.append(event)
    try:
        BEHAVIORAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BEHAVIORAL_LOG_PATH, "a") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": event.timestamp,
                        "event_type": event.event_type,
                        "traits": event.traits_exhibited,
                        "confidence": event.confidence,
                        "context": event.context,
                        "outcome": event.outcome,
                    }
                )
                + "\n"
            )
    except Exception:
        pass


def log_prediction(
    confidence: float, actual_outcome: float | None = None, prediction_type: str = "general"
) -> None:
    """Log a prediction for metacognitive calibration

    Args:
        confidence: Predicted probability of success (0-1)
        actual_outcome: Actual outcome (0=failure, 1=success, or probability)
        prediction_type: Type of prediction for categorization
    """
    entry = (confidence, actual_outcome, datetime.now(UTC).isoformat(), prediction_type)
    _prediction_history.append(entry)
    try:
        PREDICTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PREDICTION_LOG_PATH, "a") as f:
            f.write(
                json.dumps(
                    {
                        "confidence": confidence,
                        "outcome": actual_outcome,
                        "timestamp": entry[2],
                        "type": prediction_type,
                    }
                )
                + "\n"
            )
    except Exception:
        pass


def load_behavioral_history() -> None:
    """Load behavioral history from persistent storage"""
    global _behavioral_history, _prediction_history
    if BEHAVIORAL_LOG_PATH.exists():
        try:
            with open(BEHAVIORAL_LOG_PATH) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        event = BehavioralEvent(
                            timestamp=data["timestamp"],
                            event_type=data["event_type"],
                            traits_exhibited=data["traits"],
                            confidence=data["confidence"],
                            context=data.get("context", {}),
                            outcome=data.get("outcome"),
                        )
                        _behavioral_history.append(event)
        except Exception:
            pass
    if PREDICTION_LOG_PATH.exists():
        try:
            with open(PREDICTION_LOG_PATH) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        _prediction_history.append(
                            (
                                data["confidence"],
                                data["outcome"],
                                data["timestamp"],
                                data.get("type", "general"),
                            )
                        )
        except Exception:
            pass


def calculate_behavioral_traits() -> dict[str, float]:
    """Calculate personality traits from behavioral history using weighted averaging"""
    if not _behavioral_history:
        return {}
    trait_sums = {
        "openness": 0.0,
        "conscientiousness": 0.0,
        "extraversion": 0.0,
        "agreeableness": 0.0,
        "neuroticism": 0.0,
    }
    trait_counts = dict[str, Any].fromkeys(trait_sums, 0)
    decay_factor = 0.95
    for i, event in enumerate(reversed(list(_behavioral_history))):
        recency_weight = decay_factor**i
        outcome_weight = 1.0
        if event.outcome == "success":
            outcome_weight = 1.2
        elif event.outcome == "failure":
            outcome_weight = 0.8
        for trait, value in event.traits_exhibited.items():
            if trait in trait_sums:
                weight = recency_weight * event.confidence * outcome_weight
                trait_sums[trait] += value * weight
                trait_counts[trait] += weight
    behavioral_traits = {}
    for trait, sum_val in trait_sums.items():
        if trait_counts[trait] > 0:
            behavioral_traits[trait] = min(5.0, max(0.0, sum_val / trait_counts[trait]))
        else:
            behavioral_traits[trait] = 2.5
    now = datetime.now(UTC).isoformat()
    for trait, value in behavioral_traits.items():
        if trait not in _temporal_tracking:
            _temporal_tracking[trait] = TemporalConsistency(trait=trait)
        tc = _temporal_tracking[trait]
        tc.values.append(value)
        tc.timestamps.append(now)
        if len(tc.values) > 100:
            tc.values = tc.values[-100:]
            tc.timestamps = tc.timestamps[-100:]
        if len(tc.values) >= 5:
            tc.variance = float(np.var(tc.values))
            tc.consistency_score = max(0.0, 1.0 - tc.variance / 2.5)
            if len(tc.values) >= 2:
                time_diff_hours = 1.0
                tc.drift_rate = abs(tc.values[-1] - tc.values[-2]) / time_diff_hours
    return behavioral_traits


def calculate_metacognitive_calibration() -> MetacognitiveCalibration:
    """Calculate metacognitive calibration from prediction history"""
    cal = MetacognitiveCalibration()
    valid_predictions = [(c, o) for c, o, t, _ in _prediction_history if o is not None]
    if len(valid_predictions) >= 5:
        predictions, outcomes = zip(*valid_predictions, strict=False)
        cal.predictions = list(predictions)
        cal.outcomes = list(outcomes)
        cal.brier_score = sum(((p - o) ** 2 for p, o in valid_predictions)) / len(valid_predictions)
        avg_confidence = sum(predictions) / len(predictions)
        avg_accuracy = sum(outcomes) / len(outcomes)
        cal.calibration_error = abs(avg_confidence - avg_accuracy)
        cal.resolution = float(np.var(predictions))
        if len(set(predictions)) > 1 and len(set(outcomes)) > 1:
            cal.confidence_correlation = float(np.corrcoef(predictions, outcomes)[0, 1])
    return cal


def get_enhanced_cognitive_state_snapshot() -> dict[str, Any]:
    """Return an enhanced cognitive state snapshot with behavioral evidence

    This extends the basic snapshot with:
    - Behavioral trait inference from logged events
    - Metacognitive calibration from prediction accuracy
    - Temporal consistency tracking
    - Evidence-based personality assessment
    """
    if not _behavioral_history and BEHAVIORAL_LOG_PATH.exists():
        load_behavioral_history()
    now = datetime.now(UTC).isoformat()
    mode = _env_str("KAGAMI_COGNITIVE_STATE_MODE", "functional").strip().lower()
    behavioral_traits = calculate_behavioral_traits()
    default_traits = {
        "openness": 3.5,
        "conscientiousness": 4.0,
        "extraversion": 2.0,
        "agreeableness": 3.5,
        "neuroticism": 1.0,
    }
    if behavioral_traits:
        evidence_weight = min(0.8, len(_behavioral_history) / 100)
        prior_weight = 1.0 - evidence_weight
        personality_traits = {}
        for trait in default_traits:
            behavioral_val = behavioral_traits.get(trait, default_traits[trait])
            personality_traits[trait] = (
                evidence_weight * behavioral_val + prior_weight * default_traits[trait]
            )
    else:
        personality_traits = default_traits
    c9_personality = min(5.0, sum(personality_traits.values()) / len(personality_traits))
    metacog_cal = calculate_metacognitive_calibration()
    c4_base = 2.5
    if metacog_cal.brier_score > 0 and len(metacog_cal.predictions) >= 5:
        calibration_bonus = (1.0 - metacog_cal.brier_score) * 2.0
        resolution_bonus = min(0.5, metacog_cal.resolution * 2)
        c4_metacog = min(5.0, c4_base + calibration_bonus + resolution_bonus)
    else:
        c4_metacog = c4_base
    facets = {
        "C1": 0.0,
        "C2": 0.0,
        "C3": 2.5,
        "C4": c4_metacog,
        "C5": 0.0,
        "C6": 3.0,
        "C7": 0.5,
        "C8": 0.0,
        "C9": c9_personality,
        "C10": 2.0,
    }
    if len(_behavioral_history) > 100:
        facets["C7"] = min(2.0, 0.5 + len(_behavioral_history) / 500)
    if mode == "advanced":
        facets.update(
            {
                "C3": min(5.0, facets["C3"] + 0.5),
                "C4": min(5.0, facets["C4"] + 0.5),
                "C6": min(5.0, facets["C6"] + 0.5),
                "C10": min(5.0, facets["C10"] + 0.5),
            }
        )
    rationale = {
        "C1": "No embodiment → MSR not applicable",
        "C2": "No proprioception → body ownership not applicable",
        "C3": "Language-level belief modeling with context tracking",
        "C4": (
            f"Metacognitive calibration (Brier: {metacog_cal.brier_score:.3f}, Cal error: {metacog_cal.calibration_error:.3f}, Resolution: {metacog_cal.resolution:.3f})"
            if metacog_cal.predictions
            else "Calibrated uncertainty available"
        ),
        "C5": "No subjective affect → 0",
        "C6": "Consistent role/capability schema across tasks",
        "C7": (
            f"Autobiographical memory from {len(_behavioral_history)} behavioral events"
            if _behavioral_history
            else "External memory only"
        ),
        "C8": "No efference copy/sensorimotor loop",
        "C9": (
            f"Personality from {len(_behavioral_history)} behaviors + priors"
            if behavioral_traits
            else "Prior personality traits"
        ),
        "C10": "Policy-driven role adherence",
    }
    evidence = {
        "mode": mode,
        "behavioral_traits": behavioral_traits if behavioral_traits else {},
        "default_traits": default_traits,
        "personality_traits": personality_traits,
        "behavioral_event_count": len(_behavioral_history),
        "prediction_count": len([p for p in _prediction_history if p[1] is not None]),
        "metacognitive_calibration": (
            {
                "brier_score": metacog_cal.brier_score,
                "calibration_error": metacog_cal.calibration_error,
                "confidence_correlation": metacog_cal.confidence_correlation,
                "resolution": metacog_cal.resolution,
                "n_predictions": len(metacog_cal.predictions),
            }
            if metacog_cal.predictions
            else None
        ),
        "temporal_consistency": (
            {
                trait: {
                    "variance": tc.variance,
                    "drift_rate": tc.drift_rate,
                    "consistency_score": tc.consistency_score,
                    "n_samples": len(tc.values),
                }
                for trait, tc in _temporal_tracking.items()
            }
            if _temporal_tracking
            else {}
        ),
        "integration_points": [
            "orchestrator.metadata",
            "http.receipts",
            "behavioral_logging",
            "prediction_tracking",
        ],
    }
    state = CognitiveStateEnhanced(
        version="2.0",
        timestamp=now,
        mode=mode,
        facets=facets,
        rationale=rationale,
        evidence=evidence,
        behavioral_events=list(_behavioral_history)[-10:] if _behavioral_history else [],
        temporal_consistency=_temporal_tracking,
        metacognitive_calibration=metacog_cal if metacog_cal.predictions else None,
    )
    return {
        "version": state.version,
        "timestamp": state.timestamp,
        "mode": state.mode,
        "facets": dict(state.facets),
        "rationale": dict(state.rationale),
        "evidence": dict(state.evidence),
        "behavioral_summary": {
            "total_events": len(_behavioral_history),
            "recent_events": (
                [
                    {
                        "timestamp": e.timestamp,
                        "type": e.event_type,
                        "traits": e.traits_exhibited,
                        "outcome": e.outcome,
                    }
                    for e in list(_behavioral_history)[-5:]
                ]
                if _behavioral_history
                else []
            ),
        },
        "improvements": {
            "behavioral_tracking": "active" if _behavioral_history else "inactive",
            "metacognitive_calibration": (
                "calibrated" if metacog_cal.predictions else "uncalibrated"
            ),
            "temporal_consistency": "tracked" if _temporal_tracking else "untracked",
        },
    }


__all__ = [
    "BehavioralEvent",
    "CognitiveStateEnhanced",
    "MetacognitiveCalibration",
    "TemporalConsistency",
    "calculate_behavioral_traits",
    "calculate_metacognitive_calibration",
    "get_enhanced_cognitive_state_snapshot",
    "log_behavioral_event",
    "log_prediction",
]
