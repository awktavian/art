"""Direct Figma API client with full scope access.

Uses custom OAuth app "Kagami" (Client ID: GFajgnWRQzodyGusD376l7)
with 14 scopes enabled. Tokens stored in macOS Keychain.

Callback URLs:
    - https://awkronos.github.io/oauth/figma/
    - https://awktavian.github.io/oauth/figma/

Available Scopes (14):
    - current_user:read - User info
    - file_content:read - Read file contents
    - file_metadata:read - Read file metadata
    - file_versions:read - Read version history
    - file_comments:read/write - Read/write comments
    - file_dev_resources:read/write - Dev resources
    - library_assets:read - Library components
    - library_content:read - Library content
    - team_library_content:read - Team library
    - projects:read - Read projects
    - webhooks:read/write - Manage webhooks

NOTE: file_variables:read/write requires special Figma approval.

Usage:
    >>> client = await get_figma_client()
    >>> user = await client.get_current_user()
    >>> file = await client.get_file("27pdTgOq30LHZuaeVYtkEN")
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class FigmaCredentials:
    """Figma OAuth credentials.

    Attributes:
        client_id: OAuth app client ID.
        client_secret: OAuth app client secret.
        access_token: Current access token (if authenticated).
        refresh_token: Refresh token for token renewal.
    """

    client_id: str
    client_secret: str
    access_token: str | None = None
    refresh_token: str | None = None


def get_from_keychain(key: str) -> str | None:
    """Get a secret from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "kagami", "-s", key, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Keychain access failed for {key}: {e}")
    return None


def set_in_keychain(key: str, value: str) -> bool:
    """Store a secret in macOS Keychain."""
    try:
        # Try to update existing
        subprocess.run(
            ["security", "add-generic-password", "-a", "kagami", "-s", key, "-w", value, "-U"],
            capture_output=True,
        )
        return True
    except Exception as e:
        logger.error(f"Keychain store failed for {key}: {e}")
        return False


class FigmaDirectClient:
    """Direct Figma API client with full scope access.

    This client bypasses Composio's scope limitations by using
    OAuth app credentials directly. Supports all Figma API scopes
    including file_variables:read.

    Example:
        >>> client = FigmaDirectClient()
        >>> await client.initialize()
        >>> variables = await client.get_local_variables("27pdTgOq30LHZuaeVYtkEN")
    """

    BASE_URL = "https://api.figma.com/v1"
    OAUTH_URL = "https://www.figma.com/oauth"

    # All available Figma OAuth scopes (14 scopes enabled for Kagami app)
    # NOTE: file_variables:read/write requires special Figma approval
    ALL_SCOPES = [
        "current_user:read",
        "file_comments:read",
        "file_comments:write",
        "file_content:read",
        "file_metadata:read",
        "file_versions:read",
        "library_assets:read",
        "library_content:read",
        "team_library_content:read",
        "file_dev_resources:read",
        "file_dev_resources:write",
        "projects:read",
        "webhooks:read",
        "webhooks:write",
    ]

    def __init__(self, credentials: FigmaCredentials | None = None) -> None:
        """Initialize the Figma client.

        Args:
            credentials: Optional pre-configured credentials.
                If not provided, loads from keychain/env.
        """
        self._credentials = credentials
        self._session: aiohttp.ClientSession | None = None
        self._initialized = False

    def _load_credentials(self) -> FigmaCredentials:
        """Load credentials from keychain or environment."""
        # Try keychain first
        client_id = get_from_keychain("figma_client_id")
        client_secret = get_from_keychain("figma_client_secret")
        access_token = get_from_keychain("figma_access_token")
        refresh_token = get_from_keychain("figma_refresh_token")

        # Fall back to environment
        if not client_id:
            client_id = os.environ.get("FIGMA_CLIENT_ID", "")
        if not client_secret:
            client_secret = os.environ.get("FIGMA_CLIENT_SECRET", "")
        if not access_token:
            access_token = os.environ.get("FIGMA_ACCESS_TOKEN")

        return FigmaCredentials(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def initialize(self) -> None:
        """Initialize the client and session."""
        if self._initialized:
            return

        if not self._credentials:
            self._credentials = self._load_credentials()

        self._session = aiohttp.ClientSession()
        self._initialized = True

        logger.info("FigmaDirectClient initialized")

    async def close(self) -> None:
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False

    def get_oauth_url(self, redirect_uri: str = "https://awkronos.github.io/oauth/figma/") -> str:
        """Get the OAuth authorization URL.

        Args:
            redirect_uri: URI to redirect after authorization.

        Returns:
            Full OAuth authorization URL.
        """
        params = {
            "client_id": self._credentials.client_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(self.ALL_SCOPES),
            "state": "kagami_auth",
            "response_type": "code",
        }
        return f"{self.OAUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str = "https://awkronos.github.io/oauth/figma/"
    ) -> bool:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback.
            redirect_uri: Same redirect URI used in authorization.

        Returns:
            True if successful.
        """
        if not self._session:
            await self.initialize()

        async with self._session.post(
            f"{self.OAUTH_URL}/token",
            data={
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                self._credentials.access_token = data.get("access_token")
                self._credentials.refresh_token = data.get("refresh_token")

                # Store in keychain
                if self._credentials.access_token:
                    set_in_keychain("figma_access_token", self._credentials.access_token)
                if self._credentials.refresh_token:
                    set_in_keychain("figma_refresh_token", self._credentials.refresh_token)

                logger.info("Figma OAuth tokens stored")
                return True
            else:
                error = await resp.text()
                logger.error(f"OAuth token exchange failed: {error}")
                return False

    async def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        if not self._credentials.refresh_token:
            logger.error("No refresh token available")
            return False

        if not self._session:
            await self.initialize()

        async with self._session.post(
            f"{self.OAUTH_URL}/refresh",
            data={
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "refresh_token": self._credentials.refresh_token,
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                self._credentials.access_token = data.get("access_token")

                if self._credentials.access_token:
                    set_in_keychain("figma_access_token", self._credentials.access_token)

                logger.info("Figma access token refreshed")
                return True
            else:
                logger.error("Token refresh failed")
                return False

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated API request.

        Args:
            method: HTTP method.
            endpoint: API endpoint (without base URL).
            **kwargs: Additional request arguments.

        Returns:
            JSON response data.
        """
        if not self._session:
            await self.initialize()

        if not self._credentials.access_token:
            raise ValueError("No access token. Complete OAuth flow first.")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._credentials.access_token}"

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        async with self._session.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status == 401:
                # Try refresh
                if await self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self._credentials.access_token}"
                    async with self._session.request(
                        method, url, headers=headers, **kwargs
                    ) as retry_resp:
                        return await retry_resp.json()
                raise ValueError("Authentication failed")

            return await resp.json()

    async def get_current_user(self) -> dict:
        """Get the current authenticated user."""
        return await self._request("GET", "/me")

    async def get_file(self, file_key: str, **params) -> dict:
        """Get a Figma file.

        Args:
            file_key: The file key.
            **params: Additional query parameters.
        """
        return await self._request("GET", f"/files/{file_key}", params=params)

    async def get_local_variables(self, file_key: str) -> dict:
        """Get local variables from a file.

        This requires the file_variables:read scope which is
        not available through Composio.

        Args:
            file_key: The file key.

        Returns:
            Variables data including collections and variables.
        """
        return await self._request("GET", f"/files/{file_key}/variables/local")

    async def get_published_variables(self, file_key: str) -> dict:
        """Get published variables from a file.

        Args:
            file_key: The file key.
        """
        return await self._request("GET", f"/files/{file_key}/variables/published")

    async def create_variables(self, file_key: str, variables: list[dict]) -> dict:
        """Create or update variables in a file.

        Requires file_variables:write scope.

        Args:
            file_key: The file key.
            variables: List of variable definitions.
        """
        return await self._request(
            "POST",
            f"/files/{file_key}/variables",
            json={"variables": variables},
        )

    async def get_file_components(self, file_key: str) -> dict:
        """Get components from a file."""
        return await self._request("GET", f"/files/{file_key}/components")

    async def get_file_styles(self, file_key: str) -> dict:
        """Get styles from a file."""
        return await self._request("GET", f"/files/{file_key}/styles")

    async def get_team_styles(self, team_id: str) -> dict:
        """Get team styles."""
        return await self._request("GET", f"/teams/{team_id}/styles")

    async def add_comment(self, file_key: str, message: str, **kwargs) -> dict:
        """Add a comment to a file.

        Args:
            file_key: The file key.
            message: Comment message.
            **kwargs: Additional comment parameters (x, y, etc).
        """
        return await self._request(
            "POST",
            f"/files/{file_key}/comments",
            json={"message": message, **kwargs},
        )

    async def get_comments(self, file_key: str) -> dict:
        """Get comments from a file."""
        return await self._request("GET", f"/files/{file_key}/comments")

    async def get_file_versions(self, file_key: str) -> dict:
        """Get version history of a file."""
        return await self._request("GET", f"/files/{file_key}/versions")

    async def get_team_projects(self, team_id: str) -> dict:
        """Get projects in a team."""
        return await self._request("GET", f"/teams/{team_id}/projects")

    async def get_project_files(self, project_id: str) -> dict:
        """Get files in a project."""
        return await self._request("GET", f"/projects/{project_id}/files")

    async def get_file_images(self, file_key: str, ids: list[str], **params) -> dict:
        """Export images from a file.

        Args:
            file_key: The file key.
            ids: List of node IDs to export.
            **params: Additional params (format, scale, etc).
        """
        params["ids"] = ",".join(ids)
        return await self._request("GET", f"/images/{file_key}", params=params)

    async def create_webhook(self, team_id: str, event_type: str, endpoint: str, **kwargs) -> dict:
        """Create a webhook for team events.

        Args:
            team_id: The team ID.
            event_type: Event type (FILE_UPDATE, FILE_DELETE, etc).
            endpoint: Callback URL.
        """
        return await self._request(
            "POST",
            "/webhooks",
            json={
                "team_id": team_id,
                "event_type": event_type,
                "endpoint": endpoint,
                **kwargs,
            },
        )

    async def get_webhooks(self, team_id: str) -> dict:
        """Get webhooks for a team."""
        return await self._request("GET", f"/webhooks?team_id={team_id}")

    async def get_dev_resources(self, file_key: str, node_ids: list[str] | None = None) -> dict:
        """Get dev resources from a file.

        Args:
            file_key: The file key.
            node_ids: Optional list of node IDs to filter.
        """
        params = {}
        if node_ids:
            params["node_ids"] = ",".join(node_ids)
        return await self._request("GET", f"/files/{file_key}/dev_resources", params=params)


# Singleton instance
_client: FigmaDirectClient | None = None


async def get_figma_client() -> FigmaDirectClient:
    """Get the singleton Figma client.

    Returns:
        Initialized FigmaDirectClient instance.
    """
    global _client
    if _client is None:
        _client = FigmaDirectClient()
        await _client.initialize()
    return _client


async def complete_oauth_flow() -> str:
    """Start OAuth flow and return authorization URL.

    After user authorizes, call exchange_code() with the code
    from the callback URL.

    Returns:
        Authorization URL to open in browser.
    """
    client = await get_figma_client()
    return client.get_oauth_url()
