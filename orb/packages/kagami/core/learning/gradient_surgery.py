"""Gradient Surgery for Multi-Objective Optimization.

Resolves gradient conflicts between competing objectives by projecting
conflicting gradients away from each other.

Based on:
- "Gradient Surgery for Multi-Task Learning" (Yu et al., 2020) - PCGrad
- "Conflict-Averse Gradient Descent" (Liu et al., 2021) - CAGrad
- "GradNorm: Gradient Normalization" (Chen et al., 2018) - Adaptive weighting

When two objectives have conflicting gradients (negative dot product),
we project one gradient onto the space orthogonal to the other.

Mathematical Formulation:
- Conflict: ⟨g₁, g₂⟩ < 0
- Projection: g₂' = g₂ - (⟨g₂,g₁⟩/||g₁||²)·g₁

Created: November 2, 2025
Updated: December 2, 2025 - Added PCGrad, GradNorm, CAGrad
Status: Production-ready
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


@dataclass
class GradientSurgeryStats:
    """Statistics from gradient surgery operations."""

    total_conflicts: int = 0
    total_checks: int = 0
    projections_applied: int = 0
    conflict_pairs: list[tuple[int, int]] = field(default_factory=list[Any])

    @property
    def conflict_rate(self) -> float:
        return self.total_conflicts / max(1, self.total_checks)


class GradientSurgery:
    """Gradient surgery to resolve multi-objective conflicts.

    When training multiple objectives simultaneously, their gradients
    can point in opposite directions (conflict). This causes oscillation
    and prevents convergence.

    Gradient surgery detects conflicts and projects gradients to remove
    the conflicting component, allowing both objectives to make progress.

    Supports:
    - Pairwise conflict detection and projection
    - Multi-task PCGrad (N>2 tasks)
    - Conflict-averse gradient descent (CAGrad)
    """

    def __init__(
        self,
        conflict_threshold: float = 0.0,
        use_random_projection_order: bool = True,
    ) -> None:
        """Initialize gradient surgery.

        Args:
            conflict_threshold: Threshold for detecting conflicts
                               (conflict if dot product < threshold)
            use_random_projection_order: Randomize order when projecting
                                        (reduces bias in PCGrad)
        """
        self.conflict_threshold = conflict_threshold
        self.use_random_projection_order = use_random_projection_order
        self.stats = GradientSurgeryStats()

    def detect_conflict(
        self,
        grad1: list[torch.Tensor | None] | torch.Tensor,
        grad2: list[torch.Tensor | None] | torch.Tensor,
    ) -> bool:
        """Detect if two gradients conflict.

        Conflict = gradients point in opposite directions (negative dot product)

        Args:
            grad1: First gradient (list[Any] of tensors or single tensor)
            grad2: Second gradient (list[Any] of tensors or single tensor)

        Returns:
            conflict: True if gradients conflict
        """
        self.stats.total_checks += 1

        # Handle tensor vs list[Any]
        if isinstance(grad1, torch.Tensor):
            grad1 = [grad1]
        if isinstance(grad2, torch.Tensor):
            grad2 = [grad2]

        # Compute dot product of flattened gradients
        dot_product = 0.0
        for g1, g2 in zip(grad1, grad2, strict=False):
            if g1 is not None and g2 is not None:
                dot_product += (g1 * g2).sum().item()

        conflict = dot_product < self.conflict_threshold

        if conflict:
            self.stats.total_conflicts += 1
            logger.debug(f"Conflict detected: dot_product={dot_product:.4f}")

        return conflict

    def project_gradient(
        self,
        grad_to_project: list[torch.Tensor | None] | torch.Tensor,
        grad_reference: list[torch.Tensor | None] | torch.Tensor,
    ) -> list[torch.Tensor | None]:
        """Project gradient away from reference gradient.

        Removes component of grad_to_project that is parallel to grad_reference.
        This ensures the projected gradient doesn't interfere with the reference.

        Formula: g' = g - (⟨g,r⟩/||r||²)·r

        Args:
            grad_to_project: Gradient to modify
            grad_reference: Reference gradient (unchanged)

        Returns:
            grad_projected: Projected gradient list[Any]
        """
        # Handle tensor vs list[Any]
        if isinstance(grad_to_project, torch.Tensor):
            grad_to_project = [grad_to_project]
        if isinstance(grad_reference, torch.Tensor):
            grad_reference = [grad_reference]

        # Compute dot product and norm
        dot_product = 0.0
        ref_norm_sq = 0.0

        for g, r in zip(grad_to_project, grad_reference, strict=False):
            if g is not None and r is not None:
                dot_product += (g * r).sum().item()
                ref_norm_sq += (r * r).sum().item()

        # Avoid division by zero
        if ref_norm_sq < 1e-8:
            logger.warning("Reference gradient near zero, skipping projection")
            return list(grad_to_project)

        # Only project if conflicting (negative dot product)
        if dot_product >= self.conflict_threshold:
            return list(grad_to_project)

        # Compute projection scale
        scale = dot_product / ref_norm_sq
        self.stats.projections_applied += 1

        # Project: remove component parallel to reference
        grad_projected: list[torch.Tensor | None] = []
        for g, r in zip(grad_to_project, grad_reference, strict=False):
            if g is not None and r is not None:
                g_proj = g - scale * r
                grad_projected.append(g_proj)
            elif g is not None:
                grad_projected.append(g)
            else:
                grad_projected.append(None)

        logger.debug(f"Gradient projected: scale={scale:.4f}")

        return grad_projected

    def get_stats(self) -> dict[str, Any]:
        """Get gradient surgery statistics.

        Returns:
            stats: Dict with conflict rate and counts
        """
        return {
            "total_conflicts": self.stats.total_conflicts,
            "total_checks": self.stats.total_checks,
            "conflict_rate": self.stats.conflict_rate,
            "projections_applied": self.stats.projections_applied,
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = GradientSurgeryStats()


class PCGrad(GradientSurgery):
    """Project Conflicting Gradients for N tasks (Yu et al., 2020).

    Full multi-task gradient surgery that handles N>2 objectives.
    For each task i, project onto the normal plane of all conflicting tasks.

    Usage:
        pcgrad = PCGrad()

        # Compute gradients for each task
        grads = [grad_task_1, grad_task_2, grad_task_3]

        # Apply PCGrad
        projected = pcgrad.apply(grads)

        # Average and apply
        final_grad = sum(projected) / len(projected)
    """

    def apply(
        self,
        gradients: list[list[torch.Tensor | None]],
    ) -> list[list[torch.Tensor | None]]:
        """Apply PCGrad to list[Any] of task gradients.

        For each task i, project onto the normal plane of all conflicting tasks.

        Args:
            gradients: List of task gradients, each is list[Any] of param tensors

        Returns:
            Projected gradients (same structure)
        """
        num_tasks = len(gradients)
        if num_tasks < 2:
            return gradients

        # Deep copy for modification
        projected: list[list[torch.Tensor | None]] = [
            [g.clone() if g is not None else None for g in grads] for grads in gradients
        ]

        # Get projection order
        if self.use_random_projection_order:
            import random

            order = list(range(num_tasks))
            random.shuffle(order)
        else:
            order = list(range(num_tasks))

        # Project each task against all others
        for i in order:
            for j in order:
                if i == j:
                    continue

                if self.detect_conflict(projected[i], gradients[j]):
                    projected[i] = self.project_gradient(projected[i], gradients[j])
                    self.stats.conflict_pairs.append((i, j))

        return projected

    def apply_to_model(
        self,
        model: nn.Module,
        losses: list[torch.Tensor],
    ) -> None:
        """Apply PCGrad directly to model parameters.

        Computes gradients for each loss, applies PCGrad, and sets
        the final averaged gradient on the model parameters.

        Args:
            model: PyTorch model
            losses: List of task losses
        """
        num_tasks = len(losses)
        params = list(model.parameters())

        # Compute per-task gradients
        task_grads: list[list[torch.Tensor | None]] = []

        for i, loss in enumerate(losses):
            model.zero_grad()
            loss.backward(retain_graph=(i < num_tasks - 1))

            grads = [p.grad.clone() if p.grad is not None else None for p in params]
            task_grads.append(grads)

        # Apply PCGrad
        projected = self.apply(task_grads)

        # Average and apply
        model.zero_grad()
        for j, param in enumerate(params):
            grad_j_list = [g[j] for g in projected if g[j] is not None]
            valid_grads: list[torch.Tensor] = [
                g for g in grad_j_list if isinstance(g, torch.Tensor)
            ]
            if valid_grads:
                param.grad = torch.stack(valid_grads).mean(dim=0)


class GradNorm(nn.Module):
    """Gradient Normalization for balanced multi-task learning (Chen et al., 2018).

    Dynamically adjusts task weights to balance gradient magnitudes across tasks.
    Tasks that are learning slower get higher weights.

    EMA STABILIZATION (Dec 3, 2025):
    Added exponential moving average for loss_ratios and target_norms to prevent
    oscillation and improve training stability. Controlled via ema_momentum.

    Usage:
        gradnorm = GradNorm(num_tasks=3, use_ema=True)

        # In training loop:
        gradnorm_loss = gradnorm.compute_weight_loss(
            losses=task_losses,
            shared_params=model.shared.parameters(),
        )

        # Add to total loss for weight update
        total_loss = sum(gradnorm.weights * losses) + gradnorm_loss
    """

    def __init__(
        self,
        num_tasks: int,
        alpha: float = 1.5,
        lr: float = 0.01,
        use_ema: bool = True,
        ema_momentum: float = 0.9,
    ) -> None:
        """Initialize GradNorm.

        Args:
            num_tasks: Number of tasks
            alpha: Asymmetry hyperparameter (higher = more aggressive balancing)
            lr: Learning rate for weight updates (separate from main optimizer)
            use_ema: If True, use EMA smoothing for stable targets (Dec 3, 2025)
            ema_momentum: Momentum for EMA smoothing (0.9 = stable, 0.5 = responsive)
        """
        super().__init__()
        self.num_tasks = num_tasks
        self.alpha = alpha
        self.use_ema = use_ema
        self.ema_momentum = ema_momentum

        # Learnable task weights (log space for positivity)
        self.log_weights = nn.Parameter(torch.zeros(num_tasks))

        # Track initial losses for computing relative training rate
        self.register_buffer("initial_losses", torch.zeros(num_tasks))
        self.initialized = False

        # =========================================================
        # EMA BUFFERS (Dec 3, 2025)
        # =========================================================
        # Smooth loss ratios and target norms to prevent oscillation
        self.register_buffer("ema_loss_ratios", torch.ones(num_tasks), persistent=False)
        self.register_buffer("ema_target_norms", torch.ones(num_tasks), persistent=False)
        self.register_buffer("ema_step", torch.tensor(0, dtype=torch.long), persistent=False)

        # Separate optimizer for weights
        self.weight_optimizer = torch.optim.Adam([self.log_weights], lr=lr)

    @property
    def weights(self) -> torch.Tensor:
        """Get current task weights (normalized to sum to num_tasks)."""
        w = torch.exp(self.log_weights)
        return w * self.num_tasks / w.sum()

    def compute_weight_loss(
        self,
        losses: list[torch.Tensor] | torch.Tensor,
        shared_params: list[nn.Parameter],
    ) -> torch.Tensor:
        """Compute GradNorm loss for weight update.

        Args:
            losses: Task losses [num_tasks]
            shared_params: Shared parameters to compute gradient norms on

        Returns:
            Loss for updating task weights
        """
        if isinstance(losses, list):
            losses = torch.stack(losses)

        # Initialize on first call
        if not self.initialized:
            self.initial_losses = losses.detach().clone()
            self.initialized = True
            return torch.tensor(0.0, device=losses.device)

        # Compute weighted losses and their gradients
        weights = self.weights
        weighted_losses = weights * losses

        # Get gradient norms for each task on shared params
        grad_norms_list: list[torch.Tensor] = []
        for _i, wl in enumerate(weighted_losses):
            # Compute gradient w.r.t. shared params
            grads = torch.autograd.grad(
                wl,
                shared_params,
                retain_graph=True,
                allow_unused=True,
            )

            # Compute norm
            norm: torch.Tensor = sum(g.norm() for g in grads if g is not None) or torch.tensor(
                0.0, device=wl.device
            )
            grad_norms_list.append(norm)

        grad_norms = torch.stack(grad_norms_list)
        mean_norm = grad_norms.mean()

        # Compute relative inverse training rate
        with torch.no_grad():
            loss_ratios = losses / (self.initial_losses + 1e-8)
            r_i = loss_ratios / loss_ratios.mean()

            # =========================================================
            # EMA SMOOTHING (Dec 3, 2025)
            # =========================================================
            # Smooth loss_ratios to prevent oscillation in weight updates
            if self.use_ema:
                # Bias correction for early steps
                ema_step = self.ema_step
                assert isinstance(ema_step, torch.Tensor)
                ema_step.add_(1)
                bias_correction = 1.0 - self.ema_momentum ** ema_step.item()

                # Update EMA of loss ratios
                ema_loss_ratios = self.ema_loss_ratios
                assert isinstance(ema_loss_ratios, torch.Tensor)
                ema_loss_ratios.copy_(
                    self.ema_momentum * ema_loss_ratios + (1 - self.ema_momentum) * r_i
                )

                # Use bias-corrected EMA for target computation
                r_i_smooth = ema_loss_ratios / bias_correction
            else:
                r_i_smooth = r_i

        # Target gradient norm for each task (using smoothed ratios)
        target_norms = mean_norm * (r_i_smooth**self.alpha)

        # =========================================================
        # EMA TARGET NORMS (Dec 3, 2025)
        # =========================================================
        # Smooth target norms to prevent sudden jumps
        if self.use_ema:
            with torch.no_grad():
                ema_target_norms = self.ema_target_norms
                assert isinstance(ema_target_norms, torch.Tensor)
                ema_target_norms.copy_(
                    self.ema_momentum * ema_target_norms + (1 - self.ema_momentum) * target_norms
                )
                target_norms_smooth = ema_target_norms / bias_correction
        else:
            target_norms_smooth = target_norms

        # GradNorm loss: minimize ||G_i - target_i||
        gradnorm_loss = torch.abs(grad_norms - target_norms_smooth).sum()

        return gradnorm_loss

    def update_weights(self, gradnorm_loss: torch.Tensor) -> None:
        """Update task weights based on GradNorm loss."""
        self.weight_optimizer.zero_grad()
        gradnorm_loss.backward(retain_graph=True)
        self.weight_optimizer.step()

        # Renormalize weights (sum to num_tasks)
        with torch.no_grad():
            self.log_weights.data -= self.log_weights.data.mean()


class CAGrad(GradientSurgery):
    """Conflict-Averse Gradient Descent (Liu et al., 2021).

    Finds a gradient direction that minimizes conflict with all tasks
    while staying close to the average gradient direction.

    Unlike PCGrad which projects pairwise, CAGrad finds the optimal
    direction that satisfies all constraints simultaneously.

    Usage:
        cagrad = CAGrad(c=0.5)
        final_grad = cagrad.compute(gradients)
    """

    def __init__(
        self,
        c: float = 0.5,
        max_iter: int = 10,
        tol: float = 1e-5,
    ) -> None:
        """Initialize CAGrad.

        Args:
            c: Convergence parameter (0 = average, 1 = min-norm in hull)
            max_iter: Maximum iterations for optimization
            tol: Convergence tolerance
        """
        super().__init__()
        self.c = c
        self.max_iter = max_iter
        self.tol = tol

    def compute(
        self,
        gradients: list[torch.Tensor] | list[list[torch.Tensor | None]],
    ) -> torch.Tensor | list[torch.Tensor | None]:
        """Compute conflict-averse gradient direction.

        Args:
            gradients: List of task gradients (flattened or list[Any] of tensors)

        Returns:
            Conflict-averse gradient direction
        """
        # Handle list[Any] of lists (per-param gradients)
        is_per_param = isinstance(gradients[0], list)
        shapes: list[torch.Size | None] | None = None
        flat_grads_or_gradients: list[torch.Tensor]

        if is_per_param:
            # Flatten each task's gradients
            flat_grads: list[torch.Tensor] = []
            grads_list = gradients if isinstance(gradients, list) else [gradients]
            for task_grads in grads_list:
                if isinstance(task_grads, list):
                    flat = []
                    if shapes is None:
                        shapes = [(g.shape if g is not None else None) for g in task_grads]
                    for g in task_grads:
                        if g is not None:
                            flat.append(g.flatten())
                    if flat:
                        flat_grads.append(torch.cat(flat))
            flat_grads_or_gradients = flat_grads
        else:
            flat_grads_or_gradients = gradients  # type: ignore[assignment]

        # Stack gradients: [num_tasks, dim]
        G = torch.stack(flat_grads_or_gradients)
        num_tasks, _dim = G.shape

        # Mean gradient
        g_mean = G.mean(dim=0)

        # If c = 0, just return mean
        if self.c == 0:
            result = g_mean
        else:
            # Iterative projection to find conflict-averse direction
            g = g_mean.clone()

            for _ in range(self.max_iter):
                g_old = g.clone()

                for i in range(num_tasks):
                    g_i = G[i]
                    dot = (g * g_i).sum()
                    threshold = self.c * (g_i.norm() ** 2)

                    if dot < threshold:
                        # Project g to satisfy constraint
                        scale = (threshold - dot) / (g_i.norm() ** 2 + 1e-8)
                        g = g + scale * g_i

                # Check convergence
                if (g - g_old).norm() < self.tol:
                    break

            result = g

        # Unflatten if needed
        if is_per_param and shapes is not None:
            result_list: list[torch.Tensor | None] = []
            offset = 0
            for shape in shapes:
                if shape is not None:
                    size = torch.prod(torch.tensor(shape)).item()
                    result_list.append(result[offset : offset + int(size)].view(shape))
                    offset += int(size)
                else:
                    result_list.append(None)
            return result_list

        return result


def apply_gradient_surgery(  # type: ignore[no-untyped-def]
    model: nn.Module,
    losses: list[torch.Tensor],
    method: str = "pcgrad",
    **kwargs,
) -> dict[str, Any]:
    """Convenience function to apply gradient surgery to a model.

    Args:
        model: PyTorch model
        losses: List of task losses
        method: "pcgrad", "cagrad", or "simple"
        **kwargs: Additional arguments for the method

    Returns:
        Dict with applied gradients and statistics
    """
    if method == "pcgrad":
        pcgrad_surgery = PCGrad(**kwargs)
        pcgrad_surgery.apply_to_model(model, losses)
        return {"method": "pcgrad", "stats": pcgrad_surgery.get_stats()}

    elif method == "cagrad":
        cagrad_surgery = CAGrad(**kwargs)

        # Compute per-task gradients
        params = list(model.parameters())
        cagrad_task_grads: list[list[torch.Tensor | None]] = []

        for i, loss in enumerate(losses):
            model.zero_grad()
            loss.backward(retain_graph=(i < len(losses) - 1))
            grads = [p.grad.clone() if p.grad is not None else None for p in params]
            cagrad_task_grads.append(grads)

        # Apply CAGrad
        final_grads_result = cagrad_surgery.compute(cagrad_task_grads)
        final_grads: list[torch.Tensor | None] = (
            final_grads_result if isinstance(final_grads_result, list) else [final_grads_result]
        )

        # Set gradients
        model.zero_grad()
        for param, grad in zip(params, final_grads, strict=False):
            if grad is not None:
                param.grad = grad

        return {"method": "cagrad", "stats": cagrad_surgery.get_stats()}

    else:  # simple
        simple_surgery = GradientSurgery(**kwargs)

        # Just average gradients (with pairwise surgery if conflicting)
        params = list(model.parameters())
        simple_task_grads: list[list[torch.Tensor | None]] = []

        for i, loss in enumerate(losses):
            model.zero_grad()
            loss.backward(retain_graph=(i < len(losses) - 1))
            grads = [p.grad.clone() if p.grad is not None else None for p in params]
            simple_task_grads.append(grads)

        # Pairwise surgery
        for i in range(len(simple_task_grads)):
            for j in range(i + 1, len(simple_task_grads)):
                if simple_surgery.detect_conflict(simple_task_grads[i], simple_task_grads[j]):
                    simple_task_grads[j] = simple_surgery.project_gradient(
                        simple_task_grads[j], simple_task_grads[i]
                    )

        # Average
        model.zero_grad()
        for j, param in enumerate(params):
            grad_j_list = [g[j] for g in simple_task_grads if g[j] is not None]
            valid_grads: list[torch.Tensor] = [
                g for g in grad_j_list if isinstance(g, torch.Tensor)
            ]
            if valid_grads:
                param.grad = torch.stack(valid_grads).mean(dim=0)

        return {"method": "simple", "stats": simple_surgery.get_stats()}


__all__ = [
    "CAGrad",
    "GradNorm",
    "GradientSurgery",
    "GradientSurgeryStats",
    "PCGrad",
    "apply_gradient_surgery",
]
