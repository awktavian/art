"""Plan-related schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PlanCreateRequest(BaseModel):
    """Request model for creating a new plan."""

    name: str
    description: str
    type: str | None = "project"
    target_date: datetime | None = None
    emotional_tags: list[str] | None = None
    visibility: str | None = "public"  # public|private


class PlanUpdateRequest(BaseModel):
    """Request model for updating a plan."""

    updates: dict[str, Any]


class TaskUpdateRequest(BaseModel):
    """Request model for updating a task."""

    updates: dict[str, Any]


class TaskResponse(BaseModel):
    """Response model for a task."""

    id: str
    plan_id: str
    title: str
    description: str | None = None
    status: str = "pending"
    priority: str = "medium"
    due_date: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    tags: list[str] = Field(default_factory=list[Any])
    metadata: dict[str, Any] = Field(default_factory=dict[str, Any])


class PlanResponse(BaseModel):
    """Response model for a plan."""

    id: str
    name: str
    description: str
    type: str = "project"
    status: str = "active"
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    target_date: datetime | None = None
    emotional_tags: list[str] = Field(default_factory=list[Any])
    tasks: list[dict[str, Any]] = Field(default_factory=list[Any])
    metadata: dict[str, Any] = Field(default_factory=dict[str, Any])


# Structured generation schemas (Pydantic) for plan suggest and task generation


class PlanSuggestArtifact(BaseModel):
    """Structured output for plan suggestions (matches PlanArtifact shape)."""

    title: str = Field("", description="Plan title; fallback to goal when empty")
    description: str | None = ""
    goals: list[str] | None = Field(default_factory=list[Any])
    tasks: list[dict[str, Any]] | None = Field(default_factory=list[Any])
    timeline: dict[str, Any] | None = Field(default_factory=dict[str, Any])
    owners: list[str] | None = Field(default_factory=list[Any])
    risks: list[str] | None = Field(default_factory=list[Any])
    metadata: dict[str, Any] | None = Field(default_factory=dict[str, Any])


class GeneratedTask(BaseModel):
    title: str
    priority: str = Field("medium", pattern=r"^(low|medium|high)$")
    description: str | None = None
    due_date: datetime | None = None
    metadata: dict[str, Any] | None = Field(default_factory=dict[str, Any])


class TaskList(BaseModel):
    tasks: list[GeneratedTask] = Field(default_factory=list[Any], max_length=8)
    metadata: dict[str, Any] | None = Field(default_factory=dict[str, Any])


# Aliases for consistency with naming convention
PlanCreate = PlanCreateRequest
TaskUpdate = TaskUpdateRequest
