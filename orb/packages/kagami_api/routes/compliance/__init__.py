"""Compliance routes."""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import audit_enhanced, policy

    router = APIRouter(prefix="/api/compliance", tags=["compliance"])

    # Include sub-routers (support both lazy and eager patterns)
    for module in [audit_enhanced, policy]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        elif hasattr(module, "router"):
            router.include_router(module.router)

    return router


__all__ = ["get_router"]
