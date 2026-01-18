"""GitHub Enterprise Configuration — Auto-Detection and URL Computation.

Supports all GitHub tiers:
- GitHub.com (Free/Pro/Team)
- GitHub Enterprise Cloud (GHEC)
- GitHub Enterprise Server (GHES)

Auto-detects enterprise type by probing API endpoints.
Computes correct URLs based on hostname.

Example:
    >>> # GitHub.com (default)
    >>> config = GitHubConfig()
    >>> config.api_url
    'https://api.github.com'

    >>> # GitHub Enterprise Server
    >>> config = GitHubConfig(hostname="github.mycompany.com")
    >>> config.api_url
    'https://github.mycompany.com/api/v3'

    >>> # Auto-detect
    >>> config = await GitHubConfig.detect("github.mycompany.com")
    >>> config.enterprise_type
    EnterpriseType.ENTERPRISE_SERVER

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Enterprise IS federation.

Created: January 2026
"""

from __future__ import annotations

import logging
import os
import ssl
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Enterprise Types
# =============================================================================


class EnterpriseType(Enum):
    """GitHub platform types.

    Attributes:
        GITHUB_COM: Public GitHub (github.com) - Free/Pro/Team tiers.
        ENTERPRISE_CLOUD: GitHub Enterprise Cloud (GHEC) - hosted by GitHub.
        ENTERPRISE_SERVER: GitHub Enterprise Server (GHES) - self-hosted.
    """

    GITHUB_COM = "github.com"
    ENTERPRISE_CLOUD = "enterprise_cloud"
    ENTERPRISE_SERVER = "enterprise_server"


class AuthMethod(Enum):
    """GitHub authentication methods.

    Attributes:
        OAUTH_APP: OAuth App (client_id + client_secret).
        GITHUB_APP: GitHub App (app_id + private_key, JWT-based).
        PERSONAL_TOKEN: Personal Access Token (PAT).
        INSTALLATION_TOKEN: GitHub App installation token.
    """

    OAUTH_APP = auto()
    GITHUB_APP = auto()
    PERSONAL_TOKEN = auto()
    INSTALLATION_TOKEN = auto()


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class GitHubConfig:
    """GitHub Enterprise configuration with auto-detection.

    Handles URL computation for all GitHub tiers:
    - GitHub.com: api.github.com
    - GHEC: api.github.com (same API, enterprise features)
    - GHES: hostname/api/v3

    Attributes:
        hostname: GitHub hostname (default: github.com).
        enterprise_type: Detected enterprise type (auto-detected if None).
        client_id: OAuth App client ID.
        client_secret: OAuth App client secret.
        app_id: GitHub App ID (for GitHub Apps auth).
        private_key: GitHub App private key (PEM format).
        installation_id: GitHub App installation ID.
        enterprise_slug: Enterprise slug for GHEC.
        ssl_verify: Whether to verify SSL (disable for self-signed GHES).
        ca_cert_path: Path to custom CA certificate for GHES.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum retry attempts for failed requests.

    Example:
        >>> # Default GitHub.com
        >>> config = GitHubConfig()
        >>> config.api_url
        'https://api.github.com'

        >>> # GitHub Enterprise Server
        >>> config = GitHubConfig(hostname="github.corp.com")
        >>> config.api_url
        'https://github.corp.com/api/v3'

        >>> # With GitHub App credentials
        >>> config = GitHubConfig(
        ...     app_id=12345,
        ...     private_key="-----BEGIN RSA PRIVATE KEY-----...",
        ... )
    """

    # Hostname configuration
    hostname: str = "github.com"
    enterprise_type: EnterpriseType | None = None

    # OAuth App credentials
    client_id: str = ""
    client_secret: str = ""

    # GitHub App credentials
    app_id: int = 0
    private_key: str = ""
    installation_id: int = 0

    # Enterprise-specific
    enterprise_slug: str = ""

    # SSL/TLS configuration (for GHES with custom CA)
    ssl_verify: bool = True
    ca_cert_path: str = ""

    # HTTP configuration
    timeout: float = 30.0
    max_retries: int = 3

    # Cached detection result
    _detected: bool = field(default=False, repr=False)
    _server_version: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Load from environment variables if not set."""
        # OAuth App credentials
        if not self.client_id:
            self.client_id = os.environ.get("GITHUB_CLIENT_ID", "")
        if not self.client_secret:
            self.client_secret = os.environ.get("GITHUB_CLIENT_SECRET", "")

        # GitHub App credentials
        if not self.app_id:
            app_id_str = os.environ.get("GITHUB_APP_ID", "0")
            self.app_id = int(app_id_str) if app_id_str.isdigit() else 0
        if not self.private_key:
            key_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "")
            if key_path and os.path.exists(key_path):
                with open(key_path) as f:
                    self.private_key = f.read()
            else:
                self.private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")

        # Enterprise configuration
        if not self.enterprise_slug:
            self.enterprise_slug = os.environ.get("GITHUB_ENTERPRISE_SLUG", "")

        # Hostname override
        env_hostname = os.environ.get("GITHUB_HOSTNAME", "")
        if env_hostname and self.hostname == "github.com":
            self.hostname = env_hostname

        # Normalize hostname
        self.hostname = self.hostname.lower().strip()
        if self.hostname.startswith("https://"):
            self.hostname = self.hostname[8:]
        if self.hostname.startswith("http://"):
            self.hostname = self.hostname[7:]
        if self.hostname.endswith("/"):
            self.hostname = self.hostname[:-1]

    # =========================================================================
    # URL Properties
    # =========================================================================

    @property
    def is_github_com(self) -> bool:
        """Check if this is github.com (not enterprise)."""
        return self.hostname == "github.com"

    @property
    def api_url(self) -> str:
        """Get API base URL.

        Returns:
            - github.com: https://api.github.com
            - GHES: https://hostname/api/v3
        """
        if self.is_github_com:
            return "https://api.github.com"
        return f"https://{self.hostname}/api/v3"

    @property
    def graphql_url(self) -> str:
        """Get GraphQL API URL.

        Returns:
            - github.com: https://api.github.com/graphql
            - GHES: https://hostname/api/graphql
        """
        if self.is_github_com:
            return "https://api.github.com/graphql"
        return f"https://{self.hostname}/api/graphql"

    @property
    def oauth_authorize_url(self) -> str:
        """Get OAuth authorization URL."""
        if self.is_github_com:
            return "https://github.com/login/oauth/authorize"
        return f"https://{self.hostname}/login/oauth/authorize"

    @property
    def oauth_token_url(self) -> str:
        """Get OAuth token exchange URL."""
        if self.is_github_com:
            return "https://github.com/login/oauth/access_token"
        return f"https://{self.hostname}/login/oauth/access_token"

    @property
    def web_url(self) -> str:
        """Get web interface URL."""
        if self.is_github_com:
            return "https://github.com"
        return f"https://{self.hostname}"

    @property
    def pages_domain(self) -> str:
        """Get GitHub Pages domain.

        Returns:
            - github.com: github.io
            - GHES: pages.hostname (configurable on GHES)
        """
        if self.is_github_com:
            return "github.io"
        # GHES pages domain is configurable, default to pages.hostname
        return f"pages.{self.hostname}"

    @property
    def upload_url(self) -> str:
        """Get upload API URL (for releases, etc)."""
        if self.is_github_com:
            return "https://uploads.github.com"
        return f"https://{self.hostname}/api/uploads"

    # =========================================================================
    # Auth Method Detection
    # =========================================================================

    @property
    def auth_method(self) -> AuthMethod:
        """Detect which auth method to use based on configured credentials."""
        if self.app_id and self.private_key:
            return AuthMethod.GITHUB_APP
        if self.client_id and self.client_secret:
            return AuthMethod.OAUTH_APP
        # Check for PAT in environment
        if os.environ.get("GITHUB_TOKEN"):
            return AuthMethod.PERSONAL_TOKEN
        return AuthMethod.OAUTH_APP  # Default

    @property
    def has_oauth_credentials(self) -> bool:
        """Check if OAuth App credentials are configured."""
        return bool(self.client_id and self.client_secret)

    @property
    def has_app_credentials(self) -> bool:
        """Check if GitHub App credentials are configured."""
        return bool(self.app_id and self.private_key)

    # =========================================================================
    # SSL Configuration
    # =========================================================================

    def get_ssl_context(self) -> ssl.SSLContext | bool:
        """Get SSL context for HTTP client.

        Returns:
            - ssl.SSLContext if custom CA is configured
            - True if default verification
            - False if verification disabled
        """
        if not self.ssl_verify:
            return False

        if self.ca_cert_path and os.path.exists(self.ca_cert_path):
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(self.ca_cert_path)
            return ctx

        return True

    # =========================================================================
    # Enterprise Detection
    # =========================================================================

    async def detect_enterprise_type(self) -> EnterpriseType:
        """Auto-detect enterprise type by probing API.

        Detection logic:
        1. If hostname is github.com → GITHUB_COM
        2. Probe /api/v3/meta for GHES (returns installed_version)
        3. If enterprise_slug set, probe /enterprises/{slug} for GHEC
        4. Default to GITHUB_COM

        Returns:
            Detected EnterpriseType.
        """
        if self._detected and self.enterprise_type:
            return self.enterprise_type

        # Quick path: github.com
        if self.is_github_com:
            # Could still be GHEC if enterprise_slug is set
            if self.enterprise_slug:
                self.enterprise_type = await self._probe_ghec()
            else:
                self.enterprise_type = EnterpriseType.GITHUB_COM
            self._detected = True
            return self.enterprise_type

        # Try GHES detection
        ghes_detected = await self._probe_ghes()
        if ghes_detected:
            self.enterprise_type = EnterpriseType.ENTERPRISE_SERVER
            self._detected = True
            return self.enterprise_type

        # Fallback to github.com behavior (might be GHEC with custom domain)
        self.enterprise_type = EnterpriseType.GITHUB_COM
        self._detected = True
        return self.enterprise_type

    async def _probe_ghes(self) -> bool:
        """Probe for GitHub Enterprise Server.

        GHES exposes /api/v3/meta with installed_version field.

        Returns:
            True if GHES detected.
        """
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                verify=self.get_ssl_context(),
            ) as client:
                response = await client.get(f"{self.api_url}/meta")

                if response.status_code == 200:
                    data = response.json()
                    # GHES has installed_version, github.com doesn't
                    if "installed_version" in data:
                        self._server_version = data["installed_version"]
                        logger.info(f"✅ Detected GHES {self._server_version} at {self.hostname}")
                        return True
        except Exception as e:
            logger.debug(f"GHES probe failed: {e}")

        return False

    async def _probe_ghec(self) -> EnterpriseType:
        """Probe for GitHub Enterprise Cloud.

        GHEC enterprises are accessible via /enterprises/{slug} endpoint.

        Returns:
            ENTERPRISE_CLOUD if detected, GITHUB_COM otherwise.
        """
        if not self.enterprise_slug:
            return EnterpriseType.GITHUB_COM

        try:
            # Need auth for enterprise endpoint
            token = os.environ.get("GITHUB_TOKEN", "")
            if not token:
                return EnterpriseType.GITHUB_COM

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/enterprises/{self.enterprise_slug}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )

                if response.status_code == 200:
                    logger.info(f"✅ Detected GHEC enterprise: {self.enterprise_slug}")
                    return EnterpriseType.ENTERPRISE_CLOUD
        except Exception as e:
            logger.debug(f"GHEC probe failed: {e}")

        return EnterpriseType.GITHUB_COM

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    async def detect(cls, hostname: str = "github.com") -> GitHubConfig:
        """Create config and auto-detect enterprise type.

        Args:
            hostname: GitHub hostname to probe.

        Returns:
            GitHubConfig with enterprise_type populated.

        Example:
            >>> config = await GitHubConfig.detect("github.mycompany.com")
            >>> config.enterprise_type
            EnterpriseType.ENTERPRISE_SERVER
        """
        config = cls(hostname=hostname)
        await config.detect_enterprise_type()
        return config

    @classmethod
    def for_github_com(cls) -> GitHubConfig:
        """Create config for github.com (default)."""
        return cls(
            hostname="github.com",
            enterprise_type=EnterpriseType.GITHUB_COM,
        )

    @classmethod
    def for_enterprise_server(
        cls,
        hostname: str,
        ssl_verify: bool = True,
        ca_cert_path: str = "",
    ) -> GitHubConfig:
        """Create config for GitHub Enterprise Server.

        Args:
            hostname: GHES hostname (e.g., github.mycompany.com).
            ssl_verify: Whether to verify SSL certificates.
            ca_cert_path: Path to custom CA certificate.

        Returns:
            GitHubConfig for GHES.
        """
        return cls(
            hostname=hostname,
            enterprise_type=EnterpriseType.ENTERPRISE_SERVER,
            ssl_verify=ssl_verify,
            ca_cert_path=ca_cert_path,
        )

    @classmethod
    def for_enterprise_cloud(cls, enterprise_slug: str) -> GitHubConfig:
        """Create config for GitHub Enterprise Cloud.

        Args:
            enterprise_slug: Enterprise slug from GitHub.

        Returns:
            GitHubConfig for GHEC.
        """
        return cls(
            hostname="github.com",
            enterprise_type=EnterpriseType.ENTERPRISE_CLOUD,
            enterprise_slug=enterprise_slug,
        )

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (excluding secrets)."""
        return {
            "hostname": self.hostname,
            "enterprise_type": self.enterprise_type.value if self.enterprise_type else None,
            "api_url": self.api_url,
            "web_url": self.web_url,
            "pages_domain": self.pages_domain,
            "auth_method": self.auth_method.name,
            "has_oauth_credentials": self.has_oauth_credentials,
            "has_app_credentials": self.has_app_credentials,
            "enterprise_slug": self.enterprise_slug,
            "server_version": self._server_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GitHubConfig:
        """Deserialize from dictionary."""
        enterprise_type = None
        if data.get("enterprise_type"):
            enterprise_type = EnterpriseType(data["enterprise_type"])

        return cls(
            hostname=data.get("hostname", "github.com"),
            enterprise_type=enterprise_type,
            enterprise_slug=data.get("enterprise_slug", ""),
        )


# =============================================================================
# SSO Error Handling
# =============================================================================


class SSORequiredError(Exception):
    """Raised when SAML SSO authentication is required.

    Enterprise organizations can enforce SAML SSO. When this is enforced,
    API requests without an active SSO session return 403 with specific
    headers indicating SSO is required.

    Attributes:
        organization: Organization requiring SSO.
        sso_url: URL to initiate SSO flow.
        message: Human-readable message.
    """

    def __init__(
        self,
        organization: str = "",
        sso_url: str = "",
        message: str = "SAML SSO authentication required",
    ) -> None:
        """Initialize SSO error.

        Args:
            organization: Organization requiring SSO.
            sso_url: URL to initiate SSO flow.
            message: Human-readable message.
        """
        super().__init__(message)
        self.organization = organization
        self.sso_url = sso_url
        self.message = message

    @classmethod
    def from_response(cls, response: httpx.Response) -> SSORequiredError | None:
        """Parse SSO error from HTTP response.

        GitHub returns 403 with X-GitHub-SSO header when SSO is required:
        X-GitHub-SSO: required; url=https://github.com/orgs/org/sso?...

        Args:
            response: HTTP response to check.

        Returns:
            SSORequiredError if SSO is required, None otherwise.
        """
        if response.status_code != 403:
            return None

        sso_header = response.headers.get("X-GitHub-SSO", "")
        if not sso_header or "required" not in sso_header.lower():
            return None

        # Parse header: "required; url=https://..."
        sso_url = ""
        if "url=" in sso_header:
            sso_url = sso_header.split("url=")[1].split(";")[0].strip()

        # Try to extract org from URL
        organization = ""
        if "/orgs/" in sso_url:
            organization = sso_url.split("/orgs/")[1].split("/")[0]

        return cls(
            organization=organization,
            sso_url=sso_url,
            message=f"SAML SSO required for organization: {organization}",
        )


# =============================================================================
# Factory Functions
# =============================================================================


_default_config: GitHubConfig | None = None


def get_github_config() -> GitHubConfig:
    """Get default GitHub configuration.

    Loads from environment variables on first call.

    Returns:
        GitHubConfig instance.
    """
    global _default_config

    if _default_config is None:
        _default_config = GitHubConfig()

    return _default_config


async def detect_github_config(hostname: str = "") -> GitHubConfig:
    """Detect GitHub configuration for a hostname.

    Args:
        hostname: GitHub hostname (default: from env or github.com).

    Returns:
        GitHubConfig with detected enterprise type.
    """
    if not hostname:
        hostname = os.environ.get("GITHUB_HOSTNAME", "github.com")

    return await GitHubConfig.detect(hostname)


__all__ = [
    "AuthMethod",
    "EnterpriseType",
    "GitHubConfig",
    "SSORequiredError",
    "detect_github_config",
    "get_github_config",
]
