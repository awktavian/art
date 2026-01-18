"""Colonies/Agents API Schemas.

Typed request/response models for:
- GET /api/colonies/agents/list
- GET /api/colonies/agents/status
- GET /api/colonies/agents/{id}/state
- WebSocket /api/colonies/stream
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent status enum."""

    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    PAUSED = "paused"
    ERROR = "error"


class AgentSummary(BaseModel):
    """Summary of an agent."""

    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    colony: str = Field(..., description="Colony the agent belongs to")
    status: AgentStatus = Field(..., description="Current status")
    current_task: str | None = Field(None, description="Current task description")
    uptime_seconds: float = Field(0, description="Agent uptime in seconds")
    tasks_completed: int = Field(0, description="Total tasks completed")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "spark-001",
                "name": "Spark Alpha",
                "colony": "spark",
                "status": "active",
                "current_task": "Processing intent",
                "uptime_seconds": 3600.5,
                "tasks_completed": 42,
            }
        }
    }


class AgentState(BaseModel):
    """Full agent state."""

    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    colony: str = Field(..., description="Colony name")
    status: AgentStatus = Field(..., description="Current status")

    # Task info
    current_task: str | None = Field(None, description="Current task")
    task_queue_size: int = Field(0, description="Tasks in queue")
    tasks_completed: int = Field(0, description="Total completed")
    tasks_failed: int = Field(0, description="Total failed")

    # Metrics
    cpu_usage: float = Field(0, ge=0, le=100, description="CPU usage %")
    memory_mb: float = Field(0, ge=0, description="Memory usage MB")

    # State
    coherence: float = Field(1.0, ge=0, le=1, description="Agent coherence (0-1)")
    energy: float = Field(1.0, ge=0, le=1, description="Agent energy (0-1)")

    # Timing
    created_at: datetime = Field(..., description="Creation time")
    last_active: datetime = Field(..., description="Last activity time")
    uptime_seconds: float = Field(0, description="Uptime in seconds")

    # Internal state
    internal_state: dict[str, Any] = Field(default_factory=dict, description="Internal state data")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "forge-001",
                "name": "Forge Prime",
                "colony": "forge",
                "status": "busy",
                "current_task": "Building component",
                "task_queue_size": 3,
                "tasks_completed": 156,
                "tasks_failed": 2,
                "cpu_usage": 45.2,
                "memory_mb": 128.5,
                "coherence": 0.95,
                "energy": 0.78,
                "created_at": "2025-12-06T10:00:00Z",
                "last_active": "2025-12-06T15:30:00Z",
                "uptime_seconds": 19800,
            }
        }
    }


class AgentsListResponse(BaseModel):
    """Response for agents list."""

    agents: list[AgentSummary] = Field(..., description="List of agents")
    total: int = Field(..., description="Total agent count")
    page: int = Field(default=1, description="Current page number")
    per_page: int = Field(default=20, description="Items per page")
    has_more: bool = Field(default=False, description="Whether more items are available")
    by_colony: dict[str, int] = Field(default_factory=dict, description="Count by colony")
    by_status: dict[str, int] = Field(default_factory=dict, description="Count by status")


class AgentsStatusResponse(BaseModel):
    """Aggregated agent status overview."""

    total_agents: int = Field(..., description="Total agents")
    active_agents: int = Field(..., description="Currently active")
    idle_agents: int = Field(..., description="Currently idle")
    busy_agents: int = Field(..., description="Currently busy")
    error_agents: int = Field(..., description="In error state")

    colonies: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Status breakdown by colony"
    )

    total_tasks_completed: int = Field(0, description="Total tasks completed across all agents")
    avg_coherence: float = Field(1.0, ge=0, le=1, description="Average coherence")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_agents": 7,
                "active_agents": 3,
                "idle_agents": 2,
                "busy_agents": 1,
                "error_agents": 1,
                "colonies": {
                    "spark": {"active": 1, "idle": 0},
                    "forge": {"active": 1, "busy": 1},
                    "flow": {"idle": 1, "error": 1},
                },
                "total_tasks_completed": 1234,
                "avg_coherence": 0.92,
            }
        }
    }


class ColonyStatus(BaseModel):
    """Status of a single colony."""

    name: str = Field(..., description="Colony name")
    active_agents: int = Field(0, description="Number of active agents")
    status: Literal["active", "idle", "error"] = Field(..., description="Overall colony status")
    catastrophe_type: str = Field(..., description="Catastrophe type (e.g., A2, A3)")
    success_rate: float = Field(1.0, ge=0, le=1, description="Colony success rate (0-1)")
    tasks_completed: int = Field(0, description="Total tasks completed by colony")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "spark",
                "active_agents": 2,
                "status": "active",
                "catastrophe_type": "A2",
                "success_rate": 0.95,
                "tasks_completed": 142,
            }
        }
    }


class ColoniesStatusResponse(BaseModel):
    """System-wide colony status response."""

    colonies: dict[str, ColonyStatus] = Field(..., description="Status by colony name")
    total_agents: int = Field(0, description="Total agents across all colonies")
    timestamp: datetime = Field(..., description="Status snapshot time")
    status: Literal["operational", "degraded", "error"] = Field(
        ..., description="Overall system status"
    )
    avg_success_rate: float = Field(1.0, ge=0, le=1, description="Average success rate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "colonies": {
                    "spark": {
                        "name": "spark",
                        "active_agents": 2,
                        "status": "active",
                        "catastrophe_type": "A2",
                        "success_rate": 0.95,
                        "tasks_completed": 142,
                    },
                    "forge": {
                        "name": "forge",
                        "active_agents": 1,
                        "status": "active",
                        "catastrophe_type": "A3",
                        "success_rate": 0.98,
                        "tasks_completed": 256,
                    },
                },
                "total_agents": 7,
                "timestamp": "2025-12-19T12:00:00Z",
                "status": "operational",
                "avg_success_rate": 0.96,
            }
        }
    }


class ColonyActivityEvent(BaseModel):
    """Event from colony activity stream."""

    type: Literal[
        "initial_state",
        "agent_created",
        "agent_updated",
        "agent_destroyed",
        "task_started",
        "task_completed",
        "task_failed",
        "heartbeat",
        "error",
    ] = Field(..., description="Event type")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Event time")
    agent_id: str | None = Field(None, description="Agent ID if applicable")
    colony: str | None = Field(None, description="Colony if applicable")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "agent_updated",
                    "timestamp": "2025-12-06T15:30:00Z",
                    "agent_id": "spark-001",
                    "colony": "spark",
                    "data": {"status": "active", "current_task": "Processing"},
                },
                {
                    "type": "task_completed",
                    "timestamp": "2025-12-06T15:30:05Z",
                    "agent_id": "forge-001",
                    "colony": "forge",
                    "data": {"task_id": "task-123", "duration_ms": 1500},
                },
            ]
        }
    }


__all__ = [
    "AgentState",
    "AgentStatus",
    "AgentSummary",
    "AgentsListResponse",
    "AgentsStatusResponse",
    "ColoniesStatusResponse",
    "ColonyActivityEvent",
    "ColonyStatus",
]
