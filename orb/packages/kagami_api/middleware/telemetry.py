"""Telemetry middleware for request tracing.

Provides TelemetryMiddleware for basic request metrics and
TracingMiddleware for distributed tracing (requires OTEL).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Lightweight telemetry middleware for request timing and metrics.

    Records:
    - Request duration
    - Status codes
    - Path patterns

    Does NOT require OpenTelemetry - uses internal metrics if OTEL unavailable.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # Execute request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log slow requests (>1s) at warning level
        if duration_ms > 1000:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} took {duration_ms:.0f}ms"
            )

        return response  # type: ignore[no-any-return]


class TracingMiddleware(BaseHTTPMiddleware):
    """Distributed tracing middleware using OpenTelemetry.

    Requires ENABLE_TRACING=1 and opentelemetry packages.
    Falls back to no-op if OTEL not available.
    """

    def __init__(self, app: Any, **kwargs: Any) -> None:
        super().__init__(app, **kwargs)
        self._tracer = None
        try:
            from opentelemetry import trace

            self._tracer = trace.get_tracer(__name__)
        except ImportError:
            logger.debug("OpenTelemetry not available, tracing disabled")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._tracer is None:
            resp: Response = await call_next(request)
            return resp

        # Create span for request
        with self._tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": request.url.path,
            },
        ) as span:
            response: Response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
            return response


__all__ = ["TelemetryMiddleware", "TracingMiddleware"]
