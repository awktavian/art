"""Performance monitoring for Forge Matrix.

Utilities for tracking latency and enforcing performance budgets.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class PerformanceViolationError(Exception):
    """Raised when an operation exceeds its performance budget in strict mode."""

    def __init__(
        self,
        operation: str,
        elapsed_ms: float | None = None,
        limit_ms: float | None = None,
        message: str | None = None,
    ):
        # Backwards-compatible: allow `PerformanceViolationError("message")`
        # (older tests treated the first arg as a free-form message).
        if elapsed_ms is None and limit_ms is None and message is None:
            self.operation = "unknown"
            self.elapsed_ms = 0.0
            self.limit_ms = 0.0
            super().__init__(operation)
            return

        self.operation = operation
        self.elapsed_ms = float(elapsed_ms or 0.0)
        self.limit_ms = float(limit_ms or 0.0)
        super().__init__(
            message or f"{operation} exceeded limit: {self.elapsed_ms:.2f}ms > {self.limit_ms}ms"
        )


def monitor_performance(operation_name: str, max_latency_ms: float | None = None) -> Callable:
    """
    Decorator to monitor performance of operations and warn if they exceed latency limits.

    Args:
        operation_name: Name of the operation being monitored
        max_latency_ms: Maximum allowed latency in milliseconds (if None, uses config)
    """

    def decorator(func: Any) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Config loading logic simulated/simplified for now
            # In a real implementation, this would look up per-operation limits
            limit = max_latency_ms if max_latency_ms is not None else 60000.0
            warning_threshold = limit * 0.8

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                if elapsed_ms > limit:
                    msg = f"Performance violation: {operation_name} took {elapsed_ms:.2f}ms (limit: {limit}ms)"
                    logger.error(msg)
                    # Strict mode check would go here
                elif elapsed_ms > warning_threshold:
                    logger.info(
                        f"Performance warning: {operation_name} took {elapsed_ms:.2f}ms (warning: {warning_threshold}ms)"
                    )
                else:
                    logger.debug(f"{operation_name} completed in {elapsed_ms:.2f}ms")

                # Attach metrics to result if it supports metadata
                if hasattr(result, "metadata") and isinstance(result.metadata, dict):
                    result.metadata["performance"] = {
                        "operation": operation_name,
                        "latency_ms": elapsed_ms,
                        "within_limit": elapsed_ms <= limit,
                    }
                elif isinstance(result, dict):
                    # If result is a dict[str, Any], we can try to inject it if appropriate
                    # or just ignore
                    pass

                return result
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(f"{operation_name} failed after {elapsed_ms:.2f}ms: {e}")
                raise

        return wrapper

    return decorator
