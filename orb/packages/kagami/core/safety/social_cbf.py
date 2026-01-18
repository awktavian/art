"""Social CBF — Control Barrier Functions for Social Safety.

This module extends the CBF framework with social safety constraints,
ensuring Kagami doesn't cause cognitive or social harm to other agents.

MATHEMATICAL FOUNDATION:
========================
Standard CBF:
    h(x) ≥ 0  ∀ reachable states

Extended with social safety:
    h(x) = min(h_physical(x), h_social(x))

Where h_social is a barrier function over social states:
    h_social(x) = min(
        h_manipulation(x),   # Don't exploit knowledge of agent
        h_confusion(x),      # Don't confuse the agent
        h_harm(x),           # Don't cause cognitive/emotional harm
        h_alignment(x),      # Stay aligned with stated goals
    )

SOCIAL SAFETY DIMENSIONS:
=========================
1. Manipulation Safety (h_manipulation):
   - Using Theory of Mind to exploit vulnerabilities
   - Saying what agent wants to hear vs truth
   - Creating false urgency/fear

2. Confusion Safety (h_confusion):
   - Actions that would leave agent confused
   - Contradicting previous statements
   - Using jargon beyond agent's knowledge

3. Harm Safety (h_harm):
   - Causing emotional distress
   - Overwhelming with information
   - Gaslighting or denying reality

4. Alignment Safety (h_alignment):
   - Matching stated vs actual intent
   - Honoring commitments
   - Transparent about capabilities/limitations

INTEGRATION:
============
Integrates with existing CBF via:
    from kagami.core.safety.social_cbf import SocialCBF

    social_cbf = SocialCBF(symbiote_module)
    h_social = social_cbf.compute_barrier(action, context)

    # Combined with physical CBF
    h = min(h_physical, h_social)

Created: December 21, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# =============================================================================
# SOCIAL SAFETY TYPES
# =============================================================================


class SocialViolationType(Enum):
    """Types of social safety violations."""

    MANIPULATION = "manipulation"
    CONFUSION = "confusion"
    HARM = "harm"
    MISALIGNMENT = "misalignment"
    DECEPTION = "deception"
    COERCION = "coercion"


@dataclass
class SocialSafetyCheck:
    """Result of a social safety check.

    Similar to SafetyCheckResult but for social dimensions.
    """

    safe: bool
    h_social: float  # Social barrier value

    # Per-dimension values
    h_manipulation: float = 1.0
    h_confusion: float = 1.0
    h_harm: float = 1.0
    h_alignment: float = 1.0

    # Violation details
    violation_type: SocialViolationType | None = None
    violation_reason: str | None = None

    # Confidence
    confidence: float = 0.5

    @property
    def zone(self) -> str:
        """Get safety zone color."""
        if self.h_social < 0:
            return "RED"
        elif self.h_social < 0.5:
            return "YELLOW"
        else:
            return "GREEN"


# =============================================================================
# SOCIAL CBF
# =============================================================================


class SocialCBF(nn.Module):
    """Social Control Barrier Function.

    Computes h_social(x) ensuring social safety constraints are satisfied.

    ARCHITECTURE:
    =============
    1. Feature extraction from action + context
    2. Per-agent barrier computation
    3. Aggregation across agents (min = conservative)
    4. Gradient for CBF-QP optimization
    """

    def __init__(
        self,
        symbiote_module: Any | None = None,  # SymbioteModule
        state_dim: int = 64,
        e8_dim: int = 8,
        hidden_dim: int = 128,
    ) -> None:
        super().__init__()

        self.symbiote = symbiote_module
        self.state_dim = state_dim
        self.e8_dim = e8_dim

        # Barrier networks for each dimension
        self.manipulation_net = self._create_barrier_net(hidden_dim)
        self.confusion_net = self._create_barrier_net(hidden_dim)
        self.harm_net = self._create_barrier_net(hidden_dim)
        self.alignment_net = self._create_barrier_net(hidden_dim)

        # Weights for combining dimensions (learnable)
        self.dimension_weights = nn.Parameter(torch.ones(4) / 4)

        # Class-K function parameters (for CBF dynamics)
        self.alpha = nn.Parameter(torch.tensor(1.0))

    def _create_barrier_net(self, hidden_dim: int) -> nn.Module:
        """Create a barrier network for one safety dimension.

        Output is h(x) ∈ (-∞, +∞), where:
        - h > 0: safe
        - h = 0: boundary
        - h < 0: unsafe
        """
        return nn.Sequential(
            nn.Linear(self.e8_dim * 2 + self.state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
            # No activation - barrier can be any real value
        )

    def set_symbiote(self, symbiote: Any) -> None:
        """Set symbiote module reference."""
        self.symbiote = symbiote

    def compute_manipulation_barrier(
        self,
        action_e8: torch.Tensor,
        agent_e8: torch.Tensor,
        features: torch.Tensor,
    ) -> torch.Tensor:
        """Compute manipulation safety barrier.

        DETECTS:
        - Using knowledge of agent vulnerabilities
        - Saying what agent wants to hear
        - Creating artificial urgency

        Args:
            action_e8: [B, 8] our action embedding
            agent_e8: [B, 8] agent model embedding
            features: [B, state_dim] action features

        Returns:
            [B] barrier values (positive = safe)
        """
        combined = torch.cat([action_e8, agent_e8, features], dim=-1)
        h = self.manipulation_net(combined).squeeze(-1)
        return cast(torch.Tensor, h)

    def compute_confusion_barrier(
        self,
        action_e8: torch.Tensor,
        agent_e8: torch.Tensor,
        features: torch.Tensor,
    ) -> torch.Tensor:
        """Compute confusion safety barrier.

        DETECTS:
        - Actions that would confuse agent
        - Jargon beyond agent's knowledge
        - Contradicting previous statements
        """
        combined = torch.cat([action_e8, agent_e8, features], dim=-1)
        h = self.confusion_net(combined).squeeze(-1)
        return cast(torch.Tensor, h)

    def compute_harm_barrier(
        self,
        action_e8: torch.Tensor,
        agent_e8: torch.Tensor,
        features: torch.Tensor,
    ) -> torch.Tensor:
        """Compute harm safety barrier.

        DETECTS:
        - Emotional distress potential
        - Information overload
        - Gaslighting patterns
        """
        combined = torch.cat([action_e8, agent_e8, features], dim=-1)
        h = self.harm_net(combined).squeeze(-1)
        return cast(torch.Tensor, h)

    def compute_alignment_barrier(
        self,
        action_e8: torch.Tensor,
        agent_e8: torch.Tensor,
        features: torch.Tensor,
    ) -> torch.Tensor:
        """Compute alignment safety barrier.

        DETECTS:
        - Stated vs actual intent mismatch
        - Broken commitments
        - Hidden limitations
        """
        combined = torch.cat([action_e8, agent_e8, features], dim=-1)
        h = self.alignment_net(combined).squeeze(-1)
        return cast(torch.Tensor, h)

    def compute_barrier(
        self,
        action_e8: torch.Tensor,
        features: torch.Tensor,
        agent_ids: list[str] | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute full social barrier function.

        Args:
            action_e8: [B, 8] our action in E8 space
            features: [B, state_dim] action features
            agent_ids: Optional specific agents to check

        Returns:
            Dict with barrier values for each dimension and combined h_social
        """
        if self.symbiote is None:
            # No symbiote = cannot evaluate social safety
            # Return safe values (h = 1.0)
            B = action_e8.shape[0]
            return {
                "h_manipulation": torch.ones(B, device=action_e8.device),
                "h_confusion": torch.ones(B, device=action_e8.device),
                "h_harm": torch.ones(B, device=action_e8.device),
                "h_alignment": torch.ones(B, device=action_e8.device),
                "h_social": torch.ones(B, device=action_e8.device),
            }

        # Get agent embeddings
        if agent_ids is None:
            agent_ids = list(self.symbiote._agent_states.keys())

        if not agent_ids:
            B = action_e8.shape[0]
            return {
                "h_manipulation": torch.ones(B, device=action_e8.device),
                "h_confusion": torch.ones(B, device=action_e8.device),
                "h_harm": torch.ones(B, device=action_e8.device),
                "h_alignment": torch.ones(B, device=action_e8.device),
                "h_social": torch.ones(B, device=action_e8.device),
            }

        # Compute barriers for each agent
        all_h_manip = []
        all_h_conf = []
        all_h_harm = []
        all_h_align = []

        for agent_id in agent_ids:
            state = self.symbiote._agent_states.get(agent_id)
            if state is None or state.e8_embedding is None:
                continue

            agent_e8 = state.e8_embedding.unsqueeze(0)
            if agent_e8.shape[0] < action_e8.shape[0]:
                agent_e8 = agent_e8.expand(action_e8.shape[0], -1)

            h_manip = self.compute_manipulation_barrier(action_e8, agent_e8, features)
            h_conf = self.compute_confusion_barrier(action_e8, agent_e8, features)
            h_harm = self.compute_harm_barrier(action_e8, agent_e8, features)
            h_align = self.compute_alignment_barrier(action_e8, agent_e8, features)

            all_h_manip.append(h_manip)
            all_h_conf.append(h_conf)
            all_h_harm.append(h_harm)
            all_h_align.append(h_align)

        if not all_h_manip:
            B = action_e8.shape[0]
            return {
                "h_manipulation": torch.ones(B, device=action_e8.device),
                "h_confusion": torch.ones(B, device=action_e8.device),
                "h_harm": torch.ones(B, device=action_e8.device),
                "h_alignment": torch.ones(B, device=action_e8.device),
                "h_social": torch.ones(B, device=action_e8.device),
            }

        # Aggregate across agents (min = conservative)
        h_manip = torch.stack(all_h_manip).min(dim=0).values
        h_conf = torch.stack(all_h_conf).min(dim=0).values
        h_harm = torch.stack(all_h_harm).min(dim=0).values
        h_align = torch.stack(all_h_align).min(dim=0).values

        # Combined social barrier (weighted sum or min)
        # Using min for maximum safety
        h_social = torch.stack([h_manip, h_conf, h_harm, h_align]).min(dim=0).values

        return {
            "h_manipulation": h_manip,
            "h_confusion": h_conf,
            "h_harm": h_harm,
            "h_alignment": h_align,
            "h_social": h_social,
        }

    def check_safety(
        self,
        action_e8: torch.Tensor,
        features: torch.Tensor,
        agent_ids: list[str] | None = None,
    ) -> SocialSafetyCheck:
        """Perform full social safety check.

        Returns:
            SocialSafetyCheck with all metrics
        """
        barriers = self.compute_barrier(action_e8, features, agent_ids)

        h_social = barriers["h_social"].mean().item()

        # Determine violation type if unsafe
        violation_type = None
        violation_reason = None

        if h_social < 0:
            # Find which dimension is most violated
            dims = {
                SocialViolationType.MANIPULATION: barriers["h_manipulation"].mean().item(),
                SocialViolationType.CONFUSION: barriers["h_confusion"].mean().item(),
                SocialViolationType.HARM: barriers["h_harm"].mean().item(),
                SocialViolationType.MISALIGNMENT: barriers["h_alignment"].mean().item(),
            }

            violation_type = min(dims, key=lambda k: dims[k])

            if violation_type == SocialViolationType.MANIPULATION:
                violation_reason = "Action may exploit knowledge of agent"
            elif violation_type == SocialViolationType.CONFUSION:
                violation_reason = "Action may confuse the agent"
            elif violation_type == SocialViolationType.HARM:
                violation_reason = "Action may cause cognitive/emotional harm"
            elif violation_type == SocialViolationType.MISALIGNMENT:
                violation_reason = "Action may be misaligned with stated intent"

        return SocialSafetyCheck(
            safe=h_social >= 0,
            h_social=h_social,
            h_manipulation=barriers["h_manipulation"].mean().item(),
            h_confusion=barriers["h_confusion"].mean().item(),
            h_harm=barriers["h_harm"].mean().item(),
            h_alignment=barriers["h_alignment"].mean().item(),
            violation_type=violation_type,
            violation_reason=violation_reason,
            confidence=self._compute_confidence(barriers),
        )

    def _compute_confidence(self, barriers: dict[str, torch.Tensor]) -> float:
        """Compute confidence from model uncertainty.

        HARDENED (Dec 22, 2025): Real confidence computation.
        """
        # Use barrier value variance as uncertainty proxy
        all_values = torch.cat([b.flatten() for b in barriers.values()])
        variance = float(all_values.var().item())
        # High variance = low confidence, low variance = high confidence
        # Sigmoid transform to [0.5, 1.0] range
        confidence = 0.5 + 0.5 * (1.0 / (1.0 + variance))
        return confidence

    def compute_gradient(
        self,
        action_e8: torch.Tensor,
        features: torch.Tensor,
        agent_ids: list[str] | None = None,
    ) -> torch.Tensor:
        """Compute gradient of social barrier for CBF-QP.

        ∇h_social is used in the CBF constraint:
            ∇h(x) · f(x, u) + α(h(x)) ≥ 0

        Args:
            action_e8: [B, 8] action embedding (requires_grad=True)
            features: [B, state_dim] features
            agent_ids: Optional agent filter

        Returns:
            [B, 8] gradient of h_social w.r.t. action_e8
        """
        action_e8 = action_e8.requires_grad_(True)

        barriers = self.compute_barrier(action_e8, features, agent_ids)
        h_social = barriers["h_social"]

        # Compute gradient
        grad = torch.autograd.grad(
            h_social.sum(),
            action_e8,
            create_graph=True,
        )[0]

        return grad

    def forward(
        self,
        action_e8: torch.Tensor,
        features: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Forward pass for training.

        Computes all barrier values.
        """
        return self.compute_barrier(action_e8, features)


# =============================================================================
# INTEGRATION WITH OPTIMAL CBF
# =============================================================================


def integrate_social_cbf(
    optimal_cbf: Any,  # OptimalCBF
    social_cbf: SocialCBF,
    combine_method: str = "min",
) -> None:
    """Integrate SocialCBF with OptimalCBF.

    Patches the OptimalCBF to include social safety in its barrier computation.

    Args:
        optimal_cbf: OptimalCBF instance
        social_cbf: SocialCBF instance
        combine_method: How to combine barriers ("min" or "weighted")
    """
    original_forward = optimal_cbf.forward

    def patched_forward(x: torch.Tensor, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        # Call original
        result = original_forward(x, *args, **kwargs)

        # Extract action and features from input
        # (This depends on OptimalCBF's input format)
        if x.shape[-1] >= social_cbf.e8_dim + social_cbf.state_dim:
            action_e8 = x[..., : social_cbf.e8_dim]
            features = x[..., social_cbf.e8_dim : social_cbf.e8_dim + social_cbf.state_dim]

            # Compute social barrier
            social_barriers = social_cbf.compute_barrier(action_e8, features)
            h_social = social_barriers["h_social"]

            # Combine with physical barrier
            if isinstance(result, tuple):
                h_physical = result[0]
                if combine_method == "min":
                    h_combined = torch.min(h_physical, h_social)
                else:
                    # Weighted average
                    h_combined = 0.7 * h_physical + 0.3 * h_social
                result = (h_combined, *result[1:])

        return cast(tuple[Any, ...], result)

    optimal_cbf.forward = patched_forward
    logger.info("✅ SocialCBF integrated with OptimalCBF")


# =============================================================================
# FACTORY
# =============================================================================


def create_social_cbf(
    symbiote_module: Any | None = None,
    **kwargs: Any,
) -> SocialCBF:
    """Create a SocialCBF instance.

    Args:
        symbiote_module: Optional SymbioteModule for agent access
        **kwargs: Additional configuration

    Returns:
        Configured SocialCBF
    """
    return SocialCBF(
        symbiote_module=symbiote_module,
        **kwargs,
    )


__all__ = [
    "SocialCBF",
    "SocialSafetyCheck",
    "SocialViolationType",
    "create_social_cbf",
    "integrate_social_cbf",
]
