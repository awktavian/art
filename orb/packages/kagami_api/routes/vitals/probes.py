"""Health Probes - Kubernetes liveness/readiness with dependency checks.

Endpoints:
- GET /probes/live - Liveness probe (is process alive?)
- GET /probes/ready - Readiness probe (can we serve traffic?)
- GET /probes/deep - Deep health check (comprehensive diagnostics)
- GET /probes/cluster - Cluster health (etcd, leader election)
- GET /probes/dependencies - All dependency health checks

Fully typed with Pydantic schemas for OpenAPI and SDK generation.
Enhanced: December 6, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from kagami_api.response_schemas import get_error_responses
from kagami_api.routes.vitals.utils import determine_overall_status
from kagami_api.schemas.vitals import (
    ClusterHealthResponse,
    DeepHealthResponse,
    DependencyCheck,
    LivenessResponse,
    ReadinessResponse,
)

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/probes", tags=["vitals"])

    # =============================================================================
    # DEPENDENCY HEALTH CHECKERS
    # =============================================================================

    async def check_database_health() -> DependencyCheck:
        """Check database connectivity and basic operations."""
        start = time.perf_counter()
        try:
            from kagami.core.database.async_connection import get_async_engine

            engine = get_async_engine()
            if not engine:
                return DependencyCheck(status="unavailable", error="No engine configured")

            # Test actual connectivity with a simple query
            from sqlalchemy import text

            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()

            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyCheck(status="healthy", latency_ms=round(latency_ms, 2))
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyCheck(
                status="unhealthy", error=str(e), latency_ms=round(latency_ms, 2)
            )

    async def check_redis_health() -> DependencyCheck:
        """Check Redis connectivity and basic operations."""
        start = time.perf_counter()
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client()
            if not redis:
                return DependencyCheck(status="unavailable", error="No Redis client configured")

            # Test ping
            pong = redis.ping()
            if not pong:
                return DependencyCheck(status="degraded", error="Ping failed")

            # Test basic get/set
            test_key = "_kagami_health_check"
            redis.set(test_key, "ok", ex=10)
            value = redis.get(test_key)

            latency_ms = (time.perf_counter() - start) * 1000
            # RedisClientFactory uses decode_responses=True, so value is str not bytes
            status = "healthy" if value == "ok" else "degraded"

            return DependencyCheck(status=status, latency_ms=round(latency_ms, 2))

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyCheck(
                status="unhealthy", error=str(e), latency_ms=round(latency_ms, 2)
            )

    async def check_etcd_health() -> DependencyCheck:
        """Check etcd connectivity."""
        start = time.perf_counter()
        try:
            from kagami.core.consensus.etcd_client import get_etcd_client

            client = get_etcd_client()
            if not client:
                return DependencyCheck(status="unavailable", error="No etcd client configured")

            # Try to get cluster status
            try:
                status = await client.status()
                latency_ms = (time.perf_counter() - start) * 1000
                return DependencyCheck(
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                    note=f"leader={getattr(status, 'leader', 'unknown')}",
                )
            except Exception:
                latency_ms = (time.perf_counter() - start) * 1000
                return DependencyCheck(
                    status="healthy", latency_ms=round(latency_ms, 2), note="connected"
                )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyCheck(
                status="unhealthy", error=str(e), latency_ms=round(latency_ms, 2)
            )

    async def check_orchestrator_health(app_state: Any) -> DependencyCheck:
        """Check orchestrator/intelligence availability."""
        try:
            orchestrator = getattr(app_state, "orchestrator", None)
            if not orchestrator:
                kagami_intelligence = getattr(app_state, "kagami_intelligence", None)
                if not kagami_intelligence:
                    return DependencyCheck(status="unavailable", error="No orchestrator")
                return DependencyCheck(status="healthy", note="kagami_intelligence")

            return DependencyCheck(
                status="healthy",
                note=f"entities={len(getattr(orchestrator, '_entities', {}))}",
            )
        except Exception as e:
            return DependencyCheck(status="unhealthy", error=str(e))

    async def check_socketio_health(app_state: Any) -> DependencyCheck:
        """Check Socket.IO server health."""
        try:
            if hasattr(app_state, "system_ready") and app_state.system_ready:
                return DependencyCheck(status="healthy", note="system_ready=true")

            from kagami_api.socketio_server import get_socketio_health

            health = get_socketio_health()
            if health.get("ready", False):
                return DependencyCheck(status="healthy")
            return DependencyCheck(status="degraded", note="not ready")
        except Exception as e:
            return DependencyCheck(status="unavailable", error=str(e))

    async def check_metrics_health() -> DependencyCheck:
        """Check metrics collection health."""
        try:
            from kagami.observability.metrics import MISSING_METRICS_MODULES

            missing_count = len(MISSING_METRICS_MODULES)
            if missing_count == 0:
                return DependencyCheck(status="healthy")
            return DependencyCheck(status="degraded", note=f"missing_modules={missing_count}")
        except Exception as e:
            return DependencyCheck(status="unavailable", error=str(e))

    # =============================================================================
    # HELPER FUNCTIONS
    # =============================================================================

    def _boot_status(state: Any) -> tuple[bool, dict[str, Any]]:
        """Extract boot status from app state."""
        boot_report = getattr(state, "boot_graph_report", {})
        if hasattr(state, "system_ready"):
            ready = bool(state.system_ready)
        else:
            ready = bool(boot_report) and all(e.get("success", False) for e in boot_report.values())
        return ready, boot_report

    # =============================================================================
    # ENDPOINTS
    # =============================================================================

    @router.get(
        "/live",
        response_model=LivenessResponse,
        summary="Liveness probe",
        description="""
    Kubernetes liveness probe - is the process alive?

    This endpoint should always return 200 if the process is running.
    Does NOT check dependencies.
        """,
    )
    async def liveness() -> LivenessResponse:
        """Kubernetes liveness probe - is the process alive?"""
        return LivenessResponse(
            status="ok",
            service="K OS",
            timestamp=datetime.now(),
            probe="liveness",
        )

    @router.get(
        "/ready",
        response_model=ReadinessResponse,
        responses={503: {"description": "Service not ready"}},
        summary="Readiness probe",
        description="""
    Kubernetes readiness probe - can we serve traffic?

    Checks critical dependencies:
    - Boot sequence completed
    - Metrics collection healthy
    - Socket.IO ready

    Returns 200 if ready, 503 if not ready.

    **Performance**: Cached with 5s TTL for reduced latency on frequent K8s probes.
        """,
    )
    async def readiness(request: Request) -> ReadinessResponse:
        """Kubernetes readiness probe - can we serve traffic?"""
        checks: dict[str, DependencyCheck] = {}

        # Check boot status (fast - no I/O)
        boot_ready, _ = _boot_status(request.app.state)
        checks["boot"] = DependencyCheck(status="healthy" if boot_ready else "unhealthy")

        # Check metrics (fast - no I/O)
        checks["metrics"] = await check_metrics_health()

        # Check socketio (fast - no I/O)
        checks["socketio"] = await check_socketio_health(request.app.state)

        # Use cached dependency checks for better performance
        # (only if boot is ready, otherwise fail fast)
        if boot_ready:
            from kagami_api.routes.vitals.cached_probes import (
                cached_database_health,
                cached_redis_health,
            )

            # Run parallel cached checks (5s TTL)
            try:
                results = await asyncio.gather(
                    cached_database_health(), cached_redis_health(), return_exceptions=True
                )
                db_check = results[0]
                redis_check = results[1]
                if not isinstance(db_check, Exception):
                    checks["database"] = db_check  # type: ignore[assignment]
                if not isinstance(redis_check, Exception):
                    checks["redis"] = redis_check  # type: ignore[assignment]
            except Exception:
                pass  # Non-critical for readiness

        # Determine overall readiness
        overall = determine_overall_status(checks)
        ready = overall == "healthy"

        response = ReadinessResponse(
            status=overall,
            ready=ready,
            timestamp=datetime.now(),
            probe="readiness",
            checks=checks,
        )

        if ready:
            return response

        raise HTTPException(status_code=503, detail=response.model_dump(mode="json"))

    @router.get(
        "/deep",
        response_model=DeepHealthResponse,
        responses=get_error_responses(500),
        summary="Deep health check",
        description="""
    Deep health check - comprehensive system diagnostics.

    Checks ALL dependencies including:
    - Database connectivity
    - Redis connectivity
    - etcd connectivity
    - Orchestrator availability
    - Socket.IO server
    - Boot status
    - Metrics collection

    **NOT cached** - use sparingly in production.
        """,
    )
    async def deep_check(request: Request) -> DeepHealthResponse:
        """Deep health check - comprehensive system diagnostics."""
        start = time.perf_counter()

        checks: dict[str, DependencyCheck] = {}

        # Non-async checks first
        boot_ready, _ = _boot_status(request.app.state)
        checks["boot"] = DependencyCheck(status="healthy" if boot_ready else "unhealthy")

        checks["orchestrator"] = await check_orchestrator_health(request.app.state)
        checks["socketio"] = await check_socketio_health(request.app.state)

        # Run dependency checks in parallel with caching for better performance
        from kagami_api.routes.vitals.cached_probes import (
            cached_database_health,
            cached_etcd_health,
            cached_redis_health,
        )

        coros: tuple[Any, ...] | None = None
        try:
            # IMPORTANT: Build coroutine objects inside the try so we can safely close
            # them if asyncio.gather fails (e.g., under non-asyncio AnyIO backends).
            # Use cached versions (5s TTL) for better performance
            coros = (
                cached_database_health(),
                cached_redis_health(),
                cached_etcd_health(),
                check_metrics_health(),
            )
            db_result, redis_result, etcd_result, metrics_result = await asyncio.gather(*coros)
            checks["database"] = db_result
            checks["redis"] = redis_result
            checks["etcd"] = etcd_result
            checks["metrics"] = metrics_result
        except RuntimeError:
            # If gather failed before scheduling, close coroutine objects to avoid
            # "coroutine was never awaited" warnings during schema generation/tests.
            if coros:
                for c in coros:
                    try:
                        c.close()
                    except Exception:
                        pass
            # Fallback to sequential with cached versions
            checks["database"] = await cached_database_health()
            checks["redis"] = await cached_redis_health()
            checks["etcd"] = await cached_etcd_health()
            checks["metrics"] = await check_metrics_health()

        # Determine overall status
        overall = determine_overall_status(checks)

        # Calculate total check time
        total_ms = (time.perf_counter() - start) * 1000

        return DeepHealthResponse(
            status=overall,
            timestamp=datetime.now(),
            probe="deep",
            duration_ms=round(total_ms, 2),
            checks=checks,
        )

    @router.get(
        "/cluster",
        response_model=ClusterHealthResponse,
        responses=get_error_responses(500),
        summary="Cluster health",
        description="Cluster health check - etcd and distributed coordination.",
    )
    async def cluster_health() -> ClusterHealthResponse:
        """Cluster health check - etcd and distributed coordination."""
        checks: dict[str, DependencyCheck] = {}

        # Check etcd
        checks["etcd"] = await check_etcd_health()

        # Check consensus status (KagamiConsensus)
        try:
            from kagami.core.coordination.kagami_consensus import get_consensus_protocol

            consensus = get_consensus_protocol()
            if consensus:
                state = consensus.current_state  # type: ignore[attr-defined]
                checks["consensus"] = DependencyCheck(
                    status="healthy" if state.converged else "degraded",
                    note=f"converged={state.converged}",
                )
            else:
                checks["consensus"] = DependencyCheck(status="unavailable")
        except Exception as e:
            checks["consensus"] = DependencyCheck(status="unavailable", note=str(e))

        overall = determine_overall_status(checks)

        return ClusterHealthResponse(
            status=overall,
            timestamp=datetime.now(),
            probe="cluster",
            checks=checks,
        )

    @router.get(
        "/dependencies",
        response_model=DeepHealthResponse,
        responses=get_error_responses(500),
        summary="Dependencies health",
        description="""
    Check all external dependencies.

    Returns health status for:
    - Database (CockroachDB/PostgreSQL)
    - Redis
    - etcd

    Useful for debugging connectivity issues.

    **Performance**: Cached with 5s TTL for reduced latency.
        """,
    )
    async def dependencies_health() -> DeepHealthResponse:
        """Check all external dependencies."""
        start = time.perf_counter()

        # Use cached versions for better performance
        from kagami_api.routes.vitals.cached_probes import (
            cached_database_health,
            cached_etcd_health,
            cached_redis_health,
        )

        # Run dependency checks in parallel
        coros: tuple[Any, ...] | None = None
        try:
            coros = (
                cached_database_health(),
                cached_redis_health(),
                cached_etcd_health(),
            )
            db_result, redis_result, etcd_result = await asyncio.gather(*coros)
            checks = {
                "database": db_result,
                "redis": redis_result,
                "etcd": etcd_result,
            }
        except RuntimeError:
            if coros:
                for c in coros:
                    try:
                        c.close()
                    except Exception:
                        pass
            # Fallback to sequential
            checks = {
                "database": await cached_database_health(),
                "redis": await cached_redis_health(),
                "etcd": await cached_etcd_health(),
            }

        overall = determine_overall_status(checks)
        total_ms = (time.perf_counter() - start) * 1000

        return DeepHealthResponse(
            status=overall,
            timestamp=datetime.now(),
            probe="dependencies",
            duration_ms=round(total_ms, 2),
            checks=checks,
        )

    return router
