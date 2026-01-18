from __future__ import annotations

"""Adaptive Hyperparameters for RL Training.

Based on 2025 best practices:
- Learning rate schedules (cosine annealing with warm restarts)
- Adaptive imagination horizon (complexity-based)
- Dynamic batch sizes (based on buffer state)
- Exploration decay (over time)

Status: ✅ PRODUCTION READY (Oct 2025)
"""
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


class AdaptiveLearningRate:
    """Cosine annealing with warm restarts (SGDR).

    Based on "SGDR: Stochastic Gradient Descent with Warm Restarts"
    (Loshchilov & Hutter, 2017)

    Learning rate follows cosine curve, periodically restarting
    to escape local minima.
    """

    def __init__(self, initial_lr: float = 0.001, T_0: int = 100, T_mult: int = 2) -> None:
        """Initialize adaptive learning rate.

        Args:
            initial_lr: Starting learning rate
            T_0: Initial restart period
            T_mult: Period multiplier after each restart
        """
        self.lr_0 = initial_lr
        self.T_0 = T_0
        self.T_mult = T_mult
        self.T_cur = 0
        self.T_i = T_0
        self.iteration = 0
        self.restart_count = 0

    def get_lr(self, iteration: int | None = None) -> float:
        """Get learning rate for current iteration.

        Args:
            iteration: Iteration number (if None, uses internal counter)

        Returns:
            Current learning rate
        """
        if iteration is None:
            iteration = self.iteration
            self.iteration += 1

        # Update current position in cycle
        self.T_cur = iteration % self.T_i

        # Cosine decay
        lr = self.lr_0 * (1 + math.cos(math.pi * self.T_cur / self.T_i)) / 2

        # Check for restart
        if self.T_cur == 0 and iteration > 0:
            self.restart_count += 1
            self.T_i *= self.T_mult
            logger.debug(
                f"🔄 Learning rate restart #{self.restart_count}, "
                f"next period: {self.T_i} iterations"
            )

        return lr

    def get_stats(self) -> dict[str, Any]:
        """Get learning rate scheduler statistics."""
        return {
            "current_lr": (self.get_lr(self.iteration - 1) if self.iteration > 0 else self.lr_0),
            "iteration": self.iteration,
            "restart_count": self.restart_count,
            "next_restart_in": self.T_i - self.T_cur,
        }


class AdaptiveHorizon:
    """Adaptive imagination horizon based on task complexity.

    Simple tasks: Plan 1-3 steps ahead (fast)
    Complex tasks: Plan 10-15 steps ahead (thorough)

    Automatically adjusts based on confidence and complexity.
    """

    def __init__(self, min_horizon: int = 1, max_horizon: int = 15) -> None:
        """Initialize adaptive horizon.

        Args:
            min_horizon: Minimum planning depth
            max_horizon: Maximum planning depth
        """
        self.min_horizon = min_horizon
        self.max_horizon = max_horizon
        self._recent_horizons: list[int] = []

    def compute_horizon(
        self,
        context: dict[str, Any],
        confidence: float = 0.5,
        complexity: float | None = None,
    ) -> int:
        """Compute optimal imagination horizon.

        Args:
            context: Current context
            confidence: Model confidence (0.0-1.0)
            complexity: Estimated task complexity (0.0-1.0, None = auto-estimate)

        Returns:
            Optimal horizon (planning depth)
        """
        # Auto-estimate complexity if not provided
        if complexity is None:
            complexity = self._estimate_complexity(context)

        # Low confidence + high complexity = plan deeper
        # High confidence + low complexity = plan shallow (fast)
        uncertainty = 1.0 - confidence
        planning_need = uncertainty * complexity

        # Map to horizon range
        horizon = int(self.min_horizon + planning_need * (self.max_horizon - self.min_horizon))

        # Bound
        horizon = max(self.min_horizon, min(self.max_horizon, horizon))

        # Track
        self._recent_horizons.append(horizon)
        if len(self._recent_horizons) > 100:
            self._recent_horizons.pop(0)

        return horizon

    def _estimate_complexity(self, context: dict[str, Any]) -> float:
        """Estimate task complexity from context.

        Args:
            context: Task context

        Returns:
            Estimated complexity (0.0-1.0)
        """
        complexity = 0.5  # Default: medium

        # Indicators of high complexity
        action = context.get("action", "").lower()

        if any(
            keyword in action
            for keyword in ["refactor", "optimize", "debug", "design", "architect"]
        ):
            complexity = 0.8  # High complexity

        elif any(keyword in action for keyword in ["read", "search", "list[Any]", "get"]):
            complexity = 0.2  # Low complexity

        # Multi-step tasks
        if context.get("loop_depth", 0) > 0:
            complexity += 0.2  # More complex if in loop

        # Novel situations
        novelty = context.get("novelty", 0.5)
        complexity += novelty * 0.2

        return min(1.0, complexity)  # External lib

    def get_stats(self) -> dict[str, Any]:
        """Get horizon statistics."""
        if not self._recent_horizons:
            return {
                "avg_horizon": (self.min_horizon + self.max_horizon) / 2,
                "samples": 0,
            }

        return {
            "avg_horizon": sum(self._recent_horizons) / len(self._recent_horizons),
            "min_horizon_used": min(self._recent_horizons),
            "max_horizon_used": max(self._recent_horizons),
            "samples": len(self._recent_horizons),
        }


class AdaptiveBatchSize:
    """Adaptive batch size based on replay buffer state.

    Small buffer: Use small batches (avoid overfitting)
    Large buffer: Use large batches (stable gradients)
    """

    def __init__(self, min_batch: int = 4, max_batch: int = 32) -> None:
        """Initialize adaptive batch size.

        Args:
            min_batch: Minimum batch size
            max_batch: Maximum batch size
        """
        self.min_batch = min_batch
        self.max_batch = max_batch

    def compute_batch_size(self, buffer_size: int, buffer_capacity: int) -> int:
        """Compute optimal batch size.

        Args:
            buffer_size: Current buffer size
            buffer_capacity: Maximum buffer capacity

        Returns:
            Optimal batch size
        """
        # Buffer fill ratio
        fill_ratio = buffer_size / buffer_capacity if buffer_capacity > 0 else 0

        # Scale batch size with buffer size
        # Small buffer: small batches (avoid overfitting)
        # Large buffer: large batches (better gradients)
        batch_size = int(self.min_batch + fill_ratio * (self.max_batch - self.min_batch))

        # Ensure we have enough samples
        batch_size = min(batch_size, buffer_size // 2) if buffer_size > 0 else self.min_batch

        # Bound
        return max(self.min_batch, min(self.max_batch, batch_size))


class ExplorationDecay:
    """Decay exploration rate over time.

    Start: High exploration (learn environment)
    Later: Low exploration (exploit knowledge)

    Exponential decay with minimum threshold.
    """

    def __init__(
        self,
        initial_epsilon: float = 0.3,
        min_epsilon: float = 0.05,
        decay_rate: float = 0.995,
    ) -> None:
        """Initialize exploration decay.

        Args:
            initial_epsilon: Starting exploration rate
            min_epsilon: Minimum exploration rate
            decay_rate: Decay multiplier per step
        """
        self.initial_epsilon = initial_epsilon
        self.min_epsilon = min_epsilon
        self.decay_rate = decay_rate
        self.epsilon = initial_epsilon
        self.step = 0

    def get_epsilon(self) -> float:
        """Get current exploration rate."""
        return self.epsilon

    def decay(self) -> float:
        """Decay exploration rate and return new value."""
        self.step += 1
        self.epsilon = max(self.min_epsilon, self.initial_epsilon * (self.decay_rate**self.step))
        return self.epsilon

    def get_stats(self) -> dict[str, Any]:
        """Get exploration statistics."""
        return {
            "epsilon": self.epsilon,
            "step": self.step,
            "decay_progress": (
                (self.initial_epsilon - self.epsilon) / (self.initial_epsilon - self.min_epsilon)
            ),
        }

    def set_epsilon(self, epsilon: float) -> float:
        """Manually set[Any] exploration rate (bounded by [min_epsilon, 0.9]).

        Args:
            epsilon: Target exploration rate

        Returns:
            The applied exploration rate after bounding
        """
        # Bound epsilon conservatively
        bounded = max(self.min_epsilon, min(0.9, float(epsilon)))
        self.epsilon = bounded
        return self.epsilon


# Global singletons
_learning_rate: AdaptiveLearningRate | None = None
_horizon: AdaptiveHorizon | None = None
_batch_size: AdaptiveBatchSize | None = None
_exploration: ExplorationDecay | None = None


def get_adaptive_learning_rate() -> AdaptiveLearningRate:
    """Get or create global adaptive learning rate scheduler."""
    global _learning_rate
    if _learning_rate is None:
        _learning_rate = AdaptiveLearningRate()
    return _learning_rate


def get_adaptive_horizon() -> AdaptiveHorizon:
    """Get or create global adaptive horizon calculator."""
    global _horizon
    if _horizon is None:
        _horizon = AdaptiveHorizon()
    return _horizon


def get_adaptive_batch_size() -> AdaptiveBatchSize:
    """Get or create global adaptive batch size calculator."""
    global _batch_size
    if _batch_size is None:
        _batch_size = AdaptiveBatchSize()
    return _batch_size


def get_exploration_decay() -> ExplorationDecay:
    """Get or create global exploration decay."""
    global _exploration
    if _exploration is None:
        _exploration = ExplorationDecay()
    return _exploration


__all__ = [
    "AdaptiveBatchSize",
    "AdaptiveHorizon",
    "AdaptiveLearningRate",
    "ExplorationDecay",
    "get_adaptive_batch_size",
    "get_adaptive_horizon",
    "get_adaptive_learning_rate",
    "get_exploration_decay",
]
