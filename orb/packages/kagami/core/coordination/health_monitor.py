"""Coordinator Health Monitor - Kagami Self-Verification.

Monitors the health of Kagami's Byzantine consensus and triggers
hierarchical fallback when coordination fails.

ARCHITECTURE:
=============
┌──────────────────────────────────────────────────────────────────┐
│                  COORDINATOR HEALTH MONITOR                       │
│                                                                   │
│  Monitors:                                                        │
│  - Consensus convergence time                                    │
│  - Mean agreement level                                          │
│  - CBF safety margin                                             │
│  - Inverter approval                                             │
│  - Failed consensus count                                        │
│                                                                   │
│  Health States:                                                  │
│  HEALTHY    → Normal operation (agreement ≥ 0.75, CBF > 0)      │
│  DEGRADED   → Conservative mode (slow convergence or low agree) │
│  CRITICAL   → Emergency mode (CBF violations, high failures)    │
│  FAILED     → Human intervention (Inverter rejects consensus)   │
└──────────────────────────────────────────────────────────────────┘

HIERARCHICAL FALLBACK:
======================
HEALTHY    → Full consensus coordination
DEGRADED   → Conservative routing (single colony mode)
CRITICAL   → Emergency mode (only safety-critical colonies)
FAILED     → Human intervention required, log alert

Created: December 14, 2025
"""

from __future__ import annotations

# Standard library imports
import logging
import time
from dataclasses import (
    dataclass,
    field,
)
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
)

# Third-party imports
import numpy as np

# Local imports
from kagami_observability.alerting import (
    AlertSeverity,
    get_alert_router,
)

if TYPE_CHECKING:
    from kagami.core.coordination.inverter import InverterAgent, MetaCoordinationAnalysis
    from kagami.core.coordination.kagami_consensus import ConsensusState, KagamiConsensus


logger = logging.getLogger(__name__)

# =============================================================================
# HEALTH STATES
# =============================================================================


class CoordinatorHealth(Enum):
    """Health states for Kagami consensus."""

    HEALTHY = "healthy"  # Consensus converging normally
    DEGRADED = "degraded"  # Slow convergence, some disagreement
    CRITICAL = "critical"  # Consensus failing, CBF violations
    FAILED = "failed"  # No consensus, emergency fallback


@dataclass
class HealthMetrics:
    """Metrics for coordinator health assessment."""

    consensus_convergence_time: float  # seconds
    mean_agreement: float  # [0, 1]
    cbf_margin: float  # h(x)
    inverter_approval: bool  # Did Inverter verify?
    failed_consensus_count: int  # Recent failures
    iterations_to_converge: int  # Consensus iterations
    timestamp: float = field(default_factory=time.time)


@dataclass
class FallbackConfig:
    """Configuration for failure handling (fail-fast, not graceful degradation)."""

    alert_webhook: str | None = None  # Optional webhook for alerts


# =============================================================================
# HEALTH MONITOR
# =============================================================================


class CoordinatorHealthMonitor:
    """Monitors Kagami consensus health and triggers fallback.

    Tracks consensus quality over time and detects degradation patterns.
    """

    def __init__(
        self,
        convergence_threshold: float = 5.0,  # seconds
        agreement_threshold: float = 0.75,  # Byzantine: 5/7 colonies
        cbf_threshold: float = 0.0,
        failure_window: int = 10,  # Track last N attempts
        failure_threshold: int = 3,  # Max failures in window
        fallback_config: FallbackConfig | None = None,
    ):
        """Initialize health monitor.

        Args:
            convergence_threshold: Max acceptable convergence time
            agreement_threshold: Min mean agreement for healthy state
            cbf_threshold: Min CBF margin h(x)
            failure_window: Number of recent attempts to track
            failure_threshold: Max failures before CRITICAL state
            fallback_config: Fallback behavior configuration
        """
        self.convergence_threshold = convergence_threshold
        self.agreement_threshold = agreement_threshold
        self.cbf_threshold = cbf_threshold
        self.failure_window = failure_window
        self.failure_threshold = failure_threshold
        self.fallback_config = fallback_config or FallbackConfig()

        self.metrics_history: list[HealthMetrics] = []
        self.current_health = CoordinatorHealth.HEALTHY
        self.last_assessment_time = time.time()

    # =========================================================================
    # HEALTH ASSESSMENT
    # =========================================================================

    def assess_health(
        self,
        consensus: ConsensusState,
        inverter_analysis: MetaCoordinationAnalysis,
    ) -> CoordinatorHealth:
        """Assess Kagami consensus health.

        Args:
            consensus: Latest consensus state
            inverter_analysis: Inverter's verification analysis

        Returns:
            CoordinatorHealth enum
        """
        # Measure convergence time
        current_time = time.time()
        convergence_time = current_time - self.last_assessment_time
        self.last_assessment_time = current_time

        # Build metrics
        metrics = HealthMetrics(
            consensus_convergence_time=convergence_time,
            mean_agreement=float(np.mean(consensus.agreement_matrix)),
            cbf_margin=consensus.cbf_constraint,
            inverter_approval=inverter_analysis.consensus_validity,
            failed_consensus_count=self._count_recent_failures(),
            iterations_to_converge=consensus.iterations,
        )

        self.metrics_history.append(metrics)

        # Keep only recent history
        if len(self.metrics_history) > self.failure_window * 2:
            self.metrics_history = self.metrics_history[-self.failure_window * 2 :]

        # Decision tree for health state
        health = self._compute_health_state(metrics, inverter_analysis)

        if health != self.current_health:
            logger.warning(
                f"Coordinator health changed: {self.current_health.value} → {health.value}"
            )
            self.current_health = health

        return health

    def _compute_health_state(
        self,
        metrics: HealthMetrics,
        inverter_analysis: MetaCoordinationAnalysis,
    ) -> CoordinatorHealth:
        """Compute health state from metrics.

        Args:
            metrics: Current metrics
            inverter_analysis: Inverter's verification

        Returns:
            CoordinatorHealth enum
        """
        # FAILED: Inverter rejected consensus
        if not metrics.inverter_approval:
            logger.error("Coordinator FAILED: Inverter rejected consensus")
            self._send_alert(
                AlertSeverity.CRITICAL,
                "Coordinator FAILED: Inverter Rejected Consensus",
                f"Inverter rejected consensus. Confidence: {inverter_analysis.confidence:.2f}",
                {"inverter_confidence": inverter_analysis.confidence},
            )
            return CoordinatorHealth.FAILED

        # CRITICAL: CBF violation
        if metrics.cbf_margin < self.cbf_threshold:
            logger.error(f"Coordinator CRITICAL: CBF violation (h={metrics.cbf_margin:.3f})")
            self._send_alert(
                AlertSeverity.CRITICAL,
                "Coordinator CRITICAL: CBF Violation",
                f"Safety invariant violated: h(x) = {metrics.cbf_margin:.3f} < {self.cbf_threshold}",
                {"cbf_margin": metrics.cbf_margin, "threshold": self.cbf_threshold},
            )
            return CoordinatorHealth.CRITICAL

        # CRITICAL: Too many recent failures
        if metrics.failed_consensus_count >= self.failure_threshold:
            logger.error(
                f"Coordinator CRITICAL: {metrics.failed_consensus_count} failures "
                f"in last {self.failure_window} attempts"
            )
            self._send_alert(
                AlertSeverity.CRITICAL,
                "Coordinator CRITICAL: High Failure Rate",
                f"{metrics.failed_consensus_count} failures in last {self.failure_window} attempts",
                {
                    "failures": metrics.failed_consensus_count,
                    "window": self.failure_window,
                    "threshold": self.failure_threshold,
                },
            )
            return CoordinatorHealth.CRITICAL

        # DEGRADED: Low agreement
        if metrics.mean_agreement < self.agreement_threshold:
            logger.warning(f"Coordinator DEGRADED: Low agreement ({metrics.mean_agreement:.2f})")
            return CoordinatorHealth.DEGRADED

        # DEGRADED: Slow convergence
        if metrics.consensus_convergence_time > self.convergence_threshold:
            logger.warning(
                f"Coordinator DEGRADED: Slow convergence ({metrics.consensus_convergence_time:.1f}s)"
            )
            return CoordinatorHealth.DEGRADED

        # DEGRADED: High iteration count
        if metrics.iterations_to_converge > 7:
            logger.warning(
                f"Coordinator DEGRADED: High iterations ({metrics.iterations_to_converge})"
            )
            return CoordinatorHealth.DEGRADED

        # HEALTHY
        return CoordinatorHealth.HEALTHY

    def _count_recent_failures(self) -> int:
        """Count consensus failures in recent history.

        Returns:
            Number of failures in last N attempts
        """
        recent = self.metrics_history[-self.failure_window :]
        return sum(1 for m in recent if not m.inverter_approval)

    # =========================================================================
    # FALLBACK ACTIONS
    # =========================================================================

    def trigger_fallback(
        self,
        health: CoordinatorHealth,
    ) -> dict[str, str]:
        """Trigger hierarchical fallback based on health state.

        Args:
            health: Current health state

        Returns:
            Fallback action dict[str, Any] with mode and instructions
        """
        if health == CoordinatorHealth.HEALTHY:
            return {
                "mode": "normal_operation",
                "action": "continue_consensus",
                "colonies_active": "all_colonies",
            }

        if health == CoordinatorHealth.DEGRADED:
            logger.error("Coordination DEGRADED - alerting and failing fast")
            self._send_alert(
                AlertSeverity.WARNING,
                "Coordination Degraded",
                "Consensus convergence issues detected. Investigate immediately.",
            )
            raise RuntimeError("Coordination degraded - consensus failing to converge")

        if health == CoordinatorHealth.CRITICAL:
            logger.error("Coordination CRITICAL - CBF violations detected, failing fast")
            self._send_alert(
                AlertSeverity.CRITICAL,
                "Coordination Critical",
                "CBF violations or high failure rate. System safety compromised.",
            )
            raise RuntimeError("Coordination critical - CBF safety compromised")

        if health == CoordinatorHealth.FAILED:
            logger.error("Coordination FAILED - human intervention required")
            self._send_alert(
                AlertSeverity.CRITICAL,
                "Coordination Failed",
                "Consensus completely failed. Human intervention required immediately.",
            )
            raise RuntimeError("Coordination failed - consensus unreachable")

        return {"mode": "unknown_state", "action": "log_error", "colonies_active": "none"}  # type: ignore[unreachable]

    def _send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        metadata: dict[str, any] | None = None,  # type: ignore[valid-type]
    ) -> None:
        """Send alert via unified alerting system.

        Args:
            severity: Alert severity (CRITICAL/WARNING/INFO)
            title: Alert title
            description: Alert description
            metadata: Optional metadata dict[str, Any]
        """
        try:
            router = get_alert_router()
            router.send_alert(
                severity=severity,
                title=title,
                description=description,
                source="coordinator_health_monitor",
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}", exc_info=True)

    # =========================================================================
    # HEALTH REPORT
    # =========================================================================

    def get_health_report(self) -> dict[str, any]:  # type: ignore[valid-type]
        """Generate comprehensive health report.

        Returns:
            Dict with health metrics and status
        """
        if not self.metrics_history:
            return {
                "status": "no_data",
                "current_health": self.current_health.value,
                "metrics_count": 0,
            }

        recent_metrics = self.metrics_history[-self.failure_window :]

        return {
            "status": "ok",
            "current_health": self.current_health.value,
            "metrics_count": len(self.metrics_history),
            "recent_window_size": len(recent_metrics),
            "stats": {
                "mean_convergence_time": float(
                    np.mean([m.consensus_convergence_time for m in recent_metrics])
                ),
                "mean_agreement": float(np.mean([m.mean_agreement for m in recent_metrics])),
                "mean_cbf_margin": float(np.mean([m.cbf_margin for m in recent_metrics])),
                "mean_iterations": float(
                    np.mean([m.iterations_to_converge for m in recent_metrics])
                ),
                "failure_rate": sum(1 for m in recent_metrics if not m.inverter_approval)
                / len(recent_metrics),
            },
            "thresholds": {
                "convergence_threshold": self.convergence_threshold,
                "agreement_threshold": self.agreement_threshold,
                "cbf_threshold": self.cbf_threshold,
                "failure_threshold": self.failure_threshold,
            },
        }


# =============================================================================
# INTEGRATED MONITORING
# =============================================================================


class KagamiHealthMonitor:
    """Integrated monitor combining consensus, inverter, and health tracking."""

    def __init__(
        self,
        consensus_protocol: KagamiConsensus,
        inverter: InverterAgent,
        health_monitor: CoordinatorHealthMonitor,
    ):
        """Initialize integrated monitor.

        Args:
            consensus_protocol: Kagami consensus protocol
            inverter: Inverter meta-verifier
            health_monitor: Health monitor
        """
        self.consensus = consensus_protocol
        self.inverter = inverter
        self.health = health_monitor

    async def execute_with_monitoring(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        world_model: Any | None = None,
    ) -> tuple[dict[str, str] | None, CoordinatorHealth]:
        """Execute consensus with full health monitoring.

        Args:
            task: Task to coordinate
            context: Additional context
            world_model: Optional KagamiWorldModel for RSSM predictions and learning

        Returns:
            (routing_result, health_state)
            routing_result is None if consensus failed
        """
        # Collect proposals (with optional world model predictions)
        proposals = await self.consensus.collect_proposals(task, context, world_model=world_model)

        # Run consensus
        consensus_state = await self.consensus.byzantine_consensus(proposals)

        # Inverter verification
        inverter_analysis = self.inverter.analyze_coordination(consensus_state, task)

        # Health assessment
        health_state = self.health.assess_health(consensus_state, inverter_analysis)

        # =================================================================
        # PART 2: CONSENSUS OUTCOMES → WORLD MODEL LEARNING
        # =================================================================
        # After consensus execution, emit receipt for world model
        if world_model is not None:
            await self._emit_consensus_receipt(  # type: ignore[unreachable]
                world_model=world_model,
                task=task,
                consensus_state=consensus_state,
                health_state=health_state,
                inverter_analysis=inverter_analysis,
            )

        # Decide action based on health
        if health_state == CoordinatorHealth.HEALTHY:
            # Execute consensus routing
            return consensus_state.consensus_routing, health_state  # type: ignore[return-value]

        # Fallback mode
        fallback_action = self.health.trigger_fallback(health_state)
        logger.info(f"Fallback triggered: {fallback_action}")

        if health_state == CoordinatorHealth.FAILED:
            # Cannot proceed
            return None, health_state

        # Return fallback routing (simplified for now)
        return self._generate_fallback_routing(fallback_action, proposals), health_state

    async def _emit_consensus_receipt(
        self,
        world_model: any,  # type: ignore[valid-type]
        task: str,
        consensus_state: ConsensusState,
        health_state: CoordinatorHealth,
        inverter_analysis: MetaCoordinationAnalysis,
    ) -> None:
        """Emit consensus receipt to world model for learning.

        Closes the learning loop: consensus → receipts → world model update.

        Args:
            world_model: KagamiWorldModel instance
            task: Task that was coordinated
            consensus_state: Consensus result
            health_state: Health state after consensus
            inverter_analysis: Inverter's verification
        """
        import numpy as np

        receipt = {
            "task": task,
            "consensus_routing": consensus_state.consensus_routing,
            "agreement": float(np.mean(consensus_state.agreement_matrix)),
            "cbf_margin": consensus_state.cbf_constraint,
            "converged": consensus_state.converged,
            "iterations": consensus_state.iterations,
            "health_state": health_state.value,
            "inverter_approved": inverter_analysis.consensus_validity,
            "confidence": inverter_analysis.confidence,
            "timestamp": time.time(),
        }

        # Feed to world model (if it has learning interface)
        if hasattr(world_model, "learn_from_consensus"):
            try:
                await world_model.learn_from_consensus(receipt)  # type: ignore[attr-defined]
                logger.debug("Consensus receipt emitted to world model")
            except Exception as e:
                logger.warning(f"Failed to emit consensus receipt: {e}")
        else:
            logger.debug("World model has no learn_from_consensus interface")

    def _generate_fallback_routing(
        self,
        fallback_action: dict[str, str],
        proposals: list[Any],
    ) -> dict[str, str]:
        """Generate simplified routing for fallback mode.

        Args:
            fallback_action: Fallback action dict[str, Any]
            proposals: Original proposals (for context)

        Returns:
            Simplified routing dict[str, Any]
        """
        mode = fallback_action["mode"]

        if mode == "conservative_routing":
            # Use single highest-confidence colony
            best_proposal = max(proposals, key=lambda p: p.confidence)
            return {best_proposal.proposer: "activate"}

        if mode == "emergency_mode":
            # Only Crystal (verify) + Flow (debug)
            from kagami.core.coordination.types import ColonyID

            return {
                ColonyID.CRYSTAL: "verify_safety",  # type: ignore[dict-item]
                ColonyID.FLOW: "diagnose_and_recover",  # type: ignore[dict-item]
            }

        # Default: empty routing (pause)
        return {}


# =============================================================================
# FACTORY
# =============================================================================


def create_health_monitor(
    convergence_threshold: float = 5.0,
    agreement_threshold: float = 0.75,
    cbf_threshold: float = 0.0,
    failure_threshold: int = 3,
) -> CoordinatorHealthMonitor:
    """Create coordinator health monitor.

    Args:
        convergence_threshold: Max acceptable convergence time (seconds)
        agreement_threshold: Min mean agreement
        cbf_threshold: Min CBF margin
        failure_threshold: Max failures before CRITICAL

    Returns:
        CoordinatorHealthMonitor instance
    """
    return CoordinatorHealthMonitor(
        convergence_threshold=convergence_threshold,
        agreement_threshold=agreement_threshold,
        cbf_threshold=cbf_threshold,
        failure_threshold=failure_threshold,
    )


__all__ = [
    "CoordinatorHealth",
    "CoordinatorHealthMonitor",
    "FallbackConfig",
    "HealthMetrics",
    "KagamiHealthMonitor",
    "create_health_monitor",
]
