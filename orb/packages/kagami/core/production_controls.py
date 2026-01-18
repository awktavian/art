from __future__ import annotations

'\nProduction Hardening Controls\n\nImplements cost controls, circuit breakers, and threshold tuning for production deployment.\n\nResearch Finding (Oct 2025): "K os should have cost controls and circuit breakers\nto prevent runaway behavior in production."\n\nThis module provides:\n1. LLM reasoning call limits per session/user\n2. Circuit breakers for high-risk operations\n3. Adaptive threshold tuning\n4. Cost tracking and alerts\n'
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from kagami_observability.metrics import (
    PRODUCTION_CONTROL_CIRCUIT_OPEN,
    PRODUCTION_CONTROL_LIMIT_HIT,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionLimits:
    """Per-session resource limits"""

    max_llm_reasoning_calls: int = 100
    max_loop_depth: int = 3
    max_duration_seconds: int = 3600
    max_cost_estimate: float = 10.0
    llm_reasoning_calls_used: int = 0
    start_time: float = field(default_factory=time.time)
    total_cost: float = 0.0


@dataclass
class CircuitBreakerState:
    """Circuit breaker for risky operations"""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    failures: int = 0
    is_open: bool = False
    last_failure_time: float = 0.0
    last_success_time: float = 0.0


class ProductionController:
    """
    Production controls for cost and safety.

    Usage:
        controller = get_production_controller()

        # Check limits before GAIA call
        if not controller.can_use_gaia(session_id):
            raise CostLimitExceeded("LLM reasoning call limit reached")

        # Record usage
        controller.record_llm_reasoning_call(session_id, cost=0.05)

        # Check circuit breaker before risky operation
        if not controller.can_execute(operation="delete_data"):
            raise CircuitBreakerOpen("delete_data circuit open due to failures")
    """

    def __init__(self) -> None:
        self._session_limits: dict[str, SessionLimits] = {}
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._global_limits = SessionLimits(max_llm_reasoning_calls=1000, max_cost_estimate=100.0)

    def get_session_limits(self, session_id: str) -> SessionLimits:
        """Get or create session limits"""
        if session_id not in self._session_limits:
            self._session_limits[session_id] = SessionLimits()
        return self._session_limits[session_id]

    def can_use_llm_reasoning(self, session_id: str) -> bool:
        """Check if session can make more LLM reasoning calls"""
        session = self.get_session_limits(session_id)
        if session.llm_reasoning_calls_used >= session.max_llm_reasoning_calls:
            logger.warning(
                f"Session {session_id} hit LLM reasoning call limit: {session.llm_reasoning_calls_used}/{session.max_llm_reasoning_calls}"
            )
            PRODUCTION_CONTROL_LIMIT_HIT.labels(limit_type="llm_reasoning_calls_session").inc()
            return False
        if (
            self._global_limits.llm_reasoning_calls_used
            >= self._global_limits.max_llm_reasoning_calls
        ):
            logger.warning(
                f"Global LLM reasoning call limit hit: {self._global_limits.llm_reasoning_calls_used}/{self._global_limits.max_llm_reasoning_calls}"
            )
            PRODUCTION_CONTROL_LIMIT_HIT.labels(limit_type="llm_reasoning_calls_global").inc()
            return False
        if session.total_cost >= session.max_cost_estimate:
            logger.warning(
                f"Session {session_id} hit cost limit: ${session.total_cost:.2f}/${session.max_cost_estimate:.2f}"
            )
            PRODUCTION_CONTROL_LIMIT_HIT.labels(limit_type="cost_session").inc()
            return False
        return True

    can_use_gaia = can_use_llm_reasoning

    def record_llm_reasoning_call(
        self, session_id: str, cost: float = 0.0, success: bool = True
    ) -> None:
        """Record an LLM reasoning call"""
        session = self.get_session_limits(session_id)
        session.llm_reasoning_calls_used += 1
        session.total_cost += cost
        self._global_limits.llm_reasoning_calls_used += 1
        self._global_limits.total_cost += cost

    def get_circuit_breaker(self, operation: str) -> CircuitBreakerState:
        """Get or create circuit breaker for operation"""
        if operation not in self._circuit_breakers:
            self._circuit_breakers[operation] = CircuitBreakerState()
        return self._circuit_breakers[operation]

    def can_execute(self, operation: str) -> bool:
        """Check if operation can execute (circuit breaker)"""
        breaker = self.get_circuit_breaker(operation)
        if breaker.is_open:
            time_since_failure = time.time() - breaker.last_failure_time
            if time_since_failure > breaker.recovery_timeout:
                logger.info(
                    f"Circuit breaker for {operation} entering half-open state (recovery timeout: {breaker.recovery_timeout}s)"
                )
                breaker.is_open = False
                breaker.failures = 0
                return True
            else:
                logger.warning(
                    f"Circuit breaker OPEN for {operation}: {breaker.failures} failures, retry in {breaker.recovery_timeout - time_since_failure:.0f}s"
                )
                return False
        return True

    def record_execution(
        self, operation: str, success: bool, error_type: str | None = None
    ) -> None:
        """Record operation execution result"""
        breaker = self.get_circuit_breaker(operation)
        if success:
            breaker.failures = 0
            breaker.last_success_time = time.time()
            if breaker.is_open:
                logger.info(f"Circuit breaker for {operation} CLOSED after success")
                breaker.is_open = False
        else:
            breaker.failures += 1
            breaker.last_failure_time = time.time()
            if breaker.failures >= breaker.failure_threshold:
                breaker.is_open = True
                logger.error(
                    f"Circuit breaker OPENED for {operation}: {breaker.failures} consecutive failures"
                )
                PRODUCTION_CONTROL_CIRCUIT_OPEN.labels(
                    operation=operation, error_type=error_type or "unknown"
                ).inc()

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get session resource usage stats"""
        session = self.get_session_limits(session_id)
        duration = time.time() - session.start_time
        return {
            "llm_reasoning_calls": {
                "used": session.llm_reasoning_calls_used,
                "max": session.max_llm_reasoning_calls,
                "remaining": session.max_llm_reasoning_calls - session.llm_reasoning_calls_used,
                "percentage": session.llm_reasoning_calls_used
                / session.max_llm_reasoning_calls
                * 100,
            },
            "cost": {
                "total": session.total_cost,
                "max": session.max_cost_estimate,
                "remaining": session.max_cost_estimate - session.total_cost,
                "percentage": session.total_cost / session.max_cost_estimate * 100,
            },
            "duration": {
                "seconds": duration,
                "max": session.max_duration_seconds,
                "remaining": session.max_duration_seconds - duration,
                "percentage": duration / session.max_duration_seconds * 100,
            },
        }

    def reset_session(self, session_id: str) -> None:
        """Reset session limits (for new session)"""
        if session_id in self._session_limits:
            del self._session_limits[session_id]

    def reset_circuit_breaker(self, operation: str) -> None:
        """Manually reset circuit breaker (admin action)"""
        if operation in self._circuit_breakers:
            logger.info(f"Manually resetting circuit breaker for {operation}")
            del self._circuit_breakers[operation]


_production_controller: ProductionController | None = None


def get_production_controller() -> ProductionController:
    """Get singleton production controller"""
    global _production_controller
    if _production_controller is None:
        _production_controller = ProductionController()
    return _production_controller


COST_PER_1K_TOKENS = {
    "qwen2:1.5b": 0.0001,
    "qwen3:7b": 0.0005,
    "qwen3:14b": 0.001,
    "qwen3:32b": 0.002,
    "gpt-oss:20b": 0.0015,
    "gpt-oss:120b": 0.005,
}


def estimate_cost(model: str, tokens: int) -> float:
    """Estimate cost for model call"""
    cost_per_1k = COST_PER_1K_TOKENS.get(model, 0.001)
    return tokens / 1000.0 * cost_per_1k
