"""Route registration helper - extracted from massive create_app function.

Handles all router include operations with proper error handling.
Reduces create_app complexity by ~300 points.
"""

import logging
import os
from collections.abc import Sequence
from enum import Enum
from typing import Any, Protocol

from fastapi import APIRouter


class SupportsRouterRegistration(Protocol):
    """Structural type for objects that behave like FastAPI applications."""

    @property
    def routes(self) -> Sequence[Any]: ...

    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = ...,
        tags: list[str | Enum] | None = ...,
    ) -> None: ...


logger = logging.getLogger(__name__)

# Track import errors for graceful degradation
_ROUTE_IMPORT_ERRORS: dict[str, Exception] = {}


def _include_router(
    app: SupportsRouterRegistration,
    router: Any,
    *,
    prefix: str | None = None,
    tags: Sequence[str | Enum] | None = None,
    name: str = "unknown",
) -> None:
    """Include router with error handling."""
    if router is None:
        err = _ROUTE_IMPORT_ERRORS.get(name)
        if err:
            logger.warning(f"Skipping {name} routes due to import error: {err}")
        return

    try:
        if prefix or tags:
            app.include_router(
                router,
                prefix=prefix or "",
                tags=list(tags) if tags is not None else [],
            )
        else:
            app.include_router(router)

        logger.info(f"✓ {name} routes loaded" + (f" ({prefix})" if prefix else ""))

    except Exception as e:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise
        logger.warning(f"Router include failed for {name} (dev continues): {e}")


def _get_router_from_module(module: Any) -> Any | None:
    """Extract router from a module, supporting both lazy and eager patterns.

    Args:
        module: Python module that may contain get_router() or router

    Returns:
        APIRouter instance or None
    """
    # Prefer lazy loading via get_router() factory function
    get_router_fn = getattr(module, "get_router", None)
    if callable(get_router_fn):
        return get_router_fn()

    # Fall back to eager loading via router attribute
    return getattr(module, "router", None)


def register_all_routes(app: SupportsRouterRegistration) -> None:
    """Register all K os API routes.

    Extracted from create_app to reduce complexity.
    Handles 100+ route registrations with proper error handling.

    Performance optimizations:
    - Lazy loading of heavy routes (forge, AR, etc.)
    - Supports both lazy (get_router factory) and eager (router attribute) patterns
    - Parallel import for independent routes
    - Skip optional routes in minimal boot mode
    """
    # Core routes - use safe imports to handle multiprocessing
    import importlib

    # All routes load synchronously - no lazy loading
    lazy_load_heavy = False

    # Startup/Diagnostics - Fast boot diagnostics (available immediately)
    try:
        from kagami_api.routes import startup

        _include_router(
            app, startup.router, prefix="/api/v1", name="Startup (diagnostics & progress)"
        )
    except Exception as e:
        logger.warning(f"Startup diagnostics routes unavailable: {e}")

    # Vitals (unified health reporting) - includes health probes, HAL, ML
    # Consolidated: health, ml_health, hal_health, vitals → /api/vitals
    try:
        from kagami_api.routes import vitals

        _include_router(app, _get_router_from_module(vitals), name="Vitals (unified health)")
    except Exception as e:
        logger.error(f"Failed to load vitals routes: {e}")

    # Core system routes
    try:
        core = importlib.import_module("kagami_api.routes.core")
        _include_router(app, _get_router_from_module(core), name="Core system routes")
    except Exception as e:
        logger.warning(f"Core routes unavailable: {e}")

    # HAL routes now part of vitals/hardware.py

    # User routes (auth, rbac, keys, settings)
    try:
        from kagami_api.routes import user

        _include_router(
            app, _get_router_from_module(user), name="User (auth, rbac, keys, settings)"
        )
    except Exception as e:
        logger.warning(f"User routes unavailable: {e}")

    # Receipts now part of mind/receipts/

    # Agent routes now part of colonies/agents/

    # Colonies Monitoring (consolidated: stream + agents + ui)
    try:
        from kagami_api.routes import colonies

        _include_router(app, _get_router_from_module(colonies), name="Colonies (unified)")
    except Exception as e:
        logger.warning(f"Colonies routes unavailable: {e}")

    # Vitals already registered above in unified health section

    # AGUI now part of colony/communication.py

    # Audio routes
    try:
        from kagami_api.routes import audio

        _include_router(app, _get_router_from_module(audio), name="Audio (TTS/STT/Multimodal)")

        # Model Management (Progressive Loading)
        from kagami_api.routes import model_management

        _include_router(app, _get_router_from_module(model_management), name="Model Management")
    except Exception as e:
        logger.warning(f"Audio/Model routes unavailable: {e}")

    # Plans & Task Management (Production feature)
    try:
        from kagami_api.routes import plans

        _include_router(app, _get_router_from_module(plans), name="Plans & Tasks")
    except Exception as e:
        logger.warning(f"Plans routes unavailable: {e}")

    # Metrics endpoint (critical for observability)
    # Note: Metrics endpoint is registered via init_metrics() in create_app_v2.py
    # No router needed - init_metrics adds /metrics endpoint directly to app
    # This check removed to eliminate unnecessary warning

    # Commercial API routes (E8, CBF, Fano) - standalone monetization APIs
    # NOTE: Import directly from modules to avoid circular dependency via kagami.api
    try:
        from kagami_api.compression_api import router as compression_router
        from kagami_api.routing_api import router as routing_router
        from kagami_api.safety_api import router as safety_router

        _include_router(app, compression_router, name="Compression API (E8 quantization)")
        _include_router(app, safety_router, name="Safety API (CBF verification)")
        _include_router(app, routing_router, name="Routing API (Fano coordination)")
    except Exception as e:
        logger.debug(f"Commercial API routes not available: {e}")

    # All other routes - bulk registration
    # NOTE: All routes define their own prefixes, so set prefix=None
    # Heavy routes (forge, AR, multimodal) marked for lazy loading
    route_configs = [
        # Core application routes (always load)
        ("command", None, ["command"], "Command (LANG/2)", False),
        # NOTE: predictions and learning routes DELETED (Jan 2, 2026)
        # They were heuristic stubs. Re-add when actual world model integration is ready.
        # Email Monitoring (January 4, 2026) — proactive service request tracking
        ("email", "/api/v1", ["email"], "Email (monitoring, service requests)", False),
        # System & infrastructure
        ("ar", None, None, "AR", True),  # lazy - very heavy (Audio2Face)
        # Smart Home (December 29, 2025)
        ("home", "/api/v1", ["home"], "Smart Home", False),
        # Smart Home Webhooks (January 6, 2026) — Control4/Lutron unauthenticated
        ("home_webhook", "/api/v1", ["home-webhook"], "Smart Home Webhooks (no auth)", False),
        # Client Devices (December 30, 2025) — Watch, Desktop, Hub, Vision
        ("clients", None, ["clients"], "Client Devices (WebSocket)", False),
        # Hub Fleet & OTA (January 2, 2026) — OTA updates, fleet management
        ("hub", "/api/v1", ["hub", "ota", "fleet"], "Hub Fleet & OTA", False),
        # visionOS Spatial Computing (December 30, 2025)
        ("vision", None, ["vision"], "Vision (spatial, hands, gaze)", False),
        # Sensor Performance Metrics (December 30, 2025)
        ("sensor_metrics", None, ["sensors", "metrics"], "Sensor Metrics Dashboard", False),
        # Marketplace & billing
        ("marketplace", None, ["marketplace"], "Marketplace", True),  # lazy
        ("billing", None, ["billing"], "Billing", False),
        ("compliance", None, ["compliance"], "Compliance", True),  # lazy
        # Property Intelligence (January 4, 2026)
        ("property", "/api/v1", ["property"], "Property Intelligence (Maps, Solar, 3D)", False),
        # Cluster Observability Dashboard (January 4, 2026)
        ("cluster_dashboard", "/api/v1/cluster", ["cluster"], "Cluster Dashboard", False),
        # Cluster WebSocket (January 4, 2026 — 125%)
        (
            "cluster_websocket",
            None,
            ["cluster", "websocket"],
            "Cluster WebSocket (real-time)",
            False,
        ),
        # Health Probes (January 4, 2026 — 125%)
        ("health", None, ["health"], "Health Probes (Kubernetes-ready)", False),
        # Prometheus Metrics (January 4, 2026 — 125%)
        ("metrics", None, ["metrics"], "Prometheus Metrics", False),
        # Specialized features
        ("control", None, None, "Control", False),
        ("inference", None, None, "Inference", True),  # lazy - heavy ML
        ("mind", None, ["mind"], "Mind (consolidated)", False),
        ("physics", None, None, "Physics", True),  # lazy - heavy (trimesh)
        ("world", None, None, "World/Rooms", False),
        # Security & audit
        ("provenance", None, ["provenance"], "Provenance (cryptographic audit)", False),
        # Orb State Sync (January 5, 2026) — cross-client orb synchronization
        ("orb", "/api/v1", ["orb"], "Orb (cross-client state sync)", False),
        # Agents — Live Markdown Agent Runtime (January 7, 2026)
        ("agents", None, ["agents"], "Agents (REST, WebSocket, Voice, Video)", False),
        # LiveKit — Real-time Voice/Video, AI Answering Machine (January 7, 2026)
        ("livekit", None, ["livekit", "voice"], "LiveKit (voice, video, answering)", False),
        # Voice Webhook — Twilio incoming calls (January 8, 2026)
        ("voice_webhook", None, ["voice", "twilio"], "Voice Webhook (Twilio incoming)", False),
        # Voice WebSocket — Twilio Media Streams ↔ ElevenLabs ConvAI (January 8, 2026)
        (
            "websockets.twilio_voice",
            None,
            ["voice", "websocket"],
            "Voice WS (Twilio ↔ ConvAI)",
            False,
        ),
        # World Model — Large OrganismRSSM inference API (January 12, 2026)
        ("world_model", None, ["world-model"], "World Model (OrganismRSSM)", False),
    ]

    # Import each route module directly using importlib (already imported above)
    # Skip lazy routes if lazy_load_heavy is enabled
    for route_name, prefix, tags, display_name, is_lazy in route_configs:
        # Skip lazy routes if lazy loading is enabled
        if is_lazy and lazy_load_heavy:
            logger.debug(f"Skipping lazy route: {display_name} (lazy loading enabled)")
            continue

        try:
            route_mod = importlib.import_module(f"kagami_api.routes.{route_name}")
            router_instance = _get_router_from_module(route_mod)
            if router_instance is not None:
                _include_router(
                    app,
                    router_instance,
                    prefix=prefix,
                    tags=tags,
                    name=display_name or route_name,
                )
        except Exception as e:
            logger.debug(f"Route {route_name} not available: {e}")

    # Admin routes from subdirectories (moved to subdirs but need explicit registration)
    # These use dot notation for nested modules (e.g., marketplace.admin)
    admin_route_configs = [
        ("marketplace.admin", None, None, "Marketplace Admin"),
        ("billing.admin", None, None, "Billing Admin"),
        ("compliance.policy", None, None, "Policy Management"),
    ]

    for route_name, prefix, tags, display_name in admin_route_configs:
        try:
            # Import using dot notation for nested modules
            route_mod = importlib.import_module(f"kagami_api.routes.{route_name}")
            router_instance = _get_router_from_module(route_mod)
            if router_instance is not None:
                _include_router(
                    app,
                    router_instance,
                    prefix=prefix,
                    tags=tags,
                    name=display_name or route_name,
                )
                logger.info(f"✓ Registered admin route: {display_name}")
            else:
                logger.error(f"Admin route {route_name} has no 'router' or 'get_router'")
        except Exception as e:
            logger.error(f"Admin route {route_name} not available: {e}")
            import traceback

            logger.debug(traceback.format_exc())

    # Log route count at INFO level - informational, not a warning
    logger.info(f"✓ Route registration complete ({len(app.routes)} total routes)")


__all__ = ["register_all_routes"]
