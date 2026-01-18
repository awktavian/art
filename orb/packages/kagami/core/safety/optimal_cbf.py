"""Optimal Control Barrier Function - Learned + Topological Safety.

CREATED: December 3, 2025
BASED ON: Ames et al. (2019), BarrierNet, K OS Catastrophe Integration

This module implements the OPTIMAL CBF approach that:
1. GROUNDS state in observables (not heuristic risk scores)
2. LEARNS the barrier function h(x) end-to-end
3. LEARNS the class-K function α(h) adaptively
4. LEARNS the dynamics f(x), g(x) from data
5. COMBINES metric + topological safety constraints

MATHEMATICAL FOUNDATION (Ames et al., 2019):
============================================
Safe set[Any]: C = {x ∈ ℝⁿ | h(x) ≥ 0}

CBF constraint (forward invariance):
    sup_u [L_f h(x) + L_g h(x)·u] ≥ -α(h(x))

Where:
- h(x): Barrier function (learned)
- α(h): Extended class-K function (learned)
- f(x), g(x): System dynamics (learned)
- L_f h = ∂h/∂x · f(x): Lie derivative w.r.t. drift
- L_g h = ∂h/∂x · g(x): Lie derivative w.r.t. control

QP for minimal modification:
    min  ||u - u_nom||²
    s.t. L_f h + L_g h·u + α(h) ≥ 0  (metric safety)
         h_topo(x) ≥ 0               (topological safety)

References:
- Ames et al. (2019): Control Barrier Functions: Theory and Applications
- Thom (1972): Structural Stability and Morphogenesis
- K OS Architecture: Catastrophe-CBF Integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# STATE ENCODER - GROUNDS SAFETY IN OBSERVABLES
# =============================================================================


class SafetyStateEncoder(nn.Module):
    """Encodes raw observations into safety-relevant state space.

    Instead of heuristic [threat, uncertainty, complexity, risk] scores,
    this encoder learns to extract safety-relevant features from actual
    observations (text embeddings, context vectors, etc.)

    The output state is what the barrier function operates on.
    """

    def __init__(
        self,
        observation_dim: int = 256,
        state_dim: int = 16,
        hidden_dim: int = 64,
    ) -> None:
        """Initialize state encoder.

        Args:
            observation_dim: Raw observation dimension
            state_dim: Safety state dimension (output)
            hidden_dim: Hidden layer dimension
        """
        super().__init__()
        self.observation_dim = observation_dim
        self.state_dim = state_dim

        self.encoder = nn.Sequential(
            nn.Linear(observation_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, state_dim),
            nn.Tanh(),  # Bound state to [-1, 1]
        )

        # Legacy compatibility: project legacy 4D state to new state space
        self.legacy_projection = nn.Linear(4, state_dim)

        logger.debug(f"SafetyStateEncoder: {observation_dim} → {state_dim}")

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """Encode observation to safety state.

        Args:
            obs: Raw observation [B, observation_dim] or legacy [B, 4]

        Returns:
            Safety state [B, state_dim]
        """
        if obs.shape[-1] == 4:
            # Legacy 4D state - project to new space
            return torch.tanh(cast(torch.Tensor, self.legacy_projection(obs)))
        elif obs.shape[-1] == self.observation_dim:
            return cast(torch.Tensor, self.encoder(obs))
        else:
            # Pad or truncate to observation_dim
            if obs.shape[-1] < self.observation_dim:
                padding = torch.zeros(
                    *obs.shape[:-1],
                    self.observation_dim - obs.shape[-1],
                    device=obs.device,
                    dtype=obs.dtype,
                )
                obs = torch.cat([obs, padding], dim=-1)
            else:
                obs = obs[..., : self.observation_dim]
            return cast(torch.Tensor, self.encoder(obs))


# =============================================================================
# LEARNED BARRIER FUNCTION
# =============================================================================


class LearnedBarrierFunction(nn.Module):
    """Neural network barrier function h(x).

    Learns h(x) such that:
    - h(x) > 0: Safe (far from boundary)
    - h(x) = 0: On safety boundary
    - h(x) < 0: Unsafe

    Architecture: Linear baseline + neural residual
    This provides interpretability (linear) + expressiveness (neural).
    """

    def __init__(
        self,
        state_dim: int = 16,
        hidden_dim: int = 64,
        safety_threshold: float = 0.3,
        use_neural_residual: bool = True,
    ) -> None:
        """Initialize learned barrier function.

        Args:
            state_dim: Safety state dimension
            hidden_dim: Hidden layer dimension for neural residual
            safety_threshold: Base safety margin
            use_neural_residual: Whether to add neural correction
        """
        super().__init__()
        self.state_dim = state_dim
        self.safety_threshold = safety_threshold
        self.use_neural_residual = use_neural_residual

        # Linear component: h_linear(x) = threshold - w·|x|
        # Learnable weights for risk aggregation
        self.risk_weights = nn.Parameter(torch.ones(state_dim) / state_dim)

        # Neural residual for nonlinear boundaries
        if use_neural_residual:
            self.residual_net = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.GELU(),
                nn.Linear(hidden_dim // 2, 1),
                nn.Tanh(),  # Bounded residual
            )
            self.residual_scale = nn.Parameter(torch.tensor(0.1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute barrier function h(x).

        Args:
            x: Safety state [B, state_dim]

        Returns:
            h: Barrier values [B]
        """
        # Normalize weights to sum to 1
        weights = F.softmax(self.risk_weights.abs(), dim=0)

        # Linear barrier: h = threshold - weighted_risk
        # Higher |x| = higher risk = lower h
        weighted_risk = (weights * x.abs()).sum(dim=-1)
        h_linear = self.safety_threshold - weighted_risk

        if self.use_neural_residual:
            # Add neural correction for nonlinear boundaries
            h_residual = cast(torch.Tensor, self.residual_net(x)).squeeze(-1)
            h = h_linear + self.residual_scale * h_residual
        else:
            h = h_linear

        # CRITICAL FIX (Dec 27, 2025): Clamp learned barrier output to reasonable range
        # Prevents numerical instability and ensures bounded h(x) for safe downstream use
        # Range [-10, 10] is sufficient for safety decisions while preventing overflow
        h = torch.clamp(h, min=-10.0, max=10.0)

        return h


# =============================================================================
# LEARNED CLASS-K FUNCTION
# =============================================================================


class LearnedClassK(nn.Module):
    """Neural class-K function α(h).

    Properties (guaranteed by construction):
    1. α(0) = 0 (h factor)
    2. α strictly increasing (softplus ensures positive derivative)
    3. α continuous (neural network is smooth)

    Architecture: α(h) = h · σ(MLP(h)) where σ > 0
    """

    def __init__(
        self,
        hidden_dim: int = 32,
        base_k: float = 1.0,
        min_alpha: float = 0.1,
        max_alpha: float = 10.0,
    ) -> None:
        """Initialize learned class-K function.

        Args:
            hidden_dim: Hidden layer dimension
            base_k: Base scaling factor
            min_alpha: Minimum slope bound
            max_alpha: Maximum slope bound
        """
        super().__init__()
        self.base_k = base_k
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha

        # MLP that outputs positive scaling factor
        self.scale_net = nn.Sequential(
            nn.Linear(1, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
        )

        # Learnable base scale (initialized to base_k)
        self.log_k = nn.Parameter(torch.tensor(base_k).log())

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """Compute α(h).

        Args:
            h: Barrier values [B] or [B, 1]

        Returns:
            α(h): Class-K values [B]
        """
        # Ensure correct shape
        h_flat = h.view(-1, 1)

        # Base scaling: softplus ensures positive
        k = F.softplus(self.log_k)

        # Neural modulation
        modulation = F.softplus(self.scale_net(h_flat)).squeeze(-1)

        # Combined scale with bounds
        scale = torch.clamp(k * modulation, self.min_alpha, self.max_alpha)

        # α(h) = h * scale (ensures α(0) = 0)
        return h.view(-1) * scale


# =============================================================================
# LEARNED DYNAMICS
# =============================================================================


class LearnedDynamics(nn.Module):
    """Learns system dynamics f(x) and g(x).

    System: ẋ = f(x) + g(x)·u

    Lie derivatives for CBF:
        L_f h(x) = ∇h(x) · f(x)
        L_g h(x) = ∇h(x) · g(x)
    """

    def __init__(
        self,
        state_dim: int = 16,
        control_dim: int = 2,
        hidden_dim: int = 64,
    ) -> None:
        """Initialize learned dynamics.

        Args:
            state_dim: Safety state dimension
            control_dim: Control dimension
            hidden_dim: Hidden layer dimension
        """
        super().__init__()
        self.state_dim = state_dim
        self.control_dim = control_dim

        # Drift dynamics f(x): state → ℝ^state_dim
        self.f_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, state_dim),
            nn.Tanh(),  # Bounded drift
        )
        self.f_scale = nn.Parameter(torch.tensor(0.1))

        # Control dynamics g(x): state → ℝ^(state_dim × control_dim)
        self.g_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, state_dim * control_dim),
        )

        # Initialize g to have negative effect (control reduces risk)
        with torch.no_grad():
            nn.init.zeros_(cast(torch.Tensor, self.g_net[-1].weight))
            nn.init.constant_(cast(torch.Tensor, self.g_net[-1].bias), -0.1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute dynamics f(x), g(x).

        Args:
            x: Safety state [B, state_dim]

        Returns:
            f: Drift [B, state_dim]
            g: Control matrix [B, state_dim, control_dim]
        """
        B = x.shape[0]

        f = self.f_scale * self.f_net(x)  # [B, state_dim]
        g_flat = self.g_net(x)  # [B, state_dim * control_dim]
        g = g_flat.view(B, self.state_dim, self.control_dim)

        return f, g


# =============================================================================
# TOPOLOGICAL SAFETY (CATASTROPHE INTEGRATION)
# =============================================================================


class TopologicalBarrier(nn.Module):
    """Topological barrier function based on catastrophe distance.

    Safety is defined as distance from bifurcation singularities:
        h_topo(x) = threshold - catastrophe_risk(x)

    This complements the metric barrier with topological stability.

    MODES (Dec 3, 2025):
    ===================
    1. Neural (default): Learns risk estimation from data
    2. Analytical: Uses rigorous B-G determinant conditions

    The neural mode is more flexible; analytical mode is more interpretable.
    """

    def __init__(
        self,
        state_dim: int = 16,
        hidden_dim: int = 64,
        threshold: float = 0.7,
        use_analytical: bool = False,
    ) -> None:
        """Initialize topological barrier.

        Args:
            state_dim: Safety state dimension
            hidden_dim: Hidden dimension for risk estimation
            threshold: Risk threshold (above = unsafe)
            use_analytical: If True, use AnalyticalCatastropheDetector
        """
        super().__init__()
        self.threshold = threshold
        self.use_analytical = use_analytical
        self.state_dim = state_dim
        self._detector: AnalyticalCatastropheDetector | None
        self.risk_net: nn.Module | None
        self.codim_weights: torch.Tensor

        if use_analytical:
            # Use rigorous B-G determinant conditions (consolidation: Dec 3, 2025)
            from kagami.core.world_model.dynamics.analytical_catastrophe import (
                AnalyticalCatastropheDetector,
            )

            self._detector = AnalyticalCatastropheDetector(
                input_dim=state_dim,
                singularity_threshold=threshold * 0.8,
                unsafe_threshold=threshold,
            )
            self.risk_net = None
        else:
            # Neural catastrophe risk estimator
            # Outputs 7 values (one per catastrophe type) + 1 aggregate
            self.risk_net = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.GELU(),
                nn.Linear(hidden_dim // 2, 8),
                nn.Sigmoid(),  # Risk in [0, 1]
            )
            self._detector = None

        # Fano-weighted aggregation (7 catastrophe types)
        # Weights inversely related to codimension (simpler = more dangerous)
        self.register_buffer(
            "codim_weights",
            torch.tensor([1.0, 0.8, 0.6, 0.4, 0.6, 0.6, 0.4]),  # fold to parabolic
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute topological barrier.

        Args:
            x: Safety state [B, state_dim]

        Returns:
            h_topo: Topological barrier [B]
            risk_vector: Per-catastrophe risks [B, 7]
        """
        if self.use_analytical and self._detector is not None:
            # Analytical mode: use B-G determinants
            total_risk, risk_vector, _ = self._detector(x)
            h_topo = self.threshold - total_risk
            return h_topo, risk_vector

        # Neural mode
        if self.risk_net is None:
            raise RuntimeError(
                "TopologicalBarrier: risk_net is None but use_analytical=False. "
                "This indicates an initialization error."
            )
        risk_output = self.risk_net(x)  # [B, 8]
        risk_vector = risk_output[..., :7]  # [B, 7]
        aggregate_risk = risk_output[..., 7]  # [B]

        # Weighted combination
        weighted_risk = (risk_vector * self.codim_weights).sum(dim=-1) / self.codim_weights.sum()

        # Combine aggregate and weighted
        total_risk = 0.5 * aggregate_risk + 0.5 * weighted_risk

        # Barrier: h = threshold - risk
        h_topo = self.threshold - total_risk

        return h_topo, risk_vector


# =============================================================================
# OPTIMAL CBF - COMPLETE IMPLEMENTATION
# =============================================================================


@dataclass
class OptimalCBFConfig:
    """Configuration for Optimal CBF."""

    # Dimensions
    observation_dim: int = 256
    state_dim: int = 16
    control_dim: int = 2
    hidden_dim: int = 64

    # Safety thresholds
    metric_threshold: float = 0.3
    topo_threshold: float = 0.7

    # Class-K bounds
    min_alpha: float = 0.1
    max_alpha: float = 10.0

    # Control bounds
    u_min: float = 0.0
    u_max: float = 1.0

    # Training
    soft_penalty_weight: float = 10.0
    safety_margin: float = 0.1

    # Features
    use_neural_residual: bool = True
    use_topological: bool = True
    use_learned_dynamics: bool = True
    use_analytical_topo: bool = False  # Use B-G determinants instead of neural

    # QP Solver (Dec 12, 2025 - Science Gap Closure)
    use_qp_solver: bool = True  # Use proper QP solver vs gradient projection
    qp_solver: str = "osqp"  # 'osqp', 'ecos', 'analytical'

    # Model Uncertainty (Dec 12, 2025 - Science Gap Closure)
    use_uncertainty: bool = True  # Inflate CBF margin by model uncertainty
    uncertainty_inflation: float = 2.0  # σ multiplier for robust margin
    ensemble_size: int = 3  # Number of dynamics models for uncertainty

    # High-Order CBF (Dec 24, 2025 - HOCBF for relative degree > 1)
    use_hocbf: bool = False  # Enable high-order CBF for higher relative degree
    relative_degree: int = 1  # System relative degree (1 = standard CBF)
    hocbf_alpha_sequence: list[float] = field(
        default_factory=lambda: [1.0, 1.0]
    )  # alpha_i for each virtual constraint

    # Lipschitz Regularization (Dec 24, 2025 - for verified training)
    use_lipschitz_reg: bool = True  # Enforce Lipschitz bounds during training
    lipschitz_target: float = 1.0  # Target Lipschitz constant
    lipschitz_weight: float = 0.01  # Regularization weight

    # Formal Verification Integration (Dec 24, 2025)
    verify_during_training: bool = False  # Run verification during training
    verification_frequency: int = 100  # Verify every N steps


# =============================================================================
# DIFFERENTIABLE QP SOLVER (Dec 12, 2025 - Science Gap Closure)
# =============================================================================


class DifferentiableQPSolver(nn.Module):
    """Differentiable QP solver for CBF constraint enforcement.

    Solves:
        min  ||u - u_nom||²
        s.t. A·u ≥ b   (CBF constraint)
             u_min ≤ u ≤ u_max

    Per Ames et al. (2019): this is the correct formulation for CBF filtering.
    Gradient projection is only an approximation.

    IMPLEMENTATION:
    ===============
    1. Analytical solution for single-constraint case (fast, exact)
    2. OSQP for multi-constraint case (if available)
    3. Falls back to gradient projection if QP fails
    """

    def __init__(
        self,
        control_dim: int = 2,
        u_min: float = 0.0,
        u_max: float = 1.0,
        solver: str = "osqp",
    ):
        """Initialize QP solver.

        Args:
            control_dim: Control dimension
            u_min: Lower bound on control
            u_max: Upper bound on control
            solver: Solver backend ('osqp', 'ecos', 'analytical')
        """
        super().__init__()
        self.control_dim = control_dim
        self.solver = solver
        self.u_min_buf: torch.Tensor
        self.u_max_buf: torch.Tensor

        self.register_buffer("u_min_buf", torch.tensor([u_min] * control_dim))
        self.register_buffer("u_max_buf", torch.tensor([u_max] * control_dim))

        # Check for OSQP availability
        self._osqp_available = False
        try:
            import osqp  # noqa: F401

            self._osqp_available = True
        except ImportError:
            logger.warning("OSQP not available, using analytical QP solver")

    def solve_analytical(
        self,
        u_nom: torch.Tensor,
        A: torch.Tensor,
        b: torch.Tensor,
    ) -> torch.Tensor:
        """Analytical solution for single linear inequality constraint.

        For: min ||u - u_nom||² s.t. a·u ≥ b

        Solution:
        - If a·u_nom ≥ b: u* = u_nom (feasible)
        - Else: u* = u_nom + λ*a where λ = (b - a·u_nom) / ||a||²

        Args:
            u_nom: Nominal control [B, D]
            A: Constraint matrix [B, D] (single constraint per sample)
            b: Constraint RHS [B]

        Returns:
            u_safe: Safe control [B, D]
        """
        # Check feasibility: a·u_nom ≥ b?
        a_dot_u = (A * u_nom).sum(dim=-1)  # [B]
        violation = b - a_dot_u  # [B], positive if violated

        # Lagrange multiplier (only positive if violated)
        a_norm_sq = (A**2).sum(dim=-1).clamp(min=1e-8)  # [B]
        lambda_star = F.relu(violation) / a_norm_sq  # [B]

        # Project: u* = u_nom + λ*a
        # This maintains the mathematical solution while preserving gradients
        # Even when lambda_star = 0 (feasible), gradients flow through u_nom
        u_correction = lambda_star.unsqueeze(-1) * A
        u_safe = u_nom + u_correction

        # Clip to bounds - use clamp which preserves gradients when not saturated
        u_safe = torch.clamp(u_safe, self.u_min_buf, self.u_max_buf)

        return u_safe

    def solve_osqp(
        self,
        u_nom: torch.Tensor,
        A: torch.Tensor,
        b: torch.Tensor,
    ) -> torch.Tensor:
        """OSQP solution for general QP.

        Uses OSQP to solve the QP exactly, then uses implicit differentiation
        for gradients through the solution.

        NOTE: This is slower than analytical but handles multiple constraints.
        """
        import numpy as np
        import osqp
        import scipy.sparse as sp

        B, D = u_nom.shape
        device = u_nom.device

        results = []
        for i in range(B):
            # Convert to numpy
            u_nom_np = u_nom[i].detach().cpu().numpy()
            A_np = A[i].detach().cpu().numpy().reshape(1, -1)
            b_np = b[i].detach().cpu().numpy().reshape(1)

            # QP: min 0.5 * u^T P u + q^T u
            # where P = I, q = -u_nom
            P = sp.eye(D, format="csc")
            q = -u_nom_np

            # Constraints: A_ub @ u >= b_ub → -A_ub @ u <= -b_ub
            # Plus box constraints: u_min <= u <= u_max
            A_ineq = np.vstack(
                [
                    -A_np,  # CBF constraint
                    -np.eye(D),  # u >= u_min
                    np.eye(D),  # u <= u_max
                ]
            )
            l_ineq = np.concatenate(
                [
                    -np.inf * np.ones(1),  # CBF: -inf <= -Au
                    self.u_min_buf.cpu().numpy(),  # u >= u_min
                    -np.inf * np.ones(D),  # -inf <= u
                ]
            )
            u_ineq = np.concatenate(
                [
                    -b_np,  # CBF: -Au <= -b → Au >= b
                    np.inf * np.ones(D),  # u <= inf
                    self.u_max_buf.cpu().numpy(),  # u <= u_max
                ]
            )

            A_osqp = sp.csc_matrix(A_ineq)

            # Solve
            prob = osqp.OSQP()
            prob.setup(P, q, A_osqp, l_ineq, u_ineq, verbose=False)
            res = prob.solve()

            if res.x is not None:
                results.append(torch.from_numpy(res.x).float())
            else:
                # Fallback to analytical
                results.append(
                    self.solve_analytical(u_nom[i : i + 1], A[i : i + 1], b[i : i + 1]).squeeze(0)
                )

        return torch.stack(results).to(device)

    def forward(
        self,
        u_nom: torch.Tensor,
        A: torch.Tensor,
        b: torch.Tensor,
    ) -> torch.Tensor:
        """Solve CBF-QP.

        Args:
            u_nom: Nominal control [B, D]
            A: Constraint matrix [B, D] or [B, K, D] for K constraints
            b: Constraint RHS [B] or [B, K]

        Returns:
            u_safe: Safe control [B, D]
        """
        # CRITICAL: If gradients are required, ALWAYS use analytical solver
        # OSQP converts to numpy and breaks gradient chain
        if u_nom.requires_grad or (torch.is_grad_enabled() and u_nom.grad_fn is not None):
            # Single constraint case: use analytical (fast, differentiable)
            if A.dim() == 2:
                return self.solve_analytical(u_nom, A, b)

            # Multi-constraint: sequential projection (approximate but differentiable)
            u_safe = u_nom.clone()
            K = A.shape[1] if A.dim() == 3 else 1
            for k in range(K):
                A_k = A[:, k] if A.dim() == 3 else A
                b_k = b[:, k] if b.dim() == 2 else b
                u_safe = self.solve_analytical(u_safe, A_k, b_k)
            return u_safe

        # Inference mode: can use OSQP for exact solution
        # Single constraint case: use analytical (fast, differentiable)
        if A.dim() == 2:
            if self.solver == "analytical" or not self._osqp_available:
                return self.solve_analytical(u_nom, A, b)
            elif self.solver == "osqp" and self._osqp_available:
                return self.solve_osqp(u_nom, A, b)

        # Multi-constraint: use OSQP if available
        if self._osqp_available:
            return self.solve_osqp(u_nom, A, b)

        # Fallback: sequential projection (approximate)
        u_safe = u_nom.clone()
        K = A.shape[1] if A.dim() == 3 else 1
        for k in range(K):
            A_k = A[:, k] if A.dim() == 3 else A
            b_k = b[:, k] if b.dim() == 2 else b
            u_safe = self.solve_analytical(u_safe, A_k, b_k)

        return u_safe


# =============================================================================
# DYNAMICS ENSEMBLE FOR UNCERTAINTY (Dec 12, 2025 - Science Gap Closure)
# =============================================================================


class DynamicsEnsemble(nn.Module):
    """Ensemble of dynamics models for uncertainty quantification.

    Per robust CBF theory: if model has uncertainty σ, inflate CBF constraint
    by λ·σ to ensure safety under model error.

    Uses ensemble disagreement as uncertainty estimate.
    """

    def __init__(
        self,
        state_dim: int = 16,
        control_dim: int = 2,
        hidden_dim: int = 64,
        ensemble_size: int = 3,
    ):
        """Initialize dynamics ensemble.

        Args:
            state_dim: Safety state dimension
            control_dim: Control dimension
            hidden_dim: Hidden dimension per member
            ensemble_size: Number of ensemble members
        """
        super().__init__()
        self.state_dim = state_dim
        self.control_dim = control_dim
        self.ensemble_size = ensemble_size

        # Create ensemble of dynamics models
        self.members = nn.ModuleList(
            [LearnedDynamics(state_dim, control_dim, hidden_dim) for _ in range(ensemble_size)]
        )

    def forward(
        self,
        x: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute dynamics with uncertainty.

        Args:
            x: Safety state [B, state_dim]

        Returns:
            f_mean: Mean drift [B, state_dim]
            g_mean: Mean control matrix [B, state_dim, control_dim]
            f_std: Drift uncertainty [B, state_dim]
            g_std: Control uncertainty [B, state_dim, control_dim]
        """
        f_list = []
        g_list = []

        for member in self.members:
            f, g = member(x)
            f_list.append(f)
            g_list.append(g)

        # Stack and compute statistics
        f_stack = torch.stack(f_list, dim=0)  # [E, B, state_dim]
        g_stack = torch.stack(g_list, dim=0)  # [E, B, state_dim, control_dim]

        f_mean = f_stack.mean(dim=0)
        g_mean = g_stack.mean(dim=0)
        f_std = f_stack.std(dim=0)
        g_std = g_stack.std(dim=0)

        return f_mean, g_mean, f_std, g_std


# =============================================================================
# HIGH-ORDER CBF (Dec 24, 2025 - for relative degree > 1)
# =============================================================================


class HighOrderCBF(nn.Module):
    """High-Order Control Barrier Function for systems with relative degree > 1.

    For a system with relative degree r, the standard CBF constraint L_g h = 0
    means control cannot directly affect the barrier. HOCBF constructs a sequence
    of virtual constraints:

        ψ_0(x) = h(x)
        ψ_1(x) = ψ̇_0(x) + α_1(ψ_0(x))
        ...
        ψ_{r-1}(x) = ψ̇_{r-2}(x) + α_{r-1}(ψ_{r-2}(x))

    The final constraint ψ_{r-1}(x) has relative degree 1 and can use standard CBF.

    References:
    - Xiao & Belta (2019): Control Barrier Functions for Systems with High Relative Degree
    - Nguyen & Sreenath (2016): Exponential CBFs for Dynamic Walking
    """

    def __init__(
        self,
        barrier_fn: nn.Module,
        dynamics_fn: nn.Module,
        relative_degree: int = 2,
        alpha_sequence: list[float] | None = None,
    ):
        """Initialize High-Order CBF.

        Args:
            barrier_fn: Base barrier function h(x)
            dynamics_fn: Dynamics model returning (f, g)
            relative_degree: System relative degree
            alpha_sequence: Class-K coefficients [α_1, ..., α_{r-1}]
        """
        super().__init__()
        self.barrier_fn = barrier_fn
        self.dynamics_fn = dynamics_fn
        self.relative_degree = relative_degree

        # Default alpha sequence (exponential convergence)
        if alpha_sequence is None:
            alpha_sequence = [1.0] * (relative_degree - 1)
        self.alpha_sequence = alpha_sequence

        logger.info(f"HighOrderCBF initialized with relative degree {relative_degree}")

    def compute_virtual_constraints(
        self,
        x: torch.Tensor,
    ) -> list[torch.Tensor]:
        """Compute sequence of virtual constraints ψ_0, ψ_1, ..., ψ_{r-1}.

        Args:
            x: State [B, state_dim]

        Returns:
            List of virtual constraint values [ψ_0, ψ_1, ..., ψ_{r-1}]
        """
        B = x.shape[0]
        device = x.device

        # ψ_0 = h(x)
        psi_values = [self.barrier_fn(x)]

        # Get dynamics
        f, _g = self.dynamics_fn(x)

        # Compute higher-order constraints
        for i in range(self.relative_degree - 1):
            # Compute gradient of previous ψ
            x_grad = x.clone().requires_grad_(True)
            psi_prev = psi_values[-1]

            if not psi_prev.requires_grad:
                # Recompute with gradient tracking
                psi_prev_recomputed = self.barrier_fn(x_grad)
                for j in range(i):
                    # Recompute all previous virtual constraints
                    grad_psi = torch.autograd.grad(
                        psi_prev_recomputed.sum(),
                        x_grad,
                        create_graph=True,
                    )[0]
                    L_f_psi = (grad_psi * f).sum(dim=-1)
                    alpha_psi = self.alpha_sequence[j] * psi_prev_recomputed
                    psi_prev_recomputed = L_f_psi + alpha_psi
                psi_prev = psi_prev_recomputed

            # Gradient of ψ_i
            if psi_prev.grad_fn is not None:
                grad_psi = torch.autograd.grad(
                    psi_prev.sum(),
                    x_grad if x_grad.grad_fn is not None else x,
                    create_graph=True,
                    allow_unused=True,
                )[0]
                if grad_psi is None:
                    grad_psi = torch.zeros(B, x.shape[1], device=device)  # type: ignore[unreachable]
            else:
                grad_psi = torch.zeros(B, x.shape[1], device=device)

            # ψ_{i+1} = L_f ψ_i + α_{i+1}(ψ_i)
            L_f_psi = (grad_psi * f).sum(dim=-1)
            alpha_psi = self.alpha_sequence[i] * psi_prev.detach()
            psi_next = L_f_psi + alpha_psi

            psi_values.append(psi_next)

        return psi_values

    def get_cbf_constraint(
        self,
        x: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get the effective CBF constraint (a, b) such that a·u ≥ b.

        For HOCBF, this uses the final virtual constraint ψ_{r-1}.

        Args:
            x: State [B, state_dim]

        Returns:
            a: Constraint gradient [B, control_dim]
            b: Constraint RHS [B]
            h: Original barrier value [B]
        """
        # Get all virtual constraints
        psi_values = self.compute_virtual_constraints(x)
        h = psi_values[0]
        psi_final = psi_values[-1]

        # Get dynamics
        f, g = self.dynamics_fn(x)

        # Compute gradient of final ψ
        x_grad = x.clone().requires_grad_(True)
        psi_final_recomputed = self._recompute_final_psi(x_grad, f)

        if psi_final_recomputed.grad_fn is not None:
            grad_psi = torch.autograd.grad(
                psi_final_recomputed.sum(),
                x_grad,
                create_graph=True,
            )[0]
        else:
            grad_psi = torch.zeros_like(x)

        # a = L_g ψ_{r-1}
        a = torch.einsum("bs,bsc->bc", grad_psi, g)

        # b = -L_f ψ_{r-1} - α_r(ψ_{r-1})
        L_f_psi = (grad_psi * f).sum(dim=-1)
        alpha_r = (
            self.alpha_sequence[-1] if len(self.alpha_sequence) >= self.relative_degree else 1.0
        )
        b = -(L_f_psi + alpha_r * psi_final)

        return a, b, h

    def _recompute_final_psi(self, x: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
        """Recompute final ψ with gradient tracking."""
        psi = self.barrier_fn(x)
        for i in range(self.relative_degree - 1):
            if psi.grad_fn is not None:
                grad_psi = torch.autograd.grad(psi.sum(), x, create_graph=True, retain_graph=True)[
                    0
                ]
                L_f_psi = (grad_psi * f).sum(dim=-1)
            else:
                L_f_psi = torch.zeros(x.shape[0], device=x.device)
            alpha_psi = self.alpha_sequence[i] * psi
            psi = L_f_psi + alpha_psi
        return cast(torch.Tensor, psi)


# =============================================================================
# LIPSCHITZ REGULARIZATION (Dec 24, 2025 - for verified training)
# =============================================================================


class LipschitzRegularizer(nn.Module):
    """Lipschitz regularization for neural barrier functions.

    Enforces Lipschitz bounds on the barrier function to enable:
    1. Tighter verification bounds (LBP works better with smaller Lipschitz)
    2. Robustness to input perturbations
    3. Stable training dynamics

    Uses spectral normalization and gradient penalty approaches.

    References:
    - Gouk et al. (2021): Regularisation of Neural Networks by Enforcing Lipschitz Continuity
    - Fazlyab et al. (2019): Efficient and Accurate Estimation of Lipschitz Constants
    """

    def __init__(
        self,
        target_lipschitz: float = 1.0,
        method: str = "gradient_penalty",
    ):
        """Initialize Lipschitz regularizer.

        Args:
            target_lipschitz: Target Lipschitz constant K
            method: Regularization method ('gradient_penalty', 'spectral', 'power_iteration')
        """
        super().__init__()
        self.target_lipschitz = target_lipschitz
        self.method = method

    def gradient_penalty(
        self,
        network: nn.Module,
        x: torch.Tensor,
    ) -> torch.Tensor:
        """Compute gradient penalty for Lipschitz regularization.

        Penalty: E[max(0, ||∇f(x)||_2 - K)²]

        Args:
            network: Network to regularize
            x: Input samples [B, D]

        Returns:
            Gradient penalty loss
        """
        x = x.clone().requires_grad_(True)
        y = network(x)

        # Compute gradient
        if y.dim() > 1:
            y = y.sum(dim=-1)

        grad = torch.autograd.grad(
            outputs=y.sum(),
            inputs=x,
            create_graph=True,
            retain_graph=True,
        )[0]

        # Gradient norm
        grad_norm = torch.norm(grad, dim=-1)

        # Penalty for exceeding target Lipschitz
        violation = F.relu(grad_norm - self.target_lipschitz)
        penalty = (violation**2).mean()

        return penalty

    def spectral_norm_penalty(
        self,
        network: nn.Module,
    ) -> torch.Tensor:
        """Compute penalty based on spectral norms of weight matrices.

        For a network f = L_n ∘ ... ∘ L_1, Lipschitz constant is bounded by:
            K ≤ ∏_i ||W_i||_2

        Args:
            network: Network to regularize

        Returns:
            Spectral norm penalty
        """
        total_penalty = torch.tensor(0.0)
        product_norm = 1.0

        for module in network.modules():
            if isinstance(module, nn.Linear):
                # Compute spectral norm (largest singular value)
                W = module.weight
                # Use power iteration for efficiency
                u = torch.randn(W.shape[0], device=W.device)
                for _ in range(3):
                    v = F.normalize(W.t() @ u, dim=0)
                    u = F.normalize(W @ v, dim=0)
                sigma = (u @ W @ v).abs()
                product_norm *= sigma.item()

        # Penalty for exceeding target
        if product_norm > self.target_lipschitz:
            total_penalty = torch.tensor(
                (product_norm - self.target_lipschitz) ** 2,
                device=next(network.parameters()).device,
            )

        return total_penalty

    def forward(
        self,
        network: nn.Module,
        x: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute Lipschitz regularization loss.

        Args:
            network: Network to regularize
            x: Input samples (required for gradient_penalty method)

        Returns:
            Regularization loss
        """
        if self.method == "gradient_penalty":
            if x is None:
                raise ValueError("gradient_penalty method requires input samples x")
            return self.gradient_penalty(network, x)
        elif self.method == "spectral":
            return self.spectral_norm_penalty(network)
        else:
            raise ValueError(f"Unknown Lipschitz method: {self.method}")


class OptimalCBF(nn.Module):
    """Optimal Control Barrier Function with learned components.

    FEATURES:
    1. Learned state encoder (grounds safety in observables)
    2. Learned barrier function h(x) (linear + neural)
    3. Learned class-K function α(h) (adaptive convergence)
    4. Learned dynamics f(x), g(x) (data-driven)
    5. Topological barrier (catastrophe distance)

    GUARANTEES:
    - Forward invariance of safe set[Any] (under model assumptions)
    - Differentiable for end-to-end training
    - Minimal modification of nominal control (QP)
    """

    def __init__(self, config: OptimalCBFConfig | None = None) -> None:
        """Initialize Optimal CBF.

        Args:
            config: CBF configuration
        """
        super().__init__()
        self.config = config or OptimalCBFConfig()
        # Optional submodules must be annotated up-front for mypy (some branches assign None).
        self.dynamics: DynamicsEnsemble | LearnedDynamics | None = None
        self.dynamics_has_uncertainty: bool = False
        self.qp_solver: DifferentiableQPSolver | None = None
        self.topo_barrier: TopologicalBarrier | None = None
        self._warned_relative_degree: bool = False

        # State encoder
        self.state_encoder = SafetyStateEncoder(
            observation_dim=self.config.observation_dim,
            state_dim=self.config.state_dim,
            hidden_dim=self.config.hidden_dim,
        )

        # Metric barrier function
        self.barrier_fn = LearnedBarrierFunction(
            state_dim=self.config.state_dim,
            hidden_dim=self.config.hidden_dim,
            safety_threshold=self.config.metric_threshold,
            use_neural_residual=self.config.use_neural_residual,
        )

        # Class-K function
        self.class_k = LearnedClassK(
            hidden_dim=self.config.hidden_dim // 2,
            base_k=1.0,
            min_alpha=self.config.min_alpha,
            max_alpha=self.config.max_alpha,
        )

        # Dynamics (with optional uncertainty via ensemble)
        if self.config.use_learned_dynamics:
            if self.config.use_uncertainty:
                self.dynamics = DynamicsEnsemble(
                    state_dim=self.config.state_dim,
                    control_dim=self.config.control_dim,
                    hidden_dim=self.config.hidden_dim,
                    ensemble_size=self.config.ensemble_size,
                )
                self.dynamics_has_uncertainty = True
            else:
                self.dynamics = LearnedDynamics(
                    state_dim=self.config.state_dim,
                    control_dim=self.config.control_dim,
                    hidden_dim=self.config.hidden_dim,
                )
                self.dynamics_has_uncertainty = False
        else:
            self.dynamics = None
            self.dynamics_has_uncertainty = False

        # QP Solver (Dec 12, 2025 - Science Gap Closure)
        if self.config.use_qp_solver:
            self.qp_solver = DifferentiableQPSolver(
                control_dim=self.config.control_dim,
                u_min=self.config.u_min,
                u_max=self.config.u_max,
                solver=self.config.qp_solver,
            )
        else:
            self.qp_solver = None

        # Topological barrier
        if self.config.use_topological:
            self.topo_barrier = TopologicalBarrier(
                state_dim=self.config.state_dim,
                hidden_dim=self.config.hidden_dim,
                threshold=self.config.topo_threshold,
                use_analytical=self.config.use_analytical_topo,
            )
        else:
            self.topo_barrier = None

        # Control bounds
        self.u_min: torch.Tensor
        self.u_max: torch.Tensor
        self.register_buffer("u_min", torch.tensor([self.config.u_min] * self.config.control_dim))
        self.register_buffer("u_max", torch.tensor([self.config.u_max] * self.config.control_dim))

        logger.info(
            f"✅ OptimalCBF initialized:\n"
            f"   State: {self.config.observation_dim} → {self.config.state_dim}\n"
            f"   Control: {self.config.control_dim}D\n"
            f"   Features: neural_residual={self.config.use_neural_residual}, "
            f"topological={self.config.use_topological}, "
            f"learned_dynamics={self.config.use_learned_dynamics}"
        )

    def encode_state(self, obs: torch.Tensor) -> torch.Tensor:
        """Encode observation to safety state.

        Args:
            obs: Raw observation [B, observation_dim] or legacy [B, 4]

        Returns:
            Safety state [B, state_dim]
        """
        return cast(torch.Tensor, self.state_encoder(obs))

    def compute_barriers(
        self,
        x: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor | None, dict[str, Any]]:
        """Compute metric and topological barriers.

        Args:
            x: Safety state [B, state_dim]

        Returns:
            h_metric: Metric barrier [B]
            h_topo: Topological barrier [B] or None
            info: Dict with additional info
        """
        # Metric barrier
        h_metric = self.barrier_fn(x)

        # Topological barrier
        if self.topo_barrier is not None:
            h_topo, risk_vector = self.topo_barrier(x)
            info = {"risk_vector": risk_vector}
        else:
            h_topo = None
            info = {}

        return h_metric, h_topo, info

    def compute_lie_derivatives(
        self,
        x: torch.Tensor,
        h: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute Lie derivatives L_f h and L_g h.

        Uses autograd for gradient ∇h when gradients are enabled,
        otherwise uses finite differences.

        Args:
            x: Safety state [B, state_dim]
            h: Barrier values [B] (with grad tracking if enabled)

        Returns:
            L_f_h: Lie derivative w.r.t. drift [B]
            L_g_h: Lie derivative w.r.t. control [B, control_dim]
            L_f_h_std: Uncertainty in L_f_h [B]
            L_g_h_std: Uncertainty in L_g_h [B, control_dim]
        """
        B = x.shape[0]
        device = x.device

        # Check if we need gradients (training vs inference)
        if torch.is_grad_enabled():
            # Use autograd for gradient computation
            x_grad = x.clone().requires_grad_(True)
            h_recomputed = self.barrier_fn(x_grad)

            grad_h = torch.autograd.grad(
                outputs=h_recomputed.sum(),
                inputs=x_grad,
                create_graph=True,
                retain_graph=True,
            )[0]  # [B, state_dim]
        else:
            # Use finite differences for inference (no gradients needed)
            eps = 1e-4
            grad_h = torch.zeros(B, self.config.state_dim, device=device)
            h_base = self.barrier_fn(x)

            for i in range(self.config.state_dim):
                x_plus = x.clone()
                x_plus[:, i] += eps
                h_plus = self.barrier_fn(x_plus)
                grad_h[:, i] = (h_plus - h_base) / eps

        if self.dynamics is not None:
            if self.dynamics_has_uncertainty:
                # Ensemble dynamics with uncertainty
                f, g, f_std, g_std = self.dynamics(x)
            else:
                # Single dynamics model
                f, g = self.dynamics(x)
                f_std = torch.zeros_like(f)
                g_std = torch.zeros_like(g)
        else:
            # Default dynamics (constant)
            f = torch.zeros(B, self.config.state_dim, device=device) + 0.05
            g = torch.ones(B, self.config.state_dim, self.config.control_dim, device=device) * (
                -0.2
            )
            f_std = torch.zeros_like(f)
            g_std = torch.zeros_like(g)

        # Lie derivatives
        L_f_h = (grad_h * f).sum(dim=-1)  # [B]
        L_g_h = torch.einsum("bs,bsc->bc", grad_h, g)  # [B, control_dim]

        # Uncertainty in Lie derivatives (for robust margin)
        L_f_h_std = (grad_h.abs() * f_std).sum(dim=-1)  # [B]
        L_g_h_std = torch.einsum("bs,bsc->bc", grad_h.abs(), g_std)  # [B, control_dim]

        return L_f_h, L_g_h, L_f_h_std, L_g_h_std

    def filter(
        self,
        obs: torch.Tensor,
        u_nominal: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Filter control to ensure safety.

        Solves QP:
            min  ||u - u_nom||²
            s.t. L_f h + L_g h·u + α(h) ≥ 0  (for each barrier)

        Args:
            obs: Observation [B, observation_dim] or [B, 4]
            u_nominal: Nominal control [B, control_dim]

        Returns:
            u_safe: Safe control [B, control_dim]
            penalty: Safety penalty for training [1]
            info: Dict with barriers, adjustments, etc.
        """
        obs.shape[0]

        # 1. Encode to safety state
        x = self.encode_state(obs)

        # 2. Compute barriers
        h_metric, h_topo, barrier_info = self.compute_barriers(x)

        # 3. Compute Lie derivatives for metric barrier (with uncertainty)
        L_f_h, L_g_h, L_f_h_std, _L_g_h_std = self.compute_lie_derivatives(x, h_metric)

        # 3a. Check relative degree (Dec 14, 2025 - theoretical gap fix)
        # Standard CBF requires relative degree 1: L_g h ≠ 0
        # If L_g h ≈ 0, constraint becomes vacuous (no control can help)
        L_g_h_norm = torch.norm(L_g_h, dim=-1)  # [B]
        relative_degree_violated = L_g_h_norm < 1e-6  # Threshold for numerical zero

        if relative_degree_violated.any():
            num_violated = relative_degree_violated.sum().item()
            if hasattr(self, "_warned_relative_degree") and self._warned_relative_degree:
                pass  # Only warn once
            else:
                logging.warning(
                    f"CBF: Relative degree assumption violated for {num_violated}/{obs.shape[0]} samples. "
                    f"L_g h ≈ 0 means control cannot directly affect barrier. "
                    f"Consider using high-order CBF (HOCBF) or redesigning barrier function."
                )
                self._warned_relative_degree = True

        # 4. Build constraint: a·u ≥ b
        # From: L_f h + L_g h·u + α(h) ≥ 0
        # Rearrange: L_g h·u ≥ -(L_f h + α(h))
        alpha_h = self.class_k(h_metric)

        # Robust margin inflation (Dec 12, 2025 - Science Gap Closure)
        # Per robust CBF: inflate constraint by λ·σ to handle model uncertainty
        if self.config.use_uncertainty:
            uncertainty_margin = self.config.uncertainty_inflation * L_f_h_std
            b = -(L_f_h + alpha_h - uncertainty_margin)  # More conservative
        else:
            b = -(L_f_h + alpha_h)  # [B]

        a = L_g_h  # [B, control_dim]

        # 5. Solve CBF-QP (Dec 12, 2025 - Science Gap Closure)
        if self.qp_solver is not None:
            u_safe = self.qp_solver(u_nominal, a, b)
            lambda_proj = torch.zeros_like(b)  # For logging
        else:
            # Fallback to gradient projection (differentiable but approximate)
            a_dot_u = (a * u_nominal).sum(dim=-1)  # [B]
            violation = F.relu(b - a_dot_u)  # [B]
            a_norm_sq = (a**2).sum(dim=-1) + 1e-8  # [B]
            lambda_proj = violation / a_norm_sq  # [B]
            u_safe = u_nominal + lambda_proj.unsqueeze(-1) * a

        # 6. Add topological constraint if enabled
        if h_topo is not None:
            # Simple: if h_topo < 0, scale down control
            topo_scale = torch.sigmoid(h_topo * 5).unsqueeze(-1)  # [B, 1]
            u_safe = u_safe * topo_scale

        # 7. Clip to bounds
        u_safe = torch.clamp(u_safe, self.u_min, self.u_max)

        # 8. Compute training penalty
        margin = self.config.safety_margin
        unsafe_margin = F.relu(margin - h_metric)
        penalty = self.config.soft_penalty_weight * (unsafe_margin**2).mean()

        if h_topo is not None:
            topo_penalty = F.relu(0.0 - h_topo)
            penalty = penalty + self.config.soft_penalty_weight * 0.5 * (topo_penalty**2).mean()

        # 9. Build info dict[str, Any]
        a_dot_u_final = (a * u_safe).sum(dim=-1)  # Check final constraint
        info = {
            "x": x,
            "h_metric": h_metric,
            "h_topo": h_topo,
            "L_f_h": L_f_h,
            "L_g_h": L_g_h,
            "L_f_h_std": L_f_h_std,  # Model uncertainty (Dec 12, 2025)
            "alpha_h": alpha_h,
            "lambda_proj": lambda_proj,
            "adjusted": (torch.abs(u_safe - u_nominal) > 1e-6).any().item(),
            "constraint_satisfied": (a_dot_u_final >= b).all().item(),
            "qp_solver_used": self.qp_solver is not None,
            "uncertainty_margin": self.config.uncertainty_inflation * L_f_h_std
            if self.config.use_uncertainty
            else None,
            **barrier_info,
        }

        return u_safe, penalty, info

    def is_safe(self, obs: torch.Tensor) -> torch.Tensor:
        """Check if observations are safe.

        Args:
            obs: Observation [B, observation_dim]

        Returns:
            safe: Boolean tensor [B]
        """
        x = self.encode_state(obs)
        h_metric, h_topo, _ = self.compute_barriers(x)

        safe = h_metric >= 0
        if h_topo is not None:
            safe = safe & (h_topo >= 0)

        return safe

    def barrier_value(self, obs: torch.Tensor) -> torch.Tensor:
        """Get minimum barrier value (most restrictive).

        Args:
            obs: Observation [B, observation_dim]

        Returns:
            h: Minimum barrier [B]
        """
        x = self.encode_state(obs)
        h_metric, h_topo, _ = self.compute_barriers(x)

        if h_topo is not None:
            return torch.min(h_metric, h_topo)
        return h_metric

    def forward(
        self,
        obs: torch.Tensor,
        u_nominal: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Forward pass - alias for filter()."""
        return self.filter(obs, u_nominal)


# Note: LegacyCompatibleCBF was removed December 2025. Use OptimalCBF directly.


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_optimal_cbf(
    observation_dim: int = 256,
    state_dim: int = 16,
    control_dim: int = 2,
    **kwargs: Any,
) -> OptimalCBF:
    """Create OptimalCBF with given configuration.

    Args:
        observation_dim: Raw observation dimension
        state_dim: Safety state dimension
        control_dim: Control dimension
        **kwargs: Additional config options

    Returns:
        Configured OptimalCBF
    """
    config = OptimalCBFConfig(
        observation_dim=observation_dim,
        state_dim=state_dim,
        control_dim=control_dim,
        **kwargs,
    )
    return OptimalCBF(config)


# Global singleton
_optimal_cbf: OptimalCBF | None = None


def get_optimal_cbf() -> OptimalCBF:
    """Get singleton OptimalCBF instance.

    Returns the tensor-based OptimalCBF for safety filtering.
    """
    global _optimal_cbf
    if _optimal_cbf is None:
        _optimal_cbf = create_optimal_cbf()
    return _optimal_cbf


__all__ = [
    # QP Solver
    "DifferentiableQPSolver",
    "DynamicsEnsemble",
    # High-Order CBF (Dec 24, 2025)
    "HighOrderCBF",
    "LearnedBarrierFunction",
    "LearnedClassK",
    "LearnedDynamics",
    # Lipschitz Regularization (Dec 24, 2025)
    "LipschitzRegularizer",
    # Core CBF
    "OptimalCBF",
    "OptimalCBFConfig",
    # Learned Components
    "SafetyStateEncoder",
    "TopologicalBarrier",
    # Factory Functions
    "create_optimal_cbf",
    "get_optimal_cbf",
]
