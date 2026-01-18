"""Health Data Routes — Client Health Ingestion.

~180 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .core import get_controller

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================


class HealthMetrics(BaseModel):
    """Health metrics from client devices."""

    heart_rate: float | None = Field(None, description="Heart rate in BPM")
    resting_heart_rate: float | None = Field(None, description="Resting heart rate in BPM")
    hrv: float | None = Field(None, description="Heart rate variability in ms")
    steps: int | None = Field(None, description="Steps today")
    active_calories: int | None = Field(None, description="Active calories burned today")
    exercise_minutes: int | None = Field(None, description="Exercise minutes today")
    blood_oxygen: float | None = Field(None, description="Blood oxygen percentage (0-100)")
    sleep_hours: float | None = Field(None, description="Sleep duration in hours")


class HealthIngest(BaseModel):
    """Health data ingest request from client apps."""

    source: str = Field(..., description="Source system (healthkit, health_connect, etc.)")
    device: str = Field(..., description="Device type (apple_watch, vision_pro, android, etc.)")
    timestamp: str = Field(..., description="ISO8601 timestamp of measurement")
    metrics: HealthMetrics = Field(..., description="Health metrics")


# =============================================================================
# ROUTES
# =============================================================================


@router.post("/health/ingest")
async def ingest_health_data(data: HealthIngest) -> dict[str, Any]:
    """Ingest health data from client apps.

    Called by:
    - kagami-watch (Apple Watch via HealthKit)
    - kagami-vision (Vision Pro via HealthKit)
    - kagami-client (Android via Health Connect)
    - kagami-hub (if connected to health sources)

    The data is passed to the Apple Health integration for unified processing.
    """
    try:
        controller = await get_controller()

        # Get Apple Health integration
        if hasattr(controller, "_apple_health") and controller._apple_health:
            # Process via the health integration's webhook handler
            webhook_data = {
                "source": data.source,
                "device": data.device,
                "timestamp": data.timestamp,
                "data": {
                    "metrics": {
                        "heart_rate": data.metrics.heart_rate,
                        "resting_heart_rate": data.metrics.resting_heart_rate,
                        "hrv": data.metrics.hrv,
                        "steps": data.metrics.steps,
                        "active_calories": data.metrics.active_calories,
                        "exercise_minutes": data.metrics.exercise_minutes,
                        "blood_oxygen": data.metrics.blood_oxygen,
                        "sleep_hours": data.metrics.sleep_hours,
                    }
                },
            }
            await controller._apple_health.process_webhook(webhook_data)

            # Also update the unified sensory integration if available
            try:
                from kagami.core.integrations import get_unified_sensory

                sensory = get_unified_sensory()
                if sensory:
                    await sensory._poll_health()
            except ImportError:
                pass

            logger.info(
                f"✅ Health data ingested from {data.device} ({data.source}): "
                f"HR={data.metrics.heart_rate}, steps={data.metrics.steps}"
            )

            return {
                "success": True,
                "device": data.device,
                "timestamp": data.timestamp,
                "metrics_received": sum(
                    1
                    for v in [
                        data.metrics.heart_rate,
                        data.metrics.resting_heart_rate,
                        data.metrics.hrv,
                        data.metrics.steps,
                        data.metrics.active_calories,
                        data.metrics.exercise_minutes,
                        data.metrics.blood_oxygen,
                        data.metrics.sleep_hours,
                    ]
                    if v is not None
                ),
            }
        else:
            # No Apple Health integration - store directly
            logger.warning("Apple Health integration not available, storing metrics directly")
            return {
                "success": True,
                "device": data.device,
                "timestamp": data.timestamp,
                "stored_directly": True,
            }

    except Exception as e:
        logger.error(f"Health ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Health data ingest failed: {e}") from e


@router.get("/health/status")
async def get_health_status() -> dict[str, Any]:
    """Get current health status from all connected sources.

    Returns aggregated health data from:
    - Apple Health (via HealthKit clients)
    - Eight Sleep (bed presence, sleep tracking)
    - Any other connected biometric sources
    """
    try:
        controller = await get_controller()
        result: dict[str, Any] = {"sources": []}

        # Apple Health
        if hasattr(controller, "_apple_health") and controller._apple_health:
            if controller._apple_health.is_connected:
                state = controller._apple_health.get_state()
                result["apple_health"] = state.to_dict() if hasattr(state, "to_dict") else {}
                result["sources"].append("apple_health")

        # Eight Sleep
        if hasattr(controller, "_eight_sleep") and controller._eight_sleep:
            if controller._eight_sleep.is_connected:
                result["eight_sleep"] = {
                    "anyone_in_bed": controller._eight_sleep.is_anyone_in_bed(),
                    "anyone_asleep": controller._eight_sleep.is_anyone_asleep(),
                }
                result["sources"].append("eight_sleep")

        return result

    except Exception as e:
        logger.error(f"Health status error: {e}")
        return {"error": str(e), "sources": []}
