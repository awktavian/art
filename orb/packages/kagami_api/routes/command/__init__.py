"""Command API - Intent parsing, execution, content generation, and scheduling.

The command module handles:
- LANG/2 intent processing (parse, execute)
- Content generation via Forge
- Scheduling (routines, recurring tasks)

Endpoints at /api/command:
- POST /parse - Parse intent from text
- POST /execute - Execute parsed intent
- GET /suggestions - Autocomplete suggestions
- /forge/* - Content generation
- /schedule/* - Routines and recurring tasks
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import forge, routes, schedule

    router = APIRouter(tags=["command"])

    # Include sub-routers (support both lazy and eager patterns)
    for module in [routes, forge, schedule]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        else:
            router.include_router(module.router)

    return router


__all__ = ["get_router"]
