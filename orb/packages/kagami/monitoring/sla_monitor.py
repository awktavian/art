"""SLA Monitoring & Alerting Framework.

Comprehensive SLA compliance monitoring with real-time alerting:
- Response time SLAs (p95, p99)
- Availability SLAs (uptime %)
- Error rate SLAs (error budget)
- Throughput SLAs (requests/second)
- Custom SLA definitions
- Multi-channel alerting

Designed for production SLA compliance and operational excellence.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class SLAType(str, Enum):
    """Types of SLA metrics."""

    RESPONSE_TIME = "response_time"
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"  # SLA breach, immediate action required
    WARNING = "warning"  # SLA at risk, action needed soon
    INFO = "info"  # SLA trend deteriorating


class AlertChannel(str, Enum):
    """Alert delivery channels."""

    LOG = "log"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"


@dataclass
class SLADefinition:
    """Definition of an SLA requirement."""

    name: str
    sla_type: SLAType
    target_value: float
    measurement_window_minutes: int
    breach_threshold_minutes: int = 5
    warning_threshold_percent: float = 0.8  # Warn at 80% of target
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class SLAMeasurement:
    """A single SLA measurement."""

    sla_name: str
    value: float
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAAlert:
    """SLA breach or warning alert."""

    sla_name: str
    severity: AlertSeverity
    current_value: float
    target_value: float
    breach_duration_minutes: float
    message: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAStatus:
    """Current SLA compliance status."""

    sla_name: str
    is_compliant: bool
    current_value: float
    target_value: float
    compliance_percent: float
    time_to_breach_minutes: float | None
    last_breach_timestamp: float | None
    measurements_count: int


class SLAMonitor:
    """Production SLA monitoring and alerting system.

    Key SLAs monitored:
    - API Response Time: p95 < 100ms, p99 < 200ms
    - System Availability: > 99.9% uptime
    - Error Rate: < 0.1% of requests
    - Scene Activation: < 100ms end-to-end
    - Integration Health: > 99% success rate
    """

    def __init__(self, max_measurements: int = 10000):
        self.max_measurements = max_measurements

        # SLA definitions and measurements
        self._slas: dict[str, SLADefinition] = {}
        self._measurements: dict[str, deque[SLAMeasurement]] = defaultdict(
            lambda: deque(maxlen=max_measurements)
        )

        # Breach tracking
        self._breach_start_times: dict[str, float] = {}
        self._last_alerts: dict[str, float] = {}

        # Alert configuration
        self._alert_callbacks: dict[AlertChannel, list[Callable[[SLAAlert], None]]] = {
            channel: [] for channel in AlertChannel
        }

        # Monitoring state
        self._running = False
        self._monitor_task: asyncio.Task | None = None

        # Performance tracking
        self._performance_buckets: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))

        # Initialize default SLAs
        self._setup_default_slas()

    def _setup_default_slas(self) -> None:
        """Set up default SLAs for the smart home system."""
        default_slas = [
            SLADefinition(
                name="api_response_time_p95",
                sla_type=SLAType.RESPONSE_TIME,
                target_value=100.0,  # 100ms
                measurement_window_minutes=5,
                breach_threshold_minutes=2,
                description="API response time 95th percentile < 100ms",
            ),
            SLADefinition(
                name="api_response_time_p99",
                sla_type=SLAType.RESPONSE_TIME,
                target_value=200.0,  # 200ms
                measurement_window_minutes=5,
                breach_threshold_minutes=3,
                description="API response time 99th percentile < 200ms",
            ),
            SLADefinition(
                name="system_availability",
                sla_type=SLAType.AVAILABILITY,
                target_value=99.9,  # 99.9% uptime
                measurement_window_minutes=60,
                breach_threshold_minutes=5,
                description="System availability > 99.9%",
            ),
            SLADefinition(
                name="error_rate",
                sla_type=SLAType.ERROR_RATE,
                target_value=0.1,  # 0.1% error rate
                measurement_window_minutes=10,
                breach_threshold_minutes=5,
                description="Error rate < 0.1%",
            ),
            SLADefinition(
                name="scene_activation_time",
                sla_type=SLAType.RESPONSE_TIME,
                target_value=100.0,  # 100ms
                measurement_window_minutes=5,
                breach_threshold_minutes=2,
                description="Scene activation time < 100ms",
            ),
            SLADefinition(
                name="integration_success_rate",
                sla_type=SLAType.AVAILABILITY,
                target_value=99.0,  # 99% success rate
                measurement_window_minutes=30,
                breach_threshold_minutes=10,
                description="Integration success rate > 99%",
            ),
        ]

        for sla in default_slas:
            self._slas[sla.name] = sla

    async def start(self) -> None:
        """Start SLA monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("📋 SLA monitoring started")

    async def stop(self) -> None:
        """Stop SLA monitoring."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("📋 SLA monitoring stopped")

    def define_sla(self, sla: SLADefinition) -> None:
        """Define a new SLA to monitor."""
        self._slas[sla.name] = sla
        logger.info(f"📋 SLA defined: {sla.name} - {sla.description}")

    def record_measurement(
        self, sla_name: str, value: float, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record an SLA measurement."""
        if sla_name not in self._slas:
            logger.warning(f"Unknown SLA: {sla_name}")
            return

        measurement = SLAMeasurement(
            sla_name=sla_name, value=value, timestamp=time.time(), metadata=metadata or {}
        )

        self._measurements[sla_name].append(measurement)

        # For response time SLAs, also track in performance buckets
        sla = self._slas[sla_name]
        if sla.sla_type == SLAType.RESPONSE_TIME:
            self._performance_buckets[sla_name].append(value)

    def record_response_time(self, operation: str, response_time_ms: float) -> None:
        """Convenience method for recording response times."""
        # Record for general API response time SLAs
        if "api" in operation.lower():
            self.record_measurement("api_response_time_p95", response_time_ms)
            self.record_measurement("api_response_time_p99", response_time_ms)

        # Record for scene activation if applicable
        if "scene" in operation.lower():
            self.record_measurement("scene_activation_time", response_time_ms)

    def record_availability(self, service: str, is_available: bool) -> None:
        """Record availability measurement."""
        availability_percent = 100.0 if is_available else 0.0

        # Record for system availability
        self.record_measurement("system_availability", availability_percent, {"service": service})

        # Record for integration success rate
        if "integration" in service.lower():
            success_rate = 100.0 if is_available else 0.0
            self.record_measurement("integration_success_rate", success_rate, {"service": service})

    def record_error(self, operation: str, is_error: bool) -> None:
        """Record error occurrence."""
        error_rate = 100.0 if is_error else 0.0
        self.record_measurement("error_rate", error_rate, {"operation": operation})

    def get_sla_status(self, sla_name: str) -> SLAStatus | None:
        """Get current status for an SLA."""
        if sla_name not in self._slas:
            return None

        sla = self._slas[sla_name]
        measurements = self._get_recent_measurements(sla_name, sla.measurement_window_minutes)

        if not measurements:
            return SLAStatus(
                sla_name=sla_name,
                is_compliant=True,
                current_value=0.0,
                target_value=sla.target_value,
                compliance_percent=100.0,
                time_to_breach_minutes=None,
                last_breach_timestamp=None,
                measurements_count=0,
            )

        # Calculate current value based on SLA type
        current_value = self._calculate_current_value(sla, measurements)

        # Determine compliance
        is_compliant = self._is_compliant(sla, current_value)

        # Calculate compliance percentage
        if sla.sla_type in (SLAType.RESPONSE_TIME, SLAType.ERROR_RATE):
            # Lower is better
            compliance_percent = max(0, 100 - (current_value / sla.target_value * 100))
        else:
            # Higher is better (availability, throughput)
            compliance_percent = current_value / sla.target_value * 100

        compliance_percent = min(100, max(0, compliance_percent))

        # Estimate time to breach
        time_to_breach = self._estimate_time_to_breach(sla, measurements)

        # Find last breach
        last_breach = self._find_last_breach(sla, measurements)

        return SLAStatus(
            sla_name=sla_name,
            is_compliant=is_compliant,
            current_value=current_value,
            target_value=sla.target_value,
            compliance_percent=compliance_percent,
            time_to_breach_minutes=time_to_breach,
            last_breach_timestamp=last_breach,
            measurements_count=len(measurements),
        )

    def _get_recent_measurements(self, sla_name: str, window_minutes: int) -> list[SLAMeasurement]:
        """Get measurements within the specified time window."""
        cutoff_time = time.time() - (window_minutes * 60)
        return [m for m in self._measurements[sla_name] if m.timestamp >= cutoff_time]

    def _calculate_current_value(
        self, sla: SLADefinition, measurements: list[SLAMeasurement]
    ) -> float:
        """Calculate current SLA value from measurements."""
        values = [m.value for m in measurements]

        if sla.sla_type == SLAType.RESPONSE_TIME:
            # For response time, calculate percentiles
            if "p99" in sla.name.lower():
                return self._calculate_percentile(values, 0.99)
            elif "p95" in sla.name.lower():
                return self._calculate_percentile(values, 0.95)
            else:
                return sum(values) / len(values)

        elif sla.sla_type == SLAType.AVAILABILITY:
            # For availability, calculate percentage of successful measurements
            return sum(values) / len(values)

        elif sla.sla_type == SLAType.ERROR_RATE:
            # For error rate, calculate percentage of errors
            error_count = sum(1 for v in values if v > 0)
            return (error_count / len(values)) * 100

        elif sla.sla_type == SLAType.THROUGHPUT:
            # For throughput, calculate average
            return sum(values) / len(values)

        else:  # CUSTOM
            return sum(values) / len(values)

    def _calculate_percentile(self, values: list[float], percentile: float) -> float:
        """Calculate percentile from list of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _is_compliant(self, sla: SLADefinition, current_value: float) -> bool:
        """Check if current value meets SLA target."""
        if sla.sla_type in (SLAType.RESPONSE_TIME, SLAType.ERROR_RATE):
            # Lower is better
            return current_value <= sla.target_value
        else:
            # Higher is better
            return current_value >= sla.target_value

    def _estimate_time_to_breach(
        self, sla: SLADefinition, measurements: list[SLAMeasurement]
    ) -> float | None:
        """Estimate time until SLA breach based on trends."""
        if len(measurements) < 3:
            return None

        # Calculate trend over recent measurements
        recent_values = [m.value for m in measurements[-10:]]
        if len(recent_values) < 3:
            return None

        # Simple linear trend
        x = list(range(len(recent_values)))
        y = recent_values

        # Calculate slope
        n = len(x)
        slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / (
            n * sum(x[i] * x[i] for i in range(n)) - sum(x) ** 2
        )

        if slope == 0:
            return None

        current_value = recent_values[-1]

        if sla.sla_type in (SLAType.RESPONSE_TIME, SLAType.ERROR_RATE):
            # Lower is better - check if trending upward
            if slope > 0:
                steps_to_breach = (sla.target_value - current_value) / slope
                return max(
                    0, steps_to_breach * (sla.measurement_window_minutes / len(recent_values))
                )
        else:
            # Higher is better - check if trending downward
            if slope < 0:
                steps_to_breach = (current_value - sla.target_value) / abs(slope)
                return max(
                    0, steps_to_breach * (sla.measurement_window_minutes / len(recent_values))
                )

        return None

    def _find_last_breach(
        self, sla: SLADefinition, measurements: list[SLAMeasurement]
    ) -> float | None:
        """Find timestamp of last SLA breach."""
        for measurement in reversed(measurements):
            value_breaches = False

            if sla.sla_type in (SLAType.RESPONSE_TIME, SLAType.ERROR_RATE):
                value_breaches = measurement.value > sla.target_value
            else:
                value_breaches = measurement.value < sla.target_value

            if value_breaches:
                return measurement.timestamp

        return None

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_sla_compliance()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SLA monitoring error: {e}")
                await asyncio.sleep(10)

    async def _check_sla_compliance(self) -> None:
        """Check compliance for all SLAs and generate alerts."""
        for sla_name, sla in self._slas.items():
            status = self.get_sla_status(sla_name)
            if not status:
                continue

            now = time.time()

            # Check for breach
            if not status.is_compliant:
                # Track breach start time
                if sla_name not in self._breach_start_times:
                    self._breach_start_times[sla_name] = now

                breach_duration = now - self._breach_start_times[sla_name]
                breach_minutes = breach_duration / 60

                # Generate alert if breach duration exceeds threshold
                if breach_minutes >= sla.breach_threshold_minutes:
                    last_alert = self._last_alerts.get(sla_name, 0)

                    # Avoid alert spam - wait at least 5 minutes between alerts
                    if now - last_alert >= 300:
                        alert = SLAAlert(
                            sla_name=sla_name,
                            severity=AlertSeverity.CRITICAL,
                            current_value=status.current_value,
                            target_value=status.target_value,
                            breach_duration_minutes=breach_minutes,
                            message=f"SLA BREACH: {sla.description} - "
                            f"Current: {status.current_value:.1f}, "
                            f"Target: {status.target_value:.1f}, "
                            f"Breach duration: {breach_minutes:.1f}min",
                            timestamp=now,
                        )

                        await self._trigger_alert(alert)
                        self._last_alerts[sla_name] = now

            else:
                # SLA is compliant - clear breach tracking
                if sla_name in self._breach_start_times:
                    del self._breach_start_times[sla_name]

                # Check for warning conditions
                warning_threshold = sla.target_value * sla.warning_threshold_percent

                warning_triggered = False
                if sla.sla_type in (SLAType.RESPONSE_TIME, SLAType.ERROR_RATE):
                    warning_triggered = status.current_value >= warning_threshold
                else:
                    warning_triggered = status.current_value <= warning_threshold

                if warning_triggered:
                    last_alert = self._last_alerts.get(f"{sla_name}_warning", 0)

                    # Warning alerts every 10 minutes max
                    if now - last_alert >= 600:
                        alert = SLAAlert(
                            sla_name=sla_name,
                            severity=AlertSeverity.WARNING,
                            current_value=status.current_value,
                            target_value=status.target_value,
                            breach_duration_minutes=0,
                            message=f"SLA WARNING: {sla.description} - "
                            f"Current: {status.current_value:.1f}, "
                            f"Warning threshold: {warning_threshold:.1f}",
                            timestamp=now,
                        )

                        await self._trigger_alert(alert)
                        self._last_alerts[f"{sla_name}_warning"] = now

    async def _trigger_alert(self, alert: SLAAlert) -> None:
        """Trigger SLA alert across configured channels."""
        logger.warning(f"🚨 SLA Alert: {alert.message}")

        # Trigger all configured alert channels
        for channel, callbacks in self._alert_callbacks.items():
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback error for {channel}: {e}")

    def on_alert(self, channel: AlertChannel, callback: Callable[[SLAAlert], None]) -> None:
        """Register alert callback for specific channel."""
        self._alert_callbacks[channel].append(callback)

    def get_all_sla_status(self) -> dict[str, SLAStatus]:
        """Get status for all defined SLAs."""
        status = {}
        for sla_name in self._slas.keys():
            sla_status = self.get_sla_status(sla_name)
            if sla_status:
                status[sla_name] = sla_status

        return status

    def get_sla_summary(self) -> dict[str, Any]:
        """Get comprehensive SLA summary."""
        all_status = self.get_all_sla_status()

        compliant_count = sum(1 for s in all_status.values() if s.is_compliant)
        total_count = len(all_status)

        breach_count = len(self._breach_start_times)

        avg_compliance = sum(s.compliance_percent for s in all_status.values()) / max(
            total_count, 1
        )

        return {
            "overall_compliance_percent": avg_compliance,
            "compliant_slas": compliant_count,
            "total_slas": total_count,
            "active_breaches": breach_count,
            "sla_status": {
                name: {
                    "compliant": status.is_compliant,
                    "current_value": status.current_value,
                    "target_value": status.target_value,
                    "compliance_percent": status.compliance_percent,
                }
                for name, status in all_status.items()
            },
            "breach_details": {
                name: {
                    "breach_duration_minutes": (time.time() - start_time) / 60,
                    "start_time": start_time,
                }
                for name, start_time in self._breach_start_times.items()
            },
        }

    async def send_slack_alert(self, webhook_url: str, alert: SLAAlert) -> None:
        """Send alert to Slack via webhook."""
        try:
            color = "danger" if alert.severity == AlertSeverity.CRITICAL else "warning"

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"SLA {alert.severity.upper()}",
                        "text": alert.message,
                        "fields": [
                            {"title": "SLA", "value": alert.sla_name, "short": True},
                            {
                                "title": "Current",
                                "value": f"{alert.current_value:.1f}",
                                "short": True,
                            },
                            {
                                "title": "Target",
                                "value": f"{alert.target_value:.1f}",
                                "short": True,
                            },
                            {"title": "Severity", "value": alert.severity.value, "short": True},
                        ],
                        "timestamp": alert.timestamp,
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send Slack alert: {response.status}")

        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
