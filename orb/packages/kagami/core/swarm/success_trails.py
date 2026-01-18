"""Success Trail Tracker - Pheromone-Style Pattern Reinforcement.

Like ant pheromone trails, successful approaches are reinforced and unsuccessful
ones fade away. The system naturally converges on optimal patterns.

Bio-Inspiration:
- Ants: Strong pheromone on successful paths → more ants follow → path reinforced
- Evaporation: Old pheromones fade → prevents lock-in to suboptimal solutions
- Emergence: Global optimum from local trail-following decisions

Usage:
    tracker = get_success_trail_tracker()

    # Reinforce trail after success
    await tracker.reinforce_trail(
        pattern="use_caching_for_embeddings",
        success=True,
        strength=1.5  # Extra strong signal
    )

    # Get recommended approach
    pattern = tracker.get_recommended_approach("optimize_embeddings")
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Trail:
    """Pheromone-style success trail."""

    strength: float = 1.0  # Trail strength (like pheromone concentration)
    recent_successes: list[float] = field(default_factory=list[Any])  # Timestamps
    total_successes: int = 0
    total_failures: int = 0
    last_reinforcement: float = field(default_factory=time.time)

    async def evaporate(self, decay_rate: float = 0.95) -> None:
        """Evaporate trail over time (like pheromone decay).

        Args:
            decay_rate: Decay factor per hour (0.95 = 5% decay/hour)
        """
        # Time-based decay
        hours_elapsed = (time.time() - self.last_reinforcement) / 3600.0
        self.strength *= decay_rate**hours_elapsed

        # Minimum threshold - trails below 0.1 effectively disappear
        if self.strength < 0.1:
            self.strength = 0.0


class SuccessTrailTracker:
    """Track and reinforce successful patterns (bio-inspired pheromone trails)."""

    def __init__(self) -> None:
        # pattern -> Trail
        self._trails: dict[str, Trail] = {}

        # Task pattern mapping (for recommendations)
        self._task_to_patterns: dict[str, set[str]] = {}

        # Evaporation config
        self._decay_rate = 0.95  # 5% decay per hour
        self._last_evaporation = time.time()
        self._evaporation_interval = 3600.0  # 1 hour

        # Feature flags for exponential growth
        # New path: defaults via environment (no feature_flags dependency)
        import os

        trail_mode_str = os.getenv("KAGAMI_TRAIL_MODE", "linear").lower()
        self._trail_mode = "exponential" if trail_mode_str == "exponential" else "linear"
        try:
            self._trail_alpha = float(os.getenv("KAGAMI_EXPONENTIAL_TRAIL_ALPHA", "0.5"))
        except Exception:
            self._trail_alpha = 0.5
        try:
            self._trail_max = float(os.getenv("KAGAMI_EXPONENTIAL_TRAIL_MAX", "100.0"))
        except Exception:
            self._trail_max = 100.0

    async def reinforce_trail(
        self,
        pattern: str,
        success: bool,
        strength: float = 1.0,
        task: str | None = None,
    ) -> None:
        """Reinforce or weaken trail based on outcome.

        Args:
            pattern: Pattern identifier (e.g., "ring_buffer_cache")
            success: Whether pattern led to success
            strength: Reinforcement strength (1.0 = normal, >1.0 = strong signal)
            task: Optional task type for pattern mapping
        """
        trail = self._trails.setdefault(pattern, Trail())

        if success:
            # Positive feedback: Reinforce trail
            if self._trail_mode == "exponential":
                # EXPONENTIAL: Winner-takes-all dynamics
                # Bounded multiplicative: trail.strength = min(MAX, trail.strength * (1 + α*strength))
                old_strength = trail.strength
                trail.strength = min(
                    self._trail_max, trail.strength * (1 + self._trail_alpha * strength)
                )
                logger.debug(
                    f"🚀 Exponential reinforcement: {pattern} "
                    f"({old_strength:.1f} → {trail.strength:.1f})"
                )
            else:
                # LINEAR (default, safe): Additive reinforcement
                trail.strength += strength

            trail.recent_successes.append(time.time())
            trail.total_successes += 1

            # Keep only recent successes (last 24 hours)
            cutoff = time.time() - 86400
            trail.recent_successes = [t for t in trail.recent_successes if t > cutoff]

            logger.info(
                f"✅ Trail reinforced: {pattern} (strength={trail.strength:.1f}, "
                f"mode={self._trail_mode}, recent={len(trail.recent_successes)})"
            )
        else:
            # Negative feedback: Weaken trail
            trail.strength *= 0.8
            trail.total_failures += 1

            logger.debug(f"⚠️ Trail weakened: {pattern} (strength={trail.strength:.1f})")

        trail.last_reinforcement = time.time()

        # Map to task if provided
        if task:
            self._task_to_patterns.setdefault(task, set()).add(pattern)

        # Emit metric
        try:
            from kagami_observability.metrics import REGISTRY
            from prometheus_client import Gauge

            if not hasattr(REGISTRY, "_trail_strength"):
                REGISTRY._trail_strength = Gauge(  # type: ignore  # Dynamic attr
                    "kagami_success_trail_strength",
                    "Success trail pheromone strength",
                    ["pattern"],
                    registry=REGISTRY,
                )

            REGISTRY._trail_strength.labels(pattern=pattern).set(trail.strength)  # type: ignore  # Dynamic attr

            # Emit amplification factor metric (exponential mode)
            if self._trail_mode == "exponential" and not hasattr(REGISTRY, "_trail_amplification"):
                REGISTRY._trail_amplification = Gauge(  # type: ignore  # Dynamic attr
                    "kagami_trail_amplification_factor",
                    "Trail amplification factor (exponential mode)",
                    ["pattern"],
                    registry=REGISTRY,
                )
            if self._trail_mode == "exponential":
                # Calculate amplification: current / (if it were linear)
                linear_equivalent = 1.0 + (trail.total_successes * strength)
                amplification = trail.strength / linear_equivalent if linear_equivalent > 0 else 1.0
                REGISTRY._trail_amplification.labels(pattern=pattern).set(amplification)  # type: ignore  # Dynamic attr
        except Exception:
            pass

        # EXPONENTIAL GROWTH: Trigger agent specialization on strong trails
        await self._check_trail_specialization_trigger(pattern, trail)

        # Broadcast strong trails (like ant recruitment)
        # Lower threshold in exponential mode (winner-takes-all emerges faster)
        broadcast_threshold = 3.0 if self._trail_mode == "exponential" else 5.0
        if trail.strength > broadcast_threshold:
            try:
                from kagami.core.events import get_unified_bus

                bus = get_unified_bus()
                await bus.publish(
                    "pattern.strong_trail",
                    {
                        "pattern": pattern,
                        "strength": trail.strength,
                        "recent_successes": len(trail.recent_successes),
                        "total_successes": trail.total_successes,
                        "success_rate": (
                            trail.total_successes / (trail.total_successes + trail.total_failures)
                            if (trail.total_successes + trail.total_failures) > 0
                            else 0.0
                        ),
                    },
                )
            except Exception:
                pass

    def get_recommended_approach(self, task: str) -> str | None:
        """Get strongest trail for task (like ants following pheromone).

        Args:
            task: Task type

        Returns:
            Pattern with strongest trail or None
        """
        # Get patterns associated with this task
        patterns = self._task_to_patterns.get(task, set())

        if not patterns:
            # Fuzzy match - find patterns with task keywords
            task_lower = task.lower()
            patterns = {
                p
                for p in self._trails.keys()
                if any(word in p.lower() for word in task_lower.split("_"))
            }

        if not patterns:
            return None

        # Find strongest trail
        best_pattern = None
        best_strength = 0.0

        for pattern in patterns:
            trail = self._trails.get(pattern)
            if trail and trail.strength > best_strength:
                best_strength = trail.strength
                best_pattern = pattern

        if best_pattern:
            logger.info(f"🐜 Following trail: {best_pattern} (strength={best_strength:.1f})")

        return best_pattern

    def get_all_trails(self, min_strength: float = 0.5) -> list[dict[str, Any]]:
        """Get all active trails above minimum strength.

        Args:
            min_strength: Minimum strength threshold

        Returns:
            List of trail info dicts
        """
        trails = []

        for pattern, trail in self._trails.items():
            if trail.strength >= min_strength:
                trails.append(
                    {
                        "pattern": pattern,
                        "strength": trail.strength,
                        "recent_successes": len(trail.recent_successes),
                        "total_successes": trail.total_successes,
                        "total_failures": trail.total_failures,
                        "success_rate": (
                            trail.total_successes / (trail.total_successes + trail.total_failures)
                            if (trail.total_successes + trail.total_failures) > 0
                            else 0.0
                        ),
                    }
                )

        # Sort by strength
        trails.sort(key=lambda t: t["strength"], reverse=True)  # type: ignore
        return trails

    async def _check_trail_specialization_trigger(
        self,
        pattern: str,
        trail: Trail,
    ) -> None:
        """EXPONENTIAL GROWTH: Spawn specialized agent when trail very strong.

        When a pattern is proven (strength > 10.0), spawn a specialist agent
        for that pattern. This enables agent multiplication based on success.

        Args:
            pattern: Pattern name
            trail: Trail object
        """
        # Trigger threshold
        SPECIALIZATION_THRESHOLD = 10.0

        if trail.strength <= SPECIALIZATION_THRESHOLD:
            return

        # Check if already spawned specialist for this pattern
        if hasattr(self, "_specialized_agents"):
            if pattern in self._specialized_agents:  # type: ignore[has-type]
                return  # Already spawned
        else:
            self._specialized_agents = set()

        # Spawn specialist agent
        try:
            from kagami.core.agents.micro_agent_factory import MicroAgentFactory

            # New path: no gating; proceed to spawn when threshold met

            factory = MicroAgentFactory()

            # Create specialist for this pattern
            specialist_name = f"{pattern}_specialist".replace("_", "")

            await factory.create_micro_agent(  # Dynamic attr
                name=specialist_name,
                capabilities={
                    "specialized_for": pattern,
                    "pattern_strength": trail.strength,
                    "success_rate": (
                        trail.total_successes / (trail.total_successes + trail.total_failures)
                        if (trail.total_successes + trail.total_failures) > 0
                        else 0.0
                    ),
                },
                domain=pattern.split("_")[0] if "_" in pattern else "general",
            )

            self._specialized_agents.add(pattern)

            logger.info(
                f"🧬 SPAWNED SPECIALIST: {specialist_name} for pattern '{pattern}' "
                f"(trail strength: {trail.strength:.1f})"
            )

            # Emit metric
            from kagami_observability.metrics import REGISTRY
            from prometheus_client import Counter

            if not hasattr(REGISTRY, "_trail_specializations"):
                REGISTRY._trail_specializations = Counter(  # type: ignore  # Dynamic attr
                    "kagami_trail_specializations_total",
                    "Specialist agents spawned from strong trails",
                    ["pattern"],
                    registry=REGISTRY,
                )

            REGISTRY._trail_specializations.labels(pattern=pattern).inc()  # type: ignore  # Dynamic attr

        except Exception as e:
            logger.warning(f"Failed to spawn specialist for {pattern}: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get trail statistics."""
        active_trails = [t for t in self._trails.values() if t.strength > 0.1]

        specialized_count = len(getattr(self, "_specialized_agents", set()))

        return {
            "total_trails": len(self._trails),
            "active_trails": len(active_trails),
            "avg_trail_strength": (
                sum(t.strength for t in active_trails) / len(active_trails)
                if active_trails
                else 0.0
            ),
            "strongest_trail": max((t.strength for t in active_trails), default=0.0),
            "specialized_agents_spawned": specialized_count,
        }


# Singleton
_SUCCESS_TRAIL_TRACKER: SuccessTrailTracker | None = None


def get_success_trail_tracker() -> SuccessTrailTracker:
    """Get singleton success trail tracker."""
    global _SUCCESS_TRAIL_TRACKER
    if _SUCCESS_TRAIL_TRACKER is None:
        _SUCCESS_TRAIL_TRACKER = SuccessTrailTracker()
    return _SUCCESS_TRAIL_TRACKER


__all__ = ["SuccessTrailTracker", "Trail", "get_success_trail_tracker"]
