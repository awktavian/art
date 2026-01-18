"""Catastrophe-Driven Program Execution.

Extracted from GeometricWorker to reduce god class complexity.

This module handles:
- Catastrophe dynamics integration
- Risk assessment
- Differentiable program execution
- Reward-based learning

Created: December 21, 2025
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn.functional as F

# NOTE: differentiable_catastrophe removed in Jan 2026 training consolidation
# ColonyCatastropheDynamics was for training, not execution

logger = logging.getLogger(__name__)


class CatastropheExecutor:
    """Executes programs using catastrophe dynamics.

    Each colony has a unique catastrophe type that influences execution:
    - Fold (A₂): Abrupt transitions
    - Cusp (A₃): Bifurcation decisions
    - Swallowtail (A₄): Hysteresis/memory
    - Butterfly (A₅): Multi-stability
    - Hyperbolic (D₄⁺): Splitting
    - Elliptic (D₄⁻): Smooth exploration
    - Parabolic (D₅): Verification
    """

    def __init__(
        self,
        colony_idx: int,
        catastrophe_threshold: float = 0.7,
    ):
        """Initialize catastrophe executor.

        Args:
            colony_idx: Colony assignment (0-6)
            catastrophe_threshold: Risk threshold for warnings
        """
        self.colony_idx = colony_idx
        self.catastrophe_threshold = catastrophe_threshold

        # Lazy-loaded catastrophe dynamics (deprecated - now in kagami_math)
        self._catastrophe_dynamics: Any = None

    @property
    def catastrophe_dynamics(self) -> Any:
        """Get catastrophe dynamics (lazy loaded).

        NOTE: differentiable_catastrophe removed in Jan 2026 training consolidation.
        This property returns None - catastrophe dynamics are now math-only.
        """
        if self._catastrophe_dynamics is None:
            logger.warning(
                "Catastrophe dynamics deprecated - use kagami_math.catastrophe_constants"
            )
        return self._catastrophe_dynamics

    def execute_program(self, program_embedding: torch.Tensor) -> torch.Tensor:
        """Execute a program to produce an action.

        This is the differentiable program execution interface used by
        ColonyRSSM.step_all_agents() for Markov blanket integration.

        Uses catastrophe dynamics for execution when available.

        Args:
            program_embedding: [8] program embedding

        Returns:
            action: [8] E8 octonion action
        """
        # Ensure 8D input
        if program_embedding.shape[-1] > 8:
            program_embedding = program_embedding[..., :8]
        elif program_embedding.shape[-1] < 8:
            program_embedding = F.pad(program_embedding, (0, 8 - program_embedding.shape[-1]))

        # If catastrophe dynamics wired, use for differentiable execution
        if self.catastrophe_dynamics is not None:
            try:
                # Use execute_by_index which accepts colony index (not colony name)
                action = self.catastrophe_dynamics.execute_by_index(
                    self.colony_idx,
                    program_embedding,
                )
                if action is not None and action.shape[-1] == 8:
                    return action
            except Exception:
                pass

        # Default: program embedding IS the action (with tanh for bounds)
        action = torch.tanh(program_embedding)

        # Ensure 8D output
        if action.shape[-1] != 8:
            if action.shape[-1] > 8:
                action = action[..., :8]
            else:
                action = F.pad(action, (0, 8 - action.shape[-1]))

        return action

    async def execute_with_catastrophe(  # type: ignore[no-untyped-def]
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
        program_idx: int | None,
        h14_position: torch.Tensor,
        do_execute_fn,
    ) -> Any:
        """Execute action using catastrophe dynamics.

        Args:
            action: Action name
            params: Action parameters
            context: Execution context
            program_idx: Program index (if selected)
            h14_position: Worker's H¹⁴ position
            do_execute_fn: Actual execution function

        Returns:
            Execution result
        """
        # Get catastrophe risk
        risk = await self._assess_catastrophe_risk(h14_position)

        if risk > self.catastrophe_threshold:
            logger.warning(f"High catastrophe risk {risk:.2f} for {action}")

        # Execute the actual action
        result = await do_execute_fn(action, params, context)

        return result

    async def _assess_catastrophe_risk(self, h14_position: torch.Tensor) -> float:
        """Assess catastrophe risk for current state.

        Args:
            h14_position: Worker's H¹⁴ position

        Returns:
            Risk value [0, 1]
        """
        if self.catastrophe_dynamics is None:
            return 0.7  # Conservative high-risk when dynamics unavailable

        try:
            risk = self.catastrophe_dynamics.compute_risk(  # type: ignore[operator]
                state=h14_position,
                colony_type=self.colony_idx,
            )
            return float(risk)
        except Exception:
            return 0.8  # High risk on computation failure

    def update_from_reward(
        self,
        reward: float,
        action: torch.Tensor,
        fitness: float,
        fitness_ema_alpha: float,
        program_library: Any | None = None,
        use_differentiable: bool = True,
    ) -> dict[str, Any]:
        """Update agent based on reward signal.

        Called by ColonyRSSM.step_all_agents() for online learning.

        Args:
            reward: Reward signal
            action: Action that was taken
            fitness: Current fitness
            fitness_ema_alpha: EMA smoothing factor
            program_library: Optional program library for complexity loss
            use_differentiable: Whether to return differentiable losses

        Returns:
            Dict with complexity_loss and update info
        """
        # Update fitness based on reward
        reward_signal = 1.0 if reward > 0 else (-1.0 if reward < 0 else 0.0)
        new_fitness = (
            fitness_ema_alpha * (0.5 + 0.5 * reward_signal) + (1 - fitness_ema_alpha) * fitness
        )

        result = {
            "fitness": new_fitness,
            "reward": reward,
        }

        if use_differentiable:
            # Compute complexity loss for library learning
            # Higher complexity = penalize programs that are used but give low reward
            complexity_loss = torch.tensor(0.0)
            if program_library is not None and reward < 0:
                # Negative reward increases complexity of used program
                complexity_loss = torch.tensor(abs(reward) * 0.1)
            result["complexity_loss"] = complexity_loss  # type: ignore[assignment]

        return result


__all__ = ["CatastropheExecutor"]
