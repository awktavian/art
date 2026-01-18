"""Vitals/Health API Schemas.

Typed request/response models for:
- GET /api/vitals/probes/live
- GET /api/vitals/probes/ready
- GET /api/vitals/probes/deep
- GET /api/vitals/probes/cluster
- GET /api/vitals/probes/dependencies
- GET /api/vitals/
- GET /api/vitals/summary
- GET /api/vitals/fano
- GET /api/vitals/hal/
- GET /api/vitals/ml/
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# =============================================================================
# DEPENDENCY CHECKS
# =============================================================================


class DependencyCheck(BaseModel):
    """Health check result for a single dependency."""

    status: Literal["healthy", "degraded", "unhealthy", "unavailable"] = Field(
        ..., description="Dependency status"
    )
    latency_ms: float | None = Field(None, description="Check latency in milliseconds")
    error: str | None = Field(None, description="Error message if unhealthy")
    note: str | None = Field(None, description="Additional context")

    model_config = {"json_schema_extra": {"example": {"status": "healthy", "latency_ms": 2.5}}}


# =============================================================================
# PROBE RESPONSES
# =============================================================================


class LivenessResponse(BaseModel):
    """Kubernetes liveness probe response."""

    status: Literal["ok"] = Field("ok", description="Always 'ok' if process is alive")
    service: str = Field("kagami", description="Service name")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Check time")
    probe: Literal["liveness"] = Field("liveness", description="Probe type")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "service": "kagami",
                "timestamp": "2025-12-06T15:30:00Z",
                "probe": "liveness",
            }
        }
    }


class ReadinessResponse(BaseModel):
    """Kubernetes readiness probe response."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall readiness status"
    )
    ready: bool = Field(..., description="Whether service can accept traffic")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Check time")
    probe: Literal["readiness"] = Field("readiness", description="Probe type")
    checks: dict[str, DependencyCheck] = Field(
        default_factory=dict, description="Individual component checks"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "ready": True,
                "timestamp": "2025-12-06T15:30:00Z",
                "probe": "readiness",
                "checks": {
                    "boot": {"status": "healthy"},
                    "metrics": {"status": "healthy"},
                    "socketio": {"status": "healthy"},
                },
            }
        }
    }


class DeepHealthResponse(BaseModel):
    """Deep health check response with all dependencies."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall health status"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Check time")
    # NOTE: This response model is shared by multiple probe endpoints.
    probe: Literal["deep", "dependencies"] = Field("deep", description="Probe type")
    duration_ms: float = Field(..., description="Total check duration in milliseconds")
    checks: dict[str, DependencyCheck] = Field(..., description="All dependency checks")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2025-12-06T15:30:00Z",
                "probe": "deep",
                "duration_ms": 45.2,
                "checks": {
                    "database": {"status": "healthy", "latency_ms": 5.2},
                    "redis": {"status": "healthy", "latency_ms": 1.1},
                    "etcd": {"status": "healthy", "latency_ms": 3.4},
                    "boot": {"status": "healthy"},
                    "orchestrator": {"status": "healthy"},
                    "socketio": {"status": "healthy"},
                    "metrics": {"status": "healthy"},
                },
            }
        }
    }


class ClusterHealthResponse(BaseModel):
    """Cluster health check response."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Cluster health status"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Check time")
    probe: Literal["cluster"] = Field("cluster", description="Probe type")
    checks: dict[str, DependencyCheck] = Field(
        default_factory=dict, description="Cluster component checks"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2025-12-06T15:30:00Z",
                "probe": "cluster",
                "checks": {
                    "etcd": {"status": "healthy", "latency_ms": 2.1},
                    "consensus": {"status": "healthy", "note": "converged: true"},
                },
            }
        }
    }


# =============================================================================
# ORGANISM VITALS
# =============================================================================


class OrganismVitals(BaseModel):
    """Comprehensive organism vitals."""

    status: str = Field(..., description="Overall organism status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Measurement time"
    )

    # Core metrics
    coherence: float = Field(..., ge=0, le=1, description="System coherence (0-1)")
    metabolism: float = Field(..., ge=0, description="Metabolic rate")
    load: float = Field(..., ge=0, le=1, description="System load (0-1)")

    # Colony health
    colonies: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Per-colony health"
    )

    # Resource usage
    cpu_percent: float = Field(0, ge=0, le=100, description="CPU usage %")
    memory_percent: float = Field(0, ge=0, le=100, description="Memory usage %")

    # Counts
    active_agents: int = Field(0, description="Active agent count")
    pending_tasks: int = Field(0, description="Pending task count")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2025-12-06T15:30:00Z",
                "coherence": 0.95,
                "metabolism": 1.2,
                "load": 0.45,
                "colonies": {
                    "spark": {"status": "active", "agents": 2},
                    "forge": {"status": "active", "agents": 1},
                },
                "cpu_percent": 35.2,
                "memory_percent": 48.5,
                "active_agents": 5,
                "pending_tasks": 12,
            }
        }
    }


class VitalsSummary(BaseModel):
    """Compact vitals for status bars."""

    status: str = Field(..., description="Status emoji/short string")
    coherence: float = Field(..., ge=0, le=1, description="Coherence (0-1)")
    load: float = Field(..., ge=0, le=1, description="Load (0-1)")
    active_colonies: int = Field(..., description="Number of active colonies")
    tone: str = Field(..., description="Current emotional tone")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "✨",
                "coherence": 0.95,
                "load": 0.3,
                "active_colonies": 5,
                "tone": "curious",
            }
        }
    }


class FanoVitals(BaseModel):
    """Fano plane collaboration vitals."""

    status: str = Field(..., description="Fano collaboration status")
    active_triads: list[tuple[str, str, str]] = Field(
        default_factory=list, description="Active Fano triads"
    )
    collaboration_strength: float = Field(0, ge=0, le=1, description="Collaboration strength")
    bottleneck_colony: str | None = Field(None, description="Current bottleneck if any")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "synchronized",
                "active_triads": [["spark", "forge", "nexus"], ["flow", "beacon", "grove"]],
                "collaboration_strength": 0.87,
                "bottleneck_colony": None,
            }
        }
    }


# =============================================================================
# HARDWARE / HAL
# =============================================================================


class HardwareStatus(BaseModel):
    """HAL subsystem health."""

    status: str = Field(..., description="HAL status")
    adapters: list[dict[str, Any]] = Field(default_factory=list, description="HAL adapters")
    available_sensors: list[str] = Field(default_factory=list, description="Available sensors")
    available_actuators: list[str] = Field(default_factory=list, description="Available actuators")


# =============================================================================
# ML HEALTH
# =============================================================================


class MLHealthStatus(BaseModel):
    """ML subsystem health."""

    status: Literal["operational", "degraded", "unavailable"] = Field(
        ..., description="ML system status"
    )
    components: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Individual ML component status"
    )
    model_loaded: bool = Field(False, description="Whether main model is loaded")
    inference_ready: bool = Field(False, description="Whether inference is ready")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "operational",
                "components": {
                    "world_model": {"status": "loaded", "device": "cuda"},
                    "embeddings": {"status": "ready", "model": "all-MiniLM-L6-v2"},
                    "llm": {"status": "available", "model": "llama-3.1"},
                },
                "model_loaded": True,
                "inference_ready": True,
            }
        }
    }


__all__ = [
    "ClusterHealthResponse",
    "DeepHealthResponse",
    "DependencyCheck",
    "FanoVitals",
    "HardwareStatus",
    "LivenessResponse",
    "MLHealthStatus",
    "OrganismVitals",
    "ReadinessResponse",
    "VitalsSummary",
]
