"""Tests for kagami_api.routes.utils route decorators and helpers."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from fastapi import HTTPException
from pydantic import BaseModel

from kagami_api.routes.utils import (
    bad_request,
    conflict,
    ensure_exists,
    forbidden,
    gateway_timeout,
    handle_route_errors,
    not_found,
    require_fields,
    service_unavailable,
    unauthorized,
    unprocessable_entity,
)

# =============================================================================
# Test Models
# =============================================================================


class UserModel(BaseModel):
    name: str
    email: str | None = None
    age: int | None = None


# =============================================================================
# Test handle_route_errors Decorator
# =============================================================================


@pytest.mark.asyncio
async def test_handle_route_errors_success_async():
    """Test decorator allows successful async execution."""

    @handle_route_errors("test_op")
    async def test_func():
        return {"success": True}

    result = await test_func()
    assert result == {"success": True}


def test_handle_route_errors_success_sync():
    """Test decorator allows successful sync execution."""

    @handle_route_errors("test_op")
    def test_func():
        return {"success": True}

    result = test_func()
    assert result == {"success": True}


@pytest.mark.asyncio
async def test_handle_route_errors_reraises_http_exception():
    """Test decorator re-raises HTTPException unchanged."""

    @handle_route_errors("test_op")
    async def test_func():
        raise HTTPException(status_code=404, detail="Not found")

    with pytest.raises(HTTPException) as exc_info:
        await test_func()

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Not found"


@pytest.mark.asyncio
async def test_handle_route_errors_converts_generic_exception():
    """Test decorator converts generic exceptions to HTTP 500."""

    @handle_route_errors("test_op")
    async def test_func():
        raise ValueError("Something went wrong")

    with pytest.raises(HTTPException) as exc_info:
        await test_func()

    assert exc_info.value.status_code == 500
    assert "Something went wrong" in exc_info.value.detail


@pytest.mark.asyncio
async def test_handle_route_errors_uses_function_name_when_no_name_provided():
    """Test decorator uses function name when operation_name not provided."""

    @handle_route_errors()
    async def my_test_function():
        raise ValueError("Test error")

    with pytest.raises(HTTPException) as exc_info:
        await my_test_function()

    assert exc_info.value.status_code == 500


# =============================================================================
# Test Error Factory Functions
# =============================================================================


def test_not_found_with_identifier():
    """Test not_found creates proper 404 with identifier."""
    exc = not_found("item", "123")
    assert exc.status_code == 404
    assert "item" in exc.detail
    assert "123" in exc.detail


def test_not_found_without_identifier():
    """Test not_found creates proper 404 without identifier."""
    exc = not_found("user")
    assert exc.status_code == 404
    assert "user" in exc.detail


def test_bad_request():
    """Test bad_request creates proper 400."""
    exc = bad_request("Invalid input")
    assert exc.status_code == 400
    assert exc.detail == "Invalid input"


def test_forbidden():
    """Test forbidden creates proper 403."""
    exc = forbidden("Admin only")
    assert exc.status_code == 403
    assert exc.detail == "Admin only"


def test_forbidden_default_message():
    """Test forbidden uses default message."""
    exc = forbidden()
    assert exc.status_code == 403
    assert "forbidden" in exc.detail.lower()


def test_unauthorized():
    """Test unauthorized creates proper 401."""
    exc = unauthorized("Token expired")
    assert exc.status_code == 401
    assert exc.detail == "Token expired"


def test_unauthorized_default_message():
    """Test unauthorized uses default message."""
    exc = unauthorized()
    assert exc.status_code == 401
    assert "authentication" in exc.detail.lower()


def test_conflict():
    """Test conflict creates proper 409."""
    exc = conflict("Already exists")
    assert exc.status_code == 409
    assert exc.detail == "Already exists"


def test_unprocessable_entity():
    """Test unprocessable_entity creates proper 422."""
    exc = unprocessable_entity("Validation failed")
    assert exc.status_code == 422
    assert exc.detail == "Validation failed"


def test_service_unavailable():
    """Test service_unavailable creates proper 503."""
    exc = service_unavailable()
    assert exc.status_code == 503


def test_gateway_timeout():
    """Test gateway_timeout creates proper 504."""
    exc = gateway_timeout()
    assert exc.status_code == 504


# =============================================================================
# Test Convenience Functions
# =============================================================================


def test_require_fields_success():
    """Test require_fields passes with all fields present."""
    data = {"name": "Test", "email": "test@example.com"}
    # Should not raise
    require_fields(data, "name", "email")


def test_require_fields_raises_on_missing():
    """Test require_fields raises when fields missing."""
    data = {"name": "Test"}

    with pytest.raises(HTTPException) as exc_info:
        require_fields(data, "name", "email")

    assert exc_info.value.status_code == 400
    assert "email" in exc_info.value.detail


def test_require_fields_with_pydantic_model():
    """Test require_fields works with Pydantic models."""
    model = UserModel(name="Test", email="test@example.com")
    # Should not raise
    require_fields(model, "name", "email")


def test_require_fields_raises_on_invalid_type():
    """Test require_fields raises on non-dict/non-model input."""
    with pytest.raises(HTTPException) as exc_info:
        require_fields("not a dict", "name")

    assert exc_info.value.status_code == 400


def test_ensure_exists_returns_object_when_present():
    """Test ensure_exists returns object when not None."""
    obj = {"id": 1, "name": "Test"}
    result = ensure_exists(obj, "item", 1)
    assert result == obj


def test_ensure_exists_raises_when_none():
    """Test ensure_exists raises not_found when None."""
    with pytest.raises(HTTPException) as exc_info:
        ensure_exists(None, "item", 123)

    assert exc_info.value.status_code == 404
    assert "item" in exc_info.value.detail
    assert "123" in exc_info.value.detail


def test_ensure_exists_without_identifier():
    """Test ensure_exists works without identifier."""
    with pytest.raises(HTTPException) as exc_info:
        ensure_exists(None, "resource")

    assert exc_info.value.status_code == 404
    assert "resource" in exc_info.value.detail


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_realistic_route_scenario():
    """Test realistic route scenario with error factories."""

    @handle_route_errors("create_item")
    async def create_item(item_id: int | None, data: dict):
        # Validate input
        require_fields(data, "name", "price")

        # Check if exists
        if item_id == 999:
            raise conflict("Item already exists")

        # Simulate database operation
        if data["price"] < 0:
            raise bad_request("Price must be positive")

        # Create item
        return {"id": item_id or 1, **data}

    # Success case
    result = await create_item(None, {"name": "Widget", "price": 10.0})
    assert result["name"] == "Widget"

    # Missing fields
    with pytest.raises(HTTPException) as exc_info:
        await create_item(None, {"name": "Widget"})
    assert exc_info.value.status_code == 400

    # Conflict
    with pytest.raises(HTTPException) as exc_info:
        await create_item(999, {"name": "Widget", "price": 10.0})
    assert exc_info.value.status_code == 409

    # Bad request
    with pytest.raises(HTTPException) as exc_info:
        await create_item(None, {"name": "Widget", "price": -10.0})
    assert exc_info.value.status_code == 400
