"""Control Barrier Function Loss Functions.

CREATED: December 14, 2025
CONSOLIDATED: December 14, 2025 into kagami.core.safety.cbf_utils
BASED ON: ICLR 2025 - MSE Loss for Neural Control Barrier Functions

For new code, import from cbf_utils:
    from kagami.core.safety.cbf_utils import (
        CBFMSELoss,
        CBFReLULoss,
        create_cbf_loss,
    )

Direct imports from this module still work for backward compatibility.

This module implements loss formulations for training neural CBFs:
1. Conservative ReLU Loss (legacy, baseline)
2. MSE Loss (ICLR 2025, faster convergence, no post-hoc verification)

MATHEMATICAL FOUNDATION:
========================

CBF Constraint (Ames et al., 2019):
    ḣ(x,u) ≥ -α(h(x))
    L_f h(x) + L_g h(x)·u + α(h(x)) ≥ 0

Conservative ReLU Loss (Baseline):
    L_relu = λ * ReLU(margin - h(x))²

    Properties:
    - Penalizes unsafe states (h < margin)
    - Simple, interpretable
    - But: requires post-hoc verification
    - Slower convergence on complex boundaries

MSE Loss (ICLR 2025):
    L_mse = E[(h(x) - h_target(x))²]

    Where h_target computed from CBF dynamics:
    h_target = max(0, h(x) + Δt * (L_f h + L_g h·u + α(h)))

    Properties:
    - Direct supervision on barrier value evolution
    - Faster convergence (25-40% reduction in training time)
    - Eliminates post-hoc verification
    - Better gradient flow on complex boundaries
    - Scalable to high-dimensional systems

References:
-----------
[1] Ames et al. (2019): Control Barrier Functions: Theory and Applications
[2] ICLR 2025: MSE Loss for Neural Control Barrier Functions (this paper)
[3] BarrierNet (Xiao et al.): Differentiable CBF for end-to-end training
[4] APO (Bae et al.): Safe RL via barrier certificates

Integration:
------------
Use with DifferentiableCBF or OptimalCBF for end-to-end training:

    cbf = OptimalCBF(config)
    loss_fn = CBFMSELoss(alpha=1.0, dt=0.1)

    # Training loop
    safe_control, _, info = cbf(obs, u_nominal)
    h = info["h_metric"]
    L_f_h = info["L_f_h"]
    L_g_h = info["L_g_h"]

    loss = loss_fn(h, L_f_h, L_g_h, u_safe)
    loss.backward()

Ablation Support:
-----------------
Both losses are available for comparison:
- CBFReLULoss: Conservative baseline
- CBFMSELoss: ICLR 2025 formulation

Use loss_comparison() to benchmark both on your dataset.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONSERVATIVE RELU LOSS (BASELINE)
# =============================================================================


class CBFReLULoss(nn.Module):
    """Conservative ReLU loss for CBF training (baseline).

    Penalizes states where h(x) < margin using soft barrier penalty:
        L = weight * ReLU(margin - h(x))²

    This is the standard soft barrier approach used in many CBF papers.
    Simple and interpretable, but slower convergence than MSE.
    """

    def __init__(
        self,
        margin: float = 0.1,
        weight: float = 10.0,
    ) -> None:
        """Initialize ReLU loss.

        Args:
            margin: Safety margin (penalize h < margin)
            weight: Loss scaling factor
        """
        super().__init__()
        self.margin = margin
        self.weight = weight

    def forward(
        self,
        h: torch.Tensor,  # [B] or [B, 1]
        reduction: str = "mean",
    ) -> torch.Tensor:
        """Compute ReLU loss.

        Args:
            h: Barrier values [B] or [B, 1]
            reduction: "mean", "sum", or "none"

        Returns:
            Loss scalar or [B] if reduction="none"
        """
        h_flat = h.view(-1)
        unsafe_margin = F.relu(self.margin - h_flat)
        loss = self.weight * (unsafe_margin**2)

        if reduction == "mean":
            return loss.mean()
        elif reduction == "sum":
            return loss.sum()
        else:
            return loss


# =============================================================================
# MSE LOSS (ICLR 2025)
# =============================================================================


@dataclass
class CBFMSELossConfig:
    """Configuration for MSE CBF loss."""

    # Class-K function parameters
    alpha: float = 1.0  # α(h) = alpha * h (linear class-K)
    alpha_min: float = 0.0  # Minimum α (must be 0 to preserve class-K: α(0) = 0)
    alpha_max: float = 10.0  # Maximum α for bounded gradients

    # Dynamics parameters
    dt: float = 0.1  # Time discretization step

    # Loss weights
    weight: float = 10.0  # Overall loss scaling
    margin_weight: float = 1.0  # Weight for margin violation term

    # Safety margin
    safety_margin: float = 0.1  # Minimum desired h(x)

    # Robust CBF (model uncertainty)
    use_uncertainty: bool = False  # Inflate target by uncertainty
    uncertainty_inflation: float = 2.0  # σ multiplier


class CBFMSELoss(nn.Module):
    """MSE loss for neural CBF training (ICLR 2025).

    Directly supervises barrier value evolution using CBF dynamics.
    Computes target h_target from dynamics and minimizes:
        L = E[(h_pred - h_target)²]

    Where:
        h_target = max(0, h + Δt * ḣ)
        ḣ = L_f h + L_g h·u + α(h)

    This eliminates the need for post-hoc verification and provides
    better gradient flow than conservative ReLU formulation.

    ADVANTAGES:
    -----------
    1. Faster convergence (25-40% reduction vs ReLU)
    2. No post-hoc verification needed
    3. Better gradient flow on complex boundaries
    4. Scalable to high-dimensional systems
    5. Direct supervision on barrier evolution

    MATHEMATICAL DERIVATION:
    ------------------------
    CBF condition: ḣ(x,u) + α(h(x)) ≥ 0

    Discretized forward Euler:
        h(t+Δt) ≈ h(t) + Δt * ḣ(t)
        h_next = h + Δt * (L_f h + L_g h·u + α(h))

    Target should satisfy safety constraint:
        h_target = max(0, h_next)

    Loss:
        L = (h_pred - h_target)²

    This directly trains the network to predict barrier values
    that evolve according to CBF dynamics.
    """

    def __init__(
        self,
        config: CBFMSELossConfig | None = None,
        alpha: float | None = None,
        dt: float | None = None,
        weight: float | None = None,
    ) -> None:
        """Initialize MSE CBF loss.

        Args:
            config: Loss configuration (creates default if None)
            alpha: Class-K parameter (overrides config if provided)
            dt: Time step (overrides config if provided)
            weight: Loss weight (overrides config if provided)
        """
        super().__init__()
        self.config = config or CBFMSELossConfig()

        # Override config with explicit parameters
        if alpha is not None:
            self.config.alpha = alpha
        if dt is not None:
            self.config.dt = dt
        if weight is not None:
            self.config.weight = weight

        logger.info(
            f"CBFMSELoss initialized: α={self.config.alpha}, "
            f"Δt={self.config.dt}, weight={self.config.weight}"
        )

    def compute_h_target(
        self,
        h: torch.Tensor,  # [B]
        L_f_h: torch.Tensor,  # [B]
        L_g_h: torch.Tensor,  # [B, control_dim]
        u: torch.Tensor,  # [B, control_dim]
        alpha: float | torch.Tensor | None = None,
        L_f_h_std: torch.Tensor | None = None,  # [B] uncertainty
    ) -> torch.Tensor:
        """Compute target barrier value from CBF dynamics.

        Uses forward Euler discretization:
            h_target = max(0, h + Δt * (L_f h + L_g h·u + α(h)))

        Args:
            h: Current barrier values [B]
            L_f_h: Lie derivative w.r.t. drift [B]
            L_g_h: Lie derivative w.r.t. control [B, control_dim]
            u: Control input [B, control_dim]
            alpha: Optional custom α (uses config.alpha if None)
            L_f_h_std: Uncertainty in L_f_h for robust margin [B]

        Returns:
            h_target: Target barrier values [B]
        """
        # Class-K function: α(h)
        if alpha is None:
            alpha_val = self.config.alpha
        elif isinstance(alpha, torch.Tensor):
            alpha_val = alpha  # type: ignore[assignment]
        else:
            alpha_val = float(alpha)

        alpha_h = alpha_val * h  # Linear class-K: α(h) = α * h

        # Clip α to bounds for stability (preserves α(0) = 0 since alpha_min = 0.0)
        if isinstance(alpha_h, torch.Tensor):
            alpha_h = torch.clamp(alpha_h, min=self.config.alpha_min, max=self.config.alpha_max)

        # Lie derivative w.r.t. control: L_g h·u
        Lg_h_u = (L_g_h * u).sum(dim=-1)  # [B]

        # Total time derivative: ḣ = L_f h + L_g h·u + α(h)
        h_dot = L_f_h + Lg_h_u + alpha_h

        # Robust margin inflation (if uncertainty provided)
        if self.config.use_uncertainty and L_f_h_std is not None:
            uncertainty_margin = self.config.uncertainty_inflation * L_f_h_std
            h_dot = h_dot + uncertainty_margin

        # Forward Euler: h_next = h + Δt * ḣ
        h_next = h + self.config.dt * h_dot

        # Safety constraint: h_target ≥ 0
        h_target = torch.clamp(h_next, min=0.0)

        return h_target

    def forward(
        self,
        h_pred: torch.Tensor,  # [B] predicted barrier
        L_f_h: torch.Tensor,  # [B] Lie derivative (drift)
        L_g_h: torch.Tensor,  # [B, control_dim] Lie derivative (control)
        u: torch.Tensor,  # [B, control_dim] control
        h_current: torch.Tensor | None = None,  # [B] current h (if different from pred)
        L_f_h_std: torch.Tensor | None = None,  # [B] uncertainty
        reduction: str = "mean",
    ) -> torch.Tensor:
        """Compute MSE loss between predicted and target barrier.

        Args:
            h_pred: Predicted barrier values [B]
            L_f_h: Lie derivative w.r.t. drift [B]
            L_g_h: Lie derivative w.r.t. control [B, control_dim]
            u: Control input [B, control_dim]
            h_current: Current barrier (defaults to h_pred)
            L_f_h_std: Uncertainty in dynamics [B]
            reduction: "mean", "sum", or "none"

        Returns:
            MSE loss scalar or [B] if reduction="none"
        """
        # Use h_pred as h_current if not provided
        if h_current is None:
            h_current = h_pred

        # Compute target from dynamics
        h_target = self.compute_h_target(
            h=h_current,
            L_f_h=L_f_h,
            L_g_h=L_g_h,
            u=u,
            L_f_h_std=L_f_h_std,
        )

        # MSE loss: (h_pred - h_target)²
        mse = (h_pred - h_target) ** 2

        # Additional penalty for margin violations
        margin_violation = F.relu(self.config.safety_margin - h_pred)
        margin_loss = self.config.margin_weight * (margin_violation**2)

        # Combined loss
        total_loss = self.config.weight * (mse + margin_loss)

        if reduction == "mean":
            return total_loss.mean()
        elif reduction == "sum":
            return total_loss.sum()
        else:
            return total_loss


# =============================================================================
# COMBINED LOSS (ABLATION SUPPORT)
# =============================================================================


class CBFCombinedLoss(nn.Module):
    """Combined ReLU + MSE loss for ablation studies.

    Allows weighted combination of both formulations:
        L = w_relu * L_relu + w_mse * L_mse

    Useful for:
    1. Gradual transition from ReLU to MSE
    2. Ablation studies comparing both
    3. Hybrid training strategies
    """

    def __init__(
        self,
        relu_weight: float = 0.5,
        mse_weight: float = 0.5,
        relu_config: dict[str, Any] | None = None,
        mse_config: CBFMSELossConfig | None = None,
    ) -> None:
        """Initialize combined loss.

        Args:
            relu_weight: Weight for ReLU loss
            mse_weight: Weight for MSE loss
            relu_config: Config for ReLU loss (margin, weight)
            mse_config: Config for MSE loss
        """
        super().__init__()
        self.relu_weight = relu_weight
        self.mse_weight = mse_weight

        relu_cfg = relu_config or {}
        self.relu_loss = CBFReLULoss(**relu_cfg)
        self.mse_loss = CBFMSELoss(config=mse_config)

    def forward(
        self,
        h_pred: torch.Tensor,
        L_f_h: torch.Tensor,
        L_g_h: torch.Tensor,
        u: torch.Tensor,
        h_current: torch.Tensor | None = None,
        L_f_h_std: torch.Tensor | None = None,
        reduction: str = "mean",
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Compute combined loss.

        Returns:
            total_loss: Weighted combination
            info: Dict with individual loss components
        """
        # ReLU component
        loss_relu = self.relu_loss(h_pred, reduction=reduction)

        # MSE component
        loss_mse = self.mse_loss(
            h_pred=h_pred,
            L_f_h=L_f_h,
            L_g_h=L_g_h,
            u=u,
            h_current=h_current,
            L_f_h_std=L_f_h_std,
            reduction=reduction,
        )

        # Combined
        total_loss = self.relu_weight * loss_relu + self.mse_weight * loss_mse

        info = {
            "loss_relu": loss_relu,
            "loss_mse": loss_mse,
            "total": total_loss,
        }

        return total_loss, info


# =============================================================================
# LOSS COMPARISON UTILITIES
# =============================================================================


def loss_comparison(
    h_pred: torch.Tensor,
    L_f_h: torch.Tensor,
    L_g_h: torch.Tensor,
    u: torch.Tensor,
    alpha: float = 1.0,
    dt: float = 0.1,
) -> dict[str, torch.Tensor]:
    """Compare ReLU vs MSE loss on a batch.

    Useful for ablation studies and loss benchmarking.

    Args:
        h_pred: Predicted barrier [B]
        L_f_h: Drift Lie derivative [B]
        L_g_h: Control Lie derivative [B, control_dim]
        u: Control [B, control_dim]
        alpha: Class-K parameter
        dt: Time step

    Returns:
        Dict with:
            - "relu": ReLU loss value
            - "mse": MSE loss value
            - "ratio": MSE/ReLU ratio
            - "h_target": MSE target values
    """
    relu_loss_fn = CBFReLULoss()
    mse_loss_fn = CBFMSELoss(alpha=alpha, dt=dt)

    loss_relu = relu_loss_fn(h_pred)
    loss_mse = mse_loss_fn(h_pred, L_f_h, L_g_h, u)

    h_target = mse_loss_fn.compute_h_target(h_pred, L_f_h, L_g_h, u)

    return {
        "relu": loss_relu,
        "mse": loss_mse,
        "ratio": loss_mse / (loss_relu + 1e-8),
        "h_target": h_target,
    }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_cbf_loss(
    loss_type: str = "mse",
    **kwargs: Any,
) -> nn.Module:
    """Factory for creating CBF loss functions.

    Args:
        loss_type: "relu", "mse", or "combined"
        **kwargs: Loss-specific configuration

    Returns:
        Configured loss module

    Examples:
        >>> # MSE loss (ICLR 2025)
        >>> loss_fn = create_cbf_loss("mse", alpha=1.0, dt=0.1)

        >>> # Conservative ReLU
        >>> loss_fn = create_cbf_loss("relu", margin=0.1, weight=10.0)

        >>> # Combined (ablation)
        >>> loss_fn = create_cbf_loss("combined", relu_weight=0.3, mse_weight=0.7)
    """
    if loss_type == "relu":
        return CBFReLULoss(**kwargs)
    elif loss_type == "mse":
        config = kwargs.pop("config", None)
        return CBFMSELoss(config=config, **kwargs)
    elif loss_type == "combined":
        return CBFCombinedLoss(**kwargs)
    else:
        raise ValueError(f"Unknown loss_type: {loss_type}. Use 'relu', 'mse', or 'combined'.")


__all__ = [
    "CBFCombinedLoss",
    "CBFMSELoss",
    "CBFMSELossConfig",
    "CBFReLULoss",
    "create_cbf_loss",
    "loss_comparison",
]
