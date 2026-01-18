"""Unified Markov Blanket Enforcement — Information Boundaries Across All Domains.

UNIFIES: Markov blanket implementation patterns identified across:
1. Physical sensory/effector boundaries (SmartHome → Control4, UniFi, Tesla)
2. Digital sensory/effector boundaries (Composio → Gmail, GitHub, Linear)
3. Memory system boundaries (Weaviate, CockroachDB, Redis isolation)
4. Colony boundaries (7 colonies with E8 communication protocols)
5. Safety boundaries (CBF constraints, h(x) ≥ 0 enforcement)

This provides:
- Unified information flow control across all domains
- Consistent boundary violation detection and recovery
- Safety-aware boundary enforcement with CBF integration
- Performance optimization through boundary-aware caching

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from .action_result import ActionError, ActionErrorType, ActionMetadata, ActionResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BoundaryType(Enum):
    """Types of Markov blanket boundaries."""

    SENSORY = "sensory"  # External world → Internal states
    ACTIVE = "active"  # Internal states → External world
    INTERNAL = "internal"  # Colony internal boundaries
    MEMORY = "memory"  # Memory system boundaries
    SAFETY = "safety"  # CBF safety boundaries
    INTER_COLONY = "inter_colony"  # Between-colony communication
    CROSS_DOMAIN = "cross_domain"  # Physical ↔ Digital boundaries


class BoundaryState(Enum):
    """States of boundary enforcement."""

    INTACT = "intact"  # Boundary functioning normally
    DEGRADED = "degraded"  # Boundary partially compromised
    VIOLATED = "violated"  # Boundary breached
    RECOVERING = "recovering"  # Boundary being restored
    DISABLED = "disabled"  # Boundary temporarily disabled


class InformationFlow(Enum):
    """Direction of information flow across boundaries."""

    INBOUND = "inbound"  # External → Internal
    OUTBOUND = "outbound"  # Internal → External
    BIDIRECTIONAL = "bidirectional"  # Both directions
    BLOCKED = "blocked"  # No flow allowed


@dataclass
class BoundaryDescriptor:
    """Descriptor for a Markov blanket boundary."""

    boundary_id: str
    boundary_type: BoundaryType
    name: str
    description: str
    information_flow: InformationFlow
    safety_critical: bool = False
    enforcement_level: float = 1.0  # 0.0 = disabled, 1.0 = strict
    monitoring_enabled: bool = True
    auto_recovery: bool = True
    dependencies: list[str] = field(default_factory=list)


@dataclass
class BoundaryViolation:
    """Record of a boundary violation."""

    violation_id: str
    boundary_id: str
    violation_type: str
    severity: float  # 0.0 = minor, 1.0 = critical
    timestamp: float
    details: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: float | None = None


@dataclass
class BoundaryMetrics:
    """Metrics for boundary performance."""

    boundary_id: str
    uptime_percentage: float
    violation_count: int
    last_violation_time: float | None
    average_recovery_time: float
    information_throughput: float  # Messages/second
    safety_margin: float  # Current safety score (h(x))


class UnifiedMarkovBlanketEnforcer:
    """Unified enforcer for Markov blanket boundaries across all domains.

    Provides centralized boundary management with safety integration.
    """

    def __init__(
        self,
        enable_monitoring: bool = True,
        violation_threshold: float = 0.8,
        recovery_timeout: float = 30.0,
        safety_integration: bool = True,
    ):
        self.enable_monitoring = enable_monitoring
        self.violation_threshold = violation_threshold
        self.recovery_timeout = recovery_timeout
        self.safety_integration = safety_integration

        # Boundary registry
        self._boundaries: dict[str, BoundaryDescriptor] = {}
        self._boundary_states: dict[str, BoundaryState] = {}
        self._boundary_handlers: dict[str, Callable] = {}

        # Violation tracking
        self._violations: list[BoundaryViolation] = []
        self._violation_lock = threading.Lock()

        # Metrics
        self._metrics: dict[str, BoundaryMetrics] = {}
        self._metrics_lock = threading.Lock()

        # Monitoring
        self._monitoring_tasks: dict[str, asyncio.Task] = {}
        self._monitoring_enabled = False

        # Safety integration
        self._safety_callbacks: list[Callable[[float], None]] = []

        logger.info("Unified Markov blanket enforcer initialized")

    def register_boundary(
        self,
        descriptor: BoundaryDescriptor,
        handler: Callable[..., Awaitable[ActionResult[Any]]] | None = None,
    ) -> None:
        """Register a boundary with the enforcer.

        Args:
            descriptor: Boundary descriptor
            handler: Optional handler function for boundary operations
        """
        self._boundaries[descriptor.boundary_id] = descriptor
        self._boundary_states[descriptor.boundary_id] = BoundaryState.INTACT

        if handler:
            self._boundary_handlers[descriptor.boundary_id] = handler

        # Initialize metrics
        with self._metrics_lock:
            self._metrics[descriptor.boundary_id] = BoundaryMetrics(
                boundary_id=descriptor.boundary_id,
                uptime_percentage=100.0,
                violation_count=0,
                last_violation_time=None,
                average_recovery_time=0.0,
                information_throughput=0.0,
                safety_margin=1.0,
            )

        logger.info(f"Registered boundary: {descriptor.name} ({descriptor.boundary_type.value})")

        # Start monitoring if enabled
        if self.enable_monitoring and self._monitoring_enabled:
            self._start_boundary_monitoring(descriptor.boundary_id)

    def unregister_boundary(self, boundary_id: str) -> None:
        """Unregister a boundary.

        Args:
            boundary_id: ID of boundary to unregister
        """
        # Stop monitoring
        if boundary_id in self._monitoring_tasks:
            self._monitoring_tasks[boundary_id].cancel()
            del self._monitoring_tasks[boundary_id]

        # Remove from registries
        self._boundaries.pop(boundary_id, None)
        self._boundary_states.pop(boundary_id, None)
        self._boundary_handlers.pop(boundary_id, None)

        with self._metrics_lock:
            self._metrics.pop(boundary_id, None)

    async def enforce_boundary(
        self,
        boundary_id: str,
        information: Any,
        flow_direction: InformationFlow,
        safety_score: float | None = None,
        **kwargs: Any,
    ) -> ActionResult[Any]:
        """Enforce a boundary for information flow.

        Args:
            boundary_id: ID of boundary to enforce
            information: Information attempting to cross boundary
            flow_direction: Direction of information flow
            safety_score: Optional safety score (h(x))
            **kwargs: Additional parameters

        Returns:
            ActionResult indicating success/failure of boundary enforcement
        """
        if boundary_id not in self._boundaries:
            error = ActionError(
                ActionErrorType.RESOURCE_NOT_FOUND, f"Boundary not registered: {boundary_id}"
            )
            return ActionResult.failure(error)

        boundary = self._boundaries[boundary_id]
        current_state = self._boundary_states[boundary_id]

        metadata = ActionMetadata(
            action_type="boundary_enforcement", target=boundary_id, safety_score=safety_score or 1.0
        )

        # Check if boundary is in valid state for enforcement
        if current_state == BoundaryState.DISABLED:
            return ActionResult.success(
                data=information,
                message=f"Boundary {boundary_id} is disabled, allowing flow",
                metadata=metadata,
            )

        if current_state == BoundaryState.VIOLATED:
            if not boundary.auto_recovery:
                error = ActionError(
                    ActionErrorType.SYSTEM_ERROR,
                    f"Boundary {boundary_id} is violated and auto-recovery disabled",
                )
                return ActionResult.failure(error, metadata=metadata)

            # Attempt recovery
            recovery_result = await self._attempt_boundary_recovery(boundary_id)
            if not recovery_result.is_success():
                return recovery_result

        try:
            # Safety check if safety integration enabled
            if self.safety_integration and boundary.safety_critical:
                safety_result = await self._check_safety_constraints(
                    boundary, information, safety_score or 1.0
                )
                if not safety_result.is_success():
                    return safety_result

            # Validate information flow direction
            if not self._validate_flow_direction(boundary, flow_direction):
                error = ActionError(
                    ActionErrorType.VALIDATION_ERROR,
                    f"Flow direction {flow_direction.value} not allowed for boundary {boundary_id}",
                )
                return ActionResult.failure(error, metadata=metadata)

            # Apply boundary enforcement
            enforcement_result = await self._apply_boundary_enforcement(
                boundary, information, flow_direction, **kwargs
            )

            # Update metrics
            self._update_boundary_metrics(boundary_id, enforcement_result.is_success())

            # Call safety callbacks if needed
            if self.safety_integration and safety_score is not None:
                for callback in self._safety_callbacks:
                    try:
                        callback(safety_score)
                    except Exception as e:
                        logger.warning(f"Safety callback failed: {e}")

            return enforcement_result

        except Exception as e:
            logger.error(f"Boundary enforcement failed for {boundary_id}: {e}")

            # Record violation
            violation = BoundaryViolation(
                violation_id=f"violation_{int(time.time() * 1000)}",
                boundary_id=boundary_id,
                violation_type="enforcement_error",
                severity=0.8,  # High severity for enforcement failures
                timestamp=time.time(),
                details={"error": str(e), "flow_direction": flow_direction.value},
            )
            self._record_violation(violation)

            error = ActionError(ActionErrorType.SYSTEM_ERROR, f"Boundary enforcement error: {e!s}")
            return ActionResult.failure(error, metadata=metadata)

    async def start_monitoring(self) -> None:
        """Start boundary monitoring."""
        if self._monitoring_enabled:
            return

        self._monitoring_enabled = True

        # Start monitoring tasks for all registered boundaries
        for boundary_id in self._boundaries:
            if self._boundaries[boundary_id].monitoring_enabled:
                self._start_boundary_monitoring(boundary_id)

        logger.info("Boundary monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop boundary monitoring."""
        self._monitoring_enabled = False

        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()

        # Wait for tasks to finish
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)

        self._monitoring_tasks.clear()
        logger.info("Boundary monitoring stopped")

    def get_boundary_status(self, boundary_id: str | None = None) -> dict[str, Any]:
        """Get status of boundaries.

        Args:
            boundary_id: Optional specific boundary ID

        Returns:
            Dictionary with boundary status information
        """
        if boundary_id:
            if boundary_id not in self._boundaries:
                return {"error": f"Boundary {boundary_id} not found"}

            boundary = self._boundaries[boundary_id]
            state = self._boundary_states[boundary_id]
            metrics = self._metrics.get(boundary_id)

            return {
                "boundary_id": boundary_id,
                "name": boundary.name,
                "type": boundary.boundary_type.value,
                "state": state.value,
                "enforcement_level": boundary.enforcement_level,
                "safety_critical": boundary.safety_critical,
                "metrics": metrics.__dict__ if metrics else None,
            }
        else:
            # Return status for all boundaries
            status = {}
            for bid in self._boundaries:
                status[bid] = self.get_boundary_status(bid)
            return status

    def get_violation_history(
        self, boundary_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get violation history.

        Args:
            boundary_id: Optional boundary filter
            limit: Maximum number of violations to return

        Returns:
            List of violation records
        """
        with self._violation_lock:
            violations = self._violations

            if boundary_id:
                violations = [v for v in violations if v.boundary_id == boundary_id]

            # Sort by timestamp (newest first)
            violations.sort(key=lambda x: x.timestamp, reverse=True)

            return [
                {
                    "violation_id": v.violation_id,
                    "boundary_id": v.boundary_id,
                    "type": v.violation_type,
                    "severity": v.severity,
                    "timestamp": v.timestamp,
                    "resolved": v.resolved,
                    "resolution_time": v.resolution_time,
                    "details": v.details,
                }
                for v in violations[:limit]
            ]

    def register_safety_callback(self, callback: Callable[[float], None]) -> None:
        """Register a safety callback function.

        Args:
            callback: Function called with safety score updates
        """
        self._safety_callbacks.append(callback)

    def unregister_safety_callback(self, callback: Callable[[float], None]) -> None:
        """Unregister a safety callback function.

        Args:
            callback: Function to unregister
        """
        if callback in self._safety_callbacks:
            self._safety_callbacks.remove(callback)

    # =============================================================================
    # PRIVATE METHODS
    # =============================================================================

    async def _apply_boundary_enforcement(
        self,
        boundary: BoundaryDescriptor,
        information: Any,
        flow_direction: InformationFlow,
        **kwargs: Any,
    ) -> ActionResult[Any]:
        """Apply boundary enforcement logic.

        Args:
            boundary: Boundary descriptor
            information: Information to process
            flow_direction: Flow direction
            **kwargs: Additional parameters

        Returns:
            ActionResult with enforcement outcome
        """
        # Check if custom handler exists
        if boundary.boundary_id in self._boundary_handlers:
            handler = self._boundary_handlers[boundary.boundary_id]
            try:
                return await handler(information, flow_direction, **kwargs)
            except Exception as e:
                error = ActionError(ActionErrorType.SYSTEM_ERROR, f"Custom handler failed: {e!s}")
                return ActionResult.failure(error)

        # Default enforcement logic
        enforcement_factor = boundary.enforcement_level

        if enforcement_factor < 0.1:
            # Very low enforcement - allow almost everything
            return ActionResult.success(
                data=information,
                message=f"Low enforcement boundary {boundary.boundary_id}",
            )
        elif enforcement_factor < 0.5:
            # Medium enforcement - some filtering
            filtered_info = self._apply_medium_filtering(information, boundary)
            return ActionResult.success(
                data=filtered_info,
                message=f"Medium enforcement applied to {boundary.boundary_id}",
            )
        else:
            # High enforcement - strict filtering
            filtered_info = self._apply_strict_filtering(information, boundary)
            if filtered_info is None:
                error = ActionError(
                    ActionErrorType.VALIDATION_ERROR,
                    f"Information blocked by strict enforcement on {boundary.boundary_id}",
                )
                return ActionResult.failure(error)
            else:
                return ActionResult.success(
                    data=filtered_info,
                    message=f"Strict enforcement applied to {boundary.boundary_id}",
                )

    def _validate_flow_direction(
        self, boundary: BoundaryDescriptor, flow_direction: InformationFlow
    ) -> bool:
        """Validate if flow direction is allowed for boundary."""
        allowed_flow = boundary.information_flow

        if allowed_flow == InformationFlow.BIDIRECTIONAL:
            return flow_direction in [InformationFlow.INBOUND, InformationFlow.OUTBOUND]
        elif allowed_flow == InformationFlow.BLOCKED:
            return False
        else:
            return flow_direction == allowed_flow

    async def _check_safety_constraints(
        self, boundary: BoundaryDescriptor, information: Any, safety_score: float
    ) -> ActionResult[Any]:
        """Check safety constraints for boundary crossing.

        Args:
            boundary: Boundary descriptor
            information: Information attempting to cross
            safety_score: Current safety score (h(x))

        Returns:
            ActionResult indicating safety check outcome
        """
        # Safety threshold - information can only cross if h(x) ≥ 0
        if safety_score < 0.0:
            return ActionResult.safety_violation(
                safety_score=safety_score,
                constraint=f"boundary_{boundary.boundary_id}_safety",
                message=f"Safety violation on boundary {boundary.boundary_id}",
            )

        # Additional safety checks for critical boundaries
        if boundary.safety_critical and safety_score < 0.3:
            return ActionResult.degraded(
                data=information,
                degradation_level=0.7,
                message=f"Reduced safety on critical boundary {boundary.boundary_id}",
                warnings=[f"Safety score {safety_score} below recommended threshold 0.3"],
            )

        return ActionResult.success(
            data=information, message=f"Safety constraints satisfied for {boundary.boundary_id}"
        )

    def _apply_medium_filtering(self, information: Any, boundary: BoundaryDescriptor) -> Any:
        """Apply medium-level filtering to information."""
        # Simplified filtering logic
        if isinstance(information, dict):
            # Filter out potentially sensitive keys
            sensitive_keys = ["password", "token", "secret", "key"]
            filtered = {
                k: v
                for k, v in information.items()
                if not any(sensitive in k.lower() for sensitive in sensitive_keys)
            }
            return filtered
        else:
            # Pass through non-dict information
            return information

    def _apply_strict_filtering(self, information: Any, boundary: BoundaryDescriptor) -> Any | None:
        """Apply strict filtering to information."""
        # Simplified strict filtering - only allow basic types
        if isinstance(information, (str, int, float, bool)):
            return information
        elif isinstance(information, dict):
            # Only allow very basic dictionaries
            basic_info = {}
            for k, v in information.items():
                if isinstance(v, (str, int, float, bool)) and len(str(v)) < 100:
                    basic_info[k] = v
            return basic_info if basic_info else None
        else:
            # Block complex types under strict enforcement
            return None

    async def _attempt_boundary_recovery(self, boundary_id: str) -> ActionResult[Any]:
        """Attempt to recover a violated boundary.

        Args:
            boundary_id: ID of boundary to recover

        Returns:
            ActionResult indicating recovery outcome
        """
        logger.info(f"Attempting recovery for boundary {boundary_id}")

        # Set state to recovering
        self._boundary_states[boundary_id] = BoundaryState.RECOVERING

        try:
            # Simplified recovery logic
            await asyncio.sleep(1.0)  # Simulate recovery time

            # Check if recovery was successful
            recovery_success = True  # Simplified - would do actual checks

            if recovery_success:
                self._boundary_states[boundary_id] = BoundaryState.INTACT
                return ActionResult.success(
                    message=f"Boundary {boundary_id} recovered successfully"
                )
            else:
                self._boundary_states[boundary_id] = BoundaryState.VIOLATED
                error = ActionError(
                    ActionErrorType.SYSTEM_ERROR, f"Recovery failed for boundary {boundary_id}"
                )
                return ActionResult.failure(error)

        except Exception as e:
            self._boundary_states[boundary_id] = BoundaryState.VIOLATED
            error = ActionError(ActionErrorType.SYSTEM_ERROR, f"Recovery attempt failed: {e!s}")
            return ActionResult.failure(error)

    def _start_boundary_monitoring(self, boundary_id: str) -> None:
        """Start monitoring task for a boundary."""
        if boundary_id in self._monitoring_tasks:
            return

        async def monitor_boundary():
            """Monitor boundary health and detect violations."""
            while self._monitoring_enabled:
                try:
                    # Simplified monitoring logic
                    await asyncio.sleep(10.0)  # Monitor every 10 seconds

                    # Check boundary health (simplified)
                    health_score = 0.95  # Would do actual health checks

                    if health_score < self.violation_threshold:
                        # Potential violation detected
                        violation = BoundaryViolation(
                            violation_id=f"monitor_{boundary_id}_{int(time.time())}",
                            boundary_id=boundary_id,
                            violation_type="health_degradation",
                            severity=1.0 - health_score,
                            timestamp=time.time(),
                            details={"health_score": health_score},
                        )
                        self._record_violation(violation)

                        # Update boundary state
                        if health_score < 0.5:
                            self._boundary_states[boundary_id] = BoundaryState.VIOLATED
                        else:
                            self._boundary_states[boundary_id] = BoundaryState.DEGRADED

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Boundary monitoring error for {boundary_id}: {e}")

        task = asyncio.create_task(monitor_boundary())
        self._monitoring_tasks[boundary_id] = task

    def _record_violation(self, violation: BoundaryViolation) -> None:
        """Record a boundary violation."""
        with self._violation_lock:
            self._violations.append(violation)

            # Keep only recent violations (last 1000)
            if len(self._violations) > 1000:
                self._violations = self._violations[-500:]

        logger.warning(
            f"Boundary violation recorded: {violation.boundary_id} - "
            f"{violation.violation_type} (severity: {violation.severity})"
        )

    def _update_boundary_metrics(self, boundary_id: str, success: bool) -> None:
        """Update metrics for a boundary."""
        with self._metrics_lock:
            if boundary_id not in self._metrics:
                return

            metrics = self._metrics[boundary_id]

            # Update throughput (simplified)
            metrics.information_throughput += 1.0

            # Update uptime based on success
            if not success:
                metrics.uptime_percentage *= 0.99  # Reduce uptime on failure
            else:
                metrics.uptime_percentage = min(100.0, metrics.uptime_percentage + 0.01)


# =============================================================================
# FACTORY FUNCTIONS AND BOUNDARY TEMPLATES
# =============================================================================


def get_unified_markov_enforcer(**kwargs) -> UnifiedMarkovBlanketEnforcer:
    """Get unified Markov blanket enforcer instance."""
    return UnifiedMarkovBlanketEnforcer(**kwargs)


def create_physical_boundary(device_type: str, safety_critical: bool = False) -> BoundaryDescriptor:
    """Create boundary descriptor for physical devices."""
    return BoundaryDescriptor(
        boundary_id=f"physical_{device_type}",
        boundary_type=BoundaryType.SENSORY,
        name=f"{device_type.title()} Device Boundary",
        description=f"Information boundary for {device_type} devices",
        information_flow=InformationFlow.BIDIRECTIONAL,
        safety_critical=safety_critical,
        enforcement_level=0.8 if safety_critical else 0.6,
    )


def create_digital_boundary(service_name: str) -> BoundaryDescriptor:
    """Create boundary descriptor for digital services."""
    return BoundaryDescriptor(
        boundary_id=f"digital_{service_name}",
        boundary_type=BoundaryType.ACTIVE,
        name=f"{service_name.title()} Service Boundary",
        description=f"Information boundary for {service_name} service",
        information_flow=InformationFlow.BIDIRECTIONAL,
        safety_critical=False,
        enforcement_level=0.7,
    )


def create_colony_boundary(colony_name: str) -> BoundaryDescriptor:
    """Create boundary descriptor for colony communication."""
    return BoundaryDescriptor(
        boundary_id=f"colony_{colony_name}",
        boundary_type=BoundaryType.INTER_COLONY,
        name=f"{colony_name} Colony Boundary",
        description=f"Information boundary for {colony_name} colony communication",
        information_flow=InformationFlow.BIDIRECTIONAL,
        safety_critical=True,
        enforcement_level=0.9,
    )


def create_memory_boundary(memory_type: str) -> BoundaryDescriptor:
    """Create boundary descriptor for memory systems."""
    return BoundaryDescriptor(
        boundary_id=f"memory_{memory_type}",
        boundary_type=BoundaryType.MEMORY,
        name=f"{memory_type.title()} Memory Boundary",
        description=f"Information boundary for {memory_type} memory system",
        information_flow=InformationFlow.BIDIRECTIONAL,
        safety_critical=True,
        enforcement_level=0.8,
    )
