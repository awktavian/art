"""Online World Model Updater - DELEGATES TO CANONICAL LOOP.

CONSOLIDATED (Dec 2, 2025):
This module now delegates to WorldModelLoop for all training.
EWC is handled by the canonical training loop.

Implements real-time gradient updates for the World Model during the CONVERGE phase,
preventing catastrophic forgetting using Elastic Weight Consolidation (EWC).
"""

from __future__ import annotations

import logging
from typing import Any

import torch

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin
from kagami.core.world_model.kagami_world_model import KagamiWorldModel

logger = logging.getLogger(__name__)


class OnlineWorldModelUpdater(SingletonCleanupMixin):
    """Handles real-time updates - DELEGATES TO CANONICAL LOOP.

    CONSOLIDATED (Dec 2, 2025):
    All training now goes through WorldModelLoop.train_full_stack().
    This class is a thin wrapper for backward compatibility.
    """

    def __init__(self, world_model: KagamiWorldModel, ewc_lambda: float = 0.4) -> None:
        """Initialize the updater.

        Args:
            world_model: The global optimized world model instance.
            ewc_lambda: Strength of the EWC regularization penalty.
        """
        self.world_model = world_model
        self.ewc_lambda = ewc_lambda

        # Get canonical training loop (Dec 2, 2025)
        from kagami.core.learning.world_model_loop import (
            TrainingConfig,
            get_canonical_training_loop,
        )

        TrainingConfig(
            enable_ewc=True,
            ewc_lambda=ewc_lambda,
        )
        self._canonical_loop = get_canonical_training_loop()

        # Override config if needed
        self._canonical_loop.config.ewc_lambda = ewc_lambda

        logger.info("✅ OnlineWorldModelUpdater delegates to canonical training loop")

    async def update(
        self, initial_state: Any, action: dict[str, Any], final_state: Any, task_id: str
    ) -> dict[str, float]:
        """Perform a single online gradient update.

        CONSOLIDATED (Dec 2, 2025):
        Delegates to WorldModelLoop.train_full_stack() for unified training.

        Args:
            initial_state: State before action (SemanticState).
            action: Action taken.
            final_state: State after action (SemanticState).
            task_id: Identifier for the current task/domain.

        Returns:
            Metrics dictionary (loss, ewc_penalty, etc.)
        """
        try:
            # Extract embeddings
            if hasattr(initial_state, "embedding"):
                device = next(self.world_model.parameters()).device

                if isinstance(initial_state.embedding, torch.Tensor):
                    state = initial_state.embedding.clone().detach().to(device)
                else:
                    state = torch.tensor(initial_state.embedding, dtype=torch.float32).to(device)

                if hasattr(final_state, "embedding"):
                    if isinstance(final_state.embedding, torch.Tensor):
                        next_state = final_state.embedding.clone().detach().to(device)
                    else:
                        next_state = torch.tensor(final_state.embedding, dtype=torch.float32).to(
                            device
                        )
                else:
                    return {"status": "skipped", "reason": "no_target_embedding"}  # type: ignore[dict-item]

                # Build batch for canonical training
                batch = {
                    "state": state.unsqueeze(0) if state.dim() == 1 else state,
                    "action": action,
                    "next_state": next_state.unsqueeze(0) if next_state.dim() == 1 else next_state,
                }

                # Train via canonical loop (handles EWC internally)
                metrics = self._canonical_loop.train_full_stack(
                    batch=batch,
                    task_id=task_id,
                    train_rl=False,  # Online updates don't train RL
                )

                return {
                    "status": "success",  # type: ignore[dict-item]
                    "total_loss": metrics.total_loss,
                    "ewc_loss": metrics.ewc_loss,
                    "task_id": task_id,  # type: ignore[dict-item]
                    "step": metrics.step,
                }

            else:
                return {"status": "skipped", "reason": "invalid_state_format"}  # type: ignore[dict-item]

        except Exception as e:
            logger.warning(f"Online update failed: {e}")
            return {"status": "failed", "error": str(e)}  # type: ignore[dict-item]

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Cleanup (SingletonCleanupMixin)."""
        # EWC state is now managed by canonical loop
        return {
            "delegated_to": "canonical_training_loop",  # type: ignore[dict-item]
            "fisher_matrices": len(self._canonical_loop._ewc_fisher)
            if hasattr(self._canonical_loop, "_ewc_fisher")
            else 0,
            "tasks_protected": len(self._canonical_loop._ewc_optimal_params)
            if hasattr(self._canonical_loop, "_ewc_optimal_params")
            else 0,
        }


# Singleton
_online_updater: OnlineWorldModelUpdater | None = None


def get_online_world_model_updater(world_model: KagamiWorldModel) -> OnlineWorldModelUpdater:
    """Get or create the online world model updater singleton.

    Args:
        world_model: The world model instance to update online.

    Returns:
        OnlineWorldModelUpdater singleton instance
    """
    global _online_updater
    if _online_updater is None:
        _online_updater = OnlineWorldModelUpdater(world_model)
    return _online_updater
