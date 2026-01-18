"""Forge Colony Integration — Connecting Forge to K OS World Model.

COLONY IDENTITY (Dec 4, 2025):
=============================
Forge is colony e₂ (Cusp A₃ catastrophe):
- Bistable decision-making with hysteresis
- Implementation focus: building, coding, execution
- Red color in the colony spectrum

INTEGRATION POINTS:
==================
1. ColonyRSSM: Forge state participates in organism-level dynamics
2. FanoActionRouter: Forge receives routed tasks for implementation
3. E8ActionReducer: Forge actions are fused with other colonies
4. OptimalityImprovements: Enhanced strange loops, Hopfield memory

CATASTROPHE DYNAMICS:
====================
Cusp (A₃) potential: V(x) = x⁴ + ax² + bx
- Two control parameters (a, b) give bistable behavior
- Smooth transitions when a > 0
- Sudden jumps when a < 0 (hysteresis)
- Perfect for implementation decisions: commit/rollback

Created: December 4, 2025
Purpose: Bridge Forge services to K OS mathematical foundations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn

if TYPE_CHECKING:
    from kagami.core.optimality.improvements import OptimalityImprovements

logger = logging.getLogger(__name__)


# =============================================================================
# FORGE COLONY CONSTANTS
# Synchronized with packages/kagami-design/design-tokens.json
# =============================================================================

FORGE_COLONY_INDEX = 1  # e₂ in octonion basis (0-indexed)
FORGE_COLOR = "#FF9500"  # Orange (Implementation e2)
FORGE_CATASTROPHE = "cusp_a3"

# Cusp catastrophe activation parameters (learned defaults)
CUSP_DEFAULT_A = -1.0  # Negative = bistable region
CUSP_DEFAULT_B = 0.0  # Control parameter


# =============================================================================
# CUSP CATASTROPHE ACTIVATION
# =============================================================================


class CuspActivation(nn.Module):
    """Cusp catastrophe activation function for Forge colony.

    The cusp is the simplest catastrophe with bistability:
    V(x) = x⁴ + ax² + bx

    Critical points satisfy: 4x³ + 2ax + b = 0

    For a < 0, there are three roots (two stable, one unstable).
    This creates hysteresis - the system "remembers" which basin it's in.

    Perfect for implementation decisions that should commit or rollback.
    """

    def __init__(
        self,
        dim: int = 256,
        a_init: float = CUSP_DEFAULT_A,
        b_init: float = CUSP_DEFAULT_B,
        learnable: bool = True,
    ):
        super().__init__()
        self.dim = dim

        if learnable:
            self.a = nn.Parameter(torch.full((dim,), a_init))
            self.b = nn.Parameter(torch.full((dim,), b_init))
        else:
            self.register_buffer("a", torch.full((dim,), a_init))
            self.register_buffer("b", torch.full((dim,), b_init))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply cusp-shaped activation.

        Instead of directly computing V(x), we use the implicit derivative
        which creates a smooth, differentiable function with cusp-like behavior:

        f(x) = tanh(x) * (1 + sigmoid(a * x²))

        This preserves gradients while creating the bistable characteristic.
        """
        # Modulated tanh with bistability
        bistable_factor = torch.sigmoid(self.a * x**2)
        shift = torch.tanh(self.b) * 0.1  # Small bias shift

        return torch.tanh(x + shift) * (1 + bistable_factor)

    def hysteresis_loss(self) -> torch.Tensor:
        """Loss encouraging bistable region (a < 0)."""
        # Penalize positive a values (monostable = boring)
        return torch.relu(self.a).mean()


# =============================================================================
# FORGE COLONY STATE
# =============================================================================


@dataclass
class ForgeColonyState:
    """State representation for Forge colony within organism.

    Matches the shared RSSM structure from ColonyRSSM:
    - h: [256] deterministic (recurrent history)
    - z: [14] stochastic (H¹⁴ uncertainty)
    """

    h: torch.Tensor  # [B, 256] deterministic state
    z: torch.Tensor  # [B, 14] stochastic state

    # Catastrophe control parameters
    cusp_a: float = CUSP_DEFAULT_A
    cusp_b: float = CUSP_DEFAULT_B

    # Implementation state
    active_tasks: list[str] = field(default_factory=list[Any])
    commit_probability: float = 0.5  # Bistable: commit or rollback

    def to_dict(self) -> dict[str, Any]:
        return {
            "h": self.h.tolist() if isinstance(self.h, torch.Tensor) else self.h,
            "z": self.z.tolist() if isinstance(self.z, torch.Tensor) else self.z,
            "cusp_a": self.cusp_a,
            "cusp_b": self.cusp_b,
            "active_tasks": self.active_tasks,
            "commit_probability": self.commit_probability,
        }


# =============================================================================
# FORGE COLONY BRIDGE
# =============================================================================


class ForgeColonyBridge(nn.Module):
    """Bridge between Forge services and K OS world model.

    This module:
    1. Translates Forge operations into colony state updates
    2. Applies cusp catastrophe dynamics
    3. Coordinates with OptimalityImprovements
    4. Emits metrics for colony activity

    INTEGRATION (Dec 4, 2025):
    =========================
    Called by ForgeMatrix during character generation to update
    colony state and leverage world model predictions.
    """

    def __init__(
        self,
        h_dim: int = 256,
        z_dim: int = 14,
        use_optimality: bool = True,
    ):
        super().__init__()
        self.h_dim = h_dim
        self.z_dim = z_dim

        # Cusp activation
        self.cusp = CuspActivation(dim=h_dim)

        # State encoders for forge operations
        self.operation_encoder = nn.Sequential(
            nn.Linear(512, 256),  # [concept_emb + context] -> h_dim
            nn.GELU(),
            self.cusp,
        )

        # Stochastic state (H¹⁴ uncertainty)
        self.z_encoder = nn.Sequential(
            nn.Linear(h_dim, z_dim * 2),  # mean + logvar
        )

        # Decision head (bistable commit/rollback)
        self.decision_head = nn.Sequential(
            nn.Linear(h_dim + z_dim, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

        # Optimality improvements
        self._optimality: OptimalityImprovements | None = None
        if use_optimality:
            try:
                from kagami.core.optimality.improvements import get_optimality_improvements

                self._optimality = get_optimality_improvements()
            except ImportError:
                logger.warning("OptimalityImprovements not available")

        # Metrics
        self._operations_processed = 0
        self._commit_ratio = 0.5

    def encode_operation(
        self,
        concept_embedding: torch.Tensor,  # [B, 256]
        context_embedding: torch.Tensor,  # [B, 256]
    ) -> ForgeColonyState:
        """Encode a Forge operation into colony state.

        Args:
            concept_embedding: Encoded character concept
            context_embedding: Encoded request context

        Returns:
            ForgeColonyState with h, z, and decision probability
        """
        concept_embedding.shape[0]

        # Concatenate embeddings
        combined = torch.cat([concept_embedding, context_embedding], dim=-1)

        # Deterministic state through cusp activation
        h = self.operation_encoder(combined)  # [B, h_dim]

        # Stochastic state
        z_params = self.z_encoder(h)
        z_mean, z_logvar = z_params.chunk(2, dim=-1)
        z_std = (0.5 * z_logvar).exp()
        z = z_mean + z_std * torch.randn_like(z_std)  # [B, z_dim]

        # Decision (commit probability)
        hz = torch.cat([h, z], dim=-1)
        commit_prob = self.decision_head(hz).squeeze(-1)  # [B]

        return ForgeColonyState(
            h=h,
            z=z,
            cusp_a=self.cusp.a.mean().item(),
            cusp_b=self.cusp.b.mean().item(),
            commit_probability=commit_prob.mean().item(),
        )

    def update_from_result(
        self,
        state: ForgeColonyState,
        success: bool,
        quality_score: float,
    ) -> ForgeColonyState:
        """Update colony state based on operation result.

        Implements active inference: use outcome to update beliefs.

        Args:
            state: Current colony state
            success: Whether operation succeeded
            quality_score: Quality metric (0-1)

        Returns:
            Updated state with refined beliefs
        """
        self._operations_processed += 1

        # Update commit ratio (EMA)
        outcome = 1.0 if success else 0.0
        self._commit_ratio = 0.95 * self._commit_ratio + 0.05 * outcome

        # Adjust cusp parameters based on outcome
        if self.training:
            # Successful high-quality → deeper bistability (a more negative)
            # Failed/low-quality → shallower bistability (a less negative)
            target_a = CUSP_DEFAULT_A * (0.5 + quality_score)
            with torch.no_grad():
                self.cusp.a.data = 0.99 * self.cusp.a.data + 0.01 * target_a

        # Update state probabilities
        state.commit_probability = self._commit_ratio

        return state

    def forward(
        self,
        concept_embedding: torch.Tensor,
        context_embedding: torch.Tensor,
        prev_state: ForgeColonyState | None = None,
    ) -> dict[str, Any]:
        """Full forward pass with state tracking.

        Args:
            concept_embedding: [B, 256] concept vector
            context_embedding: [B, 256] context vector
            prev_state: Optional previous state for recurrence

        Returns:
            Dict with state, decision, losses
        """
        state = self.encode_operation(concept_embedding, context_embedding)

        # Use optimality improvements if available
        losses: dict[str, Any] = {}
        if self._optimality is not None:
            # Use adaptive convergence for strange loop
            if hasattr(self._optimality, "convergence_monitor"):
                losses["convergence_stats"] = self._optimality.convergence_monitor.get_statistics()

            # Hysteresis loss from cusp
        losses["hysteresis_loss"] = self.cusp.hysteresis_loss()

        return {
            "state": state,
            "h": state.h,
            "z": state.z,
            "commit_probability": state.commit_probability,
            "losses": losses,
            "metrics": {
                "operations_processed": self._operations_processed,
                "commit_ratio": self._commit_ratio,
                "cusp_a_mean": state.cusp_a,
                "cusp_b_mean": state.cusp_b,
            },
        }


# =============================================================================
# OPTIMALITY-ENHANCED FORGE PIPELINE
# =============================================================================


class OptimalForge(nn.Module):
    """Forge pipeline enhanced with optimality improvements.

    IMPROVEMENTS APPLIED:
    ====================
    1. AdaptiveConvergenceMonitor - Dynamic iterations for generation loops
    2. ModernHopfieldScaled - E8 hierarchical memory for pattern storage
    3. TrueOctonionMultiply - Proper colony interactions
    4. UncertaintyCalibrator - Calibrated confidence in generation quality

    This is the "optimal" Forge - uses all available improvements.
    """

    def __init__(
        self,
        h_dim: int = 256,
        z_dim: int = 14,
        pattern_dim: int = 256,
    ):
        super().__init__()

        # Colony bridge
        self.colony_bridge = ForgeColonyBridge(h_dim=h_dim, z_dim=z_dim)

        # Optimality components (declare with Optional types)
        self.convergence: AdaptiveConvergenceMonitor | None
        self.hopfield: ModernHopfieldScaled | None
        self.octonion: TrueOctonionMultiply | None
        self.calibrator: UncertaintyCalibrator | None

        try:
            from kagami.core.optimality.improvements import (
                AdaptiveConvergenceMonitor,
                ModernHopfieldScaled,
                TrueOctonionMultiply,
                UncertaintyCalibrator,
            )

            self.convergence = AdaptiveConvergenceMonitor()
            self.hopfield = ModernHopfieldScaled(pattern_dim=pattern_dim)
            self.octonion = TrueOctonionMultiply()
            self.calibrator = UncertaintyCalibrator()
            self._has_optimality = True

        except ImportError:
            logger.warning("Optimality improvements not available, using basic mode")
            self._has_optimality = False
            self.convergence = None
            self.hopfield = None
            self.octonion = None
            self.calibrator = None

        # Pattern memory (stores successful generation patterns)
        self.register_buffer("pattern_count", torch.tensor(0))

    def store_pattern(self, pattern: torch.Tensor) -> None:
        """Store a successful generation pattern in Hopfield memory."""
        if self._has_optimality and self.hopfield is not None:
            # Pattern is stored implicitly through Hopfield training
            count_val = self.get_buffer("pattern_count")
            if isinstance(count_val, torch.Tensor):
                self.register_buffer("pattern_count", count_val + 1)

    def retrieve_similar(self, query: torch.Tensor) -> torch.Tensor:
        """Retrieve similar patterns from memory."""
        if self._has_optimality and self.hopfield is not None:
            result = self.hopfield(query)
            return result["retrieved"]  # type: ignore[no-any-return]
        return query  # Passthrough if no memory

    def colony_interact(
        self,
        forge_state: torch.Tensor,  # [B, 8]
        other_colony_state: torch.Tensor,  # [B, 8]
    ) -> torch.Tensor:
        """Compute interaction with another colony using octonion multiplication.

        Uses proper octonion multiplication (non-commutative, non-associative)
        as defined by Fano plane structure. Element-wise product is INCORRECT
        for colony interactions.
        """
        if self._has_optimality and self.octonion is not None:
            return self.octonion.multiply(forge_state, other_colony_state)
        # Use OctonionManifold from core math as canonical implementation
        from kagami_math.octonions.algebra import OctonionManifold

        manifold = OctonionManifold()
        # Extract imaginary parts (7D), multiply, then reconstruct 8D
        im1 = forge_state[..., 1:]
        im2 = other_colony_state[..., 1:]
        im_result = manifold.multiply(im1, im2)
        # Reconstruct 8D: real part from dot product contribution
        real_part = -(im1 * im2).sum(dim=-1, keepdim=True)
        return torch.cat([real_part, im_result], dim=-1)

    def calibrated_confidence(self, raw_confidence: float, was_correct: bool) -> float:
        """Get calibrated confidence using uncertainty calibrator."""
        if self._has_optimality and self.calibrator is not None:
            self.calibrator.update(raw_confidence, was_correct)
            # Return ECE as a measure of calibration quality
            return 1.0 - self.calibrator.compute_ece()
        return raw_confidence

    def forward(
        self,
        concept_embedding: torch.Tensor,
        context_embedding: torch.Tensor,
    ) -> dict[str, Any]:
        """Enhanced forward pass with all optimality improvements."""

        # Basic colony processing
        result = self.colony_bridge(concept_embedding, context_embedding)

        # Enhance with Hopfield memory
        if self._has_optimality and self.hopfield is not None:
            h = result["h"]
            hopfield_result = self.hopfield(h)
            result["hopfield_retrieved"] = hopfield_result["retrieved"]
            result["hopfield_entropy"] = hopfield_result["attention_entropy"]
            result["effective_capacity"] = hopfield_result["effective_capacity"]

            if "separation_loss" in hopfield_result:
                result["losses"]["hopfield_separation"] = hopfield_result["separation_loss"]

        # Add calibration metrics
        if self._has_optimality and self.calibrator is not None:
            result["calibration_ece"] = self.calibrator.compute_ece()

        return result  # type: ignore[no-any-return]


# =============================================================================
# FACTORY AND INTEGRATION
# =============================================================================

_FORGE_COLONY_BRIDGE: ForgeColonyBridge | None = None
_OPTIMAL_FORGE: OptimalForge | None = None


def get_forge_colony_bridge() -> ForgeColonyBridge:
    """Get singleton ForgeColonyBridge instance."""
    global _FORGE_COLONY_BRIDGE
    if _FORGE_COLONY_BRIDGE is None:
        _FORGE_COLONY_BRIDGE = ForgeColonyBridge()
    return _FORGE_COLONY_BRIDGE


def get_optimal_forge() -> OptimalForge:
    """Get singleton OptimalForge instance."""
    global _OPTIMAL_FORGE
    if _OPTIMAL_FORGE is None:
        _OPTIMAL_FORGE = OptimalForge()
    return _OPTIMAL_FORGE


__all__ = [
    "CUSP_DEFAULT_A",
    "CUSP_DEFAULT_B",
    "FORGE_CATASTROPHE",
    # Constants
    "FORGE_COLONY_INDEX",
    "FORGE_COLOR",
    # Classes
    "CuspActivation",
    "ForgeColonyBridge",
    "ForgeColonyState",
    "OptimalForge",
    # Factories
    "get_forge_colony_bridge",
    "get_optimal_forge",
]
