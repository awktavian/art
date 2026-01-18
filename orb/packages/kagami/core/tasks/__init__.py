"""Celery task queue integration and job scheduling for K os.

Full Operation Mode: All task components are REQUIRED. No graceful degradation.

CONSOLIDATION (December 8, 2025):
=================================
Merged kagami/core/scheduling/ → kagami/core/tasks/
Job definitions (BaseJob, ScheduledJob, RecurringJob) now live here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .app import CeleryConfig, celery_app
from .etcd_checkpoint_lock import checkpoint_lock

# HARDENED: etcd integration utilities are REQUIRED for distributed deployment
from .etcd_integration import ensure_single_instance_execution, leader_only_task

# HARDENED: Processing state tasks (organism monitoring) are REQUIRED
from .processing_state import (
    compute_composite_integration,
    gaussian_pid_synergy_task,
    generate_goals_task,
    train_instincts_task,
    update_causal_task,
    update_fractal_task,
    update_lzc_task,
    update_synergy_task,
)

# Optional imports - may not exist in all configurations
# HARDENED: All core tasks are REQUIRED - no graceful fallbacks
from .tasks import (
    cleanup_expired_data_task,
    generate_analytics_task,
    health_check_task,
    process_intent_task,
    sync_embeddings_task,
)

# =============================================================================
# JOB DEFINITIONS (merged from scheduling/)
# =============================================================================


@dataclass(slots=True)
class BaseJob:
    """Base class for all scheduled jobs."""

    id: str
    created_at: str = ""
    updated_at: str = ""
    intent: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# One-Shot Jobs
JobStatus = Literal["pending", "claimed", "cancelled", "completed"]


@dataclass(slots=True)
class ScheduledJob(BaseJob):
    """A single execution scheduled job."""

    run_at: str = ""
    status: JobStatus = "pending"
    outcome: dict[str, Any] | None = None


# Recurring Jobs
RecurrenceType = Literal["cron", "interval", "natural", "adaptive"]
ConflictStrategy = Literal["skip", "delay", "stack", "merge", "ask"]


@dataclass(slots=True)
class RecurringJob(BaseJob):
    """Recurring job definition with persona awareness."""

    name: str = ""
    description: str = ""
    recurrence_type: RecurrenceType = "cron"
    recurrence_spec: str = ""  # Cron expr, interval spec, or natural language

    # Scheduling configuration
    timezone_offset: int = 0  # Minutes from UTC
    enabled: bool = True

    # Persona and context
    owner_persona: str | None = None  # User persona or agent name
    preferred_times: list[str] = field(default_factory=list[Any])  # Preferred execution windows
    avoid_times: list[str] = field(default_factory=list[Any])  # Times to avoid

    # Conflict handling
    conflict_strategy: ConflictStrategy = "delay"
    max_delay_minutes: int = 60

    # Metadata
    last_run_at: str | None = None
    next_run_at: str | None = None
    run_count: int = 0

    # Learning and adaptation
    success_rate: float = 1.0
    average_duration_ms: float | None = None
    user_feedback: dict[str, Any] = field(default_factory=dict[str, Any])


__all__ = [
    "BaseJob",
    "CeleryConfig",
    "ConflictStrategy",
    "JobStatus",
    "RecurrenceType",
    "RecurringJob",
    "ScheduledJob",
    "celery_app",
    "checkpoint_lock",
    "cleanup_expired_data_task",
    "compute_composite_integration",
    "ensure_single_instance_execution",
    "gaussian_pid_synergy_task",
    "generate_analytics_task",
    "generate_goals_task",
    "health_check_task",
    "leader_only_task",
    "process_intent_task",
    "sync_embeddings_task",
    "train_instincts_task",
    "update_causal_task",
    "update_fractal_task",
    "update_lzc_task",
    "update_synergy_task",
]
