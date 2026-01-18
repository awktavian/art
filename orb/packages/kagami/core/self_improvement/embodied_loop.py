from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OnlineTrainer:
    """Lightweight online trainer for self-improvement feedback.

    Implements a simple experience replay and gradient-free optimization
    approach for learning from embodied experience.
    """

    learning_rate: float = 0.01
    momentum: float = 0.9
    max_buffer_size: int = 1000
    batch_size: int = 32
    update_frequency: int = 10

    # Internal state
    _experience_buffer: list[dict[str, Any]] = field(default_factory=list[Any])
    _policy_params: dict[str, float] = field(default_factory=dict[str, Any])
    _velocity: dict[str, float] = field(default_factory=dict[str, Any])
    _update_count: int = 0
    _initialized: bool = False

    def __post_init__(self) -> None:
        """Initialize trainer state."""
        self._experience_buffer = []
        self._policy_params = {
            "exploration_rate": 0.3,
            "risk_tolerance": 0.5,
            "planning_depth": 3.0,
            "integration_weight": 0.7,
        }
        self._velocity = dict[str, Any].fromkeys(self._policy_params, 0.0)
        self._initialized = True

    def record_plan_feedback(self, plan: dict[str, Any], metrics: dict[str, Any]) -> None:
        """Record plan execution feedback for learning.

        Args:
            plan: The executed plan
            metrics: Execution metrics including success, integration_score, etc.
        """
        if not self._initialized:
            return

        # Create experience entry
        experience = {
            "plan": plan,
            "metrics": metrics,
            "timestamp": time.time(),
            "policy_snapshot": dict(self._policy_params),
        }

        # Add to buffer with FIFO eviction
        self._experience_buffer.append(experience)
        if len(self._experience_buffer) > self.max_buffer_size:
            self._experience_buffer.pop(0)

        self._update_count += 1

        # Periodic policy update
        if self._update_count % self.update_frequency == 0:
            self._update_policy()

    def _update_policy(self) -> None:
        """Update policy parameters based on recent experience."""
        if len(self._experience_buffer) < self.batch_size:
            return

        # Sample recent experiences
        recent = self._experience_buffer[-self.batch_size :]

        # Compute gradients based on success correlation
        gradients: dict[str, float] = dict[str, Any].fromkeys(self._policy_params, 0.0)

        for exp in recent:
            metrics = exp["metrics"]
            policy_snap = exp["policy_snapshot"]

            success = 1.0 if metrics.get("success", False) else 0.0
            integration = metrics.get("integration_score", 0.5)
            reward = success * 0.6 + integration * 0.4

            # Simple policy gradient estimation
            for key in self._policy_params:
                if key in policy_snap:
                    diff = self._policy_params[key] - policy_snap[key]
                    gradients[key] += reward * diff

        # Normalize gradients
        for key in gradients:
            gradients[key] /= len(recent)

        # Apply momentum SGD update
        for key in self._policy_params:
            self._velocity[key] = (
                self.momentum * self._velocity[key] + self.learning_rate * gradients[key]
            )
            self._policy_params[key] += self._velocity[key]

            # Clamp to valid ranges
            if key == "exploration_rate":
                self._policy_params[key] = max(0.05, min(0.95, self._policy_params[key]))
            elif key == "risk_tolerance":
                self._policy_params[key] = max(0.1, min(0.9, self._policy_params[key]))
            elif key == "planning_depth":
                self._policy_params[key] = max(1.0, min(10.0, self._policy_params[key]))
            elif key == "integration_weight":
                self._policy_params[key] = max(0.1, min(1.0, self._policy_params[key]))

        logger.debug(f"Policy updated: {self._policy_params}")

    def get_policy_params(self) -> dict[str, float]:
        """Get current policy parameters."""
        return dict(self._policy_params)

    def get_stats(self) -> dict[str, Any]:
        """Get trainer statistics."""
        if not self._experience_buffer:
            return {
                "buffer_size": 0,
                "update_count": self._update_count,
                "avg_success_rate": 0.0,
                "policy_params": dict(self._policy_params),
            }

        successes = [
            1.0 if exp["metrics"].get("success", False) else 0.0 for exp in self._experience_buffer
        ]

        return {
            "buffer_size": len(self._experience_buffer),
            "update_count": self._update_count,
            "avg_success_rate": statistics.fmean(successes) if successes else 0.0,
            "policy_params": dict(self._policy_params),
        }


def create_online_trainer(
    learning_rate: float = 0.01,
    momentum: float = 0.9,
    max_buffer_size: int = 1000,
) -> OnlineTrainer:
    """Factory function to create an online trainer.

    Args:
        learning_rate: Learning rate for policy updates
        momentum: Momentum coefficient for SGD
        max_buffer_size: Maximum experience buffer size

    Returns:
        Configured OnlineTrainer instance
    """
    return OnlineTrainer(
        learning_rate=learning_rate,
        momentum=momentum,
        max_buffer_size=max_buffer_size,
    )


class EmbodiedSelfImprovementLoop:
    """Tracks virtual action plans and world generation results for self-improvement."""

    def __init__(self) -> None:
        self.sessions: deque[dict[str, Any]] = deque(maxlen=200)
        self._trainer: OnlineTrainer | None = None

    def _ensure_trainer(self) -> None:
        """Initialize the online trainer if not already done.

        Creates an OnlineTrainer instance for learning from embodied experience.
        The trainer implements a simple policy gradient approach with experience
        replay to improve planning and execution over time.
        """
        if self._trainer is None:
            try:
                self._trainer = create_online_trainer(
                    learning_rate=0.01,
                    momentum=0.9,
                    max_buffer_size=1000,
                )
                logger.info("Online trainer initialized for embodied self-improvement")
            except Exception as exc:
                logger.debug("Unable to initialize online trainer: %s", exc)
                self._trainer = None

    def record_session(self, plan: dict[str, Any], result: Any) -> None:
        """Record a completed embodied session."""
        metrics = {
            "provider": getattr(result, "provider", None)
            or getattr(result, "metadata", {}).get("provider"),
            "success": getattr(result, "success", False),
            "integration_score": (plan.get("predictions") or {}).get("integration_score", 0.0),
            "timestamp": time.time(),
        }
        session_entry = {
            "plan": plan,
            "result": {
                "success": getattr(result, "success", False),
                "error": getattr(result, "error", None),
                "metadata": getattr(result, "metadata", {}),
            },
            "metrics": metrics,
        }
        self.sessions.append(session_entry)

        try:
            self._ensure_trainer()
            if self._trainer is not None:
                self._trainer.record_plan_feedback(plan, metrics)
        except Exception as exc:
            logger.debug("Failed to record plan feedback in trainer: %s", exc)

    def recent_summary(self, window: int = 20) -> dict[str, Any]:
        """Summarize recent sessions."""
        if not self.sessions:
            return {"count": 0, "avg_integration": 0.0, "providers": {}}

        recent = list(self.sessions)[-window:]
        integration_scores = [entry["metrics"].get("integration_score", 0.0) for entry in recent]
        providers: dict[str, int] = {}
        for entry in recent:
            provider = entry["metrics"].get("provider") or "unknown"
            providers[provider] = providers.get(provider, 0) + 1

        return {
            "count": len(recent),
            "avg_integration": statistics.fmean(integration_scores) if integration_scores else 0.0,
            "providers": providers,
        }

    def needs_unrealzoo_benchmark(self, threshold: float = 0.4) -> bool:
        summary = self.recent_summary(window=10)
        return bool(summary["count"] >= 5 and summary["avg_integration"] < threshold)


_embodied_loop: EmbodiedSelfImprovementLoop | None = None


def get_embodied_self_improvement_loop() -> EmbodiedSelfImprovementLoop:
    global _embodied_loop
    if _embodied_loop is None:
        _embodied_loop = EmbodiedSelfImprovementLoop()
    return _embodied_loop


__all__ = ["EmbodiedSelfImprovementLoop", "get_embodied_self_improvement_loop"]
