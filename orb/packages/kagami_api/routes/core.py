"""Core API routes - command execution.

The primary command endpoint for K OS.

SECURITY FIX (December 15, 2025):
- Removed KAGAMI_COMMAND_PUBLIC environment variable bypass
- Enforced mandatory authentication with Permission.TOOL_EXECUTE
- Added CBF safety check before command execution
- Added comprehensive audit logging with correlation_id
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from kagami_api.audit_logger import AuditEventType, AuditSeverity, get_audit_logger
from kagami_api.idempotency import ensure_idempotency
from kagami_api.rbac import Permission, require_permission
from kagami_api.response_schemas import get_error_responses
from kagami_api.schemas.command import (
    CommandBlockedResponse,
    CommandFallbackResponse,
    CommandResponse,
    CommandSuccessResponse,
)
from kagami_api.security import Principal, require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["command"])

    @router.post(
        "/api/command",
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
        response_model=CommandResponse,
        responses=get_error_responses(400, 401, 403, 422, 429, 500, 503),
    )
    async def execute_command(
        request: Request,
        command: dict[str, Any],
        current_user: Principal = Depends(require_auth),
    ) -> CommandFallbackResponse | CommandBlockedResponse | CommandSuccessResponse:
        """Execute a command through K OS.

        SECURITY:
        - Requires authentication (current_user)
        - Requires Permission.TOOL_EXECUTE permission
        - Performs CBF safety check before execution
        - Logs all operations to audit trail with correlation_id
        """
        start = time.time()
        audit_logger = get_audit_logger()

        # Generate correlation_id for audit trail
        correlation_id = str(uuid.uuid4())

        await ensure_idempotency(request)
        kagami_intelligence = getattr(request.app.state, "kagami_intelligence", None)
        if not kagami_intelligence:
            return CommandFallbackResponse(ok=True)

        # Build intent with correlation_id
        intent_dict = {
            "action": command.get("command", "command.execute"),
            "params": {
                "text": command.get("text", ""),
                "context": command.get("context", {}),
                "parameters": command.get("parameters", {}),
            },
            "metadata": {
                "source": "api",
                "endpoint": "/api/command",
                "correlation_id": correlation_id,
            },
            "correlation_id": correlation_id,
        }

        # CBF SAFETY CHECK - run before command execution
        try:
            from kagami.core.orchestrator.safety_gates import get_safety_gates

            safety_gates = get_safety_gates()
            safety_result = await safety_gates.check_cbf_safety(intent_dict)

            if not safety_result.safe:
                # Audit log the blocked operation
                audit_logger.log_security_event(
                    event_type=AuditEventType.SYSTEM_COMMAND,
                    severity=AuditSeverity.CRITICAL,
                    user_id=current_user.user_id,
                    request=request,
                    outcome="blocked",
                    details={
                        "correlation_id": correlation_id,
                        "command": command.get("command", ""),
                        "text": command.get("text", "")[:200],  # Truncate for logging
                        "cbf_reason": safety_result.reason,
                        "cbf_detail": safety_result.detail,
                        "h_x": safety_result.h_x,
                    },
                )

                # Return error response
                return CommandBlockedResponse(
                    status="blocked",
                    reason=safety_result.reason,
                    detail=safety_result.detail,
                    correlation_id=correlation_id,
                    timestamp=datetime.utcnow().isoformat(),
                    h_x=safety_result.h_x,
                )
        except Exception as e:
            # FAIL-CLOSED: If CBF check fails to execute, block the operation
            logger.error(f"CBF safety check failed: {e} - BLOCKING operation")
            audit_logger.log_security_event(
                event_type=AuditEventType.SYSTEM_COMMAND,
                severity=AuditSeverity.CRITICAL,
                user_id=current_user.user_id,
                request=request,
                outcome="blocked",
                details={
                    "correlation_id": correlation_id,
                    "command": command.get("command", ""),
                    "error": "safety_check_failed",
                    "exception": str(e),
                },
            )
            return CommandBlockedResponse(
                status="blocked",
                reason="safety_check_error",
                detail=f"Safety verification failed: {e}",
                correlation_id=correlation_id,
                timestamp=datetime.utcnow().isoformat(),
            )

        # Audit log the command execution attempt
        audit_logger.log_system_event(
            event_type=AuditEventType.SYSTEM_COMMAND,
            user_id=current_user.user_id,  # type: ignore[arg-type]
            resource=f"/api/command:{command.get('command', '')}",
            request=request,
            outcome="initiated",
            details={
                "correlation_id": correlation_id,
                "command": command.get("command", ""),
                "text": command.get("text", "")[:200],  # Truncate for logging
            },
        )

        # Execute the command
        response = await kagami_intelligence.process_intent(intent_dict)

        # Audit log successful execution
        audit_logger.log_system_event(
            event_type=AuditEventType.SYSTEM_COMMAND,
            user_id=current_user.user_id,  # type: ignore[arg-type]
            resource=f"/api/command:{command.get('command', '')}",
            request=request,
            outcome="success",
            details={
                "correlation_id": correlation_id,
                "command": command.get("command", ""),
                "duration_ms": int((time.time() - start) * 1000),
            },
        )

        try:
            from kagami.core.schemas.receipt_schema import Receipt
        except Exception:
            Receipt = None  # type: ignore[assignment, misc]

        guardrails = {
            "rbac": "enforced",
            "cbf_safety": "passed",
            "csrf": "n/a",
            "rate_limit": "ok",
            "idempotency": "accepted",
        }
        now_ms = int(time.time() * 1000)
        elapsed_ms = int(max(0.0, (time.time() - start) * 1000))
        receipt_dict = {}
        if Receipt is not None:
            try:
                receipt_obj = Receipt(
                    correlation_id=correlation_id,
                    intent={
                        "action": "command.execute",
                        "app": "Core",
                        "args": {
                            "text": command.get("text", ""),
                            "command": command.get("command", ""),
                        },
                    },
                    event={
                        "name": "command.executed",
                        "data": {"response_kind": type(response).__name__},
                    },
                    duration_ms=elapsed_ms,
                    ts=now_ms,
                    guardrails=guardrails,
                    metrics={"endpoint": "/metrics"},
                )
                receipt_dict = receipt_obj.model_dump()
            except Exception:
                receipt_dict = {
                    "correlation_id": correlation_id,
                    "intent": {
                        "action": "command.execute",
                        "app": "Core",
                        "args": {
                            "text": command.get("text", ""),
                            "command": command.get("command", ""),
                        },
                    },
                    "event": {"name": "command.executed", "data": {}},
                    "duration_ms": elapsed_ms,
                    "ts": now_ms,
                    "guardrails": guardrails,
                    "metrics": {"endpoint": "/metrics"},
                }
        return CommandSuccessResponse(
            response=response,
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            correlation_id=correlation_id,
            receipt=receipt_dict,
        )

    return router
