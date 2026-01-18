"""🔗 Kagami Protocol Handler — kagami:// → HTTPS.

This module translates kagami:// URIs into HTTP(S) API calls,
making kagami:// feel like a native protocol.

Architecture:
    kagami://lights/living-room/50
         ↓
    KagamiProtocolHandler.resolve()
         ↓
    POST https://api.awkronos.com/v1/lights/living-room
         {"level": 50}

Colony: Nexus (e4)
Created: January 5, 2026
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class ProtocolMethod(Enum):
    """HTTP methods for protocol resolution."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    WSS = "WSS"  # WebSocket
    DEEPLINK = "DEEPLINK"  # App deep link


@dataclass
class ProtocolRoute:
    """A route mapping kagami:// to HTTP."""

    pattern: str
    method: ProtocolMethod
    endpoint: str
    body_template: str | None = None

    def matches(self, path: str) -> dict[str, str] | None:
        """Check if path matches this route, extracting params.

        Args:
            path: The kagami:// path (e.g., "lights/living-room/50")

        Returns:
            Dict of extracted parameters, or None if no match
        """
        # Convert {param} to regex groups
        pattern_regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", self.pattern)
        pattern_regex = f"^{pattern_regex}$"

        match = re.match(pattern_regex, path)
        if match:
            return match.groupdict()
        return None


@dataclass
class ResolvedRequest:
    """A resolved HTTP request from a kagami:// URI."""

    method: ProtocolMethod
    url: str
    body: dict[str, Any] | None = None
    headers: dict[str, str] | None = None


# =============================================================================
# DEFAULT ROUTES
# =============================================================================

DEFAULT_ROUTES = [
    # Smart Home - Lights
    ProtocolRoute(
        pattern="lights/{room}/{level}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/lights/{room}",
        body_template='{"level": {level}}',
    ),
    ProtocolRoute(
        pattern="lights/{room}",
        method=ProtocolMethod.GET,
        endpoint="https://api.awkronos.com/v1/lights/{room}",
    ),
    # Smart Home - Shades
    ProtocolRoute(
        pattern="shades/{room}/{action}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/shades/{room}",
        body_template='{"action": "{action}"}',
    ),
    # Smart Home - Scenes
    ProtocolRoute(
        pattern="scene/{name}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/scenes/{name}/activate",
    ),
    # Smart Home - Fireplace
    ProtocolRoute(
        pattern="fireplace/{action}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/fireplace",
        body_template='{"action": "{action}"}',
    ),
    # Smart Home - TV
    ProtocolRoute(
        pattern="tv/{action}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/tv",
        body_template='{"action": "{action}"}',
    ),
    ProtocolRoute(
        pattern="tv/{action}/{preset}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/tv",
        body_template='{"action": "{action}", "preset": {preset}}',
    ),
    # Smart Home - Announce
    ProtocolRoute(
        pattern="announce/{message}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/announce",
        body_template='{"message": "{message}"}',
    ),
    ProtocolRoute(
        pattern="announce/{room}/{message}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/announce",
        body_template='{"message": "{message}", "rooms": ["{room}"]}',
    ),
    # Smart Home - Locks
    ProtocolRoute(
        pattern="lock/all",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/locks/all",
        body_template='{"action": "lock"}',
    ),
    ProtocolRoute(
        pattern="unlock/{door}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/locks/{door}",
        body_template='{"action": "unlock"}',
    ),
    # Voice
    ProtocolRoute(
        pattern="voice/start",
        method=ProtocolMethod.WSS,
        endpoint="wss://voice.awkronos.com/v1/stream",
    ),
    ProtocolRoute(
        pattern="voice/join/{call_id}",
        method=ProtocolMethod.WSS,
        endpoint="wss://voice.awkronos.com/v1/call/{call_id}",
    ),
    # Status
    ProtocolRoute(
        pattern="status",
        method=ProtocolMethod.GET,
        endpoint="https://api.awkronos.com/v1/status",
    ),
    ProtocolRoute(
        pattern="status/{component}",
        method=ProtocolMethod.GET,
        endpoint="https://api.awkronos.com/v1/status/{component}",
    ),
    # Intent (natural language)
    ProtocolRoute(
        pattern="intent/{query}",
        method=ProtocolMethod.POST,
        endpoint="https://api.awkronos.com/v1/intent",
        body_template='{"query": "{query}"}',
    ),
    # Events (WebSocket)
    ProtocolRoute(
        pattern="events",
        method=ProtocolMethod.WSS,
        endpoint="wss://ws.awkronos.com/v1/events",
    ),
    ProtocolRoute(
        pattern="events/{topic}",
        method=ProtocolMethod.WSS,
        endpoint="wss://ws.awkronos.com/v1/events/{topic}",
    ),
    # App deep links
    ProtocolRoute(
        pattern="app/{screen}",
        method=ProtocolMethod.DEEPLINK,
        endpoint="kagami-app://{screen}",
    ),
]


class KagamiProtocolHandler:
    """Handles kagami:// protocol URIs.

    This class translates kagami:// URIs into HTTP(S) requests,
    making the protocol feel native while using standard HTTP
    infrastructure.

    Example:
        >>> handler = KagamiProtocolHandler()
        >>> request = handler.resolve("kagami://lights/living-room/50")
        >>> print(request.url)
        https://api.awkronos.com/v1/lights/living-room
        >>> print(request.body)
        {"level": 50}
    """

    # Base URLs (configurable via environment)
    API_BASE = os.environ.get("KAGAMI_API_URL", "https://api.awkronos.com")
    WS_BASE = os.environ.get("KAGAMI_WS_URL", "wss://ws.awkronos.com")
    VOICE_BASE = os.environ.get("KAGAMI_VOICE_URL", "wss://voice.awkronos.com")

    def __init__(self, routes: list[ProtocolRoute] | None = None):
        """Initialize handler with routes.

        Args:
            routes: Custom routes, or None to use defaults
        """
        self._routes = routes or DEFAULT_ROUTES

    def resolve(self, uri: str) -> ResolvedRequest | None:
        """Resolve a kagami:// URI to an HTTP request.

        Args:
            uri: Full kagami:// URI (e.g., "kagami://lights/living-room/50")

        Returns:
            ResolvedRequest with HTTP details, or None if no match
        """
        parsed = urlparse(uri)

        # Validate scheme
        if parsed.scheme != "kagami":
            logger.warning(f"Invalid scheme: {parsed.scheme}")
            return None

        # Extract path (host is treated as first path segment)
        path = parsed.netloc
        if parsed.path:
            path = f"{path}{parsed.path}".strip("/")

        # Extract query params
        query_params = parse_qs(parsed.query)

        # Find matching route
        for route in self._routes:
            params = route.matches(path)
            if params is not None:
                return self._build_request(route, params, query_params)

        logger.warning(f"No route matched: {uri}")
        return None

    def _build_request(
        self,
        route: ProtocolRoute,
        params: dict[str, str],
        query_params: dict[str, list[str]],
    ) -> ResolvedRequest:
        """Build HTTP request from route and params."""
        # Substitute params in endpoint
        url = route.endpoint
        for key, value in params.items():
            url = url.replace(f"{{{key}}}", value)

        # Apply environment-based URL overrides
        url = self._apply_base_url(url)

        # Build body if template exists
        body = None
        if route.body_template:
            body_str = route.body_template
            for key, value in params.items():
                # Try to parse as int/float for JSON
                try:
                    if "." in value:
                        parsed_value = float(value)
                    else:
                        parsed_value = int(value)
                    body_str = body_str.replace(f"{{{key}}}", str(parsed_value))
                except ValueError:
                    body_str = body_str.replace(f"{{{key}}}", value)

            import json

            try:
                body = json.loads(body_str)
            except json.JSONDecodeError:
                body = {"raw": body_str}

        # Add query params to body
        if body and query_params:
            for key, values in query_params.items():
                body[key] = values[0] if len(values) == 1 else values

        return ResolvedRequest(
            method=route.method,
            url=url,
            body=body,
            headers={"Content-Type": "application/json"} if body else None,
        )

    def _apply_base_url(self, url: str) -> str:
        """Apply environment-based URL overrides."""
        if url.startswith("https://api.awkronos.com"):
            return url.replace("https://api.awkronos.com", self.API_BASE)
        if url.startswith("wss://ws.awkronos.com"):
            return url.replace("wss://ws.awkronos.com", self.WS_BASE)
        if url.startswith("wss://voice.awkronos.com"):
            return url.replace("wss://voice.awkronos.com", self.VOICE_BASE)
        return url

    async def execute(self, uri: str) -> dict[str, Any]:
        """Resolve and execute a kagami:// URI.

        Args:
            uri: Full kagami:// URI

        Returns:
            Response data from the API
        """
        request = self.resolve(uri)
        if not request:
            return {"error": "No route matched", "uri": uri}

        if request.method == ProtocolMethod.WSS:
            return {"error": "WebSocket URIs must use connect()", "url": request.url}

        if request.method == ProtocolMethod.DEEPLINK:
            return {"deeplink": request.url}

        import aiohttp

        async with aiohttp.ClientSession() as session:
            method = request.method.value.lower()
            kwargs: dict[str, Any] = {"headers": request.headers}
            if request.body:
                kwargs["json"] = request.body

            async with session.request(method, request.url, **kwargs) as response:
                try:
                    data = await response.json()
                except Exception:
                    data = {"text": await response.text()}

                return {
                    "status": response.status,
                    "data": data,
                    "url": request.url,
                }


# =============================================================================
# SINGLETON
# =============================================================================

_handler: KagamiProtocolHandler | None = None


def get_protocol_handler() -> KagamiProtocolHandler:
    """Get protocol handler singleton."""
    global _handler
    if _handler is None:
        _handler = KagamiProtocolHandler()
    return _handler


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def resolve(uri: str) -> ResolvedRequest | None:
    """Resolve a kagami:// URI.

    Args:
        uri: Full kagami:// URI

    Returns:
        ResolvedRequest or None
    """
    return get_protocol_handler().resolve(uri)


async def execute(uri: str) -> dict[str, Any]:
    """Execute a kagami:// URI.

    Args:
        uri: Full kagami:// URI

    Returns:
        Response data
    """
    return await get_protocol_handler().execute(uri)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m kagami.core.protocol.handler <kagami://uri>")
        sys.exit(1)

    handler = KagamiProtocolHandler()
    result = handler.resolve(sys.argv[1])

    if result:
        print(f"Method: {result.method.value}")
        print(f"URL: {result.url}")
        if result.body:
            print(f"Body: {result.body}")
    else:
        print("No route matched")
