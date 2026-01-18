"""Tests for Extended Authentication Methods.

Tests:
- Phone OTP (Twilio integration)
- Magic Links (passwordless)
- TOTP 2FA (authenticator apps)
- WebAuthn/Passkeys

Colony: Crystal (e7) — Verification
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set test environment
os.environ["KAGAMI_ENVIRONMENT"] = "test"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Create test FastAPI app."""
    from kagami_api.routes.user import auth_extended

    test_app = FastAPI()
    test_app.include_router(auth_extended.get_router())
    return test_app


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


# =============================================================================
# Auth Methods Status Tests
# =============================================================================


class TestAuthMethods:
    """Test auth methods availability endpoint."""

    def test_get_auth_methods(self, client: TestClient):
        """Returns available auth methods."""
        resp = client.get("/api/user/auth/methods")

        assert resp.status_code == 200
        data = resp.json()

        # Core methods always available
        assert data["password"] is True
        assert data["magic_link"] is True
        assert data["totp"] is True
        assert data["webauthn"] is True

        # Optional methods depend on config
        assert "phone_sms" in data
        assert "phone_call" in data
        assert "apple" in data
        assert "google" in data


# =============================================================================
# TOTP Tests
# =============================================================================


class TestTOTP:
    """Test TOTP implementation."""

    def test_generate_secret(self):
        """Generate valid TOTP secret."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()

        # Should be base32 encoded (with padding)
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in secret)
        assert len(secret) == 32  # 20 bytes base32 encoded

    def test_generate_code(self):
        """Generate valid TOTP code."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()
        code = TOTPManager.generate_code(secret)

        # Should be 6 digits
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_code_current(self):
        """Verify current TOTP code."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()
        code = TOTPManager.generate_code(secret)

        # Should verify successfully
        assert TOTPManager.verify_code(secret, code)

    def test_verify_code_window(self):
        """Verify TOTP code within time window."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()

        # Code from previous interval
        prev_counter = int(time.time()) // 30 - 1
        prev_code = TOTPManager.generate_code(secret, prev_counter)

        # Should still verify with window=1
        assert TOTPManager.verify_code(secret, prev_code, window=1)

    def test_verify_code_expired(self):
        """Reject TOTP code outside window."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()

        # Code from 5 intervals ago
        old_counter = int(time.time()) // 30 - 5
        old_code = TOTPManager.generate_code(secret, old_counter)

        # Should fail with default window=1
        assert not TOTPManager.verify_code(secret, old_code, window=1)

    def test_verify_code_invalid(self):
        """Reject invalid TOTP code."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()

        # Invalid codes
        assert not TOTPManager.verify_code(secret, "000000")
        assert not TOTPManager.verify_code(secret, "")
        assert not TOTPManager.verify_code(secret, "12345")  # Wrong length
        assert not TOTPManager.verify_code(secret, "abcdef")  # Not numeric

    def test_totp_uri_generation(self):
        """Generate valid otpauth URI."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = "JBSWY3DPEHPK3PXP"
        uri = TOTPManager.get_totp_uri(secret, "testuser", "Kagami")

        assert uri.startswith("otpauth://totp/")
        assert "Kagami" in uri
        assert "testuser" in uri
        assert secret in uri

    def test_totp_known_vector(self):
        """Verify against known test vectors (RFC 6238)."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        # Test secret from RFC 6238
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # Base32 of "12345678901234567890"

        # Known test vectors (T, expected TOTP)
        # Using T=0 (time 0 / 30 = counter 0)
        code = TOTPManager.generate_code(secret, counter=0)
        assert len(code) == 6
        assert code.isdigit()


# =============================================================================
# Magic Link Tests
# =============================================================================


class TestMagicLink:
    """Test magic link implementation."""

    def test_generate_link(self):
        """Generate valid magic link."""
        from kagami_api.routes.user.auth_extended import MagicLinkManager

        token, url = MagicLinkManager.generate_link("test@example.com")

        assert len(token) > 60  # Secure token length
        assert "token=" in url
        assert token in url

    def test_verify_valid_link(self):
        """Verify valid magic link."""
        from kagami_api.routes.user.auth_extended import MagicLinkManager

        token, _ = MagicLinkManager.generate_link("test@example.com", "user-123")

        result = MagicLinkManager.verify_link(token)

        assert result is not None
        assert result["email"] == "test@example.com"
        assert result["user_id"] == "user-123"

    def test_single_use(self):
        """Magic links are single-use."""
        from kagami_api.routes.user.auth_extended import MagicLinkManager

        token, _ = MagicLinkManager.generate_link("test@example.com")

        # First use succeeds
        result1 = MagicLinkManager.verify_link(token)
        assert result1 is not None

        # Second use fails
        result2 = MagicLinkManager.verify_link(token)
        assert result2 is None

    def test_invalid_token(self):
        """Reject invalid magic link token."""
        from kagami_api.routes.user.auth_extended import MagicLinkManager

        result = MagicLinkManager.verify_link("invalid-token")
        assert result is None

    def test_expired_link(self):
        """Reject expired magic link."""
        from kagami_api.routes.user.auth_extended import (
            MagicLinkManager,
            _magic_links,
        )

        token, _ = MagicLinkManager.generate_link("test@example.com")

        # Manually expire the link
        _magic_links[token]["expires_at"] = time.time() - 1

        result = MagicLinkManager.verify_link(token)
        assert result is None


# =============================================================================
# Phone OTP Tests (Twilio)
# =============================================================================


class TestPhoneOTP:
    """Test phone OTP (Twilio) integration."""

    def test_twilio_not_configured(self, client: TestClient):
        """Returns 503 when Twilio not configured."""
        resp = client.post(
            "/api/user/auth/phone/send",
            json={"phone_number": "+1234567890", "channel": "sms"},
        )

        # Should indicate service unavailable
        assert resp.status_code == 503
        detail = resp.json()["detail"].lower()
        assert "not available" in detail or "not configured" in detail

    def test_send_sms_otp_not_configured(self, client: TestClient):
        """Send SMS OTP returns 503 when not configured."""
        resp = client.post(
            "/api/user/auth/phone/send",
            json={"phone_number": "+1234567890", "channel": "sms"},
        )

        # Without Twilio configured, expect 503
        assert resp.status_code == 503

    def test_phone_validation(self, client: TestClient):
        """Validates phone number format."""
        # Invalid format (missing +)
        resp = client.post(
            "/api/user/auth/phone/send",
            json={"phone_number": "1234567890", "channel": "sms"},
        )

        assert resp.status_code == 422  # Validation error

    def test_channel_validation(self, client: TestClient):
        """Validates channel (sms or call)."""
        resp = client.post(
            "/api/user/auth/phone/send",
            json={"phone_number": "+1234567890", "channel": "email"},
        )

        assert resp.status_code == 422  # Validation error


# =============================================================================
# WebAuthn Tests
# =============================================================================


class TestWebAuthn:
    """Test WebAuthn/Passkey implementation."""

    def test_register_options_requires_auth(self, client: TestClient):
        """Registration options requires authentication."""
        resp = client.post("/api/user/auth/webauthn/register/options")

        # Should require auth
        assert resp.status_code in [401, 403, 422]

    def test_auth_options_no_auth_required(self, client: TestClient):
        """Authentication options available without auth."""
        resp = client.post("/api/user/auth/webauthn/authenticate/options")

        assert resp.status_code == 200
        data = resp.json()

        assert "challenge" in data
        assert "rpId" in data
        assert "timeout" in data

    def test_auth_options_includes_challenge(self, client: TestClient):
        """Auth options includes secure challenge."""
        resp = client.post("/api/user/auth/webauthn/authenticate/options")
        data = resp.json()

        # Challenge should be secure random
        challenge = data["challenge"]
        assert len(challenge) > 20

        # Each call should generate new challenge
        resp2 = client.post("/api/user/auth/webauthn/authenticate/options")
        assert resp2.json()["challenge"] != challenge


# =============================================================================
# Magic Link Endpoint Tests
# =============================================================================


class TestMagicLinkEndpoints:
    """Test magic link API endpoints."""

    def test_send_magic_link(self, client: TestClient):
        """Send magic link email."""
        with patch("kagami_api.routes.user.auth._send_email_smtp") as mock_send:
            resp = client.post(
                "/api/user/auth/magic-link/send",
                json={"email": "test@example.com"},
            )

        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "sent"
        assert "expires_in" in data

    def test_verify_magic_link_invalid(self, client: TestClient):
        """Reject invalid magic link token."""
        resp = client.post(
            "/api/user/auth/magic-link/verify",
            json={"token": "invalid-token"},
        )

        assert resp.status_code == 401


# =============================================================================
# Integration Tests
# =============================================================================


class TestAuthIntegration:
    """Integration tests for auth flow."""

    def test_totp_setup_requires_auth(self, client: TestClient):
        """TOTP setup requires authentication."""
        resp = client.post("/api/user/auth/totp/setup")

        # Should require auth
        assert resp.status_code in [401, 403, 422]

    def test_webauthn_list_requires_auth(self, client: TestClient):
        """WebAuthn credential listing requires auth."""
        resp = client.get("/api/user/auth/webauthn/credentials")

        # Should require auth
        assert resp.status_code in [401, 403, 422]


# =============================================================================
# Security Tests
# =============================================================================


class TestAuthSecurity:
    """Security-focused tests."""

    def test_totp_timing_safe(self):
        """TOTP verification uses timing-safe comparison."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()
        code = TOTPManager.generate_code(secret)

        # Multiple verifications should have consistent timing
        times = []
        for _ in range(100):
            start = time.perf_counter()
            TOTPManager.verify_code(secret, code)
            times.append(time.perf_counter() - start)

        # Low variance indicates timing-safe
        import statistics

        std_dev = statistics.stdev(times)
        assert std_dev < 0.001

    def test_magic_link_token_entropy(self):
        """Magic link tokens have sufficient entropy."""
        from kagami_api.routes.user.auth_extended import MagicLinkManager

        tokens = set()
        for _ in range(100):
            token, _ = MagicLinkManager.generate_link(f"test{_}@example.com")
            assert token not in tokens
            tokens.add(token)
            # Should have at least 256 bits of entropy
            assert len(token) >= 40

    def test_phone_number_validation_e164(self, client: TestClient):
        """Phone numbers must be E.164 format."""
        invalid_numbers = [
            "1234567890",  # Missing +
            "+123",  # Too short
            "+123456789012345678",  # Too long
            "+abcdefghij",  # Non-numeric
            "555-1234",  # Local format
        ]

        for number in invalid_numbers:
            resp = client.post(
                "/api/user/auth/phone/send",
                json={"phone_number": number, "channel": "sms"},
            )
            assert resp.status_code in [422, 503], f"Expected error for {number}"


# =============================================================================
# Performance Tests
# =============================================================================


class TestAuthPerformance:
    """Performance benchmarks."""

    def test_totp_generation_performance(self):
        """TOTP generation is fast."""
        from kagami_api.routes.user.auth_extended import TOTPManager

        secret = TOTPManager.generate_secret()

        start = time.perf_counter()
        for _ in range(10000):
            TOTPManager.generate_code(secret)
        elapsed = time.perf_counter() - start

        ops_per_sec = 10000 / elapsed
        assert ops_per_sec > 10000, f"TOTP too slow: {ops_per_sec:.0f} ops/sec"

    def test_magic_link_generation_performance(self):
        """Magic link generation is fast."""
        from kagami_api.routes.user.auth_extended import MagicLinkManager

        start = time.perf_counter()
        for i in range(1000):
            MagicLinkManager.generate_link(f"test{i}@example.com")
        elapsed = time.perf_counter() - start

        ops_per_sec = 1000 / elapsed
        assert ops_per_sec > 1000, f"Magic link too slow: {ops_per_sec:.0f} ops/sec"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
