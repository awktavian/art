"""GitHub App Authentication — JWT and Installation Tokens.

Implements GitHub App authentication for enterprise-grade access:
- JWT generation using RS256
- Installation access token exchange
- Automatic token refresh
- Per-repository permission scoping

GitHub Apps are preferred over OAuth Apps for enterprise because:
- More granular permissions
- Can act as the app itself (not as a user)
- Better audit trail
- No user token needed for automation

Example:
    >>> app = GitHubAppAuth(config)
    >>>
    >>> # Get installation token for a repo
    >>> token = await app.get_installation_token(
    ...     installation_id=12345,
    ...     repositories=["my-repo"],
    ... )
    >>>
    >>> # Use token for API calls
    >>> async with app.get_client() as client:
    ...     response = await client.get("/repos/owner/repo")

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Enterprise IS security.

Created: January 2026
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# JWT Generation
# =============================================================================


def generate_jwt(
    app_id: int,
    private_key: str,
    expiration_minutes: int = 10,
) -> str:
    """Generate JWT for GitHub App authentication.

    GitHub Apps authenticate using JWTs signed with their private key.
    JWTs are valid for up to 10 minutes.

    Args:
        app_id: GitHub App ID.
        private_key: RSA private key in PEM format.
        expiration_minutes: JWT expiration time (max 10).

    Returns:
        Signed JWT string.

    Raises:
        ImportError: If PyJWT is not installed.
        ValueError: If private key is invalid.

    Example:
        >>> jwt = generate_jwt(12345, private_key_pem)
        >>> headers = {"Authorization": f"Bearer {jwt}"}
    """
    try:
        import jwt
    except ImportError as e:
        raise ImportError(
            "PyJWT is required for GitHub App authentication. "
            "Install with: pip install PyJWT[crypto]"
        ) from e

    # Cap expiration at 10 minutes (GitHub limit)
    expiration_minutes = min(expiration_minutes, 10)

    now = int(time.time())

    payload = {
        # Issued at time (60 seconds in the past for clock skew)
        "iat": now - 60,
        # Expiration time
        "exp": now + (expiration_minutes * 60),
        # GitHub App's identifier
        "iss": str(app_id),
    }

    try:
        return jwt.encode(payload, private_key, algorithm="RS256")
    except Exception as e:
        raise ValueError(f"Failed to generate JWT: {e}") from e


# =============================================================================
# Installation Token
# =============================================================================


@dataclass
class InstallationToken:
    """GitHub App installation access token.

    Installation tokens provide access to resources the app is installed on.
    Tokens expire after 1 hour and should be refreshed before expiry.

    Attributes:
        token: The access token.
        expires_at: When the token expires.
        permissions: Granted permissions.
        repositories: Accessible repository names.
        repository_selection: "all" or "selected".
    """

    token: str
    expires_at: datetime
    permissions: dict[str, str] = field(default_factory=dict)
    repositories: list[str] = field(default_factory=list)
    repository_selection: str = "all"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 5 minute buffer)."""
        return datetime.utcnow() > (self.expires_at - timedelta(minutes=5))

    @property
    def expires_in_seconds(self) -> int:
        """Seconds until token expires."""
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> InstallationToken:
        """Create from GitHub API response.

        Args:
            data: Response from POST /app/installations/{id}/access_tokens.

        Returns:
            InstallationToken instance.
        """
        # Parse expiration time
        expires_str = data.get("expires_at", "")
        if expires_str:
            # GitHub returns ISO format: 2023-10-27T10:00:00Z
            expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            # Convert to UTC naive for comparison
            expires_at = expires_at.replace(tzinfo=None)
        else:
            # Default to 1 hour from now
            expires_at = datetime.utcnow() + timedelta(hours=1)

        # Extract repository names
        repositories = []
        for repo in data.get("repositories", []):
            if isinstance(repo, dict):
                repositories.append(repo.get("full_name", repo.get("name", "")))
            elif isinstance(repo, str):
                repositories.append(repo)

        return cls(
            token=data.get("token", ""),
            expires_at=expires_at,
            permissions=data.get("permissions", {}),
            repositories=repositories,
            repository_selection=data.get("repository_selection", "all"),
        )


# =============================================================================
# GitHub App Auth
# =============================================================================


class GitHubAppAuth:
    """GitHub App authentication manager.

    Handles JWT generation and installation token exchange for GitHub Apps.
    Automatically refreshes tokens when they expire.

    Example:
        >>> from kagami.core.federation.github_config import GitHubConfig
        >>>
        >>> config = GitHubConfig(
        ...     app_id=12345,
        ...     private_key=open("private-key.pem").read(),
        ... )
        >>>
        >>> app = GitHubAppAuth(config)
        >>>
        >>> # Get installation token
        >>> token = await app.get_installation_token(installation_id=67890)
        >>>
        >>> # Use in API calls
        >>> headers = {"Authorization": f"Bearer {token.token}"}

    Attributes:
        config: GitHub configuration.
        _jwt_cache: Cached JWT (regenerated every 9 minutes).
        _token_cache: Cached installation tokens by installation_id.
    """

    def __init__(self, config: Any = None) -> None:
        """Initialize GitHub App auth.

        Args:
            config: GitHubConfig instance. If None, loads from environment.
        """
        if config is None:
            from kagami.core.federation.github_config import GitHubConfig

            config = GitHubConfig()

        self._config = config
        self._jwt: str = ""
        self._jwt_expires: float = 0
        self._token_cache: dict[int, InstallationToken] = {}
        self._http: httpx.AsyncClient | None = None

    @property
    def app_id(self) -> int:
        """Get GitHub App ID."""
        return self._config.app_id

    @property
    def private_key(self) -> str:
        """Get GitHub App private key."""
        return self._config.private_key

    @property
    def api_url(self) -> str:
        """Get API base URL."""
        return self._config.api_url

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=30.0,
                verify=self._config.get_ssl_context(),
            )
        return self._http

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None

    def _get_jwt(self) -> str:
        """Get or generate JWT.

        JWTs are cached for 9 minutes (1 minute before 10-minute expiry).

        Returns:
            JWT string.
        """
        now = time.time()

        # Regenerate if expired or about to expire
        if not self._jwt or now >= self._jwt_expires:
            self._jwt = generate_jwt(self.app_id, self.private_key)
            self._jwt_expires = now + (9 * 60)  # 9 minutes
            logger.debug("Generated new JWT for GitHub App")

        return self._jwt

    async def get_app_info(self) -> dict[str, Any]:
        """Get information about the GitHub App.

        Returns:
            App info from GET /app endpoint.
        """
        client = await self._get_client()
        jwt = self._get_jwt()

        response = await client.get(
            f"{self.api_url}/app",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        return response.json()

    async def list_installations(self) -> list[dict[str, Any]]:
        """List all installations of this GitHub App.

        Returns:
            List of installation objects.
        """
        client = await self._get_client()
        jwt = self._get_jwt()

        response = await client.get(
            f"{self.api_url}/app/installations",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_installation(self, installation_id: int) -> dict[str, Any]:
        """Get information about a specific installation.

        Args:
            installation_id: Installation ID.

        Returns:
            Installation object.
        """
        client = await self._get_client()
        jwt = self._get_jwt()

        response = await client.get(
            f"{self.api_url}/app/installations/{installation_id}",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_installation_token(
        self,
        installation_id: int | None = None,
        repositories: list[str] | None = None,
        repository_ids: list[int] | None = None,
        permissions: dict[str, str] | None = None,
    ) -> InstallationToken:
        """Get or refresh installation access token.

        Tokens are cached and automatically refreshed when expired.

        Args:
            installation_id: Installation ID (uses config if not provided).
            repositories: Limit token to specific repos by name.
            repository_ids: Limit token to specific repos by ID.
            permissions: Override default permissions.

        Returns:
            InstallationToken with access token.

        Example:
            >>> # Full access
            >>> token = await app.get_installation_token(12345)
            >>>
            >>> # Limited to specific repos
            >>> token = await app.get_installation_token(
            ...     12345,
            ...     repositories=["owner/repo1", "owner/repo2"],
            ... )
            >>>
            >>> # Custom permissions
            >>> token = await app.get_installation_token(
            ...     12345,
            ...     permissions={"contents": "read", "issues": "write"},
            ... )
        """
        # Use config installation_id if not provided
        if installation_id is None:
            installation_id = self._config.installation_id

        if not installation_id:
            raise ValueError(
                "installation_id required. Set via parameter or GITHUB_INSTALLATION_ID env."
            )

        # Check cache (only if no custom scoping)
        cache_key = installation_id
        if not repositories and not repository_ids and not permissions:
            cached = self._token_cache.get(cache_key)
            if cached and not cached.is_expired:
                return cached

        # Request new token
        client = await self._get_client()
        jwt = self._get_jwt()

        payload: dict[str, Any] = {}
        if repositories:
            payload["repositories"] = repositories
        if repository_ids:
            payload["repository_ids"] = repository_ids
        if permissions:
            payload["permissions"] = permissions

        response = await client.post(
            f"{self.api_url}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
            },
            json=payload if payload else None,
        )
        response.raise_for_status()

        token = InstallationToken.from_response(response.json())

        # Cache token (only if no custom scoping)
        if not repositories and not repository_ids and not permissions:
            self._token_cache[cache_key] = token

        logger.debug(f"Got installation token (expires in {token.expires_in_seconds}s)")

        return token

    async def get_installation_for_repo(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any] | None:
        """Find installation ID for a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Installation object or None if not installed.
        """
        client = await self._get_client()
        jwt = self._get_jwt()

        try:
            response = await client.get(
                f"{self.api_url}/repos/{owner}/{repo}/installation",
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )

            if response.status_code == 200:
                return response.json()

            return None
        except Exception:
            return None

    async def get_authenticated_client(
        self,
        installation_id: int | None = None,
        **token_kwargs: Any,
    ) -> httpx.AsyncClient:
        """Get an HTTP client authenticated with installation token.

        Args:
            installation_id: Installation ID.
            **token_kwargs: Arguments for get_installation_token.

        Returns:
            Authenticated httpx.AsyncClient.

        Example:
            >>> async with await app.get_authenticated_client(12345) as client:
            ...     response = await client.get(f"{api}/repos/owner/repo")
        """
        token = await self.get_installation_token(installation_id, **token_kwargs)

        return httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token.token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30.0,
            verify=self._config.get_ssl_context(),
        )


# =============================================================================
# Factory Functions
# =============================================================================


_app_auth: GitHubAppAuth | None = None


async def get_github_app_auth() -> GitHubAppAuth:
    """Get singleton GitHub App auth instance.

    Returns:
        GitHubAppAuth instance.
    """
    global _app_auth

    if _app_auth is None:
        from kagami.core.federation.github_config import GitHubConfig

        config = GitHubConfig()
        _app_auth = GitHubAppAuth(config)

    return _app_auth


__all__ = [
    "GitHubAppAuth",
    "InstallationToken",
    "generate_jwt",
    "get_github_app_auth",
]
