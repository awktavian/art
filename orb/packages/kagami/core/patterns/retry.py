"""Retry Pattern with Exponential Backoff.

Provides resilient retry logic for transient failures with
configurable backoff strategies and jitter.

Example:
    >>> @retry(max_attempts=5, base_delay=1.0)
    ... async def fetch_data():
    ...     return await api.get("/data")
"""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)


T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Multiplier for exponential backoff.
        jitter: Random jitter range (0-1).
        retryable_exceptions: Tuple of exception types to retry.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


def calculate_backoff(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: float,
) -> float:
    """Calculate delay with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (0-indexed).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        exponential_base: Multiplier for each attempt.
        jitter: Random variation (0-1).

    Returns:
        Delay in seconds with jitter applied.

    Example:
        >>> delay = calculate_backoff(3, 1.0, 60.0, 2.0, 0.1)
        >>> # Returns approximately 8.0 seconds (2^3 * 1.0) with jitter
    """
    # Exponential backoff: base_delay * exponential_base^attempt
    delay = base_delay * (exponential_base**attempt)

    # Apply cap
    delay = min(delay, max_delay)

    # Add jitter (±jitter%)
    jitter_range = delay * jitter
    delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)  # Ensure non-negative


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        exponential_base: Multiplier for backoff.
        jitter: Random jitter range.
        retryable_exceptions: Exceptions to retry on.
        on_retry: Callback called on each retry.

    Returns:
        Decorated function with retry logic.

    Example:
        >>> @retry(max_attempts=5, base_delay=1.0)
        ... async def call_api():
        ...     return await http.get(url)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    delay = calculate_backoff(
                        attempt=attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/"
                        f"{max_attempts}): {e}. Retrying in {delay:.2f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt + 1)

                    await asyncio.sleep(delay)

            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop completed without success or exception")

        return wrapper

    return decorator


class RetryContext:
    """Context manager for retry with exponential backoff.

    Provides more control than the decorator for complex retry scenarios.

    Attributes:
        config: Retry configuration.
        attempt: Current attempt number.

    Example:
        >>> async with RetryContext(max_attempts=5) as ctx:
        ...     while ctx.should_retry():
        ...         try:
        ...             result = await call_api()
        ...             break
        ...         except Exception as e:
        ...             await ctx.wait(e)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: float = 0.1,
    ) -> None:
        """Initialize retry context.

        Args:
            max_attempts: Maximum number of attempts.
            base_delay: Initial delay in seconds.
            max_delay: Maximum delay cap.
            exponential_base: Multiplier for backoff.
            jitter: Random jitter range.
        """
        self.config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
        )
        self.attempt = 0
        self._last_exception: Exception | None = None

    async def __aenter__(self) -> "RetryContext":
        """Enter retry context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit retry context."""
        pass

    def should_retry(self) -> bool:
        """Check if another retry attempt should be made.

        Returns:
            True if more attempts are available.
        """
        return self.attempt < self.config.max_attempts

    async def wait(self, exception: Exception) -> None:
        """Wait with backoff after a failure.

        Args:
            exception: The exception that caused the failure.

        Raises:
            Exception: If no more retries available.
        """
        self._last_exception = exception
        self.attempt += 1

        if self.attempt >= self.config.max_attempts:
            raise exception

        delay = calculate_backoff(
            attempt=self.attempt - 1,
            base_delay=self.config.base_delay,
            max_delay=self.config.max_delay,
            exponential_base=self.config.exponential_base,
            jitter=self.config.jitter,
        )

        logger.warning(
            f"Retry {self.attempt}/{self.config.max_attempts} after {delay:.2f}s: {exception}"
        )

        await asyncio.sleep(delay)


# Common retry configurations
RETRY_AGGRESSIVE = RetryConfig(
    max_attempts=10,
    base_delay=0.5,
    max_delay=30.0,
    exponential_base=1.5,
)

RETRY_CONSERVATIVE = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
)

RETRY_QUICK = RetryConfig(
    max_attempts=5,
    base_delay=0.1,
    max_delay=5.0,
    exponential_base=2.0,
)
