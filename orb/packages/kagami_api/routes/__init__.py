"""K os API Routes package.

Route registration is handled by route_registry.py.
This module provides utility exports only.
"""

from typing import Any

# Lazy imports to avoid circular dependencies and import-time errors
__all__ = ["agui", "audio", "health"]


def __getattr__(name: str) -> Any:
    """Lazy attribute access for backward compatibility."""
    if name == "agui":
        from kagami_api.routes.colonies import ui

        return ui
    elif name == "health":
        from kagami_api.routes import vitals

        return vitals
    elif name == "audio":
        from kagami_api.routes.home import audio

        return audio
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
