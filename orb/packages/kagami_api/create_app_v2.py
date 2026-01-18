"""Streamlined FastAPI application factory (V2).

Refactored from 3,009-line create_app monster into focused orchestration.
All heavy lifting extracted into helper modules.

Complexity: <50 (down from 428)
"""

import logging
import os

# Load environment variables from .env EARLY (before any other imports)
# dotenv is optional - no error if not installed
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Install uvloop for high-performance async (2-4x throughput)
# Must happen BEFORE any event loops are created
try:
    from kagami.core.async_utils import install_uvloop

    install_uvloop()
except ImportError:
    pass  # async_utils not available yet

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Version
try:
    from kagami._version import __version__ as _pkg_version
except Exception:
    _pkg_version = os.getenv("KAGAMI_VERSION", "0.0.0")

# ORJSON availability
try:
    from fastapi.responses import ORJSONResponse as _ORJSONResponse

    _ORJSON_AVAILABLE = True
except Exception:
    _ORJSON_AVAILABLE = False


def create_app_v2(
    title: str = "K os API",
    description: str = "AI Life Companions API",
    version: str = _pkg_version,
    allowed_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure FastAPI application (V2 - streamlined).

    Replaces massive 3,009-line create_app with focused orchestration.
    All functionality preserved via helper modules.

    Args:
        title: API title
        description: API description
        version: API version
        allowed_origins: CORS origins (None = auto-detect)

    Returns:
        Configured FastAPI application
    """
    # Step 1: Environment setup
    from kagami_api.factory_helpers import (
        setup_test_mode_stubs,
        setup_transformers_hardening,
    )
    from kagami_api.provider_registry import register_api_providers

    setup_test_mode_stubs()
    setup_transformers_hardening()
    register_api_providers()

    # Test mode should be deterministic and lightweight by default.
    # Many API tests set KAGAMI_TEST_MODE=1 but do not set LIGHTWEIGHT_STARTUP
    # before calling create_app(); ensure the lightweight stack is used.
    try:
        if os.getenv("KAGAMI_TEST_MODE", "0").lower() in ("1", "true", "yes", "on"):
            os.environ.setdefault("LIGHTWEIGHT_STARTUP", "1")
    except Exception:
        pass  # Environment access may fail in restricted environments

    # Step 2: Install uvloop if available (optional performance optimization)
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        pass  # uvloop is optional, falls back to standard asyncio

    # Step 3: Create FastAPI instance
    from kagami_api.lifespan_v2 import lifespan_v2

    use_orjson = os.getenv("DISABLE_ORJSON", "0").lower() not in ("1", "true") and _ORJSON_AVAILABLE

    env_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
    docs_public = os.getenv("DOCS_PUBLIC", "0").lower() in ("1", "true")

    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan_v2,
        default_response_class=(_ORJSONResponse if use_orjson else JSONResponse),
        docs_url=("/docs" if (not env_prod or docs_public) else None),
        redoc_url=("/redoc" if (not env_prod or docs_public) else None),
        openapi_url=("/openapi.json" if (not env_prod or docs_public) else None),
    )

    # Step 4: Configure middleware
    from kagami_api.factory_helpers import (
        configure_cors,
        setup_compression_middleware,
        setup_request_size_limit,
        setup_security_middleware,
    )

    configure_cors(app, allowed_origins)
    setup_security_middleware(app)
    setup_compression_middleware(app)
    setup_request_size_limit(app)

    # Step 4a: Wire global middlewares (rate limiting, idempotency, receipts, telemetry, quotas)
    # NOTE: Performance middleware disabled - request coalescing causes issues with streaming responses
    # Application-level caching (health, metrics) is more reliable
    from kagami_api.middleware_stack import configure_gateway_middlewares

    configure_gateway_middlewares(app, logger=logger)

    # Step 4b: Initialize single metrics surface (/metrics)
    try:
        from kagami_observability.metrics_prometheus import init_metrics

        # Use explicit METRICS_PUBLIC configuration - no implicit defaults
        # Set METRICS_PUBLIC=1 in env if you want public metrics
        init_metrics(app)
        try:
            app.state.metrics_initialized = True
        except Exception:
            pass
        logger.info("✓ Metrics surface initialized at /metrics")
    except Exception as e:
        logger.warning(f"Metrics initialization failed: {e}")

    # Step 5: Register all routes
    from kagami_api.route_registry import register_all_routes

    register_all_routes(app)

    # Step 5b: Emit route summary for ops visibility
    try:
        routes = []
        for rt in app.routes:
            try:
                p = getattr(rt, "path", None)
                name = getattr(rt, "name", "")
                methods = sorted(getattr(rt, "methods", []))
                if p:
                    routes.append((p, name, methods))
            except Exception:
                pass
        # Deduplicate by path
        seen = set()
        uniq = []
        for p, n, m in routes:
            if p not in seen:
                seen.add(p)
                uniq.append((p, n, m))
        # Too noisy for normal startup; keep available in debug logs.
        logger.debug(
            "Route summary:\n" + "\n".join(f"  {p}  methods={m}" for p, _, m in uniq[:100])
        )
    except Exception:
        pass

    # Step 6: Setup error handlers
    from kagami_api.error_handlers import setup_error_handlers

    setup_error_handlers(app)

    # Step 7: Mount static files
    from kagami_api.static_files import mount_static_files

    mount_static_files(app)

    # Step 8: Attach Socket.IO server at /socket.io
    # IMPORTANT: We wrap the FastAPI app with Socket.IO's ASGIApp, which intercepts
    # Socket.IO requests and forwards all other requests to FastAPI.
    wrapped_app = app  # Default: no wrapping
    try:
        import socketio as _socketio

        from kagami_api.socketio_server import (
            create_socketio_app,
            set_socketio_server,
        )

        sio = create_socketio_app(cors_allowed_origins=allowed_origins, async_mode="asgi")
        # Wrap FastAPI with Socket.IO ASGIApp - this becomes the top-level ASGI app
        # Socket.IO will handle /socket.io/* requests and forward everything else to FastAPI
        wrapped_app = _socketio.ASGIApp(sio, other_asgi_app=app)

        # CRITICAL: Apply security middleware to the wrapped app
        # Socket.IO's ASGIApp wrapper intercepts requests BEFORE FastAPI middleware,
        # so we must apply security headers to the outer wrapped app
        from kagami_api.security_middleware import SecurityMiddleware

        wrapped_app = SecurityMiddleware(wrapped_app)  # type: ignore[assignment]

        set_socketio_server(sio)
        try:
            app.state.socketio_ready = True
        except Exception:
            pass
        logger.info(
            "✓ Socket.IO wrapped around FastAPI with security middleware (handles /socket.io/* paths)"
        )
    except Exception as e:
        logger.warning(f"Socket.IO initialization failed: {e}")
        wrapped_app = app  # Fall back to unwrapped app

    # Step 9: Mount MCP server (if enabled)
    if os.getenv("KAGAMI_MCP_ENABLED", "1").lower() in ("1", "true", "yes", "on"):
        try:
            from kagami.core.services.mcp import get_mcp_asgi_app

            mcp_app = get_mcp_asgi_app()  # type: ignore[func-returns-value]
            if mcp_app:
                app.mount("/mcp", mcp_app)
                try:
                    app.state.mcp_ready = True
                except Exception:
                    pass
                logger.info("✓ MCP server mounted at /mcp")
            else:
                logger.debug("MCP server not available (fastmcp not installed)")
        except Exception as e:
            logger.warning(f"MCP server initialization failed: {e}")

    logger.info(f"✅ K os API created: {len(app.routes)} routes, {version}")

    # Return the wrapped app (with Socket.IO) if available, otherwise the plain FastAPI app
    return wrapped_app


__all__ = ["create_app_v2"]
