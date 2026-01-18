"""Fano Plane Compositional Control Barrier Functions.

CREATED: December 14, 2025
MISSION: Safety for multi-colony Fano line compositions

When multiple colonies work together along Fano lines, their joint safety
must be verified compositionally. This module implements barrier composition
rules that ensure safe multi-colony coordination.

MATHEMATICAL FOUNDATION:
========================
For colonies A, B working together:
    h_AB = min(h_A, h_B, h_shared)

Where:
- h_A: Colony A's local barrier (from DecentralizedCBF)
- h_B: Colony B's local barrier (from DecentralizedCBF)
- h_shared: Shared resource barrier (memory, compute, communication)

Fano line composition: A × B = C
- A, B compose to produce result C
- All three must be safe: h_A ≥ 0, h_B ≥ 0, h_C ≥ 0
- Shared resources must be safe: h_shared ≥ 0

FANO LINES (7 total, 0-indexed):
=================================
Line 0: {0, 1, 2} — Spark × Forge = Flow
Line 1: {0, 3, 4} — Spark × Nexus = Beacon
Line 2: {0, 6, 5} — Spark × Crystal = Grove
Line 3: {1, 3, 5} — Forge × Nexus = Grove
Line 4: {1, 4, 6} — Forge × Beacon = Crystal
Line 5: {2, 3, 6} — Flow × Nexus = Crystal
Line 6: {2, 5, 4} — Flow × Grove = Beacon

USAGE:
======
# Compose barriers for two colonies on a Fano line
h_AB = compose_fano_barriers(
    h_A=0.3,
    h_B=0.2,
    shared_resources={"memory": 0.7, "compute": 0.8},
    fano_line=0,  # Spark × Forge = Flow
)

# Check all Fano lines for safety violations
checker = FanoCompositionChecker()
violations = checker.check_all_lines(colony_states)

References:
- Ames et al. (2019): Control Barrier Functions
- Wang et al. (2017): Safety Barrier Certificates for Collectives
- Fano plane structure: kagami/core/math/fano_plane.py
- Decentralized CBF: kagami/core/safety/decentralized_cbf.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch
from kagami_math.fano_plane import FANO_LINES, get_fano_lines_zero_indexed

if TYPE_CHECKING:
    from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Fano lines with 0-based indexing
FANO_LINES_0IDX = get_fano_lines_zero_indexed()

# Shared resource thresholds (normalized 0-1)
DEFAULT_RESOURCE_THRESHOLDS = {
    "memory": 0.85,  # 85% memory utilization = unsafe
    "compute": 0.90,  # 90% compute utilization = unsafe
    "bandwidth": 0.80,  # 80% bandwidth utilization = unsafe
    "latency": 0.75,  # 75% of latency budget = unsafe
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class CompositionBarrierResult:
    """Result of Fano barrier composition."""

    h_composed: float  # Composed barrier value
    h_A: float  # Colony A barrier
    h_B: float  # Colony B barrier
    h_shared: float  # Shared resource barrier
    is_safe: bool  # h_composed >= 0
    limiting_factor: str  # Which barrier is most restrictive
    fano_line: int  # Which Fano line (0-6)
    metadata: dict[str, Any]


# =============================================================================
# SHARED RESOURCE BARRIER COMPUTATION
# =============================================================================


def compute_shared_resource_barrier(
    shared_resources: dict[str, float],
    thresholds: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    """Compute barrier value for shared resources.

    Shared resources (memory, compute, bandwidth) have thresholds beyond which
    multi-colony work becomes unsafe. This computes a barrier that ensures
    resources stay below danger thresholds.

    Args:
        shared_resources: Dict of resource utilization [0, 1]
            - "memory": Memory utilization fraction
            - "compute": Compute utilization fraction
            - "bandwidth": Network bandwidth utilization
            - "latency": Latency budget consumption
        thresholds: Optional custom thresholds per resource

    Returns:
        h_shared: Barrier value (positive = safe, negative = unsafe)
        per_resource: Per-resource barrier values
    """
    if thresholds is None:
        thresholds = DEFAULT_RESOURCE_THRESHOLDS

    per_resource_barriers: dict[str, float] = {}

    for resource, utilization in shared_resources.items():
        # Get threshold for this resource
        threshold = thresholds.get(resource, 0.85)

        # Barrier: h = threshold - utilization
        # Positive when utilization < threshold (safe)
        # Negative when utilization > threshold (unsafe)
        h_resource = threshold - utilization
        per_resource_barriers[resource] = h_resource

    # Overall shared barrier is minimum (most restrictive)
    if per_resource_barriers:
        h_shared = min(per_resource_barriers.values())
    else:
        # No resource constraints → fully safe
        h_shared = 1.0

    return h_shared, per_resource_barriers


# =============================================================================
# FANO BARRIER COMPOSITION
# =============================================================================


def compose_fano_barriers(
    h_A: float,
    h_B: float,
    shared_resources: dict[str, float],
    fano_line: int,
    resource_thresholds: dict[str, float] | None = None,
) -> float:
    """Compose two colony barriers along a Fano line.

    When colonies A and B work together on a Fano line, their joint safety
    is the minimum of:
    1. Colony A's local safety (h_A)
    2. Colony B's local safety (h_B)
    3. Shared resource safety (h_shared)

    This ensures that composition is safe only if ALL components are safe.

    Args:
        h_A: Barrier value for colony A
        h_B: Barrier value for colony B
        shared_resources: Dict of resource utilization (memory, compute, etc.)
        fano_line: Which Fano line (0-6) this composition is on
        resource_thresholds: Optional custom resource thresholds

    Returns:
        h_AB: Composed barrier (h_AB >= 0 means safe, < 0 means violation)

    Examples:
        >>> # Safe composition
        >>> h = compose_fano_barriers(
        ...     h_A=0.3, h_B=0.2,
        ...     shared_resources={"memory": 0.5, "compute": 0.6},
        ...     fano_line=0,
        ... )
        >>> h >= 0  # True if all components safe
        True

        >>> # Unsafe due to resource constraint
        >>> h = compose_fano_barriers(
        ...     h_A=0.3, h_B=0.2,
        ...     shared_resources={"memory": 0.95},  # Over threshold
        ...     fano_line=0,
        ... )
        >>> h < 0  # True - memory violation
        True
    """
    # Validate fano_line
    if not 0 <= fano_line < 7:
        raise ValueError(f"fano_line must be 0-6, got {fano_line}")

    # Compute shared resource barrier
    h_shared, _ = compute_shared_resource_barrier(
        shared_resources,
        thresholds=resource_thresholds,
    )

    # Composition: min of all barriers
    # All must be safe for joint work to be safe
    h_AB = min(h_A, h_B, h_shared)

    return h_AB


def compose_fano_barriers_detailed(
    h_A: float,
    h_B: float,
    shared_resources: dict[str, float],
    fano_line: int,
    resource_thresholds: dict[str, float] | None = None,
) -> CompositionBarrierResult:
    """Detailed barrier composition with diagnostic information.

    Args:
        h_A: Barrier value for colony A
        h_B: Barrier value for colony B
        shared_resources: Dict of resource utilization
        fano_line: Which Fano line (0-6)
        resource_thresholds: Optional custom resource thresholds

    Returns:
        CompositionBarrierResult with full diagnostics
    """
    # Compute shared resource barrier with per-resource breakdown
    h_shared, per_resource = compute_shared_resource_barrier(
        shared_resources,
        thresholds=resource_thresholds,
    )

    # Composed barrier
    h_composed = min(h_A, h_B, h_shared)

    # Determine limiting factor
    if h_composed == h_A:
        limiting_factor = "colony_A"
    elif h_composed == h_B:
        limiting_factor = "colony_B"
    else:
        # Find which resource is most limiting
        limiting_resource = min(per_resource.items(), key=lambda x: x[1])[0]
        limiting_factor = f"resource_{limiting_resource}"

    return CompositionBarrierResult(
        h_composed=h_composed,
        h_A=h_A,
        h_B=h_B,
        h_shared=h_shared,
        is_safe=h_composed >= 0.0,
        limiting_factor=limiting_factor,
        fano_line=fano_line,
        metadata={
            "per_resource_barriers": per_resource,
            "shared_resources": shared_resources,
        },
    )


# =============================================================================
# FANO COMPOSITION CHECKER
# =============================================================================


class FanoCompositionChecker:
    """Check safety of Fano line compositions.

    This class verifies that multi-colony compositions along Fano lines
    maintain safety invariants. It integrates with DecentralizedCBF to
    access per-colony barriers and computes compositional safety.

    Usage:
        checker = FanoCompositionChecker()

        # Check single line
        h_line = checker.check_line(
            line_id=0,
            colony_states=states,
            shared_resources=resources,
        )

        # Check all lines
        results = checker.check_all_lines(
            colony_states=states,
            shared_resources=resources,
        )
    """

    def __init__(
        self,
        cbf_registry: FanoDecentralizedCBF | None = None,
        resource_thresholds: dict[str, float] | None = None,
    ):
        """Initialize Fano composition checker.

        Args:
            cbf_registry: Optional DecentralizedCBF for per-colony barriers
                If None, barriers must be provided directly to check methods
            resource_thresholds: Optional custom resource thresholds
        """
        self.cbf_registry = cbf_registry
        self.resource_thresholds = resource_thresholds or DEFAULT_RESOURCE_THRESHOLDS

        logger.debug(
            f"✅ FanoCompositionChecker initialized: "
            f"cbf_registry={'present' if cbf_registry else 'none'}"
        )

    def check_line(
        self,
        line_id: int,
        colony_states: dict[int, torch.Tensor] | torch.Tensor,
        shared_resources: dict[str, float] | None = None,
        colony_barriers: dict[int, float] | None = None,
    ) -> float:
        """Check if a Fano line composition is safe.

        Args:
            line_id: Fano line index (0-6)
            colony_states: Either:
                - Dict mapping colony_idx → state tensor [state_dim]
                - Tensor [7, state_dim] with all colony states
            shared_resources: Dict of resource utilization
            colony_barriers: Optional pre-computed barriers per colony
                If None, will compute from colony_states using cbf_registry

        Returns:
            h_line: Barrier value for this line (positive = safe)

        Raises:
            ValueError: If line_id invalid or required data missing
        """
        if not 0 <= line_id < 7:
            raise ValueError(f"line_id must be 0-6, got {line_id}")

        # Get colony indices on this line
        i, j, k = FANO_LINES_0IDX[line_id]

        # Get barriers for colonies on this line
        if colony_barriers is not None:
            # Use pre-computed barriers
            h_i = colony_barriers.get(i, 0.0)
            h_j = colony_barriers.get(j, 0.0)
            h_k = colony_barriers.get(k, 0.0)
        elif self.cbf_registry is not None:
            # Compute barriers from states
            if isinstance(colony_states, dict):
                # Convert dict[str, Any] to tensor [7, state_dim]
                state_list = []
                for idx in range(7):
                    if idx in colony_states:
                        state_list.append(colony_states[idx])
                    else:
                        # Missing state - use zeros
                        state_dim = next(iter(colony_states.values())).shape[-1]
                        state_list.append(torch.zeros(state_dim))
                x_all = torch.stack(state_list).unsqueeze(0)  # [1, 7, state_dim]
            else:
                # Already tensor [B, 7, state_dim] or [7, state_dim]
                if colony_states.dim() == 2:
                    x_all = colony_states.unsqueeze(0)  # [1, 7, state_dim]
                else:
                    x_all = colony_states

            # Compute barriers for all colonies
            h_all = self.cbf_registry(x_all)  # [B, 7]
            h_i = h_all[0, i].item()
            h_j = h_all[0, j].item()
            h_k = h_all[0, k].item()
        else:
            raise ValueError("Either colony_barriers or cbf_registry must be provided")

        # Default shared resources
        if shared_resources is None:
            shared_resources = {"memory": 0.5, "compute": 0.5}

        # Compose pairwise: i × j → k
        # Check: (i, j) composition and result k
        h_ij = compose_fano_barriers(
            h_A=h_i,
            h_B=h_j,
            shared_resources=shared_resources,
            fano_line=line_id,
            resource_thresholds=self.resource_thresholds,
        )

        # Full line barrier: min(h_ij, h_k)
        # Both the composition (i×j) and result (k) must be safe
        h_line = min(h_ij, h_k)

        return h_line

    def check_all_lines(
        self,
        colony_states: dict[int, torch.Tensor] | torch.Tensor,
        shared_resources: dict[str, float] | None = None,
        colony_barriers: dict[int, float] | None = None,
    ) -> dict[int, float]:
        """Check all 7 Fano lines for safety.

        Args:
            colony_states: Colony states (dict[str, Any] or tensor)
            shared_resources: Dict of resource utilization
            colony_barriers: Optional pre-computed barriers

        Returns:
            Dict mapping line_id → h_line for all 7 lines
        """
        results = {}

        for line_id in range(7):
            h_line = self.check_line(
                line_id=line_id,
                colony_states=colony_states,
                shared_resources=shared_resources,
                colony_barriers=colony_barriers,
            )
            results[line_id] = h_line

        return results

    def get_unsafe_lines(
        self,
        colony_states: dict[int, torch.Tensor] | torch.Tensor,
        shared_resources: dict[str, float] | None = None,
        threshold: float = 0.0,
        colony_barriers: dict[int, float] | None = None,
    ) -> list[tuple[int, float]]:
        """Get list[Any] of unsafe Fano lines.

        Args:
            colony_states: Colony states
            shared_resources: Resource utilization
            threshold: Safety threshold (default: 0.0)
            colony_barriers: Optional pre-computed barriers

        Returns:
            List of (line_id, h_line) for lines where h_line < threshold
        """
        all_results = self.check_all_lines(colony_states, shared_resources, colony_barriers)

        unsafe = [
            (line_id, h_line) for line_id, h_line in all_results.items() if h_line < threshold
        ]

        return unsafe

    def verify_compositional_safety(
        self,
        colony_states: dict[int, torch.Tensor] | torch.Tensor,
        shared_resources: dict[str, float] | None = None,
        colony_barriers: dict[int, float] | None = None,
    ) -> dict[str, Any]:
        """Comprehensive safety verification across all Fano lines.

        Args:
            colony_states: Colony states
            shared_resources: Resource utilization
            colony_barriers: Optional pre-computed barriers

        Returns:
            Verification report with:
                - all_safe: bool
                - unsafe_lines: list[Any] of (line_id, h_line)
                - min_barrier: float (most restrictive)
                - per_line_barriers: dict[str, Any]
                - violations: detailed violation info
        """
        # Check all lines
        per_line = self.check_all_lines(colony_states, shared_resources, colony_barriers)

        # Find unsafe lines
        unsafe_lines = [(line_id, h_line) for line_id, h_line in per_line.items() if h_line < 0.0]

        # Minimum barrier (most restrictive)
        min_barrier = min(per_line.values())

        # Build violation details
        violations = []
        for line_id, h_line in unsafe_lines:
            i, j, k = FANO_LINES_0IDX[line_id]
            violations.append(
                {
                    "line_id": line_id,
                    "colonies": [i, j, k],
                    "barrier": h_line,
                    "fano_line_1idx": FANO_LINES[line_id],  # 1-indexed
                }
            )

        return {
            "all_safe": len(unsafe_lines) == 0,
            "unsafe_lines": unsafe_lines,
            "min_barrier": min_barrier,
            "max_barrier": max(per_line.values()),
            "mean_barrier": sum(per_line.values()) / len(per_line),
            "per_line_barriers": per_line,
            "violations": violations,
            "num_violations": len(violations),
        }


# =============================================================================
# INTEGRATION WITH FANO ACTION ROUTER
# =============================================================================


def check_fano_routing_safety(
    routing_result: Any,  # RoutingResult from FanoActionRouter
    colony_states: torch.Tensor,
    shared_resources: dict[str, float] | None = None,
    cbf_registry: FanoDecentralizedCBF | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Check safety of a FanoActionRouter routing decision.

    Verifies that the routed colonies are safe to execute together.

    Args:
        routing_result: RoutingResult from FanoActionRouter.route()
        colony_states: Current colony states [7, state_dim] or [B, 7, state_dim]
        shared_resources: Resource utilization dict[str, Any]
        cbf_registry: DecentralizedCBF for barrier computation

    Returns:
        is_safe: bool indicating if routing is safe
        info: Dict with barrier values and diagnostics
    """
    from kagami.core.unified_agents.fano_action_router import ActionMode

    mode = routing_result.mode

    # Simple case: single colony
    if mode == ActionMode.SINGLE:
        # Just check single colony barrier
        colony_idx = routing_result.actions[0].colony_idx
        if cbf_registry is not None:
            if colony_states.dim() == 2:
                x_all = colony_states.unsqueeze(0)  # [1, 7, state_dim]
            else:
                x_all = colony_states
            h_all = cbf_registry(x_all)  # [B, 7]
            h_colony = h_all[0, colony_idx].item()
        else:
            h_colony = 0.5  # Assume safe if no registry

        return h_colony >= 0.0, {"h_colony": h_colony, "colony_idx": colony_idx}

    # Fano line composition
    elif mode == ActionMode.FANO_LINE:
        if routing_result.fano_line is None:
            return True, {"mode": "fano", "status": "no_line_specified"}

        # Extract line index from fano_line tuple[Any, ...]
        # routing_result.fano_line is (primary, partner, result) tuple[Any, ...]
        # Need to find which of the 7 lines this corresponds to
        line_tuple = tuple(sorted(routing_result.fano_line))
        line_id = None
        for idx, (i, j, k) in enumerate(FANO_LINES_0IDX):
            if tuple(sorted([i, j, k])) == line_tuple:
                line_id = idx
                break

        if line_id is None:
            logger.warning(
                f"Invalid fano_line tuple[Any, ...] {routing_result.fano_line}, not a valid Fano line"
            )
            return False, {"error": "invalid_fano_line"}

        # Check line safety
        checker = FanoCompositionChecker(cbf_registry=cbf_registry)
        h_line = checker.check_line(
            line_id=line_id,
            colony_states=colony_states,
            shared_resources=shared_resources,
        )

        return h_line >= 0.0, {
            "h_line": h_line,
            "line_id": line_id,
            "fano_line": routing_result.fano_line,
        }

    # All colonies
    elif mode == ActionMode.ALL_COLONIES:
        # Check all Fano lines
        checker = FanoCompositionChecker(cbf_registry=cbf_registry)
        verification = checker.verify_compositional_safety(
            colony_states=colony_states,
            shared_resources=shared_resources,
        )

        return verification["all_safe"], verification

    else:
        return True, {"mode": str(mode), "status": "unknown"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DEFAULT_RESOURCE_THRESHOLDS",
    "FANO_LINES_0IDX",
    "CompositionBarrierResult",
    "FanoCompositionChecker",
    "check_fano_routing_safety",
    "compose_fano_barriers",
    "compose_fano_barriers_detailed",
    "compute_shared_resource_barrier",
]
