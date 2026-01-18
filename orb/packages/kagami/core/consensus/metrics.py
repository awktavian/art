"""PBFT Consensus Metrics — Observable Byzantine Behavior.

Provides Prometheus-compatible metrics for monitoring PBFT consensus:
- Latency histograms
- Message counters
- View change tracking
- Byzantine detection alerts

Colony: Crystal (D₅) — Verification through observation
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""

    COUNTER = auto()
    GAUGE = auto()
    HISTOGRAM = auto()
    SUMMARY = auto()


@dataclass
class HistogramBucket:
    """Histogram bucket for latency tracking."""

    le: float  # Less than or equal to
    count: int = 0


@dataclass
class Metric:
    """A single metric value with labels.

    Attributes:
        name: Metric name.
        metric_type: Type of metric.
        help_text: Description of metric.
        labels: Label key-value pairs.
        value: Current value.
        buckets: Histogram buckets (for HISTOGRAM type).
    """

    name: str
    metric_type: MetricType
    help_text: str
    labels: dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    buckets: list[HistogramBucket] = field(default_factory=list)

    def inc(self, amount: float = 1.0) -> None:
        """Increment counter."""
        self.value += amount

    def set(self, value: float) -> None:
        """Set gauge value."""
        self.value = value

    def observe(self, value: float) -> None:
        """Observe value for histogram."""
        for bucket in self.buckets:
            if value <= bucket.le:
                bucket.count += 1

    def to_prometheus(self) -> str:
        """Export in Prometheus format."""
        label_str = ""
        if self.labels:
            label_pairs = [f'{k}="{v}"' for k, v in self.labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"

        if self.metric_type == MetricType.HISTOGRAM:
            lines = []
            for bucket in self.buckets:
                lines.append(f'{self.name}_bucket{{le="{bucket.le}"{label_str}}} {bucket.count}')
            lines.append(f"{self.name}_sum{label_str} {self.value}")
            lines.append(f"{self.name}_count{label_str} {len(self.buckets)}")
            return "\n".join(lines)

        return f"{self.name}{label_str} {self.value}"


# Default histogram buckets (latency in seconds)
DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]


class PBFTMetrics:
    """Metrics collector for PBFT consensus.

    Example:
        >>> metrics = PBFTMetrics()
        >>>
        >>> # Track consensus latency
        >>> with metrics.consensus_latency("update_state"):
        ...     result = await node.submit_request("update_state", data)
        >>>
        >>> # Export metrics
        >>> print(metrics.export_prometheus())
    """

    def __init__(self) -> None:
        self._metrics: dict[str, Metric] = {}
        self._latency_samples: deque = deque(maxlen=1000)
        self._start_time = time.time()

        # Initialize standard metrics
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize standard PBFT metrics."""
        # Consensus latency histogram
        self._metrics["kagami_pbft_consensus_latency_seconds"] = Metric(
            name="kagami_pbft_consensus_latency_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="Time to reach consensus in seconds",
            buckets=[HistogramBucket(le=b) for b in DEFAULT_BUCKETS],
        )

        # Message counters by type
        for msg_type in ["pre_prepare", "prepare", "commit", "view_change", "checkpoint"]:
            self._metrics[f"kagami_pbft_messages_sent_{msg_type}"] = Metric(
                name="kagami_pbft_messages_sent_total",
                metric_type=MetricType.COUNTER,
                help_text="Total PBFT messages sent",
                labels={"type": msg_type},
            )
            self._metrics[f"kagami_pbft_messages_received_{msg_type}"] = Metric(
                name="kagami_pbft_messages_received_total",
                metric_type=MetricType.COUNTER,
                help_text="Total PBFT messages received",
                labels={"type": msg_type},
            )

        # View change counter
        self._metrics["kagami_pbft_view_changes"] = Metric(
            name="kagami_pbft_view_changes_total",
            metric_type=MetricType.COUNTER,
            help_text="Total view changes",
        )

        # Byzantine detection counter
        self._metrics["kagami_pbft_byzantine_detections"] = Metric(
            name="kagami_pbft_byzantine_detections_total",
            metric_type=MetricType.COUNTER,
            help_text="Detected Byzantine behavior",
        )

        # Gauges for current state
        self._metrics["kagami_pbft_current_view"] = Metric(
            name="kagami_pbft_current_view",
            metric_type=MetricType.GAUGE,
            help_text="Current PBFT view number",
        )

        self._metrics["kagami_pbft_current_sequence"] = Metric(
            name="kagami_pbft_current_sequence",
            metric_type=MetricType.GAUGE,
            help_text="Current PBFT sequence number",
        )

        self._metrics["kagami_pbft_pending_requests"] = Metric(
            name="kagami_pbft_pending_requests",
            metric_type=MetricType.GAUGE,
            help_text="Number of pending consensus requests",
        )

        self._metrics["kagami_pbft_is_primary"] = Metric(
            name="kagami_pbft_is_primary",
            metric_type=MetricType.GAUGE,
            help_text="Whether this node is the current primary (1=yes, 0=no)",
        )

    # =========================================================================
    # Recording Methods
    # =========================================================================

    def record_consensus_latency(
        self,
        latency_seconds: float,
        operation: str = "",
    ) -> None:
        """Record consensus latency.

        Args:
            latency_seconds: Time to reach consensus.
            operation: Operation type (optional).
        """
        metric = self._metrics["kagami_pbft_consensus_latency_seconds"]
        metric.observe(latency_seconds)
        metric.value += latency_seconds  # For sum

        self._latency_samples.append(latency_seconds)

    def record_message_sent(self, msg_type: str) -> None:
        """Record outgoing PBFT message.

        Args:
            msg_type: Message type (pre_prepare, prepare, commit, etc.)
        """
        key = f"kagami_pbft_messages_sent_{msg_type}"
        if key in self._metrics:
            self._metrics[key].inc()

    def record_message_received(self, msg_type: str) -> None:
        """Record incoming PBFT message.

        Args:
            msg_type: Message type.
        """
        key = f"kagami_pbft_messages_received_{msg_type}"
        if key in self._metrics:
            self._metrics[key].inc()

    def record_view_change(self, reason: str = "") -> None:
        """Record view change event.

        Args:
            reason: Reason for view change.
        """
        self._metrics["kagami_pbft_view_changes"].inc()
        logger.info(f"📊 View change recorded: {reason}")

    def record_byzantine_detection(self, detection_type: str, node_id: str) -> None:
        """Record Byzantine behavior detection.

        Args:
            detection_type: Type of Byzantine behavior detected.
            node_id: ID of suspected Byzantine node.
        """
        self._metrics["kagami_pbft_byzantine_detections"].inc()
        logger.warning(f"⚠️ Byzantine detection: {detection_type} from {node_id}")

    def update_state(
        self,
        view: int,
        sequence: int,
        pending: int,
        is_primary: bool,
    ) -> None:
        """Update current state gauges.

        Args:
            view: Current view number.
            sequence: Current sequence number.
            pending: Number of pending requests.
            is_primary: Whether this node is primary.
        """
        self._metrics["kagami_pbft_current_view"].set(view)
        self._metrics["kagami_pbft_current_sequence"].set(sequence)
        self._metrics["kagami_pbft_pending_requests"].set(pending)
        self._metrics["kagami_pbft_is_primary"].set(1.0 if is_primary else 0.0)

    # =========================================================================
    # Context Manager for Latency
    # =========================================================================

    class LatencyTimer:
        """Context manager for timing consensus operations."""

        def __init__(self, metrics: PBFTMetrics, operation: str = "") -> None:
            self._metrics = metrics
            self._operation = operation
            self._start: float = 0.0

        def __enter__(self) -> PBFTMetrics.LatencyTimer:
            self._start = time.time()
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            latency = time.time() - self._start
            self._metrics.record_consensus_latency(latency, self._operation)

    def consensus_latency(self, operation: str = "") -> LatencyTimer:
        """Create a timer context for consensus latency.

        Args:
            operation: Operation name.

        Returns:
            LatencyTimer context manager.

        Example:
            >>> with metrics.consensus_latency("update"):
            ...     await node.submit_request(...)
        """
        return self.LatencyTimer(self, operation)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_latency_stats(self) -> dict[str, float]:
        """Get latency statistics.

        Returns:
            Dict with p50, p90, p99, and mean latencies.
        """
        if not self._latency_samples:
            return {"p50": 0, "p90": 0, "p99": 0, "mean": 0}

        sorted_samples = sorted(self._latency_samples)
        n = len(sorted_samples)

        return {
            "p50": sorted_samples[int(n * 0.50)],
            "p90": sorted_samples[int(n * 0.90)],
            "p99": sorted_samples[int(n * 0.99)] if n > 100 else sorted_samples[-1],
            "mean": sum(sorted_samples) / n,
            "count": n,
        }

    def get_throughput(self) -> float:
        """Get current throughput (operations per second).

        Returns:
            Operations per second.
        """
        elapsed = time.time() - self._start_time
        if elapsed <= 0:
            return 0.0

        total_ops = len(self._latency_samples)
        return total_ops / elapsed

    # =========================================================================
    # Export
    # =========================================================================

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string.
        """
        lines = []

        for _name, metric in self._metrics.items():
            lines.append(f"# HELP {metric.name} {metric.help_text}")
            lines.append(f"# TYPE {metric.name} {metric.metric_type.name.lower()}")
            lines.append(metric.to_prometheus())
            lines.append("")

        return "\n".join(lines)

    def export_json(self) -> dict[str, Any]:
        """Export metrics as JSON.

        Returns:
            Dict with all metrics.
        """
        return {
            "uptime_seconds": time.time() - self._start_time,
            "latency": self.get_latency_stats(),
            "throughput_ops": self.get_throughput(),
            "metrics": {
                name: {
                    "value": m.value,
                    "labels": m.labels,
                }
                for name, m in self._metrics.items()
            },
        }


# =============================================================================
# Adaptive Timeout
# =============================================================================


class AdaptiveTimeout:
    """Adaptive timeout based on observed latencies.

    Adjusts timeout based on p99 latency to handle network variability
    while maintaining responsiveness.

    Example:
        >>> timeout = AdaptiveTimeout(base_timeout=30.0)
        >>>
        >>> # Record latencies
        >>> timeout.record(0.5)
        >>> timeout.record(0.8)
        >>>
        >>> # Get current timeout
        >>> current = timeout.get_timeout()
    """

    def __init__(
        self,
        base_timeout: float = 30.0,
        multiplier: float = 2.0,
        min_samples: int = 10,
        max_timeout: float = 300.0,
    ) -> None:
        """Initialize adaptive timeout.

        Args:
            base_timeout: Base timeout value.
            multiplier: Multiply p99 by this for timeout.
            min_samples: Minimum samples before adapting.
            max_timeout: Maximum timeout value.
        """
        self.base_timeout = base_timeout
        self.multiplier = multiplier
        self.min_samples = min_samples
        self.max_timeout = max_timeout

        self._latencies: deque[float] = deque(maxlen=100)

    def record(self, latency: float) -> None:
        """Record observed latency.

        Args:
            latency: Observed latency in seconds.
        """
        self._latencies.append(latency)

    def get_timeout(self) -> float:
        """Get current adaptive timeout.

        Returns:
            Timeout value in seconds.
        """
        if len(self._latencies) < self.min_samples:
            return self.base_timeout

        sorted_latencies = sorted(self._latencies)
        p99_idx = int(len(sorted_latencies) * 0.99)
        p99 = sorted_latencies[p99_idx]

        adaptive = p99 * self.multiplier
        return min(max(self.base_timeout, adaptive), self.max_timeout)

    def reset(self) -> None:
        """Reset collected latencies."""
        self._latencies.clear()


# =============================================================================
# Factory Functions
# =============================================================================


_pbft_metrics: PBFTMetrics | None = None


def get_pbft_metrics() -> PBFTMetrics:
    """Get singleton PBFT metrics collector.

    Returns:
        PBFTMetrics instance.
    """
    global _pbft_metrics

    if _pbft_metrics is None:
        _pbft_metrics = PBFTMetrics()

    return _pbft_metrics


_adaptive_timeout: AdaptiveTimeout | None = None


def get_adaptive_timeout() -> AdaptiveTimeout:
    """Get singleton adaptive timeout.

    Returns:
        AdaptiveTimeout instance.
    """
    global _adaptive_timeout

    if _adaptive_timeout is None:
        _adaptive_timeout = AdaptiveTimeout()

    return _adaptive_timeout


__all__ = [
    "AdaptiveTimeout",
    "Metric",
    "MetricType",
    "PBFTMetrics",
    "get_adaptive_timeout",
    "get_pbft_metrics",
]
