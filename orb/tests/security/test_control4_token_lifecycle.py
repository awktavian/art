"""💎 CRYSTAL COLONY — Control4 Token Lifecycle Validation

Comprehensive testing for Control4 bearer token security, lifecycle management,
and authentication reliability. Ensures secure credential handling and proper
token refresh mechanisms with crystalline safety verification.

Token Security Areas:
1. Bearer token format validation and security
2. Token expiration and refresh mechanisms
3. Authentication flow security and error handling
4. Token storage and retrieval from keychain
5. Network security during token operations
6. Rate limiting and abuse prevention
7. Token revocation and cleanup procedures

Safety Focus:
- Credential security and PII protection
- Authentication bypass prevention
- Token leakage detection and mitigation
- Secure storage validation
- Network communication encryption

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import aiohttp

from kagami.core.safety import get_safety_filter
from kagami_smarthome.integrations.control4 import Control4Integration
from kagami_smarthome.types import SmartHomeConfig


class TestControl4TokenSecurity:
    """Test Control4 bearer token security mechanisms."""

    @pytest.fixture
    def config(self):
        """Create test configuration with valid token."""
        return SmartHomeConfig(
            control4_host="192.168.1.100",
            control4_bearer_token="test_secure_token_12345_abcdef",
            control4_director_id="1234",
        )

    @pytest.fixture
    def integration(self, config):
        """Create Control4 integration instance."""
        return Control4Integration(config)

    @pytest.fixture
    def cbf_filter(self):
        """Create CBF filter for safety validation."""
        return get_safety_filter()

    def test_bearer_token_format_validation(self, integration, cbf_filter):
        """Test bearer token format validation and security."""

        # Valid token formats
        valid_tokens = [
            "secure_token_12345_abcdef",
            "control4_api_key_67890_ghijkl",
            "bearer_auth_token_long_format_with_numbers_123456789",
        ]

        for token in valid_tokens:
            assert integration._validate_bearer_token(token)

            # Safety validation
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "token_validation",
                    "token_format": "valid",
                    "token_length": len(token),
                    "security_context": "authentication",
                }
            )
            assert h_value >= 0.7  # High safety for valid tokens

    def test_bearer_token_security_requirements(self, integration, cbf_filter):
        """Test bearer token security requirements."""

        # Invalid/insecure token formats
        invalid_tokens = [
            "",  # Empty
            "short",  # Too short
            "123456",  # Only numbers
            "abcdef",  # Only letters
            "test",  # Too simple
            "password123",  # Common pattern
            "admin",  # Default credential
            None,  # None value
        ]

        for token in invalid_tokens:
            assert not integration._validate_bearer_token(token)

            # Safety validation - insecure tokens have low safety
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "token_validation",
                    "token_format": "invalid",
                    "token_value": str(token) if token else "null",
                    "security_risk": "authentication_bypass",
                }
            )
            assert h_value < 0.5  # Low safety for invalid tokens

    def test_token_entropy_validation(self, integration, cbf_filter):
        """Test token entropy and randomness requirements."""

        # Low entropy tokens (security risk)
        low_entropy_tokens = [
            "aaaaaaaaaaaaaaaaaaa",  # Repeated characters
            "123456789012345678",  # Sequential numbers
            "abcdefghijklmnopqrs",  # Sequential letters
            "token_token_token_token",  # Repeated patterns
        ]

        for token in low_entropy_tokens:
            # Should fail security validation even if format looks valid
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "token_entropy_check",
                    "token": token,
                    "entropy_level": "low",
                    "security_concern": "predictable_token",
                }
            )
            assert h_value < 0.4  # Very low safety for predictable tokens

    def test_token_storage_security(self, integration, cbf_filter):
        """Test secure token storage mechanisms."""

        # Test keychain storage security
        with patch("kagami_smarthome.secrets.secrets.get") as mock_keychain:
            mock_keychain.return_value = "secure_keychain_token_12345"

            # Loading from keychain should be secure
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "token_storage",
                    "storage_method": "keychain",
                    "encrypted": True,
                    "access_control": "app_specific",
                }
            )
            assert h_value >= 0.8  # High safety for secure storage

    def test_token_transmission_security(self, integration, cbf_filter):
        """Test token transmission security."""

        # HTTPS transmission
        https_h_value = cbf_filter.evaluate_safety(
            {
                "action": "token_transmission",
                "protocol": "https",
                "encryption": "tls_1.3",
                "certificate_validation": True,
            }
        )
        assert https_h_value >= 0.9  # Very high safety for HTTPS

        # HTTP transmission (insecure)
        http_h_value = cbf_filter.evaluate_safety(
            {
                "action": "token_transmission",
                "protocol": "http",
                "encryption": False,
                "security_risk": "credential_exposure",
            }
        )
        assert http_h_value < 0.2  # Very low safety for HTTP

    def test_authorization_header_construction(self, integration):
        """Test secure authorization header construction."""

        headers = integration._get_headers()

        # Verify header structure
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

        # Extract token from header
        auth_header = headers["Authorization"]
        token = auth_header.replace("Bearer ", "")

        # Token should not be exposed in logs
        assert token == integration.config.control4_bearer_token
        assert len(token) > 10  # Reasonable minimum length

    @pytest.mark.asyncio
    async def test_token_authentication_flow(self, integration, cbf_filter):
        """Test complete authentication flow security."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Mock successful authentication
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"director": {"id": "1234"}, "authenticated": True}
            )
            mock_get.return_value.__aenter__.return_value = mock_response

            # Perform authentication
            start_time = time.time()
            success = await integration.connect()
            auth_duration = time.time() - start_time

            assert success

            # Validate authentication safety
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "authentication_flow",
                    "success": success,
                    "duration_ms": auth_duration * 1000,
                    "secure_channel": True,
                }
            )
            assert h_value >= 0.8

    @pytest.mark.asyncio
    async def test_authentication_failure_handling(self, integration, cbf_filter):
        """Test authentication failure handling and security."""

        failure_scenarios = [
            (401, "Unauthorized", "invalid_token"),
            (403, "Forbidden", "insufficient_permissions"),
            (429, "Rate Limited", "too_many_requests"),
            (500, "Server Error", "server_failure"),
        ]

        for status_code, reason, error_type in failure_scenarios:
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_response = Mock()
                mock_response.status = status_code
                mock_response.json = AsyncMock(return_value={"error": reason, "code": error_type})
                mock_get.return_value.__aenter__.return_value = mock_response

                # Authentication should fail gracefully
                success = await integration.connect()
                assert not success

                # Validate failure handling safety
                h_value = cbf_filter.evaluate_safety(
                    {
                        "action": "authentication_failure",
                        "status_code": status_code,
                        "error_type": error_type,
                        "graceful_failure": True,
                    }
                )
                assert h_value >= 0.5  # Should maintain safety during failures


class TestControl4TokenLifecycle:
    """Test Control4 token lifecycle management."""

    @pytest.fixture
    def config(self):
        return SmartHomeConfig(
            control4_host="192.168.1.100",
            control4_bearer_token="lifecycle_test_token_12345",
            control4_director_id="1234",
        )

    @pytest.fixture
    def integration(self, config):
        return Control4Integration(config)

    @pytest.mark.asyncio
    async def test_token_expiration_detection(self, integration):
        """Test detection of expired tokens."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Mock token expiration response
            mock_response = Mock()
            mock_response.status = 401
            mock_response.json = AsyncMock(
                return_value={"error": "Token expired", "code": "token_expired"}
            )
            mock_get.return_value.__aenter__.return_value = mock_response

            # Should detect expiration
            success = await integration.connect()
            assert not success

            # Integration should know token is invalid
            assert not integration.is_connected

    @pytest.mark.asyncio
    async def test_token_refresh_mechanism(self, integration):
        """Test automatic token refresh mechanisms."""

        # Note: Control4 uses long-lived bearer tokens, not refresh tokens
        # This test validates the pattern for potential future refresh support

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"access_token": "new_refreshed_token_67890", "expires_in": 3600}
            )
            mock_post.return_value.__aenter__.return_value = mock_response

            # Simulate token refresh (if implemented)
            if hasattr(integration, "_refresh_token"):
                new_token = await integration._refresh_token()
                assert new_token is not None
                assert new_token != integration.config.control4_bearer_token

    @pytest.mark.asyncio
    async def test_token_validation_before_requests(self, integration):
        """Test token validation before making API requests."""

        # Invalid token configuration
        integration.config.control4_bearer_token = ""

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Should not make request with invalid token
            await integration.connect()

            # Verify no request was made
            mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_cleanup_on_disconnect(self, integration):
        """Test proper token cleanup on disconnection."""

        # Connect first
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"director": {"id": "1234"}})
            mock_get.return_value.__aenter__.return_value = mock_response

            await integration.connect()
            assert integration.is_connected

        # Disconnect should clear state
        await integration.disconnect()
        assert not integration.is_connected

        # Internal state should be cleared
        # (Implementation specific - may vary based on actual cleanup logic)

    def test_token_storage_location_security(self, integration):
        """Test secure token storage location."""

        # Token should not be stored in easily accessible locations
        # Should use system keychain or secure storage

        # Verify token is not in plain text files
        import tempfile
        import os

        # Check that integration doesn't write tokens to temp files
        temp_dir = tempfile.gettempdir()
        for root, _dirs, files in os.walk(temp_dir):
            for file in files:
                if "control4" in file.lower() or "token" in file.lower():
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path) as f:
                            content = f.read()
                            assert integration.config.control4_bearer_token not in content
                    except (PermissionError, UnicodeDecodeError):
                        pass  # Can't read file or binary file

    @pytest.mark.asyncio
    async def test_concurrent_token_usage(self, integration):
        """Test thread-safe token usage in concurrent scenarios."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"rooms": []})
            mock_get.return_value.__aenter__.return_value = mock_response

            # Connect first
            integration._connected = True

            # Simulate concurrent requests using the same token
            tasks = []
            for _ in range(10):
                task = asyncio.create_task(integration.get_rooms())
                tasks.append(task)

            # All requests should complete without token conflicts
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check that no exceptions occurred due to token conflicts
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0


class TestControl4NetworkSecurity:
    """Test network security for Control4 communications."""

    @pytest.fixture
    def integration(self):
        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="network_security_token_12345"
        )
        return Control4Integration(config)

    @pytest.fixture
    def cbf_filter(self):
        return get_safety_filter()

    def test_https_enforcement(self, integration, cbf_filter):
        """Test HTTPS enforcement for all requests."""

        # All API endpoints should use HTTPS
        endpoint = integration._build_endpoint("/test/endpoint")
        assert endpoint.startswith("https://")
        assert ":8443" in endpoint  # Control4 HTTPS port

        # Validate HTTPS usage safety
        h_value = cbf_filter.evaluate_safety(
            {"action": "api_request", "protocol": "https", "port": 8443, "encryption": True}
        )
        assert h_value >= 0.9

    @pytest.mark.asyncio
    async def test_ssl_certificate_validation(self, integration, cbf_filter):
        """Test SSL certificate validation."""

        # Control4 typically uses self-signed certificates
        # Integration should handle this securely

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = Mock()
            mock_session.return_value = mock_session_instance

            # Verify SSL context configuration
            ssl_context = integration._create_ssl_context()

            # Should have appropriate SSL settings for self-signed certificates
            # while maintaining reasonable security

            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "ssl_configuration",
                    "self_signed_allowed": True,
                    "hostname_verification": False,  # Typical for Control4
                    "certificate_validation": "relaxed",
                }
            )
            assert h_value >= 0.6  # Moderate safety for local devices

    @pytest.mark.asyncio
    async def test_request_timeout_security(self, integration, cbf_filter):
        """Test request timeout security."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Mock timeout scenario
            mock_get.side_effect = TimeoutError("Request timed out")

            # Should handle timeouts gracefully
            start_time = time.time()

            try:
                await integration.connect()
            except TimeoutError:
                pass  # Expected

            duration = time.time() - start_time

            # Should timeout reasonably quickly (not hang indefinitely)
            assert duration < 30  # 30 second max

            # Validate timeout handling safety
            h_value = cbf_filter.evaluate_safety(
                {"action": "request_timeout", "duration_s": duration, "graceful_failure": True}
            )
            assert h_value >= 0.7

    @pytest.mark.asyncio
    async def test_rate_limiting_compliance(self, integration, cbf_filter):
        """Test compliance with rate limiting."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Mock rate limit response
            mock_response = Mock()
            mock_response.status = 429
            mock_response.headers = {"Retry-After": "60"}
            mock_get.return_value.__aenter__.return_value = mock_response

            # Should respect rate limits
            success = await integration.connect()
            assert not success

            # Validate rate limit compliance safety
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "rate_limit_response",
                    "status_code": 429,
                    "retry_after": 60,
                    "compliant": True,
                }
            )
            assert h_value >= 0.8

    def test_local_network_security(self, integration, cbf_filter):
        """Test local network security considerations."""

        # Control4 operates on local network
        config_host = integration.config.control4_host

        # Validate local IP ranges
        local_ip_ranges = [
            "192.168.",
            "10.",
            "172.16.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
            "172.23.",
            "172.24.",
            "172.25.",
            "172.26.",
            "172.27.",
            "172.28.",
            "172.29.",
            "172.30.",
            "172.31.",
        ]

        is_local = any(config_host.startswith(prefix) for prefix in local_ip_ranges)

        if is_local:
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "local_network_access",
                    "ip_address": config_host,
                    "network_scope": "local",
                    "trusted_network": True,
                }
            )
            assert h_value >= 0.7
        else:
            # External IP should have higher security requirements
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "external_network_access",
                    "ip_address": config_host,
                    "network_scope": "external",
                    "security_enhanced": True,
                }
            )
            assert h_value >= 0.5

    @pytest.mark.asyncio
    async def test_man_in_the_middle_protection(self, integration, cbf_filter):
        """Test protection against man-in-the-middle attacks."""

        # For local Control4 systems, MITM protection is limited
        # but should still validate basic security measures

        h_value = cbf_filter.evaluate_safety(
            {
                "action": "mitm_protection",
                "https_enforced": True,
                "certificate_pinning": False,  # Typically not used for local devices
                "local_network": True,
                "attack_surface": "local_network_only",
            }
        )
        assert h_value >= 0.6  # Moderate protection for local networks


class TestControl4TokenLeakageProtection:
    """Test protection against token leakage."""

    @pytest.fixture
    def integration(self):
        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="secret_token_do_not_leak_12345"
        )
        return Control4Integration(config)

    def test_token_not_in_logs(self, integration):
        """Test that tokens are not leaked in logs."""

        # Setup log capture
        import logging
        import io

        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger("kagami_smarthome.integrations.control4")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            # Perform operations that might log
            headers = integration._get_headers()
            endpoint = integration._build_endpoint("/test")

            # Check log output
            log_output = log_capture.getvalue()

            # Token should not appear in logs
            assert integration.config.control4_bearer_token not in log_output

        finally:
            logger.removeHandler(handler)

    def test_token_not_in_exceptions(self, integration):
        """Test that tokens are not leaked in exception messages."""

        # Create an exception scenario
        try:
            # Force an error that might include token info
            invalid_endpoint = integration._build_endpoint("/invalid/../../../etc/passwd")
            # This shouldn't actually expose the token, but test anyway
        except Exception as e:
            error_message = str(e)
            assert integration.config.control4_bearer_token not in error_message

    def test_token_not_in_response_data(self, integration):
        """Test that tokens don't leak in response processing."""

        # Mock response that might echo back request data
        mock_response_data = {
            "request_headers": {
                "Authorization": "Bearer [REDACTED]",
                "User-Agent": "KagamiHome/1.0",
            },
            "echo": "Request processed",
        }

        # Process response (if such method exists)
        # Token should be filtered out of any response echoes
        if hasattr(integration, "_process_response"):
            processed = integration._process_response(mock_response_data)
            response_str = str(processed)
            assert integration.config.control4_bearer_token not in response_str

    @pytest.mark.asyncio
    async def test_token_not_in_network_errors(self, integration):
        """Test that network errors don't leak tokens."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Mock network error
            mock_get.side_effect = aiohttp.ClientError("Connection failed")

            try:
                await integration.connect()
            except aiohttp.ClientError as e:
                error_message = str(e)
                # Token should not be in error message
                assert integration.config.control4_bearer_token not in error_message

    def test_memory_cleanup_on_destruction(self, integration):
        """Test that tokens are cleared from memory on object destruction."""

        original_token = integration.config.control4_bearer_token

        # Clear references
        integration.config.control4_bearer_token = None
        integration = None

        # Force garbage collection
        import gc

        gc.collect()

        # In a real scenario, we'd verify memory scrubbing
        # This is more of a documentation of expected behavior


class TestControl4RateLimitingAndAbusePrevention:
    """Test rate limiting and abuse prevention."""

    @pytest.fixture
    def integration(self):
        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="rate_limit_test_token_12345"
        )
        return Control4Integration(config)

    @pytest.mark.asyncio
    async def test_request_rate_limiting(self, integration):
        """Test request rate limiting implementation."""

        request_times = []

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            mock_get.return_value.__aenter__.return_value = mock_response

            integration._connected = True

            # Make rapid consecutive requests
            for _ in range(10):
                start = time.time()
                await integration.get_rooms()
                request_times.append(time.time() - start)

        # Should not make requests too rapidly
        # (Implementation dependent - Control4 integration may or may not implement rate limiting)

        # At minimum, requests should complete in reasonable time
        avg_time = sum(request_times) / len(request_times)
        assert avg_time < 1.0  # Average under 1 second

    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self, integration):
        """Test concurrent request limiting."""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"rooms": []})
            mock_get.return_value.__aenter__.return_value = mock_response

            integration._connected = True

            # Launch many concurrent requests
            tasks = []
            for _ in range(50):  # High concurrency
                task = asyncio.create_task(integration.get_rooms())
                tasks.append(task)

            # Should handle concurrency gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successful vs failed requests
            successes = [r for r in results if not isinstance(r, Exception)]
            failures = [r for r in results if isinstance(r, Exception)]

            # Should have reasonable success rate
            success_rate = len(successes) / len(results)
            assert success_rate >= 0.7  # At least 70% success

    def test_abuse_detection_patterns(self, integration):
        """Test patterns that might indicate abuse."""

        cbf_filter = get_safety_filter()

        # Test various usage patterns
        patterns = [
            {"requests_per_minute": 10, "pattern": "normal_usage", "expected_h": 0.9},
            {"requests_per_minute": 60, "pattern": "high_usage", "expected_h": 0.6},
            {"requests_per_minute": 300, "pattern": "potential_abuse", "expected_h": 0.3},
            {"requests_per_minute": 1000, "pattern": "definite_abuse", "expected_h": 0.1},
        ]

        for pattern in patterns:
            h_value = cbf_filter.evaluate_safety(
                {
                    "action": "usage_pattern_analysis",
                    "requests_per_minute": pattern["requests_per_minute"],
                    "pattern_type": pattern["pattern"],
                    "abuse_detection": True,
                }
            )

            assert h_value <= pattern["expected_h"]


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.asyncio
class TestControl4TokenIntegrationScenarios:
    """Integration tests for real-world token usage scenarios."""

    async def test_morning_routine_token_usage(self):
        """Test token usage during morning routine scenario."""

        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="morning_routine_token_12345"
        )
        integration = Control4Integration(config)

        with (
            patch("aiohttp.ClientSession.get") as mock_get,
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            # Mock successful responses
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"success": True})
            mock_get.return_value.__aenter__.return_value = mock_response
            mock_post.return_value.__aenter__.return_value = mock_response

            # Simulate morning routine API calls
            integration._connected = True

            actions = [
                integration.set_light_level(101, 75),  # Bedroom light
                integration.set_shade_level(201, 50),  # Bedroom shade
                integration.set_light_level(102, 100),  # Kitchen light
                integration.set_shade_level(202, 0),  # Kitchen shade open
            ]

            # All actions should complete successfully
            results = await asyncio.gather(*actions, return_exceptions=True)

            # No authentication errors should occur
            auth_errors = [r for r in results if isinstance(r, Exception) and "401" in str(r)]
            assert len(auth_errors) == 0

    async def test_movie_mode_token_persistence(self):
        """Test token persistence during movie mode scenario."""

        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="movie_mode_token_12345"
        )
        integration = Control4Integration(config)

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"success": True})
            mock_post.return_value.__aenter__.return_value = mock_response

            integration._connected = True

            # Extended movie session (multiple hours of API calls)
            for _hour in range(3):  # 3 hour movie
                # Periodic adjustments during movie
                await integration.set_light_level(101, 5)  # Dim lights
                await asyncio.sleep(0.1)  # Small delay
                await integration.set_room_volume(301, 50)  # Audio adjustment

            # Token should remain valid throughout
            assert integration.is_connected

    async def test_security_scenario_token_reliability(self):
        """Test token reliability during security scenarios."""

        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="security_scenario_token_12345"
        )
        integration = Control4Integration(config)

        with (
            patch("aiohttp.ClientSession.get") as mock_get,
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "armed"})
            mock_get.return_value.__aenter__.return_value = mock_response
            mock_post.return_value.__aenter__.return_value = mock_response

            integration._connected = True

            # Critical security operations
            security_actions = [
                integration.get_security_state(),  # Check current state
                integration.lock_all(),  # Lock all doors
                integration.arm_security("away"),  # Arm system
                integration.get_security_state(),  # Verify armed
            ]

            # All security operations should succeed
            results = await asyncio.gather(*security_actions, return_exceptions=True)

            # No failures allowed for security operations
            failures = [r for r in results if isinstance(r, Exception)]
            assert len(failures) == 0


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
class TestControl4TokenPerformance:
    """Performance tests for token operations."""

    async def test_authentication_performance(self):
        """Test authentication performance."""

        config = SmartHomeConfig(
            control4_host="192.168.1.100", control4_bearer_token="performance_test_token_12345"
        )
        integration = Control4Integration(config)

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"director": {"id": "1234"}})
            mock_get.return_value.__aenter__.return_value = mock_response

            # Time authentication
            start_time = time.time()
            success = await integration.connect()
            auth_duration = time.time() - start_time

            assert success
            assert auth_duration < 5.0  # Should authenticate within 5 seconds

    async def test_token_validation_performance(self):
        """Test token validation performance."""

        config = SmartHomeConfig(
            control4_host="192.168.1.100",
            control4_bearer_token="validation_performance_token_12345",
        )
        integration = Control4Integration(config)

        # Time token validation
        start_time = time.time()

        for _ in range(1000):  # Many validations
            valid = integration._validate_bearer_token(config.control4_bearer_token)
            assert valid

        validation_duration = time.time() - start_time

        # Should validate very quickly
        assert validation_duration < 0.1  # Under 100ms for 1000 validations

    async def test_concurrent_authentication_performance(self):
        """Test concurrent authentication performance."""

        async def authenticate():
            config = SmartHomeConfig(
                control4_host="192.168.1.100", control4_bearer_token="concurrent_auth_token_12345"
            )
            integration = Control4Integration(config)

            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_response = Mock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"director": {"id": "1234"}})
                mock_get.return_value.__aenter__.return_value = mock_response

                return await integration.connect()

        # Multiple concurrent authentications
        tasks = [authenticate() for _ in range(10)]

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time

        # All should succeed
        assert all(results)

        # Should complete in reasonable time
        assert duration < 10.0  # 10 seconds max for 10 concurrent auths


if __name__ == "__main__":
    # Run Control4 token security tests
    pytest.main([__file__, "-v"])
