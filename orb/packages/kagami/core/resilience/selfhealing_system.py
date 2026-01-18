from __future__ import annotations

from kagami.core.async_utils import safe_create_task

"""Self-Healing System: Detect, diagnose, and repair autonomously."""
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Anomaly:
    """Detected anomaly."""

    type: str
    severity: str  # "critical"|"warning"|"info"
    metric: str
    current: float
    baseline: float
    detected_at: float


@dataclass
class RepairStep:
    """Single repair step."""

    action: str
    target: str
    params: dict[str, Any] | None = None


@dataclass
class RepairPlan:
    """Plan for repairing an anomaly."""

    steps: list[RepairStep]
    safety_score: float  # 0-1
    rollback_plan: list[RepairStep]
    estimated_downtime_seconds: float = 0.0


@dataclass
class Diagnosis:
    """Root cause diagnosis."""

    anomaly: Anomaly
    likely_causes: list[tuple[Any, ...]]  # (event, causation_score)
    root_cause: dict[str, Any] | None
    confidence: float


class SelfHealingSystem:
    """Autonomous anomaly detection and repair."""

    def __init__(self) -> None:
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._repair_history: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Start continuous monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = safe_create_task(self._monitor_and_heal(), name="_monitor_and_heal")
        logger.info("Self-healing system started")

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_and_heal(self) -> None:
        """Continuous monitoring loop."""
        while self._running:
            try:
                # Check every minute
                await asyncio.sleep(60)

                # Detect anomalies
                anomalies = await self._detect_anomalies()

                for anomaly in anomalies:
                    logger.warning(
                        f"Anomaly detected: {anomaly.type} (severity={anomaly.severity})"
                    )

                    # Diagnose root cause
                    diagnosis = await self._diagnose_root_cause(anomaly)

                    # Generate repair plan
                    repair_plan = await self._generate_repair_plan(diagnosis)

                    # Execute if safe
                    if repair_plan.safety_score > 0.8:
                        logger.info(
                            f"Auto-repairing: {anomaly.type} "
                            f"(safety={repair_plan.safety_score:.2f})"
                        )
                        success = await self._execute_repair(repair_plan)
                        if success:
                            await self._verify_repair(repair_plan, anomaly)
                    else:
                        logger.warning(
                            f"Repair plan unsafe (safety={repair_plan.safety_score:.2f}), "
                            "escalating to human"
                        )
                        await self._escalate_to_human(diagnosis, repair_plan)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Self-healing loop error: {e}", exc_info=True)

    async def _detect_anomalies(self) -> list[Anomaly]:
        """Statistical anomaly detection on metrics."""
        anomalies = []

        # Fetch metrics (would use Prometheus API in real impl)
        try:
            # Check latency spikes
            recent_latency = await self._get_metric_sample(
                "kagami_intent_execute_duration_seconds", window="5m"
            )
            baseline_latency = await self._get_metric_sample(
                "kagami_intent_execute_duration_seconds", window="7d"
            )

            if recent_latency and baseline_latency and recent_latency > baseline_latency * 1.5:
                anomalies.append(
                    Anomaly(
                        type="latency_spike",
                        severity="warning",
                        metric="intent_duration",
                        current=recent_latency,
                        baseline=baseline_latency,
                        detected_at=__import__("time").time(),
                    )
                )

            # Check error rate spikes
            recent_errors = await self._get_error_rate(window="5m")
            baseline_errors = await self._get_error_rate(window="7d")

            if recent_errors and baseline_errors and recent_errors > baseline_errors * 2:
                anomalies.append(
                    Anomaly(
                        type="error_rate_spike",
                        severity="critical",
                        metric="api_errors",
                        current=recent_errors,
                        baseline=baseline_errors,
                        detected_at=__import__("time").time(),
                    )
                )

        except Exception as e:
            logger.debug(f"Anomaly detection error: {e}")

        return anomalies

    async def _diagnose_root_cause(self, anomaly: Anomaly) -> Diagnosis:
        """Causal analysis to find root cause."""
        # Get recent events
        events = await self._get_recent_events(_minutes=15)

        # Find correlated events
        correlated = [e for e in events if abs(e.get("timestamp", 0) - anomaly.detected_at) < 300]

        # Rank by causation likelihood
        causes = []
        for event in correlated:
            score = self._compute_causation_likelihood(event, anomaly)
            if score > 0.6:
                causes.append((event, score))

        causes.sort(key=lambda x: x[1], reverse=True)

        return Diagnosis(
            anomaly=anomaly,
            likely_causes=causes,
            root_cause=causes[0][0] if causes else None,
            confidence=causes[0][1] if causes else 0.0,
        )

    async def _generate_repair_plan(self, diagnosis: Diagnosis) -> RepairPlan:
        """Generate executable repair steps."""
        anomaly_type = diagnosis.anomaly.type

        # Latency spike repairs
        if anomaly_type == "latency_spike":
            return RepairPlan(
                steps=[
                    RepairStep(
                        action="clear_cache",
                        target="redis",
                        params={"pattern": "*"},
                    ),
                    RepairStep(
                        action="restart_workers",
                        target="gunicorn",
                        params={"graceful": True},
                    ),
                ],
                safety_score=0.85,
                rollback_plan=[],
                estimated_downtime_seconds=5.0,
            )

        # Error rate spike repairs
        elif anomaly_type == "error_rate_spike":
            return RepairPlan(
                steps=[
                    RepairStep(
                        action="enable_circuit_breaker",
                        target="downstream_service",
                    ),
                    RepairStep(action="increase_timeout", target="client"),
                ],
                safety_score=0.9,
                rollback_plan=[
                    RepairStep(
                        action="disable_circuit_breaker",
                        target="downstream_service",
                    )
                ],
                estimated_downtime_seconds=0.0,
            )

        # Unknown - low safety
        return RepairPlan(steps=[], safety_score=0.0, rollback_plan=[])

    async def _execute_repair(self, plan: RepairPlan) -> bool:
        """Execute repair plan."""
        try:
            for step in plan.steps:
                logger.info(f"Executing repair: {step.action} on {step.target}")
                # Would actually execute - for now, just log
                await asyncio.sleep(0.1)

            # Record success
            self._repair_history.append(
                {
                    "plan": plan,
                    "result": "success",
                    "timestamp": __import__("time").time(),
                }
            )
            return True

        except Exception as e:
            logger.error(f"Repair execution failed: {e}")

            # Execute rollback
            for step in plan.rollback_plan:
                try:
                    logger.info(f"Rolling back: {step.action}")
                    await asyncio.sleep(0.1)
                except Exception:
                    pass

            return False

    async def _verify_repair(self, plan: RepairPlan, anomaly: Anomaly) -> bool:
        """Verify repair was successful."""
        await asyncio.sleep(60)  # Wait 1 minute

        # Re-check metric
        current = await self._get_metric_sample(anomaly.metric, window="1m")

        # Success if back to baseline
        if current and current < anomaly.baseline * 1.1:
            logger.info(f"Repair verified: {anomaly.type} resolved")
            return True

        logger.warning(f"Repair verification failed: {anomaly.type} persists")
        return False

    async def _escalate_to_human(self, diagnosis: Diagnosis, plan: RepairPlan) -> None:
        """Escalate to human for manual intervention."""
        logger.warning(
            f"Escalating {diagnosis.anomaly.type} to human: safety_score={plan.safety_score:.2f}"
        )

        # Emit escalation event
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            await bus.publish(
                "selfhealing.escalation",
                {
                    "type": "escalation",
                    "anomaly": {
                        "type": diagnosis.anomaly.type,
                        "severity": diagnosis.anomaly.severity,
                        "metric": diagnosis.anomaly.metric,
                    },
                    "diagnosis": {
                        "confidence": diagnosis.confidence,
                        "root_cause": diagnosis.root_cause,
                    },
                    "plan": {
                        "safety_score": plan.safety_score,
                        "steps": len(plan.steps),
                    },
                    "timestamp": __import__("time").time(),
                },
            )
        except Exception as e:
            logger.debug(f"Could not emit escalation: {e}")

    async def _get_metric_sample(self, metric: str, window: str) -> float | None:
        """Get metric value (mock for now)."""
        # Would query Prometheus - simplified
        return 50.0

    async def _get_error_rate(self, window: str) -> float | None:
        """Get error rate."""
        # Would compute from metrics
        return 0.02

    async def _get_recent_events(self, _minutes: int) -> list[dict[str, Any]]:
        """Get recent events."""
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            # Convert E8Event objects to dicts
            events = bus.recent_events(limit=200)
            return [e.to_dict() if hasattr(e, "to_dict") else dict(e.__dict__) for e in events]
        except Exception:
            return []

    def _compute_causation_likelihood(self, event: dict[str, Any], anomaly: Anomaly) -> float:
        """Estimate how likely event caused anomaly."""
        # Simplified causation scoring
        # Temporal proximity
        time_diff = abs(event.get("timestamp", 0) - anomaly.detected_at)
        temporal_score = max(0, 1.0 - time_diff / 600)  # Decay over 10min

        # Type matching
        event_type = event.get("type", "")
        type_score = 0.8 if event_type == "error" else 0.5

        return float((temporal_score + type_score) / 2)
