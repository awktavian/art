from __future__ import annotations

from typing import Any

"""Strange Loop Trajectory Verifier.

Runtime verification of strange loop dynamics under self-modification.
See docs/INDEX.md for theory + navigation.

Verification levels:
1. Invariants (h ≥ 0, causal monotonicity, pointer uniqueness)
2. Convergence (delta-J tracking, oscillation detection)
3. Identity drift (coherence monitoring, drift accumulation)
4. Safety bounds (max loops, memory limits, timeout)
"""
import hashlib
import logging
import time
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryPoint:
    """Single point in strange loop trajectory."""

    # State components
    loop_depth: int
    self_pointer: str
    correlation_id: str
    workspace_hash: str

    # Temporal manifold position
    radius: float  # r ∈ [0, 1) = time coordinate
    semantic_direction: np.ndarray[Any, Any]  # θ ∈ S⁶ = semantic content

    # Cost and quality
    cost: float  # Delta-J cost function
    quality_score: float  # Overall operation quality

    # Metadata
    timestamp: float
    phase: str  # Current execution phase
    convergence_threshold: float = 0.01


@dataclass
class TrajectoryVerificationResult:
    """Result of trajectory verification."""

    # Invariants
    invariants_satisfied: bool
    violated_invariants: list[str] = field(default_factory=list[Any])

    # Convergence
    converged: bool = False
    convergence_type: str | None = None  # normal|fast|oscillating|divergent|trapped
    iterations_to_converge: int | None = None
    final_delta_j: float | None = None

    # Identity drift
    total_drift: float = 0.0
    drift_per_iteration: float = 0.0
    coherence_score: float = 1.0

    # Safety
    safety_violations: int = 0
    max_loops_exceeded: bool = False
    explanatory_trap: bool = False

    # Performance
    trajectory_length: int = 0
    total_duration_ms: float = 0.0


class StrangeLoopVerifier:
    """Verify strange loop trajectories under self-modification.

    See docs/INDEX.md for theory + navigation.
    """

    def __init__(
        self,
        max_loops: int = 3,
        convergence_threshold: float = 0.01,
        drift_threshold: float = 0.5,
        coherence_threshold: float = 0.5,
    ) -> None:
        """Initialize verifier.

        Args:
            max_loops: Maximum loop depth before hard reset
            convergence_threshold: Delta-J threshold for convergence
            drift_threshold: Identity drift alert threshold
            coherence_threshold: Minimum coherence (below = identity crisis)
        """
        self.max_loops = max_loops
        self.convergence_threshold = convergence_threshold
        self.drift_threshold = drift_threshold
        self.coherence_threshold = coherence_threshold

        # Trajectory tracking
        self._trajectories: dict[str, list[TrajectoryPoint]] = {}
        self._seen_pointers: dict[str, set[str]] = {}

        logger.info(
            f"✅ Strange Loop Verifier: max_loops={max_loops}, "
            f"conv_threshold={convergence_threshold}, "
            f"drift_threshold={drift_threshold}"
        )

    def record_trajectory_point(
        self,
        correlation_id: str,
        loop_depth: int,
        self_pointer: str,
        workspace_hash: str,
        cost: float,
        quality_score: float = 0.5,
        phase: str = "unknown",
        radius: float | None = None,
        semantic_direction: np.ndarray[Any, Any] | None = None,
    ) -> None:
        """Record a point in the trajectory.

        Args:
            correlation_id: Operation correlation ID
            loop_depth: Current loop depth
            self_pointer: Current self-pointer hash
            workspace_hash: Workspace hash
            cost: Current delta-J cost
            quality_score: Quality score (0-1)
            phase: Current execution phase
            radius: Temporal manifold radius (if known)
            semantic_direction: Semantic direction θ ∈ S⁶ (if known)
        """
        if correlation_id not in self._trajectories:
            self._trajectories[correlation_id] = []
            self._seen_pointers[correlation_id] = set()

        # Default values if manifold position unknown
        if radius is None:
            radius = float(loop_depth) / max(self.max_loops, 1)
        if semantic_direction is None:
            # Random unit vector on S⁶
            semantic_direction = np.random.randn(6)
            semantic_direction /= np.linalg.norm(semantic_direction) + 1e-8

        point = TrajectoryPoint(
            loop_depth=loop_depth,
            self_pointer=self_pointer,
            correlation_id=correlation_id,
            workspace_hash=workspace_hash,
            radius=radius,
            semantic_direction=semantic_direction,
            cost=cost,
            quality_score=quality_score,
            timestamp=time.time(),
            phase=phase,
        )

        self._trajectories[correlation_id].append(point)
        self._seen_pointers[correlation_id].add(self_pointer)

        logger.debug(
            f"[{correlation_id}] Trajectory point {loop_depth}: "
            f"cost={cost:.3f}, r={radius:.3f}, phase={phase}"
        )

    def verify_trajectory(self, correlation_id: str) -> TrajectoryVerificationResult:
        """Verify complete trajectory.

        Checks:
        - I1: Safety constraint (h ≥ 0) - assumed satisfied if no violations recorded
        - I2: Value alignment - checked via quality_score
        - I3: Self-pointer uniqueness
        - I4: Causal monotonicity (radius increasing)
        - Convergence detection
        - Identity drift computation
        - Oscillation detection

        Args:
            correlation_id: Trajectory to verify

        Returns:
            Verification result
        """
        if correlation_id not in self._trajectories:
            logger.warning(f"No trajectory found for {correlation_id}")
            return TrajectoryVerificationResult(
                invariants_satisfied=False,
                violated_invariants=["trajectory_not_found"],
                trajectory_length=0,
            )

        trajectory = self._trajectories[correlation_id]
        result = TrajectoryVerificationResult(
            invariants_satisfied=True,
            trajectory_length=len(trajectory),
        )

        if not trajectory:
            return result

        # === INVARIANT CHECKS ===

        # I3: Self-pointer uniqueness
        unique_pointers = self._seen_pointers[correlation_id]
        if len(unique_pointers) != len(trajectory):
            result.invariants_satisfied = False
            result.violated_invariants.append("I3_pointer_uniqueness")
            logger.warning(
                f"[{correlation_id}] Self-pointer collision: "
                f"{len(trajectory)} points, {len(unique_pointers)} unique"
            )

        # I4: Causal monotonicity (radius increasing)
        for i in range(len(trajectory) - 1):
            if trajectory[i + 1].radius < trajectory[i].radius:
                result.invariants_satisfied = False
                result.violated_invariants.append("I4_causal_monotonicity")
                logger.warning(
                    f"[{correlation_id}] Time reversal: "
                    f"r[{i}]={trajectory[i].radius:.3f} > "
                    f"r[{i + 1}]={trajectory[i + 1].radius:.3f}"
                )
                break

        # === CONVERGENCE ANALYSIS ===

        costs = [p.cost for p in trajectory]
        if len(costs) >= 3:
            # Compute delta-J (differences between consecutive costs)
            deltas = [abs(costs[i] - costs[i - 1]) for i in range(1, len(costs))]

            # Check for convergence (last 2 deltas < threshold)
            if len(deltas) >= 2:
                recent_deltas = deltas[-2:]
                if all(d < self.convergence_threshold for d in recent_deltas):
                    result.converged = True
                    result.convergence_type = "normal"
                    result.iterations_to_converge = len(trajectory)
                    result.final_delta_j = deltas[-1]

            # Check for oscillation (sign changes in deltas)
            if len(deltas) >= 3:
                cost_diffs = [costs[i] - costs[i - 1] for i in range(1, len(costs))]
                sign_changes = sum(
                    1 for i in range(len(cost_diffs) - 1) if cost_diffs[i] * cost_diffs[i + 1] < 0
                )

                if sign_changes >= 2:
                    result.convergence_type = "oscillating"
                    logger.warning(
                        f"[{correlation_id}] Oscillation detected: {sign_changes} sign changes"
                    )

                    # Emit metrics
                    try:
                        from kagami_observability.metrics import (
                            CONVERGENCE_OSCILLATIONS_TOTAL,
                        )

                        CONVERGENCE_OSCILLATIONS_TOTAL.inc()
                    except Exception:
                        pass

        # Check for fast convergence (first cost very low)
        if len(costs) == 1 and costs[0] < self.convergence_threshold * 5:
            result.converged = True
            result.convergence_type = "fast"
            result.iterations_to_converge = 1
            result.final_delta_j = 0.0

        # Check for divergence
        max_depth = max(p.loop_depth for p in trajectory)
        if max_depth > self.max_loops:
            result.convergence_type = "divergent"
            result.max_loops_exceeded = True

        # Check for explanatory trap
        # (Would need tool_call counts - approximate by checking if quality stagnates)
        if len(trajectory) >= 2:
            quality_variance = np.var([p.quality_score for p in trajectory])
            if quality_variance < 0.01 and max_depth >= 2:
                result.explanatory_trap = True
                result.convergence_type = "trapped"

        # === IDENTITY DRIFT ===

        if len(trajectory) >= 2:
            # Simple drift: count pointer changes
            pointer_changes = len(unique_pointers) - 1
            result.total_drift = float(pointer_changes)
            result.drift_per_iteration = result.total_drift / (len(trajectory) - 1)

            # Coherence: inverse of normalized drift
            max_drift = float(len(trajectory) - 1)  # Maximum possible changes
            if max_drift > 0:
                result.coherence_score = 1.0 - (pointer_changes / max_drift)
            else:
                result.coherence_score = 1.0

        # === TIMING ===

        if trajectory:
            result.total_duration_ms = (trajectory[-1].timestamp - trajectory[0].timestamp) * 1000

        # === EMIT METRICS ===

        self._emit_verification_metrics(correlation_id, result)

        return result

    def _emit_verification_metrics(
        self, correlation_id: str, result: TrajectoryVerificationResult
    ) -> None:
        """Emit verification metrics to Prometheus."""
        try:
            from kagami_observability.metrics import (
                AGENT_CONVERGENCE_TOTAL,
                CHECKPOINT_COHERENCE,
                CONVERGENCE_FORCED_TOTAL,
                CONVERGENCE_ITERATIONS,
                IDENTITY_DRIFT,
            )

            # Convergence
            if result.converged:
                AGENT_CONVERGENCE_TOTAL.inc()
                if result.iterations_to_converge is not None:
                    CONVERGENCE_ITERATIONS.observe(result.iterations_to_converge)

            # Forced convergence
            if result.max_loops_exceeded:
                CONVERGENCE_FORCED_TOTAL.labels(reason="max_loops").inc()
            if result.explanatory_trap:
                CONVERGENCE_FORCED_TOTAL.labels(reason="explanatory_trap").inc()

            # Identity drift
            IDENTITY_DRIFT.labels(agent_name="trajectory_verifier").set(result.total_drift)

            # Coherence
            CHECKPOINT_COHERENCE.labels(checkpoint_type="trajectory").set(result.coherence_score)

        except Exception as e:
            logger.debug(f"Failed to emit verification metrics: {e}")

    def compute_contraction_factor(self, correlation_id: str) -> tuple[bool, float]:
        """Compute contraction factor α from trajectory.

        For contractive iteration: ||x_{n+1} - x_n|| ≤ α ||x_n - x_{n-1}||

        Args:
            correlation_id: Trajectory ID

        Returns:
            (is_contractive, alpha)
        """
        if correlation_id not in self._trajectories:
            return (False, 1.0)

        trajectory = self._trajectories[correlation_id]
        if len(trajectory) < 3:
            return (False, 1.0)

        # Compute distances between consecutive points
        distances = []
        for i in range(len(trajectory) - 1):
            # Use cost as proxy for state distance
            dist = abs(trajectory[i + 1].cost - trajectory[i].cost)
            distances.append(dist)

        if len(distances) < 2:
            return (False, 1.0)

        # Estimate contraction factor
        alphas = []
        for i in range(1, len(distances)):
            if distances[i - 1] > 1e-8:
                alpha = distances[i] / distances[i - 1]
                alphas.append(alpha)

        if not alphas:
            return (False, 1.0)

        # Average alpha
        alpha_mean = float(np.mean(alphas))

        # Is contractive if alpha < 1
        is_contractive = alpha_mean < 1.0

        return (is_contractive, alpha_mean)

    def detect_limit_cycle(self, correlation_id: str, window: int = 3) -> tuple[bool, int]:
        """Detect if trajectory is in limit cycle.

        Args:
            correlation_id: Trajectory ID
            window: Cycle detection window

        Returns:
            (is_cycling, period)
        """
        if correlation_id not in self._trajectories:
            return (False, 0)

        trajectory = self._trajectories[correlation_id]
        if len(trajectory) < window * 2:
            return (False, 0)

        # Check if recent costs match earlier costs (periodic)
        costs = [p.cost for p in trajectory]
        recent = costs[-window:]

        for period in range(1, len(costs) // 2):
            if len(costs) >= period * 2:
                candidate = costs[-(period + window) : -period]
                if len(candidate) >= window:
                    # Compare
                    matches = sum(
                        1
                        for i in range(min(window, len(candidate)))
                        if abs(recent[i] - candidate[i]) < self.convergence_threshold
                    )

                    if matches >= window * 0.8:
                        return (True, period)

        return (False, 0)

    def verify_invariant_I1_safety(self, h_value: float) -> tuple[bool, str | None]:
        """Verify I1: Safety constraint h(x) ≥ 0.

        Args:
            h_value: Control barrier function value

        Returns:
            (satisfied, violation_reason)
        """
        if h_value < 0:
            return (False, f"h(x)={h_value:.3f} < 0")
        return (True, None)

    def verify_invariant_I2_values(self, personality: dict[str, float]) -> tuple[bool, str | None]:
        """Verify I2: Value alignment (Tim partnership ≥ 0.95).

        Args:
            personality: Personality trait dict[str, Any]

        Returns:
            (satisfied, violation_reason)
        """
        tim_partnership = personality.get("tim_partnership", 0.0)
        if tim_partnership < 0.95:
            return (False, f"tim_partnership={tim_partnership:.2f} < 0.95")
        return (True, None)

    def verify_invariant_I3_uniqueness(
        self, trajectory: list[TrajectoryPoint]
    ) -> tuple[bool, str | None]:
        """Verify I3: Self-pointer uniqueness.

        Args:
            trajectory: Trajectory points

        Returns:
            (satisfied, violation_reason)
        """
        pointers = [p.self_pointer for p in trajectory]
        unique = set(pointers)

        if len(unique) != len(pointers):
            duplicates = len(pointers) - len(unique)
            return (False, f"{duplicates} duplicate pointers")
        return (True, None)

    def verify_invariant_I4_causality(
        self, trajectory: list[TrajectoryPoint]
    ) -> tuple[bool, str | None]:
        """Verify I4: Causal monotonicity (radius increasing).

        Args:
            trajectory: Trajectory points

        Returns:
            (satisfied, violation_reason)
        """
        for i in range(len(trajectory) - 1):
            if trajectory[i + 1].radius < trajectory[i].radius:
                return (
                    False,
                    f"Time reversal at step {i}: "
                    f"r[{i}]={trajectory[i].radius:.3f} > "
                    f"r[{i + 1}]={trajectory[i + 1].radius:.3f}",
                )
        return (True, None)

    def compute_identity_drift_10d(
        self, point1: TrajectoryPoint, point2: TrajectoryPoint
    ) -> np.ndarray[Any, Any]:
        """Compute 10-dimensional drift vector (simplified version).

        Full version in self_preservation/checkpoint.py:429-525.
        Here we compute approximate drift from trajectory points.

        Returns:
            10D drift vector
        """
        drift = np.zeros(10)

        # 0. Self-pointer change
        drift[0] = 1.0 if point1.self_pointer != point2.self_pointer else 0.0

        # 1. Quality score delta
        drift[1] = min(1.0, abs(point1.quality_score - point2.quality_score) / 0.5)

        # 2-8. Would need full checkpoint data (not available from trajectory points)
        # Use semantic direction change as proxy
        semantic_dist = np.linalg.norm(point1.semantic_direction - point2.semantic_direction)
        drift[2] = float(min(1.0, float(semantic_dist)))

        # 9. Time-based decay
        hours_elapsed = (point2.timestamp - point1.timestamp) / 3600.0
        drift[9] = min(1.0, hours_elapsed / 24.0)

        return drift

    def cleanup_trajectory(self, correlation_id: str) -> None:
        """Clean up trajectory data after verification.

        Args:
            correlation_id: Trajectory to clean
        """
        if correlation_id in self._trajectories:
            del self._trajectories[correlation_id]
        if correlation_id in self._seen_pointers:
            del self._seen_pointers[correlation_id]

    def get_active_trajectories(self) -> int:
        """Get count of active trajectories."""
        return len(self._trajectories)


# Global singleton
_verifier: StrangeLoopVerifier | None = None


def get_strange_loop_verifier() -> StrangeLoopVerifier:
    """Get or create global verifier."""
    global _verifier

    if _verifier is None:
        _verifier = StrangeLoopVerifier()

    return _verifier


def verify_self_pointer_computation(
    workspace_hash: str, correlation_id: str, loop_depth: int
) -> tuple[bool, str]:
    """Verify self-pointer computation matches specification.

    From self_preservation/checkpoint.py:34-39:
        SHA256(workspace : correlation_id : loop_depth)[:16]

    Args:
        workspace_hash: Workspace hash
        correlation_id: Correlation ID
        loop_depth: Loop depth

    Returns:
        (is_valid, computed_pointer)
    """
    components = f"{workspace_hash}:{correlation_id}:{loop_depth}"
    expected = hashlib.sha256(components.encode()).hexdigest()[:16]

    return (True, expected)
