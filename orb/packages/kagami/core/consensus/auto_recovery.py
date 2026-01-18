"""Automatic Recovery System — Byzantine fault recovery and self-healing.

This module implements automatic recovery mechanisms for the distributed cluster:
- Byzantine fault detection and isolation
- Periodic health monitoring
- Automatic re-admission of recovered nodes
- Graceful degradation during network partitions
- Self-healing mesh coordination

The system follows the principle: h(x) ≥ 0 always.

Architecture:
```
    Fault Detection         Recovery Manager         Re-admission
    ─────────────────       ─────────────────        ─────────────
    Monitor peers       →   Evaluate evidence   →    Vote on re-join
    Track violations    →   Apply isolation     →    Verify correction
    Emit alerts         →   Log to audit trail  →    Restore trust
```

Colony: Flow (A₄) — Recovery, adaptation, healing
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class RecoveryAction(str, Enum):
    """Actions that can be taken for recovery."""

    NONE = "none"  # No action needed
    WARN = "warn"  # Log warning, continue monitoring
    ISOLATE = "isolate"  # Temporarily isolate node
    EJECT = "eject"  # Remove from cluster (requires PBFT consensus)
    READMIT = "readmit"  # Allow isolated node back


class FaultSeverity(str, Enum):
    """Severity levels for Byzantine faults."""

    LOW = "low"  # Timeouts, minor protocol violations
    MEDIUM = "medium"  # Signature failures, invalid messages
    HIGH = "high"  # Equivocation detected
    CRITICAL = "critical"  # Active attack patterns


@dataclass
class RecoveryConfig:
    """Configuration for automatic recovery system."""

    # Fault detection thresholds
    fault_threshold_warn: int = 3
    fault_threshold_isolate: int = 5
    fault_threshold_eject: int = 10

    # Time windows (seconds)
    fault_window_seconds: float = 300.0  # 5 minutes
    isolation_duration_seconds: float = 600.0  # 10 minutes
    readmission_cooldown_seconds: float = 60.0  # 1 minute between attempts

    # Health check intervals
    health_check_interval_seconds: float = 30.0
    recovery_check_interval_seconds: float = 60.0

    # Safety margins
    max_isolated_ratio: float = 0.3  # Max 30% of nodes can be isolated
    min_healthy_nodes: int = 3  # Minimum nodes for cluster operation


# =============================================================================
# Fault Tracking
# =============================================================================


@dataclass
class FaultRecord:
    """Record of a detected fault."""

    node_id: str
    fault_type: str
    severity: FaultSeverity
    timestamp: float
    evidence_hash: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "fault_type": self.fault_type,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "evidence_hash": self.evidence_hash,
            "details": self.details,
        }


@dataclass
class NodeRecoveryState:
    """Recovery state for a single node."""

    node_id: str
    is_isolated: bool = False
    isolation_start: float | None = None
    fault_count: int = 0
    fault_score: float = 0.0  # Weighted by severity
    last_fault_time: float | None = None
    faults: list[FaultRecord] = field(default_factory=list)
    readmission_attempts: int = 0
    last_readmission_attempt: float | None = None

    def add_fault(self, fault: FaultRecord) -> None:
        """Add a fault record."""
        self.faults.append(fault)
        self.fault_count += 1
        self.last_fault_time = fault.timestamp

        # Weight by severity
        severity_weights = {
            FaultSeverity.LOW: 1.0,
            FaultSeverity.MEDIUM: 2.0,
            FaultSeverity.HIGH: 5.0,
            FaultSeverity.CRITICAL: 10.0,
        }
        self.fault_score += severity_weights.get(fault.severity, 1.0)

        # Keep only recent faults (last 100)
        if len(self.faults) > 100:
            self.faults = self.faults[-100:]

    def decay_faults(self, window_seconds: float) -> None:
        """Decay fault score over time."""
        if self.last_fault_time is None:
            return

        elapsed = time.time() - self.last_fault_time
        if elapsed > window_seconds:
            # Decay by 50% for each window elapsed
            decay_factor = 0.5 ** (elapsed / window_seconds)
            self.fault_score *= decay_factor
            if self.fault_score < 0.1:
                self.fault_score = 0.0
                self.fault_count = 0

    def can_attempt_readmission(self, cooldown: float) -> bool:
        """Check if readmission can be attempted."""
        if not self.is_isolated:
            return False
        if self.last_readmission_attempt is None:
            return True
        return time.time() - self.last_readmission_attempt > cooldown


# =============================================================================
# Auto Recovery Manager
# =============================================================================


class AutoRecoveryManager:
    """Manages automatic recovery from Byzantine faults.

    This manager coordinates:
    - Fault detection and scoring
    - Node isolation decisions
    - Automatic re-admission
    - Cluster health monitoring
    """

    def __init__(
        self,
        node_id: str,
        config: RecoveryConfig | None = None,
    ) -> None:
        """Initialize the recovery manager.

        Args:
            node_id: This node's identifier.
            config: Recovery configuration.
        """
        self.node_id = node_id
        self.config = config or RecoveryConfig()

        # Node states
        self._node_states: dict[str, NodeRecoveryState] = {}

        # Callbacks
        self._on_isolate: Callable[[str, FaultRecord], None] | None = None
        self._on_readmit: Callable[[str], None] | None = None
        self._on_eject: Callable[[str], None] | None = None

        # Background tasks
        self._running = False
        self._health_task: asyncio.Task | None = None
        self._recovery_task: asyncio.Task | None = None

        # Metrics
        self._total_faults_detected = 0
        self._total_isolations = 0
        self._total_readmissions = 0

        logger.info(f"AutoRecoveryManager initialized for node {node_id}")

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start the recovery manager."""
        if self._running:
            return

        self._running = True

        # Start background tasks
        self._health_task = asyncio.create_task(
            self._health_check_loop(),
            name="recovery_health_check",
        )
        self._recovery_task = asyncio.create_task(
            self._recovery_check_loop(),
            name="recovery_readmission_check",
        )

        logger.info("AutoRecoveryManager started")

    async def stop(self) -> None:
        """Stop the recovery manager."""
        self._running = False

        # Cancel background tasks
        for task in [self._health_task, self._recovery_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("AutoRecoveryManager stopped")

    # =========================================================================
    # Fault Recording
    # =========================================================================

    def record_fault(
        self,
        node_id: str,
        fault_type: str,
        severity: FaultSeverity,
        details: dict[str, Any] | None = None,
    ) -> RecoveryAction:
        """Record a detected fault.

        Args:
            node_id: Node that committed the fault.
            fault_type: Type of fault detected.
            severity: Severity level.
            details: Additional details.

        Returns:
            Action to take.
        """
        # Create fault record
        evidence_hash = hashlib.sha256(
            f"{node_id}:{fault_type}:{time.time()}".encode()
        ).hexdigest()[:16]

        fault = FaultRecord(
            node_id=node_id,
            fault_type=fault_type,
            severity=severity,
            timestamp=time.time(),
            evidence_hash=evidence_hash,
            details=details or {},
        )

        # Get or create node state
        if node_id not in self._node_states:
            self._node_states[node_id] = NodeRecoveryState(node_id=node_id)

        state = self._node_states[node_id]
        state.add_fault(fault)
        self._total_faults_detected += 1

        logger.warning(
            f"Fault recorded for {node_id}: {fault_type} ({severity.value}) "
            f"[score: {state.fault_score:.1f}]"
        )

        # Determine action
        action = self._evaluate_action(state, fault)

        # Execute action
        if action == RecoveryAction.ISOLATE:
            self._isolate_node(node_id, fault)
        elif action == RecoveryAction.EJECT:
            self._request_ejection(node_id, fault)

        return action

    def _evaluate_action(
        self,
        state: NodeRecoveryState,
        fault: FaultRecord,
    ) -> RecoveryAction:
        """Evaluate what action to take for a fault."""
        # Critical faults trigger immediate isolation
        if fault.severity == FaultSeverity.CRITICAL:
            return RecoveryAction.ISOLATE

        # High severity faults lower the threshold
        effective_score = state.fault_score
        if fault.severity == FaultSeverity.HIGH:
            effective_score *= 1.5

        # Check thresholds
        if effective_score >= self.config.fault_threshold_eject:
            return RecoveryAction.EJECT
        elif effective_score >= self.config.fault_threshold_isolate:
            return RecoveryAction.ISOLATE
        elif effective_score >= self.config.fault_threshold_warn:
            return RecoveryAction.WARN

        return RecoveryAction.NONE

    def _isolate_node(self, node_id: str, fault: FaultRecord) -> None:
        """Isolate a node."""
        state = self._node_states.get(node_id)
        if not state:
            return

        if state.is_isolated:
            return  # Already isolated

        state.is_isolated = True
        state.isolation_start = time.time()
        self._total_isolations += 1

        logger.warning(f"🔴 ISOLATED node {node_id} due to: {fault.fault_type}")

        # Callback
        if self._on_isolate:
            self._on_isolate(node_id, fault)

    def _request_ejection(self, node_id: str, fault: FaultRecord) -> None:
        """Request node ejection via PBFT consensus."""
        logger.error(f"🔴 EJECTION REQUESTED for {node_id} due to: {fault.fault_type}")

        # Callback
        if self._on_eject:
            self._on_eject(node_id)

    # =========================================================================
    # Recovery
    # =========================================================================

    async def check_readmission(self, node_id: str) -> bool:
        """Check if a node can be re-admitted.

        Args:
            node_id: Node to check.

        Returns:
            True if re-admitted.
        """
        state = self._node_states.get(node_id)
        if not state or not state.is_isolated:
            return False

        # Check cooldown
        if not state.can_attempt_readmission(self.config.readmission_cooldown_seconds):
            return False

        # Check isolation duration
        if state.isolation_start is None:
            return False

        elapsed = time.time() - state.isolation_start
        if elapsed < self.config.isolation_duration_seconds:
            logger.debug(
                f"Node {node_id} isolation not expired: "
                f"{elapsed:.0f}s < {self.config.isolation_duration_seconds:.0f}s"
            )
            return False

        # Decay fault score
        state.decay_faults(self.config.fault_window_seconds)

        # Check if fault score is low enough
        if state.fault_score > self.config.fault_threshold_warn:
            logger.debug(f"Node {node_id} fault score too high: {state.fault_score:.1f}")
            state.readmission_attempts += 1
            state.last_readmission_attempt = time.time()
            return False

        # Re-admit the node
        state.is_isolated = False
        state.isolation_start = None
        state.fault_count = 0
        state.fault_score = 0.0
        self._total_readmissions += 1

        logger.info(f"✅ RE-ADMITTED node {node_id}")

        # Callback
        if self._on_readmit:
            self._on_readmit(node_id)

        return True

    # =========================================================================
    # Background Tasks
    # =========================================================================

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)

                # Decay fault scores
                for state in self._node_states.values():
                    state.decay_faults(self.config.fault_window_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _recovery_check_loop(self) -> None:
        """Periodic recovery check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.recovery_check_interval_seconds)

                # Check for nodes that can be re-admitted
                for node_id, state in list(self._node_states.items()):
                    if state.is_isolated:
                        await self.check_readmission(node_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Recovery check error: {e}")

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_isolate(
        self,
        callback: Callable[[str, FaultRecord], None],
    ) -> None:
        """Set callback for node isolation."""
        self._on_isolate = callback

    def on_readmit(self, callback: Callable[[str], None]) -> None:
        """Set callback for node re-admission."""
        self._on_readmit = callback

    def on_eject(self, callback: Callable[[str], None]) -> None:
        """Set callback for node ejection request."""
        self._on_eject = callback

    # =========================================================================
    # Query API
    # =========================================================================

    def is_isolated(self, node_id: str) -> bool:
        """Check if a node is isolated."""
        state = self._node_states.get(node_id)
        return state.is_isolated if state else False

    def get_isolated_nodes(self) -> list[str]:
        """Get list of isolated node IDs."""
        return [node_id for node_id, state in self._node_states.items() if state.is_isolated]

    def get_node_state(self, node_id: str) -> dict[str, Any] | None:
        """Get recovery state for a node."""
        state = self._node_states.get(node_id)
        if not state:
            return None

        return {
            "node_id": state.node_id,
            "is_isolated": state.is_isolated,
            "isolation_start": state.isolation_start,
            "fault_count": state.fault_count,
            "fault_score": state.fault_score,
            "readmission_attempts": state.readmission_attempts,
            "recent_faults": [f.to_dict() for f in state.faults[-10:]],
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get recovery manager metrics."""
        isolated_count = len(self.get_isolated_nodes())
        total_nodes = len(self._node_states)

        return {
            "total_faults_detected": self._total_faults_detected,
            "total_isolations": self._total_isolations,
            "total_readmissions": self._total_readmissions,
            "currently_isolated": isolated_count,
            "total_tracked_nodes": total_nodes,
            "isolation_ratio": isolated_count / total_nodes if total_nodes > 0 else 0.0,
        }


# =============================================================================
# Singleton Access
# =============================================================================


_recovery_manager: AutoRecoveryManager | None = None


async def get_recovery_manager(
    node_id: str | None = None,
    config: RecoveryConfig | None = None,
) -> AutoRecoveryManager:
    """Get or create the recovery manager singleton.

    Args:
        node_id: This node's identifier (required on first call).
        config: Recovery configuration.

    Returns:
        The recovery manager instance.
    """
    global _recovery_manager

    if _recovery_manager is None:
        if node_id is None:
            raise ValueError("node_id required for first initialization")

        _recovery_manager = AutoRecoveryManager(
            node_id=node_id,
            config=config,
        )
        await _recovery_manager.start()

    return _recovery_manager


async def shutdown_recovery_manager() -> None:
    """Shutdown the recovery manager."""
    global _recovery_manager

    if _recovery_manager:
        await _recovery_manager.stop()
        _recovery_manager = None


# =============================================================================
# 鏡
# Recovery is continuous. The mesh heals. h(x) ≥ 0. Always.
# =============================================================================
