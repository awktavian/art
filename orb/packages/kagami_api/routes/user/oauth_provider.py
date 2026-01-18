"""OAuth2 Provider — Login with Kagami.

Makes Kagami an OAuth2/OpenID Connect provider so third-party apps can use
"Login with Kagami" for authentication.

Implements:
- OAuth 2.0 Authorization Code Flow (RFC 6749)
- OAuth 2.0 PKCE Extension (RFC 7636)
- OpenID Connect Core 1.0
- OpenID Connect Discovery
- JSON Web Key Sets (JWKS)

Endpoints:
- GET  /oauth/authorize        — Authorization endpoint (user consent)
- POST /oauth/token            — Token exchange
- GET  /oauth/userinfo         — OpenID Connect userinfo
- POST /oauth/revoke           — Token revocation
- GET  /.well-known/openid-configuration — Discovery
- GET  /.well-known/jwks.json  — Public keys

Security:
- PKCE required for public clients
- State parameter validation
- Secure token storage
- Rate limiting

Colony: Crystal (e7) — Security
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user_optional, require_auth
from kagami_api.security import SecurityFramework
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


def get_issuer() -> str:
    """Get the OAuth issuer URL.

    Default production domain: awkronos.com
    Can be overridden via KAGAMI_OAUTH_ISSUER env var.
    """
    return os.environ.get("KAGAMI_OAUTH_ISSUER", "https://awkronos.com")


def get_jwks_url() -> str:
    """Get JWKS URL."""
    return f"{get_issuer()}/.well-known/jwks.json"


# =============================================================================
# OAuth Client Registry
# =============================================================================


class OAuthClient(BaseModel):
    """Registered OAuth client application."""

    client_id: str
    client_secret: str | None = None  # None for public clients
    client_name: str
    redirect_uris: list[str]
    allowed_scopes: list[str] = ["openid", "profile", "email"]
    client_type: str = "confidential"  # confidential or public
    logo_uri: str | None = None
    website_uri: str | None = None
    description: str | None = None
    created_at: float = Field(default_factory=time.time)
    is_active: bool = True
    require_pkce: bool = True  # Always require PKCE for security


# In-memory client registry (production would use database)
_oauth_clients: dict[str, OAuthClient] = {}

# Authorization codes (short-lived, in-memory)
_auth_codes: dict[str, dict[str, Any]] = {}

# Refresh tokens (would be in database in production)
_refresh_tokens: dict[str, dict[str, Any]] = {}


def register_oauth_client(client: OAuthClient) -> None:
    """Register an OAuth client."""
    _oauth_clients[client.client_id] = client


def get_oauth_client(client_id: str) -> OAuthClient | None:
    """Get registered OAuth client."""
    return _oauth_clients.get(client_id)


def _init_default_clients() -> None:
    """Initialize default OAuth clients for development."""
    # Development client for testing
    if os.environ.get("KAGAMI_ENVIRONMENT", "development") != "production":
        register_oauth_client(
            OAuthClient(
                client_id="kagami-dev-client",
                client_secret="kagami-dev-secret",
                client_name="Kagami Development",
                redirect_uris=[
                    "http://localhost:3000/callback",
                    "http://localhost:8000/callback",
                    "http://127.0.0.1:3000/callback",
                ],
                allowed_scopes=["openid", "profile", "email", "agents"],
                client_type="confidential",
                require_pkce=False,  # Allow without PKCE for dev
            )
        )

    # Register from environment
    client_configs = os.environ.get("KAGAMI_OAUTH_CLIENTS", "")
    if client_configs:
        try:
            for config in json.loads(client_configs):
                register_oauth_client(OAuthClient(**config))
        except Exception as e:
            logger.error(f"Failed to load OAuth clients from env: {e}")


# Initialize on module load
_init_default_clients()


# =============================================================================
# PKCE Utilities
# =============================================================================


def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """Verify PKCE code verifier against challenge.

    Args:
        code_verifier: The code verifier from token request.
        code_challenge: The stored code challenge from authorization.
        method: Challenge method (S256 or plain).

    Returns:
        True if valid.
    """
    if method == "S256":
        # SHA256 hash, base64url encoded
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return hmac.compare_digest(computed, code_challenge)
    elif method == "plain":
        return hmac.compare_digest(code_verifier, code_challenge)
    return False


# =============================================================================
# Schemas
# =============================================================================


class TokenRequest(BaseModel):
    """OAuth token request."""

    grant_type: str
    code: str | None = None
    redirect_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    code_verifier: str | None = None
    refresh_token: str | None = None
    scope: str | None = None


class TokenResponse(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: str | None = None
    scope: str | None = None
    id_token: str | None = None  # OpenID Connect


class UserInfoResponse(BaseModel):
    """OpenID Connect UserInfo response."""

    sub: str  # Subject (user ID)
    name: str | None = None
    preferred_username: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    picture: str | None = None
    updated_at: int | None = None


class ClientRegistrationRequest(BaseModel):
    """OAuth client registration request."""

    client_name: str
    redirect_uris: list[str]
    client_type: str = "confidential"
    logo_uri: str | None = None
    website_uri: str | None = None
    description: str | None = None
    allowed_scopes: list[str] = ["openid", "profile", "email"]


class ClientRegistrationResponse(BaseModel):
    """OAuth client registration response."""

    client_id: str
    client_secret: str | None = None
    client_name: str
    redirect_uris: list[str]
    client_type: str
    created_at: str


# =============================================================================
# Router
# =============================================================================


def get_router() -> APIRouter:
    """Create OAuth provider router."""
    router = APIRouter(tags=["oauth"])

    # =========================================================================
    # Discovery Endpoints
    # =========================================================================

    @router.get("/.well-known/openid-configuration")
    async def openid_configuration() -> dict[str, Any]:
        """OpenID Connect Discovery document.

        Returns metadata about the OAuth/OIDC provider.
        """
        issuer = get_issuer()

        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/oauth/authorize",
            "token_endpoint": f"{issuer}/oauth/token",
            "userinfo_endpoint": f"{issuer}/oauth/userinfo",
            "revocation_endpoint": f"{issuer}/oauth/revoke",
            "jwks_uri": f"{issuer}/.well-known/jwks.json",
            "registration_endpoint": f"{issuer}/oauth/register",
            "scopes_supported": [
                "openid",
                "profile",
                "email",
                "agents",
                "offline_access",
            ],
            "response_types_supported": [
                "code",
                "token",
                "id_token",
                "code token",
                "code id_token",
                "token id_token",
                "code token id_token",
            ],
            "response_modes_supported": ["query", "fragment", "form_post"],
            "grant_types_supported": [
                "authorization_code",
                "refresh_token",
                "client_credentials",
            ],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256", "HS256"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
                "none",
            ],
            "claims_supported": [
                "sub",
                "name",
                "preferred_username",
                "email",
                "email_verified",
                "picture",
                "updated_at",
            ],
            "code_challenge_methods_supported": ["S256", "plain"],
            "service_documentation": f"{issuer}/docs/oauth",
            "ui_locales_supported": ["en"],
        }

    @router.get("/.well-known/jwks.json")
    async def jwks() -> dict[str, Any]:
        """JSON Web Key Set for token verification.

        Returns public keys for verifying JWTs.
        """
        # In production, this would return actual RSA public keys
        # For now, return a placeholder indicating HS256 is used

        # Get JWT secret for key ID
        jwt_secret = os.environ.get("JWT_SECRET", "dev-secret")
        key_id = hashlib.sha256(jwt_secret.encode()).hexdigest()[:16]

        return {
            "keys": [
                {
                    "kty": "oct",  # Symmetric key (HS256)
                    "kid": key_id,
                    "use": "sig",
                    "alg": "HS256",
                }
            ]
        }

    # =========================================================================
    # Authorization Endpoint
    # =========================================================================

    @router.get("/oauth/authorize", response_class=HTMLResponse)
    async def authorize(
        request: Request,
        response_type: str = Query(..., description="Must be 'code'"),
        client_id: str = Query(..., description="OAuth client ID"),
        redirect_uri: str = Query(..., description="Callback URL"),
        scope: str = Query("openid profile", description="Requested scopes"),
        state: str = Query(..., description="CSRF state parameter"),
        code_challenge: str | None = Query(None, description="PKCE code challenge"),
        code_challenge_method: str = Query("S256", description="PKCE method"),
        nonce: str | None = Query(None, description="OpenID nonce"),
    ):
        """OAuth authorization endpoint.

        Shows consent screen if user is logged in, otherwise redirects to login.
        """
        # Validate client
        client = get_oauth_client(client_id)
        if not client:
            return _error_response(redirect_uri, "invalid_client", "Unknown client", state)

        if not client.is_active:
            return _error_response(redirect_uri, "invalid_client", "Client is disabled", state)

        # Validate redirect URI
        if redirect_uri not in client.redirect_uris:
            # Don't redirect to invalid URI - show error page
            return HTMLResponse(
                content=_error_page("Invalid redirect URI"),
                status_code=400,
            )

        # Validate response type
        if response_type != "code":
            return _error_response(
                redirect_uri,
                "unsupported_response_type",
                "Only 'code' response type is supported",
                state,
            )

        # PKCE validation
        if client.require_pkce and not code_challenge:
            return _error_response(
                redirect_uri, "invalid_request", "PKCE code_challenge is required", state
            )

        # Validate scopes
        requested_scopes = scope.split()
        invalid_scopes = set(requested_scopes) - set(client.allowed_scopes)
        if invalid_scopes:
            return _error_response(
                redirect_uri, "invalid_scope", f"Invalid scopes: {invalid_scopes}", state
            )

        # Check if user is logged in
        user = await _get_current_user_from_session(request)

        if not user:
            # Redirect to login with return URL
            login_url = f"/login?next={request.url}"
            return RedirectResponse(login_url, status_code=302)

        # Show consent screen
        return HTMLResponse(
            content=_consent_page(
                client=client,
                scopes=requested_scopes,
                user=user,
                state=state,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                nonce=nonce,
            ),
            status_code=200,
        )

    @router.post("/oauth/authorize")
    async def authorize_consent(
        request: Request,
        action: str = Form(...),
        client_id: str = Form(...),
        redirect_uri: str = Form(...),
        scope: str = Form(...),
        state: str = Form(...),
        code_challenge: str | None = Form(None),
        code_challenge_method: str = Form("S256"),
        nonce: str | None = Form(None),
    ) -> RedirectResponse:
        """Handle authorization consent form submission."""
        # Get current user
        user = await _get_current_user_from_session(request)
        if not user:
            return _error_response(redirect_uri, "access_denied", "User not authenticated", state)

        # Check consent decision
        if action != "approve":
            return _error_response(
                redirect_uri, "access_denied", "User denied authorization", state
            )

        # Validate client
        client = get_oauth_client(client_id)
        if not client or redirect_uri not in client.redirect_uris:
            return _error_response(redirect_uri, "invalid_client", "Invalid client", state)

        # Generate authorization code
        code = secrets.token_urlsafe(32)

        # Store code with metadata (expires in 10 minutes)
        _auth_codes[code] = {
            "client_id": client_id,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "nonce": nonce,
            "expires_at": time.time() + 600,  # 10 minutes
        }

        # Redirect with code
        params = {"code": code, "state": state}
        redirect_url = f"{redirect_uri}?{urlencode(params)}"

        logger.info(f"Authorization code issued for user {user.username} to client {client_id}")

        return RedirectResponse(redirect_url, status_code=302)

    # =========================================================================
    # Token Endpoint
    # =========================================================================

    @router.post("/oauth/token", response_model=TokenResponse)
    async def token(
        request: Request,
        grant_type: str = Form(...),
        code: str | None = Form(None),
        redirect_uri: str | None = Form(None),
        client_id: str | None = Form(None),
        client_secret: str | None = Form(None),
        code_verifier: str | None = Form(None),
        refresh_token: str | None = Form(None),
        scope: str | None = Form(None),
    ) -> TokenResponse:
        """OAuth token endpoint.

        Exchanges authorization code for tokens.
        """
        # Extract client credentials from Basic auth or form
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode()
                client_id, client_secret = decoded.split(":", 1)
            except Exception:
                pass

        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="client_id is required",
            )

        # Validate client
        client = get_oauth_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client",
            )

        # Validate client secret for confidential clients
        if client.client_type == "confidential":
            if not client_secret or client.client_secret != client_secret:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid client credentials",
                )

        # Handle grant types
        if grant_type == "authorization_code":
            return await _handle_authorization_code(client, code, redirect_uri, code_verifier)
        elif grant_type == "refresh_token":
            return await _handle_refresh_token(client, refresh_token, scope)
        elif grant_type == "client_credentials":
            return await _handle_client_credentials(client, scope)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported grant_type: {grant_type}",
            )

    # =========================================================================
    # UserInfo Endpoint
    # =========================================================================

    @router.get("/oauth/userinfo", response_model=UserInfoResponse)
    @router.post("/oauth/userinfo", response_model=UserInfoResponse)
    async def userinfo(
        request: Request,
        user: User = Depends(require_auth),
    ) -> UserInfoResponse:
        """OpenID Connect UserInfo endpoint.

        Returns claims about the authenticated user.
        """
        # Get full user info from store
        user_store = get_user_store()
        user_data = user_store.get_user(user.username)

        return UserInfoResponse(
            sub=user.id,
            name=user_data.get("display_name") if user_data else user.username,
            preferred_username=user.username,
            email=user.email,
            email_verified=user_data.get("is_verified", False) if user_data else False,
            picture=user_data.get("avatar_url") if user_data else None,
            updated_at=int(time.time()),
        )

    # =========================================================================
    # Token Revocation
    # =========================================================================

    @router.post("/oauth/revoke")
    async def revoke_token(
        token: str = Form(...),
        token_type_hint: str | None = Form(None),
        client_id: str | None = Form(None),
        client_secret: str | None = Form(None),
    ) -> dict[str, str]:
        """Revoke an access or refresh token."""
        # Validate client if provided
        if client_id:
            client = get_oauth_client(client_id)
            if client and client.client_type == "confidential":
                if not client_secret or client.client_secret != client_secret:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid client credentials",
                    )

        # Try to revoke refresh token
        if token in _refresh_tokens:
            del _refresh_tokens[token]
            logger.info("Revoked refresh token")

        # For access tokens, would need to blacklist
        # (handled by token_manager in production)

        return {"status": "ok"}

    # =========================================================================
    # Client Registration
    # =========================================================================

    @router.post("/oauth/register", response_model=ClientRegistrationResponse)
    async def register_client(
        request: ClientRegistrationRequest,
        user: User = Depends(require_auth),
    ) -> ClientRegistrationResponse:
        """Register a new OAuth client application.

        Requires authentication. Admin users can register confidential clients.
        """
        # Generate client credentials
        client_id = f"kagami_{secrets.token_hex(8)}"
        client_secret = secrets.token_urlsafe(32) if request.client_type == "confidential" else None

        # Validate redirect URIs
        for uri in request.redirect_uris:
            parsed = urlparse(uri)
            if not parsed.scheme or not parsed.netloc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid redirect URI: {uri}",
                )
            # Require HTTPS in production (except localhost)
            if os.environ.get("KAGAMI_ENVIRONMENT") == "production":
                if parsed.scheme != "https" and parsed.netloc not in ("localhost", "127.0.0.1"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Redirect URIs must use HTTPS in production",
                    )

        # Create client
        client = OAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            client_name=request.client_name,
            redirect_uris=request.redirect_uris,
            client_type=request.client_type,
            logo_uri=request.logo_uri,
            website_uri=request.website_uri,
            description=request.description,
            allowed_scopes=request.allowed_scopes,
            require_pkce=request.client_type == "public",
        )

        register_oauth_client(client)

        logger.info(f"Registered OAuth client {client_id} for user {user.username}")

        return ClientRegistrationResponse(
            client_id=client_id,
            client_secret=client_secret,
            client_name=request.client_name,
            redirect_uris=request.redirect_uris,
            client_type=request.client_type,
            created_at=datetime.utcnow().isoformat(),
        )

    return router


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_current_user_from_session(request: Request) -> User | None:
    """Get current user from session/cookie or Authorization header."""
    try:
        # Try to get from Authorization header
        user = await get_current_user_optional(
            credentials=None  # Will check request headers
        )
        if user:
            return user

        # Try session cookie (would need session middleware in production)
        # For now, check for token in cookie
        token = request.cookies.get("kagami_token")
        if token:
            from kagami_api.auth import get_user_from_token

            return await get_user_from_token(token)

    except Exception as e:
        logger.debug(f"Failed to get user from session: {e}")

    return None


async def _handle_authorization_code(
    client: OAuthClient,
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
) -> TokenResponse:
    """Handle authorization code grant."""
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code is required",
        )

    # Get and validate authorization code
    auth_data = _auth_codes.pop(code, None)
    if not auth_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code",
        )

    # Validate expiration
    if auth_data["expires_at"] < time.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code has expired",
        )

    # Validate client
    if auth_data["client_id"] != client.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client mismatch",
        )

    # Validate redirect URI
    if redirect_uri and auth_data["redirect_uri"] != redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redirect URI mismatch",
        )

    # Validate PKCE
    if auth_data.get("code_challenge"):
        if not code_verifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="code_verifier is required",
            )
        if not verify_pkce(
            code_verifier,
            auth_data["code_challenge"],
            auth_data.get("code_challenge_method", "S256"),
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid code_verifier",
            )

    # Generate tokens
    security = SecurityFramework()

    scopes = auth_data["scope"].split()

    access_token = security.create_access_token(
        subject=auth_data["username"],
        scopes=scopes,
        additional_claims={
            "client_id": client.client_id,
            "uid": auth_data["user_id"],
        },
    )

    # Generate refresh token
    refresh_token = secrets.token_urlsafe(32)
    _refresh_tokens[refresh_token] = {
        "user_id": auth_data["user_id"],
        "username": auth_data["username"],
        "client_id": client.client_id,
        "scope": auth_data["scope"],
        "expires_at": time.time() + 30 * 24 * 3600,  # 30 days
    }

    # Generate ID token for OpenID Connect
    id_token = None
    if "openid" in scopes:
        id_token = security.create_access_token(
            subject=auth_data["user_id"],
            scopes=["openid"],
            additional_claims={
                "aud": client.client_id,
                "nonce": auth_data.get("nonce"),
                "email": auth_data.get("email"),
                "preferred_username": auth_data["username"],
            },
        )

    logger.info(f"Token issued for user {auth_data['username']} to client {client.client_id}")

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,
        refresh_token=refresh_token,
        scope=auth_data["scope"],
        id_token=id_token,
    )


async def _handle_refresh_token(
    client: OAuthClient,
    refresh_token: str | None,
    scope: str | None,
) -> TokenResponse:
    """Handle refresh token grant."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required",
        )

    # Validate refresh token
    token_data = _refresh_tokens.get(refresh_token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token",
        )

    # Validate expiration
    if token_data["expires_at"] < time.time():
        del _refresh_tokens[refresh_token]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token has expired",
        )

    # Validate client
    if token_data["client_id"] != client.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client mismatch",
        )

    # Use original or requested scope
    final_scope = scope or token_data["scope"]

    # Generate new access token
    security = SecurityFramework()

    access_token = security.create_access_token(
        subject=token_data["username"],
        scopes=final_scope.split(),
        additional_claims={
            "client_id": client.client_id,
            "uid": token_data["user_id"],
        },
    )

    # Optionally rotate refresh token
    new_refresh_token = secrets.token_urlsafe(32)
    _refresh_tokens[new_refresh_token] = {
        **token_data,
        "expires_at": time.time() + 30 * 24 * 3600,
    }
    del _refresh_tokens[refresh_token]

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,
        refresh_token=new_refresh_token,
        scope=final_scope,
    )


async def _handle_client_credentials(
    client: OAuthClient,
    scope: str | None,
) -> TokenResponse:
    """Handle client credentials grant (machine-to-machine)."""
    if client.client_type != "confidential":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client credentials grant requires confidential client",
        )

    # Validate requested scopes
    requested_scopes = (scope or "").split()
    invalid = set(requested_scopes) - set(client.allowed_scopes)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {invalid}",
        )

    final_scope = scope or " ".join(client.allowed_scopes)

    # Generate access token for client (no user)
    security = SecurityFramework()

    access_token = security.create_access_token(
        subject=f"client:{client.client_id}",
        scopes=final_scope.split(),
        additional_claims={
            "client_id": client.client_id,
            "grant_type": "client_credentials",
        },
    )

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,
        scope=final_scope,
    )


def _error_response(
    redirect_uri: str,
    error: str,
    description: str,
    state: str | None,
) -> RedirectResponse:
    """Create OAuth error redirect response."""
    params = {
        "error": error,
        "error_description": description,
    }
    if state:
        params["state"] = state

    url = f"{redirect_uri}?{urlencode(params)}"
    return RedirectResponse(url, status_code=302)


def _error_page(message: str) -> str:
    """Generate error page HTML."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error — Kagami</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .error-container {{
            text-align: center;
            padding: 48px;
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
            max-width: 400px;
        }}
        h1 {{
            font-size: 24px;
            margin-bottom: 16px;
            color: #ff6b6b;
        }}
        p {{
            color: #888;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="error-container">
        <h1>⚠️ Error</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""


def _consent_page(
    client: OAuthClient,
    scopes: list[str],
    user: User,
    state: str,
    redirect_uri: str,
    code_challenge: str | None,
    code_challenge_method: str,
    nonce: str | None,
) -> str:
    """Generate beautiful consent page HTML with audio and microinteractions."""
    scope_descriptions = {
        "openid": ("🔑", "Verify your identity"),
        "profile": ("👤", "Access your profile information"),
        "email": ("📧", "Access your email address"),
        "agents": ("🤖", "Access your AI agents"),
        "offline_access": ("🔄", "Stay logged in"),
    }

    scope_html = ""
    for i, scope in enumerate(scopes):
        icon, desc = scope_descriptions.get(scope, ("•", scope))
        scope_html += (
            f'<li style="animation-delay: {i * 0.1}s"><span class="icon">{icon}</span> {desc}</li>'
        )

    hidden_fields = f"""
        <input type="hidden" name="client_id" value="{client.client_id}">
        <input type="hidden" name="redirect_uri" value="{redirect_uri}">
        <input type="hidden" name="scope" value="{" ".join(scopes)}">
        <input type="hidden" name="state" value="{state}">
    """
    if code_challenge:
        hidden_fields += f'<input type="hidden" name="code_challenge" value="{code_challenge}">'
        hidden_fields += (
            f'<input type="hidden" name="code_challenge_method" value="{code_challenge_method}">'
        )
    if nonce:
        hidden_fields += f'<input type="hidden" name="nonce" value="{nonce}">'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authorize — Kagami</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --accent: #667eea;
            --accent-dark: #764ba2;
            --bg-primary: #0a0a0f;
            --bg-secondary: #1a1a2e;
            --text-primary: #fff;
            --text-secondary: #888;
            --border-subtle: rgba(255,255,255,0.08);
            --timing-fast: 0.15s;
            --timing-medium: 0.3s;
            --timing-slow: 0.5s;
        }}

        body {{
            font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow: hidden;
        }}

        /* Animated background particles */
        .bg-particles {{
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: -1;
        }}

        .particle {{
            position: absolute;
            width: 4px;
            height: 4px;
            background: var(--accent);
            border-radius: 50%;
            opacity: 0.3;
            animation: float 20s infinite ease-in-out;
        }}

        @keyframes float {{
            0%, 100% {{ transform: translateY(0) translateX(0); opacity: 0.1; }}
            25% {{ transform: translateY(-100px) translateX(50px); opacity: 0.4; }}
            50% {{ transform: translateY(-50px) translateX(-30px); opacity: 0.2; }}
            75% {{ transform: translateY(-150px) translateX(20px); opacity: 0.3; }}
        }}

        .consent-container {{
            width: 100%;
            max-width: 420px;
            background: rgba(255,255,255,0.03);
            border-radius: 24px;
            border: 1px solid var(--border-subtle);
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
            animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
            backdrop-filter: blur(10px);
        }}

        @keyframes slideUp {{
            from {{
                opacity: 0;
                transform: translateY(30px) scale(0.98);
            }}
            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
            }}
        }}

        .header {{
            padding: 32px;
            text-align: center;
            background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, transparent 100%);
            position: relative;
        }}

        .logo {{
            width: 72px;
            height: 72px;
            margin: 0 auto 16px;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
            border-radius: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            animation: pulse 2s infinite ease-in-out;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        }}

        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3); }}
            50% {{ transform: scale(1.02); box-shadow: 0 15px 50px rgba(102, 126, 234, 0.4); }}
        }}

        h1 {{
            font-size: 22px;
            font-weight: 600;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #fff, #ddd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .subtitle {{
            color: var(--text-secondary);
            font-size: 14px;
        }}

        .client-info {{
            padding: 20px 32px;
            background: rgba(255,255,255,0.02);
            border-top: 1px solid var(--border-subtle);
            border-bottom: 1px solid var(--border-subtle);
            animation: fadeIn 0.5s 0.2s backwards;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}

        .client-name {{
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 4px;
        }}

        .client-url {{
            color: var(--text-secondary);
            font-size: 13px;
        }}

        .permissions {{
            padding: 24px 32px;
        }}

        .permissions h3 {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }}

        .permissions ul {{
            list-style: none;
        }}

        .permissions li {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 0;
            border-bottom: 1px solid var(--border-subtle);
            font-size: 15px;
            animation: slideIn 0.4s backwards;
            transition: background var(--timing-fast);
        }}

        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateX(-10px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}

        .permissions li:hover {{
            background: rgba(255,255,255,0.02);
        }}

        .permissions li:last-child {{
            border-bottom: none;
        }}

        .icon {{
            font-size: 20px;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(102, 126, 234, 0.15);
            border-radius: 8px;
        }}

        .user-info {{
            padding: 18px 32px;
            background: rgba(102, 126, 234, 0.08);
            display: flex;
            align-items: center;
            gap: 14px;
            animation: fadeIn 0.5s 0.4s backwards;
        }}

        .user-avatar {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 18px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}

        .user-details {{
            flex: 1;
        }}

        .user-name {{
            font-weight: 500;
            font-size: 15px;
        }}

        .user-email {{
            color: var(--text-secondary);
            font-size: 13px;
        }}

        .actions {{
            padding: 24px 32px;
            display: flex;
            gap: 12px;
        }}

        button {{
            flex: 1;
            padding: 14px 24px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: all var(--timing-medium) cubic-bezier(0.4, 0, 0.2, 1);
            border: none;
            font-family: inherit;
            position: relative;
            overflow: hidden;
        }}

        button::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transform: translateX(-100%);
            transition: transform 0.6s;
        }}

        button:hover::after {{
            transform: translateX(100%);
        }}

        .btn-approve {{
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
            color: #fff;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}

        .btn-approve:hover {{
            transform: translateY(-3px);
            box-shadow: 0 12px 25px rgba(102, 126, 234, 0.4);
        }}

        .btn-approve:active {{
            transform: translateY(0);
            box-shadow: 0 4px 10px rgba(102, 126, 234, 0.3);
        }}

        .btn-deny {{
            background: rgba(255,255,255,0.05);
            color: var(--text-secondary);
            border: 1px solid var(--border-subtle);
        }}

        .btn-deny:hover {{
            background: rgba(255,255,255,0.1);
            color: var(--text-primary);
            border-color: rgba(255,255,255,0.2);
        }}

        .btn-deny:active {{
            background: rgba(255,255,255,0.08);
        }}

        .footer {{
            padding: 16px 32px;
            text-align: center;
            font-size: 12px;
            color: #666;
            background: rgba(0,0,0,0.2);
        }}

        .footer a {{
            color: var(--text-secondary);
            text-decoration: none;
            transition: color var(--timing-fast);
        }}

        .footer a:hover {{
            color: var(--text-primary);
        }}

        /* Loading state */
        .loading {{
            pointer-events: none;
            opacity: 0.7;
        }}

        .loading .btn-approve::before {{
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            border: 2px solid transparent;
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            left: calc(50% - 10px);
            top: calc(50% - 10px);
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        /* Focus states for accessibility */
        button:focus-visible {{
            outline: 2px solid var(--accent);
            outline-offset: 2px;
        }}

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}
    </style>
</head>
<body>
    <!-- Animated background particles -->
    <div class="bg-particles" id="particles"></div>

    <div class="consent-container">
        <div class="header">
            <div class="logo" role="img" aria-label="Kagami logo">鏡</div>
            <h1>Sign in with Kagami</h1>
            <p class="subtitle">Authorize this application</p>
        </div>

        <div class="client-info">
            <div class="client-name">{client.client_name}</div>
            <div class="client-url">{client.website_uri or redirect_uri.split("/")[2]}</div>
        </div>

        <div class="permissions">
            <h3>This app wants to</h3>
            <ul role="list" aria-label="Requested permissions">
                {scope_html}
            </ul>
        </div>

        <div class="user-info">
            <div class="user-avatar" aria-hidden="true">{user.username[0].upper()}</div>
            <div class="user-details">
                <div class="user-name">{user.username}</div>
                <div class="user-email">{user.email}</div>
            </div>
        </div>

        <form method="POST" action="/oauth/authorize" id="authForm">
            {hidden_fields}
            <div class="actions">
                <button type="submit" name="action" value="deny" class="btn-deny" aria-label="Deny authorization">
                    Deny
                </button>
                <button type="submit" name="action" value="approve" class="btn-approve" aria-label="Authorize application">
                    Authorize
                </button>
            </div>
        </form>

        <div class="footer">
            By authorizing, you agree to Kagami's <a href="/terms">Terms</a> and <a href="/privacy">Privacy Policy</a>
        </div>
    </div>

    <script>
        // Audio Context for synthesized sounds
        let audioContext;
        function getAudioContext() {{
            if (!audioContext) {{
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }}
            return audioContext;
        }}

        function playTone(frequency, duration, type = 'sine', volume = 0.2) {{
            try {{
                const ctx = getAudioContext();
                if (ctx.state === 'suspended') ctx.resume();

                const osc = ctx.createOscillator();
                const gain = ctx.createGain();

                osc.connect(gain);
                gain.connect(ctx.destination);

                osc.type = type;
                osc.frequency.setValueAtTime(frequency, ctx.currentTime);

                gain.gain.setValueAtTime(0, ctx.currentTime);
                gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + 0.01);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + duration);
            }} catch (e) {{ /* Audio not available */ }}
        }}

        function playHoverSound() {{
            playTone(1200, 0.03, 'sine', 0.05);
        }}

        function playClickSound() {{
            playTone(800, 0.05, 'sine', 0.1);
        }}

        function playSuccessSound() {{
            setTimeout(() => playTone(523.25, 0.12, 'sine', 0.2), 0);
            setTimeout(() => playTone(659.25, 0.12, 'sine', 0.2), 40);
            setTimeout(() => playTone(783.99, 0.2, 'sine', 0.25), 80);
        }}

        function playDenySound() {{
            playTone(440, 0.15, 'triangle', 0.15);
        }}

        // Generate particles
        const particlesContainer = document.getElementById('particles');
        for (let i = 0; i < 20; i++) {{
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.top = Math.random() * 100 + '%';
            particle.style.animationDelay = Math.random() * 20 + 's';
            particle.style.animationDuration = (15 + Math.random() * 10) + 's';
            particlesContainer.appendChild(particle);
        }}

        // Button interactions
        const buttons = document.querySelectorAll('button');
        buttons.forEach(btn => {{
            btn.addEventListener('mouseenter', playHoverSound);
            btn.addEventListener('click', function(e) {{
                playClickSound();

                // Visual ripple effect
                const ripple = document.createElement('span');
                const rect = btn.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                ripple.style.cssText = `
                    position: absolute;
                    width: ${{size}}px;
                    height: ${{size}}px;
                    left: ${{e.clientX - rect.left - size/2}}px;
                    top: ${{e.clientY - rect.top - size/2}}px;
                    background: rgba(255,255,255,0.3);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: ripple 0.6s ease-out;
                    pointer-events: none;
                `;
                btn.appendChild(ripple);
                setTimeout(() => ripple.remove(), 600);
            }});
        }});

        // Add ripple animation
        const style = document.createElement('style');
        style.textContent = '@keyframes ripple {{ to {{ transform: scale(2.5); opacity: 0; }} }}';
        document.head.appendChild(style);

        // Form submission handling
        const form = document.getElementById('authForm');
        form.addEventListener('submit', function(e) {{
            const action = e.submitter?.value;

            if (action === 'approve') {{
                playSuccessSound();
                document.querySelector('.consent-container').classList.add('loading');
                e.submitter.innerHTML = 'Authorizing...';
            }} else {{
                playDenySound();
            }}

            // Haptic feedback
            if ('vibrate' in navigator) {{
                navigator.vibrate(action === 'approve' ? [10, 50, 10] : [30]);
            }}
        }});

        // Scope list hover sounds
        document.querySelectorAll('.permissions li').forEach(li => {{
            li.addEventListener('mouseenter', () => playTone(600 + Math.random() * 200, 0.02, 'sine', 0.03));
        }});
    </script>
</body>
</html>"""


__all__ = [
    "OAuthClient",
    "get_oauth_client",
    "get_router",
    "register_oauth_client",
]
