"""Physics API - Genesis simulation integrated with rooms."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.core.events import get_unified_bus
from kagami.core.receipts import emit_receipt
from kagami.forge.modules.genesis_physics_wrapper import get_or_create_physics
from pydantic import BaseModel, Field

from kagami_api.idempotency import ensure_idempotency
from kagami_api.rbac import Permission, require_permission
from kagami_api.rooms.state_service import update_physics_entities
from kagami_api.routes.user.auth import get_current_user

logger = logging.getLogger(__name__)

# Resource limit constants (MODULE LEVEL - PUBLIC API)
MAX_DURATION_SECONDS = 60.0
MIN_DURATION_SECONDS = 0.1
MAX_SIMULATIONS_PER_MINUTE = 10
MAX_CONCURRENT_SIMULATIONS_PER_USER = 3
MAX_GPU_SECONDS_PER_HOUR = 300.0
MAX_OBJECTS_PER_SIMULATION = 100


# Global resource tracking (MODULE LEVEL - PUBLIC API)
class ResourceTracker:
    """Track per-user resource usage for physics simulations."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._simulation_counts: dict[str, list[float]] = defaultdict(list)
        self._concurrent_sims: dict[str, int] = defaultdict(int)
        self._gpu_usage: dict[str, list[tuple[float, float]]] = defaultdict(list)

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create lock for user."""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    async def check_rate_limit(self, user_id: str) -> tuple[bool, int]:
        """Check if user has exceeded rate limit. Returns (allowed, remaining)."""
        async with self._get_lock(user_id):
            now = time.time()
            window_start = now - 60.0

            # Clean old entries
            self._simulation_counts[user_id] = [
                ts for ts in self._simulation_counts[user_id] if ts >= window_start
            ]

            count = len(self._simulation_counts[user_id])
            if count >= MAX_SIMULATIONS_PER_MINUTE:
                return False, 0

            return True, MAX_SIMULATIONS_PER_MINUTE - count

    async def check_concurrent_limit(self, user_id: str) -> tuple[bool, int]:
        """Check if user has exceeded concurrent simulation limit. Returns (allowed, active)."""
        async with self._get_lock(user_id):
            active = self._concurrent_sims[user_id]
            if active >= MAX_CONCURRENT_SIMULATIONS_PER_USER:
                return False, active
            return True, active

    async def check_gpu_budget(self, user_id: str, duration: float) -> tuple[bool, float, float]:
        """Check if user has sufficient GPU budget. Returns (allowed, used, remaining)."""
        async with self._get_lock(user_id):
            now = time.time()
            window_start = now - 3600.0

            # Clean old entries
            self._gpu_usage[user_id] = [
                (ts, dur) for ts, dur in self._gpu_usage[user_id] if ts >= window_start
            ]

            used = sum(dur for _, dur in self._gpu_usage[user_id])
            remaining = MAX_GPU_SECONDS_PER_HOUR - used

            if used + duration > MAX_GPU_SECONDS_PER_HOUR:
                return False, used, remaining

            return True, used, remaining

    async def record_simulation_start(self, user_id: str) -> None:
        """Record simulation start for rate limiting and concurrency tracking."""
        async with self._get_lock(user_id):
            now = time.time()
            self._simulation_counts[user_id].append(now)
            self._concurrent_sims[user_id] += 1

    async def record_simulation_end(self, user_id: str, duration: float) -> None:
        """Record simulation completion for concurrency and budget tracking."""
        async with self._get_lock(user_id):
            self._concurrent_sims[user_id] = max(0, self._concurrent_sims[user_id] - 1)
            now = time.time()
            self._gpu_usage[user_id].append((now, duration))

    async def get_user_status(self, user_id: str) -> dict[str, Any]:
        """Get current resource usage status for user."""
        async with self._get_lock(user_id):
            now = time.time()

            # Rate limit status
            window_start = now - 60.0
            recent_sims = [ts for ts in self._simulation_counts[user_id] if ts >= window_start]
            rate_remaining = MAX_SIMULATIONS_PER_MINUTE - len(recent_sims)

            # GPU budget status
            hour_start = now - 3600.0
            recent_usage = [(ts, dur) for ts, dur in self._gpu_usage[user_id] if ts >= hour_start]
            gpu_used = sum(dur for _, dur in recent_usage)
            gpu_remaining = MAX_GPU_SECONDS_PER_HOUR - gpu_used

            # Concurrent status
            concurrent_active = self._concurrent_sims[user_id]
            concurrent_remaining = MAX_CONCURRENT_SIMULATIONS_PER_USER - concurrent_active

            return {
                "rate_limit": {
                    "limit": MAX_SIMULATIONS_PER_MINUTE,
                    "remaining": rate_remaining,
                    "window_seconds": 60,
                },
                "concurrent_limit": {
                    "limit": MAX_CONCURRENT_SIMULATIONS_PER_USER,
                    "active": concurrent_active,
                    "remaining": concurrent_remaining,
                },
                "gpu_budget": {
                    "limit_seconds": MAX_GPU_SECONDS_PER_HOUR,
                    "used_seconds": round(gpu_used, 2),
                    "remaining_seconds": round(gpu_remaining, 2),
                    "window_seconds": 3600,
                },
                "constraints": {
                    "max_duration_seconds": MAX_DURATION_SECONDS,
                    "min_duration_seconds": MIN_DURATION_SECONDS,
                    "max_objects": MAX_OBJECTS_PER_SIMULATION,
                },
            }


# Global resource tracker instance (MODULE LEVEL)
_resource_tracker = ResourceTracker()


# Request/Response Models (MODULE LEVEL - PUBLIC API)
class SimulateMotionRequest(BaseModel):
    """Run Genesis physics motion simulation.

    Resource limits enforced per user:
    - Duration: 0.1 to 60.0 seconds
    - Rate: 10 simulations per minute
    - Concurrency: 3 simultaneous simulations
    - GPU budget: 300 GPU-seconds per hour
    """

    room_id: str
    motion_type: str
    duration: float = Field(
        default=3.0,
        ge=MIN_DURATION_SECONDS,
        le=MAX_DURATION_SECONDS,
        description=(
            f"Simulation duration in seconds ({MIN_DURATION_SECONDS}-{MAX_DURATION_SECONDS})"
        ),
    )


class TransformUpdateRequest(BaseModel):
    """Broadcast object transform update."""

    room_id: str
    object_id: str
    position: list[float]
    rotation: list[float] | None = None
    scale: list[float] | None = None


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/physics", tags=["physics"])

    @router.post("/simulate", dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))])  # type: ignore[func-returns-value]
    async def simulate_motion(
        request: Request,
        body: SimulateMotionRequest,
        current_user: dict = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Run Genesis physics simulation and broadcast to room participants.

        Resource limits enforced per user:
        - Rate limit: 10 simulations per minute
        - Concurrent limit: 3 simultaneous simulations
        - GPU budget: 300 GPU-seconds per hour
        - Duration: 0.1 to 60.0 seconds (validated by Pydantic)

        Returns HTTP 429 (Too Many Requests) if any limit is exceeded.
        """
        await ensure_idempotency(request)

        # Extract user ID
        user_id = current_user.get("sub") or current_user.get("user_id") or "anonymous"

        # Enforce rate limit (10 simulations/minute)
        rate_allowed, rate_remaining = await _resource_tracker.check_rate_limit(user_id)
        if not rate_allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Maximum {MAX_SIMULATIONS_PER_MINUTE} simulations per minute exceeded",
                    "limit": MAX_SIMULATIONS_PER_MINUTE,
                    "window_seconds": 60,
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # Enforce concurrent simulation limit (max 3)
        concurrent_allowed, concurrent_active = await _resource_tracker.check_concurrent_limit(
            user_id
        )
        if not concurrent_allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "concurrent_limit_exceeded",
                    "message": (
                        f"Maximum {MAX_CONCURRENT_SIMULATIONS_PER_USER} concurrent simulations exceeded"
                    ),
                    "limit": MAX_CONCURRENT_SIMULATIONS_PER_USER,
                    "active": concurrent_active,
                },
            )

        # Enforce GPU budget (300 GPU-seconds/hour)
        budget_allowed, budget_used, budget_remaining = await _resource_tracker.check_gpu_budget(
            user_id, body.duration
        )
        if not budget_allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "gpu_budget_exceeded",
                    "message": f"GPU budget of {MAX_GPU_SECONDS_PER_HOUR}s per hour exceeded",
                    "limit_seconds": MAX_GPU_SECONDS_PER_HOUR,
                    "used_seconds": round(budget_used, 2),
                    "remaining_seconds": round(budget_remaining, 2),
                    "requested_seconds": body.duration,
                    "window_seconds": 3600,
                    "retry_after": 3600,
                },
                headers={"Retry-After": "3600"},
            )

        # Record simulation start
        await _resource_tracker.record_simulation_start(user_id)

        try:
            import time as _t

            from kagami.observability.metrics import PHYSICS_API_LATENCY_SECONDS

            _t0 = _t.perf_counter()
            physics = await get_or_create_physics(body.room_id)

            # Validate object count (if available)
            # Note: This assumes physics engine has a method to get object count
            # If not available, this check can be removed or moved to physics wrapper
            try:
                entity_count = len(getattr(physics, "entities", []))
                if entity_count > MAX_OBJECTS_PER_SIMULATION:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "object_limit_exceeded",
                            "message": (
                                f"Scene has {entity_count} objects, "
                                f"maximum is {MAX_OBJECTS_PER_SIMULATION}"
                            ),
                            "limit": MAX_OBJECTS_PER_SIMULATION,
                            "current": entity_count,
                        },
                    )
            except AttributeError:
                # Physics engine doesn't expose entity count, skip validation
                pass

            result = await physics.simulate_character_motion(  # type: ignore[call-arg]
                motion_type=body.motion_type,
                duration=body.duration,
                capture_rate=30,
                record_data=True,
            )
            snapshot = result.get("snapshot", {})
            if snapshot:
                entities = snapshot.get("entities", [])
                await update_physics_entities(body.room_id, entities)
                bus = get_unified_bus()
                await bus.publish(
                    "state_snapshot",
                    {"type": "state_snapshot", "room_id": body.room_id, "snapshot": snapshot},
                )
            relations = result.get("relations", [])
            collisions = [r for r in relations if r.get("predicate") in ("touching", "collision")]
            if collisions:
                bus = get_unified_bus()
                await bus.publish(
                    "collision",
                    {"type": "collision", "room_id": body.room_id, "collisions": collisions},
                )
            try:
                PHYSICS_API_LATENCY_SECONDS.labels(
                    operation=f"simulate:{body.motion_type}"
                ).observe(max(0.0, _t.perf_counter() - _t0))
            except Exception:
                pass

            # Record actual simulation end with duration
            await _resource_tracker.record_simulation_end(user_id, body.duration)

            receipt = emit_receipt(
                correlation_id=f"physics-{body.room_id}-{int(time.time() * 1000)}",
                action="physics.simulate",
                app="Physics",
                args={"room_id": body.room_id, "motion_type": body.motion_type, "user_id": user_id},
                event_name="physics.simulated",
                event_data={
                    "room_id": body.room_id,
                    "frames": len(result.get("frames", [])),
                    "collisions": len(collisions),
                    "duration": body.duration,
                },
                duration_ms=int(body.duration * 1000),
                guardrails={
                    "rbac": "allow",
                    "csrf": "n/a",
                    "rate_limit": "enforced",
                    "concurrent_limit": "enforced",
                    "gpu_budget": "enforced",
                    "idempotency": "accepted",
                },
            )
            return {
                "ok": True,
                "frames": len(result.get("frames", [])),
                "collisions": collisions,
                "performance": result.get("performance", {}),
                "correlation_id": receipt["correlation_id"],
                "resource_usage": {
                    "duration_seconds": body.duration,
                    "rate_remaining": rate_remaining - 1,
                    "gpu_remaining_seconds": round(budget_remaining - body.duration, 2),
                },
            }
        except HTTPException:
            # Re-raise HTTP exceptions without wrapping
            # Decrement concurrent counter on failure
            await _resource_tracker.record_simulation_end(user_id, 0.0)
            raise
        except Exception as e:
            # Decrement concurrent counter on failure
            await _resource_tracker.record_simulation_end(user_id, 0.0)
            logger.error(f"Physics simulation failed for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Physics simulation failed: {e}") from None

    @router.get("/status")
    async def get_physics_status(
        current_user: dict = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Get current resource usage and quota status for the authenticated user.

        Returns:
            - rate_limit: Simulations per minute quota and usage
            - concurrent_limit: Active concurrent simulations
            - gpu_budget: GPU-seconds used and remaining in current hour
            - constraints: System-wide limits (duration, object count)

        Use this endpoint to check remaining quotas before submitting simulations.
        """
        user_id = current_user.get("sub") or current_user.get("user_id") or "anonymous"
        status = await _resource_tracker.get_user_status(user_id)

        return {
            "ok": True,
            "user_id": user_id,
            **status,
        }

    return router


__all__ = [
    "MAX_CONCURRENT_SIMULATIONS_PER_USER",
    "MAX_DURATION_SECONDS",
    "MAX_GPU_SECONDS_PER_HOUR",
    "MAX_OBJECTS_PER_SIMULATION",
    "MAX_SIMULATIONS_PER_MINUTE",
    "MIN_DURATION_SECONDS",
    "ResourceTracker",
    "SimulateMotionRequest",
    "TransformUpdateRequest",
    "get_router",
]
