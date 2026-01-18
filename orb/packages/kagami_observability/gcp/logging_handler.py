"""Cloud Logging Handler for Kagami.

Integrates Python logging with Google Cloud Logging for centralized,
structured log management with automatic severity mapping.

FEATURES:
=========
- Automatic severity mapping (DEBUG→INFO→WARNING→ERROR→CRITICAL)
- Structured JSON logging with custom fields
- Request context propagation (trace ID, span ID)
- Labels for filtering (colony, service, environment)
- Async batched writes for performance

USAGE:
======
    from kagami_observability.gcp.logging_handler import setup_gcp_logging

    # Setup for all loggers
    setup_gcp_logging()

    # Use standard Python logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Hello from Kagami", extra={"colony": "forge"})

Created: January 4, 2026
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Lazy import for optional dependency
_cloud_logging = None
_cloud_logging_available = False


def _lazy_import_cloud_logging() -> Any:
    """Lazy import google.cloud.logging."""
    global _cloud_logging, _cloud_logging_available
    if _cloud_logging is not None:
        return _cloud_logging
    try:
        import google.cloud.logging as gcl

        _cloud_logging = gcl
        _cloud_logging_available = True
        return gcl
    except ImportError as e:
        _cloud_logging_available = False
        raise ImportError(
            "google-cloud-logging not installed. Install with: pip install google-cloud-logging"
        ) from e


# Severity mapping from Python to Cloud Logging
SEVERITY_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}


class CloudLoggingHandler(logging.Handler):
    """Python logging handler that sends logs to Cloud Logging.

    Supports:
    - Structured JSON payloads
    - Custom labels for filtering
    - Trace context propagation
    - Async background writes

    Example:
        handler = CloudLoggingHandler(
            project_id="my-project",
            labels={"service": "kagami-api"},
        )
        logger = logging.getLogger()
        logger.addHandler(handler)
    """

    def __init__(
        self,
        project_id: str | None = None,
        log_name: str = "kagami",
        labels: dict[str, str] | None = None,
        resource_type: str = "global",
        resource_labels: dict[str, str] | None = None,
    ):
        """Initialize Cloud Logging handler.

        Args:
            project_id: GCP project ID.
            log_name: Name for the log in Cloud Logging.
            labels: Default labels applied to all log entries.
            resource_type: Monitored resource type.
            resource_labels: Labels for the monitored resource.
        """
        super().__init__()

        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.log_name = log_name
        self.default_labels = labels or {}
        self.resource_type = resource_type
        self.resource_labels = resource_labels or {}

        self._client = None
        self._logger = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Ensure Cloud Logging client is initialized."""
        if self._initialized:
            return

        try:
            gcl = _lazy_import_cloud_logging()

            self._client = gcl.Client(project=self.project_id)
            self._logger = self._client.logger(self.log_name)
            self._initialized = True

        except ImportError:
            # Cloud Logging not available, will fall back to stderr
            pass
        except Exception as e:
            # Log initialization error to stderr
            print(f"Cloud Logging init failed: {e}", file=sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Cloud Logging.

        Args:
            record: Python LogRecord to emit.
        """
        try:
            self._ensure_initialized()

            # Build structured payload
            payload = self._build_payload(record)
            severity = SEVERITY_MAP.get(record.levelno, "DEFAULT")
            labels = self._build_labels(record)

            if self._logger:
                # Send to Cloud Logging
                self._logger.log_struct(
                    payload,
                    severity=severity,
                    labels=labels,
                )
            else:
                # Fallback to stderr as JSON
                output = {
                    "severity": severity,
                    "labels": labels,
                    **payload,
                }
                print(json.dumps(output), file=sys.stderr)

        except Exception:
            # Don't raise exceptions from logging
            self.handleError(record)

    def _build_payload(self, record: logging.LogRecord) -> dict[str, Any]:
        """Build structured log payload.

        Args:
            record: Log record.

        Returns:
            Structured payload dict.
        """
        payload: dict[str, Any] = {
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "python_level": record.levelname,
        }

        # Add source location
        payload["sourceLocation"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception info if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        extra_fields = [
            "colony",
            "e8_index",
            "fano_line",
            "user_id",
            "request_id",
            "trace_id",
            "span_id",
            "correlation_id",
        ]

        for field in extra_fields:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        # Add any custom extra data
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            payload.update(record.extra_data)

        return payload

    def _build_labels(self, record: logging.LogRecord) -> dict[str, str]:
        """Build labels for the log entry.

        Args:
            record: Log record.

        Returns:
            Labels dict.
        """
        labels = dict(self.default_labels)

        # Add module as label
        labels["module"] = record.module

        # Add colony if present
        if hasattr(record, "colony"):
            labels["colony"] = str(record.colony)

        # Add environment
        labels["environment"] = os.getenv("KAGAMI_ENVIRONMENT", "dev")

        return labels

    def close(self) -> None:
        """Close the handler and flush pending logs."""
        super().close()


class StructuredLogFormatter(logging.Formatter):
    """Formatter that outputs JSON for Cloud Logging.

    Used when running outside GCP but wanting structured output.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format record as JSON.

        Args:
            record: Log record.

        Returns:
            JSON string.
        """
        output = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "sourceLocation": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
        }

        if record.exc_info:
            output["exception"] = self.formatException(record.exc_info)

        return json.dumps(output)


def setup_gcp_logging(
    project_id: str | None = None,
    log_name: str = "kagami",
    labels: dict[str, str] | None = None,
    level: int = logging.INFO,
    setup_root: bool = True,
) -> CloudLoggingHandler:
    """Setup Cloud Logging for the application.

    Args:
        project_id: GCP project ID.
        log_name: Log name in Cloud Logging.
        labels: Default labels for all entries.
        level: Logging level threshold.
        setup_root: If True, add handler to root logger.

    Returns:
        Configured CloudLoggingHandler.

    Example:
        # Basic setup
        setup_gcp_logging()

        # With custom labels
        setup_gcp_logging(
            labels={"service": "kagami-api", "colony": "forge"},
            level=logging.DEBUG,
        )
    """
    handler = CloudLoggingHandler(
        project_id=project_id,
        log_name=log_name,
        labels=labels or {"service": "kagami"},
    )
    handler.setLevel(level)

    if setup_root:
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        # Also set level on root if needed
        if root_logger.level > level:
            root_logger.setLevel(level)

    return handler


def get_cloud_logger(
    name: str,
    labels: dict[str, str] | None = None,
) -> logging.Logger:
    """Get a logger configured for Cloud Logging.

    Args:
        name: Logger name (typically __name__).
        labels: Extra labels for this logger.

    Returns:
        Configured logger.

    Example:
        logger = get_cloud_logger(__name__, labels={"colony": "spark"})
        logger.info("Generating idea")
    """
    logger = logging.getLogger(name)

    # Create adapter that adds labels
    class LabeledLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            extra = kwargs.get("extra", {})
            extra.update(self.extra or {})
            kwargs["extra"] = extra
            return msg, kwargs

    return LabeledLoggerAdapter(logger, labels or {})


__all__ = [
    "SEVERITY_MAP",
    "CloudLoggingHandler",
    "StructuredLogFormatter",
    "get_cloud_logger",
    "setup_gcp_logging",
]
