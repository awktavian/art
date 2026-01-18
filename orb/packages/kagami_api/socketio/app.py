from __future__ import annotations

import logging
import os

from kagami.core.boot_mode import is_test_mode

import socketio
from kagami_api.socketio.namespaces.agents import AgentsNamespace
from kagami_api.socketio.namespaces.forge import ForgeNamespace
from kagami_api.socketio.namespaces.intents import IntentNamespace
from kagami_api.socketio.namespaces.metrics import MetricsNamespace
from kagami_api.socketio.namespaces.root import KagamiOSNamespace

logger = logging.getLogger(__name__)


def _get_cors_origins(provided_origins: list[str] | None) -> list[str]:
    """Determine CORS origins for WebSocket with environment-based defaults.

    SECURITY CRITICAL:
    - Production REQUIRES explicit origins (via parameter or ALLOWED_ORIGINS env var)
    - Development defaults to localhost only
    - Wildcard "*" is ONLY allowed in test mode

    Args:
        provided_origins: Explicit origins passed to create_socketio_app

    Returns:
        List of allowed origins

    Raises:
        ValueError: If origins are missing/invalid in production
    """
    _env = (os.getenv("ENVIRONMENT") or "development").lower()
    _is_test_mode = _env == "test" or is_test_mode()

    # Use provided origins if explicitly passed
    if provided_origins is not None:
        # Validate in production
        if _env == "production" and not _is_test_mode:
            has_wildcard = any(o.strip() == "*" for o in provided_origins)
            if has_wildcard:
                raise ValueError(
                    "Wildcard '*' is not allowed in production WebSocket CORS. "
                    "Pass explicit origins to create_socketio_app()."
                )
        return provided_origins

    # Read from environment variable
    origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
    if origins_env:
        return [o.strip() for o in origins_env.split(",") if o.strip()]

    # Apply defaults based on environment
    if _env == "production" and not _is_test_mode:
        raise ValueError(
            "ALLOWED_ORIGINS environment variable must be set in production for WebSocket CORS. "
            "Example: ALLOWED_ORIGINS=https://app.example.com,https://www.example.com"
        )
    elif _is_test_mode:
        # Test mode: Allow wildcard for test flexibility
        return ["*"]
    else:
        # Development: Default to localhost only (secure default)
        return [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001",
        ]


def create_socketio_app(
    cors_allowed_origins: list[str] | None = None,
    async_mode: str = "asgi",
) -> socketio.AsyncServer:
    """Create the Socket.IO server (namespaces + config).

    Args:
        cors_allowed_origins: Explicit list of allowed origins. If None, reads from
            ALLOWED_ORIGINS env var or applies secure defaults based on ENVIRONMENT.
        async_mode: Socket.IO async mode (default: "asgi")

    Returns:
        Configured Socket.IO AsyncServer instance

    Raises:
        ValueError: In production if no origins are configured
    """
    # Get CORS origins with environment-based security
    origins = _get_cors_origins(cors_allowed_origins)

    # LOGSPAM FIX (Dec 30, 2025): Disable internal socketio logging
    # The library logs every emit at INFO level, creating massive spam.
    # Set logger=False to suppress per-emit logging; we log important events ourselves.
    sio = socketio.AsyncServer(
        async_mode=async_mode,
        cors_allowed_origins=origins,
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1_000_000,
        allow_upgrades=True,
        http_compression=True,
        compression_threshold=1024,
        cookie="kagami_sid",
        logger=False,  # Suppress per-emit logging spam
        engineio_logger=False,
    )

    sio.register_namespace(KagamiOSNamespace("/"))
    sio.register_namespace(IntentNamespace())
    sio.register_namespace(ForgeNamespace())
    sio.register_namespace(AgentsNamespace())
    sio.register_namespace(MetricsNamespace())

    logger.info("Socket.IO server created with namespaces: /, /intents, /forge, /agents, /metrics")

    return sio


__all__ = ["create_socketio_app"]
