"""Audit logging for K os security events.

This module provides comprehensive audit logging for security-related events
including authentication, authorization, and sensitive operations.
"""

import json
import logging
import re
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import Request

logger = logging.getLogger("kagami.audit")


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    TOKEN_REFRESH = "auth.token.refresh"

    # Authorization events
    ACCESS_GRANTED = "authz.access.granted"
    ACCESS_DENIED = "authz.access.denied"

    # Rate limiting events
    RATE_LIMIT_EXCEEDED = "rate.limit.exceeded"

    # File system events
    FILE_ACCESS = "file.access"
    FILE_MODIFICATION = "file.modification"
    FILE_DELETION = "file.deletion"

    # Admin operations
    ADMIN_ROLE_CHANGE = "admin.role.change"

    # Business app events
    APP_SETTINGS_CHANGE = "app.settings.change"

    # Security events
    SQL_INJECTION_ATTEMPT = "security.sql_injection"
    SYSTEM_COMMAND = "system.command"

    # System events
    DATABASE_MIGRATION = "system.database.migration"
    CONFIGURATION_CHANGE = "system.config.change"

    # Admin events
    ADMIN_USER_CREATE = "admin.user.create"
    ADMIN_USER_DELETE = "admin.user.delete"
    ADMIN_BACKUP = "admin.backup"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEvent:
    """Represents an audit event."""

    def __init__(
        self,
        event_type: AuditEventType,
        user_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        severity: AuditSeverity = AuditSeverity.LOW,
        details: dict[str, Any] | None = None,
        outcome: str = "unknown",
        resource: str | None = None,
        request_id: str | None = None,
    ):
        """Initialize an audit event.

        Args:
            event_type: Type of audit event
            user_id: User identifier (if authenticated)
            client_ip: Client IP address
            user_agent: Client user agent
            severity: Event severity level
            details: Additional event details
            outcome: Event outcome (success, failure, denied, etc.)
            resource: Resource being accessed/modified
            request_id: Request ID for correlation
        """
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.event_type = event_type
        self.user_id = user_id
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.severity = severity
        self.details = details or {}
        self.outcome = outcome
        self.resource = resource
        self.request_id = request_id

    def to_dict(self) -> dict[str, Any]:
        """Convert audit event to dictionary.

        Returns:
            Dictionary representation of the audit event
        """
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "severity": self.severity,
            "outcome": self.outcome,
            "resource": self.resource,
            "request_id": self.request_id,
            "details": self.details,
        }

    def to_json(self) -> str:
        """Convert audit event to JSON string.

        Returns:
            JSON representation of the audit event
        """
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Centralized audit logging system."""

    def __init__(self) -> None:
        """Initialize the audit logger."""
        self.logger = logger
        # Keep a bounded in-memory buffer for SIEM export (best-effort)
        # This avoids persistence complexity while enabling enterprise exports.
        self._buffer_max = 10000
        self._buffer: deque[dict[str, Any]] = deque(maxlen=self._buffer_max)
        # Precompile scrubbing patterns for sensitive data
        self._sensitive_key_names: set[str] = {
            "authorization",
            "api_key",
            "apikey",
            "token",
            "password",
            "passwd",
            "secret",
            "session",
            "sessionid",
            "cookie",
            "bearer",
        }
        self._scrub_patterns: list[tuple[re.Pattern[str], str]] = [
            (
                re.compile(
                    r"(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~\+\/=]+)",
                    re.IGNORECASE,
                ),
                r"\1[REDACTED]",
            ),
            (
                re.compile(r"(api[_-]?key\s*[=:]\s*)([^\s,]+)", re.IGNORECASE),
                r"\1[REDACTED]",
            ),
            (
                re.compile(
                    r"(secret|token|password|passwd|sessionid)\s*[=:]\s*([^\s,]+)",
                    re.IGNORECASE,
                ),
                r"\1=[REDACTED]",
            ),
        ]

    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        Args:
            event: Audit event to log
        """
        # Scrub sensitive fields before emitting/logging
        try:
            event_dict_sanitized = self._scrub_event(event.to_dict())
        except Exception:
            event_dict_sanitized = event.to_dict()

        # Log to structured JSON format (extras are sanitized)
        self.logger.info(
            f"AUDIT: {event.event_type}",
            extra={
                "audit_event": event_dict_sanitized,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "client_ip": event.client_ip,
                "severity": event.severity,
                "outcome": event.outcome,
            },
        )

        # Also log human-readable format for debugging
        if self.logger.isEnabledFor(logging.DEBUG):
            try:
                self.logger.debug(f"Audit Event: {json.dumps(event_dict_sanitized, default=str)}")
            except Exception:
                self.logger.debug(f"Audit Event: {event.to_json()}")

        # Store in ring buffer for SIEM export if enabled by admin settings
        try:
            self._buffer.append(event_dict_sanitized)
        except Exception as e:
            self.logger.debug("Failed to buffer event: %s", e)

    def _scrub_event(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return a deep-scrubbed copy of an audit event dict.

        - Redacts values under sensitive keys (case-insensitive)
        - Applies regex-based redaction to any string content
        - Ensures excessively large fields are truncated
        """

        def _scrub_value(key: str | None, value: Any) -> Any:
            try:
                key_lower = (key or "").lower()
                # If key indicates sensitive content, redact fully
                if key_lower in self._sensitive_key_names:
                    return "[REDACTED]"
                # Recurse into mappings
                if isinstance(value, dict):
                    return {k: _scrub_value(k, v) for k, v in value.items()}
                # Recurse into sequences (but not strings/bytes)
                if isinstance(value, list):
                    return [_scrub_value(None, v) for v in value]
                if isinstance(value, tuple):
                    return tuple(_scrub_value(None, v) for v in value)
                # Scrub strings using regex patterns
                if isinstance(value, str):
                    scrubbed = value
                    for rx, repl in self._scrub_patterns:
                        try:
                            scrubbed = rx.sub(repl, scrubbed)
                        except Exception:
                            continue  # Skip failed pattern, try next
                    # Truncate extremely long strings to avoid log bloat
                    if len(scrubbed) > 4096:
                        return scrubbed[:4096] + "…"
                    return scrubbed
                return value
            except Exception:
                return "[REDACTED]"

        # Work on a shallow copy then deep-process values
        result: dict[str, Any] = {}
        for k, v in data.items():
            result[k] = _scrub_value(k, v)
        return result

    def get_recent_events(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Return up to `limit` most recent audit events.

        This powers the SIEM export endpoint. It is best-effort and in-memory only.
        """
        try:
            if limit <= 0:
                return []
            # Convert to list in time order (oldest..newest), then slice to most recent
            data = list(self._buffer)
            if len(data) <= limit:
                return data
            return data[-limit:]
        except Exception:
            return []

    def log_authentication(
        self,
        event_type: AuditEventType,
        user_id: str | None,
        request: Request | None = None,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log authentication-related events.

        Args:
            event_type: Type of authentication event
            user_id: User identifier
            request: FastAPI request object
            outcome: Event outcome
            details: Additional details
        """
        severity = AuditSeverity.HIGH if outcome == "failure" else AuditSeverity.MEDIUM

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            client_ip=self._get_client_ip(request) if request else None,
            user_agent=self._get_user_agent(request) if request else None,
            severity=severity,
            outcome=outcome,
            details=details or {},
            request_id=self._get_request_id(request) if request else None,
        )

        self.log_event(event)

    def log_authorization(
        self,
        event_type: AuditEventType,
        user_id: str,
        resource: str,
        required_permission: str | None = None,
        request: Request | None = None,
        outcome: str = "denied",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log authorization-related events.

        Args:
            event_type: Type of authorization event
            user_id: User identifier
            resource: Resource being accessed
            required_permission: Required permission
            request: FastAPI request object
            outcome: Event outcome
            details: Additional details
        """
        severity = AuditSeverity.HIGH if outcome == "denied" else AuditSeverity.LOW

        audit_details = details or {}
        if required_permission:
            audit_details["required_permission"] = required_permission

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            client_ip=self._get_client_ip(request) if request else None,
            user_agent=self._get_user_agent(request) if request else None,
            severity=severity,
            outcome=outcome,
            resource=resource,
            details=audit_details,
            request_id=self._get_request_id(request) if request else None,
        )

        self.log_event(event)

    def log_security_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        user_id: str | None = None,
        request: Request | None = None,
        outcome: str = "blocked",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log security-related events.

        Args:
            event_type: Type of security event
            severity: Event severity
            user_id: User identifier (if known)
            request: FastAPI request object
            outcome: Event outcome
            details: Additional details
        """
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            client_ip=self._get_client_ip(request) if request else None,
            user_agent=self._get_user_agent(request) if request else None,
            severity=severity,
            outcome=outcome,
            details=details or {},
            request_id=self._get_request_id(request) if request else None,
        )

        self.log_event(event)

    def log_system_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        resource: str | None = None,
        request: Request | None = None,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log system operation events.

        Args:
            event_type: Type of system event
            user_id: User identifier
            resource: Resource being accessed/modified
            request: FastAPI request object
            outcome: Event outcome
            details: Additional details
        """
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            client_ip=self._get_client_ip(request) if request else None,
            user_agent=self._get_user_agent(request) if request else None,
            severity=AuditSeverity.MEDIUM,
            outcome=outcome,
            resource=resource,
            details=details or {},
            request_id=self._get_request_id(request) if request else None,
        )

        self.log_event(event)

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP from request.

        Args:
            request: FastAPI request object

        Returns:
            Client IP address
        """
        # Check for real IP in headers (proxy scenarios)
        real_ip = (
            request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        )

        if real_ip:
            return str(real_ip)

        # Fallback to direct client IP
        return str(getattr(request.client, "host", None)) if request.client else None

    def _get_user_agent(self, request: Request) -> str | None:
        """Extract user agent from request.

        Args:
            request: FastAPI request object

        Returns:
            User agent string
        """
        ua = request.headers.get("User-Agent")
        return str(ua) if ua is not None else None

    def _get_request_id(self, request: Request) -> str | None:
        """Extract request ID from request.

        Args:
            request: FastAPI request object

        Returns:
            Request ID if available
        """
        rid = request.headers.get("X-Request-ID")
        return rid if rid is not None else getattr(request.state, "request_id", None)


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.

    Returns:
        The global AuditLogger instance
    """
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger()

    return _audit_logger


def audit_event(
    event_type: AuditEventType,
    user_id: str | None = None,
    severity: AuditSeverity = AuditSeverity.MEDIUM,
    details: dict[str, Any] | None = None,
    client_ip: str | None = None,
) -> None:
    """Convenience function to log an audit event.

    Args:
        event_type: Type of audit event
        user_id: User ID associated with the event
        severity: Severity level of the event
        details: Additional details about the event
        client_ip: Client IP address if available
    """
    logger = get_audit_logger()
    event = AuditEvent(
        event_type=event_type,
        user_id=user_id,
        severity=severity,
        details=details or {},
        client_ip=client_ip,
    )
    logger.log_event(event)


# Convenience functions for common audit events
def audit_login_success(  # type: ignore[no-untyped-def]
    user_id: str, request: Request | None = None, details: dict[str, Any] | None = None
):
    """Log successful login."""
    get_audit_logger().log_authentication(
        AuditEventType.LOGIN_SUCCESS, user_id, request, "success", details
    )


def audit_login_failure(  # type: ignore[no-untyped-def]
    user_id: str, request: Request | None = None, details: dict[str, Any] | None = None
):
    """Log failed login."""
    get_audit_logger().log_authentication(
        AuditEventType.LOGIN_FAILURE, user_id, request, "failure", details
    )


def audit_permission_denied(  # type: ignore[no-untyped-def]
    user_id: str,
    resource: str,
    permission: str,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
):
    """Log permission denied."""
    get_audit_logger().log_authorization(
        AuditEventType.ACCESS_DENIED,
        user_id,
        resource,
        permission,
        request,
        "denied",
        details,
    )


def audit_rate_limit_exceeded(  # type: ignore[no-untyped-def]
    user_id: str | None,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
):
    """Log rate limit exceeded."""
    get_audit_logger().log_security_event(
        AuditEventType.RATE_LIMIT_EXCEEDED,
        AuditSeverity.MEDIUM,
        user_id,
        request,
        "blocked",
        details,
    )


# Export all audit functions
__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditLogger",
    "AuditSeverity",
    "audit_event",
    "audit_file_operation",
    "audit_login_failure",
    "audit_login_success",
    "audit_permission_denied",
    "audit_privileged_operation",
    "audit_rate_limit_exceeded",
    "get_audit_logger",
]

import functools
import inspect


def audit_privileged_operation(  # type: ignore[no-untyped-def]
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.MEDIUM,
    resource_param: str | None = None,
):
    """Decorator to audit privileged operations."""

    def decorator(func):  # type: ignore[no-untyped-def]
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            # Extract user_id from args/kwargs if available
            # Expecting current_user={"id": ...} or similar
            bound_args = inspect.signature(func).bind(*args, **kwargs)
            bound_args.apply_defaults()

            current_user = bound_args.arguments.get("current_user")
            user_id = "system"
            if isinstance(current_user, dict):
                user_id = current_user.get("id", "system")

            request = bound_args.arguments.get("request")

            resource = None
            if resource_param and resource_param in bound_args.arguments:
                resource = str(bound_args.arguments[resource_param])

            try:
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                get_audit_logger().log_event(
                    AuditEvent(
                        event_type=event_type,
                        user_id=user_id,
                        severity=severity,
                        outcome="success",
                        resource=resource,
                        request_id=getattr(request, "state", None)
                        and getattr(request.state, "request_id", None),  # type: ignore[union-attr]
                    )
                )
                return result
            except Exception as e:
                get_audit_logger().log_event(
                    AuditEvent(
                        event_type=event_type,
                        user_id=user_id,
                        severity=AuditSeverity.CRITICAL,  # Elevate to CRITICAL on failure
                        outcome="failure",
                        resource=resource,
                        details={"error": str(e)},
                    )
                )
                raise e

        # Handle sync functions too (if needed, though logic above tries to handle both)
        # But the wrapper is defined as async. The test uses it on sync functions too?
        # "test_audit_privileged_operation_sync_success" uses it on a sync function.
        # So the wrapper must be intelligent or we need two wrappers.

        if inspect.iscoroutinefunction(func):
            return wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                bound_args = inspect.signature(func).bind(*args, **kwargs)
                bound_args.apply_defaults()

                current_user = bound_args.arguments.get("current_user")
                user_id = "system"
                if isinstance(current_user, dict):
                    user_id = current_user.get("id", "system")

                bound_args.arguments.get("request")

                resource = None
                if resource_param and resource_param in bound_args.arguments:
                    resource = str(bound_args.arguments[resource_param])

                try:
                    result = func(*args, **kwargs)
                    get_audit_logger().log_event(
                        AuditEvent(
                            event_type=event_type,
                            user_id=user_id,
                            severity=severity,
                            outcome="success",
                            resource=resource,
                        )
                    )
                    return result
                except Exception as e:
                    get_audit_logger().log_event(
                        AuditEvent(
                            event_type=event_type,
                            user_id=user_id,
                            severity=severity,
                            outcome="failure",
                            resource=resource,
                            details={"error": str(e)},
                        )
                    )
                    raise e

            return sync_wrapper

    return decorator


def audit_file_operation(operation_type: str) -> None:
    """Decorator to audit file operations."""
    # Map string operation to EventType and Severity
    mapping = {
        "access": (AuditEventType.FILE_ACCESS, AuditSeverity.MEDIUM),
        "modification": (AuditEventType.FILE_MODIFICATION, AuditSeverity.MEDIUM),
        "deletion": (AuditEventType.FILE_DELETION, AuditSeverity.HIGH),
    }

    event_type, default_severity = mapping.get(
        operation_type, (AuditEventType.FILE_ACCESS, AuditSeverity.LOW)
    )

    def decorator(func):  # type: ignore[no-untyped-def]
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound_args = inspect.signature(func).bind(*args, **kwargs)
            bound_args.apply_defaults()

            path = bound_args.arguments.get("path")
            current_user = bound_args.arguments.get("current_user")
            user_id = "system"
            if isinstance(current_user, dict):
                user_id = current_user.get("id", "system")

            try:
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                get_audit_logger().log_event(
                    AuditEvent(
                        event_type=event_type,
                        user_id=user_id,
                        severity=default_severity,
                        resource=path,
                        outcome="success",
                    )
                )
                return result
            except Exception as e:
                get_audit_logger().log_event(
                    AuditEvent(
                        event_type=event_type,
                        user_id=user_id,
                        severity=AuditSeverity.HIGH,
                        resource=path,
                        outcome="failure",
                        details={"error": str(e)},
                    )
                )
                raise e

        return wrapper

    return decorator  # type: ignore[return-value]
