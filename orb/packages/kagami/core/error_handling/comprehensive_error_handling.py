"""Comprehensive error handling framework with decorators and utilities.

This module provides production-ready error handling with circuit breakers,
retry logic, fallback mechanisms, and comprehensive error wrapping.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import threading
import time
from collections.abc import Callable, Coroutine, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

# Import shared config (CONSOLIDATED: Jan 11, 2026)
from kagami.core.config.shared import CircuitBreakerConfig
from kagami.core.exceptions import (
    CircuitOpenError,
    InfrastructureError,
    KagamiOSTimeoutError,
    ResourceError,
    RetryExhaustedError,
    wrap_exception,
)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy options."""

    FIXED = "fixed"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    EXPONENTIAL_BACKOFF_WITH_JITTER = "exponential_backoff_with_jitter"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        InfrastructureError,
        ResourceError,
    )


# CircuitBreakerConfig is now imported from kagami.core.config.shared
# Re-exported for backward compatibility


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""

    fallback_func: Callable[..., Any] | None = None
    fallback_value: Any = None
    use_cache: bool = False
    cache_ttl: float = 300.0


@dataclass
class ErrorHandlingConfig:
    """Comprehensive error handling configuration."""

    retry_config: RetryConfig | None = None
    circuit_breaker_config: CircuitBreakerConfig | None = None
    fallback_config: FallbackConfig | None = None
    timeout: float | None = None
    log_errors: bool = True
    log_retries: bool = True
    raise_on_exhaustion: bool = True
    context_vars: dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """Thread-safe circuit breaker implementation."""

    def __init__(self, config: CircuitBreakerConfig, name: str = "default"):
        self.config = config
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self._lock = threading.RLock()

    def can_execute(self) -> bool:
        """Check if execution is allowed based on current state."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
                    return True
                return False
            else:  # HALF_OPEN
                return True

    def record_success(self) -> None:
        """Record a successful execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self, exception: Exception) -> None:
        """Record a failed execution."""
        with self._lock:
            if any(
                isinstance(exception, exc_type) for exc_type in self.config.monitored_exceptions
            ):
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.state == CircuitState.CLOSED:
                    if self.failure_count >= self.config.failure_threshold:
                        self.state = CircuitState.OPEN
                        logger.warning(
                            f"Circuit breaker '{self.name}' OPENED after {self.failure_count} failures"
                        )
                elif self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN
                    logger.warning(f"Circuit breaker '{self.name}' returned to OPEN state")


class RetryCalculator:
    """Calculate retry delays based on strategy."""

    @staticmethod
    def calculate_delay(attempt: int, config: RetryConfig) -> float:
        """Calculate delay for the given attempt number."""
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER:
            base_delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
            jitter = base_delay * config.jitter_ratio * (2 * random.random() - 1)
            delay = base_delay + jitter
        else:
            delay = config.base_delay

        return min(delay, config.max_delay)


# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breaker_lock = threading.Lock()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
    """Get or create a circuit breaker instance."""
    with _circuit_breaker_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(config, name)
        return _circuit_breakers[name]


class ComprehensiveErrorHandler:
    """Main error handling orchestrator."""

    def __init__(self, config: ErrorHandlingConfig):
        self.config = config
        self.circuit_breaker = None
        if config.circuit_breaker_config:
            cb_name = f"handler_{id(self)}"
            self.circuit_breaker = get_circuit_breaker(cb_name, config.circuit_breaker_config)

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with comprehensive error handling."""
        start_time = time.time()
        last_exception = None

        # Set up context for logging
        context = {
            "function_name": getattr(func, "__name__", str(func)),
            "module": getattr(func, "__module__", "unknown"),
            **self.config.context_vars,
        }

        # Circuit breaker check
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            error_msg = f"Circuit breaker open for {context['function_name']}"
            if self.config.log_errors:
                logger.warning(error_msg, extra=context)
            raise CircuitOpenError(error_msg)

        # Retry loop
        max_attempts = self.config.retry_config.max_attempts if self.config.retry_config else 1

        for attempt in range(1, max_attempts + 1):
            try:
                # Execute with timeout if configured
                if self.config.timeout:
                    result = self._execute_with_timeout(func, args, kwargs, self.config.timeout)
                else:
                    result = func(*args, **kwargs)

                # Record success
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                # Log successful execution
                if self.config.log_errors:
                    duration = (time.time() - start_time) * 1000
                    logger.debug(
                        f"Function {context['function_name']} completed successfully",
                        extra={**context, "duration_ms": duration, "attempts": attempt},
                    )

                return result

            except Exception as e:
                last_exception = e
                duration = (time.time() - start_time) * 1000

                # Record failure
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(e)

                # Check if this exception is retryable
                is_retryable = (
                    self.config.retry_config
                    and attempt < max_attempts
                    and any(
                        isinstance(e, exc_type)
                        for exc_type in self.config.retry_config.retryable_exceptions
                    )
                )

                if is_retryable:
                    # Calculate delay and retry
                    delay = RetryCalculator.calculate_delay(attempt, self.config.retry_config)

                    if self.config.log_retries:
                        logger.warning(
                            f"Function {context['function_name']} failed (attempt {attempt}/{max_attempts}), retrying in {delay:.2f}s",
                            extra={
                                **context,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "retry_delay": delay,
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                                "duration_ms": duration,
                            },
                            exc_info=e,
                        )

                    time.sleep(delay)
                else:
                    # Not retryable or max attempts reached
                    if self.config.log_errors:
                        log_level = logging.ERROR if not is_retryable else logging.WARNING
                        logger.log(
                            log_level,
                            f"Function {context['function_name']} failed after {attempt} attempt(s)",
                            extra={
                                **context,
                                "final_attempt": True,
                                "attempts": attempt,
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                                "duration_ms": duration,
                            },
                            exc_info=e,
                        )
                    break

        # All attempts exhausted, try fallback
        if self.config.fallback_config:
            try:
                return self._execute_fallback(*args, **kwargs)
            except Exception as fallback_error:
                if self.config.log_errors:
                    logger.error(
                        f"Fallback failed for {context['function_name']}",
                        extra={**context, "fallback_error": str(fallback_error)},
                        exc_info=fallback_error,
                    )

        # Raise appropriate exception
        if self.config.raise_on_exhaustion:
            if max_attempts > 1:
                wrapped_exception = RetryExhaustedError(
                    f"All {max_attempts} retry attempts exhausted for {context['function_name']}",
                    context={"attempts": max_attempts, "last_exception": str(last_exception)},
                    cause=last_exception,
                )
            else:
                wrapped_exception = wrap_exception(last_exception, context=context)

            raise wrapped_exception from last_exception

        # Return fallback value if configured
        if self.config.fallback_config and self.config.fallback_config.fallback_value is not None:
            return self.config.fallback_config.fallback_value

        raise last_exception

    def _execute_with_timeout(
        self, func: Callable[..., T], args: tuple, kwargs: dict, timeout: float
    ) -> T:
        """Execute function with timeout (sync version)."""
        import signal

        class TimeoutException(Exception):
            pass

        def timeout_handler(signum, frame):
            raise TimeoutException("Function execution timed out")

        # Set timeout alarm
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # Cancel alarm
            return result
        except TimeoutException as e:
            raise KagamiOSTimeoutError(
                f"Function execution timed out after {timeout} seconds"
            ) from e
        finally:
            signal.signal(signal.SIGALRM, old_handler)

    def _execute_fallback(self, *args, **kwargs) -> Any:
        """Execute fallback function or return fallback value."""
        fallback_config = self.config.fallback_config

        if fallback_config.fallback_func:
            return fallback_config.fallback_func(*args, **kwargs)
        else:
            return fallback_config.fallback_value


# Async version of error handler
class AsyncComprehensiveErrorHandler:
    """Async version of comprehensive error handler."""

    def __init__(self, config: ErrorHandlingConfig):
        self.config = config
        self.circuit_breaker = None
        if config.circuit_breaker_config:
            cb_name = f"async_handler_{id(self)}"
            self.circuit_breaker = get_circuit_breaker(cb_name, config.circuit_breaker_config)

    async def execute(self, coro: Coroutine[Any, Any, T]) -> T:
        """Execute coroutine with comprehensive error handling."""
        start_time = time.time()
        last_exception = None
        func_name = getattr(coro, "__name__", "async_function")

        context = {"function_name": func_name, "is_async": True, **self.config.context_vars}

        # Circuit breaker check
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            error_msg = f"Circuit breaker open for {func_name}"
            if self.config.log_errors:
                logger.warning(error_msg, extra=context)
            raise CircuitOpenError(error_msg)

        # Retry loop
        max_attempts = self.config.retry_config.max_attempts if self.config.retry_config else 1

        for attempt in range(1, max_attempts + 1):
            try:
                # Execute with timeout if configured
                if self.config.timeout:
                    result = await asyncio.wait_for(coro, timeout=self.config.timeout)
                else:
                    result = await coro

                # Record success
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                # Log successful execution
                if self.config.log_errors:
                    duration = (time.time() - start_time) * 1000
                    logger.debug(
                        f"Async function {func_name} completed successfully",
                        extra={**context, "duration_ms": duration, "attempts": attempt},
                    )

                return result

            except Exception as e:
                last_exception = e
                duration = (time.time() - start_time) * 1000

                # Record failure
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(e)

                # Check if this exception is retryable
                is_retryable = (
                    self.config.retry_config
                    and attempt < max_attempts
                    and any(
                        isinstance(e, exc_type)
                        for exc_type in self.config.retry_config.retryable_exceptions
                    )
                )

                if is_retryable:
                    # Calculate delay and retry
                    delay = RetryCalculator.calculate_delay(attempt, self.config.retry_config)

                    if self.config.log_retries:
                        logger.warning(
                            f"Async function {func_name} failed (attempt {attempt}/{max_attempts}), retrying in {delay:.2f}s",
                            extra={
                                **context,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "retry_delay": delay,
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                                "duration_ms": duration,
                            },
                            exc_info=e,
                        )

                    await asyncio.sleep(delay)
                else:
                    break

        # Handle exhaustion similar to sync version
        if self.config.raise_on_exhaustion:
            if max_attempts > 1:
                wrapped_exception = RetryExhaustedError(
                    f"All {max_attempts} retry attempts exhausted for {func_name}",
                    context={"attempts": max_attempts, "last_exception": str(last_exception)},
                    cause=last_exception,
                )
            else:
                wrapped_exception = wrap_exception(last_exception, context=context)

            raise wrapped_exception from last_exception

        raise last_exception


# Decorator implementations
def error_handler(
    retry_attempts: int = 1,
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
    retry_delay: float = 1.0,
    timeout: float | None = None,
    circuit_breaker: bool = False,
    fallback_func: Callable | None = None,
    fallback_value: Any = None,
    retryable_exceptions: tuple[type[Exception], ...] = (ConnectionError, TimeoutError),
    log_errors: bool = True,
) -> Callable[[F], F]:
    """Decorator for comprehensive error handling."""

    def decorator(func: F) -> F:
        # Build configuration
        retry_config = (
            RetryConfig(
                max_attempts=retry_attempts,
                strategy=retry_strategy,
                base_delay=retry_delay,
                retryable_exceptions=retryable_exceptions,
            )
            if retry_attempts > 1
            else None
        )

        circuit_breaker_config = CircuitBreakerConfig() if circuit_breaker else None

        fallback_config = (
            FallbackConfig(fallback_func=fallback_func, fallback_value=fallback_value)
            if fallback_func or fallback_value is not None
            else None
        )

        config = ErrorHandlingConfig(
            retry_config=retry_config,
            circuit_breaker_config=circuit_breaker_config,
            fallback_config=fallback_config,
            timeout=timeout,
            log_errors=log_errors,
        )

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                handler = AsyncComprehensiveErrorHandler(config)
                coro = func(*args, **kwargs)
                return await handler.execute(coro)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                handler = ComprehensiveErrorHandler(config)
                return handler.execute(func, *args, **kwargs)

            return sync_wrapper

    return decorator


def safe_execute(func: Callable[..., T], *args, **kwargs) -> T | Exception:
    """Safely execute function and return result or exception."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return e


async def safe_execute_async(coro: Coroutine[Any, Any, T]) -> T | Exception:
    """Safely execute coroutine and return result or exception."""
    try:
        return await coro
    except Exception as e:
        return e


@contextmanager
def error_context(
    operation_name: str, log_entry: bool = True, log_exit: bool = True, reraise: bool = True
) -> Generator[None, None, None]:
    """Context manager for error handling with entry/exit logging."""
    if log_entry:
        logger.info(f"Starting operation: {operation_name}")

    start_time = time.time()
    try:
        yield
        if log_exit:
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Operation completed: {operation_name}",
                extra={"duration_ms": duration, "success": True},
            )
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Operation failed: {operation_name}",
            extra={
                "duration_ms": duration,
                "success": False,
                "exception_type": type(e).__name__,
                "exception_message": str(e),
            },
            exc_info=e,
        )
        if reraise:
            raise


# Exception suppression utilities
@contextmanager
def suppress_exceptions(*exception_types: type[Exception]) -> Generator[None, None, None]:
    """Context manager to suppress specified exception types."""
    try:
        yield
    except exception_types:
        pass  # Suppress these exceptions


def ignore_errors(func: F) -> F:
    """Decorator to ignore all errors (returns None on error)."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            return None

    return wrapper


__all__ = [
    "AsyncComprehensiveErrorHandler",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "ComprehensiveErrorHandler",
    "ErrorHandlingConfig",
    "FallbackConfig",
    "RetryCalculator",
    "RetryConfig",
    "RetryStrategy",
    "error_context",
    "error_handler",
    "get_circuit_breaker",
    "ignore_errors",
    "safe_execute",
    "safe_execute_async",
    "suppress_exceptions",
]
