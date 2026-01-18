"""Admin API routes for Kagami Enterprise.

Provides administrative endpoints for:
- Enterprise authentication configuration (SAML, LDAP)
- Audit log access
- System configuration

RALPH Week 3 - Enterprise Features
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the admin API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    from . import enterprise

    router = APIRouter(tags=["admin"])

    # Include enterprise settings
    if hasattr(enterprise, "get_router"):
        router.include_router(enterprise.get_router())
    else:
        router.include_router(enterprise.router)  # type: ignore[attr-defined]

    return router


__all__ = ["get_router"]
