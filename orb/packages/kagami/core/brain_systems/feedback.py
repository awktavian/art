"""Feedback Projection - Top-Down Hierarchical Recurrence.

BRAIN SCIENCE BASIS (December 2025):
====================================
The brain has ~10:1 feedback to feedforward ratio. Feedback enables:

1. TOP-DOWN PREDICTIONS
   - Higher areas predict lower area activity
   - Mismatches generate prediction errors
   - Errors propagate upward for learning

2. CONTEXTUAL MODULATION
   - Feedback changes gain, not driving input
   - Context shapes interpretation of sensory data
   - Attention modulated via feedback

3. SUSTAINED ACTIVITY
   - Recurrence maintains representations
   - Working memory via recurrent loops
   - Stabilizes transient inputs

This module implements feedback projections for:
- RSSM: Colony → Colony recurrence
- H-JEPA: Level → Level predictions
- Colony coordination: Cross-colony modulation

References:
- Felleman & Van Essen (1991): Distributed hierarchical processing
- Bastos et al. (2012): Canonical microcircuits for predictive coding
- Lamme & Roelfsema (2000): The distinct modes of vision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
import torch.nn as nn

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class FeedbackState:
    """State of feedback projections."""

    # Feedback signals [B, 7, D]
    feedback_signals: torch.Tensor

    # Prediction errors [B, 7, D]
    prediction_errors: torch.Tensor

    # Feedback strength per colony [7]
    feedback_strengths: torch.Tensor

    # Recurrence count
    iteration: int = 0


class FeedbackProjection(nn.Module):
    """Feedback projection for top-down modulation.

    Implements brain-like feedback with:
    1. Prediction generation (top-down)
    2. Error computation (prediction - input)
    3. Gain modulation (multiplicative effect)
    4. Iterative refinement
    """

    def __init__(
        self,
        input_dim: int = 256,  # RSSM h_dim
        num_colonies: int = 7,
        feedback_ratio: float = 5.0,  # Target 5:1 feedback:feedforward
        num_iterations: int = 3,  # Recurrent iterations
    ):
        super().__init__()
        self.input_dim = input_dim
        self.num_colonies = num_colonies
        self.feedback_ratio = feedback_ratio
        self.num_iterations = num_iterations

        # Cross-colony feedback (7 → 7 with Fano structure)
        # Each colony can modulate others it's connected to
        self.cross_colony_feedback = nn.ModuleList(
            [nn.Linear(input_dim, input_dim) for _ in range(num_colonies)]
        )

        # Prediction head: generates top-down predictions
        self.prediction_head = nn.Sequential(
            nn.Linear(input_dim, input_dim * 2),
            nn.GELU(),
            nn.Linear(input_dim * 2, input_dim),
        )

        # Error head: processes prediction errors
        self.error_head = nn.Sequential(
            nn.Linear(input_dim, input_dim),
            nn.GELU(),
            nn.Linear(input_dim, input_dim),
        )

        # Gain modulation: feedback affects gain, not direct input
        self.gain_net = nn.Sequential(
            nn.Linear(input_dim * 2, input_dim),
            nn.Sigmoid(),
        )

        # Fano-structured feedback mask
        self.register_buffer("fano_mask", self._build_fano_mask())

        # Learnable feedback strength per colony
        self.feedback_strength = nn.Parameter(torch.ones(num_colonies) * 0.5)

    def _build_fano_mask(self) -> torch.Tensor:
        """Build Fano-structured feedback mask.

        Colonies on the same Fano line can provide feedback to each other.
        """
        # Fano lines (0-indexed)
        fano_lines = [
            (0, 1, 2),
            (0, 3, 4),
            (0, 6, 5),
            (1, 3, 5),
            (1, 4, 6),
            (2, 3, 6),
            (2, 5, 4),
        ]

        mask = torch.zeros(7, 7)
        for line in fano_lines:
            for i in range(3):
                for j in range(3):
                    if i != j:
                        mask[line[i], line[j]] = 1.0

        return mask

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, 7, D] colony hidden states
        bottom_up_input: torch.Tensor | None = None,  # [B, 7, D] feedforward
    ) -> tuple[torch.Tensor, FeedbackState]:
        """Apply feedback projection with iterative refinement.

        Args:
            hidden_states: Current colony hidden states [B, 7, D]
            bottom_up_input: Optional feedforward input [B, 7, D]

        Returns:
            refined_states: States after feedback refinement [B, 7, D]
            state: FeedbackState with diagnostic info
        """
        _B, _C, _D = hidden_states.shape
        # Note: device available via hidden_states.device if needed

        # Use hidden states as bottom-up if not provided
        if bottom_up_input is None:
            bottom_up_input = hidden_states

        current = hidden_states.clone()
        all_errors = []

        for _iteration in range(self.num_iterations):
            # 1. Generate top-down predictions
            predictions = self.prediction_head(current)  # [B, 7, D]

            # 2. Compute prediction errors
            errors = bottom_up_input - predictions  # [B, 7, D]
            all_errors.append(errors)

            # 3. Cross-colony feedback (Fano-structured)
            feedback = torch.zeros_like(current)
            for i in range(self.num_colonies):
                # Weighted sum of other colonies' feedback
                for j in range(self.num_colonies):
                    if self.fano_mask[i, j] > 0:  # type: ignore[index]
                        fb = self.cross_colony_feedback[j](current[:, j, :])
                        feedback[:, i, :] += fb * self.fano_mask[i, j]  # type: ignore[index]

            # 4. Gain modulation (multiplicative)
            # Feedback affects gain, not direct input
            combined = torch.cat([current, feedback], dim=-1)  # [B, 7, 2D]
            gain = self.gain_net(combined)  # [B, 7, D] in [0, 1]

            # 5. Update with error and modulated gain
            processed_error = self.error_head(errors)
            update = processed_error * gain * self.feedback_strength.view(1, -1, 1)

            # 6. Residual update
            current = current + update * (self.feedback_ratio / self.num_iterations)

        # Average errors across iterations
        avg_errors = torch.stack(all_errors, dim=0).mean(dim=0)

        state = FeedbackState(
            feedback_signals=feedback,
            prediction_errors=avg_errors,
            feedback_strengths=self.feedback_strength,
            iteration=self.num_iterations,
        )

        return current, state

    def compute_feedback_loss(
        self,
        prediction_errors: torch.Tensor,
    ) -> torch.Tensor:
        """Compute loss based on prediction errors.

        Minimizing prediction error improves top-down models.
        """
        return (prediction_errors**2).mean()


class HierarchicalFeedback(nn.Module):
    """Hierarchical feedback for H-JEPA integration.

    Implements multi-level feedback where:
    - Higher levels predict lower level representations
    - Errors at each level propagate upward
    - Creates predictive coding hierarchy
    """

    def __init__(
        self,
        dims: list[int],  # Dimensions at each level [L0, L1, L2, ...]
        num_iterations: int = 2,
    ):
        super().__init__()
        self.num_levels = len(dims)
        self.num_iterations = num_iterations

        # Top-down projections (higher → lower)
        self.top_down = nn.ModuleList(
            [nn.Linear(dims[i + 1], dims[i]) for i in range(len(dims) - 1)]
        )

        # Error projections (error → update)
        self.error_proj = nn.ModuleList([nn.Linear(dims[i], dims[i]) for i in range(len(dims) - 1)])

    def forward(
        self,
        representations: list[torch.Tensor],  # [level0, level1, ...]
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """Apply hierarchical feedback.

        Args:
            representations: List of tensors at each level

        Returns:
            refined: Refined representations at each level
            errors: Prediction errors at each level
        """
        refined = [r.clone() for r in representations]
        all_errors = []

        for _ in range(self.num_iterations):
            level_errors = []

            # Top-down pass: generate predictions and compute errors
            for level in range(self.num_levels - 2, -1, -1):
                # Higher level predicts lower level
                prediction = self.top_down[level](refined[level + 1])
                error = refined[level] - prediction
                level_errors.append(error)

                # Update with error
                update = self.error_proj[level](error)
                refined[level] = refined[level] + update * 0.1

            all_errors = level_errors

        return refined, all_errors


def create_feedback_projection(
    input_dim: int = 256,
    num_colonies: int = 7,
    feedback_ratio: float = 5.0,
) -> FeedbackProjection:
    """Factory function for feedback projection."""
    return FeedbackProjection(
        input_dim=input_dim,
        num_colonies=num_colonies,
        feedback_ratio=feedback_ratio,
    )


__all__ = [
    "FeedbackProjection",
    "FeedbackState",
    "HierarchicalFeedback",
    "create_feedback_projection",
]
