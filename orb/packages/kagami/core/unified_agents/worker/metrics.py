"""Worker Performance Metrics.

Extracted from GeometricWorker to reduce god class complexity.

This module handles:
- Success/failure tracking
- Latency EMA updates
- Fitness updates
- Statistics collection

Created: December 21, 2025
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.unified_agents.geometric_worker import WorkerState

import logging

logger = logging.getLogger(__name__)


class WorkerMetrics:
    """Tracks worker performance metrics.

    Metrics:
    - Task completion (success/failure counts)
    - Average latency (EMA)
    - Fitness (EMA)
    - Age
    """

    def __init__(
        self,
        state: WorkerState,
        fitness_ema_alpha: float = 0.1,
    ):
        """Initialize metrics tracker.

        Args:
            state: Worker state reference
            fitness_ema_alpha: EMA smoothing factor for fitness
        """
        self.state = state
        self.fitness_ema_alpha = fitness_ema_alpha

    def update_success(self, latency: float) -> None:
        """Update state after successful execution.

        Args:
            latency: Task execution time
        """
        self.state.completed_tasks += 1

        # EMA update for latency
        alpha = self.fitness_ema_alpha
        self.state.avg_latency = alpha * latency + (1 - alpha) * self.state.avg_latency

        # Update fitness (small increase on success)
        self.state.fitness = min(1.0, self.state.fitness + 0.01)

    def update_failure(self, latency: float) -> None:
        """Update state after failed execution.

        Args:
            latency: Task execution time (even failures have latency)
        """
        self.state.failed_tasks += 1

        # Update fitness (larger decrease on failure)
        self.state.fitness = max(0.0, self.state.fitness - 0.05)

    def get_stats(self) -> dict[str, Any]:
        """Get worker statistics.

        Returns:
            Dict with all relevant metrics
        """
        return {
            "worker_id": self.state.worker_id,
            "colony": self.state.colony_name,
            "catastrophe": self.state.catastrophe_type,
            "status": self.state.status.value,
            "completed": self.state.completed_tasks,
            "failed": self.state.failed_tasks,
            "success_rate": self.state.success_rate,
            "fitness": self.state.fitness,
            "avg_latency": self.state.avg_latency,
            "current_tasks": self.state.current_tasks,
            "age_seconds": time.time() - self.state.created_at,
        }


__all__ = ["WorkerMetrics"]
