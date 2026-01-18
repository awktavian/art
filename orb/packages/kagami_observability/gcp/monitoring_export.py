"""Cloud Monitoring Metrics Exporter for Kagami.

Exports Prometheus metrics to Google Cloud Monitoring for unified
dashboarding, alerting, and long-term storage.

FEATURES:
=========
- Automatic Prometheus metric conversion
- Custom metric descriptors
- Batched metric writes
- Label propagation
- Integration with existing Prometheus registry

METRIC TYPES:
=============
- Gauge → GAUGE
- Counter → CUMULATIVE
- Histogram → DISTRIBUTION
- Summary → DISTRIBUTION (approximated)

USAGE:
======
    from kagami_observability.gcp.monitoring_export import setup_gcp_monitoring

    # Setup exporter
    await setup_gcp_monitoring()

    # Metrics automatically exported from prometheus_client

    # Or export specific metrics
    await export_metrics_to_gcp({
        "kagami_requests_total": 1000,
        "kagami_latency_seconds": 0.05,
    })

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports
_monitoring_v3 = None
_monitoring_available = False


def _lazy_import_monitoring() -> Any:
    """Lazy import google.cloud.monitoring_v3."""
    global _monitoring_v3, _monitoring_available
    if _monitoring_v3 is not None:
        return _monitoring_v3
    try:
        from google.cloud import monitoring_v3

        _monitoring_v3 = monitoring_v3
        _monitoring_available = True
        return monitoring_v3
    except ImportError as e:
        _monitoring_available = False
        raise ImportError(
            "google-cloud-monitoring not installed. "
            "Install with: pip install google-cloud-monitoring"
        ) from e


@dataclass
class MetricConfig:
    """Configuration for Cloud Monitoring export.

    Attributes:
        project_id: GCP project ID.
        metric_prefix: Prefix for custom metrics.
        export_interval_seconds: How often to export metrics.
        labels: Default labels for all metrics.
        resource_type: Monitored resource type.
        resource_labels: Labels for the monitored resource.
    """

    project_id: str | None = None
    metric_prefix: str = "custom.googleapis.com/kagami"
    export_interval_seconds: float = 60.0
    labels: dict[str, str] = field(default_factory=dict)
    resource_type: str = "global"
    resource_labels: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> MetricConfig:
        """Create config from environment."""
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID"),
            metric_prefix=os.getenv("MONITORING_METRIC_PREFIX", "custom.googleapis.com/kagami"),
            export_interval_seconds=float(os.getenv("MONITORING_EXPORT_INTERVAL", "60")),
            labels={
                "environment": os.getenv("KAGAMI_ENVIRONMENT", "dev"),
                "service": os.getenv("KAGAMI_SERVICE_NAME", "kagami"),
            },
        )


class CloudMonitoringExporter:
    """Exports metrics to Google Cloud Monitoring.

    Integrates with prometheus_client to automatically export
    registered metrics to Cloud Monitoring.

    Example:
        exporter = CloudMonitoringExporter()
        await exporter.initialize()

        # Start background export
        await exporter.start_periodic_export()

        # Or manual export
        await exporter.export()
    """

    # Batch size for time series writes
    MAX_TIME_SERIES_PER_REQUEST = 200

    def __init__(self, config: MetricConfig | None = None):
        """Initialize exporter.

        Args:
            config: Export configuration.
        """
        self.config = config or MetricConfig.from_env()
        self._client = None
        self._initialized = False
        self._export_task: asyncio.Task[None] | None = None
        self._running = False
        self._metric_descriptors: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize Cloud Monitoring client."""
        if self._initialized:
            return

        monitoring_v3 = _lazy_import_monitoring()

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

        self._client = monitoring_v3.MetricServiceClient()
        self._initialized = True

        logger.info(f"Cloud Monitoring initialized: project={self.config.project_id}")

    def _ensure_initialized(self) -> None:
        """Ensure client is initialized."""
        if not self._initialized:
            raise RuntimeError("CloudMonitoringExporter not initialized. Call initialize() first.")

    def _get_metric_type(self, name: str) -> str:
        """Get full metric type from short name."""
        return f"{self.config.metric_prefix}/{name}"

    def _create_time_series(
        self,
        metric_name: str,
        value: float | int,
        labels: dict[str, str] | None = None,
        value_type: str = "DOUBLE",
    ) -> Any:
        """Create a TimeSeries object.

        Args:
            metric_name: Short metric name.
            value: Metric value.
            labels: Metric labels.
            value_type: DOUBLE, INT64, or DISTRIBUTION.

        Returns:
            TimeSeries proto.
        """
        monitoring_v3 = _lazy_import_monitoring()

        series = monitoring_v3.TimeSeries()

        # Metric
        series.metric.type = self._get_metric_type(metric_name)
        if labels:
            for key, val in labels.items():
                series.metric.labels[key] = str(val)

        # Resource
        series.resource.type = self.config.resource_type
        for key, val in self.config.resource_labels.items():
            series.resource.labels[key] = str(val)

        # Add project_id for global resource
        if self.config.resource_type == "global":
            series.resource.labels["project_id"] = self.config.project_id or ""

        # Point
        now = time.time()
        seconds = int(now)
        nanos = int((now - seconds) * 10**9)

        point = monitoring_v3.Point()
        point.interval.end_time.seconds = seconds
        point.interval.end_time.nanos = nanos

        if value_type == "INT64":
            point.value.int64_value = int(value)
        else:
            point.value.double_value = float(value)

        series.points.append(point)

        return series

    async def export_metric(
        self,
        name: str,
        value: float | int,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Export a single metric value.

        Args:
            name: Metric name.
            value: Metric value.
            labels: Metric labels.
        """
        self._ensure_initialized()

        series = self._create_time_series(name, value, labels)

        project_name = f"projects/{self.config.project_id}"

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.create_time_series(
                name=project_name,
                time_series=[series],
            ),
        )

    async def export_metrics(
        self,
        metrics: dict[str, float | int | tuple[float | int, dict[str, str]]],
    ) -> None:
        """Export multiple metrics in batch.

        Args:
            metrics: Dict of metric_name -> value or (value, labels).

        Example:
            await exporter.export_metrics({
                "requests_total": 1000,
                "latency_p99": (0.5, {"endpoint": "/api/v1"}),
            })
        """
        self._ensure_initialized()

        time_series = []

        for name, data in metrics.items():
            if isinstance(data, tuple):
                value, labels = data
            else:
                value, labels = data, None

            series = self._create_time_series(name, value, labels)
            time_series.append(series)

        # Batch write (max 200 per request)
        project_name = f"projects/{self.config.project_id}"

        for i in range(0, len(time_series), self.MAX_TIME_SERIES_PER_REQUEST):
            batch = time_series[i : i + self.MAX_TIME_SERIES_PER_REQUEST]

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda b=batch: self._client.create_time_series(
                    name=project_name,
                    time_series=b,
                ),
            )

    async def export_prometheus_metrics(self) -> None:
        """Export all registered Prometheus metrics.

        Reads from prometheus_client registry and exports to Cloud Monitoring.
        """
        self._ensure_initialized()

        try:
            from prometheus_client import REGISTRY, CollectorRegistry
            from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily

            metrics_to_export: dict[str, tuple[float, dict[str, str]]] = {}

            for metric in REGISTRY.collect():
                for sample in metric.samples:
                    # Build metric name
                    name = sample.name.replace("_total", "")

                    # Build labels
                    labels = {k: str(v) for k, v in sample.labels.items()}
                    labels.update(self.config.labels)

                    # Use sample name as key to handle multiple label combinations
                    key = f"{name}_{hash(frozenset(labels.items()))}"
                    metrics_to_export[key] = (sample.value, labels)

            if metrics_to_export:
                await self.export_metrics(dict(metrics_to_export.items()))
                logger.debug(f"Exported {len(metrics_to_export)} metrics to Cloud Monitoring")

        except ImportError:
            logger.warning("prometheus_client not available for export")

    async def start_periodic_export(self) -> None:
        """Start background periodic export task."""
        if self._running:
            return

        self._running = True

        async def _export_loop() -> None:
            while self._running:
                try:
                    await self.export_prometheus_metrics()
                except Exception as e:
                    logger.error(f"Metric export error: {e}")

                await asyncio.sleep(self.config.export_interval_seconds)

        self._export_task = asyncio.create_task(_export_loop())
        logger.info(
            f"Started periodic metric export (interval={self.config.export_interval_seconds}s)"
        )

    async def stop_periodic_export(self) -> None:
        """Stop background export task."""
        self._running = False

        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass
            self._export_task = None

        logger.info("Stopped periodic metric export")

    async def create_metric_descriptor(
        self,
        name: str,
        display_name: str,
        description: str,
        metric_kind: str = "GAUGE",
        value_type: str = "DOUBLE",
        unit: str = "1",
        labels: list[dict[str, str]] | None = None,
    ) -> Any:
        """Create a custom metric descriptor.

        Args:
            name: Metric name.
            display_name: Human-readable name.
            description: Metric description.
            metric_kind: GAUGE, DELTA, or CUMULATIVE.
            value_type: BOOL, INT64, DOUBLE, STRING, or DISTRIBUTION.
            unit: Unit string (e.g., "1", "s", "By").
            labels: Label descriptors.

        Returns:
            Created MetricDescriptor.
        """
        self._ensure_initialized()
        monitoring_v3 = _lazy_import_monitoring()

        descriptor = monitoring_v3.MetricDescriptor(
            type=self._get_metric_type(name),
            display_name=display_name,
            description=description,
            metric_kind=getattr(monitoring_v3.MetricDescriptor.MetricKind, metric_kind),
            value_type=getattr(monitoring_v3.MetricDescriptor.ValueType, value_type),
            unit=unit,
        )

        if labels:
            for label in labels:
                descriptor.labels.append(
                    monitoring_v3.LabelDescriptor(
                        key=label["key"],
                        value_type=monitoring_v3.LabelDescriptor.ValueType.STRING,
                        description=label.get("description", ""),
                    )
                )

        project_name = f"projects/{self.config.project_id}"

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._client.create_metric_descriptor(
                name=project_name,
                metric_descriptor=descriptor,
            ),
        )

        self._metric_descriptors[name] = result
        logger.info(f"Created metric descriptor: {name}")

        return result


# Singleton instance
_monitoring_exporter: CloudMonitoringExporter | None = None


def get_monitoring_exporter(config: MetricConfig | None = None) -> CloudMonitoringExporter:
    """Get or create singleton monitoring exporter.

    Args:
        config: Optional configuration.

    Returns:
        CloudMonitoringExporter instance.
    """
    global _monitoring_exporter
    if _monitoring_exporter is None:
        _monitoring_exporter = CloudMonitoringExporter(config)
    return _monitoring_exporter


async def setup_gcp_monitoring(
    config: MetricConfig | None = None,
    start_export: bool = True,
) -> CloudMonitoringExporter:
    """Setup Cloud Monitoring export.

    Args:
        config: Export configuration.
        start_export: If True, start periodic export.

    Returns:
        Initialized exporter.

    Example:
        await setup_gcp_monitoring()
    """
    exporter = get_monitoring_exporter(config)
    await exporter.initialize()

    if start_export:
        await exporter.start_periodic_export()

    return exporter


async def export_metrics_to_gcp(
    metrics: dict[str, float | int],
    labels: dict[str, str] | None = None,
) -> None:
    """Convenience function to export metrics.

    Args:
        metrics: Metric name -> value dict.
        labels: Labels to apply to all metrics.

    Example:
        await export_metrics_to_gcp({
            "api_requests": 100,
            "error_count": 5,
        })
    """
    exporter = get_monitoring_exporter()
    if not exporter._initialized:
        await exporter.initialize()

    if labels:
        export_data = {name: (value, labels) for name, value in metrics.items()}
    else:
        export_data = metrics

    await exporter.export_metrics(export_data)


__all__ = [
    "CloudMonitoringExporter",
    "MetricConfig",
    "export_metrics_to_gcp",
    "get_monitoring_exporter",
    "setup_gcp_monitoring",
]
