"""Static file mounting for FastAPI application.

Extracted from create_app to reduce complexity.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

logger = logging.getLogger(__name__)


def mount_static_files(app: FastAPI) -> None:
    """Mount static file directories for the application."""
    # Determine static directory path
    api_dir = Path(__file__).parent
    static_dir = api_dir / "static"

    if static_dir.exists():
        try:

            class _CachedStatic(StaticFiles):
                async def get_response(self, path, scope):  # type: ignore[no-untyped-def]
                    resp: Response = await super().get_response(path, scope)
                    # Set long-cache headers for immutable static assets
                    try:
                        resp.headers.setdefault(
                            "Cache-Control", "public, max-age=31536000, immutable"
                        )
                    except Exception:
                        pass
                    return resp

            app.mount("/static", _CachedStatic(directory=str(static_dir)), name="static")
            logger.info(f"✓ Static files mounted from {static_dir}")
        except Exception as e:
            logger.warning(f"Failed to mount static files: {e}")
    else:
        logger.debug("No static directory found (expected in production)")


__all__ = ["mount_static_files"]
