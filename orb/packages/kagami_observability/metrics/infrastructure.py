"""Infrastructure Metrics - Database, Redis, and connection monitoring.

Centralized infrastructure metrics for observability.
"""

from .core import Counter, Gauge, Histogram

DB_POOL_SIZE = Gauge("kagami_db_pool_size", "Database connection pool size", ["database"])
DB_SLOW_QUERIES_TOTAL = Counter(
    "kagami_db_slow_queries_total", "Total slow queries (>100ms)", ["operation", "database"]
)
REDIS_POOL_SIZE = Gauge(
    "kagami_redis_pool_size", "Redis connection pool max connections", ["purpose"]
)
REDIS_POOL_CREATED = Gauge("kagami_redis_pool_created", "Redis connections created", ["purpose"])
REDIS_POOL_AVAILABLE = Gauge(
    "kagami_redis_pool_available", "Redis connections available", ["purpose"]
)
REDIS_POOL_IN_USE = Gauge("kagami_redis_pool_in_use", "Redis connections in use", ["purpose"])
REDIS_CONNECTION_ERRORS_TOTAL = Counter(
    "kagami_redis_connection_errors_total",
    "Total Redis connection errors",
    ["purpose", "error_type"],
)
ERRORS_TOTAL = Counter(
    "kagami_errors_total", "Total errors by component and type", ["component", "error_type"]
)
AR_SCENE_CACHE_HITS = Counter("kagami_ar_scene_cache_hits", "AR scene cache hits", ["scene_type"])
AR_SCENE_CACHE_MISSES = Counter(
    "kagami_ar_scene_cache_misses", "AR scene cache misses", ["scene_type"]
)

# Generic cache metrics used by caching modules
CACHE_HITS_TOTAL = Counter("kagami_cache_hits_total", "Cache hits by cache name", ["cache_name"])
CACHE_MISSES_TOTAL = Counter(
    "kagami_cache_misses_total", "Cache misses by cache name", ["cache_name"]
)
CACHE_EVICTIONS_TOTAL = Counter(
    "kagami_cache_evictions_total", "Cache evictions by cache name", ["cache_name"]
)
BACKGROUND_TASKS_RUNNING = Gauge(
    "kagami_background_tasks_running", "Currently running background tasks", ["task_type"]
)
TASK_DURATION = Histogram("kagami_task_duration_seconds", "Task execution duration", ["task_type"])
TASK_RETRIES = Counter("kagami_task_retries_total", "Task retry attempts", ["task_type", "reason"])
GENERATION_DURATION = Histogram(
    "kagami_generation_duration_seconds", "Generation operation duration", ["operation"]
)
TENANT_USAGE_EVENTS = Counter(
    "kagami_tenant_usage_events", "Tenant usage events", ["tenant_tier", "event_type"]
)


def update_db_pool_stats(database: str, stats: dict) -> None:
    """Update database pool statistics.

    Args:
        database: Database name
        stats: Stats dict with size, checked_out, overflow, waits
    """
    if "size" in stats:
        DB_POOL_SIZE.labels(database=database).set(stats["size"])


def update_redis_pool_stats(purpose: str, stats: dict) -> None:
    """Update Redis pool statistics.

    Args:
        purpose: Redis client purpose
        stats: Stats dict with max_connections, created_connections, etc
    """
    if "max_connections" in stats:
        REDIS_POOL_SIZE.labels(purpose=purpose).set(stats["max_connections"] or 0)
    if "created_connections" in stats:
        REDIS_POOL_CREATED.labels(purpose=purpose).set(len(stats["created_connections"]))
    if "available_connections" in stats:
        REDIS_POOL_AVAILABLE.labels(purpose=purpose).set(len(stats["available_connections"]))
    if "in_use_connections" in stats:
        REDIS_POOL_IN_USE.labels(purpose=purpose).set(len(stats["in_use_connections"]))


def record_error(component: str, error_type: str) -> None:
    """Record an error occurrence.

    Args:
        component: Component name
        error_type: Error type/exception name
    """
    ERRORS_TOTAL.labels(component=component, error_type=error_type).inc()


MODEL_LOADS_TOTAL = Counter("kagami_model_loads_total", "Model Loads Total", ["model"])
MODEL_LOAD_DURATION_SECONDS = Histogram(
    "kagami_model_load_duration_seconds", "Model Load Duration Seconds", ["model"]
)
REDIS_FALLBACK_TOTAL = Counter("kagami_redis_fallback_total", "Redis Fallback Total")
# Weaviate vector search metrics (Dec 2025)
WEAVIATE_SEARCH_DURATION_SECONDS = Histogram(
    "kagami_weaviate_search_duration_seconds",
    "Weaviate vector search duration",
    ["collection"],
)
WEAVIATE_SEARCH_RESULTS_COUNT = Counter(
    "kagami_weaviate_search_results_count",
    "Weaviate vector search results returned",
    ["collection"],
)
REDIS_COMMAND_ERRORS_TOTAL = Counter(
    "kagami_redis_command_errors_total",
    "Redis command execution errors",
    ["command", "error_type"],
)
REDIS_STAMPEDE_PREVENTED_TOTAL = Counter(
    "kagami_redis_stampede_prevented_total", "Cache stampede prevention triggers", ["key_prefix"]
)
CACHE_STAMPEDE_PREVENTED_TOTAL = Counter(
    "kagami_cache_stampede_prevented_total",
    "Times cache stampede was prevented by locking",
    ["cache_tier"],
)
DB_QUERY_ROWS_RETURNED = Histogram(
    "kagami_db_query_rows_returned", "Number of rows returned by query", ["operation"]
)
DB_CONNECTION_ACQUISITION_SECONDS = Histogram(
    "kagami_db_connection_acquisition_seconds",
    "Time to acquire database connection from pool",
    ["database"],
)

# Tool execution metrics
TOOL_EXECUTIONS_TOTAL = Counter(
    "kagami_tool_executions_total",
    "Total tool executions",
    ["tool_name", "status"],  # status: success/failure
)

TOOL_EXECUTION_DURATION_SECONDS = Histogram(
    "kagami_tool_execution_duration_seconds",
    "Tool execution duration",
    ["tool_name"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
)

TOOL_EXECUTION_ERRORS_TOTAL = Counter(
    "kagami_tool_execution_errors_total",
    "Tool execution errors",
    ["tool_name", "error_type"],
)

TOOL_SANDBOX_VIOLATIONS_TOTAL = Counter(
    "kagami_tool_sandbox_violations_total",
    "Sandbox violations detected during tool execution",
    ["tool_name", "violation_type"],
)

TOOL_RATE_LIMITED_TOTAL = Counter(
    "kagami_tool_rate_limited_total",
    "Tool executions blocked by rate limiting",
    ["tool_name"],
)

__all__ = [
    "AR_SCENE_CACHE_HITS",
    "AR_SCENE_CACHE_MISSES",
    "BACKGROUND_TASKS_RUNNING",
    "CACHE_EVICTIONS_TOTAL",
    "CACHE_HITS_TOTAL",
    "CACHE_MISSES_TOTAL",
    "CACHE_STAMPEDE_PREVENTED_TOTAL",
    "DB_CONNECTION_ACQUISITION_SECONDS",
    "DB_POOL_SIZE",
    "DB_QUERY_ROWS_RETURNED",
    "DB_SLOW_QUERIES_TOTAL",
    "ERRORS_TOTAL",
    "FALLBACK_TRIGGERED",
    "GENERATION_DURATION",
    "MEMORY_STORED_TOTAL",
    "MODEL_LOADS_TOTAL",
    "MODEL_LOAD_DURATION_SECONDS",
    "REDIS_COMMAND_ERRORS_TOTAL",
    "REDIS_CONNECTION_ERRORS_TOTAL",
    "REDIS_FALLBACK_TOTAL",
    "REDIS_POOL_AVAILABLE",
    "REDIS_POOL_CREATED",
    "REDIS_POOL_IN_USE",
    "REDIS_POOL_SIZE",
    "REDIS_STAMPEDE_PREVENTED_TOTAL",
    "TASK_DURATION",
    "TASK_RETRIES",
    "TENANT_USAGE_EVENTS",
    "TOOL_EXECUTIONS_TOTAL",
    "TOOL_EXECUTION_DURATION_SECONDS",
    "TOOL_EXECUTION_ERRORS_TOTAL",
    "TOOL_RATE_LIMITED_TOTAL",
    "TOOL_SANDBOX_VIOLATIONS_TOTAL",
    "WEAVIATE_SEARCH_DURATION_SECONDS",
    "WEAVIATE_SEARCH_RESULTS_COUNT",
]

FALLBACK_TRIGGERED = Counter(
    "kagami_fallback_triggered_total",
    "Fallback code paths triggered (should be 0 in Full Operation)",
    ["component", "reason", "severity"],
)

__all__.append("FALLBACK_TRIGGERED")

MEMORY_STORED_TOTAL = Counter(
    "kagami_memory_stored_total",
    "Memory Stored Total",
    ["memory_type"],
)

__all__.append("MEMORY_STORED_TOTAL")
