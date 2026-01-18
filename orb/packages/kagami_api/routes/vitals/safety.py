"""Safety vitals endpoint - real-time h(x) monitoring.

CREATED: December 20, 2025
PURPOSE: Expose CBF safety metrics for external monitoring

Endpoints:
- GET /api/vitals/safety - Current h(x) values and safety status
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================


class SafetyVitalsResponse(BaseModel):
    """Current safety vitals from CBF monitor."""

    monitor_ready: bool = Field(..., description="Is CBF monitor operational")
    current_h_value: float | None = Field(
        default=None, description="Most recent barrier value h(x)"
    )
    zone: str | None = Field(default=None, description="Safety zone (GREEN/YELLOW/RED)")
    statistics: dict[str, Any] = Field(default_factory=dict, description="Historical statistics")
    recent_violations: list[dict[str, Any]] = Field(
        default_factory=list, description="Recent violation records"
    )
    timestamp: float = Field(..., description="Response timestamp")


# =============================================================================
# ROUTER
# =============================================================================


def get_router() -> APIRouter:
    """Create safety vitals router."""
    router = APIRouter(tags=["vitals"])

    @router.get("/safety", response_model=SafetyVitalsResponse)
    async def get_safety_vitals(request: Request) -> SafetyVitalsResponse:
        """Get current CBF safety vitals.

        Returns:
            SafetyVitalsResponse with current h(x) values and monitoring stats

        Example:
            ```bash
            curl http://localhost:8000/api/vitals/safety
            ```

        Response:
            ```json
            {
              "monitor_ready": true,
              "current_h_value": 0.87,
              "zone": "GREEN",
              "statistics": {
                "total_checks": 1523,
                "violations": 0,
                "warnings": 12,
                "mean_h": 0.82
              },
              "recent_violations": [],
              "timestamp": 1734753600.0
            }
            ```
        """
        try:
            # Check if monitor is initialized
            monitor_ready = getattr(request.app.state, "cbf_monitor_ready", False)
            monitor = getattr(request.app.state, "cbf_monitor", None)

            if not monitor_ready or monitor is None:
                return SafetyVitalsResponse(
                    monitor_ready=False,
                    current_h_value=None,
                    zone=None,
                    statistics={},
                    recent_violations=[],
                    timestamp=time.time(),
                )

            # Get statistics from monitor
            stats = monitor.get_statistics()

            # Determine current h value and zone
            current_h = stats.get("mean_h", None)
            zone = None
            if current_h is not None:
                if current_h > 0.5:
                    zone = "GREEN"
                elif current_h >= 0.0:
                    zone = "YELLOW"
                else:
                    zone = "RED"

            # Get recent violations
            violations = monitor.get_violations()
            recent_violations = [
                {
                    "timestamp": v.timestamp,
                    "h_value": v.h_value,
                    "operation": v.operation,
                    "barrier": v.barrier_name,
                    "tier": v.tier,
                }
                for v in violations[-10:]  # Last 10 violations
            ]

            return SafetyVitalsResponse(
                monitor_ready=True,
                current_h_value=current_h,
                zone=zone,
                statistics=stats,
                recent_violations=recent_violations,
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"Safety vitals check failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Safety vitals unavailable: {e!s}") from e

    return router


__all__ = ["SafetyVitalsResponse", "get_router"]
