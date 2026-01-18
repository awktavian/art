"""Startup Progress and Diagnostics Routes.

Provides real-time visibility into boot sequence:
- GET /api/v1/startup/progress - Detailed model loading status
- GET /api/v1/startup/health - System health during boot
- GET /api/v1/startup/ready - Simple readiness check

Used by:
- Frontend to show "Loading..." UI with progress
- Load balancers to know when to start routing traffic
- Monitoring to track boot duration
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from kagami.boot.model_loader import get_model_loader_state
from starlette.responses import Response

from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/startup", tags=["vitals"])


@router.get(
    "/progress",
    response_model=dict[str, Any],
    responses=get_error_responses(429, 500),
)
async def get_startup_progress() -> dict[str, Any]:
    """Get detailed model loading progress.

    Returns:
        {
            "phase": "startup|ready|degraded|error",
            "elapsed_seconds": 2.5,
            "models_ready": ["encoder", "llm_instant"],
            "models_loading": ["world_model"],
            "models_failed": [],
            "overall_readiness": 0.67,  # 0-1 weighted score
            "details": {
                "world_model": {
                    "status": "loading|ready|failed|pending",
                    "elapsed_ms": 1500,
                    "error": null
                }
            }
        }
    """
    loader = get_model_loader_state()
    return loader.get_progress()


@router.get(
    "/health",
    response_model=dict[str, Any],
    responses=get_error_responses(429, 500),
)
async def get_startup_health() -> dict[str, Any]:
    """Get system health during boot.

    Returns:
        {
            "critical_models_ready": true,
            "critical_models_failed": false,
            "phase": "ready",
            "readiness_score": 0.95
        }
    """
    loader = get_model_loader_state()
    return loader.get_health()


@router.get(
    "/ready",
    responses=get_error_responses(425, 429, 503),
)
async def check_ready() -> Response:
    """Simple readiness check for load balancers.

    Returns:
        204 No Content if ready
        425 Too Early if still loading
        503 Service Unavailable if degraded/failed

    Used by Kubernetes readiness probes:
        readinessProbe:
          httpGet:
            path: /api/v1/startup/ready
            port: 8000
          initialDelaySeconds: 2
          periodSeconds: 5
    """
    loader = get_model_loader_state()
    phase = loader.get_phase()

    if phase.value == "ready":
        # All critical models loaded, ready to serve
        return Response(status_code=204)

    if phase.value == "startup":
        # Still loading - too early
        raise HTTPException(status_code=425, detail="System still booting, retry in a few seconds")

    # degraded or error
    raise HTTPException(status_code=503, detail=f"System unavailable: {phase.value}")


@router.get(
    "/diagnostics",
    response_model=dict[str, Any],
    responses=get_error_responses(429, 500),
)
async def get_startup_diagnostics() -> dict[str, Any]:
    """Get comprehensive diagnostics for troubleshooting slow boots.

    Includes:
    - Model loading timings
    - Failed models with error messages
    - Recommendations for speedup
    """
    loader = get_model_loader_state()
    progress = loader.get_progress()

    # Analyze issues
    recommendations = []
    details = progress.get("details", {})

    # Find slow models
    slow_threshold_ms = 5000  # 5 seconds
    for name, state in details.items():
        if state.get("status") == "ready" and state.get("elapsed_ms", 0) > slow_threshold_ms:
            recommendations.append(
                f"Model '{name}' took {state['elapsed_ms']:.0f}ms to load - "
                f"consider quantization or distillation"
            )

    # Find failed models
    failed = progress.get("models_failed", [])
    if failed:
        for name in failed:
            state = details.get(name, {})
            error = state.get("error", "unknown")
            recommendations.append(f"Model '{name}' failed: {error}")

    # Check if still loading after reasonable time
    if progress.get("elapsed_seconds", 0) > 30 and progress.get("models_loading"):
        recommendations.append(
            f"Boot is taking longer than expected (~{progress['elapsed_seconds']:.0f}s). "
            "Check system resources."
        )

    return {
        "progress": progress,
        "recommendations": recommendations,
        "estimated_ready_seconds": _estimate_ready_time(progress),
    }


def _estimate_ready_time(progress: dict[str, Any]) -> float:
    """Estimate remaining time until ready."""
    loading = progress.get("models_loading", [])

    if not loading:
        return 0.0

    # Rough estimate: assume each loading model takes 3-5 seconds
    # This is a heuristic for display purposes
    estimated_remaining = len(loading) * 4.0

    return max(0.0, estimated_remaining)


__all__ = ["router"]
