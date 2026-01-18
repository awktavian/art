"""ActionResult Adapter — Migration Utilities for Legacy Result Patterns.

MIGRATION HELPER: Provides utilities to migrate legacy boolean/exception patterns
to the unified ActionResult pattern without breaking existing APIs.

This allows gradual migration:
1. Update internal implementations to use ActionResult
2. Maintain existing bool-returning APIs via adapters
3. Gradually migrate callers to use ActionResult directly
4. Remove adapters once migration is complete

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .action_result import (
    ActionError,
    ActionErrorType,
    ActionMetadata,
    ActionResult,
    BatchActionResult,
    from_exception,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ActionResultAdapter:
    """Adapter utilities for migrating to ActionResult pattern.

    Provides methods to convert between legacy patterns and ActionResult.
    """

    @staticmethod
    def to_bool(result: ActionResult[Any]) -> bool:
        """Convert ActionResult to boolean for legacy API compatibility.

        Args:
            result: ActionResult instance

        Returns:
            True if success/partial success, False otherwise
        """
        return result.is_success() or result.is_partial_success()

    @staticmethod
    def to_bool_strict(result: ActionResult[Any]) -> bool:
        """Convert ActionResult to boolean with strict success requirement.

        Args:
            result: ActionResult instance

        Returns:
            True only if complete success, False otherwise
        """
        return result.is_success()

    @staticmethod
    async def execute_with_fallback(
        primary_func: Callable[[], Awaitable[ActionResult[T]]],
        fallback_func: Callable[[], Awaitable[ActionResult[T]]] | None = None,
        metadata: ActionMetadata | None = None,
    ) -> ActionResult[T]:
        """Execute primary function with optional fallback.

        Args:
            primary_func: Primary action function
            fallback_func: Optional fallback function if primary fails
            metadata: Optional metadata to include

        Returns:
            ActionResult from primary or fallback
        """
        if metadata is None:
            metadata = ActionMetadata()

        try:
            result = await primary_func()

            # If primary succeeded or fallback not available
            if result.is_success() or not fallback_func:
                return result

            # Try fallback
            metadata.add_retry()
            fallback_result = await fallback_func()

            # Combine warnings from both attempts
            if result.warnings:
                fallback_result.warnings.extend(result.warnings)

            return fallback_result

        except Exception as e:
            logger.error(f"Execute with fallback failed: {e}")
            return from_exception(e, metadata)


class BatchActionAdapter:
    """Adapter for batch operations using ActionResult pattern.

    Converts legacy batch patterns to unified ActionResult approach.
    """

    @staticmethod
    async def execute_batch_parallel(
        targets: list[str],
        action_func: Callable[[str], Awaitable[ActionResult[T]]],
        max_concurrent: int = 10,
        metadata: ActionMetadata | None = None,
    ) -> BatchActionResult[T]:
        """Execute batch operation in parallel with concurrency control.

        Args:
            targets: List of targets to operate on
            action_func: Function to execute for each target
            max_concurrent: Maximum concurrent operations
            metadata: Optional batch metadata

        Returns:
            BatchActionResult with individual results
        """
        if metadata is None:
            metadata = ActionMetadata(action_type="batch_parallel")

        batch_result = BatchActionResult(metadata=metadata)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_with_semaphore(target: str) -> tuple[str, ActionResult[T]]:
            async with semaphore:
                try:
                    result = await action_func(target)
                    return target, result
                except Exception as e:
                    error_result = from_exception(
                        e, ActionMetadata(target=target, action_type=metadata.action_type)
                    )
                    return target, error_result

        # Execute all targets in parallel
        tasks = [execute_with_semaphore(target) for target in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for item in results:
            if isinstance(item, Exception):
                # Gather failed - this shouldn't happen with return_exceptions=True
                logger.error(f"Unexpected gather exception: {item}")
                continue

            target, result = item
            batch_result.add_result(target, result)

        batch_result.metadata.mark_completed()
        return batch_result

    @staticmethod
    async def execute_batch_sequential(
        targets: list[str],
        action_func: Callable[[str], Awaitable[ActionResult[T]]],
        stop_on_failure: bool = False,
        metadata: ActionMetadata | None = None,
    ) -> BatchActionResult[T]:
        """Execute batch operation sequentially.

        Args:
            targets: List of targets to operate on
            action_func: Function to execute for each target
            stop_on_failure: Whether to stop on first failure
            metadata: Optional batch metadata

        Returns:
            BatchActionResult with individual results
        """
        if metadata is None:
            metadata = ActionMetadata(action_type="batch_sequential")

        batch_result = BatchActionResult(metadata=metadata)

        for target in targets:
            try:
                result = await action_func(target)
                batch_result.add_result(target, result)

                # Stop on failure if requested
                if stop_on_failure and result.is_failure():
                    logger.info(f"Stopping batch operation at {target} due to failure")
                    break

            except Exception as e:
                error_result = from_exception(
                    e, ActionMetadata(target=target, action_type=metadata.action_type)
                )
                batch_result.add_result(target, error_result)

                if stop_on_failure:
                    logger.info(f"Stopping batch operation at {target} due to exception: {e}")
                    break

        batch_result.metadata.mark_completed()
        return batch_result


class SmartHomeFunctionAdapter:
    """Specific adapter for SmartHome controller functions.

    Handles the specific patterns used in the SmartHome controller:
    - any(results) patterns
    - null integration checking
    - batch device operations
    """

    @staticmethod
    def check_integration_available(integration: Any, integration_name: str) -> ActionResult[None]:
        """Check if integration is available.

        Args:
            integration: Integration instance to check
            integration_name: Name for error messages

        Returns:
            Success if available, failure if not
        """
        metadata = ActionMetadata(action_type="integration_check", target=integration_name)

        if integration is None:
            error = ActionError(
                ActionErrorType.SERVICE_UNAVAILABLE,
                f"{integration_name} integration is not available",
                recoverable=False,  # Integration needs to be configured
            )
            return ActionResult.failure(error, metadata=metadata)

        return ActionResult.success(metadata=metadata)

    @staticmethod
    async def execute_device_operation(
        device_id: str,
        operation: Callable[[], Awaitable[bool]],
        operation_type: str,
        target_name: str | None = None,
    ) -> ActionResult[bool]:
        """Execute operation on a single device with error handling.

        Args:
            device_id: ID of device to operate on
            operation: Async operation that returns bool
            operation_type: Type of operation for metadata
            target_name: Optional target name for metadata

        Returns:
            ActionResult with operation outcome
        """
        metadata = ActionMetadata(action_type=operation_type, target=target_name or device_id)

        try:
            success = await operation()

            if success:
                return ActionResult.success(
                    data=True,
                    message=f"{operation_type} succeeded for {device_id}",
                    metadata=metadata,
                )
            else:
                error = ActionError(
                    ActionErrorType.SYSTEM_ERROR,
                    f"{operation_type} failed for {device_id}",
                    recoverable=True,
                    retry_after=1.0,
                )
                return ActionResult.failure(error, metadata=metadata)

        except TimeoutError:
            return ActionResult.timeout(
                timeout_duration=30.0,  # Default timeout
                message=f"{operation_type} timed out for {device_id}",
                metadata=metadata,
            )
        except Exception as e:
            return from_exception(e, metadata)

    @staticmethod
    def analyze_batch_results(
        batch_result: BatchActionResult[T], require_all_success: bool = False
    ) -> tuple[bool, str]:
        """Analyze batch results and return legacy-compatible (bool, message).

        Args:
            batch_result: BatchActionResult to analyze
            require_all_success: Whether all operations must succeed

        Returns:
            Tuple of (success_bool, status_message)
        """
        total = batch_result.total_count
        success_count = batch_result.success_count

        if total == 0:
            return True, "No operations to perform"

        if require_all_success:
            success = batch_result.is_complete_success()
            if success:
                message = f"All {total} operations succeeded"
            else:
                failed_targets = batch_result.get_failed_targets()
                message = (
                    f"{success_count}/{total} succeeded. Failed: {', '.join(failed_targets[:3])}"
                )
                if len(failed_targets) > 3:
                    message += f" and {len(failed_targets) - 3} others"
        else:
            # Legacy any() behavior - succeed if any succeeded
            success = success_count > 0
            if success:
                if success_count == total:
                    message = f"All {total} operations succeeded"
                else:
                    message = f"{success_count}/{total} operations succeeded"
            else:
                message = f"All {total} operations failed"

        return success, message


def migrate_smart_home_function(integration_name: str, require_all_success: bool = False):
    """Decorator to migrate SmartHome controller functions to ActionResult pattern.

    Args:
        integration_name: Name of integration for error messages
        require_all_success: Whether to require all operations to succeed

    Returns:
        Decorator function
    """

    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # Extract integration check from function
            integration = getattr(self, f"_{integration_name.lower()}", None)

            # Check integration availability
            availability_check = SmartHomeFunctionAdapter.check_integration_available(
                integration, integration_name
            )

            if availability_check.is_failure():
                # Return legacy bool for backward compatibility
                return ActionResultAdapter.to_bool(availability_check)

            # Execute original function logic but capture detailed results
            # This would need to be implemented per function
            # For now, we'll call the original function
            result = await func(self, *args, **kwargs)

            # If result is already ActionResult, convert to bool
            if isinstance(result, ActionResult):
                return ActionResultAdapter.to_bool(result)

            # Legacy boolean result
            return result

        return wrapper

    return decorator
