"""Intent Tracking System for K os Kernel.

Provides in-memory tracking of running intents with support for:
- Query intent status
- Cancel running intents
- Track completion/errors
- Emit receipts for lifecycle events

Created: November 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class IntentStatus(str, Enum):
    """Intent execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrackedIntent:
    """Tracked intent with metadata."""

    intent_id: str
    action: str
    params: dict[str, Any]
    status: IntentStatus = IntentStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None
    correlation_id: str | None = None

    # Task handle for cancellation
    task: asyncio.Task | None = None


class IntentTracker:
    """Global intent tracker for kernel syscalls.

    Provides fast in-memory tracking with optional Redis persistence.
    """

    def __init__(self) -> None:
        self._intents: dict[str, TrackedIntent] = {}
        self._lock = asyncio.Lock()

        # Cleanup old intents after 1 hour
        self._cleanup_interval = 3600
        self._last_cleanup = time.time()

    async def track_intent(
        self,
        intent_id: str,
        action: str,
        params: dict[str, Any],
        correlation_id: str | None = None,
        task: asyncio.Task | None = None,
    ) -> TrackedIntent:
        """Start tracking an intent.

        Args:
            intent_id: Unique intent ID
            action: Action being executed
            params: Intent parameters
            correlation_id: Optional correlation ID for receipts
            task: Optional asyncio task handle

        Returns:
            TrackedIntent instance
        """
        async with self._lock:
            tracked = TrackedIntent(
                intent_id=intent_id,
                action=action,
                params=params,
                status=IntentStatus.RUNNING,
                started_at=time.time(),
                correlation_id=correlation_id,
                task=task,
            )

            self._intents[intent_id] = tracked

            logger.debug(f"Tracking intent {intent_id}: {action}")

            # Periodic cleanup
            await self._maybe_cleanup()

            return tracked

    async def update_intent_status(
        self,
        intent_id: str,
        status: IntentStatus,
        result: Any = None,
        error: str | None = None,
    ) -> bool:
        """Update intent status.

        Args:
            intent_id: Intent ID
            status: New status
            result: Optional result data
            error: Optional error message

        Returns:
            True if updated, False if intent not found
        """
        async with self._lock:
            if intent_id not in self._intents:
                return False

            tracked = self._intents[intent_id]
            tracked.status = status
            tracked.result = result
            tracked.error = error

            if status in (IntentStatus.COMPLETED, IntentStatus.FAILED, IntentStatus.CANCELLED):
                tracked.completed_at = time.time()

            logger.debug(f"Intent {intent_id} status: {status.value}")

            return True

    async def get_intent(self, intent_id: str) -> TrackedIntent | None:
        """Get tracked intent by ID.

        Args:
            intent_id: Intent ID

        Returns:
            TrackedIntent or None if not found
        """
        async with self._lock:
            return self._intents.get(intent_id)

    async def cancel_intent(self, intent_id: str) -> bool:
        """Cancel running intent.

        Args:
            intent_id: Intent ID

        Returns:
            True if cancelled, False if not found or already completed
        """
        async with self._lock:
            if intent_id not in self._intents:
                logger.warning(f"Cannot cancel intent {intent_id}: not found")
                return False

            tracked = self._intents[intent_id]

            # Can't cancel completed/failed intents
            if tracked.status in (
                IntentStatus.COMPLETED,
                IntentStatus.FAILED,
                IntentStatus.CANCELLED,
            ):
                logger.warning(f"Cannot cancel intent {intent_id}: already {tracked.status.value}")
                return False

            # Cancel asyncio task if present
            if tracked.task and not tracked.task.done():
                tracked.task.cancel()
                logger.info(f"Cancelled task for intent {intent_id}")

            # Update status
            tracked.status = IntentStatus.CANCELLED
            tracked.completed_at = time.time()
            tracked.error = "Cancelled by user"

            # Emit cancellation receipt
            try:
                from kagami.core.receipts import UnifiedReceiptFacade as URF

                await URF.emit(  # type: ignore[misc]
                    correlation_id=tracked.correlation_id or intent_id,
                    action="intent.cancel",
                    event_name="INTENT_CANCELLED",
                    data={
                        "intent_id": intent_id,
                        "action": tracked.action,
                        "reason": "user_requested",
                    },
                )
            except Exception as e:
                logger.debug(f"Failed to emit cancellation receipt: {e}")

            logger.info(f"Intent {intent_id} cancelled")
            return True

    async def list_active_intents(self) -> list[dict[str, Any]]:
        """List all active intents.

        Returns:
            List of intent summaries
        """
        async with self._lock:
            active = []

            for intent in self._intents.values():
                if intent.status in (IntentStatus.PENDING, IntentStatus.RUNNING):
                    active.append(
                        {
                            "intent_id": intent.intent_id,
                            "action": intent.action,
                            "status": intent.status.value,
                            "created_at": intent.created_at,
                            "duration_ms": (time.time() - intent.created_at) * 1000,
                        }
                    )

            return active

    async def _maybe_cleanup(self) -> None:
        """Cleanup old completed intents."""
        now = time.time()

        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now

        # Remove intents older than 1 hour
        cutoff = now - 3600
        to_remove = []

        for intent_id, tracked in self._intents.items():
            if (
                tracked.status
                in (IntentStatus.COMPLETED, IntentStatus.FAILED, IntentStatus.CANCELLED)
                and (tracked.completed_at or tracked.created_at) < cutoff
            ):
                to_remove.append(intent_id)

        for intent_id in to_remove:
            del self._intents[intent_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old intents")

    def get_stats(self) -> dict[str, Any]:
        """Get tracker statistics.

        Returns:
            Stats dict[str, Any]
        """
        status_counts: dict[str, Any] = {}
        for tracked in self._intents.values():
            status_counts[tracked.status.value] = status_counts.get(tracked.status.value, 0) + 1

        return {
            "total_tracked": len(self._intents),
            "by_status": status_counts,
        }


# Global singleton
_intent_tracker: IntentTracker | None = None


def get_intent_tracker() -> IntentTracker:
    """Get global intent tracker.

    Returns:
        IntentTracker singleton
    """
    global _intent_tracker

    if _intent_tracker is None:
        _intent_tracker = IntentTracker()

    return _intent_tracker


__all__ = [
    "IntentStatus",
    "IntentTracker",
    "TrackedIntent",
    "get_intent_tracker",
]
