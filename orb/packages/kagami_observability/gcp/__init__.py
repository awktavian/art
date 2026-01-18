"""GCP Observability Stack Integration.

Provides unified observability via Google Cloud Operations Suite:
- Cloud Logging: Structured log ingestion
- Cloud Monitoring: Metrics and dashboards
- Cloud Trace: Distributed tracing

ARCHITECTURE:
=============
    ┌─────────────────────────────────────────────────────────────────┐
    │                   Kagami Application                             │
    │                                                                  │
    │   Existing Stack          │      GCP Operations Suite            │
    │   ─────────────           │      ────────────────────            │
    │   Prometheus metrics      │      Cloud Monitoring                │
    │   Python logging          │      Cloud Logging                   │
    │   OpenTelemetry spans     │      Cloud Trace                    │
    └─────────────────────────────────────────────────────────────────┘

USAGE:
======
    from kagami_observability.gcp import (
        setup_gcp_logging,
        setup_gcp_monitoring,
        setup_gcp_tracing,
        initialize_gcp_observability,
    )

    # Initialize all at once
    await initialize_gcp_observability()

    # Or individually
    setup_gcp_logging()
    await setup_gcp_monitoring()
    setup_gcp_tracing()

Created: January 4, 2026
"""

from kagami_observability.gcp.logging_handler import (
    CloudLoggingHandler,
    get_cloud_logger,
    setup_gcp_logging,
)
from kagami_observability.gcp.monitoring_export import (
    CloudMonitoringExporter,
    MetricConfig,
    export_metrics_to_gcp,
    setup_gcp_monitoring,
)
from kagami_observability.gcp.trace_exporter import (
    CloudTraceExporter,
    get_tracer,
    setup_gcp_tracing,
)
from kagami_observability.gcp.unified import (
    GCPObservabilityConfig,
    initialize_gcp_observability,
    shutdown_gcp_observability,
)

__all__ = [
    # Logging
    "CloudLoggingHandler",
    # Monitoring
    "CloudMonitoringExporter",
    # Tracing
    "CloudTraceExporter",
    # Unified
    "GCPObservabilityConfig",
    "MetricConfig",
    "export_metrics_to_gcp",
    "get_cloud_logger",
    "get_tracer",
    "initialize_gcp_observability",
    "setup_gcp_logging",
    "setup_gcp_monitoring",
    "setup_gcp_tracing",
    "shutdown_gcp_observability",
]
