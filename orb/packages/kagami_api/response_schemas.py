"""Response Schemas for K OS API.

Provides standardized response models for OpenAPI documentation
and runtime validation. Ensures consistent response structure
across all endpoints.

Created: December 5, 2025
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeAlias, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

OpenAPIResponseSpec: TypeAlias = dict[str, Any]
OpenAPIResponses: TypeAlias = dict[int | str, OpenAPIResponseSpec]


# =============================================================================
# ERROR RESPONSE SCHEMAS
# =============================================================================


class ErrorDetail(BaseModel):
    """Structured error detail for K OS API responses."""

    code: str = Field(description="Error code (K-XXXX format)")
    message: str = Field(description="Human-readable error message")
    category: str = Field(description="Error category (auth, validation, etc.)")
    retryable: bool = Field(default=False, description="Whether operation can be retried")
    detail: str | None = Field(default=None, description="Additional error detail")
    field: str | None = Field(default=None, description="Field name for validation errors")
    guidance: list[str] | None = Field(default=None, description="Steps to resolve the error")
    correlation_id: str | None = Field(default=None, description="Request correlation ID")


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail = Field(description="Error details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": {
                        "code": "K-1002",
                        "message": "Invalid authentication credentials",
                        "category": "authentication",
                        "retryable": False,
                        "guidance": ["Check your API key or token is correct"],
                        "correlation_id": "req-abc123def456",
                    }
                }
            ]
        }
    }


# =============================================================================
# SUCCESS RESPONSE SCHEMAS
# =============================================================================


class SuccessResponse(BaseModel, Generic[T]):
    """Generic success response envelope with typed data."""

    data: T = Field(description="Response payload")
    meta: dict[str, Any] | None = Field(default=None, description="Response metadata")


class PaginatedMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(description="Total number of items")
    page: int = Field(default=1, ge=1, description="Current page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    pages: int = Field(description="Total number of pages")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    data: list[T] = Field(description="List of items")
    meta: PaginatedMeta = Field(description="Pagination metadata")


# =============================================================================
# COMMON RESPONSE SCHEMAS
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    probe: str = Field(description="Probe type (liveness, readiness, deep)")
    checks: dict[str, dict[str, Any]] | None = Field(
        default=None, description="Individual component checks"
    )
    duration_ms: float | None = Field(default=None, description="Check duration in milliseconds")


class ActionResponse(BaseModel):
    """Response for action/mutation operations."""

    success: bool = Field(description="Whether the action succeeded")
    message: str = Field(description="Human-readable result message")
    correlation_id: str | None = Field(default=None, description="Request correlation ID")
    data: dict[str, Any] | None = Field(default=None, description="Action result data")


class ReceiptResponse(BaseModel):
    """Receipt for a completed operation."""

    receipt_id: str = Field(description="Unique receipt identifier")
    correlation_id: str = Field(description="Request correlation ID")
    phase: str = Field(description="Receipt phase: PLAN, EXECUTE, VERIFY")
    status: str = Field(description="Operation status: success, failure, partial")
    timestamp: datetime = Field(default_factory=datetime.now, description="Receipt timestamp")
    data: dict[str, Any] | None = Field(default=None, description="Receipt data")


# =============================================================================
# OPENAPI RESPONSE DEFINITIONS
# =============================================================================


# Standard responses for common HTTP status codes
RESPONSES_401 = {
    "description": "Authentication required",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-1001",
                    "message": "Authentication credentials are required",
                    "category": "authentication",
                    "retryable": False,
                    "guidance": ["Provide an API key via Authorization header"],
                }
            },
        }
    },
}

RESPONSES_403 = {
    "description": "Insufficient permissions",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-1010",
                    "message": "Insufficient permissions for this operation",
                    "category": "authentication",
                    "retryable": False,
                }
            },
        }
    },
}

RESPONSES_404 = {
    "description": "Resource not found",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-3001",
                    "message": "Requested resource not found",
                    "category": "resource",
                    "retryable": False,
                }
            },
        }
    },
}

RESPONSES_422 = {
    "description": "Validation error",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-2001",
                    "message": "Invalid input data",
                    "category": "validation",
                    "retryable": False,
                    "detail": [{"field": "name", "message": "Field required"}],
                }
            },
        }
    },
}

RESPONSES_429 = {
    "description": "Rate limit exceeded",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-4001",
                    "message": "Rate limit exceeded",
                    "category": "rate_limit",
                    "retryable": True,
                    "guidance": ["Wait before retrying", "Check Retry-After header"],
                }
            },
        }
    },
}

RESPONSES_500 = {
    "description": "Internal server error",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-5001",
                    "message": "Internal server error",
                    "category": "internal",
                    "retryable": True,
                }
            },
        }
    },
}

RESPONSES_503 = {
    "description": "Service unavailable",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-5003",
                    "message": "Service temporarily unavailable",
                    "category": "internal",
                    "retryable": True,
                }
            },
        }
    },
}


RESPONSES_400 = {
    "description": "Bad request",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-2000",
                    "message": "Invalid request parameters",
                    "category": "validation",
                    "retryable": False,
                }
            },
        }
    },
}

RESPONSES_504 = {
    "description": "Gateway timeout",
    "content": {
        "application/json": {
            "schema": ErrorResponse.model_json_schema(),
            "example": {
                "error": {
                    "code": "K-5004",
                    "message": "Request timeout exceeded",
                    "category": "timeout",
                    "retryable": True,
                }
            },
        }
    },
}

# Convenience dict for common error responses
COMMON_ERROR_RESPONSES: dict[int, OpenAPIResponseSpec] = {
    400: RESPONSES_400,
    401: RESPONSES_401,
    403: RESPONSES_403,
    404: RESPONSES_404,
    422: RESPONSES_422,
    429: RESPONSES_429,
    500: RESPONSES_500,
    503: RESPONSES_503,
    504: RESPONSES_504,
}


def get_error_responses(*status_codes: int) -> OpenAPIResponses:
    """Get error response definitions for specified status codes.

    Usage:
        @router.get("/resource", responses=get_error_responses(401, 404, 500))
        async def get_resource(): ...
    """
    return {
        code: COMMON_ERROR_RESPONSES[code]
        for code in status_codes
        if code in COMMON_ERROR_RESPONSES
    }


# =============================================================================
# RESPONSE ENVELOPE HELPERS
# =============================================================================


def success_envelope(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap data in a success response envelope.

    Args:
        data: Response payload
        meta: Optional metadata

    Returns:
        Dict with 'data' and optional 'meta' keys
    """
    response = {"data": data}
    if meta:
        response["meta"] = meta
    return response


def paginated_envelope(
    items: list[Any],
    total: int,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """Wrap list in a paginated response envelope.

    Args:
        items: List of items
        total: Total count
        page: Current page
        per_page: Items per page

    Returns:
        Dict with 'data' and 'meta' for pagination
    """
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return {
        "data": items,
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        },
    }


def action_envelope(
    success: bool,
    message: str,
    correlation_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an action response envelope.

    Args:
        success: Whether action succeeded
        message: Result message
        correlation_id: Optional correlation ID
        data: Optional result data

    Returns:
        Action response dict
    """
    response = {
        "success": success,
        "message": message,
    }
    if correlation_id:
        response["correlation_id"] = correlation_id
    if data:
        response["data"] = data
    return response


# =============================================================================
# STATUS RESPONSE HELPERS (for common dict returns)
# =============================================================================


class StatusResponse(BaseModel):
    """Generic status response for health checks and probes."""

    status: str = Field(description="Status: healthy, degraded, unhealthy, unavailable, error")
    error: str | None = Field(
        default=None, description="Error message if status is error/unhealthy"
    )
    latency_ms: float | None = Field(default=None, description="Latency in milliseconds")

    @classmethod
    def healthy(cls, latency_ms: float | None = None) -> StatusResponse:
        """Create a healthy status response."""
        return cls(status="healthy", latency_ms=latency_ms)

    @classmethod
    def unhealthy(cls, error: str, latency_ms: float | None = None) -> StatusResponse:
        """Create an unhealthy status response."""
        return cls(status="unhealthy", error=error, latency_ms=latency_ms)

    @classmethod
    def unavailable(cls, error: str | None = None) -> StatusResponse:
        """Create an unavailable status response."""
        return cls(status="unavailable", error=error)

    @classmethod
    def degraded(cls, error: str | None = None) -> StatusResponse:
        """Create a degraded status response."""
        return cls(status="degraded", error=error)


class ServiceHealthResponse(BaseModel):
    """Aggregated health response for multiple services.

    Note: Individual service health uses StatusResponse which has the same fields
    as the removed DependencyHealthResponse (status, latency_ms, error).
    """

    status: str = Field(description="Overall status")
    services: dict[str, StatusResponse] = Field(
        default_factory=dict, description="Individual service health"
    )


def status_envelope(  # type: ignore[no-untyped-def]
    status: str,
    error: str | None = None,
    latency_ms: float | None = None,
    **extra,
) -> dict[str, Any]:
    """Create a status response dict.

    Args:
        status: Status string (healthy, unhealthy, etc.)
        error: Optional error message
        latency_ms: Optional latency measurement
        **extra: Additional fields to include

    Returns:
        Status response dict

    Example:
        >>> status_envelope("healthy", latency_ms=50.5)
        {"status": "healthy", "latency_ms": 50.5}
        >>> status_envelope("unhealthy", error="Connection refused")
        {"status": "unhealthy", "error": "Connection refused"}
    """
    response: dict[str, Any] = {"status": status}
    if error:
        response["error"] = error
    if latency_ms is not None:
        response["latency_ms"] = round(latency_ms, 2)
    response.update(extra)
    return response


def list_envelope(
    items: list[Any],
    count: int | None = None,
    key: str = "items",
) -> dict[str, Any]:
    """Create a list response dict.

    Args:
        items: List of items
        count: Optional count (defaults to len(items))
        key: Key name for the list (default: "items")

    Returns:
        List response dict

    Example:
        >>> list_envelope([{"id": 1}, {"id": 2}], key="agents")
        {"agents": [...], "count": 2}
    """
    return {key: items, "count": count if count is not None else len(items)}


def ok_envelope(message: str = "ok", **data) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Create a simple OK response dict.

    Args:
        message: Status message (default: "ok")
        **data: Additional data to include

    Returns:
        OK response dict

    Example:
        >>> ok_envelope()
        {"status": "ok"}
        >>> ok_envelope("created", id="abc123")
        {"status": "created", "id": "abc123"}
    """
    response: dict[str, Any] = {"status": message}
    response.update(data)
    return response


__all__ = [
    # OpenAPI response definitions
    "COMMON_ERROR_RESPONSES",
    "RESPONSES_400",
    "RESPONSES_401",
    "RESPONSES_403",
    "RESPONSES_404",
    "RESPONSES_422",
    "RESPONSES_429",
    "RESPONSES_500",
    "RESPONSES_503",
    "RESPONSES_504",
    # Error schemas
    "ErrorDetail",
    "ErrorResponse",
    # Success schemas
    "SuccessResponse",
    "PaginatedMeta",
    "PaginatedResponse",
    # Common schemas
    "HealthResponse",
    "ActionResponse",
    "ReceiptResponse",
    # Status schemas (for health checks)
    "StatusResponse",
    "ServiceHealthResponse",
    # Envelope helpers
    "success_envelope",
    "paginated_envelope",
    "action_envelope",
    "status_envelope",
    "list_envelope",
    "ok_envelope",
    "get_error_responses",
]
