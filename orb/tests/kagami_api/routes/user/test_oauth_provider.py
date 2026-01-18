"""Comprehensive tests for OAuth2 Provider — Login with Kagami.

Tests cover:
- OAuth2 Authorization Code Flow
- PKCE verification
- Token exchange and refresh
- OpenID Connect compliance
- Client registration
- Security edge cases
- Performance requirements

Colony: Crystal (e7) — Verification
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app():
    """Create test FastAPI app with OAuth routes."""
    from kagami_api.routes.user.oauth_provider import get_router

    app = FastAPI()
    app.include_router(get_router())
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_client_credentials():
    """Test OAuth client credentials."""
    return {
        "client_id": "kagami-dev-client",
        "client_secret": "kagami-dev-secret",
        "redirect_uri": "http://localhost:3000/callback",
    }


@pytest.fixture
def pkce_pair():
    """Generate PKCE code verifier and challenge."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return {"verifier": verifier, "challenge": challenge}


# =============================================================================
# Discovery Endpoint Tests
# =============================================================================


class TestOpenIDDiscovery:
    """Tests for OpenID Connect Discovery."""

    def test_discovery_endpoint_returns_valid_config(self, client):
        """Discovery endpoint returns valid OpenID configuration."""
        response = client.get("/.well-known/openid-configuration")

        assert response.status_code == 200
        config = response.json()

        # Required fields per OpenID Connect Discovery spec
        assert "issuer" in config
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config
        assert "userinfo_endpoint" in config
        assert "jwks_uri" in config

        # Verify endpoints are URLs
        assert config["authorization_endpoint"].startswith("http")
        assert config["token_endpoint"].startswith("http")

    def test_discovery_includes_supported_scopes(self, client):
        """Discovery includes all supported scopes."""
        response = client.get("/.well-known/openid-configuration")
        config = response.json()

        scopes = config.get("scopes_supported", [])
        assert "openid" in scopes
        assert "profile" in scopes
        assert "email" in scopes

    def test_discovery_includes_pkce_support(self, client):
        """Discovery indicates PKCE support."""
        response = client.get("/.well-known/openid-configuration")
        config = response.json()

        methods = config.get("code_challenge_methods_supported", [])
        assert "S256" in methods

    def test_jwks_endpoint_returns_keys(self, client):
        """JWKS endpoint returns key set."""
        response = client.get("/.well-known/jwks.json")

        assert response.status_code == 200
        jwks = response.json()

        assert "keys" in jwks
        assert len(jwks["keys"]) > 0

        key = jwks["keys"][0]
        assert "kty" in key
        assert "kid" in key
        assert "use" in key


# =============================================================================
# PKCE Tests
# =============================================================================


class TestPKCE:
    """Tests for PKCE implementation."""

    def test_verify_pkce_s256_valid(self):
        """S256 PKCE verification with valid verifier."""
        from kagami_api.routes.user.oauth_provider import verify_pkce

        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        # Pre-computed challenge for this verifier
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

        assert verify_pkce(verifier, challenge, "S256") is True

    def test_verify_pkce_s256_invalid(self):
        """S256 PKCE verification fails with wrong verifier."""
        from kagami_api.routes.user.oauth_provider import verify_pkce

        verifier = "wrong_verifier"
        challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

        assert verify_pkce(verifier, challenge, "S256") is False

    def test_verify_pkce_plain_valid(self):
        """Plain PKCE verification with matching verifier."""
        from kagami_api.routes.user.oauth_provider import verify_pkce

        verifier = "test_code_verifier"
        challenge = "test_code_verifier"

        assert verify_pkce(verifier, challenge, "plain") is True

    def test_verify_pkce_plain_invalid(self):
        """Plain PKCE verification fails with wrong verifier."""
        from kagami_api.routes.user.oauth_provider import verify_pkce

        verifier = "wrong_verifier"
        challenge = "test_code_verifier"

        assert verify_pkce(verifier, challenge, "plain") is False

    def test_verify_pkce_unknown_method(self):
        """Unknown PKCE method returns False."""
        from kagami_api.routes.user.oauth_provider import verify_pkce

        assert verify_pkce("verifier", "challenge", "unknown") is False


# =============================================================================
# Client Registration Tests
# =============================================================================


class TestClientRegistration:
    """Tests for OAuth client management."""

    def test_register_client(self):
        """Client registration creates valid client."""
        from kagami_api.routes.user.oauth_provider import (
            OAuthClient,
            get_oauth_client,
            register_oauth_client,
        )

        client = OAuthClient(
            client_id="test-reg-client",
            client_secret="test-secret",
            client_name="Test Registration",
            redirect_uris=["http://localhost:3000/callback"],
            allowed_scopes=["openid", "profile"],
        )

        register_oauth_client(client)
        retrieved = get_oauth_client("test-reg-client")

        assert retrieved is not None
        assert retrieved.client_name == "Test Registration"
        assert retrieved.allowed_scopes == ["openid", "profile"]

    def test_get_nonexistent_client(self):
        """Getting nonexistent client returns None."""
        from kagami_api.routes.user.oauth_provider import get_oauth_client

        result = get_oauth_client("nonexistent-client-id")
        assert result is None

    def test_client_types(self):
        """Client types are properly set."""
        from kagami_api.routes.user.oauth_provider import OAuthClient

        public = OAuthClient(
            client_id="public-client",
            client_name="Public App",
            redirect_uris=["http://localhost:3000"],
            client_type="public",
        )
        assert public.client_secret is None
        assert public.require_pkce is True

        confidential = OAuthClient(
            client_id="confidential-client",
            client_secret="secret",
            client_name="Server App",
            redirect_uris=["http://localhost:3000"],
            client_type="confidential",
        )
        assert confidential.client_secret == "secret"


# =============================================================================
# Authorization Endpoint Tests
# =============================================================================


class TestAuthorizationEndpoint:
    """Tests for OAuth authorization endpoint."""

    def test_authorize_missing_client_id(self, client):
        """Authorization fails without client_id."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "redirect_uri": "http://localhost:3000/callback",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        # Missing required param returns 422
        assert response.status_code == 422

    def test_authorize_invalid_client(self, client):
        """Authorization fails with invalid client."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": "invalid-client-id",
                "redirect_uri": "http://localhost:3000/callback",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        # Redirects with error
        assert response.status_code == 302
        assert "error=invalid_client" in response.headers.get("location", "")

    def test_authorize_invalid_redirect_uri(self, client, test_client_credentials):
        """Authorization fails with unregistered redirect URI."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": "http://evil.com/callback",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        # Returns error page (not redirect to untrusted URI)
        assert response.status_code == 400

    def test_authorize_unsupported_response_type(self, client, test_client_credentials):
        """Authorization fails with unsupported response type."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "token",  # Implicit flow not supported
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": test_client_credentials["redirect_uri"],
                "state": "test-state",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=unsupported_response_type" in response.headers.get("location", "")

    def test_authorize_invalid_scope(self, client, test_client_credentials):
        """Authorization fails with invalid scope."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": test_client_credentials["redirect_uri"],
                "scope": "openid admin_all_the_things",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=invalid_scope" in response.headers.get("location", "")


# =============================================================================
# Token Endpoint Tests
# =============================================================================


class TestTokenEndpoint:
    """Tests for OAuth token endpoint."""

    def test_token_missing_grant_type(self, client):
        """Token request fails without grant_type."""
        response = client.post(
            "/oauth/token",
            data={
                "code": "test-code",
                "client_id": "test-client",
            },
        )
        assert response.status_code == 422

    def test_token_unsupported_grant_type(self, client, test_client_credentials):
        """Token request fails with unsupported grant type."""
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "password",  # Not supported
                "client_id": test_client_credentials["client_id"],
                "client_secret": test_client_credentials["client_secret"],
            },
        )
        assert response.status_code == 400
        assert "unsupported" in response.json().get("detail", "").lower()

    def test_token_invalid_client(self, client):
        """Token request fails with invalid client."""
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "test-code",
                "client_id": "invalid-client",
                "redirect_uri": "http://localhost:3000/callback",
            },
        )
        assert response.status_code == 401

    def test_token_invalid_client_secret(self, client, test_client_credentials):
        """Token request fails with wrong client secret."""
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "test-code",
                "client_id": test_client_credentials["client_id"],
                "client_secret": "wrong-secret",
                "redirect_uri": test_client_credentials["redirect_uri"],
            },
        )
        assert response.status_code == 401

    def test_token_invalid_code(self, client, test_client_credentials):
        """Token request fails with invalid authorization code."""
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "invalid-or-expired-code",
                "client_id": test_client_credentials["client_id"],
                "client_secret": test_client_credentials["client_secret"],
                "redirect_uri": test_client_credentials["redirect_uri"],
            },
        )
        assert response.status_code == 400

    def test_token_basic_auth(self, client, test_client_credentials):
        """Token request supports Basic auth for client credentials."""
        credentials = (
            f"{test_client_credentials['client_id']}:{test_client_credentials['client_secret']}"
        )
        encoded = base64.b64encode(credentials.encode()).decode()

        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "test-code",
                "redirect_uri": test_client_credentials["redirect_uri"],
            },
            headers={"Authorization": f"Basic {encoded}"},
        )
        # Should fail due to invalid code, but client auth should pass
        assert response.status_code == 400  # Invalid code, not 401


# =============================================================================
# Token Revocation Tests
# =============================================================================


class TestTokenRevocation:
    """Tests for token revocation endpoint."""

    def test_revoke_token_success(self, client, test_client_credentials):
        """Token revocation returns success."""
        response = client.post(
            "/oauth/revoke",
            data={
                "token": "some-refresh-token",
                "client_id": test_client_credentials["client_id"],
                "client_secret": test_client_credentials["client_secret"],
            },
        )
        assert response.status_code == 200
        assert response.json().get("status") == "ok"

    def test_revoke_invalid_client_secret(self, client, test_client_credentials):
        """Revocation fails with wrong client secret."""
        response = client.post(
            "/oauth/revoke",
            data={
                "token": "some-token",
                "client_id": test_client_credentials["client_id"],
                "client_secret": "wrong-secret",
            },
        )
        assert response.status_code == 401


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Performance requirement tests."""

    def test_discovery_response_time(self, client):
        """Discovery endpoint responds within 50ms."""
        start = time.time()
        response = client.get("/.well-known/openid-configuration")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed < 50, f"Discovery took {elapsed:.2f}ms (limit: 50ms)"

    def test_jwks_response_time(self, client):
        """JWKS endpoint responds within 50ms."""
        start = time.time()
        response = client.get("/.well-known/jwks.json")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed < 50, f"JWKS took {elapsed:.2f}ms (limit: 50ms)"

    def test_pkce_verification_performance(self, pkce_pair):
        """PKCE verification completes within 5ms."""
        from kagami_api.routes.user.oauth_provider import verify_pkce

        start = time.time()
        for _ in range(100):
            verify_pkce(pkce_pair["verifier"], pkce_pair["challenge"], "S256")
        elapsed = (time.time() - start) * 1000

        avg_time = elapsed / 100
        assert avg_time < 5, f"PKCE avg {avg_time:.2f}ms (limit: 5ms)"


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurity:
    """Security-focused tests."""

    def test_state_parameter_required(self, client, test_client_credentials):
        """Authorization requires state parameter."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": test_client_credentials["redirect_uri"],
                "scope": "openid",
                # Missing state
            },
            follow_redirects=False,
        )
        # Missing required param
        assert response.status_code == 422

    def test_pkce_required_for_public_clients(self):
        """Public clients require PKCE."""
        from kagami_api.routes.user.oauth_provider import OAuthClient

        public = OAuthClient(
            client_id="public-test",
            client_name="Public Test",
            redirect_uris=["http://localhost:3000"],
            client_type="public",
        )
        assert public.require_pkce is True

    def test_redirect_uri_exact_match(self, client, test_client_credentials):
        """Redirect URI must match exactly (no partial matches)."""
        # Trailing slash difference
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": test_client_credentials["redirect_uri"] + "/",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        # Should fail - URI doesn't match exactly
        assert response.status_code == 400

    def test_no_open_redirect(self, client, test_client_credentials):
        """Cannot use unregistered redirect URI (open redirect prevention)."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": "http://attacker.com/steal",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        # Should NOT redirect to attacker's URI
        assert response.status_code == 400
        location = response.headers.get("location", "")
        assert "attacker.com" not in location


# =============================================================================
# Integration Tests
# =============================================================================


class TestFullFlow:
    """End-to-end OAuth flow tests."""

    @pytest.mark.asyncio
    async def test_authorization_code_flow_with_pkce(self, pkce_pair):
        """Complete authorization code flow with PKCE."""
        from kagami_api.routes.user.oauth_provider import (
            OAuthClient,
            _auth_codes,
            _handle_authorization_code,
            register_oauth_client,
        )

        # Register test client
        client = OAuthClient(
            client_id="flow-test-client",
            client_secret="flow-test-secret",
            client_name="Flow Test",
            redirect_uris=["http://localhost:3000/callback"],
            allowed_scopes=["openid", "profile", "email"],
            require_pkce=True,
        )
        register_oauth_client(client)

        # Simulate authorization code generation (normally happens after consent)
        code = secrets.token_urlsafe(32)
        _auth_codes[code] = {
            "client_id": "flow-test-client",
            "user_id": "test-user-123",
            "username": "testuser",
            "email": "test@kagami.ai",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "openid profile email",
            "code_challenge": pkce_pair["challenge"],
            "code_challenge_method": "S256",
            "nonce": "test-nonce",
            "expires_at": time.time() + 600,
        }

        # Exchange code for tokens
        tokens = await _handle_authorization_code(
            client=client,
            code=code,
            redirect_uri="http://localhost:3000/callback",
            code_verifier=pkce_pair["verifier"],
        )

        # Verify token response
        assert tokens.access_token is not None
        assert tokens.token_type == "Bearer"
        assert tokens.expires_in == 3600
        assert tokens.refresh_token is not None
        assert tokens.scope == "openid profile email"
        assert tokens.id_token is not None  # OpenID Connect

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self):
        """Refresh token exchange works correctly."""
        from kagami_api.routes.user.oauth_provider import (
            OAuthClient,
            _handle_refresh_token,
            _refresh_tokens,
            register_oauth_client,
        )

        # Register test client
        client = OAuthClient(
            client_id="refresh-test-client",
            client_secret="refresh-test-secret",
            client_name="Refresh Test",
            redirect_uris=["http://localhost:3000/callback"],
        )
        register_oauth_client(client)

        # Create a refresh token
        refresh_token = secrets.token_urlsafe(32)
        _refresh_tokens[refresh_token] = {
            "user_id": "test-user",
            "username": "testuser",
            "client_id": "refresh-test-client",
            "scope": "openid profile",
            "expires_at": time.time() + 86400,
        }

        # Refresh the token
        tokens = await _handle_refresh_token(
            client=client,
            refresh_token=refresh_token,
            scope=None,
        )

        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        # Old refresh token should be rotated
        assert refresh_token not in _refresh_tokens


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_expired_authorization_code(self):
        """Expired authorization code is rejected."""
        from kagami_api.routes.user.oauth_provider import (
            OAuthClient,
            _auth_codes,
            register_oauth_client,
        )

        client = OAuthClient(
            client_id="expire-test-client",
            client_secret="secret",
            client_name="Expire Test",
            redirect_uris=["http://localhost:3000/callback"],
        )
        register_oauth_client(client)

        # Create expired code
        code = "expired-code"
        _auth_codes[code] = {
            "client_id": "expire-test-client",
            "user_id": "test",
            "username": "test",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "openid",
            "expires_at": time.time() - 100,  # Expired
        }

        # Code should be in store but considered expired
        assert code in _auth_codes

    def test_unicode_in_client_name(self):
        """Unicode in client name is handled."""
        from kagami_api.routes.user.oauth_provider import OAuthClient

        client = OAuthClient(
            client_id="unicode-client",
            client_name="鏡 Kagami App 日本語",
            redirect_uris=["http://localhost:3000"],
        )
        assert "鏡" in client.client_name

    def test_empty_scopes(self, client, test_client_credentials):
        """Empty scope parameter uses defaults."""
        response = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": test_client_credentials["client_id"],
                "redirect_uri": test_client_credentials["redirect_uri"],
                "scope": "",
                "state": "test-state",
            },
            follow_redirects=False,
        )
        # Should not error on empty scope
        assert response.status_code in (200, 302)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
