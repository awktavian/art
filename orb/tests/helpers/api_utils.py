"""API testing utilities for handling FastAPI app wrapping.

This module provides utilities for tests that need to access FastAPI app internals,
particularly when the app is wrapped by Socket.IO or other ASGI middleware.
"""

from typing import Any


def get_fastapi_app(app: Any) -> Any:
    """Unwrap FastAPI app from Socket.IO or other ASGI wrapper if needed.

    When create_app() returns a Socket.IO ASGI application, the actual FastAPI
    app is accessible via the `other_asgi_app` attribute. This helper function
    handles both cases:
    - If app is wrapped (has other_asgi_app), returns the inner FastAPI app
    - If app is already FastAPI, returns it directly

    This allows tests to access app.routes, app.router, and other FastAPI-specific
    attributes consistently regardless of wrapping.

    Args:
        app: Application instance (may be FastAPI or Socket.IO wrapper)

    Returns:
        The unwrapped FastAPI application instance

    Example:
        >>> from kagami_api import create_app
        >>> app = create_app()  # May return Socket.IO wrapper
        >>> fastapi_app = get_fastapi_app(app)
        >>> routes = fastapi_app.routes  # Access routes correctly
    """
    if hasattr(app, "other_asgi_app"):
        # Socket.IO wrapper: return the inner FastAPI app
        return app.other_asgi_app
    # Already FastAPI app or no wrapping
    return app
