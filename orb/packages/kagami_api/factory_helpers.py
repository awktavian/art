"""Helper functions for FastAPI application factory.

Extracted from massive create_app function to reduce complexity.
Each helper is focused on a single responsibility.
"""

import logging
import os
from typing import Any

from fastapi import FastAPI
from kagami.core.boot_mode import is_test_mode

logger = logging.getLogger(__name__)


def setup_test_mode_stubs() -> None:
    """Set up test mode stubs for isolated testing.

    This is a no-op in production but configures environment for test mode.
    """
    if is_test_mode():
        logger.debug("Test mode stubs configured")


def setup_transformers_hardening() -> None:
    """Harden Transformers imports - disable TensorFlow, allow normal GGUF handling.

    Transformers 4.43.4 doesn't need integration stubs - let it handle imports normally.
    """
    # Disable TF in Transformers
    os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

    logger.debug("Transformers hardening applied (TF disabled)")


def configure_cors(app: FastAPI, allowed_origins: list[str] | None = None) -> None:
    """Configure CORS middleware with strict security defaults.

    SECURITY CRITICAL:
    - Production REQUIRES explicit ALLOWED_ORIGINS (no wildcards)
    - Development defaults to localhost only (NOT wildcard)
    - Wildcard "*" is ONLY allowed in test mode
    - All origins must use https:// in production

    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origins. None = read from ALLOWED_ORIGINS env var.

    Raises:
        ValueError: If ALLOWED_ORIGINS is missing/invalid in production
    """
    from fastapi.middleware.cors import CORSMiddleware

    _env = (os.getenv("ENVIRONMENT") or "development").lower()
    _is_test_mode = _env == "test" or is_test_mode()

    # Determine allowed origins
    if allowed_origins is None:
        # Read from environment variable
        origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
        if origins_env:
            # Parse comma-separated list
            allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
        else:
            # No env var set - apply defaults based on environment
            if _env == "production" and not _is_test_mode:
                raise ValueError(
                    "ALLOWED_ORIGINS environment variable must be set in production. "
                    "Example: ALLOWED_ORIGINS=https://app.example.com,https://www.example.com"
                )
            elif _is_test_mode:
                # Test mode: Allow wildcard for test flexibility
                allowed_origins = ["*"]
            else:
                # Development: Default to localhost only (secure default)
                allowed_origins = [
                    "http://localhost:3000",
                    "http://localhost:8000",
                    "http://localhost:8001",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:8000",
                    "http://127.0.0.1:8001",
                ]

    # Validate origins in production
    if _env == "production" and not _is_test_mode:
        if not allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must be non-empty in production")

        # Check for wildcard (insecure)
        has_wildcard = any(o.strip() == "*" for o in allowed_origins)
        if has_wildcard:
            raise ValueError(
                "Wildcard '*' is not allowed in production CORS. "
                "Use explicit origin list: ALLOWED_ORIGINS=https://app.example.com"
            )

        # Check for insecure http:// in production
        has_http = any(str(o or "").startswith("http://") for o in allowed_origins)
        if has_http:
            raise ValueError(
                "HTTP origins are not allowed in production. "
                "All CORS origins must use https:// protocol."
            )

    # Credentials: disable with wildcard, enable otherwise
    if any(o == "*" for o in allowed_origins or []):
        _allow_credentials = False
    else:
        _allow_credentials = True

    # Apply CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        # Explicit header whitelist instead of wildcard for security
        # - Standard headers: Accept, Content-Type, Authorization
        # - Custom headers: X-Request-ID for tracing, X-CSRF-Token for CSRF protection
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Authorization",
            "Cache-Control",
            "Content-Language",
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
            "X-Requested-With",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # Mark CORS readiness
    try:
        app.state.cors_ready = True
        app.state.config_ready = True
    except Exception:
        pass

    # Log configuration (truncate for security)
    origins_display = allowed_origins[:3] if len(allowed_origins) > 3 else allowed_origins
    if len(allowed_origins) > 3:
        origins_display.append(f"...and {len(allowed_origins) - 3} more")
    logger.info(f"CORS configured: origins={origins_display}, credentials={_allow_credentials}")


def setup_security_middleware(app: FastAPI) -> None:
    """Add security middleware (CSRF protection, security headers).

    Complexity reduced from create_app by extracting this section.
    """
    from typing import cast

    from .security_middleware import SecurityMiddleware

    # Starlette's add_middleware is dynamically typed
    app.add_middleware(cast(Any, SecurityMiddleware))
    logger.info("Security middleware configured")
    try:
        app.state.security_ready = True
    except Exception:
        pass


def setup_compression_middleware(app: FastAPI) -> None:
    """Add Brotli (if available) and GZip compression middleware."""
    # Prefer Brotli when available for better compression ratios on text assets
    try:
        from brotli_asgi import BrotliMiddleware

        app.add_middleware(BrotliMiddleware, quality=4)
        logger.info("Brotli compression enabled")
    except Exception:
        pass

    try:
        from fastapi.middleware.gzip import GZipMiddleware

        app.add_middleware(GZipMiddleware, minimum_size=1000)
        logger.info("GZip compression enabled")
    except Exception:
        pass

    # Mark compression as ready
    try:
        app.state.compression_ready = True
    except Exception:
        pass


def setup_request_size_limit(app: FastAPI, max_bytes: int | None = None) -> None:
    """Add request size limiting middleware to mitigate abuse.

    Args:
        app: FastAPI application
        max_bytes: Maximum allowed request size in bytes (defaults to env REQUEST_MAX_BYTES or 1MB)
    """
    import os

    from fastapi import status as _status
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    if max_bytes is None:
        try:
            max_bytes = int(os.getenv("REQUEST_MAX_BYTES", "1048576"))
        except Exception:
            max_bytes = 1048576

    class _SizeLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Any:
            try:
                cl = request.headers.get("content-length")
                if cl and cl.isdigit() and int(cl) > int(max_bytes):  # type: ignore[arg-type]
                    return Response(status_code=_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
            except Exception:
                pass
            return await call_next(request)

    app.add_middleware(_SizeLimitMiddleware)
    logger.info(f"Request size limit enabled: {max_bytes} bytes")


__all__ = [
    "configure_cors",
    "setup_compression_middleware",
    "setup_security_middleware",
    "setup_test_mode_stubs",
    "setup_transformers_hardening",
]
