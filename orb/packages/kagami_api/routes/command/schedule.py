"Unified Schedule API - Routines, Jobs, and Recurring Tasks.\n\nConsolidated from routines.py + scheduler.py + recurring.py.\n\nProvides:\n- Event-driven routines: /api/schedule/routines/*\n- One-time scheduled jobs: /api/schedule/jobs/*\n- Recurring tasks: /api/schedule/recurring/*\n"

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.core.events import E8Event, get_unified_bus
from kagami.core.receipts import emit_receipt
from kagami.core.recurring_scheduler import (
    ConflictStrategy,
    RecurrenceType,
    create_recurring,
    get_recommendations,
)
from pydantic import BaseModel, Field

from kagami_api.rbac import Permission, require_permission
from kagami_api.routes.user.auth import get_current_user

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/command/schedule", tags=["command", "schedule"])

    class RoutineRule(BaseModel):
        when_topic: str = Field(..., description="Event topic prefix to match")
        condition: dict[str, Any] | None = Field(
            default=None, description="Optional shallow key==value matches"
        )
        lang: str = Field(..., description="Intent LANG to execute when matched")
        require_confirm: bool = Field(
            default=True, description="High-risk actions require explicit confirm"
        )

    class RoutineCreateRequest(BaseModel):
        name: str
        rule: RoutineRule

    class RoutineResponse(BaseModel):
        id: str
        name: str
        rule: RoutineRule
        description: str | None = None

    _ROUTINES: dict[str, RoutineResponse] = {}

    @router.post("/routines/create", response_model=RoutineResponse)
    async def create_routine(
        req: RoutineCreateRequest, user: Any = Depends(get_current_user)
    ) -> RoutineResponse:
        """Create an event-driven routine that executes an intent when events match."""
        try:
            rid = uuid.uuid4().hex
            routine = RoutineResponse(
                id=rid, name=req.name, rule=req.rule, description="Auto-generated routine"
            )
            _ROUTINES[rid] = routine
            bus = get_unified_bus()

            async def _handler(event: E8Event) -> Any:
                try:
                    ok = True
                    cond = req.rule.condition or {}
                    # Allow conditions to match against payload + key event metadata.
                    event_dict: dict[str, Any] = dict(event.payload or {})
                    event_dict.setdefault("topic", event.topic)
                    if event.correlation_id:
                        event_dict.setdefault("correlation_id", event.correlation_id)
                    event_dict.setdefault("source_colony", event.source_colony)
                    event_dict.setdefault("target_colony", event.target_colony)
                    for k, v in cond.items():
                        if event_dict.get(k) != v:
                            ok = False
                            break
                    if not ok:
                        return
                    from kagami.core.schemas.schemas.intent_lang import parse_intent

                    intent = await parse_intent(req.rule.lang)
                    event_payload = intent.to_event()
                    event_payload.setdefault("metadata", {})
                    event_payload["metadata"].setdefault("source", "routine")
                    await bus.publish("intent.execute", event_payload)
                except Exception:
                    return

            bus.subscribe(req.rule.when_topic, _handler)
            return routine
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None

    class RoutinesListResponse(BaseModel):
        """Response for routines list with pagination."""

        routines: list[RoutineResponse]
        total: int
        page: int = 1
        per_page: int = 20
        has_more: bool = False

    @router.get("/routines", response_model=RoutinesListResponse)
    async def list_routines(  # type: ignore[no-untyped-def]
        page: int = 1,
        per_page: int = 20,
    ):
        """List all registered event-driven routines with pagination."""
        all_routines = list(_ROUTINES.values())
        total = len(all_routines)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_routines = all_routines[start_idx:end_idx]
        has_more = end_idx < total

        return RoutinesListResponse(
            routines=paginated_routines,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
        )

    class EnqueueRequest(BaseModel):
        run_at: str
        intent: dict[str, Any]

    class CreateRecurringRequest(BaseModel):
        """Request to create a recurring job."""

        name: str = Field(..., min_length=1, max_length=200)
        description: str | None = None
        schedule: str = Field(..., description="Cron expr, interval, or natural language")
        intent: dict[str, Any] = Field(..., description="Intent to execute")
        persona: str | None = Field(None, description="Owner persona for preferences")
        timezone_offset: int = Field(0, description="Minutes from UTC")
        conflict_strategy: ConflictStrategy | None = None
        preferred_times: list[str] | None = None
        avoid_times: list[str] | None = None

    class UpdateFeedbackRequest(BaseModel):
        """Feedback for a completed recurring job execution."""

        job_id: str
        success: bool
        duration_ms: float | None = None
        user_satisfaction: float | None = Field(None, ge=0, le=1)

    class RecurringJobResponse(BaseModel):
        """Response for recurring job operations."""

        id: str
        name: str
        description: str
        schedule: str
        recurrence_type: RecurrenceType
        enabled: bool
        owner_persona: str | None
        next_run_at: str | None
        last_run_at: str | None
        run_count: int
        success_rate: float
        conflict_strategy: ConflictStrategy
        preferred_times: list[str]
        avoid_times: list[str]

    @router.post(
        "/recurring/create",
        response_model=RecurringJobResponse,
        dependencies=[Depends(require_permission(Permission.SYSTEM_WRITE))],  # type: ignore[func-returns-value]
    )
    async def create_recurring_job(  # type: ignore[no-untyped-def]
        request: Request,
        body: CreateRecurringRequest,
        user=Depends(get_current_user),
    ) -> RecurringJobResponse:
        """Create a new recurring job with intelligent scheduling."""
        try:
            persona = body.persona
            if not persona and user:
                if hasattr(user, "persona"):
                    persona = user.persona
                elif hasattr(user, "role"):
                    persona = f"human_{user.role}"
            job = create_recurring(
                name=body.name,
                schedule=body.schedule,
                intent=body.intent,
                description=body.description or f"Recurring task: {body.name}",
                persona=persona,
                timezone_offset=body.timezone_offset,
                conflict_strategy=body.conflict_strategy,
                preferred_times=body.preferred_times or [],
                avoid_times=body.avoid_times or [],
            )
            emit_receipt(
                correlation_id=job["id"],  # type: ignore[index]
                action="recurring.create",
                app="scheduler",
                args={"name": body.name, "schedule": body.schedule},
                event_name="recurring.created",
                event_data={"job_id": job["id"]},  # type: ignore[index]
            )
            return RecurringJobResponse(**job)  # type: ignore[arg-type]
        except Exception as e:
            logger.error(f"Failed to create recurring job: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.get("/recurring/{job_id}/recommendations")
    async def get_job_recommendations(job_id: str) -> dict[str, Any]:
        """Get personalized recommendations for improving a recurring job."""
        try:
            # get_recommendations is async and accepts an optional context dict.
            recommendations = await get_recommendations(context={"job_id": job_id})
            return {"status": "ok", "recommendations": recommendations}
        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    return router
