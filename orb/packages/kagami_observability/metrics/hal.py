"""HAL Metrics.

Prometheus metrics for Hardware Abstraction Layer.
"""

from .core import Counter, Gauge, Histogram

__all__ = [
    "HAL_ADAPTER_STATUS",
    "HAL_BATTERY_LEVEL",
    "HAL_ERRORS",
    "HAL_INIT_SUCCESS",
    "HAL_LATENCY",
    "HAL_OPERATIONS",
    "HAL_POWER_WATTS",
]


# Operation counters
HAL_OPERATIONS = Counter(
    "kagami_hal_operations_total",
    "Total HAL operations",
    ["platform", "adapter", "operation", "status"],
)

# Latency histogram
HAL_LATENCY = Histogram(
    "kagami_hal_operation_duration_seconds",
    "HAL operation latency",
    ["platform", "adapter", "operation"],
    buckets=[0.0001, 0.001, 0.005, 0.01, 0.05, 0.1],
)

# Error counters
HAL_ERRORS = Counter("kagami_hal_errors_total", "HAL errors", ["platform", "adapter", "error_type"])

# Adapter availability
HAL_ADAPTER_STATUS = Gauge(
    "kagami_hal_adapter_available",
    "Adapter availability (1=available, 0=unavailable)",
    ["platform", "adapter_type"],
)

# Initialization success tracking
HAL_INIT_SUCCESS = Gauge(
    "kagami_hal_init_success",
    "HAL adapter initialization success (1=success, 0=failed)",
    ["platform", "adapter"],
)

# Resource usage
HAL_POWER_WATTS = Gauge("kagami_hal_power_watts", "Current power consumption in Watts", ["source"])

HAL_BATTERY_LEVEL = Gauge(
    "kagami_hal_battery_level",
    "Battery level percent (0-100)",
    ["source"],
)
