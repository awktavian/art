"""K os Observability Package.

Provides monitoring and metrics collection using Prometheus.
"""

# Re-export single source of truth from metrics package to ensure all modules share
# the same REGISTRY and helper constructors.
from kagami_observability.metrics import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    get_current_metrics,
    get_prometheus_metrics,
)

# Keep init of the /metrics endpoint available
from .metrics_prometheus import init_metrics, metrics_middleware
from .performance import PerformanceTimer, monitor_performance
from .trace import is_tracing_enabled, trace_span, traced

__all__ = [
    "REGISTRY",
    "Counter",
    "Gauge",
    "Histogram",
    # Performance monitoring
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
