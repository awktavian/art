"""Kagami observability metrics module - re-exports from kagami_observability.metrics.

This module provides a compatibility shim so that tests and code can import
from either `kagami.observability.metrics` or `kagami_observability.metrics`.
"""

# Re-export everything from kagami_observability.metrics
from kagami_observability.metrics import *  # noqa: F403

# Re-export submodules (needed for `from kagami.observability.metrics import chaos`)
# Re-export special markers
from kagami_observability.metrics import (
    MISSING_METRICS_MODULES,
    api,
    chaos,
    colony,
    forge,
    hal,
    learning,
    receipts,
    safety,
)

# Re-export API metrics that are commonly needed
from kagami_observability.metrics.api import (
    API_ERRORS,
    INTENT_REQUESTS,
    INTENT_REQUESTS_BY_ACTION_APP,
    KAGAMI_HTTP_REQUEST_DURATION_SECONDS,
    KAGAMI_HTTP_REQUESTS_TOTAL,
    REQUEST_COUNT,
    REQUEST_DURATION,
    record_intent_metrics,
)

# Re-export core components
from kagami_observability.metrics.core import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Summary,
    counter,
    emit_counter,
    emit_gauge,
    emit_histogram,
    gauge,
    get_counter,
    get_current_metrics,
    get_histogram,
    get_prometheus_metrics,
    histogram,
    safe_emit,
    summary,
)

# Re-export forge metrics (includes GENUI_VALIDATE_FAILURES)
from kagami_observability.metrics.forge import GENUI_VALIDATE_FAILURES

# Explicitly re-export system metrics that are commonly used
from kagami_observability.metrics.system import (
    CHARACTER_GENERATIONS,
    DB_CONNECTION_POOL_SIZE,
    DB_QUERY_ERRORS,
    DB_QUERY_SECONDS,
    EXTERNAL_ERRORS_TOTAL,
    EXTERNAL_REQUEST_DURATION,
    GENUI_CACHE_HITS,
    GENUI_GENERATE_DURATION,
    GENUI_REQUESTS,
    REFLECTION_DURATION_SECONDS,
    REFLECTIONS_TOTAL,
    SYSTEM_CPU_PERCENT,
    SYSTEM_CPU_USAGE,
    SYSTEM_DISK_BYTES,
    SYSTEM_MEMORY_BYTES,
    SYSTEM_MEMORY_USAGE,
    record_learning_observation,
)
