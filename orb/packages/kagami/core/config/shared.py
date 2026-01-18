"""Shared configuration classes for Kagami.

CREATED: January 11, 2026
PURPOSE: Consolidate duplicated configuration classes across the codebase.

This module contains configuration classes that were previously duplicated
in multiple locations. All modules should import from here for consistency.

CONSOLIDATED CLASSES:
=====================
- CircuitBreakerConfig: Circuit breaker pattern configuration
  - Previously in: patterns/circuit_breaker.py, error_handling/comprehensive_error_handling.py,
                   resilience/circuit_breaker.py, unified_agents/worker/lifecycle.py

MIGRATION:
==========
Original locations now re-export from this module for backward compatibility.
New code should import directly from kagami.core.config.shared.

Example:
    from kagami.core.config.shared import CircuitBreakerConfig

    # Or via the main config module:
    from kagami.core.config import CircuitBreakerConfig
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# CIRCUIT BREAKER CONFIG
# =============================================================================


class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    The circuit breaker pattern prevents cascading failures by stopping
    calls to failing dependencies. This config controls the behavior
    of circuit breakers throughout the system.

    States:
    - CLOSED: Normal operation (calls pass through)
    - OPEN: Failure threshold exceeded (calls blocked)
    - HALF_OPEN: Testing recovery (limited calls allowed)

    Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: After success_threshold successes
    - HALF_OPEN -> OPEN: On any failure

    Attributes:
        failure_threshold: Number of failures before opening circuit.
            Default: 5 (balance between sensitivity and stability)
        recovery_timeout: Seconds to wait before attempting recovery.
            Default: 30.0 (enough time for transient issues to resolve)
            Note: Also accepts 'timeout_seconds' for backward compatibility.
        success_threshold: Successes needed in half-open state to close.
            Default: 2 (require multiple successes to confirm recovery)
        half_open_max_calls: Max concurrent calls allowed in half-open state.
            Default: 3 (allow some testing without overwhelming recovering service)
        monitored_exceptions: Exception types that trigger failure counting.
            Default: (ConnectionError, TimeoutError) for network operations

    Example:
        >>> config = CircuitBreakerConfig(
        ...     failure_threshold=3,
        ...     recovery_timeout=60.0,
        ...     success_threshold=2,
        ... )
        >>> breaker = CircuitBreaker(config=config)

        # Backward compatible:
        >>> config = CircuitBreakerConfig(timeout_seconds=60.0)  # Also works
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float | None = None,
        success_threshold: int = 2,
        half_open_max_calls: int = 3,
        monitored_exceptions: tuple[type[Exception], ...] | None = None,
        # Backward compatibility alias
        timeout_seconds: float | None = None,
    ):
        """Initialize circuit breaker configuration.

        Args:
            failure_threshold: Failures before opening circuit (default: 5)
            recovery_timeout: Seconds before attempting recovery (default: 30.0)
            success_threshold: Successes to close from half-open (default: 2)
            half_open_max_calls: Max calls in half-open state (default: 3)
            monitored_exceptions: Exceptions to monitor (default: ConnectionError, TimeoutError)
            timeout_seconds: Alias for recovery_timeout (backward compatibility)
        """
        self.failure_threshold = failure_threshold
        # Handle both recovery_timeout and timeout_seconds (timeout_seconds takes precedence for backward compat)
        if timeout_seconds is not None:
            self.recovery_timeout = timeout_seconds
        elif recovery_timeout is not None:
            self.recovery_timeout = recovery_timeout
        else:
            self.recovery_timeout = 30.0
        self.success_threshold = success_threshold
        self.half_open_max_calls = half_open_max_calls
        self.monitored_exceptions = monitored_exceptions or (ConnectionError, TimeoutError)

    @property
    def timeout_seconds(self) -> float:
        """Alias for recovery_timeout (backward compatibility)."""
        return self.recovery_timeout

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"CircuitBreakerConfig(failure_threshold={self.failure_threshold}, "
            f"recovery_timeout={self.recovery_timeout}, "
            f"success_threshold={self.success_threshold}, "
            f"half_open_max_calls={self.half_open_max_calls}, "
            f"monitored_exceptions={self.monitored_exceptions})"
        )


# =============================================================================
# POOL CONFIG (Base)
# =============================================================================


@dataclass
class BasePoolConfig:
    """Base configuration for resource pools.

    This provides common pool configuration fields. Specific pool types
    (connection pool, memory pool, VM pool) extend this with domain-specific
    fields.

    Attributes:
        max_size: Maximum number of resources in pool.
        min_size: Minimum number of resources to maintain.
        acquire_timeout: Max time to wait for a resource (seconds).
        health_check_interval: How often to check resource health (seconds).
        max_lifetime: Maximum lifetime of a resource (seconds).
    """

    max_size: int = 10
    min_size: int = 1
    acquire_timeout: float = 5.0
    health_check_interval: float = 30.0
    max_lifetime: float = 3600.0  # 1 hour


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "BasePoolConfig",
    "CircuitBreakerConfig",
]
