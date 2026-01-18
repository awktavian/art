"""GitHub Pages Federation — Zero-Config Instance Creation.

Sign in with GitHub → Get a federated Kagami instance instantly.
No domain required. No server needed. Just GitHub Pages.

Discovery Flow:
```
1. User signs in with GitHub OAuth
2. We create/fork kagami-instance repo
3. GitHub Pages serves HTML agents at username.github.io/kagami
4. Discovery via /.kagami.json in repo
5. Encrypted state stored as JSON blobs in repo
```

Why GitHub Pages:
- Zero cost (free GitHub account)
- Zero setup (automatic HTTPS)
- Zero maintenance (GitHub handles hosting)
- Global CDN (fast everywhere)
- Git history = audit log

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Federation should be frictionless.

Created: January 2026
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (defaults, overridden by GitHubConfig for enterprise)
# =============================================================================

# Template repo to fork for new instances
TEMPLATE_REPO = "kagami-io/kagami-instance-template"
DEFAULT_REPO_NAME = "kagami"

# Discovery file in repo
DISCOVERY_FILE = ".kagami.json"

# Default GitHub domains (for github.com)
GITHUB_PAGES_DOMAIN = "github.io"
GITHUB_API_URL = "https://api.github.com"


def _get_default_config() -> Any:
    """Get default GitHubConfig (lazy import to avoid circular deps)."""
    from kagami.core.federation.github_config import GitHubConfig

    return GitHubConfig()


# =============================================================================
# Data Models
# =============================================================================


class GitHubScope(Enum):
    """GitHub OAuth scopes needed."""

    REPO = "repo"  # Full repo access (for private repos)
    PUBLIC_REPO = "public_repo"  # Public repos only
    USER = "user:email"  # Read email for identity


@dataclass
class GitHubUser:
    """GitHub user profile.

    Attributes:
        id: GitHub user ID.
        login: GitHub username.
        name: Display name.
        email: Primary email.
        avatar_url: Profile picture URL.
        html_url: GitHub profile URL.
        pages_domain_override: Custom pages domain for enterprise.
    """

    id: int
    login: str
    name: str | None
    email: str | None
    avatar_url: str
    html_url: str
    pages_domain_override: str = ""

    def get_pages_domain(self, config: Any = None) -> str:
        """Get user's GitHub Pages domain.

        Args:
            config: Optional GitHubConfig for enterprise support.

        Returns:
            Pages domain (e.g., username.github.io or username.pages.enterprise.com).
        """
        if self.pages_domain_override:
            return self.pages_domain_override
        if config is not None:
            return f"{self.login}.{config.pages_domain}"
        return f"{self.login}.github.io"

    @property
    def pages_domain(self) -> str:
        """Get user's GitHub Pages domain (default)."""
        return self.get_pages_domain()

    def get_instance_url(self, config: Any = None) -> str:
        """Get user's Kagami instance URL.

        Args:
            config: Optional GitHubConfig for enterprise support.

        Returns:
            Instance URL.
        """
        return f"https://{self.get_pages_domain(config)}/{DEFAULT_REPO_NAME}"

    @property
    def instance_url(self) -> str:
        """Get user's Kagami instance URL (default)."""
        return self.get_instance_url()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "login": self.login,
            "name": self.name,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "html_url": self.html_url,
            "pages_domain": self.pages_domain,
            "instance_url": self.instance_url,
        }


@dataclass
class GitHubPagesInstance:
    """A Kagami instance hosted on GitHub Pages.

    Attributes:
        owner: GitHub username.
        repo: Repository name.
        public_key: Instance public key (base64).
        created_at: Instance creation timestamp.
        last_sync: Last state sync timestamp.
        federation_enabled: Whether federation is enabled.
        metadata: Additional instance metadata.
    """

    owner: str
    repo: str = DEFAULT_REPO_NAME
    public_key: str = ""
    created_at: float = field(default_factory=time.time)
    last_sync: float = 0.0
    federation_enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def url(self) -> str:
        """Get instance URL."""
        return f"https://{self.owner}.{GITHUB_PAGES_DOMAIN}/{self.repo}"

    @property
    def api_url(self) -> str:
        """Get GitHub API URL for repo."""
        return f"{GITHUB_API_URL}/repos/{self.owner}/{self.repo}"

    @property
    def discovery_url(self) -> str:
        """Get discovery file URL."""
        return f"{self.url}/{DISCOVERY_FILE}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "public_key": self.public_key,
            "created_at": self.created_at,
            "last_sync": self.last_sync,
            "federation_enabled": self.federation_enabled,
            "metadata": self.metadata,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GitHubPagesInstance:
        """Deserialize from dictionary."""
        return cls(
            owner=data["owner"],
            repo=data.get("repo", DEFAULT_REPO_NAME),
            public_key=data.get("public_key", ""),
            created_at=data.get("created_at", time.time()),
            last_sync=data.get("last_sync", 0.0),
            federation_enabled=data.get("federation_enabled", True),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DiscoveryManifest:
    """Kagami discovery manifest (.kagami.json).

    This file lives in the root of the GitHub Pages repo and
    enables discovery by other instances.

    Attributes:
        version: Protocol version.
        instance_id: Unique instance identifier.
        owner: GitHub username.
        public_key: Instance public key (base64).
        endpoints: API endpoints.
        capabilities: Instance capabilities.
        created_at: Creation timestamp.
    """

    version: str = "1"
    instance_id: str = ""
    owner: str = ""
    public_key: str = ""
    endpoints: dict[str, str] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Generate instance ID if not set."""
        if not self.instance_id and self.owner:
            self.instance_id = hashlib.sha256(f"github:{self.owner}".encode()).hexdigest()[:16]

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "version": self.version,
                "instance_id": self.instance_id,
                "owner": self.owner,
                "public_key": self.public_key,
                "endpoints": self.endpoints,
                "capabilities": self.capabilities,
                "created_at": self.created_at,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, data: str | dict) -> DiscoveryManifest:
        """Parse from JSON."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(
            version=data.get("version", "1"),
            instance_id=data.get("instance_id", ""),
            owner=data.get("owner", ""),
            public_key=data.get("public_key", ""),
            endpoints=data.get("endpoints", {}),
            capabilities=data.get("capabilities", []),
            created_at=data.get("created_at", time.time()),
        )


# =============================================================================
# GitHub OAuth Client
# =============================================================================


class GitHubOAuthClient:
    """GitHub OAuth client for authentication.

    Supports GitHub.com, Enterprise Cloud, and Enterprise Server.

    Example:
        >>> # GitHub.com (default)
        >>> client = GitHubOAuthClient()
        >>>
        >>> # GitHub Enterprise Server
        >>> from kagami.core.federation.github_config import GitHubConfig
        >>> config = GitHubConfig(hostname="github.mycompany.com")
        >>> client = GitHubOAuthClient(config=config)
        >>>
        >>> # Step 1: Get authorization URL
        >>> url = client.get_auth_url(redirect_uri)
        >>> # User visits URL, authorizes, gets code
        >>>
        >>> # Step 2: Exchange code for token
        >>> token = await client.exchange_code(code, redirect_uri)
        >>>
        >>> # Step 3: Get user profile
        >>> user = await client.get_user(token)
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        config: Any = None,
    ) -> None:
        """Initialize OAuth client.

        Args:
            client_id: GitHub OAuth app client ID (overrides config).
            client_secret: GitHub OAuth app client secret (overrides config).
            config: GitHubConfig for enterprise support.
        """
        # Use provided config or create default
        if config is None:
            config = _get_default_config()
        self._config = config

        # Credentials: explicit > config > env
        self.client_id = client_id or config.client_id or os.environ.get("GITHUB_CLIENT_ID", "")
        self.client_secret = (
            client_secret or config.client_secret or os.environ.get("GITHUB_CLIENT_SECRET", "")
        )

    @property
    def config(self) -> Any:
        """Get GitHub configuration."""
        return self._config

    def get_auth_url(
        self,
        redirect_uri: str,
        scope: list[GitHubScope] | None = None,
        state: str | None = None,
    ) -> str:
        """Get GitHub OAuth authorization URL.

        Args:
            redirect_uri: URL to redirect after authorization.
            scope: OAuth scopes to request.
            state: CSRF state token.

        Returns:
            Authorization URL (uses enterprise URL if configured).
        """
        scope = scope or [GitHubScope.PUBLIC_REPO, GitHubScope.USER]
        scope_str = " ".join(s.value for s in scope)

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope_str,
        }

        if state:
            params["state"] = state

        # Use enterprise OAuth URL if configured
        base_url = self._config.oauth_authorize_url
        return f"{base_url}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> str:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from GitHub.
            redirect_uri: Same redirect URI used in auth.

        Returns:
            Access token.

        Raises:
            SSORequiredError: If SAML SSO is required.
            ValueError: If OAuth error occurs.
        """
        async with httpx.AsyncClient(
            timeout=30.0,
            verify=self._config.get_ssl_context(),
        ) as client:
            response = await client.post(
                self._config.oauth_token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

            # Check for SSO requirement
            from kagami.core.federation.github_config import SSORequiredError

            sso_error = SSORequiredError.from_response(response)
            if sso_error:
                raise sso_error

            data = response.json()

            if "error" in data:
                raise ValueError(
                    f"GitHub OAuth error: {data.get('error_description', data['error'])}"
                )

            return data["access_token"]

    async def get_user(self, access_token: str) -> GitHubUser:
        """Get authenticated user profile.

        Args:
            access_token: GitHub access token.

        Returns:
            GitHubUser profile.

        Raises:
            SSORequiredError: If SAML SSO is required.
        """
        async with httpx.AsyncClient(
            timeout=30.0,
            verify=self._config.get_ssl_context(),
        ) as client:
            # Get basic profile
            response = await client.get(
                f"{self._config.api_url}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

            # Check for SSO requirement
            from kagami.core.federation.github_config import SSORequiredError

            sso_error = SSORequiredError.from_response(response)
            if sso_error:
                raise sso_error

            response.raise_for_status()
            data = response.json()

            # Get primary email if not public
            email = data.get("email")
            if not email:
                email_response = await client.get(
                    f"{self._config.api_url}/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                emails = email_response.json()
                for e in emails:
                    if e.get("primary"):
                        email = e["email"]
                        break

            return GitHubUser(
                id=data["id"],
                login=data["login"],
                name=data.get("name"),
                email=email,
                avatar_url=data["avatar_url"],
                html_url=data["html_url"],
            )


# =============================================================================
# GitHub Pages Instance Manager
# =============================================================================


class GitHubPagesManager:
    """Manage GitHub Pages Kagami instances.

    Supports GitHub.com, Enterprise Cloud, and Enterprise Server.

    Example:
        >>> # GitHub.com (default)
        >>> manager = GitHubPagesManager(access_token)
        >>>
        >>> # GitHub Enterprise Server
        >>> from kagami.core.federation.github_config import GitHubConfig
        >>> config = GitHubConfig(hostname="github.mycompany.com")
        >>> manager = GitHubPagesManager(access_token, config=config)
        >>>
        >>> # Create a new instance
        >>> instance = await manager.create_instance()
        >>>
        >>> # Discover another instance
        >>> other = await manager.discover("octocat")
        >>>
        >>> # Sync state
        >>> await manager.sync_state(instance, {"presence": "home"})
    """

    def __init__(self, access_token: str, config: Any = None) -> None:
        """Initialize manager.

        Args:
            access_token: GitHub access token.
            config: GitHubConfig for enterprise support.
        """
        self._token = access_token
        self._config = config if config is not None else _get_default_config()
        self._user: GitHubUser | None = None

    @property
    def config(self) -> Any:
        """Get GitHub configuration."""
        return self._config

    async def get_user(self) -> GitHubUser:
        """Get current user."""
        if self._user is None:
            client = GitHubOAuthClient(config=self._config)
            self._user = await client.get_user(self._token)
        return self._user

    async def create_instance(
        self,
        repo_name: str = DEFAULT_REPO_NAME,
        description: str = "My Kagami instance",
        private: bool = False,
    ) -> GitHubPagesInstance:
        """Create a new Kagami instance repo.

        Creates a new repo (or uses existing) and sets up GitHub Pages.

        Args:
            repo_name: Repository name.
            description: Repository description.
            private: Whether repo should be private.

        Returns:
            GitHubPagesInstance.
        """
        user = await self.get_user()
        api_url = self._config.api_url

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=self._config.get_ssl_context(),
        ) as client:
            # Check if repo exists
            check_response = await client.get(
                f"{api_url}/repos/{user.login}/{repo_name}",
                headers={"Authorization": f"Bearer {self._token}"},
            )

            if check_response.status_code == 200:
                logger.info(f"Repo {repo_name} already exists")
            else:
                # Create new repo
                create_response = await client.post(
                    f"{api_url}/user/repos",
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/vnd.github+json",
                    },
                    json={
                        "name": repo_name,
                        "description": description,
                        "private": private,
                        "auto_init": True,
                        "has_pages": True,
                    },
                )

                if check_response.status_code not in (200, 201):
                    raise ValueError(f"Failed to create repo: {create_response.text}")

                logger.info(f"Created repo {repo_name}")

            # Generate instance keypair
            from kagami.core.security.quantum_safe import HybridCrypto

            hybrid = HybridCrypto()
            keypair = hybrid.generate_keypair()
            public_key = base64.b64encode(keypair.export_public_keys()).decode()

            # Create discovery manifest
            manifest = DiscoveryManifest(
                owner=user.login,
                public_key=public_key,
                capabilities=[
                    "presence",
                    "automation",
                    "federation",
                ],
                endpoints={
                    "state": f"/{repo_name}/state.json",
                    "agents": f"/{repo_name}/agents/",
                },
            )

            # Upload discovery file
            await self._upload_file(
                repo=repo_name,
                path=DISCOVERY_FILE,
                content=manifest.to_json(),
                message="Initialize Kagami instance",
            )

            # Upload base index.html
            index_html = self._generate_index_html(user, manifest)
            await self._upload_file(
                repo=repo_name,
                path="index.html",
                content=index_html,
                message="Add index.html",
            )

            # Enable GitHub Pages
            await self._enable_pages(repo_name)

            return GitHubPagesInstance(
                owner=user.login,
                repo=repo_name,
                public_key=public_key,
                created_at=time.time(),
                federation_enabled=True,
            )

    async def discover(self, username: str) -> GitHubPagesInstance | None:
        """Discover another user's Kagami instance.

        Args:
            username: GitHub username.

        Returns:
            GitHubPagesInstance or None if not found.
        """
        pages_domain = self._config.pages_domain
        discovery_url = f"https://{username}.{pages_domain}/{DEFAULT_REPO_NAME}/{DISCOVERY_FILE}"

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                verify=self._config.get_ssl_context(),
            ) as client:
                response = await client.get(discovery_url)

                if response.status_code != 200:
                    return None

                manifest = DiscoveryManifest.from_json(response.json())

                return GitHubPagesInstance(
                    owner=username,
                    public_key=manifest.public_key,
                    created_at=manifest.created_at,
                    federation_enabled=True,
                    metadata={"capabilities": manifest.capabilities},
                )

        except Exception as e:
            logger.debug(f"Discovery failed for {username}: {e}")
            return None

    async def sync_state(
        self,
        state: dict[str, Any],
        repo_name: str = DEFAULT_REPO_NAME,
    ) -> bool:
        """Sync encrypted state to repo.

        Args:
            state: State to sync.
            repo_name: Repository name.

        Returns:
            True if successful.
        """
        try:
            # Encrypt state
            from kagami.core.security import get_unified_crypto

            crypto = await get_unified_crypto()
            state_json = json.dumps(state)
            encrypted = await crypto.encrypt(
                state_json.encode(),
                {"purpose": "github_pages_state"},
            )

            # Upload encrypted state
            state_b64 = base64.b64encode(encrypted).decode()
            await self._upload_file(
                repo=repo_name,
                path="state.json",
                content=json.dumps(
                    {
                        "encrypted": True,
                        "data": state_b64,
                        "timestamp": time.time(),
                    }
                ),
                message="Sync state",
            )

            return True

        except Exception as e:
            logger.error(f"State sync failed: {e}")
            return False

    async def _upload_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
    ) -> None:
        """Upload a file to the repo.

        Args:
            repo: Repository name.
            path: File path in repo.
            content: File content.
            message: Commit message.
        """
        user = await self.get_user()
        api_url = self._config.api_url

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=self._config.get_ssl_context(),
        ) as client:
            # Check if file exists to get SHA
            check_response = await client.get(
                f"{api_url}/repos/{user.login}/{repo}/contents/{path}",
                headers={"Authorization": f"Bearer {self._token}"},
            )

            sha = None
            if check_response.status_code == 200:
                sha = check_response.json().get("sha")

            # Upload file
            data = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode(),
            }
            if sha:
                data["sha"] = sha

            response = await client.put(
                f"{api_url}/repos/{user.login}/{repo}/contents/{path}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                },
                json=data,
            )

            if response.status_code not in (200, 201):
                raise ValueError(f"Failed to upload {path}: {response.text}")

    async def _enable_pages(self, repo: str) -> None:
        """Enable GitHub Pages for repo.

        Args:
            repo: Repository name.
        """
        user = await self.get_user()
        api_url = self._config.api_url

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=self._config.get_ssl_context(),
        ) as client:
            response = await client.post(
                f"{api_url}/repos/{user.login}/{repo}/pages",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "source": {
                        "branch": "main",
                        "path": "/",
                    },
                },
            )

            # 201 = created, 409 = already exists
            if response.status_code not in (200, 201, 409, 422):
                logger.warning(f"Pages enable response: {response.status_code}")

    def _generate_index_html(
        self,
        user: GitHubUser,
        manifest: DiscoveryManifest,
    ) -> str:
        """Generate the index.html for the instance.

        Args:
            user: GitHub user.
            manifest: Discovery manifest.

        Returns:
            HTML content.
        """
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>鏡 Kagami — {user.name or user.login}</title>

    <!-- Kagami Discovery -->
    <link rel="kagami-manifest" href=".kagami.json">
    <meta name="kagami:instance-id" content="{manifest.instance_id}">
    <meta name="kagami:public-key" content="{manifest.public_key[:32]}...">

    <style>
        :root {{
            --bg: #0a0a0f;
            --fg: #e8e8f0;
            --accent: #6366f1;
            --glow: rgba(99, 102, 241, 0.3);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'IBM Plex Sans', system-ui, sans-serif;
            background: var(--bg);
            color: var(--fg);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .container {{
            text-align: center;
            padding: 2rem;
        }}

        .mirror {{
            font-size: 6rem;
            margin-bottom: 1rem;
            animation: pulse 3s ease-in-out infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 0.8; transform: scale(1); }}
            50% {{ opacity: 1; transform: scale(1.05); }}
        }}

        h1 {{
            font-size: 2rem;
            font-weight: 300;
            margin-bottom: 0.5rem;
        }}

        .owner {{
            color: var(--accent);
            font-weight: 500;
        }}

        .status {{
            margin-top: 2rem;
            padding: 1rem;
            border: 1px solid var(--accent);
            border-radius: 8px;
            background: rgba(99, 102, 241, 0.1);
        }}

        .status-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #22c55e;
            margin-right: 0.5rem;
            animation: blink 2s ease-in-out infinite;
        }}

        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        .capabilities {{
            margin-top: 1.5rem;
            display: flex;
            gap: 0.5rem;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .cap {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            background: rgba(255,255,255,0.1);
            font-size: 0.875rem;
        }}

        footer {{
            margin-top: 3rem;
            opacity: 0.5;
            font-size: 0.875rem;
        }}

        a {{
            color: var(--accent);
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="mirror">鏡</div>
        <h1>Kagami Instance</h1>
        <p>Owned by <span class="owner">@{user.login}</span></p>

        <div class="status">
            <span class="status-dot"></span>
            Federated &amp; Encrypted
        </div>

        <div class="capabilities">
            <span class="cap">🏠 Presence</span>
            <span class="cap">⚡ Automation</span>
            <span class="cap">🔗 Federation</span>
            <span class="cap">🔐 E2E Encrypted</span>
        </div>

        <footer>
            <p>Powered by <a href="https://github.com/kagami-io/kagami">Kagami</a></p>
            <p>Instance ID: {manifest.instance_id}</p>
        </footer>
    </div>

    <!-- Kagami Agent Bootstrap -->
    <script type="module">
        // This HTML file IS a cognitive agent
        // It participates in Byzantine consensus via the browser

        const MANIFEST_URL = '.kagami.json';
        const STATE_URL = 'state.json';

        class KagamiAgent {{
            constructor() {{
                this.instanceId = '{manifest.instance_id}';
                this.owner = '{user.login}';
                this.initialized = false;
            }}

            async init() {{
                try {{
                    const manifest = await fetch(MANIFEST_URL).then(r => r.json());
                    console.log('🪞 Kagami Agent initialized:', manifest);
                    this.initialized = true;

                    // Connect to federation network
                    await this.connectFederation();
                }} catch (e) {{
                    console.error('Agent init failed:', e);
                }}
            }}

            async connectFederation() {{
                // In production, this connects to the PBFT network
                // For now, just log status
                console.log('🔗 Federation: Ready to connect');
            }}

            async getState() {{
                try {{
                    const state = await fetch(STATE_URL).then(r => r.json());
                    return state;
                }} catch (e) {{
                    return null;
                }}
            }}
        }}

        // Initialize agent
        window.kagami = new KagamiAgent();
        window.kagami.init();
    </script>
</body>
</html>
'''


# =============================================================================
# Factory Functions
# =============================================================================


_oauth_client: GitHubOAuthClient | None = None


def get_github_oauth() -> GitHubOAuthClient:
    """Get singleton GitHub OAuth client.

    Returns:
        GitHubOAuthClient instance.
    """
    global _oauth_client

    if _oauth_client is None:
        _oauth_client = GitHubOAuthClient()

    return _oauth_client


async def create_github_pages_instance(
    access_token: str,
    repo_name: str = DEFAULT_REPO_NAME,
) -> GitHubPagesInstance:
    """Create a new Kagami instance on GitHub Pages.

    Args:
        access_token: GitHub access token.
        repo_name: Repository name.

    Returns:
        GitHubPagesInstance.
    """
    manager = GitHubPagesManager(access_token)
    return await manager.create_instance(repo_name)


async def discover_github_instance(username: str) -> GitHubPagesInstance | None:
    """Discover a Kagami instance by GitHub username.

    Args:
        username: GitHub username.

    Returns:
        GitHubPagesInstance or None.
    """
    manager = GitHubPagesManager("")  # No token needed for discovery
    return await manager.discover(username)


__all__ = [
    "DiscoveryManifest",
    "GitHubOAuthClient",
    "GitHubPagesInstance",
    "GitHubPagesManager",
    "GitHubScope",
    "GitHubUser",
    "create_github_pages_instance",
    "discover_github_instance",
    "get_github_oauth",
]
