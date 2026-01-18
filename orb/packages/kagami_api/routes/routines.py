"""Routines API — Manage SmartHome adaptive routines and suggestions.

Endpoints:
- GET /routines - List all routines
- GET /routines/{routine_id} - Get routine details
- POST /routines/{routine_id}/execute - Execute a routine
- GET /routines/suggestions - Get pending suggestions
- POST /routines/suggestions/{suggestion_id}/approve - Approve a suggestion
- POST /routines/suggestions/{suggestion_id}/reject - Reject a suggestion

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kagami_api.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routines", tags=["routines"], dependencies=[Depends(require_auth)])


# =============================================================================
# Request/Response Models
# =============================================================================


class RoutineResponse(BaseModel):
    """Routine details."""

    id: str
    name: str
    description: str
    safety_critical: bool
    params: dict[str, Any]
    param_ranges: dict[str, tuple[float, float]]


class RoutineExecuteResponse(BaseModel):
    """Response after executing a routine."""

    routine_id: str
    success: bool
    actions_count: int
    error: str | None = None


class SuggestionResponse(BaseModel):
    """Suggestion details."""

    id: str
    routine_id: str
    param_name: str | None
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float
    source: str
    status: str = "pending"


class RejectRequest(BaseModel):
    """Request body for rejection."""

    reason: str | None = None


# =============================================================================
# Routine Endpoints
# =============================================================================


@router.get("", response_model=list[RoutineResponse])
async def list_routines() -> list[dict[str, Any]]:
    """List all registered routines."""
    try:
        from kagami_smarthome.routines import get_routine_registry

        registry = get_routine_registry()
        routines = registry.get_all_routines()

        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "safety_critical": r.safety_critical,
                "params": r.params,
                "param_ranges": r.param_ranges,
            }
            for r in routines
        ]

    except ImportError:
        logger.warning("SmartHome routines not available")
        return []


@router.get("/{routine_id}", response_model=RoutineResponse)
async def get_routine(routine_id: str) -> dict[str, Any]:
    """Get details of a specific routine."""
    try:
        from kagami_smarthome.routines import get_routine_registry

        registry = get_routine_registry()
        routine = registry.get_routine(routine_id)

        if not routine:
            raise HTTPException(status_code=404, detail=f"Routine not found: {routine_id}")

        return {
            "id": routine.id,
            "name": routine.name,
            "description": routine.description,
            "safety_critical": routine.safety_critical,
            "params": routine.params,
            "param_ranges": routine.param_ranges,
        }

    except ImportError as err:
        raise HTTPException(status_code=503, detail="SmartHome routines not available") from err


@router.post("/{routine_id}/execute", response_model=RoutineExecuteResponse)
async def execute_routine(routine_id: str) -> dict[str, Any]:
    """Execute a routine manually.

    SECURITY: Performs CBF safety check before execution per h(x) >= 0 invariant.
    """
    try:
        from kagami_smarthome import get_smart_home
        from kagami_smarthome.context import get_context_engine
        from kagami_smarthome.execution import get_executor
        from kagami_smarthome.routines import get_routine_registry

        # Get components
        controller = await get_smart_home()
        context_engine = get_context_engine(controller)
        executor = get_executor(controller)
        registry = get_routine_registry()

        # Get context
        context = await context_engine.get_context()

        # SECURITY: CBF safety check before routine execution
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            cbf_result = await check_cbf_for_operation(
                operation=f"execute_routine:{routine_id}",
                context={"routine_id": routine_id, "source": "api"},
            )
            if not cbf_result.is_safe:
                logger.warning(
                    f"CBF blocked routine execution: {routine_id}, h(x)={cbf_result.h_x}"
                )
                return {
                    "routine_id": routine_id,
                    "success": False,
                    "actions_count": 0,
                    "error": f"Safety check failed: h(x)={cbf_result.h_x:.3f}",
                }
        except ImportError:
            # CBF not available - FAIL CLOSED per h(x) >= 0
            logger.error(f"CBF service unavailable - blocking routine {routine_id}")
            return {
                "routine_id": routine_id,
                "success": False,
                "actions_count": 0,
                "error": "Safety service unavailable - action blocked",
            }

        # Execute routine
        result = await registry.execute_routine(routine_id, context, executor)

        return {
            "routine_id": result.routine_id,
            "success": result.success,
            "actions_count": len(result.actions),
            "error": result.error,
        }

    except ImportError as err:
        raise HTTPException(status_code=503, detail="SmartHome routines not available") from err
    except Exception as e:
        logger.error(f"Failed to execute routine {routine_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Suggestion Endpoints
# =============================================================================


@router.get("/suggestions", response_model=list[SuggestionResponse])
async def get_pending_suggestions() -> list[dict[str, Any]]:
    """Get pending routine improvement suggestions."""
    try:
        from kagami_smarthome.routines import get_routine_registry

        registry = get_routine_registry()
        suggestions = registry.get_pending_suggestions()

        return [s.to_dict() for s in suggestions]

    except ImportError:
        logger.warning("SmartHome routines not available")
        return []


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
async def approve_suggestion(suggestion_id: str) -> dict[str, Any]:
    """Approve a routine improvement suggestion."""
    try:
        from kagami_smarthome.routines import get_routine_registry

        registry = get_routine_registry()
        suggestion = registry.get_suggestion(suggestion_id)

        if not suggestion:
            raise HTTPException(status_code=404, detail=f"Suggestion not found: {suggestion_id}")

        # Apply the suggestion
        success = await registry.apply_suggestion(suggestion)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply suggestion")

        # Emit receipt
        _emit_suggestion_receipt(suggestion_id, "approved", None)

        return suggestion.to_dict()

    except ImportError as err:
        raise HTTPException(status_code=503, detail="SmartHome routines not available") from err


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
async def reject_suggestion(
    suggestion_id: str, body: RejectRequest | None = None
) -> dict[str, Any]:
    """Reject a routine improvement suggestion."""
    try:
        from kagami_smarthome.routines import get_routine_registry

        registry = get_routine_registry()
        suggestion = registry.get_suggestion(suggestion_id)

        if not suggestion:
            raise HTTPException(status_code=404, detail=f"Suggestion not found: {suggestion_id}")

        reason = body.reason if body else None
        registry.reject_suggestion(suggestion_id, reason)

        # Emit receipt
        _emit_suggestion_receipt(suggestion_id, "rejected", reason)

        return suggestion.to_dict()

    except ImportError as err:
        raise HTTPException(status_code=503, detail="SmartHome routines not available") from err


# =============================================================================
# Helpers
# =============================================================================


def _emit_suggestion_receipt(suggestion_id: str, action: str, reason: str | None) -> None:
    """Emit receipt for suggestion action."""
    try:
        from kagami.core.receipts.facade import URF, emit_receipt

        emit_receipt(
            URF.generate_correlation_id(),
            f"routine.suggestion.{action}",
            event_data={"suggestion_id": suggestion_id, "reason": reason},
        )
    except ImportError:
        logger.debug(f"Suggestion {action}: {suggestion_id}")


__all__ = ["router"]
