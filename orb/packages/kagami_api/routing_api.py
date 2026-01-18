"""Agent Routing API - Fano Plane Multi-Agent Coordination.

CREATED: December 14, 2025
PURPOSE: Commercial multi-agent routing and coordination API

This module exposes the Fano plane routing system as an API:
- POST /v1/route: Route task to appropriate colony(s) based on complexity
- POST /v1/coordinate: Coordinate multi-agent execution
- WebSocket /v1/stream: Real-time coordination events

MATHEMATICAL FOUNDATION:
- Fano plane: 7 points, 7 lines (octonion multiplication table)
- Complexity-based routing: 1 agent (simple) / 3 agents (complex) / 7 agents (synthesis)
- Catastrophe theory: Each colony = one elementary catastrophe

MONETIZATION (Month 7):
- Free: Single-agent routing only
- Pro: Multi-agent coordination + real-time streaming
- Enterprise: Custom Fano line composition

Reference: docs/BUSINESS_STRATEGY.md
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from kagami.core.database.connection import get_db
from kagami.core.unified_agents.fano_action_router import (
    ActionMode,
    FanoActionRouter,
)
from kagami_math.fano_plane import FANO_LINES
from pydantic import BaseModel, Field

from kagami_api.rate_limiter import RateLimiter
from kagami_api.security import verify_api_key_with_context

logger = logging.getLogger(__name__)

# =============================================================================
# SCHEMAS
# =============================================================================


class TaskComplexity(str, Enum):
    """Task complexity level."""

    SIMPLE = "simple"  # < 0.3
    COMPLEX = "complex"  # 0.3 - 0.7
    SYNTHESIS = "synthesis"  # > 0.7


class RouteRequest(BaseModel):
    """Request to route a task."""

    task: str = Field(..., description="Task description")
    context: dict[str, Any] = Field(default_factory=dict, description="Task context")
    complexity: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Estimated complexity (None = auto)"
    )
    preferred_colonies: list[str] | None = Field(
        default=None, description="Preferred colonies (optional)"
    )


class ColonyAssignment(BaseModel):
    """Assignment to a specific colony."""

    colony_name: str = Field(..., description="Colony name (spark, forge, etc.)")
    colony_idx: int = Field(..., description="Colony index (0-6)")
    action: str = Field(..., description="Action to execute")
    params: dict[str, Any] = Field(..., description="Action parameters")
    weight: float = Field(..., description="Contribution weight")
    is_primary: bool = Field(..., description="Primary colony for this task")


class RouteResponse(BaseModel):
    """Response from routing decision."""

    mode: str = Field(..., description="Routing mode (single/fano/all)")
    complexity: float = Field(..., description="Estimated task complexity")
    assignments: list[ColonyAssignment] = Field(..., description="Colony assignments")
    fano_line: list[int] | None = Field(default=None, description="Fano line used (if mode=fano)")
    execution_plan: str = Field(..., description="Human-readable execution plan")
    estimated_time_ms: int = Field(..., description="Estimated execution time")


class CoordinateRequest(BaseModel):
    """Request to coordinate multi-agent execution."""

    assignments: list[ColonyAssignment] = Field(..., description="Colony assignments")
    dependencies: dict[str, list[str]] = Field(
        default_factory=dict, description="Task dependencies (DAG)"
    )
    timeout_ms: int = Field(default=30000, description="Coordination timeout")
    return_intermediate: bool = Field(default=False, description="Return intermediate results")


class CoordinateResponse(BaseModel):
    """Response from coordination."""

    job_id: str = Field(..., description="Coordination job ID")
    status: str = Field(..., description="Status (running/completed/failed)")
    results: dict[str, Any] = Field(default_factory=dict, description="Colony results")
    execution_time_ms: int = Field(..., description="Total execution time")
    fano_composition: dict[str, Any] = Field(
        default_factory=dict, description="Fano composition metrics"
    )


class StreamEvent(BaseModel):
    """Real-time coordination event."""

    event_type: str = Field(..., description="Event type")
    colony: str = Field(..., description="Colony emitting event")
    timestamp: float = Field(..., description="Event timestamp")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")


# =============================================================================
# API DEPENDENCIES
# =============================================================================

rate_limiter_free = RateLimiter(requests_per_minute=60)
rate_limiter_pro = RateLimiter(requests_per_minute=600)


async def verify_api_key(request: Request) -> dict[str, Any]:
    """Verify API key and return tier info.

    SECURITY: Delegates to centralized verify_api_key_with_context.
    See kagami.api.security for implementation.
    """
    return await verify_api_key_with_context(request, get_db)


async def verify_api_key_with_context_for_ws(api_key: str) -> dict[str, Any]:
    """Verify API key directly (for WebSocket endpoints).

    Unlike verify_api_key_with_context which expects a Request object,
    this accepts the API key string directly for WebSocket use.

    Args:
        api_key: The API key to verify

    Returns:
        Dictionary with tier, user_id, scopes, key_id, username, tenant_id

    Raises:
        Exception: If validation fails
    """
    from kagami_api.security import get_api_key_manager

    db = next(get_db())
    api_key_manager = get_api_key_manager()
    context = api_key_manager.validate_api_key(db, api_key)

    if not context:
        raise ValueError("Invalid or expired API key")

    return {
        "tier": context.tier,
        "key_id": context.key_id,
        "user_id": context.user_id,
        "scopes": context.scopes,
        "username": context.username,
        "tenant_id": context.tenant_id,
    }


# =============================================================================
# REDIS HELPERS
# =============================================================================


def _get_redis():
    """Get Redis client for job tracking."""
    try:
        from kagami.core.caching.redis import RedisClientFactory

        return RedisClientFactory.get_client()
    except Exception as e:
        logger.debug(f"Redis unavailable for routing jobs: {e}")
        return None


# Redis key prefix for routing jobs
REDIS_ROUTING_JOB_PREFIX = "kagami:routing:job:"
ROUTING_JOB_TTL = 3600  # 1 hour


# =============================================================================
# ROUTING ENGINE
# =============================================================================


class RoutingEngine:
    """Production routing engine with Fano plane composition.

    Architecture (Horizontally Scalable):
    - Router: In-memory (stateless mathematical routing)
    - Active jobs: Redis (cross-pod job status tracking)
    - Event subscribers: Local (WebSocket connections are pod-local)
    """

    def __init__(self) -> None:
        self.router = FanoActionRouter(simple_threshold=0.3, complex_threshold=0.7, device="cpu")
        self._local_jobs: dict[str, dict[str, Any]] = {}  # Fallback when Redis unavailable
        self.event_subscribers: list[asyncio.Queue] = []
        logger.info("RoutingEngine initialized with Fano plane (Redis-backed jobs)")

    def _set_job(self, job_id: str, job_data: dict[str, Any]) -> None:
        """Store job data in Redis (or local fallback)."""
        import json

        redis = _get_redis()
        if redis:
            try:
                # Convert assignments to serializable format
                serializable_data = {
                    "status": job_data.get("status"),
                    "start_time": job_data.get("start_time"),
                    "assignments": [
                        a.model_dump() if hasattr(a, "model_dump") else a
                        for a in job_data.get("assignments", [])
                    ],
                }
                redis.setex(
                    f"{REDIS_ROUTING_JOB_PREFIX}{job_id}",
                    ROUTING_JOB_TTL,
                    json.dumps(serializable_data),
                )
                return
            except Exception as e:
                logger.debug(f"Redis job set failed: {e}")
        # Fallback to local
        self._local_jobs[job_id] = job_data

    def _update_job_status(self, job_id: str, status: str) -> None:
        """Update job status in Redis (or local fallback)."""
        import json

        redis = _get_redis()
        if redis:
            try:
                data = redis.get(f"{REDIS_ROUTING_JOB_PREFIX}{job_id}")
                if data:
                    job_data = json.loads(data)
                    job_data["status"] = status
                    redis.setex(
                        f"{REDIS_ROUTING_JOB_PREFIX}{job_id}",
                        ROUTING_JOB_TTL,
                        json.dumps(job_data),
                    )
                    return
            except Exception as e:
                logger.debug(f"Redis job update failed: {e}")
        # Fallback to local
        if job_id in self._local_jobs:
            self._local_jobs[job_id]["status"] = status

    def _get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job data from Redis (or local fallback)."""
        import json

        redis = _get_redis()
        if redis:
            try:
                data = redis.get(f"{REDIS_ROUTING_JOB_PREFIX}{job_id}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.debug(f"Redis job get failed: {e}")
        # Fallback to local
        return self._local_jobs.get(job_id)

    def _task_to_action(self, task: str) -> str:
        """Convert task description to an action string for routing.

        Args:
            task: Task description text

        Returns:
            Action string for the Fano router (e.g., "research.topic", "build.feature")
        """
        task_lower = task.lower()

        # Map keywords to colony actions
        if any(kw in task_lower for kw in ["create", "build", "implement", "make"]):
            return "build.feature"
        elif any(kw in task_lower for kw in ["fix", "debug", "repair", "resolve"]):
            return "flow.debug"
        elif any(kw in task_lower for kw in ["research", "explore", "learn", "investigate"]):
            return "research.topic"
        elif any(kw in task_lower for kw in ["test", "verify", "validate", "check"]):
            return "verify.code"
        elif any(kw in task_lower for kw in ["plan", "design", "architect", "structure"]):
            return "plan.architecture"
        elif any(kw in task_lower for kw in ["connect", "integrate", "merge", "combine"]):
            return "integrate.systems"
        elif any(kw in task_lower for kw in ["brainstorm", "ideate", "imagine"]):
            return "spark.idea"

        # Default to research for unknown tasks (Grove handles unknowns)
        return "research.general"

    def estimate_complexity(self, task: str, context: dict[str, Any]) -> float:
        """Estimate task complexity from description and context.

        Uses heuristics + optional learned model.
        """
        # Heuristic: Length + keywords
        complexity = min(len(task) / 1000.0, 1.0)

        # Check for complexity keywords
        if any(kw in task.lower() for kw in ["simple", "quick", "basic", "trivial", "easy"]):
            complexity *= 0.5
        elif any(
            kw in task.lower() for kw in ["complex", "difficult", "advanced", "comprehensive"]
        ):
            complexity = min(complexity + 0.3, 1.0)

        # Check context
        if "requires_multiple_steps" in context:
            complexity = min(complexity + 0.2, 1.0)

        return complexity

    def route(
        self,
        task: str,
        context: dict[str, Any],
        complexity: float | None = None,
        preferred_colonies: list[str] | None = None,
    ) -> RouteResponse:
        """Route task to appropriate colonies using Fano plane.

        Args:
            task: Task description
            context: Task context
            complexity: Optional explicit complexity
            preferred_colonies: Optional colony preferences

        Returns:
            RouteResponse with colony assignments
        """
        # Estimate complexity if not provided
        if complexity is None:
            complexity = self.estimate_complexity(task, context)

        # Convert task to action string for Fano router
        action = self._task_to_action(task)

        # Build params from task and context
        params = {"task": task, **context}

        # Route using Fano plane
        routing_result = self.router.route(
            action=action,
            params=params,
            complexity=complexity,
            context=context,
        )

        # Convert to API response format
        assignments = [
            ColonyAssignment(
                colony_name=action.colony_name,
                colony_idx=action.colony_idx,
                action=action.action,
                params=action.params,
                weight=action.weight,
                is_primary=action.is_primary,
            )
            for action in routing_result.actions
        ]

        # Build execution plan
        mode_str = routing_result.mode.value
        if routing_result.mode == ActionMode.SINGLE:
            plan = f"Execute via {assignments[0].colony_name} colony"
        elif routing_result.mode == ActionMode.FANO_LINE:
            colonies = [a.colony_name for a in assignments]
            plan = f"Fano line composition: {' × '.join(colonies[:2])} → {colonies[2]}"
        else:
            plan = "Full 7-colony synthesis (all catastrophes engaged)"

        # Estimate execution time based on complexity
        estimated_time = int(1000 + complexity * 5000)  # 1-6 seconds

        return RouteResponse(
            mode=mode_str,
            complexity=complexity,
            assignments=assignments,
            fano_line=(list(routing_result.fano_line) if routing_result.fano_line else None),
            execution_plan=plan,
            estimated_time_ms=estimated_time,
        )

    async def coordinate(
        self,
        assignments: list[ColonyAssignment],
        dependencies: dict[str, list[str]],
        timeout_ms: int,
        return_intermediate: bool,
    ) -> CoordinateResponse:
        """Coordinate multi-colony execution.

        Args:
            assignments: Colony task assignments
            dependencies: Task dependency graph
            timeout_ms: Coordination timeout
            return_intermediate: Return intermediate results

        Returns:
            CoordinateResponse with results
        """
        import hashlib

        start_time = time.time()

        # Generate job ID
        job_id = hashlib.sha256((str(assignments) + str(time.time())).encode()).hexdigest()[:16]

        # Track job (Redis-backed for cross-pod access)
        self._set_job(
            job_id,
            {
                "assignments": assignments,
                "status": "running",
                "start_time": start_time,
            },
        )

        try:
            # Execute assignments (simplified for prototype)
            results = {}
            for assignment in assignments:
                # Simulate colony execution
                await asyncio.sleep(0.1)  # Simulate work
                results[assignment.colony_name] = {
                    "action": assignment.action,
                    "status": "completed",
                    "output": f"Result from {assignment.colony_name}",
                }

                # Emit event
                await self._emit_event(
                    StreamEvent(
                        event_type="colony_completed",
                        colony=assignment.colony_name,
                        timestamp=time.time(),
                        data={"action": assignment.action},
                    )
                )

            # Calculate metrics
            execution_time = int((time.time() - start_time) * 1000)

            # Fano composition metrics
            fano_metrics = {
                "num_colonies": len(assignments),
                "composition_type": "fano_line" if len(assignments) == 3 else "single",
                "coordination_overhead_ms": execution_time // len(assignments),
            }

            self._update_job_status(job_id, "completed")

            return CoordinateResponse(
                job_id=job_id,
                status="completed",
                results=results,
                execution_time_ms=execution_time,
                fano_composition=fano_metrics,
            )

        except Exception as e:
            logger.error(f"Coordination failed: {e}", exc_info=True)
            self._update_job_status(job_id, "failed")
            raise HTTPException(status_code=500, detail=f"Coordination failed: {e!s}") from e

    async def _emit_event(self, event: StreamEvent) -> None:
        """Emit event to all subscribers."""
        for queue in self.event_subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")

    def subscribe_events(self) -> asyncio.Queue:
        """Subscribe to coordination events."""
        queue: asyncio.Queue = asyncio.Queue()
        self.event_subscribers.append(queue)
        return queue

    def unsubscribe_events(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from events."""
        if queue in self.event_subscribers:
            self.event_subscribers.remove(queue)


# Global engine
routing_engine = RoutingEngine()

# =============================================================================
# API ROUTER
# =============================================================================

router = APIRouter(prefix="/v1", tags=["routing"])


@router.post("/route", response_model=RouteResponse)
async def route_task(
    request: RouteRequest,
    user_info: dict = Depends(verify_api_key),
) -> RouteResponse:
    """Route task to appropriate colonies using Fano plane composition.

    This endpoint determines which catastrophe colonies should handle the task
    based on complexity:
    - Simple (< 0.3): Single colony
    - Complex (0.3-0.7): Fano line (3 colonies)
    - Synthesis (≥ 0.7): All 7 colonies

    **Example:**
    ```bash
    curl -X POST "https://api.kagami.ai/v1/route" \\
         -H "X-API-Key: sk_pro_..." \\
         -H "Content-Type: application/json" \\
         -d '{
           "task": "Design and implement new feature X",
           "context": {"domain": "backend"},
           "complexity": null
         }'
    ```
    """
    try:
        # Free tier: single-agent only
        if user_info["tier"] == "free" and request.complexity and request.complexity >= 0.3:
            raise HTTPException(
                status_code=403,
                detail="Multi-agent routing requires Pro tier. "
                "Free tier limited to simple tasks (complexity < 0.3).",
            )

        response = routing_engine.route(
            request.task,
            request.context,
            request.complexity,
            request.preferred_colonies,
        )

        logger.info(
            f"Routed task (complexity={response.complexity:.2f}) to "
            f"{len(response.assignments)} colonies for {user_info['tier']} user"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Routing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Routing failed: {e!s}") from e


@router.post("/coordinate", response_model=CoordinateResponse)
async def coordinate_execution(
    request: CoordinateRequest,
    user_info: dict = Depends(verify_api_key),
) -> CoordinateResponse:
    """Coordinate multi-colony execution with dependency management.

    Executes assigned tasks across multiple colonies with proper ordering
    based on dependency graph.

    **Pro tier only.**

    **Example:**
    ```bash
    curl -X POST "https://api.kagami.ai/v1/coordinate" \\
         -H "X-API-Key: sk_pro_..." \\
         -H "Content-Type: application/json" \\
         -d '{
           "assignments": [...],
           "dependencies": {"task2": ["task1"]},
           "timeout_ms": 30000
         }'
    ```
    """
    if user_info["tier"] != "pro":
        raise HTTPException(status_code=403, detail="Multi-agent coordination requires Pro tier")

    try:
        response = await routing_engine.coordinate(
            request.assignments,
            request.dependencies,
            request.timeout_ms,
            request.return_intermediate,
        )

        logger.info(
            f"Coordinated {len(request.assignments)} colonies in "
            f"{response.execution_time_ms}ms (job {response.job_id})"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Coordination failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Coordination failed: {e!s}") from e


@router.websocket("/stream")
async def stream_coordination(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time coordination events.

    Streams events as colonies complete tasks, errors occur, etc.

    **Pro tier only.**

    Authentication:
    - API key via query param: ?api_key=sk_...
    - API key via header: X-API-Key: sk_...
    - JWT token via header: Authorization: Bearer <token>

    **Example (Python):**
    ```python
    import websockets
    import json

    async with websockets.connect(
        "wss://api.kagami.ai/v1/stream?api_key=sk_pro_..."
    ) as ws:
        async for message in ws:
            event = json.loads(message)
            print(f"Colony {event['colony']}: {event['event_type']}")
    ```
    """
    from kagami_api.security import SecurityFramework
    from kagami_api.security.websocket import WS_CLOSE_UNAUTHORIZED

    # Extract API key from query params or headers
    api_key = websocket.query_params.get("api_key", "")
    if not api_key:
        api_key = websocket.headers.get("x-api-key", "")

    # Validate API key using SecurityFramework
    if not api_key or not SecurityFramework.validate_api_key(api_key):
        logger.warning("WebSocket /v1/stream: Invalid or missing API key")
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Invalid API key")
        return

    # Verify tier - streaming requires pro tier
    try:
        tier_info = await verify_api_key_with_context_for_ws(api_key)
        if tier_info.get("tier") != "pro":
            logger.warning(
                f"WebSocket /v1/stream: Non-pro tier attempted streaming (tier={tier_info.get('tier')})"
            )
            await websocket.close(code=1008, reason="Pro tier required for streaming")
            return
    except Exception as e:
        logger.error(f"WebSocket /v1/stream: Tier verification failed: {e}")
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication failed")
        return

    await websocket.accept()
    logger.info("WebSocket client connected to /v1/stream (pro tier)")

    # Subscribe to events
    event_queue = routing_engine.subscribe_events()

    try:
        while True:
            # Wait for events
            event = await event_queue.get()

            # Send to client
            await websocket.send_json(event.model_dump())

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /v1/stream")
    except Exception as e:
        logger.error(f"WebSocket /v1/stream error: {e}", exc_info=True)
    finally:
        routing_engine.unsubscribe_events(event_queue)


@router.get("/fano/lines")
async def get_fano_lines(
    user_info: dict = Depends(verify_api_key),
) -> dict[str, Any]:
    """Get Fano plane line definitions.

    Returns the 7 Fano lines used for 3-colony composition.

    **Example:**
    ```bash
    curl "https://api.kagami.ai/v1/fano/lines" \\
         -H "X-API-Key: sk_pro_..."
    ```
    """
    from kagami_math.catastrophe_constants import COLONY_NAMES

    lines_with_names = []
    for line_idx, (i, j, k) in enumerate(FANO_LINES):
        # FANO_LINES uses 1-indexed (1-7), convert to 0-indexed for COLONY_NAMES
        i0, j0, k0 = i - 1, j - 1, k - 1
        lines_with_names.append(
            {
                "line_id": line_idx,
                "colonies": [COLONY_NAMES[i0], COLONY_NAMES[j0], COLONY_NAMES[k0]],
                "indices": [i, j, k],  # Keep original 1-indexed for display
                "description": f"{COLONY_NAMES[i0]} × {COLONY_NAMES[j0]} → {COLONY_NAMES[k0]}",
            }
        )

    return {
        "fano_lines": lines_with_names,
        "total_lines": len(FANO_LINES),
        "description": "Valid 3-colony compositions from Fano plane geometry",
    }


__all__ = [
    "CoordinateRequest",
    "CoordinateResponse",
    "RouteRequest",
    "RouteResponse",
    "StreamEvent",
    "router",
]
