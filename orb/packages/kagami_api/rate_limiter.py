"""Rate limiting middleware for K os API.

This module provides rate limiting functionality to protect against brute force
attacks and DoS. Defaults to in-memory for development and can be upgraded to
Redis-backed counters for production by setting RATE_LIMIT_USE_REDIS=true.

Consolidated to use `kagami.core.unified_rate_limiter`.
"""

import ipaddress
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import Request, Response
from kagami.core.boot_mode import is_full_mode, is_test_mode
from kagami.core.unified_rate_limiter import (
    RateLimitConfig,
    RateLimitStrategy,
    UnifiedRateLimiter,
)

from kagami_api.guardrails import update_guardrails

try:
    from kagami_observability.metrics import RATE_LIMIT_BLOCKS as _RATE_LIMIT_BLOCKS
except Exception:
    _RATE_LIMIT_BLOCKS = None

# Re-export with proper typing for mypy
RATE_LIMIT_BLOCKS = _RATE_LIMIT_BLOCKS

logger = logging.getLogger(__name__)


def _parse_trusted_proxies() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None:
    """Parse TRUSTED_PROXIES environment variable into IP networks.

    Returns:
        List of IP networks if TRUSTED_PROXIES is set, None otherwise.
        Empty list means trust no proxies (use direct client IP only).
    """
    trusted_proxies_env = os.getenv("TRUSTED_PROXIES", "").strip()

    if not trusted_proxies_env:
        return None  # Not configured

    if trusted_proxies_env.lower() in ("none", ""):
        return []  # Explicitly trust no proxies

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for proxy_str in trusted_proxies_env.split(","):
        proxy_str = proxy_str.strip()
        if not proxy_str:
            continue
        try:
            # Parse as network (supports CIDR notation like 10.0.0.0/8)
            network = ipaddress.ip_network(proxy_str, strict=False)
            networks.append(network)
        except ValueError as e:
            logger.warning(f"Invalid trusted proxy address '{proxy_str}': {e}")

    return networks


def _is_trusted_proxy(
    client_host: str, trusted_proxies: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None
) -> bool:
    """Check if client_host is in the trusted proxy list.

    Args:
        client_host: The IP address of the direct client
        trusted_proxies: List of trusted proxy networks, or None if not configured

    Returns:
        True if trusted, False otherwise
    """
    if trusted_proxies is None:
        # Not configured - backward compatibility mode (trust all, but warn)
        return True

    if not trusted_proxies:
        # Empty list - trust no proxies
        return False

    try:
        client_ip = ipaddress.ip_address(client_host)
        for network in trusted_proxies:
            if client_ip in network:
                return True
    except ValueError:
        # Invalid IP address
        logger.warning(f"Invalid client IP address: {client_host}")
        return False

    return False


# Parse trusted proxies once at module load
_TRUSTED_PROXIES = _parse_trusted_proxies()
_TRUSTED_PROXIES_WARNING_LOGGED = False


class RateLimiter:
    """Unified wrapper around UnifiedRateLimiter for API compatibility.

    Consolidates all rate limiting functionality into a single class.
    Provides both sync and async interfaces with proper event loop handling.
    """

    def __init__(self, requests_per_minute: int = 60, window_size: int = 60) -> None:
        self.requests_per_minute = int(requests_per_minute)
        self.window_size = int(window_size)

        # Prefer Redis in production when explicitly enabled
        use_redis = (os.getenv("RATE_LIMIT_USE_REDIS") or "0").lower() in (
            "1",
            "true",
            "yes",
            "on",
        ) and not is_test_mode()

        # Default config (in-memory sliding window)
        self.config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            window_size_seconds=window_size,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            burst_size=max(1, min(requests_per_minute, 50)),
            use_redis=use_redis,
        )
        self._impl = UnifiedRateLimiter(self.config)

        # Expose internal maps for compatibility with tests and header helpers
        self.clients = self._impl.clients
        self.burst_attempts = self._impl.burst_attempts
        self.burst_reset_time = self._impl.burst_reset_time

    def is_allowed(self, client_id: str) -> tuple[bool, int, int]:
        """Sync check - uses fallback when in event loop to avoid deadlock."""
        import asyncio
        import time
        from collections import deque

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: safe to run async method synchronously
            result = asyncio.run(self._impl.is_allowed(client_id))
            return cast(tuple[bool, int, int], result)  # type: ignore[redundant-cast]

        # Running loop: use local sliding-window fallback to avoid deadlock
        now = time.time()
        client_requests = self.clients.get(client_id)
        if client_requests is None:
            client_requests = deque()
            self.clients[client_id] = client_requests

        # Drop timestamps outside the window
        window_start = now - self.window_size
        while client_requests and client_requests[0] <= window_start:
            client_requests.popleft()

        # Enforce limit
        if len(client_requests) >= self.requests_per_minute:
            reset_time = max(0, int(self.window_size - (now - client_requests[0])))
            return False, 0, reset_time

        client_requests.append(now)
        remaining = self.requests_per_minute - len(client_requests)
        return True, remaining, int(self.window_size)

    async def is_allowed_async(self, client_id: str) -> tuple[bool, int, int]:
        """Async allowance check (preferred)."""
        result = await self._impl.is_allowed(client_id)
        return cast(tuple[bool, int, int], result)  # type: ignore[redundant-cast]

    def get_client_id(self, request: Request) -> str:
        """Extract client identifier from FastAPI Request with proxy validation.

        Security: Only trusts X-Forwarded-For/X-Real-IP headers when the request
        comes from a trusted proxy (configured via TRUSTED_PROXIES env var).

        Environment:
            TRUSTED_PROXIES: Comma-separated list of trusted proxy IPs/networks
                           (e.g., "10.0.0.0/8,172.16.0.0/12,192.168.1.1")
                           If not set, defaults to trusting all (with warning)
                           Set to "none" to trust no proxies

        Returns:
            Client identifier string combining IP and hashed user agent
        """
        global _TRUSTED_PROXIES_WARNING_LOGGED

        # Get direct client IP (the actual TCP connection source)
        direct_client_ip = getattr(request.client, "host", "unknown")

        # Check if request comes from a trusted proxy
        is_from_trusted_proxy = _is_trusted_proxy(direct_client_ip, _TRUSTED_PROXIES)

        # Determine the real client IP
        real_ip: str
        if is_from_trusted_proxy:
            # Trust proxy headers
            forwarded_ip = (
                request.headers.get("X-Real-IP")
                or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            )
            if forwarded_ip:
                real_ip = forwarded_ip
                # Log warning if TRUSTED_PROXIES not configured (backward compatibility mode)
                if _TRUSTED_PROXIES is None and not _TRUSTED_PROXIES_WARNING_LOGGED:
                    logger.warning(
                        "SECURITY: TRUSTED_PROXIES not configured. Trusting all X-Forwarded-For headers. "
                        "Set TRUSTED_PROXIES environment variable to specify trusted proxy IPs/networks."
                    )
                    _TRUSTED_PROXIES_WARNING_LOGGED = True
            else:
                # No forwarded headers, use direct IP
                real_ip = direct_client_ip
        else:
            # Not from trusted proxy - ignore forwarded headers
            real_ip = direct_client_ip
            # Log warning if untrusted proxy headers are present
            untrusted_headers = request.headers.get("X-Real-IP") or request.headers.get(
                "X-Forwarded-For"
            )
            if untrusted_headers:
                logger.warning(
                    f"Ignored X-Forwarded-For/X-Real-IP from untrusted source {direct_client_ip}. "
                    f"Add to TRUSTED_PROXIES if this is a legitimate proxy."
                )

        user_agent = request.headers.get("User-Agent", "unknown")
        return f"{real_ip}:{hash(user_agent) % 10000}"

    async def reset_async(self, client_id: str) -> None:
        """Reset limiter state for a client (async)."""
        await self._impl.reset(client_id)

    def reset(self, client_id: str) -> None:
        """Reset limiter state for a client (sync helper)."""
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._impl.reset(client_id))
            return
        # Running loop: best-effort local reset on exposed maps
        try:
            self.clients.pop(client_id, None)
            self.burst_attempts.pop(client_id, None)
            self.burst_reset_time.pop(client_id, None)
        except Exception:
            pass


# Per-user rate limit configuration (requests per minute)
USER_RATE_LIMIT_GUEST = 30  # Unauthenticated users (IP-based)
USER_RATE_LIMIT_USER = 120  # Authenticated standard users
USER_RATE_LIMIT_API_USER = 600  # API users with elevated access
USER_RATE_LIMIT_ADMIN = 1200  # Admin users

# Global instances
from kagami_api.api_settings import RATE_LIMIT_API_RPM as _API_RPM
from kagami_api.api_settings import RATE_LIMIT_AUTH_RPM as _AUTH_RPM
from kagami_api.api_settings import RATE_LIMIT_PUBLIC_RPM as _PUBLIC_RPM

auth_rate_limiter = RateLimiter(requests_per_minute=_AUTH_RPM, window_size=60)
api_rate_limiter = RateLimiter(requests_per_minute=_API_RPM, window_size=60)
public_rate_limiter = RateLimiter(requests_per_minute=_PUBLIC_RPM, window_size=60)

# Per-user tier limiters (for efficient per-user rate limiting)
guest_limiter = RateLimiter(requests_per_minute=USER_RATE_LIMIT_GUEST, window_size=60)
user_limiter = RateLimiter(requests_per_minute=USER_RATE_LIMIT_USER, window_size=60)
api_user_limiter = RateLimiter(requests_per_minute=USER_RATE_LIMIT_API_USER, window_size=60)
admin_limiter = RateLimiter(requests_per_minute=USER_RATE_LIMIT_ADMIN, window_size=60)

_redis_limiters_enabled = False


async def _get_user_from_request(request: Request) -> dict[str, Any] | None:
    """Extract authenticated user from request without raising exceptions.

    Args:
        request: FastAPI Request object

    Returns:
        User info dict with id and roles, or None if not authenticated
    """
    try:
        # Check for Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.replace("Bearer ", "").strip()
        if not token:
            return None

        # Import auth utilities
        from kagami_api.auth import get_user_from_token

        # Attempt to get user from token (async)
        try:
            user = await get_user_from_token(token)
            if user and user.is_active:
                return {
                    "id": user.id,
                    "roles": user.roles,
                    "is_admin": user.is_admin,
                }
        except Exception:
            # Invalid/expired token - treat as unauthenticated
            pass

    except Exception as e:
        logger.debug(f"Failed to extract user from request: {e}")

    return None


def _get_limiter_for_user(user_info: dict[str, Any] | None) -> tuple[RateLimiter, str]:
    """Get appropriate limiter and tier name based on user info.

    Args:
        user_info: User info dict with roles, or None for unauthenticated

    Returns:
        Tuple of (limiter instance, tier name)
    """
    if user_info is None:
        # Unauthenticated - use guest limiter
        return guest_limiter, "guest"

    roles = user_info.get("roles", [])
    is_admin = user_info.get("is_admin", False)

    # Check roles in order of privilege (highest first)
    if is_admin or "admin" in roles:
        return admin_limiter, "admin"
    elif "api_user" in roles:
        return api_user_limiter, "api_user"
    else:
        # Authenticated user without special roles
        return user_limiter, "user"


def _get_rate_limit_key(request: Request, user_info: dict[str, Any] | None) -> str:
    """Get rate limit key for request - uses user_id if authenticated, IP if not.

    Args:
        request: FastAPI Request object
        user_info: User info dict with id, or None for unauthenticated

    Returns:
        Rate limit key string (user:{user_id} or ip:{client_id})
    """
    if user_info and user_info.get("id"):
        # Authenticated - use user_id as key
        return f"user:{user_info['id']}"
    else:
        # Unauthenticated - fall back to IP-based limiting
        return f"ip:{api_rate_limiter.get_client_id(request)}"


async def rate_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Rate limiting middleware with per-user and per-IP rate limiting.

    Implements tiered rate limiting:
    - Authenticated users: rate limited by user_id with tier-based limits
    - Unauthenticated users: rate limited by IP address (guest tier)

    Rate limit tiers (requests per minute):
    - Guest (unauthenticated): 30 RPM
    - User (authenticated): 120 RPM
    - API User: 600 RPM
    - Admin: 1200 RPM
    """
    # Skip rate limiting in test mode to allow running many tests
    if is_test_mode():
        update_guardrails(request, rate_limit="bypassed_test_mode")
        return await call_next(request)

    # Extract user info from request (returns None if not authenticated)
    user_info = await _get_user_from_request(request)

    # Get appropriate limiter and tier based on user
    limiter, user_tier = _get_limiter_for_user(user_info)

    # Get rate limit key (user:{id} for authenticated, ip:{ip} for unauthenticated)
    rate_limit_key = _get_rate_limit_key(request, user_info)

    # Check rate limit
    is_allowed, remaining, reset_time = await limiter.is_allowed_async(rate_limit_key)

    if not is_allowed:
        if RATE_LIMIT_BLOCKS:
            try:
                RATE_LIMIT_BLOCKS.labels(reason="rate_limit").inc()
            except Exception as e:
                logger.debug(f"Failed to increment rate limit metric: {e}")
        update_guardrails(request, rate_limit="blocked")

        # IMPORTANT:
        # Do NOT raise HTTPException from BaseHTTPMiddleware-based middleware.
        # Under Starlette/AnyIO this can surface as an ExceptionGroup and get
        # misclassified by the general exception handler (-> 500).
        from fastapi.responses import JSONResponse

        try:
            from kagami_api.correlation import get_correlation_id as _get_cid

            correlation_id = _get_cid() or getattr(request.state, "correlation_id", None)
        except Exception:
            correlation_id = getattr(request.state, "correlation_id", None)

        detail = {
            "error": "rate_limit_exceeded",
            "message": "Too many requests",
            "retry_after": reset_time,
            "limit": limiter.requests_per_minute,
            "tier": user_tier,
        }

        content: dict[str, Any] = {
            "error": {
                "code": "K-4001",
                "message": "Rate limit exceeded",
                "category": "rate_limit",
                "retryable": True,
                "detail": detail,
                "guidance": [
                    "Wait before retrying",
                    "Check Retry-After header for wait time",
                ],
            }
        }
        if correlation_id:
            content["error"]["correlation_id"] = correlation_id
            # Include request context for debugging in non-production
            try:
                if os.getenv("ENVIRONMENT", "development").lower() != "production":
                    content["error"]["path"] = str(request.url.path)
                    content["error"]["method"] = request.method
            except Exception:
                pass

        response = JSONResponse(
            status_code=429,
            content=content,
            headers={"Retry-After": str(reset_time)},
        )
        # Match normal successful responses' headers (best-effort)
        response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response

    update_guardrails(request, rate_limit="enforced")
    response = await call_next(request)

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_time)

    return response


async def enable_redis_rate_limiting() -> None:
    """Switch global limiters to Redis-backed if configured."""
    global auth_rate_limiter, api_rate_limiter, public_rate_limiter
    global guest_limiter, user_limiter, api_user_limiter, admin_limiter
    global _redis_limiters_enabled

    if _redis_limiters_enabled:
        return
    if os.getenv("KAGAMI_EMBEDDED") or is_test_mode():
        return

    env_val = os.getenv("RATE_LIMIT_USE_REDIS")
    if env_val is not None:
        use_redis = env_val.lower() in ("1", "true", "yes", "on")
    else:
        use_redis = is_full_mode()

    if not use_redis:
        return

    try:
        # Re-configure globals to use Redis strategy
        # We update the underlying _impl

        auth_rate_limiter.config = RateLimitConfig(
            requests_per_minute=_AUTH_RPM, use_redis=True, namespace="kagami:rl:auth"
        )
        auth_rate_limiter._impl = UnifiedRateLimiter(auth_rate_limiter.config)

        api_rate_limiter.config = RateLimitConfig(
            requests_per_minute=_API_RPM, use_redis=True, namespace="kagami:rl:api"
        )
        api_rate_limiter._impl = UnifiedRateLimiter(api_rate_limiter.config)

        public_rate_limiter.config = RateLimitConfig(
            requests_per_minute=_PUBLIC_RPM, use_redis=True, namespace="kagami:rl:public"
        )
        public_rate_limiter._impl = UnifiedRateLimiter(public_rate_limiter.config)

        # Configure per-user tier limiters
        guest_limiter.config = RateLimitConfig(
            requests_per_minute=USER_RATE_LIMIT_GUEST, use_redis=True, namespace="kagami:rl:guest"
        )
        guest_limiter._impl = UnifiedRateLimiter(guest_limiter.config)

        user_limiter.config = RateLimitConfig(
            requests_per_minute=USER_RATE_LIMIT_USER, use_redis=True, namespace="kagami:rl:user"
        )
        user_limiter._impl = UnifiedRateLimiter(user_limiter.config)

        api_user_limiter.config = RateLimitConfig(
            requests_per_minute=USER_RATE_LIMIT_API_USER,
            use_redis=True,
            namespace="kagami:rl:api_user",
        )
        api_user_limiter._impl = UnifiedRateLimiter(api_user_limiter.config)

        admin_limiter.config = RateLimitConfig(
            requests_per_minute=USER_RATE_LIMIT_ADMIN, use_redis=True, namespace="kagami:rl:admin"
        )
        admin_limiter._impl = UnifiedRateLimiter(admin_limiter.config)

        _redis_limiters_enabled = True
        logger.info("Enabled Redis-backed rate limiting (Unified + per-user tiers)")

    except Exception as e:
        if is_full_mode():
            logger.error(f"FULL OPERATION MODE: Redis rate limiting required but unavailable: {e}")
            raise RuntimeError(f"Full Operation requires Redis. Error: {e}") from e
        logger.warning(f"Failed to enable Redis rate limiting: {e}")


def get_rate_limit_status() -> dict[str, Any]:
    """Get current rate limiting status for monitoring."""
    return {
        "auth_limiter": {
            "rpm": auth_rate_limiter.requests_per_minute,
            "redis": auth_rate_limiter.config.use_redis,
            "clients": len(auth_rate_limiter._impl.clients),
        },
        "api_limiter": {
            "rpm": api_rate_limiter.requests_per_minute,
            "redis": api_rate_limiter.config.use_redis,
            "clients": len(api_rate_limiter._impl.clients),
        },
        "public_limiter": {
            "rpm": public_rate_limiter.requests_per_minute,
            "redis": public_rate_limiter.config.use_redis,
            "clients": len(public_rate_limiter._impl.clients),
        },
        "per_user_limiters": {
            "guest": {
                "rpm": guest_limiter.requests_per_minute,
                "redis": guest_limiter.config.use_redis,
                "clients": len(guest_limiter._impl.clients),
            },
            "user": {
                "rpm": user_limiter.requests_per_minute,
                "redis": user_limiter.config.use_redis,
                "clients": len(user_limiter._impl.clients),
            },
            "api_user": {
                "rpm": api_user_limiter.requests_per_minute,
                "redis": api_user_limiter.config.use_redis,
                "clients": len(api_user_limiter._impl.clients),
            },
            "admin": {
                "rpm": admin_limiter.requests_per_minute,
                "redis": admin_limiter.config.use_redis,
                "clients": len(admin_limiter._impl.clients),
            },
        },
    }
