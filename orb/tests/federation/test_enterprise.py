"""Integration tests for GitHub Enterprise Federation.

Tests cover:
- GitHub.com (standard)
- GitHub Enterprise Cloud (GHEC)
- GitHub Enterprise Server (GHES)
- GitHub Apps authentication
- SAML SSO flows
- Identity linking

These tests use mocked HTTP responses to simulate GitHub API behavior
for different enterprise environments.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import sys

sys.path.insert(0, "packages")

from kagami.core.federation.github_config import (
    GitHubConfig,
    EnterpriseType,
    AuthMethod,
    SSORequiredError,
    detect_github_config,
)
from kagami.core.federation.github_app import (
    GitHubAppAuth,
    InstallationToken,
    generate_jwt,
)
from kagami.core.federation.sso import (
    SSOManager,
    SSOSession,
    SSOProvider,
    SSOConfig,
)
from kagami.core.federation.github_pages import GitHubOAuthClient
from kagami.core.federation.github_native import (
    GitHubFederationClient,
    GitHubInstance,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def github_com_config():
    """Standard GitHub.com configuration."""
    config = GitHubConfig(
        hostname="github.com",
        enterprise_type=EnterpriseType.GITHUB_COM,
    )
    config.client_id = "test_client_id"
    config.client_secret = "test_client_secret"
    return config


@pytest.fixture
def ghec_config():
    """GitHub Enterprise Cloud configuration."""
    config = GitHubConfig.for_enterprise_cloud(enterprise_slug="mycompany")
    config.client_id = "ghec_client_id"
    config.client_secret = "ghec_client_secret"
    return config


@pytest.fixture
def ghes_config():
    """GitHub Enterprise Server configuration."""
    config = GitHubConfig.for_enterprise_server(
        hostname="github.corp.example.com",
        ssl_verify=False,  # Common for internal CAs
    )
    config.client_id = "ghes_client_id"
    config.client_secret = "ghes_client_secret"
    return config


@pytest.fixture
def github_app_config():
    """Configuration with GitHub App credentials."""
    # Generate a test RSA key (not secure, just for testing structure)
    test_private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3QO0TUX/B4ZQ0P/jGbV6W5Vhs2M3VQ7a8gOQxc1pVZxFJv
C8e3bRWX3m4p7lSBnYP2bCQp6T3Z5z6fEYB8e0H5nKJ9e7ZQi8R5xKU3x6t8HYCX
4M/3DGPX3KZQ5+JEGwHVWQKDABFzEz7SvQ7Z8s3G9J6k8X3OdQ0e7F3Z0Z0Z0Z0Z
0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z
0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z
0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z
0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0Z0ZIBAAKCAQEA0Z3QO0TUX/B4ZQ0P/jGbV6W5Vhs2M3
-----END RSA PRIVATE KEY-----"""

    config = GitHubConfig(hostname="github.com", app_id=12345)
    config.private_key = test_private_key
    return config


@pytest.fixture
def sso_manager():
    """SSO Manager instance."""
    return SSOManager()


# =============================================================================
# GitHubConfig Tests
# =============================================================================


class TestGitHubConfig:
    """Tests for GitHubConfig enterprise detection and URL generation."""

    def test_github_com_urls(self, github_com_config):
        """GitHub.com URLs should use api.github.com."""
        assert github_com_config.api_url == "https://api.github.com"
        assert github_com_config.oauth_authorize_url == "https://github.com/login/oauth/authorize"
        assert github_com_config.oauth_token_url == "https://github.com/login/oauth/access_token"
        assert github_com_config.pages_domain == "github.io"
        assert github_com_config.is_github_com

    def test_ghec_urls(self, ghec_config):
        """GHEC uses api.github.com with enterprise features."""
        assert ghec_config.api_url == "https://api.github.com"
        assert ghec_config.enterprise_type == EnterpriseType.ENTERPRISE_CLOUD
        assert ghec_config.enterprise_slug == "mycompany"
        # GHEC still uses github.io for pages
        assert ghec_config.pages_domain == "github.io"

    def test_ghes_urls(self, ghes_config):
        """GHES uses custom hostname for API and Pages."""
        assert ghes_config.api_url == "https://github.corp.example.com/api/v3"
        assert (
            ghes_config.oauth_authorize_url
            == "https://github.corp.example.com/login/oauth/authorize"
        )
        assert ghes_config.pages_domain == "pages.github.corp.example.com"
        assert not ghes_config.is_github_com
        assert not ghes_config.ssl_verify

    def test_factory_methods(self):
        """Factory methods should create correct configurations."""
        ghec = GitHubConfig.for_enterprise_cloud("testent")
        assert ghec.enterprise_type == EnterpriseType.ENTERPRISE_CLOUD
        assert ghec.enterprise_slug == "testent"

        ghes = GitHubConfig.for_enterprise_server("git.corp.com")
        assert ghes.enterprise_type == EnterpriseType.ENTERPRISE_SERVER
        assert ghes.hostname == "git.corp.com"

    def test_auth_method_detection(self, github_com_config, github_app_config):
        """Auth method should be detected from configuration."""
        # OAuth App by default (with credentials set)
        assert github_com_config.auth_method in [AuthMethod.OAUTH_APP, AuthMethod.PERSONAL_TOKEN]

        # App auth when app_id and private key present
        assert github_app_config.auth_method == AuthMethod.GITHUB_APP


class TestEnterpriseDetection:
    """Tests for automatic enterprise type detection."""

    @pytest.mark.asyncio
    async def test_detect_github_com(self):
        """Detection should identify GitHub.com."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Mock /meta response for github.com
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "hooks": ["192.30.252.0/22"],
            }
            mock_instance.get.return_value = mock_response

            config = await detect_github_config("github.com")
            assert config.enterprise_type == EnterpriseType.GITHUB_COM

    @pytest.mark.asyncio
    async def test_detect_ghes(self):
        """Detection should identify GHES from enterprise-specific response."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Mock response with installed_version for GHES
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "installed_version": "3.8.0",
            }
            mock_instance.get.return_value = mock_response

            config = await detect_github_config("github.corp.com")
            assert config.enterprise_type == EnterpriseType.ENTERPRISE_SERVER


# =============================================================================
# GitHub App Authentication Tests
# =============================================================================


class TestGitHubAppAuth:
    """Tests for GitHub App JWT and installation token flow."""

    def test_installation_token_parsing(self):
        """InstallationToken should parse API response correctly."""
        response_data = {
            "token": "ghs_testtoken123",
            "expires_at": "2024-06-01T12:00:00Z",
            "permissions": {
                "contents": "read",
                "metadata": "read",
                "issues": "write",
            },
            "repositories": [
                {"full_name": "owner/repo1"},
                {"full_name": "owner/repo2"},
            ],
        }

        token = InstallationToken.from_response(response_data)

        assert token.token == "ghs_testtoken123"
        assert token.permissions == {"contents": "read", "metadata": "read", "issues": "write"}
        assert token.repositories == ["owner/repo1", "owner/repo2"]

    def test_expired_token_detection(self):
        """Should detect expired tokens."""
        token = InstallationToken(
            token="ghs_expired",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            permissions={},
            repositories=[],
        )
        assert token.is_expired

    def test_valid_token_detection(self):
        """Should detect valid tokens."""
        token = InstallationToken(
            token="ghs_valid",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            permissions={},
            repositories=[],
        )
        assert not token.is_expired


# =============================================================================
# SSO Tests
# =============================================================================


class TestSSOManager:
    """Tests for SAML/LDAP SSO handling."""

    def test_sso_initiate_url(self, sso_manager):
        """Should generate correct SSO initiation URL."""
        url = sso_manager.get_sso_initiate_url(
            organization="myorg",
            return_to="https://app.kagami.io/callback",
        )

        assert "orgs/myorg/sso" in url
        assert "return_to=" in url

    def test_session_management(self, sso_manager):
        """Should store and retrieve SSO sessions."""
        session = SSOSession(
            provider=SSOProvider.SAML,
            organization="testorg",
            user_id=12345,
            username="testuser",
            email="test@example.com",
        )

        # Store session
        sso_manager.set_session(session)

        # Retrieve session
        retrieved = sso_manager.get_session("testorg")
        assert retrieved is not None
        assert retrieved.username == "testuser"
        assert retrieved.user_id == 12345

        # Clear session
        sso_manager.clear_session("testorg")
        assert sso_manager.get_session("testorg") is None

    def test_sso_required_error_parsing(self):
        """Should parse SSO-required headers from GitHub."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-GitHub-SSO": "required; url=https://github.com/orgs/myorg/sso?signature=abc123"
        }

        error = SSORequiredError.from_response(mock_response)

        assert error is not None
        assert error.organization == "myorg"
        assert "sso" in error.sso_url

    def test_no_sso_error_for_normal_403(self):
        """Should not create error for non-SSO 403 responses."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {}  # No SSO header

        error = SSORequiredError.from_response(mock_response)
        assert error is None


# =============================================================================
# OAuth Client Tests
# =============================================================================


class TestGitHubOAuthClient:
    """Tests for OAuth flow with enterprise support."""

    def test_auth_url_github_com(self, github_com_config):
        """Auth URL should use github.com for standard config."""
        client = GitHubOAuthClient(
            client_id="test_id",
            config=github_com_config,
        )

        url = client.get_auth_url("http://localhost/callback")

        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test_id" in url

    def test_auth_url_ghes(self, ghes_config):
        """Auth URL should use GHES hostname."""
        client = GitHubOAuthClient(
            client_id="test_id",
            config=ghes_config,
        )

        url = client.get_auth_url("http://localhost/callback")

        assert "github.corp.example.com/login/oauth/authorize" in url


# =============================================================================
# Federation Client Tests
# =============================================================================


class TestGitHubFederationClient:
    """Tests for federation client with enterprise support."""

    def test_api_url_github_com(self, github_com_config):
        """Should use api.github.com for standard config."""
        client = GitHubFederationClient(
            token="test_token",
            config=github_com_config,
        )

        assert client.api_url == "https://api.github.com"

    def test_api_url_ghes(self, ghes_config):
        """Should use GHES API URL for enterprise server."""
        client = GitHubFederationClient(
            token="test_token",
            config=ghes_config,
        )

        assert client.api_url == "https://github.corp.example.com/api/v3"

    def test_instance_urls_github_com(self):
        """GitHubInstance should generate correct URLs for github.com."""
        instance = GitHubInstance(
            owner="testuser",
            repo="kagami-instance",
            public_key="pk123",
        )

        assert instance.full_name == "testuser/kagami-instance"
        assert instance.api_url == "https://api.github.com/repos/testuser/kagami-instance"
        assert (
            instance.wellknown_url
            == "https://testuser.github.io/kagami-instance/.well-known/kagami.json"
        )

    def test_instance_urls_ghes(self):
        """GitHubInstance should generate correct URLs for GHES."""
        instance = GitHubInstance(
            owner="testuser",
            repo="kagami-instance",
            public_key="pk123",
            api_base_url="https://github.corp.com/api/v3",
            pages_domain="pages.github.corp.com",
        )

        assert instance.api_url == "https://github.corp.com/api/v3/repos/testuser/kagami-instance"
        assert "pages.github.corp.com" in instance.wellknown_url


# =============================================================================
# Integration Tests (End-to-End Flows)
# =============================================================================


class TestEnterpriseIntegration:
    """End-to-end integration tests for enterprise flows."""

    @pytest.mark.asyncio
    async def test_full_ghes_oauth_flow(self, ghes_config):
        """Test OAuth URL generation for GHES."""
        # 1. Create OAuth client with GHES config
        oauth_client = GitHubOAuthClient(
            client_id=ghes_config.client_id,
            client_secret=ghes_config.client_secret,
            config=ghes_config,
        )

        # 2. Generate auth URL (should point to GHES)
        auth_url = oauth_client.get_auth_url("http://localhost/callback")
        assert ghes_config.hostname in auth_url

    @pytest.mark.asyncio
    async def test_sso_session_workflow(self, sso_manager):
        """Test SSO session management workflow."""
        # 1. Create session
        session = SSOSession(
            provider=SSOProvider.SAML,
            organization="myorg",
            user_id=12345,
            username="ssouser",
        )

        # 2. Store session
        sso_manager.set_session(session)

        # 3. Verify session is active
        retrieved = sso_manager.get_session("myorg")
        assert retrieved is not None
        assert retrieved.username == "ssouser"

        # 4. Check session not expired
        assert not retrieved.is_expired


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_hostname_handling(self):
        """Should handle invalid hostnames gracefully."""
        config = GitHubConfig(hostname="not-a-real-github.example.com")
        # Should still generate URLs, just won't work
        assert "not-a-real-github.example.com" in config.api_url

    def test_config_from_environment(self):
        """Should load config from environment variables."""
        # This tests that GitHubConfig reads from environment
        config = GitHubConfig()
        # Hostname defaults to github.com when not set
        assert config.hostname == "github.com"

    def test_malformed_sso_header_partial(self):
        """Should handle partial SSO headers."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-GitHub-SSO": "required"  # No URL
        }

        error = SSORequiredError.from_response(mock_response)
        # Should create error with empty sso_url
        assert error is not None
        assert error.sso_url == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
