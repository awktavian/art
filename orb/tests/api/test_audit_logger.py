"""Comprehensive tests for audit logging decorators and functionality.

Tests that audit events are properly logged with correct type, severity, and context.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import json
from unittest.mock import MagicMock, patch

from fastapi import Request

from kagami_api.audit_logger import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
    audit_file_operation,
    audit_login_failure,
    audit_login_success,
    audit_permission_denied,
    audit_privileged_operation,
    audit_rate_limit_exceeded,
    get_audit_logger,
)


class TestAuditEvent:
    """Test AuditEvent class."""

    def test_audit_event_initialization(self) -> None:
        """Test AuditEvent initialization with all parameters."""
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user123",
            client_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            severity=AuditSeverity.MEDIUM,
            details={"method": "password"},
            outcome="success",
            resource="/api/login",
            request_id="req-123",
        )

        assert event.event_type == AuditEventType.LOGIN_SUCCESS
        assert event.user_id == "user123"
        assert event.client_ip == "192.168.1.1"
        assert event.user_agent == "TestAgent/1.0"
        assert event.severity == AuditSeverity.MEDIUM
        assert event.details == {"method": "password"}
        assert event.outcome == "success"
        assert event.resource == "/api/login"
        assert event.request_id == "req-123"
        assert event.timestamp.endswith("Z")

    def test_audit_event_minimal_initialization(self) -> None:
        """Test AuditEvent with minimal parameters."""
        event = AuditEvent(event_type=AuditEventType.FILE_ACCESS)

        assert event.event_type == AuditEventType.FILE_ACCESS
        assert event.user_id is None
        assert event.severity == AuditSeverity.LOW
        assert event.details == {}
        assert event.outcome == "unknown"

    def test_audit_event_to_dict(self) -> None:
        """Test converting AuditEvent to dictionary."""
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            user_id="user456",
            severity=AuditSeverity.HIGH,
        )

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == AuditEventType.ACCESS_DENIED
        assert event_dict["user_id"] == "user456"
        assert event_dict["severity"] == AuditSeverity.HIGH
        assert "timestamp" in event_dict

    def test_audit_event_to_json(self) -> None:
        """Test converting AuditEvent to JSON."""
        event = AuditEvent(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            details={"limit": 100, "requests": 150},
        )

        event_json = event.to_json()
        parsed = json.loads(event_json)

        assert parsed["event_type"] == AuditEventType.RATE_LIMIT_EXCEEDED
        assert parsed["details"]["limit"] == 100
        assert parsed["details"]["requests"] == 150


class TestAuditLogger:
    """Test AuditLogger class."""

    @pytest.fixture
    def audit_logger(self):
        """Create AuditLogger instance."""
        return AuditLogger()

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.headers = {
            "X-Real-IP": "10.0.0.1",
            "User-Agent": "TestBrowser/2.0",
            "X-Request-ID": "req-abc-123",
        }
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        request.state.request_id = None
        return request

    def test_log_event(self, audit_logger) -> None:
        """Test logging an audit event."""
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user123",
        )

        with patch.object(audit_logger.logger, "info") as mock_info:
            audit_logger.log_event(event)

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            # Check the string representation of the enum value
            assert "LOGIN_SUCCESS" in call_args[0][0]
            assert call_args[1]["extra"]["event_type"] == AuditEventType.LOGIN_SUCCESS
            assert call_args[1]["extra"]["user_id"] == "user123"

    def test_log_event_with_debug(self, audit_logger) -> None:
        """Test logging includes debug output when enabled."""
        event = AuditEvent(event_type=AuditEventType.FILE_DELETION)

        with patch.object(audit_logger.logger, "isEnabledFor", return_value=True):
            with patch.object(audit_logger.logger, "info") as mock_info:
                with patch.object(audit_logger.logger, "debug") as mock_debug:
                    audit_logger.log_event(event)

                    mock_info.assert_called_once()
                    mock_debug.assert_called_once()
                    assert "Audit Event:" in mock_debug.call_args[0][0]

    def test_log_authentication_success(self, audit_logger, mock_request) -> None:
        """Test logging successful authentication."""
        # Debug: Check the mock request
        assert mock_request.headers.get("X-Real-IP") == "10.0.0.1"

        with patch.object(audit_logger, "log_event") as mock_log:
            audit_logger.log_authentication(
                AuditEventType.LOGIN_SUCCESS,
                "user123",
                mock_request,
                "success",
                {"method": "oauth"},
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == AuditEventType.LOGIN_SUCCESS
            assert event.user_id == "user123"
            assert event.severity == AuditSeverity.MEDIUM
            assert event.outcome == "success"
            assert event.details == {"method": "oauth"}
            # Client IP should be extracted from the request headers
            assert event.client_ip == "10.0.0.1"

    def test_log_authentication_failure(self, audit_logger, mock_request) -> None:
        """Test logging failed authentication."""
        with patch.object(audit_logger, "log_event") as mock_log:
            audit_logger.log_authentication(
                AuditEventType.LOGIN_FAILURE,
                "user123",
                mock_request,
                "failure",
                {"reason": "invalid_password"},
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.severity == AuditSeverity.HIGH  # Higher for failures
            assert event.outcome == "failure"

    def test_log_authorization_denied(self, audit_logger, mock_request) -> None:
        """Test logging authorization denial."""
        with patch.object(audit_logger, "log_event") as mock_log:
            audit_logger.log_authorization(
                AuditEventType.ACCESS_DENIED,
                "user123",
                "/admin/users",
                "admin.users.write",
                mock_request,
                "denied",
                {"action": "delete_user"},
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == AuditEventType.ACCESS_DENIED
            assert event.resource == "/admin/users"
            assert event.severity == AuditSeverity.HIGH
            assert event.details["required_permission"] == "admin.users.write"
            assert event.details["action"] == "delete_user"

    def test_log_authorization_granted(self, audit_logger) -> None:
        """Test logging authorization granted."""
        with patch.object(audit_logger, "log_event") as mock_log:
            audit_logger.log_authorization(
                AuditEventType.ACCESS_GRANTED,
                "user123",
                "/api/data",
                "data.read",
                None,
                "granted",
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.severity == AuditSeverity.LOW  # Lower for granted

    def test_log_security_event(self, audit_logger, mock_request) -> None:
        """Test logging security event."""
        with patch.object(audit_logger, "log_event") as mock_log:
            audit_logger.log_security_event(
                AuditEventType.SQL_INJECTION_ATTEMPT,
                AuditSeverity.CRITICAL,
                None,
                mock_request,
                "blocked",
                {"query": "'; DROP TABLE users; --"},
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == AuditEventType.SQL_INJECTION_ATTEMPT
            assert event.severity == AuditSeverity.CRITICAL
            assert event.outcome == "blocked"

    def test_log_system_event(self, audit_logger) -> None:
        """Test logging system event."""
        with patch.object(audit_logger, "log_event") as mock_log:
            audit_logger.log_system_event(
                AuditEventType.DATABASE_MIGRATION,
                "admin",
                "database",
                None,
                "success",
                {"version": "v2.0"},
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == AuditEventType.DATABASE_MIGRATION
            assert event.user_id == "admin"
            assert event.resource == "database"
            assert event.severity == AuditSeverity.MEDIUM

    def test_get_client_ip_from_real_ip(self, audit_logger, mock_request) -> None:
        """Test extracting client IP from X-Real-IP header."""
        client_ip = audit_logger._get_client_ip(mock_request)
        assert client_ip == "10.0.0.1"

    def test_get_client_ip_from_forwarded(self, audit_logger) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = None

        client_ip = audit_logger._get_client_ip(request)
        assert client_ip == "192.168.1.1"

    def test_get_client_ip_fallback(self, audit_logger) -> None:
        """Test client IP fallback to direct connection."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "172.16.0.1"

        client_ip = audit_logger._get_client_ip(request)
        assert client_ip == "172.16.0.1"

    def test_get_user_agent(self, audit_logger, mock_request) -> None:
        """Test extracting user agent."""
        user_agent = audit_logger._get_user_agent(mock_request)
        assert user_agent == "TestBrowser/2.0"

    def test_get_request_id_from_header(self, audit_logger, mock_request) -> None:
        """Test extracting request ID from header."""
        request_id = audit_logger._get_request_id(mock_request)
        assert request_id == "req-abc-123"

    def test_get_request_id_from_state(self, audit_logger) -> None:
        """Test extracting request ID from request state."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()
        request.state.request_id = "state-req-456"

        request_id = audit_logger._get_request_id(request)
        assert request_id == "state-req-456"


class TestAuditConvenienceFunctions:
    """Test convenience audit functions."""

    def test_audit_login_success(self) -> None:
        """Test audit_login_success convenience function."""
        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            audit_login_success("user123", None, {"session": "abc"})

            mock_logger.log_authentication.assert_called_once_with(
                AuditEventType.LOGIN_SUCCESS,
                "user123",
                None,
                "success",
                {"session": "abc"},
            )

    def test_audit_login_failure(self) -> None:
        """Test audit_login_failure convenience function."""
        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            audit_login_failure("user123", None, {"attempts": 3})

            mock_logger.log_authentication.assert_called_once_with(
                AuditEventType.LOGIN_FAILURE,
                "user123",
                None,
                "failure",
                {"attempts": 3},
            )

    def test_audit_permission_denied(self) -> None:
        """Test audit_permission_denied convenience function."""
        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            audit_permission_denied(
                "user123",
                "/admin",
                "admin.access",
                None,
                {"role": "user"},
            )

            mock_logger.log_authorization.assert_called_once_with(
                AuditEventType.ACCESS_DENIED,
                "user123",
                "/admin",
                "admin.access",
                None,
                "denied",
                {"role": "user"},
            )

    def test_audit_rate_limit_exceeded(self) -> None:
        """Test audit_rate_limit_exceeded convenience function."""
        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            audit_rate_limit_exceeded("user123", None, {"limit": 100})

            mock_logger.log_security_event.assert_called_once_with(
                AuditEventType.RATE_LIMIT_EXCEEDED,
                AuditSeverity.MEDIUM,
                "user123",
                None,
                "blocked",
                {"limit": 100},
            )

    def test_get_audit_logger_singleton(self) -> None:
        """Test that get_audit_logger returns singleton."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2


class TestAuditDecorators:
    """Test audit logging decorators."""

    @pytest.mark.asyncio
    async def test_audit_privileged_operation_async_success(self) -> None:
        """Test audit decorator on successful async function."""

        @audit_privileged_operation(
            AuditEventType.ADMIN_USER_CREATE,
            AuditSeverity.HIGH,
            resource_param="username",
        )
        async def create_user(username, current_user=None, request=None):
            return {"id": "123", "username": username}

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            result = await create_user(
                "newuser",
                current_user={"id": "admin123"},
                request=None,
            )

            assert result["username"] == "newuser"
            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.event_type == AuditEventType.ADMIN_USER_CREATE
            assert event.user_id == "admin123"
            assert event.severity == AuditSeverity.HIGH
            assert event.outcome == "success"
            assert event.resource == "newuser"

    @pytest.mark.asyncio
    async def test_audit_privileged_operation_async_failure(self) -> None:
        """Test audit decorator on failed async function."""

        @audit_privileged_operation(AuditEventType.ADMIN_USER_DELETE)
        async def delete_user(user_id: str, current_user: dict[str, str] | None = None) -> None:
            raise ValueError("User not found")

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            with pytest.raises(ValueError):
                await delete_user("user456", current_user={"id": "admin123"})

            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.event_type == AuditEventType.ADMIN_USER_DELETE
            assert event.severity == AuditSeverity.CRITICAL  # Elevated for failure
            assert event.outcome == "failure"
            assert "User not found" in event.details["error"]

    def test_audit_privileged_operation_sync_success(self) -> None:
        """Test audit decorator on successful sync function."""

        @audit_privileged_operation(
            AuditEventType.CONFIGURATION_CHANGE,
            AuditSeverity.MEDIUM,
            resource_param="config_key",
        )
        def update_config(
            config_key: str, value: Any, current_user: dict[str, str] | None = None
        ) -> Any:
            return {"key": config_key, "value": value}

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            result = update_config(
                "max_connections",
                100,
                current_user={"id": "admin456"},
            )

            assert result["key"] == "max_connections"
            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.resource == "max_connections"
            assert event.outcome == "success"

    def test_audit_privileged_operation_sync_failure(self) -> None:
        """Test audit decorator on failed sync function."""

        @audit_privileged_operation(AuditEventType.ADMIN_BACKUP)
        def create_backup():
            raise OSError("Disk full")

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            with pytest.raises(IOError):
                create_backup()

            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.outcome == "failure"
            assert "Disk full" in event.details["error"]

    @pytest.mark.asyncio
    async def test_audit_file_operation_access(self) -> None:
        """Test file operation decorator for access."""

        @audit_file_operation("access")
        async def read_file(path: str) -> str:
            return f"Contents of {path}"

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            result = await read_file("/etc/config.json")

            assert "Contents of /etc/config.json" in result
            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.event_type == AuditEventType.FILE_ACCESS
            assert event.severity == AuditSeverity.MEDIUM
            assert event.resource == "/etc/config.json"

    @pytest.mark.asyncio
    async def test_audit_file_operation_deletion(self) -> None:
        """Test file operation decorator for deletion."""

        @audit_file_operation("deletion")
        async def delete_file(path: str, current_user: dict[str, str] | None = None) -> bool:
            return True

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            result = await delete_file(
                "/tmp/temp.txt",
                current_user={"id": "user789"},
            )

            assert result is True
            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.event_type == AuditEventType.FILE_DELETION
            assert event.severity == AuditSeverity.HIGH  # Higher for deletion
            assert event.resource == "/tmp/temp.txt"
            assert event.user_id == "user789"

    @pytest.mark.asyncio
    async def test_audit_file_operation_modification(self) -> None:
        """Test file operation decorator for modification."""

        @audit_file_operation("modification")
        async def write_file(path: str, content: str) -> int:
            return len(content)

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            result = await write_file("/data/output.txt", "test content")

            assert result == 12
            mock_logger.log_event.assert_called_once()

            event = mock_logger.log_event.call_args[0][0]
            assert event.event_type == AuditEventType.FILE_MODIFICATION
            assert event.severity == AuditSeverity.MEDIUM

    def test_decorator_preserves_function_metadata(self) -> None:
        """Test that decorators preserve function metadata."""

        @audit_privileged_operation(AuditEventType.ADMIN_USER_CREATE)
        async def my_function():
            """This is my function."""

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."

    @pytest.mark.asyncio
    async def test_decorator_without_user_context(self) -> None:
        """Test decorator behavior without user context."""

        @audit_privileged_operation(AuditEventType.SYSTEM_COMMAND)
        async def run_command(cmd: str) -> str:
            return f"Executed: {cmd}"

        with patch("kagami_api.audit_logger.get_audit_logger") as mock_get:
            mock_logger = MagicMock()
            mock_get.return_value = mock_logger

            result = await run_command("ls -la")

            assert result == "Executed: ls -la"

            event = mock_logger.log_event.call_args[0][0]
            assert event.user_id == "system"  # Defaults to "system"
