"""Resource leak detection and tracking.

Provides centralized tracking of all resources to detect leaks
and enable automated cleanup.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrackedResource:
    """Information about a tracked resource.

    Attributes:
        resource_id: Unique identifier for resource
        resource_type: Type of resource (file, connection, gpu, etc)
        created_at: Timestamp when resource was created
        metadata: Additional metadata about resource
        stack_trace: Stack trace where resource was created (for debugging)
    """

    resource_id: str
    resource_type: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    stack_trace: list[str] = field(default_factory=list[Any])


class ResourceTracker:
    """Central resource tracking for leak detection.

    Features:
    - Track all resources across the system
    - Detect resource leaks
    - Automatic cleanup on shutdown
    - Metrics and statistics
    - Alert on long-lived resources

    Usage:
        tracker = get_resource_tracker()

        # Track a resource
        resource_id = tracker.track(
            resource_type="file",
            resource_id="/tmp/file.txt",
            metadata={"mode": "r"}
        )

        # Untrack when done
        tracker.untrack(resource_id)

        # Check for leaks
        leaks = tracker.detect_leaks(threshold=300)  # Resources older than 5 min

        # Get statistics
        stats = tracker.get_stats()
    """

    def __init__(self, enable_stack_traces: bool = False) -> None:
        """Initialize resource tracker.

        Args:
            enable_stack_traces: Whether to capture stack traces (expensive)
        """
        self._resources: dict[str, TrackedResource] = {}
        self._lock = threading.RLock()
        self._enable_stack_traces = enable_stack_traces
        self._total_tracked = 0
        self._total_untracked = 0
        self._leak_threshold = 300.0  # 5 minutes default
        self._cleanup_callbacks: list[tuple[str, Any]] = []

        # Weak references to resources for automatic cleanup
        self._weak_refs: dict[str, Any] = {}

    def track(
        self,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Track a resource.

        Args:
            resource_type: Type of resource
            resource_id: Unique identifier
            metadata: Optional metadata

        Returns:
            Tracking ID (same as resource_id)
        """
        with self._lock:
            # Create tracked resource
            stack_trace = []
            if self._enable_stack_traces:
                import traceback

                stack_trace = traceback.format_stack()[:-1]  # Exclude this frame

            tracked = TrackedResource(
                resource_id=resource_id,
                resource_type=resource_type,
                created_at=time.time(),
                metadata=metadata or {},
                stack_trace=stack_trace,
            )

            self._resources[resource_id] = tracked
            self._total_tracked += 1

            logger.debug(
                f"Tracking resource: type={resource_type}, id={resource_id}, "
                f"total={len(self._resources)}"
            )

            return resource_id

    def untrack(self, resource_id: str) -> bool:
        """Stop tracking a resource.

        Args:
            resource_id: Resource identifier

        Returns:
            True if resource was tracked, False otherwise
        """
        with self._lock:
            if resource_id in self._resources:
                resource = self._resources.pop(resource_id)
                self._total_untracked += 1

                # Calculate lifetime
                lifetime = time.time() - resource.created_at

                logger.debug(
                    f"Untracking resource: type={resource.resource_type}, "
                    f"id={resource_id}, lifetime={lifetime:.2f}s, "
                    f"remaining={len(self._resources)}"
                )

                # Remove weak reference
                if resource_id in self._weak_refs:
                    del self._weak_refs[resource_id]

                return True

            return False

    def detect_leaks(
        self, threshold: float | None = None, resource_type: str | None = None
    ) -> list[TrackedResource]:
        """Detect potential resource leaks.

        Args:
            threshold: Age threshold in seconds (uses default if None)
            resource_type: Filter by resource type (all types if None)

        Returns:
            List of leaked resources
        """
        threshold = threshold or self._leak_threshold
        current_time = time.time()
        leaks = []

        with self._lock:
            for resource in self._resources.values():
                # Check age
                age = current_time - resource.created_at
                if age < threshold:
                    continue

                # Check type filter
                if resource_type and resource.resource_type != resource_type:
                    continue

                leaks.append(resource)

        if leaks:
            logger.warning(
                f"Detected {len(leaks)} potential resource leaks (threshold={threshold}s)"
            )

        return leaks

    def get_stats(self) -> dict[str, Any]:
        """Get resource tracking statistics.

        Returns:
            Statistics dict[str, Any]
        """
        with self._lock:
            # Count by type
            by_type: dict[str, int] = defaultdict(int)
            oldest_by_type: dict[str, float] = {}
            current_time = time.time()

            for resource in self._resources.values():
                by_type[resource.resource_type] += 1

                age = current_time - resource.created_at
                if resource.resource_type not in oldest_by_type:
                    oldest_by_type[resource.resource_type] = age
                else:
                    oldest_by_type[resource.resource_type] = max(
                        oldest_by_type[resource.resource_type], age
                    )

            return {
                "total_tracked": len(self._resources),
                "total_created": self._total_tracked,
                "total_cleaned": self._total_untracked,
                "by_type": dict(by_type),
                "oldest_by_type": oldest_by_type,
                "leak_threshold": self._leak_threshold,
            }

    def get_resources(self, resource_type: str | None = None) -> list[TrackedResource]:
        """Get all tracked resources.

        Args:
            resource_type: Filter by type (all if None)

        Returns:
            List of tracked resources
        """
        with self._lock:
            if resource_type:
                return [r for r in self._resources.values() if r.resource_type == resource_type]
            return list(self._resources.values())

    def register_cleanup_callback(self, resource_type: str, callback: Any) -> None:
        """Register a cleanup callback for a resource type.

        Args:
            resource_type: Type to register for
            callback: Cleanup function
        """
        with self._lock:
            self._cleanup_callbacks.append((resource_type, callback))

    async def cleanup_all(self, force: bool = False) -> int:
        """Cleanup all tracked resources.

        Args:
            force: Force cleanup even if resources are young

        Returns:
            Number of resources cleaned up
        """
        cleaned = 0

        with self._lock:
            resources = list(self._resources.values())

        for resource in resources:
            # Check age unless forcing
            if not force:
                age = time.time() - resource.created_at
                if age < self._leak_threshold:
                    continue

            # Try cleanup callbacks
            for callback_type, callback in self._cleanup_callbacks:
                if callback_type == resource.resource_type:
                    try:
                        result = callback(resource)
                        if asyncio.iscoroutine(result):
                            await result
                        cleaned += 1
                        self.untrack(resource.resource_id)
                    except Exception as e:
                        logger.error(
                            f"Failed to cleanup {resource.resource_type} "
                            f"{resource.resource_id}: {e}"
                        )

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} leaked resources")

        return cleaned

    def set_leak_threshold(self, threshold: float) -> None:
        """Set the leak detection threshold.

        Args:
            threshold: Threshold in seconds
        """
        self._leak_threshold = threshold

    def clear(self) -> None:
        """Clear all tracked resources (for testing)."""
        with self._lock:
            self._resources.clear()
            self._weak_refs.clear()
            self._total_tracked = 0
            self._total_untracked = 0

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return (
            f"ResourceTracker(tracked={stats['total_tracked']}, "
            f"created={stats['total_created']}, "
            f"cleaned={stats['total_cleaned']})"
        )


# Global tracker instance
_TRACKER: ResourceTracker | None = None
_TRACKER_LOCK = threading.Lock()


def get_resource_tracker() -> ResourceTracker:
    """Get the global resource tracker instance.

    Returns:
        Resource tracker singleton
    """
    global _TRACKER

    if _TRACKER is None:
        with _TRACKER_LOCK:
            if _TRACKER is None:
                _TRACKER = ResourceTracker()

    return _TRACKER


def track_resource(
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Convenience function to track a resource.

    Args:
        resource_type: Type of resource
        resource_id: Unique identifier
        metadata: Optional metadata

    Returns:
        Tracking ID
    """
    tracker = get_resource_tracker()
    return tracker.track(resource_type, resource_id, metadata)


def untrack_resource(resource_id: str) -> bool:
    """Convenience function to untrack a resource.

    Args:
        resource_id: Resource identifier

    Returns:
        True if resource was tracked
    """
    tracker = get_resource_tracker()
    return tracker.untrack(resource_id)


async def check_for_leaks(
    threshold: float | None = None, log: bool = True
) -> list[TrackedResource]:
    """Check for resource leaks.

    Args:
        threshold: Age threshold in seconds
        log: Whether to log findings

    Returns:
        List of leaked resources
    """
    tracker = get_resource_tracker()
    leaks = tracker.detect_leaks(threshold)

    if log and leaks:
        logger.error(f"Found {len(leaks)} resource leaks:")
        for leak in leaks:
            age = time.time() - leak.created_at
            logger.error(
                f"  - {leak.resource_type}: {leak.resource_id} "
                f"(age={age:.1f}s, metadata={leak.metadata})"
            )

            if leak.stack_trace:
                logger.error("    Stack trace:")
                for line in leak.stack_trace:
                    logger.error(f"      {line}")

    return leaks


async def cleanup_leaked_resources(force: bool = False) -> int:
    """Cleanup any leaked resources.

    Args:
        force: Force cleanup even if resources are young

    Returns:
        Number of resources cleaned up
    """
    tracker = get_resource_tracker()
    return await tracker.cleanup_all(force=force)


def get_resource_stats() -> dict[str, Any]:
    """Get resource tracking statistics.

    Returns:
        Statistics dict[str, Any]
    """
    tracker = get_resource_tracker()
    return tracker.get_stats()


def reset_tracker() -> None:
    """Reset the global tracker (for testing)."""
    global _TRACKER
    with _TRACKER_LOCK:
        if _TRACKER:
            _TRACKER.clear()
        _TRACKER = None
