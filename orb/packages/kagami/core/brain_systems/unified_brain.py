"""Unified Brain System - Integrated Neural Mechanisms.

This module integrates all brain-inspired components into a single
coherent system that can be used by the Kagami architecture.

INTEGRATION POINTS:
==================
1. FanoActionRouter: Uses InhibitoryGate for colony competition
2. OrganismRSSM: Uses FeedbackProjection for recurrence
3. EFE Calculator: Uses NeuromodulatorSystem for weight modulation
4. ParallelExecutor: Uses OscillatoryCoordinator for binding
5. Memory: Uses BrainConsolidation for offline learning

December 2025 - Full Brain-Kagami Integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn

from kagami.core.dynamics.oscillatory_coordinator import (
    OscillatorState,
    create_oscillatory_coordinator,
)
from kagami.core.neuromodulation import (
    NeuromodulatorState,
    create_neuromodulator_system,
)
from kagami.core.unified_agents.inhibitory_gate import (
    InhibitionState,
    create_inhibitory_gate,
)

from .feedback import (
    FeedbackState,
    create_feedback_projection,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class BrainSystemState:
    """Unified state of all brain systems."""

    # Component states
    inhibition: InhibitionState | None = None
    neuromodulation: NeuromodulatorState | None = None
    oscillation: OscillatorState | None = None
    feedback: FeedbackState | None = None

    # Derived metrics
    arousal: float = 0.5
    binding_strength: float = 0.0
    competition_winner: int | None = None

    # Diagnostic
    step_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "arousal": self.arousal,
            "binding_strength": self.binding_strength,
            "competition_winner": self.competition_winner,
            "step_count": self.step_count,
            "neuromodulation": self.neuromodulation.to_dict() if self.neuromodulation else {},
            "is_synchronized": self.oscillation.is_synchronized if self.oscillation else False,
        }


class UnifiedBrainSystem(nn.Module):
    """Unified brain system integrating all neural mechanisms.

    This class provides a single interface to all brain-inspired components:
    - Inhibition: Colony competition and suppression
    - Neuromodulation: State-dependent processing
    - Oscillation: Phase coordination and binding
    - Feedback: Top-down predictions and recurrence

    The system maintains coherent state across all components and
    provides methods for integration with Kagami's core systems.
    """

    def __init__(
        self,
        num_colonies: int = 7,
        state_dim: int = 8,  # E8 code dimension
        hidden_dim: int = 64,
        enable_inhibition: bool = True,
        enable_neuromodulation: bool = True,
        enable_oscillation: bool = True,
        enable_feedback: bool = True,
    ):
        super().__init__()
        self.num_colonies = num_colonies
        self.state_dim = state_dim

        # Component enables
        self.enable_inhibition = enable_inhibition
        self.enable_neuromodulation = enable_neuromodulation
        self.enable_oscillation = enable_oscillation
        self.enable_feedback = enable_feedback

        # Initialize components
        if enable_inhibition:
            self.inhibitory_gate = create_inhibitory_gate(num_colonies)
        else:
            self.inhibitory_gate = None  # type: ignore[assignment]

        if enable_neuromodulation:
            self.neuromodulator = create_neuromodulator_system(
                input_dim=state_dim,
                hidden_dim=hidden_dim,
            )
        else:
            self.neuromodulator = None  # type: ignore[assignment]

        if enable_oscillation:
            self.oscillator = create_oscillatory_coordinator(num_colonies)
        else:
            self.oscillator = None  # type: ignore[assignment]

        if enable_feedback:
            self.feedback_proj = create_feedback_projection(
                input_dim=hidden_dim,
                num_colonies=num_colonies,
            )
        else:
            self.feedback_proj = None  # type: ignore[assignment]

        # Step counter
        self.step_count = 0

        logger.info(
            f"UnifiedBrainSystem initialized: "
            f"inhibition={enable_inhibition}, neuromod={enable_neuromodulation}, "
            f"oscillation={enable_oscillation}, feedback={enable_feedback}"
        )

    def step(
        self,
        colony_activations: torch.Tensor,  # [B, 7] or [7]
        state: torch.Tensor | None = None,  # [B, D] current state
        hidden_states: torch.Tensor | None = None,  # [B, 7, H] RSSM hidden
        reward: float | None = None,
        prediction_error: float | None = None,
    ) -> tuple[torch.Tensor, BrainSystemState]:
        """Run one step of unified brain processing.

        Args:
            colony_activations: Raw colony activation levels
            state: Current E8 state for neuromodulation
            hidden_states: RSSM hidden states for feedback
            reward: Optional reward for dopamine
            prediction_error: Optional surprise for norepinephrine

        Returns:
            processed_activations: Modulated colony activations
            brain_state: Unified brain system state
        """
        self.step_count += 1
        # Note: device available via colony_activations.device if needed

        # Ensure batch dimension
        if colony_activations.dim() == 1:
            colony_activations = colony_activations.unsqueeze(0)

        B = colony_activations.shape[0]
        current = colony_activations

        # Component states
        inhibition_state = None
        neuromod_state = None
        oscillation_state = None
        feedback_state = None

        # 1. Neuromodulation - affects all downstream processing
        if self.neuromodulator is not None and state is not None:
            neuromod_state = self.neuromodulator(
                state,
                reward=torch.tensor([reward]) if reward is not None else None,
                prediction_error=torch.tensor([prediction_error])
                if prediction_error is not None
                else None,
            )

        # 2. Inhibition - colony competition
        if self.inhibitory_gate is not None:
            # Meta signal from neuromodulation (if available)
            meta_signal = None
            if neuromod_state is not None:
                # Use norepinephrine as meta-control (exploration signal)
                meta_signal = neuromod_state.norepinephrine.expand(B, self.num_colonies)

            current, inhibition_state = self.inhibitory_gate(
                current,
                meta_signal=meta_signal,
            )

        # 3. Oscillation - phase coordination
        if self.oscillator is not None:
            oscillation_state = self.oscillator.step(current)

            # Modulate activations by phase coherence
            if oscillation_state.is_synchronized:
                # Bound colonies get boost
                coherence = oscillation_state.coherence_matrix.mean(dim=-1)
                current = current * (1 + coherence.unsqueeze(0) * 0.2)

        # 4. Feedback (if hidden states provided)
        if self.feedback_proj is not None and hidden_states is not None:
            _, feedback_state = self.feedback_proj(hidden_states)

        # Build unified state
        brain_state = BrainSystemState(
            inhibition=inhibition_state,
            neuromodulation=neuromod_state,
            oscillation=oscillation_state,
            feedback=feedback_state,
            arousal=neuromod_state.arousal if neuromod_state else 0.5,
            binding_strength=oscillation_state.binding_strength if oscillation_state else 0.0,
            competition_winner=inhibition_state.winner_idx if inhibition_state else None,
            step_count=self.step_count,
        )

        return current.squeeze(0) if B == 1 else current, brain_state

    def get_efe_weights(self) -> dict[str, float]:
        """Get EFE component weights from neuromodulator state.

        Should be called after step() to get current modulation.
        """
        if self.neuromodulator is None:
            return {"epistemic": 1.0, "pragmatic": 1.0, "safety": 1.0}  # type: ignore[unreachable]

        # Need to run neuromodulator to get weights
        # Return default for now (will be set[Any] by step())
        return {"epistemic": 1.0, "pragmatic": 1.0, "safety": 1.0}

    def apply_feedback(
        self,
        hidden_states: torch.Tensor,  # [B, 7, H]
    ) -> tuple[torch.Tensor, FeedbackState | None]:
        """Apply feedback projection to RSSM hidden states.

        Args:
            hidden_states: Colony hidden states

        Returns:
            refined_states: States after feedback refinement
            feedback_state: Feedback diagnostic state
        """
        if self.feedback_proj is None:
            return hidden_states, None  # type: ignore[unreachable]

        return self.feedback_proj(hidden_states)  # type: ignore[no-any-return]

    def reset_oscillators(self) -> None:
        """Reset oscillator phases (e.g., at episode start)."""
        if self.oscillator is not None:
            self.oscillator.reset_phases(random=True)

    def get_stats(self) -> dict[str, Any]:
        """Get brain system statistics."""
        stats = {
            "step_count": self.step_count,
            "inhibition_enabled": self.inhibitory_gate is not None,
            "neuromodulation_enabled": self.neuromodulator is not None,
            "oscillation_enabled": self.oscillator is not None,
            "feedback_enabled": self.feedback_proj is not None,
        }

        if self.inhibitory_gate is not None:
            stats["inhibition_stats"] = self.inhibitory_gate.get_inhibition_stats()  # type: ignore[assignment]

        return stats


def create_unified_brain_system(
    num_colonies: int = 7,
    state_dim: int = 8,
    hidden_dim: int = 64,
    **kwargs: Any,
) -> UnifiedBrainSystem:
    """Factory function for unified brain system."""
    return UnifiedBrainSystem(
        num_colonies=num_colonies,
        state_dim=state_dim,
        hidden_dim=hidden_dim,
        **kwargs,
    )


# Global instance
_brain_system: UnifiedBrainSystem | None = None


def get_brain_system() -> UnifiedBrainSystem:
    """Get or create global brain system instance."""
    global _brain_system
    if _brain_system is None:
        _brain_system = create_unified_brain_system()
    return _brain_system


__all__ = [
    "BrainSystemState",
    "UnifiedBrainSystem",
    "create_unified_brain_system",
    "get_brain_system",
]
