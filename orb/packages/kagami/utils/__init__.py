"""K os Utilities Package.

Provides shared utilities used throughout the codebase:
- Retry logic with exponential backoff
- Error handling contexts
- Connection pooling
- Performance monitoring
"""

from __future__ import annotations

from typing import Any

# NOTE: Performance moved to kagami_observability (Dec 22, 2025)
from kagami_observability.performance import PerformanceTimer, monitor_performance

# NOTE: errors.py removed - use kagami.core.exceptions instead
# from .errors import ErrorContext, KagamiOSError
from kagami.core.exceptions import KagamiOSException as KagamiOSError

# NOTE: Connection pool moved to kagami.core.infra (Dec 22, 2025)
from kagami.core.infra.connection_pool import ConnectionPool, PoolConfig

from .retry import RetryConfig, retry_async, with_retry


class ErrorContext:
    """Context for error handling decisions (migrated from errors.py)."""

    def __init__(self, operation: str = "", **kwargs: Any) -> None:
        self.operation = operation
        self.metadata = kwargs

    def __repr__(self) -> str:
        parts: list[str] = []
        if self.operation:
            parts.append(f"operation={self.operation!r}")
        if self.metadata:
            parts.append(f"metadata={self.metadata!r}")
        inside = ", ".join(parts)
        return f"ErrorContext({inside})"


__all__ = [
    "ConnectionPool",
    "ErrorContext",
    "KagamiOSError",  # Re-exported from core.exceptions for backwards compatibility
    "PerformanceTimer",
    "PoolConfig",
    "RetryConfig",
    "monitor_performance",
    "retry_async",
    "with_retry",
]
