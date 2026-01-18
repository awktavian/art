"""Recurring Task Scheduler Module.

Provides functions for creating and managing recurring tasks.
Re-exports types from kagami.core.tasks.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

# Re-export types from tasks module
from kagami.core.tasks import ConflictStrategy, RecurrenceType, RecurringJob

logger = logging.getLogger(__name__)


async def create_recurring(
    name: str,
    intent: dict[str, Any],
    recurrence_type: RecurrenceType,
    recurrence_spec: str,
    *,
    description: str = "",
    conflict_strategy: ConflictStrategy = "delay",
    owner_persona: str | None = None,
    enabled: bool = True,
) -> RecurringJob:
    """Create a new recurring task.

    Args:
        name: Task name
        intent: Intent dict to execute
        recurrence_type: Type of recurrence (cron, interval, natural, adaptive)
        recurrence_spec: Recurrence specification (cron expr, interval, etc.)
        description: Task description
        conflict_strategy: How to handle conflicts
        owner_persona: Optional owner persona
        enabled: Whether the task is enabled

    Returns:
        RecurringJob instance
    """
    import uuid

    now = datetime.now(UTC).isoformat()
    job = RecurringJob(
        id=uuid.uuid4().hex,
        name=name,
        description=description,
        intent=intent,
        recurrence_type=recurrence_type,
        recurrence_spec=recurrence_spec,
        conflict_strategy=conflict_strategy,
        owner_persona=owner_persona,
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )

    logger.info(f"Created recurring job: {name} ({recurrence_type}: {recurrence_spec})")
    return job


async def get_recommendations(
    context: dict[str, Any] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Get scheduling recommendations based on context.

    Args:
        context: Optional context for personalized recommendations
        limit: Maximum number of recommendations to return

    Returns:
        List of recommendation dicts
    """
    # Basic recommendations - can be enhanced with ML-based suggestions
    recommendations = [
        {
            "type": "daily_check",
            "name": "Daily Status Check",
            "recurrence_type": "cron",
            "recurrence_spec": "0 9 * * *",
            "description": "Daily morning status check",
            "confidence": 0.9,
        },
        {
            "type": "weekly_backup",
            "name": "Weekly Backup",
            "recurrence_type": "cron",
            "recurrence_spec": "0 2 * * 0",
            "description": "Weekly backup on Sunday at 2 AM",
            "confidence": 0.85,
        },
        {
            "type": "hourly_metrics",
            "name": "Hourly Metrics Collection",
            "recurrence_type": "interval",
            "recurrence_spec": "1h",
            "description": "Collect system metrics every hour",
            "confidence": 0.8,
        },
    ]

    return recommendations[:limit]


__all__ = [
    "ConflictStrategy",
    "RecurrenceType",
    "RecurringJob",
    "create_recurring",
    "get_recommendations",
]
