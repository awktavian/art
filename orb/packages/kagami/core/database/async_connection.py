"""Async database connection management for K os."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

# Apply CockroachDB compatibility patches for asyncpg JSON codec
# This import triggers the patches in cockroach.py
# HARDENED: CockroachDB patches are REQUIRED
from kagami.core.database import cockroach as _cockroach_patches  # noqa: F401

# Import config functions locally to avoid circular imports
from kagami.core.database.connection import resolve_database_url

logger = logging.getLogger(__name__)

# Suppress SQLAlchemy pool connection closing errors during shutdown
# These are benign CancelledError exceptions when the event loop tears down
logging.getLogger("sqlalchemy.pool.impl").setLevel(logging.CRITICAL)

_ASYNC_DATABASE_URL_CACHE: str | None = None
_ASYNC_ENGINE: AsyncEngine | None = None
_ASYNC_SESSION_FACTORY: async_sessionmaker | None = None
_ASYNC_ENGINE_LOOP_ID: int | None = None  # Track which event loop the engine was created on
_TABLES_INITIALIZED: bool = False  # Track whether tables have been created (test mode)


def _convert_sslmode_for_asyncpg(url: str) -> str:
    """Convert psycopg2 sslmode parameter to asyncpg-compatible format.

    asyncpg doesn't accept 'sslmode' as a URL parameter. Instead, it uses 'ssl'.
    For 'sslmode=disable', we remove the parameter entirely (asyncpg default is no SSL).
    For other modes, we convert to the equivalent 'ssl' parameter.
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    if not parsed.query:
        return url

    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # Handle sslmode conversion
    if "sslmode" in query_params:
        sslmode = query_params.pop("sslmode")[0]
        # asyncpg ssl parameter mapping:
        # - disable: no ssl (remove parameter)
        # - prefer/allow: ssl=prefer (not strictly supported, use default)
        # - require: ssl=require
        # - verify-ca/verify-full: ssl=verify-full
        if sslmode in ("require", "verify-ca", "verify-full"):
            query_params["ssl"] = ["require" if sslmode == "require" else "verify-full"]
        # For 'disable', 'prefer', 'allow' - don't add ssl parameter

    # Rebuild URL
    new_query = urlencode(query_params, doseq=True) if query_params else ""
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def _resolve_async_database_url() -> str:
    global _ASYNC_DATABASE_URL_CACHE
    if _ASYNC_DATABASE_URL_CACHE is not None:
        return _ASYNC_DATABASE_URL_CACHE

    base_url = resolve_database_url()
    if base_url.startswith("postgresql+asyncpg://") or base_url.startswith("sqlite+aiosqlite://"):
        async_url = base_url
    elif base_url.startswith("postgresql+psycopg2://"):
        async_url = base_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    elif base_url.startswith("postgresql://"):
        async_url = base_url.replace("postgresql://", "postgresql+asyncpg://")
    elif base_url.startswith("sqlite://"):
        async_url = base_url.replace("sqlite://", "sqlite+aiosqlite://")
    else:
        logger.warning("Unknown database URL format for async engine: %s", base_url)
        async_url = base_url

    # Convert sslmode for asyncpg compatibility
    if "asyncpg" in async_url and "sslmode" in async_url:
        async_url = _convert_sslmode_for_asyncpg(async_url)

    _ASYNC_DATABASE_URL_CACHE = async_url
    return async_url


def get_async_engine() -> AsyncEngine:
    # Import here to avoid circular import
    from kagami.core.config.unified_config import get_bool_config

    global _ASYNC_ENGINE, _ASYNC_ENGINE_LOOP_ID

    # Check if we're on a different event loop than when the engine was created
    # This prevents "attached to a different loop" errors when asyncio.run() is called multiple times
    current_loop_id: int | None = None
    try:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)
    except RuntimeError:
        # No running loop - that's fine, we'll create engine anyway
        pass

    # If engine exists but was created on a different loop, reset it
    if _ASYNC_ENGINE is not None:
        if _ASYNC_ENGINE_LOOP_ID is not None and current_loop_id is not None:
            if current_loop_id != _ASYNC_ENGINE_LOOP_ID:
                # This is expected during uvicorn reload or test setup - reduce to DEBUG
                logger.debug(
                    "Event loop change detected (old=%s, new=%s). Resetting async engine (expected during reload).",
                    _ASYNC_ENGINE_LOOP_ID,
                    current_loop_id,
                )
                # Dispose old engine connections
                try:
                    # Can't await dispose() here since we might not be in async context
                    # The old connections will be cleaned up by garbage collection
                    pass
                except Exception:
                    pass
                _ASYNC_ENGINE = None
                _ASYNC_ENGINE_LOOP_ID = None
                # Also reset session factory since it's bound to the old engine
                global _ASYNC_SESSION_FACTORY
                _ASYNC_SESSION_FACTORY = None

        if _ASYNC_ENGINE is not None:
            return _ASYNC_ENGINE

    database_url = _resolve_async_database_url()
    if database_url.startswith("sqlite+aiosqlite://"):
        is_memory = ":memory:" in database_url
        # In tests, share a single StaticPool to avoid creating 100s of connections
        engine = create_async_engine(
            database_url,
            poolclass=StaticPool if is_memory else NullPool,
            echo=get_bool_config("SQL_ECHO", False),
            connect_args={"check_same_thread": False},
        )
    else:
        connect_args: dict[str, Any] = {}
        if "cockroach" in database_url.lower():
            pass

        # SECURITY: Enforce TLS in production (Dec 21, 2025)
        if database_url.startswith("postgresql"):
            import os

            environment = os.getenv("ENVIRONMENT", "development").lower()
            if environment == "production":
                if "sslmode=disable" in database_url or "ssl=disable" in database_url:
                    raise RuntimeError(
                        "Production database connections must use TLS. "
                        "Remove sslmode=disable (or ssl=disable for asyncpg) from DATABASE_URL. "
                        "Recommended: sslmode=verify-full (psycopg2) or ssl=verify-full (asyncpg). "
                        "Example: postgresql+asyncpg://user@host:26257/db?ssl=verify-full"
                    )

        # Use reduced pool size for tests/dev to save memory
        # Production default: 50
        import os

        is_test = os.getenv("KAGAMI_TEST_MODE") == "1" or os.getenv("KAGAMI_BOOT_MODE") == "test"
        pool_size = 5 if is_test else 50
        max_overflow = 10 if is_test else 50

        engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=get_bool_config("SQL_ECHO", False),
            connect_args=connect_args,
            # Use READ COMMITTED to reduce serialization conflicts in CockroachDB
            # (default SERIALIZABLE is too strict for receipt persistence)
            isolation_level="READ COMMITTED",
        )

    setup_async_event_listeners(engine)
    _ASYNC_ENGINE = engine

    # Store the loop ID so we can detect loop changes later
    _ASYNC_ENGINE_LOOP_ID = current_loop_id

    return _ASYNC_ENGINE


def _get_async_session_factory() -> async_sessionmaker:
    global _ASYNC_SESSION_FACTORY
    if _ASYNC_SESSION_FACTORY is None:
        _ASYNC_SESSION_FACTORY = async_sessionmaker(
            bind=get_async_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _ASYNC_SESSION_FACTORY


def setup_async_event_listeners(engine: AsyncEngine) -> None:
    """Setup event listeners for async engine using the sync_engine attribute."""
    try:
        _ = engine.sync_engine  # Accessing the attribute sets up listeners internally.
    except Exception:
        logger.debug("Async engine does not expose sync_engine for event listeners")


async def init_async_db() -> None:
    """Initialize database tables asynchronously."""
    from .models import Base

    engine = get_async_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        logger.info("Database tables created successfully")
    except SQLAlchemyError as exc:
        if "already exists" in str(exc).lower():
            logger.info("Database tables already exist (skip)")
        else:
            logger.error(f"Failed to create database tables: {exc}")
            raise


def _is_serialization_error(exc: Exception) -> bool:
    """Check if exception is a CockroachDB serialization conflict (retriable)."""
    error_str = str(exc).lower()
    return (
        "serialization" in error_str
        or "retry_serializable" in error_str
        or "restart transaction" in error_str
        or "transactionretryerror" in error_str
    )


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session.

    In test mode, automatically creates tables on first use.
    """
    global _TABLES_INITIALIZED

    # Auto-create tables on first use in test mode
    # This prevents "no such table" errors in tests
    if not _TABLES_INITIALIZED:
        import os

        is_test = os.getenv("KAGAMI_TEST_MODE") == "1" or os.getenv("KAGAMI_BOOT_MODE") == "test"
        if is_test:
            try:
                await init_async_db()
            except Exception as e:
                # Log at debug level - table creation might fail if already exists
                logger.debug(f"Auto table creation: {e}")
            _TABLES_INITIALIZED = True

    session_factory = _get_async_session_factory()
    session: AsyncSession = session_factory()
    try:
        yield session
        await session.commit()
    except Exception as exc:
        # Log at debug level for serialization errors (normal under concurrent load)
        if _is_serialization_error(exc):
            logger.debug(f"Async DB serialization conflict (caller should retry): {exc}")
        else:
            logger.error(f"Async DB transaction failed: {exc}")
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_async_db_session_with_retry(
    max_retries: int = 5,
    initial_delay: float = 0.05,
) -> AsyncGenerator[AsyncSession, None]:
    """Get async database session with automatic retry on serialization errors.

    CockroachDB can return RETRY_SERIALIZABLE errors under concurrent load.
    This context manager automatically retries the entire transaction.

    Args:
        max_retries: Maximum retry attempts (default 5)
        initial_delay: Initial backoff delay in seconds

    Yields:
        AsyncSession with automatic retry on serialization conflicts

    Raises:
        Exception: If all retries exhausted or non-retriable error occurs
    """
    import random

    delay = initial_delay
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            async with get_async_db_session() as session:
                yield session
                return  # Success - exit retry loop
        except Exception as exc:
            last_exc = exc

            if not _is_serialization_error(exc):
                # Non-retriable error - raise immediately
                raise

            if attempt < max_retries - 1:
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, delay * 0.5)
                actual_delay = delay + jitter
                logger.debug(
                    f"DB serialization conflict (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {actual_delay:.3f}s"
                )
                await asyncio.sleep(actual_delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(f"DB transaction failed after {max_retries} retries: {exc}")
                raise

    # Should not reach here, but for safety
    if last_exc:
        raise last_exc


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_async_db_session (backwards compatibility)."""
    async with get_async_db_session() as session:
        yield session


def reset_async_engine() -> None:
    """Reset the async engine and session factory cache.

    Useful for testing or when database configuration changes.
    Also resets the loop ID tracking to allow fresh engine creation.
    """
    global \
        _ASYNC_DATABASE_URL_CACHE, \
        _ASYNC_ENGINE, \
        _ASYNC_SESSION_FACTORY, \
        _ASYNC_ENGINE_LOOP_ID, \
        _TABLES_INITIALIZED
    _ASYNC_DATABASE_URL_CACHE = None
    _ASYNC_ENGINE = None
    _ASYNC_SESSION_FACTORY = None
    _ASYNC_ENGINE_LOOP_ID = None
    _TABLES_INITIALIZED = False


__all__ = [
    "get_async_db_session",
    "get_async_db_session_with_retry",
    "get_async_engine",
    "get_async_session",
    "init_async_db",
    "reset_async_engine",
]


# Backwards compatibility - expose engine and session factory as module attributes
def __getattr__(name: str) -> Any:
    """Lazy attribute access for backwards compatibility."""
    if name == "async_engine":
        return get_async_engine()
    elif name == "AsyncSessionLocal":
        return _get_async_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
