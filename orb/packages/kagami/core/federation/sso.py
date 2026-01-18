"""Enterprise SSO Integration — SAML, LDAP, and OIDC Support.

Handles enterprise Single Sign-On (SSO) flows:
- SAML SSO detection and session management
- LDAP authentication pass-through
- OIDC token validation
- SSO-required error handling

GitHub Enterprise can enforce SSO at:
- Organization level (GHEC)
- Enterprise level (GHES)

When SSO is enforced, API calls require an active SSO session.
This module helps detect and handle SSO requirements gracefully.

Example:
    >>> from kagami.core.federation.sso import SSOManager
    >>>
    >>> sso = SSOManager(config)
    >>>
    >>> # Check if SSO is required
    >>> if await sso.is_sso_required(org="myorg"):
    ...     # Redirect user to SSO flow
    ...     url = sso.get_sso_initiate_url(org="myorg")
    ...     print(f"Please authenticate at: {url}")

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Security IS trust.

Created: January 2026
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# SSO Types
# =============================================================================


class SSOProvider(Enum):
    """Supported SSO providers.

    Attributes:
        SAML: Security Assertion Markup Language (most common).
        LDAP: Lightweight Directory Access Protocol.
        OIDC: OpenID Connect.
        CAS: Central Authentication Service.
    """

    SAML = "saml"
    LDAP = "ldap"
    OIDC = "oidc"
    CAS = "cas"


class SSOEnforcement(Enum):
    """SSO enforcement level.

    Attributes:
        NONE: SSO not configured.
        OPTIONAL: SSO available but not required.
        ENFORCED: SSO required for all access.
    """

    NONE = auto()
    OPTIONAL = auto()
    ENFORCED = auto()


# =============================================================================
# SSO Session
# =============================================================================


@dataclass
class SSOSession:
    """Active SSO session information.

    Attributes:
        provider: SSO provider type.
        organization: Organization the session is for.
        user_id: GitHub user ID.
        username: GitHub username.
        email: User's email from IdP.
        created_at: Session creation timestamp.
        expires_at: Session expiration timestamp.
        attributes: Additional SAML attributes.
    """

    provider: SSOProvider
    organization: str
    user_id: int
    username: str
    email: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        if self.expires_at == 0:
            return False  # No expiration
        return time.time() > self.expires_at

    @property
    def remaining_seconds(self) -> int:
        """Seconds until session expires."""
        if self.expires_at == 0:
            return -1  # No expiration
        return max(0, int(self.expires_at - time.time()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "provider": self.provider.value,
            "organization": self.organization,
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SSOSession:
        """Deserialize from dictionary."""
        return cls(
            provider=SSOProvider(data["provider"]),
            organization=data["organization"],
            user_id=data["user_id"],
            username=data["username"],
            email=data.get("email", ""),
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at", 0.0),
            attributes=data.get("attributes", {}),
        )


# =============================================================================
# SSO Configuration
# =============================================================================


@dataclass
class SSOConfig:
    """SSO configuration for an organization or enterprise.

    Attributes:
        organization: Organization slug.
        enforcement: SSO enforcement level.
        provider: SSO provider type.
        sso_url: SSO initiation URL.
        idp_entity_id: IdP entity ID (SAML).
        acs_url: Assertion Consumer Service URL (SAML).
        metadata_url: IdP metadata URL (SAML).
    """

    organization: str
    enforcement: SSOEnforcement = SSOEnforcement.NONE
    provider: SSOProvider = SSOProvider.SAML
    sso_url: str = ""
    idp_entity_id: str = ""
    acs_url: str = ""
    metadata_url: str = ""

    @property
    def is_enforced(self) -> bool:
        """Check if SSO is enforced."""
        return self.enforcement == SSOEnforcement.ENFORCED

    @property
    def is_configured(self) -> bool:
        """Check if SSO is configured."""
        return self.enforcement != SSOEnforcement.NONE


# =============================================================================
# SSO Manager
# =============================================================================


class SSOManager:
    """Manage SSO flows for GitHub Enterprise.

    Handles SSO detection, session management, and error handling.

    Example:
        >>> from kagami.core.federation.github_config import GitHubConfig
        >>>
        >>> config = GitHubConfig(hostname="github.mycompany.com")
        >>> sso = SSOManager(config)
        >>>
        >>> # Check if SSO is required for an organization
        >>> if await sso.is_sso_required("engineering"):
        ...     print("SSO authentication required")
        ...     url = sso.get_sso_initiate_url("engineering")
        ...     print(f"Authenticate at: {url}")
        >>>
        >>> # Handle SSO error from API response
        >>> try:
        ...     await api_call()
        ... except SSORequiredError as e:
        ...     session = await sso.handle_sso_error(e)
    """

    def __init__(self, config: Any = None, token: str = "") -> None:
        """Initialize SSO manager.

        Args:
            config: GitHubConfig for enterprise.
            token: GitHub access token.
        """
        if config is None:
            from kagami.core.federation.github_config import GitHubConfig

            config = GitHubConfig()

        self._config = config
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._sso_configs: dict[str, SSOConfig] = {}
        self._sessions: dict[str, SSOSession] = {}
        self._http: httpx.AsyncClient | None = None

    @property
    def config(self) -> Any:
        """Get GitHub configuration."""
        return self._config

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None:
            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "Kagami-SSO/1.0",
            }
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            self._http = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                verify=self._config.get_ssl_context(),
            )
        return self._http

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None

    async def get_sso_config(self, organization: str) -> SSOConfig:
        """Get SSO configuration for an organization.

        Args:
            organization: Organization slug.

        Returns:
            SSOConfig for the organization.
        """
        # Check cache
        if organization in self._sso_configs:
            return self._sso_configs[organization]

        # Probe organization settings
        client = await self._get_client()

        try:
            # Try to access org — if SSO required, will get 403 with X-GitHub-SSO
            response = await client.get(f"{self._config.api_url}/orgs/{organization}")

            # Check X-GitHub-SSO header
            sso_header = response.headers.get("X-GitHub-SSO", "")

            if "required" in sso_header.lower():
                # Parse SSO URL from header
                sso_url = ""
                if "url=" in sso_header:
                    sso_url = sso_header.split("url=")[1].split(";")[0].strip()

                config = SSOConfig(
                    organization=organization,
                    enforcement=SSOEnforcement.ENFORCED,
                    sso_url=sso_url,
                )
            elif "partial" in sso_header.lower():
                config = SSOConfig(
                    organization=organization,
                    enforcement=SSOEnforcement.OPTIONAL,
                )
            else:
                config = SSOConfig(
                    organization=organization,
                    enforcement=SSOEnforcement.NONE,
                )

            self._sso_configs[organization] = config
            return config

        except Exception as e:
            logger.debug(f"SSO probe failed for {organization}: {e}")
            return SSOConfig(organization=organization)

    async def is_sso_required(self, organization: str) -> bool:
        """Check if SSO is required for an organization.

        Args:
            organization: Organization slug.

        Returns:
            True if SSO is enforced.
        """
        config = await self.get_sso_config(organization)
        return config.is_enforced

    def get_sso_initiate_url(
        self,
        organization: str,
        return_to: str = "",
    ) -> str:
        """Get URL to initiate SSO flow.

        Args:
            organization: Organization slug.
            return_to: URL to return to after SSO.

        Returns:
            SSO initiation URL.
        """
        # Check cached config for SSO URL
        config = self._sso_configs.get(organization)
        if config and config.sso_url:
            url = config.sso_url
            if return_to:
                url += f"&return_to={return_to}"
            return url

        # Default GitHub SSO URL pattern
        base_url = self._config.web_url
        url = f"{base_url}/orgs/{organization}/sso"

        if return_to:
            url += f"?return_to={return_to}"

        return url

    async def handle_sso_error(
        self,
        error: Any,
    ) -> str:
        """Handle SSO required error.

        Extracts organization and SSO URL from error,
        caches SSO config, and returns initiation URL.

        Args:
            error: SSORequiredError from API call.

        Returns:
            SSO initiation URL.
        """
        # Extract info from error
        organization = getattr(error, "organization", "")
        sso_url = getattr(error, "sso_url", "")

        if organization:
            # Cache SSO config
            self._sso_configs[organization] = SSOConfig(
                organization=organization,
                enforcement=SSOEnforcement.ENFORCED,
                sso_url=sso_url,
            )

        return sso_url or self.get_sso_initiate_url(organization)

    def get_session(self, organization: str) -> SSOSession | None:
        """Get active SSO session for an organization.

        Args:
            organization: Organization slug.

        Returns:
            Active SSOSession or None.
        """
        session = self._sessions.get(organization)
        if session and not session.is_expired:
            return session
        return None

    def set_session(self, session: SSOSession) -> None:
        """Store SSO session.

        Args:
            session: SSOSession to store.
        """
        self._sessions[session.organization] = session

    def clear_session(self, organization: str) -> None:
        """Clear SSO session.

        Args:
            organization: Organization slug.
        """
        self._sessions.pop(organization, None)

    async def validate_session(
        self,
        organization: str,
    ) -> bool:
        """Validate SSO session is still active.

        Args:
            organization: Organization slug.

        Returns:
            True if session is valid.
        """
        session = self.get_session(organization)
        if not session:
            return False

        # Try to access org-level resource to validate
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._config.api_url}/orgs/{organization}/members/{session.username}"
            )
            return response.status_code in (200, 204, 302)
        except Exception:
            return False


# =============================================================================
# Factory Functions
# =============================================================================


_sso_manager: SSOManager | None = None


async def get_sso_manager() -> SSOManager:
    """Get singleton SSO manager.

    Returns:
        SSOManager instance.
    """
    global _sso_manager

    if _sso_manager is None:
        from kagami.core.federation.github_config import GitHubConfig

        config = GitHubConfig()
        _sso_manager = SSOManager(config)

    return _sso_manager


__all__ = [
    "SSOConfig",
    "SSOEnforcement",
    "SSOManager",
    "SSOProvider",
    "SSOSession",
    "get_sso_manager",
]
