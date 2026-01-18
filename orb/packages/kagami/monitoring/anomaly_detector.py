"""Anomaly Detection for System Metrics.

Advanced anomaly detection using statistical and machine learning techniques:
- Time series anomaly detection
- Multi-dimensional metric correlation
- Seasonal pattern recognition
- Threshold-based detection
- Statistical outlier identification
- Adaptive baselines and learning

Enables predictive monitoring and early warning systems.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies detected."""

    THRESHOLD = "threshold"  # Simple threshold violation
    STATISTICAL = "statistical"  # Statistical outlier (z-score)
    SEASONAL = "seasonal"  # Deviation from seasonal pattern
    TREND = "trend"  # Unexpected trend change
    CORRELATION = "correlation"  # Correlation break between metrics
    SPIKE = "spike"  # Sudden sharp increase
    DROP = "drop"  # Sudden sharp decrease


class Severity(str, Enum):
    """Anomaly severity levels."""

    LOW = "low"  # Minor deviation
    MEDIUM = "medium"  # Moderate anomaly
    HIGH = "high"  # Significant anomaly
    CRITICAL = "critical"  # Severe anomaly requiring immediate attention


@dataclass
class MetricPoint:
    """A single metric data point."""

    timestamp: float
    value: float
    metric_name: str
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Anomaly:
    """Detected anomaly."""

    metric_name: str
    anomaly_type: AnomalyType
    severity: Severity
    timestamp: float
    actual_value: float
    expected_value: float | None
    deviation: float
    confidence: float
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricBaseline:
    """Baseline statistics for a metric."""

    metric_name: str
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    sample_count: int
    last_updated: float
    seasonal_patterns: dict[str, float] = field(default_factory=dict)


class AnomalyDetector:
    """Advanced anomaly detection system for production monitoring.

    Features:
    - Multi-algorithm anomaly detection
    - Adaptive baselines with learning
    - Seasonal pattern recognition
    - Metric correlation analysis
    - Real-time alerting
    - False positive suppression
    """

    def __init__(self, max_data_points: int = 50000):
        self.max_data_points = max_data_points

        # Data storage
        self._metric_data: dict[str, deque[MetricPoint]] = defaultdict(
            lambda: deque(maxlen=max_data_points // 10)  # Roughly 5000 points per metric
        )

        # Baselines and models
        self._baselines: dict[str, MetricBaseline] = {}
        self._metric_correlations: dict[tuple[str, str], float] = {}

        # Detection configuration
        self._detection_config: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "enabled": True,
                "threshold_factor": 3.0,  # Standard deviations for threshold
                "min_data_points": 50,
                "learning_rate": 0.1,
                "seasonal_detection": True,
                "correlation_detection": True,
            }
        )

        # Anomaly storage
        self._anomalies: deque[Anomaly] = deque(maxlen=10000)
        self._recent_anomalies: dict[str, deque[Anomaly]] = defaultdict(lambda: deque(maxlen=100))

        # Monitoring state
        self._running = False
        self._detection_task: asyncio.Task | None = None

        # Suppression to avoid alert spam
        self._suppression_windows: dict[str, float] = defaultdict(float)

        # Callbacks for anomaly alerts
        self._anomaly_callbacks: list[Callable[[Anomaly], None]] = []

        # Performance optimization
        self._last_baseline_update: dict[str, float] = {}
        self._baseline_update_interval = 300  # 5 minutes

    async def start(self) -> None:
        """Start anomaly detection."""
        if self._running:
            return

        self._running = True
        self._detection_task = asyncio.create_task(self._detection_loop())
        logger.info("🔍 Anomaly detector started")

    async def stop(self) -> None:
        """Stop anomaly detection."""
        self._running = False

        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass

        logger.info("🔍 Anomaly detector stopped")

    def add_metric_point(
        self,
        metric_name: str,
        value: float,
        timestamp: float | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Add a new metric data point."""
        if timestamp is None:
            timestamp = time.time()

        point = MetricPoint(
            timestamp=timestamp, value=value, metric_name=metric_name, tags=tags or {}
        )

        self._metric_data[metric_name].append(point)

        # Update baseline if needed
        self._maybe_update_baseline(metric_name)

        # Run detection on new point
        if self._detection_config[metric_name]["enabled"]:
            self._detect_anomalies_for_point(point)

    def _maybe_update_baseline(self, metric_name: str) -> None:
        """Update baseline if enough time has passed."""
        now = time.time()
        last_update = self._last_baseline_update.get(metric_name, 0)

        if now - last_update >= self._baseline_update_interval:
            self._update_baseline(metric_name)
            self._last_baseline_update[metric_name] = now

    def _update_baseline(self, metric_name: str) -> None:
        """Update baseline statistics for a metric."""
        data_points = self._metric_data[metric_name]
        config = self._detection_config[metric_name]

        if len(data_points) < config["min_data_points"]:
            return

        # Calculate basic statistics
        values = [p.value for p in data_points]
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        min_value = min(values)
        max_value = max(values)

        # Update existing baseline or create new one
        if metric_name in self._baselines:
            baseline = self._baselines[metric_name]
            learning_rate = config["learning_rate"]

            # Exponential moving average
            baseline.mean = baseline.mean * (1 - learning_rate) + mean * learning_rate
            baseline.std_dev = baseline.std_dev * (1 - learning_rate) + std_dev * learning_rate
            baseline.min_value = min(baseline.min_value, min_value)
            baseline.max_value = max(baseline.max_value, max_value)
            baseline.sample_count += len(values)
            baseline.last_updated = time.time()
        else:
            baseline = MetricBaseline(
                metric_name=metric_name,
                mean=mean,
                std_dev=std_dev,
                min_value=min_value,
                max_value=max_value,
                sample_count=len(values),
                last_updated=time.time(),
            )
            self._baselines[metric_name] = baseline

        # Update seasonal patterns if enabled
        if config["seasonal_detection"]:
            self._update_seasonal_patterns(metric_name, data_points)

    def _update_seasonal_patterns(self, metric_name: str, data_points: deque[MetricPoint]) -> None:
        """Update seasonal pattern detection."""
        if len(data_points) < 100:  # Need enough data for patterns
            return

        baseline = self._baselines[metric_name]

        # Group by hour of day for daily patterns
        hourly_values = defaultdict(list)
        for point in data_points:
            hour = int(time.localtime(point.timestamp).tm_hour)
            hourly_values[hour].append(point.value)

        # Calculate average for each hour
        for hour, values in hourly_values.items():
            if len(values) >= 3:  # At least 3 data points
                baseline.seasonal_patterns[f"hour_{hour}"] = statistics.mean(values)

    def _detect_anomalies_for_point(self, point: MetricPoint) -> None:
        """Detect anomalies for a single data point."""
        metric_name = point.metric_name
        config = self._detection_config[metric_name]

        if metric_name not in self._baselines:
            return  # No baseline yet

        baseline = self._baselines[metric_name]
        anomalies = []

        # Threshold-based detection
        anomaly = self._detect_threshold_anomaly(point, baseline, config)
        if anomaly:
            anomalies.append(anomaly)

        # Statistical outlier detection
        anomaly = self._detect_statistical_anomaly(point, baseline, config)
        if anomaly:
            anomalies.append(anomaly)

        # Seasonal anomaly detection
        if config["seasonal_detection"]:
            anomaly = self._detect_seasonal_anomaly(point, baseline)
            if anomaly:
                anomalies.append(anomaly)

        # Spike/drop detection
        anomaly = self._detect_spike_drop_anomaly(point, metric_name)
        if anomaly:
            anomalies.append(anomaly)

        # Process detected anomalies
        for anomaly in anomalies:
            self._process_anomaly(anomaly)

    def _detect_threshold_anomaly(
        self, point: MetricPoint, baseline: MetricBaseline, config: dict[str, Any]
    ) -> Anomaly | None:
        """Detect simple threshold-based anomalies."""
        threshold_factor = config["threshold_factor"]

        if baseline.std_dev == 0:
            return None  # No variability

        upper_threshold = baseline.mean + (threshold_factor * baseline.std_dev)
        lower_threshold = baseline.mean - (threshold_factor * baseline.std_dev)

        if point.value > upper_threshold:
            deviation = point.value - upper_threshold
            severity = self._calculate_severity(deviation, baseline.std_dev)

            return Anomaly(
                metric_name=point.metric_name,
                anomaly_type=AnomalyType.THRESHOLD,
                severity=severity,
                timestamp=point.timestamp,
                actual_value=point.value,
                expected_value=baseline.mean,
                deviation=deviation,
                confidence=min(0.99, deviation / baseline.std_dev / 10),
                message=f"Value {point.value:.2f} exceeds upper threshold {upper_threshold:.2f}",
                metadata={"threshold": upper_threshold, "baseline_mean": baseline.mean},
            )

        elif point.value < lower_threshold:
            deviation = lower_threshold - point.value
            severity = self._calculate_severity(deviation, baseline.std_dev)

            return Anomaly(
                metric_name=point.metric_name,
                anomaly_type=AnomalyType.THRESHOLD,
                severity=severity,
                timestamp=point.timestamp,
                actual_value=point.value,
                expected_value=baseline.mean,
                deviation=deviation,
                confidence=min(0.99, deviation / baseline.std_dev / 10),
                message=f"Value {point.value:.2f} below lower threshold {lower_threshold:.2f}",
                metadata={"threshold": lower_threshold, "baseline_mean": baseline.mean},
            )

        return None

    def _detect_statistical_anomaly(
        self, point: MetricPoint, baseline: MetricBaseline, config: dict[str, Any]
    ) -> Anomaly | None:
        """Detect statistical outliers using z-score."""
        if baseline.std_dev == 0:
            return None

        z_score = abs(point.value - baseline.mean) / baseline.std_dev

        # Z-score threshold (3 sigma = 99.7% confidence)
        z_threshold = 3.0

        if z_score > z_threshold:
            severity = self._calculate_severity_from_zscore(z_score)

            return Anomaly(
                metric_name=point.metric_name,
                anomaly_type=AnomalyType.STATISTICAL,
                severity=severity,
                timestamp=point.timestamp,
                actual_value=point.value,
                expected_value=baseline.mean,
                deviation=abs(point.value - baseline.mean),
                confidence=min(0.999, (z_score - z_threshold) / 10),
                message=f"Statistical outlier: z-score {z_score:.2f}",
                metadata={
                    "z_score": z_score,
                    "baseline_mean": baseline.mean,
                    "baseline_std": baseline.std_dev,
                },
            )

        return None

    def _detect_seasonal_anomaly(
        self, point: MetricPoint, baseline: MetricBaseline
    ) -> Anomaly | None:
        """Detect seasonal pattern anomalies."""
        hour = int(time.localtime(point.timestamp).tm_hour)
        expected_key = f"hour_{hour}"

        if expected_key not in baseline.seasonal_patterns:
            return None

        expected_value = baseline.seasonal_patterns[expected_key]
        deviation = abs(point.value - expected_value)

        # Use a smaller threshold for seasonal detection
        if baseline.std_dev > 0:
            seasonal_threshold = baseline.std_dev * 2.0

            if deviation > seasonal_threshold:
                severity = self._calculate_severity(deviation, baseline.std_dev)

                return Anomaly(
                    metric_name=point.metric_name,
                    anomaly_type=AnomalyType.SEASONAL,
                    severity=severity,
                    timestamp=point.timestamp,
                    actual_value=point.value,
                    expected_value=expected_value,
                    deviation=deviation,
                    confidence=min(0.95, deviation / seasonal_threshold),
                    message=f"Seasonal pattern deviation at hour {hour}",
                    metadata={"expected_seasonal": expected_value, "hour": hour},
                )

        return None

    def _detect_spike_drop_anomaly(self, point: MetricPoint, metric_name: str) -> Anomaly | None:
        """Detect sudden spikes or drops."""
        data_points = self._metric_data[metric_name]

        if len(data_points) < 3:
            return None

        # Get recent points
        recent_points = list(data_points)[-3:]
        current = recent_points[-1]
        previous = recent_points[-2]

        # Calculate rate of change
        time_diff = current.timestamp - previous.timestamp
        if time_diff <= 0:
            return None

        rate_of_change = abs(current.value - previous.value) / time_diff

        # Calculate baseline rate of change
        if len(data_points) >= 10:
            baseline_rates = []
            for i in range(1, min(len(data_points), 10)):
                prev_point = data_points[-i - 1]
                curr_point = data_points[-i]
                dt = curr_point.timestamp - prev_point.timestamp
                if dt > 0:
                    baseline_rates.append(abs(curr_point.value - prev_point.value) / dt)

            if baseline_rates:
                avg_rate = statistics.mean(baseline_rates)
                rate_std = statistics.stdev(baseline_rates) if len(baseline_rates) > 1 else 0

                spike_threshold = avg_rate + (3 * rate_std)

                if rate_of_change > spike_threshold:
                    anomaly_type = (
                        AnomalyType.SPIKE if current.value > previous.value else AnomalyType.DROP
                    )
                    severity = self._calculate_severity(rate_of_change - spike_threshold, rate_std)

                    return Anomaly(
                        metric_name=point.metric_name,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        timestamp=point.timestamp,
                        actual_value=point.value,
                        expected_value=previous.value,
                        deviation=abs(current.value - previous.value),
                        confidence=min(0.95, (rate_of_change - spike_threshold) / spike_threshold),
                        message=f"Sudden {'spike' if anomaly_type == AnomalyType.SPIKE else 'drop'}: "
                        f"rate {rate_of_change:.2f} vs baseline {avg_rate:.2f}",
                        metadata={"rate_of_change": rate_of_change, "baseline_rate": avg_rate},
                    )

        return None

    def _calculate_severity(self, deviation: float, baseline_std: float) -> Severity:
        """Calculate anomaly severity based on deviation."""
        if baseline_std == 0:
            return Severity.MEDIUM

        severity_ratio = deviation / baseline_std

        if severity_ratio >= 5.0:
            return Severity.CRITICAL
        elif severity_ratio >= 3.0:
            return Severity.HIGH
        elif severity_ratio >= 2.0:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    def _calculate_severity_from_zscore(self, z_score: float) -> Severity:
        """Calculate severity from z-score."""
        if z_score >= 5.0:
            return Severity.CRITICAL
        elif z_score >= 4.0:
            return Severity.HIGH
        elif z_score >= 3.0:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    def _process_anomaly(self, anomaly: Anomaly) -> None:
        """Process a detected anomaly."""
        # Check suppression
        suppression_key = f"{anomaly.metric_name}:{anomaly.anomaly_type.value}"
        now = time.time()

        if suppression_key in self._suppression_windows:
            if now - self._suppression_windows[suppression_key] < 300:  # 5 minute suppression
                return

        # Store anomaly
        self._anomalies.append(anomaly)
        self._recent_anomalies[anomaly.metric_name].append(anomaly)

        # Set suppression window
        self._suppression_windows[suppression_key] = now

        # Log anomaly
        logger.warning(
            f"🚨 Anomaly detected in {anomaly.metric_name}: {anomaly.message} "
            f"(severity: {anomaly.severity.value}, confidence: {anomaly.confidence:.2f})"
        )

        # Trigger callbacks
        for callback in self._anomaly_callbacks:
            try:
                callback(anomaly)
            except Exception as e:
                logger.error(f"Anomaly callback error: {e}")

    async def _detection_loop(self) -> None:
        """Main detection loop for correlation analysis."""
        while self._running:
            try:
                # Update metric correlations
                self._update_metric_correlations()

                # Detect correlation anomalies
                self._detect_correlation_anomalies()

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Anomaly detection loop error: {e}")
                await asyncio.sleep(30)

    def _update_metric_correlations(self) -> None:
        """Update correlations between metrics."""
        metric_names = list(self._metric_data.keys())

        for i, metric1 in enumerate(metric_names):
            for metric2 in metric_names[i + 1 :]:
                correlation = self._calculate_correlation(metric1, metric2)
                if correlation is not None:
                    self._metric_correlations[(metric1, metric2)] = correlation

    def _calculate_correlation(self, metric1: str, metric2: str) -> float | None:
        """Calculate correlation coefficient between two metrics."""
        data1 = self._metric_data[metric1]
        data2 = self._metric_data[metric2]

        if len(data1) < 10 or len(data2) < 10:
            return None

        # Align data points by timestamp (approximate)
        aligned_pairs = []

        for point1 in list(data1)[-50:]:  # Last 50 points
            closest_point2 = None
            min_time_diff = float("inf")

            for point2 in data2:
                time_diff = abs(point1.timestamp - point2.timestamp)
                if time_diff < min_time_diff and time_diff < 60:  # Within 1 minute
                    min_time_diff = time_diff
                    closest_point2 = point2

            if closest_point2:
                aligned_pairs.append((point1.value, closest_point2.value))

        if len(aligned_pairs) < 10:
            return None

        # Calculate Pearson correlation
        values1 = [pair[0] for pair in aligned_pairs]
        values2 = [pair[1] for pair in aligned_pairs]

        try:
            correlation = np.corrcoef(values1, values2)[0, 1]
            return correlation if not np.isnan(correlation) else None
        except Exception:
            return None

    def _detect_correlation_anomalies(self) -> None:
        """Detect when metric correlations break down."""
        # This would detect when previously correlated metrics diverge
        # Implementation would compare current correlation with historical baseline
        pass

    def on_anomaly(self, callback: Callable[[Anomaly], None]) -> None:
        """Register callback for anomaly detection."""
        self._anomaly_callbacks.append(callback)

    def configure_metric(
        self,
        metric_name: str,
        threshold_factor: float = 3.0,
        min_data_points: int = 50,
        learning_rate: float = 0.1,
        enabled: bool = True,
    ) -> None:
        """Configure anomaly detection for a specific metric."""
        self._detection_config[metric_name].update(
            {
                "threshold_factor": threshold_factor,
                "min_data_points": min_data_points,
                "learning_rate": learning_rate,
                "enabled": enabled,
            }
        )

    def get_recent_anomalies(
        self, metric_name: str | None = None, limit: int = 100
    ) -> list[Anomaly]:
        """Get recent anomalies for a metric or all metrics."""
        if metric_name:
            return list(self._recent_anomalies[metric_name])[-limit:]
        else:
            return list(self._anomalies)[-limit:]

    def get_anomaly_summary(self) -> dict[str, Any]:
        """Get comprehensive anomaly detection summary."""
        now = time.time()

        # Count anomalies by severity in last hour
        recent_anomalies = [a for a in self._anomalies if now - a.timestamp <= 3600]

        severity_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for anomaly in recent_anomalies:
            severity_counts[anomaly.severity.value] += 1
            type_counts[anomaly.anomaly_type.value] += 1

        # Get metrics with most anomalies
        metric_anomaly_counts = defaultdict(int)
        for anomaly in recent_anomalies:
            metric_anomaly_counts[anomaly.metric_name] += 1

        top_noisy_metrics = sorted(metric_anomaly_counts.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]

        return {
            "total_anomalies_last_hour": len(recent_anomalies),
            "severity_counts": dict(severity_counts),
            "type_counts": dict(type_counts),
            "monitored_metrics": len(self._metric_data),
            "baselines_established": len(self._baselines),
            "metric_correlations": len(self._metric_correlations),
            "top_noisy_metrics": top_noisy_metrics,
            "detection_running": self._running,
            "total_data_points": sum(len(data) for data in self._metric_data.values()),
        }

    def get_metric_baseline(self, metric_name: str) -> MetricBaseline | None:
        """Get baseline information for a metric."""
        return self._baselines.get(metric_name)

    def get_metric_health_score(self, metric_name: str) -> float:
        """Calculate health score for a metric (0-100)."""
        recent_anomalies = self.get_recent_anomalies(metric_name, limit=10)

        if not recent_anomalies:
            return 100.0

        # Count critical and high severity anomalies
        critical_count = sum(1 for a in recent_anomalies if a.severity == Severity.CRITICAL)
        high_count = sum(1 for a in recent_anomalies if a.severity == Severity.HIGH)

        # Decrease score based on anomaly severity
        score = 100.0
        score -= critical_count * 20  # -20 per critical
        score -= high_count * 10  # -10 per high
        score -= (len(recent_anomalies) - critical_count - high_count) * 5  # -5 per other

        return max(0.0, score)

    def reset_baselines(self) -> None:
        """Reset all baselines for relearning."""
        self._baselines.clear()
        self._last_baseline_update.clear()
        logger.info("🔍 All anomaly detection baselines reset")

    def export_anomaly_report(self, start_time: float, end_time: float) -> dict[str, Any]:
        """Export detailed anomaly report for time period."""
        anomalies_in_period = [a for a in self._anomalies if start_time <= a.timestamp <= end_time]

        report = {
            "period": {
                "start_time": start_time,
                "end_time": end_time,
                "duration_hours": (end_time - start_time) / 3600,
            },
            "summary": {
                "total_anomalies": len(anomalies_in_period),
                "unique_metrics": len({a.metric_name for a in anomalies_in_period}),
                "severity_breakdown": {},
                "type_breakdown": {},
            },
            "anomalies": [],
        }

        # Calculate breakdowns
        severity_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for anomaly in anomalies_in_period:
            severity_counts[anomaly.severity.value] += 1
            type_counts[anomaly.anomaly_type.value] += 1

            # Add to detailed list
            report["anomalies"].append(
                {
                    "timestamp": anomaly.timestamp,
                    "metric_name": anomaly.metric_name,
                    "type": anomaly.anomaly_type.value,
                    "severity": anomaly.severity.value,
                    "actual_value": anomaly.actual_value,
                    "expected_value": anomaly.expected_value,
                    "deviation": anomaly.deviation,
                    "confidence": anomaly.confidence,
                    "message": anomaly.message,
                    "metadata": anomaly.metadata,
                }
            )

        report["summary"]["severity_breakdown"] = dict(severity_counts)
        report["summary"]["type_breakdown"] = dict(type_counts)

        return report


# Global anomaly detector instance
_global_detector: AnomalyDetector | None = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get the global anomaly detector instance."""
    global _global_detector
    if _global_detector is None:
        _global_detector = AnomalyDetector()

    return _global_detector
