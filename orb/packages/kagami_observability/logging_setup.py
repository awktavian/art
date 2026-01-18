from __future__ import annotations

"""Centralized logging configuration for K os.

Provides structured JSON logging in production and a concise console format
in development/tests. Also exposes context utilities to attach request and
user metadata to log records without manual plumbing.
"""
import json
import logging
import os
import re
import sys
import threading
import time
from contextvars import ContextVar
from typing import Any

# Context variables used by filters/formatters
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
_client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)


def set_logging_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    client_ip: str | None = None,
) -> None:
    """Set logging context values for the current task/thread.

    Args:
        request_id: Request identifier (will also be used as correlation id if not set)
        user_id: Authenticated user id if available
        client_ip: Best-effort client IP
    """

    if request_id:
        _request_id_var.set(request_id)
        # If correlation id not explicitly provided via header, reuse request id
        if get_correlation_id() is None:
            _correlation_id_var.set(request_id)
    if user_id is not None:
        _user_id_var.set(user_id)
    if client_ip is not None:
        _client_ip_var.set(client_ip)


def clear_logging_context() -> None:
    """Clear logging context for the current task/thread."""

    _request_id_var.set(None)
    _correlation_id_var.set(None)
    _user_id_var.set(None)
    _client_ip_var.set(None)


def set_correlation_id(correlation_id: str | None) -> None:
    _correlation_id_var.set(correlation_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


def get_correlation_id() -> str | None:
    return _correlation_id_var.get()


class LazyConfigHandler(logging.Handler):
    """Trigger lazy logging configuration on first log emission.

    This handler ensures logging is configured before any log records
    are processed, enabling true lazy initialization. Once configuration
    is triggered, this handler removes itself and lets the real handlers
    take over.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Trigger configuration and re-emit the record."""
        # Trigger configuration (idempotent)
        _ensure_configured()

        # Remove ourselves from the root logger
        root = logging.getLogger()
        try:
            root.removeHandler(self)
        except ValueError:
            pass  # Already removed

        # Re-emit the record to the newly configured handlers
        for handler in root.handlers:
            if handler.level <= record.levelno:
                handler.handle(record)


class RequestContextFilter(logging.Filter):
    """Attach contextvars to LogRecord for formatters to include."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Attach attributes dynamically; use setattr to keep mypy satisfied
            record.request_id = get_request_id()
            record.correlation_id = get_correlation_id()
            record.user_id = _user_id_var.get()
            record.client_ip = _client_ip_var.get()
        except (LookupError, AttributeError) as e:
            # Never block logging on context variable access issues
            # LookupError: ContextVar.get() called outside context
            # AttributeError: LogRecord missing expected attributes
            import logging as _logging

            _logging.getLogger(__name__).debug(f"Context attachment failed: {e}")
            record.request_id = None
            record.correlation_id = None
            record.user_id = None
            record.client_ip = None
        return True


class OtelContextFilter(logging.Filter):
    """Attach OpenTelemetry trace/span ids to LogRecord when available.

    Enabled when OTEL_ENABLED is set and opentelemetry SDK is importable.
    """

    def __init__(self) -> None:
        super().__init__()
        try:
            from opentelemetry import trace as _trace

            self._trace: Any = _trace
            self._ok = True
        except (ImportError, ModuleNotFoundError) as e:
            # OpenTelemetry SDK not installed or unavailable
            import logging as _logging

            _logging.getLogger(__name__).debug(f"OpenTelemetry unavailable: {e}")
            self._trace = None
            self._ok = False

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._ok:
            return True
        try:
            span = self._trace.get_current_span() if self._trace else None
            ctx = span.get_span_context() if span else None
            if ctx and getattr(ctx, "is_valid", False):
                # Represent ids as hex strings
                record.trace_id = f"{ctx.trace_id:032x}"
                record.span_id = f"{ctx.span_id:016x}"
        except (AttributeError, TypeError, ValueError) as e:
            # AttributeError: span/context missing expected methods
            # TypeError: invalid context object type
            # ValueError: invalid trace/span ID format
            import logging as _logging

            _logging.getLogger(__name__).debug(f"OpenTelemetry context access failed: {e}")
        return True


class _ConsoleFormatter(logging.Formatter):
    """Readable console logs for development/tests."""

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        name = record.name
        # Be resilient to malformed logging args (avoid crashing tests)
        try:
            message = super().format(record)
        except (TypeError, ValueError, KeyError) as e:
            # TypeError: args incompatible with format string
            # ValueError: invalid format string
            # KeyError: missing format key in mapping-style format
            import logging as _logging

            _logging.getLogger(__name__).debug(f"Log message formatting failed: {e}")
            try:
                # Best-effort: render message without %-interpolation
                message = str(getattr(record, "msg", ""))
            except (AttributeError, TypeError) as e2:
                # AttributeError: record missing 'msg'
                # TypeError: msg not convertible to str
                _logging.getLogger(__name__).debug(f"Fallback message rendering failed: {e2}")
                message = ""
        ts = time.strftime("%H:%M:%S")

        ctx_bits = []
        rid = getattr(record, "request_id", None)
        if rid:
            ctx_bits.append(f"rid={rid}")
        cid = getattr(record, "correlation_id", None)
        if cid and cid != rid:
            ctx_bits.append(f"cid={cid}")
        uid = getattr(record, "user_id", None)
        if uid:
            ctx_bits.append(f"user={uid}")
        ip = getattr(record, "client_ip", None)
        if ip:
            ctx_bits.append(f"ip={ip}")
        tid = getattr(record, "trace_id", None)
        sid = getattr(record, "span_id", None)
        if tid:
            ctx_bits.append(f"trace={tid[:8]}")
        if sid:
            ctx_bits.append(f"span={sid}")
        ctx = (" " + " ".join(ctx_bits)) if ctx_bits else ""

        return f"{ts} {level:<8} {name}: {message}{ctx}"


class _JsonFormatter(logging.Formatter):
    """Structured JSON formatter for production logging."""

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": int(getattr(record, "created", time.time()) * 1000),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "thread": threading.current_thread().name,
        }

        # Attach context
        rid = getattr(record, "request_id", None)
        cid = getattr(record, "correlation_id", None)
        if rid:
            base["request_id"] = rid
        if cid:
            base["correlation_id"] = cid
        uid = getattr(record, "user_id", None)
        if uid:
            base["user_id"] = uid
        ip = getattr(record, "client_ip", None)
        if ip:
            base["client_ip"] = ip

        # Include OTel context
        tid = getattr(record, "trace_id", None)
        sid = getattr(record, "span_id", None)
        if tid:
            base["trace_id"] = tid
        if sid:
            base["span_id"] = sid

        # Include exception info when present
        if record.exc_info:
            try:
                base["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
                base["exc_text"] = self.formatException(record.exc_info)
            except (AttributeError, TypeError, ValueError) as e:
                # AttributeError: exc_info tuple element missing __name__
                # TypeError: exc_info not a proper tuple
                # ValueError: formatException failed
                import logging as _logging

                _logging.getLogger(__name__).debug(f"Exception info formatting failed: {e}")

        return json.dumps(base, ensure_ascii=False)


class SensitiveDataFilter(logging.Filter):
    """Redact common sensitive values in log records.

    This is a best-effort filter that scrubs tokens, passwords, API keys, and
    Authorization headers from both messages and known extra fields.
    """

    _patterns = [
        (
            re.compile(r"(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~\+\/=]+)", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(api[_-]?key\s*[=:]\s*)([^\s,]+)", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"(secret|token|password|passwd|sessionid)\s*[=:]\s*([^\s,]+)",
                re.IGNORECASE,
            ),
            r"\1=[REDACTED]",
        ),
    ]

    _sensitive_keys = {
        "authorization",
        "api_key",
        "apikey",
        "token",
        "password",
        "secret",
        "sessionid",
        "bearer",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Scrub message text
            try:
                msg = record.getMessage()
                for rx, repl in self._patterns:
                    msg = rx.sub(repl, msg)
                # Overwrite the message with a scrubbed, fully-rendered string
                record.msg = msg
                # Prevent downstream formatters from attempting %-interpolation again
                # on a plain string message with stale args
                record.args = ()
            except (TypeError, ValueError, AttributeError) as e:
                # TypeError: getMessage() failed due to bad args
                # ValueError: regex substitution failed
                # AttributeError: record missing expected attributes
                import logging as _logging

                _logging.getLogger(__name__).debug(f"Message scrubbing failed: {e}")

            # Scrub known attributes in record.__dict__
            for key in list(record.__dict__.keys()):
                if key.lower() in self._sensitive_keys:
                    record.__dict__[key] = "[REDACTED]"
        except (AttributeError, RuntimeError) as e:
            # AttributeError: record.__dict__ access failed
            # RuntimeError: dictionary changed size during iteration
            import logging as _logging

            _logging.getLogger(__name__).debug(f"Attribute scrubbing failed: {e}")
        return True


_configured_flag = False
_config_lock = threading.Lock()

# ===== NOISY LOGGERS =====
# Single source of truth for loggers that should be suppressed to WARNING
# (unless LOG_LEVEL=DEBUG is explicitly set). Used by both configure_logging()
# and _suppress_noisy_loggers() to avoid duplication.
_NOISY_LOGGERS: tuple[str, ...] = (
    # Boot/wiring - verbose initialization messages
    "kagami.boot.actions.wiring",
    "kagami.boot.actions.init",
    "kagami.boot.actions.registration",
    "kagami.boot.model_loader",
    "kagami.boot",
    "kagami.boot.nodes",
    "kagami.boot.nodes.core",
    "kagami.boot.nodes.network",
    "kagami.boot.nodes.background",
    # Production systems - per-component init spam
    "kagami.core.production_systems_coordinator",
    # Unified agents - colony/worker init spam
    "kagami.core.unified_agents.fano_action_router",
    "kagami.core.unified_agents.unified_organism",
    "kagami.core.unified_agents.geometric_worker",
    "kagami.core.unified_agents.e8_action_reducer",
    "kagami.core.unified_agents.markov_blanket",
    "kagami.core.unified_agents.homeostasis",
    "kagami.core.unified_agents.hierarchical_jepa",
    "kagami.core.unified_agents.ego_model",
    "kagami.core.unified_agents.entity_memory",
    "kagami.core.unified_agents.memory.stigmergy",
    # Safety - CBF init details
    "kagami.core.safety.cbf_init",
    "kagami.core.safety.cbf_registry",
    "kagami.core.safety.llm_safety_integration",
    "kagami.core.safety.optimal_cbf",
    "kagami.core.safety.cbf_integration",
    "kagami.core.safety.cbf_runtime_monitor",
    "kagami.core.safety.provenance_chain",
    "kagami.core.safety.provenance",
    "kagami.core.safety.infrastructure",
    "kagami.core.safety.provenance_integration",
    # Services - LLM/model loading spam
    "kagami.core.services.llm.llm_providers",
    "kagami.core.services.llm.progressive_loader",
    "kagami.core.services.llm.structured_client",
    "kagami.core.services.llm.client_manager",
    "kagami.core.services.llm.service",
    "kagami.core.services.embedding_service",
    # World model - initialization details
    "kagami.core.world_model.initializer",
    "kagami.core.world_model.service",
    "kagami.core.world_model.multimodal_encoder",
    "kagami.core.world_model.hierarchical_jepa",
    "kagami.core.world_model.ego_model",
    "kagami.core.world_model.entity_memory",
    "kagami.core.world_model.unified_orchestrator",
    # Learning systems
    "kagami.core.learning.receipt_learning",
    "kagami.core.learning.coordinator",
    "kagami.core.learning.instinct_learning_loop",
    "kagami.core.learning.maml",
    "kagami.core.learning.maml_integration",
    # Events/receipts
    "kagami.core.events.receipt_stream_processor",
    "kagami.core.receipts.etcd_receipt_sync",
    "kagami.core.receipts",
    # Infrastructure
    "kagami.core.infra.background_task_manager",
    "kagami.core.coordination.kagami_consensus",
    "kagami.core.consensus.etcd_client",
    "kagami.core.consensus.gc",
    "kagami.core.consensus.metrics_extended",
    "kagami.core.database.connection",
    "kagami.core.database.async_connection",
    "kagami.core.database",
    "kagami.core.caching.redis.factory",
    # Orchestrator
    "kagami.core.orchestrator.core",
    "kagami.orchestration.intent_orchestrator",
    "kagami.core.orchestrator.unified_orchestrator",
    # Continuous/autonomous
    "kagami.core.continuous.continuous_mind",
    "kagami.core.autonomous_goal_engine",
    "kagami.core.motivation.intrinsic_motivation",
    "kagami.core.motivation.proactive_goals",
    # Misc noisy modules
    "kagami.core.rl.unified_cost_module",
    "kagami.core.rl.unified_replay",
    "kagami.core.unified_rate_limiter",
    "kagami.core.ambient.multi_device_coordinator",
    "kagami.core.ambient.controller",
    "kagami.core.ambient.registration",
    "kagami.core.brain_api",
    "kagami.core.unified_e8_bus",
    "kagami.core.events.unified_e8_bus",
    "kagami.core.tasks.task_registry",
    "kagami.core.task_registry",
    "kagami.core.tools_integration",
    "kagami.core.knowledge_graph",
    "kagami.core.boot_mode",
    "kagami.core._full_operation_check",
    "kagami.core.config_parser",
    "kagami.core.config_root",
    "kagami.core.utils.mps_ops",
    # Execution
    "kagami.core.execution.markov_blanket",
    # Reasoning
    "kagami.core.reasoning.optimal_integration",
    "kagami.core.reasoning.symbolic.z3_solver",
    "kagami.core.coordination.optimal_integration",
    # Instincts
    "kagami.core.instincts.threat_instinct",
    "kagami.core.instincts.common_sense_instinct",
    "kagami.core.security.jailbreak_detector",
    # Memory
    "kagami.core.memory.manager",
    "kagami.core.memory.unified_replay",
    # Debugging
    "kagami.core.debugging.unified_debugging_system",
    # Multimodal
    "kagami.core.multimodal.contrastive_fusion",
    "kagami.core.multimodal.hierarchical_encoder",
    # Gameplay
    "kagami.core.gameplay.motion_primitives",
    # API
    "kagami.api.lifespan_v2",
    "kagami.api.create_app_v2",
    "kagami.api.security_middleware",
    "kagami.api.route_registry",
    "kagami.api.routes",
    "kagami.api.provider_registry",
    "kagami.api.factory_helpers",
    "kagami.api.compression_api",
    "kagami.api.safety_api",
    "kagami.api.routing_api",
    "kagami.api.error_handlers",
    "kagami.api._full_operation_check",
    "kagami.api.socketio.app",
    "kagami.api.socketio.registration",
    "kagami.api.services.redis_job_storage",
    # Observability
    "kagami.observability.metrics_prometheus",
    # Third-party
    "OpenGL.acceleratesupport",
)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _ensure_configured() -> None:
    """Ensure logging is configured. Called automatically on first log emission.

    This is thread-safe and idempotent. Uses double-checked locking pattern
    to minimize overhead after first configuration.
    """
    global _configured_flag
    if _configured_flag:
        return

    with _config_lock:
        # Double-check inside lock (needed for concurrent access)
        if _configured_flag:
            return  # type: ignore[unreachable]
        configure_logging(force=False)


def configure_logging(force: bool = False) -> None:
    """Configure root logging for K os once.

    - Development/tests: concise console logs
    - Production: JSON lines to stdout (12-factor compliant)
    - Optional file logging with rotation (LOG_FILE env var)
    - Unify uvicorn/gunicorn loggers with root handler
    - Capture warnings module into logging

    Note: This is called automatically on first log emission. Manual calls
    are only needed for tests or explicit early configuration.
    """

    global _configured_flag
    if _configured_flag and not force:
        return

    # Determine level (default to INFO in all environments unless overridden)
    level_name = os.getenv("LOG_LEVEL") or os.getenv("KAGAMI_LOG_LEVEL") or "INFO"
    try:
        level = getattr(logging, level_name.upper())
    except (AttributeError, TypeError) as e:
        # AttributeError: invalid log level name
        # TypeError: level_name is not a string
        import logging as _logging

        _logging.getLogger(__name__).warning(
            f"Invalid log level '{level_name}': {e}, defaulting to INFO"
        )
        level = logging.INFO

    # Build handler
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(RequestContextFilter())
    try:
        handler.addFilter(OtelContextFilter())
    except (TypeError, RuntimeError) as e:
        # TypeError: OtelContextFilter init failed with bad arguments
        # RuntimeError: filter initialization error
        import logging as _logging

        _logging.getLogger(__name__).debug(f"OtelContextFilter setup failed: {e}")
    handler.addFilter(SensitiveDataFilter())
    # Disable JSON output by default; enable by setting KAGAMI_LOG_JSON=1
    if _env_bool("KAGAMI_LOG_JSON", default=False):
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_ConsoleFormatter("%(message)s"))

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers that might have been configured by libraries
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

    # Add file handler with rotation if LOG_FILE is set
    log_file = os.getenv("LOG_FILE")
    if log_file:
        try:
            from kagami_observability.log_rotation import create_rotating_file_handler

            # Parse rotation config from env vars
            rotation_type = os.getenv("LOG_ROTATION_TYPE", "time")
            rotation_when = os.getenv("LOG_ROTATION_WHEN", "midnight")
            rotation_interval = int(os.getenv("LOG_ROTATION_INTERVAL", "1"))
            rotation_max_bytes = int(os.getenv("LOG_ROTATION_MAX_BYTES", str(10 * 1024 * 1024)))
            rotation_backup_count = int(os.getenv("LOG_ROTATION_BACKUP_COUNT", "7"))
            rotation_compress = _env_bool("LOG_ROTATION_COMPRESS", default=True)

            file_handler = create_rotating_file_handler(
                filename=log_file,
                rotation_type=rotation_type,  # type: ignore
                when=rotation_when,
                interval=rotation_interval,
                max_bytes=rotation_max_bytes,
                backup_count=rotation_backup_count,
                compress=rotation_compress,
            )

            # Apply same filters and formatter
            file_handler.addFilter(RequestContextFilter())
            file_handler.addFilter(SensitiveDataFilter())
            if _env_bool("KAGAMI_LOG_JSON", default=False):
                file_handler.setFormatter(_JsonFormatter())
            else:
                file_handler.setFormatter(_ConsoleFormatter("%(message)s"))

            root.addHandler(file_handler)
            import logging as _logging

            _logging.getLogger(__name__).info(
                f"File logging enabled: {log_file} (rotation={rotation_type}, "
                f"backup_count={rotation_backup_count}, compress={rotation_compress})"
            )

        except Exception as e:
            import logging as _logging

            _logging.getLogger(__name__).error(
                f"Failed to configure file logging: {e}", exc_info=True
            )

    # Unify uvicorn / gunicorn / fastapi loggers
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "gunicorn",
        "gunicorn.error",
        "gunicorn.access",
        "fastapi",
    ):
        lg = logging.getLogger(name)
        lg.propagate = True
        lg.handlers = []
        if name.endswith("access"):
            # Keep access logs at INFO; allow root level to control verbosity otherwise
            lg.setLevel(logging.INFO)
        else:
            lg.setLevel(level)

    # Suppress noisy internal loggers (use module-level constant)
    if level > logging.DEBUG:
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)

    # Capture warnings
    logging.captureWarnings(True)

    _configured_flag = True


def setup_logging(
    *,
    level: int | str | None = None,
    force: bool = False,
) -> None:
    """Public helper for configuring K os logging.

    Args:
        level: Optional logging level override (int or string name).
        force: Reconfigure even if already configured.
    """
    configure_logging(force=force)

    if level is None:
        return

    root = logging.getLogger()
    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), root.level)
    else:
        numeric_level = level

    root.setLevel(numeric_level)
    for handler in root.handlers:
        handler.setLevel(numeric_level)


__all__ = [
    "RequestContextFilter",
    "clear_logging_context",
    "configure_logging",
    "get_correlation_id",
    "get_request_id",
    "set_correlation_id",
    "set_logging_context",
    "setup_logging",
]


# ===== LAZY INITIALIZATION SETUP =====
# Install lazy configuration handler on root logger at import time.
# This is lightweight (< 1ms) but ensures configure_logging() is called
# automatically on first log emission.
def _install_lazy_config() -> None:
    """Install lazy configuration handler on root logger.

    This is safe to call at module import time because it only adds
    a handler, without doing the expensive formatter/filter setup.
    The handler removes itself after triggering configuration.
    """
    root = logging.getLogger()
    # Check if already installed or already configured
    if _configured_flag:
        return
    for h in root.handlers:
        if isinstance(h, LazyConfigHandler):
            return
    # Add lazy handler that will trigger configuration on first log
    root.addHandler(LazyConfigHandler())
    # Set level to DEBUG so all logs trigger configuration
    root.setLevel(logging.DEBUG)


# Install at module import time (fast, < 1ms)
_install_lazy_config()


# ===== EARLY LOG SUPPRESSION =====
# Suppress noisy internal loggers at import time (BEFORE first log emission).
# This is critical for reducing startup log spam.
def _suppress_noisy_loggers() -> None:
    """Suppress noisy internal loggers at import time.

    This runs immediately at import time to prevent log spam before
    configure_logging() is called. Only suppresses to WARNING level
    unless LOG_LEVEL=DEBUG is explicitly set.
    """
    # Check if DEBUG mode is requested
    level_name = os.getenv("LOG_LEVEL") or os.getenv("KAGAMI_LOG_LEVEL") or "INFO"
    if level_name.upper() == "DEBUG":
        return  # Don't suppress in DEBUG mode

    # Use module-level constant (single source of truth)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


# Run suppression immediately at import time
_suppress_noisy_loggers()
