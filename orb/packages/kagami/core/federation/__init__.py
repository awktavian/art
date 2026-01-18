"""Kagami Federation — Distributed Instance Network.

Supports all GitHub tiers:
- GitHub.com (Free/Pro/Team)
- GitHub Enterprise Cloud (GHEC)
- GitHub Enterprise Server (GHES)

Two ways to federate:

1. **GitHub Pages (Recommended)** — Zero-config, just sign in:
    >>> from kagami.core.federation import get_github_federation_client
    >>>
    >>> client = await get_github_federation_client(token="ghp_xxx")
    >>> instance = await client.create_instance("my-kagami")
    >>> print(f"Live at: {instance.pages_url}")

2. **GitHub Enterprise** — For enterprise environments:
    >>> from kagami.core.federation import GitHubConfig, GitHubAppAuth
    >>>
    >>> config = GitHubConfig(hostname="github.mycompany.com")
    >>> auth = GitHubAppAuth(config)
    >>> token = await auth.get_installation_token(12345)

3. **Custom Domain** — For power users:
    >>> from kagami.core.federation import get_federation_manager
    >>>
    >>> manager = await get_federation_manager()
    >>> await manager.federate("example.com")

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Federation IS freedom.
"""

# Enterprise configuration (auto-detection)
# GitHub Apps authentication (enterprise-grade)
from kagami.core.federation.github_app import (
    GitHubAppAuth,
    InstallationToken,
    generate_jwt,
    get_github_app_auth,
)
from kagami.core.federation.github_config import (
    AuthMethod,
    EnterpriseType,
    GitHubConfig,
    SSORequiredError,
    detect_github_config,
    get_github_config,
)

# GitHub-Native federation (enhanced)
from kagami.core.federation.github_native import (
    ConsensusProposal,
    GitHubFederationClient,
    GitHubInstance,
    GitHubTier,
    generate_template_index,
    generate_template_wellknown,
    get_github_federation_client,
)

# GitHub Pages federation (default, zero-config)
from kagami.core.federation.github_pages import (
    DiscoveryManifest,
    GitHubOAuthClient,
    GitHubPagesInstance,
    GitHubPagesManager,
    GitHubScope,
    GitHubUser,
    create_github_pages_instance,
    discover_github_instance,
    get_github_oauth,
)

# Domain-based federation (power users)
from kagami.core.federation.protocol import (
    KFP_VERSION,
    FederatedInstance,
    FederationManager,
    FederationState,
    HandshakeRequest,
    HandshakeResponse,
    KFPDiscovery,
    KFPRecord,
    create_federation_router,
    create_webfinger_response,
    get_federation_manager,
    shutdown_federation,
)

# SSO integration (SAML, LDAP, OIDC)
from kagami.core.federation.sso import (
    SSOConfig,
    SSOEnforcement,
    SSOManager,
    SSOProvider,
    SSOSession,
    get_sso_manager,
)

__all__ = [
    "KFP_VERSION",
    # Enterprise configuration
    "AuthMethod",
    # GitHub-Native (enhanced client)
    "ConsensusProposal",
    # GitHub Pages (OAuth flow)
    "DiscoveryManifest",
    "EnterpriseType",
    # Domain-based federation
    "FederatedInstance",
    "FederationManager",
    "FederationState",
    # GitHub Apps authentication
    "GitHubAppAuth",
    "GitHubConfig",
    "GitHubFederationClient",
    "GitHubInstance",
    "GitHubOAuthClient",
    "GitHubPagesInstance",
    "GitHubPagesManager",
    "GitHubScope",
    "GitHubTier",
    "GitHubUser",
    "HandshakeRequest",
    "HandshakeResponse",
    "InstallationToken",
    "KFPDiscovery",
    "KFPRecord",
    # SSO integration
    "SSOConfig",
    "SSOEnforcement",
    "SSOManager",
    "SSOProvider",
    "SSORequiredError",
    "SSOSession",
    "create_federation_router",
    "create_github_pages_instance",
    "create_webfinger_response",
    "detect_github_config",
    "discover_github_instance",
    "generate_jwt",
    "generate_template_index",
    "generate_template_wellknown",
    "get_federation_manager",
    "get_github_app_auth",
    "get_github_config",
    "get_github_federation_client",
    "get_github_oauth",
    "get_sso_manager",
    "shutdown_federation",
]
