"""Tests for model readiness middleware.

Covers:
- require_model_ready decorator
- ModelReadinessMiddleware path matching
- 425 (Too Early) vs 503 (Service Unavailable) responses
- Path exclusion patterns
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.tier_unit


class MockModelLoaderState:
    """Mock model loader state for testing."""

    def __init__(
        self,
        ready_models: set[str] | None = None,
        loading_models: list[str] | None = None,
    ) -> None:
        self.ready_models = ready_models or set()
        self.loading_models = loading_models or []

    def is_ready(self, model_name: str) -> bool:
        return model_name in self.ready_models

    def get_progress(self) -> dict:
        return {"models_loading": self.loading_models}


class TestRequireModelReadyDecorator:
    """Test the @require_model_ready decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_when_models_ready(self) -> None:
        """Decorator should allow execution when models are ready."""
        from kagami_api.middleware.model_readiness import require_model_ready

        mock_loader = MockModelLoaderState(ready_models={"llm_standard", "encoder"})

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):

            @require_model_ready("llm_standard", "encoder")
            async def test_endpoint() -> str:
                return "success"

            result = await test_endpoint()
            assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_raises_425_when_loading(self) -> None:
        """Decorator should raise 425 when models are still loading."""
        from kagami_api.middleware.model_readiness import require_model_ready

        mock_loader = MockModelLoaderState(
            ready_models=set(),
            loading_models=["llm_standard"],
        )

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):

            @require_model_ready("llm_standard")
            async def test_endpoint() -> str:
                return "success"

            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint()

            assert exc_info.value.status_code == 425
            assert "loading" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_decorator_raises_503_when_failed(self) -> None:
        """Decorator should raise 503 when models failed to load."""
        from kagami_api.middleware.model_readiness import require_model_ready

        mock_loader = MockModelLoaderState(
            ready_models=set(),
            loading_models=[],  # No models loading = failed
        )

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):

            @require_model_ready("world_model")
            async def test_endpoint() -> str:
                return "success"

            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint()

            assert exc_info.value.status_code == 503
            assert "unavailable" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_decorator_lists_missing_models(self) -> None:
        """Decorator should list missing models in error message."""
        from kagami_api.middleware.model_readiness import require_model_ready

        mock_loader = MockModelLoaderState(ready_models={"encoder"})

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):

            @require_model_ready("llm_standard", "encoder", "world_model")
            async def test_endpoint() -> str:
                return "success"

            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint()

            # Should mention llm_standard and world_model (not encoder)
            assert "llm_standard" in exc_info.value.detail
            assert "world_model" in exc_info.value.detail


class TestModelReadinessMiddleware:
    """Test ModelReadinessMiddleware class."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create mock FastAPI app."""
        return MagicMock()

    def test_middleware_init_defaults(self, mock_app: MagicMock) -> None:
        """Middleware should have sensible defaults."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        middleware = ModelReadinessMiddleware(mock_app)

        assert "world_model" in middleware.required_models
        assert "/health" in middleware.excluded_paths

    def test_middleware_custom_config(self, mock_app: MagicMock) -> None:
        """Middleware should accept custom configuration."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        middleware = ModelReadinessMiddleware(
            mock_app,
            required_models=["custom_model"],
            excluded_paths=["/custom/*"],
            defer_check_for_paths=["/deferred/*"],
        )

        assert middleware.required_models == ["custom_model"]
        assert "/custom/*" in middleware.excluded_paths
        assert "/deferred/*" in middleware.defer_check_for_paths

    def test_path_matching_exact(self, mock_app: MagicMock) -> None:
        """Path matching should work for exact matches."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        middleware = ModelReadinessMiddleware(mock_app, excluded_paths=["/health"])

        assert middleware._path_matches("/health", "/health") is True
        assert middleware._path_matches("/health/live", "/health") is False

    def test_path_matching_glob(self, mock_app: MagicMock) -> None:
        """Path matching should support glob patterns."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        middleware = ModelReadinessMiddleware(mock_app)

        assert middleware._path_matches("/api/v1/test", "/api/*") is True
        assert middleware._path_matches("/other/path", "/api/*") is False

    def test_should_check_readiness_excludes_health(self, mock_app: MagicMock) -> None:
        """Health endpoints should be excluded from readiness check."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        middleware = ModelReadinessMiddleware(mock_app)

        assert middleware._should_check_readiness("/health") is False
        assert middleware._should_check_readiness("/docs") is False
        assert middleware._should_check_readiness("/api/generate") is True

    @pytest.mark.asyncio
    async def test_middleware_dispatch_allows_excluded_paths(
        self, mock_app: MagicMock
    ) -> None:
        """Middleware should allow excluded paths without checking models."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        middleware = ModelReadinessMiddleware(mock_app)

        request = MagicMock()
        request.url.path = "/health"
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_dispatch_allows_ready_models(
        self, mock_app: MagicMock
    ) -> None:
        """Middleware should allow requests when models are ready."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        mock_loader = MockModelLoaderState(ready_models={"world_model", "encoder"})

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):
            middleware = ModelReadinessMiddleware(mock_app)

            request = MagicMock()
            request.url.path = "/api/generate"
            call_next = AsyncMock(return_value=MagicMock(status_code=200))

            response = await middleware.dispatch(request, call_next)

            call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_dispatch_returns_425_when_loading(
        self, mock_app: MagicMock
    ) -> None:
        """Middleware should return 425 when models are loading."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        mock_loader = MockModelLoaderState(
            ready_models=set(),
            loading_models=["world_model"],
        )

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):
            middleware = ModelReadinessMiddleware(mock_app)

            request = MagicMock()
            request.url.path = "/api/generate"
            call_next = AsyncMock()

            response = await middleware.dispatch(request, call_next)

            assert response.status_code == 425
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_dispatch_returns_503_when_failed(
        self, mock_app: MagicMock
    ) -> None:
        """Middleware should return 503 when models failed to load."""
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        mock_loader = MockModelLoaderState(
            ready_models=set(),
            loading_models=[],
        )

        with patch(
            "kagami_api.middleware.model_readiness.get_model_loader_state",
            return_value=mock_loader,
        ):
            middleware = ModelReadinessMiddleware(mock_app)

            request = MagicMock()
            request.url.path = "/api/generate"
            call_next = AsyncMock()

            response = await middleware.dispatch(request, call_next)

            assert response.status_code == 503
            call_next.assert_not_called()
