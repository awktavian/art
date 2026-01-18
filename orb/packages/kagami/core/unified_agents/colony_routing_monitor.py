"""Colony Routing Monitor — Detect local optima and dead colonies.

The 7-colony architecture routes tasks via Fano plane geometry. If routing gets
stuck in local optima (e.g., always using Forge, never using Grove), the system
loses diverse perspectives.

MONITORS:
- Colony usage distribution (Gini coefficient)
- Dead colonies (< 5% of recent routes)
- Task-colony success rates
- Exploration-exploitation balance

RECOVERY:
- Force exploration for underutilized colonies
- Override router with UCB-style bonuses
- A/B test alternative routing strategies

Created: December 14, 2025 (Flow e₃)
Reference: CLAUDE.md — Fano plane routing § 3.2
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Colony names (canonical)
COLONY_NAMES = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]


@dataclass
class RoutingMetrics:
    """Metrics for colony routing health."""

    gini_coefficient: float  # Inequality (0 = perfect balance, 1 = one colony dominates)
    dead_colonies: list[int]  # Colony indices with < 5% usage
    usage_counts: list[int]  # Counts per colony [7]
    success_rates: list[float]  # Success rate per colony [7]
    total_routes: int  # Total routing decisions
    is_healthy: bool  # True if routing is diverse and effective


@dataclass
class RoutingEvent:
    """Single routing decision record."""

    colony_idx: int
    colony_name: str
    task_type: str
    success: bool
    timestamp: float
    complexity: float | None = None


class ColonyRoutingMonitor:
    """Monitor colony routing for local optima and dead colonies.

    HEALTH INDICATORS:
    - Gini < 0.6: Balanced routing (good)
    - Gini 0.6-0.7: Moderate imbalance (caution)
    - Gini > 0.7: Severe imbalance (unhealthy)

    DEAD COLONY THRESHOLD:
    - Colony usage < 5% of recent window (default: 1000 routes)

    USAGE:
        monitor = ColonyRoutingMonitor(window_size=1000)
        for task in tasks:
            colony_idx = router.route(task)
            success = execute_task(colony_idx, task)
            monitor.record_routing(colony_idx, task.type, success)
            metrics = monitor.get_metrics()
            if not metrics.is_healthy:
                # Trigger exploration or reset router
    """

    def __init__(
        self,
        window_size: int = 1000,
        dead_threshold: float = 0.05,
        gini_threshold: float = 0.7,
    ):
        """Initialize colony routing monitor.

        Args:
            window_size: Number of recent routes to track
            dead_threshold: Usage fraction below which colony is "dead"
            gini_threshold: Gini coefficient above which routing is unhealthy
        """
        self.window_size = window_size
        self.dead_threshold = dead_threshold
        self.gini_threshold = gini_threshold

        # Routing history (sliding window)
        self.routing_history: list[RoutingEvent] = []

        # Success tracking per colony
        self.colony_success_counts = [0] * 7
        self.colony_total_counts = [0] * 7

        # Task-colony affinity learning
        self.task_colony_success: dict[str, dict[int, tuple[int, int]]] = defaultdict(
            lambda: dict[str, Any].fromkeys(range(7), (0, 0))
        )  # task_type -> {colony_idx: (successes, total)}

    def record_routing(
        self,
        colony_idx: int,
        task_type: str,
        success: bool,
        complexity: float | None = None,
    ) -> None:
        """Record a routing decision and its outcome.

        Args:
            colony_idx: Which colony was chosen (0-6)
            task_type: Type of task (e.g., "create", "build", "fix")
            success: Whether the task succeeded
            complexity: Task complexity (optional)
        """
        if not 0 <= colony_idx < 7:
            logger.warning(f"Invalid colony_idx: {colony_idx}")
            return

        # Record event
        event = RoutingEvent(
            colony_idx=colony_idx,
            colony_name=COLONY_NAMES[colony_idx],
            task_type=task_type,
            success=success,
            timestamp=time.time(),
            complexity=complexity,
        )
        self.routing_history.append(event)

        # Maintain sliding window
        if len(self.routing_history) > self.window_size:
            # Remove oldest event and update counts
            oldest = self.routing_history.pop(0)
            self.colony_total_counts[oldest.colony_idx] -= 1
            if oldest.success:
                self.colony_success_counts[oldest.colony_idx] -= 1

        # Update success tracking
        self.colony_total_counts[colony_idx] += 1
        if success:
            self.colony_success_counts[colony_idx] += 1

        # Update task-colony affinity
        task_stats = self.task_colony_success[task_type][colony_idx]
        new_total = task_stats[1] + 1
        new_successes = task_stats[0] + (1 if success else 0)
        self.task_colony_success[task_type][colony_idx] = (new_successes, new_total)

    def get_metrics(self) -> RoutingMetrics:
        """Compute current routing health metrics.

        Returns:
            RoutingMetrics with health assessment
        """
        # Compute usage distribution
        usage_counts = self._get_usage_counts()
        gini = self._compute_gini_coefficient(usage_counts)

        # Detect dead colonies
        dead_colonies = self._detect_dead_colonies(usage_counts)

        # Compute success rates
        success_rates = [
            (
                self.colony_success_counts[i] / self.colony_total_counts[i]
                if self.colony_total_counts[i] > 0
                else 0.0
            )
            for i in range(7)
        ]

        # Assess health
        is_healthy = self._is_healthy(gini, dead_colonies)

        return RoutingMetrics(
            gini_coefficient=gini,
            dead_colonies=dead_colonies,
            usage_counts=usage_counts,
            success_rates=success_rates,
            total_routes=len(self.routing_history),
            is_healthy=is_healthy,
        )

    def _get_usage_counts(self) -> list[int]:
        """Get usage count per colony from recent history."""
        counts = [0] * 7
        for event in self.routing_history:
            counts[event.colony_idx] += 1
        return counts

    def _compute_gini_coefficient(self, usage_counts: list[int]) -> float:
        """Compute Gini coefficient to measure routing inequality.

        Gini = 0: Perfect equality (all colonies used equally)
        Gini = 1: Perfect inequality (one colony used exclusively)

        Formula: G = (2 * Σ(i * x_i)) / (n * Σx_i) - (n+1)/n

        Args:
            usage_counts: List of usage counts per colony

        Returns:
            Gini coefficient (0.0 to 1.0)
        """
        if sum(usage_counts) == 0:
            return 0.0

        # Sort counts for Lorenz curve
        sorted_counts = sorted(usage_counts)
        n = len(sorted_counts)

        # Compute cumulative sum weighted by rank
        cumsum = sum((i + 1) * count for i, count in enumerate(sorted_counts))
        total = sum(sorted_counts)

        # Gini formula
        gini = (2 * cumsum) / (n * total) - (n + 1) / n

        return gini

    def _detect_dead_colonies(self, usage_counts: list[int]) -> list[int]:
        """Detect colonies with usage below threshold.

        Args:
            usage_counts: List of usage counts per colony

        Returns:
            List of colony indices that are "dead"
        """
        total = sum(usage_counts)
        if total == 0:
            return list(range(7))  # All dead if no routes

        threshold_count = int(total * self.dead_threshold)
        dead = [i for i, count in enumerate(usage_counts) if count < threshold_count]

        if dead:
            dead_names = [COLONY_NAMES[i] for i in dead]
            logger.warning(
                f"⚠️ DEAD COLONIES detected: {dead_names} (< {self.dead_threshold:.0%} usage)"
            )

        return dead

    def _is_healthy(self, gini: float, dead_colonies: list[int]) -> bool:
        """Assess overall routing health.

        Args:
            gini: Gini coefficient
            dead_colonies: List of dead colony indices

        Returns:
            True if healthy, False if unhealthy
        """
        # Check Gini threshold
        if gini > self.gini_threshold:
            logger.error(f"❌ ROUTING IMBALANCE: Gini={gini:.2f} > threshold={self.gini_threshold}")
            return False

        # Check for dead colonies
        if len(dead_colonies) > 2:
            logger.error(f"❌ TOO MANY DEAD COLONIES: {len(dead_colonies)} colonies unused")
            return False

        return True

    def get_exploration_bonus(self, colony_idx: int) -> float:
        """Compute exploration bonus for underutilized colonies (UCB-style).

        UCB formula: sqrt(log(total) / uses)

        This encourages exploration of colonies that haven't been tried much.

        Args:
            colony_idx: Colony to compute bonus for

        Returns:
            Exploration bonus (higher = more exploration needed)
        """
        total_uses = len(self.routing_history)
        colony_uses = self.colony_total_counts[colony_idx]

        if colony_uses == 0:
            return 10.0  # Maximum bonus for unused colonies

        if total_uses <= 1:
            return 0.0  # No bonus if not enough data

        # Upper Confidence Bound formula
        bonus = math.sqrt(math.log(total_uses) / colony_uses)

        return bonus

    def get_task_affinity(self, task_type: str) -> dict[int, float | None]:
        """Get learned affinity scores for task type.

        Args:
            task_type: Type of task

        Returns:
            Dictionary mapping colony_idx -> success_rate (None if no data)
        """
        if task_type not in self.task_colony_success:
            # No data: return None to indicate unknown affinity
            return dict[str, Any].fromkeys(range(7), None)

        affinity: dict[int, float | None] = {}
        for colony_idx in range(7):
            successes, total = self.task_colony_success[task_type][colony_idx]
            if total == 0:
                affinity[colony_idx] = None  # No data, not fake 0.5
            else:
                affinity[colony_idx] = successes / total

        return affinity

    def suggest_exploration(self) -> int | None:
        """Suggest a colony to explore (if exploration is needed).

        Returns:
            Colony index to explore, or None if no exploration needed
        """
        metrics = self.get_metrics()

        # If unhealthy, suggest least-used colony
        if not metrics.is_healthy:
            usage_counts = metrics.usage_counts
            min_usage_idx = usage_counts.index(min(usage_counts))
            logger.info(f"🔍 EXPLORATION: Suggesting {COLONY_NAMES[min_usage_idx]} (least used)")
            return min_usage_idx

        return None

    def reset(self) -> None:
        """Reset monitoring state (e.g., after router reset)."""
        self.routing_history = []
        self.colony_success_counts = [0] * 7
        self.colony_total_counts = [0] * 7
        self.task_colony_success = defaultdict(lambda: dict[str, Any].fromkeys(range(7), (0, 0)))
        logger.info("🔄 ColonyRoutingMonitor reset")


def create_routing_monitor(
    window_size: int = 1000,
    dead_threshold: float = 0.05,
    gini_threshold: float = 0.7,
) -> ColonyRoutingMonitor:
    """Factory function for creating a colony routing monitor.

    Args:
        window_size: Number of recent routes to track
        dead_threshold: Usage fraction below which colony is "dead"
        gini_threshold: Gini coefficient above which routing is unhealthy

    Returns:
        Configured ColonyRoutingMonitor instance
    """
    return ColonyRoutingMonitor(
        window_size=window_size,
        dead_threshold=dead_threshold,
        gini_threshold=gini_threshold,
    )


__all__ = [
    "COLONY_NAMES",
    "ColonyRoutingMonitor",
    "RoutingEvent",
    "RoutingMetrics",
    "create_routing_monitor",
]
