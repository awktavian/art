"""OAuth2 Authentication Routes.

Provides OAuth2 authentication endpoints for:
- Apple Sign In (iOS, macOS)
- Google Sign In (Android, Web)

These endpoints allow users to authenticate using their existing
Apple ID or Google account, creating or linking Kagami accounts.

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.1
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from datetime import timedelta
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt as jose_jwt
from pydantic import BaseModel, Field

from kagami_api.audit_logger import audit_login_success
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import SecurityFramework
from kagami_api.security.shared import ACCESS_TOKEN_EXPIRE_MINUTES
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS (Module-level for OpenAPI schema generation)
# =============================================================================


class AppleAuthRequest(BaseModel):
    """Request for Apple Sign In."""

    id_token: str = Field(..., description="Apple identity token")
    authorization_code: str | None = Field(None, description="Apple authorization code")
    first_name: str | None = Field(None, description="User's first name (only on first sign in)")
    last_name: str | None = Field(None, description="User's last name (only on first sign in)")


class GoogleAuthRequest(BaseModel):
    """Request for Google Sign In."""

    id_token: str = Field(..., description="Google ID token")
    access_token: str | None = Field(None, description="Google access token")


class OAuthTokenResponse(BaseModel):
    """Response containing JWT tokens."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    is_new_user: bool = False
    user_id: str
    username: str
    email: str


class UnlinkRequest(BaseModel):
    """Request to unlink an OAuth provider."""

    provider: str = Field(..., description="Provider to unlink: apple, google")


def get_router() -> APIRouter:
    """Create and configure the OAuth router."""
    router = APIRouter(prefix="/api/user/oauth", tags=["user", "oauth"])

    # =============================================================================
    # APPLE SIGN IN
    # =============================================================================

    async def _verify_apple_token(id_token: str) -> dict[str, Any]:
        """Verify Apple identity token and extract claims.

        Args:
            id_token: The identity token from Apple Sign In

        Returns:
            Dict with user info: sub, email, email_verified

        Raises:
            HTTPException: If token is invalid
        """
        # Apple's public keys endpoint
        APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
        APPLE_ISSUER = "https://appleid.apple.com"

        # Get Apple's public keys
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(APPLE_KEYS_URL)
                response.raise_for_status()
                apple_keys = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Apple public keys: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify Apple credentials",
            ) from e

        # Get the key ID from token header
        try:
            unverified_header = jose_jwt.get_unverified_header(id_token)
            kid = unverified_header.get("kid")
        except Exception as e:
            logger.error(f"Invalid Apple token header: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Apple token"
            ) from e

        # Find matching key
        key = None
        for k in apple_keys.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Apple token key not found"
            )

        # Verify and decode token
        try:
            # Apple client ID (Bundle ID for iOS, Service ID for web)
            client_id = os.getenv("APPLE_CLIENT_ID", "com.kagami.ios")

            claims = jose_jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=client_id,
                issuer=APPLE_ISSUER,
            )

            return {
                "sub": claims.get("sub"),  # Unique user ID from Apple
                "email": claims.get("email"),
                "email_verified": claims.get("email_verified", False),
            }
        except jose_jwt.ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Apple token has expired"
            ) from e
        except jose_jwt.JWTClaimsError as e:
            logger.error(f"Apple token claims error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Apple token claims"
            ) from e
        except Exception as e:
            logger.error(f"Apple token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Apple token"
            ) from e

    @router.post(
        "/apple",
        response_model=OAuthTokenResponse,
        responses=get_error_responses(400, 401, 403, 500, 503),
        summary="Apple Sign In",
        description="""
        Authenticate using Apple Sign In.

        On first sign in, Apple provides the user's name (first_name, last_name).
        This information is only sent once, so capture it on first use.

        Creates a new account if user doesn't exist.
        Links to existing account if email matches.
        """,
    )
    async def apple_sign_in(
        request: AppleAuthRequest,
        http_request: Request,
    ) -> OAuthTokenResponse:
        """Authenticate with Apple Sign In."""
        start = time.time()

        # Verify Apple token
        apple_user = await _verify_apple_token(request.id_token)
        apple_sub = apple_user["sub"]
        email = apple_user.get("email")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Apple. Please allow email access.",
            )

        # Check for existing user by Apple ID or email
        user_store = get_user_store()
        user = None
        is_new_user = False

        # Try to find by SSO ID first
        if hasattr(user_store, "get_user_by_sso"):
            user = user_store.get_user_by_sso("apple", apple_sub)

        # Fall back to email lookup
        if not user:
            user = (
                user_store.get_user_by_email(email)
                if hasattr(user_store, "get_user_by_email")
                else None
            )

        # Create new user if not found
        if not user:
            is_new_user = True
            # Generate username from email or name
            base_username = email.split("@")[0]
            if request.first_name:
                base_username = f"{request.first_name.lower()}"
                if request.last_name:
                    base_username += f"_{request.last_name.lower()}"

            # Ensure unique username
            username = base_username
            counter = 1
            while user_store.user_exists(username):
                username = f"{base_username}_{counter}"
                counter += 1

            # Create user with random password (they'll use OAuth)
            random_password = secrets.token_urlsafe(32)
            created = user_store.add_user(
                username=username,
                password=random_password,
                roles=["user"],
                email=email,
                sso_provider="apple",
                sso_user_id=apple_sub,
            )

            if not created:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account",
                )

            user = user_store.get_user(username)
            logger.info(f"Created new user via Apple Sign In: {username}")
        else:
            # Link Apple ID if not already linked
            if hasattr(user_store, "link_sso") and not user.get("sso_user_id"):
                user_store.link_sso(user["username"], "apple", apple_sub)

        # Generate tokens
        security = SecurityFramework()

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
                "uid": user.get("id"),
                "oauth_provider": "apple",
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

        (time.time() - start) * 1000

        # Audit logging
        audit_login_success(
            user["username"],
            http_request.client.host if http_request.client else None,
            {
                "login_method": "oauth_apple",
                "is_new_user": is_new_user,
            },
        )

        logger.info(f"Apple Sign In successful for: {user['username']} (new={is_new_user})")

        return OAuthTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            is_new_user=is_new_user,
            user_id=str(user.get("id", "")),
            username=user["username"],
            email=email,
        )

    # =============================================================================
    # GOOGLE SIGN IN
    # =============================================================================

    async def _verify_google_token(id_token: str) -> dict[str, Any]:
        """Verify Google ID token and extract claims.

        Args:
            id_token: The ID token from Google Sign In

        Returns:
            Dict with user info: sub, email, email_verified, name, picture

        Raises:
            HTTPException: If token is invalid
        """
        # Google's token info endpoint (simpler than full JWT verification)
        GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": id_token})

                if response.status_code != 200:
                    logger.error(f"Google token verification failed: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token"
                    )

                claims = response.json()

                # Verify audience (client ID)
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                if client_id and claims.get("aud") != client_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Google token audience mismatch",
                    )

                return {
                    "sub": claims.get("sub"),  # Unique user ID from Google
                    "email": claims.get("email"),
                    "email_verified": claims.get("email_verified") == "true",
                    "name": claims.get("name"),
                    "picture": claims.get("picture"),
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Google token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify Google credentials",
            ) from e

    @router.post(
        "/google",
        response_model=OAuthTokenResponse,
        responses=get_error_responses(400, 401, 403, 500, 503),
        summary="Google Sign In",
        description="""
        Authenticate using Google Sign In.

        Creates a new account if user doesn't exist.
        Links to existing account if email matches.
        """,
    )
    async def google_sign_in(
        request: GoogleAuthRequest,
        http_request: Request,
    ) -> OAuthTokenResponse:
        """Authenticate with Google Sign In."""
        start = time.time()

        # Verify Google token
        google_user = await _verify_google_token(request.id_token)
        google_sub = google_user["sub"]
        email = google_user.get("email")
        name = google_user.get("name")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google. Please allow email access.",
            )

        # Check for existing user by Google ID or email
        user_store = get_user_store()
        user = None
        is_new_user = False

        # Try to find by SSO ID first
        if hasattr(user_store, "get_user_by_sso"):
            user = user_store.get_user_by_sso("google", google_sub)

        # Fall back to email lookup
        if not user:
            user = (
                user_store.get_user_by_email(email)
                if hasattr(user_store, "get_user_by_email")
                else None
            )

        # Create new user if not found
        if not user:
            is_new_user = True
            # Generate username from email or name
            base_username = email.split("@")[0]
            if name:
                # Use first part of name
                name_parts = name.lower().split()
                if len(name_parts) >= 2:
                    base_username = f"{name_parts[0]}_{name_parts[-1]}"
                else:
                    base_username = name_parts[0]

            # Ensure unique username
            username = base_username.replace(" ", "_")
            counter = 1
            while user_store.user_exists(username):
                username = f"{base_username}_{counter}"
                counter += 1

            # Create user with random password (they'll use OAuth)
            random_password = secrets.token_urlsafe(32)
            created = user_store.add_user(
                username=username,
                password=random_password,
                roles=["user"],
                email=email,
                sso_provider="google",
                sso_user_id=google_sub,
            )

            if not created:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account",
                )

            user = user_store.get_user(username)
            logger.info(f"Created new user via Google Sign In: {username}")
        else:
            # Link Google ID if not already linked
            if hasattr(user_store, "link_sso") and not user.get("sso_user_id"):
                user_store.link_sso(user["username"], "google", google_sub)

        # Generate tokens
        security = SecurityFramework()

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
                "uid": user.get("id"),
                "oauth_provider": "google",
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

        (time.time() - start) * 1000

        # Audit logging
        audit_login_success(
            user["username"],
            http_request.client.host if http_request.client else None,
            {
                "login_method": "oauth_google",
                "is_new_user": is_new_user,
            },
        )

        logger.info(f"Google Sign In successful for: {user['username']} (new={is_new_user})")

        return OAuthTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            is_new_user=is_new_user,
            user_id=str(user.get("id", "")),
            username=user["username"],
            email=email,
        )

    # =============================================================================
    # UNLINK OAUTH
    # =============================================================================

    @router.post(
        "/unlink",
        responses=get_error_responses(400, 401, 403, 404, 500),
        summary="Unlink OAuth provider",
        description="Unlink an OAuth provider from the current user's account.",
    )
    async def unlink_oauth(
        request: UnlinkRequest,
        http_request: Request,
    ) -> dict[str, Any]:
        """Unlink an OAuth provider from the user's account."""

        # Get current user from token
        # This will be injected via dependency
        # For now, return not implemented
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OAuth unlinking not yet implemented",
        )

    return router


__all__ = ["get_router"]
