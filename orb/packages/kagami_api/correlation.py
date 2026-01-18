"""Request Correlation ID Middleware for K OS API.

Ensures every request has a correlation ID for distributed tracing.
Adds X-Request-ID and X-Correlation-ID headers to all responses.

Features:
- Generates unique request IDs
- Propagates correlation IDs across services
- Integrates with OpenTelemetry trace context (W3C Trace Context)
- Tracks request timing

Created: December 4, 2025
Enhanced: December 5, 2025 - Added W3C Trace Context support
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variables for request lifecycle
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
request_start_time_var: ContextVar[float] = ContextVar("request_start_time", default=0.0)
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")


def get_correlation_id() -> str:
    """Get the current request's correlation ID from context."""
    return correlation_id_var.get()


def get_trace_id() -> str:
    """Get the current request's trace ID from context."""
    return trace_id_var.get()


def get_span_id() -> str:
    """Get the current request's span ID from context."""
    return span_id_var.get()


def generate_request_id() -> str:
    """Generate a unique request ID.

    Delegates to canonical implementation in kagami.core.utils.ids.
    Format: 'req_{hex16}' (uses underscore, not hyphen, for consistency).
    """
    from kagami.core.utils.ids import generate_request_id as _gen_request_id

    return _gen_request_id()


def generate_trace_id() -> str:
    """Generate a W3C-compliant trace ID (32 hex chars)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a W3C-compliant span ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def parse_traceparent(header: str | None) -> tuple[str, str] | None:
    """Parse W3C traceparent header.

    Format: {version}-{trace-id}-{parent-span-id}-{flags}
    Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01

    Returns:
        Tuple of (trace_id, parent_span_id) or None if invalid
    """
    if not header:
        return None

    try:
        parts = header.split("-")
        if len(parts) != 4:
            return None
        version, trace_id, parent_span_id, _flags = parts

        # Validate format
        if version != "00" or len(trace_id) != 32 or len(parent_span_id) != 16:
            return None

        return trace_id, parent_span_id
    except Exception:
        return None


def build_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Build W3C traceparent header.

    Args:
        trace_id: 32 hex char trace ID
        span_id: 16 hex char span ID
        sampled: Whether trace is sampled

    Returns:
        W3C traceparent header value
    """
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware to add correlation IDs and trace context to all requests.

    Headers added to response:
    - X-Request-ID: Unique ID for this request
    - X-Correlation-ID: ID for distributed tracing (from request or generated)
    - X-Response-Time: Request processing time in milliseconds
    - traceparent: W3C Trace Context propagation header

    Headers read from request:
    - X-Request-ID: If provided, used as request ID
    - X-Correlation-ID: If provided, used for distributed tracing
    - traceparent: W3C Trace Context header (if provided)
    - tracestate: W3C Trace Context vendor-specific state
    """
    start_time = time.perf_counter()
    request_start_time_var.set(start_time)

    # Parse W3C Trace Context if present
    traceparent = request.headers.get("traceparent")
    parsed = parse_traceparent(traceparent)

    if parsed:
        trace_id, _parent_span_id = parsed
        span_id = generate_span_id()  # New span for this request
    else:
        trace_id = generate_trace_id()
        span_id = generate_span_id()

    # Extract or generate correlation ID
    correlation_id = (
        request.headers.get("X-Correlation-ID")
        or request.headers.get("X-Request-ID")
        or f"req-{trace_id[:16]}"
    )

    # Set in context for use by handlers
    correlation_token = correlation_id_var.set(correlation_id)
    trace_token = trace_id_var.set(trace_id)
    span_token = span_id_var.set(span_id)

    # Attach to request state for route handlers
    try:
        request.state.correlation_id = correlation_id
        request.state.request_id = correlation_id
        request.state.trace_id = trace_id
        request.state.span_id = span_id
    except Exception:
        pass  # Request state may be unavailable in some contexts

    # Integrate with OpenTelemetry if available
    otel_span = None
    try:
        if os.getenv("OTEL_ENABLED", "0").lower() in ("1", "true"):
            from opentelemetry import trace as otel_trace

            tracer = otel_trace.get_tracer("kagami.api")
            otel_span = tracer.start_span(
                f"{request.method} {request.url.path}",
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.route": request.url.path,
                    "kagami.correlation_id": correlation_id,
                },
            )
    except Exception:
        pass  # OpenTelemetry optional

    try:
        response = await call_next(request)

        # Calculate response time
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add correlation headers to response
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Add W3C Trace Context headers
        response.headers["traceparent"] = build_traceparent(trace_id, span_id)
        # Preserve tracestate if present
        if tracestate := request.headers.get("tracestate"):
            response.headers["tracestate"] = tracestate

        # Update OpenTelemetry span
        if otel_span:
            try:
                otel_span.set_attribute("http.status_code", response.status_code)
                otel_span.end()
            except Exception:
                pass  # OTel cleanup best-effort

        # Log request completion (INFO for slow requests, DEBUG otherwise)
        if duration_ms > 100:
            logger.info(
                f"[{correlation_id}] {request.method} {request.url.path} "
                f"completed in {duration_ms:.2f}ms (status={response.status_code})"
            )
        else:
            logger.debug(
                f"[{correlation_id}] {request.method} {request.url.path} "
                f"completed in {duration_ms:.2f}ms"
            )

        return response

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"[{correlation_id}] {request.method} {request.url.path} "
            f"failed after {duration_ms:.2f}ms: {e}"
        )

        if otel_span:
            try:
                otel_span.set_attribute("error", True)
                otel_span.set_attribute("error.message", str(e))
                otel_span.end()
            except Exception:
                pass  # OTel cleanup best-effort

        raise

    finally:
        # Reset context
        correlation_id_var.reset(correlation_token)
        trace_id_var.reset(trace_token)
        span_id_var.reset(span_token)


def get_request_context() -> dict[str, Any]:
    """Get current request context for logging/receipts."""
    return {
        "correlation_id": correlation_id_var.get() or "unknown",
        "trace_id": trace_id_var.get() or "unknown",
        "span_id": span_id_var.get() or "unknown",
        "request_start_time": request_start_time_var.get(),
    }


def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]:
    """Inject trace headers for outgoing requests.

    Use when making HTTP calls to other services to propagate trace context.

    Args:
        headers: Existing headers dict

    Returns:
        Headers dict with trace context added
    """
    headers = dict(headers)  # Copy to avoid mutation

    correlation_id = correlation_id_var.get()
    trace_id = trace_id_var.get()
    span_id = span_id_var.get()

    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
        headers["X-Request-ID"] = correlation_id

    if trace_id and span_id:
        headers["traceparent"] = build_traceparent(trace_id, span_id)

    return headers


__all__ = [
    "build_traceparent",
    "correlation_id_var",
    "correlation_middleware",
    "generate_request_id",
    "generate_span_id",
    "generate_trace_id",
    "get_correlation_id",
    "get_request_context",
    "get_span_id",
    "get_trace_id",
    "inject_trace_headers",
    "parse_traceparent",
    "span_id_var",
    "trace_id_var",
]
