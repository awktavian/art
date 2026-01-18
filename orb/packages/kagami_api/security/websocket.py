"""WebSocket Authentication for K os.

Moved from kagami/api/websocket/auth_common.py (Batch 2, Nov 1, 2025).

Provides first-frame authentication for WebSocket connections with 5-second timeout.

Usage:
    from kagami_api.security.websocket import authenticate_ws, wait_for_auth_with_timeout

    # In WebSocket handler
    auth_payload = await wait_for_auth_with_timeout(auth_future)
    if not auth_payload:
        await websocket.close(code=4401, reason="Authentication timeout")
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# WebSocket authentication timeout (5 seconds)
WS_AUTH_TIMEOUT_SECONDS = 5.0

# WebSocket close codes
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_RATE_LIMITED = 4429


async def authenticate_ws(auth_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Authenticate WebSocket connection from auth message.

    Args:
        auth_payload: Authentication payload from client
            Expected format: {"type": "auth", "api_key": "...", "token": "..."}

    Returns:
        Authentication info dict if successful, None if failed
        Format: {"user_id": str, "roles": list[str], "tenant_id": str | None}

    Example:
        >>> auth_msg = {"type": "auth", "api_key": "test_key"}
        >>> auth_info = await authenticate_ws(auth_msg)
        >>> if auth_info:
        ...     print(f"Authenticated: {auth_info['user_id']}")
    """
    try:
        auth_type = auth_payload.get("type")
        if auth_type != "auth":
            logger.warning(f"Invalid auth message type: {auth_type}")
            return None

        # Try API key first
        api_key = auth_payload.get("api_key")
        if api_key:
            from kagami_api.security import SecurityFramework

            if SecurityFramework.validate_api_key(api_key):
                return {
                    "user_id": "api_key_user",
                    "roles": ["api_user"],
                    "tenant_id": None,
                }

        # Try JWT token
        token = auth_payload.get("token")
        if token:
            from kagami_api.security import SecurityFramework

            try:
                principal = SecurityFramework.verify_token(token)
                return {
                    "user_id": principal.sub,
                    "roles": principal.roles,
                    "tenant_id": principal.tenant_id,
                }
            except Exception as e:
                logger.warning(f"JWT verification failed: {e}")

        logger.warning("No valid credentials in auth payload")
        return None

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None


async def wait_for_auth_with_timeout(
    auth_future: asyncio.Future[dict[str, Any] | None],
    timeout: float = WS_AUTH_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    """Wait for authentication with timeout.

    Args:
        auth_future: Future that will be set with auth result
        timeout: Maximum time to wait in seconds (default: 5.0)

    Returns:
        Authentication info if successful within timeout, None otherwise

    Note:
        Emits K-8001 metric on timeout for observability.

    Example:
        >>> auth_future = asyncio.Future()
        >>> # In another coroutine: auth_future.set_result(auth_info)
        >>> auth_info = await wait_for_auth_with_timeout(auth_future)
        >>> if not auth_info:
        ...     print("Authentication timeout or failed")
    """
    import time

    start_time = time.perf_counter()

    try:
        auth_info = await asyncio.wait_for(auth_future, timeout=timeout)
        duration = time.perf_counter() - start_time

        if auth_info:
            emit_auth_metrics(success=True, duration_seconds=duration)
        else:
            emit_auth_metrics(
                success=False, reason="invalid_credentials", duration_seconds=duration
            )

        return auth_info

    except TimeoutError:
        duration = time.perf_counter() - start_time
        logger.warning(f"WebSocket authentication timeout ({timeout}s) - K-8001")
        emit_auth_metrics(success=False, reason="timeout", duration_seconds=duration)
        return None

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"Error waiting for auth: {e}")
        emit_auth_metrics(success=False, reason="error", duration_seconds=duration)
        return None


def emit_auth_metrics(success: bool, reason: str = "", duration_seconds: float = 0.0) -> None:
    """Emit authentication metrics for monitoring.

    Tracks K-8XXX WebSocket error codes:
    - K-8001: Auth timeout (reason="timeout")
    - K-8002: Auth invalid (reason="invalid_token", "invalid_key", etc.)
    - K-8003: Rate limited (reason="rate_limited")

    Args:
        success: Whether authentication succeeded
        reason: Failure reason if unsuccessful
        duration_seconds: Time taken for authentication

    Example:
        >>> emit_auth_metrics(True, duration_seconds=0.15)
        >>> emit_auth_metrics(False, reason="timeout")  # K-8001
        >>> emit_auth_metrics(False, reason="invalid_token")  # K-8002
    """
    try:
        from kagami.observability.metrics.api import (
            WS_AUTH_DURATION_SECONDS,
            WS_AUTH_FAILURES_TOTAL,
        )

        if not success:
            # Map reason to K-8XXX error code for tracking
            error_code = _reason_to_error_code(reason)
            if WS_AUTH_FAILURES_TOTAL:
                WS_AUTH_FAILURES_TOTAL.labels(
                    reason=reason or "unknown", error_code=error_code
                ).inc()
            logger.warning(f"WebSocket auth failure: {error_code} ({reason})")

        if duration_seconds > 0 and WS_AUTH_DURATION_SECONDS:
            WS_AUTH_DURATION_SECONDS.observe(duration_seconds)

    except Exception as e:
        logger.debug(f"Failed to emit auth metrics: {e}")


def _reason_to_error_code(reason: str) -> str:
    """Map auth failure reason to K-8XXX error code.

    Error code mapping:
    - K-8001: Authentication timeout
    - K-8002: Invalid credentials (token, key, etc.)
    - K-8003: Rate limited
    - K-8004: Connection closed
    - K-8005: Invalid message format
    """
    reason_lower = reason.lower() if reason else ""

    if "timeout" in reason_lower:
        return "K-8001"
    elif "rate" in reason_lower or "limit" in reason_lower:
        return "K-8003"
    elif "closed" in reason_lower or "disconnect" in reason_lower:
        return "K-8004"
    elif "format" in reason_lower or "invalid_message" in reason_lower:
        return "K-8005"
    else:
        # Default to invalid credentials
        return "K-8002"


__all__ = [
    "WS_AUTH_TIMEOUT_SECONDS",
    "WS_CLOSE_RATE_LIMITED",
    "WS_CLOSE_UNAUTHORIZED",
    "authenticate_ws",
    "emit_auth_metrics",
    "wait_for_auth_with_timeout",
]
