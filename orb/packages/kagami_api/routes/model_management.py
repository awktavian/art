"""Model Management API - Progressive Loading Control.

Endpoints at /api/models:
- GET /status - Current progressive loading status
- POST /upgrade/{size} - Upgrade to larger model
- GET /info - Model size information

Related: /api/llm/performance/* for runtime performance tuning.
See also: llm_performance.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.safety import enforce_tier1
from kagami.core.safety.cbf_integration import check_cbf_for_operation

from kagami_api.response_schemas import get_error_responses
from kagami_api.security import require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/models", tags=["mind"])

    @router.get(
        "/status",
        responses=get_error_responses(429, 500),
    )
    @enforce_tier1("rate_limit")
    async def get_model_status() -> dict[str, Any]:
        """Get current progressive loading status

        Returns:
            Status of all models (loaded, loading, available)
        """
        try:
            from kagami.core.services.llm.progressive_loader import get_progressive_loader

            loader = get_progressive_loader()
            status = loader.get_status()

            return {
                "status": "success",
                "progressive_loading_enabled": True,
                **status,
            }

        except ImportError:
            return {
                "status": "unavailable",
                "progressive_loading_enabled": False,
                "message": "Progressive loading not available",
            }
        except Exception as e:
            logger.error(f"Failed to get model status: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.post(
        "/upgrade/{size}",
        responses=get_error_responses(400, 401, 403, 429, 500, 501),
    )
    @enforce_tier1("process")
    async def upgrade_to_model(size: str, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Upgrade to a larger model on-demand

        Args:
            size: Target model size (instant, standard, flagship, ultimate)

        Returns:
            Result of upgrade operation
        """
        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.models.upgrade",
            action="upgrade",
            target="model",
            params={"size": size},
            metadata={"endpoint": f"/api/models/upgrade/{size}"},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        try:
            from kagami.core.services.llm.progressive_loader import get_progressive_loader

            valid_sizes = ["instant", "standard", "flagship", "ultimate"]
            if size not in valid_sizes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid model size. Must be one of: {', '.join(valid_sizes)}",
                )

            loader = get_progressive_loader()

            # Check if already loaded
            status = loader.get_status()
            if size in status.get("models_loaded", []):
                return {
                    "status": "already_loaded",
                    "model": size,
                    "message": f"Model {size} is already loaded",
                }

            # Check if currently loading
            if size in status.get("models_loading", []):
                return {
                    "status": "loading",
                    "model": size,
                    "message": f"Model {size} is currently loading in background",
                }

            # Start upgrade (will block until complete)
            logger.info(f"Starting on-demand upgrade to {size} model...")
            await loader.upgrade_to(size)  # type: ignore

            return {
                "status": "success",
                "model": size,
                "message": f"Successfully upgraded to {size} model",
                "model_name": loader.get_model_info(size)["name"],  # type: ignore
            }

        except ImportError:
            raise HTTPException(
                status_code=501, detail="Progressive loading not available"
            ) from None
        except Exception as e:
            logger.error(f"Failed to upgrade model: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.get(
        "/info",
        responses=get_error_responses(429, 500, 501),
    )
    @enforce_tier1("rate_limit")
    async def get_models_info() -> dict[str, Any]:
        """Get information about all available model sizes

        Returns:
            Info about instant, standard, flagship, and ultimate models
        """
        try:
            from kagami.core.services.llm.progressive_loader import get_progressive_loader

            loader = get_progressive_loader()

            sizes = ["instant", "standard", "flagship", "ultimate"]
            models_info = {}

            for size in sizes:
                info = loader.get_model_info(size)  # type: ignore[arg-type]
                models_info[size] = info

            return {
                "status": "success",
                "models": models_info,
            }

        except ImportError:
            raise HTTPException(
                status_code=501, detail="Progressive loading not available"
            ) from None
        except Exception as e:
            logger.error(f"Failed to get models info: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    return router
