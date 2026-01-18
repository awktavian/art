"""Contract test fixtures.

Provides HTTP client fixture for API contract testing.
Skips tests gracefully when API server is not available.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Generator
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest

if TYPE_CHECKING:
    import httpx


def _api_server_available() -> bool:
    """Check if the API server is reachable.

    Returns True if a TCP connection can be established to the API server.
    """
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000

    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (TimeoutError, OSError):
        return False


# Cache the check result at module load time for consistent behavior
_SERVER_AVAILABLE: bool | None = None
_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def _check_server() -> bool:
    """Check server availability, caching the result."""
    global _SERVER_AVAILABLE
    if _SERVER_AVAILABLE is None:
        _SERVER_AVAILABLE = _api_server_available()
    return _SERVER_AVAILABLE


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # noqa: ARG001
    """Skip tests that use HTTP client fixture when server is unavailable."""
    if _check_server():
        return  # Server available, run all tests

    skip_marker = pytest.mark.skip(reason=f"API server not available at {_BASE_URL}")

    for item in items:
        # Skip tests that use the 'client' fixture
        if "client" in getattr(item, "fixturenames", ()):
            item.add_marker(skip_marker)


# Module-level skip marker for all tests requiring HTTP client
requires_api_server = pytest.mark.skipif(
    not _check_server(),
    reason=f"API server not available at {_BASE_URL}",
)


@pytest.fixture
def client() -> Generator[httpx.Client, None, None]:
    """Create HTTP client for contract testing.

    Uses API_BASE_URL environment variable or defaults to localhost:8000.
    Skips the test if the API server is not reachable.
    """
    import httpx

    # Skip immediately if server not available (cached check)
    if not _check_server():
        pytest.skip(f"API server not available at {_BASE_URL}")

    http_client = httpx.Client(
        base_url=_BASE_URL,
        headers={
            "X-API-Key": os.getenv("API_KEY", "dev_test_key"),
            "Content-Type": "application/json",
        },
        timeout=10.0,
    )

    try:
        yield http_client
    finally:
        http_client.close()
