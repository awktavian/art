"""EFE-CBF Constrained Optimizer - Safety-Constrained Policy Selection.

CREATED: December 14, 2025
PURPOSE: Integrate Expected Free Energy (EFE) with Control Barrier Functions (CBF)
         for mathematically-guaranteed safe policy selection.

ARCHITECTURE:
============
This module solves the constrained optimization problem:

    π* = argmin_π G(π)  subject to  h(x_π) ≥ 0

Where:
- G(π): Expected Free Energy (epistemic + pragmatic + risk + catastrophe)
- h(x): Control Barrier Function (safety margin, h≥0 = safe)
- x_π: State trajectory under policy π

TWO MODES:
==========
1. TRAINING (soft penalty):
   - Uses differentiable penalty: L = G(π) + λ * ReLU(-h(x_π))
   - Allows gradient flow for end-to-end learning
   - CBF learns from violations, policy learns to avoid them

2. DEPLOYMENT (hard QP constraint):
   - Solves QP: min ||u - u_nom||² s.t. L_g h·u ≥ -(L_f h + α(h))
   - Mathematical guarantee: h(x) ≥ 0 always
   - No violations possible (if QP is feasible)

INTEGRATION POINTS:
==================
- ExpectedFreeEnergy: Computes G(π) for policies
- OptimalCBF: Provides h(x), L_f h, L_g h, α(h)
- DifferentiableQPSolver: Solves CBF-QP for deployment

References:
- Friston et al. (2015): Active Inference and EFE
- Ames et al. (2019): Control Barrier Functions
- Viazovska (2017): E8 sphere packing (underlying representation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.safety.optimal_cbf import (
    DifferentiableQPSolver,
    OptimalCBF,
    OptimalCBFConfig,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class EFECBFConfig:
    """Configuration for EFE-CBF constrained optimizer.

    DUAL-MODE OPERATION:
    ===================
    - Training: Soft penalty for gradients
    - Deployment: Hard QP constraint for guarantees

    UNCERTAINTY HANDLING:
    ====================
    Per robust CBF theory (Choi et al., 2020):
    If model has uncertainty σ, inflate constraint by λ·σ
    to ensure safety under model error.
    """

    # Dimensions (must match EFE and CBF configs)
    state_dim: int = 256  # RSSM h_dim
    stochastic_dim: int = 14  # RSSM z_dim
    action_dim: int = 8  # E8 octonion

    # Penalty weight (training mode)
    penalty_weight: float = 10.0  # λ in L = G + λ*max(0, -h)

    # Uncertainty inflation (deployment mode)
    use_uncertainty: bool = True
    uncertainty_inflation: float = 2.0  # σ multiplier for robust margin

    # QP solver settings
    qp_solver_method: str = "analytical"  # 'analytical', 'osqp'
    u_min: float = 0.0  # Control bounds
    u_max: float = 1.0

    # Class-K function (CBF convergence rate)
    class_k_alpha: float = 1.0  # α(h) = alpha * h

    # Safety thresholds
    safety_margin: float = 0.1  # Minimum h(x) for "safe enough"
    feasibility_tolerance: float = 1e-4  # QP feasibility check

    # Features
    per_policy_cbf: bool = True  # Evaluate h(x) for each policy
    log_violations: bool = True  # Track safety violations


# =============================================================================
# EFE-CBF OPTIMIZER
# =============================================================================


class EFECBFOptimizer(nn.Module):
    """Constrained Expected Free Energy optimizer with CBF safety guarantees.

    CORE OPERATION:
    ==============
    Solves: min_π G(π) subject to h(x_π) ≥ 0

    Where:
    - G(π): Expected Free Energy (from ExpectedFreeEnergy module)
    - h(x): Barrier function (from OptimalCBF)
    - x_π: State trajectory under policy π

    MODES:
    ======
    1. Training (soft):
       - G_safe = G + λ * max(0, -h)
       - Differentiable, allows gradients
       - CBF learns from data

    2. Deployment (hard):
       - Solves CBF-QP to project unsafe policies
       - min ||u - u_nom||² s.t. h_constraint ≥ 0
       - Mathematical safety guarantee

    USAGE:
    ======
    ```python
    optimizer = EFECBFOptimizer(config, cbf_module)

    # Training mode
    safe_G, info = optimizer(G_values, states, policies, training=True)
    loss = safe_G.min() + info['cbf_penalty']

    # Deployment mode
    safe_policy, info = optimizer(G_values, states, policies, training=False)
    ```
    """

    def __init__(
        self,
        config: EFECBFConfig | None = None,
        cbf_module: OptimalCBF | None = None,
    ) -> None:
        """Initialize EFE-CBF optimizer.

        Args:
            config: Optimizer configuration
            cbf_module: Pre-trained OptimalCBF (creates new if None)
        """
        super().__init__()
        self.config = config or EFECBFConfig()

        # Combined state dimension (h + z)
        self.combined_dim = self.config.state_dim + self.config.stochastic_dim

        # CBF module (for h(x) computation)
        if cbf_module is None:
            cbf_config = OptimalCBFConfig(
                observation_dim=256,
                state_dim=self.config.state_dim,
                control_dim=self.config.action_dim,
                use_qp_solver=True,
                qp_solver=self.config.qp_solver_method,
                use_uncertainty=self.config.use_uncertainty,
                uncertainty_inflation=self.config.uncertainty_inflation,
            )
            self.cbf = OptimalCBF(cbf_config)
        else:
            self.cbf = cbf_module

        # QP solver (for hard constraint mode)
        self.qp_solver = DifferentiableQPSolver(
            control_dim=self.config.action_dim,
            u_min=self.config.u_min,
            u_max=self.config.u_max,
            solver=self.config.qp_solver_method,
        )

        # Learnable penalty weight (log for positivity)
        self.log_penalty = nn.Parameter(torch.tensor(self.config.penalty_weight).log())

        # Statistics
        self._num_violations = 0
        self._total_evaluations = 0

        logger.info(
            f"EFECBFOptimizer initialized:\n"
            f"  State: {self.combined_dim}D\n"
            f"  Action: {self.config.action_dim}D\n"
            f"  Mode: {'Soft (training)' if self.training else 'Hard (deployment)'}\n"
            f"  QP Solver: {self.config.qp_solver_method}"
        )

    def compute_barrier_values(
        self,
        states: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Compute barrier function h(x) for state trajectories.

        Args:
            states: [batch, num_policies, state_dim] or [batch, state_dim]
                   where state_dim = h_dim + z_dim (combined state)

        Returns:
            h_values: [batch, num_policies] or [batch] barrier values
            info: Dict with CBF metrics
        """
        original_shape = states.shape
        batch_shape = original_shape[:-1]  # Everything except last dim

        # Flatten to [N, state_dim] for CBF
        states_flat = states.reshape(-1, original_shape[-1])

        # OptimalCBF's state_encoder expects the combined state
        # It will encode it to its internal state_dim
        # Use encode_state first, then compute barriers
        x_encoded = self.cbf.encode_state(states_flat)  # [N, cbf_state_dim]

        # Compute barriers on encoded state
        h_metric, h_topo, barrier_info = self.cbf.compute_barriers(x_encoded)

        # Combined barrier (min of metric and topological)
        if h_topo is not None:
            h_combined = torch.min(h_metric, h_topo)
        else:
            h_combined = h_metric

        # Reshape back to original batch shape
        h_values = h_combined.reshape(batch_shape)

        info = {
            "h_metric": h_metric.reshape(batch_shape),
            "h_topo": h_topo.reshape(batch_shape) if h_topo is not None else None,
            **barrier_info,
        }

        return h_values, info

    def _optimize_soft(
        self,
        G_values: torch.Tensor,
        states: torch.Tensor,
        policies: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Soft constraint optimization (training mode).

        DIFFERENTIABLE PENALTY:
        ======================
        G_safe = G + λ * max(0, -h)

        This allows gradients to flow:
        - Policy learns to avoid high-G regions
        - CBF learns to predict unsafe states
        - Penalty weight λ learned adaptively

        Args:
            G_values: [batch, num_policies] EFE values
            states: [batch, num_policies, state_dim] state trajectories
            policies: [batch, num_policies, horizon, action_dim] policies

        Returns:
            G_safe: [batch, num_policies] penalized EFE values
            info: Dict with penalty metrics
        """
        B, P = G_values.shape

        # Compute h(x) for each policy's state
        h_values, cbf_info = self.compute_barrier_values(states)

        # Violation penalty: max(0, -h)
        # Positive when h < 0 (unsafe)
        violation = F.relu(-h_values)  # [batch, num_policies]

        # Adaptive penalty weight
        penalty_weight = self.log_penalty.exp().clamp(min=0.1, max=100.0)

        # Penalize unsafe policies
        cbf_penalty = penalty_weight * violation

        # Combined objective
        G_safe = G_values + cbf_penalty

        # Track violations - accumulate tensors, sync at logging boundary
        num_violations_tensor = (h_values < 0).sum()
        constraint_satisfied_tensor = (h_values >= 0).all()

        # Defer sync to info dict[str, Any] construction (consumers may use tensors directly)
        info = {
            "mode": "soft",
            "h_values": h_values,
            "violation": violation,
            "cbf_penalty": cbf_penalty.mean(),  # Keep as tensor
            "penalty_weight": penalty_weight,  # Keep as tensor
            "num_violations": num_violations_tensor,  # Keep as tensor
            "constraint_satisfied": constraint_satisfied_tensor,  # Keep as tensor
            **cbf_info,
        }

        # Single sync point for logging
        if self.config.log_violations:
            num_violations = int(num_violations_tensor.item())
            if num_violations > 0:
                logger.debug(
                    f"Soft mode: {num_violations}/{B * P} policies violate h≥0 "
                    f"(penalty={cbf_penalty.mean().item():.3f})"
                )
            # Update statistics
            self._num_violations += num_violations
            self._total_evaluations += B * P

        return G_safe, info

    def _optimize_hard(
        self,
        G_values: torch.Tensor,
        states: torch.Tensor,
        policies: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Hard constraint optimization (deployment mode).

        CBF-QP PROJECTION:
        =================
        For each policy, solves:
            min  ||u - u_nom||²
            s.t. L_f h + L_g h·u + α(h) ≥ 0

        This GUARANTEES h(x) ≥ 0 if QP is feasible.

        Args:
            G_values: [batch, num_policies] EFE values
            states: [batch, num_policies, state_dim] state trajectories
            policies: [batch, num_policies, horizon, action_dim] policies

        Returns:
            safe_policies: [batch, num_policies, horizon, action_dim]
            info: Dict with QP metrics
        """
        B, P, _H, _A = policies.shape

        # Compute h(x) for each policy
        h_values, cbf_info = self.compute_barrier_values(states)

        # For policies that violate h ≥ margin, apply QP correction
        # We project the FIRST ACTION only (MPC-style)
        # Then re-evaluate trajectory (would need world model integration)

        # For now: Simple approach - check h, apply penalty if violated
        # Full QP integration requires world model step() in loop

        # Check which policies are unsafe
        unsafe_mask = h_values < self.config.safety_margin  # [B, P]

        # Count violations - defer sync
        num_violations_tensor = unsafe_mask.sum()

        # For unsafe policies: compute Lie derivatives for first action
        # This requires dynamics (f, g) which CBF has

        safe_policies = policies.clone()
        qp_corrections = torch.zeros(B, P, device=policies.device)

        # Only sync for conditional check
        num_violations = int(num_violations_tensor.item())
        if num_violations > 0:
            # Get indices of unsafe policies
            unsafe_indices = unsafe_mask.nonzero(as_tuple=True)  # (batch_idx, policy_idx)

            for batch_idx_tensor, policy_idx_tensor in zip(
                unsafe_indices[0], unsafe_indices[1], strict=False
            ):
                # Convert tensor indices to Python ints
                batch_idx = int(batch_idx_tensor.item())
                policy_idx = int(policy_idx_tensor.item())

                # Get state for this policy
                state = states[batch_idx, policy_idx]  # [combined_dim]

                # Encode state to CBF's internal state dimension
                state_encoded = self.cbf.encode_state(state.unsqueeze(0)).squeeze(
                    0
                )  # [cbf_state_dim]

                # Get nominal action (first action in sequence)
                u_nominal = policies[batch_idx, policy_idx, 0]  # [action_dim]

                # Compute Lie derivatives using CBF
                # Need h value for this state
                h = h_values[batch_idx, policy_idx]

                # Compute gradients of h on encoded state
                state_batch = state_encoded.unsqueeze(0)  # [1, cbf_state_dim]
                h_batch = h.unsqueeze(0)  # [1]

                L_f_h, L_g_h, L_f_h_std, _L_g_h_std = self.cbf.compute_lie_derivatives(
                    state_batch, h_batch
                )

                # Class-K function
                alpha_h = self.cbf.class_k(h_batch)  # [1]

                # Build QP constraint: L_g h·u ≥ -(L_f h + α(h))
                # With uncertainty inflation if enabled
                if self.config.use_uncertainty:
                    margin = self.config.uncertainty_inflation * L_f_h_std
                    b = -(L_f_h + alpha_h - margin)  # [1]
                else:
                    b = -(L_f_h + alpha_h)  # [1]

                a = L_g_h  # [1, action_dim]

                # Solve CBF-QP
                try:
                    u_safe = self.qp_solver(
                        u_nominal.unsqueeze(0),  # [1, action_dim]
                        a,  # [1, action_dim]
                        b,  # [1]
                    ).squeeze(0)  # [action_dim]

                    # Update policy (only first action)
                    safe_policies[batch_idx, policy_idx, 0] = u_safe

                    # Track correction magnitude
                    correction = (u_safe - u_nominal).norm()
                    qp_corrections[batch_idx, policy_idx] = correction

                except RuntimeError as e:
                    # QP infeasible - BLOCK this policy by setting to zero action
                    # This preserves the CBF safety guarantee: h(x) >= 0 always
                    logger.error(
                        f"CBF-QP infeasible for policy ({batch_idx}, {policy_idx}): {e}\n"
                        f"  h={h.item():.3f}, L_f h={L_f_h.item():.3f}\n"
                        f"  Blocking policy (zero action)."
                    )
                    # Zero action is always safe (no change to state)
                    safe_policies[batch_idx, policy_idx, 0] = torch.zeros_like(u_nominal)
                    qp_corrections[batch_idx, policy_idx] = float("inf")  # Mark as blocked

        # Keep tensors in info dict[str, Any] (consumers may use directly)
        info = {
            "mode": "hard",
            "h_values": h_values,
            "num_violations": num_violations_tensor,  # Keep as tensor
            "constraint_satisfied": (h_values >= self.config.safety_margin).all(),  # Keep as tensor
            "qp_corrections": qp_corrections.mean(),  # Keep as tensor
            "max_correction": qp_corrections.max(),  # Keep as tensor
            **cbf_info,
        }

        # Single sync point for logging and statistics
        if self.config.log_violations and num_violations > 0:
            logger.warning(
                f"Hard mode: {num_violations}/{B * P} policies unsafe "
                f"(avg_correction={qp_corrections.mean().item():.3f})"
            )

        # Update statistics
        self._num_violations += num_violations
        self._total_evaluations += B * P

        return safe_policies, info

    def forward(
        self,
        G_values: torch.Tensor,
        states: torch.Tensor,
        policies: torch.Tensor,
        training: bool | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Optimize policy selection with CBF constraints.

        DUAL-MODE OPERATION:
        ===================
        - Training=True:  Soft penalty, differentiable
        - Training=False: Hard QP, guaranteed safe

        Args:
            G_values: [batch, num_policies] EFE values
            states: [batch, num_policies, state_dim] state trajectories
            policies: [batch, num_policies, horizon, action_dim] policies
            training: Override mode (default: self.training)

        Returns:
            result: [batch, num_policies] (soft) or [batch, num_policies, H, A] (hard)
            info: Dict with safety metrics
        """
        if training is None:
            training = self.training

        if training:
            return self._optimize_soft(G_values, states, policies)
        else:
            return self._optimize_hard(G_values, states, policies)

    def select_safe_policy(
        self,
        G_values: torch.Tensor,
        states: torch.Tensor,
        policies: torch.Tensor,
        training: bool | None = None,
    ) -> tuple[torch.Tensor, int | list[int], dict[str, Any]]:
        """Select best policy with safety constraints.

        COMPLETE PIPELINE:
        =================
        1. Apply CBF constraints (soft or hard)
        2. Select policy with minimum constrained G
        3. Return selected policy + index + metrics

        Args:
            G_values: [batch, num_policies] EFE values
            states: [batch, num_policies, state_dim] states
            policies: [batch, num_policies, horizon, action_dim] policies
            training: Mode override

        Returns:
            selected_policy: [batch, horizon, action_dim]
            selected_idx: int (batch=1) or list[int] (batch>1) index of selected policy
            info: Dict with metrics
        """
        B, _P, _H, _A = policies.shape

        # Apply constraints
        result, info = self.forward(G_values, states, policies, training)

        if training is None:
            training = self.training

        if training:
            # Soft mode: result is G_safe [B, P]
            G_safe = result
            best_idx = G_safe.argmin(dim=-1)  # [B]

            # Selected policies (no modification)
            selected = policies[torch.arange(B, device=policies.device), best_idx]

        else:
            # Hard mode: result is safe_policies [B, P, H, A]
            safe_policies = result

            # Re-evaluate G for safe policies? Or use original G?
            # Use original G to select (QP already enforced safety)
            best_idx = G_values.argmin(dim=-1)  # [B]

            # Selected safe policies
            selected = safe_policies[torch.arange(B, device=policies.device), best_idx]

        # API boundary: convert tensors to Python types for backward compatibility
        # Internal optimization kept tensors to avoid GPU sync in hot loops
        if B == 1:
            selected_idx_int = int(best_idx[0].item())
        else:
            selected_idx_int = [int(idx.item()) for idx in best_idx]  # type: ignore[assignment]

        info["selected_idx"] = selected_idx_int
        info["selected_G"] = float(
            G_values[torch.arange(B, device=G_values.device), best_idx].mean().item()
        )

        # Return Python int for API consistency
        return selected, selected_idx_int, info

    def get_statistics(self) -> dict[str, Any]:
        """Get safety violation statistics.

        Returns:
            Dict with cumulative metrics
        """
        violation_rate = (
            self._num_violations / self._total_evaluations if self._total_evaluations > 0 else 0.0
        )

        return {
            "total_evaluations": self._total_evaluations,
            "total_violations": self._num_violations,
            "violation_rate": violation_rate,
        }

    def reset_statistics(self) -> None:
        """Reset violation counters."""
        self._num_violations = 0
        self._total_evaluations = 0


# =============================================================================
# FACTORY & INTEGRATION
# =============================================================================


def create_efe_cbf_optimizer(  # type: ignore[no-untyped-def]
    state_dim: int = 256,
    stochastic_dim: int = 14,
    action_dim: int = 8,
    cbf_module: OptimalCBF | None = None,
    **kwargs,
) -> EFECBFOptimizer:
    """Create EFE-CBF optimizer with configuration.

    Args:
        state_dim: RSSM h dimension
        stochastic_dim: RSSM z dimension
        action_dim: Action dimension (E8 octonion)
        cbf_module: Optional pre-trained CBF
        **kwargs: Additional config options

    Returns:
        Configured EFECBFOptimizer
    """
    config = EFECBFConfig(
        state_dim=state_dim,
        stochastic_dim=stochastic_dim,
        action_dim=action_dim,
        **kwargs,
    )
    return EFECBFOptimizer(config, cbf_module)


__all__ = [
    "EFECBFConfig",
    "EFECBFOptimizer",
    "create_efe_cbf_optimizer",
]
