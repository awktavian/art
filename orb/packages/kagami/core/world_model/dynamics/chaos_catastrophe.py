"""Unified Chaos and Catastrophe Dynamics for KagamiWorldModel.

This module integrates:
1. Chaos Theory (strange attractors, Lyapunov exponents, edge-of-chaos)
2. Catastrophe Theory (7 elementary catastrophes, singularity detection)
3. World Model dynamics (state evolution, training loss, monitoring)

DESIGN PHILOSOPHY:
==================
Rather than having chaos and catastrophe as separate, fragmented subsystems,
this module provides a UNIFIED interface for:

- Computing catastrophe risk from agent/colony embeddings
- Enriching representations with chaotic dynamics
- Monitoring system criticality (edge of chaos)
- Providing training loss terms for geometric constraints

Mathematical Foundation:
========================

1. CATASTROPHE THEORY (Thom, 1972; Jeffrey, 2022)
   - 7 elementary catastrophes: Fold, Cusp, Swallowtail, Butterfly,
     Hyperbolic Umbilic, Elliptic Umbilic, Parabolic Umbilic
   - Mapped to 7 octonion imaginary units (e₁...e₇)
   - Uses B-G determinant conditions (analytical polynomials, not learned)
   - Risk = proximity to singularity where B₁ = B₂ = ... = Bᵣ = 0
   - G₂-invariant risk aggregation

2. CHAOS THEORY (Lorenz, 1963; Benettin et al., 1980)
   - Full Lyapunov spectrum via QR factorization (rigorous)
   - λ_max > 0 indicates chaos; λ_max ≈ 0 is edge of chaos
   - Kaplan-Yorke dimension measures attractor complexity

3. INTEGRATION
   - Catastrophe risk feeds into CBF safety state
   - Chaos enrichment adds nonlinearity to representations
   - Edge-of-chaos monitoring guides system tuning

References:
- Thom, R. (1972). Structural Stability and Morphogenesis
- Jeffrey, M.R. (2022). Catastrophe conditions for vector fields in ℝⁿ
- Lorenz, E.N. (1963). Deterministic Nonperiodic Flow
- Benettin et al. (1980). Lyapunov characteristic exponents
- Bertschinger et al. (2004). Edge of Chaos in Reservoir Computing

Created: November 29, 2025
Updated: November 30, 2025 - Replaced learned mappings with rigorous implementations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Import canonical constants (consolidation: Dec 3, 2025)
from kagami_math.catastrophe_constants import CATASTROPHE_NAMES

from kagami.core.world_model.dynamics.analytical_catastrophe import (
    AnalyticalCatastropheDetector,
    CatastropheResult,
)

# Import rigorous implementations
from kagami.core.world_model.dynamics.rigorous_lyapunov import (
    LyapunovSpectrumResult,
    RigorousLyapunovComputer,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ChaosCatastropheConfig:
    """Configuration for unified chaos-catastrophe dynamics.

    HARDENED (Dec 5, 2025):
    =======================
    ALL FEATURES ALWAYS ENABLED. No optional toggles.
    - Catastrophe singularity detection: ALWAYS ON
    - Chaotic feature enrichment: ALWAYS ON
    - Edge-of-chaos monitoring: ALWAYS ON

    Attributes:
        catastrophe_latent_dim: Dimension for catastrophe projections
        chaos_strength: 0-1, controls chaotic perturbation magnitude
        chaos_steps: Number of Lorenz attractor iterations

        target_lyapunov: Target Lyapunov exponent for edge-of-chaos
        lyapunov_tolerance: Acceptable deviation from target

        lambda_catastrophe: Weight for catastrophe loss term
        lambda_stability: Weight for stability regularization
        lambda_chaos_entropy: Weight for chaos entropy regularization
    """

    # Catastrophe parameters
    catastrophe_latent_dim: int = 64
    singularity_threshold: float = 0.7
    unsafe_threshold: float = 0.9

    # Chaos parameters
    chaos_strength: float = 0.3
    chaos_steps: int = 30
    lorenz_sigma: float = 10.0
    lorenz_rho: float = 28.0
    lorenz_beta: float = 8.0 / 3.0
    lorenz_dt: float = 0.01

    # Edge-of-chaos parameters
    target_lyapunov: float = 0.05
    lyapunov_tolerance: float = 0.1

    # Loss weights
    lambda_catastrophe: float = 0.1
    lambda_stability: float = 0.05
    lambda_chaos_entropy: float = 0.01


@dataclass
class CatastropheMetrics:
    """Metrics for catastrophe detection."""

    total_risk: float
    gradient_risk: float  # Risk from B₁ determinant
    hessian_risk: float  # Risk from B₂ determinant
    dominant_type: str
    risk_vector: list[float]
    b_determinants: list[float]  # B₁, B₂, B₃ values
    near_singularity: bool
    cbf_unsafe: bool


# =============================================================================
# CATASTROPHE DETECTION (Rigorous B-G Conditions)
# =============================================================================


class CatastropheDetector(nn.Module):
    """Catastrophe singularity detector using rigorous B-G conditions.

    Uses AnalyticalCatastropheDetector with exact polynomial B-determinants
    from singularity theory (Jeffrey, 2022).

    Features:
    1. B-G determinant conditions (analytical polynomials)
    2. Vectorized computation for all 7 catastrophes
    3. True singularity detection (B₁ = B₂ = ... = Bᵣ = 0)
    4. G₂-invariant feature aggregation
    5. Fano plane interaction effects
    """

    # Reference canonical names (consolidation: Dec 3, 2025)
    TYPES = list(CATASTROPHE_NAMES)

    def __init__(self, config: ChaosCatastropheConfig, input_dim: int | None = None):
        """Initialize catastrophe detector with rigorous B-G conditions."""
        super().__init__()
        self.config = config
        actual_input_dim = input_dim or config.catastrophe_latent_dim
        self.input_dim = actual_input_dim

        # Rigorous analytical detector
        self._detector = AnalyticalCatastropheDetector(
            input_dim=actual_input_dim,
            singularity_threshold=config.singularity_threshold,
            unsafe_threshold=config.unsafe_threshold,
        )

        logger.debug("CatastropheDetector initialized: dim=%d", actual_input_dim)

    def forward(self, embedding: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, str]:
        """Detect catastrophe singularities.

        Args:
            embedding: [B, D] agent/colony embeddings

        Returns:
            total_risk: [B] scalar risk in [0, 1]
            risk_vector: [B, 7] per-type risks
            dominant_type: Name of highest-risk catastrophe
        """
        return self._detector(embedding)

    def forward_detailed(self, embedding: torch.Tensor) -> CatastropheMetrics:
        """Compute detailed catastrophe metrics for diagnostics."""
        if embedding.dim() == 1:
            embedding = embedding.unsqueeze(0)

        result = self._detector.detect_detailed(embedding)

        return CatastropheMetrics(
            total_risk=result.total_risk,
            gradient_risk=abs(result.b_determinants[0]) if result.b_determinants else 0.0,
            hessian_risk=abs(result.b_determinants[1]) if len(result.b_determinants) > 1 else 0.0,
            dominant_type=result.type_name,
            risk_vector=list(result.type_risks.values()),
            b_determinants=result.b_determinants,
            near_singularity=result.near_singularity,
            cbf_unsafe=result.cbf_unsafe,
        )

    def get_cbf_risk(self, embedding: torch.Tensor) -> float:
        """Get scalar risk for CBF integration."""
        return self._detector.get_cbf_risk(embedding)


# =============================================================================
# CHAOTIC ENRICHMENT (with Rigorous Lyapunov)
# =============================================================================


class ChaoticEnricher(nn.Module):
    """Chaotic feature enrichment via Lorenz attractor.

    Features:
    1. Pure torch operations (no numpy in forward pass)
    2. Vectorized RK4 integration
    3. Rigorous Lyapunov spectrum computation via QR factorization
    """

    def __init__(self, dim: int, config: ChaosCatastropheConfig):
        super().__init__()
        self.config = config
        self.dim = dim

        # Lorenz parameters (learnable for fine-tuning)
        self.lorenz = nn.Parameter(
            torch.tensor([config.lorenz_sigma, config.lorenz_rho, config.lorenz_beta])
        )
        self.dt = config.lorenz_dt
        self.steps = config.chaos_steps

        # Projections
        self.input_proj = nn.Linear(dim, 3)  # To Lorenz space
        self.output_proj = nn.Linear(18, dim)  # From trajectory features

        # Chaos strength (learnable)
        self.strength = nn.Parameter(torch.tensor(config.chaos_strength))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Enrich features with chaotic dynamics.

        Args:
            x: [B, D] or [B, S, D] input features

        Returns:
            Chaos-enriched features (same shape)
        """
        orig_shape = x.shape
        if x.dim() == 3:
            B, S, D = x.shape
            x_flat = x.reshape(B * S, D)
        else:
            x_flat = x

        # Project to Lorenz initial conditions
        state = self.input_proj(x_flat)  # [N, 3]

        # Iterate Lorenz attractor (vectorized RK4)
        trajectory = [state]
        for _ in range(self.steps):
            state = self._lorenz_step(state)
            trajectory.append(state)

        traj = torch.stack(trajectory, dim=1)  # [N, steps+1, 3]

        # Extract trajectory statistics
        features = torch.cat(
            [
                traj[:, 0],  # initial
                traj[:, -1],  # final
                traj.mean(dim=1),  # mean
                traj.std(dim=1),  # std
                traj.min(dim=1)[0],  # min
                traj.max(dim=1)[0],  # max
            ],
            dim=-1,
        )  # [N, 18]

        # Project back and apply as residual
        perturbation = self.output_proj(features)
        output = x_flat + torch.tanh(perturbation) * self.strength.abs()

        return output.reshape(orig_shape)

    def _lorenz_step(self, state: torch.Tensor) -> torch.Tensor:
        """Single RK4 Lorenz step."""
        sigma, rho, beta = self.lorenz.abs().clamp(min=0.1)

        def deriv(s):  # type: ignore[no-untyped-def]
            x, y, z = s[..., 0], s[..., 1], s[..., 2]
            return torch.stack([sigma * (y - x), x * (rho - z) - y, x * y - beta * z], dim=-1)

        # RK4
        k1 = deriv(state)
        k2 = deriv(state + 0.5 * self.dt * k1)
        k3 = deriv(state + 0.5 * self.dt * k2)
        k4 = deriv(state + self.dt * k3)

        return state + (self.dt / 6) * (k1 + 2 * k2 + 2 * k3 + k4)

    def estimate_lyapunov(self, x: torch.Tensor, steps: int = 100) -> float:
        """Estimate largest Lyapunov exponent using rigorous QR method.

        Args:
            x: Input features [D], [B, D], or [B, S, D]
            steps: Integration steps

        Returns:
            Maximum Lyapunov exponent (λ_max)
        """
        result = self.estimate_lyapunov_spectrum(x, steps)
        return result.lambda_max

    def estimate_lyapunov_spectrum(
        self, x: torch.Tensor, steps: int = 1000
    ) -> LyapunovSpectrumResult:
        """Compute full Lyapunov spectrum using rigorous QR method.

        This is the preferred method for Lyapunov analysis.

        Args:
            x: Input features [D], [B, D], or [B, S, D]
            steps: Integration steps (more = more accurate)

        Returns:
            LyapunovSpectrumResult with full spectrum and diagnostics
        """
        with torch.no_grad():
            # Handle any input shape: [D], [B, D], [B, S, D]
            # We need to get a single [D] vector for Lyapunov analysis

            if x.dim() == 1:
                # [D] - use as is
                sample = x
            elif x.dim() == 2:
                # [B, D] - take first batch element
                sample = x[0]
            elif x.dim() == 3:
                # [B, S, D] - take first batch, first sequence element
                sample = x[0, 0]
            else:
                # Flatten and take first element
                sample = x.flatten()[: x.shape[-1]]

            # Project to 3D Lorenz space
            state = self.input_proj(sample.unsqueeze(0))  # [1, 3]

            computer = RigorousLyapunovComputer(
                dim=3,
                dt=self.dt,
                qr_interval=10,
            )
            return computer.compute_spectrum(
                state,
                total_steps=steps,
                transient_steps=min(100, steps // 10),
            )


# =============================================================================
# EDGE-OF-CHAOS CONTROLLER
# =============================================================================


class EdgeOfChaosController:
    """Monitors and maintains edge-of-chaos regime.

    The edge of chaos (λ ≈ 0) is where computational capacity is maximized
    (Bertschinger et al., 2004). This controller:

    1. Tracks Lyapunov exponent estimates
    2. Classifies current regime (ordered, edge, chaotic)
    3. Provides adjustment signals for system tuning
    """

    def __init__(self, config: ChaosCatastropheConfig):
        self.config = config
        self.target = config.target_lyapunov
        self.tolerance = config.lyapunov_tolerance
        self.history: list[float] = []

    def update(self, lyapunov: float) -> dict[str, Any]:
        """Update with new Lyapunov measurement.

        Returns:
            Dict with regime classification and adjustment signal
        """
        self.history.append(lyapunov)
        if len(self.history) > 100:
            self.history.pop(0)

        # Classify regime
        if lyapunov < -0.1:
            regime = "ordered"
        elif lyapunov > 0.5:
            regime = "chaotic"
        elif abs(lyapunov - self.target) <= self.tolerance:
            regime = "edge_of_chaos"
        elif lyapunov > 0:
            regime = "weakly_chaotic"
        else:
            regime = "stable"

        # Adjustment signal
        if lyapunov < self.target - self.tolerance:
            adjustment = "increase_chaos"
            delta = min(0.2, (self.target - lyapunov) / 2)
        elif lyapunov > self.target + self.tolerance:
            adjustment = "decrease_chaos"
            delta = -min(0.2, (lyapunov - self.target) / 2)
        else:
            adjustment = "maintain"
            delta = 0.0

        return {
            "regime": regime,
            "lyapunov": lyapunov,
            "at_edge": regime == "edge_of_chaos",
            "adjustment": adjustment,
            "delta": delta,
            "avg_lyapunov": np.mean(self.history[-10:]) if self.history else 0.0,
        }


# =============================================================================
# UNIFIED DYNAMICS MODULE
# =============================================================================


class ChaosCatastropheDynamics(nn.Module):
    """Unified chaos and catastrophe dynamics for world model integration.

    This is the main interface for the KagamiWorldModel to use.
    Provides:
    - Catastrophe risk computation (via rigorous B-G conditions)
    - Chaotic feature enrichment
    - Edge-of-chaos monitoring (via rigorous Lyapunov spectrum)
    - Training loss terms

    Usage:
        dynamics = ChaosCatastropheDynamics(config, dim=512)

        # During forward pass
        enriched = dynamics.enrich(features)

        # During training
        loss_terms = dynamics.compute_loss(prediction, target, embeddings)

        # For monitoring
        metrics = dynamics.get_metrics()
    """

    def __init__(
        self,
        config: ChaosCatastropheConfig | None = None,
        dim: int = 512,
        manifold_dim: int | None = None,
    ):
        super().__init__()
        self.config = config or ChaosCatastropheConfig()
        self.dim = dim
        self.manifold_dim = manifold_dim or 15  # Default: E8(8) + S7(7) = 15

        # ALL FEATURES ALWAYS ENABLED (Dec 5, 2025 - HARDENED)

        # Catastrophe detector (ALWAYS ON)
        self.catastrophe = CatastropheDetector(self.config, input_dim=self.manifold_dim)

        # Chaotic enricher (ALWAYS ON)
        self.chaos = ChaoticEnricher(dim, self.config)

        # Edge-of-chaos controller (ALWAYS ON)
        self.edge_controller = EdgeOfChaosController(self.config)

        # Metrics state
        self._last_catastrophe_risk = 0.0
        self._last_lyapunov = 0.0
        self._last_regime = "unknown"

        logger.debug("ChaosCatastropheDynamics initialized (HARDENED)")

    def enrich(self, x: torch.Tensor) -> torch.Tensor:
        """Enrich features with chaotic dynamics.

        Args:
            x: Input features [B, D] or [B, S, D]

        Returns:
            Enriched features (same shape)
        """
        return self.chaos(x)

    def detect_catastrophe(self, embedding: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, str]:
        """Detect catastrophe risk from embedding.

        Args:
            embedding: [B, D] agent/colony embedding

        Returns:
            total_risk: [B] scalar risk
            risk_vector: [B, 7] per-type risks
            dominant_type: Name of dominant catastrophe
        """
        risk, vec, dom = self.catastrophe(embedding)
        self._last_catastrophe_risk = risk.mean().item()
        return risk, vec, dom

    def update_lyapunov(self, x: torch.Tensor) -> dict[str, Any]:
        """Update Lyapunov estimate and edge-of-chaos status.

        Args:
            x: Features to estimate Lyapunov from

        Returns:
            Edge-of-chaos metrics dict[str, Any]
        """
        lyap = self.chaos.estimate_lyapunov(x)
        self._last_lyapunov = lyap
        result = self.edge_controller.update(lyap)
        self._last_regime = result["regime"]
        return result

    def compute_loss(
        self,
        prediction: torch.Tensor,
        target: torch.Tensor,
        embeddings: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute training loss terms.

        NOTE: This method is provided for standalone usage.
        In the unified World Model training loop, please use UnifiedLossModule
        which integrates these terms optimally.
        """
        device = prediction.device
        losses = {}

        # Base prediction loss
        losses["prediction"] = F.mse_loss(prediction, target)

        # Catastrophe risk loss (ALWAYS computed)
        losses["catastrophe"] = torch.tensor(0.0, device=device)
        if embeddings is not None:
            if embeddings.dim() == 3:
                # [B, 7, D] - process each colony
                B = embeddings.shape[0]
                total_risk = torch.zeros(B, device=device)
                for i in range(embeddings.shape[1]):
                    risk, _, _ = self.catastrophe(embeddings[:, i])
                    total_risk += risk
                losses["catastrophe"] = total_risk.mean() * self.config.lambda_catastrophe
            else:
                risk, _, _ = self.catastrophe(embeddings)
                losses["catastrophe"] = risk.mean() * self.config.lambda_catastrophe

        # Stability regularization (penalize sharp gradients)
        losses["stability"] = torch.tensor(0.0, device=device)
        if prediction.shape[-1] > 1:
            grad_mag = (prediction[..., 1:] - prediction[..., :-1]).norm(dim=-1).mean()
            losses["stability"] = grad_mag * self.config.lambda_stability

        # Chaos entropy regularization (encourage exploration)
        losses["chaos_entropy"] = torch.tensor(0.0, device=device)
        if self.chaos is not None:
            # Encourage diverse outputs (high entropy)
            pred_entropy = (
                -(F.softmax(prediction, dim=-1) * F.log_softmax(prediction + 1e-8, dim=-1))
                .sum(dim=-1)
                .mean()
            )
            losses["chaos_entropy"] = -pred_entropy * self.config.lambda_chaos_entropy

        losses["total"] = (
            losses["prediction"]
            + losses["catastrophe"]
            + losses["stability"]
            + losses["chaos_entropy"]
        )

        return losses

    def get_metrics(self) -> dict[str, Any]:
        """Get current dynamics metrics for monitoring.

        Returns:
            Dict with catastrophe_risk, lyapunov, regime, etc.
        """
        return {
            "catastrophe_risk": self._last_catastrophe_risk,
            "lyapunov_exponent": self._last_lyapunov,
            "regime": self._last_regime,
            "at_edge_of_chaos": self._last_regime == "edge_of_chaos",
            "config": {
                # HARDENED (Dec 5, 2025): All features always enabled
                "catastrophe_enabled": True,
                "chaos_enabled": True,
                "chaos_strength": self.config.chaos_strength,
            },
        }

    def get_cbf_risk(self, embedding: torch.Tensor) -> float:
        """Get scalar risk for CBF integration.

        Args:
            embedding: Agent embedding [D] or [1, D]

        Returns:
            Risk value in [0, 1]
        """
        if self.catastrophe is not None:
            return self.catastrophe.get_cbf_risk(embedding)
        return 0.0


# =============================================================================
# FACTORY AND SINGLETON
# =============================================================================


_dynamics_instance: ChaosCatastropheDynamics | None = None


def get_chaos_catastrophe_dynamics(
    config: ChaosCatastropheConfig | None = None,
    dim: int = 512,
    manifold_dim: int = 15,  # E8(8) + S7(7) = 15
) -> ChaosCatastropheDynamics:
    """Get or create singleton ChaosCatastropheDynamics instance.

    Args:
        config: Optional configuration
        dim: Bulk feature dimension (for chaos enrichment)
        manifold_dim: Manifold dimension (for catastrophe detection)

    Returns:
        ChaosCatastropheDynamics singleton
    """
    global _dynamics_instance
    if _dynamics_instance is None:
        _dynamics_instance = ChaosCatastropheDynamics(config, dim, manifold_dim)
    return _dynamics_instance


def reset_chaos_catastrophe_dynamics() -> None:
    """Reset singleton (for testing)."""
    global _dynamics_instance
    _dynamics_instance = None


__all__ = [
    "AnalyticalCatastropheDetector",
    "CatastropheDetector",
    "CatastropheMetrics",
    "CatastropheResult",
    "ChaosCatastropheConfig",
    "ChaosCatastropheDynamics",
    "ChaoticEnricher",
    "EdgeOfChaosController",
    "LyapunovSpectrumResult",
    # Re-export rigorous implementations
    "RigorousLyapunovComputer",
    "get_chaos_catastrophe_dynamics",
    "reset_chaos_catastrophe_dynamics",
]
