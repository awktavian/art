"""Marketplace Routes - Plugin management."""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import admin, public

    router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

    # Include sub-routers (support both lazy and eager patterns)
    for module in [public, admin]:
        if hasattr(module, "get_router"):
            sub_router = module.get_router()
        else:
            sub_router = module.router
        router.include_router(sub_router)

    return router


__all__ = ["get_router"]
