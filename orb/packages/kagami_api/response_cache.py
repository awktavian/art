"""Response caching middleware with ETag and Cache-Control support.

Provides HTTP-standard caching:
- ETag generation for response content
- Cache-Control headers
- Conditional GET (If-None-Match) support
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths that should never be cached
NEVER_CACHE_PATHS = frozenset(
    {
        "/health",
        "/health/live",
        "/health/ready",
        "/metrics",
        "/api/vitals/probes/liveness",
        "/api/vitals/probes/readiness",
    }
)

# Paths that benefit from caching (GET only)
CACHEABLE_PREFIXES = (
    "/api/static/",
    "/api/assets/",
    "/openapi.json",
)


async def response_cache_middleware(request: Request, call_next: Callable) -> Response:
    """HTTP caching middleware with ETag and Cache-Control.

    For GET requests to cacheable paths:
    - Generates ETag from response content
    - Returns 304 Not Modified if client has current version
    - Adds Cache-Control headers for browser/CDN caching

    Non-GET requests and dynamic paths pass through unchanged.
    """
    # Only cache GET requests
    if request.method != "GET":
        response: Response = await call_next(request)
        return response

    path = request.url.path

    # Never cache health/metrics endpoints
    if path in NEVER_CACHE_PATHS:
        resp: Response = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Execute request
    resp2: Response = await call_next(request)

    # Skip caching for non-2xx responses
    if not (200 <= resp2.status_code < 300):
        return resp2

    # Skip if response already has Cache-Control
    if "Cache-Control" in resp2.headers:
        return resp2

    # Check if path is cacheable
    is_static = any(path.startswith(prefix) for prefix in CACHEABLE_PREFIXES)

    if is_static:
        # Long cache for static assets
        resp2.headers["Cache-Control"] = "public, max-age=86400"
    else:
        # Short/no cache for API responses
        resp2.headers["Cache-Control"] = "private, no-cache"

    # Generate ETag if response has content
    # Note: For streaming responses, skip ETag
    try:
        if hasattr(resp2, "body"):
            body = resp2.body
            if body:
                etag = hashlib.md5(body, usedforsecurity=False).hexdigest()[:16]
                resp2.headers["ETag"] = f'W/"{etag}"'

                # Check If-None-Match for conditional GET
                if_none_match = request.headers.get("If-None-Match")
                if if_none_match and if_none_match == f'W/"{etag}"':
                    return Response(status_code=304)
    except Exception:
        pass  # Skip ETag for streaming/chunked responses

    return resp2


__all__ = ["response_cache_middleware"]
