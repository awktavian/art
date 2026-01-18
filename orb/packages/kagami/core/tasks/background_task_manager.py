"""Background task manager for in-process async tasks.

PURPOSE: Complements Celery (not redundant)
- Celery: Distributed scheduled tasks via Redis broker
- BackgroundTaskManager: In-process async tasks with receipts

This module provides:
- Receipt tracking (PLAN/EXECUTE/VERIFY audit trail)
- Retry logic with exponential backoff
- Task monitoring and health checks
- Consensus-aware leader election

Use BackgroundTaskManager for:
- In-process async operations that need receipts
- Tasks requiring immediate execution (not scheduled)
- Operations that should emit audit trails

Use Celery for:
- Scheduled/periodic tasks (beat_schedule)
- Distributed processing across workers
- Long-running background jobs
"""

import asyncio
import logging
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from kagami.core.async_utils import safe_create_task
from kagami.core.receipts import UnifiedReceiptFacade as URF

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Background task status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """Background task metadata."""

    name: str
    task: asyncio.Task
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    result: Any | None = None
    correlation_id: str | None = None


class BackgroundTaskManager:
    """Manages background tasks with proper error handling and monitoring."""

    def __init__(self) -> None:
        """Initialize the background task manager."""
        self._tasks: dict[str, BackgroundTask] = {}
        self._task_lock = asyncio.Lock()
        self._running = True
        self._monitor_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the task manager and monitoring with consensus check."""
        # Check consensus for background task management
        try:
            from kagami.core.coordination.kagami_consensus import get_consensus_protocol

            consensus = get_consensus_protocol()
            if consensus:
                state = consensus.current_state  # type: ignore[attr-defined]
                if state.converged and state.leader_id != consensus.instance_id:  # type: ignore[attr-defined]
                    logger.info(
                        "⏭️  Not leader for background tasks - another instance is managing them"
                    )
                    return
                logger.info("🎖️  Acting as leader for background task management")

        except Exception as e:
            logger.warning(f"Consensus unavailable: {e} - assuming single instance")

        self._running = True
        self._monitor_task = safe_create_task(self._monitor_tasks(), name="_monitor_tasks")
        logger.info("Background task manager started")

    async def stop(self) -> None:
        """Stop the task manager gracefully."""
        self._running = False

        # Cancel all running tasks
        async with self._task_lock:
            for task_name, task_info in self._tasks.items():
                if task_info.status == TaskStatus.RUNNING:
                    task_info.task.cancel()
                    logger.info(f"Cancelling task: {task_name}")

        # Wait for monitor to stop
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Wait for all tasks to complete
        tasks = []
        async with self._task_lock:
            for task_info in self._tasks.values():
                if not task_info.task.done():
                    tasks.append(task_info.task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Background task manager stopped")

    async def create_task(
        self,
        name: str,
        coro: Coroutine,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        correlation_id: str | None = None,
    ) -> str:
        """Create and manage a background task.

        Args:
            name: Unique task name
            coro: Coroutine to execute
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries (exponential backoff)
            correlation_id: Optional tracking ID for receipts

        Returns:
            Task name for tracking
        """
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = URF.generate_correlation_id(name)

        # Emit PLAN receipt
        URF.emit(
            correlation_id=correlation_id,
            action="background_task.plan",
            event_name="PLAN",
            app="background_task_manager",
            event_data={
                "task_name": name,
                "max_retries": max_retries,
                "retry_delay": retry_delay,
            },
        )

        # Wrap coroutine with error handling
        wrapped_coro = self._wrap_task(name, coro, max_retries, retry_delay, correlation_id)

        # Create the task
        task = safe_create_task(wrapped_coro, name=f"background_task_{name}")

        # Store task info
        async with self._task_lock:
            self._tasks[name] = BackgroundTask(
                name=name,
                task=task,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow(),
                max_retries=max_retries,
                correlation_id=correlation_id,
            )

        logger.info(f"Created background task: {name} (correlation_id={correlation_id})")
        return name

    async def _wrap_task(
        self,
        name: str,
        coro: Coroutine,
        max_retries: int,
        retry_delay: float,
        correlation_id: str,
    ) -> None:
        """Wrap a task with error handling and retry logic."""
        async with self._task_lock:
            if name in self._tasks:
                self._tasks[name].status = TaskStatus.RUNNING
                self._tasks[name].started_at = datetime.utcnow()

        # Emit EXECUTE receipt
        URF.emit(
            correlation_id=correlation_id,
            action="background_task.execute",
            event_name="EXECUTE",
            app="background_task_manager",
            event_data={"task_name": name},
        )

        retry_count = 0
        last_error = None
        start_wall = time.time()

        while retry_count <= max_retries:
            try:
                # Execute the task
                result = await coro

                # Mark as completed
                async with self._task_lock:
                    if name in self._tasks:
                        self._tasks[name].status = TaskStatus.COMPLETED
                        self._tasks[name].completed_at = datetime.utcnow()
                        self._tasks[name].result = result

                logger.info(f"Task {name} completed successfully")

                # Emit VERIFY receipt (Success)
                URF.emit(
                    correlation_id=correlation_id,
                    action="background_task.verify",
                    event_name="VERIFY",
                    app="background_task_manager",
                    status="success",
                    event_data={
                        "task_name": name,
                        "result": str(result)[:200],  # Truncate result in receipt
                        "duration_ms": int((time.time() - start_wall) * 1000),
                    },
                )

                # Observe duration metric (best-effort)
                try:
                    from kagami_observability.metrics import TASK_DURATION

                    TASK_DURATION.labels(name, "success").observe(
                        max(0.0, time.time() - start_wall)
                    )
                except Exception:
                    pass
                return result  # type: ignore[no-any-return]

            except asyncio.CancelledError:
                # Task was cancelled
                async with self._task_lock:
                    if name in self._tasks:
                        self._tasks[name].status = TaskStatus.CANCELLED
                        self._tasks[name].completed_at = datetime.utcnow()

                logger.info(f"Task {name} was cancelled")

                # Emit VERIFY receipt (Cancelled)
                URF.emit(
                    correlation_id=correlation_id,
                    action="background_task.verify",
                    event_name="VERIFY",
                    app="background_task_manager",
                    status="cancelled",
                    event_data={
                        "task_name": name,
                        "reason": "cancelled",
                        "duration_ms": int((time.time() - start_wall) * 1000),
                    },
                )
                raise

            except Exception as e:
                last_error = str(e)
                logger.error(f"Task {name} failed (attempt {retry_count + 1}): {e}")

                # Update retry count
                async with self._task_lock:
                    if name in self._tasks:
                        self._tasks[name].retry_count = retry_count
                        self._tasks[name].error = last_error

                if retry_count < max_retries:
                    # Exponential backoff
                    delay = retry_delay * (2**retry_count)
                    logger.info(f"Retrying task {name} in {delay} seconds...")
                    try:
                        from kagami_observability.metrics import TASK_RETRIES

                        TASK_RETRIES.labels(name).inc()
                    except Exception:
                        pass
                    await asyncio.sleep(delay)
                    retry_count += 1
                else:
                    # Max retries exceeded
                    break

        # Mark as failed
        async with self._task_lock:
            if name in self._tasks:
                self._tasks[name].status = TaskStatus.FAILED
                self._tasks[name].completed_at = datetime.utcnow()
                self._tasks[name].error = last_error

        logger.error(f"Task {name} failed after {max_retries + 1} attempts")

        # Emit VERIFY receipt (Failed)
        URF.emit(
            correlation_id=correlation_id,
            action="background_task.verify",
            event_name="VERIFY",
            app="background_task_manager",
            status="failed",
            event_data={
                "task_name": name,
                "error": last_error,
                "attempts": retry_count + 1,
                "duration_ms": int((time.time() - start_wall) * 1000),
            },
        )

        try:
            from kagami_observability.metrics import TASK_DURATION

            TASK_DURATION.labels(name, "failure").observe(max(0.0, time.time() - start_wall))
        except Exception:
            pass
        raise Exception(f"Task {name} failed: {last_error}") from None

    async def _monitor_tasks(self) -> None:
        """Monitor task health and clean up completed tasks."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Check task health
                async with self._task_lock:
                    unhealthy_tasks = []
                    completed_tasks = []

                    for name, task_info in self._tasks.items():
                        if task_info.status == TaskStatus.RUNNING:
                            if task_info.task.done():
                                # Task completed but status not updated
                                if task_info.task.exception():
                                    task_info.status = TaskStatus.FAILED
                                    task_info.error = str(task_info.task.exception())
                                    unhealthy_tasks.append(name)
                                else:
                                    task_info.status = TaskStatus.COMPLETED
                                task_info.completed_at = datetime.utcnow()

                        # Clean up old completed tasks
                        if task_info.status in [
                            TaskStatus.COMPLETED,
                            TaskStatus.CANCELLED,
                        ]:
                            if task_info.completed_at:
                                age = (datetime.utcnow() - task_info.completed_at).total_seconds()
                                if age > 3600:  # 1 hour old
                                    completed_tasks.append(name)

                    # Remove old tasks
                    for name in completed_tasks:
                        del self._tasks[name]
                        logger.debug(f"Cleaned up completed task: {name}")

                    # Log unhealthy tasks
                    for name in unhealthy_tasks:
                        logger.error(f"Unhealthy task detected: {name}")

                    # Emit gauge metrics (best-effort)
                    try:
                        from kagami_observability.metrics import (
                            BACKGROUND_TASKS_RUNNING,
                        )

                        running_cnt = sum(
                            1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING
                        )
                        sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
                        BACKGROUND_TASKS_RUNNING.set(running_cnt)
                        # BACKGROUND_TASKS_FAILED is a Counter, incremented elsewhere
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task monitor: {e}")

    async def get_task_status(self, name: str) -> dict[str, Any] | None:
        """Get the status of a task."""
        async with self._task_lock:
            if name not in self._tasks:
                return None

            task_info = self._tasks[name]
            return {
                "name": task_info.name,
                "status": task_info.status.value,
                "created_at": task_info.created_at.isoformat(),
                "started_at": (task_info.started_at.isoformat() if task_info.started_at else None),
                "completed_at": (
                    task_info.completed_at.isoformat() if task_info.completed_at else None
                ),
                "error": task_info.error,
                "retry_count": task_info.retry_count,
                "max_retries": task_info.max_retries,
                "correlation_id": task_info.correlation_id,
            }

    async def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get status of all tasks."""
        tasks = []
        async with self._task_lock:
            for name in self._tasks:
                status = await self.get_task_status(name)
                if status:
                    tasks.append(status)
        return tasks

    async def cancel_task(self, name: str) -> bool:
        """Cancel a running task."""
        async with self._task_lock:
            if name not in self._tasks:
                return False

            task_info = self._tasks[name]
            if task_info.status == TaskStatus.RUNNING:
                task_info.task.cancel()
                logger.info(f"Cancelled task: {name}")
                return True

            return False

    async def wait_for_task(self, name: str, timeout: float | None = None) -> Any:
        """Wait for a task to complete."""
        async with self._task_lock:
            if name not in self._tasks:
                raise ValueError(f"Task {name} not found")
            task_info = self._tasks[name]

        # If the task belongs to a different loop, avoid awaiting the Task directly
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None  # Not in an event loop

        task_loop = None
        try:
            task_loop = task_info.task.get_loop()
        except Exception:
            pass

        if current_loop is not None and task_loop is not None and current_loop is task_loop:
            # Same loop, safe to await directly
            try:
                return await asyncio.wait_for(task_info.task, timeout=timeout)
            except TimeoutError:
                logger.warning(f"Timeout waiting for task: {name}")
                raise
        else:
            # Different or unknown loop: poll status and return stored result
            loop = asyncio.get_running_loop()
            deadline = None if timeout is None else (loop.time() + float(timeout))
            while True:
                async with self._task_lock:
                    status = task_info.status
                    result = task_info.result
                    error = task_info.error
                if status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                ):
                    if status == TaskStatus.COMPLETED:
                        return result
                    # Mirror await semantics: raise on failure/cancel
                    raise Exception(
                        error or f"Task {name} did not complete successfully: {status.value}"
                    )
                # Not done yet; check timeout and sleep briefly
                now = loop.time()
                if deadline is not None and now >= deadline:
                    logger.warning(f"Timeout waiting for task (polled): {name}")
                    raise TimeoutError()
                await asyncio.sleep(0.05)

    async def health_check(self) -> dict[str, Any]:
        """Check health of all background tasks."""
        async with self._task_lock:
            total_tasks = len(self._tasks)
            running_tasks = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
            failed_tasks = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
            completed_tasks = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED
            )

        return {
            "healthy": failed_tasks == 0,
            "total_tasks": total_tasks,
            "running_tasks": running_tasks,
            "failed_tasks": failed_tasks,
            "completed_tasks": completed_tasks,
            "monitor_running": self._monitor_task and not self._monitor_task.done(),
        }


# Singleton via centralized registry
from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_task_manager = _singleton_registry.register_sync(
    "background_task_manager", BackgroundTaskManager
)
