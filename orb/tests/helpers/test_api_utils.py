"""Tests for API testing utilities."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


from unittest.mock import MagicMock

from tests.helpers.api_utils import get_fastapi_app


def test_get_fastapi_app_with_wrapper() -> None:
    """Test unwrapping FastAPI app from Socket.IO wrapper."""
    # Create mock FastAPI app
    mock_fastapi = MagicMock()
    mock_fastapi.routes = ["route1", "route2"]

    # Create mock Socket.IO wrapper
    mock_wrapper = MagicMock()
    mock_wrapper.other_asgi_app = mock_fastapi

    # Test unwrapping
    result = get_fastapi_app(mock_wrapper)
    assert result is mock_fastapi
    assert result.routes == ["route1", "route2"]


def test_get_fastapi_app_without_wrapper() -> None:
    """Test with direct FastAPI app (no wrapper)."""
    # Create mock FastAPI app without wrapper
    mock_fastapi = MagicMock()
    mock_fastapi.routes = ["route1", "route2"]
    # Ensure it doesn't have other_asgi_app attribute
    del mock_fastapi.other_asgi_app

    # Test passthrough
    result = get_fastapi_app(mock_fastapi)
    assert result is mock_fastapi
    assert result.routes == ["route1", "route2"]


def test_get_fastapi_app_preserves_attributes() -> None:
    """Test that unwrapping preserves app attributes."""
    # Create mock FastAPI app with attributes
    mock_fastapi = MagicMock()
    mock_fastapi.routes = ["route1"]
    mock_fastapi.state = MagicMock()
    mock_fastapi.router = MagicMock()

    # Wrap it
    mock_wrapper = MagicMock()
    mock_wrapper.other_asgi_app = mock_fastapi

    # Test unwrapping preserves attributes
    result = get_fastapi_app(mock_wrapper)
    assert hasattr(result, "routes")
    assert hasattr(result, "state")
    assert hasattr(result, "router")
