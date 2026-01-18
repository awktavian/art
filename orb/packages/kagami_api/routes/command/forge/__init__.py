"""Forge generation routes - aggregated router.

Content generation capabilities:
- /api/command/forge/generate - Character generation
- /api/command/forge/animate/* - Animation
- /api/command/forge/safety/* - Content safety
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import (
        animate,
        content_safety,
        generate,
        image_generation,
        intent,
        validate,
    )

    router = APIRouter()

    # Include sub-routers (support both lazy and eager patterns)
    for module in [intent, generate, animate, image_generation, validate, content_safety]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        else:
            router.include_router(module.router)

    return router


__all__ = ["get_router"]
