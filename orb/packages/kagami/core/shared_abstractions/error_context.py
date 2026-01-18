"""Error Context Builder — Unified Error Context Across All Services.

CONSOLIDATES: Error context patterns across all services
REDUCES: Inconsistent error reporting, missing context information
PROVIDES: Standardized error context with service identification

This module provides consistent error context building for all Kagami services,
enabling better debugging and error tracking across the distributed system.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ServiceContext(Enum):
    """Types of service contexts for error reporting."""

    ACTIVE_INFERENCE = "active_inference"
    WORLD_MODEL = "world_model"
    SENSORY_INTEGRATION = "sensory_integration"
    EFFECTOR_CONTROL = "effector_control"
    MEMORY_SYSTEM = "memory_system"
    COLONY_COORDINATION = "colony_coordination"
    SAFETY_ENFORCEMENT = "safety_enforcement"
    TOOL_COMPOSITION = "tool_composition"
    MARKOV_BOUNDARY = "markov_boundary"
    SMART_HOME = "smart_home"
    COMPOSIO_INTEGRATION = "composio_integration"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Structured error context information."""

    # Core identification
    service: ServiceContext
    operation: str
    timestamp: float = field(default_factory=time.time)

    # Error details
    error_message: str = ""
    error_type: str = ""
    stack_trace: str = ""

    # Context information
    user_intent: str = ""
    session_id: str = ""
    colony: str = ""
    safety_score: float = 1.0

    # Service-specific context
    service_state: dict[str, Any] = field(default_factory=dict)
    input_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Error tracking
    error_count: int = 1
    first_occurrence: float = field(default_factory=time.time)
    recent_occurrences: list[float] = field(default_factory=list)


class ErrorContextBuilder:
    """Builder for creating consistent error contexts across services."""

    def __init__(self, service: ServiceContext, operation: str):
        self.service = service
        self.operation = operation
        self._context = ErrorContext(service=service, operation=operation)

    def with_error(
        self, error: Exception | str, include_traceback: bool = True
    ) -> ErrorContextBuilder:
        """Add error information to the context."""
        if isinstance(error, Exception):
            self._context.error_message = str(error)
            self._context.error_type = type(error).__name__
            if include_traceback:
                self._context.stack_trace = traceback.format_exc()
        else:
            self._context.error_message = str(error)
            self._context.error_type = "String Error"

        return self

    def with_user_intent(self, intent: str) -> ErrorContextBuilder:
        """Add user intent to the context."""
        self._context.user_intent = intent
        return self

    def with_session(self, session_id: str) -> ErrorContextBuilder:
        """Add session information to the context."""
        self._context.session_id = session_id
        return self

    def with_colony(self, colony: str) -> ErrorContextBuilder:
        """Add colony information to the context."""
        self._context.colony = colony
        return self

    def with_safety_score(self, safety_score: float) -> ErrorContextBuilder:
        """Add safety score (h(x)) to the context."""
        self._context.safety_score = safety_score
        return self

    def with_service_state(self, **state: Any) -> ErrorContextBuilder:
        """Add service-specific state information."""
        self._context.service_state.update(state)
        return self

    def with_input_data(self, **data: Any) -> ErrorContextBuilder:
        """Add input data that led to the error."""
        self._context.input_data.update(data)
        return self

    def with_metadata(self, **metadata: Any) -> ErrorContextBuilder:
        """Add additional metadata to the context."""
        self._context.metadata.update(metadata)
        return self

    def with_error_tracking(
        self, error_count: int, first_occurrence: float, recent_occurrences: list[float]
    ) -> ErrorContextBuilder:
        """Add error tracking information."""
        self._context.error_count = error_count
        self._context.first_occurrence = first_occurrence
        self._context.recent_occurrences = recent_occurrences.copy()
        return self

    def build(self) -> ErrorContext:
        """Build the final error context."""
        return self._context

    def log_error(self, log_level: int = logging.ERROR) -> ErrorContext:
        """Log the error with context and return the context."""
        context = self.build()

        # Format log message
        log_message = (
            f"[{context.service.value}:{context.operation}] "
            f"{context.error_type}: {context.error_message}"
        )

        # Add context details
        if context.user_intent:
            log_message += f" | Intent: {context.user_intent}"
        if context.colony:
            log_message += f" | Colony: {context.colony}"
        if context.safety_score < 1.0:
            log_message += f" | Safety: {context.safety_score:.3f}"

        # Log the error
        logger.log(log_level, log_message)

        # Log stack trace if available
        if context.stack_trace and log_level >= logging.ERROR:
            logger.debug(
                f"Stack trace for {context.service.value}:{context.operation}:\n{context.stack_trace}"
            )

        return context


# =============================================================================
# SERVICE-SPECIFIC BUILDERS
# =============================================================================


def create_active_inference_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for active inference errors."""
    return ErrorContextBuilder(ServiceContext.ACTIVE_INFERENCE, operation)


def create_world_model_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for world model errors."""
    return ErrorContextBuilder(ServiceContext.WORLD_MODEL, operation)


def create_sensory_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for sensory integration errors."""
    return ErrorContextBuilder(ServiceContext.SENSORY_INTEGRATION, operation)


def create_effector_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for effector control errors."""
    return ErrorContextBuilder(ServiceContext.EFFECTOR_CONTROL, operation)


def create_memory_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for memory system errors."""
    return ErrorContextBuilder(ServiceContext.MEMORY_SYSTEM, operation)


def create_colony_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for colony coordination errors."""
    return ErrorContextBuilder(ServiceContext.COLONY_COORDINATION, operation)


def create_safety_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for safety enforcement errors."""
    return ErrorContextBuilder(ServiceContext.SAFETY_ENFORCEMENT, operation)


def create_tool_composition_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for tool composition errors."""
    return ErrorContextBuilder(ServiceContext.TOOL_COMPOSITION, operation)


def create_markov_boundary_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for Markov boundary errors."""
    return ErrorContextBuilder(ServiceContext.MARKOV_BOUNDARY, operation)


def create_smart_home_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for smart home errors."""
    return ErrorContextBuilder(ServiceContext.SMART_HOME, operation)


def create_composio_error(operation: str) -> ErrorContextBuilder:
    """Create error context builder for Composio integration errors."""
    return ErrorContextBuilder(ServiceContext.COMPOSIO_INTEGRATION, operation)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def get_error_context_builder(service: ServiceContext | str, operation: str) -> ErrorContextBuilder:
    """Get error context builder for specified service and operation.

    Args:
        service: Service context (enum or string)
        operation: Operation being performed

    Returns:
        ErrorContextBuilder instance
    """
    if isinstance(service, str):
        try:
            service = ServiceContext(service)
        except ValueError:
            service = ServiceContext.UNKNOWN

    return ErrorContextBuilder(service, operation)


# =============================================================================
# ERROR CONTEXT DECORATORS
# =============================================================================


def with_error_context(service: ServiceContext | str, operation: str | None = None):
    """Decorator to automatically capture error context for functions.

    Args:
        service: Service context
        operation: Optional operation name (defaults to function name)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            op_name = operation or func.__name__

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Create error context
                (
                    get_error_context_builder(service, op_name)
                    .with_error(e)
                    .with_metadata(
                        function_name=func.__name__,
                        args_count=len(args),
                        kwargs_keys=list(kwargs.keys()),
                    )
                    .log_error()
                )

                # Re-raise with enhanced context
                raise e

        # For async functions
        async def async_wrapper(*args, **kwargs):
            op_name = operation or func.__name__

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Create error context
                (
                    get_error_context_builder(service, op_name)
                    .with_error(e)
                    .with_metadata(
                        function_name=func.__name__,
                        args_count=len(args),
                        kwargs_keys=list(kwargs.keys()),
                        async_function=True,
                    )
                    .log_error()
                )

                # Re-raise with enhanced context
                raise e

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


# =============================================================================
# ERROR AGGREGATION
# =============================================================================


class ErrorAggregator:
    """Aggregates error contexts for pattern analysis."""

    def __init__(self, max_errors: int = 1000):
        self.max_errors = max_errors
        self._errors: list[ErrorContext] = []
        self._error_counts: dict[str, int] = {}

    def add_error(self, error_context: ErrorContext) -> None:
        """Add an error context to the aggregator."""
        self._errors.append(error_context)

        # Track error patterns
        error_key = (
            f"{error_context.service.value}:{error_context.operation}:{error_context.error_type}"
        )
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1

        # Maintain size limit
        if len(self._errors) > self.max_errors:
            self._errors = self._errors[-self.max_errors // 2 :]

    def get_error_patterns(self) -> dict[str, dict[str, Any]]:
        """Get common error patterns."""
        patterns = {}

        for error_key, count in self._error_counts.items():
            if count > 1:  # Only patterns that occur multiple times
                service, operation, error_type = error_key.split(":", 2)
                patterns[error_key] = {
                    "service": service,
                    "operation": operation,
                    "error_type": error_type,
                    "count": count,
                    "frequency": count / len(self._errors) if self._errors else 0.0,
                }

        return patterns

    def get_recent_errors(self, limit: int = 10) -> list[ErrorContext]:
        """Get most recent errors."""
        return self._errors[-limit:]

    def clear(self) -> None:
        """Clear all aggregated errors."""
        self._errors.clear()
        self._error_counts.clear()


# Global error aggregator instance
_global_error_aggregator = ErrorAggregator()


def get_global_error_aggregator() -> ErrorAggregator:
    """Get the global error aggregator instance."""
    return _global_error_aggregator
