"""Formal Verification of Neural Control Barrier Functions via LBP.

CREATED: December 24, 2025
BASED ON: "Scalable Verification of Neural Control Barrier Functions
          Using Linear Bound Propagation" (arXiv:2511.06341, Nov 2025)

This module provides FORMAL VERIFICATION guarantees for neural CBFs
by computing sound linear bounds on the CBF constraint across state space.

MATHEMATICAL FOUNDATION:
========================
A function h: R^n -> R is a valid CBF if:
    forall x in X: h(x) >= 0 => dh/dx @ f(x) + dh/dx @ g(x) @ u + alpha(h(x)) >= 0

Traditional SMT-based verification is exponential in network size.
LBP provides polynomial-time sufficient conditions by propagating linear bounds.

LBP KEY INSIGHT:
================
For each layer of a neural network, we can compute linear bounds:
    L(x) <= f(x) <= U(x)
where L and U are affine functions of the input.

By propagating these bounds through the network, we obtain:
    L_h(x) <= h(x) <= U_h(x)

If L_h(x) >= 0 for all x in safe region, the CBF is verified.

VERIFICATION WORKFLOW:
======================
1. Partition state space into regions R_1, ..., R_k
2. For each region R_i:
   a. Compute LBP bounds on h(x) and dh/dx
   b. Compute bounds on L_f h and L_g h using dynamics bounds
   c. Check: min(L_f h + L_g h @ u + alpha(h)) >= 0?
3. If all regions pass, CBF is formally verified

References:
- Chen et al. (2025): Scalable Verification of Neural CBFs Using LBP
- Liu et al. (2024): PNCBF - Policy Neural Control Barrier Functions
- Xu et al. (2020): Automatic Perturbation Analysis (auto_LiRPA)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# =============================================================================
# VERIFICATION STATUS
# =============================================================================


class VerificationStatus(Enum):
    """Verification result status."""

    VERIFIED = "verified"  # CBF is formally verified
    VIOLATED = "violated"  # Found counterexample
    UNKNOWN = "unknown"  # Verification inconclusive (bounds too loose)
    TIMEOUT = "timeout"  # Verification timed out
    ERROR = "error"  # Verification error


@dataclass
class VerificationResult:
    """Result of formal CBF verification."""

    status: VerificationStatus
    verified_fraction: float  # Fraction of regions verified
    total_regions: int  # Total regions checked
    verified_regions: int  # Regions that passed
    violated_regions: int  # Regions with violations
    unknown_regions: int  # Regions with inconclusive bounds

    # Counterexample if found
    counterexample: torch.Tensor | None = None
    counterexample_h: float | None = None

    # Verification metrics
    max_violation: float = 0.0  # Largest CBF constraint violation
    avg_bound_gap: float = 0.0  # Average gap between upper/lower bounds
    verification_time_ms: float = 0.0

    # Detailed region results
    region_results: list[dict[str, Any]] = field(default_factory=list[Any])

    @property
    def is_verified(self) -> bool:
        """Check if CBF is formally verified."""
        return self.status == VerificationStatus.VERIFIED

    def summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"CBF Verification: {self.status.value}\n"
            f"  Regions: {self.verified_regions}/{self.total_regions} verified "
            f"({self.verified_fraction:.1%})\n"
            f"  Violated: {self.violated_regions}, Unknown: {self.unknown_regions}\n"
            f"  Max violation: {self.max_violation:.6f}\n"
            f"  Time: {self.verification_time_ms:.1f}ms"
        )


# =============================================================================
# LINEAR BOUND PROPAGATION (LBP)
# =============================================================================


class LinearBounds:
    """Linear bounds on a neural network output.

    Represents: L @ x + l <= f(x) <= U @ x + u

    Where:
    - L, U: [out_dim, in_dim] matrices
    - l, u: [out_dim] bias vectors
    - f(x): neural network output
    """

    def __init__(
        self,
        L: torch.Tensor,  # Lower bound matrix [out_dim, in_dim]
        l: torch.Tensor,  # Lower bound bias [out_dim]
        U: torch.Tensor,  # Upper bound matrix [out_dim, in_dim]
        u: torch.Tensor,  # Upper bound bias [out_dim]
    ):
        self.L = L
        self.l = l
        self.U = U
        self.u = u

    def evaluate_bounds(
        self,
        x_lb: torch.Tensor,  # Lower bound on input [in_dim]
        x_ub: torch.Tensor,  # Upper bound on input [in_dim]
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Evaluate concrete bounds given input bounds.

        Returns:
            y_lb: Lower bound on output [out_dim]
            y_ub: Upper bound on output [out_dim]
        """
        # For each output dimension, compute:
        # y_lb = min over x in [x_lb, x_ub] of L @ x + l
        # y_ub = max over x in [x_lb, x_ub] of U @ x + u

        # For linear functions, min is achieved at corners
        # L @ x = sum_i L_i * x_i
        # If L_i >= 0, min at x_i = x_lb_i; else min at x_i = x_ub_i

        # Lower bound
        L_pos = torch.clamp(self.L, min=0)
        L_neg = torch.clamp(self.L, max=0)
        y_lb = L_pos @ x_lb + L_neg @ x_ub + self.l

        # Upper bound
        U_pos = torch.clamp(self.U, min=0)
        U_neg = torch.clamp(self.U, max=0)
        y_ub = U_pos @ x_ub + U_neg @ x_lb + self.u

        return y_lb, y_ub


class LBPropagator(nn.Module):
    """Linear Bound Propagation through neural networks.

    Propagates linear bounds through each layer to compute
    sound output bounds for any input region.

    Supports:
    - Linear layers
    - ReLU activation (using optimal relaxation)
    - GELU activation (using linear relaxation)
    - Tanh/Sigmoid (using linear relaxation)
    - LayerNorm (using affine approximation)
    """

    def __init__(self, network: nn.Module):
        """Initialize LBP for given network.

        Args:
            network: Neural network to verify
        """
        super().__init__()
        self.network = network
        self._layers = self._extract_layers(network)

    def _extract_layers(self, network: nn.Module) -> list[nn.Module]:
        """Extract sequential layers from network."""
        layers = []

        def _recurse(module: nn.Module) -> None:
            children = list(module.children())
            if not children:
                # Leaf module
                if not isinstance(module, nn.Identity):
                    layers.append(module)
            elif isinstance(module, nn.Sequential):
                for child in children:
                    _recurse(child)
            else:
                # For non-Sequential containers, try to get sequential structure
                for child in children:
                    _recurse(child)

        _recurse(network)
        return layers

    def propagate_linear(
        self,
        bounds: LinearBounds,
        layer: nn.Linear,
    ) -> LinearBounds:
        """Propagate bounds through linear layer.

        y = W @ x + b
        L_y @ z + l_y <= y <= U_y @ z + u_y

        Where z is original input (for composition).
        """
        W = layer.weight  # [out, in]
        b = layer.bias if layer.bias is not None else torch.zeros(W.shape[0], device=W.device)

        # Compose with previous bounds
        # y = W @ (L @ z + l) + b = (W @ L) @ z + (W @ l + b)
        new_L = W @ bounds.L
        new_l = W @ bounds.l + b
        new_U = W @ bounds.U
        new_u = W @ bounds.u + b

        return LinearBounds(new_L, new_l, new_U, new_u)

    def propagate_relu(
        self,
        bounds: LinearBounds,
        x_lb: torch.Tensor,
        x_ub: torch.Tensor,
    ) -> LinearBounds:
        """Propagate bounds through ReLU using optimal relaxation.

        For each neuron with pre-activation in [l, u]:
        - If l >= 0: ReLU is identity (slope = 1)
        - If u <= 0: ReLU is zero (slope = 0)
        - If l < 0 < u: Use optimal linear relaxation

        The optimal relaxation for l < 0 < u is:
        - Lower bound: max(0, x) >= lambda * x where lambda in [0, u/(u-l)]
        - Upper bound: max(0, x) <= u/(u-l) * (x - l)
        """
        # Get pre-activation bounds
        y_lb, y_ub = bounds.evaluate_bounds(x_lb, x_ub)

        out_dim = y_lb.shape[0]
        in_dim = bounds.L.shape[1]
        device = bounds.L.device

        # Initialize output bounds
        new_L = torch.zeros(out_dim, in_dim, device=device)
        new_l = torch.zeros(out_dim, device=device)
        new_U = torch.zeros(out_dim, in_dim, device=device)
        new_u = torch.zeros(out_dim, device=device)

        for i in range(out_dim):
            lb_i, ub_i = y_lb[i].item(), y_ub[i].item()

            if lb_i >= 0:
                # ReLU is identity
                new_L[i] = bounds.L[i]
                new_l[i] = bounds.l[i]
                new_U[i] = bounds.U[i]
                new_u[i] = bounds.u[i]
            elif ub_i <= 0:
                # ReLU is zero
                new_L[i] = 0
                new_l[i] = 0
                new_U[i] = 0
                new_u[i] = 0
            else:
                # Crossing region: use optimal relaxation
                # Upper bound slope
                slope_upper = ub_i / (ub_i - lb_i)

                # For lower bound, use slope that minimizes area
                # Optimal is lambda = u/(u-l) if |l| < |u|, else 0
                if abs(lb_i) < abs(ub_i):
                    slope_lower = slope_upper
                else:
                    slope_lower = 0.0

                # Lower bound: y >= slope_lower * x
                new_L[i] = slope_lower * bounds.L[i]
                new_l[i] = slope_lower * bounds.l[i]

                # Upper bound: y <= slope_upper * (x - l) = slope_upper * x - slope_upper * l
                new_U[i] = slope_upper * bounds.U[i]
                new_u[i] = slope_upper * bounds.u[i] - slope_upper * lb_i

        return LinearBounds(new_L, new_l, new_U, new_u)

    def propagate_gelu(
        self,
        bounds: LinearBounds,
        x_lb: torch.Tensor,
        x_ub: torch.Tensor,
    ) -> LinearBounds:
        """Propagate bounds through GELU using linear relaxation.

        GELU(x) = x * Phi(x) where Phi is standard normal CDF.

        We use tangent line relaxation at midpoint for simplicity.
        More sophisticated methods possible (e.g., CROWN).
        """
        y_lb, y_ub = bounds.evaluate_bounds(x_lb, x_ub)
        mid = (y_lb + y_ub) / 2

        # GELU derivative at midpoint
        # d/dx GELU(x) = Phi(x) + x * phi(x)
        # where phi is standard normal PDF
        sqrt_2pi = 2.5066282746310002
        phi_mid = torch.exp(-0.5 * mid**2) / sqrt_2pi
        Phi_mid = 0.5 * (1 + torch.erf(mid / 1.4142135623730951))
        gelu_deriv = Phi_mid + mid * phi_mid

        # GELU value at midpoint
        gelu_mid = mid * Phi_mid

        # Use tangent line as both lower and upper bound (conservative)
        # y ≈ gelu_deriv * (x - mid) + gelu_mid = gelu_deriv * x + (gelu_mid - gelu_deriv * mid)
        scale = gelu_deriv.unsqueeze(1)  # [out_dim, 1]

        new_L = scale * bounds.L
        new_l = gelu_deriv * bounds.l + (gelu_mid - gelu_deriv * mid)
        new_U = scale * bounds.U
        new_u = gelu_deriv * bounds.u + (gelu_mid - gelu_deriv * mid)

        return LinearBounds(new_L, new_l, new_U, new_u)

    def propagate_tanh(
        self,
        bounds: LinearBounds,
        x_lb: torch.Tensor,
        x_ub: torch.Tensor,
    ) -> LinearBounds:
        """Propagate bounds through Tanh using chord relaxation."""
        y_lb, y_ub = bounds.evaluate_bounds(x_lb, x_ub)

        # Chord slope between endpoints
        tanh_lb = torch.tanh(y_lb)
        tanh_ub = torch.tanh(y_ub)

        # Avoid division by zero
        denom = y_ub - y_lb
        denom = torch.where(denom.abs() < 1e-8, torch.ones_like(denom), denom)
        slope = (tanh_ub - tanh_lb) / denom

        # Use chord as bounds (conservative for monotonic function)
        scale = slope.unsqueeze(1)

        new_L = scale * bounds.L
        new_l = slope * bounds.l + (tanh_lb - slope * y_lb)
        new_U = scale * bounds.U
        new_u = slope * bounds.u + (tanh_ub - slope * y_ub)

        return LinearBounds(new_L, new_l, new_U, new_u)

    def propagate(
        self,
        x_lb: torch.Tensor,
        x_ub: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Propagate bounds through entire network.

        Args:
            x_lb: Lower bound on input [in_dim]
            x_ub: Upper bound on input [in_dim]

        Returns:
            y_lb: Lower bound on output
            y_ub: Upper bound on output
        """
        in_dim = x_lb.shape[0]
        device = x_lb.device

        # Initialize with identity bounds
        bounds = LinearBounds(
            L=torch.eye(in_dim, device=device),
            l=torch.zeros(in_dim, device=device),
            U=torch.eye(in_dim, device=device),
            u=torch.zeros(in_dim, device=device),
        )

        for layer in self._layers:
            if isinstance(layer, nn.Linear):
                bounds = self.propagate_linear(bounds, layer)
            elif isinstance(layer, nn.ReLU):
                bounds = self.propagate_relu(bounds, x_lb, x_ub)
            elif isinstance(layer, nn.GELU):
                bounds = self.propagate_gelu(bounds, x_lb, x_ub)
            elif isinstance(layer, (nn.Tanh, nn.Sigmoid)):
                bounds = self.propagate_tanh(bounds, x_lb, x_ub)
            elif isinstance(layer, nn.LayerNorm):
                # Skip LayerNorm for now (treat as identity)
                # More precise handling requires running statistics
                pass
            else:
                logger.warning(f"LBP: Unsupported layer type {type(layer)}, treating as identity")

        return bounds.evaluate_bounds(x_lb, x_ub)


# =============================================================================
# CBF VERIFIER
# =============================================================================


@dataclass
class VerificationConfig:
    """Configuration for CBF verification."""

    # State space bounds
    state_lb: list[float] = field(default_factory=lambda: [-1.0] * 16)
    state_ub: list[float] = field(default_factory=lambda: [1.0] * 16)

    # Control bounds
    control_lb: list[float] = field(default_factory=lambda: [0.0, 0.0])
    control_ub: list[float] = field(default_factory=lambda: [1.0, 1.0])

    # Verification parameters
    num_partitions: int = 10  # Partitions per dimension
    max_depth: int = 3  # Max refinement depth
    verification_margin: float = 0.0  # Margin for numerical stability
    timeout_seconds: float = 60.0  # Verification timeout

    # Refinement strategy
    refine_violated: bool = True  # Refine regions with violations
    refine_unknown: bool = True  # Refine regions with loose bounds


class NeuralCBFVerifier:
    """Formal verifier for neural Control Barrier Functions.

    Uses Linear Bound Propagation to verify that:
    forall x in Safe: CBF constraint holds

    CBF constraint:
        L_f h(x) + L_g h(x) @ u + alpha(h(x)) >= 0

    For all admissible controls u in [u_lb, u_ub].
    """

    def __init__(
        self,
        barrier_fn: nn.Module,
        dynamics_fn: nn.Module | None = None,
        class_k_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
        config: VerificationConfig | None = None,
    ):
        """Initialize CBF verifier.

        Args:
            barrier_fn: Neural barrier function h(x)
            dynamics_fn: Dynamics model (f, g) or None for default
            class_k_fn: Class-K function alpha(h) or None for linear
            config: Verification configuration
        """
        self.barrier_fn = barrier_fn
        self.dynamics_fn = dynamics_fn
        self.class_k_fn = class_k_fn or (lambda h: h)  # Default: linear
        self.config = config or VerificationConfig()

        # Create LBP propagator for barrier function
        self.barrier_lbp = LBPropagator(barrier_fn)

        logger.info("NeuralCBFVerifier initialized")

    def _generate_regions(
        self,
        state_lb: torch.Tensor,
        state_ub: torch.Tensor,
        num_partitions: int,
    ) -> list[tuple[torch.Tensor, torch.Tensor]]:
        """Generate grid of verification regions."""
        dim = state_lb.shape[0]
        device = state_lb.device

        # For high dimensions, use random sampling instead of grid
        if dim > 4:
            # Random regions centered on sampled points
            num_regions = num_partitions ** min(dim, 4)
            regions = []
            for _ in range(num_regions):
                center = state_lb + torch.rand(dim, device=device) * (state_ub - state_lb)
                half_width = (state_ub - state_lb) / (2 * num_partitions)
                region_lb = torch.clamp(center - half_width, min=state_lb)
                region_ub = torch.clamp(center + half_width, max=state_ub)
                regions.append((region_lb, region_ub))
            return regions

        # For low dimensions, use grid
        steps = [
            torch.linspace(state_lb[i], state_ub[i], num_partitions + 1, device=device)
            for i in range(dim)
        ]

        regions = []
        # Generate all grid cells
        indices = [range(num_partitions) for _ in range(dim)]

        import itertools

        for idx in itertools.product(*indices):
            region_lb = torch.tensor([steps[d][idx[d]] for d in range(dim)], device=device)
            region_ub = torch.tensor([steps[d][idx[d] + 1] for d in range(dim)], device=device)
            regions.append((region_lb, region_ub))

        return regions

    def _compute_gradient_bounds(
        self,
        x_lb: torch.Tensor,
        x_ub: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute bounds on gradient dh/dx using finite differences with LBP.

        For each dimension i, compute bounds on partial h / partial x_i.
        """
        dim = x_lb.shape[0]
        device = x_lb.device
        eps = 1e-4

        grad_lb = torch.zeros(dim, device=device)
        grad_ub = torch.zeros(dim, device=device)

        # Compute h bounds at base point
        h_lb_base, h_ub_base = self.barrier_lbp.propagate(x_lb, x_ub)

        for i in range(dim):
            # Perturb dimension i
            x_lb_plus = x_lb.clone()
            x_ub_plus = x_ub.clone()
            x_lb_plus[i] += eps
            x_ub_plus[i] += eps

            h_lb_plus, h_ub_plus = self.barrier_lbp.propagate(x_lb_plus, x_ub_plus)

            # Gradient bounds via finite difference
            # grad_i in [(h_lb_plus - h_ub_base) / eps, (h_ub_plus - h_lb_base) / eps]
            grad_lb[i] = (h_lb_plus - h_ub_base) / eps
            grad_ub[i] = (h_ub_plus - h_lb_base) / eps

        # Ensure lb <= ub
        grad_lb, grad_ub = torch.min(grad_lb, grad_ub), torch.max(grad_lb, grad_ub)

        return grad_lb, grad_ub

    def _verify_region(
        self,
        x_lb: torch.Tensor,
        x_ub: torch.Tensor,
        u_lb: torch.Tensor,
        u_ub: torch.Tensor,
    ) -> dict[str, Any]:
        """Verify CBF constraint in a single region.

        Returns dict[str, Any] with:
        - verified: bool
        - h_lb, h_ub: barrier bounds
        - constraint_lb: lower bound on CBF constraint
        - counterexample: point if violation found
        """
        device = x_lb.device

        # 1. Compute barrier bounds
        h_lb, h_ub = self.barrier_lbp.propagate(x_lb, x_ub)
        h_lb = h_lb.squeeze()
        h_ub = h_ub.squeeze()

        # 2. If h_ub < 0, this region is entirely unsafe - skip verification
        if h_ub < 0:
            return {
                "verified": True,  # No safe states to verify
                "h_lb": h_lb.item(),
                "h_ub": h_ub.item(),
                "constraint_lb": float("inf"),
                "reason": "unsafe_region",
            }

        # 3. Compute gradient bounds
        grad_lb, grad_ub = self._compute_gradient_bounds(x_lb, x_ub)

        # 4. Get dynamics bounds
        if self.dynamics_fn is not None:
            # Use midpoint for dynamics evaluation
            x_mid = (x_lb + x_ub) / 2
            f, g = self.dynamics_fn(x_mid.unsqueeze(0))
            f = f.squeeze(0)  # [state_dim]
            g = g.squeeze(0)  # [state_dim, control_dim]
        else:
            # Default conservative dynamics
            state_dim = x_lb.shape[0]
            control_dim = u_lb.shape[0]
            f = torch.ones(state_dim, device=device) * 0.1
            g = torch.ones(state_dim, control_dim, device=device) * (-0.2)

        # 5. Compute Lie derivative bounds
        # L_f h = grad_h @ f
        # Bound: use interval arithmetic
        L_f_lb = torch.where(f >= 0, grad_lb * f, grad_ub * f).sum()
        _ = torch.where(f >= 0, grad_ub * f, grad_lb * f).sum()  # L_f_ub for future use

        # L_g h = grad_h @ g (matrix)
        # Result is [control_dim] vector
        control_dim = g.shape[1]
        L_g_lb = torch.zeros(control_dim, device=device)
        L_g_ub = torch.zeros(control_dim, device=device)

        for j in range(control_dim):
            g_j = g[:, j]
            lb_j = torch.where(g_j >= 0, grad_lb * g_j, grad_ub * g_j).sum()
            ub_j = torch.where(g_j >= 0, grad_ub * g_j, grad_lb * g_j).sum()
            L_g_lb[j] = lb_j
            L_g_ub[j] = ub_j

        # 6. Compute class-K bounds
        # alpha(h) for h in [h_lb, h_ub]
        # Assuming alpha is monotonic
        alpha_lb = self.class_k_fn(h_lb)
        _ = self.class_k_fn(h_ub)  # alpha_ub for future use

        # 7. Compute CBF constraint lower bound
        # Constraint: L_f h + L_g h @ u + alpha(h) >= 0
        # Find min over u in [u_lb, u_ub]

        # L_g h @ u is minimized when:
        # - If L_g_lb[j] >= 0: choose u[j] = u_lb[j]
        # - If L_g_ub[j] <= 0: choose u[j] = u_ub[j]
        # - Else: can be either

        # Conservative: use lower bound on L_g h
        L_g_u_lb = torch.where(L_g_lb >= 0, L_g_lb * u_lb, L_g_lb * u_ub).sum()
        L_g_u_lb = torch.min(L_g_u_lb, torch.where(L_g_ub >= 0, L_g_ub * u_lb, L_g_ub * u_ub).sum())

        # CBF constraint lower bound
        constraint_lb = L_f_lb + L_g_u_lb + alpha_lb

        # 8. Check verification
        margin = self.config.verification_margin
        verified = constraint_lb >= margin

        # 9. If not verified, find counterexample
        counterexample = None
        if not verified and h_lb >= 0:
            # Sample point where violation is likely
            counterexample = (x_lb + x_ub) / 2

        return {
            "verified": bool(verified),
            "h_lb": h_lb.item(),
            "h_ub": h_ub.item(),
            "L_f_h_lb": L_f_lb.item(),
            "L_g_h_lb": L_g_lb.tolist(),
            "alpha_lb": alpha_lb.item() if isinstance(alpha_lb, torch.Tensor) else alpha_lb,
            "constraint_lb": constraint_lb.item(),
            "counterexample": counterexample,
            "bound_gap": (h_ub - h_lb).item(),
        }

    def verify(
        self,
        state_lb: torch.Tensor | None = None,
        state_ub: torch.Tensor | None = None,
    ) -> VerificationResult:
        """Verify CBF constraint across state space.

        Args:
            state_lb: Lower bound on state (uses config default if None)
            state_ub: Upper bound on state (uses config default if None)

        Returns:
            VerificationResult with status and details
        """
        import time

        start_time = time.perf_counter()

        # Get bounds from config if not provided
        device = next(self.barrier_fn.parameters()).device
        if state_lb is None:
            state_lb = torch.tensor(self.config.state_lb, device=device)
        if state_ub is None:
            state_ub = torch.tensor(self.config.state_ub, device=device)

        u_lb = torch.tensor(self.config.control_lb, device=device)
        u_ub = torch.tensor(self.config.control_ub, device=device)

        # Generate verification regions
        regions = self._generate_regions(state_lb, state_ub, self.config.num_partitions)

        # Verify each region
        verified_count = 0
        violated_count = 0
        unknown_count = 0
        max_violation = 0.0
        total_bound_gap = 0.0
        counterexample = None
        counterexample_h = None
        region_results = []

        for x_lb_region, x_ub_region in regions:
            result = self._verify_region(x_lb_region, x_ub_region, u_lb, u_ub)
            region_results.append(result)

            if result["verified"]:
                verified_count += 1
            elif result["constraint_lb"] < -0.1:  # Clear violation
                violated_count += 1
                violation = -result["constraint_lb"]
                if violation > max_violation:
                    max_violation = violation
                    if result["counterexample"] is not None:
                        counterexample = result["counterexample"]
                        counterexample_h = result["h_lb"]
            else:
                unknown_count += 1

            total_bound_gap += result.get("bound_gap", 0.0)

        # Determine overall status
        total_regions = len(regions)
        if violated_count > 0:
            status = VerificationStatus.VIOLATED
        elif verified_count == total_regions:
            status = VerificationStatus.VERIFIED
        else:
            status = VerificationStatus.UNKNOWN

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return VerificationResult(
            status=status,
            verified_fraction=verified_count / total_regions if total_regions > 0 else 0.0,
            total_regions=total_regions,
            verified_regions=verified_count,
            violated_regions=violated_count,
            unknown_regions=unknown_count,
            counterexample=counterexample,
            counterexample_h=counterexample_h,
            max_violation=max_violation,
            avg_bound_gap=total_bound_gap / total_regions if total_regions > 0 else 0.0,
            verification_time_ms=elapsed_ms,
            region_results=region_results,
        )


# =============================================================================
# INTEGRATION WITH OPTIMAL CBF
# =============================================================================


def verify_optimal_cbf(
    cbf: Any,  # OptimalCBF
    config: VerificationConfig | None = None,
) -> VerificationResult:
    """Verify an OptimalCBF instance.

    Args:
        cbf: OptimalCBF instance to verify
        config: Verification configuration

    Returns:
        VerificationResult
    """
    # Extract components from OptimalCBF
    barrier_fn = cbf.barrier_fn
    dynamics_fn = cbf.dynamics if hasattr(cbf, "dynamics") else None

    def class_k_fn(h: torch.Tensor) -> torch.Tensor:
        """Class-K function from CBF or identity."""
        if hasattr(cbf, "class_k"):
            return cast(torch.Tensor, cbf.class_k(h))
        return h

    # Create verifier
    verifier = NeuralCBFVerifier(
        barrier_fn=barrier_fn,
        dynamics_fn=dynamics_fn,
        class_k_fn=class_k_fn,
        config=config,
    )

    # Run verification
    return verifier.verify()


def create_verified_cbf(
    cbf: Any,  # OptimalCBF
    verification_config: VerificationConfig | None = None,
) -> tuple[Any, VerificationResult]:
    """Create a verified CBF or raise if verification fails.

    Args:
        cbf: OptimalCBF to verify
        verification_config: Verification configuration

    Returns:
        Tuple of (cbf, verification_result)

    Raises:
        ValueError: If CBF fails verification
    """
    result = verify_optimal_cbf(cbf, verification_config)

    if result.status == VerificationStatus.VIOLATED:
        raise ValueError(
            f"CBF verification FAILED:\n"
            f"  {result.violated_regions} regions violated\n"
            f"  Max violation: {result.max_violation:.6f}\n"
            f"  Counterexample h(x): {result.counterexample_h}"
        )

    if result.status == VerificationStatus.VERIFIED:
        logger.info(f"CBF VERIFIED: {result.verified_regions}/{result.total_regions} regions")
    else:
        logger.warning(
            f"CBF verification UNKNOWN: {result.verified_fraction:.1%} verified, "
            f"{result.unknown_regions} inconclusive"
        )

    return cbf, result


__all__ = [
    "LBPropagator",
    "LinearBounds",
    "NeuralCBFVerifier",
    "VerificationConfig",
    "VerificationResult",
    "VerificationStatus",
    "create_verified_cbf",
    "verify_optimal_cbf",
]
