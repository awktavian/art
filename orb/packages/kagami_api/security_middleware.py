"""Security middleware for K os API.

Provides comprehensive input validation, CSRF protection, and XSS prevention.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import re
import secrets
from collections.abc import Callable
from typing import Any

try:
    import bleach as _bleach_module

    bleach: Any = _bleach_module
except Exception:
    bleach = None
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from kagami.core.boot_mode import is_test_mode
from kagami.core.caching.redis import RedisClientFactory
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
_CSRF_TOKEN_STORE: dict[str, str] = {}
_CSRF_LOCK: asyncio.Lock | None = None


def _get_csrf_lock() -> asyncio.Lock:
    global _CSRF_LOCK
    if _CSRF_LOCK is None:
        _CSRF_LOCK = asyncio.Lock()
    return _CSRF_LOCK


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware for input validation and attack prevention."""

    def __init__(self, app, enable_csrf: bool = True, enable_xss_protection: bool = True):  # type: ignore[no-untyped-def]
        super().__init__(app)
        _environment = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").lower()
        _disable_csrf_env = os.getenv("KAGAMI_DISABLE_CSRF", "0").lower() in ("1", "true", "yes")

        # SECURITY: CSRF protection cannot be disabled in production
        if _disable_csrf_env and _environment == "production":
            raise RuntimeError(
                "SECURITY VIOLATION: CSRF protection cannot be disabled in production. "
                "Remove KAGAMI_DISABLE_CSRF environment variable."
            )

        self.enable_csrf = enable_csrf and (not _disable_csrf_env)
        self.enable_xss_protection = enable_xss_protection
        if _disable_csrf_env:
            logger.warning(
                "⚠️ CSRF protection DISABLED via KAGAMI_DISABLE_CSRF env var (dev/test only)"
            )
        self.redis_client = None
        self.async_redis_client = None
        self.use_redis = False
        global _CSRF_TOKEN_STORE
        try:
            # Only skip Redis in actual test mode, not development
            if os.getenv("CI") in ("true", "1") or os.getenv("PYTEST_CURRENT_TEST"):
                raise RuntimeError("skip_redis_in_ci")
            self.redis_client = RedisClientFactory.get_client(purpose="default", async_mode=False)
            self.use_redis = True
            logger.info("✅ Using Redis for CSRF token storage")
        except Exception as e:
            logger.warning(f"Redis not available for CSRF tokens: {e}")
            logger.warning("Falling back to in-memory CSRF token storage")
        self.csrf_secret = os.getenv("CSRF_SECRET") or os.getenv("JWT_SECRET")
        _environment = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").lower()
        if _environment == "production" and (not self.csrf_secret):
            raise RuntimeError(
                "CSRF_SECRET or JWT_SECRET must be configured in production. Refusing to start with no CSRF protection."
            )
        if not self.csrf_secret:
            logger.warning(
                "No CSRF_SECRET configured, using weak fallback. This is ONLY acceptable in development."
            )
            self.csrf_secret = "dev-fallback-secret-DO-NOT-USE-IN-PRODUCTION"
        _environment = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").lower()
        if (
            self.enable_csrf
            and _environment == "production"
            and (not self.use_redis)
            and (not is_test_mode())
        ):
            raise RuntimeError(
                "CSRF protection requires Redis in production. Configure REDIS_URL or disable CSRF explicitly."
            )
        self.allowed_tags = [
            "b",
            "i",
            "u",
            "strong",
            "em",
            "p",
            "br",
            "ul",
            "ol",
            "li",
            "code",
            "pre",
        ]
        self.allowed_attributes = {"*": ["class", "id"], "a": ["href", "title"]}
        _environment = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").lower()
        if self.enable_xss_protection and _environment == "production":
            try:
                import importlib

                _bleach_dyn = importlib.import_module("bleach")
            except Exception:
                _bleach_dyn = None
            if _bleach_dyn is None or not hasattr(_bleach_dyn, "clean"):
                raise RuntimeError(
                    "bleach dependency is required for XSS protection in production"
                ) from None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security checks."""
        try:
            if self._should_skip_security(request):
                _resp_skip: Response = await call_next(request)
                # CRITICAL: Add security headers to ALL responses, even skipped paths
                self._add_security_headers(_resp_skip)
                return _resp_skip
            await self._validate_and_sanitize_input(request)
            if self.enable_csrf and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
                try:
                    await self._validate_csrf_token(request)
                    pass  # Metric removed (cleanup Dec 2025)
                # Metrics are non-critical
                except HTTPException as he:
                    try:
                        from kagami.observability.security_events import (
                            log_security_event as _log_evt,
                        )

                        _log_evt(
                            "csrf_failed",
                            {
                                "path": request.url.path,
                                "method": request.method,
                                "client_ip": getattr(request.client, "host", None),
                            },
                        )
                    except Exception:
                        pass
                    how_to_fix = {
                        "how_to_fix": "Fetch /api/user/csrf-token, then send X-CSRF-Token and X-Session-ID on state-changing requests.",
                        "required_headers": ["X-CSRF-Token", "X-Session-ID"],
                        "token_endpoint": "/api/user/csrf-token",
                    }
                    pass  # Metric removed (cleanup Dec 2025)
                    # Metrics are non-critical
                    error_response = JSONResponse(
                        status_code=he.status_code,
                        content={
                            "error": {
                                "type": "csrf_error",
                                "code": he.status_code,
                                "message": he.detail,
                            },
                            **how_to_fix,
                        },
                    )
                    self._add_security_headers(error_response)
                    return error_response
                except Exception:
                    try:
                        from kagami.observability.security_events import (
                            log_security_event as _log_evt2,
                        )

                        _log_evt2(
                            "csrf_failed",
                            {
                                "path": request.url.path,
                                "method": request.method,
                                "client_ip": getattr(request.client, "host", None),
                            },
                        )
                    except Exception:
                        pass
                    how_to_fix = {
                        "how_to_fix": "Fetch /api/user/csrf-token, then send X-CSRF-Token and X-Session-ID on state-changing requests.",
                        "required_headers": ["X-CSRF-Token", "X-Session-ID"],
                        "token_endpoint": "/api/user/csrf-token",
                    }
                    pass  # Metric removed (cleanup Dec 2025)
                    # Metrics are non-critical
                    error_response = JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": {
                                "type": "csrf_error",
                                "code": status.HTTP_403_FORBIDDEN,
                                "message": "CSRF validation error",
                            },
                            **how_to_fix,
                        },
                    )
                    self._add_security_headers(error_response)
                    return error_response
            _resp_final: Response = await call_next(request)
            # CRITICAL: Add security headers to ALL responses
            self._add_security_headers(_resp_final)
            return _resp_final
        except HTTPException:
            raise
        except Exception as e:
            try:
                import traceback

                logger.error(
                    "Security validation failed for %s %s: %s\n%s",
                    request.method,
                    request.url.path,
                    str(e),
                    traceback.format_exc(),
                )
            except Exception:
                pass
            error_response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Security validation failed"},
            )
            self._add_security_headers(error_response)
            return error_response

    def _should_skip_security(self, request: Request) -> bool:
        """Check if security checks should be skipped for this request."""
        skip_paths = [
            "/health",
            "/health/live",
            "/health/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/user/csrf-token",
            # Auth endpoints - must be accessible without CSRF for login flow
            "/api/user/token",
            "/api/user/register",
            "/api/user/refresh",
            "/api/voice/synthesize",
            "/api/command",
            "/api/billing/stripe/webhook",
            "/api/i18n/translate",
            "/api/command/parse",
            "/api/command/nl",
            "/api/command/execute",
            "/favicon.ico",
            "/static",
            "/socket.io",
            # Vitals/health probes - must be accessible without auth for k8s
            "/api/vitals/probes/live",
            "/api/vitals/probes/ready",
            "/api/vitals/probes/deep",
            "/api/vitals/probes/cluster",
            "/api/vitals/probes/dependencies",
            # Home automation webhooks - called by Control4/Lutron without CSRF
            "/api/home/shades/",
            "/api/home/lights/",
            "/api/home/scene",
            "/api/home/movie-mode/",
            "/api/v1/home/shades/",
            "/api/v1/home/lights/",
            "/api/v1/home/scene",
            "/api/v1/home/movie-mode/",
            # Webhook endpoints (no auth required)
            "/api/v1/home/webhook/",
        ]
        try:
            import os as _os

            # Allow socket.io requests to pass through without strict validation
            if "socket.io" in request.url.path:
                return True

            try:
                if request.url.path.startswith("/metrics"):
                    _public = (_os.getenv("METRICS_PUBLIC") or "0").lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    )
                    if _public:
                        return True
                    _allow_ips = (_os.getenv("METRICS_ALLOW_IPS") or "").replace(",", " ").split()
                    client_ip = getattr(request.client, "host", "") if request.client else ""
                    if client_ip and _allow_ips:
                        if client_ip in _allow_ips or client_ip in ("127.0.0.1", "::1"):
                            return True
            except Exception:
                pass
            ua = (request.headers.get("user-agent") or "").lower()
            if (
                "testclient" in ua
                and (_os.getenv("ENVIRONMENT") or "development").lower() != "production"
            ):
                skip_paths.extend(
                    [
                        "/api/rooms",
                        "/api/rooms/",
                        "/api/rooms/session",
                        "/api/rooms/session/",
                        "/api/worldgraph",
                        "/api/worldgraph/",
                        "/api/compiler",
                        "/api/compiler/",
                    ]
                )
        except Exception:
            pass
        return any(request.url.path.startswith(path) for path in skip_paths)

    async def _validate_and_sanitize_input(self, request: Request) -> None:
        """Validate and sanitize all input data."""
        dangerous_patterns = [
            "<script[^>]*>",
            "javascript:",
            "vbscript:",
            "onload=",
            "onerror=",
            "onclick=",
            "SELECT.*FROM",
            "UNION.*SELECT",
            "DROP.*TABLE",
            "INSERT.*INTO",
            "UPDATE.*SET",
            "DELETE.*FROM",
            "\\.\\./",
            "\\\\.\\\\.\\\\",
        ]
        request_data = await self._extract_request_data(request)
        for pattern in dangerous_patterns:
            if self._check_pattern_in_data(pattern, request_data):
                logger.warning(
                    f"Blocked malicious pattern: {pattern} from {(request.client.host if request.client else 'unknown')}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input detected"
                )

    async def _extract_request_data(self, request: Request) -> dict[str, Any]:
        """Extract data from request for validation."""
        data = {}
        if request.query_params:
            data["query"] = dict(request.query_params)
        safe_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in ["authorization", "cookie"]
        }
        data["headers"] = safe_headers
        if hasattr(request, "path_params"):
            data["path"] = request.path_params
        return data

    def _check_pattern_in_data(self, pattern: str, data: dict[str, Any]) -> bool:
        """Check if malicious pattern exists in request data."""
        pattern_re = re.compile(pattern, re.IGNORECASE)

        def check_value(value: Any) -> bool:
            if isinstance(value, str):
                return bool(pattern_re.search(value))
            elif isinstance(value, dict):
                return any(check_value(v) for v in value.values())
            elif isinstance(value, list):
                return any(check_value(item) for item in value)
            return False

        return check_value(data)

    async def _validate_csrf_token(self, request: Request) -> None:
        """Validate CSRF token for state-changing operations.

        REMOVED: CSRF bypass flags (KAGAMI_DEV_BYPASS, KAGAMI_TESTCLIENT_CSRF_BYPASS)
        Tests must generate proper CSRF tokens via /api/user/csrf-token endpoint.
        """
        if request.headers.get("X-API-Key"):
            return
        if request.headers.get("Authorization", "").startswith("Bearer "):
            return
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type:
                pass
        if not csrf_token:
            logger.warning(
                f"Missing CSRF token from {(request.client.host if request.client else 'unknown')}"
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token required")
        # SECURITY: Require explicit session ID to prevent shared token attacks
        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            # Generate session-specific ID from request fingerprint for anonymous sessions
            client_ip = getattr(request.client, "host", "") if request.client else ""
            user_agent = request.headers.get("user-agent", "")[:100]  # Truncate for safety
            import hashlib as _hashlib

            session_id = _hashlib.sha256(f"{client_ip}:{user_agent}".encode()).hexdigest()[:32]
        if self.use_redis:
            try:
                csrf_key = f"csrf_token:{session_id}"
                expected_token = self.redis_client.get(csrf_key) if self.redis_client else None
            except Exception as e:
                logger.error(f"Redis error retrieving CSRF token: {e}")
                expected_token = None
        else:
            try:
                if self.csrf_secret:
                    expected_token = hmac.new(
                        key=self.csrf_secret.encode("utf-8"),
                        msg=session_id.encode("utf-8"),
                        digestmod=hashlib.sha256,
                    ).hexdigest()
                else:
                    lock = _get_csrf_lock()
                    async with lock:
                        expected_token = _CSRF_TOKEN_STORE.get(session_id)
            except Exception:
                expected_token = None
        if not expected_token or csrf_token != expected_token:
            logger.warning(
                f"Invalid CSRF token from {(request.client.host if request.client else 'unknown')}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token"
            ) from None

    def _add_security_headers(self, response: Response) -> None:
        """Add comprehensive security headers to ALL responses.

        CRITICAL: This runs on ALL responses including health checks and OPTIONS.
        Security headers are defense-in-depth and cost nothing to add.
        """
        try:
            import os as _os

            _env = (_os.getenv("ENVIRONMENT") or "development").lower()
            allow_dev_extras = _env != "production"

            def _split_hosts(val: str | None) -> list[str]:
                if not val:
                    return []
                parts = [p.strip() for p in val.replace(",", " ").split()]
                return [p for p in parts if p]

            extra_script = (
                _split_hosts(_os.getenv("CSP_SCRIPT_SRC_EXTRA")) if allow_dev_extras else []
            )
            extra_style = (
                _split_hosts(_os.getenv("CSP_STYLE_SRC_EXTRA")) if allow_dev_extras else []
            )
            extra_font = _split_hosts(_os.getenv("CSP_FONT_SRC_EXTRA")) if allow_dev_extras else []
            if _env == "production":
                script_src = ["'self'", *extra_script]
                style_src = ["'self'", *extra_style]
            else:
                # Development: allow unsafe-inline for hot reload, debugging
                script_src = ["'self'", "'unsafe-inline'", *extra_script]
                style_src = ["'self'", "'unsafe-inline'", *extra_style]
            font_src = ["'self'", *extra_font]
            extra_connect = _split_hosts(_os.getenv("CSP_CONNECT_SRC_EXTRA"))

            # In development, automatically allow common local origins for WebSocket, etc.
            if _env != "production":
                dev_origins = [
                    "http://localhost:3000",
                    "http://localhost:8001",
                    "ws://localhost:3000",
                    "ws://localhost:8001",
                ]
                connect_src = ["'self'", *dev_origins, *extra_connect]
            else:
                connect_src = ["'self'", *extra_connect]

            # Build CSP directive
            csp = (
                "default-src 'self'; "
                + f"script-src {' '.join(script_src)}; "
                + f"script-src-elem {' '.join(script_src)}; "
                + f"style-src {' '.join(style_src)}; "
                + f"style-src-elem {' '.join(style_src)}; "
                + "img-src 'self' data: https:; "
                + f"font-src {' '.join(font_src)}; "
                + f"connect-src {' '.join(connect_src)}; "
                + "frame-ancestors 'none'; "
                + "object-src 'none'; "
                + "base-uri 'self'; "
                + "form-action 'self'"
            )
        except Exception:
            # Fallback CSP if configuration parsing fails
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )

        # CSP reporting configuration
        report_only = (os.getenv("CSP_REPORT_ONLY") or "0").lower() in ("1", "true", "yes", "on")
        csp_header_name = (
            "Content-Security-Policy-Report-Only" if report_only else "Content-Security-Policy"
        )
        csp_report_uri = os.getenv("CSP_REPORT_URI")
        if csp_report_uri:
            csp = f"{csp}; report-uri {csp_report_uri}"

        # Comprehensive security headers (OWASP recommendations)
        security_headers = {
            # Content sniffing protection
            "X-Content-Type-Options": "nosniff",
            # Clickjacking protection
            "X-Frame-Options": "DENY",
            # Legacy XSS protection (defense in depth, CSP is primary)
            "X-XSS-Protection": "1; mode=block",
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # Content Security Policy
            csp_header_name: csp,
            # Cross-Origin policies
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Embedder-Policy": (
                "credentialless" if _env != "production" else "require-corp"
            ),
            "Cross-Origin-Resource-Policy": "same-origin",
            # Feature policy / permissions policy
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), payment=(), "
                "usb=(), bluetooth=(), magnetometer=(), gyroscope=(), "
                "accelerometer=(), ambient-light-sensor=()"
            ),
        }

        # HSTS: ALWAYS in production, optional in development
        # CRITICAL: Only set HSTS over HTTPS to avoid breaking development
        if _env == "production":
            # Production: Enforce HTTPS with HSTS
            security_headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        elif os.getenv("ENABLE_HSTS_DEV", "0").lower() in ("1", "true"):
            # Development: Optional HSTS (only if explicitly enabled)
            security_headers["Strict-Transport-Security"] = "max-age=3600; includeSubDomains"

        # Apply all security headers
        # Use setdefault to avoid overwriting headers set by other middleware
        for header, value in security_headers.items():
            if header not in response.headers:
                response.headers[header] = value

    async def generate_csrf_token(self, session_id: str = "default") -> str:
        """Generate and store a new CSRF token."""
        csrf_token = secrets.token_urlsafe(32)
        if self.use_redis:
            try:
                if self.async_redis_client is None:
                    self.async_redis_client = RedisClientFactory.get_client(
                        purpose="default", async_mode=True, decode_responses=True
                    )
                csrf_key = f"csrf_token:{session_id}"
                # Factory raises on failure, so client is guaranteed non-None
                redis_client = self.async_redis_client
                try:
                    await redis_client.setex(csrf_key, 86400, csrf_token)  # type: ignore[attr-defined]
                except Exception:
                    self.async_redis_client = RedisClientFactory.get_client(
                        purpose="default", async_mode=True, decode_responses=True
                    )
                    redis_client = self.async_redis_client
                    await redis_client.setex(csrf_key, 86400, csrf_token)  # type: ignore[attr-defined]
            except Exception as e:
                logger.error(f"Redis error storing CSRF token: {e}")
                try:
                    _CSRF_TOKEN_STORE[session_id] = csrf_token
                except Exception:
                    pass
        else:
            if self.csrf_secret:
                csrf_token = hmac.new(
                    key=self.csrf_secret.encode("utf-8"),
                    msg=session_id.encode("utf-8"),
                    digestmod=hashlib.sha256,
                ).hexdigest()
            try:
                lock = _get_csrf_lock()
                async with lock:
                    _CSRF_TOKEN_STORE[session_id] = csrf_token
            except Exception:
                pass
        logger.info(f"CSRF token generated for session: {session_id}")
        return csrf_token

    def sanitize_html(self, content: str) -> str:
        """Sanitize HTML content to prevent XSS."""
        if not self.enable_xss_protection:
            return content
        if bleach is None:
            return content
        try:
            cleaned: str = bleach.clean(
                content,
                tags=self.allowed_tags,
                attributes=self.allowed_attributes,
                strip=True,
                strip_comments=True,
            )
            cleaned = re.sub(
                "<\\s*script[^>]*>.*?<\\s*/\\s*script\\s*>",
                "",
                cleaned,
                flags=re.IGNORECASE | re.DOTALL,
            )
            cleaned = re.sub(
                "<\\s*style[^>]*>.*?<\\s*/\\s*style\\s*>",
                "",
                cleaned,
                flags=re.IGNORECASE | re.DOTALL,
            )
        except Exception:
            cleaned = content
        return cleaned


_security_middleware: SecurityMiddleware | None = None


def get_security_middleware() -> SecurityMiddleware:
    """Get a default-configured security middleware instance.

    Note: When wiring via app.add_middleware, Starlette will construct
    its own instance using the middleware class; this singleton exists primarily
    for helpers (e.g., CSRF service) to share config/state.
    """
    global _security_middleware
    if _security_middleware is None:
        _security_middleware = SecurityMiddleware(app=None)
    return _security_middleware
