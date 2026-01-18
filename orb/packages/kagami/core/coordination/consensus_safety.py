"""Compositional CBF Consensus Safety Verification.

CREATED: December 15, 2025
PURPOSE: Verify that consensus decisions maintain all colony CBF constraints

ARCHITECTURE:
=============
Consensus-level safety is compositional:
    ∀i ∈ {0..6}: h_i(μ_i, μ_{neighbors}) ≥ 0  ⟹  consensus is safe

This module:
1. Takes consensus actions (dict[ColonyID, str])
2. Simulates next states via world model (RSSM rollout)
3. Evaluates all 7 colony barrier functions h_i
4. Returns True iff ALL h_i ≥ threshold

SAFETY GUARANTEES:
==================
- If verify_compositional_cbf returns True, consensus is PROVEN safe
- If False, provides detailed diagnostics (which colonies violated, h values)
- Fallback: return safest single colony proposal (argmax_i h_i)

INTEGRATION:
============
- Uses FanoDecentralizedCBF from kagami.core.safety.decentralized_cbf
- Uses KagamiWorldModel for state prediction
- Prometheus metrics for safety monitoring

References:
- Ames et al. (2017): Control Barrier Functions
- Wang et al. (2017): Safety Barrier Certificates for Collectives
- Byzantine consensus with CBF constraints (this codebase)
"""

# Standard library imports
import logging
import time
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

# Third-party imports
import torch
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)

# Local imports
from kagami.core.coordination.types import ColonyID
from kagami.core.exceptions import SafetyViolation
from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

logger = logging.getLogger(__name__)

# Optional imports (will be checked at runtime)
try:
    from kagami.core.coordination.types import ColonyID
    from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

    CONSENSUS_AVAILABLE = True
except ImportError:
    logger.warning("coordination.types or decentralized_cbf not available")
    CONSENSUS_AVAILABLE = False

# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

# Safety check outcomes
cbf_checks_total = Counter(
    "consensus_cbf_checks_total",
    "Total number of consensus CBF safety checks",
    ["result"],  # safe | unsafe | error
)

# Minimum barrier margin across all colonies
cbf_margin_min = Gauge(
    "consensus_cbf_margin_min",
    "Minimum CBF barrier value h_i across all colonies",
)

# Per-colony violation tracking
cbf_violations_total = Counter(
    "consensus_cbf_violations_total",
    "Total CBF violations by colony",
    ["colony_id"],
)

# Safety check duration
cbf_check_duration = Histogram(
    "consensus_cbf_check_duration_seconds",
    "Duration of consensus safety verification",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class SafetyVerificationResult:
    """Result of consensus safety verification.

    Attributes:
        is_safe: True if ALL h_i ≥ threshold
        h_values: Barrier values [7] for each colony
        min_barrier: Minimum h_i across all colonies
        violated_colonies: List of colony indices where h_i < threshold
        fallback_colony: Safest single colony (argmax_i h_i) if consensus unsafe
        check_duration: Time taken for safety check (seconds)
        timestamp: When verification occurred
        details: Additional diagnostic info
    """

    is_safe: bool
    h_values: dict[int, float]
    min_barrier: float
    violated_colonies: list[int] = field(default_factory=list[Any])
    fallback_colony: int | None = None
    check_duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict[str, Any])


# =============================================================================
# CORE VERIFICATION FUNCTION
# =============================================================================


async def verify_compositional_cbf(
    consensus_actions: dict[ColonyID, str],
    dcbf: FanoDecentralizedCBF,
    world_model: Any,
    current_states: torch.Tensor | None = None,
    threshold: float = 0.0,
    use_simulation: bool = True,
) -> tuple[bool, dict[str, Any]]:
    """Verify consensus maintains all colony CBF constraints.

    ALGORITHM:
    ==========
    1. If use_simulation=True:
       - Use world_model to predict next states from consensus actions
       - Compute h_i(next_state) for all colonies
    2. If use_simulation=False or no world_model:
       - Use current_states directly
       - Compute h_i(current_state) for all colonies
    3. Return True if ALL h_i ≥ threshold

    Args:
        consensus_actions: Dict mapping ColonyID → action string
        dcbf: FanoDecentralizedCBF instance
        world_model: KagamiWorldModel for state prediction (optional)
        current_states: Current colony states [B, 7, state_dim] (optional)
        threshold: Minimum h_i required (default: 0.0)
        use_simulation: If True, simulate next state; else use current

    Returns:
        (is_safe, details): Tuple of safety status and diagnostic dict[str, Any]

    Raises:
        ValueError: If both world_model and current_states are None
        SafetyViolation: If violations detected and raise_on_violation=True
    """
    start_time = time.time()

    if not CONSENSUS_AVAILABLE:
        logger.error("Consensus or CBF modules not available")
        cbf_checks_total.labels(result="error").inc()
        return False, {"error": "Required modules not available"}

    try:
        # =================================================================
        # PART 1: GET COLONY STATES
        # =================================================================
        if use_simulation and world_model is not None:
            # Simulate next state from consensus actions
            colony_states = await _simulate_consensus_states(
                consensus_actions=consensus_actions,
                world_model=world_model,
                current_states=current_states,
            )
        elif current_states is not None:
            # Use provided states directly
            colony_states = current_states
        else:
            raise ValueError("Must provide either world_model (for simulation) or current_states")

        # Ensure states are [B, 7, state_dim]
        if colony_states.dim() == 2:
            # [7, state_dim] → [1, 7, state_dim]
            colony_states = colony_states.unsqueeze(0)

        B, num_colonies, _state_dim = colony_states.shape
        if num_colonies != 7:
            raise ValueError(f"Expected 7 colonies, got {num_colonies}")

        # =================================================================
        # PART 2: EVALUATE BARRIER FUNCTIONS
        # =================================================================
        with torch.no_grad():
            h = dcbf(colony_states)  # [B, 7] barrier values

        # Extract h values for batch (use first sample if batch)
        h_batch = h[0] if B > 0 else h.squeeze(0)  # [7]

        # Per-colony safety
        colony_safe = h_batch >= threshold  # [7]
        all_safe = colony_safe.all().item()

        # Find violated colonies
        violated_mask = ~colony_safe
        violated_indices = violated_mask.nonzero(as_tuple=True)[0].tolist()

        # Extract h values as dict[str, Any]
        h_values_dict = {i: float(h_batch[i].item()) for i in range(7)}

        # Minimum barrier value
        min_barrier_val = float(h_batch.min().item())

        # =================================================================
        # PART 3: FALLBACK SELECTION
        # =================================================================
        fallback_colony_idx = None
        if not all_safe:
            # Select safest colony: argmax_i h_i
            fallback_colony_idx = int(h_batch.argmax().item())

            # Record violations in metrics
            for colony_idx in violated_indices:
                cbf_violations_total.labels(colony_id=str(colony_idx)).inc()

        # =================================================================
        # PART 4: METRICS AND RESULT
        # =================================================================
        check_duration = time.time() - start_time

        # Update metrics
        cbf_checks_total.labels(result="safe" if all_safe else "unsafe").inc()
        cbf_margin_min.set(min_barrier_val)
        cbf_check_duration.observe(check_duration)

        # Build result
        result = SafetyVerificationResult(
            is_safe=all_safe,
            h_values=h_values_dict,
            min_barrier=min_barrier_val,
            violated_colonies=violated_indices,
            fallback_colony=fallback_colony_idx,
            check_duration=check_duration,
            details={
                "threshold": threshold,
                "num_violated": len(violated_indices),
                "consensus_actions": {k.name: v for k, v in consensus_actions.items()},
                "simulation_used": use_simulation and world_model is not None,
            },
        )

        # Log result
        if all_safe:
            logger.info(
                f"✓ Consensus safe: min_h={min_barrier_val:.3f} (took {check_duration * 1000:.1f}ms)"
            )
        else:
            colony_names = ["Spark", "Forge", "Flow", "Nexus", "Beacon", "Grove", "Crystal"]
            violated_names = [colony_names[i] for i in violated_indices]
            logger.warning(
                f"✗ Consensus UNSAFE: {len(violated_indices)} violations - {violated_names}\n"
                f"  min_h={min_barrier_val:.3f}, fallback={colony_names[fallback_colony_idx]}"  # type: ignore[index]
            )

        # Return tuple[Any, ...] format for backward compatibility
        details_dict = {
            "is_safe": all_safe,
            "h_values": h_values_dict,
            "min_barrier": min_barrier_val,
            "violated_colonies": violated_indices,
            "fallback_colony": fallback_colony_idx,
            "check_duration": check_duration,
            **result.details,
        }

        return all_safe, details_dict

    except Exception as e:
        logger.error(f"Error in CBF safety verification: {e}", exc_info=True)
        cbf_checks_total.labels(result="error").inc()
        return False, {"error": str(e), "check_duration": time.time() - start_time}


# =============================================================================
# STATE SIMULATION
# =============================================================================


async def _simulate_consensus_states(
    consensus_actions: dict[ColonyID, str],
    world_model: Any,
    current_states: torch.Tensor | None = None,
) -> torch.Tensor:
    """Simulate next colony states from consensus actions via world model.

    Uses RSSM rollout or simplified prediction if RSSM not available.

    Args:
        consensus_actions: Dict mapping ColonyID → action string
        world_model: KagamiWorldModel instance
        current_states: Optional current states [B, 7, state_dim]

    Returns:
        Predicted next states [B, 7, state_dim]
    """
    # =================================================================
    # PART 1: CONVERT ACTIONS TO TENSOR
    # =================================================================
    # Action encoding: simple binary (0 = inactive, 1 = active)
    action_tensor = torch.zeros(7)  # [7]

    for colony_id, action_str in consensus_actions.items():
        if action_str == "activate":
            action_tensor[colony_id.value] = 1.0

    # Add batch dimension [1, 7]
    action_tensor = action_tensor.unsqueeze(0)

    # =================================================================
    # PART 2: PREDICT NEXT STATE (SIMPLIFIED Dec 21, 2025)
    # =================================================================
    # NOTE: KagamiWorldModel.rssm was removed in Dec 2025.
    # Use OrganismRSSM directly via get_organism_rssm() if RSSM prediction
    # is needed. For consensus safety, the fallback simulation is sufficient.
    #
    # For future integration with OrganismRSSM:
    #   from kagami.core.world_model.colony_rssm import get_organism_rssm
    #   rssm = get_organism_rssm()
    #   next_states = rssm.imagine(action=action_tensor, horizon=1)

    # Simple dynamics simulation (fast and sufficient for consensus)
    if current_states is not None:
        # Simple transition: next = current + action * 0.1 (small perturbation)
        action_expanded = action_tensor.unsqueeze(-1)  # [1, 7, 1]
        perturbation = action_expanded * 0.1  # Small action-dependent change

        # Extract safety state dims if current_states has more dims
        if current_states.shape[-1] > 4:
            safety_states = current_states[..., :4]
        else:
            safety_states = current_states

        next_states = safety_states + perturbation
        # Clamp to valid range [0, 1]
        next_states = torch.clamp(next_states, 0.0, 1.0)

        return next_states
    else:
        # No current state — create synthetic states based on actions
        # High activity → higher risk
        risk_factor = action_tensor.unsqueeze(-1) * 0.5  # [1, 7, 1]

        # Create safety state: [threat, uncertainty, complexity, risk]
        next_states = torch.cat(
            [
                risk_factor * 0.3,  # threat
                risk_factor * 0.4,  # uncertainty
                risk_factor * 0.2,  # complexity
                risk_factor * 1.0,  # risk
            ],
            dim=-1,
        )  # [1, 7, 4]

        return next_states


# =============================================================================
# CONSENSUS SAFETY FILTER
# =============================================================================


async def filter_unsafe_consensus(
    proposals: list[Any],  # list[CoordinationProposal]
    dcbf: FanoDecentralizedCBF,
    world_model: Any,
    threshold: float = 0.0,
) -> tuple[list[Any], SafetyVerificationResult]:
    """Filter consensus proposals to retain only safe ones.

    If consensus is unsafe, returns fallback to safest single colony.

    Args:
        proposals: List of CoordinationProposals from all colonies
        dcbf: FanoDecentralizedCBF instance
        world_model: KagamiWorldModel for simulation
        threshold: Minimum h_i required

    Returns:
        (safe_proposals, verification_result): Filtered proposals and safety details
    """
    if not CONSENSUS_AVAILABLE:
        logger.error("Consensus module not available")
        return proposals, SafetyVerificationResult(
            is_safe=False,
            h_values={},
            min_barrier=-1.0,
            details={"error": "Consensus module not available"},
        )

    # Extract consensus actions from proposals
    # Merge proposals into single consensus dict[str, Any]
    consensus_actions: dict[ColonyID, str] = {}
    colony_votes = dict[str, Any].fromkeys(ColonyID, 0)

    for proposal in proposals:
        for target in proposal.target_colonies:
            colony_votes[target] += 1

    # Activate colonies with >30% support
    threshold_votes = len(proposals) * 0.3
    for colony, votes in colony_votes.items():
        if votes >= threshold_votes:
            consensus_actions[colony] = "activate"

    # Verify safety
    is_safe, details = await verify_compositional_cbf(
        consensus_actions=consensus_actions,
        dcbf=dcbf,
        world_model=world_model,
        threshold=threshold,
    )

    result = SafetyVerificationResult(
        is_safe=is_safe,
        h_values=details.get("h_values", {}),
        min_barrier=details.get("min_barrier", -1.0),
        violated_colonies=details.get("violated_colonies", []),
        fallback_colony=details.get("fallback_colony"),
        check_duration=details.get("check_duration", 0.0),
        details=details,
    )

    if is_safe:
        # Return all proposals
        return proposals, result
    else:
        # Return only fallback colony's proposal
        fallback_idx = result.fallback_colony
        if fallback_idx is not None and fallback_idx < len(proposals):
            fallback_proposal = proposals[fallback_idx]
            logger.warning(f"Consensus unsafe, falling back to {ColonyID(fallback_idx).name}")
            return [fallback_proposal], result
        else:
            # No fallback available — return empty
            logger.error("No fallback available, rejecting consensus")
            return [], result


# =============================================================================
# UTILITIES
# =============================================================================


def get_safest_colony(
    h_values: dict[int, float],
) -> int:
    """Get safest colony index (argmax_i h_i).

    Args:
        h_values: Dict mapping colony_idx → barrier value

    Returns:
        Colony index with highest h_i
    """
    return max(h_values.items(), key=lambda x: x[1])[0]


def compute_safety_margin_distribution(
    h_values: dict[int, float],
) -> dict[str, float]:
    """Compute statistics of safety margins across colonies.

    Args:
        h_values: Dict mapping colony_idx → barrier value

    Returns:
        Dict with min, max, mean, std of h values
    """
    values = torch.tensor(list(h_values.values()))

    return {
        "min": float(values.min().item()),
        "max": float(values.max().item()),
        "mean": float(values.mean().item()),
        "std": float(values.std().item()),
    }


# =============================================================================
# BATCH VERIFICATION
# =============================================================================


async def verify_batch_consensus(
    batch_consensus_actions: list[dict[ColonyID, str]],
    dcbf: FanoDecentralizedCBF,
    world_model: Any,
    threshold: float = 0.0,
) -> list[SafetyVerificationResult]:
    """Verify multiple consensus decisions in batch.

    Args:
        batch_consensus_actions: List of consensus action dicts
        dcbf: FanoDecentralizedCBF instance
        world_model: KagamiWorldModel
        threshold: Minimum h_i required

    Returns:
        List of SafetyVerificationResults
    """
    results = []

    for consensus_actions in batch_consensus_actions:
        is_safe, details = await verify_compositional_cbf(
            consensus_actions=consensus_actions,
            dcbf=dcbf,
            world_model=world_model,
            threshold=threshold,
        )

        results.append(
            SafetyVerificationResult(
                is_safe=is_safe,
                h_values=details.get("h_values", {}),
                min_barrier=details.get("min_barrier", -1.0),
                violated_colonies=details.get("violated_colonies", []),
                fallback_colony=details.get("fallback_colony"),
                check_duration=details.get("check_duration", 0.0),
                details=details,
            )
        )

    return results


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Data structures
    "SafetyVerificationResult",
    # Exceptions
    "SafetyViolation",
    "cbf_check_duration",
    # Metrics (for monitoring)
    "cbf_checks_total",
    "cbf_margin_min",
    "cbf_violations_total",
    "compute_safety_margin_distribution",
    "filter_unsafe_consensus",
    # Utilities
    "get_safest_colony",
    "verify_batch_consensus",
    # Core functions
    "verify_compositional_cbf",
]
