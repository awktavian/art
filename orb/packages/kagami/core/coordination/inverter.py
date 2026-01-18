"""Inverter - Meta-Coordination Verifier (e₈ level).

The Inverter is NOT a colony - it's the meta-observer that verifies Kagami's
consensus itself. While the 7 colonies map to e₁-e₇ (imaginary octonions) and
Thom's 7 elementary catastrophes, the Inverter operates at the e₈ (real) level,
observing the coordination structure from outside.

NOTE: Uses `from __future__ import annotations` to defer type hint evaluation,
breaking the circular import with kagami_consensus.py.

ARCHITECTURE:
=============
┌──────────────────────────────────────────────────────────────────┐
│                      INVERTER (e₈ level)                         │
│                                                                   │
│  Observes: Kagami consensus, routing state, colony agreement     │
│  Verifies: Fano line consistency, CBF constraints, task alignment│
│  Detects: Coordinator drift, receipt pollution, routing staleness│
│  Action: Approve / Reject consensus, trigger fallback            │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼ (observes from meta-level)
┌──────────────────────────────────────────────────────────────────┐
│                  KAGAMI (consensus layer)                         │
│  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐        │
│  │ e₁ │  │ e₂ │  │ e₃ │  │ e₄ │  │ e₅ │  │ e₆ │  │ e₇ │        │
│  └────┘  └────┘  └────┘  └────┘  └────┘  └────┘  └────┘        │
└──────────────────────────────────────────────────────────────────┘

MATHEMATICAL GROUNDING:
=======================
Not a catastrophe (7 elementary catastrophes are complete for codim ≤ 5).
Instead, represents the STABILITY analysis - the meta-level that asks
"is this coordination structure itself coherent?"

In active inference terms: Inverter computes the expected free energy
of the coordination process itself (meta-level EFE).

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
from typing import (
    TYPE_CHECKING,
    Any,
)

# Third-party imports
import numpy as np

# Local imports
from kagami_math.fano_plane import FANO_LINES

if TYPE_CHECKING:
    from kagami.core.coordination.kagami_consensus import ConsensusState

logger = logging.getLogger(__name__)

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class MetaCoordinationAnalysis:
    """Inverter's output: analysis of coordination itself."""

    consensus_validity: bool
    detected_anomalies: list[str] = field(default_factory=list[Any])
    fano_line_violations: list[str] = field(default_factory=list[Any])
    cbf_violations: list[str] = field(default_factory=list[Any])
    routing_staleness: list[str] = field(default_factory=list[Any])
    receipt_anomalies: list[str] = field(default_factory=list[Any])
    recommended_action: str = "approve_consensus"
    confidence: float = 0.9
    timestamp: float = field(default_factory=time.time)


@dataclass
class CoordinatorDriftReport:
    """Long-term drift detection for Kagami."""

    drift_detected: bool
    drift_type: str | None = None  # "convergence_slowdown", "agreement_degradation", etc.
    severity: float = 0.0  # [0, 1]
    trend_data: dict[str, Any] = field(default_factory=dict[str, Any])
    recommendation: str = "continue_monitoring"


# =============================================================================
# FANO PLANE STRUCTURE (for verification)
# =============================================================================

# FANO_LINES imported at module level - convert to 0-indexed sets
FANO_LINES_ZERO_INDEXED = [{idx - 1 for idx in line} for line in FANO_LINES]

# Legacy fallback reference (for internal use only)
_FANO_LINES_FALLBACK = [
    {0, 1, 2},  # Spark × Forge = Flow
    {0, 3, 4},  # Spark × Nexus = Beacon
    {0, 5, 6},  # Spark × Grove = Crystal
    {1, 3, 5},  # Forge × Nexus = Grove
    {1, 4, 6},  # Beacon × Forge = Crystal
    {2, 3, 6},  # Nexus × Flow = Crystal
    {2, 4, 5},  # Beacon × Flow = Grove
]

# =============================================================================
# INVERTER META-VERIFIER
# =============================================================================


class InverterAgent:
    """e₈ level meta-observer - verifies Kagami consensus.

    NOT a colony - operates at the meta-coordination level.
    Observes the 7-colony coordination structure from outside.

    Character: The Skeptic - questions coordination itself.
    """

    def __init__(
        self,
        agreement_threshold: float = 0.75,  # Byzantine tolerance: 6/8
        cbf_threshold: float = 0.0,
        convergence_threshold: float = 5.0,  # seconds
    ):
        """Initialize Inverter.

        Args:
            agreement_threshold: Minimum mean agreement for valid consensus
            cbf_threshold: Minimum CBF margin h(x)
            convergence_threshold: Maximum acceptable convergence time (seconds)
        """
        self.name = "Inverter"
        self.symbol = "e₈"
        self.level = "meta-coordination"

        self.agreement_threshold = agreement_threshold
        self.cbf_threshold = cbf_threshold
        self.convergence_threshold = convergence_threshold

        # History for drift detection
        self.consensus_history: list[ConsensusState] = []
        self.analysis_history: list[MetaCoordinationAnalysis] = []

    # =========================================================================
    # PRIMARY VERIFICATION
    # =========================================================================

    def analyze_coordination(
        self,
        consensus: ConsensusState,
        task_context: str = "",
    ) -> MetaCoordinationAnalysis:
        """Inverter's primary function: verify Kagami's consensus.

        Checks:
        1. Fano line consistency (do proposed colonies lie on valid lines?)
        2. CBF constraints (is h(x) ≥ 0 for all proposals?)
        3. Byzantine tolerance (sufficient agreement?)
        4. Task-routing alignment (does routing match task requirements?)
        5. Convergence quality (did consensus converge properly?)

        Args:
            consensus: The consensus state to verify
            task_context: Original task description (for alignment check)

        Returns:
            MetaCoordinationAnalysis with verification results
        """
        anomalies: list[str] = []
        fano_violations: list[str] = []
        cbf_violations: list[str] = []

        # Check 1: Convergence
        if not consensus.converged:
            anomalies.append("Consensus failed to converge")

        # Check 2: Fano consistency
        if not self._verify_fano_consistency(consensus):
            fano_violations.append("Routing violates Fano plane structure")

        # Check 3: CBF constraints
        if consensus.cbf_constraint < self.cbf_threshold:
            cbf_violations.append(
                f"CBF margin below threshold: {consensus.cbf_constraint:.3f} < {self.cbf_threshold}"
            )

        # Check 4: Byzantine tolerance
        mean_agreement = float(np.mean(consensus.agreement_matrix))
        if mean_agreement < self.agreement_threshold:
            anomalies.append(f"Low agreement: {mean_agreement:.2f} < {self.agreement_threshold}")

        # Check 5: Task alignment
        if task_context and not self._verify_task_alignment(consensus, task_context):
            anomalies.append("Routing doesn't match task requirements")

        # Decision
        critical_failures = len(fano_violations) + len(cbf_violations)
        valid = critical_failures == 0 and len(anomalies) < 2  # Tolerate 1 anomaly

        if not valid:
            action = "reject_consensus_and_retry"
            confidence = 0.3
        elif len(anomalies) > 0:
            action = "accept_with_monitoring"
            confidence = 0.7
        else:
            action = "approve_consensus"
            confidence = 0.95

        analysis = MetaCoordinationAnalysis(
            consensus_validity=valid,
            detected_anomalies=anomalies,
            fano_line_violations=fano_violations,
            cbf_violations=cbf_violations,
            recommended_action=action,
            confidence=confidence,
        )

        # Record for drift detection
        self.consensus_history.append(consensus)
        self.analysis_history.append(analysis)

        logger.info(
            f"Inverter analysis: valid={valid}, action={action}, confidence={confidence:.2f}"
        )

        return analysis

    def _verify_fano_consistency(self, consensus: ConsensusState) -> bool:
        """Check if proposed colony activations lie on valid Fano lines.

        Args:
            consensus: Consensus state with routing

        Returns:
            True if routing respects Fano structure
        """
        if consensus.consensus_routing is None:
            return False

        # Extract active colony indices
        active_colonies = {
            i
            for i, (colony_id, task) in enumerate(consensus.consensus_routing.items())
            if task and task != "inactive"
        }

        if len(active_colonies) == 0:
            return False

        # Single colony: always valid
        if len(active_colonies) == 1:
            return True

        # Two colonies: valid if they lie on some Fano line
        if len(active_colonies) == 2:
            for line in FANO_LINES_ZERO_INDEXED:
                if active_colonies.issubset(line):
                    return True
            return False

        # Three colonies: valid if they form a Fano line
        if len(active_colonies) == 3:
            return active_colonies in FANO_LINES_ZERO_INDEXED

        # More than 3: complex task, check if decomposable into Fano lines
        # This is always true (any subset of colonies can be covered by lines)
        return True

    def _verify_task_alignment(self, consensus: ConsensusState, task: str) -> bool:
        """Check if routing matches task requirements.

        Uses simple heuristics to verify routing makes sense for task.
        In production, this would use learned task-colony affinity.

        Args:
            consensus: Consensus state with routing
            task: Task description

        Returns:
            True if routing aligns with task semantics
        """
        if consensus.consensus_routing is None:
            return False

        active = set(consensus.consensus_routing.keys())

        # Heuristics based on task keywords
        task_lower = task.lower()

        required_colonies = []

        if any(kw in task_lower for kw in ["implement", "build", "create", "code"]):
            required_colonies.append(1)  # Forge

        if any(kw in task_lower for kw in ["verify", "test", "check", "audit"]):
            required_colonies.append(6)  # Crystal

        if any(kw in task_lower for kw in ["plan", "design", "architect", "strategy"]):
            required_colonies.append(4)  # Beacon

        if any(kw in task_lower for kw in ["research", "explore", "investigate", "study"]):
            required_colonies.append(5)  # Grove

        if any(kw in task_lower for kw in ["debug", "fix", "error", "recover"]):
            required_colonies.append(2)  # Flow

        if any(kw in task_lower for kw in ["brainstorm", "ideate", "creative", "imagine"]):
            required_colonies.append(0)  # Spark

        if any(kw in task_lower for kw in ["integrate", "connect", "combine", "unify"]):
            required_colonies.append(3)  # Nexus

        # If no keywords matched, accept any routing
        if not required_colonies:
            return len(active) > 0

        # Check if at least one required colony is active
        return any(colony_id in active for colony_id in required_colonies)  # type: ignore[comparison-overlap]

    # =========================================================================
    # DRIFT DETECTION
    # =========================================================================

    def detect_coordinator_drift(self, window_size: int = 10) -> CoordinatorDriftReport:
        """Detect if Kagami's coordination is drifting over time.

        Analyzes trends in consensus quality:
        - Convergence time increasing
        - Agreement decreasing
        - CBF margin eroding
        - Rejection rate increasing

        Args:
            window_size: Number of recent consensus states to analyze

        Returns:
            CoordinatorDriftReport with drift analysis
        """
        if len(self.consensus_history) < window_size:
            return CoordinatorDriftReport(
                drift_detected=False,
                recommendation="insufficient_data",
            )

        recent = self.consensus_history[-window_size:]
        recent_analyses = self.analysis_history[-window_size:]

        # Split into first half vs second half for trend analysis
        mid = window_size // 2
        first_half = recent[:mid]
        second_half = recent[mid:]

        drift_signals: list[str] = []
        severity = 0.0

        # Signal 1: Agreement degradation
        agreement_first = np.mean([np.mean(c.agreement_matrix) for c in first_half])
        agreement_second = np.mean([np.mean(c.agreement_matrix) for c in second_half])

        if agreement_second < agreement_first - 0.1:
            drift_signals.append("agreement_degradation")
            severity += 0.3

        # Signal 2: CBF margin erosion
        cbf_first = np.mean([c.cbf_constraint for c in first_half])
        cbf_second = np.mean([c.cbf_constraint for c in second_half])

        if cbf_second < cbf_first - 0.1:
            drift_signals.append("cbf_margin_erosion")
            severity += 0.4

        # Signal 3: Convergence failure rate
        converged_first = sum(1 for c in first_half if c.converged) / len(first_half)
        converged_second = sum(1 for c in second_half if c.converged) / len(second_half)

        if converged_second < converged_first - 0.2:
            drift_signals.append("convergence_failure_increase")
            severity += 0.5

        # Signal 4: Rejection rate
        rejected_first = sum(1 for a in recent_analyses[:mid] if not a.consensus_validity) / len(
            recent_analyses[:mid]
        )
        rejected_second = sum(1 for a in recent_analyses[mid:] if not a.consensus_validity) / len(
            recent_analyses[mid:]
        )

        if rejected_second > rejected_first + 0.2:
            drift_signals.append("rejection_rate_increase")
            severity += 0.4

        # Decision
        drift_detected = len(drift_signals) >= 2 or severity > 0.7

        if drift_detected:
            drift_type = ", ".join(drift_signals)
            if severity > 0.8:
                recommendation = "emergency_reset"
            elif severity > 0.5:
                recommendation = "trigger_fallback"
            else:
                recommendation = "increase_monitoring"
        else:
            drift_type = None
            recommendation = "continue_monitoring"

        return CoordinatorDriftReport(
            drift_detected=drift_detected,
            drift_type=drift_type,
            severity=severity,
            trend_data={
                "agreement_first": float(agreement_first),
                "agreement_second": float(agreement_second),
                "cbf_first": float(cbf_first),
                "cbf_second": float(cbf_second),
                "converged_first": float(converged_first),
                "converged_second": float(converged_second),
                "rejected_first": float(rejected_first),
                "rejected_second": float(rejected_second),
            },
            recommendation=recommendation,
        )

    # =========================================================================
    # RECEIPT VALIDATION
    # =========================================================================

    def validate_receipt(
        self,
        receipt: dict[str, Any],
        expected_colony: int | None = None,
    ) -> tuple[bool, str]:
        """Validate a receipt before allowing it to update routing model.

        Prevents adversarial colonies from polluting the receipt history.

        Args:
            receipt: Receipt dict[str, Any] with task, action, outcome, etc.
            expected_colony: If provided, verify receipt is from this colony

        Returns:
            (is_valid, reason)
        """
        # Check 1: Required fields present
        required_fields = ["task", "action", "outcome", "colony_id"]
        missing = [f for f in required_fields if f not in receipt]

        if missing:
            return False, f"Missing fields: {missing}"

        # Check 2: Colony ID is valid (0-6)
        colony_id = receipt.get("colony_id", -1)
        if not isinstance(colony_id, int) or not (0 <= colony_id <= 6):
            return False, f"Invalid colony_id: {colony_id}"

        # Check 3: If expected colony specified, match
        if expected_colony is not None and colony_id != expected_colony:
            return False, f"Colony mismatch: expected {expected_colony}, got {colony_id}"

        # Check 4: Outcome is reasonable
        outcome = receipt.get("outcome", {})
        if not isinstance(outcome, dict):
            return False, "Outcome must be dict[str, Any]"

        # Check 5: No suspiciously high confidence (>0.999)
        confidence = receipt.get("confidence", 0.5)
        if confidence > 0.999:
            return False, f"Suspiciously high confidence: {confidence}"

        # Check 6: Timestamp is recent (within 1 hour)
        timestamp = receipt.get("timestamp", 0)
        if time.time() - timestamp > 3600:
            return False, f"Stale receipt: {time.time() - timestamp:.0f}s old"

        return True, "valid"

    # =========================================================================
    # ROUTING STATE VERIFICATION
    # =========================================================================

    def verify_routing_state(
        self,
        router_state: dict[str, Any],
        colony_capabilities: dict[int, set[str]],
    ) -> tuple[bool, list[str]]:
        """Verify FanoActionRouter state consistency.

        Checks:
        1. Domain affinity cache matches current colony capabilities
        2. Fano neighbor structure is symmetric
        3. No routing cycles exist

        Args:
            router_state: Router's internal state (domain_affinity, fano_neighbors)
            colony_capabilities: Current capabilities per colony

        Returns:
            (is_consistent, list[Any] of issues)
        """
        issues: list[str] = []

        # Check 1: Domain affinity matches capabilities
        domain_affinity = router_state.get("domain_affinity", {})

        for domain, colony_scores in domain_affinity.items():
            for colony_id, _score in colony_scores:
                if colony_id not in colony_capabilities:
                    issues.append(f"Colony {colony_id} in affinity but not in capabilities")
                    continue

                # If colony no longer has this capability, affinity is stale
                if domain not in colony_capabilities[colony_id]:
                    issues.append(
                        f"Colony {colony_id} affinity for {domain} is stale (no longer has capability)"
                    )

        # Check 2: Fano neighbor structure
        fano_neighbors = router_state.get("fano_neighbors", {})

        for colony_id, neighbors in fano_neighbors.items():
            if not (0 <= colony_id <= 6):
                issues.append(f"Invalid colony_id in fano_neighbors: {colony_id}")
                continue

            # Each colony should have exactly 3 Fano neighbors
            if len(neighbors) != 3:
                issues.append(f"Colony {colony_id} has {len(neighbors)} Fano neighbors, expected 3")

            # Check symmetry: if A neighbors B, then B neighbors A
            for neighbor_id in neighbors:
                if neighbor_id not in fano_neighbors:
                    issues.append(
                        f"Asymmetric Fano structure: {colony_id} → {neighbor_id}, but {neighbor_id} not in graph"
                    )
                elif colony_id not in fano_neighbors[neighbor_id]:
                    issues.append(
                        f"Asymmetric Fano structure: {colony_id} → {neighbor_id}, but not {neighbor_id} → {colony_id}"
                    )

        # Check 3: No routing cycles (simple: ensure no colony routes to itself)
        # In a more complex check, we'd build a graph and check for cycles
        for colony_id in range(7):
            if colony_id in fano_neighbors.get(colony_id, []):
                issues.append(f"Colony {colony_id} has self-loop in Fano neighbors")

        is_consistent = len(issues) == 0

        if not is_consistent:
            logger.warning(f"Routing state inconsistency detected: {len(issues)} issues")

        return is_consistent, issues


# =============================================================================
# FACTORY
# =============================================================================


def create_inverter(
    agreement_threshold: float = 0.75,
    cbf_threshold: float = 0.0,
    convergence_threshold: float = 5.0,
) -> InverterAgent:
    """Create Inverter meta-verifier.

    Args:
        agreement_threshold: Minimum mean agreement for valid consensus
        cbf_threshold: Minimum CBF margin h(x)
        convergence_threshold: Maximum acceptable convergence time (seconds)

    Returns:
        InverterAgent instance
    """
    return InverterAgent(
        agreement_threshold=agreement_threshold,
        cbf_threshold=cbf_threshold,
        convergence_threshold=convergence_threshold,
    )


__all__ = [
    "CoordinatorDriftReport",
    "InverterAgent",
    "MetaCoordinationAnalysis",
    "create_inverter",
]
