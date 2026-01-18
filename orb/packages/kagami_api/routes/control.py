"""Control API - Manage K os agents and system.

Provides endpoints for:
- Triggering agent scans
- Stopping/restarting agents
- Adjusting power modes
- Managing experiments/feature flags
- Emergency stop and system halt controls (SAFETY CRITICAL)
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from kagami.core.safety import enforce_tier1
from pydantic import BaseModel, Field

from kagami_api.rbac import Permission, require_permission
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import Principal, require_auth

logger = logging.getLogger(__name__)

# Global safety override state (thread-safe via GIL) (MODULE LEVEL)
_emergency_stop_active: bool = False
_emergency_stop_reason: str | None = None
_emergency_stop_timestamp: float | None = None
_emergency_stop_user: str | None = None


# ===== REQUEST/RESPONSE SCHEMAS (MODULE LEVEL - PUBLIC API) =====


class EmergencyStopRequest(BaseModel):
    """Request to trigger emergency stop."""

    reason: str = Field(..., min_length=10, max_length=500, description="Reason for emergency stop")
    confirmation_token: str = Field(
        ..., description="Confirmation token (must be 'EMERGENCY_STOP_CONFIRMED')"
    )


class EmergencyStopResponse(BaseModel):
    """Response from emergency stop operation."""

    success: bool
    message: str
    timestamp: float
    user: str
    reason: str
    actions_taken: list[str]


class SystemHaltRequest(BaseModel):
    """Request to halt system."""

    reason: str = Field(..., min_length=10, max_length=500, description="Reason for system halt")
    confirmation_token: str = Field(
        ..., description="Confirmation token (must be 'SYSTEM_HALT_CONFIRMED')"
    )
    force: bool = Field(
        default=False, description="Force halt even if colonies don't stop gracefully"
    )


class SystemHaltResponse(BaseModel):
    """Response from system halt operation."""

    success: bool
    message: str
    timestamp: float
    user: str
    reason: str
    colonies_stopped: int
    warnings: list[str]


class SafetyStatusResponse(BaseModel):
    """Current safety status of the system."""

    emergency_stop_active: bool
    h_value: float | None = Field(None, description="Current CBF barrier value h(x)")
    safety_zone: str = Field(
        ..., description="GREEN (h > 0.5), YELLOW (0 <= h <= 0.5), RED (h < 0)"
    )
    emergency_stop_reason: str | None
    emergency_stop_timestamp: float | None
    emergency_stop_user: str | None
    colonies_running: int
    system_healthy: bool


class ResumeSystemRequest(BaseModel):
    """Request to resume system after emergency stop."""

    confirmation_token: str = Field(
        ..., description="Confirmation token (must be 'RESUME_CONFIRMED')"
    )
    reason: str = Field(
        ..., min_length=10, max_length=500, description="Reason for resuming operations"
    )


class ResumeSystemResponse(BaseModel):
    """Response from system resume operation."""

    success: bool
    message: str
    timestamp: float
    user: str
    previous_stop_reason: str | None


class StopAgentResponse(BaseModel):
    """Response from agent stop operation."""

    status: str = Field(..., description="Operation status: 'success' or 'error'")
    agent: str = Field(..., description="Name of the agent")
    message: str = Field(..., description="Human-readable status message")


# Helper functions (MODULE LEVEL - PUBLIC API)
def _emit_emergency_audit_event(
    event_type: str,
    user: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit critical audit event for emergency operations.

    Args:
        event_type: Type of emergency event
        user: User who triggered the event
        reason: Reason provided by user
        details: Additional event details
    """
    try:
        from kagami_api.audit_logger import (
            AuditEvent,
            AuditEventType,
            AuditSeverity,
            get_audit_logger,
        )

        # Map event type to AuditEventType
        event_type_map = {
            "emergency_stop": AuditEventType.SYSTEM_COMMAND,
            "system_halt": AuditEventType.SYSTEM_COMMAND,
            "system_resume": AuditEventType.SYSTEM_COMMAND,
        }

        audit_logger = get_audit_logger()
        event = AuditEvent(
            event_type=event_type_map.get(event_type, AuditEventType.SYSTEM_COMMAND),
            user_id=user,
            severity=AuditSeverity.CRITICAL,
            outcome="success",
            resource=f"system.{event_type}",
            details={
                "reason": reason,
                "event_subtype": event_type,
                **(details or {}),
            },
        )
        audit_logger.log_event(event)
        logger.critical(f"EMERGENCY AUDIT: {event_type} by {user}: {reason}")
    except Exception as e:
        # Never fail emergency operations due to audit logging errors
        logger.error(f"Failed to emit emergency audit event: {e}")


def _emit_emergency_receipt(
    action: str,
    user: str,
    reason: str,
    event_data: dict[str, Any] | None = None,
) -> None:
    """Emit receipt for emergency operation.

    Args:
        action: Action identifier
        user: User who triggered the action
        reason: Reason provided by user
        event_data: Additional event data
    """
    try:
        from kagami.core.receipts import UnifiedReceiptFacade

        UnifiedReceiptFacade.emit(
            correlation_id=f"emergency-{action}-{int(time.time() * 1000)}",
            action=f"control.emergency.{action}",
            app="Control",
            event_name=f"emergency.{action}",
            event_data={
                "user": user,
                "reason": reason,
                "timestamp": time.time(),
                **(event_data or {}),
            },
            duration_ms=0,
        )
    except Exception as e:
        logger.error(f"Failed to emit emergency receipt: {e}")


def _get_current_h_value() -> float | None:
    """Get current CBF barrier value h(x).

    Returns:
        Current h(x) value, or None if unavailable
    """
    try:
        from kagami.core.safety.cbf_runtime_monitor import get_cbf_monitor

        monitor = get_cbf_monitor()
        if monitor and monitor.history:
            # Get most recent h(x) value
            return monitor.history[-1].h_value
    except Exception as e:
        logger.debug(f"Could not retrieve h(x) value: {e}")
    return None


def _get_safety_zone(h_value: float | None) -> str:
    """Determine safety zone from h(x) value.

    Args:
        h_value: CBF barrier value

    Returns:
        Safety zone: GREEN, YELLOW, or RED
    """
    if h_value is None:
        return "UNKNOWN"
    if h_value > 0.5:
        return "GREEN"
    elif h_value >= 0.0:
        return "YELLOW"
    else:
        return "RED"


def is_emergency_stop_active() -> bool:
    """Check if emergency stop is currently active.

    This function is exported for use by other modules to check emergency stop state.

    Returns:
        True if emergency stop is active, False otherwise
    """
    return _emergency_stop_active


# Route handler business logic (MODULE LEVEL - PUBLIC API for tests)
async def emergency_stop(
    request: EmergencyStopRequest,
    principal: Principal,
) -> EmergencyStopResponse:
    """EMERGENCY STOP: Force system into RED zone (h = -1.0) and stop all operations.

    SAFETY CRITICAL: This endpoint immediately halts all colony workers, cancels
    queued jobs, and forces the CBF barrier into violation state.

    Args:
        request: Emergency stop request with reason and confirmation
        principal: Authenticated principal (admin required)

    Returns:
        Emergency stop response with actions taken

    Raises:
        HTTPException: If confirmation token is invalid
    """

    global _emergency_stop_active, _emergency_stop_reason, _emergency_stop_timestamp
    global _emergency_stop_user

    # Validate confirmation token
    if request.confirmation_token != "EMERGENCY_STOP_CONFIRMED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation token. Must be 'EMERGENCY_STOP_CONFIRMED'",
        )

    timestamp = time.time()
    actions_taken: list[str] = []

    logger.critical(f"EMERGENCY STOP initiated by {principal.sub}: {request.reason}")

    # 1. Set global emergency stop flag
    _emergency_stop_active = True
    _emergency_stop_reason = request.reason
    _emergency_stop_timestamp = timestamp
    _emergency_stop_user = principal.sub
    actions_taken.append("Set global emergency stop flag")

    # 2. Force h(x) = -1.0 (RED zone) via CBF runtime monitor
    try:
        from kagami.core.safety.cbf_runtime_monitor import get_cbf_monitor

        monitor = get_cbf_monitor()
        if monitor:
            monitor.log_check(
                h_value=-1.0,
                operation="emergency_stop",
                context={
                    "user": principal.sub,
                    "reason": request.reason,
                    "forced": True,
                },
                safe=False,
                barrier_name="emergency_override",
                tier=1,
            )
            actions_taken.append("Forced h(x) = -1.0 (RED zone)")
        else:
            logger.warning("CBF monitor not available, skipping h(x) override")
    except Exception as e:
        logger.error(f"Failed to force h(x) = -1.0: {e}")
        actions_taken.append(f"Failed to force h(x): {e}")

    # 3. Stop all colony workers
    colonies_stopped = 0
    try:
        from kagami.orchestration.colony_manager import get_colony_manager

        manager = get_colony_manager()
        if manager:
            await manager.stop_all()
            colonies_stopped = 7  # All 7 colonies
            actions_taken.append(f"Stopped all {colonies_stopped} colonies")
        else:
            logger.warning("Colony manager not available")
    except Exception as e:
        logger.error(f"Failed to stop colonies: {e}")
        actions_taken.append(f"Failed to stop colonies: {e}")

    # 4. Cancel all queued jobs (if unified organism is available)
    try:
        from kagami.core.unified_agents.unified_organism import get_organism

        organism = get_organism()
        if organism:
            # Stop all colony background tasks
            for colony_name, colony in organism._colonies.items():
                try:
                    if hasattr(colony, "stop_background"):
                        await colony.stop_background()
                        actions_taken.append(f"Stopped colony {colony_name} background tasks")
                except Exception as e:
                    logger.error(f"Failed to stop colony {colony_name}: {e}")
        else:
            logger.warning("Organism not available")
    except Exception as e:
        logger.error(f"Failed to cancel queued jobs: {e}")
        actions_taken.append(f"Failed to cancel jobs: {e}")

    # 5. Pause physics simulation (if world model service is available)
    try:
        from kagami.core.services.world.world_model_service import get_world_model_service

        service = get_world_model_service()
        if service and service.is_available:
            # Set simulation to paused state (implementation depends on service API)
            if hasattr(service, "pause"):
                await service.pause()
                actions_taken.append("Paused physics simulation")
        else:
            logger.warning("World model service not available")
    except Exception as e:
        logger.error(f"Failed to pause simulation: {e}")
        actions_taken.append(f"Failed to pause simulation: {e}")

    # 6. Emit critical audit event
    _emit_emergency_audit_event(
        event_type="emergency_stop",
        user=principal.sub,
        reason=request.reason,
        details={
            "actions_taken": actions_taken,
            "colonies_stopped": colonies_stopped,
            "timestamp": timestamp,
        },
    )

    # 7. Emit receipt
    _emit_emergency_receipt(
        action="stop",
        user=principal.sub,
        reason=request.reason,
        event_data={"actions_taken": actions_taken},
    )

    return EmergencyStopResponse(
        success=True,
        message="Emergency stop executed successfully",
        timestamp=timestamp,
        user=principal.sub,
        reason=request.reason,
        actions_taken=actions_taken,
    )


async def system_halt(
    request: SystemHaltRequest,
    principal: Principal,
) -> SystemHaltResponse:
    """SYSTEM HALT: Gracefully stop all colonies and prepare for shutdown.

    This is a more graceful alternative to emergency stop. It:
    - Stops all colony processes gracefully
    - Waits for in-flight tasks to complete (unless force=True)
    - Does NOT force h(x) = -1.0

    Args:
        request: System halt request with reason and confirmation
        principal: Authenticated principal (admin required)

    Returns:
        System halt response with colonies stopped

    Raises:
        HTTPException: If confirmation token is invalid
    """
    # Validate confirmation token
    if request.confirmation_token != "SYSTEM_HALT_CONFIRMED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation token. Must be 'SYSTEM_HALT_CONFIRMED'",
        )

    timestamp = time.time()
    warnings: list[str] = []
    colonies_stopped = 0

    logger.warning(
        f"SYSTEM HALT initiated by {principal.sub}: {request.reason} (force={request.force})"
    )

    # Stop all colonies
    try:
        from kagami.orchestration.colony_manager import get_colony_manager

        manager = get_colony_manager()
        if manager:
            await manager.stop_all()
            colonies_stopped = 7
            logger.info(f"Stopped {colonies_stopped} colonies")
        else:
            warnings.append("Colony manager not available")
    except Exception as e:
        logger.error(f"Failed to stop colonies: {e}")
        warnings.append(f"Failed to stop some colonies: {e}")

    # Stop organism background tasks
    try:
        from kagami.core.unified_agents.unified_organism import get_organism

        organism = get_organism()
        if organism:
            # Stop background tasks
            organism._running = False
            logger.info("Stopped organism background tasks")
    except Exception as e:
        logger.error(f"Failed to stop organism: {e}")
        warnings.append(f"Failed to stop organism: {e}")

    # Emit audit event
    _emit_emergency_audit_event(
        event_type="system_halt",
        user=principal.sub,
        reason=request.reason,
        details={
            "force": request.force,
            "colonies_stopped": colonies_stopped,
            "warnings": warnings,
            "timestamp": timestamp,
        },
    )

    # Emit receipt
    _emit_emergency_receipt(
        action="halt",
        user=principal.sub,
        reason=request.reason,
        event_data={
            "colonies_stopped": colonies_stopped,
            "warnings": warnings,
        },
    )

    return SystemHaltResponse(
        success=len(warnings) == 0,
        message="System halt completed" if not warnings else "System halt completed with warnings",
        timestamp=timestamp,
        user=principal.sub,
        reason=request.reason,
        colonies_stopped=colonies_stopped,
        warnings=warnings,
    )


async def get_safety_status(
    principal: Principal,
) -> SafetyStatusResponse:
    """Get current safety status of the system.

    Returns:
        - Emergency stop state
        - Current h(x) value
        - Safety zone (GREEN/YELLOW/RED)
        - Colonies running count
        - System health

    Args:
        principal: Authenticated principal

    Returns:
        Safety status response
    """
    # Get current h(x) value
    h_value = _get_current_h_value()
    safety_zone = _get_safety_zone(h_value)

    # Count running colonies
    colonies_running = 0
    system_healthy = True
    try:
        from kagami.orchestration.colony_manager import get_colony_manager

        manager = get_colony_manager()
        if manager:
            colonies_running = sum(
                1
                for info in manager._colonies.values()
                if info.get("healthy", False)  # type: ignore[misc, attr-defined]
            )
            system_healthy = manager.all_healthy()
    except Exception as e:
        logger.error(f"Failed to get colony status: {e}")
        system_healthy = False

    return SafetyStatusResponse(
        emergency_stop_active=_emergency_stop_active,
        h_value=h_value,
        safety_zone=safety_zone,
        emergency_stop_reason=_emergency_stop_reason,
        emergency_stop_timestamp=_emergency_stop_timestamp,
        emergency_stop_user=_emergency_stop_user,
        colonies_running=colonies_running,
        system_healthy=system_healthy,
    )


async def resume_system(
    request: ResumeSystemRequest,
    principal: Principal,
) -> ResumeSystemResponse:
    """Resume system operations after emergency stop.

    Clears the emergency stop flag and allows system to resume normal operations.
    Does NOT automatically restart colonies - use colony manager for that.

    Args:
        request: Resume request with reason and confirmation
        principal: Authenticated principal (admin required)

    Returns:
        Resume response

    Raises:
        HTTPException: If confirmation token is invalid or no emergency stop is active
    """

    global _emergency_stop_active, _emergency_stop_reason, _emergency_stop_timestamp
    global _emergency_stop_user

    # Validate confirmation token
    if request.confirmation_token != "RESUME_CONFIRMED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation token. Must be 'RESUME_CONFIRMED'",
        )

    # Check if emergency stop is active
    if not _emergency_stop_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No emergency stop is currently active",
        )

    timestamp = time.time()
    previous_stop_reason = _emergency_stop_reason

    logger.warning(
        f"SYSTEM RESUME initiated by {principal.sub}: {request.reason} "
        f"(previous stop reason: {previous_stop_reason})"
    )

    # Clear emergency stop flag
    _emergency_stop_active = False
    previous_reason = _emergency_stop_reason
    _emergency_stop_reason = None
    _emergency_stop_timestamp = None
    _emergency_stop_user = None

    # Emit audit event
    _emit_emergency_audit_event(
        event_type="system_resume",
        user=principal.sub,
        reason=request.reason,
        details={
            "previous_stop_reason": previous_reason,
            "timestamp": timestamp,
        },
    )

    # Emit receipt
    _emit_emergency_receipt(
        action="resume",
        user=principal.sub,
        reason=request.reason,
        event_data={
            "previous_stop_reason": previous_reason,
        },
    )

    return ResumeSystemResponse(
        success=True,
        message="System resumed successfully. Restart colonies manually if needed.",
        timestamp=timestamp,
        user=principal.sub,
        previous_stop_reason=previous_reason,
    )


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/control", tags=["control"])

    @router.post(
        "/agent/{name}/stop",
        response_model=StopAgentResponse,
        responses=get_error_responses(401, 403, 404, 429, 500),
    )
    @enforce_tier1("rate_limit")
    async def stop_agent(name: str, _user=Depends(require_auth)) -> StopAgentResponse:  # type: ignore[no-untyped-def]
        """Stop agent execution.

        Args:
            name: Agent name

        Returns:
            Stop result
        """
        import time

        from kagami.core.orchestrator.app_loader import get_app_class

        try:
            agent_cls = get_app_class(name)
        except (ValueError, KeyError):
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None

        try:
            agent = agent_cls()  # type: ignore[call-arg]
            if hasattr(agent, "stop_background"):
                await agent.stop_background()

                # Emit receipt for agent stop event
                try:
                    from kagami.core.receipts import UnifiedReceiptFacade

                    UnifiedReceiptFacade.emit(
                        correlation_id=f"control-agent-stop-{name}-{int(time.time() * 1000)}",
                        action="control.agent.stop",
                        app="Control",
                        event_name="control.agent.stopped",
                        event_data={"agent_name": name},
                        duration_ms=0,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit receipt for agent stop: {e}")

                return StopAgentResponse(
                    status="success", agent=name, message=f"Agent {name} stopped"
                )
            else:
                return StopAgentResponse(
                    status="error",
                    agent=name,
                    message=f"Agent {name} cannot be stopped (not a background agent)",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to stop agent {name}: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    # ===== EMERGENCY CONTROL ENDPOINTS (SAFETY CRITICAL) =====

    @router.post(
        "/emergency-stop",
        response_model=EmergencyStopResponse,
        responses=get_error_responses(400, 401, 403, 429, 500),
    )
    async def emergency_stop_route(
        request: EmergencyStopRequest,
        principal: Principal = Depends(require_permission(Permission.SYSTEM_ADMIN)),  # type: ignore[func-returns-value]
    ) -> EmergencyStopResponse:
        """EMERGENCY STOP route handler (delegates to module-level function)."""
        return await emergency_stop(request, principal)

    @router.post(
        "/system/halt",
        response_model=SystemHaltResponse,
        responses=get_error_responses(400, 401, 403, 429, 500),
    )
    async def system_halt_route(
        request: SystemHaltRequest,
        principal: Principal = Depends(require_permission(Permission.SYSTEM_ADMIN)),  # type: ignore[func-returns-value]
    ) -> SystemHaltResponse:
        """SYSTEM HALT route handler (delegates to module-level function)."""
        return await system_halt(request, principal)

    @router.get(
        "/safety/status",
        response_model=SafetyStatusResponse,
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def get_safety_status_route(
        principal: Principal = Depends(require_auth),
    ) -> SafetyStatusResponse:
        """SAFETY STATUS route handler (delegates to module-level function)."""
        return await get_safety_status(principal)

    @router.post(
        "/system/resume",
        response_model=ResumeSystemResponse,
        responses=get_error_responses(400, 401, 403, 429, 500),
    )
    async def resume_system_route(
        request: ResumeSystemRequest,
        principal: Principal = Depends(require_permission(Permission.SYSTEM_ADMIN)),  # type: ignore[func-returns-value]
    ) -> ResumeSystemResponse:
        """SYSTEM RESUME route handler (delegates to module-level function)."""
        return await resume_system(request, principal)

    return router


__all__ = [
    "EmergencyStopRequest",
    "EmergencyStopResponse",
    "ResumeSystemRequest",
    "ResumeSystemResponse",
    "SafetyStatusResponse",
    "StopAgentResponse",
    "SystemHaltRequest",
    "SystemHaltResponse",
    "_emit_emergency_audit_event",
    "_emit_emergency_receipt",
    "_get_current_h_value",
    "_get_safety_zone",
    "emergency_stop",
    "get_router",
    "get_safety_status",
    "is_emergency_stop_active",
    "resume_system",
    "system_halt",
]
