"""
Billing Routes - Consolidated billing functionality.

Consolidation: October 3, 2025
Before: billing_admin.py, billing_experience.py, billing_stripe.py (3 files)
After: billing/ directory with admin.py, experience.py, stripe.py

All routers exposed at same paths for backward compatibility.
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import admin, experience, stripe

    router = APIRouter(prefix="/api/billing", tags=["billing"])

    # Include all sub-routers (support both lazy and eager patterns)
    # Admin routes go directly under /billing (no /admin prefix for backward compatibility)
    for module, prefix in [(admin, ""), (experience, "/experience"), (stripe, "/stripe")]:
        if hasattr(module, "get_router"):
            sub_router = module.get_router()
        else:
            sub_router = module.router

        if prefix:
            router.include_router(sub_router, prefix=prefix)
        else:
            router.include_router(sub_router)

    return router


__all__ = ["get_router"]
