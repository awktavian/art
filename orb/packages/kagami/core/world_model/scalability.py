"""Scalability utilities for KagamiWorldModel.

This module provides utilities for:
- Sequence parallelism configuration
- Memory usage estimation
- Distributed training support
- Dynamic auto-scaling (Dec 27, 2025)

Created: December 6, 2025
Updated: December 27, 2025 - Added dynamic auto-scaling triggers
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.unified_agents.unified_organism import UnifiedOrganism

logger = logging.getLogger(__name__)


# =============================================================================
# AUTO-SCALING (Dec 27, 2025)
# =============================================================================


class ScalingAction(Enum):
    """Auto-scaling actions."""

    NONE = "none"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


@dataclass
class AutoScaleConfig:
    """Configuration for dynamic auto-scaling.

    RATIONALE (Dec 27, 2025):
    Dynamic scaling ensures optimal resource utilization:
    - Scale up when load exceeds threshold
    - Scale down when resources are underutilized
    - Prevent thrashing with cooldown periods
    """

    # Thresholds
    scale_up_load_threshold: float = 0.8  # 80% load → scale up
    scale_down_load_threshold: float = 0.3  # 30% load → scale down
    scale_up_latency_threshold: float = 1.0  # 1s avg latency → scale up
    queue_depth_threshold: int = 10  # Queue depth → scale up

    # Capacity
    min_workers_per_colony: int = 1
    max_workers_per_colony: int = 10
    scale_increment: int = 1  # Workers to add/remove per action

    # Timing
    evaluation_interval: float = 5.0  # Seconds between evaluations
    cooldown_period: float = 30.0  # Seconds between scaling actions
    warmup_period: float = 60.0  # Seconds before first scale decision


@dataclass
class ScalingMetrics:
    """Metrics for auto-scaling decisions."""

    timestamp: float = field(default_factory=time.time)
    load: float = 0.0  # 0-1, fraction of workers busy
    avg_latency: float = 0.0  # Seconds
    queue_depth: int = 0
    success_rate: float = 1.0
    worker_count: int = 0
    available_count: int = 0


@dataclass
class ScalingDecision:
    """Result of scaling evaluation."""

    action: ScalingAction
    colony_idx: int
    reason: str
    current_workers: int
    target_workers: int
    metrics: ScalingMetrics


class AutoScaler:
    """Dynamic auto-scaler for organism workers.

    PATTERN (Dec 27, 2025):
    =====================
    Implements reactive auto-scaling based on:
    1. Load (% workers busy)
    2. Latency (avg task latency)
    3. Queue depth (pending tasks)
    4. Success rate (health signal)

    Scaling Algorithm:
    - Collect metrics every evaluation_interval
    - Compare against thresholds
    - Apply cooldown to prevent thrashing
    - Scale incrementally (not all at once)

    Usage:
        scaler = AutoScaler(organism)
        await scaler.start()  # Background monitoring
        # ... later
        await scaler.stop()
    """

    def __init__(
        self,
        organism: UnifiedOrganism,
        config: AutoScaleConfig | None = None,
    ):
        """Initialize auto-scaler.

        Args:
            organism: UnifiedOrganism to scale
            config: Auto-scaling configuration
        """
        self._organism = organism
        self.config = config or AutoScaleConfig()
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_scale_time: float = 0.0
        self._start_time: float = 0.0
        self._metrics_history: list[ScalingMetrics] = []
        self._decisions: list[ScalingDecision] = []

    async def start(self) -> None:
        """Start background auto-scaling."""
        if self._running:
            return
        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._scaling_loop())
        logger.info("AutoScaler started")

    async def stop(self) -> None:
        """Stop auto-scaling."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("AutoScaler stopped")

    async def _scaling_loop(self) -> None:
        """Background scaling evaluation loop."""
        while self._running:
            await asyncio.sleep(self.config.evaluation_interval)

            # Skip during warmup
            if time.time() - self._start_time < self.config.warmup_period:
                continue

            # Evaluate each colony
            for colony_idx in range(7):
                decision = await self._evaluate_colony(colony_idx)
                if decision.action != ScalingAction.NONE:
                    await self._apply_decision(decision)

    async def _evaluate_colony(self, colony_idx: int) -> ScalingDecision:
        """Evaluate scaling need for a colony.

        Args:
            colony_idx: Colony to evaluate (0-6)

        Returns:
            Scaling decision
        """
        metrics = await self._collect_metrics(colony_idx)
        self._metrics_history.append(metrics)

        # Trim history to last 100 entries
        if len(self._metrics_history) > 100:
            self._metrics_history = self._metrics_history[-100:]

        # Check cooldown
        if time.time() - self._last_scale_time < self.config.cooldown_period:
            return ScalingDecision(
                action=ScalingAction.NONE,
                colony_idx=colony_idx,
                reason="cooldown",
                current_workers=metrics.worker_count,
                target_workers=metrics.worker_count,
                metrics=metrics,
            )

        # Evaluate scale up conditions
        if self._should_scale_up(metrics):
            target = min(
                metrics.worker_count + self.config.scale_increment,
                self.config.max_workers_per_colony,
            )
            if target > metrics.worker_count:
                return ScalingDecision(
                    action=ScalingAction.SCALE_UP,
                    colony_idx=colony_idx,
                    reason=self._scale_up_reason(metrics),
                    current_workers=metrics.worker_count,
                    target_workers=target,
                    metrics=metrics,
                )

        # Evaluate scale down conditions
        if self._should_scale_down(metrics):
            target = max(
                metrics.worker_count - self.config.scale_increment,
                self.config.min_workers_per_colony,
            )
            if target < metrics.worker_count:
                return ScalingDecision(
                    action=ScalingAction.SCALE_DOWN,
                    colony_idx=colony_idx,
                    reason=self._scale_down_reason(metrics),
                    current_workers=metrics.worker_count,
                    target_workers=target,
                    metrics=metrics,
                )

        return ScalingDecision(
            action=ScalingAction.NONE,
            colony_idx=colony_idx,
            reason="within_thresholds",
            current_workers=metrics.worker_count,
            target_workers=metrics.worker_count,
            metrics=metrics,
        )

    def _should_scale_up(self, metrics: ScalingMetrics) -> bool:
        """Check if colony should scale up."""
        return (
            metrics.load > self.config.scale_up_load_threshold
            or metrics.avg_latency > self.config.scale_up_latency_threshold
            or metrics.queue_depth > self.config.queue_depth_threshold
        )

    def _should_scale_down(self, metrics: ScalingMetrics) -> bool:
        """Check if colony should scale down."""
        return (
            metrics.load < self.config.scale_down_load_threshold
            and metrics.queue_depth == 0
            and metrics.worker_count > self.config.min_workers_per_colony
        )

    def _scale_up_reason(self, metrics: ScalingMetrics) -> str:
        """Get reason for scale up."""
        reasons = []
        if metrics.load > self.config.scale_up_load_threshold:
            reasons.append(f"high_load({metrics.load:.0%})")
        if metrics.avg_latency > self.config.scale_up_latency_threshold:
            reasons.append(f"high_latency({metrics.avg_latency:.2f}s)")
        if metrics.queue_depth > self.config.queue_depth_threshold:
            reasons.append(f"queue_depth({metrics.queue_depth})")
        return ",".join(reasons) or "unknown"

    def _scale_down_reason(self, metrics: ScalingMetrics) -> str:
        """Get reason for scale down."""
        return f"low_load({metrics.load:.0%})"

    async def _collect_metrics(self, colony_idx: int) -> ScalingMetrics:
        """Collect scaling metrics for a colony."""
        try:
            colony = self._organism.get_colony_by_index(colony_idx)
            if colony is None:
                return ScalingMetrics()

            worker_count = colony.get_worker_count()
            available_count = colony.get_available_count()

            # Compute load (0 workers = 0 load, avoid division by zero)
            load = 0.0
            if worker_count > 0:
                load = 1.0 - (available_count / worker_count)

            # Get latency from stats
            stats = getattr(colony, "stats", None)
            avg_latency = getattr(stats, "avg_latency", 0.0) if stats else 0.0
            success_rate = getattr(stats, "success_rate", 1.0) if stats else 1.0

            # Queue depth (if available)
            queue_depth = getattr(colony, "queue_depth", 0)

            return ScalingMetrics(
                timestamp=time.time(),
                load=load,
                avg_latency=avg_latency,
                queue_depth=queue_depth,
                success_rate=success_rate,
                worker_count=worker_count,
                available_count=available_count,
            )
        except Exception as e:
            logger.debug(f"Failed to collect metrics for colony {colony_idx}: {e}")
            return ScalingMetrics()

    async def _apply_decision(self, decision: ScalingDecision) -> None:
        """Apply a scaling decision.

        Args:
            decision: Scaling decision to apply
        """
        self._decisions.append(decision)
        self._last_scale_time = time.time()

        try:
            colony = self._organism.get_colony_by_index(decision.colony_idx)
            if colony is None:
                logger.warning(f"Colony {decision.colony_idx} not found for scaling")
                return

            if decision.action == ScalingAction.SCALE_UP:
                # Add workers
                workers_to_add = decision.target_workers - decision.current_workers
                for _ in range(workers_to_add):
                    if hasattr(colony, "add_worker"):
                        await colony.add_worker()
                logger.info(
                    f"Scaled UP colony {decision.colony_idx}: "
                    f"{decision.current_workers} → {decision.target_workers} "
                    f"({decision.reason})"
                )

            elif decision.action == ScalingAction.SCALE_DOWN:
                # Remove workers
                workers_to_remove = decision.current_workers - decision.target_workers
                for _ in range(workers_to_remove):
                    if hasattr(colony, "remove_worker"):
                        await colony.remove_worker()
                logger.info(
                    f"Scaled DOWN colony {decision.colony_idx}: "
                    f"{decision.current_workers} → {decision.target_workers} "
                    f"({decision.reason})"
                )

        except Exception as e:
            logger.error(f"Failed to apply scaling decision: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get auto-scaler statistics."""
        return {
            "running": self._running,
            "start_time": self._start_time,
            "last_scale_time": self._last_scale_time,
            "decisions_count": len(self._decisions),
            "recent_decisions": [
                {
                    "action": d.action.value,
                    "colony_idx": d.colony_idx,
                    "reason": d.reason,
                    "current": d.current_workers,
                    "target": d.target_workers,
                }
                for d in self._decisions[-10:]
            ],
            "config": {
                "scale_up_load": self.config.scale_up_load_threshold,
                "scale_down_load": self.config.scale_down_load_threshold,
                "min_workers": self.config.min_workers_per_colony,
                "max_workers": self.config.max_workers_per_colony,
            },
        }


# =============================================================================
# SEQUENCE PARALLELISM
# =============================================================================


@dataclass
class SequenceParallelConfig:
    """Configuration for sequence parallelism.

    Sequence parallelism splits long sequences across GPUs,
    reducing memory per GPU for very long context.

    Attributes:
        sequence_parallel_size: Number of GPUs to split sequences across
        overlap_communication: Whether to overlap compute with communication
    """

    sequence_parallel_size: int = 1
    overlap_communication: bool = True


def estimate_memory_usage(
    model: Any,
    input_shape: tuple[int, ...],
) -> dict[str, float]:
    """Estimate memory usage for training.

    Provides rough estimates to help determine batch size and
    sequence length for available GPU memory.

    Args:
        model: KagamiWorldModel instance
        input_shape: (batch_size, seq_len, input_dim) tuple[Any, ...]

    Returns:
        Dict with memory estimates in MB:
        - params_mb: Model parameters
        - activations_mb: Forward pass activations
        - gradients_mb: Gradient storage
        - optimizer_mb: Optimizer state (Adam = 2x params)
        - total_mb: Total estimated memory
    """
    batch_size, seq_len, input_dim = input_shape

    # Count parameters
    num_params = sum(p.numel() for p in model.parameters())
    params_bytes = num_params * 4  # float32
    params_mb = params_bytes / (1024 * 1024)

    # Estimate activations (rough: batch * seq * hidden * num_layers * 4)
    # This is a simplification - actual depends on architecture
    hidden_dim = getattr(model.config, "layer_dimensions", [input_dim])[-1]
    num_layers = getattr(model, "num_layers", 6)

    activation_bytes = batch_size * seq_len * hidden_dim * num_layers * 4
    activations_mb = activation_bytes / (1024 * 1024)

    # Gradients = same as parameters
    gradients_mb = params_mb

    # Optimizer state (Adam uses 2x params for momentum and variance)
    optimizer_mb = params_mb * 2

    total_mb = params_mb + activations_mb + gradients_mb + optimizer_mb

    return {
        "params_mb": round(params_mb, 2),
        "activations_mb": round(activations_mb, 2),
        "gradients_mb": round(gradients_mb, 2),
        "optimizer_mb": round(optimizer_mb, 2),
        "total_mb": round(total_mb, 2),
    }


__all__ = [
    "AutoScaleConfig",
    "AutoScaler",
    "ScalingAction",
    "ScalingDecision",
    "ScalingMetrics",
    "SequenceParallelConfig",
    "estimate_memory_usage",
]
