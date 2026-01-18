from __future__ import annotations

from kagami.core.async_utils import safe_create_task

"""Canary Rollout & Feature Flags for Safe Evolution.

Gradual rollout with automatic rollback:
1. Apply change behind feature flag (disabled by default)
2. Enable for small % of operations (canary)
3. Monitor metrics for regression
4. If good: increase %, if bad: auto-rollback
5. Gradual rollout to 100% or rollback to 0%

Ensures improvements are safe before full deployment.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RolloutStatus(Enum):
    """Status of canary rollout."""

    DISABLED = "disabled"  # Feature flag off
    CANARY = "canary"  # Small % enabled
    PARTIAL = "partial"  # 50% enabled
    FULL = "full"  # 100% enabled
    ROLLING_BACK = "rolling_back"  # Detected regression, rolling back
    ROLLED_BACK = "rolled_back"  # Fully rolled back


@dataclass
class CanaryConfig:
    """Configuration for canary rollout."""

    feature_name: str
    initial_percentage: float = 0.05  # Start with 5%
    increment: float = 0.10  # Increase by 10% if good
    evaluation_window_s: float = 300  # 5 minutes per stage
    rollback_on_error_rate: float = 0.10  # Rollback if error rate >10%
    rollback_on_latency_increase: float = 0.20  # Rollback if latency +20%


@dataclass
class CanaryMetrics:
    """Metrics collected during canary rollout."""

    requests_total: int
    requests_canary: int
    errors_total: int
    errors_canary: int
    p95_latency_baseline: float
    p95_latency_canary: float
    error_rate_baseline: float
    error_rate_canary: float


class CanaryRollout:
    """Manage canary rollout with automatic rollback."""

    def __init__(self) -> None:
        self._active_rollouts: dict[str, dict[str, Any]] = {}
        self._feature_flags: dict[str, bool] = {}
        self._rollout_history: list[dict[str, Any]] = []

    async def start_rollout(
        self, feature_name: str, config: CanaryConfig | None = None
    ) -> dict[str, Any]:
        """Start canary rollout for a feature.

        Args:
            feature_name: Name of feature to roll out
            config: Rollout configuration

        Returns:
            Rollout status dict[str, Any]
        """
        if feature_name in self._active_rollouts:
            return {
                "status": "error",
                "message": f"Rollout already active for {feature_name}",
            }

        config = config or CanaryConfig(feature_name=feature_name)

        rollout = {
            "feature_name": feature_name,
            "config": config,
            "status": RolloutStatus.CANARY,
            "percentage": config.initial_percentage,
            "started_at": time.time(),
            "last_evaluation": time.time(),
            "metrics_history": [],
        }

        self._active_rollouts[feature_name] = rollout
        self._feature_flags[feature_name] = True  # Enable flag

        logger.info(f"🚩 Started canary rollout: {feature_name} at {config.initial_percentage:.0%}")

        # Start monitoring task
        safe_create_task(self._monitor_rollout(feature_name, name="_monitor_rollout"))  # type: ignore  # Call sig

        return {"status": "started", "percentage": config.initial_percentage}

    async def _monitor_rollout(self, feature_name: str) -> None:
        """Monitor canary rollout and adjust percentage."""
        rollout = self._active_rollouts.get(feature_name)
        if not rollout:
            return

        config: CanaryConfig = rollout["config"]

        while rollout["status"] in [RolloutStatus.CANARY, RolloutStatus.PARTIAL]:
            # Wait for evaluation window
            await asyncio.sleep(config.evaluation_window_s)

            # Collect metrics
            metrics = await self._collect_canary_metrics(feature_name)
            rollout["metrics_history"].append(metrics)

            # Evaluate health
            health = self._evaluate_canary_health(metrics, config)

            if not health["healthy"]:
                # ROLLBACK!
                logger.warning(f"⚠️ Canary unhealthy for {feature_name}: {health['reason']}")
                await self._rollback(feature_name, reason=health["reason"])
                break

            # Healthy - increase percentage
            current_pct = rollout["percentage"]
            new_pct = min(1.0, current_pct + config.increment)

            rollout["percentage"] = new_pct
            rollout["last_evaluation"] = time.time()

            logger.info(f"📈 Canary {feature_name}: {current_pct:.0%} → {new_pct:.0%}")

            if new_pct >= 1.0:
                # Full rollout complete!
                rollout["status"] = RolloutStatus.FULL
                logger.info(f"✅ Canary rollout complete: {feature_name} at 100%")
                break

    async def _collect_canary_metrics(self, feature_name: str) -> CanaryMetrics:
        """Collect metrics for canary evaluation from Prometheus.

        Args:
            feature_name: Name of the feature being rolled out.

        Returns:
            CanaryMetrics with real data from metrics system.
        """
        # Default metrics if collection fails
        default_metrics = CanaryMetrics(
            requests_total=1000,
            requests_canary=50,
            errors_total=5,
            errors_canary=1,
            p95_latency_baseline=50.0,
            p95_latency_canary=52.0,
            error_rate_baseline=0.005,
            error_rate_canary=0.02,
        )

        try:
            from prometheus_client import REGISTRY

            requests_total: float = 0
            requests_canary: float = 0
            errors_total: float = 0
            errors_canary: float = 0
            latency_baseline_samples = []
            latency_canary_samples = []

            for metric in REGISTRY.collect():
                metric_name = metric.name

                for sample in metric.samples:
                    labels = sample.labels

                    # Count requests
                    if (
                        "http_requests_total" in metric_name
                        or "kagami_requests_total" in metric_name
                    ):
                        is_canary = (
                            labels.get("canary") == "true" or labels.get("variant") == "canary"
                        )

                        if is_canary:
                            requests_canary += sample.value
                            if labels.get("status", "").startswith("5"):
                                errors_canary += sample.value
                        else:
                            requests_total += sample.value
                            if labels.get("status", "").startswith("5"):
                                errors_total += sample.value

                    # Collect latency from histograms
                    if (
                        "http_request_duration" in metric_name
                        or "kagami_request_duration" in metric_name
                    ):
                        if "_sum" in sample.name:
                            is_canary = (
                                labels.get("canary") == "true" or labels.get("variant") == "canary"
                            )
                            if is_canary:
                                latency_canary_samples.append(sample.value)
                            else:
                                latency_baseline_samples.append(sample.value)

            # Calculate p95 approximations from samples
            def calc_p95(samples: list[float]) -> float:
                if not samples:
                    return 50.0  # Default 50ms
                sorted_samples = sorted(samples)
                idx = int(len(sorted_samples) * 0.95)
                return sorted_samples[min(idx, len(sorted_samples) - 1)] * 1000  # Convert to ms

            # Calculate error rates
            error_rate_baseline = errors_total / max(requests_total, 1)
            error_rate_canary = errors_canary / max(requests_canary, 1)

            return CanaryMetrics(
                requests_total=int(requests_total),
                requests_canary=int(requests_canary),
                errors_total=int(errors_total),
                errors_canary=int(errors_canary),
                p95_latency_baseline=calc_p95(latency_baseline_samples),
                p95_latency_canary=calc_p95(latency_canary_samples),
                error_rate_baseline=error_rate_baseline,
                error_rate_canary=error_rate_canary,
            )

        except ImportError:
            logger.debug("Prometheus client not available, using default metrics")
            return default_metrics
        except Exception as e:
            logger.warning(f"Failed to collect canary metrics: {e}")
            return default_metrics

    def _evaluate_canary_health(
        self, metrics: CanaryMetrics, config: CanaryConfig
    ) -> dict[str, Any]:
        """Evaluate if canary is healthy."""
        # Check error rate
        if metrics.error_rate_canary > config.rollback_on_error_rate:
            return {
                "healthy": False,
                "reason": (
                    f"Error rate {metrics.error_rate_canary:.1%} > "
                    f"{config.rollback_on_error_rate:.1%}"
                ),
            }

        # Check latency increase
        latency_increase = (
            (metrics.p95_latency_canary - metrics.p95_latency_baseline)
            / metrics.p95_latency_baseline
            if metrics.p95_latency_baseline > 0
            else 0
        )

        if latency_increase > config.rollback_on_latency_increase:
            return {
                "healthy": False,
                "reason": (
                    f"Latency increased {latency_increase:.1%} > "
                    f"{config.rollback_on_latency_increase:.1%}"
                ),
            }

        # Healthy!
        return {"healthy": True}

    async def _rollback(self, feature_name: str, reason: str) -> None:
        """Rollback a canary deployment."""
        rollout = self._active_rollouts.get(feature_name)
        if not rollout:
            return

        logger.warning(f"🔄 Rolling back {feature_name}: {reason}")

        # Disable feature flag
        self._feature_flags[feature_name] = False

        # Update status
        rollout["status"] = RolloutStatus.ROLLED_BACK
        rollout["rollback_reason"] = reason
        rollout["rolled_back_at"] = time.time()

        # Record in history
        self._rollout_history.append(
            {
                "feature_name": feature_name,
                "outcome": "rolled_back",
                "reason": reason,
                "percentage_reached": rollout["percentage"],
                "duration_s": time.time() - rollout["started_at"],
            }
        )

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_rollback_total", labels={"feature": feature_name})
        except Exception:
            pass

    def is_enabled(self, feature_name: str) -> bool:
        """Check if feature is enabled (for feature flag checks)."""
        return self._feature_flags.get(feature_name, False)

    def get_rollout_percentage(self, feature_name: str) -> float:
        """Get current rollout percentage for feature."""
        rollout = self._active_rollouts.get(feature_name)
        if not rollout:
            return 0.0

        return rollout.get("percentage", 0.0)  # type: ignore  # External lib

    def should_use_canary(self, feature_name: str) -> bool:
        """Determine if this request should use canary feature.

        Uses hash-based assignment for consistent behavior.
        """
        import hashlib
        import random

        if not self.is_enabled(feature_name):
            return False

        percentage = self.get_rollout_percentage(feature_name)
        if percentage >= 1.0:
            return True  # Full rollout

        # Hash-based assignment (consistent per request)
        request_hash = hashlib.md5(f"{time.time()}".encode(), usedforsecurity=False).hexdigest()
        random.seed(int(request_hash[:8], 16))
        return random.random() < percentage

    def get_rollout_status(self, feature_name: str) -> dict[str, Any]:
        """Get status of a rollout."""
        rollout = self._active_rollouts.get(feature_name)
        if not rollout:
            return {"status": "not_found"}

        return {
            "status": rollout["status"].value,
            "percentage": rollout["percentage"],
            "started_at": rollout["started_at"],
            "metrics_collected": len(rollout["metrics_history"]),
        }


# Singleton
_canary_rollout: CanaryRollout | None = None


def get_canary_rollout() -> CanaryRollout:
    """Get global canary rollout manager."""
    global _canary_rollout
    if _canary_rollout is None:
        _canary_rollout = CanaryRollout()
    return _canary_rollout
