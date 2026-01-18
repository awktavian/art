"""RSSM State Definitions.

CREATED: December 21, 2025
PURPOSE: Break circular import between rssm_core and rssm_components by
         providing a shared state definition module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch


@dataclass
class ColonyState:
    """State representation for a colony in the RSSM.

    Encapsulates all the state information for a single colony,
    including deterministic and stochastic components.
    """

    # Core state tensors
    hidden: torch.Tensor  # Hidden deterministic state
    stochastic: torch.Tensor  # Stochastic latent state

    # Colony-specific information
    colony_id: int  # Which colony (0-6 for e₁-e₇)
    timestep: int = 0  # Current timestep

    # Attention and communication
    attention_weights: torch.Tensor | None = None
    messages: torch.Tensor | None = None

    # Hofstadter loop state
    loop_state: torch.Tensor | None = None
    fixed_point: torch.Tensor | None = None

    # Metadata
    active: bool = True  # Whether this colony is active
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        """Validate state consistency."""
        if self.colony_id < 0 or self.colony_id >= 7:
            raise ValueError(f"colony_id must be in [0, 6], got {self.colony_id}")

        if self.hidden.dim() < 2:
            raise ValueError("hidden state must be at least 2D (batch, features)")

        if self.stochastic.dim() < 2:
            raise ValueError("stochastic state must be at least 2D (batch, features)")

        batch_size = self.hidden.size(0)
        if self.stochastic.size(0) != batch_size:
            raise ValueError("hidden and stochastic states must have same batch size")

    def clone(self) -> ColonyState:
        """Create a deep copy of this state."""
        return ColonyState(
            hidden=self.hidden.clone(),
            stochastic=self.stochastic.clone(),
            colony_id=self.colony_id,
            timestep=self.timestep,
            attention_weights=self.attention_weights.clone()
            if self.attention_weights is not None
            else None,
            messages=self.messages.clone() if self.messages is not None else None,
            loop_state=self.loop_state.clone() if self.loop_state is not None else None,
            fixed_point=self.fixed_point.clone() if self.fixed_point is not None else None,
            active=self.active,
            metadata=self.metadata.copy(),
        )

    def detach(self) -> ColonyState:
        """Detach all tensors from computation graph."""
        return ColonyState(
            hidden=self.hidden.detach(),
            stochastic=self.stochastic.detach(),
            colony_id=self.colony_id,
            timestep=self.timestep,
            attention_weights=self.attention_weights.detach()
            if self.attention_weights is not None
            else None,
            messages=self.messages.detach() if self.messages is not None else None,
            loop_state=self.loop_state.detach() if self.loop_state is not None else None,
            fixed_point=self.fixed_point.detach() if self.fixed_point is not None else None,
            active=self.active,
            metadata=self.metadata.copy(),
        )

    def to(self, device: torch.device | str) -> ColonyState:
        """Move state to device."""
        return ColonyState(
            hidden=self.hidden.to(device),
            stochastic=self.stochastic.to(device),
            colony_id=self.colony_id,
            timestep=self.timestep,
            attention_weights=self.attention_weights.to(device)
            if self.attention_weights is not None
            else None,
            messages=self.messages.to(device) if self.messages is not None else None,
            loop_state=self.loop_state.to(device) if self.loop_state is not None else None,
            fixed_point=self.fixed_point.to(device) if self.fixed_point is not None else None,
            active=self.active,
            metadata=self.metadata.copy(),
        )


def create_colony_states(
    batch_size: int,
    num_colonies: int = 7,
    device: str = "cpu",
    *,
    hidden_dim: int | None = None,
    stochastic_dim: int | None = None,
) -> list[ColonyState]:
    """Create initial colony states.

    Args:
        batch_size: Batch dimension
        num_colonies: Number of colonies (default 7)
        device: Device to create tensors on
        hidden_dim: Hidden state dimension (default: from global config)
        stochastic_dim: Stochastic state dimension (default: from global config)

    Returns:
        List of initialized ColonyState instances
    """
    from kagami.core.config.unified_config import get_kagami_config

    # Use provided dims or fall back to global config
    if hidden_dim is None or stochastic_dim is None:
        config = get_kagami_config().world_model.rssm
        hidden_dim = hidden_dim or config.hidden_dim
        stochastic_dim = stochastic_dim or config.stochastic_dim

    states = []
    for i in range(num_colonies):
        states.append(
            ColonyState(
                hidden=torch.zeros(batch_size, hidden_dim, device=device),
                stochastic=torch.zeros(batch_size, stochastic_dim, device=device),
                colony_id=i,
            )
        )
    return states


__all__ = ["ColonyState", "create_colony_states"]
