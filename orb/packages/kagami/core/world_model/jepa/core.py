"""JEPA Core - Joint Embedding Predictive Architecture.

Type stubs for world model interface used in TYPE_CHECKING contexts.

Created: December 26, 2025 (stub for type checking)
"""

from __future__ import annotations

from typing import Any, Protocol

import torch


class WorldModel(Protocol):
    """Protocol defining the world model interface.

    Used for type checking in optional_deps.py and other modules
    that need to reference world model types without hard dependencies.
    """

    def encode(self, observation: torch.Tensor) -> torch.Tensor:
        """Encode observation to latent state."""
        ...

    def decode(self, latent: torch.Tensor) -> torch.Tensor:
        """Decode latent state to observation."""
        ...

    def predict(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Predict next state given current state and action."""
        ...

    def forward(self, x: torch.Tensor) -> Any:
        """Forward pass."""
        ...


__all__ = ["WorldModel"]
