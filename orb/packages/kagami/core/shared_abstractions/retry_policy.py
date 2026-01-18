"""Unified RetryPolicy Abstraction.

Provides a single, configurable retry mechanism for all async operations
across the Kagami codebase. Consolidates 10+ different retry implementations
into one robust, well-typed abstraction.

Usage:
    # Simple usage with defaults
    policy = RetryPolicy()
    result = await policy.execute(fetch_data)

    # With custom configuration
    policy = RetryPolicy(
        max_attempts=5,
        base_delay=0.5,
        exponential_backoff=True,
        on_retry=lambda e, attempt: logger.warning(f"Retry {attempt}: {e}")
    )
    result = await policy.execute(unreliable_api_call, arg1, arg2)

    # With specific exception handling
    policy = RetryPolicy(
        retryable_exceptions=(ConnectionError, TimeoutError),
        on_retry=log_retry_to_metrics
    )

    # As a decorator
    @retry_with_policy(max_attempts=3)
    async def my_function():
        ...

Created: January 12, 2026
Consolidates: patterns/retry.py, error_handling retry logic, database retry patterns
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Generic, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class BackoffStrategy(Enum):
    """Backoff strategy options for retry delays."""

    FIXED = "fixed"
    """Use constant delay between retries."""

    LINEAR = "linear"
    """Increase delay linearly: base_delay * attempt."""

    EXPONENTIAL = "exponential"
    """Increase delay exponentially: base_delay * (multiplier ^ attempt)."""

    EXPONENTIAL_JITTER = "exponential_jitter"
    """Exponential backoff with random jitter to prevent thundering herd."""


@dataclass(frozen=True)
class RetryPolicy(Generic[T]):
    """Unified retry policy configuration and executor.

    Immutable configuration that can be shared across multiple operations.
    The execute() method wraps any async operation with retry logic.

    Attributes:
        max_attempts: Maximum number of execution attempts (including first try).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay cap in seconds.
        backoff_strategy: How to calculate increasing delays.
        backoff_multiplier: Multiplier for exponential backoff (default 2.0).
        jitter: Random jitter factor (0.0-1.0) for delay variation.
        retryable_exceptions: Tuple of exception types that trigger retry.
        on_retry: Optional callback invoked before each retry.
        on_success: Optional callback invoked on successful completion.
        on_failure: Optional callback invoked when all retries exhausted.
        name: Optional name for logging/debugging.

    Example:
        >>> policy = RetryPolicy(
        ...     max_attempts=5,
        ...     base_delay=1.0,
        ...     backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
        ...     retryable_exceptions=(ConnectionError, TimeoutError),
        ...     on_retry=lambda e, n: print(f"Retry {n}: {e}")
        ... )
        >>> result = await policy.execute(unreliable_operation)
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    backoff_multiplier: float = 2.0
    jitter: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)
    on_retry: (
        Callable[[Exception, int], None] | Callable[[Exception, int], Awaitable[None]] | None
    ) = None
    on_success: Callable[[T, int], None] | Callable[[T, int], Awaitable[None]] | None = None
    on_failure: (
        Callable[[Exception, int], None] | Callable[[Exception, int], Awaitable[None]] | None
    ) = None
    name: str | None = None

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds before next retry.
        """
        if self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.base_delay
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.backoff_multiplier**attempt)
        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            base = self.base_delay * (self.backoff_multiplier**attempt)
            jitter_range = base * self.jitter
            delay = base + random.uniform(-jitter_range, jitter_range)
        else:
            delay = self.base_delay

        return max(0.0, min(delay, self.max_delay))

    async def execute(
        self,
        func: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute an async function with retry logic.

        Args:
            func: Async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Result of the function call.

        Raises:
            Exception: The last exception if all retries are exhausted.

        Example:
            >>> async def fetch_data():
            ...     return await api.get("/data")
            >>> policy = RetryPolicy(max_attempts=5)
            >>> data = await policy.execute(fetch_data)
        """
        last_exception: Exception | None = None
        func_name = self.name or getattr(func, "__name__", "unknown")

        for attempt in range(self.max_attempts):
            try:
                result = await func(*args, **kwargs)

                # Invoke success callback
                if self.on_success:
                    callback_result = self.on_success(result, attempt + 1)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result

                if attempt > 0:
                    logger.info(
                        f"[{func_name}] Succeeded on attempt {attempt + 1}/{self.max_attempts}"
                    )

                return result

            except self.retryable_exceptions as exc:
                last_exception = exc

                if attempt == self.max_attempts - 1:
                    # Last attempt failed - invoke failure callback
                    logger.error(f"[{func_name}] Failed after {self.max_attempts} attempts: {exc}")
                    if self.on_failure:
                        callback_result = self.on_failure(exc, self.max_attempts)
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
                    raise

                delay = self.calculate_delay(attempt)

                logger.warning(
                    f"[{func_name}] Attempt {attempt + 1}/{self.max_attempts} failed: {exc}. "
                    f"Retrying in {delay:.2f}s..."
                )

                # Invoke retry callback
                if self.on_retry:
                    callback_result = self.on_retry(exc, attempt + 1)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result

                await asyncio.sleep(delay)

        # Should never reach here, but satisfy type checker
        if last_exception:
            raise last_exception
        raise RuntimeError(f"[{func_name}] Retry loop completed without success or exception")

    def with_overrides(self, **kwargs: Any) -> RetryPolicy[T]:
        """Create a new policy with some values overridden.

        Useful for deriving specialized policies from a base configuration.

        Args:
            **kwargs: Values to override in the new policy.

        Returns:
            New RetryPolicy with specified overrides.

        Example:
            >>> base = RetryPolicy(max_attempts=3)
            >>> aggressive = base.with_overrides(max_attempts=10, base_delay=0.1)
        """
        current = {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_strategy": self.backoff_strategy,
            "backoff_multiplier": self.backoff_multiplier,
            "jitter": self.jitter,
            "retryable_exceptions": self.retryable_exceptions,
            "on_retry": self.on_retry,
            "on_success": self.on_success,
            "on_failure": self.on_failure,
            "name": self.name,
        }
        current.update(kwargs)
        return RetryPolicy(**current)


# ============================================================================
# Pre-configured Policy Templates
# ============================================================================

RETRY_AGGRESSIVE = RetryPolicy(
    max_attempts=10,
    base_delay=0.5,
    max_delay=30.0,
    backoff_multiplier=1.5,
    jitter=0.2,
    name="aggressive",
)
"""Aggressive retry for critical operations: 10 attempts, fast initial retry."""

RETRY_CONSERVATIVE = RetryPolicy(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    backoff_multiplier=2.0,
    jitter=0.1,
    name="conservative",
)
"""Conservative retry for rate-limited APIs: 3 attempts, slow backoff."""

RETRY_QUICK = RetryPolicy(
    max_attempts=5,
    base_delay=0.1,
    max_delay=5.0,
    backoff_multiplier=2.0,
    jitter=0.1,
    name="quick",
)
"""Quick retry for fast-recovering services: 5 attempts, very short delays."""

RETRY_DATABASE = RetryPolicy(
    max_attempts=5,
    base_delay=0.05,
    max_delay=2.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
    backoff_multiplier=2.0,
    jitter=0.5,  # Higher jitter to prevent thundering herd
    name="database",
)
"""Database retry policy optimized for serialization conflicts."""

RETRY_NETWORK = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    name="network",
)
"""Network retry policy for external API calls."""


# ============================================================================
# Decorator Interface
# ============================================================================


def retry_with_policy(
    policy: RetryPolicy | None = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER,
    backoff_multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None]
    | Callable[[Exception, int], Awaitable[None]]
    | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to apply retry policy to an async function.

    Can accept a pre-configured policy or keyword arguments to create one.

    Args:
        policy: Optional pre-configured RetryPolicy to use.
        max_attempts: Maximum retry attempts (if not using policy).
        base_delay: Base delay between retries (if not using policy).
        max_delay: Maximum delay cap (if not using policy).
        backoff_strategy: Backoff strategy (if not using policy).
        backoff_multiplier: Exponential multiplier (if not using policy).
        jitter: Jitter factor (if not using policy).
        retryable_exceptions: Exceptions to retry on (if not using policy).
        on_retry: Callback for each retry (if not using policy).

    Returns:
        Decorated function with retry logic.

    Example:
        >>> @retry_with_policy(max_attempts=5)
        ... async def fetch_data():
        ...     return await api.get("/data")

        >>> @retry_with_policy(policy=RETRY_AGGRESSIVE)
        ... async def critical_operation():
        ...     ...
    """
    if policy is None:
        policy = RetryPolicy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_strategy=backoff_strategy,
            backoff_multiplier=backoff_multiplier,
            jitter=jitter,
            retryable_exceptions=retryable_exceptions,
            on_retry=on_retry,
        )

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        # Use function name for logging
        named_policy = policy.with_overrides(name=func.__name__) if policy.name is None else policy

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await named_policy.execute(func, *args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# Context Manager Interface
# ============================================================================


@dataclass
class RetryContext:
    """Context manager for fine-grained retry control.

    Provides manual control over the retry loop for complex scenarios
    where the decorator pattern is insufficient.

    Attributes:
        policy: The retry policy configuration.
        attempt: Current attempt number (1-indexed).

    Example:
        >>> async with RetryContext(max_attempts=5) as ctx:
        ...     while ctx.should_retry():
        ...         try:
        ...             result = await risky_operation()
        ...             break
        ...         except Exception as e:
        ...             await ctx.handle_error(e)
    """

    policy: RetryPolicy = field(default_factory=RetryPolicy)
    attempt: int = 0
    _last_exception: Exception | None = field(default=None, init=False, repr=False)

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        *,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER,
    ) -> None:
        """Initialize retry context.

        Args:
            policy: Pre-configured policy (takes precedence).
            max_attempts: Maximum attempts if not using policy.
            base_delay: Base delay if not using policy.
            max_delay: Max delay if not using policy.
            backoff_strategy: Backoff strategy if not using policy.
        """
        if policy is not None:
            self.policy = policy
        else:
            self.policy = RetryPolicy(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_strategy=backoff_strategy,
            )
        self.attempt = 0
        self._last_exception = None

    async def __aenter__(self) -> RetryContext:
        """Enter the retry context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the retry context."""
        return False  # Don't suppress exceptions

    def should_retry(self) -> bool:
        """Check if another retry attempt is available.

        Returns:
            True if more attempts are available.
        """
        return self.attempt < self.policy.max_attempts

    async def handle_error(self, exception: Exception) -> None:
        """Handle an error and wait before next retry.

        Args:
            exception: The exception that occurred.

        Raises:
            Exception: If no more retries are available.
        """
        self._last_exception = exception
        self.attempt += 1

        if self.attempt >= self.policy.max_attempts:
            logger.error(f"Retry exhausted after {self.policy.max_attempts} attempts: {exception}")
            raise exception

        delay = self.policy.calculate_delay(self.attempt - 1)

        logger.warning(
            f"Attempt {self.attempt}/{self.policy.max_attempts} failed: {exception}. "
            f"Retrying in {delay:.2f}s..."
        )

        # Invoke retry callback if configured
        if self.policy.on_retry:
            callback_result = self.policy.on_retry(exception, self.attempt)
            if asyncio.iscoroutine(callback_result):
                await callback_result

        await asyncio.sleep(delay)


# ============================================================================
# Utility Functions
# ============================================================================


def is_retryable(
    exception: Exception,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> bool:
    """Check if an exception is retryable.

    Args:
        exception: The exception to check.
        retryable_exceptions: Tuple of retryable exception types.

    Returns:
        True if the exception should trigger a retry.
    """
    return isinstance(exception, retryable_exceptions)


async def execute_with_retry(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
    **kwargs: Any,
) -> T:
    """Execute a function with retry logic (convenience function).

    For simple cases where creating a RetryPolicy object is overkill.

    Args:
        func: Async function to execute.
        *args: Positional arguments for the function.
        max_attempts: Maximum number of attempts.
        base_delay: Base delay between retries.
        retryable_exceptions: Exceptions that trigger retry.
        on_retry: Optional callback on each retry.
        **kwargs: Keyword arguments for the function.

    Returns:
        Result of the function call.

    Example:
        >>> result = await execute_with_retry(
        ...     fetch_data,
        ...     max_attempts=3,
        ...     retryable_exceptions=(ConnectionError,)
        ... )
    """
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        retryable_exceptions=retryable_exceptions,
        on_retry=on_retry,
        name=getattr(func, "__name__", "unknown"),
    )
    return await policy.execute(func, *args, **kwargs)


__all__ = [
    # Pre-configured policies
    "RETRY_AGGRESSIVE",
    "RETRY_CONSERVATIVE",
    "RETRY_DATABASE",
    "RETRY_NETWORK",
    "RETRY_QUICK",
    "BackoffStrategy",
    "RetryContext",
    # Core classes
    "RetryPolicy",
    # Utilities
    "execute_with_retry",
    "is_retryable",
    # Decorator
    "retry_with_policy",
]
