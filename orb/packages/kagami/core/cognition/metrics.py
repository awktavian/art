"""Simplified Cognitive Metrics

Consolidates C1-C10 cognitive facets to practical subset actually used in production.

**Active Metrics (4):**
- **C4: Metacognitive Calibration** - Prediction accuracy, confidence calibration
- **C7: Temporal Coherence** - Plan consistency over time
- **C9: Personality Consistency** - Behavioral stability
- **C10: Evolution** - Learning rate, fitness growth

**Removed (6):** C1 (digital embodiment), C2 (self-recognition), C3 (autonomy),
C5 (theory of mind), C6 (emotional valence), C8 (integration/synergy)

These were interesting theoretically but not actionable in practice.

Usage:
    from kagami.core.cognition.metrics import get_cognitive_state

    state = get_cognitive_state(agent)
    print(f"Metacognition: {state.metacognition:.2f}")
    print(f"Consistency: {state.consistency:.2f}")

Note: Consolidated from kagami.core.cognitive.simplified_metrics
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CognitiveState:
    """Simplified cognitive state with 4 practical metrics."""

    # C4: Metacognitive Calibration (0-1)
    metacognition: float = 0.0
    metacognition_ece: float = 0.5  # Expected Calibration Error
    metacognition_samples: int = 0

    # C7: Temporal Coherence (0-1)
    temporal_coherence: float = 0.0
    plan_stability: float = 0.0

    # C9: Personality Consistency (0-1)
    consistency: float = 0.0
    behavioral_variance: float = 0.0

    # C10: Evolution (growth rate)
    evolution_rate: float = 0.0
    fitness_trend: float = 0.0
    learning_speed: float = 0.0

    # Metadata
    timestamp: float = 0.0
    agent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict[str, Any] for storage/transport."""
        return {
            "metacognition": self.metacognition,
            "metacognition_ece": self.metacognition_ece,
            "temporal_coherence": self.temporal_coherence,
            "consistency": self.consistency,
            "evolution_rate": self.evolution_rate,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
        }

    def get_overall_score(self) -> float:
        """Compute overall cognitive score (0-1).

        Weighted combination of active metrics.
        """
        return (
            0.4 * self.metacognition
            + 0.2 * self.temporal_coherence
            + 0.2 * self.consistency
            + 0.2 * max(0, self.evolution_rate)  # Clamp to positive
        )


def compute_metacognition(
    predictions: list[float],
    outcomes: list[float],
) -> tuple[float, float]:
    """Compute metacognitive calibration.

    Measures how well confidence matches actual accuracy.

    Args:
        predictions: Predicted confidences (0-1)
        outcomes: Actual outcomes (0=fail, 1=success)

    Returns:
        (calibration_score, ECE)
        - calibration_score: 1.0 = perfect, 0.0 = worst
        - ECE: Expected Calibration Error (0-1)
    """
    if len(predictions) < 10:
        return 0.5, 0.5  # Not enough data

    # Bin predictions into 10 bins
    predictions = np.array(predictions)  # type: ignore[assignment]
    outcomes = np.array(outcomes)  # type: ignore[assignment]

    bins = np.linspace(0, 1, 11)
    ece = 0.0

    for i in range(10):
        mask = (predictions >= bins[i]) & (predictions < bins[i + 1])

        if mask.sum() > 0:
            bin_conf = predictions[mask].mean()
            bin_acc = outcomes[mask].mean()
            bin_weight = mask.sum() / len(predictions)

            ece += bin_weight * abs(bin_acc - bin_conf)

    # Calibration score = 1 - ECE
    calibration_score = max(0, 1.0 - ece)

    return float(calibration_score), float(ece)


def compute_temporal_coherence(
    plans: list[dict[str, Any]],
    window_size: int = 10,
) -> float:
    """Compute temporal coherence of plans.

    Measures how consistent plans are over time.

    Args:
        plans: Recent plans with 'action' and 'timestamp'
        window_size: Window for comparison

    Returns:
        Coherence score (0-1), 1.0 = perfectly consistent
    """
    if len(plans) < 2:
        return 0.0  # Insufficient data for coherence

    # Recent plans
    recent = plans[-window_size:]

    # Count action transitions
    actions = [p.get("action", "") for p in recent]

    # Coherence = 1 - (unique actions / total actions)
    # Higher when agent sticks to same actions
    unique_ratio = len(set(actions)) / len(actions)
    coherence = 1.0 - unique_ratio

    return float(coherence)


def compute_consistency(
    behaviors: list[dict[str, Any]],
    window_size: int = 20,
) -> float:
    """Compute behavioral consistency.

    Measures variance in decision patterns.

    Args:
        behaviors: Recent behaviors with metrics
        window_size: Window for analysis

    Returns:
        Consistency score (0-1), 1.0 = perfectly consistent
    """
    if len(behaviors) < 5:
        return 0.0  # Insufficient data for consistency

    recent = behaviors[-window_size:]

    # Extract confidence values
    confidences = [b.get("confidence", 0.5) for b in recent]

    # Consistency = 1 - normalized_variance
    variance = np.var(confidences)
    consistency = max(0, 1.0 - variance * 4)  # Normalize assuming variance ~0.25

    return float(consistency)


def compute_evolution_rate(
    fitness_history: list[float],
    window_size: int = 50,
) -> float:
    """Compute evolution rate (fitness growth).

    Args:
        fitness_history: Fitness values over time
        window_size: Window for trend analysis

    Returns:
        Evolution rate (positive = improving, negative = declining)
    """
    if len(fitness_history) < 10:
        return 0.0

    recent = fitness_history[-window_size:]

    # Linear regression to get trend
    x = np.arange(len(recent))
    y = np.array(recent)

    # Slope = evolution rate
    if len(x) > 1:
        slope = np.polyfit(x, y, 1)[0]
        return float(slope)
    else:
        return 0.0


def get_cognitive_state(agent: Any) -> CognitiveState:
    """Compute cognitive state for agent.

    Args:
        agent: FractalAgent instance

    Returns:
        CognitiveState with 4 practical metrics
    """
    state = CognitiveState(
        timestamp=time.time(),
        agent_id=getattr(agent, "agent_id", "unknown"),
    )

    # C4: Metacognition (from prediction error tracking)
    try:
        # Get prediction history if available
        predictions = getattr(agent, "_prediction_confidences", [])
        outcomes = getattr(agent, "_prediction_outcomes", [])

        if predictions and outcomes:
            metacog, ece = compute_metacognition(predictions, outcomes)
            state.metacognition = metacog
            state.metacognition_ece = ece
            state.metacognition_samples = len(predictions)
    except Exception as e:
        logger.debug(f"Metacognition computation failed: {e}")

    # C7: Temporal Coherence (from plan history)
    try:
        plans = getattr(agent, "_plan_history", [])
        if plans:
            state.temporal_coherence = compute_temporal_coherence(plans)
    except Exception as e:
        logger.debug(f"Temporal coherence computation failed: {e}")

    # C9: Consistency (from behavior history)
    try:
        behaviors = getattr(agent, "_behavior_history", [])
        if behaviors:
            state.consistency = compute_consistency(behaviors)
    except Exception as e:
        logger.debug(f"Consistency computation failed: {e}")

    # C10: Evolution (from fitness history)
    try:
        fitness_history = getattr(agent, "_fitness_history", [])
        if fitness_history:
            state.evolution_rate = compute_evolution_rate(fitness_history)
            state.fitness_trend = fitness_history[-1] if fitness_history else 0.0
    except Exception as e:
        logger.debug(f"Evolution computation failed: {e}")

    return state


__all__ = [
    "CognitiveState",
    "compute_consistency",
    "compute_evolution_rate",
    "compute_metacognition",
    "compute_temporal_coherence",
    "get_cognitive_state",
]
