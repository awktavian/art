from kagami.core.async_utils import safe_create_task

"""Queue manager for handling concurrent requests in Forge."""

import asyncio
import heapq
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any

logger = logging.getLogger(__name__)


class QueuePriority(Enum):
    """Priority levels for request queue."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class RequestStatus(Enum):
    """Status of a queued request."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class QueuedRequest:
    """Represents a queued request."""

    request_id: str
    func: Callable
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    priority: QueuePriority
    timestamp: float
    timeout: float | None = None
    status: RequestStatus = RequestStatus.PENDING
    result: Any = None
    error: Exception | None = None
    started_at: float | None = None
    completed_at: float | None = None

    def __lt__(self, other: Any) -> None:
        """Compare requests by priority (higher priority first) then timestamp (older first)."""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value  # type: ignore[no-any-return]
        return self.timestamp < other.timestamp  # type: ignore[no-any-return]


class RequestQueue:
    """Priority queue for managing concurrent requests."""

    def __init__(
        self,
        max_concurrent: int = 10,
        max_queue_size: int = 1000,
        worker_count: int = 5,
    ) -> None:
        """Initialize request queue.

        Args:
            max_concurrent: Maximum concurrent requests
            max_queue_size: Maximum queue size
            worker_count: Number of worker tasks
        """
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.worker_count = worker_count

        # Priority queue for pending requests
        self._pending_queue: list[QueuedRequest] = []
        self._queue_lock = asyncio.Lock()

        # Active requests
        self._active_requests: dict[str, QueuedRequest] = {}
        self._active_lock = asyncio.Lock()

        # All requests tracking
        self.requests: dict[str, QueuedRequest] = {}

        # Worker management
        self.workers: list[asyncio.Task] = []
        self.running = False
        self._stop_event = asyncio.Event()

        # Statistics
        self._total_processed = 0
        self._total_errors = 0
        self._total_timeouts = 0
        # Retention controls for completed/failed requests (seconds)
        self._retention_seconds: float = 600.0

    async def start(self) -> None:
        """Start the request queue workers."""
        if self.running:
            return

        self.running = True
        self._stop_event.clear()

        # Start worker tasks
        for i in range(self.worker_count):
            worker = safe_create_task(self._worker(f"worker-{i}"), name=f"forge-queue-worker-{i}")
            self.workers.append(worker)

    async def stop(self) -> None:
        """Stop the request queue workers."""
        if not self.running:
            return

        self.running = False
        self._stop_event.set()

        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers = []

    async def submit(
        self,
        func: Callable,
        *args: Any,
        priority: QueuePriority = QueuePriority.NORMAL,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> str:
        """Submit a request to the queue.

        Args:
            func: Function to execute
            args: Positional arguments
            priority: Request priority
            timeout: Timeout in seconds
            kwargs: Keyword arguments

        Returns:
            Request ID
        """
        request_id = str(uuid.uuid4())

        request = QueuedRequest(
            request_id=request_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timestamp=time.time(),
            timeout=timeout,
        )

        # Add to tracking
        self.requests[request_id] = request

        # Opportunistic GC of old completed requests
        try:
            self._purge_old_requests()
        except Exception:
            logger.debug("Failed to purge old requests during enqueue", exc_info=True)
        # Add to queue
        async with self._queue_lock:
            if len(self._pending_queue) >= self.max_queue_size:
                request.status = RequestStatus.FAILED
                request.error = Exception("Queue is full")
                request.completed_at = time.time()
                raise RuntimeError("Queue is full") from None

            heapq.heappush(self._pending_queue, request)  # type: ignore[type-var]

        return request_id

    async def _worker(self, worker_name: str) -> None:
        """Worker task to process requests."""
        while not self._stop_event.is_set():
            try:
                # Check if we can process more requests
                async with self._active_lock:
                    if len(self._active_requests) >= self.max_concurrent:
                        await asyncio.sleep(0.1)
                        continue

                # Get next request from queue
                request = None
                async with self._queue_lock:
                    if self._pending_queue:
                        request = heapq.heappop(self._pending_queue)  # type: ignore[type-var]

                if request is None:
                    await asyncio.sleep(0.1)
                    continue

                # Process the request
                await self._process_request(request)

            except Exception as e:
                # Log worker error but continue
                import logging

                logging.getLogger(__name__).error("Worker %s error: %s", worker_name, e)
                await asyncio.sleep(0.1)

    async def _process_request(self, request: QueuedRequest) -> None:
        """Process a single request."""
        # Update status
        request.status = RequestStatus.RUNNING
        request.started_at = time.time()

        # Add to active requests
        async with self._active_lock:
            self._active_requests[request.request_id] = request

        try:
            # Execute with timeout if specified
            if request.timeout:
                request.result = await asyncio.wait_for(
                    self._execute_request(request), timeout=request.timeout
                )
            else:
                request.result = await self._execute_request(request)

            request.status = RequestStatus.COMPLETED
            self._total_processed += 1

        except TimeoutError:
            request.status = RequestStatus.TIMEOUT
            request.error = TimeoutError(f"Request timed out after {request.timeout}s")
            self._total_timeouts += 1

        except Exception as e:
            request.status = RequestStatus.FAILED
            request.error = e
            self._total_errors += 1

        finally:
            request.completed_at = time.time()

            # Remove from active requests
            async with self._active_lock:
                self._active_requests.pop(request.request_id, None)

    async def _execute_request(self, request: QueuedRequest) -> Any:
        """Execute the request function."""
        if asyncio.iscoroutinefunction(request.func):
            return await request.func(*request.args, **request.kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_running_loop()
            bound = partial(request.func, *request.args, **request.kwargs)
            return await loop.run_in_executor(None, bound)

    async def get_result(
        self, request_id: str, wait: bool = False, timeout: float | None = None
    ) -> tuple[bool, Any]:
        """Get the result of a request.

        Args:
            request_id: Request ID
            wait: Wait for completion
            timeout: Wait timeout

        Returns:
            Tuple of (success, result/error)
        """
        # Opportunistic GC
        try:
            self._purge_old_requests()
        except Exception:
            logger.debug("Failed to purge old requests during result fetch", exc_info=True)
        request = self.requests.get(request_id)
        if request is None:
            return False, "Request not found"

        if wait and request.status in [RequestStatus.PENDING, RequestStatus.RUNNING]:
            # Wait for completion
            start_time = time.time()
            while request.status in [RequestStatus.PENDING, RequestStatus.RUNNING]:
                if timeout and (time.time() - start_time) > timeout:
                    return False, "Wait timeout"
                await asyncio.sleep(0.1)

        if request.status == RequestStatus.COMPLETED:
            return True, request.result
        elif request.status in [RequestStatus.FAILED, RequestStatus.TIMEOUT]:
            return False, request.error
        elif request.status == RequestStatus.CANCELLED:
            return False, "Request was cancelled"
        else:
            return False, f"Request is {request.status.value}"

    def _purge_old_requests(self) -> None:
        """Purge completed/failed/timeout requests older than retention window."""
        now = time.time()
        to_delete: list[str] = []
        for rid, req in list(self.requests.items()):
            try:
                if (
                    req.completed_at is not None
                    and (now - float(req.completed_at)) > self._retention_seconds
                    and req.status
                    in (
                        RequestStatus.COMPLETED,
                        RequestStatus.FAILED,
                        RequestStatus.TIMEOUT,
                        RequestStatus.CANCELLED,
                    )
                ):
                    to_delete.append(rid)
            except Exception:
                logger.debug("Failed to check request %s for deletion", rid, exc_info=True)
                continue
        for rid in to_delete:
            try:
                self.requests.pop(rid, None)
            except Exception:
                logger.debug("Failed to delete request %s", rid, exc_info=True)

    async def get_status(self, request_id: str) -> dict[str, Any]:
        """Get the status of a request."""
        request = self.requests.get(request_id)
        if request is None:
            return {"status": "not_found"}

        return {
            "status": request.status.value,
            "priority": request.priority.name,
            "created_at": request.timestamp,
            "started_at": request.started_at,
            "completed_at": request.completed_at,
            "has_result": request.status == RequestStatus.COMPLETED,
            "has_error": request.error is not None,
        }


# Global queue instance
_global_queue: RequestQueue | None = None


__all__ = [
    "QueuePriority",
    "QueuedRequest",
    "RequestQueue",
    "RequestStatus",
]
