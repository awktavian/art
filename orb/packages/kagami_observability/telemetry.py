"""
OpenTelemetry instrumentation for K os.

Provides comprehensive distributed tracing, metrics, and logging.
"""

import functools
import inspect
import logging
from contextlib import contextmanager
from typing import Any

from opentelemetry import baggage, metrics, trace
from opentelemetry.context import attach
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import set_meter_provider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Status, StatusCode

OPENTELEMETRY_AVAILABLE = True


logger = logging.getLogger(__name__)
# Optional telemetry exporters - silence import warnings at module load time
# These are optional dependencies; logging would spam on every startup
try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter

    JAEGER_AVAILABLE = True
except ImportError:
    JAEGER_AVAILABLE = False

try:
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

try:
    from opentelemetry.propagators.b3 import B3MultiFormat

    B3_AVAILABLE = True
except ImportError:
    B3_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FASTAPI_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    FASTAPI_INSTRUMENTATION_AVAILABLE = False

try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPX_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    HTTPX_INSTRUMENTATION_AVAILABLE = False

try:
    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    LOGGING_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    LOGGING_INSTRUMENTATION_AVAILABLE = False
try:
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    REDIS_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    REDIS_INSTRUMENTATION_AVAILABLE = False
    logger.debug("Redis instrumentation not available")
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLALCHEMY_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    SQLALCHEMY_INSTRUMENTATION_AVAILABLE = False
    logger.debug("SQLAlchemy instrumentation not available")


class TelemetryManager:
    """
    Manages OpenTelemetry instrumentation for K os.
    """

    def __init__(self) -> None:
        """Initialize telemetry manager."""
        if OPENTELEMETRY_AVAILABLE:
            self.tracer_provider: TracerProvider | None = None
            self.meter_provider: MeterProvider | None = None
            self.tracer: Any | None = None
            self.meter: Any | None = None
        else:
            self.tracer_provider = None
            self.meter_provider = None
            self.tracer = None
            self.meter = None
        self._initialized = False

    def initialize(
        self,
        service_name: str = "kagami",
        service_version: str = "0.1.0",
        otlp_endpoint: str | None = None,
        jaeger_endpoint: str | None = None,
        enable_console: bool = False,
        sampling_rate: float = 1.0,
    ) -> None:
        """
        Initialize OpenTelemetry with all instrumentations.

        Args:
            service_name: Name of the service
            service_version: Version of the service
            otlp_endpoint: OTLP collector endpoint
            jaeger_endpoint: Jaeger collector endpoint
            enable_console: Enable console exporters for debugging
            sampling_rate: Trace sampling rate (0.0 to 1.0)
        """
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry not available - telemetry disabled")
            self._initialized = True
            return
        if self._initialized:
            logger.warning("Telemetry already initialized")
            return
        from kagami.core.config import get_config

        resource = Resource.create(
            {
                SERVICE_NAME: service_name,
                SERVICE_VERSION: service_version,
                "service.environment": get_config("ENVIRONMENT", "development"),  # type: ignore[dict-item]
                "service.instance.id": get_config("INSTANCE_ID", "local"),  # type: ignore[dict-item]
            }
        )
        self._init_tracing(
            resource=resource,
            otlp_endpoint=otlp_endpoint or get_config("OTLP_ENDPOINT"),
            jaeger_endpoint=jaeger_endpoint or get_config("JAEGER_ENDPOINT"),
            enable_console=enable_console,
            sampling_rate=sampling_rate,
        )
        self._init_metrics(
            resource=resource,
            otlp_endpoint=otlp_endpoint or get_config("OTLP_ENDPOINT"),
            enable_console=enable_console,
        )
        if B3_AVAILABLE:
            set_global_textmap(B3MultiFormat())
        # B3 propagator is optional; silence missing dependency
        self._instrument_libraries()
        self.tracer = trace.get_tracer(
            instrumenting_module_name=__name__, tracer_provider=self.tracer_provider
        )
        self.meter = metrics.get_meter(name=__name__, meter_provider=self.meter_provider)
        self._initialized = True
        logger.info(f"Telemetry initialized for {service_name} v{service_version}")

    def _init_tracing(
        self,
        resource: Resource,
        otlp_endpoint: str | None,
        jaeger_endpoint: str | None,
        enable_console: bool,
        sampling_rate: float,
    ) -> None:
        """Initialize tracing with exporters."""
        self.tracer_provider = TracerProvider(
            resource=resource, sampler=TraceIdRatioBased(sampling_rate)
        )
        if enable_console:
            console_exporter = ConsoleSpanExporter()
            self.tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))
        if otlp_endpoint and OTLP_AVAILABLE:
            try:
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                self.tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OTLP trace exporter configured: {otlp_endpoint}")
            except Exception as e:
                logger.error(f"Failed to configure OTLP exporter: {e}")
        elif otlp_endpoint and (not OTLP_AVAILABLE):
            logger.warning("OTLP endpoint configured but OTLP exporter not available")
        if jaeger_endpoint and JAEGER_AVAILABLE:
            try:
                jaeger_exporter = JaegerExporter(
                    agent_host_name=jaeger_endpoint.split(":")[0],
                    agent_port=(
                        int(jaeger_endpoint.split(":")[1]) if ":" in jaeger_endpoint else 6831
                    ),
                )
                self.tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
                logger.info(f"Jaeger trace exporter configured: {jaeger_endpoint}")
            except Exception as e:
                logger.error(f"Failed to configure Jaeger exporter: {e}")
        elif jaeger_endpoint and (not JAEGER_AVAILABLE):
            logger.warning("Jaeger endpoint configured but Jaeger exporter not available")
        trace.set_tracer_provider(self.tracer_provider)

    def _init_metrics(
        self, resource: Resource, otlp_endpoint: str | None, enable_console: bool
    ) -> None:
        """Initialize metrics with exporters."""
        readers = []
        if enable_console:
            console_reader = PeriodicExportingMetricReader(
                ConsoleMetricExporter(), export_interval_millis=5000
            )
            readers.append(console_reader)
        if otlp_endpoint and OTLP_AVAILABLE:
            try:
                otlp_reader = PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
                    export_interval_millis=10000,
                )
                readers.append(otlp_reader)
                logger.info(f"OTLP metric exporter configured: {otlp_endpoint}")
            except Exception as e:
                logger.error(f"Failed to configure OTLP metric exporter: {e}")
        elif otlp_endpoint and (not OTLP_AVAILABLE):
            logger.warning("OTLP endpoint configured but OTLP metric exporter not available")
        prometheus_reader = PrometheusMetricReader()
        readers.append(prometheus_reader)  # type: ignore[arg-type]
        self.meter_provider = MeterProvider(resource=resource, metric_readers=readers)
        set_meter_provider(self.meter_provider)

    def _instrument_libraries(self) -> None:
        """Auto-instrument common libraries."""
        instrumented = []
        try:
            if FASTAPI_INSTRUMENTATION_AVAILABLE:
                FastAPIInstrumentor().instrument(
                    tracer_provider=self.tracer_provider, meter_provider=self.meter_provider
                )
                instrumented.append("FastAPI")
            if SQLALCHEMY_INSTRUMENTATION_AVAILABLE:
                SQLAlchemyInstrumentor().instrument(tracer_provider=self.tracer_provider)
                instrumented.append("SQLAlchemy")
            if REDIS_INSTRUMENTATION_AVAILABLE:
                RedisInstrumentor().instrument(tracer_provider=self.tracer_provider)
                instrumented.append("Redis")
            if HTTPX_INSTRUMENTATION_AVAILABLE:
                HTTPXClientInstrumentor().instrument(tracer_provider=self.tracer_provider)
                instrumented.append("HTTPX")
            if LOGGING_INSTRUMENTATION_AVAILABLE:
                LoggingInstrumentor().instrument(tracer_provider=self.tracer_provider)
                instrumented.append("Logging")
            if instrumented:
                logger.info(f"Auto-instrumentation completed: {', '.join(instrumented)}")
            else:
                logger.debug("No instrumentation libraries available (optional)")
        except Exception as e:
            logger.error(f"Failed to instrument libraries: {e}")

    def shutdown(self) -> None:
        """Shutdown telemetry and flush all data."""
        if not self._initialized:
            return
        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown()
            if self.meter_provider:
                self.meter_provider.shutdown()
            self._initialized = False
            logger.info("Telemetry shutdown complete")
        except Exception as e:
            logger.error(f"Error during telemetry shutdown: {e}")


_telemetry_manager_instance: TelemetryManager | None = None


def get_telemetry_manager() -> TelemetryManager:
    """Get the global telemetry manager singleton (lazy initialization)."""
    global _telemetry_manager_instance
    if _telemetry_manager_instance is None:
        _telemetry_manager_instance = TelemetryManager()
    return _telemetry_manager_instance


def get_tracer(name: str = __name__) -> Any:
    """Get a tracer instance."""
    if not OPENTELEMETRY_AVAILABLE:
        return None
    manager = get_telemetry_manager()
    if not manager._initialized:
        manager.initialize()
    return trace.get_tracer(name)


def get_meter(name: str = __name__) -> Any:
    """Get a meter instance."""
    if not OPENTELEMETRY_AVAILABLE:
        return None
    manager = get_telemetry_manager()
    if not manager._initialized:
        manager.initialize()
    return metrics.get_meter(name)


@contextmanager  # type: ignore[arg-type]
def traced_operation(name: str, kind: Any = None, attributes: dict[str, Any] | None = None) -> None:  # type: ignore[misc]
    """
    Context manager for tracing operations.

    Usage:
        with traced_operation("database.query", attributes={"query": "SELECT *"}):
            # Perform operation
            pass
    """
    if not OPENTELEMETRY_AVAILABLE:
        yield
        return
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind, attributes=attributes or {}) as span:
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """Add attributes to the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def set_span_status(code: StatusCode, description: str | None = None) -> None:
    """Set status of the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_status(Status(code, description or ""))


def record_exception(exception: Exception) -> None:
    """Record an exception in the current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


def set_baggage(key: str, value: str) -> None:
    """Set baggage for context propagation."""
    ctx = baggage.set_baggage(key, value)
    attach(ctx)


def get_baggage(key: str) -> str | None:
    """Get baggage value from context."""
    return baggage.get_baggage(key)  # type: ignore[return-value]


_request_counter = None
_request_duration = None
_active_connections = None


def track_operation(
    operation_name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Any:
    """Decorator to track an operation with tracing metadata.

    Works for sync and async callables. If telemetry is disabled, this becomes
    a no-op wrapper so tests can still rely on the decorator being callable.
    """

    attributes = dict(attributes or {})

    def decorator(func: Any) -> Any:
        if inspect.iscoroutinefunction(func):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with traced_operation(operation_name, attributes=attributes):
                    return await func(*args, **kwargs)

            return functools.wraps(func)(async_wrapper)

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with traced_operation(operation_name, attributes=attributes):
                return func(*args, **kwargs)

        return functools.wraps(func)(sync_wrapper)

    return decorator


def init_metrics() -> None:
    """Initialize common metrics."""
    global _request_counter, _request_duration, _active_connections
    meter = get_meter()
    _request_counter = meter.create_counter(
        name="kagami_requests_total", description="Total number of requests", unit="1"
    )
    _request_duration = meter.create_histogram(
        name="kagami_request_duration_seconds", description="Request duration in seconds", unit="s"
    )
    _active_connections = meter.create_up_down_counter(
        name="kagami_active_connections", description="Number of active connections", unit="1"
    )


def increment_request_counter(method: str, endpoint: str, status_code: int) -> None:
    """Increment request counter metric."""
    if _request_counter:
        _request_counter.add(
            1, attributes={"method": method, "endpoint": endpoint, "status_code": str(status_code)}
        )


def record_request_duration(duration: float, method: str, endpoint: str) -> None:
    """Record request duration metric."""
    if _request_duration:
        _request_duration.record(duration, attributes={"method": method, "endpoint": endpoint})


def update_active_connections(delta: int) -> None:
    """Update active connections metric."""
    if _active_connections:
        _active_connections.add(delta)
