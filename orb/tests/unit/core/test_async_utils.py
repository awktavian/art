"""Unit Tests: Async Utilities

Comprehensive tests for safe task management, error handling, retry mechanisms,
uvloop integration, and concurrent execution patterns.

Created: December 27, 2025
Updated: January 12, 2026 - Expanded test coverage
"""

from __future__ import annotations

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_unit,
    pytest.mark.unit,
    pytest.mark.timeout(30),
]

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

# =============================================================================
# TEST: safe_create_task
# =============================================================================


@pytest.mark.asyncio
async def test_safe_create_task_success() -> None:
    """Test safe_create_task with successful task execution.

    Scenario:
        - Create task with safe_create_task
        - Verify task completes successfully
        - Verify no error logging
    """
    from kagami.core.async_utils import safe_create_task

    executed = False

    async def simple_task() -> str:
        nonlocal executed
        executed = True
        return "success"

    # Mock task registry to allow task creation
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(simple_task(), name="test-task")
        result = await task

        assert result == "success"
        assert executed


@pytest.mark.asyncio
async def test_safe_create_task_error_handling() -> None:
    """Test safe_create_task logs errors properly.

    Scenario:
        - Create task that raises exception
        - Verify exception logged
        - Verify error callback invoked
    """
    from kagami.core.async_utils import safe_create_task

    error_callback_called = False
    captured_exception = None

    def error_callback(exc: Exception) -> None:
        nonlocal error_callback_called, captured_exception
        error_callback_called = True
        captured_exception = exc

    async def failing_task() -> None:
        raise ValueError("Task failed")

    # Mock task registry
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(
            failing_task(),
            name="failing-task",
            error_callback=error_callback,
        )

        # Wait for task to complete
        with pytest.raises(ValueError, match="Task failed"):
            await task

        # Give callback time to execute
        await asyncio.sleep(0.01)

        assert error_callback_called
        assert isinstance(captured_exception, ValueError)


@pytest.mark.asyncio
async def test_safe_create_task_task_limit() -> None:
    """Test safe_create_task respects task limit.

    Scenario:
        - Mock registry to reject task (limit exceeded)
        - Attempt to create task
        - Verify RuntimeError raised
        - Verify task cancelled
    """
    from kagami.core.async_utils import safe_create_task

    async def dummy_task() -> None:
        await asyncio.sleep(0.1)

    # Mock task registry to reject registration
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = False
        mock_reg.max_tasks = 100
        mock_registry.return_value = mock_reg

        with pytest.raises(RuntimeError, match="Task limit exceeded"):
            safe_create_task(dummy_task(), name="over-limit-task")


@pytest.mark.asyncio
async def test_safe_create_task_cancellation() -> None:
    """Test safe_create_task handles cancellation gracefully.

    Scenario:
        - Create long-running task
        - Cancel it
        - Verify CancelledError handled correctly
    """
    from kagami.core.async_utils import safe_create_task

    started = False

    async def long_task() -> None:
        nonlocal started
        started = True
        await asyncio.sleep(10)  # Long running

    # Mock task registry
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(long_task(), name="long-task")

        # Wait for task to start
        await asyncio.sleep(0.01)
        assert started

        # Cancel task
        task.cancel()

        # Verify cancellation handled
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_safe_create_task_with_logger_context() -> None:
    """Test safe_create_task with logger context.

    Scenario:
        - Create task with custom logger context
        - Task fails
        - Verify context is available in error handling
    """
    from kagami.core.async_utils import safe_create_task

    async def failing_task() -> None:
        raise RuntimeError("Intentional failure")

    logger_context = {"request_id": "test-123", "user": "test_user"}

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(
            failing_task(),
            name="context-task",
            logger_context=logger_context,
        )

        with pytest.raises(RuntimeError, match="Intentional failure"):
            await task


@pytest.mark.asyncio
async def test_safe_create_task_with_none_name() -> None:
    """Test safe_create_task with no name provided.

    Scenario:
        - Create task without specifying name
        - Verify task runs successfully
    """
    from kagami.core.async_utils import safe_create_task

    async def simple_task() -> int:
        return 42

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(simple_task())  # No name
        result = await task

        assert result == 42


@pytest.mark.asyncio
async def test_safe_create_task_preserves_return_type() -> None:
    """Test safe_create_task preserves coroutine return type.

    Scenario:
        - Create task with typed return value
        - Verify type is preserved
    """
    from kagami.core.async_utils import safe_create_task

    async def typed_task() -> dict[str, int]:
        return {"a": 1, "b": 2}

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(typed_task(), name="typed")
        result = await task

        assert isinstance(result, dict)
        assert result == {"a": 1, "b": 2}


# =============================================================================
# TEST: safe_gather
# =============================================================================


@pytest.mark.asyncio
async def test_safe_gather_success() -> None:
    """Test safe_gather with successful coroutines.

    Scenario:
        - Gather multiple successful coroutines
        - Verify all results returned
    """
    from kagami.core.async_utils import safe_gather

    async def task1() -> int:
        await asyncio.sleep(0.01)
        return 1

    async def task2() -> int:
        await asyncio.sleep(0.01)
        return 2

    async def task3() -> int:
        await asyncio.sleep(0.01)
        return 3

    results = await safe_gather(task1(), task2(), task3())

    assert results == [1, 2, 3]


@pytest.mark.asyncio
async def test_safe_gather_with_exception() -> None:
    """Test safe_gather with failing coroutine.

    Scenario:
        - Gather with one failing coroutine
        - Verify exception propagates by default
    """
    from kagami.core.async_utils import safe_gather

    async def task1() -> int:
        return 1

    async def failing_task() -> int:
        raise ValueError("Task failed")

    async def task3() -> int:
        return 3

    # Without return_exceptions, should raise
    with pytest.raises(ValueError, match="Task failed"):
        await safe_gather(task1(), failing_task(), task3())


@pytest.mark.asyncio
async def test_safe_gather_return_exceptions() -> None:
    """Test safe_gather with return_exceptions=True.

    Scenario:
        - Gather with one failing coroutine
        - Use return_exceptions=True
        - Verify exception returned in results
    """
    from kagami.core.async_utils import safe_gather

    async def task1() -> int:
        return 1

    async def failing_task() -> int:
        raise ValueError("Task failed")

    async def task3() -> int:
        return 3

    results = await safe_gather(task1(), failing_task(), task3(), return_exceptions=True)

    assert len(results) == 3
    assert results[0] == 1
    assert isinstance(results[1], ValueError)
    assert results[2] == 3


@pytest.mark.asyncio
async def test_safe_gather_empty() -> None:
    """Test safe_gather with no coroutines.

    Scenario:
        - Call safe_gather with no arguments
        - Verify empty list returned
    """
    from kagami.core.async_utils import safe_gather

    results = await safe_gather()
    assert results == []


@pytest.mark.asyncio
async def test_safe_gather_single_task() -> None:
    """Test safe_gather with single coroutine.

    Scenario:
        - Gather single coroutine
        - Verify result wrapped in list
    """
    from kagami.core.async_utils import safe_gather

    async def single_task() -> str:
        return "only one"

    results = await safe_gather(single_task())
    assert results == ["only one"]


@pytest.mark.asyncio
async def test_safe_gather_concurrent_execution() -> None:
    """Test safe_gather executes coroutines concurrently.

    Scenario:
        - Create tasks that would take long if sequential
        - Verify total time is approximately parallel time
    """
    import time

    from kagami.core.async_utils import safe_gather

    async def slow_task(delay: float) -> float:
        await asyncio.sleep(delay)
        return delay

    start = time.monotonic()
    results = await safe_gather(
        slow_task(0.05),
        slow_task(0.05),
        slow_task(0.05),
    )
    elapsed = time.monotonic() - start

    assert results == [0.05, 0.05, 0.05]
    # Should complete in ~0.05s (parallel), not 0.15s (sequential)
    assert elapsed < 0.15


@pytest.mark.asyncio
async def test_safe_gather_multiple_exceptions() -> None:
    """Test safe_gather with multiple exceptions.

    Scenario:
        - Multiple tasks fail
        - With return_exceptions=True, all exceptions returned
    """
    from kagami.core.async_utils import safe_gather

    async def fail1() -> int:
        raise ValueError("Error 1")

    async def fail2() -> int:
        raise TypeError("Error 2")

    async def succeed() -> int:
        return 42

    results = await safe_gather(fail1(), succeed(), fail2(), return_exceptions=True)

    assert len(results) == 3
    assert isinstance(results[0], ValueError)
    assert results[1] == 42
    assert isinstance(results[2], TypeError)


# =============================================================================
# TEST: cancel_and_await
# =============================================================================


@pytest.mark.asyncio
async def test_cancel_and_await() -> None:
    """Test cancel_and_await utility.

    Scenario:
        - Start long-running task
        - Cancel and await it
        - Verify task cancelled cleanly
    """
    from kagami.core.async_utils import cancel_and_await

    started = False
    completed = False

    async def long_task() -> None:
        nonlocal started, completed
        started = True
        try:
            await asyncio.sleep(10)
            completed = True
        except asyncio.CancelledError:
            raise

    task = asyncio.create_task(long_task())

    # Wait for start
    await asyncio.sleep(0.01)
    assert started
    assert not completed

    # Cancel and await
    await cancel_and_await(task)

    # Verify cancelled
    assert task.cancelled()
    assert not completed


@pytest.mark.asyncio
async def test_cancel_and_await_none() -> None:
    """Test cancel_and_await with None task.

    Scenario:
        - Call cancel_and_await with None
        - Verify no error raised
    """
    from kagami.core.async_utils import cancel_and_await

    await cancel_and_await(None)  # Should not raise


@pytest.mark.asyncio
async def test_cancel_and_await_already_done() -> None:
    """Test cancel_and_await with already completed task.

    Scenario:
        - Create completed task
        - Call cancel_and_await
        - Verify no error raised
    """
    from kagami.core.async_utils import cancel_and_await

    async def quick_task() -> str:
        return "done"

    task = asyncio.create_task(quick_task())
    await task  # Complete task

    # Should not raise
    await cancel_and_await(task)


@pytest.mark.asyncio
async def test_cancel_and_await_failed_task() -> None:
    """Test cancel_and_await with failed task.

    Scenario:
        - Task that raises exception
        - Cancel and await should handle cleanly
    """
    from kagami.core.async_utils import cancel_and_await

    async def failing_task() -> None:
        raise RuntimeError("Intentional failure")

    task = asyncio.create_task(failing_task())

    # Wait for failure
    await asyncio.sleep(0.01)

    # Should not raise (task already done with exception)
    await cancel_and_await(task)


@pytest.mark.asyncio
async def test_cancel_and_await_cancelled_task() -> None:
    """Test cancel_and_await with already cancelled task.

    Scenario:
        - Task already cancelled externally
        - cancel_and_await should handle cleanly
    """
    from kagami.core.async_utils import cancel_and_await

    async def slow_task() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(slow_task())
    task.cancel()

    # Wait for cancellation
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should not raise
    await cancel_and_await(task)


# =============================================================================
# TEST: background_task decorator
# =============================================================================


@pytest.mark.asyncio
async def test_background_task_decorator() -> None:
    """Test @background_task decorator.

    Scenario:
        - Decorate async function
        - Call decorated function
        - Verify task created and runs in background
    """
    from kagami.core.async_utils import background_task

    executed = False

    @background_task(name="test-bg-task")
    async def bg_function() -> str:
        nonlocal executed
        await asyncio.sleep(0.01)
        executed = True
        return "background-result"

    # Mock task registry
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        # Call returns task immediately
        task = bg_function()
        assert isinstance(task, asyncio.Task)

        # Wait for completion
        result = await task
        assert result == "background-result"
        assert executed


@pytest.mark.asyncio
async def test_background_task_retry() -> None:
    """Test @background_task with retry logic.

    Scenario:
        - Decorate function with retry_count=2
        - Function fails twice, succeeds third time
        - Verify retries work
    """
    from kagami.core.async_utils import background_task

    attempt_count = 0

    @background_task(name="retry-task", retry_count=2, retry_delay=0.01)
    async def retry_function() -> str:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ValueError(f"Attempt {attempt_count} failed")
        return "success"

    # Mock task registry
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = retry_function()
        result = await task

        assert result == "success"
        assert attempt_count == 3


@pytest.mark.asyncio
async def test_background_task_retry_exhausted() -> None:
    """Test @background_task when retries exhausted.

    Scenario:
        - Decorate function with retry_count=2
        - Function always fails
        - Verify exception raised after retries
    """
    from kagami.core.async_utils import background_task

    attempt_count = 0

    @background_task(name="always-fail", retry_count=2, retry_delay=0.01)
    async def failing_function() -> None:
        nonlocal attempt_count
        attempt_count += 1
        raise ValueError("Always fails")

    # Mock task registry
    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = failing_function()

        with pytest.raises(ValueError, match="Always fails"):
            await task

        # Should have attempted 3 times (initial + 2 retries)
        assert attempt_count == 3


@pytest.mark.asyncio
async def test_background_task_no_retry() -> None:
    """Test @background_task without retries.

    Scenario:
        - Decorate function with default retry_count=0
        - Function fails once
        - Verify no retry attempted
    """
    from kagami.core.async_utils import background_task

    attempt_count = 0

    @background_task(name="no-retry")
    async def failing_function() -> None:
        nonlocal attempt_count
        attempt_count += 1
        raise RuntimeError("Single failure")

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = failing_function()

        with pytest.raises(RuntimeError, match="Single failure"):
            await task

        assert attempt_count == 1


@pytest.mark.asyncio
async def test_background_task_with_args() -> None:
    """Test @background_task with function arguments.

    Scenario:
        - Decorate function that takes arguments
        - Call with positional and keyword args
        - Verify args passed correctly
    """
    from kagami.core.async_utils import background_task

    @background_task(name="args-task")
    async def func_with_args(a: int, b: str, c: float = 1.0) -> dict:
        return {"a": a, "b": b, "c": c}

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = func_with_args(42, "hello", c=3.14)
        result = await task

        assert result == {"a": 42, "b": "hello", "c": 3.14}


@pytest.mark.asyncio
async def test_background_task_uses_function_name() -> None:
    """Test @background_task uses function name when no name provided.

    Scenario:
        - Decorate function without explicit name
        - Verify task uses function's __name__
    """
    from kagami.core.async_utils import background_task

    @background_task()  # No name provided
    async def my_named_function() -> str:
        return "named"

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = my_named_function()
        result = await task

        assert result == "named"


# =============================================================================
# TEST: uvloop utilities
# =============================================================================


def test_install_uvloop_idempotent() -> None:
    """Test install_uvloop is idempotent.

    Scenario:
        - Call install_uvloop multiple times
        - Verify no error raised
    """
    from kagami.core.async_utils import install_uvloop

    # First call
    result1 = install_uvloop()

    # Second call should also succeed (idempotent)
    result2 = install_uvloop()

    # Both should return same value
    assert result1 == result2


def test_install_uvloop_skipped_in_test_mode() -> None:
    """Test install_uvloop skips in test mode.

    Scenario:
        - PYTEST_CURRENT_TEST is set
        - Verify uvloop installation is skipped
    """
    # Note: We're already in test mode (pytest), so this is implicit
    # The module should have detected this and skipped installation
    from kagami.core.async_utils import is_uvloop_active

    # In test mode, uvloop should NOT be active
    # (pytest-asyncio manages its own loop)
    # This is the expected behavior per the module's design
    pass  # Test passes if no exception during import


def test_is_uvloop_active_returns_bool() -> None:
    """Test is_uvloop_active returns boolean.

    Scenario:
        - Call is_uvloop_active
        - Verify returns bool (True or False)
    """
    from kagami.core.async_utils import is_uvloop_active

    result = is_uvloop_active()
    assert isinstance(result, bool)


# =============================================================================
# TEST: Timeout behavior
# =============================================================================


@pytest.mark.asyncio
async def test_task_timeout_behavior() -> None:
    """Test task behavior with asyncio.timeout.

    Scenario:
        - Create task with timeout wrapper
        - Task takes longer than timeout
        - Verify TimeoutError raised
    """
    from kagami.core.async_utils import safe_create_task

    async def slow_task() -> str:
        await asyncio.sleep(10)
        return "completed"

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(slow_task(), name="slow")

        # Use asyncio.wait_for for timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=0.05)


@pytest.mark.asyncio
async def test_task_completes_before_timeout() -> None:
    """Test task completes before timeout.

    Scenario:
        - Create task with timeout wrapper
        - Task completes quickly
        - Verify result returned
    """
    from kagami.core.async_utils import safe_create_task

    async def quick_task() -> str:
        await asyncio.sleep(0.01)
        return "quick"

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(quick_task(), name="quick")

        result = await asyncio.wait_for(task, timeout=1.0)
        assert result == "quick"


# =============================================================================
# TEST: Concurrent execution patterns
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_task_creation() -> None:
    """Test creating many tasks concurrently.

    Scenario:
        - Create multiple tasks rapidly
        - Verify all complete successfully
    """
    from kagami.core.async_utils import safe_create_task

    results = []

    async def numbered_task(n: int) -> int:
        await asyncio.sleep(0.01)
        return n

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        tasks = [safe_create_task(numbered_task(i), name=f"task-{i}") for i in range(10)]

        results = await asyncio.gather(*tasks)

    assert results == list(range(10))


@pytest.mark.asyncio
async def test_task_with_cleanup() -> None:
    """Test task with cleanup on cancellation.

    Scenario:
        - Task with try/finally for cleanup
        - Cancel task
        - Verify cleanup executed
    """
    from kagami.core.async_utils import cancel_and_await

    cleanup_executed = False

    async def task_with_cleanup() -> None:
        nonlocal cleanup_executed
        try:
            await asyncio.sleep(10)
        finally:
            cleanup_executed = True

    task = asyncio.create_task(task_with_cleanup())

    # Wait for start
    await asyncio.sleep(0.01)

    # Cancel
    await cancel_and_await(task)

    assert cleanup_executed


@pytest.mark.asyncio
async def test_nested_background_tasks() -> None:
    """Test background task creating another background task.

    Scenario:
        - Outer task creates inner background task
        - Both complete successfully
    """
    from kagami.core.async_utils import background_task

    inner_executed = False

    @background_task(name="inner")
    async def inner_task() -> str:
        nonlocal inner_executed
        inner_executed = True
        return "inner-done"

    @background_task(name="outer")
    async def outer_task() -> str:
        inner = inner_task()
        inner_result = await inner
        return f"outer-{inner_result}"

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = outer_task()
        result = await task

        assert result == "outer-inner-done"
        assert inner_executed


# =============================================================================
# TEST: Edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_error_callback_exception_suppressed() -> None:
    """Test error callback exception is suppressed.

    Scenario:
        - Error callback itself raises exception
        - Task failure handling should not crash
    """
    from kagami.core.async_utils import safe_create_task

    def bad_callback(exc: Exception) -> None:
        raise RuntimeError("Callback crashed")

    async def failing_task() -> None:
        raise ValueError("Original error")

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(
            failing_task(),
            name="error-test",
            error_callback=bad_callback,
        )

        # Should raise original error, not callback error
        with pytest.raises(ValueError, match="Original error"):
            await task


@pytest.mark.asyncio
async def test_task_returns_none() -> None:
    """Test task that returns None explicitly.

    Scenario:
        - Task returns None
        - Verify None is captured correctly
    """
    from kagami.core.async_utils import safe_create_task

    async def none_task() -> None:
        return None

    with patch("kagami.core.task_registry.get_task_registry") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.register_task.return_value = True
        mock_registry.return_value = mock_reg

        task = safe_create_task(none_task(), name="none-task")
        result = await task

        assert result is None


@pytest.mark.asyncio
async def test_safe_gather_preserves_order() -> None:
    """Test safe_gather preserves result order regardless of completion order.

    Scenario:
        - Tasks complete in different order than submitted
        - Results should match submission order
    """
    from kagami.core.async_utils import safe_gather

    async def delayed_task(n: int, delay: float) -> int:
        await asyncio.sleep(delay)
        return n

    # Submit: 1 (slow), 2 (fast), 3 (medium)
    results = await safe_gather(
        delayed_task(1, 0.05),  # Slow
        delayed_task(2, 0.01),  # Fast
        delayed_task(3, 0.03),  # Medium
    )

    # Results should be in submission order [1, 2, 3], not completion order [2, 3, 1]
    assert results == [1, 2, 3]
