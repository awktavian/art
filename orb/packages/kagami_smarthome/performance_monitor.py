"""Performance Monitoring & Metrics Collection.

Tracks performance metrics across all smart home integrations:
- Connection latency and reliability
- Scene activation timing
- Integration health and uptime
- Resource utilization
- Error rates and patterns

Implements adaptive strategies based on performance data to maintain
sub-100ms scene activation and 99.9% uptime resilience.

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of performance metrics."""

    CONNECTION_LATENCY = "connection_latency"
    SCENE_ACTIVATION_TIME = "scene_activation_time"
    INTEGRATION_UPTIME = "integration_uptime"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    NETWORK_LATENCY = "network_latency"
    RESPONSE_TIME = "response_time"


class SeverityLevel(str, Enum):
    """Performance issue severity levels."""

    CRITICAL = "critical"  # System failure imminent
    HIGH = "high"  # Performance degraded significantly
    MEDIUM = "medium"  # Minor performance impact
    LOW = "low"  # Informational only


@dataclass
class PerformanceMetric:
    """A single performance measurement."""

    metric_type: MetricType
    value: float
    timestamp: float
    integration: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration."""

    metric_type: MetricType
    warning_threshold: float
    critical_threshold: float
    trend_window_minutes: int = 5


@dataclass
class PerformanceAlert:
    """Performance degradation alert."""

    severity: SeverityLevel
    metric_type: MetricType
    integration: str
    current_value: float
    threshold: float
    message: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """Monitors and optimizes smart home system performance.

    Tracks key metrics across all integrations and provides:
    - Real-time performance monitoring
    - Adaptive optimization strategies
    - Predictive degradation detection
    - Automatic failover recommendations

    Performance Targets:
    - Scene activation: <100ms
    - System initialization: <2s
    - Integration uptime: 99.9%
    - Network latency: <50ms
    """

    def __init__(self, max_metrics_per_type: int = 1000):
        self.max_metrics_per_type = max_metrics_per_type

        # Metric storage (in-memory circular buffers)
        self._metrics: dict[MetricType, deque[PerformanceMetric]] = {
            metric_type: deque(maxlen=max_metrics_per_type) for metric_type in MetricType
        }

        # Integration health tracking
        self._integration_status: dict[str, dict[str, Any]] = {}
        self._last_health_check: dict[str, float] = {}

        # Performance thresholds
        self._thresholds = self._default_thresholds()

        # Alert callbacks
        self._alert_callbacks: list[Callable[[PerformanceAlert], None]] = []

        # Background monitoring task
        self._monitor_task: asyncio.Task | None = None
        self._running = False

        # Performance optimization state
        self._optimization_enabled = True
        self._adaptive_strategies: dict[str, Any] = {}

    def _default_thresholds(self) -> dict[MetricType, PerformanceThreshold]:
        """Default performance thresholds for optimal operation."""
        return {
            MetricType.SCENE_ACTIVATION_TIME: PerformanceThreshold(
                metric_type=MetricType.SCENE_ACTIVATION_TIME,
                warning_threshold=100.0,  # 100ms warning
                critical_threshold=500.0,  # 500ms critical
                trend_window_minutes=5,
            ),
            MetricType.CONNECTION_LATENCY: PerformanceThreshold(
                metric_type=MetricType.CONNECTION_LATENCY,
                warning_threshold=50.0,  # 50ms warning
                critical_threshold=200.0,  # 200ms critical
                trend_window_minutes=3,
            ),
            MetricType.RESPONSE_TIME: PerformanceThreshold(
                metric_type=MetricType.RESPONSE_TIME,
                warning_threshold=1000.0,  # 1s warning
                critical_threshold=5000.0,  # 5s critical
                trend_window_minutes=2,
            ),
            MetricType.ERROR_RATE: PerformanceThreshold(
                metric_type=MetricType.ERROR_RATE,
                warning_threshold=0.01,  # 1% warning
                critical_threshold=0.05,  # 5% critical
                trend_window_minutes=10,
            ),
            MetricType.INTEGRATION_UPTIME: PerformanceThreshold(
                metric_type=MetricType.INTEGRATION_UPTIME,
                warning_threshold=0.99,  # 99% warning
                critical_threshold=0.95,  # 95% critical
                trend_window_minutes=60,
            ),
            MetricType.MEMORY_USAGE: PerformanceThreshold(
                metric_type=MetricType.MEMORY_USAGE,
                warning_threshold=80.0,  # 80% warning
                critical_threshold=95.0,  # 95% critical
                trend_window_minutes=5,
            ),
            MetricType.CPU_USAGE: PerformanceThreshold(
                metric_type=MetricType.CPU_USAGE,
                warning_threshold=70.0,  # 70% warning
                critical_threshold=90.0,  # 90% critical
                trend_window_minutes=3,
            ),
        }

    async def start(self) -> None:
        """Start performance monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("📊 Performance monitoring started")

    async def stop(self) -> None:
        """Stop performance monitoring."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("📊 Performance monitoring stopped")

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        integration: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a performance metric."""
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            timestamp=time.time(),
            integration=integration,
            metadata=metadata or {},
        )

        self._metrics[metric_type].append(metric)

        # Check for threshold violations
        self._check_threshold(metric)

        # Update integration health
        self._update_integration_health(integration, metric)

    def _check_threshold(self, metric: PerformanceMetric) -> None:
        """Check if metric violates performance thresholds."""
        threshold = self._thresholds.get(metric.metric_type)
        if not threshold:
            return

        alert = None

        if metric.value >= threshold.critical_threshold:
            alert = PerformanceAlert(
                severity=SeverityLevel.CRITICAL,
                metric_type=metric.metric_type,
                integration=metric.integration,
                current_value=metric.value,
                threshold=threshold.critical_threshold,
                message=f"Critical performance degradation: {metric.metric_type.value} "
                f"reached {metric.value:.1f} (threshold: {threshold.critical_threshold})",
                timestamp=metric.timestamp,
                metadata=metric.metadata,
            )
        elif metric.value >= threshold.warning_threshold:
            alert = PerformanceAlert(
                severity=SeverityLevel.HIGH,
                metric_type=metric.metric_type,
                integration=metric.integration,
                current_value=metric.value,
                threshold=threshold.warning_threshold,
                message=f"Performance warning: {metric.metric_type.value} "
                f"reached {metric.value:.1f} (threshold: {threshold.warning_threshold})",
                timestamp=metric.timestamp,
                metadata=metric.metadata,
            )

        if alert:
            self._trigger_alert(alert)

    def _trigger_alert(self, alert: PerformanceAlert) -> None:
        """Trigger a performance alert."""
        # Reduced to debug to avoid log spam during boot
        logger.debug(f"🚨 Performance Alert: {alert.message}")

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def _update_integration_health(self, integration: str, metric: PerformanceMetric) -> None:
        """Update integration health status."""
        now = time.time()

        if integration not in self._integration_status:
            self._integration_status[integration] = {
                "last_seen": now,
                "error_count": 0,
                "success_count": 0,
                "avg_response_time": 0.0,
                "status": "healthy",
            }

        status = self._integration_status[integration]
        status["last_seen"] = now

        # Update based on metric type
        if metric.metric_type == MetricType.ERROR_RATE:
            if metric.value > 0:
                status["error_count"] += 1
            else:
                status["success_count"] += 1
        elif metric.metric_type == MetricType.RESPONSE_TIME:
            # Exponential moving average
            alpha = 0.1
            status["avg_response_time"] = (
                alpha * metric.value + (1 - alpha) * status["avg_response_time"]
            )

        # Update overall health status
        self._update_integration_health_status(integration)

    def _update_integration_health_status(self, integration: str) -> None:
        """Update overall health status for an integration."""
        status = self._integration_status[integration]
        now = time.time()

        # Check if we haven't heard from the integration recently
        time_since_last_seen = now - status["last_seen"]
        if time_since_last_seen > 300:  # 5 minutes
            status["status"] = "offline"
            return

        # Calculate error rate
        total_operations = status["error_count"] + status["success_count"]
        error_rate = status["error_count"] / max(total_operations, 1)

        # Determine health status
        if error_rate > 0.1:  # >10% error rate
            status["status"] = "degraded"
        elif error_rate > 0.05:  # >5% error rate
            status["status"] = "warning"
        elif status["avg_response_time"] > 2000:  # >2s response time
            status["status"] = "slow"
        else:
            status["status"] = "healthy"

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                await self._perform_health_checks()
                await self._analyze_trends()
                await self._optimize_performance()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance monitor error: {e}")
                await asyncio.sleep(10)

    async def _perform_health_checks(self) -> None:
        """Perform periodic health checks on integrations."""
        now = time.time()

        for integration, status in self._integration_status.items():
            last_check = self._last_health_check.get(integration, 0)

            # Check every 5 minutes
            if now - last_check >= 300:
                self._last_health_check[integration] = now

                # Calculate uptime percentage
                time_since_last_seen = now - status["last_seen"]
                uptime = max(0, 1 - (time_since_last_seen / 3600))  # 1-hour window

                self.record_metric(MetricType.INTEGRATION_UPTIME, uptime, integration)

    async def _analyze_trends(self) -> None:
        """Analyze performance trends and predict issues."""
        for metric_type, threshold in self._thresholds.items():
            metrics = self._get_recent_metrics(metric_type, threshold.trend_window_minutes)

            if len(metrics) < 3:  # Need at least 3 data points
                continue

            # Calculate trend (simple linear regression slope)
            trend = self._calculate_trend(metrics)

            # Predict if we'll hit threshold in next 10 minutes
            if trend > 0:
                current_avg = sum(m.value for m in metrics[-3:]) / 3
                predicted_value = current_avg + (trend * 10)  # 10 minutes ahead

                if predicted_value >= threshold.warning_threshold:
                    # Create predictive alert
                    integration = metrics[-1].integration
                    alert = PerformanceAlert(
                        severity=SeverityLevel.MEDIUM,
                        metric_type=metric_type,
                        integration=integration,
                        current_value=current_avg,
                        threshold=threshold.warning_threshold,
                        message=f"Trend analysis: {metric_type.value} trending toward threshold "
                        f"(predicted: {predicted_value:.1f})",
                        timestamp=time.time(),
                        metadata={"trend": trend, "prediction": predicted_value},
                    )
                    self._trigger_alert(alert)

    def _get_recent_metrics(
        self, metric_type: MetricType, window_minutes: int
    ) -> list[PerformanceMetric]:
        """Get recent metrics within time window."""
        cutoff_time = time.time() - (window_minutes * 60)
        return [m for m in self._metrics[metric_type] if m.timestamp >= cutoff_time]

    def _calculate_trend(self, metrics: list[PerformanceMetric]) -> float:
        """Calculate trend slope for metrics."""
        if len(metrics) < 2:
            return 0.0

        # Simple linear regression
        n = len(metrics)
        sum_x = sum(range(n))
        sum_y = sum(m.value for m in metrics)
        sum_xy = sum(i * m.value for i, m in enumerate(metrics))
        sum_x2 = sum(i * i for i in range(n))

        if n * sum_x2 - sum_x * sum_x == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        return slope

    async def _optimize_performance(self) -> None:
        """Apply adaptive optimization strategies."""
        if not self._optimization_enabled:
            return

        # Analyze current performance bottlenecks
        bottlenecks = self._identify_bottlenecks()

        # Apply optimizations in parallel
        if bottlenecks:
            await asyncio.gather(
                *[self._apply_optimization_strategy(b) for b in bottlenecks], return_exceptions=True
            )

    def _identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify current performance bottlenecks."""
        bottlenecks = []
        now = time.time()

        for integration, status in self._integration_status.items():
            issues = []

            # Check response time
            if status["avg_response_time"] > 1000:
                issues.append(
                    {
                        "type": "slow_response",
                        "value": status["avg_response_time"],
                        "severity": "high" if status["avg_response_time"] > 2000 else "medium",
                    }
                )

            # Check error rate
            total_ops = status["error_count"] + status["success_count"]
            if total_ops > 0:
                error_rate = status["error_count"] / total_ops
                if error_rate > 0.05:
                    issues.append(
                        {
                            "type": "high_error_rate",
                            "value": error_rate,
                            "severity": "critical" if error_rate > 0.1 else "high",
                        }
                    )

            # Check connectivity
            time_since_last_seen = now - status["last_seen"]
            if time_since_last_seen > 60:
                issues.append(
                    {
                        "type": "connectivity_issue",
                        "value": time_since_last_seen,
                        "severity": "critical" if time_since_last_seen > 300 else "high",
                    }
                )

            if issues:
                bottlenecks.append({"integration": integration, "issues": issues, "status": status})

        return bottlenecks

    async def _apply_optimization_strategy(self, bottleneck: dict[str, Any]) -> None:
        """Apply optimization strategy for a bottleneck."""
        integration = bottleneck["integration"]
        issues = bottleneck["issues"]

        for issue in issues:
            strategy_key = f"{integration}:{issue['type']}"

            # Rate limit optimization attempts
            last_attempt = self._adaptive_strategies.get(strategy_key, 0)
            if time.time() - last_attempt < 300:  # 5 minute cooldown
                continue

            self._adaptive_strategies[strategy_key] = time.time()

            if issue["type"] == "slow_response":
                await self._optimize_response_time(integration, issue)
            elif issue["type"] == "high_error_rate":
                await self._optimize_error_rate(integration, issue)
            elif issue["type"] == "connectivity_issue":
                await self._optimize_connectivity(integration, issue)

    async def _optimize_response_time(self, integration: str, issue: dict[str, Any]) -> None:
        """Optimize response time for an integration."""
        logger.info(f"🔧 Optimizing response time for {integration}")

        # Strategies:
        # 1. Increase timeout slightly to reduce failures
        # 2. Reduce polling frequency temporarily
        # 3. Enable connection pooling

        # This would trigger optimization in the actual integration
        # For now, we log the recommendation
        logger.info(
            f"📋 Optimization recommendation for {integration}: "
            f"Increase timeout, reduce polling frequency"
        )

    async def _optimize_error_rate(self, integration: str, issue: dict[str, Any]) -> None:
        """Optimize error rate for an integration."""
        logger.info(f"🔧 Optimizing error rate for {integration}")

        # Strategies:
        # 1. Implement exponential backoff
        # 2. Add circuit breaker pattern
        # 3. Increase retry attempts with jitter

        logger.info(
            f"📋 Optimization recommendation for {integration}: "
            f"Implement exponential backoff and circuit breaker"
        )

    async def _optimize_connectivity(self, integration: str, issue: dict[str, Any]) -> None:
        """Optimize connectivity for an integration."""
        logger.info(f"🔧 Optimizing connectivity for {integration}")

        # Strategies:
        # 1. Trigger immediate reconnection attempt
        # 2. Switch to backup endpoint if available
        # 3. Increase health check frequency temporarily

        logger.info(
            f"📋 Optimization recommendation for {integration}: "
            f"Increase health check frequency, attempt reconnection"
        )

    def on_alert(self, callback: Callable[[PerformanceAlert], None]) -> None:
        """Register callback for performance alerts."""
        self._alert_callbacks.append(callback)

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of current performance metrics."""
        summary = {}
        now = time.time()

        for metric_type, metrics in self._metrics.items():
            if not metrics:
                continue

            # Get recent metrics (last 5 minutes)
            recent = [m for m in metrics if now - m.timestamp <= 300]

            if recent:
                values = [m.value for m in recent]
                summary[metric_type.value] = {
                    "count": len(recent),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": recent[-1].value,
                    "timestamp": recent[-1].timestamp,
                }

        return summary

    def get_integration_health(self) -> dict[str, dict[str, Any]]:
        """Get health status for all integrations."""
        health = {}
        now = time.time()

        for integration, status in self._integration_status.items():
            health[integration] = {
                "status": status["status"],
                "last_seen": status["last_seen"],
                "uptime_seconds": now - status["last_seen"],
                "error_count": status["error_count"],
                "success_count": status["success_count"],
                "avg_response_time_ms": status["avg_response_time"],
                "error_rate": status["error_count"]
                / max(status["error_count"] + status["success_count"], 1),
            }

        return health

    def get_performance_score(self) -> float:
        """Calculate overall system performance score (0-100)."""
        scores = []

        # Integration health scores
        for integration, status in self._integration_status.items():
            if status["status"] == "healthy":
                scores.append(100)
            elif status["status"] == "warning":
                scores.append(80)
            elif status["status"] == "slow":
                scores.append(60)
            elif status["status"] == "degraded":
                scores.append(40)
            else:  # offline
                scores.append(0)

        if not scores:
            return 100.0  # No integrations = perfect score

        return sum(scores) / len(scores)

    def enable_optimization(self, enabled: bool = True) -> None:
        """Enable or disable automatic optimization."""
        self._optimization_enabled = enabled
        logger.info(f"🔧 Adaptive optimization {'enabled' if enabled else 'disabled'}")
