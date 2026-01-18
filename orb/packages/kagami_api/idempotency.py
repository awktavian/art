"""Idempotency middleware for K OS API.

Refactored to use canonical IdempotencyStore from kagami.core.idempotency.store.
"Idempotency is Identity" - ALL mutations require Idempotency-Key header.

Key behaviors:
- GET/HEAD/OPTIONS: No idempotency required
- POST/PUT/PATCH/DELETE: Require Idempotency-Key header
- Duplicate requests: Replay original response (not 409)
- Response caching: Only for small JSON responses (<512KB)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from kagami.core.receipts.store import get_idempotency_store
from starlette.concurrency import iterate_in_threadpool
from starlette.responses import Response, StreamingResponse

from kagami_api.guardrails import update_guardrails

logger = logging.getLogger(__name__)

# Endpoints exempt from idempotency (read-only POST)
EXEMPT_PATTERNS = [
    "/api/command/parse",
    "/api/command/nl",
    "/api/command/suggest",
    "/api/auth/token",
    "/api/auth/refresh",
    "/api/auth/register",
    "/api/user/token",  # Login endpoint (canonical)
    "/api/user/refresh",  # Token refresh (canonical)
    "/api/user/register",  # Registration (canonical)
    "/api/tools/recommend",
    "/health",
    "/api/status",
    # Home automation webhooks (Control4/Lutron)
    "/api/v1/home/webhook/",
]


async def idempotency_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Idempotency middleware for FastAPI.

    Uses IdempotencyStore for unified state management.
    """
    method = request.method.upper()

    # Allow read-only methods without Idempotency-Key
    if method in ("GET", "HEAD", "OPTIONS"):
        update_guardrails(request, idempotency="not_required")
        return await call_next(request)

    path = str(request.url.path)

    # Exempt read-only POST endpoints
    if any(path.startswith(pattern) or path == pattern for pattern in EXEMPT_PATTERNS):
        update_guardrails(request, idempotency="exempt_read_only")
        return await call_next(request)

    # Get idempotency key
    idem_key = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")

    # Require idempotency key for mutations
    if not idem_key and method in ("POST", "PUT", "PATCH", "DELETE"):
        update_guardrails(request, idempotency="rejected_missing_key")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_idempotency_key",
                "message": "Idempotency-Key header required for mutating operations",
            },
        )

    if not idem_key:
        return await call_next(request)

    # Get store singleton
    store = get_idempotency_store()
    store.ensure_cleanup_running()

    # Check for duplicate and acquire lock
    is_new, cached_entry = await store.check_and_acquire(path, idem_key)

    if not is_new:
        # Duplicate request - check for cached response
        if (
            cached_entry
            and cached_entry.status_code is not None
            and cached_entry.response_body is not None
        ):
            update_guardrails(request, idempotency="duplicate_replayed")
            from fastapi.responses import JSONResponse

            return JSONResponse(
                content=cached_entry.response_body,
                status_code=cached_entry.status_code,
                headers={"X-Idempotency-Replayed": "true"},
            )

        # No cached response - return 409
        update_guardrails(request, idempotency="duplicate_blocked")
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_request",
                "message": "Request with this Idempotency-Key already processed",
            },
        )

    # Mark as enforced
    try:
        request.state._idempotency_enforced = True
        request.state._idempotency_key = f"{path}:{idem_key}"
    except Exception as e:
        logger.debug(f"Failed to set idempotency state on request: {e}")

    update_guardrails(request, idempotency="enforced")

    # Process request
    response = await call_next(request)

    # Cache response if appropriate
    if hasattr(response, "status_code"):
        content_type = response.headers.get("content-type", "")

        # Skip streaming responses
        is_streaming = (
            "text/event-stream" in content_type
            or "application/octet-stream" in content_type
            or "multipart/" in content_type
            or response.headers.get("transfer-encoding") == "chunked"
        )

        should_cache = (
            not is_streaming and "application/json" in content_type and response.status_code < 500
        )

        if should_cache and isinstance(response, StreamingResponse):
            # Buffer response for caching
            body_bytes = b""
            try:
                async for chunk in response.body_iterator:
                    if isinstance(chunk, bytes):
                        body_bytes += chunk
                    elif isinstance(chunk, str):
                        body_bytes += chunk.encode("utf-8")
                    else:
                        body_bytes += bytes(chunk)

                    # Size limit
                    if len(body_bytes) > 512 * 1024:
                        should_cache = False
                        break
            except Exception as e:
                logger.debug(f"Failed to buffer response: {e}")
                should_cache = False
            finally:
                # Restore iterator
                response.body_iterator = iterate_in_threadpool(iter([body_bytes]))

            if should_cache and body_bytes:
                try:
                    import json

                    raw_bytes = body_bytes
                    if response.headers.get("content-encoding", "").lower() == "gzip":
                        import gzip

                        raw_bytes = gzip.decompress(body_bytes)

                    response_body = json.loads(raw_bytes.decode("utf-8"))

                    # Store in unified store
                    await store.store_response(
                        path=path,
                        idempotency_key=idem_key,
                        status_code=response.status_code,
                        response_body=response_body,
                    )
                except Exception as e:
                    logger.debug(f"Failed to cache response: {e}")

    return response


async def ensure_idempotency(request: Request, ttl_seconds: int = 300) -> None:
    """Ensure Idempotency-Key is present.

    Used by routes that need manual enforcement.
    """
    key = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
    if not key:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_idempotency_key",
                "message": "Idempotency-Key header required",
            },
        )


__all__ = ["EXEMPT_PATTERNS", "ensure_idempotency", "idempotency_middleware"]
