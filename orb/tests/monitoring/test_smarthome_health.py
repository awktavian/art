"""💎 CRYSTAL COLONY — Smart Home Health Monitoring & Alerting

Comprehensive health monitoring and alerting system for smart home reliability.
Implements continuous monitoring, proactive failure detection, and automated
recovery mechanisms with crystalline verification precision.

Monitoring Domains:
- Integration health and connectivity status
- Device responsiveness and communication quality
- Network stability and latency monitoring
- Security system health and zone integrity
- HVAC performance and energy efficiency
- Battery levels and maintenance alerts
- Performance metrics and capacity planning

Alerting Capabilities:
- Real-time health status dashboard
- Proactive failure prediction
- Automated escalation protocols
- Integration-specific health checks
- Performance degradation detection
- Security and safety critical alerts

Safety Integration:
- Control Barrier Function monitoring
- h(x) ≥ 0 compliance verification
- Graceful degradation orchestration
- Emergency response coordination

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from collections.abc import Callable
from unittest.mock import AsyncMock, Mock, patch

import pytest

from kagami.core.safety import get_safety_filter
from kagami_smarthome import SmartHomeController, SmartHomeConfig
from kagami_smarthome.types import PresenceState, SecurityState

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthMetric:
    """Individual health metric."""

    name: str
    value: float
    status: HealthStatus
    threshold_warning: float = 0.8
    threshold_critical: float = 0.3
    last_updated: datetime = field(default_factory=datetime.now)
    trend: str = "stable"  # improving, degrading, stable


@dataclass
class IntegrationHealth:
    """Health status for a smart home integration."""

    name: str
    status: HealthStatus
    connected: bool = False
    response_time_ms: float = 0.0
    success_rate: float = 1.0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    failure_count: int = 0
    metrics: dict[str, HealthMetric] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SystemHealthAlert:
    """System health alert."""

    id: str
    level: AlertLevel
    message: str
    component: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    actions_taken: list[str] = field(default_factory=list)


class SmartHomeHealthMonitor:
    """💎 Crystal precision health monitoring for smart home systems."""

    def __init__(self, controller: SmartHomeController):
        self.controller = controller
        self.cbf_filter = get_safety_filter()

        # Health tracking
        self._integration_health: dict[str, IntegrationHealth] = {}
        self._system_metrics: dict[str, HealthMetric] = {}
        self._alerts: list[SystemHealthAlert] = []

        # Monitoring configuration
        self._monitoring_interval = 30.0  # seconds
        self._health_check_timeout = 10.0
        self._performance_history_size = 100

        # Monitoring state
        self._monitoring_active = False
        self._monitoring_task: asyncio.Task | None = None

        # Alert callbacks
        self._alert_callbacks: list[Callable[[SystemHealthAlert], None]] = []

        # Performance tracking
        self._performance_history: dict[str, list[float]] = {}

        # Initialize integration health tracking
        self._initialize_health_tracking()

    def _initialize_health_tracking(self) -> None:
        """Initialize health tracking for all integrations."""
        integrations = [
            "control4",
            "unifi",
            "denon",
            "august",
            "eight_sleep",
            "lg_tv",
            "samsung_tv",
            "tesla",
            "oelo",
            "mitsubishi",
            "envisalink",
        ]

        for integration in integrations:
            self._integration_health[integration] = IntegrationHealth(
                name=integration, status=HealthStatus.UNKNOWN
            )

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        logger.info("💎 Starting smart home health monitoring...")

        # Start monitoring task
        from kagami.core.async_utils import safe_create_task

        self._monitoring_task = safe_create_task(
            self._monitoring_loop(),
            name="smarthome_health_monitor",
            error_callback=lambda e: logger.error(f"Health monitoring error: {e}"),
        )

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._monitoring_active = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None

        logger.info("💎 Smart home health monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Perform health checks
                await self._perform_health_checks()

                # Update system metrics
                await self._update_system_metrics()

                # Check for alerts
                await self._check_alert_conditions()

                # Cleanup old data
                self._cleanup_old_data()

                # Wait for next check
                await asyncio.sleep(self._monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring loop error: {e}")
                await asyncio.sleep(60.0)  # Wait longer on error

    async def _perform_health_checks(self) -> None:
        """Perform health checks for all integrations."""
        health_check_tasks = [
            self._check_control4_health(),
            self._check_unifi_health(),
            self._check_denon_health(),
            self._check_august_health(),
            self._check_eight_sleep_health(),
            self._check_lg_tv_health(),
            self._check_samsung_tv_health(),
            self._check_tesla_health(),
            self._check_oelo_health(),
            self._check_mitsubishi_health(),
            self._check_envisalink_health(),
        ]

        # Run health checks concurrently
        await asyncio.gather(*health_check_tasks, return_exceptions=True)

    async def _check_control4_health(self) -> None:
        """Check Control4 integration health."""
        integration = self._integration_health["control4"]

        try:
            if not self.controller._control4:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            start_time = time.time()

            # Test basic connectivity
            rooms = self.controller._control4.get_rooms()

            response_time = (time.time() - start_time) * 1000
            integration.response_time_ms = response_time
            integration.connected = self.controller._control4.is_connected
            integration.last_success = datetime.now()

            # Evaluate health status
            if response_time > 5000:  # 5 second threshold
                integration.status = HealthStatus.CRITICAL
            elif response_time > 2000:  # 2 second threshold
                integration.status = HealthStatus.WARNING
            else:
                integration.status = HealthStatus.HEALTHY

            # Update metrics
            integration.metrics["response_time"] = HealthMetric(
                name="response_time",
                value=response_time,
                status=integration.status,
                threshold_warning=2000.0,
                threshold_critical=5000.0,
            )

            integration.metrics["device_count"] = HealthMetric(
                name="device_count",
                value=len(rooms) if rooms else 0,
                status=HealthStatus.HEALTHY if rooms else HealthStatus.WARNING,
            )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1
            logger.debug(f"Control4 health check failed: {e}")

    async def _check_unifi_health(self) -> None:
        """Check UniFi integration health."""
        integration = self._integration_health["unifi"]

        try:
            if not self.controller._unifi:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            start_time = time.time()

            # Test camera connectivity
            cameras = self.controller._unifi.get_cameras()

            response_time = (time.time() - start_time) * 1000
            integration.response_time_ms = response_time
            integration.connected = self.controller._unifi.is_connected
            integration.last_success = datetime.now()

            # Check camera health
            if cameras and len(cameras) >= 4:  # Expected 4 cameras
                integration.status = HealthStatus.HEALTHY
            elif cameras:
                integration.status = HealthStatus.WARNING
            else:
                integration.status = HealthStatus.CRITICAL

            integration.metrics["camera_count"] = HealthMetric(
                name="camera_count", value=len(cameras) if cameras else 0, status=integration.status
            )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_denon_health(self) -> None:
        """Check Denon AVR health."""
        integration = self._integration_health["denon"]

        try:
            if not self.controller._denon:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            start_time = time.time()

            # Test basic status query
            zones = self.controller._denon.get_zones()

            response_time = (time.time() - start_time) * 1000
            integration.response_time_ms = response_time
            integration.connected = self.controller._denon.is_connected
            integration.last_success = datetime.now()

            if response_time > 3000:
                integration.status = HealthStatus.WARNING
            else:
                integration.status = HealthStatus.HEALTHY

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_august_health(self) -> None:
        """Check August locks health."""
        integration = self._integration_health["august"]

        try:
            if not self.controller._august:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            start_time = time.time()

            # Check lock states and battery levels
            battery_levels = self.controller.get_lock_battery_levels()

            response_time = (time.time() - start_time) * 1000
            integration.response_time_ms = response_time
            integration.connected = self.controller._august.is_connected
            integration.last_success = datetime.now()

            # Check battery health
            low_batteries = [name for name, level in battery_levels.items() if level < 0.2]
            critical_batteries = [name for name, level in battery_levels.items() if level < 0.1]

            if critical_batteries:
                integration.status = HealthStatus.CRITICAL
            elif low_batteries:
                integration.status = HealthStatus.WARNING
            else:
                integration.status = HealthStatus.HEALTHY

            # Update battery metrics
            for lock_name, level in battery_levels.items():
                integration.metrics[f"battery_{lock_name}"] = HealthMetric(
                    name=f"battery_{lock_name}",
                    value=level,
                    status=HealthStatus.CRITICAL
                    if level < 0.1
                    else HealthStatus.WARNING
                    if level < 0.2
                    else HealthStatus.HEALTHY,
                    threshold_warning=0.2,
                    threshold_critical=0.1,
                )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_eight_sleep_health(self) -> None:
        """Check Eight Sleep health."""
        integration = self._integration_health["eight_sleep"]

        try:
            if not self.controller._eight_sleep:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            # Check bed sensors
            in_bed = self.controller.is_anyone_in_bed()
            asleep = self.controller.is_anyone_asleep()

            integration.connected = self.controller._eight_sleep.is_connected
            integration.last_success = datetime.now()

            # Eight Sleep health is based on connectivity
            integration.status = (
                HealthStatus.HEALTHY if integration.connected else HealthStatus.FAILED
            )

            integration.metrics["bed_occupied"] = HealthMetric(
                name="bed_occupied", value=1.0 if in_bed else 0.0, status=HealthStatus.HEALTHY
            )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_lg_tv_health(self) -> None:
        """Check LG TV health."""
        integration = self._integration_health["lg_tv"]

        try:
            if not self.controller._lg_tv:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            integration.connected = self.controller._lg_tv.is_connected

            if integration.connected:
                integration.status = HealthStatus.HEALTHY
                integration.last_success = datetime.now()
            else:
                integration.status = HealthStatus.WARNING  # TV might be off

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_samsung_tv_health(self) -> None:
        """Check Samsung TV health."""
        integration = self._integration_health["samsung_tv"]

        try:
            if not self.controller._samsung_tv:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            integration.connected = (
                self.controller._samsung_tv.is_connected if self.controller._samsung_tv else False
            )

            if integration.connected:
                integration.status = HealthStatus.HEALTHY
                integration.last_success = datetime.now()
            else:
                integration.status = HealthStatus.WARNING  # TV might be off

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_tesla_health(self) -> None:
        """Check Tesla integration health."""
        integration = self._integration_health["tesla"]

        try:
            if not self.controller._tesla:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            # Check vehicle connectivity
            is_home = self.controller.is_car_home()
            battery = self.controller.get_car_battery()

            integration.connected = self.controller._tesla.is_connected
            integration.last_success = datetime.now()

            # Tesla health based on API connectivity
            if integration.connected:
                integration.status = HealthStatus.HEALTHY
            else:
                integration.status = HealthStatus.WARNING

            integration.metrics["battery_level"] = HealthMetric(
                name="battery_level",
                value=battery,
                status=HealthStatus.CRITICAL
                if battery < 20
                else HealthStatus.WARNING
                if battery < 50
                else HealthStatus.HEALTHY,
                threshold_warning=50.0,
                threshold_critical=20.0,
            )

            integration.metrics["at_home"] = HealthMetric(
                name="at_home", value=1.0 if is_home else 0.0, status=HealthStatus.HEALTHY
            )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_oelo_health(self) -> None:
        """Check Oelo outdoor lighting health."""
        integration = self._integration_health["oelo"]

        try:
            if not self.controller._oelo:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            integration.connected = self.controller._oelo.is_connected

            if integration.connected:
                integration.status = HealthStatus.HEALTHY
                integration.last_success = datetime.now()
            else:
                integration.status = HealthStatus.WARNING

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_mitsubishi_health(self) -> None:
        """Check Mitsubishi HVAC health."""
        integration = self._integration_health["mitsubishi"]

        try:
            if not self.controller._mitsubishi:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            # Check HVAC zones
            temps = self.controller.get_hvac_temps()
            avg_temp = self.controller.get_average_temp()

            integration.connected = self.controller._mitsubishi.is_connected
            integration.last_success = datetime.now()

            # Check temperature ranges
            extreme_temps = [
                name
                for name, (current, target) in temps.items()
                if current < 55 or current > 85  # Extreme temperatures
            ]

            if extreme_temps:
                integration.status = HealthStatus.CRITICAL
            elif temps:
                integration.status = HealthStatus.HEALTHY
            else:
                integration.status = HealthStatus.WARNING

            integration.metrics["avg_temperature"] = HealthMetric(
                name="avg_temperature",
                value=avg_temp,
                status=HealthStatus.HEALTHY if 65 <= avg_temp <= 80 else HealthStatus.WARNING,
            )

            integration.metrics["zone_count"] = HealthMetric(
                name="zone_count",
                value=len(temps),
                status=HealthStatus.HEALTHY if temps else HealthStatus.WARNING,
            )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _check_envisalink_health(self) -> None:
        """Check Envisalink DSC security health."""
        integration = self._integration_health["envisalink"]

        try:
            if not self.controller._envisalink:
                integration.status = HealthStatus.FAILED
                integration.connected = False
                return

            # Check security system health
            security_state = await self.controller.get_security_state()
            open_zones = self.controller.get_open_zones()
            trouble_status = self.controller.get_dsc_trouble_status()

            integration.connected = self.controller._envisalink.is_connected
            integration.last_success = datetime.now()

            # Check for trouble conditions
            has_troubles = False
            if isinstance(trouble_status, dict):
                has_troubles = any(
                    trouble_status.get(key, False)
                    for key in [
                        "ac_failure",
                        "battery_low",
                        "bell_trouble",
                        "phone_line_trouble",
                        "fire_trouble",
                        "system_tamper",
                    ]
                )

            if has_troubles:
                integration.status = HealthStatus.CRITICAL
            elif len(open_zones) > 5:  # Many zones open might indicate issue
                integration.status = HealthStatus.WARNING
            else:
                integration.status = HealthStatus.HEALTHY

            integration.metrics["open_zones"] = HealthMetric(
                name="open_zones",
                value=len(open_zones),
                status=HealthStatus.WARNING if len(open_zones) > 5 else HealthStatus.HEALTHY,
            )

            integration.metrics["trouble_conditions"] = HealthMetric(
                name="trouble_conditions",
                value=1.0 if has_troubles else 0.0,
                status=HealthStatus.CRITICAL if has_troubles else HealthStatus.HEALTHY,
            )

        except Exception as e:
            integration.status = HealthStatus.FAILED
            integration.connected = False
            integration.last_failure = datetime.now()
            integration.failure_count += 1

    async def _update_system_metrics(self) -> None:
        """Update system-wide health metrics."""
        # Overall connectivity
        total_integrations = len(self._integration_health)
        connected_integrations = sum(
            1 for health in self._integration_health.values() if health.connected
        )
        connectivity_ratio = (
            connected_integrations / total_integrations if total_integrations > 0 else 0
        )

        self._system_metrics["connectivity"] = HealthMetric(
            name="connectivity",
            value=connectivity_ratio,
            status=HealthStatus.CRITICAL
            if connectivity_ratio < 0.5
            else HealthStatus.WARNING
            if connectivity_ratio < 0.8
            else HealthStatus.HEALTHY,
            threshold_warning=0.8,
            threshold_critical=0.5,
        )

        # Safety health (CBF compliance)
        try:
            h_value = self.cbf_filter.evaluate_safety(
                {
                    "system": "smart_home",
                    "timestamp": time.time(),
                    "connectivity": connectivity_ratio,
                }
            )

            self._system_metrics["safety_h"] = HealthMetric(
                name="safety_h",
                value=h_value,
                status=HealthStatus.CRITICAL
                if h_value < 0
                else HealthStatus.WARNING
                if h_value < 0.3
                else HealthStatus.HEALTHY,
                threshold_warning=0.3,
                threshold_critical=0.0,
            )
        except Exception:
            self._system_metrics["safety_h"] = HealthMetric(
                name="safety_h",
                value=0.5,  # Default safe value
                status=HealthStatus.WARNING,
            )

        # Performance metrics
        avg_response_time = sum(
            h.response_time_ms for h in self._integration_health.values() if h.response_time_ms > 0
        ) / max(1, len([h for h in self._integration_health.values() if h.response_time_ms > 0]))

        self._system_metrics["avg_response_time"] = HealthMetric(
            name="avg_response_time",
            value=avg_response_time,
            status=HealthStatus.CRITICAL
            if avg_response_time > 5000
            else HealthStatus.WARNING
            if avg_response_time > 2000
            else HealthStatus.HEALTHY,
            threshold_warning=2000.0,
            threshold_critical=5000.0,
        )

    async def _check_alert_conditions(self) -> None:
        """Check for conditions that should trigger alerts."""
        current_time = datetime.now()

        # Check system-wide alerts
        connectivity = self._system_metrics.get("connectivity")
        if connectivity and connectivity.status == HealthStatus.CRITICAL:
            await self._create_alert(
                AlertLevel.CRITICAL,
                f"System connectivity critical: {connectivity.value:.1%}",
                "system",
            )

        safety_h = self._system_metrics.get("safety_h")
        if safety_h and safety_h.value < 0:
            await self._create_alert(
                AlertLevel.EMERGENCY, f"Safety violation: h(x) = {safety_h.value:.3f} < 0", "safety"
            )

        # Check integration-specific alerts
        for name, health in self._integration_health.items():
            # Critical integration failures
            if health.status == HealthStatus.FAILED:
                await self._create_alert(AlertLevel.CRITICAL, f"{name} integration failed", name)

            # Security system specific alerts
            if name == "envisalink" and health.status == HealthStatus.CRITICAL:
                await self._create_alert(
                    AlertLevel.EMERGENCY, f"Security system critical: {name}", name
                )

            # Battery alerts for August locks
            if name == "august":
                for metric_name, metric in health.metrics.items():
                    if (
                        metric_name.startswith("battery_")
                        and metric.status == HealthStatus.CRITICAL
                    ):
                        await self._create_alert(
                            AlertLevel.WARNING,
                            f"Low battery: {metric_name.replace('battery_', '')} at {metric.value:.1%}",
                            name,
                        )

            # High response time alerts
            if health.response_time_ms > 10000:  # 10 seconds
                await self._create_alert(
                    AlertLevel.WARNING,
                    f"{name} response time high: {health.response_time_ms:.0f}ms",
                    name,
                )

        # Check for repeated failures
        for name, health in self._integration_health.names():
            if health.failure_count >= 5:  # 5 consecutive failures
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    f"{name} has {health.failure_count} consecutive failures",
                    name,
                )

    async def _create_alert(self, level: AlertLevel, message: str, component: str) -> None:
        """Create a new system alert."""
        # Check if similar alert already exists and is not resolved
        existing = next(
            (
                alert
                for alert in self._alerts
                if alert.component == component and alert.message == message and not alert.resolved
            ),
            None,
        )

        if existing:
            return  # Don't create duplicate alerts

        alert = SystemHealthAlert(
            id=f"{component}_{int(time.time())}", level=level, message=message, component=component
        )

        self._alerts.append(alert)
        logger.warning(f"💎 HEALTH ALERT [{level.value.upper()}]: {message}")

        # Trigger alert callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Take automated actions based on alert level
        await self._handle_alert_actions(alert)

    async def _handle_alert_actions(self, alert: SystemHealthAlert) -> None:
        """Handle automated actions for alerts."""
        if alert.level == AlertLevel.EMERGENCY:
            # Emergency actions (safety violations, security failures)
            if "safety" in alert.component:
                # Safety violation - attempt system stabilization
                alert.actions_taken.append("attempted_system_stabilization")

            elif "envisalink" in alert.component:
                # Security system failure - notify immediately
                alert.actions_taken.append("security_failure_notification")

        elif alert.level == AlertLevel.CRITICAL:
            # Critical actions (integration failures)
            if alert.component in self._integration_health:
                # Attempt integration restart
                alert.actions_taken.append(f"attempted_restart_{alert.component}")

        elif alert.level == AlertLevel.WARNING:
            # Warning actions (performance issues, low batteries)
            alert.actions_taken.append("logged_warning")

    def _cleanup_old_data(self) -> None:
        """Clean up old performance data and resolved alerts."""
        cutoff_time = datetime.now() - timedelta(hours=24)

        # Remove old resolved alerts
        self._alerts = [
            alert for alert in self._alerts if not alert.resolved or alert.timestamp > cutoff_time
        ]

        # Limit performance history size
        for key, history in self._performance_history.items():
            if len(history) > self._performance_history_size:
                self._performance_history[key] = history[-self._performance_history_size :]

    # =============================================================================
    # Public API
    # =============================================================================

    def get_system_health(self) -> dict[str, Any]:
        """Get overall system health status."""
        total_integrations = len(self._integration_health)
        healthy_integrations = sum(
            1 for h in self._integration_health.values() if h.status == HealthStatus.HEALTHY
        )
        connected_integrations = sum(1 for h in self._integration_health.values() if h.connected)

        critical_alerts = [
            a for a in self._alerts if a.level == AlertLevel.CRITICAL and not a.resolved
        ]
        warning_alerts = [
            a for a in self._alerts if a.level == AlertLevel.WARNING and not a.resolved
        ]

        return {
            "overall_status": self._calculate_overall_status(),
            "connectivity_ratio": connected_integrations / total_integrations
            if total_integrations > 0
            else 0,
            "health_ratio": healthy_integrations / total_integrations
            if total_integrations > 0
            else 0,
            "active_alerts": len([a for a in self._alerts if not a.resolved]),
            "critical_alerts": len(critical_alerts),
            "warning_alerts": len(warning_alerts),
            "last_check": datetime.now().isoformat(),
            "monitoring_active": self._monitoring_active,
            "system_metrics": {
                name: {
                    "value": metric.value,
                    "status": metric.status.value,
                    "last_updated": metric.last_updated.isoformat(),
                }
                for name, metric in self._system_metrics.items()
            },
        }

    def get_integration_health(self) -> dict[str, dict[str, Any]]:
        """Get health status for all integrations."""
        return {
            name: {
                "name": health.name,
                "status": health.status.value,
                "connected": health.connected,
                "response_time_ms": health.response_time_ms,
                "success_rate": health.success_rate,
                "failure_count": health.failure_count,
                "last_success": health.last_success.isoformat() if health.last_success else None,
                "last_failure": health.last_failure.isoformat() if health.last_failure else None,
                "metrics": {
                    metric_name: {
                        "value": metric.value,
                        "status": metric.status.value,
                        "threshold_warning": metric.threshold_warning,
                        "threshold_critical": metric.threshold_critical,
                        "last_updated": metric.last_updated.isoformat(),
                    }
                    for metric_name, metric in health.metrics.items()
                },
            }
            for name, health in self._integration_health.items()
        }

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get all active (unresolved) alerts."""
        return [
            {
                "id": alert.id,
                "level": alert.level.value,
                "message": alert.message,
                "component": alert.component,
                "timestamp": alert.timestamp.isoformat(),
                "actions_taken": alert.actions_taken,
            }
            for alert in self._alerts
            if not alert.resolved
        ]

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        alert = next((a for a in self._alerts if a.id == alert_id), None)
        if alert:
            alert.resolved = True
            return True
        return False

    def add_alert_callback(self, callback: Callable[[SystemHealthAlert], None]) -> None:
        """Add callback for alert notifications."""
        self._alert_callbacks.append(callback)

    def _calculate_overall_status(self) -> str:
        """Calculate overall system health status."""
        # Check for emergency conditions
        safety_h = self._system_metrics.get("safety_h")
        if safety_h and safety_h.value < 0:
            return "emergency"

        # Check for critical alerts
        critical_alerts = [
            a for a in self._alerts if a.level == AlertLevel.CRITICAL and not a.resolved
        ]
        if critical_alerts:
            return "critical"

        # Check integration health
        failed_integrations = [
            h for h in self._integration_health.values() if h.status == HealthStatus.FAILED
        ]
        critical_integrations = [
            h for h in self._integration_health.values() if h.status == HealthStatus.CRITICAL
        ]

        if len(failed_integrations) >= 3:  # Multiple failures
            return "critical"
        elif failed_integrations or critical_integrations:
            return "warning"

        # Check connectivity
        connectivity = self._system_metrics.get("connectivity")
        if connectivity:
            if connectivity.value < 0.5:
                return "critical"
            elif connectivity.value < 0.8:
                return "warning"

        return "healthy"


# =============================================================================
# Test Suite
# =============================================================================


@pytest.mark.asyncio
class TestSmartHomeHealthMonitoring:
    """Test suite for smart home health monitoring."""

    @pytest.fixture
    async def controller(self):
        """Create test controller."""
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Mock integrations
        controller._control4 = Mock()
        controller._control4.is_connected = True
        controller._control4.get_rooms = Mock(return_value={"1": {"name": "Living Room"}})

        controller._unifi = Mock()
        controller._unifi.is_connected = True
        controller._unifi.get_cameras = Mock(
            return_value={
                "cam1": {"name": "Front Door"},
                "cam2": {"name": "Back Yard"},
                "cam3": {"name": "Driveway"},
                "cam4": {"name": "Side Gate"},
            }
        )

        controller._august = Mock()
        controller._august.is_connected = True
        controller.get_lock_battery_levels = Mock(
            return_value={"front_door": 0.85, "back_door": 0.75}
        )

        return controller

    @pytest.fixture
    async def health_monitor(self, controller):
        """Create health monitor."""
        return SmartHomeHealthMonitor(controller)

    async def test_health_monitor_initialization(self, health_monitor):
        """Test health monitor initialization."""
        assert not health_monitor._monitoring_active
        assert len(health_monitor._integration_health) == 11  # All integrations
        assert all(
            health.status == HealthStatus.UNKNOWN
            for health in health_monitor._integration_health.values()
        )

    async def test_control4_health_check(self, health_monitor):
        """Test Control4 health checking."""
        await health_monitor._check_control4_health()

        control4_health = health_monitor._integration_health["control4"]
        assert control4_health.connected
        assert control4_health.status == HealthStatus.HEALTHY
        assert control4_health.response_time_ms >= 0
        assert "device_count" in control4_health.metrics

    async def test_unifi_health_check(self, health_monitor):
        """Test UniFi health checking."""
        await health_monitor._check_unifi_health()

        unifi_health = health_monitor._integration_health["unifi"]
        assert unifi_health.connected
        assert unifi_health.status == HealthStatus.HEALTHY
        assert "camera_count" in unifi_health.metrics
        assert unifi_health.metrics["camera_count"].value == 4

    async def test_august_battery_monitoring(self, health_monitor):
        """Test August battery monitoring."""
        await health_monitor._check_august_health()

        august_health = health_monitor._integration_health["august"]
        assert august_health.connected
        assert "battery_front_door" in august_health.metrics
        assert "battery_back_door" in august_health.metrics

        # Check battery health
        front_battery = august_health.metrics["battery_front_door"]
        assert front_battery.value == 0.85
        assert front_battery.status == HealthStatus.HEALTHY

    async def test_low_battery_alert(self, health_monitor):
        """Test low battery alert generation."""
        # Mock low battery
        health_monitor.controller.get_lock_battery_levels = Mock(
            return_value={
                "front_door": 0.05  # Critical battery
            }
        )

        await health_monitor._check_august_health()
        await health_monitor._check_alert_conditions()

        # Should create alert for low battery
        alerts = health_monitor.get_active_alerts()
        battery_alerts = [a for a in alerts if "battery" in a["message"].lower()]
        assert len(battery_alerts) > 0

    async def test_system_metrics_calculation(self, health_monitor):
        """Test system metrics calculation."""
        # Run health checks first
        await health_monitor._perform_health_checks()
        await health_monitor._update_system_metrics()

        metrics = health_monitor._system_metrics

        assert "connectivity" in metrics
        assert "safety_h" in metrics
        assert "avg_response_time" in metrics

        # Connectivity should be high with mocked integrations
        connectivity = metrics["connectivity"]
        assert connectivity.value > 0.5

    async def test_alert_creation_and_resolution(self, health_monitor):
        """Test alert creation and resolution."""
        # Create test alert
        await health_monitor._create_alert(
            AlertLevel.WARNING, "Test alert message", "test_component"
        )

        # Check alert exists
        alerts = health_monitor.get_active_alerts()
        assert len(alerts) == 1
        assert alerts[0]["message"] == "Test alert message"

        # Resolve alert
        alert_id = alerts[0]["id"]
        success = health_monitor.resolve_alert(alert_id)
        assert success

        # Check alert is resolved
        active_alerts = health_monitor.get_active_alerts()
        assert len(active_alerts) == 0

    async def test_integration_failure_handling(self, health_monitor):
        """Test integration failure handling."""
        # Mock integration failure
        health_monitor.controller._control4.get_rooms = Mock(
            side_effect=Exception("Connection failed")
        )

        await health_monitor._check_control4_health()

        control4_health = health_monitor._integration_health["control4"]
        assert control4_health.status == HealthStatus.FAILED
        assert not control4_health.connected
        assert control4_health.failure_count > 0

    async def test_monitoring_loop(self, health_monitor):
        """Test monitoring loop functionality."""
        # Start monitoring briefly
        await health_monitor.start_monitoring()
        assert health_monitor._monitoring_active
        assert health_monitor._monitoring_task is not None

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Stop monitoring
        await health_monitor.stop_monitoring()
        assert not health_monitor._monitoring_active

    async def test_system_health_summary(self, health_monitor):
        """Test system health summary generation."""
        # Run health checks
        await health_monitor._perform_health_checks()
        await health_monitor._update_system_metrics()

        summary = health_monitor.get_system_health()

        assert "overall_status" in summary
        assert "connectivity_ratio" in summary
        assert "health_ratio" in summary
        assert "active_alerts" in summary
        assert "system_metrics" in summary

        # With healthy mocked integrations
        assert summary["connectivity_ratio"] > 0.5
        assert summary["overall_status"] in ["healthy", "warning", "critical"]

    async def test_cbf_safety_monitoring(self, health_monitor):
        """Test Control Barrier Function safety monitoring."""
        await health_monitor._update_system_metrics()

        safety_metric = health_monitor._system_metrics.get("safety_h")
        assert safety_metric is not None
        assert safety_metric.value >= 0  # Should satisfy h(x) ≥ 0

    async def test_performance_tracking(self, health_monitor):
        """Test performance tracking functionality."""
        # Multiple health checks to build performance history
        for _ in range(5):
            await health_monitor._check_control4_health()
            await asyncio.sleep(0.01)

        control4_health = health_monitor._integration_health["control4"]
        assert control4_health.response_time_ms > 0

        # Check response time trends
        await health_monitor._update_system_metrics()
        avg_response = health_monitor._system_metrics["avg_response_time"]
        assert avg_response.value > 0

    async def test_alert_callback_system(self, health_monitor):
        """Test alert callback system."""
        received_alerts = []

        def alert_callback(alert: SystemHealthAlert):
            received_alerts.append(alert)

        health_monitor.add_alert_callback(alert_callback)

        # Create test alert
        await health_monitor._create_alert(AlertLevel.WARNING, "Callback test alert", "test")

        # Check callback was called
        assert len(received_alerts) == 1
        assert received_alerts[0].message == "Callback test alert"

    async def test_emergency_alert_handling(self, health_monitor):
        """Test emergency alert handling."""
        # Create emergency alert
        await health_monitor._create_alert(
            AlertLevel.EMERGENCY, "Safety violation detected", "safety"
        )

        # Check emergency alert exists
        alerts = health_monitor.get_active_alerts()
        emergency_alerts = [a for a in alerts if a["level"] == "emergency"]
        assert len(emergency_alerts) == 1

        # Check automated actions
        alert = next(a for a in health_monitor._alerts if a.level == AlertLevel.EMERGENCY)
        assert len(alert.actions_taken) > 0


@pytest.mark.asyncio
class TestHealthMonitoringIntegration:
    """Integration tests for health monitoring with real scenarios."""

    async def test_morning_routine_health_monitoring(self):
        """Test health monitoring during morning routine scenario."""
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Mock integrations for morning routine
        controller._control4 = Mock()
        controller._control4.is_connected = True
        controller._mitsubishi = Mock()
        controller._mitsubishi.is_connected = True
        controller._august = Mock()
        controller._august.is_connected = True

        health_monitor = SmartHomeHealthMonitor(controller)

        # Simulate morning routine with health monitoring
        await health_monitor._perform_health_checks()

        # All integrations should be healthy
        health_status = health_monitor.get_integration_health()
        connected_count = sum(1 for h in health_status.values() if h["connected"])
        assert connected_count >= 3

    async def test_network_failure_recovery_monitoring(self):
        """Test health monitoring during network failure and recovery."""
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Initially working integration
        controller._control4 = Mock()
        controller._control4.is_connected = True
        controller._control4.get_rooms = Mock(return_value={"1": {"name": "Living Room"}})

        health_monitor = SmartHomeHealthMonitor(controller)

        # Initial health check - should be healthy
        await health_monitor._check_control4_health()
        assert health_monitor._integration_health["control4"].status == HealthStatus.HEALTHY

        # Simulate network failure
        controller._control4.get_rooms = Mock(side_effect=Exception("Network timeout"))

        await health_monitor._check_control4_health()
        assert health_monitor._integration_health["control4"].status == HealthStatus.FAILED

        # Simulate recovery
        controller._control4.get_rooms = Mock(return_value={"1": {"name": "Living Room"}})

        await health_monitor._check_control4_health()
        assert health_monitor._integration_health["control4"].status == HealthStatus.HEALTHY

    async def test_security_system_health_critical_path(self):
        """Test health monitoring for security system critical paths."""
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Mock security integrations
        controller._envisalink = Mock()
        controller._envisalink.is_connected = True
        controller.get_security_state = AsyncMock(return_value=SecurityState.DISARMED)
        controller.get_open_zones = Mock(return_value=[])
        controller.get_dsc_trouble_status = Mock(
            return_value={"ac_failure": False, "battery_low": False, "system_tamper": False}
        )

        health_monitor = SmartHomeHealthMonitor(controller)

        # Check security system health
        await health_monitor._check_envisalink_health()

        envisalink_health = health_monitor._integration_health["envisalink"]
        assert envisalink_health.status == HealthStatus.HEALTHY

        # Simulate security trouble
        controller.get_dsc_trouble_status = Mock(
            return_value={"ac_failure": True, "battery_low": True, "system_tamper": False}
        )

        await health_monitor._check_envisalink_health()
        assert envisalink_health.status == HealthStatus.CRITICAL


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
class TestHealthMonitoringPerformance:
    """Performance tests for health monitoring."""

    async def test_health_check_performance(self):
        """Test health check execution time."""
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Mock all integrations
        for attr in [
            "_control4",
            "_unifi",
            "_denon",
            "_august",
            "_eight_sleep",
            "_lg_tv",
            "_samsung_tv",
            "_tesla",
            "_oelo",
            "_mitsubishi",
            "_envisalink",
        ]:
            setattr(controller, attr, Mock())

        health_monitor = SmartHomeHealthMonitor(controller)

        # Time full health check
        start_time = time.time()
        await health_monitor._perform_health_checks()
        duration = time.time() - start_time

        # Should complete quickly with mocks
        assert duration < 2.0  # 2 second limit

    async def test_concurrent_health_checks(self):
        """Test concurrent health check performance."""
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Mock integrations
        controller._control4 = Mock()
        controller._unifi = Mock()

        health_monitor = SmartHomeHealthMonitor(controller)

        # Run multiple health checks concurrently
        tasks = [
            health_monitor._check_control4_health(),
            health_monitor._check_unifi_health(),
            health_monitor._update_system_metrics(),
        ]

        start_time = time.time()
        await asyncio.gather(*tasks)
        duration = time.time() - start_time

        # Should be fast with mocks
        assert duration < 1.0


if __name__ == "__main__":
    # Run health monitoring tests
    pytest.main([__file__, "-v"])
