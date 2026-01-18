"""Instinct Learning - Behavioral pattern extraction from agent operations.

Observes agent behavior patterns and extracts instinctive responses.
These become fast-path responses for common situations.

SCHEDULING: Via Celery Beat (kagami.core.tasks.processing_state.train_instincts_task)
No internal loop - Celery handles periodic execution.

Created: November 8, 2025
Updated: December 28, 2025 - Removed internal loop, Celery handles scheduling
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InstinctLearningLoop:
    """Learns instinctive behavior patterns from agent operations.

    Observes successful agent behaviors and extracts fast-path responses.
    Over time, builds a library of instinctive reactions to common situations.

    NOTE: No internal loop. Celery Beat calls train_step() periodically.
    """

    def __init__(
        self,
        *,
        production_systems: Any | None = None,
        batch_size: int = 32,
        min_buffer_size: int = 100,
    ) -> None:
        """Initialize instinct learning."""
        self.instincts: dict[str, Any] = {}
        self.observation_count = 0
        self.iterations = 0
        self.total_samples = 0
        self.production_systems = production_systems
        self.batch_size = batch_size
        self.min_buffer_size = min_buffer_size

    async def train_step(self) -> dict[str, Any]:
        """Execute a single training step (called by Celery).

        Returns:
            Training step results
        """
        try:
            self.observation_count += 1
            self.iterations += 1

            replay = getattr(self.production_systems, "prioritized_replay", None)
            if replay is not None:
                buffer_size = getattr(replay, "size", 0)
                if buffer_size >= self.min_buffer_size:
                    experiences, _weights, _indices = replay.sample(self.batch_size)
                    self.total_samples += len(experiences)
                    for exp in experiences:
                        ctx = getattr(exp, "context", None) or {}
                        action = ctx.get("action")
                        if action and action not in self.instincts:
                            self.instincts[action] = getattr(exp, "outcome", {})

            if self.observation_count % 10 == 0:
                logger.debug(
                    f"Instinct learning: {self.observation_count} observations, "
                    f"{len(self.instincts)} instincts"
                )

            return {
                "status": "success",
                "observations": self.observation_count,
                "instincts": len(self.instincts),
                "samples": self.total_samples,
            }
        except Exception as e:
            logger.warning(f"Instinct training step failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_instinct(self, situation: str) -> Any | None:
        """Get learned instinct for a situation."""
        return self.instincts.get(situation)

    def add_instinct(self, situation: str, response: Any) -> None:
        """Manually add an instinct."""
        self.instincts[situation] = response
        logger.info(f"Added instinct: {situation}")

    def get_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        return {
            "observations": self.observation_count,
            "instincts_learned": len(self.instincts),
            "iterations": self.iterations,
            "total_samples": self.total_samples,
        }


# Global singleton
_instinct_loop: InstinctLearningLoop | None = None


def get_instinct_learning_loop() -> InstinctLearningLoop:
    """Get or create global instinct learning loop."""
    global _instinct_loop
    if _instinct_loop is None:
        _instinct_loop = InstinctLearningLoop()
    return _instinct_loop


# Alias for Celery task compatibility
def get_learning_loop() -> InstinctLearningLoop | None:
    """Get the learning loop instance (for Celery task)."""
    return get_instinct_learning_loop()


def create_learning_loop(production_systems: Any = None) -> InstinctLearningLoop:
    """Create instinct learning loop (sync version for lifespan).

    Args:
        production_systems: Optional production systems coordinator

    Returns:
        InstinctLearningLoop instance
    """
    global _instinct_loop
    _instinct_loop = InstinctLearningLoop(production_systems=production_systems)
    return _instinct_loop
