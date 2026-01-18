"""Consensus Monitoring and Metrics Infrastructure.

Comprehensive Prometheus metrics for Kagami Byzantine consensus protocol,
covering convergence dynamics, CBF safety, Fano line composition, and
per-colony performance tracking.

ARCHITECTURE:
=============
┌──────────────────────────────────────────────────────────────────┐
│              CONSENSUS METRICS INFRASTRUCTURE                     │
│                                                                   │
│  Tracks:                                                          │
│  - Consensus outcomes (converged, failed, timeout, fallback)     │
│  - Phase-specific latency (proposal, verification, quorum, CBF)  │
│  - Participant counts and per-colony activity                    │
│  - CBF constraint violations and safety margins                  │
│  - Fano line agreement patterns                                  │
│  - Health state transitions                                      │
│                                                                   │
│  Integration:                                                     │
│  - KagamiConsensus (collect_proposals, byzantine_consensus)      │
│  - CoordinatorHealthMonitor (assess_health, trigger_fallback)    │
│  - Prometheus exporter (/metrics endpoint)                       │
└──────────────────────────────────────────────────────────────────┘

PROMETHEUS ALERTING:
====================
Example alerting rules:

```yaml
groups:
  - name: consensus_alerts
    interval: 30s
    rules:
      - alert: ConsensusFailureRate
        expr: rate(kagami_consensus_rounds_total{status="failed"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High consensus failure rate
          description: "{{ $value | humanizePercentage }} of consensus rounds failing"

      - alert: CBFViolation
        expr: kagami_consensus_cbf_violations_total > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: CBF safety constraint violated
          description: "Colony {{ $labels.colony_id }} violated CBF (h(x) < 0)"

      - alert: ConsensusLatencyHigh
        expr: histogram_quantile(0.95, rate(kagami_consensus_latency_seconds_bucket[5m])) > 2.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Consensus latency P95 > 2s
          description: "Phase {{ $labels.phase }} taking {{ $value }}s (P95)"

      - alert: ConsensusHealthDegraded
        expr: kagami_consensus_health_state{state="degraded"} == 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: Consensus health degraded
          description: "Coordinator health degraded for >10m"

      - alert: ConsensusHealthCritical
        expr: kagami_consensus_health_state{state="critical"} == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Consensus health critical
          description: "Coordinator entering emergency mode"

      - alert: LowCBFMargin
        expr: kagami_consensus_cbf_margin_min < 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Low CBF safety margin
          description: "Minimum CBF margin: {{ $value }}"
```

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kagami_observability.metrics.core import Counter, Gauge, Histogram

if TYPE_CHECKING:
    from kagami.core.coordination.health_monitor import CoordinatorHealth
    from kagami.core.coordination.kagami_consensus import ConsensusState

logger = logging.getLogger(__name__)


# =============================================================================
# PROMETHEUS METRICS DEFINITIONS
# =============================================================================


# Consensus outcomes
consensus_rounds_total = Counter(
    "kagami_consensus_rounds_total",
    "Total consensus rounds by status",
    ["status"],  # converged, failed, timeout, fallback
)

# Consensus latency by phase
consensus_latency_seconds = Histogram(
    "kagami_consensus_latency_seconds",
    "Consensus phase latency distribution",
    ["phase"],  # proposal, verification, quorum, cbf_check, total
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# Active participants
consensus_participants_count = Gauge(
    "kagami_consensus_participants",
    "Number of participating colonies in consensus round",
    [],
)

# CBF violations (CRITICAL metric)
consensus_cbf_violations_total = Counter(
    "kagami_consensus_cbf_violations_total",
    "CBF constraint violations during consensus",
    ["colony_id"],
)

# Minimum CBF margin across all colonies
consensus_cbf_margin_min = Gauge(
    "kagami_consensus_cbf_margin_min",
    "Minimum CBF safety margin (h(x)) across all colonies",
    [],
)

# Per-colony proposal counts
colony_proposal_total = Counter(
    "kagami_colony_proposal_total",
    "Total proposals submitted by colony",
    ["colony_id"],
)

# Per-colony verification success rate
colony_verification_success_rate = Gauge(
    "kagami_colony_verification_success_rate",
    "Colony verification success rate (0-1)",
    ["colony_id"],
)

# Fano line consensus patterns
fano_line_consensus_total = Counter(
    "kagami_fano_line_consensus_total",
    "Fano line composition agreement counts",
    ["line", "result"],  # line="0-1-2", result="agree|disagree"
)

# Agreement matrix statistics
consensus_agreement_mean = Gauge(
    "kagami_consensus_agreement_mean",
    "Mean pairwise agreement across all colonies",
    [],
)

consensus_agreement_min = Gauge(
    "kagami_consensus_agreement_min",
    "Minimum pairwise agreement",
    [],
)

consensus_agreement_max = Gauge(
    "kagami_consensus_agreement_max",
    "Maximum pairwise agreement",
    [],
)

# Consensus iterations
consensus_iterations_total = Histogram(
    "kagami_consensus_iterations_total",
    "Number of iterations to reach consensus",
    [],
    buckets=[1, 2, 3, 5, 7, 10, 15],
)

# Health state tracking
consensus_health_state = Gauge(
    "kagami_consensus_health_state",
    "Coordinator health state (1=active, 0=inactive)",
    ["state"],  # healthy, degraded, critical, failed
)

# Fallback mode activations
consensus_fallback_activations_total = Counter(
    "kagami_consensus_fallback_activations_total",
    "Fallback mode activation count",
    ["mode"],  # conservative_routing, emergency_mode, human_intervention
)

# Proposal confidence distribution
proposal_confidence_distribution = Histogram(
    "kagami_proposal_confidence_distribution",
    "Colony proposal confidence distribution",
    ["colony_id"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Task complexity (estimated from proposal diversity)
consensus_task_complexity = Gauge(
    "kagami_consensus_task_complexity",
    "Estimated task complexity (0-1) from proposal diversity",
    [],
)


# =============================================================================
# METRICS COLLECTOR
# =============================================================================


@dataclass
class ConsensusRoundMetrics:
    """Metrics collected from a single consensus round."""

    status: str  # converged, failed, timeout, fallback
    latency_by_phase: dict[str, float]  # phase -> seconds
    participants: int  # Number of active colonies
    cbf_values: dict[int, float]  # colony_id -> h(x)
    agreement_stats: dict[str, float]  # mean, min, max
    iterations: int
    task_complexity: float  # 0-1
    timestamp: float = field(default_factory=time.time)


class ConsensusMetricsCollector:
    """Collects and exports consensus metrics to Prometheus.

    Integrates with KagamiConsensus and CoordinatorHealthMonitor to track
    consensus dynamics, safety constraints, and health state transitions.
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.round_count = 0
        self.last_health_state: CoordinatorHealth | None = None

        # Initialize all health states to 0
        for state in ["healthy", "degraded", "critical", "failed"]:
            consensus_health_state.labels(state=state).set(0)

        logger.info("ConsensusMetricsCollector initialized")

    # =========================================================================
    # CONSENSUS ROUND RECORDING
    # =========================================================================

    def record_consensus_round(
        self,
        status: str,
        latency_by_phase: dict[str, float],
        participants: int,
        cbf_values: dict[int, float],
        agreement_stats: dict[str, float],
        iterations: int,
        task_complexity: float = 0.5,
    ) -> None:
        """Record metrics from a consensus round.

        Args:
            status: Consensus outcome (converged, failed, timeout, fallback)
            latency_by_phase: Dict mapping phase name to latency (seconds)
            participants: Number of participating colonies
            cbf_values: Dict mapping colony_id to CBF margin h(x)
            agreement_stats: Dict with mean, min, max agreement
            iterations: Number of iterations to convergence
            task_complexity: Estimated complexity [0, 1]
        """
        try:
            self.round_count += 1

            # Consensus outcome
            consensus_rounds_total.labels(status=status).inc()

            # Phase latencies
            for phase, latency in latency_by_phase.items():
                consensus_latency_seconds.labels(phase=phase).observe(latency)

            # Participants
            consensus_participants_count.set(participants)

            # CBF metrics
            self._record_cbf_metrics(cbf_values)

            # Agreement statistics
            self._record_agreement_stats(agreement_stats)

            # Iterations
            consensus_iterations_total.observe(iterations)

            # Task complexity
            consensus_task_complexity.set(task_complexity)

            logger.debug(
                f"Recorded consensus round {self.round_count}: "
                f"status={status}, participants={participants}, "
                f"iterations={iterations}"
            )

        except Exception as e:
            logger.error(f"Failed to record consensus round metrics: {e}")

    def _record_cbf_metrics(self, cbf_values: dict[int, float]) -> None:
        """Record CBF constraint metrics.

        Args:
            cbf_values: Dict mapping colony_id to h(x) value
        """
        if not cbf_values:
            return

        # Minimum CBF margin
        min_margin = min(cbf_values.values())
        consensus_cbf_margin_min.set(min_margin)

        # Track violations
        for colony_id, margin in cbf_values.items():
            if margin < 0:
                consensus_cbf_violations_total.labels(colony_id=str(colony_id)).inc()
                logger.warning(f"CBF violation: Colony {colony_id} h(x)={margin:.3f}")

    def _record_agreement_stats(self, agreement_stats: dict[str, float]) -> None:
        """Record agreement matrix statistics.

        Args:
            agreement_stats: Dict with mean, min, max agreement
        """
        if "mean" in agreement_stats:
            consensus_agreement_mean.set(agreement_stats["mean"])

        if "min" in agreement_stats:
            consensus_agreement_min.set(agreement_stats["min"])

        if "max" in agreement_stats:
            consensus_agreement_max.set(agreement_stats["max"])

    # =========================================================================
    # PER-COLONY METRICS
    # =========================================================================

    def record_colony_proposal(
        self,
        colony_id: int,
        confidence: float,
    ) -> None:
        """Record a colony proposal submission.

        Args:
            colony_id: Colony identifier (0-6)
            confidence: Proposal confidence [0, 1]
        """
        try:
            colony_proposal_total.labels(colony_id=str(colony_id)).inc()

            proposal_confidence_distribution.labels(colony_id=str(colony_id)).observe(confidence)

        except Exception as e:
            logger.debug(f"Failed to record colony proposal: {e}")

    def update_colony_verification_rate(
        self,
        colony_id: int,
        success_rate: float,
    ) -> None:
        """Update colony verification success rate.

        Args:
            colony_id: Colony identifier (0-6)
            success_rate: Verification success rate [0, 1]
        """
        try:
            colony_verification_success_rate.labels(colony_id=str(colony_id)).set(success_rate)

        except Exception as e:
            logger.debug(f"Failed to update verification rate: {e}")

    # =========================================================================
    # FANO LINE METRICS
    # =========================================================================

    def record_fano_line_consensus(
        self,
        line: str,
        result: str,
    ) -> None:
        """Record Fano line consensus check result.

        Args:
            line: Fano line identifier (e.g., "0-1-2")
            result: Agreement result ("agree" or "disagree")
        """
        try:
            fano_line_consensus_total.labels(line=line, result=result).inc()

        except Exception as e:
            logger.debug(f"Failed to record Fano line consensus: {e}")

    # =========================================================================
    # HEALTH STATE TRACKING
    # =========================================================================

    def update_health_state(self, health: CoordinatorHealth) -> None:
        """Update coordinator health state gauge.

        Sets the current health state to 1, all others to 0.

        Args:
            health: Current CoordinatorHealth enum
        """
        try:
            # State transition detection
            if self.last_health_state != health:
                logger.info(
                    f"Health state transition: "
                    f"{self.last_health_state.value if self.last_health_state else 'unknown'} "
                    f"-> {health.value}"
                )
                self.last_health_state = health

            # Set all states to 0, then activate current state
            for state in ["healthy", "degraded", "critical", "failed"]:
                consensus_health_state.labels(state=state).set(
                    1.0 if state == health.value else 0.0
                )

        except Exception as e:
            logger.error(f"Failed to update health state: {e}")

    def record_fallback_activation(self, mode: str) -> None:
        """Record fallback mode activation.

        Args:
            mode: Fallback mode (conservative_routing, emergency_mode, etc.)
        """
        try:
            consensus_fallback_activations_total.labels(mode=mode).inc()
            logger.warning(f"Fallback mode activated: {mode}")

        except Exception as e:
            logger.error(f"Failed to record fallback activation: {e}")

    # =========================================================================
    # HIGH-LEVEL INTERFACE
    # =========================================================================

    def record_consensus_state(
        self,
        consensus_state: ConsensusState,
        latency_by_phase: dict[str, float],
        health: CoordinatorHealth | None = None,
    ) -> None:
        """High-level interface: record complete consensus state.

        Args:
            consensus_state: ConsensusState from KagamiConsensus
            latency_by_phase: Phase latency measurements
            health: Optional CoordinatorHealth state
        """
        import numpy as np

        try:
            # Extract metrics from consensus state
            status = "converged" if consensus_state.converged else "failed"

            # Participant count
            participants = len(consensus_state.proposals)

            # CBF values from proposals
            cbf_values = {p.proposer.value: p.cbf_margin for p in consensus_state.proposals}

            # Agreement statistics
            agreement_matrix = consensus_state.agreement_matrix
            agreement_stats = {
                "mean": float(np.mean(agreement_matrix)),
                "min": float(np.min(agreement_matrix)),
                "max": float(np.max(agreement_matrix)),
            }

            # Estimate task complexity from proposal diversity
            # Higher disagreement = higher complexity
            task_complexity = 1.0 - agreement_stats["mean"]

            # Record consensus round
            self.record_consensus_round(
                status=status,
                latency_by_phase=latency_by_phase,
                participants=participants,
                cbf_values=cbf_values,
                agreement_stats=agreement_stats,
                iterations=consensus_state.iterations,
                task_complexity=task_complexity,
            )

            # Record per-colony proposals
            for proposal in consensus_state.proposals:
                self.record_colony_proposal(
                    colony_id=proposal.proposer.value,
                    confidence=proposal.confidence,
                )

            # Update health state if provided
            if health is not None:
                self.update_health_state(health)

        except Exception as e:
            logger.error(f"Failed to record consensus state: {e}")


# =============================================================================
# HEALTH CHECK
# =============================================================================


async def check_consensus_health() -> dict[str, Any]:
    """Health check for consensus system.

    Queries current metric values to assess system health.

    Returns:
        Dict with health check results
    """
    try:
        from kagami_observability.metrics.core import REGISTRY

        # Extract metric values from registry
        metrics: dict[str, Any] = {}

        # Recent failures (would need proper query, this is placeholder)
        # In production, use Prometheus query API or track internally
        metrics["recent_failures"] = 0  # Placeholder

        # Current CBF margin
        # Access internal _value if available (Prometheus client internals)
        try:
            metrics["min_cbf_margin"] = consensus_cbf_margin_min._value.get()
        except Exception:
            metrics["min_cbf_margin"] = None

        # Current health state (find active state)
        health_state = "unknown"
        for state in ["healthy", "degraded", "critical", "failed"]:
            try:
                value = consensus_health_state.labels(state=state)._value.get()
                if value == 1.0:
                    health_state = state
                    break
            except Exception:
                continue

        metrics["health_state"] = health_state

        # Participant count
        try:
            metrics["participants"] = consensus_participants_count._value.get()
        except Exception:
            metrics["participants"] = None

        return {
            "status": "healthy" if health_state in ["healthy", "degraded"] else "unhealthy",
            "metrics": metrics,
            "registry_size": len(REGISTRY._names_to_collectors),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================


_metrics_collector: ConsensusMetricsCollector | None = None


def get_metrics_collector() -> ConsensusMetricsCollector:
    """Get or create singleton metrics collector.

    Returns:
        ConsensusMetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = ConsensusMetricsCollector()
    return _metrics_collector


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "ConsensusMetricsCollector",
    "ConsensusRoundMetrics",
    "check_consensus_health",
    "colony_proposal_total",
    "colony_verification_success_rate",
    "consensus_agreement_max",
    "consensus_agreement_mean",
    "consensus_agreement_min",
    "consensus_cbf_margin_min",
    "consensus_cbf_violations_total",
    "consensus_fallback_activations_total",
    "consensus_health_state",
    "consensus_iterations_total",
    "consensus_latency_seconds",
    "consensus_participants_count",
    # Metrics (for direct access if needed)
    "consensus_rounds_total",
    "consensus_task_complexity",
    "fano_line_consensus_total",
    "get_metrics_collector",
    "proposal_confidence_distribution",
]
