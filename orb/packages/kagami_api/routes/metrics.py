"""Prometheus Metrics Export — Observable distributed system metrics.

This module provides Prometheus-compatible metrics endpoints:
- /metrics — Prometheus scrape endpoint
- /metrics/json — JSON format for dashboards
- Custom metrics registry

Metrics Categories:
```
    Category            Examples                        Labels
    ────────            ────────                        ──────
    Request             http_requests_total             method, path, status
    Latency             request_duration_seconds        method, path, quantile
    Consensus           pbft_operations_total           operation, result
    Recovery            byzantine_faults_total          node, fault_type
    Service             service_instances_active        service_type, health
```

Colony: Grove (D₄⁻) — Observation and documentation
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


# =============================================================================
# Metric Types
# =============================================================================


class MetricType(str, Enum):
    """Prometheus metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricDefinition:
    """Definition of a metric."""

    name: str
    type: MetricType
    help: str
    labels: list[str] = field(default_factory=list)


@dataclass
class MetricValue:
    """A single metric value with labels."""

    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float | None = None


# =============================================================================
# Metrics Registry
# =============================================================================


class MetricsRegistry:
    """Registry for Prometheus metrics.

    Features:
    - Counter, Gauge, Histogram support
    - Label handling
    - Prometheus text format export
    - JSON export for dashboards
    """

    def __init__(self) -> None:
        """Initialize the metrics registry."""
        self._definitions: dict[str, MetricDefinition] = {}
        self._counters: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._gauges: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

        # Define default metrics
        self._register_default_metrics()

    def _register_default_metrics(self) -> None:
        """Register default application metrics."""
        # HTTP metrics
        self.define(
            MetricDefinition(
                name="http_requests_total",
                type=MetricType.COUNTER,
                help="Total HTTP requests",
                labels=["method", "path", "status"],
            )
        )

        self.define(
            MetricDefinition(
                name="http_request_duration_seconds",
                type=MetricType.HISTOGRAM,
                help="HTTP request duration in seconds",
                labels=["method", "path"],
            )
        )

        # Consensus metrics
        self.define(
            MetricDefinition(
                name="pbft_operations_total",
                type=MetricType.COUNTER,
                help="Total PBFT operations",
                labels=["operation", "result"],
            )
        )

        self.define(
            MetricDefinition(
                name="pbft_view_number",
                type=MetricType.GAUGE,
                help="Current PBFT view number",
                labels=[],
            )
        )

        self.define(
            MetricDefinition(
                name="pbft_committed_operations",
                type=MetricType.COUNTER,
                help="Total committed PBFT operations",
                labels=[],
            )
        )

        # Recovery metrics
        self.define(
            MetricDefinition(
                name="byzantine_faults_total",
                type=MetricType.COUNTER,
                help="Total Byzantine faults detected",
                labels=["node", "fault_type", "severity"],
            )
        )

        self.define(
            MetricDefinition(
                name="node_isolations_total",
                type=MetricType.COUNTER,
                help="Total node isolations",
                labels=["node"],
            )
        )

        self.define(
            MetricDefinition(
                name="node_readmissions_total",
                type=MetricType.COUNTER,
                help="Total node readmissions",
                labels=["node"],
            )
        )

        self.define(
            MetricDefinition(
                name="isolated_nodes_current",
                type=MetricType.GAUGE,
                help="Currently isolated nodes",
                labels=[],
            )
        )

        # Service registry metrics
        self.define(
            MetricDefinition(
                name="service_instances_total",
                type=MetricType.GAUGE,
                help="Total service instances",
                labels=["service_type", "health"],
            )
        )

        # WebSocket metrics
        self.define(
            MetricDefinition(
                name="websocket_connections_active",
                type=MetricType.GAUGE,
                help="Active WebSocket connections",
                labels=[],
            )
        )

        self.define(
            MetricDefinition(
                name="websocket_messages_total",
                type=MetricType.COUNTER,
                help="Total WebSocket messages sent",
                labels=[],
            )
        )

        # Application metrics
        self.define(
            MetricDefinition(
                name="application_uptime_seconds",
                type=MetricType.GAUGE,
                help="Application uptime in seconds",
                labels=[],
            )
        )

        self.define(
            MetricDefinition(
                name="application_info",
                type=MetricType.GAUGE,
                help="Application information",
                labels=["version", "node_id"],
            )
        )

    def define(self, definition: MetricDefinition) -> None:
        """Define a new metric."""
        self._definitions[definition.name] = definition

    def _labels_key(self, labels: dict[str, str]) -> str:
        """Convert labels dict to a hashable key."""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))

    # Counter operations
    def inc(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter."""
        key = self._labels_key(labels or {})
        self._counters[name][key] += value

    # Gauge operations
    def set(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge value."""
        key = self._labels_key(labels or {})
        self._gauges[name][key] = value

    def inc_gauge(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a gauge."""
        key = self._labels_key(labels or {})
        self._gauges[name][key] += value

    def dec_gauge(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Decrement a gauge."""
        key = self._labels_key(labels or {})
        self._gauges[name][key] -= value

    # Histogram operations
    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Observe a histogram value."""
        key = self._labels_key(labels or {})
        self._histograms[name][key].append(value)

        # Keep only last 1000 observations per bucket
        if len(self._histograms[name][key]) > 1000:
            self._histograms[name][key] = self._histograms[name][key][-1000:]

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        for name, definition in self._definitions.items():
            # HELP line
            lines.append(f"# HELP {name} {definition.help}")
            # TYPE line
            lines.append(f"# TYPE {name} {definition.type.value}")

            if definition.type == MetricType.COUNTER:
                for labels_key, value in self._counters[name].items():
                    metric_line = f"{name}"
                    if labels_key:
                        metric_line += f"{{{labels_key}}}"
                    metric_line += f" {value}"
                    lines.append(metric_line)

            elif definition.type == MetricType.GAUGE:
                for labels_key, value in self._gauges[name].items():
                    metric_line = f"{name}"
                    if labels_key:
                        metric_line += f"{{{labels_key}}}"
                    metric_line += f" {value}"
                    lines.append(metric_line)

            elif definition.type == MetricType.HISTOGRAM:
                # Export histogram with buckets and sum/count
                buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

                for labels_key, values in self._histograms[name].items():
                    if not values:
                        continue

                    # Compute bucket counts
                    for bucket in buckets:
                        count = sum(1 for v in values if v <= bucket)
                        bucket_labels = (
                            f'{labels_key},le="{bucket}"' if labels_key else f'le="{bucket}"'
                        )
                        lines.append(f"{name}_bucket{{{bucket_labels}}} {count}")

                    # +Inf bucket
                    inf_labels = f'{labels_key},le="+Inf"' if labels_key else 'le="+Inf"'
                    lines.append(f"{name}_bucket{{{inf_labels}}} {len(values)}")

                    # Sum and count
                    sum_labels = f"{{{labels_key}}}" if labels_key else ""
                    lines.append(f"{name}_sum{sum_labels} {sum(values)}")
                    lines.append(f"{name}_count{sum_labels} {len(values)}")

            lines.append("")  # Empty line between metrics

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """Export metrics in JSON format."""
        result = {}

        for name, definition in self._definitions.items():
            metric_data = {
                "type": definition.type.value,
                "help": definition.help,
                "values": [],
            }

            if definition.type == MetricType.COUNTER:
                for labels_key, value in self._counters[name].items():
                    metric_data["values"].append(
                        {
                            "labels": labels_key,
                            "value": value,
                        }
                    )

            elif definition.type == MetricType.GAUGE:
                for labels_key, value in self._gauges[name].items():
                    metric_data["values"].append(
                        {
                            "labels": labels_key,
                            "value": value,
                        }
                    )

            elif definition.type == MetricType.HISTOGRAM:
                for labels_key, values in self._histograms[name].items():
                    if values:
                        metric_data["values"].append(
                            {
                                "labels": labels_key,
                                "count": len(values),
                                "sum": sum(values),
                                "avg": sum(values) / len(values),
                                "min": min(values),
                                "max": max(values),
                            }
                        )

            result[name] = metric_data

        return result


# =============================================================================
# Singleton
# =============================================================================


_registry: MetricsRegistry | None = None


def get_metrics_registry() -> MetricsRegistry:
    """Get or create the metrics registry singleton."""
    global _registry

    if _registry is None:
        _registry = MetricsRegistry()

    return _registry


# =============================================================================
# Middleware for HTTP metrics
# =============================================================================


async def record_request_metrics(
    request: Request,
    call_next,
) -> Response:
    """Middleware to record HTTP request metrics."""
    registry = get_metrics_registry()

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Record metrics
    labels = {
        "method": request.method,
        "path": request.url.path,
        "status": str(response.status_code),
    }

    registry.inc("http_requests_total", labels=labels)
    registry.observe(
        "http_request_duration_seconds",
        duration,
        labels={"method": request.method, "path": request.url.path},
    )

    return response


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """Prometheus scrape endpoint.

    Returns metrics in Prometheus text exposition format.
    """
    registry = get_metrics_registry()

    # Update application metrics
    try:
        from kagami_api.routes.health import get_health_manager

        health_manager = get_health_manager()
        registry.set("application_uptime_seconds", health_manager.uptime_seconds)
    except Exception:
        pass

    # Update WebSocket metrics
    try:
        import asyncio

        from kagami_api.routes.cluster_websocket import get_ws_manager

        ws_manager = asyncio.get_event_loop().run_until_complete(get_ws_manager())
        ws_metrics = ws_manager.get_metrics()
        registry.set("websocket_connections_active", ws_metrics["active_connections"])
        registry.set("websocket_messages_total", ws_metrics["total_messages_sent"])
    except Exception:
        pass

    return registry.to_prometheus()


@router.get("/json")
async def json_metrics() -> dict[str, Any]:
    """JSON format metrics for dashboards."""
    registry = get_metrics_registry()
    return registry.to_json()


# =============================================================================
# Convenience functions for recording metrics
# =============================================================================


def record_pbft_operation(operation: str, result: str) -> None:
    """Record a PBFT operation."""
    registry = get_metrics_registry()
    registry.inc("pbft_operations_total", labels={"operation": operation, "result": result})


def record_byzantine_fault(node: str, fault_type: str, severity: str) -> None:
    """Record a Byzantine fault detection."""
    registry = get_metrics_registry()
    registry.inc(
        "byzantine_faults_total",
        labels={"node": node, "fault_type": fault_type, "severity": severity},
    )


def record_node_isolation(node: str) -> None:
    """Record a node isolation."""
    registry = get_metrics_registry()
    registry.inc("node_isolations_total", labels={"node": node})
    registry.inc_gauge("isolated_nodes_current")


def record_node_readmission(node: str) -> None:
    """Record a node readmission."""
    registry = get_metrics_registry()
    registry.inc("node_readmissions_total", labels={"node": node})
    registry.dec_gauge("isolated_nodes_current")


def set_service_instances(service_type: str, health: str, count: int) -> None:
    """Set service instance count."""
    registry = get_metrics_registry()
    registry.set(
        "service_instances_total",
        count,
        labels={"service_type": service_type, "health": health},
    )


# =============================================================================
# 鏡
# What gets measured gets managed. h(x) ≥ 0. Always.
# =============================================================================
