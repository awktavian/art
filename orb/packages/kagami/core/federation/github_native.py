"""GitHub-Native Federation — Zero Server Required.

Enables Kagami federation using only GitHub infrastructure:
- GitHub OAuth for authentication
- GitHub Repos for encrypted storage
- GitHub Pages for static hosting
- GitHub Issues for async consensus
- Optional relay for real-time sync

User Journey:
1. Sign in with GitHub
2. Fork template repo
3. Enable GitHub Pages
4. You're federated!

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Federation IS freedom.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Template repo to fork for new instances
TEMPLATE_REPO = "kagami-io/kagami-instance"
WELLKNOWN_PATH = ".well-known/kagami.json"
CONSENSUS_LABEL = "kagami-consensus"


def _get_default_config() -> Any:
    """Get default GitHubConfig (lazy import to avoid circular deps)."""
    from kagami.core.federation.github_config import GitHubConfig

    return GitHubConfig()


# =============================================================================
# Data Models
# =============================================================================


class GitHubTier(Enum):
    """GitHub account tiers affecting federation capabilities."""

    FREE = auto()  # Public repos only
    PRO = auto()  # Private repos + Pages
    TEAM = auto()  # Organization features
    ENTERPRISE = auto()  # Full access control


@dataclass
class GitHubInstance:
    """A Kagami instance hosted on GitHub.

    Supports GitHub.com, Enterprise Cloud, and Enterprise Server.

    Attributes:
        owner: GitHub username or org.
        repo: Repository name.
        public_key: Instance's public key (base64).
        relay_url: Optional relay endpoint.
        capabilities: What this instance supports.
        pages_url: GitHub Pages URL.
        api_base_url: Base API URL (for enterprise).
        pages_domain: Pages domain (for enterprise).
    """

    owner: str
    repo: str
    public_key: str = ""
    relay_url: str = ""
    capabilities: list[str] = field(default_factory=list)
    pages_url: str = ""
    api_base_url: str = "https://api.github.com"  # Enterprise override
    pages_domain: str = "github.io"  # Enterprise override

    @property
    def full_name(self) -> str:
        """Full repository name (owner/repo)."""
        return f"{self.owner}/{self.repo}"

    @property
    def api_url(self) -> str:
        """GitHub API URL for this repo."""
        return f"{self.api_base_url}/repos/{self.full_name}"

    @property
    def wellknown_url(self) -> str:
        """URL to .well-known/kagami.json."""
        if self.pages_url:
            return f"{self.pages_url}/.well-known/kagami.json"
        return f"https://{self.owner}.{self.pages_domain}/{self.repo}/.well-known/kagami.json"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "public_key": self.public_key,
            "relay_url": self.relay_url,
            "capabilities": self.capabilities,
            "pages_url": self.pages_url,
        }

    @classmethod
    def from_wellknown(cls, data: dict[str, Any], owner: str, repo: str) -> GitHubInstance:
        """Create from .well-known/kagami.json data."""
        return cls(
            owner=owner,
            repo=repo,
            public_key=data.get("public_key", ""),
            relay_url=data.get("relay_url", ""),
            capabilities=data.get("capabilities", []),
            pages_url=data.get("pages_url", ""),
        )


@dataclass
class ConsensusProposal:
    """A consensus proposal via GitHub Issues.

    Attributes:
        issue_number: GitHub issue number.
        title: Proposal title.
        body: Proposal body (JSON-encoded).
        proposer: GitHub username of proposer.
        votes: Votes received (username -> signature).
        created_at: Creation timestamp.
        state: Issue state (open/closed).
    """

    issue_number: int
    title: str
    body: dict[str, Any]
    proposer: str
    votes: dict[str, str] = field(default_factory=dict)
    created_at: float = 0.0
    state: str = "open"

    @property
    def vote_count(self) -> int:
        """Number of votes received."""
        return len(self.votes)

    def has_quorum(self, threshold: int) -> bool:
        """Check if proposal has reached quorum."""
        return self.vote_count >= threshold


# =============================================================================
# GitHub Client
# =============================================================================


class GitHubFederationClient:
    """Client for GitHub-native federation operations.

    Supports GitHub.com, Enterprise Cloud, and Enterprise Server.

    Example:
        >>> # GitHub.com (default)
        >>> client = GitHubFederationClient(token="ghp_xxx")
        >>>
        >>> # GitHub Enterprise Server
        >>> from kagami.core.federation.github_config import GitHubConfig
        >>> config = GitHubConfig(hostname="github.mycompany.com")
        >>> client = GitHubFederationClient(token="ghp_xxx", config=config)
        >>>
        >>> # Create instance from template
        >>> instance = await client.create_instance("my-kagami")
        >>>
        >>> # Discover another instance
        >>> other = await client.discover_instance("friend", "kagami-instance")
        >>>
        >>> # Create consensus proposal
        >>> proposal = await client.create_proposal(
        ...     title="Update automation",
        ...     body={"action": "set_lights", "value": 50},
        ... )
    """

    def __init__(
        self,
        token: str = "",
        owner: str = "",
        repo: str = "kagami-instance",
        config: Any = None,
    ) -> None:
        """Initialize GitHub federation client.

        Args:
            token: GitHub personal access token or OAuth token.
            owner: GitHub username (auto-detected if not provided).
            repo: Repository name for this instance.
            config: GitHubConfig for enterprise support.
        """
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._owner = owner
        self._repo = repo
        self._config = config if config is not None else _get_default_config()
        self._user_info: dict[str, Any] | None = None
        self._http: httpx.AsyncClient | None = None

    @property
    def config(self) -> Any:
        """Get GitHub configuration."""
        return self._config

    @property
    def api_url(self) -> str:
        """Get API base URL."""
        return self._config.api_url

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Kagami-Federation/1.0",
            }
            if self._token:
                headers["Authorization"] = f"token {self._token}"

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

    async def get_user(self) -> dict[str, Any]:
        """Get authenticated user info.

        Returns:
            User info dict with login, id, etc.

        Raises:
            SSORequiredError: If SAML SSO is required.
        """
        if self._user_info:
            return self._user_info

        client = await self._get_client()
        response = await client.get(f"{self.api_url}/user")

        # Check for SSO requirement
        from kagami.core.federation.github_config import SSORequiredError

        sso_error = SSORequiredError.from_response(response)
        if sso_error:
            raise sso_error
        response.raise_for_status()

        self._user_info = response.json()

        if not self._owner:
            self._owner = self._user_info["login"]

        return self._user_info

    async def create_instance(
        self,
        repo_name: str = "kagami-instance",
        private: bool = False,
        description: str = "My Kagami smart home instance",
    ) -> GitHubInstance:
        """Create a new Kagami instance by forking template.

        Args:
            repo_name: Name for the new repository.
            private: Whether to make repo private (requires Pro).
            description: Repository description.

        Returns:
            GitHubInstance for the new repo.
        """
        client = await self._get_client()
        user = await self.get_user()

        # Fork the template repository
        response = await client.post(
            f"{self.api_url}/repos/{TEMPLATE_REPO}/forks",
            json={
                "name": repo_name,
                "default_branch_only": True,
            },
        )

        if response.status_code == 202:
            # Fork is being created
            fork_data = response.json()
            logger.info(f"✅ Forked template to {fork_data['full_name']}")
        elif response.status_code == 422:
            # Already exists, that's fine
            logger.info(f"Repository {repo_name} already exists")
        else:
            response.raise_for_status()

        self._repo = repo_name

        # Wait for fork to be ready
        await asyncio.sleep(2)

        # Update repo settings
        await client.patch(
            f"{self.api_url}/repos/{user['login']}/{repo_name}",
            json={
                "description": description,
                "private": private,
                "has_issues": True,  # Needed for consensus
                "has_pages": True,
            },
        )

        # Enable GitHub Pages
        try:
            await client.post(
                f"{self.api_url}/repos/{user['login']}/{repo_name}/pages",
                json={
                    "source": {
                        "branch": "main",
                        "path": "/",
                    },
                },
            )
            logger.info("✅ GitHub Pages enabled")
        except Exception as e:
            logger.warning(f"Could not enable Pages (may already be enabled): {e}")

        return GitHubInstance(
            owner=user["login"],
            repo=repo_name,
            pages_url=f"https://{user['login']}.github.io/{repo_name}",
        )

    async def discover_instance(
        self,
        owner: str,
        repo: str = "kagami-instance",
    ) -> GitHubInstance | None:
        """Discover a Kagami instance by owner/repo.

        Args:
            owner: GitHub username.
            repo: Repository name.

        Returns:
            GitHubInstance or None if not found.
        """
        client = await self._get_client()

        # Try to fetch .well-known/kagami.json from Pages
        pages_url = f"https://{owner}.github.io/{repo}"
        wellknown_url = f"{pages_url}/.well-known/kagami.json"

        try:
            response = await client.get(wellknown_url)
            if response.status_code == 200:
                data = response.json()
                return GitHubInstance.from_wellknown(data, owner, repo)
        except Exception as e:
            logger.debug(f"Could not fetch wellknown from Pages: {e}")

        # Fallback: try to fetch from repo directly
        try:
            response = await client.get(
                f"{self.api_url}/repos/{owner}/{repo}/contents/{WELLKNOWN_PATH}",
            )
            if response.status_code == 200:
                content = response.json()
                if content.get("encoding") == "base64":
                    data = json.loads(base64.b64decode(content["content"]).decode())
                    instance = GitHubInstance.from_wellknown(data, owner, repo)
                    instance.pages_url = pages_url
                    return instance
        except Exception as e:
            logger.debug(f"Could not fetch wellknown from repo: {e}")

        # Repo exists but no wellknown - return basic instance
        try:
            response = await client.get(f"{self.api_url}/repos/{owner}/{repo}")
            if response.status_code == 200:
                return GitHubInstance(
                    owner=owner,
                    repo=repo,
                    pages_url=pages_url,
                )
        except Exception:
            pass

        return None

    async def update_wellknown(
        self,
        public_key: str,
        relay_url: str = "",
        capabilities: list[str] | None = None,
    ) -> bool:
        """Update .well-known/kagami.json in repo.

        Args:
            public_key: Instance's public key (base64).
            relay_url: Relay endpoint URL.
            capabilities: List of capabilities.

        Returns:
            True if successful.
        """
        client = await self._get_client()
        user = await self.get_user()

        data = {
            "version": "kfp1",
            "owner": user["login"],
            "repo": self._repo,
            "public_key": public_key,
            "relay_url": relay_url or "wss://relay.kagami.io",
            "capabilities": capabilities or ["presence", "automation", "federation"],
            "pages_url": f"https://{user['login']}.github.io/{self._repo}",
            "updated_at": time.time(),
        }

        content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()

        # Check if file exists
        sha = None
        try:
            response = await client.get(
                f"{self.api_url}/repos/{user['login']}/{self._repo}/contents/{WELLKNOWN_PATH}",
            )
            if response.status_code == 200:
                sha = response.json().get("sha")
        except Exception:
            pass

        # Create or update file
        payload: dict[str, Any] = {
            "message": "Update Kagami federation config",
            "content": content,
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha

        response = await client.put(
            f"{self.api_url}/repos/{user['login']}/{self._repo}/contents/{WELLKNOWN_PATH}",
            json=payload,
        )

        return response.status_code in (200, 201)

    # =========================================================================
    # Consensus via GitHub Issues
    # =========================================================================

    async def create_proposal(
        self,
        title: str,
        body: dict[str, Any],
        signature: str = "",
    ) -> ConsensusProposal:
        """Create a consensus proposal via GitHub Issue.

        Args:
            title: Proposal title.
            body: Proposal body (will be JSON-encoded).
            signature: Cryptographic signature.

        Returns:
            ConsensusProposal object.
        """
        client = await self._get_client()
        user = await self.get_user()

        # Encode body as JSON
        body_json = json.dumps(
            {
                "proposal": body,
                "signature": signature,
                "timestamp": time.time(),
            },
            indent=2,
        )

        response = await client.post(
            f"{self.api_url}/repos/{user['login']}/{self._repo}/issues",
            json={
                "title": f"[CONSENSUS] {title}",
                "body": f"```json\n{body_json}\n```",
                "labels": [CONSENSUS_LABEL],
            },
        )
        response.raise_for_status()

        issue_data = response.json()

        return ConsensusProposal(
            issue_number=issue_data["number"],
            title=title,
            body=body,
            proposer=user["login"],
            created_at=time.time(),
            state="open",
        )

    async def vote_on_proposal(
        self,
        issue_number: int,
        vote: bool,
        signature: str,
    ) -> bool:
        """Vote on a consensus proposal via Issue comment.

        Args:
            issue_number: GitHub issue number.
            vote: True for approve, False for reject.
            signature: Cryptographic signature of vote.

        Returns:
            True if vote was recorded.
        """
        client = await self._get_client()
        user = await self.get_user()

        vote_data = {
            "vote": "approve" if vote else "reject",
            "voter": user["login"],
            "signature": signature,
            "timestamp": time.time(),
        }

        response = await client.post(
            f"{self.api_url}/repos/{self._owner}/{self._repo}/issues/{issue_number}/comments",
            json={
                "body": f"```json\n{json.dumps(vote_data, indent=2)}\n```",
            },
        )

        return response.status_code == 201

    async def get_proposal_votes(
        self,
        issue_number: int,
    ) -> dict[str, str]:
        """Get all votes on a proposal.

        Args:
            issue_number: GitHub issue number.

        Returns:
            Dict of voter -> signature.
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.api_url}/repos/{self._owner}/{self._repo}/issues/{issue_number}/comments",
        )
        response.raise_for_status()

        votes = {}
        for comment in response.json():
            body = comment.get("body", "")
            if "```json" in body:
                try:
                    json_str = body.split("```json")[1].split("```")[0].strip()
                    vote_data = json.loads(json_str)
                    if "vote" in vote_data and "signature" in vote_data:
                        votes[vote_data["voter"]] = vote_data["signature"]
                except Exception:
                    continue

        return votes

    async def close_proposal(
        self,
        issue_number: int,
        merged: bool = True,
    ) -> bool:
        """Close a consensus proposal.

        Args:
            issue_number: GitHub issue number.
            merged: True if consensus was reached.

        Returns:
            True if successful.
        """
        client = await self._get_client()

        response = await client.patch(
            f"{self.api_url}/repos/{self._owner}/{self._repo}/issues/{issue_number}",
            json={
                "state": "closed",
                "labels": [
                    CONSENSUS_LABEL,
                    "consensus-reached" if merged else "consensus-rejected",
                ],
            },
        )

        return response.status_code == 200

    # =========================================================================
    # Encrypted Storage
    # =========================================================================

    async def store_encrypted(
        self,
        path: str,
        ciphertext: bytes,
        message: str = "Update encrypted data",
    ) -> bool:
        """Store encrypted data in repository.

        Args:
            path: File path in repo.
            ciphertext: Encrypted data.
            message: Commit message.

        Returns:
            True if successful.
        """
        client = await self._get_client()
        user = await self.get_user()

        content = base64.b64encode(ciphertext).decode()

        # Check if file exists
        sha = None
        try:
            response = await client.get(
                f"{self.api_url}/repos/{user['login']}/{self._repo}/contents/{path}",
            )
            if response.status_code == 200:
                sha = response.json().get("sha")
        except Exception:
            pass

        payload: dict[str, Any] = {
            "message": message,
            "content": content,
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha

        response = await client.put(
            f"{self.api_url}/repos/{user['login']}/{self._repo}/contents/{path}",
            json=payload,
        )

        return response.status_code in (200, 201)

    async def load_encrypted(self, path: str) -> bytes | None:
        """Load encrypted data from repository.

        Args:
            path: File path in repo.

        Returns:
            Encrypted bytes or None.
        """
        client = await self._get_client()
        user = await self.get_user()

        try:
            response = await client.get(
                f"{self.api_url}/repos/{user['login']}/{self._repo}/contents/{path}",
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("encoding") == "base64":
                    return base64.b64decode(data["content"])
        except Exception as e:
            logger.debug(f"Could not load {path}: {e}")

        return None


# =============================================================================
# Template Repository Content
# =============================================================================


def generate_template_wellknown(
    owner: str,
    repo: str = "kagami-instance",
    public_key: str = "",
) -> str:
    """Generate .well-known/kagami.json content.

    Args:
        owner: GitHub username.
        repo: Repository name.
        public_key: Instance public key.

    Returns:
        JSON string.
    """
    return json.dumps(
        {
            "version": "kfp1",
            "owner": owner,
            "repo": repo,
            "public_key": public_key,
            "relay_url": "wss://relay.kagami.io",
            "capabilities": [
                "presence",
                "automation",
                "federation",
                "encrypted_storage",
            ],
            "pages_url": f"https://{owner}.github.io/{repo}",
            "updated_at": time.time(),
        },
        indent=2,
    )


def generate_template_index() -> str:
    """Generate index.html for GitHub Pages.

    Returns:
        HTML string.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kagami Instance</title>
    <style>
        :root {
            --bg: #0d1117;
            --fg: #c9d1d9;
            --accent: #58a6ff;
            --surface: #161b22;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--fg);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .mirror { font-size: 4rem; margin-bottom: 1rem; }
        .status {
            background: var(--surface);
            padding: 1rem 2rem;
            border-radius: 8px;
            margin-top: 2rem;
        }
        .status.connected { border-left: 4px solid #3fb950; }
        .status.offline { border-left: 4px solid #f85149; }
        a { color: var(--accent); }
    </style>
</head>
<body>
    <div class="container">
        <div class="mirror">鏡</div>
        <h1>Kagami</h1>
        <p>Your federated smart home instance</p>
        <div class="status" id="status">
            Checking connection...
        </div>
    </div>
    <script type="module">
        // Check if we can connect to the relay
        const ws = new WebSocket('wss://relay.kagami.io');
        const status = document.getElementById('status');

        ws.onopen = () => {
            status.className = 'status connected';
            status.textContent = '✅ Connected to Kagami Network';
        };

        ws.onerror = () => {
            status.className = 'status offline';
            status.innerHTML = '⚠️ Offline mode — <a href="https://kagami.io/docs/hub">Get a Kagami Hub</a> for local control';
        };

        ws.onclose = () => {
            status.className = 'status offline';
            status.textContent = '🔌 Disconnected from relay';
        };
    </script>
</body>
</html>
"""


# =============================================================================
# Factory Functions
# =============================================================================


_github_client: GitHubFederationClient | None = None


async def get_github_federation_client(
    token: str = "",
) -> GitHubFederationClient:
    """Get or create GitHub federation client.

    Args:
        token: GitHub token (uses env if not provided).

    Returns:
        GitHubFederationClient instance.
    """
    global _github_client

    if _github_client is None:
        _github_client = GitHubFederationClient(token=token)

    return _github_client


__all__ = [
    "ConsensusProposal",
    "GitHubFederationClient",
    "GitHubInstance",
    "GitHubTier",
    "generate_template_index",
    "generate_template_wellknown",
    "get_github_federation_client",
]
