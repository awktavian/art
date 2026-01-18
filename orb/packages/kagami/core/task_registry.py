"""Global task registry with automatic cleanup.

CRITICAL SAFETY SYSTEM to prevent unbounded task creation (Nov 9, 2025 kernel panic).

This registry:
1. Tracks ALL background tasks globally
2. Enforces hard limit (default 5,000 tasks)
3. Automatic cleanup of completed tasks
4. Graceful shutdown support
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from weakref import WeakSet

logger = logging.getLogger(__name__)


class TaskRegistry:
    """Global registry for all background tasks with lifecycle management.

    SAFETY: Prevents unbounded task creation that caused kernel panic.

    Usage:
        registry = get_task_registry()

        # Register task (returns False if limit exceeded)
        task = asyncio.create_task(coro())
        if not registry.register_task(task):
            task.cancel()
            raise RuntimeError("Task limit exceeded")
    """

    def __init__(self, max_tasks: int = 5000) -> None:
        """Initialize registry with hard limit.

        Args:
            max_tasks: Maximum number of concurrent tasks (default 5,000)
        """
        # Use WeakSet so completed tasks are auto-removed by GC
        self.tasks: WeakSet[asyncio.Task[Any]] = WeakSet()
        self.max_tasks = max_tasks
        self._lock = asyncio.Lock()

        # Statistics
        self.total_created = 0
        self.total_rejected = 0
        self.total_completed = 0

        logger.info(f"TaskRegistry initialized (max_tasks={max_tasks})")

    def register_task(self, task: asyncio.Task[Any], task_name: str | None = None) -> bool:
        """Register task with limit enforcement (sync version for create_task).

        Args:
            task: Task to register
            task_name: Optional name for debugging

        Returns:
            True if registered, False if limit exceeded
        """
        # Clean up completed tasks (weakref handles most, but be explicit)
        completed_count = 0
        for t in list(self.tasks):
            if t.done():
                self.tasks.discard(t)
                completed_count += 1

        if completed_count > 0:
            self.total_completed += completed_count

        # Check limit
        active_count = len(self.tasks)
        if active_count >= self.max_tasks:
            self.total_rejected += 1
            logger.error(
                f"🚨 TASK LIMIT EXCEEDED: {active_count}/{self.max_tasks} active tasks. "
                f"REFUSING to create task '{task_name or task.get_name()}' to prevent memory exhaustion. "
                f"(Total created: {self.total_created}, rejected: {self.total_rejected})"
            )

            # Emit metric

            return False

        # Register task
        self.tasks.add(task)
        self.total_created += 1

        # Log warning if approaching limit
        if active_count > self.max_tasks * 0.9:
            logger.warning(
                f"⚠️  Task count high: {active_count}/{self.max_tasks} ({active_count * 100 // self.max_tasks}%)"
            )

        return True

    async def cleanup_all(self) -> dict[str, int]:
        """Cancel all registered tasks (for shutdown).

        Returns:
            Statistics about cleanup
        """
        async with self._lock:
            tasks = list(self.tasks)
            cancelled_count = 0

            for task in tasks:
                if not task.done():
                    task.cancel()
                    cancelled_count += 1

            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(
                f"🧹 Task registry cleanup: {cancelled_count} cancelled, {len(tasks)} total"
            )

            return {
                "total_tasks": len(tasks),
                "cancelled": cancelled_count,
                "already_done": len(tasks) - cancelled_count,
            }

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        active_count = len(self.tasks)
        return {
            "active_tasks": active_count,
            "max_tasks": self.max_tasks,
            "utilization": active_count / self.max_tasks if self.max_tasks > 0 else 0.0,
            "total_created": self.total_created,
            "total_rejected": self.total_rejected,
            "total_completed": self.total_completed,
        }


# Global singleton
_registry: TaskRegistry | None = None


def get_task_registry() -> TaskRegistry:
    """Get global task registry singleton."""
    global _registry
    if _registry is None:
        # Default 5,000 tasks (conservative)
        # Can be overridden via env var
        import os

        max_tasks = int(os.getenv("KAGAMI_MAX_TASKS", "5000"))
        _registry = TaskRegistry(max_tasks=max_tasks)
    return _registry


def reset_task_registry() -> None:
    """Reset global registry (for testing only)."""
    global _registry
    _registry = None


__all__ = [
    "TaskRegistry",
    "get_task_registry",
    "reset_task_registry",
]
