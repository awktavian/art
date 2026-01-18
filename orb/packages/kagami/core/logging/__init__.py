"""Comprehensive Logging Framework for Kagami.

This package provides production-ready logging with:
- Structured JSON output for log aggregation
- Request context propagation via contextvars
- Performance tracking with memory metrics
- Security audit logging with rotation
- Integration with observability systems

Quick Start:
    # Get a logger
    from kagami.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Operation started", task_id="123")

    # Set context for a request
    from kagami.core.logging import log_context, LogContext

    with log_context(LogContext(user_id="user123")):
        logger.info("User action")  # Includes user_id

    # Track performance
    with logger.performance_context("api_call"):
        response = await client.get(url)

    # Security audit
    from kagami.core.logging import get_security_logger

    security = get_security_logger()
    security.log_authentication_attempt("user@example.com", True)

Components:
    - ComprehensiveLogger: Main logger with context and metrics
    - LogContext: Request/trace context propagation
    - PerformanceMetrics: Timing and memory metrics
    - SecurityAuditLogger: Dedicated security event logging
    - StructuredFormatter: JSON log formatter
    - get_logger(): Get/create logger by name
    - log_context(): Context manager for scoped context
    - set/get/update/clear_log_context(): Manual context control

See comprehensive_logging.py for detailed documentation.
"""

from .comprehensive_logging import (
    ComprehensiveLogger,
    LogContext,
    PerformanceMetrics,
    SecurityAuditLogger,
    StructuredFormatter,
    clear_log_context,
    get_log_context,
    get_logger,
    get_security_logger,
    log_context,
    set_log_context,
    update_log_context,
)

__all__ = [
    "ComprehensiveLogger",
    "LogContext",
    "PerformanceMetrics",
    "SecurityAuditLogger",
    "StructuredFormatter",
    "clear_log_context",
    "get_log_context",
    "get_logger",
    "get_security_logger",
    "log_context",
    "set_log_context",
    "update_log_context",
]
