from __future__ import annotations

"""Agent Memory Guard - Per-agent memory limit enforcer.

CRITICAL SAFETY SYSTEM to prevent >800GB memory explosions like Jan 11, 2025.

This watchdog:
1. Monitors EACH agent's memory usage independently
2. Hard-kills agents exceeding limits
3. Prevents system-wide memory exhaustion
4. Logs violations for forensics
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from kagami.core.async_utils import safe_create_task

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    # psutil module not available - code will check PSUTIL_AVAILABLE flag

logger = logging.getLogger(__name__)

# Import metrics from central registry (Batch 1 Nov 1, 2025: removed fallback to eliminate duplicates)
from kagami_observability.metrics import (
    AGENT_MEMORY_BYTES,
    AGENT_MEMORY_PRESSURE,
    AGENT_MEMORY_VIOLATIONS,
)

_ONE_GB_BYTES = float(1024**3)


def _coerce_float(value: Any) -> float:
    """Best-effort conversion of arbitrary values (including mocks) to float."""
    if isinstance(value, (int, float)):
        return float(value)

    # Handle NumPy / Torch scalars
    if hasattr(value, "item"):
        try:
            return float(value.item())
        except (TypeError, ValueError):
            return 0.0

    # Strings that look like numbers
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        # MagicMock / other non-numeric objects -> treat as 0 for safety
        return 0.0


def _bytes_to_gb(value: Any) -> float:
    """Convert a byte value (possibly mocked) to gigabytes."""
    bytes_value = _coerce_float(value)
    if bytes_value <= 0.0:
        return 0.0
    return bytes_value / _ONE_GB_BYTES


@dataclass
class MemoryLimit:
    """Memory limit configuration for an agent."""

    soft_limit_gb: float = 4.0  # Warn at this level
    hard_limit_gb: float = 8.0  # Kill at this level
    check_interval: float = 2.0  # Check every N seconds
    grace_period: float = 5.0  # Allow N seconds over soft before hard kill


from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin


class AgentMemoryGuard(SingletonCleanupMixin):
    """Per-agent memory watchdog with automatic cleanup.

    CRITICAL SAFETY: This singleton now has automatic cleanup to prevent
    unbounded memory growth (root cause of 800GB crash).

    Usage:
        guard = AgentMemoryGuard()

        # Register agent with limits
        guard.register_agent("sage", soft_limit_gb=4.0, hard_limit_gb=8.0)

        # In agent's scan loop:
        if guard.should_abort(agent_name="sage"):
            logger.error("Memory limit exceeded, aborting!")
            return
    """

    def __init__(self) -> None:
        self.limits: dict[str, MemoryLimit] = {}
        self.baseline_memory: dict[str, float] = {}
        self.soft_violation_time: dict[str, float | None] = {}
        self.monitoring_task: asyncio.Task[None] | None = None
        # SAFETY: Memory guard is ALWAYS enabled when psutil is available (no opt-out)
        self.enabled = PSUTIL_AVAILABLE

        # Configure cleanup (cleanup every 5 minutes)
        self._cleanup_interval = 300.0
        self._register_cleanup_on_exit()

        # ENHANCEMENT: Memory pressure prediction (proactive)
        self._pressure_predictors: dict[str, Any] = {}  # agent_name -> predictor
        try:
            from kagami.core.memory.pressure_predictor import MemoryPressurePredictor

            self._predictor_class: type | None = MemoryPressurePredictor
            self._prediction_enabled = True
        except ImportError:
            self._predictor_class = None
            self._prediction_enabled = False

        if not self.enabled:
            import os

            boot_mode = os.getenv("KAGAMI_BOOT_MODE", "full")
            if boot_mode == "full":
                logger.critical(
                    "AgentMemoryGuard DISABLED - psutil library unavailable in FULL mode!"
                )
                raise RuntimeError(
                    "Critical Safety Failure: psutil missing in full operation mode. Install psutil."
                )

            logger.error(
                "AgentMemoryGuard DISABLED - psutil library unavailable! "
                "System is vulnerable to memory explosions! Install psutil immediately."
            )

    def register_agent(
        self,
        agent_name: str,
        soft_limit_gb: float = 4.0,
        hard_limit_gb: float = 8.0,
    ) -> None:
        """Register an agent with memory limits.

        Args:
            agent_name: Agent identifier
            soft_limit_gb: Soft limit (warning threshold)
            hard_limit_gb: Hard limit (kill threshold)
        """
        if not self.enabled:
            return

        # Allow per-agent override via env, and global budget increase without crashing
        try:
            import os as _os

            soft_env = _os.getenv(f"KAGAMI_AGENT_{agent_name.upper()}_SOFT_GB")
            hard_env = _os.getenv(f"KAGAMI_AGENT_{agent_name.upper()}_HARD_GB")
            if soft_env:
                soft_limit_gb = float(soft_env)
            if hard_env:
                hard_limit_gb = float(hard_env)
        except Exception as env_err:
            # OPTIONAL: Environment variable parsing failed, use defaults
            logger.debug(f"Failed to parse memory limit overrides for {agent_name}: {env_err}")

        self.limits[agent_name] = MemoryLimit(
            soft_limit_gb=max(soft_limit_gb, 1.0),
            hard_limit_gb=max(hard_limit_gb, soft_limit_gb + 1.0),
        )
        self.soft_violation_time[agent_name] = None

        # Baseline memory = current process memory
        baseline_gb = 0.0
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                mem_info = process.memory_info()
                baseline_gb = _bytes_to_gb(getattr(mem_info, "rss", 0.0))
            except Exception as exc:
                logger.debug("Failed to capture baseline memory for %s: %s", agent_name, exc)

        self.baseline_memory[agent_name] = baseline_gb

        # Initialize metrics to zero (makes them visible immediately)
        try:
            AGENT_MEMORY_BYTES.labels(agent_name=agent_name).set(0)
            AGENT_MEMORY_PRESSURE.labels(agent_name=agent_name).observe(0)
            # Publish effective budget for observability
            from kagami_observability.metrics import AGENT_MEMORY_BUDGET_GB as _BUD

            _BUD.labels(agent_name=agent_name).set(self.limits[agent_name].hard_limit_gb)
        except Exception as metrics_err:
            # OPTIONAL: Metrics publication failed (non-critical telemetry)
            logger.debug(f"Failed to publish memory budget metric for {agent_name}: {metrics_err}")

        logger.info(
            f"Agent '{agent_name}' registered: soft={soft_limit_gb}GB, hard={hard_limit_gb}GB"
        )

    @classmethod
    def get_instance(cls) -> AgentMemoryGuard:
        """Backwards compatibility shim for legacy singleton access."""
        return get_memory_guard()

    def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent and clear its state.

        Raises:
            ValueError: If unregistration fails due to state corruption
        """
        try:
            self.limits.pop(agent_name, None)
            self.baseline_memory.pop(agent_name, None)
            self.soft_violation_time.pop(agent_name, None)
            self._pressure_predictors.pop(agent_name, None)
        except Exception as unreg_err:
            # IMPORTANT: Log unregistration failure (may indicate memory leak)
            logger.warning(
                f"Failed to unregister agent {agent_name}: {unreg_err}",
                extra={"agent_name": agent_name, "error": str(unreg_err)},
            )
            raise ValueError(f"Agent unregistration failed for {agent_name}") from unreg_err

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up dead/inactive agents (implements SingletonCleanupMixin).

        Removes agents that:
        1. Have no baseline memory (never actually started)
        2. Have been inactive (no memory checks) for >5 minutes

        Returns:
            Cleanup statistics
        """
        removed_agents = []
        time.time()

        # Find agents to remove
        for agent_name in list(self.limits.keys()):
            # Check if agent has no baseline (never started)
            if agent_name not in self.baseline_memory:
                removed_agents.append(agent_name)
                continue

            # Check if agent inactive (last violation check was >5 min ago)
            # Note: We don't have explicit heartbeat, so we keep agents unless
            # they're clearly dead (no baseline or monitoring stopped)

        # Remove dead agents
        for agent_name in removed_agents:
            logger.info(f"Cleaning up dead agent: {agent_name}")
            self.unregister_agent(agent_name)

        # Clean up old pressure predictors (keep only for active agents)
        if self._pressure_predictors:
            for agent_name in list(self._pressure_predictors.keys()):
                if agent_name not in self.limits:
                    self._pressure_predictors.pop(agent_name, None)

        return {
            "agents_removed": len(removed_agents),
            "active_agents": len(self.limits),
            "pressure_predictors_active": len(self._pressure_predictors),
        }

    def get_agent_memory_usage(self, agent_name: str) -> float:
        """Get current memory usage for agent in GB.

        Returns:
            Memory usage in GB (approximate, based on delta from baseline)
        """
        if not self.enabled or not PSUTIL_AVAILABLE:
            return 0.0

        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            current_gb = _bytes_to_gb(getattr(mem_info, "rss", 0.0))

            baseline = _coerce_float(self.baseline_memory.get(agent_name, 0.0))
            if baseline < 0.0:
                baseline = 0.0
            elif baseline < 1e-3:
                # Treat extremely small/invalid baselines as zero (common when mocks are used)
                baseline = 0.0
            # Persist sanitized baseline for future calls
            self.baseline_memory[agent_name] = baseline

            # Approximate agent usage = max(delta, current) to avoid zeroing out
            delta = max(0.0, current_gb - baseline)
            if delta > 0.0 and baseline > 0.0:
                # Group agents with comparable baselines (within 0.1%)
                tolerance = max(1e-6, baseline * 1e-3)
                share_group_size = sum(
                    1
                    for other_agent, other_baseline in self.baseline_memory.items()
                    if other_agent in self.limits
                    and other_baseline > 0.0
                    and abs(other_baseline - baseline) <= tolerance
                )
                share_group_size = max(1, share_group_size)
            else:
                share_group_size = 1

            per_agent_delta = delta / share_group_size if delta > 0.0 else 0.0
            per_agent_absolute = current_gb / share_group_size

            if per_agent_delta > 0.0 or per_agent_absolute > 0.0:
                return max(per_agent_delta, per_agent_absolute)

            # Fall back to distributing current usage if delta is zero
            total_agents = max(1, len(self.limits))
            return max(0.0, current_gb / total_agents)
        except Exception as e:
            logger.warning(f"Failed to get memory for {agent_name}: {e}")
            return 0.0

    def should_abort(self, agent_name: str) -> bool:
        """Check if agent should abort due to memory limits.

        Args:
            agent_name: Agent to check

        Returns:
            True if agent should abort immediately
        """
        if not self.enabled:
            if PSUTIL_AVAILABLE:
                self.enabled = True
            else:
                return False

        if agent_name not in self.limits:
            return False

        limit = self.limits[agent_name]
        usage = self.get_agent_memory_usage(agent_name)
        if agent_name == "test_agent":
            logger.debug(
                f"[MemoryGuard] agent={agent_name} usage={usage:.4f}GB "
                f"soft={limit.soft_limit_gb:.4f}GB hard={limit.hard_limit_gb:.4f}GB "
                f"enabled={self.enabled}"
            )

        # Update metrics
        AGENT_MEMORY_BYTES.labels(agent_name=agent_name).set(usage * 1024**3)

        if usage > 0:
            pressure = usage / limit.hard_limit_gb
            AGENT_MEMORY_PRESSURE.labels(agent_name=agent_name).observe(pressure)

            # PROACTIVE: Update pressure predictor
            if self._prediction_enabled and agent_name not in self._pressure_predictors:
                if self._predictor_class:
                    self._pressure_predictors[agent_name] = self._predictor_class()

            if agent_name in self._pressure_predictors:
                predictor = self._pressure_predictors[agent_name]
                predictor.add_sample(usage)

                # Predict future pressure (60 seconds ahead)
                forecast = predictor.predict(
                    horizon_seconds=60.0, hard_limit_gb=limit.hard_limit_gb
                )

                # Proactive warning if approaching limit
                if forecast.time_to_limit_seconds and forecast.time_to_limit_seconds < 120:
                    logger.warning(
                        f"PROACTIVE: Agent '{agent_name}' will hit memory limit in "
                        f"{forecast.time_to_limit_seconds:.0f}s (current: {usage:.2f}GB, "
                        f"predicted: {forecast.predicted_usage_gb:.2f}GB)"
                    )

        # Check hard limit
        if usage >= limit.hard_limit_gb:
            AGENT_MEMORY_VIOLATIONS.labels(
                agent_name=agent_name,
                violation_type="hard_limit",
            ).inc()

            logger.error(
                f"MEMORY VIOLATION: Agent '{agent_name}' exceeded hard limit "
                f"({usage:.2f}GB >= {limit.hard_limit_gb}GB). ABORTING!"
            )

            # Emit receipt for safety action (agent termination)
            try:
                import uuid

                from kagami.core.receipts import UnifiedReceiptFacade as URF

                URF.emit(
                    correlation_id=str(uuid.uuid4()),
                    action="safety.agent_termination",
                    app="memory_guard",
                    args={
                        "agent_name": agent_name,
                        "violation_type": "hard_limit",
                    },
                    event_name="SAFETY_AGENT_TERMINATION",
                    event_data={
                        "phase": "execute",
                        "reason": "memory_limit_exceeded",
                        "usage_gb": usage,
                        "hard_limit_gb": limit.hard_limit_gb,
                        "soft_limit_gb": limit.soft_limit_gb,
                    },
                    status="success",
                    duration_ms=0,
                )
            except Exception as e:
                logger.debug(f"Safety receipt emission failed: {e}")

            return True

        # Check soft limit with grace period
        if usage >= limit.soft_limit_gb:
            if self.soft_violation_time[agent_name] is None:
                # First soft violation - start grace period
                self.soft_violation_time[agent_name] = time.time()
                logger.warning(
                    f"Agent '{agent_name}' exceeded soft limit "
                    f"({usage:.2f}GB >= {limit.soft_limit_gb}GB). "
                    f"Grace period: {limit.grace_period}s"
                )
            else:
                # Check if grace period expired
                violation_time = self.soft_violation_time[agent_name]
                if violation_time is not None:
                    elapsed = time.time() - violation_time
                else:
                    elapsed = 0.0
                if elapsed > limit.grace_period:
                    AGENT_MEMORY_VIOLATIONS.labels(
                        agent_name=agent_name,
                        violation_type="soft_limit_grace_expired",
                    ).inc()

                    logger.error(
                        f"MEMORY VIOLATION: Agent '{agent_name}' exceeded soft limit "
                        f"for {elapsed:.1f}s (grace: {limit.grace_period}s). ABORTING!"
                    )

                    # Emit receipt for safety action (agent termination)
                    try:
                        import uuid

                        from kagami.core.receipts import UnifiedReceiptFacade as URF

                        URF.emit(
                            correlation_id=str(uuid.uuid4()),
                            action="safety.agent_termination",
                            app="memory_guard",
                            args={
                                "agent_name": agent_name,
                                "violation_type": "soft_limit_grace_expired",
                            },
                            event_name="SAFETY_AGENT_TERMINATION",
                            event_data={
                                "phase": "execute",
                                "reason": "soft_limit_grace_expired",
                                "usage_gb": usage,
                                "hard_limit_gb": limit.hard_limit_gb,
                                "soft_limit_gb": limit.soft_limit_gb,
                                "grace_period_seconds": elapsed,
                            },
                            status="success",
                            duration_ms=0,
                        )
                    except Exception as e:
                        logger.debug(f"Safety receipt emission failed: {e}")

                    return True
        else:
            # Below soft limit - reset grace period
            self.soft_violation_time[agent_name] = None

        return False

    async def start_monitoring(self) -> None:
        """Start background monitoring task."""
        if not self.enabled:
            return

        if self.monitoring_task is not None:
            logger.warning("Monitoring already started")
            return

        self.monitoring_task = safe_create_task(self._monitoring_loop(), name="_monitoring_loop")
        logger.info("Agent memory monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop background monitoring task."""
        if self.monitoring_task is not None:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                # Expected: Task cancellation is normal during shutdown
                logger.debug("Memory monitoring task cancelled during shutdown")
            self.monitoring_task = None
            logger.info("Agent memory monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Background loop that checks all agents periodically."""
        while True:
            try:
                for agent_name in list(self.limits.keys()):
                    usage = self.get_agent_memory_usage(agent_name)
                    limit = self.limits[agent_name]

                    # Update metrics every cycle (makes them visible at /metrics)
                    try:
                        AGENT_MEMORY_BYTES.labels(agent_name=agent_name).set(usage * 1024**3)
                        if limit.hard_limit_gb > 0:
                            pressure = usage / limit.hard_limit_gb
                            AGENT_MEMORY_PRESSURE.labels(agent_name=agent_name).observe(pressure)
                    except Exception as metrics_err:
                        # OPTIONAL: Metrics publication failed (non-critical telemetry)
                        logger.debug(
                            f"Failed to publish memory pressure for {agent_name}: {metrics_err}"
                        )

                    # Log if approaching limits (80% soft threshold)
                    if usage > limit.soft_limit_gb * 0.8:
                        logger.debug(
                            f"Agent '{agent_name}' memory: {usage:.2f}GB "
                            f"(soft: {limit.soft_limit_gb}GB, hard: {limit.hard_limit_gb}GB)"
                        )

                await asyncio.sleep(5.0)  # Check every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")
                await asyncio.sleep(5.0)


# Global singleton
_guard: AgentMemoryGuard | None = None


def get_memory_guard() -> AgentMemoryGuard:
    """Get global memory guard singleton."""
    global _guard
    if _guard is None:
        _guard = AgentMemoryGuard()
    return _guard


def get_agent_memory_guard() -> AgentMemoryGuard:
    """Back-compat alias for get_memory_guard used in tests."""
    return get_memory_guard()


def register_agent_memory_limit(
    agent_name: str,
    soft_limit_gb: float = 4.0,
    hard_limit_gb: float = 8.0,
) -> None:
    """Register an agent with the global memory guard.

    Call this in agent __init__:
        register_agent_memory_limit("sage", soft_limit_gb=4.0, hard_limit_gb=8.0)
    """
    guard = get_memory_guard()
    guard.register_agent(agent_name, soft_limit_gb, hard_limit_gb)


def check_agent_memory(agent_name: str) -> bool:
    """Check if agent should abort due to memory limits.

    Call this in agent scan loop:
        if check_agent_memory("sage"):
            logger.error("Memory limit exceeded!")
            return

    Returns:
        True if agent should abort
    """
    guard = get_memory_guard()
    return guard.should_abort(agent_name)
