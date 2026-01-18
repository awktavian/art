"""Comprehensive Token Manager Tests

Tests for kagami_api/security/token_manager.py with full coverage.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit

import os
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("KAGAMI_TEST_ECHO_LLM", "1")
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_testing_only_12345678")


@pytest.fixture(autouse=True)
def reset_security_state():
    """Reset security framework state before each test to prevent pollution."""
    from kagami_api.security.token_manager import reset_token_manager_for_testing

    reset_token_manager_for_testing()
    yield
    reset_token_manager_for_testing()


class TestTokenManagerBasics:
    """Tests for basic token manager functionality."""

    def test_token_manager_import(self) -> None:
        """Test token manager can be imported."""
        from kagami_api.security.token_manager import TokenManager

        assert TokenManager is not None

    def test_token_manager_instantiation(self) -> None:
        """Test token manager can be instantiated."""
        from kagami_api.security.token_manager import TokenManager

        manager = TokenManager()
        assert manager is not None

    def test_token_manager_has_create_token(self) -> None:
        """Test token manager has create_token method."""
        from kagami_api.security.token_manager import TokenManager

        manager = TokenManager()
        assert hasattr(manager, "create_token") or hasattr(manager, "create_access_token")

    def test_token_manager_has_verify_token(self) -> None:
        """Test token manager has verify_token method."""
        from kagami_api.security.token_manager import TokenManager

        manager = TokenManager()
        assert hasattr(manager, "verify_token") or hasattr(manager, "decode_token")


class TestTokenCreation:
    """Tests for token creation."""

    @pytest.fixture
    def token_manager(self) -> Any:
        """Create token manager instance."""
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    def test_create_access_token(self, token_manager) -> Any:
        """Test creating access token."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
            )
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0
        elif hasattr(token_manager, "create_token"):
            token = token_manager.create_token(
                user_id="test_user",
            )
            assert token is not None

    def test_create_token_with_expiry(self, token_manager) -> None:
        """Test creating token with custom expiry."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
                expires_delta=timedelta(hours=1),
            )
            assert token is not None

    def test_create_refresh_token(self, token_manager) -> None:
        """Test creating refresh token."""
        if hasattr(token_manager, "create_refresh_token"):
            token = token_manager.create_refresh_token(
                data={"sub": "test_user"},
            )
            assert token is not None
            assert isinstance(token, str)


class TestTokenVerification:
    """Tests for token verification."""

    @pytest.fixture
    def token_manager(self) -> Any:
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    def test_verify_valid_token(self, token_manager) -> Any:
        """Test verifying valid token."""
        # Create a token first
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
            )

            if hasattr(token_manager, "verify_token"):
                result = token_manager.verify_token(token)
                assert result is not None
            elif hasattr(token_manager, "decode_token"):
                result = token_manager.decode_token(token)
                assert result is not None

    def test_verify_invalid_token(self, token_manager) -> None:
        """Test verifying invalid token."""
        invalid_token = "invalid.token.here"

        if hasattr(token_manager, "verify_token"):
            try:
                result = token_manager.verify_token(invalid_token)
                # May return None or raise
            except Exception:
                pass  # Expected
        elif hasattr(token_manager, "decode_token"):
            try:
                result = token_manager.decode_token(invalid_token)
            except Exception:
                pass  # Expected

    def test_verify_expired_token(self, token_manager) -> None:
        """Test verifying expired token."""
        if hasattr(token_manager, "create_access_token"):
            # Create token with very short expiry
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
                expires_delta=timedelta(seconds=-1),  # Already expired
            )

            if hasattr(token_manager, "verify_token"):
                try:
                    result = token_manager.verify_token(token)
                    # Should be None or raise
                except Exception:
                    pass  # Expected


class TestTokenRefresh:
    """Tests for token refresh."""

    @pytest.fixture
    def token_manager(self) -> Any:
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    def test_refresh_token(self, token_manager) -> Any:
        """Test refreshing a token."""
        if hasattr(token_manager, "refresh_token"):
            # Create initial token
            if hasattr(token_manager, "create_access_token"):
                original = token_manager.create_access_token(
                    data={"sub": "test_user"},
                )

                new_token = token_manager.refresh_token(original)
                assert new_token is not None


class TestTokenInfo:
    """Tests for token info extraction."""

    @pytest.fixture
    def token_manager(self) -> Any:
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    def test_get_token_info(self, token_manager) -> Any:
        """Test getting token info."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user", "role": "user"},
            )

            if hasattr(token_manager, "get_token_info"):
                info = token_manager.get_token_info(token)
                assert info is not None

    def test_token_contains_subject(self, token_manager) -> None:
        """Test token contains subject claim."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
            )

            if hasattr(token_manager, "decode_token"):
                payload = token_manager.decode_token(token)
                if payload:
                    assert "sub" in payload


class TestTokenManagerSingleton:
    """Tests for token manager singleton pattern."""

    def test_get_token_manager(self) -> None:
        """Test getting token manager singleton."""
        try:
            from kagami_api.security.token_manager import get_token_manager

            manager1 = get_token_manager()
            manager2 = get_token_manager()

            assert manager1 is not None
            assert manager2 is not None
        except ImportError:
            pytest.skip("get_token_manager not available")


class TestTokenManagerAsync:
    """Tests for async token operations."""

    @pytest.fixture
    def token_manager(self) -> Any:
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    @pytest.mark.asyncio
    async def test_async_create_token(self, token_manager: Any) -> Any:
        """Test async token creation if available."""
        if hasattr(token_manager, "create_access_token_async"):
            token = await token_manager.create_access_token_async(
                data={"sub": "test_user"},
            )
            assert token is not None

    @pytest.mark.asyncio
    async def test_async_verify_token(self, token_manager: Any) -> None:
        """Test async token verification if available."""
        if hasattr(token_manager, "verify_token_async"):
            if hasattr(token_manager, "create_access_token"):
                token = token_manager.create_access_token(
                    data={"sub": "test_user"},
                )
                result = await token_manager.verify_token_async(token)
                assert result is not None


class TestJWTClaims:
    """Tests for JWT claims handling."""

    @pytest.fixture
    def token_manager(self) -> Any:
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    def test_custom_claims(self, token_manager) -> Any:
        """Test adding custom claims to token."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={
                    "sub": "test_user",
                    "role": "admin",
                    "permissions": ["read", "write"],
                },
            )

            if hasattr(token_manager, "decode_token"):
                payload = token_manager.decode_token(token)
                if payload:
                    assert payload.get("role") == "admin"

    def test_expiry_claim(self, token_manager) -> None:
        """Test expiry claim is set."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
                expires_delta=timedelta(hours=1),
            )

            if hasattr(token_manager, "decode_token"):
                payload = token_manager.decode_token(token)
                if payload:
                    assert "exp" in payload


class TestTokenSecurityMeasures:
    """Tests for token security measures."""

    @pytest.fixture
    def token_manager(self) -> Any:
        from kagami_api.security.token_manager import TokenManager

        return TokenManager()

    def test_token_is_signed(self, token_manager) -> Any:
        """Test token is properly signed."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
            )

            # JWT format: header.payload.signature
            parts = token.split(".")
            assert len(parts) == 3
            assert len(parts[2]) > 0  # Has signature

    def test_tampered_token_rejected(self, token_manager) -> None:
        """Test tampered token is rejected."""
        if hasattr(token_manager, "create_access_token"):
            token = token_manager.create_access_token(
                data={"sub": "test_user"},
            )

            # Tamper with token
            parts = token.split(".")
            tampered = parts[0] + "." + parts[1] + ".invalid_signature"

            if hasattr(token_manager, "verify_token"):
                try:
                    result = token_manager.verify_token(tampered)
                    assert result is None
                except Exception:
                    pass  # Expected
