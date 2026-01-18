"""GitHub OAuth API Routes — Token exchange and instance creation.

Handles the server-side OAuth flow for GitHub Pages federation.
Client-side code redirects to GitHub, which redirects back with a code.
We exchange that code for an access token securely on the server.

Supports:
- GitHub.com (Free/Pro/Team)
- GitHub Enterprise Cloud (GHEC)
- GitHub Enterprise Server (GHES)
- GitHub Apps (JWT + installation tokens)

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Federation should be frictionless.

Created: January 2026
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["GitHub OAuth"])


# =============================================================================
# Models
# =============================================================================


class EnterpriseDetectRequest(BaseModel):
    """Request to detect enterprise type from hostname."""

    hostname: str = Field(..., description="GitHub hostname (e.g., github.mycompany.com)")


class EnterpriseDetectResponse(BaseModel):
    """Response with detected enterprise configuration."""

    hostname: str
    enterprise_type: str | None = Field(
        None, description="github.com, enterprise_cloud, or enterprise_server"
    )
    api_url: str
    oauth_authorize_url: str
    pages_domain: str
    server_version: str | None = None
    is_enterprise: bool


class TokenExchangeRequest(BaseModel):
    """Request to exchange OAuth code for token."""

    code: str
    redirect_uri: str
    hostname: str = Field("github.com", description="GitHub hostname for enterprise support")


class TokenExchangeResponse(BaseModel):
    """Response with access token."""

    access_token: str
    token_type: str = "bearer"
    scope: str


class CreateInstanceRequest(BaseModel):
    """Request to create a GitHub Pages instance."""

    access_token: str
    repo_name: str = "kagami"
    hostname: str = Field("github.com", description="GitHub hostname for enterprise support")


class InstanceResponse(BaseModel):
    """Response with instance details."""

    success: bool
    url: str | None = None
    owner: str | None = None
    error: str | None = None


class UserResponse(BaseModel):
    """GitHub user profile."""

    id: int
    login: str
    name: str | None
    email: str | None
    avatar_url: str
    pages_domain: str
    instance_url: str


class GitHubAppCallbackRequest(BaseModel):
    """Request for GitHub App installation callback."""

    installation_id: int
    setup_action: str = "install"  # install, update, or suspend
    hostname: str = Field("github.com", description="GitHub hostname for enterprise support")


class GitHubAppCallbackResponse(BaseModel):
    """Response from GitHub App installation callback."""

    success: bool
    installation_id: int | None = None
    organization: str | None = None
    repositories: list[str] = []
    error: str | None = None


class SSOInitiateRequest(BaseModel):
    """Request to initiate SSO flow."""

    organization: str
    return_to: str = ""
    hostname: str = Field("github.com", description="GitHub hostname for enterprise support")


class SSOInitiateResponse(BaseModel):
    """Response with SSO initiation URL."""

    sso_url: str
    organization: str
    sso_required: bool


# =============================================================================
# Routes
# =============================================================================


@router.post("/enterprise/detect", response_model=EnterpriseDetectResponse)
async def detect_enterprise(request: EnterpriseDetectRequest) -> EnterpriseDetectResponse:
    """Detect GitHub Enterprise type from hostname.

    Probes the hostname to determine if it's:
    - github.com (standard)
    - GitHub Enterprise Cloud (GHEC)
    - GitHub Enterprise Server (GHES)

    Args:
        request: Enterprise detection request with hostname.

    Returns:
        Detected enterprise configuration.
    """
    try:
        from kagami.core.federation import detect_github_config

        config = await detect_github_config(request.hostname)

        enterprise_type = None
        if config.enterprise_type:
            enterprise_type = config.enterprise_type.value

        return EnterpriseDetectResponse(
            hostname=config.hostname,
            enterprise_type=enterprise_type,
            api_url=config.api_url,
            oauth_authorize_url=config.oauth_authorize_url,
            pages_domain=config.pages_domain,
            server_version=config._server_version or None,
            is_enterprise=not config.is_github_com,
        )

    except Exception as e:
        logger.error(f"Enterprise detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/token", response_model=TokenExchangeResponse)
async def exchange_token(request: TokenExchangeRequest) -> TokenExchangeResponse:
    """Exchange OAuth authorization code for access token.

    This endpoint securely exchanges the code for a token server-side,
    keeping the client_secret private.

    Supports GitHub.com and Enterprise (GHEC/GHES).

    Args:
        request: Token exchange request with code, redirect_uri, and hostname.

    Returns:
        Access token response.

    Raises:
        HTTPException: If exchange fails.
    """
    try:
        from kagami.core.federation import (
            GitHubConfig,
            GitHubOAuthClient,
            SSORequiredError,
        )

        # Create config for enterprise support
        config = GitHubConfig(hostname=request.hostname)
        client = GitHubOAuthClient(config=config)

        try:
            token = await client.exchange_code(request.code, request.redirect_uri)

            return TokenExchangeResponse(
                access_token=token,
                token_type="bearer",
                scope="",  # Scope not returned by GitHub
            )

        except SSORequiredError as e:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "sso_required",
                    "message": e.message,
                    "organization": e.organization,
                    "sso_url": e.sso_url,
                },
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/user", response_model=UserResponse)
async def get_user(
    request: Request,
    hostname: str = "github.com",
) -> UserResponse:
    """Get GitHub user profile from access token.

    Requires Authorization header with Bearer token.
    Supports GitHub.com and Enterprise (GHEC/GHES).

    Args:
        request: HTTP request with Authorization header.
        hostname: GitHub hostname for enterprise support.

    Returns:
        User profile with Pages URL.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ", 1)[1]

    try:
        from kagami.core.federation import GitHubConfig, GitHubOAuthClient

        config = GitHubConfig(hostname=hostname)
        client = GitHubOAuthClient(config=config)
        user = await client.get_user(token)

        return UserResponse(
            id=user.id,
            login=user.login,
            name=user.name,
            email=user.email,
            avatar_url=user.avatar_url,
            pages_domain=user.get_pages_domain(config),
            instance_url=user.get_instance_url(config),
        )

    except Exception as e:
        logger.error(f"Get user failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/instance", response_model=InstanceResponse)
async def create_instance(request: CreateInstanceRequest) -> InstanceResponse:
    """Create a new Kagami instance on GitHub Pages.

    Creates the repository, enables Pages, and uploads initial files.
    Supports GitHub.com and Enterprise (GHEC/GHES).

    Args:
        request: Instance creation request.

    Returns:
        Instance details with URL.
    """
    try:
        from kagami.core.federation import GitHubConfig, GitHubPagesManager

        config = GitHubConfig(hostname=request.hostname)
        manager = GitHubPagesManager(request.access_token, config=config)
        instance = await manager.create_instance(request.repo_name)

        return InstanceResponse(
            success=True,
            url=instance.url,
            owner=instance.owner,
        )

    except Exception as e:
        logger.error(f"Instance creation failed: {e}")
        return InstanceResponse(
            success=False,
            error=str(e),
        )


@router.get("/discover/{username}", response_model=InstanceResponse)
async def discover_instance(username: str) -> InstanceResponse:
    """Discover another user's Kagami instance.

    Args:
        username: GitHub username.

    Returns:
        Instance details if found.
    """
    try:
        from kagami.core.federation import discover_github_instance

        instance = await discover_github_instance(username)

        if instance:
            return InstanceResponse(
                success=True,
                url=instance.url,
                owner=instance.owner,
            )
        else:
            return InstanceResponse(
                success=False,
                error=f"No Kagami instance found for {username}",
            )

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return InstanceResponse(
            success=False,
            error=str(e),
        )


@router.get("/config")
async def get_config(hostname: str = "github.com") -> dict[str, Any]:
    """Get GitHub OAuth configuration for frontend.

    Returns client_id (safe to expose) but not client_secret.
    Supports GitHub.com and Enterprise (GHEC/GHES).

    Args:
        hostname: GitHub hostname for enterprise support.

    Returns:
        OAuth configuration.
    """
    from kagami.core.federation import GitHubConfig

    config = GitHubConfig(hostname=hostname)

    return {
        "client_id": config.client_id,
        "scopes": ["public_repo", "user:email"],
        "authorize_url": config.oauth_authorize_url,
        "api_url": config.api_url,
        "pages_domain": config.pages_domain,
        "hostname": config.hostname,
        "is_enterprise": not config.is_github_com,
        "configured": bool(config.client_id),
    }


@router.post("/app/callback", response_model=GitHubAppCallbackResponse)
async def github_app_callback(request: GitHubAppCallbackRequest) -> GitHubAppCallbackResponse:
    """Handle GitHub App installation callback.

    Called after a user installs the GitHub App on their account/org.
    Retrieves installation details and creates installation token.

    Args:
        request: Installation callback data.

    Returns:
        Installation details.
    """
    try:
        from kagami.core.federation import GitHubAppAuth, GitHubConfig

        config = GitHubConfig(hostname=request.hostname)

        if not config.has_app_credentials:
            raise HTTPException(
                status_code=500,
                detail="GitHub App not configured. Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY.",
            )

        app_auth = GitHubAppAuth(config)

        # Get installation details
        installation = await app_auth.get_installation(request.installation_id)

        # Get repositories accessible to this installation (validates installation)
        _ = await app_auth.get_installation_token(request.installation_id)

        return GitHubAppCallbackResponse(
            success=True,
            installation_id=request.installation_id,
            organization=installation.get("account", {}).get("login"),
            repositories=[repo["full_name"] for repo in installation.get("repositories", [])],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub App callback failed: {e}")
        return GitHubAppCallbackResponse(
            success=False,
            error=str(e),
        )


@router.post("/sso/initiate", response_model=SSOInitiateResponse)
async def initiate_sso(request: SSOInitiateRequest) -> SSOInitiateResponse:
    """Initiate SSO flow for an organization.

    Checks if SSO is required and returns the SSO URL.

    Args:
        request: SSO initiation request.

    Returns:
        SSO URL if required.
    """
    try:
        from kagami.core.federation import GitHubConfig
        from kagami.core.federation.sso import SSOManager

        config = GitHubConfig(hostname=request.hostname)
        sso = SSOManager(config)

        # Check if SSO is required
        is_required = await sso.is_sso_required(request.organization)

        # Get SSO URL
        sso_url = sso.get_sso_initiate_url(
            request.organization,
            return_to=request.return_to,
        )

        return SSOInitiateResponse(
            sso_url=sso_url,
            organization=request.organization,
            sso_required=is_required,
        )

    except Exception as e:
        logger.error(f"SSO initiate failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/identity/link")
async def link_github_identity(
    request: Request,
    hostname: str = "github.com",
) -> dict[str, Any]:
    """Link GitHub identity to current Kagami user.

    Requires Authorization header with Kagami JWT and GitHub token.

    Args:
        request: HTTP request with authorization headers.
        hostname: GitHub hostname for enterprise support.

    Returns:
        Linked identity details.
    """
    # Get Kagami user from JWT (X-Kagami-Auth header)
    kagami_auth = request.headers.get("X-Kagami-Auth")
    if not kagami_auth:
        raise HTTPException(status_code=401, detail="Missing X-Kagami-Auth header")

    # Get GitHub token (Authorization header)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing GitHub Authorization header")

    github_token = auth_header.split(" ", 1)[1]

    try:
        # Decode Kagami JWT to get user_id
        # For now, trust the header value as user_id
        user_id = kagami_auth

        # Get GitHub user
        from kagami.core.federation import GitHubConfig, GitHubOAuthClient

        config = GitHubConfig(hostname=hostname)
        client = GitHubOAuthClient(config=config)
        github_user = await client.get_user(github_token)

        # Link identity
        from kagami.core.identity import get_unified_identity_service

        service = await get_unified_identity_service()
        link = await service.link_github_identity(
            user_id=user_id,
            github_user=github_user,
            enterprise_host=hostname if not config.is_github_com else None,
        )

        return {
            "success": True,
            "user_id": link.user_id,
            "github_id": link.github_id,
            "github_username": link.github_username,
            "enterprise_host": link.github_enterprise_host,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Identity link failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


__all__ = ["router"]
