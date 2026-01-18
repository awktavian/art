from __future__ import annotations

"""Socket.IO telemetry utilities — OpenTelemetry integration.

Provides telemetry functions for tracing Socket.IO operations.
If OpenTelemetry is not available, provides no-op fallbacks to
avoid import errors.

Functions:
    add_span_attributes: Add attributes to the current trace span.
    traced_operation: Context manager for tracing an operation.

Usage:
    >>> from kagami_api.socketio.telemetry import traced_operation
    >>> with traced_operation("socketio.emit", {"event": "message"}):
    ...     await socket.emit("message", data)
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
from typing import Any  # Type hints

# =============================================================================
# OPTIONAL TELEMETRY IMPORT
# =============================================================================
# Try to import telemetry functions; provide no-op fallbacks if unavailable.
# This allows Socket.IO code to use telemetry without requiring the dependency.

try:
    from kagami.observability.telemetry import add_span_attributes, traced_operation
except Exception:
    # Optional dependency not installed — provide no-op fallbacks
    from contextlib import contextmanager

    def add_span_attributes(attrs: dict[str, Any] | None) -> None:
        """No-op fallback when OpenTelemetry is not available."""
        return None

    @contextmanager  # type: ignore[arg-type]
    def traced_operation(name: str, attributes: dict[str, Any] | None = None) -> None:  # type: ignore[misc]
        """No-op fallback when OpenTelemetry is not available."""
        yield


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = ["add_span_attributes", "traced_operation"]
