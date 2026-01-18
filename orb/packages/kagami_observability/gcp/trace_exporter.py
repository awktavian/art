"""Cloud Trace Exporter for Kagami.

Provides distributed tracing via Google Cloud Trace with OpenTelemetry
integration for end-to-end request visibility.

FEATURES:
=========
- OpenTelemetry SDK integration
- Automatic trace context propagation
- Span attributes for debugging
- Sampling configuration
- Batch span export

USAGE:
======
    from kagami_observability.gcp.trace_exporter import setup_gcp_tracing, get_tracer

    # Setup tracing
    setup_gcp_tracing()

    # Get tracer
    tracer = get_tracer("kagami-api")

    # Create spans
    with tracer.start_as_current_span("process_request") as span:
        span.set_attribute("colony", "forge")
        span.set_attribute("user_id", "123")
        # ... do work ...

Created: January 4, 2026
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports
_trace_available = False
_otel_trace = None


def _lazy_import_otel() -> tuple[Any, ...]:
    """Lazy import OpenTelemetry components."""
    global _trace_available, _otel_trace
    if _otel_trace is not None:
        return _otel_trace

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Try Cloud Trace exporter
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            _trace_available = True
        except ImportError:
            CloudTraceSpanExporter = None
            logger.warning(
                "opentelemetry-exporter-gcp-trace not installed. "
                "Install with: pip install opentelemetry-exporter-gcp-trace"
            )

        _otel_trace = (trace, TracerProvider, BatchSpanProcessor, Resource, CloudTraceSpanExporter)
        return _otel_trace

    except ImportError as e:
        raise ImportError(
            "opentelemetry-sdk not installed. "
            "Install with: pip install opentelemetry-sdk opentelemetry-exporter-gcp-trace"
        ) from e


class CloudTraceExporter:
    """Cloud Trace exporter with OpenTelemetry integration.

    Sets up the OpenTelemetry SDK to export spans to Cloud Trace.

    Example:
        exporter = CloudTraceExporter()
        exporter.setup()

        tracer = exporter.get_tracer("my-service")
        with tracer.start_as_current_span("operation"):
            # traced work
            pass
    """

    def __init__(
        self,
        project_id: str | None = None,
        service_name: str = "kagami",
        service_version: str = "1.0.0",
        sample_rate: float = 1.0,
    ):
        """Initialize trace exporter.

        Args:
            project_id: GCP project ID.
            service_name: Service name for traces.
            service_version: Service version.
            sample_rate: Trace sampling rate (0.0 to 1.0).
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.service_name = service_name
        self.service_version = service_version
        self.sample_rate = sample_rate
        self._provider = None
        self._initialized = False

    def setup(self) -> None:
        """Setup OpenTelemetry with Cloud Trace exporter.

        Configures the global tracer provider and span processor.
        """
        if self._initialized:
            return

        (
            trace,
            TracerProvider,
            BatchSpanProcessor,
            Resource,
            CloudTraceSpanExporter,
        ) = _lazy_import_otel()

        # Create resource
        resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.version": self.service_version,
                "deployment.environment": os.getenv("KAGAMI_ENVIRONMENT", "dev"),
            }
        )

        # Create sampler based on rate
        if self.sample_rate < 1.0:
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

            sampler = TraceIdRatioBased(self.sample_rate)
        else:
            from opentelemetry.sdk.trace.sampling import ALWAYS_ON

            sampler = ALWAYS_ON

        # Create provider
        self._provider = TracerProvider(resource=resource, sampler=sampler)

        # Add Cloud Trace exporter if available
        if CloudTraceSpanExporter:
            try:
                exporter = CloudTraceSpanExporter(project_id=self.project_id)
                processor = BatchSpanProcessor(exporter)
                self._provider.add_span_processor(processor)
                logger.info(f"Cloud Trace exporter configured (project={self.project_id})")
            except Exception as e:
                logger.warning(f"Failed to setup Cloud Trace exporter: {e}")

        # Set as global provider
        trace.set_tracer_provider(self._provider)

        self._initialized = True
        logger.info(f"Tracing setup complete (service={self.service_name})")

    def get_tracer(self, name: str | None = None) -> Any:
        """Get a tracer instance.

        Args:
            name: Tracer name (defaults to service name).

        Returns:
            OpenTelemetry Tracer.
        """
        if not self._initialized:
            self.setup()

        trace, *_ = _lazy_import_otel()
        return trace.get_tracer(name or self.service_name, self.service_version)

    def shutdown(self) -> None:
        """Shutdown tracer provider and flush pending spans."""
        if self._provider:
            self._provider.shutdown()
            self._initialized = False


# Singleton exporter
_trace_exporter: CloudTraceExporter | None = None


def setup_gcp_tracing(
    project_id: str | None = None,
    service_name: str = "kagami",
    sample_rate: float = 1.0,
) -> CloudTraceExporter:
    """Setup Cloud Trace integration.

    Args:
        project_id: GCP project ID.
        service_name: Service name for traces.
        sample_rate: Sampling rate (0.0-1.0).

    Returns:
        Configured CloudTraceExporter.

    Example:
        setup_gcp_tracing(sample_rate=0.1)  # Sample 10%
    """
    global _trace_exporter

    if _trace_exporter is None:
        _trace_exporter = CloudTraceExporter(
            project_id=project_id,
            service_name=service_name,
            sample_rate=sample_rate,
        )

    _trace_exporter.setup()
    return _trace_exporter


def get_tracer(name: str | None = None) -> Any:
    """Get a tracer for creating spans.

    Args:
        name: Tracer name.

    Returns:
        OpenTelemetry Tracer.

    Example:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my_operation"):
            # traced code
            pass
    """
    global _trace_exporter

    if _trace_exporter is None:
        _trace_exporter = CloudTraceExporter()
        _trace_exporter.setup()

    return _trace_exporter.get_tracer(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str | None = None,
):
    """Context manager for creating traced spans.

    Args:
        name: Span name.
        attributes: Span attributes.
        tracer_name: Tracer name.

    Yields:
        The created span.

    Example:
        with trace_span("process_colony_request", {"colony": "forge"}):
            # traced code
            pass
    """
    tracer = get_tracer(tracer_name)

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current span.

    Args:
        **attributes: Key-value attributes to add.

    Example:
        add_span_attributes(user_id="123", colony="spark")
    """
    trace, *_ = _lazy_import_otel()
    span = trace.get_current_span()

    if span:
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span.

    Args:
        exception: Exception to record.
    """
    trace, *_ = _lazy_import_otel()
    span = trace.get_current_span()

    if span:
        span.record_exception(exception)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


__all__ = [
    "CloudTraceExporter",
    "add_span_attributes",
    "get_tracer",
    "record_exception",
    "setup_gcp_tracing",
    "trace_span",
]
