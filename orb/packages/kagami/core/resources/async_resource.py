"""Generic async resource management with automatic cleanup.

Provides a generic pattern for managing any async resource with
guaranteed cleanup, even in error conditions.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Literal, TypeVar

from kagami.core.resources.tracker import track_resource

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResourceCleanupError(Exception):
    """Error during resource cleanup."""

    pass


class AsyncResource:
    """Generic async resource wrapper with automatic cleanup.

    Features:
    - Automatic cleanup via context manager
    - Resource leak tracking
    - Error handling with proper cleanup
    - Support for sync and async cleanup functions
    - Metrics collection

    Usage:
        # With cleanup function
        async def cleanup_fn(resource):
            await resource.close()

        async with AsyncResource(my_resource, cleanup_fn) as r:
            await r.use()

        # With enter/exit callbacks
        async def setup(resource):
            await resource.connect()
            return resource

        async with AsyncResource(
            my_resource,
            cleanup_fn,
            enter_fn=setup
        ) as r:
            await r.use()
    """

    def __init__(
        self,
        resource: T,
        cleanup_fn: Callable[[T], None] | Callable[[T], Any],
        enter_fn: Callable[[T], T] | Callable[[T], Any] | None = None,
        resource_type: str = "generic",
        track: bool = True,
    ) -> None:
        """Initialize async resource wrapper.

        Args:
            resource: Resource to manage
            cleanup_fn: Function to cleanup resource (sync or async)
            enter_fn: Optional function to run on entry (sync or async)
            resource_type: Type name for tracking
            track: Whether to track resource
        """
        self.resource = resource
        self.cleanup_fn = cleanup_fn
        self.enter_fn = enter_fn
        self.resource_type = resource_type
        self.track_resource = track
        self._resource_id: str | None = None
        self._entered = False
        self._cleaned_up = False

    async def __aenter__(self) -> T:
        """Async context manager entry."""
        # Run enter function if provided
        if self.enter_fn:
            result = self.enter_fn(self.resource)
            if asyncio.iscoroutine(result):
                self.resource = await result
            else:
                self.resource = result

        # Track resource
        if self.track_resource:
            self._resource_id = track_resource(
                resource_type=self.resource_type,
                resource_id=str(id(self.resource)),
                metadata={"type": type(self.resource).__name__},
            )

        self._entered = True
        logger.debug(f"Acquired {self.resource_type} resource: {id(self.resource)}")

        return self.resource

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Async context manager exit with cleanup."""
        await self.cleanup()
        return False

    async def cleanup(self) -> None:
        """Cleanup the resource."""
        if self._cleaned_up:
            return

        cleanup_error = None
        try:
            # Call cleanup function
            if self.cleanup_fn:
                try:
                    result = self.cleanup_fn(self.resource)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    cleanup_error = e
                    logger.error(f"Failed to cleanup {self.resource_type} resource: {e}")

        finally:
            self._cleaned_up = True

            # Untrack resource
            if self._resource_id:
                from kagami.core.resources.tracker import get_resource_tracker

                tracker = get_resource_tracker()
                tracker.untrack(self._resource_id)
                self._resource_id = None

            logger.debug(f"Cleaned up {self.resource_type} resource: {id(self.resource)}")

            if cleanup_error:
                raise ResourceCleanupError(
                    f"Cleanup failed for {self.resource_type}"
                ) from cleanup_error

    @property
    def cleaned_up(self) -> bool:
        """Check if resource has been cleaned up."""
        return self._cleaned_up


class AsyncResourceManager:
    """Manager for multiple async resources with batch cleanup.

    Features:
    - Manage multiple resources together
    - Batch cleanup (all or nothing)
    - Automatic tracking
    - Error aggregation

    Usage:
        async with AsyncResourceManager() as mgr:
            res1 = await mgr.add(resource1, cleanup1)
            res2 = await mgr.add(resource2, cleanup2)
            res3 = await mgr.add(resource3, cleanup3)
            # All cleaned up together
    """

    def __init__(self) -> None:
        """Initialize resource manager."""
        self._resources: list[AsyncResource[Any]] = []
        self._resource_id: str | None = None

    async def __aenter__(self) -> "AsyncResourceManager":
        """Async context manager entry."""
        # Track manager
        self._resource_id = track_resource(
            resource_type="resource_manager",
            resource_id=str(id(self)),
            metadata={"resources": 0},
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Async context manager exit with cleanup."""
        await self.cleanup_all()
        return False

    async def add(
        self,
        resource: T,
        cleanup_fn: Callable[[T], None] | Callable[[T], Any],
        enter_fn: Callable[[T], T] | Callable[[T], Any] | None = None,
        resource_type: str = "generic",
    ) -> T:
        """Add a resource to be managed.

        Args:
            resource: Resource to manage
            cleanup_fn: Cleanup function
            enter_fn: Optional entry function
            resource_type: Resource type name

        Returns:
            The resource (possibly modified by enter_fn)
        """
        async_resource = AsyncResource(resource, cleanup_fn, enter_fn, resource_type, track=True)

        # Enter the resource
        actual_resource = await async_resource.__aenter__()

        # Track it
        self._resources.append(async_resource)

        logger.debug(f"Added {resource_type} to manager: {id(resource)}")

        return actual_resource

    async def cleanup_all(self) -> None:
        """Cleanup all managed resources."""
        cleanup_errors = []

        # Cleanup in reverse order (LIFO)
        for resource in reversed(self._resources):
            try:
                await resource.cleanup()
            except Exception as e:
                cleanup_errors.append(e)
                logger.error(f"Failed to cleanup resource: {e}")

        self._resources.clear()

        # Untrack manager
        if self._resource_id:
            from kagami.core.resources.tracker import get_resource_tracker

            tracker = get_resource_tracker()
            tracker.untrack(self._resource_id)
            self._resource_id = None

        # Raise aggregated errors
        if cleanup_errors:
            raise ResourceCleanupError(
                f"Failed to cleanup {len(cleanup_errors)} resources"
            ) from cleanup_errors[0]

    @property
    def resource_count(self) -> int:
        """Get number of managed resources."""
        return len(self._resources)


# Convenience functions


async def with_cleanup(
    resource: T,
    cleanup_fn: Callable[[T], None] | Callable[[T], Any],
    operation: Callable[[T], Any],
) -> Any:
    """Execute operation with resource and guarantee cleanup.

    Args:
        resource: Resource to use
        cleanup_fn: Cleanup function
        operation: Async function to execute

    Returns:
        Result of operation
    """
    async with AsyncResource(resource, cleanup_fn) as r:
        result = operation(r)
        if asyncio.iscoroutine(result):
            return await result
        return result


async def ensure_cleanup(
    *resources: tuple[T, Callable[[T], None] | Callable[[T], Any]],
) -> AsyncResourceManager:
    """Ensure cleanup for multiple resources.

    Args:
        *resources: Tuples of (resource, cleanup_fn)

    Returns:
        Resource manager context manager

    Usage:
        async with await ensure_cleanup(
            (resource1, cleanup1),
            (resource2, cleanup2),
        ) as mgr:
            # Use resources
            pass
    """
    manager = AsyncResourceManager()
    await manager.__aenter__()

    for resource, cleanup_fn in resources:
        await manager.add(resource, cleanup_fn)

    return manager
