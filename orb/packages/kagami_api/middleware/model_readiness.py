"""Model Readiness Middleware — Enforce Model Availability Before Serving.

Guards endpoints that depend on heavy models:
- World model routes
- Embedding routes
- LLM-based routes (generate, intent routing, etc.)
- Inference endpoints

Pattern:
    @router.get("/generate")
    @require_model_ready("llm_standard")
    async def generate(request: GenerateRequest) -> GenerateResponse:
        # LLM is guaranteed to be loaded here
        ...

Or use middleware to guard all routes under a path:
    app.add_middleware(
        ModelReadinessMiddleware,
        required_models=["world_model", "encoder"],
        excluded_paths=["/health", "/startup/*"]
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException, Request
from kagami.boot.model_loader import get_model_loader_state
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Type variable for the wrapped async function
F = TypeVar("F", bound=Callable[..., Any])


def require_model_ready(*model_names: str) -> Callable[[F], F]:
    """Decorator to enforce model readiness before endpoint execution.

    Usage:
        @router.post("/generate")
        @require_model_ready("llm_standard", "encoder")
        async def generate(request: GenerateRequest) -> GenerateResponse:
            # LLM and encoder are guaranteed to be loaded
            ...

    Args:
        model_names: Names of required models (space-separated or multiple args)

    Raises:
        HTTPException(503): If any required model is not ready
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            loader = get_model_loader_state()

            # Check each required model
            missing_models = [m for m in model_names if not loader.is_ready(m)]

            if missing_models:
                progress = loader.get_progress()
                loading_models = progress.get("models_loading", [])

                if loading_models:
                    # Still loading - 425 Too Early
                    raise HTTPException(
                        status_code=425,
                        detail=f"Required models still loading: {', '.join(missing_models)}",
                    )
                else:
                    # Failed to load - 503 Service Unavailable
                    raise HTTPException(
                        status_code=503,
                        detail=f"Required models unavailable: {', '.join(missing_models)}",
                    )

            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


class ModelReadinessMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce model availability for all requests.

    Protects heavy-model endpoints from being called before models are ready.

    Usage:
        from kagami_api.middleware.model_readiness import ModelReadinessMiddleware

        app = FastAPI()
        app.add_middleware(
            ModelReadinessMiddleware,
            required_models=["world_model"],
            excluded_paths=["/health", "/startup", "/docs", "/openapi.json"],
            defer_check_for_paths=["/api/v1/lightweight/*"]
        )

    Args:
        required_models: List of model names that must be ready
        excluded_paths: Paths that bypass the check (glob patterns supported)
        defer_check_for_paths: Paths that return 425 if loading (vs 503 if failed)
    """

    def __init__(
        self,
        app: FastAPI,
        required_models: list[str] | None = None,
        excluded_paths: list[str] | None = None,
        defer_check_for_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.required_models = required_models or ["world_model", "encoder"]
        self.excluded_paths = excluded_paths or [
            "/health",
            "/startup",
            "/docs",
            "/openapi.json",
            "/.well-known",
        ]
        self.defer_check_for_paths = defer_check_for_paths or []

    def _should_check_readiness(self, path: str) -> bool:
        """Determine if path should be subject to readiness check."""
        # Check excluded paths
        for excluded in self.excluded_paths:
            if self._path_matches(path, excluded):
                return False

        return True

    def _is_defer_check_path(self, path: str) -> bool:
        """Check if this path should defer rather than fail."""
        for pattern in self.defer_check_for_paths:
            if self._path_matches(path, pattern):
                return True
        return False

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        """Match path against glob-like pattern."""
        import fnmatch

        return fnmatch.fnmatch(path, pattern)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Check model readiness before processing request."""
        if not self._should_check_readiness(request.url.path):
            # Skip check for this path
            return await call_next(request)  # type: ignore[no-any-return]

        loader = get_model_loader_state()

        # Check each required model
        missing_models = [m for m in self.required_models if not loader.is_ready(m)]

        if not missing_models:
            # All models ready, proceed
            return await call_next(request)  # type: ignore[no-any-return]

        # Some models missing - determine response
        progress = loader.get_progress()
        loading_models = progress.get("models_loading", [])
        is_defer_path = self._is_defer_check_path(request.url.path)

        if loading_models or is_defer_path:
            # Still loading - return 425 Too Early
            return Response(
                content=f"System initializing, required models still loading: {', '.join(missing_models)}",
                status_code=425,
                media_type="text/plain",
            )
        else:
            # Failed to load - return 503 Service Unavailable
            return Response(
                content=f"System unavailable, required models failed to load: {', '.join(missing_models)}",
                status_code=503,
                media_type="text/plain",
            )


__all__ = ["ModelReadinessMiddleware", "require_model_ready"]
