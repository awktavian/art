"""Unified Action Result Pattern — Consistent Result Handling Across All Effectors.

CONSOLIDATES: 11+ different result patterns across sensory/effector implementations
REDUCES: Inconsistent error handling, unreliable status tracking, scattered metadata
PROVIDES: Unified result type for physical + digital actions

Problems this solves:
1. Control4 integration inconsistencies (7 different error patterns)
2. Composio result handling variations (success/failure ambiguity)
3. SmartHome batch operation error aggregation
4. Cross-domain trigger result composition
5. EFE calculation reliability (requires consistent action outcomes)

This unified pattern eliminates duplication and provides reliable action result handling.

Created: December 30, 2025
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")  # Success result type


class ActionStatus(Enum):
    """Standard action execution statuses."""

    SUCCESS = "success"  # Action completed successfully
    PARTIAL_SUCCESS = "partial"  # Some components succeeded
    FAILURE = "failure"  # Action failed completely
    TIMEOUT = "timeout"  # Action timed out
    CANCELLED = "cancelled"  # Action was cancelled
    DEGRADED = "degraded"  # Action completed with reduced functionality
    RETRY_NEEDED = "retry"  # Action needs retry
    SAFETY_VIOLATION = "safety"  # Action blocked for safety (h(x) < 0)


class ActionErrorType(Enum):
    """Classification of action errors for intelligent handling."""

    # Network/Communication
    NETWORK_ERROR = "network"  # Connection issues
    TIMEOUT_ERROR = "timeout"  # Operation timeout
    RATE_LIMIT = "rate_limit"  # API rate limiting

    # Authentication/Authorization
    AUTH_ERROR = "auth"  # Authentication failed
    PERMISSION_ERROR = "permission"  # Insufficient permissions

    # Input/Validation
    VALIDATION_ERROR = "validation"  # Input validation failed
    INVALID_STATE = "invalid_state"  # System in wrong state
    RESOURCE_NOT_FOUND = "not_found"  # Target resource missing

    # System/Infrastructure
    SYSTEM_ERROR = "system"  # Internal system error
    SERVICE_UNAVAILABLE = "unavailable"  # Service down
    CAPACITY_ERROR = "capacity"  # System overloaded

    # Safety/Security
    SAFETY_ERROR = "safety"  # Safety constraint violation
    SECURITY_ERROR = "security"  # Security policy violation

    # Unknown/Unclassified
    UNKNOWN_ERROR = "unknown"  # Unclassified error


@dataclass
class ActionError:
    """Structured error information for action failures."""

    error_type: ActionErrorType
    message: str
    code: str | None = None  # Error code from underlying system
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True  # Whether error might be recoverable
    retry_after: float | None = None  # Suggested retry delay (seconds)

    def __str__(self) -> str:
        return f"{self.error_type.value}: {self.message}"


@dataclass
class ActionMetadata:
    """Metadata about action execution for analysis and optimization."""

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration: float | None = None

    # Identity
    action_id: str | None = None  # Unique action identifier
    action_type: str | None = None  # Type of action (lights, email, etc.)
    target: str | None = None  # Target of action (room, service, etc.)

    # Context
    colony: str | None = None  # Which colony executed this
    user_intent: str | None = None  # Original user intent/goal
    confidence: float | None = None  # Confidence in action selection

    # Performance
    retries: int = 0  # Number of retries attempted
    degradation_level: float = 0.0  # Level of degradation (0.0 = normal, 1.0 = max degradation)
    cache_hit: bool = False  # Whether result came from cache

    # Safety
    safety_score: float = 1.0  # Safety score (h(x), 1.0 = safe)
    cbf_active: bool = False  # Whether CBF constraints were applied

    def mark_completed(self) -> None:
        """Mark action as completed and calculate duration."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

    def add_retry(self) -> None:
        """Increment retry counter."""
        self.retries += 1


@dataclass
class ActionResult(Generic[T]):
    """Unified result type for all action executions.

    Provides consistent interface for success/failure handling, error classification,
    and metadata collection across all physical and digital effectors.

    Usage:
        # Success case
        result = ActionResult.success(
            data=light_status,
            message="Lights set to 80%",
            metadata=ActionMetadata(action_type="lights", target="Living Room")
        )

        # Failure case
        result = ActionResult.failure(
            error=ActionError(ActionErrorType.NETWORK_ERROR, "Control4 unreachable"),
            metadata=ActionMetadata(action_type="lights", retries=3)
        )

        # Check results
        if result.is_success():
            print(f"Success: {result.data}")
        else:
            print(f"Failed: {result.primary_error}")
            if result.is_recoverable():
                # Retry logic
    """

    status: ActionStatus
    data: T | None = None  # Success data (if status == SUCCESS)
    errors: list[ActionError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""  # Human-readable status message
    metadata: ActionMetadata = field(default_factory=ActionMetadata)

    @classmethod
    def success(
        cls, data: T | None = None, message: str = "", metadata: ActionMetadata | None = None
    ) -> ActionResult[T]:
        """Create successful result."""
        if metadata:
            metadata.mark_completed()

        return cls(
            status=ActionStatus.SUCCESS,
            data=data,
            message=message,
            metadata=metadata or ActionMetadata(),
        )

    @classmethod
    def partial_success(
        cls,
        data: T | None = None,
        message: str = "",
        warnings: list[str] | None = None,
        metadata: ActionMetadata | None = None,
    ) -> ActionResult[T]:
        """Create partial success result."""
        if metadata:
            metadata.mark_completed()

        return cls(
            status=ActionStatus.PARTIAL_SUCCESS,
            data=data,
            message=message,
            warnings=warnings or [],
            metadata=metadata or ActionMetadata(),
        )

    @classmethod
    def failure(
        cls, error: ActionError | str, message: str = "", metadata: ActionMetadata | None = None
    ) -> ActionResult[T]:
        """Create failure result."""
        if metadata:
            metadata.mark_completed()

        if isinstance(error, str):
            error = ActionError(ActionErrorType.UNKNOWN_ERROR, error)

        return cls(
            status=ActionStatus.FAILURE,
            errors=[error],
            message=message,
            metadata=metadata or ActionMetadata(),
        )

    @classmethod
    def timeout(
        cls, timeout_duration: float, message: str = "", metadata: ActionMetadata | None = None
    ) -> ActionResult[T]:
        """Create timeout result."""
        if metadata:
            metadata.mark_completed()

        error = ActionError(
            ActionErrorType.TIMEOUT_ERROR,
            f"Action timed out after {timeout_duration}s",
            recoverable=True,
            retry_after=min(timeout_duration * 2, 30.0),  # Exponential backoff, max 30s
        )

        return cls(
            status=ActionStatus.TIMEOUT,
            errors=[error],
            message=message,
            metadata=metadata or ActionMetadata(),
        )

    @classmethod
    def safety_violation(
        cls,
        safety_score: float,
        constraint: str,
        message: str = "",
        metadata: ActionMetadata | None = None,
    ) -> ActionResult[T]:
        """Create safety violation result."""
        if metadata:
            metadata.mark_completed()
            metadata.safety_score = safety_score
            metadata.cbf_active = True

        error = ActionError(
            ActionErrorType.SAFETY_ERROR,
            f"Safety constraint violated: {constraint} (h(x) = {safety_score:.3f})",
            recoverable=False,  # Safety violations should not be automatically retried
        )

        return cls(
            status=ActionStatus.SAFETY_VIOLATION,
            errors=[error],
            message=message,
            metadata=metadata or ActionMetadata(),
        )

    @classmethod
    def cancelled(
        cls, reason: str = "Action cancelled", metadata: ActionMetadata | None = None
    ) -> ActionResult[T]:
        """Create cancelled result."""
        if metadata:
            metadata.mark_completed()

        return cls(
            status=ActionStatus.CANCELLED, message=reason, metadata=metadata or ActionMetadata()
        )

    @classmethod
    def degraded(
        cls,
        data: T | None = None,
        degradation_level: float = 0.5,
        message: str = "",
        warnings: list[str] | None = None,
        metadata: ActionMetadata | None = None,
    ) -> ActionResult[T]:
        """Create degraded result (reduced functionality)."""
        if metadata:
            metadata.mark_completed()
            metadata.degradation_level = degradation_level

        return cls(
            status=ActionStatus.DEGRADED,
            data=data,
            message=message,
            warnings=warnings or [],
            metadata=metadata or ActionMetadata(),
        )

    def is_success(self) -> bool:
        """Check if action was successful."""
        return self.status == ActionStatus.SUCCESS

    def is_partial_success(self) -> bool:
        """Check if action was partially successful."""
        return self.status == ActionStatus.PARTIAL_SUCCESS

    def is_failure(self) -> bool:
        """Check if action failed."""
        return self.status in [
            ActionStatus.FAILURE,
            ActionStatus.TIMEOUT,
            ActionStatus.SAFETY_VIOLATION,
        ]

    def is_recoverable(self) -> bool:
        """Check if failure might be recoverable."""
        if not self.is_failure():
            return False
        return all(error.recoverable for error in self.errors)

    def requires_retry(self) -> bool:
        """Check if action should be retried."""
        return self.status == ActionStatus.RETRY_NEEDED

    def has_data(self) -> bool:
        """Check if result contains data."""
        return self.data is not None

    @property
    def primary_error(self) -> ActionError | None:
        """Get the primary (first) error, if any."""
        return self.errors[0] if self.errors else None

    @property
    def suggested_retry_delay(self) -> float | None:
        """Get suggested retry delay from primary error."""
        if self.primary_error and self.primary_error.retry_after:
            return self.primary_error.retry_after
        return None

    def add_error(self, error: ActionError | str) -> None:
        """Add additional error to result."""
        if isinstance(error, str):
            error = ActionError(ActionErrorType.UNKNOWN_ERROR, error)
        self.errors.append(error)

        # Upgrade status to failure if not already failed
        if self.status not in [
            ActionStatus.FAILURE,
            ActionStatus.TIMEOUT,
            ActionStatus.SAFETY_VIOLATION,
        ]:
            self.status = ActionStatus.FAILURE

    def add_warning(self, warning: str) -> None:
        """Add warning message."""
        self.warnings.append(warning)

    def with_metadata(self, **kwargs: Any) -> ActionResult[T]:
        """Update metadata fields and return self for chaining."""
        for key, value in kwargs.items():
            setattr(self.metadata, key, value)
        return self


# =============================================================================
# BATCH OPERATION SUPPORT
# =============================================================================


@dataclass
class BatchActionResult(Generic[T]):
    """Result for batch operations across multiple targets.

    Aggregates individual ActionResult instances with overall status computation.
    Useful for operations like "turn off all lights" or "send multiple emails".
    """

    results: dict[str, ActionResult[T]] = field(default_factory=dict)
    metadata: ActionMetadata = field(default_factory=ActionMetadata)

    def add_result(self, target: str, result: ActionResult[T]) -> None:
        """Add individual result for target."""
        self.results[target] = result

    @property
    def overall_status(self) -> ActionStatus:
        """Compute overall status from individual results."""
        if not self.results:
            return ActionStatus.SUCCESS

        statuses = [result.status for result in self.results.values()]

        # All success
        if all(status == ActionStatus.SUCCESS for status in statuses):
            return ActionStatus.SUCCESS

        # All failure
        if all(
            status in [ActionStatus.FAILURE, ActionStatus.TIMEOUT, ActionStatus.SAFETY_VIOLATION]
            for status in statuses
        ):
            return ActionStatus.FAILURE

        # Mixed results
        return ActionStatus.PARTIAL_SUCCESS

    @property
    def success_count(self) -> int:
        """Count of successful results."""
        return sum(1 for result in self.results.values() if result.is_success())

    @property
    def failure_count(self) -> int:
        """Count of failed results."""
        return sum(1 for result in self.results.values() if result.is_failure())

    @property
    def total_count(self) -> int:
        """Total number of operations."""
        return len(self.results)

    @property
    def success_rate(self) -> float:
        """Success rate as fraction (0.0 to 1.0)."""
        if self.total_count == 0:
            return 1.0
        return self.success_count / self.total_count

    @property
    def all_errors(self) -> list[ActionError]:
        """Get all errors from all results."""
        errors = []
        for result in self.results.values():
            errors.extend(result.errors)
        return errors

    @property
    def all_warnings(self) -> list[str]:
        """Get all warnings from all results."""
        warnings = []
        for result in self.results.values():
            warnings.extend(result.warnings)
        return warnings

    def is_complete_success(self) -> bool:
        """Check if all operations succeeded."""
        return self.overall_status == ActionStatus.SUCCESS

    def is_complete_failure(self) -> bool:
        """Check if all operations failed."""
        return self.overall_status == ActionStatus.FAILURE

    def get_successful_targets(self) -> list[str]:
        """Get list of targets that succeeded."""
        return [target for target, result in self.results.items() if result.is_success()]

    def get_failed_targets(self) -> list[str]:
        """Get list of targets that failed."""
        return [target for target, result in self.results.items() if result.is_failure()]


# =============================================================================
# CONVERSION UTILITIES
# =============================================================================


def to_action_result(
    success: bool,
    data: T | None = None,
    error_msg: str = "",
    metadata: ActionMetadata | None = None,
) -> ActionResult[T]:
    """Convert simple boolean success to ActionResult.

    Utility for migrating legacy code that returns (bool, data, error).
    """
    if success:
        return ActionResult.success(data=data, metadata=metadata)
    else:
        return ActionResult.failure(error_msg, metadata=metadata)


def from_exception(
    exception: Exception, metadata: ActionMetadata | None = None
) -> ActionResult[Any]:
    """Convert exception to ActionResult.

    Automatically classifies common exception types.
    """
    error_type = ActionErrorType.UNKNOWN_ERROR
    recoverable = True
    retry_after = None

    # Classify common exception types
    exc_name = type(exception).__name__
    exc_msg = str(exception)

    if "timeout" in exc_msg.lower() or "TimeoutError" in exc_name:
        error_type = ActionErrorType.TIMEOUT_ERROR
        retry_after = 5.0
    elif "connection" in exc_msg.lower() or "network" in exc_msg.lower():
        error_type = ActionErrorType.NETWORK_ERROR
        retry_after = 2.0
    elif "auth" in exc_msg.lower() or "401" in exc_msg:
        error_type = ActionErrorType.AUTH_ERROR
        recoverable = False
    elif "permission" in exc_msg.lower() or "403" in exc_msg:
        error_type = ActionErrorType.PERMISSION_ERROR
        recoverable = False
    elif "not found" in exc_msg.lower() or "404" in exc_msg:
        error_type = ActionErrorType.RESOURCE_NOT_FOUND
        recoverable = False
    elif "rate limit" in exc_msg.lower() or "429" in exc_msg:
        error_type = ActionErrorType.RATE_LIMIT
        retry_after = 60.0
    elif "unavailable" in exc_msg.lower() or "503" in exc_msg:
        error_type = ActionErrorType.SERVICE_UNAVAILABLE
        retry_after = 10.0

    error = ActionError(
        error_type=error_type,
        message=exc_msg,
        code=getattr(exception, "code", None),
        recoverable=recoverable,
        retry_after=retry_after,
    )

    return ActionResult.failure(error=error, metadata=metadata)


def aggregate_results(results: Sequence[ActionResult[T]]) -> ActionResult[list[T]]:
    """Aggregate multiple ActionResult instances into a single result.

    Success data is collected into a list. Overall status follows batch logic.
    """
    if not results:
        return ActionResult.success(data=[])

    # Collect successful data
    success_data = []
    all_errors = []
    all_warnings = []

    for result in results:
        if result.has_data():
            success_data.append(result.data)
        all_errors.extend(result.errors)
        all_warnings.extend(result.warnings)

    # Determine overall status
    statuses = [result.status for result in results]

    if all(status == ActionStatus.SUCCESS for status in statuses):
        overall_status = ActionStatus.SUCCESS
    elif all(
        status in [ActionStatus.FAILURE, ActionStatus.TIMEOUT, ActionStatus.SAFETY_VIOLATION]
        for status in statuses
    ):
        overall_status = ActionStatus.FAILURE
    else:
        overall_status = ActionStatus.PARTIAL_SUCCESS

    # Create aggregate metadata
    aggregate_metadata = ActionMetadata(
        action_type="batch",
        retries=max((r.metadata.retries for r in results), default=0),
        duration=sum((r.metadata.duration or 0.0 for r in results), 0.0),
    )

    return ActionResult(
        status=overall_status,
        data=success_data,
        errors=all_errors,
        warnings=all_warnings,
        message=f"Batch operation: {len(success_data)}/{len(results)} succeeded",
        metadata=aggregate_metadata,
    )
