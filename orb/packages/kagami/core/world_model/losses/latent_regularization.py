"""Latent regularization losses.

This module provides Information Bottleneck, KL divergence, and
safety-aware loss scaling mechanisms.

Key Components:
===============
- AdaptiveIBScheduler: Dynamic β scheduling for IB compression
- CBFAwareLossScaler: Safety-margin-aware loss weighting
- fsd_loss: Function-space discrepancy (anti-forgetting)
- Wasserstein IB: Smoother gradients than KL

Created: December 15, 2025 (refactored from unified_loss.py)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    from kagami.core.world_model.losses.composed import LossConfig


class AdaptiveIBScheduler:
    """Adaptive Information Bottleneck beta scheduler.

    Based on insights from APO (Amortized Proximal Optimization) paper:
    - Early training: less compression (explore representation space)
    - Later training: more compression (consolidate learned features)

    Supports multiple schedules:
    - constant: Fixed beta
    - linear: Linear warmup from min to max
    - cyclical: DreamerV3-style cyclic annealing
    - adaptive: Dynamic based on rate-distortion tradeoff
    """

    def __init__(self, config: LossConfig) -> None:
        self.config = config
        self.step = 0
        self._rate_distortion_history: list[tuple[float, float]] = []
        self._current_beta = config.ib_beta

    def get_beta(self, rate: float | None = None, distortion: float | None = None) -> float:
        """Get current beta value based on schedule.

        Args:
            rate: Current IB rate (bits used)
            distortion: Current distortion (prediction error)

        Returns:
            Current beta value
        """
        schedule = self.config.ib_beta_schedule
        beta_min = self.config.ib_beta_min
        beta_max = self.config.ib_beta_max
        warmup = self.config.ib_warmup_steps

        if schedule == "constant":
            beta = self.config.ib_beta

        elif schedule == "linear":
            # Linear warmup from min to max
            progress = min(1.0, self.step / warmup)
            beta = beta_min + progress * (beta_max - beta_min)

        elif schedule == "cyclical":
            # Cyclical annealing (DreamerV3-inspired)
            cycle_length = warmup * 2
            cycle_pos = self.step % cycle_length

            if cycle_pos < warmup:
                # Increasing phase
                beta = beta_min + (cycle_pos / warmup) * (beta_max - beta_min)
            else:
                # Decreasing phase
                progress = (cycle_pos - warmup) / warmup
                beta = beta_max - progress * (beta_max - beta_min)

        elif schedule == "adaptive":
            # Adaptive based on rate-distortion tradeoff
            if rate is not None and distortion is not None:
                self._rate_distortion_history.append((rate, distortion))

                # Keep last 100 samples
                if len(self._rate_distortion_history) > 100:
                    self._rate_distortion_history = self._rate_distortion_history[-100:]

                if len(self._rate_distortion_history) >= 10:
                    # Compute moving averages
                    recent = self._rate_distortion_history[-10:]
                    avg_rate = sum(r for r, d in recent) / len(recent)
                    avg_dist = sum(d for r, d in recent) / len(recent)

                    # Adjust beta to balance rate and distortion
                    if avg_rate > 2.0 * avg_dist:
                        # Rate too high → increase compression
                        self._current_beta = min(beta_max, self._current_beta * 1.05)
                    elif avg_dist > 2.0 * avg_rate:
                        # Distortion too high → decrease compression
                        self._current_beta = max(beta_min, self._current_beta * 0.95)

            beta = self._current_beta

        else:
            beta = self.config.ib_beta

        self.step += 1
        return beta

    def state_dict(self) -> dict[str, Any]:
        """Get scheduler state for checkpointing."""
        return {
            "step": self.step,
            "current_beta": self._current_beta,
            "history": self._rate_distortion_history[-100:],
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Load scheduler state from checkpoint."""
        self.step = state.get("step", 0)
        self._current_beta = state.get("current_beta", self.config.ib_beta)
        self._rate_distortion_history = state.get("history", [])


class CBFAwareLossScaler:
    """Scale losses based on Control Barrier Function safety margin.

    When safety margin h(x) is low:
    - Safety-related losses get boosted
    - Other losses get reduced (focus on safety first)

    When safety margin h(x) is high:
    - Normal weighting resumes
    """

    SAFETY_KEYS = frozenset(
        {
            "cbf",
            "safety",
            "tic_safety",
            "catastrophe",
            "stability",
            "constraint",
            "barrier",
            "guard",
        }
    )

    def __init__(self, config: LossConfig) -> None:
        self.config = config
        self.sensitivity = config.cbf_safety_sensitivity
        self.enabled = config.cbf_aware_scaling

    def scale_weights(
        self,
        base_weights: dict[str, float],
        safety_margin: float,
    ) -> dict[str, float]:
        """Scale loss weights based on CBF safety margin.

        Args:
            base_weights: Original loss weights
            safety_margin: h(x) from CBF (>0 = safe, <0 = unsafe)

        Returns:
            Scaled loss weights
        """
        if not self.enabled:
            return base_weights

        scaled = {}

        for key, base_weight in base_weights.items():
            # Check if this is a safety-related loss
            is_safety = any(s in key.lower() for s in self.SAFETY_KEYS)

            if is_safety:
                # Safety losses get boosted when margin is low
                if safety_margin < 0.5:
                    # Exponential boost as margin approaches 0
                    scale = 1.0 + self.sensitivity * (0.5 - safety_margin) * 2
                else:
                    scale = 1.0
            else:
                # Non-safety losses get reduced when margin is low
                if safety_margin < 0.5:
                    # Gradual reduction
                    scale = max(0.1, safety_margin / 0.5)
                else:
                    scale = 1.0

            scaled[key] = base_weight * scale

        return scaled

    def get_scaling_factor(self, safety_margin: float, is_safety_loss: bool) -> float:
        """Get scaling factor for a single loss.

        Args:
            safety_margin: h(x) from CBF
            is_safety_loss: Whether this is a safety-related loss

        Returns:
            Scaling factor
        """
        if not self.enabled:
            return 1.0

        if is_safety_loss:
            if safety_margin < 0.5:
                return 1.0 + self.sensitivity * (0.5 - safety_margin) * 2
            return 1.0
        else:
            if safety_margin < 0.5:
                return max(0.1, safety_margin / 0.5)
            return 1.0


def fsd_loss(
    model: nn.Module,
    reference_batch: dict[str, torch.Tensor],
    old_predictions: torch.Tensor | None = None,
    loss_type: str = "mse",
) -> torch.Tensor:
    """Compute function-space discrepancy loss.

    Penalizes changes to predictions on held-out (reference) data.
    This prevents catastrophic forgetting during gradient updates.

    Two usage modes:
    1. old_predictions=None: Returns current predictions for caching
    2. old_predictions provided: Returns FSD loss

    Args:
        model: The model to evaluate
        reference_batch: Held-out batch for FSD computation
        old_predictions: Cached predictions from before update
        loss_type: "mse" or "kl"

    Returns:
        FSD loss (or current predictions if old_predictions is None)
    """
    # Get current predictions
    with torch.set_grad_enabled(old_predictions is not None):
        output = model(reference_batch)

        if isinstance(output, tuple):
            new_predictions = output[0]
        elif isinstance(output, dict):
            new_predictions = output.get(
                "prediction", output.get("output", next(iter(output.values())))
            )
        else:
            new_predictions = output

    # If no old predictions, return current for caching
    if old_predictions is None:
        return new_predictions.detach()

    # Compute discrepancy
    if loss_type == "kl" and new_predictions.dim() >= 2:
        fsd = F.kl_div(
            F.log_softmax(new_predictions, dim=-1),
            F.softmax(old_predictions.detach(), dim=-1),
            reduction="batchmean",
        )
    else:
        fsd = F.mse_loss(new_predictions, old_predictions)

    return fsd


__all__ = [
    "AdaptiveIBScheduler",
    "CBFAwareLossScaler",
    "fsd_loss",
]
