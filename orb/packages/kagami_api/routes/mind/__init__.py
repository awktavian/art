"""Mind API - Kagami's cognitive center.

The mind is where Kagami thinks:
- Thoughts: awareness, perception (/api/mind/thoughts)
- Insights: unified intelligence (/api/mind/insights)
- Goals: autonomous pursuit control (/api/mind/goals/*)
- Receipts: memory and audit trail (/api/mind/receipts/*)
- Learning: training and adaptation (/api/mind/learning/*)
- Dynamics: chaos and criticality (/api/mind/dynamics/*)

Endpoints:
- GET /thoughts - Recent thoughts
- GET /insights - Unified intelligence (brief + activity + suggestions)
- POST /sense - Unified sensorimotor (perceive/predict/act)
- GET /goals/status - Autonomous orchestrator status
- /receipts/* - Receipt memory system
- /learning/* - Training streams
- /dynamics/* - Chaos and criticality
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import dynamics, goals, learning, receipts, thoughts

    router = APIRouter(tags=["mind"])

    # Include sub-routers (they define their own full prefixes, support both patterns)
    for module in [thoughts, goals, receipts, learning, dynamics]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        else:
            router.include_router(module.router)

    return router


__all__ = ["get_router"]
