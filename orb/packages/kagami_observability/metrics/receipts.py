"""K os Receipt generation and tracking metrics.

Domain-specific metrics for Receipt generation and tracking metrics.
"""

from kagami_observability.metrics.core import Counter, Gauge, Histogram

# Receipt write errors
RECEIPT_WRITE_ERRORS_TOTAL = Counter(
    "kagami_receipt_write_errors",
    "Total receipt write errors",
    ["error_type"],
)

# ==============================================================================
# TIER S SLO METRICS - Receipt System (20/20 rating)
# ==============================================================================

# Receipt endpoint latency tracking (SLO: p99 < 50ms)
RECEIPTS_ENDPOINT_DURATION_SECONDS = Histogram(
    "kagami_receipts_endpoint_duration_seconds",
    "Receipt endpoint request duration in seconds",
    ["endpoint", "method"],
)

# Receipt success/error rates
RECEIPTS_REQUESTS_TOTAL = Counter(
    "kagami_receipts_requests_total",
    "Total receipt API requests",
    ["endpoint", "method", "status"],
)

# Receipt storage success
RECEIPTS_STORED_TOTAL = Counter(
    "kagami_receipts_stored_total",
    "Total receipts successfully stored",
    ["storage_backend"],
)

# Receipt analytics metrics
RECEIPTS_ANALYTICS_QUERIES_TOTAL = Counter(
    "kagami_receipts_analytics_queries_total",
    "Total analytics queries on receipts",
    ["query_type"],
)

RECEIPTS_SLO_COMPLIANCE = Counter(
    "kagami_receipts_slo_compliance_total",
    "Receipt SLO compliance events",
    ["status"],
)

# Receipt sync metrics (cross-instance synchronization)
RECEIPT_SYNC_PUBLISHES_TOTAL = Counter(
    "kagami_receipt_sync_publishes_total",
    "Total receipts published to etcd for cross-instance sync",
    ["instance"],
)

RECEIPT_SYNC_RATE_LIMITED_TOTAL = Counter(
    "kagami_receipt_sync_rate_limited_total",
    "Receipt publishes blocked by rate limit",
    ["instance"],
)

RECEIPT_SYNC_WATCH_FAILURES_TOTAL = Counter(
    "kagami_receipt_sync_watch_failures_total",
    "Total watch loop failures requiring restart",
    ["instance"],
)

RECEIPT_SYNC_SUBSCRIBES_TOTAL = Counter(
    "kagami_receipt_sync_subscribes_total",
    "Total receipts received from other instances",
    ["instance", "source_instance"],
)

RECEIPT_SYNC_DURATION_SECONDS = Histogram(
    "kagami_receipt_sync_duration_seconds",
    "Time to publish receipt to etcd",
    ["instance"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

RECEIPT_SYNC_LAG_SECONDS = Histogram(
    "kagami_receipt_sync_lag_seconds",
    "End-to-end lag between publish and peer processing",
    ["from_instance", "to_instance"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

KAGAMI_RECEIPTS_TOTAL = Counter(
    "kagami_receipts_total",
    "Total receipts emitted",
    ["phase"],
)

RECEIPTS_LZC_SCORE = Counter(
    "kagami_receipts_lzc_score",
    "Lempel-Ziv Complexity score of receipt stream",
)

# Completeness Validator Metrics
RECEIPT_COMPLETENESS_SCORE = Gauge(
    "kagami_receipt_completeness_score",
    "Percentage of operations with complete PLAN/EXECUTE/VERIFY cycle",
)

RECEIPT_MISSING_PHASE_TOTAL = Counter(
    "kagami_receipt_missing_phase_total",
    "Total missing phases detected in receipt streams",
    ["phase"],
)

__all__ = [
    "KAGAMI_RECEIPTS_TOTAL",
    "RECEIPTS_ANALYTICS_QUERIES_TOTAL",
    "RECEIPTS_ENDPOINT_DURATION_SECONDS",
    "RECEIPTS_LZC_SCORE",
    "RECEIPTS_REQUESTS_TOTAL",
    "RECEIPTS_SLO_COMPLIANCE",
    "RECEIPTS_STORED_TOTAL",
    "RECEIPT_COMPLETENESS_SCORE",
    "RECEIPT_MISSING_PHASE_TOTAL",
    "RECEIPT_SYNC_DURATION_SECONDS",
    "RECEIPT_SYNC_LAG_SECONDS",
    "RECEIPT_SYNC_PUBLISHES_TOTAL",
    "RECEIPT_SYNC_RATE_LIMITED_TOTAL",
    "RECEIPT_SYNC_SUBSCRIBES_TOTAL",
    "RECEIPT_SYNC_WATCH_FAILURES_TOTAL",
    "RECEIPT_WRITE_ERRORS_TOTAL",
]
