"""Authentication routes for K os API.

Provides authentication endpoints:
- /api/user/token - Login and get JWT
- /api/user/refresh - Refresh JWT
- /api/user/me - Current user info
- /api/user/register - New user registration
- /api/user/verify-email - Verify email address with token
- /api/user/password-reset - Request password reset email
- /api/user/password-reset/confirm - Confirm password reset with token
- /api/user/logout - Logout and invalidate token
- /api/user/api-keys - Create/list/revoke API keys
"""

import asyncio
import logging
import os
import secrets
import smtplib
import time
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from kagami.core.database.connection import get_db
from kagami.core.database.models import APIKey as DBAPIKey
from kagami.core.database.models import User as DBUser
from kagami.core.database.models import VerificationToken
from kagami.core.safety import monitor_cbf
from kagami.core.safety.cbf_integration import check_cbf_for_operation
from kagami.core.schemas.schemas.validation import RegisterRequest
from pydantic import BaseModel

from kagami_api.audit_logger import (
    AuditEventType,
    audit_login_failure,
    audit_login_success,
    get_audit_logger,
)
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import Principal, SecurityFramework, get_token_manager, require_auth
from kagami_api.security.login_tracker import get_login_tracker
from kagami_api.security.shared import ACCESS_TOKEN_EXPIRE_MINUTES
from kagami_api.security_middleware import get_security_middleware
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)


async def _safe_audit(coro: Any) -> None:
    """Execute audit logging without crashing on failure.
    
    Audit logging should never prevent authentication operations.
    Errors are logged at debug level for troubleshooting.
    """
    try:
        await coro
    except Exception as e:
        logger.debug(f"Audit logging failed (non-fatal): {type(e).__name__}: {e}")


def _safe_parse_int(value: str, default: int) -> int:
    """Parse int from string with default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_parse_float(value: str, default: float) -> float:
    """Parse float from string with default on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# Module-level dependency for backward compatibility
# This is imported by other modules that need user authentication
def get_current_user(principal: Principal = Depends(require_auth)) -> Principal:
    """Get current authenticated user/principal.

    This is a FastAPI dependency that can be used in other route modules.
    Returns the Principal object from require_auth.

    For the actual /me endpoint that returns user details, see the route handler
    inside get_router().
    """
    return principal


# Request/Response Models (MODULE LEVEL - PUBLIC API)
class TokenRequest(BaseModel):
    """Request model for token endpoint with validation."""

    username: str
    password: str
    grant_type: str = "password"


class TokenResponse(BaseModel):
    """Response model for token endpoint."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None


class RefreshTokenRequest(BaseModel):
    """Request model for refresh token endpoint."""

    refresh_token: str
    grant_type: str = "refresh_token"


class CSRFTokenResponse(BaseModel):
    """Response model for CSRF token endpoint."""

    csrf_token: str
    session_id: str


class PasswordChangeRequest(BaseModel):
    """Request model for password change."""

    current_password: str
    new_password: str


class RegisterResponse(BaseModel):
    username: str
    email: str
    message: str


class VerifyEmailResponse(BaseModel):
    message: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetResponse(BaseModel):
    message: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class LogoutResponse(BaseModel):
    """Response for logout endpoint."""

    message: str
    logged_out: bool = True


class APIKeyCreateRequest(BaseModel):
    """Request model for creating an API key."""

    name: str
    scopes: list[str] | None = None
    expires_in_days: int | None = None  # None = never expires


class APIKeyResponse(BaseModel):
    """Response model for API key (includes secret only on creation)."""

    id: str
    name: str
    key_prefix: str  # First 8 characters for identification
    scopes: list[str]
    is_active: bool
    created_at: str
    last_used_at: str | None = None
    expires_at: str | None = None
    key: str | None = None  # Full key, only returned on creation


class APIKeyListResponse(BaseModel):
    """Response model for listing API keys."""

    keys: list[APIKeyResponse]
    total: int


class UserResponse(BaseModel):
    """Response model for user information."""

    username: str
    roles: list[str]
    scopes: list[str]
    email: str | None = None
    display_name: str | None = None


# Module-level login function (PUBLIC API - for tests)
async def login(request: TokenRequest) -> TokenResponse:
    """Authenticate user and return JWT token.

    Uses secure password hashing with Argon2.
    Configure passwords via environment variables:
    - KAGAMI_ADMIN_PASSWORD
    - KAGAMI_USER_PASSWORD
    - KAGAMI_GUEST_PASSWORD
    """
    start = time.time()
    try:
        if request.grant_type != "password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported grant type"
            )
        security = SecurityFramework()
        user_store = get_user_store()
        login_tracker = await get_login_tracker()

        # CRITICAL: Use distributed lock to prevent race condition on login attempts
        # Without this lock, concurrent login requests can bypass rate limiting
        lock_key = f"kagami:login:lock:{request.username}"
        lock_acquired = False
        lock_expires = 5  # Lock expires in 5 seconds (prevents deadlock)
        lock_acquire_timeout = 5.0  # Max time to wait for lock acquisition

        # Check environment - fail hard in production if lock unavailable
        env = (os.getenv("ENVIRONMENT") or "development").lower()
        is_production = env in ("production", "prod", "staging")
        full_operation = (
            os.getenv("KAGAMI_FULL_OPERATION") or ("1" if is_production else "0")
        ).lower() in ("1", "true", "yes", "on")

        # Try to acquire distributed lock with timeout (Redis SET NX)
        try:
            if login_tracker.redis_client and login_tracker._use_redis:
                # Wrap lock acquisition in timeout to prevent hanging
                try:
                    lock_acquired = await asyncio.wait_for(
                        login_tracker.redis_client.set(  # type: ignore[arg-type]
                            lock_key, "locked", nx=True, ex=lock_expires
                        ),
                        timeout=lock_acquire_timeout,
                    )
                except TimeoutError:
                    logger.error(
                        f"Lock acquisition timeout after {lock_acquire_timeout}s "
                        f"for: {request.username}"
                    )
                    # In production, fail hard on timeout
                    if is_production or full_operation:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Authentication service temporarily unavailable",
                            headers={"Retry-After": "10"},
                        ) from None
                    # In development, allow degraded operation
                    logger.warning("Development mode: continuing without lock after timeout")
                    lock_acquired = False

                if not lock_acquired:
                    # Another request is processing this username, fail fast
                    logger.warning(f"Login rate limit lock contention for: {request.username}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Login attempt in progress. Please wait.",
                        headers={"Retry-After": str(lock_expires)},
                    )
            else:
                # Redis not available
                if is_production or full_operation:
                    # PRODUCTION: Distributed lock is MANDATORY
                    logger.error(
                        f"PRODUCTION MODE: Redis lock required but unavailable "
                        f"for login: {request.username}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Authentication service temporarily unavailable",
                        headers={"Retry-After": "30"},
                    ) from None
                else:
                    # Development: Allow degraded operation with warning
                    logger.warning(
                        f"Development mode: Redis unavailable, continuing without "
                        f"distributed lock for: {request.username}"
                    )
        except HTTPException:
            # Re-raise HTTP exceptions (429, 503)
            raise
        except Exception as e:
            # Unexpected error during lock acquisition
            logger.error(f"Unexpected error acquiring login lock for {request.username}: {e}")
            if is_production or full_operation:
                # PRODUCTION: Fail hard on unexpected errors
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service error",
                    headers={"Retry-After": "30"},
                ) from e
            else:
                # Development: Log and continue
                logger.warning(f"Development mode: continuing after lock error: {e}")

        # Start heartbeat task for lock renewal (if operation takes >3s)
        heartbeat_task: asyncio.Task | None = None
        heartbeat_interval = 3.0  # Renew lock every 3 seconds

        async def _renew_lock() -> None:
            """Heartbeat task to renew lock for long-running operations."""
            try:
                while True:
                    await asyncio.sleep(heartbeat_interval)
                    if lock_acquired and login_tracker.redis_client and login_tracker._use_redis:
                        try:
                            # Renew lock expiration
                            renewed = await asyncio.wait_for(
                                login_tracker.redis_client.expire(lock_key, lock_expires),
                                timeout=1.0,
                            )
                            if not renewed:
                                logger.warning(f"Lock renewal failed for: {request.username}")
                                break
                        except Exception as e:
                            logger.warning(f"Lock heartbeat error for {request.username}: {e}")
                            break
            except asyncio.CancelledError:
                # Normal shutdown
                pass

        try:
            # Start heartbeat task for lock renewal
            if lock_acquired:
                heartbeat_task = asyncio.create_task(_renew_lock())

            is_locked, unlock_seconds = await login_tracker.is_locked(request.username)
            if is_locked:
                logger.warning(f"Login attempt on locked account: {request.username}")
                audit_login_failure(
                    request.username,
                    None,
                    {
                        "reason": "account_locked",
                        "unlock_in_seconds": unlock_seconds,
                        "login_method": "password",
                    },
                )
                unlock_minutes = ((unlock_seconds or 0) + 59) // 60
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Account locked. Try again in {unlock_minutes} minutes.",
                    headers={"Retry-After": str(unlock_seconds)},
                )
            user = user_store.get_user(request.username)
            if not user:
                logger.warning(f"Login failed: User {request.username} not found")
                audit_login_failure(
                    request.username, None, {"reason": "user_not_found", "login_method": "password"}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
                )
            if not user_store.authenticate_user(request.username, request.password):
                remaining_attempts, now_locked = await login_tracker.record_failed_attempt(
                    request.username
                )
                logger.warning(
                    f"Login failed: Invalid password for user {request.username} "
                    f"(remaining attempts: {remaining_attempts})"
                )
                audit_login_failure(
                    request.username,
                    None,
                    {
                        "reason": "invalid_password",
                        "remaining_attempts": remaining_attempts,
                        "account_locked": now_locked,
                        "login_method": "password",
                    },
                )
                if now_locked:
                    lockout_msg = (
                        f"Too many failed attempts. Account locked for "
                        f"{login_tracker.lockout_minutes} minutes."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=lockout_msg,
                        headers={"Retry-After": str(login_tracker.lockout_minutes * 60)},
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid credentials. {remaining_attempts} attempts remaining.",
                    )
            scopes = set()
            for role in user.get("roles", []):
                if role == "admin":
                    scopes.update(["read", "write", "admin"])
                elif role == "user":
                    scopes.update(["read", "write"])
                elif role == "guest":
                    scopes.add("read")
            scopes_list = list(scopes)
            access_token = security.create_access_token(
                subject=user["username"],
                scopes=scopes_list,
                tenant_id=user.get("tenant_id"),
                additional_claims={
                    "roles": user.get("roles", []),
                    # Stable UUID (string) when available (DB-backed users)
                    "uid": user.get("id"),
                },
            )
            refresh_token = security.create_refresh_token(
                subject=user["username"],
                additional_claims={
                    "roles": user.get("roles", []),
                    "tenant_id": user.get("tenant_id"),
                    "uid": user.get("id"),
                },
            )
            expires_in = int(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds())
            await login_tracker.clear_attempts(request.username)
            logger.info(f"User {request.username} logged in successfully")
            audit_login_success(
                request.username, None, {"roles": user.get("roles", []), "login_method": "password"}
            )
            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(f"Performance violation in login endpoint: {elapsed_ms:.2f}ms")

            # Emit receipt for authentication event
            try:
                from kagami.core.receipts import UnifiedReceiptFacade

                UnifiedReceiptFacade.emit(
                    correlation_id=f"auth-login-{request.username}-{int(time.time() * 1000)}",
                    action="auth.login",
                    app="Authentication",
                    event_name="auth.login.success",
                    event_data={
                        "username": request.username,
                        "roles": user.get("roles", []),
                        "login_method": "password",
                    },
                    duration_ms=int(elapsed_ms),
                )
            except Exception as e:
                logger.debug(f"Receipt emit failed (non-fatal): {type(e).__name__}")

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=expires_in,
                refresh_token=refresh_token,
                scope=" ".join(scopes),
            )
        finally:
            # CRITICAL: Always release distributed lock and stop heartbeat
            # Cancel heartbeat task first
            if heartbeat_task and not heartbeat_task.done():
                try:
                    heartbeat_task.cancel()
                    # Wait briefly for cancellation
                    await asyncio.wait_for(heartbeat_task, timeout=0.5)
                except (TimeoutError, asyncio.CancelledError):
                    pass
                except Exception as e:
                    logger.debug(f"Heartbeat cleanup error: {e}")

            # Release lock with timeout
            if lock_acquired and login_tracker.redis_client and login_tracker._use_redis:
                try:
                    # Wrap lock release in timeout to prevent hanging
                    await asyncio.wait_for(login_tracker.redis_client.delete(lock_key), timeout=2.0)
                    logger.debug(f"Released login lock for: {request.username}")
                except TimeoutError:
                    logger.error(f"Lock release timeout for: {request.username}")
                    # Lock will auto-expire, but log the issue
                except Exception as e:
                    logger.error(f"Failed to release login lock for {request.username}: {e}")
                    # Lock will auto-expire after lock_expires seconds
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed for user {request.username}: {e}")
        audit_login_failure(
            request.username,
            None,
            {"reason": "authentication_error", "error": str(e), "login_method": "password"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication service error"
        ) from e


# Helper function for SMTP (MODULE LEVEL)
def _send_email_smtp(to_email: str, subject: str, body: str) -> None:
    """Send an email using SMTP configuration from environment.

    Required env vars:
      - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
      - SMTP_USE_TLS (optional, default true)
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", user or "noreply@kagami.local")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes", "on")
    if not host or not port or (not user) or (not password):
        logger.warning("SMTP not fully configured; email not sent")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)
    attempts_env = os.getenv("SMTP_RETRY_ATTEMPTS", "3")
    base_delay_env = os.getenv("SMTP_RETRY_BASE_DELAY_SECONDS", "0.2")
    attempts = _safe_parse_int(attempts_env, 3)
    base_delay = _safe_parse_float(base_delay_env, 0.2)

    def _send_blocking() -> None:
        last_err: Exception | None = None
        for attempt in range(max(1, attempts)):
            try:
                with smtplib.SMTP(host, port, timeout=10) as server:
                    server.ehlo()
                    if use_tls:
                        try:
                            server.starttls()
                            server.ehlo()
                        except (smtplib.SMTPException, OSError) as e:
                            logger.debug(f"STARTTLS failed (continuing without TLS): {e}")
                    server.login(user, password)
                    server.send_message(msg)
                logger.info(f"Sent email to {to_email}")
                return
            except Exception as e:
                last_err = e
                if attempt < attempts - 1:
                    delay = min(2.0, base_delay * 2**attempt)
                    try:
                        import random as _random
                        time.sleep(delay + _random.uniform(0, delay * 0.5))
                    except ImportError:
                        time.sleep(delay)
                else:
                    break
        logger.error(f"Failed to send email to {to_email}: {last_err}")

    try:
        import threading as _threading
        t = _threading.Thread(target=_send_blocking, name="smtp-send", daemon=True)
        t.start()
    except (ImportError, RuntimeError) as e:
        logger.debug(f"Threading unavailable, sending synchronously: {e}")
        _send_blocking()


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/user", tags=["user"])

    @router.post(
        "/token",
        response_model=TokenResponse,
        responses=get_error_responses(400, 401, 429, 500),
    )
    async def login_route(request: TokenRequest) -> TokenResponse:
        """Authenticate user and return JWT token (route handler).

        Delegates to module-level login() function for business logic.
        Rate limiting handled by rate_limiter middleware.
        """
        return await login(request)

    @router.post(
        "/refresh",
        response_model=TokenResponse,
        responses=get_error_responses(400, 401, 429, 500),
    )
    async def refresh_token(request: RefreshTokenRequest, req: Request) -> TokenResponse:
        """Refresh an access token using a refresh token.

        Implements token refresh rotation:
        - Verifies the refresh token
        - Detects and blocks token reuse attacks
        - Generates new access + refresh tokens
        - Blacklists the old refresh token
        - Logs refresh events for audit
        """
        start = time.time()
        try:
            if request.grant_type != "refresh_token":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported grant type"
                )

            # Delegate to token_manager for rotation logic
            token_manager = get_token_manager()

            # Collect client info for audit logging
            client_info = {
                "ip": req.client.host if req.client else None,
                "user_agent": req.headers.get("user-agent"),
            }

            # Use token_manager's refresh method (handles rotation + reuse detection)
            result = token_manager.refresh_access_token(
                request.refresh_token, client_info=client_info
            )

            if not result:
                logger.warning("Token refresh failed: Invalid or reused token")
                try:
                    get_audit_logger().log_authentication(
                        AuditEventType.TOKEN_REFRESH,
                        user_id="unknown",
                        request=req,
                        outcome="failure",
                        details={"reason": "invalid_or_reused_token"},
                    )
                except Exception as e:
                    logger.debug(f"Non-critical operation failed: {type(e).__name__}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token",
                )

            # Verify the new token to get user info for response
            security = SecurityFramework()
            principal = security.verify_refresh_token(
                result.get("refresh_token") or request.refresh_token
            )

            expires_in = int(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds())

            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(
                    f"Performance violation in refresh_token endpoint: {elapsed_ms:.2f}ms"
                )

            # Emit receipt for token refresh event
            try:
                from kagami.core.receipts import UnifiedReceiptFacade

                UnifiedReceiptFacade.emit(
                    correlation_id=f"auth-refresh-{principal.sub}-{int(time.time() * 1000)}",
                    action="auth.refresh",
                    app="Authentication",
                    event_name="auth.refresh.success",
                    event_data={
                        "username": principal.sub,
                        "rotated": "refresh_token" in result,
                    },
                    duration_ms=int(elapsed_ms),
                )
            except Exception as e:
                logger.debug(f"Non-critical operation failed: {type(e).__name__}")

            return TokenResponse(
                access_token=result["access_token"],
                token_type=result["token_type"],
                expires_in=expires_in,
                refresh_token=result.get("refresh_token"),
                scope=" ".join(principal.scopes),
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            try:
                get_audit_logger().log_authentication(
                    AuditEventType.TOKEN_REFRESH,
                    user_id="unknown",
                    request=req,
                    outcome="failure",
                    details={"reason": "internal_error", "error": str(e)},
                )
            except Exception as e:
                logger.debug(f"Non-critical operation failed: {type(e).__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token refresh failed"
            ) from e

    @router.get(
        "/csrf-token",
        responses=get_error_responses(429, 500),
    )
    async def get_csrf_token(_request: Request) -> dict[str, Any]:
        """Generate CSRF token for browser-based mutations.

        Returns a CSRF token that must be included in the X-CSRF-Token header
        for POST/PUT/PATCH/DELETE requests from browsers.
        """
        try:
            session_id = str(uuid.uuid4())
            security_middleware = get_security_middleware()
            token = await security_middleware.generate_csrf_token(session_id=session_id)

            return {
                "csrf_token": token,
                "session_id": session_id,
                "expires_in": 86400,
            }
        except Exception as e:
            logger.error(f"CSRF token generation failed: {e}")
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get(
        "/me",
        responses=get_error_responses(401, 403, 404, 429, 500),
    )
    async def get_current_user_info(principal: Principal = Depends(require_auth)) -> None:
        """Get current user information.

        Requires authentication.
        """
        start = time.time()
        try:
            user_store = get_user_store()
            user = user_store.get_user(principal.sub)
            if not user:
                # getattr with default won't raise, but list() might on non-iterable
                try:
                    roles = list(getattr(principal, "roles", []) or [])
                except (TypeError, AttributeError):
                    roles = []
                if "api_user" in roles or getattr(principal, "sub", "") == "api_key_user":
                    result = {
                        "username": getattr(principal, "sub", "api_key_user"),
                        "roles": roles or ["api_user"],
                        "scopes": list(getattr(principal, "scopes", []) or ["read"]),
                        "email": None,
                        "display_name": getattr(principal, "sub", "api_key_user"),
                    }
                    elapsed_ms = (time.time() - start) * 1000
                    if elapsed_ms > 50:
                        logger.warning(
                            f"Performance violation in get_current_user endpoint: {elapsed_ms:.2f}ms"
                        )
                    return result  # type: ignore[return-value]
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            scopes = set()
            for role in user.get("roles", []):
                if role == "admin":
                    scopes.update(["read", "write", "admin"])
                elif role == "user":
                    scopes.update(["read", "write"])
                elif role == "guest":
                    scopes.add("read")
            scopes_list = list(scopes)
            result = {
                "username": user.get("username"),
                "roles": user.get("roles", []),
                "scopes": scopes_list,
                "email": user.get("email"),
                "display_name": user.get("display_name", user.get("username")),
            }
            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > 50:
                logger.warning(
                    f"Performance violation in get_current_user endpoint: {elapsed_ms:.2f}ms"
                )
            return result  # type: ignore[return-value]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get user info for {principal.sub}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get user info"
            ) from e

    @router.post(
        "/register",
        response_model=RegisterResponse,
        responses=get_error_responses(400, 403, 409, 422, 429, 500),
    )
    async def register(request: RegisterRequest, req: Request) -> RegisterResponse:
        """Register a new user.

        Controlled by env var ALLOW_REGISTRATION (default: false). When enabled,
        creates a user as unverified and sends an email verification link via SMTP.

        Idempotency: Enforced via Idempotency-Key header (recommended for registration).
        """
        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.auth.register",
            action="create",
            target="user",
            params={"username": request.username, "email": request.email},
            metadata={"endpoint": "/api/user/register"},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        # Check idempotency for registration (prevents duplicate accounts)
        try:
            from kagami_api.idempotency import ensure_idempotency

            await ensure_idempotency(req)
        except HTTPException as e:
            # If idempotency check fails (duplicate key), return 409
            if e.status_code == 409:
                raise
            # Otherwise, log and continue (not critical for registration)
            logger.debug(f"Idempotency check skipped for registration: {e}")
        except Exception as e:
            logger.debug(f"Idempotency check failed for registration: {e}")

        allow = os.getenv("ALLOW_REGISTRATION", "false").lower() in ("1", "true", "yes", "on")
        if not allow:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled"
            )
        store = get_user_store()
        if store.user_exists(request.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
            )
        if hasattr(store, "_use_database") and getattr(store, "_use_database", False):
            try:
                for session in get_db():
                    exists = (
                        session.query(DBUser).filter(DBUser.email == request.email).first()
                        is not None
                    )
                    if exists:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use"
                        )
                    break
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Email uniqueness check failed: {e}")
        created = store.add_user(
            request.username, request.password, roles=["user"], email=request.email
        )
        if not created:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create user"
            ) from None
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)
        try:
            if getattr(store, "_use_database", False):
                for session in get_db():
                    db_user = (
                        session.query(DBUser).filter(DBUser.username == request.username).first()
                    )
                    if not db_user:
                        break
                    vt = VerificationToken(
                        user_id=db_user.id,
                        token=token,
                        token_type="email_verification",
                        expires_at=expires,
                    )
                    session.add(vt)
                    session.commit()
                    break
        except Exception as e:
            logger.error(f"Failed to store verification token: {e}")
        try:
            base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
            verify_link = f"{base_url}/auth/verify-email?token={token}"
            _send_email_smtp(
                to_email=request.email,
                subject="Verify your K os account",
                body=f"Hello {request.username},\n\nPlease verify your email by clicking the link below:\n{verify_link}\n\nThis link expires in 24 hours.\n\n— K os",
            )
        except Exception as e:
            logger.debug(f"Non-critical operation failed: {type(e).__name__}")

        # Emit receipt for registration event
        try:
            from kagami.core.receipts import UnifiedReceiptFacade

            UnifiedReceiptFacade.emit(
                correlation_id=f"auth-register-{request.username}-{int(time.time() * 1000)}",
                action="auth.register",
                app="Authentication",
                event_name="auth.register.success",
                event_data={"username": request.username, "email": request.email},
                duration_ms=0,
            )
        except Exception as e:
            logger.debug(f"Non-critical operation failed: {type(e).__name__}")

        return RegisterResponse(
            username=request.username,
            email=request.email,
            message="Registration successful. Please check your email to verify your account.",
        )

    @router.post(
        "/verify-email",
        response_model=VerifyEmailResponse,
        responses=get_error_responses(400, 404, 410, 422, 429, 500),
    )
    async def verify_email(token: str) -> VerifyEmailResponse:
        """Verify email address using the token sent during registration.

        The token is single-use and expires after 24 hours.
        Once verified, the user's email_verified flag is set to True.
        """
        if not token or len(token) < 16:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token format",
            )

        store = get_user_store()
        if not getattr(store, "_use_database", False):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Email verification requires database mode",
            )

        try:
            for session in get_db():
                # Find the verification token
                vt = (
                    session.query(VerificationToken)
                    .filter(
                        VerificationToken.token == token,
                        VerificationToken.token_type == "email_verification",
                    )
                    .first()
                )

                if not vt:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Verification token not found",
                    )

                # Check if already consumed
                if vt.consumed_at is not None:
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Verification token has already been used",
                    )

                # Check if expired
                if vt.expires_at < datetime.utcnow():
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Verification token has expired",
                    )

                # Find the user
                db_user = session.query(DBUser).filter(DBUser.id == vt.user_id).first()
                if not db_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Mark user as verified
                db_user.is_verified = True  # type: ignore[assignment]

                # Mark token as consumed
                vt.consumed_at = datetime.utcnow()  # type: ignore[assignment]

                session.commit()

                logger.info(f"Email verified for user: {db_user.username}")

                # Emit receipt
                try:
                    from kagami.core.receipts import UnifiedReceiptFacade

                    UnifiedReceiptFacade.emit(
                        correlation_id=f"auth-verify-email-{db_user.username}-{int(time.time() * 1000)}",
                        action="auth.verify_email",
                        app="Authentication",
                        event_name="auth.verify_email.success",
                        event_data={"username": db_user.username, "email": db_user.email},
                        duration_ms=0,
                    )
                except Exception as e:
                    logger.debug(f"Non-critical operation failed: {type(e).__name__}")

                return VerifyEmailResponse(
                    message="Email verified successfully. You can now log in.",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Email verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email verification failed",
            ) from e

    @router.post(
        "/password-reset",
        response_model=PasswordResetResponse,
        responses=get_error_responses(400, 422, 429, 500),
    )
    async def request_password_reset(request: PasswordResetRequest) -> PasswordResetResponse:
        """Request a password reset email.

        Sends an email with a secure token to reset the password.
        For security, always returns success even if email doesn't exist.
        Token expires after 1 hour.
        """
        # Always return success to prevent email enumeration
        success_message = (
            "If an account with this email exists, a password reset link has been sent."
        )

        if not request.email or "@" not in request.email:
            # Still return success to prevent enumeration
            return PasswordResetResponse(message=success_message)

        store = get_user_store()
        if not getattr(store, "_use_database", False):
            # In-memory mode: log warning but don't fail
            logger.warning("Password reset requested in non-database mode")
            return PasswordResetResponse(message=success_message)

        try:
            for session in get_db():
                # Find user by email
                db_user = (
                    session.query(DBUser)
                    .filter(DBUser.email == request.email, DBUser.is_active.is_(True))
                    .first()
                )

                if not db_user:
                    # Don't reveal that user doesn't exist
                    logger.debug(
                        f"Password reset requested for non-existent email: {request.email}"
                    )
                    return PasswordResetResponse(message=success_message)

                # Invalidate any existing password reset tokens for this user
                session.query(VerificationToken).filter(
                    VerificationToken.user_id == db_user.id,
                    VerificationToken.token_type == "password_reset",
                    VerificationToken.consumed_at.is_(None),
                ).update({"consumed_at": datetime.utcnow()})

                # Generate new token
                token = secrets.token_urlsafe(32)
                expires = datetime.utcnow() + timedelta(hours=1)

                vt = VerificationToken(
                    user_id=db_user.id,
                    token=token,
                    token_type="password_reset",
                    expires_at=expires,
                )
                session.add(vt)
                session.commit()

                # Send email
                try:
                    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
                    reset_link = f"{base_url}/auth/reset-password?token={token}"
                    _send_email_smtp(
                        to_email=request.email,
                        subject="Reset your K os password",
                        body=(
                            f"Hello {db_user.username},\n\n"
                            f"A password reset was requested for your account.\n\n"
                            f"Click the link below to reset your password:\n{reset_link}\n\n"
                            f"This link expires in 1 hour.\n\n"
                            f"If you did not request this, please ignore this email.\n\n"
                            f"- K os"
                        ),
                    )
                except Exception as e:
                    logger.error(f"Failed to send password reset email: {e}")
                    # Don't fail the request - token is still valid

                logger.info(f"Password reset token generated for user: {db_user.username}")

                # Emit receipt
                try:
                    from kagami.core.receipts import UnifiedReceiptFacade

                    UnifiedReceiptFacade.emit(
                        correlation_id=f"auth-password-reset-{db_user.username}-{int(time.time() * 1000)}",
                        action="auth.password_reset_request",
                        app="Authentication",
                        event_name="auth.password_reset.requested",
                        event_data={"username": db_user.username},
                        duration_ms=0,
                    )
                except Exception as e:
                    logger.debug(f"Non-critical operation failed: {type(e).__name__}")

                break

            return PasswordResetResponse(message=success_message)

        except Exception as e:
            logger.error(f"Password reset request failed: {e}")
            # Return success to prevent information leakage
            return PasswordResetResponse(message=success_message)

    @router.post(
        "/password-reset/confirm",
        response_model=PasswordResetResponse,
        responses=get_error_responses(400, 404, 410, 422, 429, 500),
    )
    async def confirm_password_reset(request: PasswordResetConfirmRequest) -> PasswordResetResponse:
        """Confirm password reset with token and new password.

        Validates the token and updates the user's password.
        Token is single-use and expires after 1 hour.
        """
        if not request.token or len(request.token) < 16:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token format",
            )

        if not request.new_password or len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters",
            )

        store = get_user_store()
        if not getattr(store, "_use_database", False):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Password reset requires database mode",
            )

        try:
            for session in get_db():
                # Find the reset token
                vt = (
                    session.query(VerificationToken)
                    .filter(
                        VerificationToken.token == request.token,
                        VerificationToken.token_type == "password_reset",
                    )
                    .first()
                )

                if not vt:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Reset token not found",
                    )

                # Check if already consumed
                if vt.consumed_at is not None:
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Reset token has already been used",
                    )

                # Check if expired
                if vt.expires_at < datetime.utcnow():
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Reset token has expired",
                    )

                # Find the user
                db_user = session.query(DBUser).filter(DBUser.id == vt.user_id).first()
                if not db_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Update password using user_store's hash function
                from kagami_api.user_store import hash_password

                db_user.hashed_password = hash_password(request.new_password)  # type: ignore[assignment]

                # Mark token as consumed
                vt.consumed_at = datetime.utcnow()  # type: ignore[assignment]

                session.commit()

                logger.info(f"Password reset completed for user: {db_user.username}")

                # Emit receipt
                try:
                    from kagami.core.receipts import UnifiedReceiptFacade

                    UnifiedReceiptFacade.emit(
                        correlation_id=f"auth-password-reset-confirm-{db_user.username}-{int(time.time() * 1000)}",
                        action="auth.password_reset_confirm",
                        app="Authentication",
                        event_name="auth.password_reset.completed",
                        event_data={"username": db_user.username},
                        duration_ms=0,
                    )
                except Exception as e:
                    logger.debug(f"Non-critical operation failed: {type(e).__name__}")

                return PasswordResetResponse(
                    message="Password has been reset successfully. You can now log in with your new password.",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password reset confirmation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password reset failed",
            ) from e

    @router.post(
        "/logout",
        response_model=LogoutResponse,
        responses=get_error_responses(401, 403, 429, 500),
    )
    @monitor_cbf("rate_limit")
    async def logout(
        request: Request,
        principal: Principal = Depends(require_auth),
    ) -> LogoutResponse:
        """Logout and invalidate the current token.

        Blacklists the access token to prevent further use.
        The refresh token should also be discarded by the client.
        """
        try:
            # Get the authorization header to extract the token
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # Blacklist the token
                try:
                    get_token_manager().blacklist_token(token)
                except Exception as e:
                    logger.warning(f"Failed to blacklist token: {e}")

            # Emit logout receipt
            try:
                from kagami.core.receipts import UnifiedReceiptFacade

                UnifiedReceiptFacade.emit(
                    correlation_id=f"auth-logout-{principal.sub}-{int(time.time() * 1000)}",
                    action="auth.logout",
                    app="Authentication",
                    event_name="auth.logout.success",
                    event_data={"username": principal.sub},
                    duration_ms=0,
                )
            except Exception as e:
                logger.debug(f"Non-critical operation failed: {type(e).__name__}")

            logger.info(f"User {principal.sub} logged out")

            return LogoutResponse(
                message="Logged out successfully",
                logged_out=True,
            )
        except Exception as e:
            logger.error(f"Logout failed for user {principal.sub}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed",
            ) from e

    # =========================================================================
    # API KEY MANAGEMENT
    # =========================================================================

    @router.post(
        "/api-keys",
        response_model=APIKeyResponse,
        responses=get_error_responses(400, 401, 403, 422, 429, 500, 501),
    )
    async def create_api_key(
        request: APIKeyCreateRequest,
        principal: Principal = Depends(require_auth),
    ) -> APIKeyResponse:
        """Create a new API key for the authenticated user.

        The full API key is only returned once at creation time.
        Store it securely - it cannot be retrieved again.

        Scopes are limited to what the user already has access to.
        """
        store = get_user_store()
        if not getattr(store, "_use_database", False):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="API key management requires database mode",
            )

        # Validate name
        if not request.name or len(request.name.strip()) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key name is required",
            )

        if len(request.name) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key name must be 255 characters or less",
            )

        # Determine scopes (default to user's scopes, or subset if specified)
        user_scopes = set(getattr(principal, "scopes", []) or ["read"])
        if request.scopes:
            # Validate requested scopes are a subset of user's scopes
            requested_scopes = set(request.scopes)
            if not requested_scopes.issubset(user_scopes):
                invalid_scopes = requested_scopes - user_scopes
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot grant scopes you don't have: {invalid_scopes}",
                )
            key_scopes = list(requested_scopes)
        else:
            key_scopes = list(user_scopes)

        try:
            for session in get_db():
                # Find the user in database
                db_user = session.query(DBUser).filter(DBUser.username == principal.sub).first()

                if not db_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Check API key limit (max 10 per user)
                existing_count = (
                    session.query(DBAPIKey)
                    .filter(
                        DBAPIKey.user_id == db_user.id,
                        DBAPIKey.is_active.is_(True),
                    )
                    .count()
                )

                if existing_count >= 10:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Maximum of 10 active API keys per user",
                    )

                # Generate secure API key (64 chars = 48 bytes of entropy)
                raw_key = secrets.token_urlsafe(48)

                # Calculate expiration
                expires_at = None
                if request.expires_in_days:
                    expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

                # Create API key record
                api_key = DBAPIKey(
                    user_id=db_user.id,
                    key=raw_key,
                    name=request.name.strip(),
                    scopes=key_scopes,
                    is_active=True,
                    expires_at=expires_at,
                )
                session.add(api_key)
                session.commit()
                session.refresh(api_key)

                logger.info(f"Created API key '{request.name}' for user: {principal.sub}")

                # Emit receipt
                try:
                    from kagami.core.receipts import UnifiedReceiptFacade

                    UnifiedReceiptFacade.emit(
                        correlation_id=f"auth-api-key-create-{principal.sub}-{int(time.time() * 1000)}",
                        action="auth.api_key.create",
                        app="Authentication",
                        event_name="auth.api_key.created",
                        event_data={
                            "username": principal.sub,
                            "key_name": request.name,
                            "key_id": str(api_key.id),
                        },
                        duration_ms=0,
                    )
                except Exception as e:
                    logger.debug(f"Non-critical operation failed: {type(e).__name__}")

                return APIKeyResponse(
                    id=str(api_key.id),
                    name=str(api_key.name),
                    key_prefix=raw_key[:8],
                    scopes=key_scopes,
                    is_active=True,
                    created_at=api_key.created_at.isoformat()
                    if api_key.created_at
                    else datetime.utcnow().isoformat(),
                    expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
                    key=raw_key,  # Only returned on creation
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create API key for user {principal.sub}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create API key",
            ) from e

    @router.get(
        "/api-keys",
        response_model=APIKeyListResponse,
        responses=get_error_responses(401, 403, 429, 500, 501),
    )
    async def list_api_keys(
        principal: Principal = Depends(require_auth),
    ) -> APIKeyListResponse:
        """List all API keys for the authenticated user.

        Returns metadata only - the actual key values cannot be retrieved.
        """
        store = get_user_store()
        if not getattr(store, "_use_database", False):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="API key management requires database mode",
            )

        try:
            for session in get_db():
                # Find the user in database
                db_user = session.query(DBUser).filter(DBUser.username == principal.sub).first()

                if not db_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Get all API keys for user
                api_keys = (
                    session.query(DBAPIKey)
                    .filter(DBAPIKey.user_id == db_user.id)
                    .order_by(DBAPIKey.created_at.desc())
                    .all()
                )

                keys = []
                for key in api_keys:
                    keys.append(
                        APIKeyResponse(
                            id=str(key.id),
                            name=str(key.name) if key.name else "Unnamed",
                            key_prefix=str(key.key)[:8] if key.key else "",
                            scopes=key.scopes or [],
                            is_active=bool(key.is_active),
                            created_at=key.created_at.isoformat() if key.created_at else "",
                            last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
                            expires_at=key.expires_at.isoformat() if key.expires_at else None,
                            key=None,  # Never return actual key
                        )
                    )

                return APIKeyListResponse(keys=keys, total=len(keys))

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to list API keys for user {principal.sub}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list API keys",
            ) from e

    @router.delete(
        "/api-keys/{key_id}",
        response_model=APIKeyResponse,
        responses=get_error_responses(401, 403, 404, 429, 500, 501),
    )
    async def revoke_api_key(
        key_id: str,
        principal: Principal = Depends(require_auth),
    ) -> APIKeyResponse:
        """Revoke (deactivate) an API key.

        The key can no longer be used for authentication after revocation.
        This action cannot be undone.
        """
        store = get_user_store()
        if not getattr(store, "_use_database", False):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="API key management requires database mode",
            )

        # Validate UUID format
        try:
            key_uuid = uuid.UUID(key_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API key ID format",
            ) from err

        try:
            for session in get_db():
                # Find the user in database
                db_user = session.query(DBUser).filter(DBUser.username == principal.sub).first()

                if not db_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Find the API key (must belong to this user)
                api_key = (
                    session.query(DBAPIKey)
                    .filter(
                        DBAPIKey.id == key_uuid,
                        DBAPIKey.user_id == db_user.id,
                    )
                    .first()
                )

                if not api_key:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="API key not found",
                    )

                # Check if already revoked
                if not api_key.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="API key is already revoked",
                    )

                # Revoke the key
                api_key.is_active = False  # type: ignore[assignment]
                session.commit()

                logger.info(f"Revoked API key '{api_key.name}' for user: {principal.sub}")

                # Emit receipt
                try:
                    from kagami.core.receipts import UnifiedReceiptFacade

                    UnifiedReceiptFacade.emit(
                        correlation_id=f"auth-api-key-revoke-{principal.sub}-{int(time.time() * 1000)}",
                        action="auth.api_key.revoke",
                        app="Authentication",
                        event_name="auth.api_key.revoked",
                        event_data={
                            "username": principal.sub,
                            "key_name": api_key.name,
                            "key_id": str(api_key.id),
                        },
                        duration_ms=0,
                    )
                except Exception as e:
                    logger.debug(f"Non-critical operation failed: {type(e).__name__}")

                return APIKeyResponse(
                    id=str(api_key.id),
                    name=str(api_key.name) if api_key.name else "Unnamed",
                    key_prefix=str(api_key.key)[:8] if api_key.key else "",
                    scopes=api_key.scopes or [],
                    is_active=False,
                    created_at=api_key.created_at.isoformat() if api_key.created_at else "",
                    last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                    expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
                    key=None,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to revoke API key for user {principal.sub}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke API key",
            ) from e

    return router


__all__ = [
    "APIKeyCreateRequest",
    "APIKeyListResponse",
    "APIKeyResponse",
    "CSRFTokenResponse",
    "LogoutResponse",
    "PasswordChangeRequest",
    "PasswordResetConfirmRequest",
    "PasswordResetRequest",
    "PasswordResetResponse",
    "RefreshTokenRequest",
    "RegisterResponse",
    "TokenRequest",
    "TokenResponse",
    "UserResponse",
    "VerifyEmailResponse",
    "get_current_user",
    "get_router",
    "login",
]
