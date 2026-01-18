"""Initialization actions for boot process.

Actions that initialize core infrastructure:
- Database connections
- Cache systems
- Event buses
- Configuration
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


# === Helper Functions ===


def _env_int(name: str, default: int) -> int:
    """Parse environment variable as integer with fallback.

    Args:
        name: Environment variable name.
        default: Default value if not set[Any] or invalid.

    Returns:
        Integer value from environment or default.
    """
    try:
        value = os.getenv(name)
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def _should_enable_loader(
    env_var: str,
    default_full: bool = True,
    default_test: bool = False,
) -> bool:
    """Determine if a loader should be enabled based on env vars and boot mode.

    Checks:
    1. Explicit env var override (1/true/yes/on = True, 0/false/no/off = False)
    2. Boot mode defaults (full mode uses default_full, test mode uses default_test)

    Args:
        env_var: Environment variable name to check
        default_full: Default value in full mode
        default_test: Default value in test mode

    Returns:
        Whether the loader should be enabled
    """
    from kagami.core.boot_mode import is_full_mode, is_test_mode

    # Check explicit env var override
    explicit = os.getenv(env_var)
    if explicit is not None:
        explicit_lower = explicit.lower()
        if explicit_lower in ("1", "true", "yes", "on"):
            return True
        if explicit_lower in ("0", "false", "no", "off"):
            return False

    # Check boot mode for defaults
    if is_test_mode():
        return default_test
    if is_full_mode():
        return default_full

    # Default to full mode behavior
    return default_full


# === Initialization Actions ===


async def enforce_full_operation_check(app: FastAPI) -> None:
    """Enforce Full Operation mode before startup."""
    try:
        from kagami_api._full_operation_check import enforce_full_operation

        # Always enforce full operation
        await enforce_full_operation()
    except Exception as e:
        logger.critical(
            f"FATAL: Cannot start API without Full Operation in any environment. "
            f"K os requires: CockroachDB, Redis Stack, and all mandatory subsystems. "
            f"Error: {e}"
        )
        sys.exit(1)


async def startup_database(app: FastAPI) -> None:
    """Initialize database tables.

    OPTIMIZED (Dec 28, 2025): Connection already verified by enforce_full_operation.
    OPTIMIZED (Dec 30, 2025): Use SQLite in local mode for faster startup.
    """
    from kagami.core.database.connection import init_db

    if not app:
        raise ValueError("FastAPI app instance required")

    # Local mode uses SQLite for simplicity
    if os.getenv("KAGAMI_LOCAL_MODE") == "1" and not os.getenv("DATABASE_URL"):
        os.environ.setdefault("DATABASE_URL", "sqlite:///./kagami_local.db")
        logger.debug("Using SQLite for local mode")

    if os.getenv("KAGAMI_OFFLINE_MODE") == "1":
        logger.debug("Database startup skipped (offline mode)")
        app.state.db_ready = False
        return

    try:
        # Connection was verified by enforce_full_operation - just ensure tables exist
        await init_db()
        app.state.db_ready = True
        logger.debug("Database ready")
    except Exception as e:
        error_msg = str(e)
        if "Could not determine version" in error_msg and "CockroachDB" in error_msg:
            # CockroachDB version parse is non-fatal
            app.state.db_ready = True
            logger.debug("Database ready (CockroachDB compatibility)")
        else:
            logger.error(f"❌ Database init failed: {e}")
            raise RuntimeError(f"Database initialization failed: {e}") from e


async def startup_redis(app: FastAPI) -> None:
    """Initialize Redis connection.

    OPTIMIZED (Dec 28, 2025): Skip ping since enforce_full_operation already verified.
    OPTIMIZED (Dec 30, 2025): Skip in local mode for faster startup.
    """
    if not app:
        raise ValueError("FastAPI app instance required")

    # Skip in local mode (bare-metal, no distributed services)
    if os.getenv("KAGAMI_LOCAL_MODE") == "1" or os.getenv("KAGAMI_SKIP_DISTRIBUTED") == "1":
        logger.debug("Redis skipped (local mode) - using in-memory cache")
        app.state.redis_ready = False  # Use in-memory fallback
        return

    if os.getenv("KAGAMI_OFFLINE_MODE") == "1":
        logger.debug("Redis startup skipped (offline mode)")
        app.state.redis_ready = False
        return

    # Redis was already verified by enforce_full_operation - just mark ready
    app.state.redis_ready = True
    logger.debug("Redis ready")


async def startup_e8_bus(app: FastAPI) -> None:
    """Start the unified E8 event bus."""
    try:
        from kagami.core.events import get_unified_bus

        offline = os.getenv("KAGAMI_OFFLINE_MODE") == "1"
        allow_redis = os.getenv("KAGAMI_E8_BUS_REDIS", "1").lower() in ("1", "true", "yes", "on")
        use_redis = bool(getattr(app.state, "redis_ready", False)) and allow_redis and not offline

        bus = get_unified_bus(use_redis=use_redis)
        await bus.start()

        app.state.e8_bus = bus
        app.state.e8_bus_ready = True
        logger.debug(f"E8Bus started (redis={use_redis})")
    except (ImportError, RuntimeError, AttributeError, ConnectionError) as e:
        app.state.e8_bus = None
        app.state.e8_bus_ready = False
        logger.debug(f"E8Bus unavailable: {e}")


async def shutdown_e8_bus(app: FastAPI) -> None:
    """Stop the unified E8 event bus (best-effort)."""
    bus = getattr(app.state, "e8_bus", None)
    if bus is not None:
        try:
            await bus.stop()
        except Exception as e:
            # OK to catch all exceptions during shutdown - best-effort cleanup
            logger.debug(f"E8Bus stop failed: {e}")
    app.state.e8_bus_ready = False


async def startup_etcd(app: FastAPI) -> None:
    """Initialize etcd connection pool.

    OPTIMIZED (Dec 28, 2025): Fast 0.5s timeout, fail-fast on timeout.
    OPTIMIZED (Dec 30, 2025): Skip in local mode for faster startup.
    """
    import asyncio

    from kagami.core.boot_mode import is_test_mode
    from kagami.core.config import get_bool_config

    required = get_bool_config("KAGAMI_ETCD_REQUIRED", False)
    app.state.etcd_pool = None
    app.state.etcd_ready = False

    # Skip in local mode (bare-metal, no distributed services)
    if os.getenv("KAGAMI_LOCAL_MODE") == "1" or os.getenv("KAGAMI_SKIP_DISTRIBUTED") == "1":
        logger.debug("etcd skipped (local mode)")
        app.state.etcd_ready = True  # Mark as ready to not block dependents
        return

    # Skip via SKIP_ETCD environment variable
    if os.getenv("SKIP_ETCD", "").lower() in ("true", "1", "yes"):
        logger.info("etcd skipped (SKIP_ETCD=true)")
        app.state.etcd_ready = True  # Mark as ready to not block dependents
        return

    if os.getenv("KAGAMI_OFFLINE_MODE") == "1":
        logger.debug("etcd skipped (offline)")
        return

    if is_test_mode() and os.getenv("KAGAMI_ETCD_TEST_ENABLED") != "1":
        app.state.etcd_ready = True
        return

    etcd_timeout = float(os.getenv("KAGAMI_ETCD_TIMEOUT", "0.5"))
    try:
        from kagami.core.consensus.etcd_client import get_etcd_client_pool

        pool = await asyncio.wait_for(get_etcd_client_pool(), timeout=etcd_timeout)
        app.state.etcd_pool = pool
        app.state.etcd_ready = True
        logger.debug("etcd connected")
    except (TimeoutError, ConnectionError, RuntimeError) as exc:
        if required:
            raise RuntimeError(f"etcd required but unavailable: {exc}") from exc
        # Single-instance mode - OK without etcd
        logger.debug(f"etcd unavailable (single-instance): {exc}")


async def shutdown_etcd(app: FastAPI) -> None:
    """Close etcd connection pool."""
    pool = getattr(app.state, "etcd_pool", None)
    if pool:
        try:
            pool.close_all()
            logger.info("✓ etcd connection pool closed")
        except Exception as exc:
            # OK to catch all exceptions during shutdown - best-effort cleanup
            logger.debug(f"etcd shutdown error: {exc}")
    app.state.etcd_ready = False


async def startup_cbf_system(app: FastAPI) -> None:
    """Initialize Control Barrier Function (CBF) safety system.

    OPTIMIZED (Dec 28, 2025): Fast init, defer safety check to background.
    """
    try:
        # Fast path: just create registry and register barriers (no I/O)
        from kagami.core.safety.cbf_init import h_blanket_integrity, h_disk, h_memory, h_process
        from kagami.core.safety.cbf_registry import CBFRegistry

        registry = CBFRegistry()

        # Register Tier 1 barriers (CPU-only, no I/O)
        registry.register(
            tier=1,
            name="organism.memory",
            func=h_memory,
            description="Memory usage must stay below 80%",
        )
        registry.register(
            tier=1, name="organism.disk", func=h_disk, description="Disk usage must stay below 90%"
        )
        registry.register(
            tier=1,
            name="organism.process",
            func=h_process,
            description="Process count must stay below 90% of system limit",
        )
        registry.register(
            tier=1,
            name="organism.blanket_integrity",
            func=h_blanket_integrity,
            description="Markov blanket integrity must remain above 50%",
        )

        # Generic rate_limit barrier (always safe - actual rate limiting done by middleware)
        # This is a fallback for decorators using @enforce_tier1("rate_limit")
        registry.register(
            tier=1,
            name="rate_limit",
            func=lambda _: 1.0,  # Always safe (h=1.0)
            description="Rate limit placeholder (actual limiting via middleware)",
        )

        app.state.cbf_registry = registry
        app.state.cbf_ready = True

        stats = registry.get_stats()
        logger.info(f"✅ CBF: {stats['total_barriers']} barriers (T1={stats['tier_1']})")

    except Exception as e:
        logger.critical(f"❌ CBF initialization failed: {e}", exc_info=True)
        raise RuntimeError(f"CBF safety system initialization failed: {e}") from e


async def startup_feature_flags(app: FastAPI) -> None:
    """Start dynamic feature flag watcher (etcd-backed)."""
    try:
        from kagami.core.config.feature_flags import get_feature_flag_watcher

        watcher = get_feature_flag_watcher()
        # Add timeout to prevent blocking lifespan
        await asyncio.wait_for(watcher.start(), timeout=10.0)
        app.state.feature_flag_watcher = watcher
        logger.debug("Feature flags active")
    except TimeoutError:
        logger.warning("⚠️  Feature flag watcher startup timed out (using defaults)")
        app.state.feature_flag_watcher = None
    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Dynamic feature flag watcher failed: {e}")


__all__ = [
    "_env_int",
    "_should_enable_loader",
    "enforce_full_operation_check",
    "shutdown_e8_bus",
    "shutdown_etcd",
    "startup_cbf_system",
    "startup_database",
    "startup_e8_bus",
    "startup_etcd",
    "startup_feature_flags",
    "startup_redis",
]
