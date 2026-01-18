"""Plan management API routes.

Handles CRUD operations for plans, tasks, and insights.

Consolidated: December 8, 2025
- Inlined plans_helpers.py functions
"""

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.core.memory import remember
from kagami.core.receipts import emit_receipt as _emit_receipt
from kagami.core.safety import enforce_tier1
from kagami.core.safety.cbf_integration import check_cbf_for_operation
from kagami.core.schemas.schemas.intents import Intent as ApiIntent
from kagami.core.schemas.schemas.intents import IntentState as ApiIntentState
from kagami.core.schemas.schemas.intents import IntentVerb as ApiIntentVerb
from kagami.core.schemas.schemas.plans import (
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    TaskList,
    TaskResponse,
    TaskUpdateRequest,
)
from kagami.core.schemas.types import Intent, IntentType
from kagami.core.services.llm.structured import (
    GenerationStrategy,
    generate_structured_enhanced,
    select_model_for,
)
from kagami.core.utils.ids import generate_correlation_id
from pydantic import BaseModel, HttpUrl

from kagami_api.idempotency import ensure_idempotency
from kagami_api.rbac import Permission, require_permission
from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/plans", tags=["mind"])

    # =============================================================================
    # HELPER FUNCTIONS (inlined from plans_helpers.py)
    # =============================================================================

    def build_gaia_metadata(*args: Any, **kwargs: Any) -> Any:
        """Build consistent metadata for memory + receipts.

        Historically, "GAIA metadata" was used to standardize app/session fields for
        downstream storage/routing. The plans routes rely on it for `remember()`.
        """
        # Backward-compatible signature: callers may pass kwargs only.
        kind = kwargs.pop("kind", None)
        app = kwargs.pop("app", None)
        session_id = kwargs.pop("session_id", None)
        base_metadata = kwargs.pop("base_metadata", None)

        md: dict[str, Any] = {}
        if isinstance(base_metadata, dict):
            md.update(base_metadata)

        if kind is not None:
            md["kind"] = kind
        if app is not None:
            md["app"] = app
        if session_id is not None:
            md["session_id"] = session_id

        # Always include a stable timestamp for ordering/debugging.
        md.setdefault("timestamp", datetime.utcnow().isoformat())

        # Merge any remaining kwargs (best-effort, skipping None).
        for k, v in kwargs.items():
            if v is not None:
                md[k] = v
        return md

    async def emit_plan_receipt(
        correlation_id: str,
        action: str,
        args: dict[str, Any],
        event_name: str,
        status: str,
        duration_ms: int = 0,
    ) -> None:
        """Emit a standard plan receipt."""
        try:
            _emit_receipt(
                correlation_id=correlation_id,
                action=action,
                app="plans",
                args=args,
                event_name=event_name,
                event_data={"status": status, **args},
                duration_ms=duration_ms,
            )
        except Exception:
            pass

    async def publish_plan_intent(
        action: str,
        target: str,
        metadata: dict[str, Any],
    ) -> None:
        """Publish an intent to the event bus."""
        try:
            from kagami.core.events import get_unified_bus as _get_bus

            bus = _get_bus()
            api_intent = ApiIntent(
                action=ApiIntentVerb.EXECUTE,
                target=target,
                state=ApiIntentState.IMMEDIATE,
                source="api.plans",
                condition=None,
                alternative=None,
                amplification=None,
                correlation_id=None,
                timestamp=None,
                user_id=None,
                metadata=metadata,
            )
            await bus.publish_intent(api_intent.to_event())  # type: ignore[attr-defined]
        except Exception:
            pass

    async def remember_plan_event(
        text: str,
        plan_id: str,
        event_type: str,
        task_id: str | None = None,
    ) -> None:
        """Store plan event in memory."""
        try:
            base_metadata = {"event": event_type, "plan_id": plan_id}
            if task_id:
                base_metadata["task_id"] = task_id

            md = build_gaia_metadata(
                kind="event",
                app="Plans",
                session_id=None,
                base_metadata=base_metadata,
            )

            tags = ["plans", str(event_type)]
            tags.append(f"plan:{plan_id}")
            if task_id:
                tags.append(f"task:{task_id}")

            # Canonical memory API: store the text as content; keep structured fields in metadata.
            await remember(
                content=str(text),
                metadata=md,
                importance=0.6,
                tags=tags,
            )
        except Exception:
            pass

    try:
        from kagami.observability.metrics import REGISTRY
        from prometheus_client import Counter, Histogram

        PLAN_OPERATIONS_TOTAL = Counter(
            "kagami_plan_operations_total",
            "Total plan operations",
            ["operation", "status"],
            registry=REGISTRY,
        )
        PLAN_OPERATION_DURATION = Histogram(
            "kagami_plan_operation_duration_seconds",
            "Plan operation duration",
            ["operation"],
            registry=REGISTRY,
        )
    except Exception:
        PLAN_OPERATIONS_TOTAL: Any = None  # type: ignore[no-redef]
        PLAN_OPERATION_DURATION: Any = None  # type: ignore[no-redef]

    async def get_orchestrator_and_plans_app(request: Request) -> tuple[Any, ...]:
        """Helper function to get orchestrator and plans app.

        Fail fast if not properly initialized - tests should set up the app correctly.
        """
        orchestrator = getattr(request.app.state, "orchestrator", None)
        if not orchestrator:
            raise HTTPException(
                status_code=503,
                detail="orchestrator_unavailable: Application not properly initialized. Ensure lifespan initialization completed successfully.",
            )
        plans_app = orchestrator.get_entity("plans")
        if not plans_app:
            raise HTTPException(status_code=404, detail="Plans app not found")
        if not getattr(plans_app, "_plans_repo", None):
            raise HTTPException(
                status_code=503, detail="Plans service unavailable (database not initialized)"
            )
        return (orchestrator, plans_app)

    class IcsImportRequest(BaseModel):
        """Payload for importing calendar events (ICS) into a plan as tasks.

        Provide either raw ICS text or a URL to a public ICS feed (e.g., Google Calendar
        secret address). If both are provided, `ics_text` takes precedence.
        """

        ics_text: str | None = None
        ics_url: HttpUrl | None = None
        default_status: str | None = "pending"
        default_priority: str | None = "medium"

    class PlanArtifact(BaseModel):
        """Structured plan artifact produced by offline mode.

        Accepts a flexible schema but enforces key fields we rely on.
        """

        title: str
        description: str | None = None
        goals: list[str] | None = None
        tasks: list[dict[str, Any]] | None = None
        timeline: dict[str, Any] | None = None
        owners: list[str] | None = None
        risks: list[str] | None = None
        metadata: dict[str, Any] | None = None

    class PlanSuggestRequest(BaseModel):
        goal: str
        context: dict[str, Any] | None = None

    class PlansListResponse(BaseModel):
        """Response for listing plans."""

        plans: list[PlanResponse]
        total: int
        page: int = 1
        per_page: int = 20
        has_more: bool = False

    @router.get(
        "/",
        response_model=PlansListResponse,
        responses=get_error_responses(401, 403, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_READ))],  # type: ignore[func-returns-value]
        summary="List plans",
        description="List all plans with pagination support.",
    )
    async def list_plans(
        request: Request,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        plan_type: str | None = None,
    ) -> PlansListResponse:
        """List all plans with optional filters."""
        start = time.time()
        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)

            # Get plans from repository
            plans_repo = getattr(plans_app, "_plans_repo", None)
            if not plans_repo:
                return PlansListResponse(plans=[], total=0, page=page, per_page=per_page)

            # Query plans
            offset = (page - 1) * per_page
            plans_list = []
            total = 0

            try:
                # Try to get plans with pagination
                if hasattr(plans_repo, "list_plans"):
                    result = await plans_repo.list_plans(
                        offset=offset,
                        limit=per_page,
                        status=status,
                        plan_type=plan_type,
                    )
                    plans_list = result.get("plans", [])
                    total = result.get("total", len(plans_list))
                elif hasattr(plans_repo, "get_all_plans"):
                    all_plans = await plans_repo.get_all_plans()
                    # Apply filters
                    if status:
                        all_plans = [p for p in all_plans if p.get("status") == status]
                    if plan_type:
                        all_plans = [p for p in all_plans if p.get("type") == plan_type]
                    total = len(all_plans)
                    plans_list = all_plans[offset : offset + per_page]
            except Exception as e:
                logger.error(f"Failed to list plans: {e}")
                return PlansListResponse(plans=[], total=0, page=page, per_page=per_page)

            # Convert to response models
            response_plans = []
            for plan in plans_list:
                if hasattr(plans_app, "_plan_to_dict"):
                    plan = await plans_app._plan_to_dict(plan, include_tasks=False)

                response_plans.append(
                    PlanResponse(
                        id=plan.get("id"),
                        name=plan.get("name"),
                        description=plan.get("description"),
                        type=plan.get("type", "project"),
                        status=plan.get("status", "active"),
                        progress=plan.get("progress", 0),
                        created_at=plan.get("created_at"),
                        updated_at=plan.get("updated_at"),
                        target_date=plan.get("target_date"),
                        emotional_tags=plan.get("emotional_tags", []),
                        tasks=[],  # Don't include tasks in list view
                        metadata=plan.get("metadata", {}),
                    )
                )

            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(f"Performance violation in list_plans: {elapsed_ms:.2f}ms")

            return PlansListResponse(
                plans=response_plans,
                total=total,
                page=page,
                per_page=per_page,
                has_more=(page * per_page) < total,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to list plans: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from None

    @router.post(
        "/",
        response_model=PlanResponse,
        responses=get_error_responses(400, 401, 403, 422, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_WRITE))],  # type: ignore[func-returns-value]
    )
    async def create_plan(request: Request, plan_data: PlanCreateRequest) -> PlanResponse:
        """Create a new plan."""
        await ensure_idempotency(request)
        start = time.time()
        correlation_id = generate_correlation_id(prefix="plan_create")

        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.plans.create",
            action="create",
            target="plan",
            params=plan_data.model_dump(),
            metadata={"endpoint": "/api/plans/", "name": plan_data.name},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        await emit_plan_receipt(
            correlation_id=correlation_id,
            action="plan.create",
            args={"name": plan_data.name},
            event_name="PLAN",
            status="planning",
        )

        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)
            plan: dict[str, Any] = {}
            created_via_repo = False
            try:
                plans_repo = getattr(plans_app, "_plans_repo", None)
                if plans_repo is not None:
                    created_row = await plans_repo.create_plan(
                        name=plan_data.name,
                        description=plan_data.description,
                        plan_type=str(plan_data.type or "project"),
                        user_id=None,
                        target_date=plan_data.target_date,
                        emotional_tags=plan_data.emotional_tags or [],
                        metadata={},
                        visibility=str(plan_data.visibility or "public"),
                    )
                    if hasattr(plans_app, "_plan_to_dict"):
                        plan = await plans_app._plan_to_dict(created_row, include_tasks=True)
                    created_via_repo = True
            except Exception:
                created_via_repo = False
            if not created_via_repo:
                raise HTTPException(
                    status_code=503, detail="Plans repository unavailable"
                ) from None

            await emit_plan_receipt(
                correlation_id=correlation_id,
                action="plan.create",
                args={"name": plan_data.name, "plan_id": plan.get("id")},
                event_name="EXECUTE",
                status="executing",
            )

            response = PlanResponse(
                id=plan.get("id"),
                name=plan.get("name") or plan_data.name,
                description=plan.get("description") or plan_data.description,
                type=plan.get("type", "project"),
                status=plan.get("status", "active"),
                progress=plan.get("progress", 0),
                created_at=plan.get("created_at"),
                updated_at=plan.get("updated_at"),
                target_date=plan.get("target_date"),
                emotional_tags=plan.get("emotional_tags", []),
                tasks=plan.get("tasks", []),
                metadata=plan.get("metadata", {}),
            )

            await remember_plan_event(
                text=f"Plan created: {response.name}",
                plan_id=response.id,
                event_type="plan.created",
            )

            await publish_plan_intent(
                action="plan.create",
                target="plan.create",
                metadata={"plan_id": response.id, "name": response.name},
            )

            duration_ms = int((time.time() - start) * 1000)

            await emit_plan_receipt(
                correlation_id=correlation_id,
                action="plan.create",
                args={"name": plan_data.name, "plan_id": response.id},
                event_name="VERIFY",
                status="success",
                duration_ms=duration_ms,
            )

            try:
                if PLAN_OPERATIONS_TOTAL:
                    PLAN_OPERATIONS_TOTAL.labels(operation="create", status="success").inc()
                if PLAN_OPERATION_DURATION:
                    PLAN_OPERATION_DURATION.labels(operation="create").observe(duration_ms / 1000)
            except Exception as e:
                logger.debug(f"Metric recording failed: {e}")
                # Metrics are non-critical
            if duration_ms > 50:
                logger.warning(f"Performance violation in create_plan: {duration_ms:.2f}ms")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            try:
                if PLAN_OPERATIONS_TOTAL:
                    PLAN_OPERATIONS_TOTAL.labels(operation="create", status="error").inc()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Internal server error") from None

    @router.get(
        "/{plan_id}",
        response_model=PlanResponse,
        responses=get_error_responses(401, 403, 404, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_READ))],  # type: ignore[func-returns-value]
    )
    async def get_plan(request: Request, plan_id: str) -> PlanResponse:
        """Get a specific plan by ID."""
        start = time.time()
        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)
            plan = await plans_app.get_plan(plan_id)
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found")
            response = PlanResponse(
                id=plan.get("id"),
                name=plan.get("name"),
                description=plan.get("description"),
                type=plan.get("type", "project"),
                status=plan.get("status", "active"),
                progress=plan.get("progress", 0),
                created_at=plan.get("created_at"),
                updated_at=plan.get("updated_at"),
                target_date=plan.get("target_date"),
                emotional_tags=plan.get("emotional_tags", []),
                tasks=plan.get("tasks", []),
                metadata=plan.get("metadata", {}),
            )
            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(f"Performance violation in get_plan: {elapsed_ms:.2f}ms")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get plan {plan_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from None

    @router.put(
        "/{plan_id}",
        response_model=PlanResponse,
        responses=get_error_responses(400, 401, 403, 404, 422, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_WRITE))],  # type: ignore[func-returns-value]
    )
    async def update_plan(
        request: Request, plan_id: str, updates: PlanUpdateRequest
    ) -> PlanResponse:
        """Update a plan."""
        await ensure_idempotency(request)
        start = time.time()
        correlation_id = generate_correlation_id(prefix="plan_update")

        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.plans.update",
            action="update",
            target="plan",
            params={"plan_id": plan_id, **updates.model_dump()},
            metadata={"endpoint": f"/api/plans/{plan_id}"},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        await emit_plan_receipt(
            correlation_id=correlation_id,
            action="plan.update",
            args={"plan_id": plan_id},
            event_name="PLAN",
            status="planning",
        )

        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)
            intent = Intent(
                type=IntentType.COMMAND,
                content=f"Update plan {plan_id}",
                source="api",
                metadata={
                    "command": "update_plan",
                    "plan_id": plan_id,
                    "updates": updates.updates,
                    "description": f"Update plan {plan_id}",
                },
            )
            result = await plans_app.process_intent(intent)
            if not result or "error" in result:
                raise HTTPException(
                    status_code=400, detail=result.get("error", "Failed to update plan")
                )
            plan = result.get("plan", {})
            response = PlanResponse(
                id=plan.get("id"),
                name=plan.get("name"),
                description=plan.get("description"),
                type=plan.get("type", "project"),
                status=plan.get("status", "active"),
                progress=plan.get("progress", 0),
                created_at=plan.get("created_at"),
                updated_at=plan.get("updated_at"),
                target_date=plan.get("target_date"),
                emotional_tags=plan.get("emotional_tags", []),
                tasks=plan.get("tasks", []),
                metadata=plan.get("metadata", {}),
            )

            await remember_plan_event(
                text=f"Plan updated: {response.name}",
                plan_id=response.id,
                event_type="plan.updated",
            )

            await publish_plan_intent(
                action="plan.update", target="plan.update", metadata={"plan_id": response.id}
            )

            duration_ms = int((time.time() - start) * 1000)

            await emit_plan_receipt(
                correlation_id=correlation_id,
                action="plan.update",
                args={"plan_id": plan_id},
                event_name="VERIFY",
                status="success",
                duration_ms=duration_ms,
            )

            try:
                if PLAN_OPERATIONS_TOTAL:
                    PLAN_OPERATIONS_TOTAL.labels(operation="update", status="success").inc()
                if PLAN_OPERATION_DURATION:
                    PLAN_OPERATION_DURATION.labels(operation="update").observe(duration_ms / 1000)
            except Exception:
                pass
            if duration_ms > 50:
                logger.warning(f"Performance violation in update_plan: {duration_ms:.2f}ms")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {e}")
            try:
                if PLAN_OPERATIONS_TOTAL:
                    PLAN_OPERATIONS_TOTAL.labels(operation="update", status="error").inc()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Internal server error") from None

    @router.delete(
        "/{plan_id}",
        responses=get_error_responses(400, 401, 403, 404, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_ADMIN))],  # type: ignore[func-returns-value]
        response_model=None,
    )
    async def delete_plan(request: Request, plan_id: str) -> dict[str, Any]:
        """Delete a plan."""
        await ensure_idempotency(request)
        start = time.time()
        correlation_id = generate_correlation_id(prefix="plan_delete")

        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.plans.delete",
            action="delete",
            target="plan",
            params={"plan_id": plan_id},
            metadata={"endpoint": f"/api/plans/{plan_id}"},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        await emit_plan_receipt(
            correlation_id=correlation_id,
            action="plan.delete",
            args={"plan_id": plan_id},
            event_name="PLAN",
            status="planning",
        )

        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)
            try:
                getattr(request.state, "principal", None)
            except Exception:
                pass
            intent = Intent(
                type=IntentType.COMMAND,
                content=f"Delete plan {plan_id}",
                source="api",
                metadata={
                    "command": "delete_plan",
                    "plan_id": plan_id,
                    "description": f"Delete plan {plan_id}",
                },
            )
            result = await plans_app.process_intent(intent)
            if not result or "error" in result:
                raise HTTPException(
                    status_code=400, detail=result.get("error", "Failed to delete plan")
                )
            response = {
                "status": "success",
                "message": f"Plan {plan_id} deleted successfully",
                "timestamp": datetime.utcnow().isoformat(),
            }

            await remember_plan_event(
                text=f"Plan deleted: {plan_id}", plan_id=plan_id, event_type="plan.deleted"
            )

            await publish_plan_intent(
                action="plan.delete", target="plan.delete", metadata={"plan_id": plan_id}
            )

            duration_ms = int((time.time() - start) * 1000)

            await emit_plan_receipt(
                correlation_id=correlation_id,
                action="plan.delete",
                args={"plan_id": plan_id},
                event_name="EXECUTE",
                status="executing",
            )

            await emit_plan_receipt(
                correlation_id=correlation_id,
                action="plan.delete",
                args={"plan_id": plan_id},
                event_name="VERIFY",
                status="success",
                duration_ms=duration_ms,
            )

            try:
                if PLAN_OPERATIONS_TOTAL:
                    PLAN_OPERATIONS_TOTAL.labels(operation="delete", status="success").inc()
                if PLAN_OPERATION_DURATION:
                    PLAN_OPERATION_DURATION.labels(operation="delete").observe(duration_ms / 1000)
            except Exception:
                pass
            if duration_ms > 50:
                logger.warning(f"Performance violation in delete_plan: {duration_ms:.2f}ms")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete plan {plan_id}: {e}")
            try:
                if PLAN_OPERATIONS_TOTAL:
                    PLAN_OPERATIONS_TOTAL.labels(operation="delete", status="error").inc()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Internal server error") from None

    @router.put(
        "/{plan_id}/tasks/{task_id}",
        response_model=TaskResponse,
        responses=get_error_responses(400, 401, 403, 404, 422, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_WRITE))],  # type: ignore[func-returns-value]
    )
    async def update_task(
        request: Request, plan_id: str, task_id: str, updates: TaskUpdateRequest
    ) -> TaskResponse:
        """Update a task within a plan."""
        await ensure_idempotency(request)
        start = time.time()

        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.plans.update_task",
            action="update",
            target="task",
            params={"plan_id": plan_id, "task_id": task_id, **updates.model_dump()},
            metadata={"endpoint": f"/api/plans/{plan_id}/tasks/{task_id}"},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)
            intent = Intent(
                type=IntentType.COMMAND,
                content=f"Update task {task_id} in plan {plan_id}",
                source="api",
                metadata={
                    "action": "update_task",
                    "parameters": {
                        "plan_id": plan_id,
                        "task_id": task_id,
                        "updates": updates.updates,
                    },
                    "description": f"Update task {task_id} in plan {plan_id}",
                },
            )
            result = await plans_app.process_intent(intent)
            if not result or "error" in result:
                raise HTTPException(
                    status_code=400, detail=result.get("error", "Failed to update task")
                )
            task = result.get("task", {})
            response = TaskResponse(
                id=task.get("id"),
                plan_id=plan_id,
                title=task.get("title"),
                description=task.get("description"),
                status=task.get("status", "pending"),
                priority=task.get("priority", "medium"),
                due_date=task.get("due_date"),
                completed_at=task.get("completed_at"),
                created_at=task.get("created_at"),
                updated_at=task.get("updated_at"),
                tags=task.get("tags", []),
                metadata=task.get("metadata", {}),
            )

            await remember_plan_event(
                text=f"Task updated: {response.title}",
                plan_id=plan_id,
                event_type="task.updated",
                task_id=response.id,
            )

            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(f"Performance violation in update_task: {elapsed_ms:.2f}ms")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update task {task_id} in plan {plan_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from None

    @router.post(
        "/{plan_id}/generate-tasks",
        responses=get_error_responses(400, 401, 403, 404, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.PLAN_WRITE))],  # type: ignore[func-returns-value]
        response_model=None,
    )
    @enforce_tier1("process")
    async def generate_tasks(request: Request, plan_id: str) -> dict[str, Any]:
        """Generate task suggestions for a plan using AI (structured)."""
        await ensure_idempotency(request)
        start = time.time()
        t0 = time.perf_counter()
        correlation_id = uuid.uuid4().hex

        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.plans.generate_tasks",
            action="generate",
            target="tasks",
            params={"plan_id": plan_id},
            metadata={"endpoint": f"/api/plans/{plan_id}/generate-tasks"},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        try:
            _orchestrator, plans_app = await get_orchestrator_and_plans_app(request)
            plan = await plans_app.get_plan(plan_id)
            plan_title = (plan or {}).get("name") or (plan or {}).get("title") or ""
            plan_desc = (plan or {}).get("description") or ""
            system_prompt = "You generate a short list (<=5) of concise tasks for this plan."
            user_prompt = f"Plan: {plan_title}\nDescription: {plan_desc}"
            model_name = select_model_for("plans.generate_tasks")
            structured = await generate_structured_enhanced(
                model_name=model_name,
                pydantic_model=TaskList,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                strategy=GenerationStrategy.GRAMMAR_CONSTRAINED,
                temperature=0.2,
                max_tokens=int(os.getenv("KAGAMI_STRUCTURED_MAX_TOKENS", "384")),
                timeout_s=float(os.getenv("KAGAMI_STRUCTURED_TIMEOUT_S", "8")),
                max_attempts=2,
            )
            tasks_payload = []
            try:
                tasks_payload = [t.model_dump() for t in structured.tasks or []]
            except Exception:
                try:
                    tasks_payload = list(structured.tasks or [])  # type: ignore[arg-type]
                except Exception:
                    tasks_payload = []
            created_records: list[dict[str, Any]] = []
            tasks_repo = getattr(plans_app, "_tasks_repo", None)
            if tasks_repo and tasks_payload:
                for t in tasks_payload[:5]:
                    try:
                        rec = await tasks_repo.upsert_task(
                            plan_id,
                            {
                                "title": str(t.get("title") or "Untitled").strip(),
                                "description": t.get("description"),
                                "priority": str(t.get("priority") or "medium"),
                                "status": "pending",
                                "due_date": t.get("due_date"),
                                "metadata": t.get("metadata") or {},
                            },
                        )
                        created_records.append(
                            {
                                "id": getattr(rec, "id", None),
                                "title": getattr(rec, "title", None) or t.get("title"),
                                "priority": getattr(rec, "priority", None) or t.get("priority"),
                                "description": getattr(rec, "description", None)
                                or t.get("description"),
                                "due_date": getattr(rec, "due_date", None) or t.get("due_date"),
                                "metadata": getattr(rec, "metadata", None) or t.get("metadata"),
                            }
                        )
                    except Exception:
                        continue
            response = {
                "plan_id": plan_id,
                "generated_tasks": created_records or tasks_payload,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
            }

            await remember_plan_event(
                text=f"Generated {len(response.get('generated_tasks', []))} tasks",
                plan_id=plan_id,
                event_type="plan.tasks.generated",
            )

            await publish_plan_intent(
                action="plan.tasks.generate",
                target="plan.tasks.generate",
                metadata={"plan_id": plan_id, "count": len(response["generated_tasks"])},
            )

            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(f"Performance violation in generate_tasks: {elapsed_ms:.2f}ms")

            await emit_plan_receipt(
                correlation_id=correlation_id,
                action="plan.tasks.generate",
                args={"plan_id": plan_id},
                event_name="plan.tasks.generated",
                status="success",
                duration_ms=int(max(0.0, time.perf_counter() - t0) * 1000),
            )

            return response
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="generate_tasks_failed") from None

    return router
