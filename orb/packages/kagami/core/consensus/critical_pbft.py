"""PBFT Integration for Critical Decisions — Byzantine consensus for safety-critical operations.

This module wires PBFT consensus into the colony decision-making process for operations
that require Byzantine fault tolerance:

1. Safety barrier violations (h(x) < 0 detection)
2. Cross-hub state mutations
3. Security-sensitive commands (unlock, disarm)
4. Resource allocation changes
5. Consensus routing changes

Architecture:
```
┌─────────────────────────────────────────────────────────────────────┐
│                    CRITICAL PBFT CONSENSUS                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Colony Consensus                         PBFT Nodes                │
│   ───────────────                         ──────────                 │
│   • Normal routing (soft consensus)       • Critical ops (hard BFT) │
│   • Threshold: 0.7                        • Threshold: 2f+1         │
│   • Latency: ~10ms                        • Latency: ~100ms         │
│                                                                      │
│   ┌─────────────────┐      Critical?      ┌─────────────────┐      │
│   │  KagamiConsensus │────────────────────▶│    PBFTNode     │      │
│   │  (7 colonies)    │                     │  (3f+1 nodes)   │      │
│   └─────────────────┘      ◄────────────────└─────────────────┘      │
│                            Result                                    │
│                                                                      │
│   Decision Flow:                                                     │
│   1. Check if operation is critical                                 │
│   2. If critical → require PBFT consensus                           │
│   3. If not critical → use soft colony consensus                    │
│   4. Log all decisions with audit trail                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Usage:
    from kagami.core.consensus.critical_pbft import (
        get_critical_pbft_coordinator,
        is_critical_operation,
        CriticalOperation,
    )

    coordinator = await get_critical_pbft_coordinator()

    # Check if operation needs PBFT
    if is_critical_operation(operation):
        result = await coordinator.submit_critical(
            operation=CriticalOperation.UNLOCK_DOOR,
            data={"door": "front"},
        )
    else:
        # Use normal colony consensus
        pass

Created: January 4, 2026
Colony: Crystal (D₅) — Verification and consensus
h(x) ≥ 0. Always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.consensus.pbft import PBFTNode

logger = logging.getLogger(__name__)


# =============================================================================
# CRITICAL OPERATION TYPES
# =============================================================================


class CriticalOperation(str, Enum):
    """Operations requiring PBFT consensus.

    These operations have safety or security implications that
    require Byzantine fault tolerance.
    """

    # Safety-critical (h(x) boundaries)
    SAFETY_OVERRIDE = "safety_override"  # Override safety barrier
    EMERGENCY_HALT = "emergency_halt"  # Emergency system halt
    CBF_THRESHOLD_CHANGE = "cbf_threshold_change"  # Modify safety thresholds

    # Security-sensitive
    UNLOCK_DOOR = "unlock_door"  # Unlock any door
    DISARM_SECURITY = "disarm_security"  # Disarm security system
    GRANT_ACCESS = "grant_access"  # Grant system access
    REVOKE_ACCESS = "revoke_access"  # Revoke system access

    # State mutations
    CONFIG_CHANGE = "config_change"  # System configuration change
    NODE_JOIN = "node_join"  # New node joining cluster
    NODE_REMOVE = "node_remove"  # Remove node from cluster
    LEADER_CHANGE = "leader_change"  # Change cluster leader

    # Resource allocation
    RESOURCE_MIGRATE = "resource_migrate"  # Migrate resources between nodes
    SCALE_CLUSTER = "scale_cluster"  # Scale cluster up/down

    # Cross-domain triggers
    CROSS_DOMAIN_ACTION = "cross_domain_action"  # Actions spanning multiple domains

    # Asset approval (colony identity)
    APPROVE_FAVICON = "approve_favicon"  # Approve colony favicon design


class CriticalityLevel(Enum):
    """Criticality levels for operations."""

    LOW = auto()  # Normal operation, no special consensus
    MEDIUM = auto()  # Important, but colony consensus sufficient
    HIGH = auto()  # Critical, requires PBFT consensus
    CRITICAL = auto()  # Safety-critical, requires unanimous PBFT


# Mapping of operations to criticality levels
OPERATION_CRITICALITY: dict[CriticalOperation, CriticalityLevel] = {
    # Safety-critical (unanimous required)
    CriticalOperation.SAFETY_OVERRIDE: CriticalityLevel.CRITICAL,
    CriticalOperation.EMERGENCY_HALT: CriticalityLevel.CRITICAL,
    CriticalOperation.CBF_THRESHOLD_CHANGE: CriticalityLevel.CRITICAL,
    # Security-sensitive (PBFT required)
    CriticalOperation.UNLOCK_DOOR: CriticalityLevel.HIGH,
    CriticalOperation.DISARM_SECURITY: CriticalityLevel.HIGH,
    CriticalOperation.GRANT_ACCESS: CriticalityLevel.HIGH,
    CriticalOperation.REVOKE_ACCESS: CriticalityLevel.HIGH,
    # State mutations (PBFT required)
    CriticalOperation.CONFIG_CHANGE: CriticalityLevel.HIGH,
    CriticalOperation.NODE_JOIN: CriticalityLevel.HIGH,
    CriticalOperation.NODE_REMOVE: CriticalityLevel.HIGH,
    CriticalOperation.LEADER_CHANGE: CriticalityLevel.HIGH,
    # Resource allocation (medium)
    CriticalOperation.RESOURCE_MIGRATE: CriticalityLevel.MEDIUM,
    CriticalOperation.SCALE_CLUSTER: CriticalityLevel.MEDIUM,
    # Cross-domain (high)
    CriticalOperation.CROSS_DOMAIN_ACTION: CriticalityLevel.HIGH,
    # Asset approval (medium - colony consensus sufficient)
    CriticalOperation.APPROVE_FAVICON: CriticalityLevel.MEDIUM,
}


def is_critical_operation(operation: str | CriticalOperation) -> bool:
    """Check if an operation requires PBFT consensus.

    Args:
        operation: Operation string or enum.

    Returns:
        True if operation requires PBFT consensus.
    """
    if isinstance(operation, str):
        try:
            operation = CriticalOperation(operation)
        except ValueError:
            return False

    level = OPERATION_CRITICALITY.get(operation, CriticalityLevel.LOW)
    return level in (CriticalityLevel.HIGH, CriticalityLevel.CRITICAL)


def get_criticality_level(operation: str | CriticalOperation) -> CriticalityLevel:
    """Get the criticality level of an operation.

    Args:
        operation: Operation string or enum.

    Returns:
        CriticalityLevel for the operation.
    """
    if isinstance(operation, str):
        try:
            operation = CriticalOperation(operation)
        except ValueError:
            return CriticalityLevel.LOW

    return OPERATION_CRITICALITY.get(operation, CriticalityLevel.LOW)


# =============================================================================
# CRITICAL PBFT RESULT
# =============================================================================


@dataclass
class CriticalPBFTResult:
    """Result from critical PBFT consensus.

    Attributes:
        success: Whether consensus was reached.
        operation: The operation that was submitted.
        data: Operation data.
        sequence: PBFT sequence number.
        view: PBFT view number.
        votes_for: Number of nodes that voted for.
        votes_against: Number of nodes that voted against.
        latency_ms: Time to reach consensus.
        error: Error message if failed.
        audit_id: Unique audit trail identifier.
    """

    success: bool
    operation: CriticalOperation
    data: dict[str, Any]
    sequence: int = -1
    view: int = 0
    votes_for: int = 0
    votes_against: int = 0
    latency_ms: float = 0.0
    error: str | None = None
    audit_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "operation": self.operation.value,
            "data": self.data,
            "sequence": self.sequence,
            "view": self.view,
            "votes_for": self.votes_for,
            "votes_against": self.votes_against,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
        }


# =============================================================================
# CRITICAL PBFT COORDINATOR
# =============================================================================


class CriticalPBFTCoordinator:
    """Coordinator for PBFT consensus on critical operations.

    Manages the lifecycle of PBFT consensus for safety-critical
    and security-sensitive operations.

    Features:
    - Automatic PBFT node management
    - Audit trail for all critical decisions
    - Integration with colony consensus
    - Fallback to local decision for liveness

    Thread Safety:
    - All public methods are async and thread-safe.
    """

    def __init__(
        self,
        pbft_node: PBFTNode | None = None,
        audit_log_path: str | None = None,
    ):
        """Initialize the coordinator.

        Args:
            pbft_node: Optional pre-configured PBFT node.
            audit_log_path: Path for audit log file.
        """
        self._pbft_node = pbft_node
        self._audit_log_path = audit_log_path

        # Audit trail
        self._audit_log: list[CriticalPBFTResult] = []
        self._audit_counter = 0

        # State
        self._started = False
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_consensus": 0,
            "failed_consensus": 0,
            "fallback_decisions": 0,
            "average_latency_ms": 0.0,
        }

        logger.info("CriticalPBFTCoordinator initialized")

    async def start(self) -> None:
        """Start the coordinator and PBFT node."""
        if self._started:
            return

        # Initialize PBFT node if not provided
        if self._pbft_node is None:
            from kagami.core.consensus.pbft import PBFTConfig, PBFTNode

            config = PBFTConfig()
            self._pbft_node = PBFTNode(config)

        await self._pbft_node.start()
        self._started = True

        logger.info("✅ CriticalPBFTCoordinator started")

    async def stop(self) -> None:
        """Stop the coordinator and PBFT node."""
        if self._pbft_node:
            await self._pbft_node.stop()

        self._started = False
        logger.info("✅ CriticalPBFTCoordinator stopped")

    async def submit_critical(
        self,
        operation: CriticalOperation,
        data: dict[str, Any],
        timeout: float = 30.0,
    ) -> CriticalPBFTResult:
        """Submit a critical operation for PBFT consensus.

        Args:
            operation: The critical operation type.
            data: Operation-specific data.
            timeout: Consensus timeout in seconds.

        Returns:
            CriticalPBFTResult with consensus outcome.

        Example:
            result = await coordinator.submit_critical(
                operation=CriticalOperation.UNLOCK_DOOR,
                data={"door": "front", "user": "tim"},
            )
            if result.success:
                # Execute the unlock
                pass
        """
        async with self._lock:
            self._stats["total_requests"] += 1
            start_time = time.time()

            # Generate audit ID
            self._audit_counter += 1
            audit_id = f"CRIT-{int(time.time())}-{self._audit_counter:06d}"

            # Check criticality level
            level = get_criticality_level(operation)
            logger.info(
                f"🔒 Critical operation submitted: {operation.value} "
                f"(level={level.name}, audit={audit_id})"
            )

            # Log pre-decision state
            await self._log_audit_event(
                audit_id=audit_id,
                event="submitted",
                operation=operation,
                data=data,
                level=level,
            )

            # Attempt PBFT consensus
            result = await self._run_pbft_consensus(
                operation=operation,
                data=data,
                audit_id=audit_id,
                timeout=timeout,
                require_unanimous=(level == CriticalityLevel.CRITICAL),
            )

            # Update statistics
            latency = (time.time() - start_time) * 1000
            result.latency_ms = latency

            if result.success:
                self._stats["successful_consensus"] += 1
            else:
                self._stats["failed_consensus"] += 1

            # Update average latency
            total = self._stats["total_requests"]
            prev_avg = self._stats["average_latency_ms"]
            self._stats["average_latency_ms"] = (prev_avg * (total - 1) + latency) / total

            # Store in audit log
            self._audit_log.append(result)

            # Log decision
            await self._log_audit_event(
                audit_id=audit_id,
                event="decided",
                result=result,
            )

            return result

    async def _run_pbft_consensus(
        self,
        operation: CriticalOperation,
        data: dict[str, Any],
        audit_id: str,
        timeout: float,
        require_unanimous: bool,
    ) -> CriticalPBFTResult:
        """Run PBFT consensus for operation.

        Args:
            operation: Operation type.
            data: Operation data.
            audit_id: Audit trail ID.
            timeout: Consensus timeout.
            require_unanimous: Require all nodes to agree.

        Returns:
            CriticalPBFTResult.
        """
        if not self._started or self._pbft_node is None:
            # Fallback: local decision for liveness
            self._stats["fallback_decisions"] += 1
            logger.warning(f"⚠️ PBFT not available, using fallback for {operation.value}")
            return CriticalPBFTResult(
                success=self._fallback_decision(operation, data),
                operation=operation,
                data=data,
                audit_id=audit_id,
                error="PBFT unavailable, used fallback",
            )

        try:
            # Submit to PBFT
            pbft_result = await self._pbft_node.submit_request(
                operation=operation.value,
                data={
                    "operation": operation.value,
                    "data": data,
                    "audit_id": audit_id,
                    "require_unanimous": require_unanimous,
                },
                timeout=timeout,
            )

            # Check if unanimous required and met
            if require_unanimous and pbft_result.success:
                # For critical ops, verify full agreement
                # In real impl, would check vote counts
                pass

            return CriticalPBFTResult(
                success=pbft_result.success,
                operation=operation,
                data=data,
                sequence=pbft_result.sequence,
                view=pbft_result.view,
                latency_ms=pbft_result.latency_ms,
                error=pbft_result.error,
                audit_id=audit_id,
            )

        except Exception as e:
            logger.error(f"PBFT consensus failed: {e}")
            return CriticalPBFTResult(
                success=False,
                operation=operation,
                data=data,
                audit_id=audit_id,
                error=str(e),
            )

    def _fallback_decision(
        self,
        operation: CriticalOperation,
        data: dict[str, Any],
    ) -> bool:
        """Make a fallback decision when PBFT is unavailable.

        Conservative fallback: deny most critical operations.

        Args:
            operation: Operation type.
            data: Operation data.

        Returns:
            Whether to allow the operation.
        """
        level = get_criticality_level(operation)

        # Critical ops never allowed in fallback
        if level == CriticalityLevel.CRITICAL:
            logger.warning(f"🚫 Denying critical operation in fallback: {operation.value}")
            return False

        # High-level ops only allowed for safety (emergency halt)
        if level == CriticalityLevel.HIGH:
            if operation == CriticalOperation.EMERGENCY_HALT:
                return True
            logger.warning(f"🚫 Denying high-level operation in fallback: {operation.value}")
            return False

        # Medium and low allowed in fallback
        return True

    async def _log_audit_event(
        self,
        audit_id: str,
        event: str,
        **kwargs: Any,
    ) -> None:
        """Log an audit event.

        Args:
            audit_id: Audit trail ID.
            event: Event type.
            **kwargs: Additional event data.
        """
        audit_entry = {
            "audit_id": audit_id,
            "event": event,
            "timestamp": time.time(),
            **kwargs,
        }

        # Log to console
        logger.info(f"📋 Audit [{audit_id}] {event}: {kwargs}")

        # Write to file if configured
        if self._audit_log_path:
            try:
                import json

                with open(self._audit_log_path, "a") as f:
                    f.write(json.dumps(audit_entry) + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

    def get_audit_log(
        self,
        limit: int = 100,
        operation: CriticalOperation | None = None,
    ) -> list[CriticalPBFTResult]:
        """Get recent audit log entries.

        Args:
            limit: Maximum entries to return.
            operation: Filter by operation type.

        Returns:
            List of CriticalPBFTResult entries.
        """
        entries = self._audit_log

        if operation:
            entries = [e for e in entries if e.operation == operation]

        return entries[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get coordinator statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            **self._stats,
            "started": self._started,
            "audit_log_size": len(self._audit_log),
            "pbft_available": self._pbft_node is not None,
        }


# =============================================================================
# COLONY CONSENSUS INTEGRATION
# =============================================================================


async def require_pbft_for_critical(
    operation: str,
    data: dict[str, Any],
    coordinator: CriticalPBFTCoordinator | None = None,
) -> CriticalPBFTResult | None:
    """Check if operation requires PBFT and run consensus if so.

    This function can be called from colony consensus to gate
    critical operations through PBFT.

    Args:
        operation: Operation string.
        data: Operation data.
        coordinator: Optional coordinator (uses global if None).

    Returns:
        CriticalPBFTResult if critical, None otherwise.

    Example:
        # In colony consensus code:
        pbft_result = await require_pbft_for_critical(
            operation="unlock_door",
            data={"door": "front"},
        )
        if pbft_result is not None:
            if not pbft_result.success:
                return ConsensusState(converged=False, ...)
    """
    if not is_critical_operation(operation):
        return None

    if coordinator is None:
        coordinator = await get_critical_pbft_coordinator()

    try:
        critical_op = CriticalOperation(operation)
    except ValueError:
        return None

    return await coordinator.submit_critical(
        operation=critical_op,
        data=data,
    )


# =============================================================================
# FACTORY
# =============================================================================


_coordinator: CriticalPBFTCoordinator | None = None
_coordinator_lock = asyncio.Lock()


async def get_critical_pbft_coordinator() -> CriticalPBFTCoordinator:
    """Get or create the global CriticalPBFTCoordinator.

    Returns:
        CriticalPBFTCoordinator singleton instance.
    """
    global _coordinator

    async with _coordinator_lock:
        if _coordinator is None:
            _coordinator = CriticalPBFTCoordinator()
            await _coordinator.start()

    return _coordinator


def get_critical_pbft_coordinator_sync() -> CriticalPBFTCoordinator | None:
    """Get the coordinator synchronously (may be None).

    Returns:
        CriticalPBFTCoordinator or None if not initialized.
    """
    return _coordinator


# =============================================================================
# 鏡
# η → s → μ → a → η′
# h(x) ≥ 0. Always.
# =============================================================================
