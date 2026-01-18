"""Uncertainty-Weighted Multi-Task Loss.

Implements automatic loss weighting based on task uncertainty (homoscedastic uncertainty).

Reference:
    Kendall, A., Gal, Y., & Cipolla, R. (2018).
    Multi-Task Learning Using Uncertainty to Weigh Losses for Scene Geometry and Semantics.
    CVPR 2018.

The key insight is that for a multi-task loss:
    L_total = Σ_i (1/σ_i²) * L_i + log(σ_i)

Where σ_i is the learnable task-specific uncertainty (noise parameter).
- Higher σ → lower weight on that loss
- The log(σ) term regularizes σ to not explode

This module wraps any set[Any] of named losses and learns optimal weightings automatically.

Created: December 27, 2025
"""

from __future__ import annotations

import logging

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class UncertaintyWeightedLoss(nn.Module):
    """Multi-task loss with learnable uncertainty-based weights.

    THEORY (Kendall et al. 2018):
    =============================
    For multi-task learning with tasks i ∈ {1, ..., K}:

        L_total = Σ_i (1/(2σ_i²)) * L_i + log(σ_i)

    Where:
    - L_i is the loss for task i
    - σ_i is the learnable uncertainty (noise parameter) for task i
    - The 1/(2σ_i²) term inversely weights the loss by uncertainty
    - The log(σ_i) term prevents σ from exploding

    IMPLEMENTATION:
    ===============
    We parameterize log(σ²) instead of σ for numerical stability:

        s_i = log(σ_i²)
        weight_i = exp(-s_i) = 1/σ_i²
        regularizer_i = 0.5 * s_i = 0.5 * log(σ_i²) = log(σ_i)

    So: L_total = Σ_i (0.5 * exp(-s_i) * L_i + 0.5 * s_i)

    USAGE:
    ======
    >>> loss_module = UncertaintyWeightedLoss(["reconstruction", "kl", "e8_commitment"])
    >>> losses = {"reconstruction": 0.5, "kl": 0.1, "e8_commitment": 0.05}
    >>> total, weighted_losses, weights = loss_module(losses)
    """

    def __init__(
        self,
        task_names: list[str],
        init_log_var: float = 0.0,
        min_log_var: float = -10.0,
        max_log_var: float = 10.0,
    ):
        """Initialize uncertainty-weighted loss module.

        Args:
            task_names: List of task/loss names to track
            init_log_var: Initial value for log(σ²) (default: 0.0 → σ=1)
            min_log_var: Minimum log variance (prevents weights from exploding)
            max_log_var: Maximum log variance (prevents weights from collapsing)
        """
        super().__init__()
        self.task_names = task_names
        self.num_tasks = len(task_names)
        self.min_log_var = min_log_var
        self.max_log_var = max_log_var

        # Learnable log variances: s_i = log(σ_i²)
        # Initialized to init_log_var (default: 0 → σ=1, weight=1)
        self.log_vars = nn.Parameter(torch.full((self.num_tasks,), init_log_var))

        # Create name → index mapping
        self.task_to_idx = {name: i for i, name in enumerate(task_names)}

        logger.info(
            f"UncertaintyWeightedLoss initialized (Kendall 2018):\n"
            f"  Tasks: {task_names}\n"
            f"  Initial log_var: {init_log_var} (σ={torch.exp(torch.tensor(init_log_var / 2)).item():.3f})"
        )

    def forward(
        self,
        losses: dict[str, torch.Tensor | float],
        return_weights: bool = True,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, float]]:
        """Compute uncertainty-weighted total loss.

        Args:
            losses: Dict mapping task names to loss values
            return_weights: If True, return weight dict[str, Any]

        Returns:
            Tuple of:
                - total_loss: Weighted sum of losses with regularization
                - weighted_losses: Dict of weighted loss per task
                - weights: Dict of current weights per task (if return_weights=True)
        """
        device = None
        for v in losses.values():
            if isinstance(v, torch.Tensor):
                device = v.device
                break

        if device is None:
            device = self.log_vars.device

        # Clamp log variances for stability
        log_vars_clamped = self.log_vars.clamp(self.min_log_var, self.max_log_var)

        total_loss = torch.tensor(0.0, device=device)
        weighted_losses: dict[str, torch.Tensor] = {}
        weights: dict[str, float] = {}

        for task_name, loss_value in losses.items():
            # Skip unknown tasks
            if task_name not in self.task_to_idx:
                logger.warning(f"Unknown task '{task_name}' in UncertaintyWeightedLoss, skipping")
                continue

            # Skip None or zero losses
            if loss_value is None:
                continue

            # Convert to tensor
            if isinstance(loss_value, (int, float)):
                loss_tensor = torch.tensor(loss_value, device=device)
            else:
                loss_tensor = loss_value.to(device)

            # Get log variance for this task
            idx = self.task_to_idx[task_name]
            s = log_vars_clamped[idx]

            # Compute weighted loss: 0.5 * exp(-s) * L + 0.5 * s
            # exp(-s) = 1/σ², so higher σ → lower weight
            precision = torch.exp(-s)  # 1/σ²
            weighted_loss = 0.5 * precision * loss_tensor + 0.5 * s

            total_loss = total_loss + weighted_loss
            weighted_losses[task_name] = weighted_loss

            if return_weights:
                weights[task_name] = precision.item()

        return total_loss, weighted_losses, weights

    def get_weights(self) -> dict[str, float]:
        """Get current task weights (1/σ²).

        Returns:
            Dict mapping task names to current weights
        """
        log_vars_clamped = self.log_vars.clamp(self.min_log_var, self.max_log_var)
        precisions = torch.exp(-log_vars_clamped)
        return {name: precisions[i].item() for name, i in self.task_to_idx.items()}

    def get_uncertainties(self) -> dict[str, float]:
        """Get current task uncertainties (σ).

        Returns:
            Dict mapping task names to current uncertainties
        """
        log_vars_clamped = self.log_vars.clamp(self.min_log_var, self.max_log_var)
        sigmas = torch.exp(0.5 * log_vars_clamped)
        return {name: sigmas[i].item() for name, i in self.task_to_idx.items()}

    def extra_repr(self) -> str:
        """Extra representation for printing."""
        weights = self.get_weights()
        weight_str = ", ".join(f"{k}={v:.3f}" for k, v in weights.items())
        return f"tasks={self.task_names}, weights=[{weight_str}]"


class GradNormLoss(nn.Module):
    """GradNorm: Gradient Normalization for Adaptive Loss Balancing.

    Reference:
        Chen, Z., Badrinarayanan, V., Lee, C. Y., & Rabinovich, A. (2018).
        GradNorm: Gradient Normalization for Adaptive Loss Balancing in Deep Multitask Networks.
        ICML 2018.

    GradNorm adaptively balances gradient magnitudes across tasks by:
    1. Tracking relative loss ratios r_i(t) = L_i(t) / L_i(0)
    2. Adjusting weights to equalize gradient norms × inverse training rates

    NOTE: This is more complex than UncertaintyWeightedLoss and requires
    tracking initial losses and gradients. Use UncertaintyWeightedLoss
    for simpler cases.

    DISABLED in Kagami (Dec 22, 2025) - caused gradient conflicts.
    Kept here for reference/future use.
    """

    def __init__(
        self,
        task_names: list[str],
        alpha: float = 1.5,
        lr: float = 0.025,
    ):
        """Initialize GradNorm loss module.

        Args:
            task_names: List of task/loss names
            alpha: Asymmetry hyperparameter (higher = more emphasis on harder tasks)
            lr: Learning rate for weight updates
        """
        super().__init__()
        self.task_names = task_names
        self.num_tasks = len(task_names)
        self.alpha = alpha
        self.lr = lr

        # Learnable task weights (will be normalized via softmax)
        self.log_weights = nn.Parameter(torch.zeros(self.num_tasks))

        # Register initial losses (set[Any] on first forward)
        self.register_buffer("initial_losses", torch.ones(self.num_tasks))
        self.register_buffer("initialized", torch.tensor(False))

        self.task_to_idx = {name: i for i, name in enumerate(task_names)}

        logger.warning(
            "GradNormLoss initialized - NOTE: This was disabled in Kagami Dec 22, 2025 "
            "due to gradient conflicts. Consider using UncertaintyWeightedLoss instead."
        )

    def forward(
        self,
        losses: dict[str, torch.Tensor],
        shared_layer: nn.Module | None = None,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, float]]:
        """Compute GradNorm-weighted loss.

        Args:
            losses: Dict mapping task names to loss values
            shared_layer: Shared layer for gradient norm computation

        Returns:
            Tuple of (total_loss, weighted_losses, weights)
        """
        device = next(iter(losses.values())).device

        # Normalize weights via softmax
        weights = torch.softmax(self.log_weights, dim=0) * self.num_tasks

        # Initialize initial losses on first call
        if not self.initialized:
            for name, loss in losses.items():
                if name in self.task_to_idx:
                    idx = self.task_to_idx[name]
                    self.initial_losses[idx] = loss.detach()  # type: ignore[operator]
            self.initialized.fill_(True)  # type: ignore[operator]

        total_loss = torch.tensor(0.0, device=device)
        weighted_losses: dict[str, torch.Tensor] = {}
        weight_dict: dict[str, float] = {}

        for task_name, loss_value in losses.items():
            if task_name not in self.task_to_idx:
                continue

            idx = self.task_to_idx[task_name]
            w = weights[idx]

            weighted_loss = w * loss_value
            total_loss = total_loss + weighted_loss
            weighted_losses[task_name] = weighted_loss
            weight_dict[task_name] = w.item()

        return total_loss, weighted_losses, weight_dict


def create_uncertainty_loss(
    task_names: list[str] | None = None,
    init_log_var: float = 0.0,
) -> UncertaintyWeightedLoss:
    """Factory function to create uncertainty-weighted loss.

    Args:
        task_names: List of task names. If None, uses default Kagami tasks.
        init_log_var: Initial log variance

    Returns:
        Configured UncertaintyWeightedLoss
    """
    if task_names is None:
        # Default Kagami tasks (Tier 1 + Tier 2)
        task_names = [
            "prediction",  # Tier 1
            "e8_commitment",  # Tier 2
            "ib_kl",  # Tier 2
            "rssm_kl",  # Tier 2
            "seq_ib_recon",  # Tier 2
            "seq_ib_kl",  # Tier 2
            "fano_synergy",  # Tier 2
            "loop_closure",  # Tier 2
            "h_jepa_pred",  # Tier 2
            "stability",  # Tier 2
        ]

    return UncertaintyWeightedLoss(task_names, init_log_var)


__all__ = [
    "GradNormLoss",  # Kept for reference
    "UncertaintyWeightedLoss",
    "create_uncertainty_loss",
]
