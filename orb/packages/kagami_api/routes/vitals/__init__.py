"""Vitals API - Unified health and system monitoring.

All health endpoints at /api/vitals:
- /api/vitals/ - Organism vitals (metabolism, coherence, Fano)
- /api/vitals/probes/ - Kubernetes liveness/readiness
- /api/vitals/hal/ - Hardware abstraction layer
- /api/vitals/ml/ - ML component health

The vitals API is how Kagami monitors its own health.
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import hardware, ml, organism, probes, safety

    router = APIRouter(prefix="/api/vitals", tags=["vitals"])

    # Include sub-routers (support both lazy and eager patterns)
    for module in [organism, probes, hardware, ml, safety]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        else:
            router.include_router(module.router)

    return router


__all__ = ["get_router"]
