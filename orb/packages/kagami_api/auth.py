"""Centralized Authentication Decorators for FastAPI Routes.

This module provides reusable authentication decorators and dependencies for
securing FastAPI endpoints. It integrates with the existing security infrastructure
in kagami/api/security/ and kagami/api/rbac.py.

Usage:
    from kagami_api.auth import require_auth, require_admin, get_current_user

    # Any authenticated user
    @router.get("/protected")
    async def protected_route(user: User = Depends(get_current_user)):
        return {"message": f"Hello {user.username}"}

    # Admin only
    @router.delete("/dangerous")
    async def admin_route(user: User = Depends(require_admin)):
        return {"message": "Admin action completed"}

    # Using as dependency in route decorator
    @router.get("/endpoint", dependencies=[Depends(require_auth)])
    async def endpoint():
        return {"message": "Authenticated"}

Architecture:
    - Uses kagami.api.security.require_auth for JWT/API key validation
    - Uses kagami.api.rbac.require_admin for admin role enforcement
    - Uses kagami.api.user_store.get_user_store for user lookup
    - Returns User objects for type-safe access to user properties
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from kagami_api.security import SecurityFramework, get_token_manager
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)


# ===== USER MODEL =====


class User(BaseModel):
    """User model for authenticated requests."""

    id: str
    username: str
    email: str
    roles: list[str]
    is_active: bool
    is_admin: bool
    tenant_id: str | None = None
    stripe_customer_id: str | None = None
    created_at: str | None = None
    scopes: list[str] = []  # API key scopes for authorization

    @property
    def is_superuser(self) -> bool:
        """Check if user is a superuser (has admin role)."""
        return self.is_admin

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope (for API key authorization)."""
        return scope in self.scopes


# ===== CORE AUTHENTICATION DEPENDENCY =====


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """Get the current authenticated user from JWT token.

    This is the core authentication dependency that validates JWT tokens,
    checks token blacklist, and returns a User object.

    Args:
        credentials: HTTP Bearer credentials from request header

    Returns:
        User object with authenticated user information

    Raises:
        HTTPException: 401 if token is missing, invalid, blacklisted, or user not found

    Example:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return {"username": user.username, "roles": user.roles}
    """
    if credentials is None or not credentials.credentials:
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
        # Try JWT first for tokens that look like JWTs (avoids DB hit for API key validation)
        try:
            principal = SecurityFramework.verify_token(token)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
    else:
        # Try API key authentication first for non-JWT tokens
        # SECURITY FIX: Use validate_api_key_with_context to get full scope info
        api_key_context = SecurityFramework.validate_api_key_with_context(token)
        if api_key_context is not None:
            # Return user with actual API key context including scopes
            return User(
                id=api_key_context.user_id,
                username=api_key_context.username or "api_key_user",
                email=api_key_context.email or "api@kagami.local",
                roles=["api_user"],
                is_active=True,
                is_admin=False,
                tenant_id=api_key_context.tenant_id,
                scopes=api_key_context.scopes,  # SECURITY: Include scopes for enforcement
            )

        # Fallback: try JWT anyway (in case it's malformed)
        try:
            principal = SecurityFramework.verify_token(token)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    # Get user from user store
    user_store = get_user_store()
    user_dict = user_store.get_user(principal.sub)

    if not user_dict:
        logger.warning(f"User not found in store: {principal.sub}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_dict.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Construct User object
    roles = user_dict.get("roles", [])
    is_admin = "admin" in roles or user_dict.get("is_superuser", False)

    return User(
        id=user_dict.get("id", ""),
        username=user_dict.get("username", principal.sub),
        email=user_dict.get("email", ""),
        roles=roles,
        is_active=user_dict.get("is_active", True),
        is_admin=is_admin,
        tenant_id=user_dict.get("tenant_id"),
        stripe_customer_id=user_dict.get("stripe_customer_id"),
        created_at=user_dict.get("created_at"),
    )


# ===== AUTHENTICATION DECORATORS =====


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """Require any authenticated user.

    This dependency ensures the request has valid authentication credentials
    (JWT token or API key) and returns the authenticated User object.

    Args:
        credentials: HTTP Bearer credentials from request header

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if authentication fails

    Example:
        @router.get("/protected")
        async def protected_route(user: User = Depends(require_auth)):
            return {"message": f"Hello {user.username}"}

        # Or as route dependency
        @router.get("/endpoint", dependencies=[Depends(require_auth)])
        async def endpoint():
            return {"message": "Authenticated"}
    """
    return await get_current_user(credentials)


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require admin role.

    This dependency ensures the authenticated user has admin privileges.
    It builds on top of get_current_user and adds role checking.

    Args:
        user: Current authenticated user (injected by get_current_user)

    Returns:
        User object (guaranteed to have admin role)

    Raises:
        HTTPException: 403 if user is not an admin

    Example:
        @router.delete("/system/reset")
        async def reset_system(user: User = Depends(require_admin)):
            return {"message": "System reset by admin", "admin": user.username}

        # Or as route dependency
        @router.delete("/danger", dependencies=[Depends(require_admin)])
        async def dangerous_operation():
            return {"message": "Admin-only operation"}
    """
    if not user.is_admin:
        logger.warning(
            f"Admin access denied: User {user.username} with roles {user.roles} attempted admin endpoint"
        )

        # Audit logging if available
        try:
            from kagami_api.audit_logger import audit_permission_denied

            audit_permission_denied(
                user.username,
                "unknown",
                "admin_access",
                None,
                {
                    "user_roles": user.roles,
                    "required_role": "admin",
                    "action": "access_denied",
                },
            )
        except Exception as e:
            logger.warning(f"Audit logging failed (admin denied): {e}")

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user


# ===== ROLE-BASED DEPENDENCIES =====


def require_role(required_roles: str | list[str]) -> None:
    """Create a dependency that requires specific role(s).

    This factory function returns a FastAPI dependency that checks if the
    authenticated user has at least one of the specified roles.

    Args:
        required_roles: Single role string or list of role strings

    Returns:
        Dependency function that can be used with Depends()

    Example:
        @router.post("/api/execute")
        async def execute_api(user: User = Depends(require_role(["api_user", "admin"]))):
            return {"message": f"API executed by {user.username}"}

        @router.get("/test")
        async def test_endpoint(user: User = Depends(require_role("tester"))):
            return {"message": "Test endpoint"}
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        """Check if user has required role."""
        user_roles_set = set(user.roles)
        required_roles_set = set(required_roles)

        if not user_roles_set & required_roles_set:
            logger.warning(
                f"Role access denied: User {user.username} with roles {user.roles} "
                f"attempted to access endpoint requiring one of {required_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required role: {' or '.join(required_roles)}",
            )

        return user

    return role_checker  # type: ignore[return-value]


# ===== PERMISSION-BASED DEPENDENCIES =====


def require_permission(permission: str) -> None:
    """Create a dependency that requires a specific permission.

    This factory function returns a FastAPI dependency that checks if the
    authenticated user's roles grant the specified permission.

    Args:
        permission: Permission string (e.g., "system:write", "file:delete")

    Returns:
        Dependency function that can be used with Depends()

    Example:
        from kagami_api.rbac import Permission

        @router.delete("/files/{file_id}")
        async def delete_file(
            file_id: str,
            user: User = Depends(require_permission(Permission.FILE_DELETE))
        ):
            return {"message": f"File {file_id} deleted by {user.username}"}
    """
    from kagami_api.rbac import get_user_permissions

    async def permission_checker(user: User = Depends(get_current_user)) -> User:
        """Check if user has required permission."""
        user_permissions = get_user_permissions(user.roles)

        if permission not in user_permissions:
            logger.warning(
                f"Permission denied: User {user.username} with roles {user.roles} "
                f"attempted to access endpoint requiring permission {permission}"
            )

            # Audit logging if available
            try:
                from kagami_api.audit_logger import audit_permission_denied

                audit_permission_denied(
                    user.username,
                    "unknown",
                    permission,
                    None,
                    {
                        "user_roles": user.roles,
                        "required_permission": permission,
                        "action": "access_denied",
                    },
                )
            except Exception as e:
                logger.warning(f"Audit logging failed (permission denied): {e}")

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}",
            )

        return user

    return permission_checker  # type: ignore[return-value]


# ===== SCOPE-BASED DEPENDENCIES (API KEY AUTHORIZATION) =====


def require_scope(required_scopes: str | list[str]) -> None:
    """Create a dependency that requires specific API key scope(s).

    This factory function returns a FastAPI dependency that checks if the
    authenticated API key has at least one of the specified scopes.
    This is the primary mechanism for enforcing API key authorization.

    SECURITY: This function enforces that API keys can only access
    endpoints they are authorized for based on their scopes.

    Args:
        required_scopes: Single scope string or list of scope strings

    Returns:
        Dependency function that can be used with Depends()

    Example:
        @router.post("/api/write")
        async def write_data(user: User = Depends(require_scope("api:write"))):
            return {"message": f"Write operation by {user.username}"}

        @router.get("/api/admin/stats")
        async def admin_stats(user: User = Depends(require_scope(["api:admin", "api:read"]))):
            return {"message": "Admin stats"}
    """
    if isinstance(required_scopes, str):
        required_scopes = [required_scopes]

    async def scope_checker(user: User = Depends(get_current_user)) -> User:
        """Check if user/API key has required scope."""
        # JWT tokens always have full access (scopes are in JWT claims if needed)
        # API keys must have explicit scopes
        if user.scopes:
            # This is an API key authentication - enforce scopes
            user_scopes_set = set(user.scopes)
            required_scopes_set = set(required_scopes)

            if not user_scopes_set & required_scopes_set:
                logger.warning(
                    f"Scope access denied: API key user {user.username} with scopes {user.scopes} "
                    f"attempted to access endpoint requiring one of {required_scopes}"
                )

                # Audit logging if available
                try:
                    from kagami_api.audit_logger import audit_permission_denied

                    audit_permission_denied(
                        user.username,
                        "unknown",
                        f"scope:{required_scopes[0]}",
                        None,
                        {
                            "user_scopes": user.scopes,
                            "required_scopes": required_scopes,
                            "action": "scope_denied",
                        },
                    )
                except Exception as e:
                    logger.warning(f"Audit logging failed (scope denied): {e}")

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient scope. Required: {' or '.join(required_scopes)}",
                )

        return user

    return scope_checker  # type: ignore[return-value]


# ===== OPTIONAL AUTHENTICATION =====


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User | None:
    """Get current user if authenticated, None otherwise.

    This is useful for endpoints that have different behavior for authenticated
    vs. anonymous users, but don't require authentication.

    Args:
        credentials: HTTP Bearer credentials from request header

    Returns:
        User object if authenticated, None if not

    Example:
        @router.get("/public/info")
        async def get_info(user: User | None = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.username}", "premium": True}
            return {"message": "Hello guest", "premium": False}
    """
    if credentials is None or not credentials.credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# ===== UTILITY FUNCTIONS =====


async def get_user_from_token(token: str) -> User:
    """Get user from a raw JWT token string.

    This is a utility function for non-FastAPI contexts where you have
    a token string and need to get the User object.

    Args:
        token: JWT token string

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found

    Example:
        from kagami_api.auth import get_user_from_token

        async def process_websocket(token: str):
            user = await get_user_from_token(token)
            print(f"WebSocket user: {user.username}")
    """
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return await get_current_user(credentials)


def verify_token_sync(token: str) -> dict[str, Any] | None:
    """Synchronously verify a token and return payload.

    This is a utility for synchronous contexts where you need to validate
    a token without async/await.

    Args:
        token: JWT token string

    Returns:
        Token payload dict if valid, None if invalid

    Example:
        from kagami_api.auth import verify_token_sync

        def check_token(token: str) -> bool:
            payload = verify_token_sync(token)
            return payload is not None
    """
    try:
        from jose import jwt

        from kagami_api.security import ALGORITHM, SECRET_KEY

        token_manager = get_token_manager()

        # Check blacklist first
        if token_manager.is_token_blacklisted(token):
            return None

        # Decode and return payload
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return dict(payload)
    except Exception:
        return None


# ===== EXPORTS =====

__all__ = [
    "User",
    "get_current_user",
    "get_current_user_optional",
    "get_user_from_token",
    "require_admin",
    "require_auth",
    "require_permission",
    "require_role",
    "require_scope",  # SECURITY: API key scope enforcement
    "verify_token_sync",
]
