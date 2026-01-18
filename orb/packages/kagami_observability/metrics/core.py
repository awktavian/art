"""K os Metrics Core Infrastructure.

Base registry and helper functions for all metrics.
Enhanced Oct 29, 2025: Added safe metric emission decorator.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from prometheus_client import REGISTRY, CollectorRegistry
from prometheus_client import Counter as _PromCounter
from prometheus_client import Gauge as _PromGauge
from prometheus_client import Histogram as _PromHistogram
from prometheus_client import Summary as _PromSummary

logger = logging.getLogger(__name__)

# Meta-monitoring: Track metric emission failures
METRIC_EMISSION_FAILURES_TOTAL = None  # Initialized after REGISTRY

# Device hint
ACCEL_DEVICE: str = "cpu"

# Create custom registry
REGISTRY: CollectorRegistry  # type: ignore  # Redef
try:
    _ = REGISTRY  # Check if already defined
except Exception:
    REGISTRY = CollectorRegistry()

# Initialize meta-monitoring metric after REGISTRY
try:
    METRIC_EMISSION_FAILURES_TOTAL = _PromCounter(
        "kagami_metric_emission_failures_total",
        "Failed metric emissions (prevents crashes)",
        ["metric_name", "error_type"],
        registry=REGISTRY,
    )
except Exception:
    METRIC_EMISSION_FAILURES_TOTAL = None


def Counter(
    name: str,
    documentation: str,
    labelnames: tuple[str, ...] | list[str] = (),
    *,
    registry: CollectorRegistry | None = None,
    **kwargs: Any,
) -> _PromCounter:
    """Create or get existing counter."""
    reg = registry or REGISTRY
    try:
        # Prometheus counters add _total suffix internally, check both
        for lookup_name in (name, f"{name}_total", f"{name}_created", name.removesuffix("_total")):
            existing = reg._names_to_collectors.get(lookup_name)
            if existing and isinstance(existing, _PromCounter):
                return existing
    except Exception:
        pass
    try:
        return _PromCounter(name, documentation, labelnames, registry=reg)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            existing = reg._names_to_collectors.get(name) or reg._names_to_collectors.get(
                f"{name}_total"
            )
            if existing:
                return cast(_PromCounter, existing)
        raise


def Gauge(
    name: str,
    documentation: str,
    labelnames: tuple[str, ...] | list[str] = (),
    *,
    registry: CollectorRegistry | None = None,
    **kwargs: Any,
) -> _PromGauge:
    """Create or get existing gauge."""
    reg = registry or REGISTRY
    try:
        existing = reg._names_to_collectors.get(name)
        if existing and isinstance(existing, _PromGauge):
            return existing
    except Exception:
        pass
    return _PromGauge(name, documentation, labelnames, registry=reg)


def Histogram(
    name: str,
    documentation: str,
    labelnames: tuple[str, ...] | list[str] = (),
    *,
    registry: CollectorRegistry | None = None,
    buckets: tuple[float, ...] | list[float] | None = None,
    **kwargs: Any,
) -> _PromHistogram:
    """Create or get existing histogram."""
    reg = registry or REGISTRY
    try:
        # Histogram creates _bucket, _count, _sum, _created suffixes - check all variants
        for lookup_name in (
            name,
            f"{name}_created",
            f"{name}_bucket",
            f"{name}_sum",
            f"{name}_count",
        ):
            existing = reg._names_to_collectors.get(lookup_name)
            if existing and isinstance(existing, _PromHistogram):
                return existing
    except Exception:
        pass
    # Try to create, fall back to returning existing if duplicate error
    try:
        if buckets:
            return _PromHistogram(name, documentation, labelnames, registry=reg, buckets=buckets)
        return _PromHistogram(name, documentation, labelnames, registry=reg)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            # Metric already exists, try to find and return it
            existing = reg._names_to_collectors.get(name) or reg._names_to_collectors.get(
                f"{name}_created"
            )
            if existing:
                return cast(_PromHistogram, existing)
        raise


def Summary(
    name: str,
    documentation: str,
    labelnames: tuple[str, ...] | list[str] = (),
    *,
    registry: CollectorRegistry | None = None,
    **kwargs: Any,
) -> _PromSummary:
    """Create or get existing summary."""
    reg = registry or REGISTRY
    try:
        existing = reg._names_to_collectors.get(name)
        if existing and isinstance(existing, _PromSummary):
            return existing
    except Exception:
        pass
    return _PromSummary(name, documentation, labelnames, registry=reg)


def _counter(name: str, documentation: str, labelnames: list[str] | None = None) -> _PromCounter:
    return Counter(name, documentation, labelnames or [], registry=REGISTRY)


def _gauge(name: str, documentation: str, labelnames: list[str] | None = None) -> _PromGauge:
    return Gauge(name, documentation, labelnames or [], registry=REGISTRY)


def _histogram(
    name: str, documentation: str, labelnames: list[str] | None = None
) -> _PromHistogram:
    return Histogram(name, documentation, labelnames or [], registry=REGISTRY)


_hist = _histogram  # Alias


def emit_counter(name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
    """Emit counter metric."""
    try:
        metric = _counter(name, f"Counter {name}", list(labels.keys()) if labels else [])
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)
    except Exception as e:
        logger.debug(f"Failed to emit counter {name}: {e}")


def emit_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Emit gauge metric."""
    try:
        metric = _gauge(name, f"Gauge {name}", list(labels.keys()) if labels else [])
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)
    except Exception as e:
        logger.debug(f"Failed to emit gauge {name}: {e}")


def emit_histogram(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Emit histogram observation."""
    try:
        metric = _histogram(name, f"Histogram {name}", list(labels.keys()) if labels else [])
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)
    except Exception as e:
        logger.debug(f"Failed to emit histogram {name}: {e}")


def get_counter(
    name: str, documentation: str = "", labelnames: list[str] | None = None
) -> _PromCounter:
    """Get or create counter."""
    return _counter(name, documentation or f"Counter {name}", labelnames)


def get_histogram(
    name: str, documentation: str = "", labelnames: list[str] | None = None
) -> _PromHistogram:
    """Get or create histogram."""
    return _histogram(name, documentation or f"Histogram {name}", labelnames)


def get_current_metrics() -> dict[str, Any]:
    """Get current metric values."""
    return {"registry": REGISTRY, "metrics": len(REGISTRY._names_to_collectors)}


def get_prometheus_metrics() -> str:
    """Get Prometheus-formatted metrics."""
    from prometheus_client import generate_latest

    payload: bytes = generate_latest(REGISTRY)
    # prometheus_client.generate_latest() returns bytes
    result: str = payload.decode("utf-8")
    return result


KAGAMI_OPERATIONS_TOTAL = Counter(
    "kagami_operations_total",
    "Total K os operations processed",
    ["operation"],
)


def counter(
    name: str, documentation: str, labelnames: list[str] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a counter metric and increment on function call.

    Args:
        name: Metric name (will be prefixed with kagami_)
        documentation: Metric description
        labelnames: Optional list of label names

    Returns:
        Decorator function
    """
    from collections.abc import Callable
    from functools import wraps

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Create counter with kagami_ prefix
        full_name = f"kagami_{name}" if not name.startswith("kagami_") else name
        metric = _counter(full_name, documentation, labelnames)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Extract labels from kwargs if labelnames specified
                if labelnames:
                    label_values = {k: kwargs.get(k, "unknown") for k in labelnames}
                    metric.labels(**label_values).inc()
                else:
                    metric.inc()
            except Exception as e:
                logger.debug(f"Failed to increment counter {full_name}: {e}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def gauge(
    name: str, documentation: str, labelnames: list[str] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a gauge metric and set value from function return.

    Args:
        name: Metric name (will be prefixed with kagami_)
        documentation: Metric description
        labelnames: Optional list of label names

    Returns:
        Decorator function
    """
    from collections.abc import Callable
    from functools import wraps

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Create gauge with kagami_ prefix
        full_name = f"kagami_{name}" if not name.startswith("kagami_") else name
        metric = _gauge(full_name, documentation, labelnames)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            try:
                if labelnames:
                    label_values = {k: kwargs.get(k, "unknown") for k in labelnames}
                    metric.labels(**label_values).set(float(result))
                else:
                    metric.set(float(result))
            except Exception as e:
                logger.debug(f"Failed to set gauge {full_name}: {e}")

            return result

        return wrapper

    return decorator


def histogram(
    name: str,
    documentation: str,
    labelnames: list[str] | None = None,
    buckets: tuple[float, ...] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a histogram metric and observe function duration.

    Args:
        name: Metric name (will be prefixed with kagami_)
        documentation: Metric description
        labelnames: Optional list of label names
        buckets: Optional histogram buckets

    Returns:
        Decorator function
    """
    import time
    from collections.abc import Callable
    from functools import wraps

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Create histogram with kagami_ prefix
        full_name = f"kagami_{name}" if not name.startswith("kagami_") else name
        metric = _histogram(full_name, documentation, labelnames)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                try:
                    if labelnames:
                        label_values = {k: kwargs.get(k, "unknown") for k in labelnames}
                        metric.labels(**label_values).observe(duration)
                    else:
                        metric.observe(duration)
                except Exception as e:
                    logger.debug(f"Failed to observe histogram {full_name}: {e}")

                return result
            except Exception:
                duration = time.time() - start_time
                try:
                    if labelnames:
                        label_values = {k: kwargs.get(k, "error") for k in labelnames}
                        metric.labels(**label_values).observe(duration)
                    else:
                        metric.observe(duration)
                except Exception:
                    pass
                raise

        return wrapper

    return decorator


def summary(
    name: str, documentation: str, labelnames: list[str] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a summary metric (uses histogram internally).

    Args:
        name: Metric name (will be prefixed with kagami_)
        documentation: Metric description
        labelnames: Optional list of label names

    Returns:
        Decorator function
    """
    # Summary is like histogram, observe the return value
    from collections.abc import Callable
    from functools import wraps

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Create histogram with kagami_ prefix (summary uses histogram backend)
        full_name = f"kagami_{name}" if not name.startswith("kagami_") else name
        metric = _histogram(full_name, documentation, labelnames)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            try:
                if labelnames:
                    label_values = {k: kwargs.get(k, "unknown") for k in labelnames}
                    metric.labels(**label_values).observe(float(result))
                else:
                    metric.observe(float(result))
            except Exception as e:
                logger.debug(f"Failed to observe summary {full_name}: {e}")

            return result

        return wrapper

    return decorator


def safe_emit(func_or_callable: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Safe metric emission - never crashes on metric errors.

    Can be used as a decorator OR as a direct call wrapper:

    Usage as decorator:
        @safe_emit
        def emit_request_metric():
            REQUEST_COUNT.labels(endpoint="/api/test").inc()

    Usage as direct call (preferred for inline metric updates):
        safe_emit(GAUGE.labels(name="x").set, 1.0)
        safe_emit(COUNTER.labels(name="y").inc)
    """
    # If called with args, it's being used as a direct wrapper
    if args or kwargs:
        try:
            return func_or_callable(*args, **kwargs)
        except Exception as e:
            try:
                if METRIC_EMISSION_FAILURES_TOTAL:
                    metric_name = getattr(func_or_callable, "__name__", "unknown")
                    error_type = type(e).__name__
                    METRIC_EMISSION_FAILURES_TOTAL.labels(
                        metric_name=metric_name, error_type=error_type
                    ).inc()
            except Exception:
                pass
            logger.debug(f"Metric emission failed: {e}")
            return None

    # If called without args, it's being used as a decorator
    @wraps(func_or_callable)
    def wrapper(*w_args: Any, **w_kwargs: Any) -> Any:
        try:
            return func_or_callable(*w_args, **w_kwargs)
        except Exception as e:
            try:
                if METRIC_EMISSION_FAILURES_TOTAL:
                    metric_name = (
                        func_or_callable.__name__
                        if hasattr(func_or_callable, "__name__")
                        else "unknown"
                    )
                    error_type = type(e).__name__
                    METRIC_EMISSION_FAILURES_TOTAL.labels(
                        metric_name=metric_name, error_type=error_type
                    ).inc()
            except Exception:
                pass
            logger.debug(f"Metric emission failed in {func_or_callable.__name__}: {e}")
            return None

    return wrapper


__all__ = [
    "ACCEL_DEVICE",
    "KAGAMI_OPERATIONS_TOTAL",
    "METRIC_EMISSION_FAILURES_TOTAL",
    "REGISTRY",
    "Counter",
    "Gauge",
    "Histogram",
    "counter",
    "emit_counter",
    "emit_gauge",
    "emit_histogram",
    "gauge",
    "get_counter",
    "get_current_metrics",
    "get_histogram",
    "get_prometheus_metrics",
    "histogram",
    "safe_emit",
    "summary",
]
