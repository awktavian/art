"""Tests for startup diagnostics routes.

Tests the wiring of:
- Startup routes in route_registry
- ModelLoaderState initialization in wiring.py
- Model readiness middleware
- Readiness endpoints for Kubernetes probes
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from fastapi.testclient import TestClient

from kagami.boot.model_loader import (
    LoaderPhase,
    ModelLoadState,
    ModelLoaderState,
    get_model_loader_state,
    reset_model_loader_state,
)


class TestModelLoaderState:
    """Tests for ModelLoaderState singleton and tracking."""

    def test_singleton_pattern(self) -> None:
        """Test that ModelLoaderState uses singleton pattern."""
        reset_model_loader_state()
        loader1 = get_model_loader_state()
        loader2 = get_model_loader_state()

        assert loader1 is loader2, "Should return same instance"

    @pytest.mark.asyncio
    async def test_initialize_registers_models(self) -> None:
        """Test that initialize() registers all known models."""
        reset_model_loader_state()
        loader = get_model_loader_state()

        await loader.initialize()

        progress = loader.get_progress()
        assert "details" in progress
        assert len(progress["details"]) >= 4  # At least world_model, encoder, etc.

    @pytest.mark.asyncio
    async def test_mark_loading_and_ready(self) -> None:
        """Test model state transitions."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Mark world_model as loading
        await loader.mark_loading("world_model")
        assert loader.is_ready("world_model") is False

        # Mark as ready
        await loader.mark_ready("world_model")
        assert loader.is_ready("world_model") is True

    @pytest.mark.asyncio
    async def test_critical_models_ready(self) -> None:
        """Test critical models readiness check."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Initially not ready
        assert loader.is_critical_ready() is False

        # Mark all critical models as ready
        for model in loader.CRITICAL_MODELS:
            await loader.mark_ready(model)

        assert loader.is_critical_ready() is True

    @pytest.mark.asyncio
    async def test_phase_transitions(self) -> None:
        """Test LoaderPhase state machine."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Initially STARTUP
        assert loader.get_phase() == LoaderPhase.STARTUP

        # After critical models ready -> READY
        for model in loader.CRITICAL_MODELS:
            await loader.mark_ready(model)
        assert loader.get_phase() == LoaderPhase.READY

        # After failure -> DEGRADED
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()
        await loader.mark_failed("world_model", "Test error")
        assert loader.get_phase() == LoaderPhase.DEGRADED

    @pytest.mark.asyncio
    async def test_get_progress(self) -> None:
        """Test progress reporting."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        progress = loader.get_progress()

        assert "phase" in progress
        assert "elapsed_seconds" in progress
        assert "models_ready" in progress
        assert "models_loading" in progress
        assert "models_failed" in progress
        assert "overall_readiness" in progress
        assert "details" in progress

        # Check structure of details
        assert isinstance(progress["details"], dict)
        for _name, state_dict in progress["details"].items():
            assert "status" in state_dict
            assert "ready" in state_dict
            assert "elapsed_ms" in state_dict

    @pytest.mark.asyncio
    async def test_get_health(self) -> None:
        """Test health reporting."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        health = loader.get_health()

        assert "critical_models_ready" in health
        assert "critical_models_failed" in health
        assert "phase" in health
        assert "readiness_score" in health

        # When nothing is ready
        assert health["critical_models_ready"] is False
        assert health["critical_models_failed"] is False

    @pytest.mark.asyncio
    async def test_mark_failed_error_tracking(self) -> None:
        """Test error tracking on model failure."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        error_msg = "Out of memory"
        await loader.mark_failed("world_model", error_msg)

        progress = loader.get_progress()
        assert "world_model" in progress["models_failed"]

        details = progress["details"]["world_model"]
        assert details["status"] == "failed"
        assert details["failed"] is True
        assert error_msg in details["error"]


class TestStartupRoutes:
    """Tests for startup diagnostics API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with startup routes."""
        # Import here to avoid circular dependencies
        from fastapi import FastAPI

        from kagami_api.routes import startup

        app = FastAPI()
        app.include_router(startup.router, prefix="/api/v1")

        return TestClient(app)

    @pytest.mark.asyncio
    async def test_progress_endpoint_basic(self, client: TestClient) -> None:
        """Test GET /api/v1/startup/progress returns valid response."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        response = client.get("/api/v1/startup/progress")
        assert response.status_code == 200

        data = response.json()
        assert "phase" in data
        assert data["phase"] in ["startup", "ready", "degraded", "error"]

    @pytest.mark.asyncio
    async def test_health_endpoint_basic(self, client: TestClient) -> None:
        """Test GET /api/v1/startup/health returns valid response."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        response = client.get("/api/v1/startup/health")
        assert response.status_code == 200

        data = response.json()
        assert "critical_models_ready" in data
        assert "phase" in data
        assert "readiness_score" in data

    @pytest.mark.asyncio
    async def test_ready_endpoint_startup_returns_425(self, client: TestClient) -> None:
        """Test GET /api/v1/startup/ready returns 425 during startup."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Models not ready -> 425 Too Early
        response = client.get("/api/v1/startup/ready")
        assert response.status_code == 425

    @pytest.mark.asyncio
    async def test_ready_endpoint_ready_returns_204(self, client: TestClient) -> None:
        """Test GET /api/v1/startup/ready returns 204 when ready."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Mark all critical models ready
        for model in loader.CRITICAL_MODELS:
            await loader.mark_ready(model)

        response = client.get("/api/v1/startup/ready")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_ready_endpoint_degraded_returns_503(self, client: TestClient) -> None:
        """Test GET /api/v1/startup/ready returns 503 when degraded."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Mark a critical model as failed
        await loader.mark_failed("world_model", "Test failure")

        response = client.get("/api/v1/startup/ready")
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_diagnostics_endpoint_basic(self, client: TestClient) -> None:
        """Test GET /api/v1/startup/diagnostics returns valid response."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        response = client.get("/api/v1/startup/diagnostics")
        assert response.status_code == 200

        data = response.json()
        assert "progress" in data
        assert "recommendations" in data
        assert "estimated_ready_seconds" in data

    @pytest.mark.asyncio
    async def test_diagnostics_includes_failed_model_errors(self, client: TestClient) -> None:
        """Test diagnostics includes errors from failed models."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        error_msg = "CUDA out of memory"
        await loader.mark_failed("world_model", error_msg)

        response = client.get("/api/v1/startup/diagnostics")
        assert response.status_code == 200

        data = response.json()
        recommendations = data["recommendations"]

        # Should include the failed model error in recommendations
        has_error_rec = any("world_model" in rec and "failed" in rec for rec in recommendations)
        assert has_error_rec


class TestModelReadinessMiddleware:
    """Tests for model readiness middleware."""

    @pytest.fixture
    def app_with_middleware(self) -> FastAPI:
        """Create FastAPI app with model readiness middleware."""
        from fastapi import FastAPI

        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        app = FastAPI()

        # Add a test endpoint that requires world_model
        @app.get("/api/test/requires-model")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        # Add middleware
        app.add_middleware(
            ModelReadinessMiddleware,  # type: ignore[arg-type]
            required_models=["world_model"],
            excluded_paths=["/health", "/startup/*"],
        )

        return app

    @pytest.mark.asyncio
    async def test_middleware_excludes_startup_paths(self, app_with_middleware: FastAPI) -> None:
        """Test middleware excludes startup paths."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        client = TestClient(app_with_middleware)

        # Startup paths should not be blocked
        response = client.get("/startup/progress")
        assert response.status_code in [404, 200]  # Not found is OK, middleware didn't block

    @pytest.mark.asyncio
    async def test_middleware_blocks_when_model_loading(self, app_with_middleware: FastAPI) -> None:
        """Test middleware returns 425 when models are loading."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        client = TestClient(app_with_middleware)

        # Mark model as loading (not ready)
        await loader.mark_loading("world_model")

        response = client.get("/api/test/requires-model")
        assert response.status_code == 425

    @pytest.mark.asyncio
    async def test_middleware_allows_when_model_ready(self, app_with_middleware: FastAPI) -> None:
        """Test middleware allows request when model is ready."""
        reset_model_loader_state()
        loader = get_model_loader_state()
        await loader.initialize()

        # Mark model as ready
        await loader.mark_ready("world_model")

        client = TestClient(app_with_middleware)
        response = client.get("/api/test/requires-model")
        assert response.status_code == 200


class TestRouteRegistration:
    """Tests for startup routes in route registry."""

    def test_startup_routes_registered(self) -> None:
        """Test startup routes are registered in route registry."""
        from unittest.mock import MagicMock

        from kagami_api.route_registry import register_all_routes

        app = MagicMock()
        app.include_router = MagicMock()
        app.routes = []

        register_all_routes(app)

        # Check that include_router was called
        calls = app.include_router.call_args_list

        # Check for startup router in calls
        # The router is passed as first positional arg
        startup_calls = []
        for call in calls:
            args, _kwargs = call
            if args:
                router = args[0]
                # Check if router has startup routes
                if hasattr(router, "routes"):
                    route_paths = {route.path for route in router.routes}
                    if "/startup/progress" in route_paths or "/startup/health" in route_paths:
                        startup_calls.append(call)

        assert (
            len(startup_calls) >= 1
        ), f"Startup routes should be registered. Total calls: {len(calls)}"

    def test_startup_router_has_all_endpoints(self) -> None:
        """Test startup router has all 4 endpoints."""
        from kagami_api.routes import startup

        routes = startup.router.routes
        route_paths = {route.path for route in routes}

        assert "/startup/progress" in route_paths
        assert "/startup/health" in route_paths
        assert "/startup/ready" in route_paths
        assert "/startup/diagnostics" in route_paths


__all__ = [
    "TestModelLoaderState",
    "TestModelReadinessMiddleware",
    "TestRouteRegistration",
    "TestStartupRoutes",
]
