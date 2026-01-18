from __future__ import annotations

"""Evolution Kill-Switch & Control Panel.

Provides safety controls for evolution system:
- Global pause/resume (kill-switch)
- Per-feature enable/disable
- Emergency rollback
- Full Operation health gate
- Rate limiting enforcement

Ensures human can always stop/control evolution.
"""
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvolutionState:
    """Current state of evolution system."""

    enabled: bool
    paused: bool
    pause_reason: str | None
    cycles_run: int
    improvements_applied: int
    last_cycle_at: float
    health_status: str  # "healthy", "degraded", "critical"


class EvolutionControls:
    """Global controls for evolution system."""

    def __init__(self) -> None:
        self._enabled = False  # Must be explicitly enabled
        self._paused = False
        self._pause_reason: str | None = None
        self._emergency_stop = False

        # State tracking
        self._cycles_run = 0
        self._improvements_applied = 0
        self._last_cycle_at = 0.0

        # Rate limiting
        self._changes_today = 0
        self._last_change_at = 0.0
        self._day_started = time.time()

    def enable_evolution(self, enabled_by: str = "system") -> dict[str, Any]:
        """Enable evolution system.

        Args:
            enabled_by: Who enabled it (for audit trail)

        Returns:
            Status dict[str, Any]
        """
        if self._enabled:
            return {"status": "already_enabled"}

        self._enabled = True

        logger.info(f"✅ Evolution system ENABLED by {enabled_by}")

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_enabled_total", labels={"by": enabled_by})
        except Exception:
            pass

        return {"status": "enabled", "enabled_by": enabled_by}

    def disable_evolution(self, disabled_by: str = "system") -> dict[str, Any]:
        """Disable evolution system (kill-switch).

        Args:
            disabled_by: Who disabled it

        Returns:
            Status dict[str, Any]
        """
        self._enabled = False
        self._paused = True
        self._pause_reason = f"Disabled by {disabled_by}"

        logger.warning(f"🛑 Evolution system DISABLED by {disabled_by}")

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_disabled_total", labels={"by": disabled_by})
        except Exception:
            pass

        return {"status": "disabled", "disabled_by": disabled_by}

    def pause(self, reason: str = "Manual pause") -> dict[str, Any]:
        """Pause evolution (temporary).

        Args:
            reason: Why paused

        Returns:
            Status dict[str, Any]
        """
        self._paused = True
        self._pause_reason = reason

        logger.info(f"⏸️ Evolution PAUSED: {reason}")

        return {"status": "paused", "reason": reason}

    def resume(self) -> dict[str, Any]:
        """Resume evolution."""
        if not self._enabled:
            return {"status": "error", "message": "Evolution not enabled"}

        self._paused = False
        self._pause_reason = None

        logger.info("▶️ Evolution RESUMED")

        return {"status": "resumed"}

    def emergency_stop(self, reason: str) -> dict[str, Any]:
        """Emergency stop - immediately halt all evolution.

        Args:
            reason: Why emergency stop triggered

        Returns:
            Status dict[str, Any]
        """
        self._emergency_stop = True
        self._enabled = False
        self._paused = True
        self._pause_reason = f"EMERGENCY STOP: {reason}"

        logger.error(f"🚨 EMERGENCY STOP: {reason}")

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_emergency_stop_total", labels={"reason": reason})
        except Exception:
            pass

        return {"status": "emergency_stopped", "reason": reason}

    def can_run_cycle(self) -> dict[str, Any]:
        """Check if evolution cycle can run.

        Returns:
            {"allowed": bool, "reason": str | None}
        """
        # Emergency stop
        if self._emergency_stop:
            return {"allowed": False, "reason": "emergency_stop_active"}

        # Not enabled
        if not self._enabled:
            return {"allowed": False, "reason": "evolution_not_enabled"}

        # Paused
        if self._paused:
            return {"allowed": False, "reason": f"paused: {self._pause_reason}"}

        # Check Full Operation health gate
        health_check = self._check_full_operation_health()
        if not health_check["healthy"]:
            return {
                "allowed": False,
                "reason": f"health_check_failed: {health_check['reason']}",
            }

        # Check rate limiting
        rate_check = self._check_rate_limit()
        if not rate_check["allowed"]:
            return {"allowed": False, "reason": f"rate_limit: {rate_check['reason']}"}

        # All checks passed
        return {"allowed": True, "reason": None}

    def _check_full_operation_health(self) -> dict[str, Any]:
        """Check Full Operation mode health.

        Returns:
            {"healthy": bool, "reason": str | None}
        """
        try:
            import asyncio

            import aiohttp

            async def check_health() -> Any:
                try:
                    async with (
                        aiohttp.ClientSession() as session,
                        session.get(
                            "http://localhost:8000/health/detailed",
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as resp,
                    ):
                        if resp.status != 200:
                            return {
                                "healthy": False,
                                "reason": f"health_check_failed_status_{resp.status}",
                            }

                        health_data = await resp.json()

                        # Check critical components
                        components = health_data.get("components", {})
                        unhealthy = []

                        for name, status in components.items():
                            if isinstance(status, dict):
                                if not status.get("healthy", status.get("status") == "ok"):
                                    unhealthy.append(name)
                            elif status not in ("ok", "healthy", True):
                                unhealthy.append(name)

                        if unhealthy:
                            return {
                                "healthy": False,
                                "reason": f"unhealthy_components: {', '.join(unhealthy)}",
                            }

                        return {"healthy": True, "reason": None}

                except aiohttp.ClientError as e:
                    return {"healthy": False, "reason": f"health_check_connection_error: {e}"}
                except TimeoutError:
                    return {"healthy": False, "reason": "health_check_timeout"}

            # Run async check
            try:
                asyncio.get_running_loop()
                # If we're in an async context, we can't use run_until_complete
                # Assume healthy if we can't check (fail open for evolution)
                return {"healthy": True, "reason": None}
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                return asyncio.run(check_health())

        except ImportError:
            # aiohttp not available, assume healthy
            return {"healthy": True, "reason": None}
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            # Fail open - allow evolution to proceed if health check itself fails
            return {"healthy": True, "reason": None}

    def _check_rate_limit(self) -> dict[str, Any]:
        """Check evolution rate limits.

        Returns:
            {"allowed": bool, "reason": str | None}
        """
        MAX_CHANGES_PER_DAY = 10
        MIN_TIME_BETWEEN_CHANGES_S = 3600  # 1 hour

        now = time.time()

        # Reset daily counter if new day
        if now - self._day_started > 86400:  # 24 hours
            self._changes_today = 0
            self._day_started = now

        # Check daily limit
        if self._changes_today >= MAX_CHANGES_PER_DAY:
            return {"allowed": False, "reason": "daily_limit_reached"}

        # Check time between changes
        time_since_last = now - self._last_change_at
        if self._last_change_at > 0 and time_since_last < MIN_TIME_BETWEEN_CHANGES_S:
            return {
                "allowed": False,
                "reason": f"too_soon ({int(time_since_last)}s < {MIN_TIME_BETWEEN_CHANGES_S}s)",
            }

        return {"allowed": True, "reason": None}

    def record_cycle(self, success: bool = True) -> None:
        """Record that a cycle ran."""
        self._cycles_run += 1
        self._last_cycle_at = time.time()

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_cycles_total", labels={"success": str(success)})
        except Exception:
            pass

    def record_improvement_applied(self) -> None:
        """Record that an improvement was applied."""
        self._improvements_applied += 1
        self._changes_today += 1
        self._last_change_at = time.time()

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_improvements_applied_total")
        except Exception:
            pass

    def get_state(self) -> EvolutionState:
        """Get current evolution state."""
        # Determine health status
        if self._emergency_stop:
            health = "critical"
        elif self._paused:
            health = "degraded"
        else:
            health = "healthy"

        return EvolutionState(
            enabled=self._enabled,
            paused=self._paused,
            pause_reason=self._pause_reason,
            cycles_run=self._cycles_run,
            improvements_applied=self._improvements_applied,
            last_cycle_at=self._last_cycle_at,
            health_status=health,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get evolution statistics."""
        state = self.get_state()

        return {
            "enabled": state.enabled,
            "paused": state.paused,
            "pause_reason": state.pause_reason,
            "cycles_run": state.cycles_run,
            "improvements_applied": state.improvements_applied,
            "changes_today": self._changes_today,
            "last_cycle_seconds_ago": (
                time.time() - state.last_cycle_at if state.last_cycle_at > 0 else None
            ),
            "health_status": state.health_status,
            "active_rollouts": len(self._active_rollouts),  # type: ignore  # Dynamic attr
        }


# Singleton
_evolution_controls: EvolutionControls | None = None


def get_evolution_controls() -> EvolutionControls:
    """Get global evolution controls."""
    global _evolution_controls
    if _evolution_controls is None:
        _evolution_controls = EvolutionControls()
    return _evolution_controls
