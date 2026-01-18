"""Production Monitoring Dashboard - Real-time system observability.

Provides comprehensive monitoring of the autonomous system including:
- Receipt processing metrics
- Learning convergence tracking
- Safety margin visualization
- Colony utilization
- Population diversity
- μ_self trajectory

Integrates with Prometheus/Grafana for production deployment.

Created: December 14, 2025
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from prometheus_client import Counter, Gauge, Histogram, Summary

logger = logging.getLogger(__name__)


# Check if in test environment
_IN_TESTS = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get("_", "")


# Prometheus metrics - use dummy metrics in test environment to avoid registry conflicts
class _DummyMetric:
    """No-op metric for test environments."""

    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def observe(self, amount):
        pass

    def set(self, value):
        pass


def _safe_create_counter(name: str, desc: str, labels: list[str] | None = None) -> Counter:
    """Create counter, returning dummy in tests if already registered."""
    if _IN_TESTS:
        return _DummyMetric()  # type: ignore
    try:
        return Counter(name, desc, labels or [])
    except ValueError:
        return _DummyMetric()  # type: ignore


def _safe_create_gauge(name: str, desc: str, labels: list[str] | None = None) -> Gauge:
    """Create gauge, returning dummy in tests if already registered."""
    if _IN_TESTS:
        return _DummyMetric()  # type: ignore
    try:
        return Gauge(name, desc, labels or [])
    except ValueError:
        return _DummyMetric()  # type: ignore


def _safe_create_histogram(name: str, desc: str, labels: list[str] | None = None) -> Histogram:
    """Create histogram, returning dummy in tests if already registered."""
    if _IN_TESTS:
        return _DummyMetric()  # type: ignore
    try:
        return Histogram(name, desc, labels or [])
    except ValueError:
        return _DummyMetric()  # type: ignore


def _safe_create_summary(name: str, desc: str, labels: list[str] | None = None) -> Summary:
    """Create summary, returning dummy in tests if already registered."""
    if _IN_TESTS:
        return _DummyMetric()  # type: ignore
    try:
        return Summary(name, desc, labels or [])
    except ValueError:
        return _DummyMetric()  # type: ignore


# Prometheus metrics - safely created
RECEIPT_COUNTER = _safe_create_counter(
    "kagami_receipts", "Total receipts processed", ["colony", "status"]
)
INTENT_DURATION = _safe_create_histogram(
    "kagami_intent_duration_seconds", "Intent execution duration", ["intent_type"]
)
SAFETY_GAUGE = _safe_create_gauge("kagami_safety_score", "Current safety score (0-1)")
COLONY_UTILIZATION = _safe_create_gauge(
    "kagami_colony_utilization", "Colony utilization percentage", ["colony"]
)
MU_SELF_DISTANCE = _safe_create_gauge(
    "kagami_mu_self_distance", "Distance to fixed point convergence"
)
LEARNING_LOSS = _safe_create_gauge("kagami_learning_loss", "Current learning loss", ["model"])
POPULATION_DIVERSITY = _safe_create_gauge(
    "kagami_population_diversity", "Population genetic diversity score"
)
MODIFICATION_SUCCESS = _safe_create_summary(
    "kagami_modification_success_rate", "Self-modification success rate"
)


@dataclass
class MetricWindow:
    """Sliding window for metric tracking."""

    max_size: int = 1000
    data: deque = field(default_factory=deque)
    timestamps: deque = field(default_factory=deque)

    def add(self, value: float, timestamp: float | None = None) -> None:
        """Add value to window."""
        if timestamp is None:
            timestamp = time.time()

        self.data.append(value)
        self.timestamps.append(timestamp)

        # Maintain window size
        while len(self.data) > self.max_size:
            self.data.popleft()
            self.timestamps.popleft()

    def get_recent(self, seconds: float = 60.0) -> list[float]:
        """Get values from last N seconds."""
        cutoff = time.time() - seconds
        recent = []
        for val, ts in zip(self.data, self.timestamps, strict=False):
            if ts > cutoff:
                recent.append(val)
        return recent

    def mean(self) -> float:
        """Get mean of window."""
        return np.mean(self.data) if self.data else 0.0

    def std(self) -> float:
        """Get standard deviation."""
        return np.std(self.data) if len(self.data) > 1 else 0.0


@dataclass
class SystemMetrics:
    """Comprehensive system metrics."""

    # Receipt tracking
    receipts_by_colony: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    receipt_success_rate: MetricWindow = field(default_factory=MetricWindow)

    # Learning metrics
    loss_history: MetricWindow = field(default_factory=MetricWindow)
    gradient_norms: MetricWindow = field(default_factory=MetricWindow)
    learning_rate: float = 1e-3

    # Safety tracking
    safety_scores: MetricWindow = field(default_factory=MetricWindow)
    safety_violations: int = 0
    cbf_values: MetricWindow = field(default_factory=MetricWindow)

    # Colony metrics
    colony_calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    colony_latencies: dict[str, MetricWindow] = field(
        default_factory=lambda: defaultdict(MetricWindow)
    )

    # Population metrics
    population_size: int = 7
    best_fitness: float = 0.0
    diversity_score: float = 1.0

    # μ_self convergence
    mu_self_trajectory: list[float] = field(default_factory=list[Any])
    convergence_rate: float = 0.0

    # System health
    uptime_seconds: float = 0.0
    total_intents: int = 0
    error_count: int = 0


class MonitoringDashboard:
    """Real-time monitoring and visualization."""

    def __init__(
        self,
        update_interval: float = 1.0,
        export_prometheus: bool = True,
        enable_wandb: bool = False,
        wandb_project: str = "kagami-os",
    ):
        self.update_interval = update_interval
        self.export_prometheus = export_prometheus
        self.enable_wandb = enable_wandb

        # Metrics storage
        self.metrics = SystemMetrics()
        self.start_time = time.time()

        # WandB integration
        if enable_wandb:
            try:
                import wandb

                self.wandb = wandb
                self.wandb.init(project=wandb_project, name=f"kagami_{int(time.time())}")
                logger.info("WandB monitoring enabled")
            except ImportError:
                logger.warning("WandB not available")
                self.enable_wandb = False

        logger.info(
            f"MonitoringDashboard initialized: prometheus={export_prometheus}, wandb={enable_wandb}"
        )

    def record_receipt(
        self,
        colony: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record receipt processing."""
        self.metrics.receipts_by_colony[colony] += 1
        self.metrics.receipt_success_rate.add(1.0 if success else 0.0)

        # Update Prometheus
        if self.export_prometheus:
            status = "success" if success else "failure"
            RECEIPT_COUNTER.labels(colony=colony, status=status).inc()
            INTENT_DURATION.labels(intent_type=colony).observe(duration_ms / 1000.0)

        # Update WandB
        if self.enable_wandb:
            self.wandb.log(
                {
                    f"receipts/{colony}/count": self.metrics.receipts_by_colony[colony],
                    f"receipts/{colony}/duration_ms": duration_ms,
                    "receipts/success_rate": self.metrics.receipt_success_rate.mean(),
                }
            )

    def record_learning_step(
        self,
        loss: float,
        grad_norm: float | None = None,
        model_name: str = "world_model",
    ) -> None:
        """Record learning metrics."""
        self.metrics.loss_history.add(loss)
        if grad_norm is not None:
            self.metrics.gradient_norms.add(grad_norm)

        # Update Prometheus
        if self.export_prometheus:
            LEARNING_LOSS.labels(model=model_name).set(loss)

        # Update WandB
        if self.enable_wandb:
            log_dict = {f"learning/{model_name}/loss": loss}
            if grad_norm is not None:
                log_dict[f"learning/{model_name}/grad_norm"] = grad_norm
            self.wandb.log(log_dict)

    def record_safety_status(
        self,
        safety_score: float,
        cbf_value: float | None = None,
    ) -> None:
        """Record safety metrics."""
        self.metrics.safety_scores.add(safety_score)
        if cbf_value is not None:
            self.metrics.cbf_values.add(cbf_value)

        if safety_score < 0.5:
            self.metrics.safety_violations += 1

        # Update Prometheus
        if self.export_prometheus:
            SAFETY_GAUGE.set(safety_score)

        # Update WandB
        if self.enable_wandb:
            log_dict = {
                "safety/score": safety_score,
                "safety/violations": self.metrics.safety_violations,
            }
            if cbf_value is not None:
                log_dict["safety/cbf_value"] = cbf_value
            self.wandb.log(log_dict)

    def record_colony_activity(
        self,
        colony: str,
        latency_ms: float,
    ) -> None:
        """Record colony utilization."""
        self.metrics.colony_calls[colony] += 1
        self.metrics.colony_latencies[colony].add(latency_ms)

        # Calculate utilization (calls per minute)
        uptime_minutes = max(1.0, (time.time() - self.start_time) / 60.0)
        utilization = self.metrics.colony_calls[colony] / uptime_minutes

        # Update Prometheus
        if self.export_prometheus:
            COLONY_UTILIZATION.labels(colony=colony).set(utilization)

        # Update WandB
        if self.enable_wandb:
            self.wandb.log(
                {
                    f"colonies/{colony}/calls": self.metrics.colony_calls[colony],
                    f"colonies/{colony}/latency_ms": latency_ms,
                    f"colonies/{colony}/utilization": utilization,
                }
            )

    def record_mu_self_convergence(
        self,
        distance: float,
    ) -> None:
        """Record μ_self fixed point convergence."""
        self.metrics.mu_self_trajectory.append(distance)

        # Calculate convergence rate
        if len(self.metrics.mu_self_trajectory) > 10:
            recent = self.metrics.mu_self_trajectory[-10:]
            self.metrics.convergence_rate = (recent[0] - recent[-1]) / len(recent)

        # Update Prometheus
        if self.export_prometheus:
            MU_SELF_DISTANCE.set(distance)

        # Update WandB
        if self.enable_wandb:
            self.wandb.log(
                {
                    "mu_self/distance": distance,
                    "mu_self/convergence_rate": self.metrics.convergence_rate,
                }
            )

    def record_population_metrics(
        self,
        population_size: int,
        best_fitness: float,
        diversity: float,
    ) -> None:
        """Record population evolution metrics."""
        self.metrics.population_size = population_size
        self.metrics.best_fitness = best_fitness
        self.metrics.diversity_score = diversity

        # Update Prometheus
        if self.export_prometheus:
            POPULATION_DIVERSITY.set(diversity)

        # Update WandB
        if self.enable_wandb:
            self.wandb.log(
                {
                    "population/size": population_size,
                    "population/best_fitness": best_fitness,
                    "population/diversity": diversity,
                }
            )

    def record_modification(
        self,
        success: bool,
        improvement: float = 0.0,
    ) -> None:
        """Record self-modification attempt."""
        # Update Prometheus
        if self.export_prometheus:
            MODIFICATION_SUCCESS.observe(1.0 if success else 0.0)

        # Update WandB
        if self.enable_wandb:
            self.wandb.log(
                {
                    "modifications/success": success,
                    "modifications/improvement": improvement,
                }
            )

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        uptime = time.time() - self.start_time

        return {
            "uptime_hours": uptime / 3600.0,
            "total_receipts": sum(self.metrics.receipts_by_colony.values()),
            "receipt_success_rate": self.metrics.receipt_success_rate.mean(),
            "average_loss": self.metrics.loss_history.mean(),
            "safety_score": self.metrics.safety_scores.mean(),
            "safety_violations": self.metrics.safety_violations,
            "mu_self_distance": (
                self.metrics.mu_self_trajectory[-1] if self.metrics.mu_self_trajectory else 1.0
            ),
            "convergence_rate": self.metrics.convergence_rate,
            "population_diversity": self.metrics.diversity_score,
            "most_active_colony": max(
                self.metrics.colony_calls.items(), key=lambda x: x[1], default=("none", 0)
            )[0],
        }

    def export_metrics_json(self) -> str:
        """Export metrics as JSON."""
        summary = self.get_summary()

        # Add detailed metrics
        summary["colonies"] = {
            colony: {
                "calls": count,
                "avg_latency_ms": self.metrics.colony_latencies[colony].mean(),
            }
            for colony, count in self.metrics.colony_calls.items()
        }

        summary["safety"] = {
            "current_score": self.metrics.safety_scores.data[-1]
            if self.metrics.safety_scores.data
            else 0.0,
            "min_score": min(self.metrics.safety_scores.data, default=0.0),
            "max_score": max(self.metrics.safety_scores.data, default=1.0),
        }

        return json.dumps(summary, indent=2)

    def generate_alert(self, condition: str, severity: str = "warning") -> dict[str, Any]:
        """Generate alert for monitoring systems."""
        return {
            "timestamp": time.time(),
            "severity": severity,
            "condition": condition,
            "metrics": self.get_summary(),
        }

    def check_health(self) -> tuple[bool, list[str]]:
        """Check system health and return issues."""
        issues = []

        # Check safety
        if self.metrics.safety_violations > 0:
            issues.append(f"Safety violations: {self.metrics.safety_violations}")

        # Check learning
        recent_loss = self.metrics.loss_history.get_recent(60)
        if recent_loss and min(recent_loss) > 1.0:
            issues.append(f"High loss: {min(recent_loss):.3f}")

        # Check convergence
        if len(self.metrics.mu_self_trajectory) > 100:
            if self.metrics.convergence_rate < 0.001:
                issues.append("Slow μ_self convergence")

        # Check colony balance
        if self.metrics.colony_calls:
            max_calls = max(self.metrics.colony_calls.values())
            min_calls = min(self.metrics.colony_calls.values())
            if max_calls > min_calls * 10:
                issues.append("Colony imbalance detected")

        is_healthy = len(issues) == 0
        return is_healthy, issues


# Singleton instance
_dashboard: MonitoringDashboard | None = None


def get_monitoring_dashboard(
    export_prometheus: bool = True,
    enable_wandb: bool = False,
) -> MonitoringDashboard:
    """Get or create monitoring dashboard."""
    global _dashboard
    if _dashboard is None:
        _dashboard = MonitoringDashboard(
            export_prometheus=export_prometheus,
            enable_wandb=enable_wandb,
        )
    return _dashboard
