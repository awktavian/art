"""Monitoring System Integration.

Central integration point for all monitoring components:
- Unified monitoring initialization
- Cross-component integration
- Centralized metrics collection
- Coordinated alerting
- System-wide observability

Provides single entry point for production monitoring setup.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .anomaly_detector import get_anomaly_detector
from .health_checks import get_health_manager
from .profiler import get_profiler, mark_critical
from .sla_monitor import SLAMonitor
from .tracer import get_tracer, trace_operation

logger = logging.getLogger(__name__)


class MonitoringIntegration:
    """Unified monitoring system integration.

    Coordinates all monitoring components:
    - Performance profiling
    - SLA monitoring
    - Health checks
    - Distributed tracing
    - Anomaly detection
    """

    def __init__(self, service_name: str = "kagami"):
        self.service_name = service_name

        # Initialize all monitoring components
        self.profiler = get_profiler()
        self.sla_monitor = SLAMonitor()
        self.health_manager = get_health_manager()
        self.tracer = get_tracer(service_name)
        self.anomaly_detector = get_anomaly_detector()

        # Integration state
        self._running = False
        self._integration_task: asyncio.Task | None = None

        # Cross-component callbacks setup
        self._setup_integrations()

    def _setup_integrations(self) -> None:
        """Setup cross-component integrations."""
        # Mark critical smart home operations for profiling
        critical_operations = [
            "scene_activation",
            "device_control",
            "presence_detection",
            "security_check",
            "integration_health",
            "api_request",
            "websocket_message",
        ]

        for operation in critical_operations:
            mark_critical(operation)

        # Setup SLA alert callbacks
        self.sla_monitor.on_alert(channel="log", callback=self._handle_sla_alert)

        # Setup health check remediation
        self.health_manager.on_unhealthy("memory_usage", self._handle_memory_pressure)

        self.health_manager.on_unhealthy("cpu_usage", self._handle_cpu_pressure)

        # Setup anomaly detection callbacks
        self.anomaly_detector.on_anomaly(self._handle_anomaly)

        # Configure anomaly detection for key metrics
        self.anomaly_detector.configure_metric(
            "scene_activation_time",
            threshold_factor=2.0,  # Stricter threshold
            min_data_points=20,
        )

        self.anomaly_detector.configure_metric(
            "api_response_time", threshold_factor=3.0, min_data_points=30
        )

    async def start(self) -> None:
        """Start the integrated monitoring system."""
        if self._running:
            return

        self._running = True

        # Start all monitoring components
        with trace_operation("monitoring_startup"):
            logger.info("🚀 Starting integrated monitoring system...")

            # Start profiler
            self.profiler.start()

            # Start SLA monitoring
            await self.sla_monitor.start()

            # Start health checks
            await self.health_manager.start()

            # Start anomaly detection
            await self.anomaly_detector.start()

            # Start integration coordination task
            self._integration_task = asyncio.create_task(self._integration_loop())

        logger.info(f"📊 Integrated monitoring system started for {self.service_name}")

    async def stop(self) -> None:
        """Stop the integrated monitoring system."""
        if not self._running:
            return

        self._running = False

        logger.info("🛑 Stopping integrated monitoring system...")

        # Stop coordination task
        if self._integration_task:
            self._integration_task.cancel()
            try:
                await self._integration_task
            except asyncio.CancelledError:
                pass

        # Stop all components
        await self.anomaly_detector.stop()
        await self.health_manager.stop()
        await self.sla_monitor.stop()
        self.profiler.stop()

        logger.info("📊 Integrated monitoring system stopped")

    async def _integration_loop(self) -> None:
        """Main integration coordination loop."""
        while self._running:
            try:
                # Collect metrics from all components
                await self._collect_cross_component_metrics()

                # Update SLA measurements
                await self._update_sla_measurements()

                # Feed metrics to anomaly detector
                await self._feed_anomaly_detector()

                # Cleanup old data
                await self._cleanup_old_data()

                await asyncio.sleep(30)  # Run every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Integration loop error: {e}")
                await asyncio.sleep(10)

    async def _collect_cross_component_metrics(self) -> None:
        """Collect metrics from all monitoring components."""
        # Get profiler metrics
        profiler_summary = self.profiler.get_performance_summary()

        # Get health check results
        health_summary = self.health_manager.get_health_summary()

        # Get SLA status
        sla_summary = self.sla_monitor.get_sla_summary()

        # Log comprehensive status (could be exported to external monitoring)
        logger.debug(
            f"Monitoring status - "
            f"Health: {health_summary['health_score']:.1f}, "
            f"SLA Compliance: {sla_summary['overall_compliance_percent']:.1f}%, "
            f"CPU: {profiler_summary['cpu']['current_percent']:.1f}%, "
            f"Memory: {profiler_summary['memory']['current_mb']:.1f}MB"
        )

    async def _update_sla_measurements(self) -> None:
        """Update SLA measurements from profiler data."""
        # Get critical function performance
        critical_stats = self.profiler.get_critical_function_stats()

        for function_name, stats in critical_stats.items():
            # Record response time SLA measurements
            if "scene" in function_name.lower():
                self.sla_monitor.record_response_time("scene_activation", stats["recent_avg_ms"])
            elif "api" in function_name.lower() or "request" in function_name.lower():
                self.sla_monitor.record_response_time("api_request", stats["recent_avg_ms"])

        # Record availability based on health checks
        overall_health = self.health_manager.get_overall_health()
        is_available = overall_health.value in ("healthy", "degraded")
        self.sla_monitor.record_availability("system", is_available)

    async def _feed_anomaly_detector(self) -> None:
        """Feed metrics to anomaly detector."""
        now = time.time()

        # Feed profiler metrics
        resource_utilization = self.profiler.get_resource_utilization()

        if "process_cpu_percent" in resource_utilization:
            self.anomaly_detector.add_metric_point(
                "cpu_usage", resource_utilization["process_cpu_percent"], now
            )

        if "process_memory_mb" in resource_utilization:
            self.anomaly_detector.add_metric_point(
                "memory_usage", resource_utilization["process_memory_mb"], now
            )

        # Feed health check results
        health_score = self.health_manager.get_health_score()
        self.anomaly_detector.add_metric_point("health_score", health_score, now)

        # Feed SLA compliance
        sla_summary = self.sla_monitor.get_sla_summary()
        self.anomaly_detector.add_metric_point(
            "sla_compliance", sla_summary["overall_compliance_percent"], now
        )

        # Feed critical function timings
        critical_stats = self.profiler.get_critical_function_stats()
        for function_name, stats in critical_stats.items():
            self.anomaly_detector.add_metric_point(
                f"function_time_{function_name}", stats["recent_avg_ms"], now
            )

    async def _cleanup_old_data(self) -> None:
        """Cleanup old data to prevent memory leaks."""
        # Cleanup old traces (older than 24 hours)
        removed_traces = self.tracer.cleanup_old_traces(max_age_hours=24)
        if removed_traces > 0:
            logger.debug(f"Cleaned up {removed_traces} old traces")

    def _handle_sla_alert(self, alert) -> None:
        """Handle SLA breach alerts."""
        # Could integrate with external alerting systems here
        logger.error(f"🚨 SLA Alert: {alert.message}")

        # Add trace event if we're in a trace
        self.tracer.add_event(
            "sla_alert",
            {
                "sla_name": alert.sla_name,
                "severity": alert.severity.value,
                "current_value": alert.current_value,
                "target_value": alert.target_value,
            },
        )

    def _handle_memory_pressure(self, health_result) -> None:
        """Handle memory pressure events."""
        logger.warning(f"🧠 Memory pressure detected: {health_result.message}")

        # Could trigger automatic cleanup or scaling here
        # For now, just log and trace
        self.tracer.add_event(
            "memory_pressure",
            {
                "memory_percent": health_result.metadata.get("memory_percent"),
                "rss_mb": health_result.metadata.get("rss_mb"),
            },
        )

    def _handle_cpu_pressure(self, health_result) -> None:
        """Handle CPU pressure events."""
        logger.warning(f"⚡ CPU pressure detected: {health_result.message}")

        # Could trigger performance optimizations here
        self.tracer.add_event(
            "cpu_pressure", {"cpu_percent": health_result.metadata.get("cpu_percent")}
        )

    def _handle_anomaly(self, anomaly) -> None:
        """Handle detected anomalies."""
        logger.warning(
            f"🔍 Anomaly in {anomaly.metric_name}: {anomaly.message} "
            f"(severity: {anomaly.severity.value})"
        )

        # Add to trace context
        self.tracer.add_event(
            "anomaly_detected",
            {
                "metric_name": anomaly.metric_name,
                "anomaly_type": anomaly.anomaly_type.value,
                "severity": anomaly.severity.value,
                "actual_value": anomaly.actual_value,
                "expected_value": anomaly.expected_value,
                "deviation": anomaly.deviation,
                "confidence": anomaly.confidence,
            },
        )

    def get_comprehensive_status(self) -> dict[str, Any]:
        """Get comprehensive monitoring system status."""
        # Get status from all components
        profiler_summary = self.profiler.get_performance_summary()
        health_summary = self.health_manager.get_health_summary()
        sla_summary = self.sla_monitor.get_sla_summary()
        tracing_summary = self.tracer.get_tracing_summary()
        anomaly_summary = self.anomaly_detector.get_anomaly_summary()

        # Calculate overall system score
        health_score = health_summary["health_score"]
        sla_score = sla_summary["overall_compliance_percent"]
        overall_score = (health_score + sla_score) / 2

        return {
            "overall_score": overall_score,
            "service_name": self.service_name,
            "running": self._running,
            "components": {
                "profiler": {
                    "active": profiler_summary["sampling"]["active"],
                    "uptime_seconds": profiler_summary["uptime_seconds"],
                    "functions_tracked": len(profiler_summary["functions"]),
                    "cpu_percent": profiler_summary["cpu"]["current_percent"],
                    "memory_mb": profiler_summary["memory"]["current_mb"],
                },
                "health_checks": {
                    "overall_status": health_summary["overall_status"],
                    "health_score": health_summary["health_score"],
                    "total_checks": health_summary["total_checks"],
                    "failing_checks": len(health_summary["failing_checks"]),
                },
                "sla_monitoring": {
                    "overall_compliance": sla_summary["overall_compliance_percent"],
                    "compliant_slas": sla_summary["compliant_slas"],
                    "total_slas": sla_summary["total_slas"],
                    "active_breaches": sla_summary["active_breaches"],
                },
                "distributed_tracing": {
                    "total_traces": tracing_summary["total_traces"],
                    "active_spans": tracing_summary["active_spans"],
                    "service_count": tracing_summary["service_count"],
                    "avg_trace_duration_ms": tracing_summary["avg_trace_duration_ms"],
                },
                "anomaly_detection": {
                    "anomalies_last_hour": anomaly_summary["total_anomalies_last_hour"],
                    "monitored_metrics": anomaly_summary["monitored_metrics"],
                    "baselines_established": anomaly_summary["baselines_established"],
                    "detection_running": anomaly_summary["detection_running"],
                },
            },
            "recent_issues": {
                "health_failures": health_summary["failing_checks"],
                "sla_breaches": list(sla_summary["breach_details"].keys()),
                "recent_anomalies": len(anomaly_summary.get("top_noisy_metrics", [])),
            },
            "timestamp": time.time(),
        }

    def record_smart_home_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool,
        integration: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record smart home operation for comprehensive monitoring."""
        # Record with profiler (if operation was traced)
        # This will be handled automatically by the @profile decorator

        # Record SLA measurement
        if "scene" in operation.lower():
            self.sla_monitor.record_response_time("scene_activation", duration_ms)
        elif "api" in operation.lower():
            self.sla_monitor.record_response_time("api_request", duration_ms)

        # Record success/failure for availability SLA
        if integration:
            self.sla_monitor.record_availability(f"integration_{integration}", success)

        # Record error for error rate SLA
        self.sla_monitor.record_error(operation, not success)

        # Add to anomaly detection
        now = time.time()
        self.anomaly_detector.add_metric_point(f"operation_{operation}_time", duration_ms, now)

        # Add trace event
        self.tracer.add_event(
            "smart_home_operation",
            {
                "operation": operation,
                "duration_ms": duration_ms,
                "success": success,
                "integration": integration,
                **(metadata or {}),
            },
        )


# Global monitoring integration instance
_global_monitoring: MonitoringIntegration | None = None


def get_monitoring() -> MonitoringIntegration:
    """Get the global monitoring integration instance."""
    global _global_monitoring
    if _global_monitoring is None:
        _global_monitoring = MonitoringIntegration()

    return _global_monitoring


async def start_monitoring(service_name: str = "kagami") -> MonitoringIntegration:
    """Start the integrated monitoring system."""
    monitoring = get_monitoring()
    monitoring.service_name = service_name
    await monitoring.start()
    return monitoring


async def stop_monitoring() -> None:
    """Stop the integrated monitoring system."""
    global _global_monitoring
    if _global_monitoring:
        await _global_monitoring.stop()
