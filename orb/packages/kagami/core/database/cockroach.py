"""
CockroachDB integration for K os.

Provides distributed SQL with strong consistency and horizontal scaling.
"""

import asyncio
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import asyncpg
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import asyncpg as sqla_asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Import config later to avoid circular dependency

try:
    from kagami_observability.telemetry import traced_operation as _traced_operation

    traced_operation = _traced_operation
except ImportError:

    @contextmanager
    def traced_operation(
        name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[None, None, None]:
        """Dummy traced operation when telemetry not available."""
        yield


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AsyncPG JSON codec compatibility (SQLAlchemy 2.x)
# Dec 21, 2025 FIX: Target PGDialect_asyncpg, not PGDialect
# ---------------------------------------------------------------------------
_target_dialect = sqla_asyncpg.PGDialect_asyncpg
_orig_setup_json = getattr(_target_dialect, "setup_asyncpg_json_codec", None)
_orig_setup_jsonb = getattr(_target_dialect, "setup_asyncpg_jsonb_codec", None)
_orig_set_type_codec = getattr(asyncpg.connection.Connection, "set_type_codec", None)


if _orig_setup_json is not None:

    async def _safe_json_codec(self: Any, conn: Any) -> None:
        assert _orig_setup_json is not None
        try:
            await _orig_setup_json(self, conn)
        except ValueError as exc:
            if "pg_catalog.json" in str(exc):
                logger.warning(
                    "Cockroach JSON codec unavailable, falling back to default text handling"
                )
                return
            raise

    _target_dialect.setup_asyncpg_json_codec = _safe_json_codec  # type: ignore[method-assign]


if _orig_setup_jsonb is not None:

    async def _safe_jsonb_codec(self: Any, conn: Any) -> None:
        assert _orig_setup_jsonb is not None
        try:
            await _orig_setup_jsonb(self, conn)
        except ValueError as exc:
            if "pg_catalog.json" in str(exc):
                logger.warning(
                    "Cockroach JSONB codec unavailable, falling back to default text handling"
                )
                return
            raise

    _target_dialect.setup_asyncpg_jsonb_codec = _safe_jsonb_codec  # type: ignore[method-assign]


if _orig_set_type_codec is not None:

    async def _safe_set_type_codec(self: Any, typename: str, *args: Any, **kwargs: Any) -> Any:
        assert _orig_set_type_codec is not None
        try:
            return await _orig_set_type_codec(self, typename, *args, **kwargs)
        except ValueError as exc:
            if "pg_catalog.json" in str(exc):
                logger.warning(
                    "Skipping asyncpg type codec registration for %s due to Cockroach mismatch",
                    typename,
                )
                return None
            raise

    asyncpg.connection.Connection.set_type_codec = _safe_set_type_codec


@dataclass
class CockroachConfig:
    """CockroachDB configuration.

    Environment variables:
        COCKROACH_HOST: Database host (default: localhost)
        COCKROACH_PORT: Database port (default: 26257)
        COCKROACH_DATABASE: Database name (default: kagami)
        COCKROACH_USER: Database user (default: root)
        COCKROACH_PASSWORD: Database password
        COCKROACH_SSLMODE: SSL mode (default: prefer)
    """

    host: str = ""  # Set in __post_init__
    port: int = 26257
    database: str = "kagami"
    user: str = "root"
    password: str | None = None
    sslmode: str = "prefer"
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    max_retries: int = 3
    retry_delay: float = 0.5
    application_name: str = "kagami"

    def __post_init__(self) -> None:
        """Initialize from environment variables."""
        if not self.host:
            self.host = os.getenv("COCKROACH_HOST", "localhost")
        if self.password is None:
            self.password = os.getenv("COCKROACH_PASSWORD")

    statement_timeout: int = 30000
    idle_in_transaction_session_timeout: int = 60000

    @property
    def connection_string(self) -> str:
        """Build connection string."""
        auth = f"{self.user}"
        if self.password:
            auth += f":{self.password}"
        conn_str = f"postgresql+asyncpg://{auth}@{self.host}:{self.port}/{self.database}"
        if self.sslmode not in ("disable", "prefer"):
            conn_str += f"?ssl={self.sslmode}"
        return conn_str


class CockroachDB:
    """
    CockroachDB client for distributed SQL operations.

    Provides strong consistency with horizontal scaling.
    """

    def __init__(self, config: CockroachConfig | None = None) -> None:
        """Initialize CockroachDB client."""
        # Import config here to avoid circular imports
        from kagami.core.config.unified_config import settings

        self.config = config or CockroachConfig(
            host=settings.COCKROACH_HOST or "localhost",
            port=settings.COCKROACH_PORT or 26257,
            database=settings.COCKROACH_DATABASE or "kagami",
            user=settings.COCKROACH_USER or "root",
            password=settings.COCKROACH_PASSWORD,
        )
        self.engine: AsyncEngine | None = None
        self.session_factory: sessionmaker | None = None
        self.metadata = MetaData()
        self._connected = False

    async def connect(self) -> None:
        """Connect to CockroachDB cluster."""
        try:
            with traced_operation("cockroachdb.connect"):
                connect_args = {
                    "server_settings": {"application_name": self.config.application_name}
                }
                self.engine = create_async_engine(
                    self.config.connection_string,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_timeout=self.config.pool_timeout,
                    pool_recycle=self.config.pool_recycle,
                    poolclass=NullPool if self.config.pool_size == 0 else None,
                    connect_args=connect_args,
                    echo=False,
                    future=True,
                    execution_options={
                        "postgresql_use_native_json": False,
                        "postgresql_readonly": False,
                    },
                )
                self.session_factory = sessionmaker(
                    bind=self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False,  # type: ignore
                )
                async with self.engine.connect() as conn:
                    from sqlalchemy import text

                    result = await conn.execute(text("SELECT version()"))
                    version = result.scalar()
                    logger.info(f"Connected to CockroachDB: {version}")
                self._connected = True
        except Exception as e:
            logger.error(f"Failed to connect to CockroachDB: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from CockroachDB."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._connected = False
            logger.info("Disconnected from CockroachDB")

    async def execute(
        self, query: str, params: dict[str, Any] | None = None, retry: bool = True
    ) -> Any:
        """
        Execute a SQL query with automatic retries.

        Args:
            query: SQL query
            params: Query parameters
            retry: Enable automatic retry on transient errors

        Returns:
            Query result
        """
        if not self._connected:
            await self.connect()
        retries = self.config.max_retries if retry else 1
        delay = self.config.retry_delay
        for attempt in range(retries):
            try:
                with traced_operation("cockroachdb.execute", attributes={"attempt": attempt + 1}):
                    if self.session_factory is None:
                        raise RuntimeError("Session factory not initialized. Call connect() first.")
                    async with self.session_factory() as session:
                        from sqlalchemy import text

                        result = await session.execute(text(query), params)
                        try:
                            await session.commit()
                        except Exception as commit_err:
                            err_text = str(commit_err).lower()
                            if "transaction is aborted" in err_text:
                                await session.rollback()
                                raise commit_err
                            raise
                        return result
            except Exception as e:
                error_str = str(e).lower()
                is_retry_error = (
                    "40001" in error_str
                    or "serialization" in error_str
                    or "retry transaction" in error_str
                )
                if is_retry_error and attempt < retries - 1:
                    logger.warning(f"Serialization error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    try:
                        if self.session_factory is not None:
                            async with self.session_factory() as session:
                                await session.rollback()
                    except Exception:
                        pass
                    logger.error(f"Query execution failed: {e}")
                    raise

    async def execute_transaction(
        self, operations: list[tuple[Any, ...]], retry: bool = True
    ) -> bool:
        """
        Execute multiple operations in a transaction.

        Args:
            operations: List of (query, params) tuples
            retry: Enable automatic retry

        Returns:
            True if successful
        """
        if not self._connected:
            await self.connect()
        retries = self.config.max_retries if retry else 1
        delay = self.config.retry_delay
        for attempt in range(retries):
            try:
                with traced_operation(
                    "cockroachdb.transaction", attributes={"operations": len(operations)}
                ):
                    if self.session_factory is None:
                        raise RuntimeError("Session factory not initialized. Call connect() first.")
                    async with self.session_factory() as session:
                        async with session.begin():
                            from sqlalchemy import text

                            for query, params in operations:
                                await session.execute(text(query), params)
                        await session.commit()
                        return True
            except Exception as e:
                error_str = str(e).lower()
                is_retry_error = (
                    "40001" in error_str
                    or "serialization" in error_str
                    or "retry transaction" in error_str
                )
                if is_retry_error and attempt < retries - 1:
                    logger.warning(f"Transaction serialization error, retrying: {e}")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Transaction failed: {e}")
                    raise
            except Exception as e:  # noqa: B025
                logger.error(f"Transaction failed: {e}")
                raise
        return False

    async def create_table(
        self,
        table_name: str,
        columns: dict[str, str],
        primary_key: str | list[str] | None = None,
        indexes: list[dict[str, Any]] | None = None,
        partition_by: str | None = None,
    ) -> bool:
        """
        Create a table with CockroachDB-specific features.

        Args:
            table_name: Table name
            columns: Column definitions
            primary_key: Primary key column(s)
            indexes: Index definitions
            partition_by: Partitioning strategy

        Returns:
            True if created
        """
        try:
            with traced_operation("cockroachdb.create_table", attributes={"table": table_name}):
                col_defs = []
                for col_name, col_type in columns.items():
                    col_defs.append(f"{col_name} {col_type}")
                if primary_key:
                    if isinstance(primary_key, str):
                        col_defs.append(f"PRIMARY KEY ({primary_key})")
                    else:
                        col_defs.append(f"PRIMARY KEY ({', '.join(primary_key)})")
                query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
                if partition_by:
                    query += f" PARTITION BY {partition_by}"
                await self.execute(query)
                if indexes:
                    for index in indexes:
                        index_name = index.get("name", f"{table_name}_{index['column']}_idx")
                        index_col = index["column"]
                        index_type = index.get("type", "")
                        idx_query = (
                            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({index_col})"
                        )
                        if index_type:
                            idx_query = f"CREATE {index_type} INDEX IF NOT EXISTS {index_name} ON {table_name} ({index_col})"
                        await self.execute(idx_query)
                logger.info(f"Created table: {table_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            return False

    async def migrate_from_postgres(
        self, postgres_conn_string: str, tables: list[str] | None = None, batch_size: int = 1000
    ) -> dict[str, int]:
        """
        Migrate data from PostgreSQL to CockroachDB.

        Args:
            postgres_conn_string: PostgreSQL connection string
            tables: Specific tables to migrate (all if None)
            batch_size: Batch size for inserts

        Returns:
            Migration statistics
        """
        stats = {}
        try:
            with traced_operation("cockroachdb.migrate_from_postgres"):
                pg_conn = await asyncpg.connect(postgres_conn_string)
                try:
                    if not tables:
                        tables_query = "\n                            SELECT tablename FROM pg_tables\n                            WHERE schemaname = 'public'\n                        "
                        tables = [row["tablename"] for row in await pg_conn.fetch(tables_query)]
                    for table in tables:
                        logger.info(f"Migrating table: {table}")
                        structure_query = f"""
                            SELECT column_name, data_type, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_name = '{table}'
                            ORDER BY ordinal_position
                        """  # nosec B608
                        columns = await pg_conn.fetch(structure_query)
                        col_defs = {}
                        for col in columns:
                            col_type = self._map_postgres_type(col["data_type"])
                            nullable = "" if col["is_nullable"] == "YES" else " NOT NULL"
                            default = (
                                f" DEFAULT {col['column_default']}" if col["column_default"] else ""
                            )
                            col_defs[col["column_name"]] = f"{col_type}{nullable}{default}"
                        await self.create_table(table, col_defs)
                        count_query = f"SELECT COUNT(*) FROM {table}"  # nosec B608
                        total_rows = await pg_conn.fetchval(count_query)
                        offset = 0
                        migrated = 0
                        while offset < total_rows:
                            select_query = (
                                f"SELECT * FROM {table} LIMIT {batch_size} OFFSET {offset}"  # nosec B608
                            )
                            rows = await pg_conn.fetch(select_query)
                            if rows:
                                col_names = list(rows[0].keys())
                                values_list = []
                                for row in rows:
                                    values = [row[col] for col in col_names]
                                    values_list.append(values)
                                insert_query = f"""
                                    INSERT INTO {table} ({", ".join(col_names)})
                                    VALUES ({", ".join(["$" + str(i + 1) for i in range(len(col_names))])})
                                """  # nosec B608
                                if self.session_factory is None:
                                    raise RuntimeError(
                                        "Session factory not initialized. Call connect() first."
                                    )
                                # Batch insert all values in single transaction
                                async with self.session_factory() as session:
                                    params_list = [
                                        dict(zip(col_names, values, strict=False))
                                        for values in values_list
                                    ]
                                    from sqlalchemy import text

                                    # Use executemany for batch insert
                                    for params in params_list:
                                        await session.execute(text(insert_query), params)
                                    await session.commit()
                                migrated += len(rows)
                            offset += batch_size
                            logger.info(f"Migrated {migrated}/{total_rows} rows from {table}")
                        stats[table] = migrated
                finally:
                    await pg_conn.close()
                logger.info(f"Migration complete: {stats}")
                return stats
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

    def _map_postgres_type(self, pg_type: str) -> str:
        """Map PostgreSQL type to CockroachDB type."""
        type_map = {
            "character varying": "STRING",
            "text": "STRING",
            "integer": "INT",
            "bigint": "INT8",
            "smallint": "INT2",
            "numeric": "DECIMAL",
            "real": "FLOAT4",
            "double precision": "FLOAT8",
            "boolean": "BOOL",
            "date": "DATE",
            "timestamp without time zone": "TIMESTAMP",
            "timestamp with time zone": "TIMESTAMPTZ",
            "json": "JSONB",
            "jsonb": "JSONB",
            "uuid": "UUID",
            "bytea": "BYTES",
        }
        return type_map.get(pg_type.lower(), "STRING")

    async def get_cluster_info(self) -> dict[str, Any]:
        """Get CockroachDB cluster information."""
        try:
            info = {}
            settings_query = "SHOW CLUSTER SETTING version"
            result = await self.execute(settings_query)
            info["version"] = result.scalar()
            nodes_query = "SHOW CLUSTER SETTING kv.range.count"
            result = await self.execute(nodes_query)
            info["range_count"] = result.scalar()
            size_query = "\n                SELECT\n                    sum(range_count) as total_ranges,\n                    sum(replica_count) as total_replicas,\n                    sum(bytes) as total_bytes\n                FROM crdb_internal.table_stats\n            "
            result = await self.execute(size_query)
            row = result.first()
            if row:
                info.update(
                    {"total_ranges": row[0], "total_replicas": row[1], "total_bytes": row[2]}
                )
            return info
        except Exception as e:
            logger.error(f"Failed to get cluster info: {e}")
            return {}


_cockroach_client: CockroachDB | None = None
