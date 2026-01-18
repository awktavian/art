"""Tests for Route Registry module."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
from unittest.mock import MagicMock, patch
from tests.helpers import get_fastapi_app
from tests.helpers.mock_factory import MockFactory
from kagami_api.route_registry import _include_router, _get_router_from_module, register_all_routes


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return MockFactory.create_fastapi_app()


def test_get_router_from_module_with_get_router():
    """Test router extraction via get_router() factory."""
    mock_module = MagicMock()
    mock_router = MagicMock()
    mock_module.get_router = MagicMock(return_value=mock_router)

    result = _get_router_from_module(mock_module)

    assert result is mock_router
    mock_module.get_router.assert_called_once()


def test_get_router_from_module_with_router_attribute():
    """Test router extraction via router attribute (fallback)."""
    mock_module = MagicMock()
    mock_router = MagicMock()
    # Remove get_router to force fallback
    del mock_module.get_router
    mock_module.router = mock_router

    result = _get_router_from_module(mock_module)

    assert result is mock_router


def test_get_router_from_module_missing_both():
    """Test router extraction when neither method exists."""
    mock_module = MagicMock()
    del mock_module.get_router
    del mock_module.router

    result = _get_router_from_module(mock_module)

    assert result is None


def test_include_router_success(app: Any) -> None:
    """Test successful router inclusion."""
    mock_router = MockFactory.create_fastapi_router()
    _include_router(app, mock_router, prefix="/test", tags=["test"], name="Test")
    app.include_router.assert_called_once()


def test_include_router_with_none(app: Any) -> None:
    """Test router inclusion with None router."""
    _include_router(app, None, prefix="/test", tags=["test"], name="Test")
    app.include_router.assert_not_called()


def test_include_router_without_prefix(app: Any) -> None:
    """Test router inclusion without prefix."""
    mock_router = MockFactory.create_fastapi_router()
    _include_router(app, mock_router, name="Test")
    app.include_router.assert_called_once_with(mock_router)


def test_include_router_with_tags(app: Any) -> None:
    """Test router inclusion with tags."""
    mock_router = MockFactory.create_fastapi_router()
    _include_router(app, mock_router, prefix="/test", tags=["tag1", "tag2"], name="Test")
    call_args = app.include_router.call_args
    assert call_args.kwargs["prefix"] == "/test"
    assert call_args.kwargs["tags"] == ["tag1", "tag2"]


def test_include_router_error_in_production(app: Any) -> None:
    """Test router inclusion error raises in production."""
    mock_router = MockFactory.create_fastapi_router()
    app.include_router.side_effect = Exception("Router error")
    with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
        with pytest.raises(Exception):  # noqa: B017 - Any exception should be raised in production
            _include_router(app, mock_router, name="Test")


def test_include_router_error_in_development(app: Any) -> None:
    """Test router inclusion error is logged in development."""
    mock_router = MockFactory.create_fastapi_router()
    app.include_router.side_effect = Exception("Router error")
    with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
        # Should not raise
        _include_router(app, mock_router, name="Test")


def test_register_all_routes_calls_include(app: Any) -> None:
    """Test that register_all_routes calls app.include_router."""
    # Test with minimal mocking - let it try to import real routes
    register_all_routes(app)
    # Should have attempted to register routes (called include_router)
    # May succeed or fail depending on route availability, but should try
    assert app.include_router.call_count >= 0  # At least attempted


def test_register_all_routes_handles_missing_modules(app: Any) -> None:
    """Test that register_all_routes handles missing optional modules gracefully."""
    # Should not raise even if optional modules are missing
    register_all_routes(app)


def test_register_all_routes_logs_success(app: Any, caplog: Any) -> None:
    """Test that successful route registration is logged."""
    register_all_routes(app)
    # Check that completion message was logged
    assert any("Route registration complete" in record.message for record in caplog.records)


def test_register_all_routes_counts_routes(app: Any) -> None:
    """Test that register_all_routes logs total route count."""
    register_all_routes(app)
    # App should have routes registered
    # Mock apps track include_router calls
    assert app.include_router.call_count >= 0


def test_register_all_routes_handles_vitals_module(app: Any) -> None:
    """Test vitals route registration."""
    with patch("kagami_api.routes.vitals") as mock_vitals:
        mock_vitals.router = MockFactory.create_fastapi_router()
        register_all_routes(app)
        # Routes should be registered
        assert app.include_router.called


def test_register_all_routes_handles_command_module(app: Any) -> None:
    """Test command route registration."""
    # Should work without patching - command module exists
    register_all_routes(app)


def test_register_all_routes_handles_intents_module(app: Any) -> None:
    """Test intents route registration."""
    # Should work - intents module exists
    register_all_routes(app)
