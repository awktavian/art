"""Tests for multi-tenancy middleware.

Covers:
- Tenant extraction from JWT claims
- Tenant extraction from API key metadata
- Tenant override via header (admin only)
- Default tenant fallback
- Tenant isolation verification
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

pytestmark = pytest.mark.tier_unit

from kagami_api.middleware.tenant import (
    DEFAULT_TENANT_ID,
    TenantMiddleware,
    get_tenant_id,
)


class TestTenantExtraction:
    """Test tenant extraction logic."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create mock FastAPI app."""
        return MagicMock()

    @pytest.fixture
    def middleware(self, mock_app: MagicMock) -> TenantMiddleware:
        """Create middleware instance."""
        return TenantMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_extract_tenant_from_jwt(
        self, middleware: TenantMiddleware
    ) -> None:
        """Should extract tenant_id from JWT user claims."""
        tenant_uuid = UUID("12345678-1234-1234-1234-123456789012")
        request = MagicMock()
        request.state.user = MagicMock(tenant_id=str(tenant_uuid))
        request.state.api_key = None
        request.headers = {}

        result = await middleware._extract_tenant(request)

        assert result == tenant_uuid

    @pytest.mark.asyncio
    async def test_extract_tenant_from_jwt_uuid_object(
        self, middleware: TenantMiddleware
    ) -> None:
        """Should handle tenant_id as UUID object in JWT."""
        tenant_uuid = UUID("12345678-1234-1234-1234-123456789012")
        request = MagicMock()
        request.state.user = MagicMock(tenant_id=tenant_uuid)
        request.state.api_key = None
        request.headers = {}

        result = await middleware._extract_tenant(request)

        assert result == tenant_uuid

    @pytest.mark.asyncio
    async def test_extract_tenant_from_api_key(
        self, middleware: TenantMiddleware
    ) -> None:
        """Should extract tenant_id from API key metadata."""
        tenant_uuid = UUID("87654321-4321-4321-4321-210987654321")
        request = MagicMock()
        request.state.user = None
        request.state.api_key = MagicMock(tenant_id=str(tenant_uuid))
        request.headers = {}

        result = await middleware._extract_tenant(request)

        assert result == tenant_uuid

    @pytest.mark.asyncio
    async def test_extract_tenant_from_header_admin(
        self, middleware: TenantMiddleware
    ) -> None:
        """Admin users should be able to override tenant via header."""
        tenant_uuid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        request = MagicMock()
        request.state.user = MagicMock(tenant_id=None, roles=["admin"])
        request.state.api_key = None
        request.headers = {"X-Tenant-ID": str(tenant_uuid)}

        result = await middleware._extract_tenant(request)

        assert result == tenant_uuid

    @pytest.mark.asyncio
    async def test_extract_tenant_header_ignored_non_admin(
        self, middleware: TenantMiddleware
    ) -> None:
        """Non-admin users should not be able to override tenant via header."""
        tenant_uuid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        request = MagicMock()
        request.state.user = MagicMock(tenant_id=None, roles=["user"])
        request.state.api_key = None
        request.headers = {"X-Tenant-ID": str(tenant_uuid)}

        result = await middleware._extract_tenant(request)

        # Should fall back to default, not header value
        assert result == DEFAULT_TENANT_ID

    @pytest.mark.asyncio
    async def test_extract_tenant_invalid_header_uuid(
        self, middleware: TenantMiddleware
    ) -> None:
        """Invalid UUID in header should be ignored."""
        request = MagicMock()
        request.state.user = MagicMock(tenant_id=None, roles=["admin"])
        request.state.api_key = None
        request.headers = {"X-Tenant-ID": "not-a-valid-uuid"}

        result = await middleware._extract_tenant(request)

        assert result == DEFAULT_TENANT_ID

    @pytest.mark.asyncio
    async def test_extract_tenant_default_fallback(
        self, middleware: TenantMiddleware
    ) -> None:
        """Should fall back to default tenant when no tenant info available."""
        request = MagicMock()
        request.state.user = None
        request.state.api_key = None
        request.headers = {}

        result = await middleware._extract_tenant(request)

        assert result == DEFAULT_TENANT_ID

    @pytest.mark.asyncio
    async def test_extract_tenant_jwt_takes_precedence_over_api_key(
        self, middleware: TenantMiddleware
    ) -> None:
        """JWT tenant should take precedence over API key tenant."""
        jwt_tenant = UUID("11111111-1111-1111-1111-111111111111")
        api_key_tenant = UUID("22222222-2222-2222-2222-222222222222")

        request = MagicMock()
        request.state.user = MagicMock(tenant_id=str(jwt_tenant))
        request.state.api_key = MagicMock(tenant_id=str(api_key_tenant))
        request.headers = {}

        result = await middleware._extract_tenant(request)

        assert result == jwt_tenant


class TestTenantMiddlewareDispatch:
    """Test middleware dispatch behavior."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create mock FastAPI app."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_dispatch_sets_tenant_on_request_state(
        self, mock_app: MagicMock
    ) -> None:
        """Dispatch should set tenant_id on request state."""
        middleware = TenantMiddleware(mock_app)
        tenant_uuid = UUID("12345678-1234-1234-1234-123456789012")

        request = MagicMock()
        request.state = MagicMock()
        request.state.user = MagicMock(tenant_id=str(tenant_uuid))
        request.state.api_key = None
        request.headers = {}

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        await middleware.dispatch(request, call_next)

        assert request.state.tenant_id == tenant_uuid

    @pytest.mark.asyncio
    async def test_dispatch_adds_tenant_header_to_response(
        self, mock_app: MagicMock
    ) -> None:
        """Dispatch should add X-Tenant-ID header to response."""
        middleware = TenantMiddleware(mock_app)
        tenant_uuid = UUID("12345678-1234-1234-1234-123456789012")

        request = MagicMock()
        request.state = MagicMock()
        request.state.user = MagicMock(tenant_id=str(tenant_uuid))
        request.state.api_key = None
        request.headers = {}

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        response = await middleware.dispatch(request, call_next)

        assert response.headers["X-Tenant-ID"] == str(tenant_uuid)


class TestGetTenantId:
    """Test get_tenant_id helper function."""

    def test_get_tenant_id_from_request_state(self) -> None:
        """Should get tenant_id from request state."""
        tenant_uuid = UUID("12345678-1234-1234-1234-123456789012")
        request = MagicMock()
        request.state.tenant_id = tenant_uuid

        result = get_tenant_id(request)

        assert result == tenant_uuid

    def test_get_tenant_id_returns_default_when_missing(self) -> None:
        """Should return default tenant when not set."""
        request = MagicMock()
        # Simulate missing attribute
        del request.state.tenant_id

        result = get_tenant_id(request)

        assert result == DEFAULT_TENANT_ID


class TestDefaultTenantId:
    """Test DEFAULT_TENANT_ID constant."""

    def test_default_tenant_is_valid_uuid(self) -> None:
        """Default tenant should be a valid UUID."""
        assert isinstance(DEFAULT_TENANT_ID, UUID)

    def test_default_tenant_is_zero_uuid(self) -> None:
        """Default tenant should be the zero UUID."""
        assert str(DEFAULT_TENANT_ID) == "00000000-0000-0000-0000-000000000000"
