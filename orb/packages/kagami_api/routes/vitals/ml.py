"""ML Vitals - Machine learning component health.

Reports on:
- Embedding service (semantic vs hash fallback)
- Vector search (Weaviate)
- World model (KagamiWorldModel)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/ml", tags=["vitals"])

    @router.get("/")
    async def ml_health() -> JSONResponse:
        """Get ML component health status."""
        health: dict[str, Any] = {"status": "operational", "components": {}}

        # Embeddings
        try:
            from kagami.core.services.embedding_service import get_embedding_service

            service = get_embedding_service()
            health["components"]["embeddings"] = {
                "status": "healthy" if service.is_semantic else "degraded",
                "mode": "semantic" if service.is_semantic else "hash_fallback",
                "dimension": service.embedding_dim,
            }
        except Exception as e:
            health["components"]["embeddings"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"

        # Vector search (Dec 7, 2025: Weaviate replaces RedisFS)
        try:
            from kagami.core.services.storage_routing import get_storage_router

            router = get_storage_router()
            status = router.get_status()
            health["components"]["vector_search"] = {
                "status": "healthy" if status["weaviate"]["enabled"] else "not_ready",
                "backend": "weaviate",
                "semantic_enabled": status["weaviate"]["enabled"],
            }
        except Exception as e:
            health["components"]["vector_search"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"

        # World model
        try:
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()
            if service:
                health["components"]["world_model"] = {
                    "status": "healthy" if service.is_available else "not_loaded",  # type: ignore[attr-defined]
                    "type": "KagamiWorldModel(HARDENED)" if service.is_available else None,  # type: ignore[attr-defined]
                    "features": service._get_feature_status() if service.is_available else {},  # type: ignore[attr-defined]
                }
            else:
                health["components"]["world_model"] = {"status": "not_initialized"}
        except Exception as e:
            health["components"]["world_model"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"

        # Return 200 unless actual errors
        code = (
            200 if all(c.get("status") != "error" for c in health["components"].values()) else 503
        )
        return JSONResponse(content=health, status_code=code)

    @router.get("/embeddings")
    async def embeddings_detail() -> JSONResponse:
        """Detailed embedding service health."""
        try:
            from kagami.core.services.embedding_service import get_embedding_service

            service = get_embedding_service()
            return JSONResponse(
                content={
                    "status": "healthy" if service.is_semantic else "degraded",
                    "mode": "semantic" if service.is_semantic else "hash_fallback",
                    "model_name": service.model_name,
                    "embedding_dim": service.embedding_dim,
                    "native_dim": getattr(service, "native_dim", service.embedding_dim),
                    "ring_buffer_size": len(service._ring_buffer),  # type: ignore[attr-defined]
                }
            )
        except Exception as e:
            return JSONResponse(content={"status": "error", "error": str(e)}, status_code=500)

    return router
