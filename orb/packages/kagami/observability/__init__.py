"""Kagami observability module - re-exports from kagami_observability.

This module provides a compatibility shim so that tests and code can import
from either `kagami.observability` or `kagami_observability`.
"""

# Re-export everything from kagami_observability
from kagami_observability import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    PerformanceTimer,
    get_current_metrics,
    get_prometheus_metrics,
    init_metrics,
    is_tracing_enabled,
    metrics_middleware,
    monitor_performance,
    trace_span,
    traced,
)

__all__ = [
    "REGISTRY",
    "Counter",
    "Gauge",
    "Histogram",
    "PerformanceTimer",
    "get_current_metrics",
    "get_prometheus_metrics",
    "init_metrics",
    "is_tracing_enabled",
    "metrics_middleware",
    "monitor_performance",
    "trace_span",
    "traced",
]
