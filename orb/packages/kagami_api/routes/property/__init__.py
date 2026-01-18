"""Property Intelligence API routes.

Exposes endpoints for property data:
- POST /property/lookup - Get property blob by address
- GET /property/orientation - Get building orientation
- GET /property/solar - Get solar potential
- DELETE /property/cache - Invalidate cached data
- GET /property/cache/stats - Get cache statistics

Example:
    >>> from kagami_api.routes.property import router
    >>> # Include in FastAPI app
"""

from kagami_api.property.router import router

__all__ = ["router"]


def get_router():
    """Get the property router for inclusion in app."""
    return router
