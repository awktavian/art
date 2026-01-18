"""🔗 Kagami Protocol — kagami:// URI handling.

This module provides the kagami:// protocol handler, translating
protocol URIs into HTTP(S) API calls.

Example:
    >>> from kagami.core.protocol import resolve, execute
    >>>
    >>> # Resolve URI to HTTP request details
    >>> request = resolve("kagami://lights/living-room/50")
    >>> print(request.url)
    https://api.awkronos.com/v1/lights/living-room
    >>>
    >>> # Execute URI directly
    >>> result = await execute("kagami://scene/movie")
    >>> print(result["status"])
    200
"""

from kagami.core.protocol.handler import (
    DEFAULT_ROUTES,
    KagamiProtocolHandler,
    ProtocolMethod,
    ProtocolRoute,
    ResolvedRequest,
    execute,
    get_protocol_handler,
    resolve,
)

__all__ = [
    "DEFAULT_ROUTES",
    "KagamiProtocolHandler",
    "ProtocolMethod",
    "ProtocolRoute",
    "ResolvedRequest",
    "execute",
    "get_protocol_handler",
    "resolve",
]
