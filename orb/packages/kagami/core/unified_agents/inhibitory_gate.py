"""Inhibitory Gate - Brain-Inspired Colony Suppression.

BRAIN SCIENCE BASIS (December 2025):
====================================
The brain is ~20% inhibitory (GABAergic interneurons). This provides:
1. Winner-take-all competition for ambiguous tasks
2. Lateral inhibition between similar colonies
3. Global rhythm coordination (PV fast-spiking)
4. Dendritic gating (SST slow inhibition)
5. Disinhibition for meta-control (VIP interneurons)

This module implements three inhibitory mechanisms:
- FastInhibition: PV-like global suppression
- SlowInhibition: SST-like selective gating
- Disinhibition: VIP-like meta-level control

References:
- Cardin (2018): Inhibitory Interneurons Regulate Temporal Precision
- Pfeffer et al. (2013): Inhibition of Inhibition in Visual Cortex
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class InhibitionType(Enum):
    """Types of inhibitory mechanisms."""

    FAST = "fast"  # PV-like: rapid, global
    SLOW = "slow"  # SST-like: sustained, dendritic
    DISINHIBITION = "disinhibition"  # VIP-like: inhibit inhibitors


@dataclass
class InhibitionState:
    """Current state of inhibitory system."""

    # Per-colony inhibition levels [7]
    inhibition_levels: torch.Tensor

    # Which colonies are suppressed (threshold > 0.5)
    suppressed_mask: torch.Tensor

    # Disinhibition signal (meta-control)
    disinhibition: torch.Tensor

    # Winner of competition (if any)
    winner_idx: int | None = None

    # Inhibition statistics
    mean_inhibition: float = 0.0
    max_inhibition: float = 0.0


class FastInhibition(nn.Module):
    """PV-like fast-spiking inhibition for global rhythm coordination.

    Implements rapid, blanket inhibition that enforces winner-take-all
    dynamics when multiple colonies compete for the same task.
    """

    def __init__(
        self,
        num_colonies: int = 7,
        inhibition_strength: float = 0.8,
        competition_threshold: float = 0.3,
    ):
        super().__init__()
        self.num_colonies = num_colonies
        self.inhibition_strength = inhibition_strength
        self.competition_threshold = competition_threshold

        # Lateral inhibition weights (all-to-all except self)
        # Initialize to uniform lateral inhibition
        lateral = torch.ones(num_colonies, num_colonies) * 0.15
        lateral.fill_diagonal_(0.0)  # No self-inhibition
        self.lateral_weights = nn.Parameter(lateral)

        # Global inhibition gain
        self.global_gain = nn.Parameter(torch.tensor(1.0))

    def forward(
        self,
        activations: torch.Tensor,  # [B, 7] colony activations
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute fast inhibition.

        Args:
            activations: Colony activation levels [B, 7]

        Returns:
            inhibited_activations: Post-inhibition activations [B, 7]
            inhibition_levels: Amount of inhibition per colony [B, 7]
        """
        # Lateral inhibition: each colony inhibits others proportionally
        # [B, 7] @ [7, 7] = [B, 7]
        lateral_inhibition = torch.matmul(activations, self.lateral_weights.T)

        # Scale by global gain
        lateral_inhibition = lateral_inhibition * self.global_gain

        # Apply inhibition (subtract, clamp to 0)
        inhibited = activations - lateral_inhibition * self.inhibition_strength
        inhibited = F.relu(inhibited)

        # Normalize to maintain total activation mass
        total_before = activations.sum(dim=-1, keepdim=True).clamp(min=1e-6)
        total_after = inhibited.sum(dim=-1, keepdim=True).clamp(min=1e-6)
        inhibited = inhibited * (total_before / total_after)

        return inhibited, lateral_inhibition


class SlowInhibition(nn.Module):
    """SST-like slow inhibition for selective dendritic gating.

    Implements sustained, targeted inhibition that gates specific
    information pathways based on context and history.
    """

    def __init__(
        self,
        num_colonies: int = 7,
        hidden_dim: int = 64,
        time_constant: float = 0.9,  # Slow decay (SST is slow)
    ):
        super().__init__()
        self.num_colonies = num_colonies
        self.time_constant = time_constant

        # Context-dependent gating
        self.gate_net = nn.Sequential(
            nn.Linear(num_colonies * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, num_colonies),
            nn.Sigmoid(),
        )

        # Persistent inhibition state (decays slowly)
        self.register_buffer("persistent_state", torch.zeros(1, num_colonies))

    def forward(
        self,
        activations: torch.Tensor,  # [B, 7]
        context: torch.Tensor | None = None,  # [B, 7] task context
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute slow inhibition.

        Args:
            activations: Colony activation levels [B, 7]
            context: Optional task context for targeted gating [B, 7]

        Returns:
            gated_activations: Post-gating activations [B, 7]
            gate_values: Gate values per colony [B, 7]
        """
        batch_size = activations.shape[0]

        # Use activations as context if not provided
        if context is None:
            context = activations

        # Expand persistent state to batch size
        persistent = self.persistent_state.expand(batch_size, -1)  # type: ignore[operator]

        # Compute gate based on current + persistent state
        gate_input = torch.cat([activations, persistent], dim=-1)
        gate = self.gate_net(gate_input)

        # Apply gate (1 = pass through, 0 = suppress)
        gated = activations * gate

        # Update persistent state with slow decay
        with torch.no_grad():
            new_persistent = self.time_constant * self.persistent_state + (  # type: ignore[operator]
                1 - self.time_constant
            ) * (1 - gate.mean(dim=0, keepdim=True))
            self.persistent_state.copy_(new_persistent)  # type: ignore[operator]

        return gated, gate


class Disinhibition(nn.Module):
    """VIP-like disinhibition for meta-level control.

    Implements "inhibition of inhibition" - allows meta-cognitive
    processes to release colonies from inhibition when needed.
    """

    def __init__(
        self,
        num_colonies: int = 7,
        hidden_dim: int = 32,
    ):
        super().__init__()
        self.num_colonies = num_colonies

        # Meta-control signal generator
        self.meta_control = nn.Sequential(
            nn.Linear(num_colonies * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, num_colonies),
            nn.Sigmoid(),
        )

    def forward(
        self,
        inhibition_levels: torch.Tensor,  # [B, 7] current inhibition
        meta_signal: torch.Tensor,  # [B, 7] meta-cognitive signal
    ) -> torch.Tensor:
        """Compute disinhibition signal.

        Args:
            inhibition_levels: Current inhibition per colony [B, 7]
            meta_signal: Meta-cognitive control signal [B, 7]

        Returns:
            disinhibition: Amount to reduce inhibition [B, 7]
        """
        # Combine inhibition state with meta signal
        combined = torch.cat([inhibition_levels, meta_signal], dim=-1)

        # Generate disinhibition (how much to release)
        disinhibition = self.meta_control(combined)

        return cast(torch.Tensor, disinhibition)


class InhibitoryGate(nn.Module):
    """Unified inhibitory gate combining all mechanisms.

    Brain-inspired inhibitory system with:
    1. Fast (PV) inhibition for competition
    2. Slow (SST) inhibition for context-dependent gating
    3. Disinhibition (VIP) for meta-control

    The final inhibition is computed as:
        effective_inhibition = fast + slow - disinhibition
        output = input * (1 - effective_inhibition)
    """

    def __init__(
        self,
        num_colonies: int = 7,
        hidden_dim: int = 64,
        fast_strength: float = 0.6,
        slow_strength: float = 0.3,
        disinhibition_strength: float = 0.2,
        winner_take_all_threshold: float = 0.7,
    ):
        super().__init__()
        self.num_colonies = num_colonies
        self.fast_strength = fast_strength
        self.slow_strength = slow_strength
        self.disinhibition_strength = disinhibition_strength
        self.winner_take_all_threshold = winner_take_all_threshold

        # Three inhibitory mechanisms
        self.fast = FastInhibition(
            num_colonies=num_colonies,
            inhibition_strength=fast_strength,
        )
        self.slow = SlowInhibition(
            num_colonies=num_colonies,
            hidden_dim=hidden_dim,
        )
        self.disinhibition = Disinhibition(
            num_colonies=num_colonies,
            hidden_dim=hidden_dim // 2,
        )

        # Blend weights for combining mechanisms
        self.blend = nn.Parameter(torch.tensor([0.5, 0.3, 0.2]))  # fast, slow, dis

    def forward(
        self,
        activations: torch.Tensor,  # [B, 7] colony activations
        context: torch.Tensor | None = None,  # [B, 7] task context
        meta_signal: torch.Tensor | None = None,  # [B, 7] meta-control
    ) -> tuple[torch.Tensor, InhibitionState]:
        """Apply unified inhibitory gating.

        Args:
            activations: Raw colony activation levels [B, 7]
            context: Optional task context for slow gating
            meta_signal: Optional meta-cognitive signal for disinhibition

        Returns:
            gated_activations: Final post-inhibition activations [B, 7]
            state: InhibitionState with diagnostic information
        """
        # Note: batch_size=activations.shape[0], device=activations.device if needed

        # Default meta signal to zeros
        if meta_signal is None:
            meta_signal = torch.zeros_like(activations)

        # Apply fast inhibition (competition)
        _fast_out, fast_inhib = self.fast(activations)

        # Apply slow inhibition (context gating)
        _slow_out, slow_gate = self.slow(activations, context)

        # Compute disinhibition
        combined_inhib = fast_inhib * self.fast_strength + (1 - slow_gate) * self.slow_strength
        disinhibition = self.disinhibition(combined_inhib, meta_signal)

        # Compute effective inhibition
        effective_inhib = combined_inhib - disinhibition * self.disinhibition_strength
        effective_inhib = effective_inhib.clamp(0, 1)

        # Apply inhibition
        gated = activations * (1 - effective_inhib)

        # Winner-take-all for high-competition scenarios
        max_activation = gated.max(dim=-1, keepdim=True)[0]
        winner_mask = (gated == max_activation) & (max_activation > self.winner_take_all_threshold)
        winner_idx = None

        if winner_mask.any():
            # Suppress non-winners
            suppression = torch.where(
                winner_mask,
                torch.ones_like(gated),
                torch.ones_like(gated) * 0.1,  # 90% suppression of losers
            )
            gated = gated * suppression

            # Record winner
            winner_idx = gated.argmax(dim=-1)[0].item()

        # Build state
        state = InhibitionState(
            inhibition_levels=effective_inhib,
            suppressed_mask=(effective_inhib > 0.5),
            disinhibition=disinhibition,
            winner_idx=winner_idx,
            mean_inhibition=effective_inhib.mean().item(),
            max_inhibition=effective_inhib.max().item(),
        )

        return gated, state

    def get_inhibition_stats(self) -> dict[str, float]:
        """Get current inhibition statistics."""
        return {
            "fast_global_gain": self.fast.global_gain.item(),
            "blend_fast": self.blend[0].item(),
            "blend_slow": self.blend[1].item(),
            "blend_dis": self.blend[2].item(),
            "slow_time_constant": self.slow.time_constant,
        }


# =============================================================================
# FACTORY AND UTILITIES
# =============================================================================


def create_inhibitory_gate(
    num_colonies: int = 7,
    config: dict[str, Any] | None = None,
) -> InhibitoryGate:
    """Create inhibitory gate with optional configuration.

    Args:
        num_colonies: Number of colonies (default 7)
        config: Optional configuration dict[str, Any]

    Returns:
        Configured InhibitoryGate instance
    """
    config = config or {}
    return InhibitoryGate(
        num_colonies=num_colonies,
        hidden_dim=config.get("hidden_dim", 64),
        fast_strength=config.get("fast_strength", 0.6),
        slow_strength=config.get("slow_strength", 0.3),
        disinhibition_strength=config.get("disinhibition_strength", 0.2),
        winner_take_all_threshold=config.get("winner_take_all_threshold", 0.7),
    )


class IdentityGate(nn.Module):
    """Identity gate that passes activations through unchanged.

    Used as fallback when full InhibitoryGate is unavailable.
    Maintains same API but applies no transformation.
    """

    def __init__(self, num_colonies: int = 7):
        super().__init__()
        self.num_colonies = num_colonies

    def forward(
        self,
        activations: torch.Tensor,
        meta_signal: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, InhibitionState]:
        """Pass activations through unchanged.

        Args:
            activations: [B, 7] colony activations
            meta_signal: Ignored (for API compatibility)

        Returns:
            (activations, identity_state) - activations unchanged
        """
        B = activations.shape[0]
        device = activations.device

        # Create identity state (no inhibition applied)
        state = InhibitionState(
            inhibition_levels=torch.zeros(self.num_colonies, device=device),
            suppressed_mask=torch.zeros(self.num_colonies, dtype=torch.bool, device=device),
            disinhibition=torch.zeros(self.num_colonies, device=device),
            winner_idx=int(activations[0].argmax().item()) if B > 0 else 0,
            mean_inhibition=0.0,
            max_inhibition=0.0,
        )

        return activations, state


def create_identity_gate(num_colonies: int = 7) -> IdentityGate:
    """Create identity gate (no-op, for fallback when full gate unavailable).

    Args:
        num_colonies: Number of colonies (default 7)

    Returns:
        IdentityGate instance
    """
    return IdentityGate(num_colonies=num_colonies)


__all__ = [
    "Disinhibition",
    "FastInhibition",
    "IdentityGate",
    "InhibitionState",
    "InhibitionType",
    "InhibitoryGate",
    "SlowInhibition",
    "create_identity_gate",
    "create_inhibitory_gate",
]
