"""Audit Trail — Complete action logging for SmartHome operations.

Records all actions with:
- Timestamp, action, parameters
- Success/failure status
- Execution time
- Error details (if failed)
- Actor (who initiated)

Provides:
- Full traceability for debugging
- Security audit compliance
- Performance analysis

Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    """Status of an audited action."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionCategory(str, Enum):
    """Category of action for filtering."""

    LIGHT = "light"
    SHADE = "shade"
    AUDIO = "audio"
    HVAC = "hvac"
    SECURITY = "security"
    TV = "tv"
    SCENE = "scene"
    PRESENCE = "presence"
    SYSTEM = "system"


@dataclass
class AuditRecord:
    """A single audit record."""

    id: str
    timestamp: float
    action: str
    category: ActionCategory
    parameters: dict[str, Any]
    status: ActionStatus = ActionStatus.PENDING
    actor: str = "system"  # Who initiated (user, automation, api)
    rooms: list[str] = field(default_factory=list)
    integration: str | None = None  # Which integration handled it

    # Filled after completion
    end_timestamp: float | None = None
    duration_ms: float | None = None
    error: str | None = None
    result: dict[str, Any] | None = None

    @property
    def datetime(self) -> datetime:
        """Get timestamp as datetime."""
        return datetime.fromtimestamp(self.timestamp)

    @property
    def is_complete(self) -> bool:
        """Check if action is complete."""
        return self.status in (ActionStatus.SUCCESS, ActionStatus.FAILED, ActionStatus.CANCELLED)


class AuditTrail:
    """Complete audit trail for SmartHome operations.

    Usage:
        audit = get_audit_trail()

        # Start an action
        record_id = audit.start_action(
            action="set_lights",
            category=ActionCategory.LIGHT,
            parameters={"level": 50, "rooms": ["Living Room"]},
            actor="user",
        )

        try:
            await do_action()
            audit.complete_success(record_id, result={"changed": 3})
        except Exception as e:
            audit.complete_failure(record_id, error=str(e))

        # Or use context manager
        async with audit.track("set_lights", ActionCategory.LIGHT, {"level": 50}) as record:
            await do_action()
    """

    def __init__(
        self,
        max_records: int = 10000,
        persist_path: Path | None = None,
    ):
        """Initialize audit trail.

        Args:
            max_records: Maximum records to keep in memory
            persist_path: Optional path to persist records
        """
        self._records: deque[AuditRecord] = deque(maxlen=max_records)
        self._pending: dict[str, AuditRecord] = {}
        self._persist_path = persist_path
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "total_actions": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_duration_ms": 0.0,
        }

    def start_action(
        self,
        action: str,
        category: ActionCategory,
        parameters: dict[str, Any],
        actor: str = "system",
        rooms: list[str] | None = None,
        integration: str | None = None,
    ) -> str:
        """Start tracking an action.

        Args:
            action: Action name (e.g., "set_lights")
            category: Action category
            parameters: Action parameters
            actor: Who initiated the action
            rooms: Affected rooms
            integration: Which integration handles it

        Returns:
            Record ID for completing the action
        """
        record_id = str(uuid.uuid4())[:8]
        record = AuditRecord(
            id=record_id,
            timestamp=time.time(),
            action=action,
            category=category,
            parameters=parameters,
            status=ActionStatus.IN_PROGRESS,
            actor=actor,
            rooms=rooms or [],
            integration=integration,
        )

        self._pending[record_id] = record
        self._stats["total_actions"] += 1

        logger.debug(f"[AUDIT] Started: {action} ({record_id})")
        return record_id

    def complete_success(
        self,
        record_id: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Mark action as successful.

        Args:
            record_id: Record ID from start_action
            result: Optional result data
        """
        record = self._pending.pop(record_id, None)
        if not record:
            logger.warning(f"[AUDIT] Unknown record ID: {record_id}")
            return

        record.status = ActionStatus.SUCCESS
        record.end_timestamp = time.time()
        record.duration_ms = (record.end_timestamp - record.timestamp) * 1000
        record.result = result

        self._records.append(record)
        self._stats["success_count"] += 1
        self._stats["total_duration_ms"] += record.duration_ms

        logger.debug(
            f"[AUDIT] Success: {record.action} ({record_id}) in {record.duration_ms:.1f}ms"
        )

        if self._persist_path:
            self._persist_record(record)

    def complete_failure(
        self,
        record_id: str,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Mark action as failed.

        Args:
            record_id: Record ID from start_action
            error: Error message
            result: Optional partial result
        """
        record = self._pending.pop(record_id, None)
        if not record:
            logger.warning(f"[AUDIT] Unknown record ID: {record_id}")
            return

        record.status = ActionStatus.FAILED
        record.end_timestamp = time.time()
        record.duration_ms = (record.end_timestamp - record.timestamp) * 1000
        record.error = error
        record.result = result

        self._records.append(record)
        self._stats["failure_count"] += 1
        self._stats["total_duration_ms"] += record.duration_ms

        logger.warning(f"[AUDIT] Failed: {record.action} ({record_id}): {error}")

        if self._persist_path:
            self._persist_record(record)

    def cancel(self, record_id: str, reason: str = "cancelled") -> None:
        """Cancel a pending action.

        Args:
            record_id: Record ID from start_action
            reason: Cancellation reason
        """
        record = self._pending.pop(record_id, None)
        if not record:
            return

        record.status = ActionStatus.CANCELLED
        record.end_timestamp = time.time()
        record.error = reason
        self._records.append(record)

        logger.debug(f"[AUDIT] Cancelled: {record.action} ({record_id}): {reason}")

    def track(
        self,
        action: str,
        category: ActionCategory,
        parameters: dict[str, Any],
        **kwargs: Any,
    ) -> AuditContext:
        """Context manager for tracking an action.

        Usage:
            async with audit.track("set_lights", ActionCategory.LIGHT, params) as record:
                await do_action()
                record.result = {"changed": 3}  # Optional result
        """
        return AuditContext(self, action, category, parameters, **kwargs)

    def get_recent(
        self,
        count: int = 100,
        category: ActionCategory | None = None,
        status: ActionStatus | None = None,
    ) -> list[AuditRecord]:
        """Get recent audit records.

        Args:
            count: Max records to return
            category: Filter by category
            status: Filter by status

        Returns:
            List of audit records (newest first)
        """
        records = list(self._records)[-count:]

        if category:
            records = [r for r in records if r.category == category]
        if status:
            records = [r for r in records if r.status == status]

        return list(reversed(records))

    def get_failures(self, count: int = 50) -> list[AuditRecord]:
        """Get recent failures."""
        return self.get_recent(count=count, status=ActionStatus.FAILED)

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        avg_duration = (
            self._stats["total_duration_ms"] / self._stats["success_count"]
            if self._stats["success_count"] > 0
            else 0
        )

        success_rate = (
            self._stats["success_count"] / self._stats["total_actions"]
            if self._stats["total_actions"] > 0
            else 1.0
        )

        return {
            **self._stats,
            "pending_count": len(self._pending),
            "records_in_memory": len(self._records),
            "avg_duration_ms": avg_duration,
            "success_rate": success_rate,
        }

    def _persist_record(self, record: AuditRecord) -> None:
        """Persist a record to disk."""
        if not self._persist_path:
            return

        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to JSONL file
            with open(self._persist_path, "a") as f:
                data = asdict(record)
                data["category"] = record.category.value
                data["status"] = record.status.value
                f.write(json.dumps(data) + "\n")

        except Exception as e:
            logger.warning(f"Failed to persist audit record: {e}")


class AuditContext:
    """Async context manager for audit tracking."""

    def __init__(
        self,
        audit: AuditTrail,
        action: str,
        category: ActionCategory,
        parameters: dict[str, Any],
        **kwargs: Any,
    ):
        self._audit = audit
        self._action = action
        self._category = category
        self._parameters = parameters
        self._kwargs = kwargs
        self._record_id: str | None = None
        self.result: dict[str, Any] | None = None

    async def __aenter__(self) -> AuditContext:
        self._record_id = self._audit.start_action(
            action=self._action,
            category=self._category,
            parameters=self._parameters,
            **self._kwargs,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._record_id is None:
            return

        if exc_type is None:
            self._audit.complete_success(self._record_id, result=self.result)
        else:
            self._audit.complete_failure(self._record_id, error=str(exc_val))


# Singleton instance
_audit_trail: AuditTrail | None = None


def get_audit_trail() -> AuditTrail:
    """Get singleton audit trail instance."""
    global _audit_trail
    if _audit_trail is None:
        # Default persist path
        persist_path = Path.home() / ".kagami" / "audit.jsonl"
        _audit_trail = AuditTrail(persist_path=persist_path)
    return _audit_trail


__all__ = [
    "ActionCategory",
    "ActionStatus",
    "AuditRecord",
    "AuditTrail",
    "get_audit_trail",
]
