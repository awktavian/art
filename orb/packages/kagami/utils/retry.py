"""
Unified Retry Utility - Single Source of Truth for Retry Logic

Consolidates 5+ retry implementations across K os and GAIA into
a single, consistent, well-tested utility.

Previous implementations:
- mcp_servers/mcp_utils.py (MCPRetryPolicy)
- kagami/core/services/forge/utils/error_handling.py (log_and_reraise)
- gaia/utils/error_handling.py (retry_on_error)
- gaia/core/retry_manager.py
- kagami/core/http_client.py (custom retry)

All new code should use this module.
"""

import asyncio
import functools
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

# Import from central exception hierarchy
from kagami.core.exceptions import RetryExhaustedError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class UnifiedRetryPolicy:
    """
    Consistent retry logic across K os and GAIA.

    Features:
    - Exponential backoff with jitter
    - Configurable max attempts and timeouts
    - Presets for common scenarios (LLM, API, DB)
    - Both sync and async support
    - Error classification (retriable vs. fatal)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        timeout: float | None = None,
        retriable_exceptions: tuple[Any, ...] = (Exception,),
        fatal_exceptions: tuple[Any, ...] = (),
    ) -> None:
        """
        Initialize retry policy.

        Args:
            max_attempts: Maximum number of attempts (including first)
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff (2.0 = double each time)
            jitter: Add randomness to delay (recommended)
            timeout: Total timeout for all attempts (None = no limit)
            retriable_exceptions: Exceptions that trigger retry
            fatal_exceptions: Exceptions that abort immediately
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.timeout = timeout
        self.retriable_exceptions = retriable_exceptions
        self.fatal_exceptions = fatal_exceptions

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        delay = self.base_delay * self.exponential_base**attempt
        delay = min(delay, self.max_delay)
        if self.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        return max(0.1, delay)

    def is_retriable(self, exception: Exception) -> bool:
        """Check if exception should trigger retry."""
        if isinstance(exception, self.fatal_exceptions):
            return False
        return isinstance(exception, self.retriable_exceptions)

    def __call__(self, func: Callable) -> Callable:
        """Decorator for synchronous functions."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            last_exception = None
            for attempt in range(self.max_attempts):
                try:
                    if self.timeout:
                        elapsed = time.time() - start_time
                        if elapsed >= self.timeout:
                            raise RetryExhaustedError(
                                f"Timeout exceeded: {elapsed:.1f}s >= {self.timeout}s"
                            )
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt + 1}")
                    return result
                except Exception as e:
                    last_exception = e
                    if not self.is_retriable(e):
                        logger.error(f"❌ {func.__name__} failed with fatal error: {e}")
                        raise
                    if attempt >= self.max_attempts - 1:
                        break
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"⚠️  {func.__name__} failed (attempt {attempt + 1}/{self.max_attempts}): {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            raise RetryExhaustedError(
                f"Max retries ({self.max_attempts}) exceeded"
            ) from last_exception

        return wrapper

    def async_decorator(self, func: Callable) -> Callable:
        """Decorator for async functions."""

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            last_exception = None
            for attempt in range(self.max_attempts):
                try:
                    if self.timeout:
                        elapsed = time.time() - start_time
                        if elapsed >= self.timeout:
                            raise RetryExhaustedError(
                                f"Timeout exceeded: {elapsed:.1f}s >= {self.timeout}s"
                            )
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt + 1}")
                    return result
                except Exception as e:
                    last_exception = e
                    if not self.is_retriable(e):
                        logger.error(f"❌ {func.__name__} failed with fatal error: {e}")
                        raise
                    if attempt >= self.max_attempts - 1:
                        break
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"⚠️  {func.__name__} failed (attempt {attempt + 1}/{self.max_attempts}): {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
            raise RetryExhaustedError(
                f"Max retries ({self.max_attempts}) exceeded"
            ) from last_exception

        return wrapper

    @classmethod
    def for_llm_inference(cls) -> "UnifiedRetryPolicy":
        """
        Preset for LLM inference calls.

        - Fewer retries (long operations)
        - Longer timeouts
        - Handles connection and timeout errors
        """
        return cls(
            max_attempts=2,
            base_delay=2.0,
            max_delay=10.0,
            timeout=120.0,
            retriable_exceptions=(ConnectionError, TimeoutError, OSError),
        )

    @classmethod
    def for_api_calls(cls) -> "UnifiedRetryPolicy":
        """
        Preset for HTTP API calls.

        - More retries (fast operations)
        - Shorter timeouts
        - Handles network errors
        """
        return cls(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            timeout=60.0,
            retriable_exceptions=(ConnectionError, TimeoutError, OSError),
        )

    @classmethod
    def for_database_operations(cls) -> "UnifiedRetryPolicy":
        """
        Preset for database operations.

        - Standard retries
        - Medium timeout
        - Handles connection errors
        """
        return cls(
            max_attempts=3,
            base_delay=0.5,
            max_delay=10.0,
            timeout=30.0,
            retriable_exceptions=(ConnectionError, TimeoutError, OSError),
        )

    @classmethod
    def for_external_services(cls) -> "UnifiedRetryPolicy":
        """
        Preset for external service calls (S3, etc).

        - More aggressive retries
        - Handles transient failures
        """
        return cls(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            timeout=120.0,
            retriable_exceptions=(ConnectionError, TimeoutError, OSError),
        )


RetryConfig = UnifiedRetryPolicy
LLM_RETRY = UnifiedRetryPolicy.for_llm_inference()
API_RETRY = UnifiedRetryPolicy.for_api_calls()
DB_RETRY = UnifiedRetryPolicy.for_database_operations()
EXTERNAL_RETRY = UnifiedRetryPolicy.for_external_services()


def retry_async(
    func: Callable | None = None,
    *,
    config: UnifiedRetryPolicy | None = None,
    attempts: int | None = None,
    delay: float | None = None,
    backoff: float | None = None,
    exceptions: tuple[Any, ...] | None = None,
) -> Callable:
    """
    Decorator for async functions with retry logic.

    Can be used with or without arguments:
        @retry_async
        async def my_func(): ...

        @retry_async(attempts=5, delay=1.0)
        async def my_func(): ...

        @retry_async(config=my_policy)
        async def my_func(): ...

    Args:
        func: The async function to decorate (when used without parentheses)
        config: UnifiedRetryPolicy to use (overrides individual params)
        attempts: Max retry attempts (maps to max_attempts)
        delay: Base delay between retries (maps to base_delay)
        backoff: Exponential backoff factor (maps to exponential_base)
        exceptions: Tuple of exceptions to retry on (maps to retriable_exceptions)

    Returns:
        Decorated async function with retry logic
    """

    def decorator(inner_func: Callable) -> Callable:
        # Build policy from parameters if no explicit config
        if config is not None:
            policy = config
        else:
            policy_kwargs: dict[str, Any] = {}
            if attempts is not None:
                policy_kwargs["max_attempts"] = attempts
            if delay is not None:
                policy_kwargs["base_delay"] = delay
            if backoff is not None:
                policy_kwargs["exponential_base"] = backoff
            if exceptions is not None:
                policy_kwargs["retriable_exceptions"] = exceptions
            policy = UnifiedRetryPolicy(**policy_kwargs)

        return policy.async_decorator(inner_func)

    # Handle both @retry_async and @retry_async()
    if func is not None:
        return decorator(func)
    return decorator


def with_retry(
    func: Callable | None = None, *, config: UnifiedRetryPolicy | None = None
) -> Callable:
    """Decorator that applies the provided retry policy to a function."""

    def decorator(inner: Callable) -> Callable:
        policy = config or UnifiedRetryPolicy()
        return policy(inner)

    if func is not None:
        return decorator(func)
    return decorator


def retry(
    func: Callable[..., T], *args: Any, config: UnifiedRetryPolicy | None = None, **kwargs: Any
) -> T:
    """Convenience wrapper executing a function under a retry policy."""
    policy = config or UnifiedRetryPolicy()
    wrapped: Callable[..., T] = policy(func)
    return wrapped(*args, **kwargs)
