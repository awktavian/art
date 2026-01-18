"""Structured Error Codes for K OS API.

Provides programmatic error handling with consistent error codes.
All errors follow the format: K-XXXX where XXXX is a 4-digit code.

Error Code Ranges:
- K-1XXX: Authentication/Authorization errors
- K-2XXX: Validation/Input errors
- K-3XXX: Resource errors (not found, conflict)
- K-4XXX: Rate limiting/Quota errors
- K-5XXX: Internal/System errors
- K-6XXX: External service errors
- K-7XXX: Safety/CBF errors

Created: December 4, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Error category for grouping related errors.

    Each category maps to a range of K-XXXX error codes:
        AUTH: K-1XXX (authentication, authorization, CSRF)
        VALIDATION: K-2XXX (input validation, format, size)
        RESOURCE: K-3XXX (not found, conflict, gone)
        RATE_LIMIT: K-4XXX (rate limits, quotas)
        INTERNAL: K-5XXX (server errors, timeouts, DB)
        EXTERNAL: K-6XXX (external service failures)
        SAFETY: K-7XXX (CBF violations, content filtering)
    """

    AUTH = "authentication"  # K-1XXX: Auth/permission errors
    VALIDATION = "validation"  # K-2XXX: Input/format errors
    RESOURCE = "resource"  # K-3XXX: Resource state errors
    RATE_LIMIT = "rate_limit"  # K-4XXX: Throttling errors
    INTERNAL = "internal"  # K-5XXX: Server errors
    EXTERNAL = "external"  # K-6XXX: Upstream service errors
    SAFETY = "safety"  # K-7XXX: Safety constraint errors


@dataclass(frozen=True)
class ErrorCode:
    """Structured error code definition.

    Immutable definition of an error code with all metadata needed
    for consistent error responses across the API.

    Attributes:
        code: K-XXXX format code (e.g., "K-1001")
        message: Human-readable error message
        category: ErrorCategory for grouping
        http_status: HTTP status code to return
        retryable: True if client should retry
        guidance: List of suggestions for resolving the error

    Example:
        MY_ERROR = ErrorCode(
            code="K-9001",
            message="Custom error",
            category=ErrorCategory.INTERNAL,
            http_status=500,
            retryable=True,
            guidance=["Try again later"]
        )
    """

    code: str  # K-XXXX format
    message: str  # Human-readable message
    category: ErrorCategory  # Error grouping
    http_status: int  # HTTP status code
    retryable: bool = False  # Can client retry?
    guidance: list[str] = field(default_factory=list)  # Resolution hints


# =============================================================================
# ERROR CODE REGISTRY
# =============================================================================


class KagamiErrorCodes:
    """Registry of all K OS error codes.

    Class-level attributes are ErrorCode definitions.
    Use with raise_error() or KagamiError.to_response().

    Error Code Ranges:
        K-1XXX: Authentication/Authorization
        K-2XXX: Validation/Input
        K-3XXX: Resource (not found, conflict)
        K-4XXX: Rate limiting/Quota
        K-5XXX: Internal/System
        K-6XXX: External service
        K-7XXX: Safety/CBF
        K-8XXX: WebSocket

    Example:
        from kagami_api.structured_errors import KagamiErrorCodes, raise_error

        raise_error(
            KagamiErrorCodes.AUTH_TOKEN_EXPIRED,
            detail="Token expired 5 minutes ago"
        )
    """

    # -------------------------------------------------------------------------
    # Authentication Errors (K-1XXX) — Login, tokens, permissions
    # -------------------------------------------------------------------------
    AUTH_MISSING_CREDENTIALS = ErrorCode(
        code="K-1001",
        message="Authentication credentials are required",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        guidance=["Provide an API key via Authorization header", "Or provide a JWT token"],
    )

    AUTH_INVALID_CREDENTIALS = ErrorCode(
        code="K-1002",
        message="Invalid authentication credentials",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        guidance=["Check your API key or token is correct", "Tokens may have expired"],
    )

    AUTH_TOKEN_EXPIRED = ErrorCode(
        code="K-1003",
        message="Authentication token has expired",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        retryable=True,
        guidance=["Refresh your token using /api/user/refresh", "Or re-authenticate"],
    )

    AUTH_TOKEN_REVOKED = ErrorCode(
        code="K-1004",
        message="Authentication token has been revoked",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        guidance=["Re-authenticate to get a new token"],
    )

    AUTH_ACCOUNT_LOCKED = ErrorCode(
        code="K-1005",
        message="Account is temporarily locked due to failed login attempts",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        retryable=True,
        guidance=["Wait for the lockout period to expire", "Contact support if needed"],
    )

    AUTH_INSUFFICIENT_PERMISSIONS = ErrorCode(
        code="K-1010",
        message="Insufficient permissions for this operation",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_403_FORBIDDEN,
        guidance=["Check required permissions for this endpoint", "Contact admin for access"],
    )

    AUTH_CSRF_INVALID = ErrorCode(
        code="K-1020",
        message="Invalid or missing CSRF token",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_403_FORBIDDEN,
        guidance=["Include X-CSRF-Token header", "Get token from /api/user/csrf-token"],
    )

    # -------------------------------------------------------------------------
    # Validation Errors (K-2XXX) — Input format, size, security checks
    # -------------------------------------------------------------------------

    VALIDATION_INVALID_INPUT = ErrorCode(
        code="K-2001",
        message="Invalid input data",
        category=ErrorCategory.VALIDATION,
        http_status=422,  # HTTP_422_UNPROCESSABLE_CONTENT
        guidance=["Check request body format", "See API documentation for schema"],
    )

    VALIDATION_MISSING_FIELD = ErrorCode(
        code="K-2002",
        message="Required field is missing",
        category=ErrorCategory.VALIDATION,
        http_status=422,  # HTTP_422_UNPROCESSABLE_CONTENT
        guidance=["Include all required fields in request"],
    )

    VALIDATION_INVALID_FORMAT = ErrorCode(
        code="K-2003",
        message="Field format is invalid",
        category=ErrorCategory.VALIDATION,
        http_status=422,  # HTTP_422_UNPROCESSABLE_CONTENT
        guidance=["Check field type and format requirements"],
    )

    VALIDATION_PATH_TRAVERSAL = ErrorCode(
        code="K-2010",
        message="Path traversal attempt detected",
        category=ErrorCategory.VALIDATION,
        http_status=status.HTTP_400_BAD_REQUEST,
        guidance=["Use relative paths without '..' sequences"],
    )

    VALIDATION_SQL_INJECTION = ErrorCode(
        code="K-2011",
        message="Potential SQL injection detected",
        category=ErrorCategory.VALIDATION,
        http_status=status.HTTP_400_BAD_REQUEST,
        guidance=["Remove SQL keywords from input"],
    )

    VALIDATION_PAYLOAD_TOO_LARGE = ErrorCode(
        code="K-2020",
        message="Request payload is too large",
        category=ErrorCategory.VALIDATION,
        http_status=413,  # HTTP_413_CONTENT_TOO_LARGE
        guidance=["Reduce payload size", "Maximum size is 1MB for most endpoints"],
    )

    VALIDATION_IDEMPOTENCY_KEY_MISSING = ErrorCode(
        code="K-2030",
        message="Idempotency-Key header is required for mutating operations",
        category=ErrorCategory.VALIDATION,
        http_status=status.HTTP_400_BAD_REQUEST,
        guidance=["Include Idempotency-Key header with a unique value"],
    )

    VALIDATION_IDEMPOTENCY_KEY_DUPLICATE = ErrorCode(
        code="K-2031",
        message="Request with this Idempotency-Key already processed",
        category=ErrorCategory.VALIDATION,
        http_status=status.HTTP_409_CONFLICT,
        guidance=["Use a new Idempotency-Key for new requests"],
    )

    # -------------------------------------------------------------------------
    # Resource Errors (K-3XXX) — CRUD state, conflicts, not found
    # -------------------------------------------------------------------------

    RESOURCE_NOT_FOUND = ErrorCode(
        code="K-3001",
        message="Requested resource not found",
        category=ErrorCategory.RESOURCE,
        http_status=status.HTTP_404_NOT_FOUND,
        guidance=["Check the resource ID is correct", "Resource may have been deleted"],
    )

    RESOURCE_ALREADY_EXISTS = ErrorCode(
        code="K-3002",
        message="Resource already exists",
        category=ErrorCategory.RESOURCE,
        http_status=status.HTTP_409_CONFLICT,
        guidance=["Use update instead of create", "Or delete existing resource first"],
    )

    RESOURCE_CONFLICT = ErrorCode(
        code="K-3003",
        message="Resource conflict detected",
        category=ErrorCategory.RESOURCE,
        http_status=status.HTTP_409_CONFLICT,
        retryable=True,
        guidance=["Refresh resource and retry", "Another request may have modified it"],
    )

    RESOURCE_GONE = ErrorCode(
        code="K-3004",
        message="Resource has been permanently deleted",
        category=ErrorCategory.RESOURCE,
        http_status=status.HTTP_410_GONE,
        guidance=["Resource cannot be recovered"],
    )

    # -------------------------------------------------------------------------
    # Rate Limiting Errors (K-4XXX) — Throttling, quotas
    # -------------------------------------------------------------------------

    RATE_LIMIT_EXCEEDED = ErrorCode(
        code="K-4001",
        message="Rate limit exceeded",
        category=ErrorCategory.RATE_LIMIT,
        http_status=status.HTTP_429_TOO_MANY_REQUESTS,
        retryable=True,
        guidance=["Wait before retrying", "Check Retry-After header for wait time"],
    )

    QUOTA_EXCEEDED = ErrorCode(
        code="K-4002",
        message="Usage quota exceeded",
        category=ErrorCategory.RATE_LIMIT,
        http_status=status.HTTP_429_TOO_MANY_REQUESTS,
        guidance=["Upgrade your plan for higher limits", "Contact support for quota increase"],
    )

    # -------------------------------------------------------------------------
    # Internal Errors (K-5XXX) — Server errors, database, cache
    # -------------------------------------------------------------------------

    INTERNAL_ERROR = ErrorCode(
        code="K-5001",
        message="Internal server error",
        category=ErrorCategory.INTERNAL,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=True,
        guidance=["Retry the request", "Contact support if error persists"],
    )

    INTERNAL_TIMEOUT = ErrorCode(
        code="K-5002",
        message="Request processing timeout",
        category=ErrorCategory.INTERNAL,
        http_status=status.HTTP_504_GATEWAY_TIMEOUT,
        retryable=True,
        guidance=["Retry the request", "Consider smaller batch sizes"],
    )

    INTERNAL_SERVICE_UNAVAILABLE = ErrorCode(
        code="K-5003",
        message="Service temporarily unavailable",
        category=ErrorCategory.INTERNAL,
        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        retryable=True,
        guidance=["Check service health at /api/vitals/probes/ready", "Retry after a moment"],
    )

    INTERNAL_DATABASE_ERROR = ErrorCode(
        code="K-5010",
        message="Database operation failed",
        category=ErrorCategory.INTERNAL,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=True,
        guidance=["Retry the request"],
    )

    INTERNAL_CACHE_ERROR = ErrorCode(
        code="K-5011",
        message="Cache operation failed",
        category=ErrorCategory.INTERNAL,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=True,
        guidance=["Request may still succeed on retry"],
    )

    # -------------------------------------------------------------------------
    # External Service Errors (K-6XXX) — Upstream dependencies
    # -------------------------------------------------------------------------

    EXTERNAL_SERVICE_ERROR = ErrorCode(
        code="K-6001",
        message="External service error",
        category=ErrorCategory.EXTERNAL,
        http_status=status.HTTP_502_BAD_GATEWAY,
        retryable=True,
        guidance=["External dependency may be unavailable", "Retry after a moment"],
    )

    EXTERNAL_SERVICE_TIMEOUT = ErrorCode(
        code="K-6002",
        message="External service timeout",
        category=ErrorCategory.EXTERNAL,
        http_status=status.HTTP_504_GATEWAY_TIMEOUT,
        retryable=True,
        guidance=["External service is slow", "Retry the request"],
    )

    # -------------------------------------------------------------------------
    # Safety Errors (K-7XXX) — CBF violations, content filtering
    # -------------------------------------------------------------------------

    SAFETY_CBF_VIOLATION = ErrorCode(
        code="K-7001",
        message="Safety constraint violated (h(x) < 0)",
        category=ErrorCategory.SAFETY,
        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        retryable=True,
        guidance=[
            "Reduce request complexity",
            "Authenticate if not already",
            "Use safer HTTP method",
            "Try again later",
        ],
    )

    SAFETY_CONTENT_BLOCKED = ErrorCode(
        code="K-7002",
        message="Content blocked by safety filters",
        category=ErrorCategory.SAFETY,
        http_status=status.HTTP_400_BAD_REQUEST,
        guidance=["Review content for policy violations", "Contact support if incorrect"],
    )

    SAFETY_RISK_TOO_HIGH = ErrorCode(
        code="K-7003",
        message="Operation risk level too high",
        category=ErrorCategory.SAFETY,
        http_status=status.HTTP_403_FORBIDDEN,
        guidance=["Confirm operation with confirm=true parameter", "Or reduce operation scope"],
    )

    # -------------------------------------------------------------------------
    # WebSocket Errors (K-8XXX) — Real-time connection issues
    # -------------------------------------------------------------------------

    WS_AUTH_TIMEOUT = ErrorCode(
        code="K-8001",
        message="WebSocket authentication timeout",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        guidance=["Send auth frame within 5 seconds of connection"],
    )

    WS_AUTH_INVALID = ErrorCode(
        code="K-8002",
        message="WebSocket authentication failed",
        category=ErrorCategory.AUTH,
        http_status=status.HTTP_401_UNAUTHORIZED,
        guidance=["Check API key or token is valid", "Ensure proper auth frame format"],
    )

    WS_RATE_LIMITED = ErrorCode(
        code="K-8003",
        message="WebSocket rate limit exceeded",
        category=ErrorCategory.RATE_LIMIT,
        http_status=status.HTTP_429_TOO_MANY_REQUESTS,
        retryable=True,
        guidance=["Reduce message frequency", "Implement client-side throttling"],
    )

    WS_CONNECTION_CLOSED = ErrorCode(
        code="K-8004",
        message="WebSocket connection closed unexpectedly",
        category=ErrorCategory.INTERNAL,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=True,
        guidance=["Reconnect with exponential backoff", "Check network connectivity"],
    )

    WS_INVALID_MESSAGE = ErrorCode(
        code="K-8005",
        message="Invalid WebSocket message format",
        category=ErrorCategory.VALIDATION,
        http_status=status.HTTP_400_BAD_REQUEST,
        guidance=["Check message follows expected JSON schema", "Include required fields"],
    )

    WS_ROOM_NOT_FOUND = ErrorCode(
        code="K-8006",
        message="WebSocket room not found",
        category=ErrorCategory.RESOURCE,
        http_status=status.HTTP_404_NOT_FOUND,
        guidance=["Create room before joining", "Check room ID is correct"],
    )


# =============================================================================
# ERROR RESPONSE BUILDER
# =============================================================================


@dataclass
class KagamiError:
    """Structured error for K OS API responses.

    Combines an ErrorCode with request-specific context to build
    consistent error responses.

    Attributes:
        error_code: The ErrorCode definition
        detail: Additional context for this specific error
        field: Field name if this is a validation error
        metadata: Extra data to include in response

    Example:
        error = KagamiError(
            error_code=KagamiErrorCodes.VALIDATION_MISSING_FIELD,
            detail="email is required",
            field="email"
        )
        return error.to_response(correlation_id="req-123")
    """

    error_code: ErrorCode  # Base error definition
    detail: str | None = None  # Request-specific detail
    field: str | None = None  # Field name for validation errors
    metadata: dict[str, Any] | None = None  # Additional response data

    def to_response(self, correlation_id: str | None = None) -> JSONResponse:
        """Convert to FastAPI JSONResponse with structured error body.

        Returns JSON with format:
            {
                "error": {
                    "code": "K-XXXX",
                    "message": "...",
                    "category": "...",
                    "retryable": true/false,
                    "detail": "...",  // if provided
                    "field": "...",   // if provided
                    "guidance": [...],
                    "correlation_id": "..."  // if provided
                }
            }
        """
        content: dict[str, Any] = {
            "error": {
                "code": self.error_code.code,
                "message": self.error_code.message,
                "category": self.error_code.category.value,
                "retryable": self.error_code.retryable,
            }
        }

        if self.detail:
            content["error"]["detail"] = self.detail

        if self.field:
            content["error"]["field"] = self.field

        if self.error_code.guidance:
            content["error"]["guidance"] = self.error_code.guidance

        if self.metadata:
            content["error"]["metadata"] = self.metadata

        if correlation_id:
            content["error"]["correlation_id"] = correlation_id

        return JSONResponse(
            status_code=self.error_code.http_status,
            content=content,
        )

    def to_exception(self) -> HTTPException:
        """Convert to HTTPException for raising.

        Use this when you need to raise an exception rather than
        return a response directly.

        Returns:
            HTTPException with structured detail dict
        """
        return HTTPException(
            status_code=self.error_code.http_status,
            detail={
                "code": self.error_code.code,
                "message": self.error_code.message,
                "detail": self.detail,
                "category": self.error_code.category.value,
                "retryable": self.error_code.retryable,
                "guidance": self.error_code.guidance,
            },
        )


def raise_error(
    error_code: ErrorCode,
    detail: str | None = None,
    field: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Raise a structured K OS error.

    Args:
        error_code: The error code from KagamiErrorCodes
        detail: Additional detail message
        field: Field name if validation error
        metadata: Additional metadata

    Raises:
        HTTPException: With structured error payload
    """
    error = KagamiError(error_code=error_code, detail=detail, field=field, metadata=metadata)
    raise error.to_exception()


# =============================================================================
# ERROR CODE LOOKUP — Runtime introspection of error codes
# =============================================================================


# Lazily-built cache of code string → ErrorCode
_ERROR_CODE_MAP: dict[str, ErrorCode] = {}


def _build_error_map() -> None:
    """Build error code lookup map (lazy initialization).

    Scans KagamiErrorCodes for ErrorCode attributes and builds
    a code-string → ErrorCode mapping for O(1) lookup.
    """
    global _ERROR_CODE_MAP
    if _ERROR_CODE_MAP:
        return

    for attr_name in dir(KagamiErrorCodes):
        if attr_name.startswith("_"):
            continue
        attr = getattr(KagamiErrorCodes, attr_name)
        if isinstance(attr, ErrorCode):
            _ERROR_CODE_MAP[attr.code] = attr


def get_error_by_code(code: str) -> ErrorCode | None:
    """Look up an error code by its code string.

    Args:
        code: K-XXXX format code string (e.g., "K-1001")

    Returns:
        ErrorCode if found, None otherwise

    Example:
        error = get_error_by_code("K-1003")
        if error:
            print(f"Message: {error.message}")
    """
    _build_error_map()
    return _ERROR_CODE_MAP.get(code)


def list_error_codes() -> list[dict[str, Any]]:
    """List all error codes for documentation.

    Returns a list of dicts suitable for API documentation or
    error code reference pages.

    Returns:
        List of dicts with code, message, category, http_status, retryable
        Sorted by code string (K-1001, K-1002, ...)
    """
    _build_error_map()
    return [
        {
            "code": ec.code,
            "message": ec.message,
            "category": ec.category.value,
            "http_status": ec.http_status,
            "retryable": ec.retryable,
        }
        for ec in sorted(_ERROR_CODE_MAP.values(), key=lambda x: x.code)
    ]


__all__ = [
    "ErrorCategory",
    "ErrorCode",
    "KagamiError",
    "KagamiErrorCodes",
    "get_error_by_code",
    "list_error_codes",
    "raise_error",
]
