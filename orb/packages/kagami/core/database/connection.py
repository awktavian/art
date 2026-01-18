"""Database connection management for K os."""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from kagami.core.boot_mode import is_test_mode as _is_test_mode

# Patch SQLAlchemy (CockroachDB compatibility) before creating any engines.
try:  # pragma: no cover - import-time patch
    from sqlalchemy.dialects.postgresql import base as pg_base

    _original_get_server_version_info = pg_base.PGDialect._get_server_version_info

    def _patched_get_server_version_info(self, connection: Any) -> tuple[int, int]:  # type: ignore[no-untyped-def]
        try:
            result: tuple[int, int] = _original_get_server_version_info(self, connection)
            return result
        except (AssertionError, ValueError, AttributeError) as exc:
            message = str(exc)
            if "CockroachDB" in message or "Could not determine version" in message:
                logging.getLogger(__name__).info(
                    "✅ CockroachDB detected, using PostgreSQL 15.0 compatibility"
                )
                return (15, 0)
            raise

    pg_base.PGDialect._get_server_version_info = _patched_get_server_version_info  # type: ignore[method-assign]
    logging.getLogger(__name__).info("✅ SQLAlchemy patched for CockroachDB compatibility")
except Exception as patch_exc:  # pragma: no cover - diagnostic only
    logging.getLogger(__name__).warning(f"Could not patch SQLAlchemy dialect: {patch_exc}")


logger = logging.getLogger(__name__)

_DATABASE_URL_CACHE: str | None = None
_TABLES_INITIALIZED: bool = False  # OPTIMIZATION: Skip repeated table creation


def _under_pytest() -> bool:
    """Check if running under pytest or CI environment."""
    return _is_test_mode() or os.getenv("CI") == "true"


def _should_persist_test_db() -> bool:
    """Check if test database should persist across runs."""
    return (os.getenv("KAGAMI_TEST_PERSIST_DB") or "0").lower() in ("1", "true", "yes", "on")


def _resolve_database_url() -> str:
    """Resolve and cache the database URL with environment-specific handling.

    Handles:
    - Test mode SQLite fallback
    - CockroachDB URL normalization
    - Production TLS validation

    Returns:
        Processed database URL string.

    Raises:
        RuntimeError: If no DATABASE_URL and not in test mode,
            or if production mode uses insecure settings.
    """
    global _DATABASE_URL_CACHE
    if _DATABASE_URL_CACHE is not None:
        return _DATABASE_URL_CACHE

    # Import here to avoid circular import
    from kagami.core.config.unified_config import get_database_url as _get_database_url

    raw_url = _get_database_url()
    test_env = _under_pytest()
    persist = _should_persist_test_db()

    if not raw_url:
        if test_env and not persist:
            pid = os.getpid()
            db_path = os.path.join(tempfile.gettempdir(), f"kagami_test_{pid}.db")
            raw_url = f"sqlite:///{db_path}"
            logger.info("PYTEST: using per-process SQLite database at %s", db_path)
        else:
            raise RuntimeError(
                "DATABASE_URL environment variable is required. Set DATABASE_URL or export "
                "KAGAMI_TEST_PERSIST_DB=1 for persistent test databases."
            )
    elif test_env and not persist and not raw_url.startswith("sqlite"):
        pid = os.getpid()
        db_path = os.path.join(tempfile.gettempdir(), f"kagami_test_{pid}.db")
        raw_url = f"sqlite:///{db_path}"
        logger.info("PYTEST: overriding DATABASE_URL to SQLite at %s", db_path)

    if raw_url.startswith("cockroachdb+psycopg2://"):
        raw_url = raw_url.replace("cockroachdb+psycopg2://", "postgresql+psycopg2://")
    elif raw_url.startswith("cockroachdb://"):
        raw_url = raw_url.replace("cockroachdb://", "postgresql://")

    # SECURITY CHECK (Dec 21, 2025): Validate TLS configuration in production
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production" and not raw_url.startswith("sqlite"):
        if "sslmode=disable" in raw_url.lower():
            raise RuntimeError(
                "Production database MUST use TLS. "
                "Remove sslmode=disable from DATABASE_URL. "
                "Use sslmode=require or sslmode=verify-full"
            )
        if "localhost" not in raw_url and "127.0.0.1" not in raw_url:
            if "sslmode" not in raw_url.lower():
                logger.warning(
                    "⚠️  DATABASE_URL in production should specify sslmode. "
                    "Add sslmode=require or sslmode=verify-full to DATABASE_URL"
                )

    _DATABASE_URL_CACHE = raw_url
    return raw_url


def resolve_database_url() -> str:
    """Public helper used by other modules to obtain the processed database URL."""
    return _resolve_database_url()


def get_engine() -> Engine:
    """Lazily create (or return cached) SQLAlchemy engine."""
    # Import here to avoid circular import
    from kagami.core.config.unified_config import get_bool_config, get_int_config

    database_url = _resolve_database_url()
    if database_url.startswith("sqlite"):
        is_memory = database_url in ("sqlite:///:memory:", "sqlite://") or database_url.endswith(
            ":memory:"
        )
        connect_args = {"check_same_thread": False}
        if is_memory:
            engine = create_engine(
                "sqlite://",
                connect_args=connect_args,
                poolclass=StaticPool,
                echo=get_bool_config("SQL_ECHO", False),
            )
        else:
            engine = create_engine(
                database_url,
                connect_args=connect_args,
                echo=get_bool_config("SQL_ECHO", False),
            )
    else:
        connect_args = {
            "connect_timeout": int(get_int_config("DB_CONNECT_TIMEOUT", 10)),  # type: ignore[dict-item]
        }
        if database_url.startswith("postgresql"):
            # PERFORMANCE FIX (Jan 2026): Reduced statement timeout from 30s to 10s
            # to prevent slow queries from blocking connection pool.
            # Use DB_STATEMENT_TIMEOUT_MS env var to override for specific use cases.
            connect_args["options"] = (
                f"-c statement_timeout={int(get_int_config('DB_STATEMENT_TIMEOUT_MS', 10000))}"  # type: ignore[assignment]
            )

            # SECURITY: Enforce TLS in production (Dec 21, 2025)
            environment = os.getenv("ENVIRONMENT", "development").lower()
            if environment == "production":
                if "sslmode=disable" in database_url:
                    raise RuntimeError(
                        "Production database connections must use TLS. "
                        "Remove sslmode=disable from DATABASE_URL. "
                        "Recommended: sslmode=verify-full with certificates. "
                        "Example: postgresql://user@host:26257/db?sslmode=verify-full&"
                        "sslrootcert=/certs/ca.crt&sslcert=/certs/client.crt&sslkey=/certs/client.key"
                    )
        if "cockroach" in database_url.lower():
            pass
        # OPTIMIZATION (Dec 21, 2025): Increased connection pool for high-concurrency workloads
        # Previous: 50 + 50 = 100 max connections
        # Current: 100 + 100 = 200 max connections (2x increase)
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=int(get_int_config("DB_POOL_SIZE", 100)),  # 2x increase
            max_overflow=int(get_int_config("DB_MAX_OVERFLOW", 100)),  # 2x increase
            pool_timeout=int(get_int_config("DB_POOL_TIMEOUT", 10)),  # Fail faster (30s → 10s)
            pool_recycle=int(get_int_config("DB_POOL_RECYCLE", 3600)),
            pool_pre_ping=True,
            echo=get_bool_config("SQL_ECHO", False),
            connect_args=connect_args,
            execution_options={
                "compiled_cache": {},  # Enable prepared statement cache
            },
        )

    return engine


def get_session_factory() -> sessionmaker:
    """Get the session factory for creating database sessions.

    This is the recommended way to create database sessions for manual
    session management (non-FastAPI code).

    Usage:
        session_factory = get_session_factory()
        db = session_factory()
        try:
            # use db
        finally:
            db.close()

    For FastAPI endpoints, prefer using get_db() with Depends():
        @router.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # db is auto-closed after request

    Returns:
        SQLAlchemy sessionmaker instance
    """
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=get_engine(),
    )


# Private alias for internal use (backward compatibility)
_get_session_factory = get_session_factory


def _classify_sql(text: str) -> str:
    """Classify SQL statement type for metrics/logging.

    Args:
        text: SQL statement text.

    Returns:
        Statement type (SELECT, INSERT, UPDATE, DELETE, CREATE,
        ALTER, DROP, or OTHER).
    """
    try:
        t = (text or "").lstrip().upper()
        if not t:
            return "OTHER"
        for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"):
            if t.startswith(kw):
                return kw
        return "OTHER"
    except Exception:
        return "OTHER"


def init_db_sync() -> None:
    """Initialize database tables synchronously."""
    import psycopg2.errors
    from sqlalchemy.exc import ProgrammingError

    from .models import Base

    engine = get_engine()
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Database tables created successfully")
    except ProgrammingError as exc:
        # Handle table already exists error gracefully (CockroachDB/Postgres)
        if isinstance(exc.orig, psycopg2.errors.DuplicateTable):
            logger.info("Database tables already exist (idempotent)")
        else:
            logger.error(f"Failed to create database tables: {exc}")
            raise
    except SQLAlchemyError as exc:
        logger.error(f"Failed to create database tables: {exc}")
        raise


def get_db() -> Generator[Session, None, None]:
    """Get database session for dependency injection."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_session_sync() -> Session:
    """Synchronous helper to obtain a DB session.

    CLARITY FIX (Jan 2026): Renamed from async get_session() to be explicit
    that this returns a synchronous session. Use get_db() for FastAPI deps.
    """
    session_factory = get_session_factory()
    return session_factory()


# Legacy alias for backward compatibility
async def get_session() -> Session:
    """Async-compatible helper to obtain a DB session.

    Note: Despite being async, this returns a synchronous Session.
    For true async operations, use AsyncSession from sqlalchemy.ext.asyncio.
    """
    return get_session_sync()


async def get_session_generator() -> AsyncGenerator[Session, None]:
    """Async generator that yields DB sessions (compat with older tests).

    DEPRECATION NOTE: Consider using get_db() for FastAPI endpoints instead.
    """
    session = get_session_sync()
    try:
        yield session
    finally:
        session.close()


async def init_db() -> None:
    """Initialize database tables asynchronously.

    OPTIMIZED (Dec 28, 2025): Skips table creation if already done in this process.
    """
    global _TABLES_INITIALIZED

    # Fast path: skip if already initialized
    if _TABLES_INITIALIZED:
        logger.debug("Database tables already initialized (cached)")
        return

    import psycopg2.errors
    from sqlalchemy.exc import ProgrammingError

    from .models import Base

    engine = get_engine()
    try:
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: Base.metadata.create_all(engine, checkfirst=True))
        _TABLES_INITIALIZED = True
        logger.debug("Database tables ready")
    except ProgrammingError as exc:
        # Handle table already exists error gracefully (CockroachDB/Postgres)
        if isinstance(exc.orig, psycopg2.errors.DuplicateTable):
            _TABLES_INITIALIZED = True
            logger.debug("Database tables already exist")
        else:
            logger.error(f"Failed to create database tables: {exc}")
            raise
    except SQLAlchemyError as exc:
        logger.error(f"Failed to create database tables: {exc}")
        raise


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[Session, None]:
    """Async context manager for database sessions."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        logger.error(f"Database transaction failed: {exc}")
        session.rollback()
        raise
    finally:
        session.close()


def check_connection() -> bool:
    """Check if database connection is working using a driver-level ping."""
    try:
        engine = get_engine()
    except Exception as exc:
        logger.error(f"Engine initialization failed: {exc}")
        return False

    try:
        backend_name = getattr(getattr(engine, "url", None), "get_backend_name", lambda: "")()
        if str(backend_name).lower().startswith("sqlite"):
            with engine.connect():
                return True
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            try:
                dbapi_conn = conn.connection

            except Exception:
                dbapi_conn = conn  # type: ignore[assignment]
            if conn.dialect.do_ping(dbapi_conn):
                return True
            trans = conn.begin()
            trans.rollback()
            return True
    except Exception as exc:
        logger.error(f"Database connection check failed: {exc}")
        return False


__all__ = [
    "check_connection",
    "get_db",
    "get_db_session",
    "get_session",
    "get_session_factory",
    "get_session_generator",
    "init_db",
    "init_db_sync",
    "resolve_database_url",
]
