"""UI Performance Metrics.

Prometheus metrics for frontend performance monitoring, caching, and user experience.

Created: December 22, 2025
"""

from __future__ import annotations

from .core import Counter, Gauge, Histogram

# --- Intelligence Brief Metrics ---

INTELLIGENCE_BRIEF_REQUESTS_TOTAL = Counter(
    "kagami_intelligence_brief_requests_total",
    "Total intelligence brief requests",
    labelnames=["cache_status"],  # "hit", "miss"
)

INTELLIGENCE_BRIEF_GENERATION_DURATION_SECONDS = Histogram(
    "kagami_intelligence_brief_generation_duration_seconds",
    "Intelligence brief generation time",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

INTELLIGENCE_BRIEF_CACHE_HIT_RATIO = Gauge(
    "kagami_intelligence_brief_cache_hit_ratio",
    "Cache hit ratio for intelligence briefs",
)

# --- WebSocket Connection Pool Metrics ---

WS_CONNECTION_POOL_SIZE = Gauge(
    "kagami_ws_connection_pool_size",
    "WebSocket connection pool size",
    labelnames=["namespace"],
)

WS_CONNECTION_POOL_REUSES_TOTAL = Counter(
    "kagami_ws_connection_pool_reuses_total",
    "WebSocket connection pool reuse count",
    labelnames=["namespace"],
)

# --- Database Query Metrics ---

DB_QUERY_EXECUTION_TIME_SECONDS = Histogram(
    "kagami_db_query_execution_time_seconds",
    "Database query execution time",
    labelnames=["query_type", "index_used"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

DB_INDEX_USAGE_TOTAL = Counter(
    "kagami_db_index_usage_total",
    "Database index usage count",
    labelnames=["table", "index_name"],
)

# --- React Component Metrics ---

REACT_COMPONENT_RENDER_DURATION_MS = Histogram(
    "kagami_react_component_render_duration_ms",
    "React component render duration in milliseconds",
    labelnames=["component_name", "render_type"],
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
)

REACT_MEMO_SKIPS_TOTAL = Counter(
    "kagami_react_memo_skips_total",
    "React.memo render skips count",
    labelnames=["component_name"],
)

REACT_USEMEMO_CACHE_HITS_TOTAL = Counter(
    "kagami_react_usememo_cache_hits_total",
    "React useMemo cache hit count",
    labelnames=["component_name", "memo_key"],
)

# --- WebSocket Backpressure Metrics ---

WS_BACKPRESSURE_QUEUE_DEPTH = Gauge(
    "kagami_ws_backpressure_queue_depth",
    "WebSocket message queue depth",
    labelnames=["connection_id"],
)

WS_BACKPRESSURE_FLOW_CONTROL_PAUSES_TOTAL = Counter(
    "kagami_ws_backpressure_flow_control_pauses_total",
    "WebSocket flow control pauses count",
    labelnames=["connection_id"],
)

WS_BACKPRESSURE_MESSAGES_DROPPED_TOTAL = Counter(
    "kagami_ws_backpressure_messages_dropped_total",
    "WebSocket messages dropped due to backpressure",
    labelnames=["connection_id", "drop_reason"],
)

# --- Virtual Scrolling Metrics ---

VIRTUAL_SCROLL_TOTAL_ITEMS = Gauge(
    "kagami_virtual_scroll_total_items",
    "Total items in virtual scroll list",
    labelnames=["list_type"],
)

VIRTUAL_SCROLL_ITEMS_RENDERED = Gauge(
    "kagami_virtual_scroll_items_rendered",
    "Items currently rendered in virtual scroll",
    labelnames=["list_type"],
)

VIRTUAL_SCROLL_SCROLL_EVENTS_TOTAL = Counter(
    "kagami_virtual_scroll_scroll_events_total",
    "Virtual scroll event count",
    labelnames=["list_type"],
)

__all__ = [
    "DB_INDEX_USAGE_TOTAL",
    # Database
    "DB_QUERY_EXECUTION_TIME_SECONDS",
    "INTELLIGENCE_BRIEF_CACHE_HIT_RATIO",
    "INTELLIGENCE_BRIEF_GENERATION_DURATION_SECONDS",
    # Intelligence Brief
    "INTELLIGENCE_BRIEF_REQUESTS_TOTAL",
    # React
    "REACT_COMPONENT_RENDER_DURATION_MS",
    "REACT_MEMO_SKIPS_TOTAL",
    "REACT_USEMEMO_CACHE_HITS_TOTAL",
    "VIRTUAL_SCROLL_ITEMS_RENDERED",
    "VIRTUAL_SCROLL_SCROLL_EVENTS_TOTAL",
    # Virtual Scroll
    "VIRTUAL_SCROLL_TOTAL_ITEMS",
    "WS_BACKPRESSURE_FLOW_CONTROL_PAUSES_TOTAL",
    "WS_BACKPRESSURE_MESSAGES_DROPPED_TOTAL",
    # Backpressure
    "WS_BACKPRESSURE_QUEUE_DEPTH",
    "WS_CONNECTION_POOL_REUSES_TOTAL",
    # WebSocket Pool
    "WS_CONNECTION_POOL_SIZE",
]
