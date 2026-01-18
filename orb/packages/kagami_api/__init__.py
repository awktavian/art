"""K os API Package

This module provides the FastAPI application factory and core API functionality.

PEP 562 lazy loading implemented to defer heavy imports (FastAPI, lifespan, etc.)
until actually needed. This reduces cold start time by 100-500ms.
"""

# CRITICAL: Import logging_setup FIRST to suppress noisy loggers before any logging
# This must happen before any other kagami module imports

import logging
import os
from typing import TYPE_CHECKING, Any

# CRITICAL: Set CPU-only mode for API server BEFORE any torch import
# This prevents MPS shutdown deadlock with Tcl (matplotlib/tkinter)
# The API doesn't need GPU acceleration - training/inference use separate processes
if not os.getenv("KAGAMI_DEVICE"):
    os.environ["KAGAMI_DEVICE"] = "cpu"
if not os.getenv("KAGAMI_WORLD_MODEL_DEVICE"):
    os.environ["KAGAMI_WORLD_MODEL_DEVICE"] = "cpu"

# Suppress gRPC fork warnings that spam the logs during uvicorn reload
# "Other threads are currently calling into gRPC, skipping fork() handlers"
# These are benign warnings when fork() is called while gRPC is active
if not os.getenv("GRPC_ENABLE_FORK_SUPPORT"):
    os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
# Also suppress gRPC verbosity (only show errors and above)
if not os.getenv("GRPC_VERBOSITY"):
    os.environ["GRPC_VERBOSITY"] = "ERROR"

# Suppress tqdm progress bars during model loading (reduces log spam)
# This affects "Loading checkpoint shards" and similar HuggingFace progress bars
if not os.getenv("HF_HUB_DISABLE_PROGRESS_BARS"):
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
if not os.getenv("TQDM_DISABLE"):
    os.environ["TQDM_DISABLE"] = "1"

if TYPE_CHECKING:
    from kagami_api.create_app_v2 import create_app_v2
    from kagami_api.lifespan_v2 import lifespan_v2

logger = logging.getLogger(__name__)

# Lightweight imports only
from . import api_settings as api_settings

# ORJSON check (fast)
try:
    _ORJSON_AVAILABLE = True
except Exception:
    _ORJSON_AVAILABLE = False

# Version (fast)
try:
    from kagami._version import __version__ as _pkg_version
except Exception:
    _pkg_version = os.getenv("KAGAMI_VERSION", "0.0.0")

# Heavy imports deferred via __getattr__ below

__all__ = [
    "_pkg_version",
    "api_settings",
    "app",
    "create_app",
    "create_app_v2",
    "input_validation_middleware",
    "lifespan_v2",
    "websocket",
]

# PEP 562: Lazy module-level import via __getattr__
_LAZY_IMPORTS = {
    "create_app_v2": "kagami_api.create_app_v2",
    "lifespan_v2": "kagami_api.lifespan_v2",
    "input_validation_middleware": "kagami_api.input_validation",
    "FastAPI": "fastapi",
}

_lazy_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    """PEP 562 lazy import mechanism.

    Heavy imports (FastAPI, lifespan, etc.) are deferred until first access.
    This eliminates 100-500ms of cold start overhead.
    """
    if name in _lazy_cache:
        return _lazy_cache[name]

    if name == "create_app_v2":
        from kagami_api.create_app_v2 import create_app_v2

        _lazy_cache[name] = create_app_v2
        return create_app_v2

    if name == "lifespan_v2":
        from kagami_api.lifespan_v2 import lifespan_v2

        _lazy_cache[name] = lifespan_v2
        return lifespan_v2

    if name == "input_validation_middleware":
        from kagami_api.input_validation import input_validation_middleware

        _lazy_cache[name] = input_validation_middleware
        return input_validation_middleware

    if name == "FastAPI":
        from fastapi import FastAPI

        _lazy_cache[name] = FastAPI
        return FastAPI

    if name == "create_app":
        # Alias to create_app_v2
        create_app_v2_func = __getattr__("create_app_v2")
        _lazy_cache[name] = create_app_v2_func
        return create_app_v2_func

    if name == "app":
        # Factory function
        def app() -> Any:
            """Return a new FastAPI app via the preferred factory."""
            create_app_func = __getattr__("create_app")
            return create_app_func()

        _lazy_cache[name] = app
        return app

    if name == "websocket":
        # Lazy import socketio_server for realtime Socket.IO API
        # Legacy 'websocket' alias now points to socketio_server (Dec 2025 migration)
        import importlib

        ws_module = importlib.import_module("kagami_api.socketio_server")
        _lazy_cache[name] = ws_module
        return ws_module

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Optional OpenTelemetry initialization (enabled via env, but deferred)
def _init_otel() -> None:
    """Initialize OpenTelemetry if enabled. Called lazily."""
    try:
        _OTEL_ENABLED = (os.getenv("OTEL_ENABLED") or "0").lower() in ("1", "true", "yes", "on")
        if _OTEL_ENABLED:
            from opentelemetry import trace as _otel_trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            if _otel_trace.get_tracer_provider().__class__.__name__ != "TracerProvider":
                _res = Resource.create(
                    {
                        "service.name": os.getenv("OTEL_SERVICE_NAME", "kagami-api"),
                        "service.version": os.getenv("KAGAMI_VERSION", _pkg_version),
                    }
                )
                _provider = TracerProvider(resource=_res)
                _endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"
                _exporter = OTLPSpanExporter(endpoint=f"{_endpoint}/v1/traces")
                _provider.add_span_processor(BatchSpanProcessor(_exporter))
                _otel_trace.set_tracer_provider(_provider)
    except Exception as e:
        logger.debug("OpenTelemetry initialization skipped: %s", e)


# Logging is now lazily configured on first log emission via LazyConfigFilter.
# This eliminates 10-50ms import-time overhead.
# Suppress verbose third-party logs (lightweight, no handler setup)
logging.getLogger("starlette.middleware").setLevel(logging.WARNING)
logging.getLogger("starlette.routing").setLevel(logging.WARNING)
logging.getLogger("starlette.requests").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Suppress verbose ML/infra libraries
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.WARNING)
logging.getLogger("transformers.modeling_utils").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("alembic").setLevel(logging.WARNING)
logging.getLogger("redis").setLevel(logging.WARNING)
logging.getLogger("aioredis").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("watchgod").setLevel(logging.WARNING)


# Conditional app creation (only if explicitly requested)
if os.getenv("KAGAMI_CREATE_APP_ON_IMPORT", "0").lower() in ("1", "true", "yes", "on"):
    # Trigger lazy load
    _init_otel()
    create_app_func = __getattr__("create_app")
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
    allowed_origins: list[str] | None = None
    if allowed_origins_env:
        allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
    uvicorn_app = create_app_func(allowed_origins=allowed_origins)
