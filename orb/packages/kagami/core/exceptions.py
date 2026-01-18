"""K os Unified Exception Hierarchy.

Centralized exception types for better error handling and instrumentation.
All exceptions inherit from KagamiOSException for consistent handling.

See docs/INDEX.md for usage guidelines.
"""

from __future__ import annotations

from typing import Any

# ============================================================================
# Base Exception
# ============================================================================


class KagamiOSException(Exception):
    """Base exception for all K os errors.

    Attributes:
        message: Human-readable error description
        error_code: Unique error code for instrumentation
        context: Additional diagnostic context
        recoverable: Whether error can be recovered from
    """

    error_code: str = "KAGAMI_ERROR"
    recoverable: bool = False

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.__cause__ = cause

        # Emit metric
        try:
            from kagami_observability.metrics import kagami_errors_total

            kagami_errors_total.labels(
                error_type=self.__class__.__name__,
                error_code=self.error_code,
                recoverable=str(self.recoverable),
            ).inc()
        except Exception:
            pass  # Don't fail if metrics unavailable


# ============================================================================
# Security Errors
# ============================================================================


class SecurityError(KagamiOSException):
    """Base class for security-related errors.

    Raised when security policy is violated, signature verification fails,
    or security constraints are not met.
    """

    error_code = "SECURITY_ERROR"
    recoverable = False


class SignatureVerificationError(SecurityError):
    """Raised when cryptographic signature verification fails."""

    error_code = "SIGNATURE_VERIFICATION"


class EncryptionError(SecurityError):
    """Raised when encryption/decryption operations fail."""

    error_code = "ENCRYPTION_ERROR"


# ============================================================================
# Safety & Control Errors
# ============================================================================


class SafetyError(KagamiOSException):
    """Base class for safety-related errors."""

    error_code = "SAFETY_ERROR"
    recoverable = False


class SafetyViolationError(SafetyError):
    """Control Barrier Function (CBF) safety constraint violated.

    h(x) < 0 detected - system prevented unsafe operation.

    Supports multiple use cases:
    - HAL actuator safety violations (with h_value, command, actuator)
    - Consensus safety violations (with violated_colonies, h_values)

    Attributes:
        h_value: The CBF barrier value h(x) at time of violation
        barrier_value: Alias for h_value (backward compatibility)
        command: The rejected command (for actuator violations)
        actuator: String name of actuator (for actuator violations)
        actuator_type: Type of actuator (for actuator violations)
        reason: Human-readable explanation
        violated_colonies: List of colony indices that violated h_i >= 0
        h_values: Dict mapping colony_idx -> barrier value h_i
        consensus_actions: The actions that caused the violation
        timestamp: When the violation occurred
    """

    error_code = "SAFETY_VIOLATION"

    def __init__(
        self,
        message: str,
        *,
        # Common attributes
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
        # HAL actuator violation attributes
        h_value: float | None = None,
        command: Any = None,
        actuator: str = "",
        actuator_type: Any = None,
        reason: str = "",
        # Consensus violation attributes
        violated_colonies: list[int] | None = None,
        h_values: dict[int, float] | None = None,
        consensus_actions: dict[str, str] | None = None,
        timestamp: float | None = None,
    ) -> None:
        super().__init__(message, context=context, cause=cause)

        # HAL actuator attributes
        self.h_value = h_value if h_value is not None else -1.0
        self.barrier_value = self.h_value  # Alias for backward compatibility
        self.command = command
        self.actuator = actuator
        self.actuator_type = actuator_type
        self.reason = reason

        # Consensus attributes
        self.violated_colonies = violated_colonies or []
        self.h_values_map = h_values or {}  # Named differently to avoid confusion
        self.consensus_actions = consensus_actions
        self.timestamp = timestamp


# Backward compatibility alias
SafetyViolation = SafetyViolationError


class CBFViolation(SafetyError):
    """Control barrier function violated (h(x) < 0)."""

    error_code = "CBF_VIOLATION"


class HonestyViolation(SafetyError):
    """Claim not backed by evidence."""

    error_code = "HONESTY_VIOLATION"


class MemoryLimitViolation(SafetyError):
    """Agent exceeded memory limits."""

    error_code = "MEMORY_LIMIT_VIOLATION"


class ThreatDetected(SafetyError):
    """Threat instinct detected dangerous pattern."""

    error_code = "THREAT_DETECTED"


class EthicalConstraintError(SafetyError):
    """Ethical constraint prevented operation."""

    error_code = "ETHICAL_CONSTRAINT"


class TICViolationError(SafetyError):
    """Typed Intent Calculus (TIC) constraint violated.

    Raised when preconditions, postconditions, or invariants fail verification.
    """

    error_code = "TIC_VIOLATION"
    recoverable = False


# ============================================================================
# Infrastructure Errors
# ============================================================================


class InfrastructureError(KagamiOSException):
    """Base class for infrastructure errors."""

    error_code = "INFRASTRUCTURE_ERROR"
    recoverable = True


class CircuitOpenError(InfrastructureError):
    """Circuit breaker is open."""

    error_code = "CIRCUIT_OPEN"


# Backwards compatibility alias
CircuitBreakerOpenError = CircuitOpenError


class RateLimitError(InfrastructureError):
    """Rate limit exceeded."""

    error_code = "RATE_LIMIT"
    recoverable = True


class RetryExhaustedError(InfrastructureError):
    """All retry attempts exhausted."""

    error_code = "RETRY_EXHAUSTED"
    recoverable = False


class BootGraphError(InfrastructureError):
    """Boot graph execution error."""

    error_code = "BOOT_GRAPH_ERROR"
    recoverable = False


class EtcdError(InfrastructureError):
    """Base class for etcd errors."""

    error_code = "ETCD_ERROR"
    recoverable = True


class EtcdConnectionError(EtcdError):
    """Failed to connect to etcd cluster."""

    error_code = "ETCD_CONNECTION"


class EtcdLeaderError(EtcdError):
    """No etcd leader available."""

    error_code = "ETCD_NO_LEADER"


class EtcdQuorumError(EtcdError):
    """etcd cluster doesn't have quorum."""

    error_code = "ETCD_NO_QUORUM"


# ============================================================================
# Resource Errors
# ============================================================================


class ResourceError(KagamiOSException):
    """Resource unavailable or exhausted."""

    error_code = "RESOURCE_ERROR"
    recoverable = True


class DatabaseUnavailable(ResourceError):
    """Database unavailable."""

    error_code = "DATABASE_UNAVAILABLE"


class RedisUnavailable(ResourceError):
    """Redis unavailable."""

    error_code = "REDIS_UNAVAILABLE"


class LLMUnavailable(ResourceError):
    """LLM service unavailable."""

    error_code = "LLM_UNAVAILABLE"


class ResourceExhaustedError(ResourceError):
    """System resource exhausted (memory, GPU, etc.)."""

    error_code = "RESOURCE_EXHAUSTED"
    recoverable = False


class ExternalRepoError(ResourceError):
    """External repository not available.

    Raised when a required external repository is missing.
    """

    error_code = "EXTERNAL_REPO_UNAVAILABLE"

    def __init__(
        self,
        repo_name: str,
        setup_command: str | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.repo_name = repo_name
        # This repo uses Makefile-driven setup for external integrations.
        self.setup_command = setup_command or "make forge-setup"
        message = f"External repository '{repo_name}' not available."
        if setup_command:
            message += f"\n\nSetup: {setup_command}"
        ctx = context or {}
        ctx["repo_name"] = repo_name
        ctx["setup_command"] = self.setup_command
        super().__init__(message, context=ctx)


# ============================================================================
# Validation Errors
# ============================================================================


class ValidationError(KagamiOSException):
    """Input/output validation failed."""

    error_code = "VALIDATION_ERROR"
    recoverable = True


class SchemaValidationError(ValidationError):
    """Data doesn't match expected schema."""

    error_code = "SCHEMA_VALIDATION_ERROR"


class ReceiptValidationError(ValidationError):
    """Receipt validation failed."""

    error_code = "RECEIPT_VALIDATION_ERROR"


class ConfigurationError(ValidationError):
    """Configuration invalid or missing."""

    error_code = "CONFIGURATION_ERROR"
    recoverable = False


class FullOperationError(ConfigurationError):
    """Required component unavailable (FULL OPERATION mode)."""

    error_code = "FULL_OPERATION_ERROR"


class FeatureNotAvailableError(ConfigurationError):
    """Feature not available in current configuration."""

    error_code = "FEATURE_UNAVAILABLE"
    recoverable = True


# ============================================================================
# Agent & Execution Errors
# ============================================================================


class AgentError(KagamiOSException):
    """Agent operation error."""

    error_code = "AGENT_ERROR"
    recoverable = True


class AgentCapabilityError(AgentError):
    """Agent lacks required capability."""

    error_code = "AGENT_CAPABILITY_MISSING"


class AgentConvergenceError(AgentError):
    """Strange loop failed to converge."""

    error_code = "AGENT_CONVERGENCE_ERROR"


class AgentNotFoundError(AgentError):
    """Requested agent does not exist."""

    error_code = "AGENT_NOT_FOUND"


class AgentOverloadError(AgentError):
    """Agent workload exceeded capacity."""

    error_code = "AGENT_OVERLOAD"


class AgentLifecycleError(AgentError):
    """Agent lifecycle state invalid for operation."""

    error_code = "AGENT_LIFECYCLE"


class ColonyError(KagamiOSException):
    """Base class for agent colony errors."""

    error_code = "COLONY_ERROR"
    recoverable = True


class ColonyPopulationError(ColonyError):
    """Colony population constraints violated."""

    error_code = "COLONY_POPULATION"


# ============================================================================
# Processing Errors
# ============================================================================


class ProcessingError(KagamiOSException):
    """Base class for processing errors."""

    error_code = "PROCESSING_ERROR"
    recoverable = True


class ModelNotFoundError(ProcessingError):
    """Requested model cannot be found."""

    error_code = "MODEL_NOT_FOUND"


class PredictionError(ProcessingError):
    """World model prediction failed."""

    error_code = "PREDICTION_FAILED"


class PerformanceViolationError(ProcessingError):
    """Operation exceeded performance limits."""

    error_code = "PERFORMANCE_VIOLATION"
    recoverable = True


# ============================================================================
# World Model Errors
# ============================================================================


class WorldModelError(KagamiOSException):
    """Base class for world model errors."""

    error_code = "WORLD_MODEL_ERROR"
    recoverable = True


class ManifoldError(WorldModelError):
    """Manifold geometry constraint violated."""

    error_code = "MANIFOLD_ERROR"


class GeometryError(ManifoldError):
    """G₂ symmetry or geometric invariant violated."""

    error_code = "GEOMETRY_ERROR"


# ============================================================================
# Data & Storage Errors
# ============================================================================


class DataError(KagamiOSException):
    """Base class for data-related errors."""

    error_code = "DATA_ERROR"
    recoverable = True


class SerializationError(DataError):
    """Object serialization/deserialization failed."""

    error_code = "SERIALIZATION_ERROR"


class StorageError(DataError):
    """Persistent storage operation failed."""

    error_code = "STORAGE_ERROR"


class CacheError(DataError):
    """Cache operation failed."""

    error_code = "CACHE_ERROR"


# ============================================================================
# Integration & External Errors
# ============================================================================


class IntegrationError(KagamiOSException):
    """Base class for external integration errors."""

    error_code = "INTEGRATION_ERROR"
    recoverable = True


class LLMError(IntegrationError):
    """LLM service error."""

    error_code = "LLM_ERROR"


class EmbeddingError(IntegrationError):
    """Embedding service error."""

    error_code = "EMBEDDING_ERROR"


class PhysicsError(IntegrationError):
    """Genesis physics simulation error."""

    error_code = "PHYSICS_ERROR"


class ComposioError(IntegrationError):
    """Composio integration error."""

    error_code = "COMPOSIO_ERROR"


class LLMGenerationError(IntegrationError):
    """LLM candidate generation failed."""

    error_code = "LLM_GENERATION_ERROR"


class HTTPClientError(IntegrationError):
    """Base exception for HTTP client errors."""

    error_code = "HTTP_CLIENT_ERROR"


class HTTPTimeoutError(HTTPClientError):
    """HTTP request timed out."""

    error_code = "HTTP_TIMEOUT"


class HTTPRetryError(HTTPClientError):
    """All HTTP retry attempts exhausted."""

    error_code = "HTTP_RETRY_EXHAUSTED"


# ============================================================================
# API Errors
# ============================================================================


class APIError(KagamiOSException):
    """API layer error."""

    error_code = "API_ERROR"
    recoverable = True


class IdempotencyError(APIError):
    """Idempotency violation."""

    error_code = "IDEMPOTENCY_ERROR"


class AuthenticationError(APIError):
    """Authentication failed."""

    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(APIError):
    """Authorization failed (insufficient permissions)."""

    error_code = "AUTHORIZATION_ERROR"


# ============================================================================
# Timeout & Concurrency Errors
# ============================================================================


class KagamiOSTimeoutError(KagamiOSException):
    """Operation timed out.

    Note: Named KagamiOSTimeoutError to avoid shadowing Python's built-in TimeoutError.
    """

    error_code = "TIMEOUT"
    recoverable = True


class ConcurrencyError(KagamiOSException):
    """Concurrency control error (deadlock, race condition)."""

    error_code = "CONCURRENCY_ERROR"
    recoverable = True


# ============================================================================
# Forge-Specific Errors (re-exported for convenience)
# ============================================================================


class ForgeError(ProcessingError):
    """Base exception for all Forge-related errors."""

    error_code = "FORGE_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, context=details)
        self.details = details or {}


# ============================================================================
# Helper Functions
# ============================================================================


def wrap_exception(e: Exception, context: dict[str, Any] | None = None) -> KagamiOSException:
    """Wrap a standard exception in KagamiOSException.

    Args:
        e: Original exception
        context: Additional context

    Returns:
        Wrapped KagamiOSException
    """
    if isinstance(e, KagamiOSException):
        return e

    # Map common exceptions
    if isinstance(e, ValueError):
        return ValidationError(str(e), context=context, cause=e)
    elif isinstance(e, TimeoutError):
        return KagamiOSTimeoutError(str(e), context=context, cause=e)
    elif isinstance(e, MemoryError):
        return ResourceExhaustedError(str(e), context=context, cause=e)
    else:
        return KagamiOSException(str(e), context=context, cause=e)


__all__ = [
    # API
    "APIError",
    "AgentCapabilityError",
    "AgentConvergenceError",
    # Agent
    "AgentError",
    "AgentLifecycleError",
    "AgentNotFoundError",
    "AgentOverloadError",
    "AuthenticationError",
    "AuthorizationError",
    "BootGraphError",
    "CBFViolation",
    "CacheError",
    "CircuitBreakerOpenError",
    "CircuitOpenError",
    "ColonyError",
    "ColonyPopulationError",
    "ComposioError",
    "ConcurrencyError",
    "ConfigurationError",
    # Data
    "DataError",
    "DatabaseUnavailable",
    "EmbeddingError",
    "EncryptionError",
    "EtcdConnectionError",
    "EtcdError",
    "EtcdLeaderError",
    "EtcdQuorumError",
    "EthicalConstraintError",
    "ExternalRepoError",
    "FeatureNotAvailableError",
    # Forge
    "ForgeError",
    "FullOperationError",
    "GeometryError",
    "HTTPClientError",
    "HTTPRetryError",
    "HTTPTimeoutError",
    "HonestyViolation",
    "IdempotencyError",
    # Infrastructure
    "InfrastructureError",
    # Integration
    "IntegrationError",
    # Base
    "KagamiOSException",
    # Concurrency
    "KagamiOSTimeoutError",
    "LLMError",
    "LLMGenerationError",
    "LLMUnavailable",
    "ManifoldError",
    "MemoryLimitViolation",
    "ModelNotFoundError",
    "PerformanceViolationError",
    "PhysicsError",
    "PredictionError",
    # Processing
    "ProcessingError",
    "RateLimitError",
    "ReceiptValidationError",
    "RedisUnavailable",
    # Resources
    "ResourceError",
    "ResourceExhaustedError",
    "RetryExhaustedError",
    # Safety
    "SafetyError",
    "SafetyViolation",
    "SafetyViolationError",
    "SchemaValidationError",
    # Security
    "SecurityError",
    "SerializationError",
    "SignatureVerificationError",
    "StorageError",
    "TICViolationError",
    "ThreatDetected",
    # Validation
    "ValidationError",
    # World Model
    "WorldModelError",
    # Helpers
    "wrap_exception",
]
