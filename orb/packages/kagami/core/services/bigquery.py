"""BigQuery Analytics Integration.

Provides data warehouse capabilities for Kagami analytics:
- Training metrics storage and analysis
- Usage analytics and dashboards
- Colony performance tracking
- Cost analysis

ARCHITECTURE:
=============
    ┌─────────────────────────────────────────────────────────────────┐
    │                     Kagami Systems                               │
    │                                                                  │
    │   Training          Usage           Colony          Cost         │
    │   Metrics           Analytics       Performance     Tracking     │
    │      │                 │                │              │         │
    └──────┼─────────────────┼────────────────┼──────────────┼─────────┘
           │                 │                │              │
           ▼                 ▼                ▼              ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                     BigQuery                                     │
    │                                                                  │
    │   kagami.training_metrics     kagami.api_usage                   │
    │   kagami.colony_events        kagami.cost_tracking               │
    └─────────────────────────────────────────────────────────────────┘

USAGE:
======
    from kagami.core.services.bigquery import get_bigquery_service

    service = get_bigquery_service()
    await service.initialize()

    # Log training metrics
    await service.log_training_metrics({
        "epoch": 10,
        "loss": 0.05,
        "colony": "forge",
    })

    # Query analytics
    results = await service.query(
        "SELECT * FROM kagami.training_metrics WHERE epoch > 5"
    )

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import
_bigquery = None
_bigquery_available = False


def _lazy_import_bigquery() -> Any:
    """Lazy import google.cloud.bigquery."""
    global _bigquery, _bigquery_available
    if _bigquery is not None:
        return _bigquery
    try:
        from google.cloud import bigquery

        _bigquery = bigquery
        _bigquery_available = True
        return bigquery
    except ImportError as e:
        _bigquery_available = False
        raise ImportError(
            "google-cloud-bigquery not installed. Install with: pip install google-cloud-bigquery"
        ) from e


@dataclass
class BigQueryConfig:
    """Configuration for BigQuery service.

    Attributes:
        project_id: GCP project ID.
        dataset_id: Default dataset for tables.
        location: BigQuery location (e.g., US, EU).
        use_streaming: Use streaming inserts for real-time data.
        batch_size: Batch size for non-streaming inserts.
    """

    project_id: str | None = None
    dataset_id: str = "kagami"
    location: str = "US"
    use_streaming: bool = True
    batch_size: int = 500

    @classmethod
    def from_env(cls) -> BigQueryConfig:
        """Create config from environment."""
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID"),
            dataset_id=os.getenv("BIGQUERY_DATASET", "kagami"),
            location=os.getenv("BIGQUERY_LOCATION", "US"),
            use_streaming=os.getenv("BIGQUERY_USE_STREAMING", "true").lower() == "true",
            batch_size=int(os.getenv("BIGQUERY_BATCH_SIZE", "500")),
        )


@dataclass
class QueryResult:
    """Result from a BigQuery query.

    Attributes:
        rows: List of row dicts.
        total_rows: Total row count.
        schema: Table schema.
        job_id: Query job ID.
        bytes_processed: Bytes processed (for cost estimation).
        duration_ms: Query duration in milliseconds.
    """

    rows: list[dict[str, Any]]
    total_rows: int
    schema: list[dict[str, str]] = field(default_factory=list)
    job_id: str = ""
    bytes_processed: int = 0
    duration_ms: float = 0.0


# Pre-defined table schemas
TABLE_SCHEMAS = {
    "training_metrics": [
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "epoch", "type": "INT64", "mode": "NULLABLE"},
        {"name": "step", "type": "INT64", "mode": "NULLABLE"},
        {"name": "loss", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "learning_rate", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "colony", "type": "STRING", "mode": "NULLABLE"},
        {"name": "model_name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "batch_size", "type": "INT64", "mode": "NULLABLE"},
        {"name": "gpu_memory_mb", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "throughput_samples_sec", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "metadata", "type": "JSON", "mode": "NULLABLE"},
    ],
    "api_usage": [
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "endpoint", "type": "STRING", "mode": "REQUIRED"},
        {"name": "method", "type": "STRING", "mode": "REQUIRED"},
        {"name": "status_code", "type": "INT64", "mode": "REQUIRED"},
        {"name": "latency_ms", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "user_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "request_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "colony", "type": "STRING", "mode": "NULLABLE"},
        {"name": "tokens_in", "type": "INT64", "mode": "NULLABLE"},
        {"name": "tokens_out", "type": "INT64", "mode": "NULLABLE"},
        {"name": "metadata", "type": "JSON", "mode": "NULLABLE"},
    ],
    "colony_events": [
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "colony", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_type", "type": "STRING", "mode": "REQUIRED"},
        {"name": "e8_index", "type": "INT64", "mode": "NULLABLE"},
        {"name": "fano_line", "type": "STRING", "mode": "NULLABLE"},
        {"name": "duration_ms", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "success", "type": "BOOL", "mode": "NULLABLE"},
        {"name": "error", "type": "STRING", "mode": "NULLABLE"},
        {"name": "payload", "type": "JSON", "mode": "NULLABLE"},
    ],
    "cost_tracking": [
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "service", "type": "STRING", "mode": "REQUIRED"},
        {"name": "resource_type", "type": "STRING", "mode": "REQUIRED"},
        {"name": "usage_amount", "type": "FLOAT64", "mode": "REQUIRED"},
        {"name": "usage_unit", "type": "STRING", "mode": "REQUIRED"},
        {"name": "estimated_cost_usd", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "project_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "labels", "type": "JSON", "mode": "NULLABLE"},
    ],
}


class BigQueryService:
    """BigQuery analytics service.

    Provides data warehouse capabilities for Kagami:
    - Structured logging of training metrics
    - API usage tracking
    - Colony event analysis
    - Cost tracking and optimization

    Thread-safe with connection pooling.

    Example:
        service = BigQueryService()
        await service.initialize()

        # Log training metrics
        await service.log_training_metrics({
            "epoch": 10,
            "loss": 0.05,
            "colony": "forge",
        })

        # Query data
        results = await service.query('''
            SELECT colony, AVG(loss) as avg_loss
            FROM kagami.training_metrics
            GROUP BY colony
        ''')
    """

    def __init__(self, config: BigQueryConfig | None = None):
        """Initialize BigQuery service.

        Args:
            config: Service configuration.
        """
        self.config = config or BigQueryConfig.from_env()
        self._client = None
        self._initialized = False
        self._dataset = None
        self._tables: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize BigQuery client and ensure dataset/tables exist."""
        if self._initialized:
            return

        bigquery = _lazy_import_bigquery()

        if not self.config.project_id:
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                        headers={"Metadata-Flavor": "Google"},
                        timeout=2.0,
                    )
                    self.config.project_id = resp.text
            except Exception as e:
                raise RuntimeError("GCP project ID not configured") from e

        self._client = bigquery.Client(
            project=self.config.project_id,
            location=self.config.location,
        )

        # Ensure dataset exists
        await self._ensure_dataset_exists()

        # Ensure tables exist
        for table_name in TABLE_SCHEMAS:
            await self._ensure_table_exists(table_name)

        self._initialized = True
        logger.info(f"BigQuery initialized: {self.config.project_id}.{self.config.dataset_id}")

    def _ensure_initialized(self) -> None:
        """Ensure client is initialized."""
        if not self._initialized:
            raise RuntimeError("BigQueryService not initialized. Call initialize() first.")

    async def _ensure_dataset_exists(self) -> None:
        """Create dataset if it doesn't exist."""
        bigquery = _lazy_import_bigquery()

        dataset_ref = bigquery.DatasetReference(
            self.config.project_id,
            self.config.dataset_id,
        )

        def _create() -> None:
            try:
                self._client.get_dataset(dataset_ref)
            except Exception:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.config.location
                self._client.create_dataset(dataset, exists_ok=True)
                logger.info(f"Created dataset: {self.config.dataset_id}")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _create)

        self._dataset = dataset_ref

    async def _ensure_table_exists(self, table_name: str) -> None:
        """Create table if it doesn't exist.

        Args:
            table_name: Table name (must be in TABLE_SCHEMAS).
        """
        if table_name not in TABLE_SCHEMAS:
            raise ValueError(f"Unknown table: {table_name}")

        bigquery = _lazy_import_bigquery()

        table_ref = self._dataset.table(table_name)
        schema = [
            bigquery.SchemaField(
                f["name"],
                f["type"],
                mode=f.get("mode", "NULLABLE"),
            )
            for f in TABLE_SCHEMAS[table_name]
        ]

        def _create() -> Any:
            try:
                return self._client.get_table(table_ref)
            except Exception:
                table = bigquery.Table(table_ref, schema=schema)

                # Enable time-based partitioning
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="timestamp",
                )

                return self._client.create_table(table, exists_ok=True)

        loop = asyncio.get_running_loop()
        table = await loop.run_in_executor(None, _create)
        self._tables[table_name] = table

    async def insert_rows(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Insert rows into a table.

        Args:
            table_name: Target table name.
            rows: List of row dicts.

        Returns:
            List of any errors (empty if successful).
        """
        self._ensure_initialized()

        if table_name not in self._tables:
            await self._ensure_table_exists(table_name)

        # Add timestamp if not present
        for row in rows:
            if "timestamp" not in row:
                row["timestamp"] = datetime.now(UTC).isoformat()

        def _insert() -> list[dict[str, Any]]:
            table_ref = self._dataset.table(table_name)

            if self.config.use_streaming:
                errors = self._client.insert_rows_json(table_ref, rows)
                return errors
            else:
                # Use load job for batch inserts
                job_config = _lazy_import_bigquery().LoadJobConfig(
                    write_disposition="WRITE_APPEND",
                )
                job = self._client.load_table_from_json(
                    rows,
                    table_ref,
                    job_config=job_config,
                )
                job.result()
                return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _insert)

    async def query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a SQL query.

        Args:
            sql: SQL query string.
            parameters: Query parameters for parameterized queries.

        Returns:
            QueryResult with rows and metadata.

        Example:
            result = await service.query('''
                SELECT colony, COUNT(*) as count
                FROM kagami.colony_events
                WHERE timestamp > @start_date
                GROUP BY colony
            ''', parameters={"start_date": "2026-01-01"})
        """
        self._ensure_initialized()
        bigquery = _lazy_import_bigquery()

        import time

        start_time = time.perf_counter()

        def _query() -> tuple[list[dict[str, Any]], Any]:
            job_config = bigquery.QueryJobConfig()

            if parameters:
                job_config.query_parameters = [
                    bigquery.ScalarQueryParameter(k, "STRING", str(v))
                    for k, v in parameters.items()
                ]

            job = self._client.query(sql, job_config=job_config)
            results = list(job.result())

            return [dict(row) for row in results], job

        loop = asyncio.get_running_loop()
        rows, job = await loop.run_in_executor(None, _query)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Extract schema
        schema = []
        if job.schema:
            schema = [{"name": f.name, "type": f.field_type} for f in job.schema]

        return QueryResult(
            rows=rows,
            total_rows=len(rows),
            schema=schema,
            job_id=job.job_id,
            bytes_processed=job.total_bytes_processed or 0,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # Convenience Methods for Common Operations
    # =========================================================================

    async def log_training_metrics(
        self,
        metrics: dict[str, Any],
    ) -> None:
        """Log training metrics.

        Args:
            metrics: Training metrics dict. Supported fields:
                - epoch, step, loss, learning_rate
                - colony, model_name, batch_size
                - gpu_memory_mb, throughput_samples_sec
                - metadata (JSON)
        """
        await self.insert_rows("training_metrics", [metrics])

    async def log_api_usage(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        **kwargs: Any,
    ) -> None:
        """Log API usage event.

        Args:
            endpoint: API endpoint path.
            method: HTTP method.
            status_code: Response status code.
            latency_ms: Request latency.
            **kwargs: Additional fields (user_id, request_id, etc.)
        """
        row = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            **kwargs,
        }
        await self.insert_rows("api_usage", [row])

    async def log_colony_event(
        self,
        colony: str,
        event_type: str,
        e8_index: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Log colony event.

        Args:
            colony: Colony name.
            event_type: Event type string.
            e8_index: E8 lattice index.
            **kwargs: Additional fields (duration_ms, success, etc.)
        """
        row = {
            "colony": colony,
            "event_type": event_type,
            "e8_index": e8_index,
            **kwargs,
        }
        await self.insert_rows("colony_events", [row])

    async def log_cost(
        self,
        service: str,
        resource_type: str,
        usage_amount: float,
        usage_unit: str,
        estimated_cost_usd: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Log cost tracking event.

        Args:
            service: GCP service name.
            resource_type: Resource type.
            usage_amount: Usage amount.
            usage_unit: Usage unit.
            estimated_cost_usd: Estimated cost in USD.
            **kwargs: Additional fields.
        """
        row = {
            "service": service,
            "resource_type": resource_type,
            "usage_amount": usage_amount,
            "usage_unit": usage_unit,
            "estimated_cost_usd": estimated_cost_usd,
            **kwargs,
        }
        await self.insert_rows("cost_tracking", [row])

    # =========================================================================
    # Analytics Queries
    # =========================================================================

    async def get_training_summary(
        self,
        model_name: str | None = None,
        colony: str | None = None,
        days: int = 7,
    ) -> QueryResult:
        """Get training summary statistics.

        Args:
            model_name: Filter by model name.
            colony: Filter by colony.
            days: Number of days to include.

        Returns:
            Summary statistics.
        """
        sql = f"""
            SELECT
                DATE(timestamp) as date,
                colony,
                model_name,
                COUNT(*) as num_steps,
                AVG(loss) as avg_loss,
                MIN(loss) as min_loss,
                AVG(throughput_samples_sec) as avg_throughput
            FROM `{self.config.project_id}.{self.config.dataset_id}.training_metrics`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        """

        if model_name:
            sql += f" AND model_name = '{model_name}'"
        if colony:
            sql += f" AND colony = '{colony}'"

        sql += " GROUP BY date, colony, model_name ORDER BY date DESC"

        return await self.query(sql)

    async def get_api_usage_summary(
        self,
        days: int = 7,
    ) -> QueryResult:
        """Get API usage summary.

        Args:
            days: Number of days to include.

        Returns:
            Usage summary by endpoint.
        """
        sql = f"""
            SELECT
                endpoint,
                method,
                COUNT(*) as request_count,
                AVG(latency_ms) as avg_latency_ms,
                COUNTIF(status_code >= 400) as error_count,
                COUNTIF(status_code >= 400) / COUNT(*) * 100 as error_rate
            FROM `{self.config.project_id}.{self.config.dataset_id}.api_usage`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY endpoint, method
            ORDER BY request_count DESC
        """

        return await self.query(sql)

    async def get_colony_performance(
        self,
        days: int = 7,
    ) -> QueryResult:
        """Get colony performance metrics.

        Args:
            days: Number of days to include.

        Returns:
            Performance metrics by colony.
        """
        sql = f"""
            SELECT
                colony,
                event_type,
                COUNT(*) as event_count,
                AVG(duration_ms) as avg_duration_ms,
                COUNTIF(success = true) / COUNT(*) * 100 as success_rate
            FROM `{self.config.project_id}.{self.config.dataset_id}.colony_events`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY colony, event_type
            ORDER BY colony, event_count DESC
        """

        return await self.query(sql)

    async def get_cost_summary(
        self,
        days: int = 30,
    ) -> QueryResult:
        """Get cost summary by service.

        Args:
            days: Number of days to include.

        Returns:
            Cost summary by service.
        """
        sql = f"""
            SELECT
                service,
                resource_type,
                SUM(estimated_cost_usd) as total_cost_usd,
                SUM(usage_amount) as total_usage,
                usage_unit
            FROM `{self.config.project_id}.{self.config.dataset_id}.cost_tracking`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY service, resource_type, usage_unit
            ORDER BY total_cost_usd DESC
        """

        return await self.query(sql)


# Singleton instance
_bigquery_service: BigQueryService | None = None


def get_bigquery_service(config: BigQueryConfig | None = None) -> BigQueryService:
    """Get or create singleton BigQuery service.

    Args:
        config: Optional configuration.

    Returns:
        BigQueryService instance.
    """
    global _bigquery_service
    if _bigquery_service is None:
        _bigquery_service = BigQueryService(config)
    return _bigquery_service


async def initialize_bigquery(config: BigQueryConfig | None = None) -> BigQueryService:
    """Initialize and return BigQuery service.

    Args:
        config: Optional configuration.

    Returns:
        Initialized BigQueryService.
    """
    service = get_bigquery_service(config)
    await service.initialize()
    return service


__all__ = [
    "TABLE_SCHEMAS",
    "BigQueryConfig",
    "BigQueryService",
    "QueryResult",
    "get_bigquery_service",
    "initialize_bigquery",
]
