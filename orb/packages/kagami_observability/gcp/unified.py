"""Unified GCP Observability Stack.

Provides a single entry point to initialize all GCP observability
components: Logging, Monitoring, and Tracing.

USAGE:
======
    from kagami_observability.gcp import initialize_gcp_observability

    # Initialize everything with defaults
    await initialize_gcp_observability()

    # Or with custom config
    config = GCPObservabilityConfig(
        project_id="my-project",
        service_name="kagami-api",
        environment="prod",
        enable_logging=True,
        enable_monitoring=True,
        enable_tracing=True,
        trace_sample_rate=0.1,
    )
    await initialize_gcp_observability(config)

Created: January 4, 2026
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from kagami_observability.gcp.logging_handler import (
    CloudLoggingHandler,
    setup_gcp_logging,
)
from kagami_observability.gcp.monitoring_export import (
    CloudMonitoringExporter,
    MetricConfig,
    setup_gcp_monitoring,
)
from kagami_observability.gcp.trace_exporter import (
    CloudTraceExporter,
    setup_gcp_tracing,
)

logger = logging.getLogger(__name__)


@dataclass
class GCPObservabilityConfig:
    """Configuration for unified GCP observability.

    Attributes:
        project_id: GCP project ID.
        service_name: Service name for identification.
        service_version: Service version.
        environment: Deployment environment.
        enable_logging: Enable Cloud Logging.
        enable_monitoring: Enable Cloud Monitoring.
        enable_tracing: Enable Cloud Trace.
        logging_level: Python logging level.
        monitoring_interval: Metric export interval (seconds).
        trace_sample_rate: Trace sampling rate (0.0-1.0).
        labels: Default labels for all telemetry.
    """

    project_id: str | None = None
    service_name: str = "kagami"
    service_version: str = "1.0.0"
    environment: str = "dev"
    enable_logging: bool = True
    enable_monitoring: bool = True
    enable_tracing: bool = True
    logging_level: int = logging.INFO
    monitoring_interval: float = 60.0
    trace_sample_rate: float = 1.0
    labels: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> GCPObservabilityConfig:
        """Create config from environment variables."""
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID"),
            service_name=os.getenv("KAGAMI_SERVICE_NAME", "kagami"),
            service_version=os.getenv("KAGAMI_SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("KAGAMI_ENVIRONMENT", "dev"),
            enable_logging=os.getenv("GCP_ENABLE_LOGGING", "true").lower() == "true",
            enable_monitoring=os.getenv("GCP_ENABLE_MONITORING", "true").lower() == "true",
            enable_tracing=os.getenv("GCP_ENABLE_TRACING", "true").lower() == "true",
            logging_level=getattr(
                logging, os.getenv("KAGAMI_LOG_LEVEL", "INFO").upper(), logging.INFO
            ),
            monitoring_interval=float(os.getenv("MONITORING_EXPORT_INTERVAL", "60")),
            trace_sample_rate=float(os.getenv("TRACE_SAMPLE_RATE", "1.0")),
        )


class GCPObservabilityStack:
    """Unified GCP observability stack manager.

    Manages the lifecycle of all observability components.
    """

    def __init__(self, config: GCPObservabilityConfig | None = None):
        """Initialize stack.

        Args:
            config: Stack configuration.
        """
        self.config = config or GCPObservabilityConfig.from_env()
        self._logging_handler: CloudLoggingHandler | None = None
        self._monitoring_exporter: CloudMonitoringExporter | None = None
        self._trace_exporter: CloudTraceExporter | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all enabled observability components."""
        if self._initialized:
            return

        base_labels = {
            "service": self.config.service_name,
            "version": self.config.service_version,
            "environment": self.config.environment,
            **self.config.labels,
        }

        # Setup Logging
        if self.config.enable_logging:
            try:
                self._logging_handler = setup_gcp_logging(
                    project_id=self.config.project_id,
                    log_name=self.config.service_name,
                    labels=base_labels,
                    level=self.config.logging_level,
                )
                logger.info("Cloud Logging enabled")
            except Exception as e:
                logger.warning(f"Cloud Logging setup failed: {e}")

        # Setup Monitoring
        if self.config.enable_monitoring:
            try:
                metric_config = MetricConfig(
                    project_id=self.config.project_id,
                    export_interval_seconds=self.config.monitoring_interval,
                    labels=base_labels,
                )
                self._monitoring_exporter = await setup_gcp_monitoring(
                    config=metric_config,
                    start_export=True,
                )
                logger.info("Cloud Monitoring enabled")
            except Exception as e:
                logger.warning(f"Cloud Monitoring setup failed: {e}")

        # Setup Tracing
        if self.config.enable_tracing:
            try:
                self._trace_exporter = setup_gcp_tracing(
                    project_id=self.config.project_id,
                    service_name=self.config.service_name,
                    sample_rate=self.config.trace_sample_rate,
                )
                logger.info("Cloud Trace enabled")
            except Exception as e:
                logger.warning(f"Cloud Trace setup failed: {e}")

        self._initialized = True
        logger.info(
            f"GCP Observability initialized: "
            f"logging={self.config.enable_logging}, "
            f"monitoring={self.config.enable_monitoring}, "
            f"tracing={self.config.enable_tracing}"
        )

    async def shutdown(self) -> None:
        """Shutdown all observability components."""
        if self._monitoring_exporter:
            await self._monitoring_exporter.stop_periodic_export()

        if self._trace_exporter:
            self._trace_exporter.shutdown()

        if self._logging_handler:
            self._logging_handler.close()

        self._initialized = False
        logger.info("GCP Observability shutdown complete")


# Singleton stack
_observability_stack: GCPObservabilityStack | None = None


async def initialize_gcp_observability(
    config: GCPObservabilityConfig | None = None,
) -> GCPObservabilityStack:
    """Initialize the unified GCP observability stack.

    Args:
        config: Stack configuration. If None, loads from environment.

    Returns:
        Initialized GCPObservabilityStack.

    Example:
        # Basic setup
        await initialize_gcp_observability()

        # Custom config
        config = GCPObservabilityConfig(
            service_name="kagami-api",
            trace_sample_rate=0.1,  # Sample 10%
        )
        await initialize_gcp_observability(config)
    """
    global _observability_stack

    if _observability_stack is None:
        _observability_stack = GCPObservabilityStack(config)

    await _observability_stack.initialize()
    return _observability_stack


async def shutdown_gcp_observability() -> None:
    """Shutdown the GCP observability stack."""
    global _observability_stack

    if _observability_stack:
        await _observability_stack.shutdown()
        _observability_stack = None


def get_observability_stack() -> GCPObservabilityStack | None:
    """Get the current observability stack.

    Returns:
        Stack if initialized, None otherwise.
    """
    return _observability_stack


__all__ = [
    "GCPObservabilityConfig",
    "GCPObservabilityStack",
    "get_observability_stack",
    "initialize_gcp_observability",
    "shutdown_gcp_observability",
]
