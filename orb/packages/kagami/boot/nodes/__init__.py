"""Boot node definitions for K OS startup graph.

This module provides boot node configurations for different subsystems.
The health_flag helper creates standardized health check callbacks.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import FastAPI


def health_flag(state_attr: str, key: str) -> Callable[[FastAPI], Mapping[str, Any]]:
    """Create a health check callback that reads a flag from app.state.

    This is a helper factory for creating standardized health checks used by
    BootNode configurations. It creates a callable that returns a dict[str, Any] with
    a single boolean key based on the truthiness of an app.state attribute.

    Args:
        state_attr: The attribute name on app.state to check (e.g., "db_ready")
        key: The key name to return in the health dict[str, Any] (e.g., "db_ready")

    Returns:
        A callable that takes FastAPI app and returns {key: bool}

    Example:
        >>> node = BootNode(
        ...     name="database",
        ...     start=startup_database,
        ...     health_check=health_flag("db_ready", "db_ready"),
        ... )
    """

    def _checker(app: FastAPI) -> Mapping[str, Any]:
        return {key: bool(getattr(app.state, state_attr, False))}

    return _checker


__all__ = ["health_flag"]
