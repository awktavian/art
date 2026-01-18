"""Unified Security Module for K os API.

Consolidated from multiple auth modules (November 1, 2025 - Batch 2).

Before (7 files):
- kagami/api/security.py (576 lines)
- kagami/api/auth/__init__.py (66 lines)
- kagami/api/token_manager.py
- kagami/api/login_tracker.py
- kagami/api/auth/oidc.py
- kagami/api/websocket/auth_common.py
- kagami/api/routes/auth.py (kept separate - endpoints only)

After (1 module):
- kagami/api/security/ (unified module)
  ├── __init__.py (this file - core auth logic)
  ├── token_manager.py (revocation, blacklisting)
  ├── login_tracker.py (rate limiting, login attempts)
  ├── oidc.py (OpenID Connect)
  └── websocket.py (WebSocket first-frame auth)

This consolidation:
1. Eliminates circular import risks
2. Reduces security attack surface
3. Provides single source of truth for auth
4. Simplifies testing and auditing

Usage:
    from kagami_api.security import require_auth, SecurityFramework, Principal

    @app.get("/protected")
    async def endpoint(principal: Principal = Depends(require_auth)):
        return {"user": principal.sub}
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

# Import centralized configuration
from kagami.core.config import get_config, get_int_config
from kagami.core.database.connection import get_db
from pydantic import BaseModel

# Import API key manager (NEW - secure validation)
from .api_key_manager import APIKeyContext, APIKeyManager, get_api_key_manager

# Import token manager from submodule
from .token_manager import TokenManager, get_token_manager

logger = logging.getLogger(__name__)

# ===== JWT CONFIGURATION =====

SECRET_KEY = get_config("JWT_SECRET") or os.getenv("JWT_SECRET")
JWT_SECRET = SECRET_KEY  # Back-compat alias

if not SECRET_KEY:
    env = (os.getenv("ENVIRONMENT") or "development").lower()
    if env == "production":
        raise ValueError("JWT_SECRET is required in production")
    else:
        import secrets as _secrets

        SECRET_KEY = _secrets.token_urlsafe(64)
        JWT_SECRET = SECRET_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = get_int_config("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
REFRESH_TOKEN_EXPIRE_DAYS = get_int_config("REFRESH_TOKEN_EXPIRE_DAYS", 7)

# Security validation constants
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

API_KEY = get_config("KAGAMI_API_KEY")
_valid_keys_raw = get_config("VALID_API_KEYS", "")
_valid_keys_str = _valid_keys_raw if isinstance(_valid_keys_raw, str) else ""
VALID_API_KEYS: list[str] = [k.strip() for k in _valid_keys_str.split(",") if k.strip()]

# Security scheme
security = HTTPBearer(auto_error=False)


# Custom header extractor for both Authorization and X-API-Key
async def get_auth_credentials(
    authorization: str | None = Header(None, alias="Authorization"),
    api_key: str | None = Header(None, alias="X-API-Key"),
) -> HTTPAuthorizationCredentials | None:
    """Extract credentials from Authorization OR X-API-Key header.

    This allows clients to authenticate using either:
    - Authorization: Bearer <token>
    - X-API-Key: <api_key>

    Args:
        authorization: Value from Authorization header
        api_key: Value from X-API-Key header

    Returns:
        HTTPAuthorizationCredentials with the token/key, or None if neither provided
    """
    if api_key:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=api_key)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return None


# ===== DATA MODELS =====


class Principal(BaseModel):
    """Represents an authenticated principal."""

    sub: str  # Subject (username or user ID)
    roles: list[str] = []
    scopes: list[str] = []
    tenant_id: str | None = None
    user_id: str | None = None
    exp: datetime | None = None

    def has_scope(self, scope: str) -> bool:
        """Check if principal has a specific scope (for API key authorization)."""
        return scope in self.scopes


# ===== SECURITY FRAMEWORK =====


class SecurityFramework:
    """Security framework for API key and JWT validation."""

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """Validate API key against database.

        DEPRECATED: Use validate_api_key_with_context() instead for full context.

        This method is kept for backward compatibility but now performs
        proper database validation instead of prefix-only checks.

        Security:
            - Database lookup with SHA-256 hash
            - Expiration validation
            - Revocation status check
            - No test/dev bypass in production
        """
        if not api_key:
            return False

        # SECURITY FIX: Remove dangerous prefix-only validation
        # OLD (VULNERABLE): if api_key.startswith("sk_pro_"): return True
        # NEW: Proper database validation

        # Test/dev bypass only in test mode (not dev or production)
        try:
            (os.getenv("ENVIRONMENT") or "development").lower()
            boot_mode = (os.getenv("KAGAMI_BOOT_MODE") or "").lower()
        except Exception:
            boot_mode = ""

        # SECURITY: Only allow test keys in actual test mode (CI/pytest)
        if boot_mode == "test":
            test_prefixes = ("test_", "test-", "dev_", "dev-", "sk-test-")
            if any(api_key.startswith(p) for p in test_prefixes):
                logger.info("API key validation: Accepted test key (test mode only)")
                return True

        # NEW: Database validation (proper implementation)
        try:
            db = next(get_db())
            api_key_manager = get_api_key_manager()
            context = api_key_manager.validate_api_key(db, api_key)
            return context is not None
        except Exception as e:
            logger.error(f"API key validation failed: {e}", exc_info=True)
            return False

    @staticmethod
    def validate_api_key_with_context(api_key: str) -> APIKeyContext | None:
        """Validate API key and return full context.

        Args:
            api_key: Plaintext API key from request

        Returns:
            APIKeyContext with user info and permissions, or None if invalid

        Security:
            - SHA-256 hash lookup in database
            - Constant-time comparison
            - Expiration validation
            - Revocation check
            - Scope validation

        Example:
            >>> context = SecurityFramework.validate_api_key_with_context("sk_pro_...")
            >>> if context and context.tier == "pro":
            ...     # Allow pro features
        """
        if not api_key:
            return None

        # SECURITY: Only allow test keys in actual test mode (CI/pytest)
        boot_mode = (os.getenv("KAGAMI_BOOT_MODE") or "").lower()
        if boot_mode == "test":
            test_prefixes = ("test_", "test-", "dev_", "dev-", "sk-test-")
            if any(api_key.startswith(p) for p in test_prefixes):
                logger.info("API key validation: Accepted test key (test mode only)")
                # Return a synthetic context for test keys
                return APIKeyContext(
                    key_id="test-key-id",
                    user_id="test-user-id",
                    tier="pro",
                    scopes=["read", "write", "admin"],  # Full access for tests
                    username="test_user",
                    email="test@kagami.local",
                    tenant_id=None,
                )

        try:
            db = next(get_db())
            api_key_manager = get_api_key_manager()
            return api_key_manager.validate_api_key(db, api_key)
        except Exception as e:
            logger.error(f"API key validation failed: {e}", exc_info=True)
            return None

    @staticmethod
    def create_access_token(
        subject: str,
        scopes: list[str] | None = None,
        roles: list[str] | None = None,
        tenant_id: str | None = None,
        expires_delta: timedelta | None = None,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create JWT access token."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "scopes": scopes or [],
            "roles": roles or [],
        }

        if tenant_id:
            to_encode["tenant_id"] = tenant_id

        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        # jose.jwt stubs are not always precise; normalize to str.
        return str(encoded_jwt)

    @staticmethod
    def create_refresh_token(
        subject: str,
        additional_claims: dict[str, Any] | None = None,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create JWT refresh token with token family ID for rotation tracking.

        Delegates to TokenManager to ensure all refresh tokens include:
        - Standard JWT claims (sub, exp, iat, type)
        - Token family ID for rotation and reuse detection
        - Custom additional claims

        Args:
            subject: User identifier (username or user ID)
            additional_claims: Additional claims to include in the token
            expires_delta: Custom expiration timedelta (defaults to REFRESH_TOKEN_EXPIRE_DAYS)

        Returns:
            Encoded JWT refresh token with family_id
        """
        # Delegate to TokenManager for consistent token generation with family_id
        token_manager = get_token_manager()

        # Prepare data payload
        data = {"sub": subject}
        if additional_claims:
            data.update(additional_claims)

        # Use TokenManager to create token with family_id
        return token_manager.create_refresh_token(
            data=data,
            expires_delta=expires_delta,
            family_id=None,  # Let TokenManager generate a new family_id
        )

    @staticmethod
    def verify_token(token: str) -> Principal:
        """Verify JWT token and return principal."""
        try:
            # Check if token is blacklisted
            token_manager = get_token_manager()
            is_blacklisted = token_manager.is_token_blacklisted(token)
            import os

            if os.getenv("KAGAMI_TEST_MODE") == "1":
                logger.debug(
                    f"Blacklist check: instance={id(token_manager)}, is_blacklisted={is_blacklisted}, blacklist_size={len(token_manager.blacklisted_tokens)}"
                )
            if is_blacklisted:
                logger.info("Rejecting blacklisted token")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Decode token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check if user is revoked
            issued_at = payload.get("iat")
            if issued_at and token_manager.is_user_revoked(username, issued_at):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User access has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            roles = payload.get("roles", [])
            scopes = payload.get("scopes", [])
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("uid") or payload.get("user_id")

            logger.info(f"Token verified for user: {username}, scopes: {scopes}")
            return Principal(
                sub=username,
                roles=roles,
                scopes=scopes,
                tenant_id=tenant_id,
                user_id=str(user_id) if user_id is not None else None,
            )

        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    @staticmethod
    def verify_refresh_token(token: str) -> Principal:
        """Verify refresh token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            token_type: str = payload.get("type", "")

            if username is None or token_type != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )

            roles = payload.get("roles", []) or []
            scopes = payload.get("scopes", []) or []
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("uid") or payload.get("user_id")

            return Principal(
                sub=username,
                roles=list(roles) if isinstance(roles, list) else [],
                scopes=list(scopes) if isinstance(scopes, list) else [],
                tenant_id=tenant_id,
                user_id=str(user_id) if user_id is not None else None,
            )

        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from None


# ===== AUTHENTICATION DEPENDENCY =====


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(get_auth_credentials),
) -> Principal:
    """Universal auth dependency that accepts either JWT or API key.

    Now supports authentication via:
    - Authorization: Bearer <token>
    - X-API-Key: <api_key>

    SECURITY: No bypasses - all requests must provide valid credentials.
    """
    if credentials is None or not getattr(credentials, "credentials", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Detect token type by format to avoid unnecessary validation attempts
    # JWT tokens have format: <header>.<payload>.<signature> (3 parts separated by dots)
    # API keys are typically single strings without dots
    is_likely_jwt = token.count(".") == 2

    if is_likely_jwt:
        # Try JWT first for tokens that look like JWTs
        try:
            return SecurityFramework.verify_token(token)
        except HTTPException:
            # If JWT fails, don't try API key - this is clearly a JWT
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
    else:
        # Try API key first for tokens without JWT structure
        # SECURITY FIX: Use validate_api_key_with_context to get full scope info
        api_key_context = SecurityFramework.validate_api_key_with_context(token)
        if api_key_context is not None:
            # Return Principal with actual API key scopes for authorization enforcement
            return Principal(
                sub=api_key_context.username or "api_key_user",
                roles=["api_user"],
                scopes=api_key_context.scopes,  # SECURITY: Include scopes for enforcement
                user_id=api_key_context.user_id,
                tenant_id=api_key_context.tenant_id,
            )

        # Fallback: try JWT anyway (in case it's malformed)
        try:
            return SecurityFramework.verify_token(token)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None


# Optional auth (returns None if not authenticated)
async def optional_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(get_auth_credentials),
) -> Principal | None:
    """Optional authentication - returns Principal if valid, None otherwise.

    Supports both Authorization: Bearer and X-API-Key headers.
    """
    if credentials is None or not getattr(credentials, "credentials", None):
        return None

    try:
        return await require_auth(request, credentials)
    except HTTPException:
        return None


# ===== PASSWORD UTILITIES =====


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return bool(pwd_context.verify(plain_password, hashed_password))
    except ImportError:
        # Fallback if passlib not available
        logger.warning("passlib not available, password verification disabled")
        return False


def hash_password(password: str) -> str:
    """Hash password for storage."""
    try:
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return str(pwd_context.hash(password))
    except ImportError:
        raise ImportError("passlib required for password hashing") from None


# ===== STANDALONE UTILITY FUNCTIONS =====


def verify_api_key(api_key: str | None) -> bool:
    """Verify an API key against configured valid keys.

    This is a convenience function wrapping SecurityFramework.validate_api_key().

    Args:
        api_key: API key to verify (can be None)

    Returns:
        True if valid, False otherwise

    Example:
        >>> from kagami_api.security import verify_api_key
        >>> if verify_api_key(request.headers.get("X-API-Key")):
        ...     # Proceed with authenticated request
        ...     pass
    """
    if api_key is None:
        return False
    return SecurityFramework.validate_api_key(api_key)


async def verify_api_key_with_context(
    request: Any,  # fastapi.Request
    db_getter: Any = None,  # Callable[[], Generator]
) -> dict[str, Any]:
    """Verify API key from request and return full context.

    This is the production-grade async verification used by API routes.
    Validates against database with cryptographic verification.

    Args:
        request: FastAPI Request object
        db_getter: Optional callable to get DB session (defaults to get_db)

    Returns:
        Dictionary with tier, user_id, scopes, key_id, username, tenant_id

    Raises:
        HTTPException: 401 if invalid/expired/revoked, 500 on service error

    Example:
        from kagami_api.security import verify_api_key_with_context

        async def my_endpoint(request: Request):
            auth = await verify_api_key_with_context(request)
            # auth["tier"], auth["user_id"], etc.
    """
    import logging

    from fastapi import HTTPException

    logger = logging.getLogger(__name__)

    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Use provided db_getter or default
    if db_getter is None:
        from kagami.core.database import get_db

        db_getter = get_db

    # Validate against database
    try:
        db = next(db_getter())
        api_key_manager = get_api_key_manager()
        context = api_key_manager.validate_api_key(db, api_key)

        if not context:
            raise HTTPException(status_code=401, detail="Invalid or expired API key")

        return {
            "tier": context.tier,
            "key_id": context.key_id,
            "user_id": context.user_id,
            "scopes": context.scopes,
            "username": context.username,
            "tenant_id": context.tenant_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key verification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication service error") from None


# ===== ROLE CHECKS =====


def require_admin(user: dict[str, Any]) -> None:
    """Check if user has admin/owner/tester role.

    Args:
        user: User dict from authentication

    Raises:
        HTTPException: 403 if user lacks required role
    """
    roles = user.get("roles") or [] if isinstance(user, dict) else []
    if not any(r in roles for r in ("admin", "owner", "tester")):
        raise HTTPException(status_code=403, detail="Admin required")


def require_role(user: dict[str, Any], *required_roles: str) -> None:
    """Check if user has any of the required roles.

    Args:
        user: User dict from authentication
        *required_roles: Role names to check

    Raises:
        HTTPException: 403 if user lacks all required roles
    """
    roles = user.get("roles") or [] if isinstance(user, dict) else []
    if not any(r in roles for r in required_roles):
        raise HTTPException(
            status_code=403,
            detail=f"Required role: {' or '.join(required_roles)}",
        )


def require_scope(principal: Principal, *required_scopes: str) -> None:
    """Check if principal has any of the required scopes.

    SECURITY: This function enforces API key scope authorization.
    API keys can only access endpoints they are authorized for.

    Args:
        principal: Principal from authentication
        *required_scopes: Scope names to check (e.g., "api:read", "api:write")

    Raises:
        HTTPException: 403 if principal lacks all required scopes

    Example:
        @app.get("/protected")
        async def endpoint(principal: Principal = Depends(require_auth)):
            require_scope(principal, "api:read")
            return {"message": "Authorized"}
    """
    if not principal.scopes:
        # JWT tokens without explicit scopes have full access (backward compatibility)
        return

    if not any(s in principal.scopes for s in required_scopes):
        logger.warning(
            f"Scope access denied: {principal.sub} with scopes {principal.scopes} "
            f"attempted to access endpoint requiring one of {required_scopes}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Required scope: {' or '.join(required_scopes)}",
        )


# ===== EXPORTS =====

__all__ = [
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "ALGORITHM",
    "API_KEY",
    "JWT_SECRET",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    # Constants
    "SECRET_KEY",
    "VALID_API_KEYS",
    "APIKeyContext",
    # API key management (NEW - secure validation)
    "APIKeyManager",
    # Core classes
    "Principal",
    "SecurityFramework",
    # Token management
    "TokenManager",
    "get_api_key_manager",
    "get_auth_credentials",
    "get_token_manager",
    "hash_password",
    "optional_auth",
    # Role checks
    "require_admin",
    # Dependencies
    "require_auth",
    "require_role",
    "require_scope",  # SECURITY: API key scope enforcement
    "security",
    # Standalone utilities
    "verify_api_key",
    "verify_api_key_with_context",
    # Password utilities
    "verify_password",
]

# ===== BACKWARD COMPATIBILITY ALIASES =====

# Support old import path: from kagami_api.security import ...
# (This file IS the new kagami.api.security module)
