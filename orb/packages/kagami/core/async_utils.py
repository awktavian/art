from __future__ import annotations

"""Async utilities for safe task management.

Provides utilities to prevent silent task failures and ensure proper error handling.

PERFORMANCE (Dec 30, 2025):
- Installs uvloop for 2-4x event loop throughput improvement
- uvloop is a drop-in replacement for asyncio's default event loop
- Based on libuv (same as Node.js) for high-performance async I/O
"""
import asyncio
import functools
import logging
import os
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# =============================================================================
# UVLOOP INSTALLATION (High-Performance Event Loop)
# =============================================================================

_UVLOOP_INSTALLED = False


def install_uvloop() -> bool:
    """Install uvloop as the default event loop policy.

    uvloop provides 2-4x throughput improvement for event-heavy workloads.
    Safe to call multiple times (idempotent).

    Returns:
        True if uvloop was installed, False if unavailable
    """
    global _UVLOOP_INSTALLED

    if _UVLOOP_INSTALLED:
        return True

    # Skip in test mode (may cause issues with pytest-asyncio)
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("KAGAMI_TEST_MODE") == "1":
        logger.debug("uvloop: Skipped in test mode")
        return False

    try:
        import uvloop

        uvloop.install()
        _UVLOOP_INSTALLED = True
        logger.info("⚡ uvloop installed: High-performance event loop active")
        return True
    except ImportError:
        logger.debug("uvloop not installed (pip install uvloop for 2-4x async speedup)")
        return False
    except Exception as e:
        logger.warning(f"uvloop installation failed: {e}")
        return False


def is_uvloop_active() -> bool:
    """Check if uvloop is the active event loop policy."""
    try:
        import uvloop

        policy = asyncio.get_event_loop_policy()
        return isinstance(policy, uvloop.EventLoopPolicy)
    except (ImportError, AttributeError):
        return False


# Auto-install uvloop on module import (production optimization)
# This runs when any code imports async_utils, ensuring uvloop is active early
if not os.getenv("KAGAMI_NO_UVLOOP"):
    install_uvloop()

T = TypeVar("T")


def safe_create_task(
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
    error_callback: Callable[[Exception], None] | None = None,
    logger_context: dict[str, Any] | None = None,
) -> asyncio.Task[T]:
    """Create an asyncio task with automatic error handling.

    Prevents silent failures by logging exceptions and optionally calling error callback.

    SAFETY (Nov 9, 2025): Now enforces global task limit to prevent kernel panics.

    Args:
        coro: Coroutine to run
        name: Optional task name for debugging
        error_callback: Optional callback for error handling
        logger_context: Additional context for error logging

    Returns:
        asyncio.Task with error handling attached

    Raises:
        RuntimeError: If global task limit exceeded

    Example:
        >>> task = safe_create_task(
        ...     slow_operation(),
        ...     name="background_sync",
        ...     error_callback=lambda e: metrics.inc("sync_errors")
        ... )
    """
    task = asyncio.create_task(coro, name=name)

    # SAFETY: Register with global task registry (limit enforcement)
    from kagami.core.task_registry import get_task_registry

    registry = get_task_registry()

    if not registry.register_task(task, task_name=name):
        # Limit exceeded - cancel task immediately
        task.cancel()
        raise RuntimeError(
            f"Task limit exceeded ({registry.max_tasks} active tasks). "
            f"Cannot create task '{name or 'unnamed'}'. "
            "This prevents memory exhaustion and system crashes."
        )

    def _error_handler(t: asyncio.Task[T]) -> None:
        """Handle task completion and log any exceptions."""
        try:
            # Retrieve exception if any (this prevents "Task exception was never retrieved")
            exc = t.exception()
            if exc is not None:
                context = logger_context or {}
                context.update(
                    {
                        "task_name": name or "unnamed",
                        "exception_type": type(exc).__name__,
                    }
                )

                logger.error(
                    f"Background task '{name or 'unnamed'}' failed: {exc}",
                    exc_info=exc,
                    extra=context,
                )

                # Emit metric
                try:
                    from kagami_observability.metrics import emit_counter

                    emit_counter(
                        "kagami_background_task_failures_total",
                        labels={"task_name": name or "unnamed", "error_type": type(exc).__name__},
                    )
                except Exception:
                    pass  # Don't fail on metric emission

                # Call custom error callback if provided
                if error_callback:
                    try:
                        error_callback(exc)  # type: ignore[arg-type]
                    except Exception as cb_error:
                        logger.error(f"Error callback failed: {cb_error}", exc_info=True)

        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            pass
        except Exception as e:
            # Error handler itself failed
            logger.error(f"Error handler failed for task '{name}': {e}", exc_info=True)

    task.add_done_callback(_error_handler)
    return task


def safe_gather(
    *coros: Coroutine[Any, Any, Any], return_exceptions: bool = False
) -> Coroutine[Any, Any, list[Any]]:
    """Wrapper for asyncio.gather with better error context.

    Args:
        *coros: Coroutines to gather
        return_exceptions: Whether to return exceptions instead of raising

    Returns:
        List of results (or exceptions if return_exceptions=True)
    """

    async def _wrapped() -> list[Any]:
        try:
            return await asyncio.gather(*coros, return_exceptions=return_exceptions)
        except Exception as e:
            logger.error(f"safe_gather failed: {e}", exc_info=True)
            try:
                from kagami_observability.metrics import emit_counter

                emit_counter(
                    "kagami_safe_gather_failures_total",
                    labels={"error_type": type(e).__name__},
                )
            except Exception:
                pass
            raise

    return _wrapped()


async def cancel_and_await(task: asyncio.Task[Any] | None) -> None:
    """Cancel an asyncio task and await its completion (ignore CancelledError)."""
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def background_task(
    *,
    name: str | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., asyncio.Task[T]]]:
    """Decorator to convert async function into safe background task launcher.

    Args:
        name: Task name for logging
        retry_count: Number of retries on failure
        retry_delay: Delay between retries in seconds

    Example:
        >>> @background_task(name="sync_metrics", retry_count=3)
        >>> async def sync_metrics():
        ...     await upload_to_prometheus()
        >>>
        >>> # Calling creates a background task:
        >>> task = sync_metrics()  # Returns Task, doesn't block
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., asyncio.Task[T]]:
        task_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> asyncio.Task[T]:
            async def _with_retry() -> T:
                last_exception: Exception | None = None
                for attempt in range(retry_count + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < retry_count:
                            logger.warning(
                                f"Task '{task_name}' attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}"
                            )
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.error(
                                f"Task '{task_name}' failed after {retry_count + 1} attempts"
                            )
                            raise

                # Should never reach here, but satisfy type checker
                if last_exception:
                    raise last_exception
                raise RuntimeError("Unexpected retry loop exit") from None

            return safe_create_task(_with_retry(), name=task_name)

        return wrapper

    return decorator


__all__ = [
    "background_task",
    "cancel_and_await",
    "install_uvloop",
    "is_uvloop_active",
    "safe_create_task",
    "safe_gather",
]
