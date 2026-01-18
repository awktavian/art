"""Comprehensive Logging Framework for Production-Ready Instrumentation.

This module provides structured logging with:
- **Context Propagation**: Request/trace IDs flow through async operations
- **Performance Tracking**: Automatic timing and memory metrics
- **Security Audit Logging**: Dedicated logging for auth and sensitive ops
- **Structured Output**: JSON formatting for log aggregation systems

Architecture:
    Application Code → ComprehensiveLogger → StructuredFormatter → Handlers

    Context (LogContext):
    - request_id: Unique ID for request tracking
    - user_id: User making the request
    - trace_id: Distributed tracing support
    - Flows via contextvars (async-safe)

Performance Tracking:
    - Automatic timing with performance_context()
    - Memory delta measurement (requires psutil)
    - Metrics emission to observability systems

Security Logging:
    - Dedicated audit trail for auth events
    - Authentication attempts (success/failure)
    - Authorization checks (granted/denied)
    - Sensitive operations (PII access, etc.)
    - Security violations (attack attempts)

Usage:
    # Get a logger for your module
    logger = get_logger(__name__)
    logger.info("Processing started", task_id="123")

    # Set context for a request
    with log_context(LogContext(user_id="user123")):
        logger.info("User action")  # Includes user_id

    # Track performance
    with logger.performance_context("api_call"):
        response = await client.get(url)

    # Security audit
    security = get_security_logger()
    security.log_authentication_attempt("user@example.com", True)

Components:
    - LogContext: Request/trace context (dataclass)
    - PerformanceMetrics: Timing/memory metrics (dataclass)
    - StructuredFormatter: JSON log formatter
    - SecurityAuditLogger: Security event logger
    - ComprehensiveLogger: Main logger class
    - get_logger(): Factory function
    - log_context(): Context manager
"""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
# Core Python modules for logging infrastructure.
import contextvars  # Async-safe context propagation
import json  # Structured log serialization
import logging  # Python's standard logging framework
import logging.handlers  # RotatingFileHandler for log rotation
import sys  # stdout for console handler
import threading  # Thread-safe logger singleton
import time  # Performance timing
import uuid  # Unique tracking IDs
from collections.abc import Generator  # Type hints for generators
from contextlib import contextmanager  # Context manager decorator
from dataclasses import dataclass, field  # Clean data structures
from pathlib import Path  # Cross-platform file paths
from typing import Any  # Generic type hints

# =============================================================================
# CONTEXT VARIABLE FOR REQUEST/OPERATION TRACKING
# =============================================================================
# Uses contextvars for async-safe context propagation. This allows request
# context (user_id, trace_id, etc.) to automatically flow through async
# operations without manual passing.
#
# Why contextvars over threading.local?
# - Works correctly with asyncio (threading.local doesn't)
# - Automatically propagates to child tasks
# - Explicit copy semantics for task spawning
#
# Usage:
#   _request_context.set({"user_id": "123", "trace_id": "abc"})
#   # ... in any function in this async context ...
#   ctx = _request_context.get()  # Gets {"user_id": "123", ...}

_request_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "request_context", default=None
)


# =============================================================================
# LOG CONTEXT
# =============================================================================
# Dataclass for request-scoped context that flows through async operations.
# Fields like user_id, trace_id, and correlation_id are automatically
# included in all log messages when set.


@dataclass
class LogContext:
    """Enhanced logging context with request/trace tracking.

    Captures request-scoped information that should be included
    in all log messages within an operation.

    Attributes:
        request_id: Unique ID for this request/operation.
        user_id: ID of the user making the request.
        operation: Name of the current operation.
        component: System component (api, worker, etc.).
        session_id: User session ID.
        trace_id: Distributed trace ID.
        parent_span_id: Parent span ID for nested operations.
        span_id: Current span ID.
        metadata: Additional key-value pairs.

    Example:
        >>> ctx = LogContext(user_id="user123", operation="update_profile")
        >>> with log_context(ctx):
        ...     logger.info("Profile updated")
    """

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    operation: str | None = None
    component: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    parent_span_id: str | None = None
    span_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging.

        Returns:
            Dict with all non-None context fields.
        """
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "operation": self.operation,
            "component": self.component,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "span_id": self.span_id,
            **self.metadata,
        }


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================
# Captures operation timing and resource usage for observability.
# Used by ComprehensiveLogger.performance_context() for automatic tracking.


@dataclass
class PerformanceMetrics:
    """Performance metrics for operation tracking.

    Captures timing, memory, and outcome for analysis/alerting.
    Designed for automatic capture via context managers.

    Attributes:
        operation_name: Name of the tracked operation.
        start_time: Unix timestamp when started.
        end_time: Unix timestamp when finished.
        duration_ms: Total duration in milliseconds.
        memory_before: RSS bytes at start (requires psutil).
        memory_after: RSS bytes at end (requires psutil).
        memory_delta: Memory change (negative = freed).
        cpu_time: CPU time used (future use).
        success: Whether operation succeeded.
        error_type: Exception class name if failed.
        error_message: Exception message if failed.

    Example:
        >>> metrics = PerformanceMetrics("db_query")
        >>> result = await db.execute(query)
        >>> metrics.finish(success=True)
    """

    operation_name: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float | None = None
    memory_before: int | None = None
    memory_after: int | None = None
    memory_delta: int | None = None
    cpu_time: float | None = None
    success: bool = True
    error_type: str | None = None
    error_message: str | None = None

    def finish(self, success: bool = True, error: Exception | None = None) -> None:
        """Mark operation finished and calculate metrics.

        Args:
            success: Whether operation succeeded.
            error: Exception if operation failed.
        """
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success

        if error:
            self.error_type = type(error).__name__
            self.error_message = str(error)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging.

        Returns:
            Dict with all metrics fields.
        """
        return {
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "memory_before": self.memory_before,
            "memory_after": self.memory_after,
            "memory_delta": self.memory_delta,
            "cpu_time": self.cpu_time,
            "success": self.success,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


# =============================================================================
# STRUCTURED FORMATTER
# =============================================================================
# JSON formatter for log aggregation systems. Converts Python LogRecords
# to JSON for systems like ELK, Splunk, CloudWatch Logs, Datadog, etc.


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Converts log records to JSON for log aggregation systems
    (ELK, Splunk, CloudWatch Logs, etc.).

    Attributes:
        include_context: Include LogContext fields in output.

    Output includes: timestamp, level, logger, message, module,
    function, line, process_id, thread_id, context, exception.
    """

    def __init__(self, include_context: bool = True):
        """Initialize formatter.

        Args:
            include_context: Include LogContext. Default: True.
        """
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Python logging LogRecord.

        Returns:
            JSON string with all log fields.
        """
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
            "thread_name": record.threadName,
        }

        # Add context information from contextvars (if set).
        # This is how request_id, user_id, trace_id flow through logs.
        if self.include_context:
            context = _request_context.get({})
            if context:
                log_entry["context"] = context

        # Add exception information for error tracking and debugging.
        # Includes type, message, and full traceback for diagnosis.
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add any extra fields passed to logger.info(msg, extra={...}).
        # Excludes standard LogRecord attributes to avoid duplication.
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "stack_info",
                "exc_info",
                "exc_text",
            }:
                log_entry[key] = value

        # Serialize to JSON. Use default=str for non-serializable objects
        # (datetime, UUID, etc.). ensure_ascii=False preserves unicode.
        return json.dumps(log_entry, default=str, ensure_ascii=False)


# =============================================================================
# SECURITY AUDIT LOGGER
# =============================================================================
# Dedicated logger for security-sensitive events. Creates separate log files
# for compliance/audit requirements. These logs should be preserved longer
# and may require different access controls.
#
# Security events to log:
# - Authentication (login, logout, failed attempts, MFA)
# - Authorization (permission checks, access denied)
# - Sensitive operations (data export, PII access, admin actions)
# - Security violations (rate limit exceeded, invalid tokens, attacks)


class SecurityAuditLogger:
    """Specialized logger for security and audit events.

    Creates a dedicated rotating log file for security events:
    authentication, authorization, sensitive operations, violations.
    These logs should be preserved longer and monitored separately.

    Log Location:
        - Primary: ~/.kagami/logs/security/security_audit.log
        - Fallback: /tmp/kagami_security_audit.log

    Log Rotation:
        - Max size: 10MB per file
        - Backup count: 5 files

    Methods:
        - log_authentication_attempt: Login/logout events
        - log_authorization_check: Permission checks
        - log_sensitive_operation: PII access, data export
        - log_security_violation: Attack attempts

    Example:
        >>> security = SecurityAuditLogger()
        >>> security.log_authentication_attempt("user@example.com", True)
        >>> security.log_authorization_check("user", "/admin", "read", False)
    """

    def __init__(self, name: str = "kagami.security"):
        """Initialize security audit logger.

        Args:
            name: Logger name. Default: "kagami.security".
        """
        self.logger = logging.getLogger(name)
        self._setup_security_handler()

    def _setup_security_handler(self) -> None:
        """Setup dedicated security log handler with rotation.

        Creates rotating file handler at security log path.
        Falls back to temp directory if primary path fails.
        """
        # Try to create security log directory
        try:
            from kagami.core.utils.paths import get_user_kagami_dir

            security_log_dir = get_user_kagami_dir() / "logs" / "security"
            security_log_dir.mkdir(parents=True, exist_ok=True)
            security_log_path = security_log_dir / "security_audit.log"
        except Exception:
            # Fallback to system temp directory
            import tempfile

            security_log_path = Path(tempfile.gettempdir()) / "kagami_security_audit.log"

        # Create rotating file handler for security logs.
        # Size limit ensures logs don't fill disk.
        # Backup count preserves history for investigation.
        try:
            handler = logging.handlers.RotatingFileHandler(
                security_log_path,
                maxBytes=10 * 1024 * 1024,  # 10MB per file
                backupCount=5,  # Keep 5 rotated files (50MB total)
            )
            handler.setLevel(logging.INFO)  # Log INFO+ for audit trail
            handler.setFormatter(StructuredFormatter())  # JSON for parsing

            # Only add if not already present
            if not any(
                isinstance(h, logging.handlers.RotatingFileHandler)
                and str(h.baseFilename) == str(security_log_path)
                for h in self.logger.handlers
            ):
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        except Exception as e:
            # If we can't set up file logging, at least log to console
            print(f"Warning: Could not set up security audit log file: {e}")

    def log_authentication_attempt(
        self,
        user_id: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        """Log authentication attempt for audit trail.

        Args:
            user_id: User identifier (email, username).
            success: Whether authentication succeeded.
            ip_address: Client IP address.
            user_agent: Client User-Agent header.
            failure_reason: Reason for failure if applicable.
        """
        self.logger.info(
            "Authentication attempt",
            extra={
                "event_type": "authentication",
                "user_id": user_id,
                "success": success,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "failure_reason": failure_reason,
            },
        )

    def log_authorization_check(
        self, user_id: str, resource: str, action: str, granted: bool, reason: str | None = None
    ) -> None:
        """Log authorization check for access control audit.

        Args:
            user_id: User requesting access.
            resource: Resource being accessed.
            action: Action attempted (read, write, delete).
            granted: Whether access was granted.
            reason: Explanation for the decision.
        """
        self.logger.info(
            "Authorization check",
            extra={
                "event_type": "authorization",
                "user_id": user_id,
                "resource": resource,
                "action": action,
                "granted": granted,
                "reason": reason,
            },
        )

    def log_sensitive_operation(
        self,
        operation: str,
        user_id: str | None = None,
        resource: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log sensitive operation for compliance audit.

        Use for operations accessing/modifying sensitive data.

        Args:
            operation: Operation name (export_user_data).
            user_id: User performing the operation.
            resource: Resource being operated on.
            success: Whether operation succeeded.
            details: Additional operation context.
        """
        self.logger.info(
            "Sensitive operation",
            extra={
                "event_type": "sensitive_operation",
                "operation": operation,
                "user_id": user_id,
                "resource": resource,
                "success": success,
                "details": details or {},
            },
        )

    def log_security_violation(
        self,
        violation_type: str,
        severity: str,
        details: dict[str, Any],
        user_id: str | None = None,
    ) -> None:
        """Log security violation for incident response.

        Use for suspicious activity and attack attempts.

        Args:
            violation_type: Type (brute_force, sql_injection).
            severity: Level (low, medium, high, critical).
            details: Investigation details.
            user_id: Associated user if known.
        """
        self.logger.warning(
            "Security violation detected",
            extra={
                "event_type": "security_violation",
                "violation_type": violation_type,
                "severity": severity,
                "user_id": user_id,
                "details": details,
            },
        )


# =============================================================================
# COMPREHENSIVE LOGGER
# =============================================================================
# Main logger class combining all features: standard logging, context
# propagation, performance tracking, and security audit integration.
# This is the primary interface for application logging.


class ComprehensiveLogger:
    """Main comprehensive logging system with context/performance.

    Provides unified logging with:
    - Standard levels (debug, info, warning, error, critical)
    - Automatic context propagation from LogContext
    - Performance tracking with memory metrics
    - Security audit integration

    Attributes:
        name: Logger name (typically module name).
        logger: Underlying Python logger.
        security_logger: Associated SecurityAuditLogger.

    Example:
        >>> logger = ComprehensiveLogger("kagami.api")
        >>> logger.info("Request received", endpoint="/users")
        >>>
        >>> with logger.performance_context("db_query"):
        ...     result = await db.execute(query)
    """

    def __init__(self, name: str):
        """Initialize comprehensive logger.

        Args:
            name: Logger name, typically __name__.
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.security_logger = SecurityAuditLogger()
        self._performance_tracking: dict[str, PerformanceMetrics] = {}
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup console and file handlers.

        Console uses human-readable in dev, JSON in production.
        File always uses JSON for log aggregation.
        """
        if self.logger.handlers:
            return  # Already configured

        self.logger.setLevel(logging.DEBUG)

        # Console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Use structured logging in production, human-readable in development
        try:
            from kagami.core.config.unified_config import is_production

            if is_production():
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
                    )
                )
        except Exception:
            # Fallback to simple formatter
            console_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )

        self.logger.addHandler(console_handler)

        # File handler for persistent logs
        self._setup_file_handler()

    def _setup_file_handler(self) -> None:
        """Setup rotating file handler for persistent logs.

        Creates log file at ~/.kagami/logs/{name}.log.
        Falls back to /tmp if primary path fails.
        """
        try:
            from kagami.core.utils.paths import get_user_kagami_dir

            log_dir = get_user_kagami_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{self.name.replace('.', '_')}.log"
        except Exception:
            import tempfile

            log_file = Path(tempfile.gettempdir()) / f"kagami_{self.name.replace('.', '_')}.log"

        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=3,
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(file_handler)
        except Exception as e:
            self.logger.warning(f"Could not set up file logging: {e}")

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with context.

        Args:
            message: Log message.
            **kwargs: Additional fields.
        """
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message with context.

        Args:
            message: Log message.
            **kwargs: Additional fields.
        """
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with context.

        Args:
            message: Log message.
            **kwargs: Additional fields.
        """
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool | Exception | None = None, **kwargs) -> None:
        """Log error message with context.

        Args:
            message: Log message.
            exc_info: Exception or True for traceback.
            **kwargs: Additional fields.
        """
        self._log_with_context(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: bool | Exception | None = None, **kwargs) -> None:
        """Log critical message with context.

        Args:
            message: Log message.
            exc_info: Exception or True for traceback.
            **kwargs: Additional fields.
        """
        self._log_with_context(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def _log_with_context(
        self, level: int, message: str, exc_info: bool | Exception | None = None, **kwargs
    ) -> None:
        """Log message with LogContext merged into extra.

        Args:
            level: Logging level (DEBUG, INFO, etc.).
            message: Log message.
            exc_info: Exception info if any.
            **kwargs: Additional extra fields.
        """
        # Convert exception to exc_info format
        if isinstance(exc_info, Exception):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)

        # Add context to extra
        kwargs.update(_request_context.get({}))

        self.logger.log(level, message, exc_info=exc_info, extra=kwargs)

    def start_performance_tracking(self, operation_name: str) -> str:
        """Start tracking performance for an operation.

        Args:
            operation_name: Name for metrics.

        Returns:
            Tracking ID for finish_performance_tracking().
        """
        tracking_id = str(uuid.uuid4())
        metrics = PerformanceMetrics(operation_name=operation_name)

        # Try to get memory usage
        try:
            import psutil

            process = psutil.Process()
            metrics.memory_before = process.memory_info().rss
        except ImportError:
            pass

        self._performance_tracking[tracking_id] = metrics

        self.debug(
            f"Started performance tracking for {operation_name}",
            tracking_id=tracking_id,
            operation=operation_name,
        )

        return tracking_id

    def finish_performance_tracking(
        self, tracking_id: str, success: bool = True, error: Exception | None = None
    ) -> None:
        """Finish performance tracking and log metrics.

        Args:
            tracking_id: ID from start_performance_tracking().
            success: Whether operation succeeded.
            error: Exception if failed.
        """
        if tracking_id not in self._performance_tracking:
            self.warning(f"Unknown performance tracking ID: {tracking_id}")
            return

        metrics = self._performance_tracking.pop(tracking_id)
        metrics.finish(success=success, error=error)

        # Try to get final memory usage
        try:
            import psutil

            process = psutil.Process()
            metrics.memory_after = process.memory_info().rss
            if metrics.memory_before:
                metrics.memory_delta = metrics.memory_after - metrics.memory_before
        except ImportError:
            pass

        # Log performance metrics
        log_level = logging.INFO if success else logging.WARNING
        self.logger.log(
            log_level,
            f"Performance metrics for {metrics.operation_name}",
            extra={"event_type": "performance_metrics", "performance": metrics.to_dict()},
        )

        # Emit metrics if available
        try:
            from kagami_observability.metrics import emit_counter, emit_histogram

            emit_histogram(
                "kagami_operation_duration_ms",
                metrics.duration_ms,
                labels={"operation": metrics.operation_name, "success": str(success)},
            )

            emit_counter(
                "kagami_operations_total",
                labels={"operation": metrics.operation_name, "success": str(success)},
            )

            if not success:
                emit_counter(
                    "kagami_operation_errors_total",
                    labels={
                        "operation": metrics.operation_name,
                        "error_type": metrics.error_type or "unknown",
                    },
                )
        except Exception:
            pass  # Don't fail if metrics unavailable

    @contextmanager
    def performance_context(self, operation_name: str) -> Generator[str, None, None]:
        """Context manager for automatic performance tracking.

        Args:
            operation_name: Name for metrics.

        Yields:
            Tracking ID (can be ignored).

        Example:
            >>> with logger.performance_context("api_call"):
            ...     response = await client.get(url)
        """
        tracking_id = self.start_performance_tracking(operation_name)
        try:
            yield tracking_id
            self.finish_performance_tracking(tracking_id, success=True)
        except Exception as e:
            self.finish_performance_tracking(tracking_id, success=False, error=e)
            raise

    def log_function_call(
        self,
        func_name: str,
        args: tuple = (),
        kwargs: dict | None = None,
        result: Any = None,
        error: Exception | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Log function call with parameters and result.

        Automatically sanitizes sensitive fields.

        Args:
            func_name: Name of function called.
            args: Positional arguments (sanitized).
            kwargs: Keyword arguments (sanitized).
            result: Return value (sanitized).
            error: Exception if failed.
            duration_ms: Call duration in milliseconds.
        """
        kwargs = kwargs or {}

        # Sanitize arguments for logging (remove sensitive data)
        safe_args = self._sanitize_for_logging(args)
        safe_kwargs = self._sanitize_for_logging(kwargs)
        safe_result = self._sanitize_for_logging(result)

        log_data = {
            "event_type": "function_call",
            "function_name": func_name,
            "args": safe_args,
            "kwargs": safe_kwargs,
            "success": error is None,
            "duration_ms": duration_ms,
        }

        if error is None:
            log_data["result"] = safe_result
            self.debug(f"Function call: {func_name}", **log_data)
        else:
            log_data["error_type"] = type(error).__name__
            log_data["error_message"] = str(error)
            self.error(f"Function call failed: {func_name}", exc_info=error, **log_data)

    def _sanitize_for_logging(self, obj: Any, max_length: int = 1000) -> Any:
        """Sanitize object for safe logging.

        Removes sensitive data (passwords, tokens) and truncates
        large strings/lists to prevent log bloat.

        Args:
            obj: Object to sanitize.
            max_length: Max string length.

        Returns:
            Sanitized version safe for logging.
        """
        if obj is None:
            return None

        # Set of substrings that indicate sensitive data.
        # If any of these appear in a dict key, the value is redacted.
        sensitive_keys = {
            "password",  # User passwords
            "secret",  # API secrets, client secrets
            "token",  # Auth tokens, refresh tokens
            "key",  # API keys, encryption keys
            "auth",  # Authorization headers
            "credential",  # Generic credentials
            "api_key",  # Explicit API key fields
            "access_token",  # OAuth access tokens
            "refresh_token",  # OAuth refresh tokens
            "session_id",  # Session identifiers
        }

        # Recursively sanitize dict values, redacting sensitive keys
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                key_lower = str(key).lower()
                # Check if key contains any sensitive substring
                if any(sensitive in key_lower for sensitive in sensitive_keys):
                    sanitized[key] = "***REDACTED***"  # Mask sensitive values
                else:
                    sanitized[key] = self._sanitize_for_logging(value, max_length)
            return sanitized

        # Recursively sanitize list/tuple items, limiting to first 10
        # to prevent huge arrays from bloating logs
        elif isinstance(obj, (list, tuple)):
            return [
                self._sanitize_for_logging(item, max_length) for item in obj[:10]
            ]  # Limit to first 10 items (truncates large arrays)

        # Truncate long strings to prevent log bloat from large payloads
        elif isinstance(obj, str):
            if len(obj) > max_length:
                return obj[:max_length] + "...[TRUNCATED]"
            return obj

        # Handle objects with __dict__ attribute (dataclasses, custom classes).
        # Convert to dict and recursively sanitize their attributes.
        elif hasattr(obj, "__dict__"):
            try:
                return self._sanitize_for_logging(obj.__dict__, max_length)
            except Exception:
                # If __dict__ access fails, fall back to string representation
                return str(obj)[:max_length]

        else:
            # Fallback: convert to string and truncate if needed.
            # Handles int, float, bool, and other primitive types.
            str_repr = str(obj)
            if len(str_repr) > max_length:
                return str_repr[:max_length] + "...[TRUNCATED]"
            return str_repr


# =============================================================================
# Context Management Functions
# =============================================================================
# These functions manage the request-scoped LogContext that propagates
# correlation IDs and metadata through async call chains.


def set_log_context(context: LogContext) -> None:
    """Set the current logging context for this async task.

    Args:
        context: LogContext with correlation_id, user_id, etc.

    Example:
        >>> ctx = LogContext(correlation_id="abc-123", user_id="user-1")
        >>> set_log_context(ctx)
    """
    _request_context.set(context.to_dict())


def update_log_context(**kwargs) -> None:
    """Update the current logging context with additional fields.

    Merges new fields into existing context without replacing.

    Args:
        **kwargs: Fields to add (e.g., operation="checkout").

    Example:
        >>> update_log_context(operation="checkout", cart_id="cart-123")
    """
    current = _request_context.get({})
    current.update(kwargs)
    _request_context.set(current)


def get_log_context() -> dict[str, Any]:
    """Get the current logging context dictionary.

    Returns:
        Dict with all context fields, or empty dict if none set.
    """
    return _request_context.get({})


def clear_log_context() -> None:
    """Clear the current logging context.

    Call at request end to prevent context leakage.
    """
    _request_context.set({})


@contextmanager
def log_context(context: LogContext) -> Generator[None, None, None]:
    """Context manager for temporary logging context.

    Automatically saves and restores previous context.

    Args:
        context: LogContext to use within the block.

    Yields:
        None.

    Example:
        >>> with log_context(LogContext(correlation_id="req-123")):
        ...     logger.info("Processing")  # Includes correlation_id
        >>> # Context restored after block
    """
    # Save current context for restoration
    previous_context = _request_context.get({})

    try:
        # Set new context for this block
        _request_context.set(context.to_dict())
        yield
    finally:
        # Restore previous context (cleanup)
        _request_context.set(previous_context)


# =============================================================================
# Logger Factory Functions
# =============================================================================
# Thread-safe singleton pattern for logger instances.

# Global logger registry (name → logger instance)
_loggers: dict[str, ComprehensiveLogger] = {}

# Lock for thread-safe logger creation
_logger_lock = threading.Lock()


def get_logger(name: str | None = None) -> ComprehensiveLogger:
    """Get or create a comprehensive logger instance.

    Uses singleton pattern — same name returns same logger.
    Auto-detects caller module if no name provided.

    Args:
        name: Logger name (defaults to caller's __name__).

    Returns:
        ComprehensiveLogger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting up")
        >>>
        >>> # Or auto-detect:
        >>> logger = get_logger()
    """
    if name is None:
        # Auto-detect caller's module name from stack
        import inspect

        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            name = caller_frame.f_globals.get("__name__", "kagami.unknown")
        finally:
            del frame

    # Thread-safe singleton access
    with _logger_lock:
        if name not in _loggers:
            _loggers[name] = ComprehensiveLogger(name)
        return _loggers[name]


def get_security_logger() -> SecurityAuditLogger:
    """Get a security audit logger instance.

    Returns:
        SecurityAuditLogger for auth/access logging.

    Example:
        >>> sec_logger = get_security_logger()
        >>> sec_logger.log_authentication_attempt(
        ...     user_id="user-1", success=True, method="oauth"
        ... )
    """
    return SecurityAuditLogger()


# =============================================================================
# PUBLIC API
# =============================================================================
# Exports for from kagami.core.logging import ...

__all__ = [
    # Main logger class — use get_logger() to obtain
    "ComprehensiveLogger",
    # Context dataclass — request/trace info
    "LogContext",
    # Performance metrics dataclass
    "PerformanceMetrics",
    # Security audit logger
    "SecurityAuditLogger",
    # JSON formatter for structured logs
    "StructuredFormatter",
    # Context management functions
    "clear_log_context",
    "get_log_context",
    # Factory functions
    "get_logger",
    "get_security_logger",
    "log_context",
    "set_log_context",
    "update_log_context",
]
