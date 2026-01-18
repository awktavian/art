"""Adaptive Learning Rate for Drive Weight Updates.

Dynamically adjusts how frequently the organism learns from its actions based on:
1. Recent success/failure patterns
2. Drive weight volatility (how rapidly weights are changing)
3. Time elapsed since last update
4. Organism health state

This prevents both under-learning (missing important signals) and over-learning
(thrashing on noise).

ADAPTATION STRATEGY:
====================
- Fast learning when: low success rate, high volatility, unhealthy organism
- Slow learning when: high success rate, stable weights, healthy organism
- Time-based forcing: If N hours pass, learn regardless (prevent staleness)

METRICS TRACKED:
================
- Success rate (rolling window)
- Weight change magnitude (volatility)
- Time since last update
- Organism health score
- Learning effectiveness (did learning help?)

Created: December 21, 2025
Author: Forge (Optimization)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Base learning frequency (goals between updates)
DEFAULT_BASE_LEARNING_INTERVAL = 10  # Goals between major weight updates
MIN_LEARNING_INTERVAL = 3  # Fastest: every 3 goals
MAX_LEARNING_INTERVAL = 20  # Slowest: every 20 goals

# Time-based forcing
MAX_TIME_WITHOUT_LEARNING = 3600.0  # Force learning after 1 hour

# Success rate thresholds
LOW_SUCCESS_THRESHOLD = 0.4  # Below = rapid learning
HIGH_SUCCESS_THRESHOLD = 0.7  # Above = slow learning

# Volatility thresholds (max weight change per update)
LOW_VOLATILITY_THRESHOLD = 0.05  # Below = stable
HIGH_VOLATILITY_THRESHOLD = 0.20  # Above = unstable

# Health thresholds
LOW_HEALTH_THRESHOLD = 0.5  # Below = rapid learning
HIGH_HEALTH_THRESHOLD = 0.8  # Above = slow learning

# Window sizes for rolling metrics
SUCCESS_WINDOW_SIZE = 10  # Recent 10 goals
VOLATILITY_WINDOW_SIZE = 5  # Recent 5 learning events


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class LearningRateMetrics:
    """Metrics used to compute adaptive learning rate."""

    success_rate: float = 0.7  # Recent success rate
    weight_volatility: float = 0.0  # Recent weight change magnitude
    time_since_last_learning: float = 0.0  # Seconds since last update
    organism_health: float = 1.0  # Current organism health
    recommended_interval: int = DEFAULT_BASE_LEARNING_INTERVAL  # Goals until next update


@dataclass
class LearningEvent:
    """Record of a learning update event."""

    timestamp: float
    goals_executed: int
    success_rate_before: float
    success_rate_after: float
    max_weight_change: float
    effectiveness: float  # Did learning improve success rate?


# =============================================================================
# LEARNING RATE ADAPTER
# =============================================================================


class LearningRateAdapter:
    """Adapts learning frequency based on system state and performance.

    USAGE:
    ------
    adapter = LearningRateAdapter()

    # After each goal execution
    adapter.record_goal_result(success=True)

    # Check if should learn now
    if adapter.should_learn_now(organism_health=0.7):
        # Perform drive weight update
        await motivation_system.update_drive_weights_from_receipts()
        adapter.record_learning_event(max_weight_change=0.15)
    """

    def __init__(self) -> None:
        # Goal execution history
        self._recent_results: deque[bool] = deque(maxlen=SUCCESS_WINDOW_SIZE)
        self._goals_since_last_learning = 0

        # Learning event history
        self._learning_history: deque[LearningEvent] = deque(maxlen=VOLATILITY_WINDOW_SIZE)
        self._last_learning_time = time.time()

        # Current adaptive interval
        self._current_interval = DEFAULT_BASE_LEARNING_INTERVAL

        # Tracking for effectiveness
        self._success_rate_at_last_learning = 0.7

    def record_goal_result(self, success: bool) -> None:
        """Record the outcome of a goal execution.

        Args:
            success: Whether the goal succeeded
        """
        self._recent_results.append(success)
        self._goals_since_last_learning += 1

    def should_learn_now(
        self,
        organism_health: float = 1.0,
        force_time_check: bool = True,
    ) -> bool:
        """Check if learning should happen now based on adaptive criteria.

        Args:
            organism_health: Current organism health score (0-1)
            force_time_check: If True, force learning after max time elapsed

        Returns:
            True if learning should happen now
        """
        # Force learning if too much time passed
        if force_time_check:
            time_elapsed = time.time() - self._last_learning_time
            if time_elapsed > MAX_TIME_WITHOUT_LEARNING:
                logger.info(
                    f"⏰ It's been a while since I learned ({time_elapsed / 60:.1f} min). "
                    "Time to reflect on what I've done."
                )
                return True

        # Compute current metrics
        metrics = self.compute_metrics(organism_health)

        # Update recommended interval
        self._current_interval = metrics.recommended_interval

        # Learn if we've executed enough goals
        should_learn = self._goals_since_last_learning >= self._current_interval

        if should_learn:
            reason = self._explain_learning_decision(metrics)
            logger.info(f"📊 {reason}")

        return should_learn

    def compute_metrics(self, organism_health: float = 1.0) -> LearningRateMetrics:
        """Compute current learning rate metrics.

        Args:
            organism_health: Current organism health score (0-1)

        Returns:
            LearningRateMetrics with all computed values
        """
        # Success rate (recent window)
        if len(self._recent_results) > 0:
            success_rate = sum(self._recent_results) / len(self._recent_results)
        else:
            success_rate = 0.7  # Default moderate

        # Weight volatility (average of recent changes)
        if len(self._learning_history) > 0:
            weight_volatility = sum(
                event.max_weight_change for event in self._learning_history
            ) / len(self._learning_history)
        else:
            weight_volatility = 0.0

        # Time since last learning
        time_since_last = time.time() - self._last_learning_time

        # Compute recommended interval
        recommended_interval = self._compute_adaptive_interval(
            success_rate, weight_volatility, organism_health
        )

        return LearningRateMetrics(
            success_rate=success_rate,
            weight_volatility=weight_volatility,
            time_since_last_learning=time_since_last,
            organism_health=organism_health,
            recommended_interval=recommended_interval,
        )

    def _compute_adaptive_interval(
        self,
        success_rate: float,
        weight_volatility: float,
        organism_health: float,
    ) -> int:
        """Compute adaptive learning interval based on multiple factors.

        Uses multiplicative adjustments so all factors contribute independently.

        Args:
            success_rate: Recent goal success rate (0-1)
            weight_volatility: Recent weight change magnitude
            organism_health: Current organism health (0-1)

        Returns:
            Recommended number of goals between learning updates
        """
        # Start with base interval
        interval = float(DEFAULT_BASE_LEARNING_INTERVAL)

        # Factor 1: Success rate (multiplicative adjustment)
        # Low success → multiply by 0.6 (faster learning)
        # High success → multiply by 1.5 (slower learning)
        if success_rate < LOW_SUCCESS_THRESHOLD:
            interval *= 0.6
        elif success_rate > HIGH_SUCCESS_THRESHOLD:
            interval *= 1.5

        # Factor 2: Weight volatility (multiplicative adjustment)
        # High volatility → multiply by 0.7 (faster learning)
        # Low volatility → multiply by 1.3 (slower learning)
        if weight_volatility > HIGH_VOLATILITY_THRESHOLD:
            interval *= 0.7
        elif weight_volatility < LOW_VOLATILITY_THRESHOLD:
            interval *= 1.3

        # Factor 3: Organism health (multiplicative adjustment)
        # Unhealthy → multiply by 0.7 (faster learning)
        # Healthy → multiply by 1.2 (slower learning)
        if organism_health < LOW_HEALTH_THRESHOLD:
            interval *= 0.7
        elif organism_health > HIGH_HEALTH_THRESHOLD:
            interval *= 1.2

        # Round to nearest integer and clamp to valid range
        interval = round(interval)
        return max(MIN_LEARNING_INTERVAL, min(MAX_LEARNING_INTERVAL, interval))

    def _explain_learning_decision(self, metrics: LearningRateMetrics) -> str:
        """Generate human-readable explanation for learning decision.

        Args:
            metrics: Current learning rate metrics

        Returns:
            Human-readable explanation string
        """
        reasons = []

        if metrics.success_rate < LOW_SUCCESS_THRESHOLD:
            reasons.append(f"success rate is low ({metrics.success_rate:.1%})")

        if metrics.weight_volatility > HIGH_VOLATILITY_THRESHOLD:
            reasons.append(f"drives are shifting rapidly (Δ={metrics.weight_volatility:.2f})")

        if metrics.organism_health < LOW_HEALTH_THRESHOLD:
            reasons.append(f"not feeling great (health={metrics.organism_health:.1%})")

        if metrics.time_since_last_learning > 1800:  # 30 min
            reasons.append(
                f"it's been {metrics.time_since_last_learning / 60:.0f}min since I learned"
            )

        if reasons:
            return f"Time to learn—{', '.join(reasons)}"
        else:
            return f"Regular learning check after {self._goals_since_last_learning} goals"

    def record_learning_event(
        self,
        max_weight_change: float,
        success_rate_after: float | None = None,
    ) -> None:
        """Record a learning event for effectiveness tracking.

        Args:
            max_weight_change: Maximum weight change across all drives
            success_rate_after: Success rate after learning (if available)
        """
        # Compute current success rate
        current_success_rate = (
            sum(self._recent_results) / len(self._recent_results)
            if len(self._recent_results) > 0
            else 0.7
        )

        # Use provided or current success rate
        if success_rate_after is None:
            success_rate_after = current_success_rate

        # Compute effectiveness (did learning help?)
        effectiveness = success_rate_after - self._success_rate_at_last_learning

        # Record event
        event = LearningEvent(
            timestamp=time.time(),
            goals_executed=self._goals_since_last_learning,
            success_rate_before=self._success_rate_at_last_learning,
            success_rate_after=success_rate_after,
            max_weight_change=max_weight_change,
            effectiveness=effectiveness,
        )
        self._learning_history.append(event)

        # Update state
        self._last_learning_time = time.time()
        self._goals_since_last_learning = 0
        self._success_rate_at_last_learning = success_rate_after

        # Log effectiveness
        if effectiveness > 0.1:
            logger.info(
                f"📈 Learning helped! Success rate: {event.success_rate_before:.1%} → "
                f"{success_rate_after:.1%} (+{effectiveness:.1%})"
            )
        elif effectiveness < -0.1:
            logger.warning(
                f"📉 Learning made things worse. Success rate: {event.success_rate_before:.1%} → "
                f"{success_rate_after:.1%} ({effectiveness:.1%})"
            )

    @property
    def recent_success_rate(self) -> float:
        """Get recent success rate for logging."""
        if len(self._recent_results) > 0:
            return sum(self._recent_results) / len(self._recent_results)
        return 0.7

    def get_learning_effectiveness(self) -> dict[str, float] | None:
        """Get the effectiveness of the most recent learning event.

        Returns:
            Dict with old_success, new_success, delta_success or None if no history
        """
        if len(self._learning_history) == 0:
            return None

        last_event = self._learning_history[-1]
        return {
            "old_success": last_event.success_rate_before,
            "new_success": last_event.success_rate_after,
            "delta_success": last_event.effectiveness,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get current adapter statistics.

        Returns:
            Dict with current metrics and history
        """
        metrics = self.compute_metrics()

        return {
            "current_interval": self._current_interval,
            "goals_since_last_learning": self._goals_since_last_learning,
            "success_rate": metrics.success_rate,
            "weight_volatility": metrics.weight_volatility,
            "time_since_last_learning_s": metrics.time_since_last_learning,
            "learning_events_tracked": len(self._learning_history),
            "recent_effectiveness": (
                sum(e.effectiveness for e in self._learning_history) / len(self._learning_history)
                if self._learning_history
                else 0.0
            ),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_global_adapter: LearningRateAdapter | None = None


def get_learning_rate_adapter() -> LearningRateAdapter:
    """Get or create global learning rate adapter instance.

    Returns:
        Global LearningRateAdapter instance
    """
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = LearningRateAdapter()
    return _global_adapter


def reset_learning_rate_adapter() -> None:
    """Reset global adapter (for testing)."""
    global _global_adapter
    _global_adapter = None
