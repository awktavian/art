"""Flow Recovery Module — Multi-Path Recovery Strategies.

Implements Swallowtail catastrophe dynamics:
- Multiple stable recovery paths (A, B, C)
- Path switching when blocked
- Rollback capabilities

Created: December 28, 2025
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RecoveryPath(Enum):
    """Recovery path options (Swallowtail branches)."""

    PATH_A = "direct_fix"  # Direct fix - fastest
    PATH_B = "workaround"  # Workaround - bypass issue
    PATH_C = "redesign"  # Redesign - fundamental change


@dataclass
class RecoveryStrategy:
    """A recovery strategy definition."""

    name: str
    path: RecoveryPath
    description: str
    steps: list[str]
    estimated_time_seconds: int
    risk_level: float  # 0-1
    rollback_possible: bool = True
    prerequisites: list[str] = field(default_factory=list[Any])

    @property
    def flow_voice(self) -> str:
        return (
            f"There's a path through this... {self.description}. "
            f"It'll take about {self.estimated_time_seconds // 60} minutes. "
            f"{'We can roll back if needed.' if self.rollback_possible else 'No rollback — we commit.'}"
        )


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    success: bool
    strategy_used: RecoveryStrategy
    duration_seconds: float
    steps_completed: int
    error: str | None = None
    rollback_performed: bool = False
    flow_voice: str = ""

    def __post_init__(self) -> None:
        if not self.flow_voice:
            if self.success:
                self.flow_voice = (
                    f"The water found its way. {self.strategy_used.name} succeeded "
                    f"in {self.duration_seconds:.1f} seconds."
                )
            else:
                self.flow_voice = f"This path was blocked... {self.error}. Let me try another way."


# Common recovery strategies
RECOVERY_STRATEGIES = {
    "restart_service": RecoveryStrategy(
        name="Restart Service",
        path=RecoveryPath.PATH_A,
        description="Restart the affected service",
        steps=[
            "Stop service gracefully",
            "Clear temporary state",
            "Start service",
            "Verify health",
        ],
        estimated_time_seconds=60,
        risk_level=0.2,
        rollback_possible=True,
    ),
    "scale_up": RecoveryStrategy(
        name="Scale Up",
        path=RecoveryPath.PATH_A,
        description="Add more capacity",
        steps=[
            "Determine required capacity",
            "Provision new instances",
            "Add to load balancer",
            "Verify traffic distribution",
        ],
        estimated_time_seconds=180,
        risk_level=0.1,
        rollback_possible=True,
    ),
    "rollback_deploy": RecoveryStrategy(
        name="Rollback Deployment",
        path=RecoveryPath.PATH_B,
        description="Revert to previous working version",
        steps=[
            "Identify last known good version",
            "Prepare rollback",
            "Execute deployment rollback",
            "Verify functionality",
        ],
        estimated_time_seconds=300,
        risk_level=0.3,
        rollback_possible=False,  # Already a rollback
    ),
    "circuit_breaker": RecoveryStrategy(
        name="Circuit Breaker",
        path=RecoveryPath.PATH_B,
        description="Enable circuit breaker to isolate failures",
        steps=[
            "Identify failing dependency",
            "Configure circuit breaker",
            "Enable fallback behavior",
            "Monitor recovery",
        ],
        estimated_time_seconds=30,
        risk_level=0.1,
        rollback_possible=True,
    ),
    "failover": RecoveryStrategy(
        name="Failover",
        path=RecoveryPath.PATH_C,
        description="Switch to backup system",
        steps=[
            "Verify backup system health",
            "Update routing",
            "Failover traffic",
            "Verify new system handling load",
            "Investigate primary failure",
        ],
        estimated_time_seconds=600,
        risk_level=0.5,
        rollback_possible=True,
    ),
}


def plan_recovery(
    symptoms: list[str],
    context: dict[str, Any] | None = None,
) -> list[RecoveryStrategy]:
    """Plan recovery strategies based on symptoms.

    Returns 3 strategies (Swallowtail branches):
    - Path A: Direct fix
    - Path B: Workaround
    - Path C: Redesign

    Args:
        symptoms: List of observed symptoms
        context: Additional context

    Returns:
        List of 3 RecoveryStrategies, one per path

    Example:
        strategies = plan_recovery(
            symptoms=["high latency", "error rate up"],
            context={"service": "api"},
        )
    """
    context = context or {}
    symptoms_lower = [s.lower() for s in symptoms]

    strategies: list[RecoveryStrategy] = []

    # Analyze symptoms and select appropriate strategies
    if any("latency" in s or "slow" in s for s in symptoms_lower):
        strategies.append(RECOVERY_STRATEGIES["scale_up"])
        strategies.append(RECOVERY_STRATEGIES["circuit_breaker"])
        strategies.append(RECOVERY_STRATEGIES["failover"])
    elif any("error" in s or "crash" in s or "down" in s for s in symptoms_lower):
        strategies.append(RECOVERY_STRATEGIES["restart_service"])
        strategies.append(RECOVERY_STRATEGIES["rollback_deploy"])
        strategies.append(RECOVERY_STRATEGIES["failover"])
    elif any("deploy" in s or "release" in s for s in symptoms_lower):
        strategies.append(RECOVERY_STRATEGIES["rollback_deploy"])
        strategies.append(RECOVERY_STRATEGIES["circuit_breaker"])
        strategies.append(RECOVERY_STRATEGIES["failover"])
    else:
        # Default recovery paths
        strategies = [
            RECOVERY_STRATEGIES["restart_service"],
            RECOVERY_STRATEGIES["rollback_deploy"],
            RECOVERY_STRATEGIES["failover"],
        ]

    logger.info(
        f"🌊 Flow: Planned {len(strategies)} recovery paths: {[s.path.value for s in strategies]}"
    )

    return strategies[:3]  # Ensure exactly 3 (Swallowtail branches)


async def execute_recovery(
    strategy: RecoveryStrategy,
    incident: Any | None = None,
    step_executor: Callable[[str], Coroutine[Any, Any, bool]] | None = None,
) -> RecoveryResult:
    """Execute a recovery strategy.

    Args:
        strategy: Recovery strategy to execute
        incident: Associated incident (optional)
        step_executor: Custom step executor (optional)

    Returns:
        RecoveryResult with outcome

    Example:
        result = await execute_recovery(strategies[0], incident=incident)
        if not result.success:
            result = await execute_recovery(strategies[1])  # Try next path
    """
    start_time = time.time()
    steps_completed = 0

    logger.info(f"🌊 Flow: Executing {strategy.name} ({strategy.path.value})")

    try:
        for step in strategy.steps:
            logger.info(f"🌊 Flow: Step {steps_completed + 1}: {step}")

            if step_executor:
                success = await step_executor(step)
            else:
                # Simulate step execution
                import asyncio

                await asyncio.sleep(0.1)
                success = True

            if not success:
                raise RuntimeError(f"Step failed: {step}")

            steps_completed += 1

        duration = time.time() - start_time
        return RecoveryResult(
            success=True,
            strategy_used=strategy,
            duration_seconds=duration,
            steps_completed=steps_completed,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"🌊 Flow: Recovery failed at step {steps_completed + 1}: {e}")

        return RecoveryResult(
            success=False,
            strategy_used=strategy,
            duration_seconds=duration,
            steps_completed=steps_completed,
            error=str(e),
        )


async def execute_multi_path_recovery(
    strategies: list[RecoveryStrategy],
    incident: Any | None = None,
    step_executor: Callable[[str], Coroutine[Any, Any, bool]] | None = None,
) -> RecoveryResult:
    """Execute recovery with automatic fallback to next path.

    Implements Swallowtail dynamics: if Path A fails, try Path B, then C.

    Args:
        strategies: List of recovery strategies to try
        incident: Associated incident
        step_executor: Custom step executor

    Returns:
        RecoveryResult from successful strategy or last failure
    """
    for i, strategy in enumerate(strategies):
        logger.info(f"🌊 Flow: Attempting path {i + 1}/{len(strategies)}: {strategy.path.value}")

        result = await execute_recovery(strategy, incident, step_executor)

        if result.success:
            return result

        logger.warning(
            f"🌊 Flow: Path {strategy.path.value} blocked. "
            f"{'Trying next path...' if i < len(strategies) - 1 else 'All paths exhausted.'}"
        )

    return result  # Return last result if all fail


__all__ = [
    "RECOVERY_STRATEGIES",
    "RecoveryPath",
    "RecoveryResult",
    "RecoveryStrategy",
    "execute_multi_path_recovery",
    "execute_recovery",
    "plan_recovery",
]
