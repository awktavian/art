"""Fano Neighbor Verification for Byzantine Consensus.

Each colony verifies its 6 Fano neighbors' proposals before consensus.
Byzantine quorum: 4/6 neighbors must be valid (tolerates 2 faulty neighbors).

FANO PLANE STRUCTURE:
=====================
7 colonies, each connected to exactly 6 others via Fano lines.
Each colony verifies:
1. CBF safety: h(x) >= 0
2. Fano compatibility: Actions compose via valid Fano lines
3. Lease validity: etcd lease is active

INTEGRATION:
============
Works with KagamiConsensus in kagami_consensus.py.
Provides decentralized verification layer before consensus aggregation.

Created: December 15, 2025
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
import time
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

# Third-party imports
import torch

# Local imports
from kagami.core.safety.decentralized_cbf import FANO_NEIGHBORS

logger = logging.getLogger(__name__)

# Import Fano neighbor structure from canonical source

# Import consensus coordination structures

# Prometheus metrics (module-level, initialized lazily)
_verification_duration: Any = None
_verification_failures: Any = None
_neighbor_validity: Any = None

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ColonyConsensusState:
    """State snapshot for a single colony's consensus proposal.

    This represents a colony's current state for Byzantine verification,
    including its RSSM latent state, safety barrier, and proposed action.
    """

    colony_id: int  # 0-6
    z_state: torch.Tensor  # [14] RSSM latent state
    h_value: float  # CBF barrier value (must be >= 0)
    proposed_action: VerificationAction  # Action this colony proposes
    lease_id: int  # etcd lease for leader election
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Validate state on construction."""
        if not 0 <= self.colony_id <= 6:
            raise ValueError(f"Invalid colony_id: {self.colony_id} (must be 0-6)")
        if self.z_state.shape != (14,):
            raise ValueError(f"Invalid z_state shape: {self.z_state.shape} (expected [14])")


@dataclass
class VerificationAction:
    """Action proposed by a colony for Byzantine verification.

    Minimal structure for verification. Full action details in fano_action_router.py.
    See also: kagami.core.unified_agents.fano_action_router.ColonyAction (canonical)
    """

    colony_id: int  # 0-6
    action_type: str  # "route", "execute", "verify", etc.
    fano_line: tuple[int, int, int] | None = None  # Fano line if composition
    routing_bias: dict[int, float] = field(
        default_factory=dict[str, Any]
    )  # Target colony affinities


@dataclass
class NeighborVerificationResult:
    """Result of verifying a colony's 6 neighbors."""

    colony_id: int  # Colony doing verification
    neighbor_validities: dict[int, bool]  # neighbor_id → is_valid
    quorum_achieved: bool  # At least 4/6 neighbors valid
    cbf_violations: list[int] = field(default_factory=list[Any])  # Colonies with h < 0
    lease_failures: list[int] = field(default_factory=list[Any])  # Colonies with invalid lease
    fano_incompatibilities: list[int] = field(default_factory=list[Any])  # Incompatible actions
    timestamp: float = field(default_factory=time.time)

    @property
    def valid_neighbor_count(self) -> int:
        """Count of valid neighbors."""
        return sum(1 for valid in self.neighbor_validities.values() if valid)

    @property
    def invalid_neighbors(self) -> list[int]:
        """List of invalid neighbor IDs."""
        return [nid for nid, valid in self.neighbor_validities.items() if not valid]


# =============================================================================
# VERIFICATION LOGIC
# =============================================================================


class FanoNeighborVerifier:
    """Verifies colony proposals against Fano neighbors.

    Each colony independently verifies its 6 neighbors' proposals.
    Byzantine quorum: 4/6 valid neighbors required.

    VERIFICATION CHECKS:
    1. CBF safety: h(x) >= cbf_threshold
    2. Fano compatibility: Actions follow valid Fano lines
    3. Lease validity: etcd lease is active

    METRICS:
    - verification_duration: Time to verify all neighbors
    - verification_failures: Count of failed verifications by type
    - neighbor_validity: Per-colony validity rate
    """

    def __init__(
        self,
        cbf_threshold: float = 0.0,
        quorum_required: int = 4,
        enable_metrics: bool = True,
    ):
        """Initialize Fano neighbor verifier.

        Args:
            cbf_threshold: Minimum CBF value for safety (h >= threshold)
            quorum_required: Minimum valid neighbors (4/6 for Byzantine tolerance)
            enable_metrics: Enable Prometheus metrics
        """
        if quorum_required < 1 or quorum_required > 6:
            raise ValueError(f"quorum_required must be 1-6, got {quorum_required}")

        self.cbf_threshold = cbf_threshold
        self.quorum_required = quorum_required
        self.enable_metrics = enable_metrics

        # Validate Fano neighbor structure
        if len(FANO_NEIGHBORS) != 7:
            raise RuntimeError(f"FANO_NEIGHBORS must have 7 colonies, got {len(FANO_NEIGHBORS)}")

        for colony_id, neighbors in FANO_NEIGHBORS.items():
            if len(neighbors) != 6:
                raise RuntimeError(f"Colony {colony_id} has {len(neighbors)} neighbors, expected 6")

        logger.info(
            f"✅ FanoNeighborVerifier initialized: "
            f"cbf_threshold={cbf_threshold}, quorum={quorum_required}/6"
        )

    async def verify_fano_neighbors(
        self,
        proposals: list[ColonyConsensusState],
        etcd_client: Any,
    ) -> dict[int, NeighborVerificationResult]:
        """Each colony verifies its 6 Fano neighbors' proposals.

        Performs parallel verification for all 7 colonies.
        Each colony checks:
        1. CBF constraint: h(x) >= threshold
        2. Fano compatibility: Actions compose via valid Fano lines
        3. Lease validity: etcd lease is active

        Args:
            proposals: List of 7 proposals (one per colony)
            etcd_client: EtcdClient or etcd3.Etcd3Client for lease checks

        Returns:
            Dict mapping colony_id → NeighborVerificationResult

        Raises:
            ValueError: If proposals list[Any] is not length 7
        """
        if len(proposals) != 7:
            raise ValueError(f"Expected 7 proposals, got {len(proposals)}")

        start_time = time.time()

        # Build proposal lookup
        proposal_map = {p.colony_id: p for p in proposals}

        # Verify all colonies in parallel
        verification_tasks = [
            self._verify_colony_neighbors(
                colony_id=colony_id,
                proposal_map=proposal_map,
                etcd_client=etcd_client,
            )
            for colony_id in range(7)
        ]

        results = await asyncio.gather(*verification_tasks)
        result_map = {r.colony_id: r for r in results}

        # Record metrics
        duration = time.time() - start_time
        self._record_metrics(result_map, duration)

        logger.debug(f"Verified Fano neighbors for 7 colonies in {duration * 1000:.1f}ms")

        return result_map

    async def _verify_colony_neighbors(
        self,
        colony_id: int,
        proposal_map: dict[int, ColonyConsensusState],
        etcd_client: Any,
    ) -> NeighborVerificationResult:
        """Verify neighbors for a single colony.

        Args:
            colony_id: Colony performing verification
            proposal_map: Map of colony_id → proposal
            etcd_client: etcd client for lease checks

        Returns:
            NeighborVerificationResult for this colony
        """
        neighbor_ids = FANO_NEIGHBORS[colony_id]
        neighbor_validities: dict[int, bool] = {}

        cbf_violations: list[int] = []
        lease_failures: list[int] = []
        fano_incompatibilities: list[int] = []

        # Check each neighbor
        for neighbor_id in neighbor_ids:
            neighbor_proposal = proposal_map.get(neighbor_id)

            if neighbor_proposal is None:
                # Missing proposal → invalid
                neighbor_validities[neighbor_id] = False
                continue

            # Check 1: CBF safety
            cbf_valid = await self._check_cbf_constraint(neighbor_proposal)
            if not cbf_valid:
                cbf_violations.append(neighbor_id)

            # Check 2: Fano compatibility
            fano_valid = await self._check_fano_compatibility(
                source_id=colony_id,
                target_proposal=neighbor_proposal,
                proposal_map=proposal_map,
            )
            if not fano_valid:
                fano_incompatibilities.append(neighbor_id)

            # Check 3: Lease validity
            lease_valid = await self._check_lease_validity(neighbor_proposal, etcd_client)
            if not lease_valid:
                lease_failures.append(neighbor_id)

            # Neighbor is valid if all checks pass
            neighbor_validities[neighbor_id] = cbf_valid and fano_valid and lease_valid

        # Byzantine quorum: 4/6 neighbors valid
        valid_count = sum(1 for valid in neighbor_validities.values() if valid)
        quorum_achieved = valid_count >= self.quorum_required

        return NeighborVerificationResult(
            colony_id=colony_id,
            neighbor_validities=neighbor_validities,
            quorum_achieved=quorum_achieved,
            cbf_violations=cbf_violations,
            lease_failures=lease_failures,
            fano_incompatibilities=fano_incompatibilities,
        )

    async def _check_cbf_constraint(
        self,
        proposal: ColonyConsensusState,
    ) -> bool:
        """Check if proposal satisfies CBF safety constraint.

        Args:
            proposal: Colony proposal to check

        Returns:
            True if h(x) >= threshold
        """
        return proposal.h_value >= self.cbf_threshold

    async def _check_fano_compatibility(
        self,
        source_id: int,
        target_proposal: ColonyConsensusState,
        proposal_map: dict[int, ColonyConsensusState],
    ) -> bool:
        """Check if target's action is Fano-compatible with source.

        Verifies that if target proposes a Fano composition, it follows
        valid Fano line structure: (a, b, c) where a × b = c.

        Args:
            source_id: Colony performing verification
            target_proposal: Neighbor's proposal to verify
            proposal_map: All proposals for context

        Returns:
            True if action is Fano-compatible
        """
        target_action = target_proposal.proposed_action

        # If no Fano line specified, check routing biases
        if target_action.fano_line is None:
            # Single-colony action: check if target routes to source
            # (indicates they want to collaborate)
            if source_id in target_action.routing_bias:
                # Target wants to work with source → compatible
                return True

            # No routing bias toward source → still compatible
            # (target may be independent, which is fine)
            return True

        # Fano line specified: verify it's a valid Fano line
        fano_line = target_action.fano_line
        if len(fano_line) != 3:
            logger.warning(  # type: ignore[unreachable]
                f"Invalid Fano line from colony {target_proposal.colony_id}: {fano_line}"
            )
            return False

        # Check if this Fano line is valid
        from kagami_math.fano_plane import get_fano_lines_zero_indexed

        valid_lines = get_fano_lines_zero_indexed()

        # Normalize line (sort for comparison)
        normalized_line = tuple(sorted(fano_line))

        for valid_line in valid_lines:
            if tuple(sorted(valid_line)) == normalized_line:
                # Valid Fano line
                return True

        logger.warning(
            f"Colony {target_proposal.colony_id} proposed invalid Fano line: {fano_line}"
        )
        return False

    async def _check_lease_validity(
        self,
        proposal: ColonyConsensusState,
        etcd_client: Any,
    ) -> bool:
        """Check if proposal's etcd lease is still valid.

        Args:
            proposal: Colony proposal with lease_id
            etcd_client: etcd client instance

        Returns:
            True if lease is valid and not expired
        """
        try:
            # Use etcd_operation context manager from etcd_client module
            from kagami.core.consensus.etcd_client import etcd_operation

            with etcd_operation("check_lease") as client:
                # Check lease TTL using get_lease_info or time_to_live
                loop = asyncio.get_running_loop()

                # Try multiple API methods (etcd3 API varies)
                ttl_response = None

                # Method 1: time_to_live (etcd3-py)
                if hasattr(client, "time_to_live"):
                    ttl_response = await loop.run_in_executor(
                        None,
                        client.time_to_live,
                        proposal.lease_id,
                    )
                # Method 2: get_lease_info (python-etcd3)
                elif hasattr(client, "get_lease_info"):
                    ttl_response = await loop.run_in_executor(
                        None,
                        client.get_lease_info,
                        proposal.lease_id,
                    )
                else:
                    # No lease API available, assume valid
                    logger.debug(
                        f"etcd client has no lease checking API, assuming valid "
                        f"for colony {proposal.colony_id}"
                    )
                    return True

                # Lease is valid if TTL > 0
                if ttl_response is not None:
                    if hasattr(ttl_response, "TTL"):
                        return ttl_response.TTL > 0  # type: ignore[no-any-return]
                    elif hasattr(ttl_response, "ttl"):
                        return ttl_response.ttl > 0  # type: ignore[no-any-return]
                    elif isinstance(ttl_response, int | float):
                        return ttl_response > 0

                # Fallback: assume valid if no error
                return True

        except Exception as e:
            logger.debug(
                f"Lease check failed for colony {proposal.colony_id} "
                f"(lease={proposal.lease_id}): {e}"
            )
            # On error, be conservative: treat as invalid
            return False

    def _record_metrics(
        self,
        results: dict[int, NeighborVerificationResult],
        duration: float,
    ) -> None:
        """Record Prometheus metrics for verification.

        Args:
            results: Verification results for all colonies
            duration: Total verification duration in seconds
        """
        if not self.enable_metrics:
            return

        try:
            global _verification_duration, _verification_failures, _neighbor_validity
            from kagami_observability.metrics import REGISTRY, Counter, Gauge, Histogram

            # Initialize metrics lazily
            if _verification_duration is None:
                _verification_duration = Histogram(
                    "kagami_fano_verification_duration_seconds",
                    "Duration of Fano neighbor verification",
                    registry=REGISTRY,
                )
                _verification_failures = Counter(
                    "kagami_fano_verification_failures_total",
                    "Count of verification failures by type",
                    ["failure_type"],
                    registry=REGISTRY,
                )
                _neighbor_validity = Gauge(
                    "kagami_fano_neighbor_validity",
                    "Neighbor validity rate per colony",
                    ["colony_id"],
                    registry=REGISTRY,
                )

            # Record duration
            _verification_duration.observe(duration)

            # Record per-colony metrics
            for colony_id, result in results.items():
                # Validity rate for this colony's neighbors
                validity_rate = result.valid_neighbor_count / 6.0
                _neighbor_validity.labels(colony_id=str(colony_id)).set(validity_rate)

                # Count failure types
                for _ in result.cbf_violations:
                    _verification_failures.labels(failure_type="cbf_violation").inc()
                for _ in result.lease_failures:
                    _verification_failures.labels(failure_type="lease_invalid").inc()
                for _ in result.fano_incompatibilities:
                    _verification_failures.labels(failure_type="fano_incompatible").inc()

        except Exception as e:
            logger.debug(f"Failed to record verification metrics: {e}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def check_global_quorum(
    verification_results: dict[int, NeighborVerificationResult],
    quorum_threshold: float = 0.714,  # 5/7 colonies (Byzantine)
) -> bool:
    """Check if global Byzantine quorum is achieved.

    For consensus to proceed, at least 5/7 colonies must achieve
    their local quorums (4/6 neighbors valid).

    Args:
        verification_results: Results for all colonies
        quorum_threshold: Minimum fraction of colonies with quorum (5/7 ≈ 0.714)

    Returns:
        True if global quorum achieved
    """
    if len(verification_results) != 7:
        return False

    colonies_with_quorum = sum(
        1 for result in verification_results.values() if result.quorum_achieved
    )

    return colonies_with_quorum >= (7 * quorum_threshold)


def get_faulty_colonies(
    verification_results: dict[int, NeighborVerificationResult],
) -> set[int]:
    """Identify colonies marked as faulty by majority of neighbors.

    A colony is faulty if > 3 neighbors (majority of 6) mark it invalid.

    Args:
        verification_results: Results for all colonies

    Returns:
        Set of colony IDs identified as faulty
    """
    # Count how many neighbors marked each colony as invalid
    invalid_counts: dict[int, int] = dict[str, Any].fromkeys(range(7), 0)

    for _verifier_id, result in verification_results.items():
        for invalid_neighbor in result.invalid_neighbors:
            invalid_counts[invalid_neighbor] += 1

    # Colony is faulty if > 3 neighbors (majority) marked it invalid
    faulty = {colony_id for colony_id, count in invalid_counts.items() if count > 3}

    if faulty:
        logger.warning(f"Byzantine faulty colonies detected: {sorted(faulty)}")

    return faulty


# =============================================================================
# FACTORY
# =============================================================================


def create_fano_verifier(
    cbf_threshold: float = 0.0,
    quorum_required: int = 4,
    enable_metrics: bool = True,
) -> FanoNeighborVerifier:
    """Create Fano neighbor verifier with Byzantine tolerance.

    Args:
        cbf_threshold: Minimum CBF safety margin
        quorum_required: Number of valid neighbors required (default 4/6)
        enable_metrics: Enable Prometheus metrics

    Returns:
        FanoNeighborVerifier instance
    """
    return FanoNeighborVerifier(
        cbf_threshold=cbf_threshold,
        quorum_required=quorum_required,
        enable_metrics=enable_metrics,
    )


# Alias for backward compatibility with tests
ColonyAction = VerificationAction

__all__ = [
    "FANO_NEIGHBORS",
    "ColonyAction",  # Alias for VerificationAction
    "ColonyConsensusState",
    "FanoNeighborVerifier",
    "NeighborVerificationResult",
    "VerificationAction",
    "check_global_quorum",
    "create_fano_verifier",
    "get_faulty_colonies",
]
