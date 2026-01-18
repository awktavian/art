"""Error handlers for FastAPI application.

Provides consistent, structured error responses with:
- K-XXXX error codes for programmatic handling
- Correlation IDs for tracing
- Retryability hints
- Guidance for resolution

Created: Refactored December 4, 2025
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from kagami_api.correlation import get_correlation_id
from kagami_api.structured_errors import (
    KagamiErrorCodes,
    get_error_by_code,
)

logger = logging.getLogger(__name__)


def _build_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    detail: Any = None,
    category: str = "internal",
    retryable: bool = False,
    guidance: list[str] | None = None,
    field: str | None = None,
) -> JSONResponse:
    """Build a consistent structured error response."""
    correlation_id = get_correlation_id() or getattr(request.state, "correlation_id", None)

    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "category": category,
            "retryable": retryable,
        }
    }

    if detail is not None:
        content["error"]["detail"] = detail

    if field:
        content["error"]["field"] = field

    if guidance:
        content["error"]["guidance"] = guidance

    if correlation_id:
        content["error"]["correlation_id"] = correlation_id

    # Add request context for debugging (non-production only)
    import os

    if os.getenv("ENVIRONMENT", "development").lower() != "production":
        content["error"]["path"] = str(request.url.path)
        content["error"]["method"] = request.method

    return JSONResponse(status_code=status_code, content=content)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions with structured error format.

    If the exception detail contains a 'code' field, use it to look up
    the full error definition. Otherwise, map to a default error code.
    """
    # Check if exception already has structured error data
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:  # type: ignore[unreachable]
        # Already structured
        error_code = detail.get("code", "K-5001")  # type: ignore[unreachable]
        error_def = get_error_by_code(error_code)

        return _build_error_response(
            request=request,
            status_code=exc.status_code,
            code=error_code,
            message=detail.get("message", str(exc.detail)),
            detail=detail.get("detail"),
            category=detail.get("category", error_def.category.value if error_def else "internal"),
            retryable=detail.get("retryable", error_def.retryable if error_def else False),
            guidance=detail.get("guidance", error_def.guidance if error_def else None),
        )

    # Map HTTP status to error codes
    status_code = exc.status_code
    error_code: str  # type: ignore[no-redef]
    message: str
    category: str
    retryable: bool
    guidance: list[str] | None

    if status_code == 401:
        ec = KagamiErrorCodes.AUTH_INVALID_CREDENTIALS
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )
    elif status_code == 403:
        ec = KagamiErrorCodes.AUTH_INSUFFICIENT_PERMISSIONS
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )
    elif status_code == 404:
        ec = KagamiErrorCodes.RESOURCE_NOT_FOUND
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )
    elif status_code == 409:
        ec = KagamiErrorCodes.RESOURCE_CONFLICT
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )
    elif status_code == 429:
        ec = KagamiErrorCodes.RATE_LIMIT_EXCEEDED
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )
    elif status_code == 503:
        ec = KagamiErrorCodes.INTERNAL_SERVICE_UNAVAILABLE
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )
    else:
        ec = KagamiErrorCodes.INTERNAL_ERROR
        error_code, message, category, retryable, guidance = (
            ec.code,
            ec.message,
            ec.category.value,
            ec.retryable,
            ec.guidance,
        )

    # Use original detail if it's a string
    detail_str = str(detail) if detail and not isinstance(detail, dict) else None  # type: ignore[unreachable]

    return _build_error_response(
        request=request,
        status_code=status_code,
        code=error_code,
        message=message,
        detail=detail_str,
        category=category,
        retryable=retryable,
        guidance=guidance,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with structured error format."""
    errors = exc.errors()

    # Build field-specific errors
    field_errors: list[dict[str, Any]] = []
    for error in errors:
        loc = error.get("loc", [])
        field = ".".join(str(l) for l in loc if l != "body")
        field_errors.append(
            {
                "field": field,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )

    ec = KagamiErrorCodes.VALIDATION_INVALID_INPUT

    return _build_error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=ec.code,
        message=ec.message,
        detail=field_errors if field_errors else None,
        category=ec.category.value,
        retryable=ec.retryable,
        guidance=[*ec.guidance, "See 'detail' for specific field errors"],
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with structured error format.

    Logs full exception details but returns sanitized error to client.
    """
    correlation_id = get_correlation_id() or getattr(request.state, "correlation_id", "unknown")

    # Log full error details
    logger.error(
        f"[{correlation_id}] Unhandled exception at {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )

    ec = KagamiErrorCodes.INTERNAL_ERROR

    # Don't leak exception type/details in production
    import os

    env = os.getenv("ENVIRONMENT", "development").lower()

    detail = None
    if env != "production":
        detail = f"{type(exc).__name__}: {exc!s}"

    return _build_error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=ec.code,
        message=ec.message,
        detail=detail,
        category=ec.category.value,
        retryable=ec.retryable,
        guidance=ec.guidance,
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Setup all error handlers for the application."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("✅ Structured error handlers configured (K-XXXX codes)")


__all__ = ["setup_error_handlers"]
