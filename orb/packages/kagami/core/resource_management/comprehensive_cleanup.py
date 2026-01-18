"""Comprehensive resource cleanup and management framework.

This module provides production-ready resource management with automatic cleanup,
leak detection, lifecycle tracking, and graceful shutdown patterns.

Architecture:
    Resource → Tracker → Manager → Priority Cleanup → Shutdown

Key Components:
    - ResourceManager: Central registry for all managed resources
    - ResourceTracker: Wraps individual resources with lifecycle metadata
    - LeakDetector: Background monitoring for potential memory leaks
    - CleanupPriority: Ordering for graceful shutdown (CRITICAL → LOW)

Cleanup Order (during shutdown):
    1. CRITICAL (locks, file handles) - Must cleanup
    2. HIGH (connections) - Important to cleanup
    3. MEDIUM (caches) - Good to cleanup
    4. LOW (temp data) - Nice to cleanup

Usage:
    # Basic registration
    manager = get_resource_manager()
    manager.register_resource(my_connection, "db_conn", priority=CleanupPriority.HIGH)

    # Decorator (auto-register instances)
    @managed_resource("connection", priority=CleanupPriority.HIGH)
    class DatabaseConnection:
        def close(self): ...

    # Context manager (auto-cleanup on exit)
    with resource_context(connection, "conn") as conn:
        conn.execute(...)

    # Async context manager
    async with async_resource_context(connection, "conn") as conn:
        await conn.execute(...)

    # Leak detection
    enable_leak_detection(check_interval=60.0)

Signal Handling:
    - SIGTERM/SIGINT: Graceful shutdown with priority-ordered cleanup
    - atexit: Emergency cleanup with 5s timeout
"""

from __future__ import annotations

import asyncio
import atexit
import gc
import signal
import sys
import threading
import time
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypeVar

from kagami.core.logging.comprehensive_logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ResourceState(Enum):
    """Resource lifecycle states.

    State Transitions:
        INITIALIZING → ACTIVE → CLEANUP_PENDING → CLEANED_UP
                           ↓                         ↑
                         ERROR ──────────────────────┘

    States:
        INITIALIZING: Resource is being set up (brief transitional state)
        ACTIVE: Resource is ready for use and being tracked
        CLEANUP_PENDING: Cleanup has started but not yet completed
        CLEANED_UP: Resource has been successfully cleaned up
        ERROR: Cleanup failed; resource may be in inconsistent state
    """

    INITIALIZING = "initializing"  # Resource being set up
    ACTIVE = "active"  # Ready for use, being tracked
    CLEANUP_PENDING = "cleanup_pending"  # Cleanup in progress
    CLEANED_UP = "cleaned_up"  # Successfully cleaned up
    ERROR = "error"  # Cleanup failed


class CleanupPriority(Enum):
    """Cleanup priority levels — determines order during shutdown.

    During graceful shutdown, resources are cleaned up in priority order:
    CRITICAL (0) first, then HIGH (1), MEDIUM (2), finally LOW (3).

    Guidelines:
        CRITICAL: Locks, file handles, anything that blocks other processes
        HIGH: Network connections, database connections, external services
        MEDIUM: Caches, buffers, pooled resources
        LOW: Temporary data, metrics, non-essential state

    Example:
        # File handles block other processes → CRITICAL
        manager.register_resource(file_handle, "log", priority=CleanupPriority.CRITICAL)

        # Database connections are valuable → HIGH
        manager.register_resource(db_conn, "postgres", priority=CleanupPriority.HIGH)

        # Cache can be rebuilt → MEDIUM
        manager.register_resource(cache, "lru_cache", priority=CleanupPriority.MEDIUM)
    """

    CRITICAL = 0  # Must cleanup: locks, file handles, blocking resources
    HIGH = 1  # Important: connections, external services, I/O
    MEDIUM = 2  # Good to cleanup: caches, buffers, pools
    LOW = 3  # Nice to cleanup: temp data, metrics, diagnostics


@dataclass
class ResourceMetrics:
    """Metrics for resource usage tracking.

    Tracks lifecycle timestamps and usage patterns for each resource.
    Used by ResourceManager to make cleanup decisions (e.g., idle resources).

    Attributes:
        creation_time: Unix timestamp when resource was registered
        last_access_time: Unix timestamp of most recent access
        access_count: Number of times mark_accessed() was called
        memory_usage: Optional memory footprint in bytes (if tracked)
        cleanup_time: Unix timestamp when cleanup completed (None if active)
        cleanup_duration: Time spent in cleanup (seconds, None if active)

    Example:
        metrics = ResourceMetrics()
        metrics.access_count += 1
        metrics.last_access_time = time.time()
        idle_seconds = time.time() - metrics.last_access_time
    """

    creation_time: float = field(default_factory=time.time)  # When registered
    last_access_time: float = field(default_factory=time.time)  # Last use
    access_count: int = 0  # Total accesses
    memory_usage: int | None = None  # Optional: bytes used
    cleanup_time: float | None = None  # When cleanup finished
    cleanup_duration: float | None = None  # How long cleanup took


class ResourceProtocol(Protocol):
    """Protocol for resources that can be cleaned up synchronously.

    Resources implementing this protocol will have their cleanup() method
    called automatically during ResourceManager shutdown.

    Also detected: close(), dispose(), destroy(), shutdown() methods,
    and __exit__() context manager protocol.

    Example:
        class FileResource:
            def cleanup(self) -> None:
                self.file.close()
    """

    def cleanup(self) -> None:
        """Cleanup the resource synchronously."""
        ...


class AsyncResourceProtocol(Protocol):
    """Protocol for resources that can be cleaned up asynchronously.

    Resources implementing this protocol will have their async cleanup()
    method called during ResourceManager shutdown.

    Also detected: async close(), async dispose(), async destroy(),
    async shutdown() methods, and __aexit__() async context manager protocol.

    Example:
        class AsyncConnection:
            async def cleanup(self) -> None:
                await self.connection.close()
    """

    async def cleanup(self) -> None:
        """Cleanup the resource asynchronously."""
        ...


@dataclass
class ResourceTracker:
    """Tracks a single resource for cleanup.

    Wraps a resource with metadata needed for lifecycle management:
    cleanup functions, priority, state, and usage metrics.

    Attributes:
        resource: The actual resource object being tracked
        cleanup_func: Optional sync cleanup function (auto-detected if None)
        async_cleanup_func: Optional async cleanup function (auto-detected if None)
        priority: Cleanup order during shutdown (CRITICAL cleaned first)
        name: Unique identifier for this resource
        state: Current lifecycle state (ACTIVE, CLEANUP_PENDING, etc.)
        metrics: Usage and timing information

    Note:
        ResourceManager auto-detects cleanup methods if not provided.
        Checks for: cleanup(), close(), dispose(), destroy(), shutdown(),
        __exit__(), and __aexit__() methods.
    """

    resource: Any  # The actual resource object
    cleanup_func: Callable[[], None] | None  # Sync cleanup (auto-detected)
    async_cleanup_func: Callable[[], Any] | None  # Async cleanup (auto-detected)
    priority: CleanupPriority  # Shutdown order (lower = earlier)
    name: str  # Unique identifier
    state: ResourceState = ResourceState.ACTIVE  # Lifecycle state
    metrics: ResourceMetrics = field(default_factory=ResourceMetrics)  # Usage stats

    def mark_accessed(self) -> None:
        """Mark resource as recently accessed (updates metrics).

        Call this when the resource is used to prevent it from being
        cleaned up as "unused" by cleanup_unused_resources().
        """
        self.metrics.last_access_time = time.time()
        self.metrics.access_count += 1


class ResourceManager:
    """Central resource manager for tracking and cleanup.

    The ResourceManager maintains a registry of all resources that need
    cleanup, handles graceful shutdown with priority ordering, and
    provides utilities for detecting unused/leaked resources.

    Thread Safety:
        All operations are protected by an RLock. Safe for concurrent use.

    Signal Handling:
        Automatically registers SIGTERM/SIGINT handlers for graceful shutdown.
        Also registers atexit handler for emergency cleanup.

    Example:
        manager = ResourceManager("my_app")

        # Register resources
        manager.register_resource(db_conn, "database", priority=CleanupPriority.HIGH)
        manager.register_resource(cache, "cache", priority=CleanupPriority.LOW)

        # Track usage
        manager.mark_resource_accessed("database")

        # Cleanup unused resources (idle > 5 minutes)
        manager.cleanup_unused_resources(max_idle_time=300.0)

        # Graceful shutdown (cleans up in priority order)
        manager.shutdown(timeout=30.0)

    Attributes:
        name: Identifier for this manager (for logging)
    """

    def __init__(self, name: str = "default"):
        """Initialize a new ResourceManager.

        Args:
            name: Identifier for this manager (appears in logs)
        """
        self.name = name
        self._resources: dict[str, ResourceTracker] = {}  # name → tracker
        self._lock = threading.RLock()  # Thread-safe operations
        self._shutdown_in_progress = False  # Block new registrations during shutdown
        self._cleanup_tasks: set[asyncio.Task] = set()  # Pending async cleanups

        # Register shutdown handlers for graceful cleanup
        atexit.register(self._emergency_cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def register_resource(
        self,
        resource: Any,
        name: str,
        cleanup_func: Callable[[], None] | None = None,
        async_cleanup_func: Callable[[], Any] | None = None,
        priority: CleanupPriority = CleanupPriority.MEDIUM,
        auto_detect_cleanup: bool = True,
    ) -> str:
        """Register a resource for managed cleanup.

        Args:
            resource: The resource object to track
            name: Identifier (auto-suffixed if collision)
            cleanup_func: Optional sync cleanup function
            async_cleanup_func: Optional async cleanup function
            priority: Cleanup order during shutdown (default: MEDIUM)
            auto_detect_cleanup: If True, auto-detect cleanup/close methods

        Returns:
            The actual name used (may have suffix if collision)

        Note:
            Registration is blocked during shutdown.
            If both cleanup functions are None and auto_detect_cleanup is True,
            the manager searches for: cleanup(), close(), dispose(), destroy(),
            shutdown(), __exit__(), __aexit__() methods.
        """

        with self._lock:
            if self._shutdown_in_progress:
                logger.warning(f"Cannot register resource '{name}' during shutdown")
                return name

            # Auto-detect cleanup methods if not provided
            if auto_detect_cleanup and cleanup_func is None and async_cleanup_func is None:
                cleanup_func, async_cleanup_func = self._detect_cleanup_methods(resource)

            # Generate unique name if collision
            original_name = name
            counter = 1
            while name in self._resources:
                name = f"{original_name}_{counter}"
                counter += 1

            tracker = ResourceTracker(
                resource=resource,
                cleanup_func=cleanup_func,
                async_cleanup_func=async_cleanup_func,
                priority=priority,
                name=name,
            )

            self._resources[name] = tracker

            logger.debug(
                f"Registered resource '{name}' with priority {priority.name}",
                extra={
                    "resource_type": type(resource).__name__,
                    "has_sync_cleanup": cleanup_func is not None,
                    "has_async_cleanup": async_cleanup_func is not None,
                },
            )

            return name

    def _detect_cleanup_methods(self, resource: Any) -> tuple[Callable | None, Callable | None]:
        """Auto-detect cleanup methods on the resource.

        Searches for common cleanup method names and context manager protocols.
        Checks (in order): cleanup, close, dispose, destroy, shutdown.
        Also checks __exit__ and __aexit__ for context manager support.

        Returns:
            Tuple of (sync_cleanup, async_cleanup) — one or both may be None.
        """
        sync_cleanup = None
        async_cleanup = None

        # Check for common cleanup method names
        cleanup_method_names = ["cleanup", "close", "dispose", "destroy", "shutdown"]

        for method_name in cleanup_method_names:
            if hasattr(resource, method_name):
                method = getattr(resource, method_name)
                if callable(method):
                    if asyncio.iscoroutinefunction(method):
                        async_cleanup = method
                    else:
                        sync_cleanup = method
                    break

        # Check for context manager protocol
        if hasattr(resource, "__exit__") and sync_cleanup is None:

            def sync_cleanup():
                return resource.__exit__(None, None, None)

        if hasattr(resource, "__aexit__") and async_cleanup is None:

            async def _async_exit():
                await resource.__aexit__(None, None, None)

            async_cleanup = _async_exit

        return sync_cleanup, async_cleanup

    def unregister_resource(self, name: str, perform_cleanup: bool = True) -> bool:
        """Unregister a resource, optionally cleaning it up.

        Args:
            name: The resource identifier
            perform_cleanup: If True, run cleanup before removing (default: True)

        Returns:
            True if resource was found and removed, False if not found.

        Note:
            Cleanup errors are logged but do not prevent unregistration.
        """

        with self._lock:
            if name not in self._resources:
                return False

            tracker = self._resources[name]

            if perform_cleanup:
                try:
                    self._cleanup_resource(tracker)
                except Exception as e:
                    logger.error(
                        f"Error cleaning up resource '{name}' during unregistration",
                        extra={"exception_type": type(e).__name__},
                        exc_info=e,
                    )

            del self._resources[name]
            logger.debug(f"Unregistered resource '{name}'")
            return True

    def mark_resource_accessed(self, name: str) -> None:
        """Mark a resource as recently accessed.

        Updates last_access_time and increments access_count in metrics.
        Call this to prevent cleanup_unused_resources() from cleaning it up.

        Args:
            name: The resource identifier
        """
        with self._lock:
            if name in self._resources:
                self._resources[name].mark_accessed()

    def get_resource_info(self, name: str) -> dict[str, Any] | None:
        """Get information about a registered resource.

        Args:
            name: The resource identifier

        Returns:
            Dict with name, state, priority, resource_type, creation_time,
            last_access_time, access_count, memory_usage. None if not found.
        """
        with self._lock:
            if name not in self._resources:
                return None

            tracker = self._resources[name]
            return {
                "name": tracker.name,
                "state": tracker.state.value,
                "priority": tracker.priority.value,
                "resource_type": type(tracker.resource).__name__,
                "creation_time": tracker.metrics.creation_time,
                "last_access_time": tracker.metrics.last_access_time,
                "access_count": tracker.metrics.access_count,
                "memory_usage": tracker.metrics.memory_usage,
            }

    def list_resources(self, state_filter: ResourceState | None = None) -> list[dict[str, Any]]:
        """List all registered resources, optionally filtered by state.

        Args:
            state_filter: If provided, only return resources in this state

        Returns:
            List of resource info dicts (same format as get_resource_info)
        """
        with self._lock:
            resources = []
            for tracker in self._resources.values():
                if state_filter is None or tracker.state == state_filter:
                    info = self.get_resource_info(tracker.name)
                    if info:
                        resources.append(info)
            return resources

    def cleanup_by_priority(self, priority: CleanupPriority) -> int:
        """Cleanup all resources of a specific priority level.

        Only cleans up resources that are currently ACTIVE.
        Errors are logged but do not stop other cleanups.

        Args:
            priority: The priority level to clean up

        Returns:
            Number of resources successfully cleaned up
        """
        cleaned_count = 0

        with self._lock:
            resources_to_clean = [
                tracker
                for tracker in self._resources.values()
                if tracker.priority == priority and tracker.state == ResourceState.ACTIVE
            ]

        for tracker in resources_to_clean:
            try:
                self._cleanup_resource(tracker)
                cleaned_count += 1
            except Exception as e:
                logger.error(
                    f"Error cleaning up resource '{tracker.name}'",
                    extra={"priority": priority.name},
                    exc_info=e,
                )

        logger.info(f"Cleaned up {cleaned_count} resources with priority {priority.name}")
        return cleaned_count

    def cleanup_unused_resources(self, max_idle_time: float = 300.0) -> int:
        """Cleanup resources that haven't been accessed recently.

        Identifies ACTIVE resources where (now - last_access_time) > max_idle_time
        and cleans them up. Useful for periodic maintenance.

        Args:
            max_idle_time: Seconds of inactivity before cleanup (default: 300 = 5 min)

        Returns:
            Number of resources cleaned up

        Note:
            Call mark_resource_accessed() to prevent a resource from being cleaned.
        """
        current_time = time.time()
        cleaned_count = 0

        with self._lock:
            unused_resources = [
                tracker
                for tracker in self._resources.values()
                if (
                    current_time - tracker.metrics.last_access_time > max_idle_time
                    and tracker.state == ResourceState.ACTIVE
                )
            ]

        for tracker in unused_resources:
            try:
                logger.info(
                    f"Cleaning up unused resource '{tracker.name}'",
                    extra={"idle_time": current_time - tracker.metrics.last_access_time},
                )
                self._cleanup_resource(tracker)
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up unused resource '{tracker.name}'", exc_info=e)

        return cleaned_count

    def _cleanup_resource(self, tracker: ResourceTracker) -> None:
        """Cleanup a single resource.

        Transitions: ACTIVE → CLEANUP_PENDING → CLEANED_UP (or ERROR)
        Tries async cleanup first if available, otherwise sync cleanup.
        Falls back to protocol-based cleanup (resource.cleanup() method).

        Raises:
            Exception: If cleanup fails (state will be ERROR)
        """
        if tracker.state != ResourceState.ACTIVE:
            return

        tracker.state = ResourceState.CLEANUP_PENDING
        cleanup_start = time.time()

        try:
            # Try async cleanup first
            if tracker.async_cleanup_func:
                if asyncio.get_event_loop().is_running():
                    # Schedule async cleanup
                    task = asyncio.create_task(tracker.async_cleanup_func())
                    self._cleanup_tasks.add(task)
                    task.add_done_callback(self._cleanup_tasks.discard)
                else:
                    # Run in new event loop
                    asyncio.run(tracker.async_cleanup_func())

            # Run sync cleanup
            elif tracker.sync_cleanup_func:
                tracker.cleanup_func()

            # Try protocol-based cleanup
            elif hasattr(tracker.resource, "cleanup"):
                cleanup_method = tracker.resource.cleanup
                if asyncio.iscoroutinefunction(cleanup_method):
                    if asyncio.get_event_loop().is_running():
                        task = asyncio.create_task(cleanup_method())
                        self._cleanup_tasks.add(task)
                        task.add_done_callback(self._cleanup_tasks.discard)
                    else:
                        asyncio.run(cleanup_method())
                else:
                    cleanup_method()

            tracker.state = ResourceState.CLEANED_UP
            tracker.metrics.cleanup_time = time.time()
            tracker.metrics.cleanup_duration = tracker.metrics.cleanup_time - cleanup_start

            logger.debug(
                f"Successfully cleaned up resource '{tracker.name}'",
                extra={"cleanup_duration_ms": tracker.metrics.cleanup_duration * 1000},
            )

        except Exception as e:
            tracker.state = ResourceState.ERROR
            logger.error(
                f"Failed to cleanup resource '{tracker.name}'",
                extra={"exception_type": type(e).__name__},
                exc_info=e,
            )
            raise

    def shutdown(self, timeout: float = 30.0) -> None:
        """Shutdown the resource manager and cleanup all resources.

        Cleans up resources in priority order: CRITICAL → HIGH → MEDIUM → LOW.
        Blocks new resource registrations during shutdown.
        Waits for async cleanup tasks to complete (up to timeout).

        Args:
            timeout: Max seconds to wait for async cleanups (default: 30)

        Note:
            Called automatically on SIGTERM/SIGINT signals and atexit.
            Safe to call multiple times (idempotent).
        """
        logger.info(f"Shutting down resource manager '{self.name}'")

        with self._lock:
            self._shutdown_in_progress = True

        # Cleanup by priority order (critical first)
        for priority in CleanupPriority:
            try:
                cleaned_count = self.cleanup_by_priority(priority)
                if cleaned_count > 0:
                    logger.info(
                        f"Cleaned up {cleaned_count} resources with priority {priority.name}"
                    )
            except Exception as e:
                logger.error(f"Error during priority {priority.name} cleanup", exc_info=e)

        # Wait for async cleanup tasks to complete
        if self._cleanup_tasks:
            try:
                if asyncio.get_event_loop().is_running():
                    # We're in an async context, can't use asyncio.run
                    # Just log that tasks are pending
                    logger.warning(f"{len(self._cleanup_tasks)} async cleanup tasks still pending")
                else:
                    # Wait for async tasks to complete
                    asyncio.run(self._wait_for_cleanup_tasks(timeout))
            except Exception as e:
                logger.error("Error waiting for async cleanup tasks", exc_info=e)

        logger.info(f"Resource manager '{self.name}' shutdown complete")

    async def _wait_for_cleanup_tasks(self, timeout: float) -> None:
        """Wait for all cleanup tasks to complete."""
        if not self._cleanup_tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._cleanup_tasks, return_exceptions=True), timeout=timeout
            )
        except TimeoutError:
            logger.warning(f"Some cleanup tasks did not complete within {timeout} seconds")
            # Cancel remaining tasks
            for task in self._cleanup_tasks:
                if not task.done():
                    task.cancel()

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating resource cleanup")
        self.shutdown()
        sys.exit(0)

    def _emergency_cleanup(self) -> None:
        """Emergency cleanup called by atexit."""
        if not self._shutdown_in_progress:
            logger.warning("Emergency cleanup triggered")
            self.shutdown(timeout=5.0)  # Shorter timeout for emergency


# Global resource manager instance
_global_resource_manager = ResourceManager("global")
_manager_lock = threading.Lock()


def get_resource_manager(name: str = "global") -> ResourceManager:
    """Get a resource manager instance.

    Args:
        name: "global" returns the singleton, other names create new instances

    Returns:
        ResourceManager instance (singleton for "global", new for others)

    Example:
        manager = get_resource_manager()  # Global singleton
        manager.register_resource(conn, "database")
    """
    global _global_resource_manager

    with _manager_lock:
        if name == "global":
            return _global_resource_manager
        else:
            # For non-global managers, create new instances
            # You might want to implement a registry here
            return ResourceManager(name)


# Decorator and context manager utilities


def managed_resource(
    name: str,
    priority: CleanupPriority = CleanupPriority.MEDIUM,
    manager: ResourceManager | None = None,
):
    """Decorator to automatically register instances for cleanup.

    Wraps __init__ to register each instance with the ResourceManager.
    Cleanup methods are auto-detected on the class.

    Args:
        name: Base name for resources (suffixed with class name and id)
        priority: Cleanup order during shutdown
        manager: ResourceManager to use (default: global)

    Example:
        @managed_resource("connection", priority=CleanupPriority.HIGH)
        class DatabaseConnection:
            def __init__(self, host: str):
                self.conn = connect(host)

            def close(self) -> None:  # Auto-detected as cleanup method
                self.conn.close()

        # Each instance is automatically registered for cleanup
        conn = DatabaseConnection("localhost")
    """

    def decorator(cls):
        original_init = cls.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

            resource_manager = manager or get_resource_manager()
            resource_name = f"{cls.__name__}_{id(self)}_{name}"

            resource_manager.register_resource(resource=self, name=resource_name, priority=priority)

            # Store the manager and name for potential manual cleanup
            self._resource_manager = resource_manager
            self._resource_name = resource_name

        cls.__init__ = new_init
        return cls

    return decorator


@contextmanager
def resource_context(
    resource: T,
    name: str,
    priority: CleanupPriority = CleanupPriority.HIGH,
    manager: ResourceManager | None = None,
) -> Generator[T, None, None]:
    """Context manager for automatic resource registration and cleanup.

    Registers resource on entry, unregisters and cleans up on exit.
    Ensures cleanup even if exception is raised.

    Args:
        resource: The resource to manage
        name: Identifier for the resource
        priority: Cleanup priority (default: HIGH)
        manager: ResourceManager to use (default: global)

    Yields:
        The resource (for use in `with` block)

    Example:
        with resource_context(open_connection(), "db_conn") as conn:
            conn.execute("SELECT 1")
        # Connection automatically cleaned up here
    """

    resource_manager = manager or get_resource_manager()
    resource_name = resource_manager.register_resource(
        resource=resource, name=name, priority=priority
    )

    try:
        yield resource
    finally:
        resource_manager.unregister_resource(resource_name, perform_cleanup=True)


@asynccontextmanager
async def async_resource_context(
    resource: T,
    name: str,
    priority: CleanupPriority = CleanupPriority.HIGH,
    manager: ResourceManager | None = None,
) -> AsyncGenerator[T, None]:
    """Async context manager for automatic resource registration and cleanup.

    Async version of resource_context. Registers resource on entry,
    unregisters and cleans up on exit. Ensures cleanup even if exception raised.

    Args:
        resource: The resource to manage
        name: Identifier for the resource
        priority: Cleanup priority (default: HIGH)
        manager: ResourceManager to use (default: global)

    Yields:
        The resource (for use in `async with` block)

    Example:
        async with async_resource_context(await open_connection(), "db") as conn:
            await conn.execute("SELECT 1")
        # Connection automatically cleaned up here
    """

    resource_manager = manager or get_resource_manager()
    resource_name = resource_manager.register_resource(
        resource=resource, name=name, priority=priority
    )

    try:
        yield resource
    finally:
        resource_manager.unregister_resource(resource_name, perform_cleanup=True)


class ResourceLeak:
    """Represents a detected resource leak.

    Created by LeakDetector when it notices a significant increase
    in object counts of a particular type.

    Attributes:
        resource_type: Name of the type that appears to be leaking
        count: Number of new instances detected
        creation_stack: Optional stack trace of where leak originated
        detection_time: Unix timestamp when leak was detected
    """

    def __init__(self, resource_type: str, count: int, creation_stack: list[str] | None = None):
        self.resource_type = resource_type  # Type name that's leaking
        self.count = count  # How many new instances
        self.creation_stack = creation_stack  # Where leak originated (if available)
        self.detection_time = time.time()  # When detected


class LeakDetector:
    """Detects and reports resource leaks.

    Periodically scans all Python objects via gc.get_objects() and
    tracks counts by type. Logs a warning if any type's count increases
    by more than 50% between checks.

    Limitations:
        - High overhead (full GC scan on each check)
        - Heuristic-based (may produce false positives)
        - Cannot identify WHERE leaks originate

    Best for development/debugging, not production.

    Example:
        detector = LeakDetector(check_interval=60.0)
        detector.start_monitoring()
        # ... run application ...
        detector.stop_monitoring()

        # Or use global functions:
        enable_leak_detection(check_interval=60.0)
        # ... run application ...
        disable_leak_detection()

    Attributes:
        check_interval: Seconds between leak checks (default: 60)
    """

    def __init__(self, check_interval: float = 60.0):
        """Initialize LeakDetector.

        Args:
            check_interval: Seconds between leak checks (default: 60)
        """
        self.check_interval = check_interval  # How often to check
        self._tracked_objects: dict[type, set[int]] = {}  # type → set of object ids
        self._running = False  # Monitoring active?
        self._task: asyncio.Task | None = None  # Async monitoring task

    def start_monitoring(self) -> None:
        """Start leak detection monitoring.

        If event loop is running, creates async task.
        Otherwise, starts daemon thread for monitoring.
        No-op if already monitoring.
        """
        if self._running:
            return

        self._running = True
        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            # No event loop running, start in background thread
            threading.Thread(target=self._monitor_in_thread, daemon=True).start()

    def stop_monitoring(self) -> None:
        """Stop leak detection monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_for_leaks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in leak detection monitoring", exc_info=e)
                await asyncio.sleep(self.check_interval)

    def _monitor_in_thread(self) -> None:
        """Monitor in background thread when no event loop is available."""
        while self._running:
            try:
                self._check_for_leaks()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error("Error in leak detection monitoring", exc_info=e)
                time.sleep(self.check_interval)

    def _check_for_leaks(self) -> None:
        """Check for potential resource leaks."""
        gc.collect()  # Force garbage collection

        # Track object counts by type
        current_objects = {}
        for obj in gc.get_objects():
            obj_type = type(obj)
            if obj_type.__name__.startswith("_"):
                continue  # Skip private types

            current_objects[obj_type] = current_objects.get(obj_type, 0) + 1

        # Compare with previous counts
        for obj_type, current_count in current_objects.items():
            previous_count = len(self._tracked_objects.get(obj_type, set()))

            # Simple heuristic: if count increased significantly, might be a leak
            if previous_count > 0 and current_count > previous_count * 1.5:
                leak = ResourceLeak(
                    resource_type=obj_type.__name__, count=current_count - previous_count
                )

                logger.warning(
                    f"Potential resource leak detected: {leak.resource_type}",
                    extra={
                        "current_count": current_count,
                        "previous_count": previous_count,
                        "increase": current_count - previous_count,
                    },
                )

        # Update tracking
        self._tracked_objects.clear()
        for obj in gc.get_objects():
            obj_type = type(obj)
            if obj_type not in self._tracked_objects:
                self._tracked_objects[obj_type] = set()
            self._tracked_objects[obj_type].add(id(obj))


# Global leak detector
_leak_detector = LeakDetector()


def enable_leak_detection(check_interval: float = 60.0) -> None:
    """Enable global resource leak detection.

    Starts background monitoring that logs warnings when potential
    memory leaks are detected (object count increases > 50%).

    Args:
        check_interval: Seconds between leak checks (default: 60)

    Note:
        High overhead — best for development/debugging only.
    """
    global _leak_detector
    _leak_detector.check_interval = check_interval
    _leak_detector.start_monitoring()
    logger.info(f"Resource leak detection enabled with {check_interval}s interval")


def disable_leak_detection() -> None:
    """Disable global resource leak detection."""
    _leak_detector.stop_monitoring()
    logger.info("Resource leak detection disabled")


# Cleanup utilities for common resource types


def cleanup_temp_files(temp_dir: Path | None = None, max_age_hours: float = 24.0) -> int:
    """Cleanup temporary files older than specified age.

    Removes files/directories matching 'kagami_*' pattern that are older
    than max_age_hours. Used for periodic maintenance of temp files.

    Args:
        temp_dir: Directory to clean (default: system temp dir)
        max_age_hours: Max file age in hours (default: 24)

    Returns:
        Number of files/directories removed

    Note:
        Only cleans files matching 'kagami_*' pattern for safety.
        Errors on individual files are logged but don't stop cleanup.
    """
    if temp_dir is None:
        import tempfile

        temp_dir = Path(tempfile.gettempdir())

    cleaned_count = 0
    cutoff_time = time.time() - (max_age_hours * 3600)

    try:
        for file_path in temp_dir.rglob("kagami_*"):
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    if file_path.is_file():
                        file_path.unlink()
                        cleaned_count += 1
                    elif file_path.is_dir():
                        import shutil

                        shutil.rmtree(file_path)
                        cleaned_count += 1
            except Exception as e:
                logger.debug(f"Could not cleanup temp file {file_path}: {e}")

    except Exception as e:
        logger.error(f"Error cleaning up temp files in {temp_dir}", exc_info=e)

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} temporary files/directories")

    return cleaned_count


def force_garbage_collection() -> dict[str, int]:
    """Force garbage collection across all generations and return stats.

    Runs gc.collect() on generations 0, 1, and 2 sequentially.
    Useful for freeing memory before memory-intensive operations.

    Returns:
        Dict with 'generation_0', 'generation_1', 'generation_2' keys,
        each containing the number of objects freed in that generation.

    Example:
        stats = force_garbage_collection()
        print(f"Freed {sum(stats.values())} objects")
    """
    import gc

    # Force collection across all generations
    collected = {
        "generation_0": gc.collect(0),
        "generation_1": gc.collect(1),
        "generation_2": gc.collect(2),
    }

    total_collected = sum(collected.values())
    if total_collected > 0:
        logger.info(f"Garbage collection freed {total_collected} objects", extra=collected)

    return collected


__all__ = [
    "AsyncResourceProtocol",
    "CleanupPriority",
    "LeakDetector",
    "ResourceLeak",
    "ResourceManager",
    "ResourceMetrics",
    "ResourceProtocol",
    "ResourceState",
    "ResourceTracker",
    "async_resource_context",
    "cleanup_temp_files",
    "disable_leak_detection",
    "enable_leak_detection",
    "force_garbage_collection",
    "get_resource_manager",
    "managed_resource",
    "resource_context",
]
