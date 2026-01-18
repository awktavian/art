from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import torch


@dataclass
class SemanticState:
    """Semantic state representation (embedding + metadata)."""

    embedding: list[float] | np.ndarray | torch.Tensor = field(default_factory=list[Any])
    timestamp: float = 0.0
    context_hash: str = ""
    geometric_coords: Any | None = None  # For H14 x S7 coordinates
    e8_index: int | None = None  # Crystallized E8 lattice index (0-239)
    lattice_stress: float = 0.0  # Distance from E8 root (0.0 = crystal, >0.5 = amorphous)

    def __post_init__(self) -> None:
        """Ensure embedding is numpy array for consistency."""
        if isinstance(self.embedding, list):
            # Use float64 first to avoid overflow, then convert to float32
            arr = np.array(self.embedding, dtype=np.float64)
            # Clip to float32 range to avoid overflow
            arr = np.clip(arr, -3.4e38, 3.4e38)
            self.embedding = arr.astype(np.float32)
        elif hasattr(self.embedding, "numpy"):  # torch.Tensor
            self.embedding = self.embedding.detach().cpu().numpy()  # type: ignore[union-attr]
        # np.ndarray passes through unchanged

    def to_numpy(self) -> np.ndarray:
        """Convert embedding to numpy array.

        Returns:
            Embedding as numpy array.
        """
        if isinstance(self.embedding, np.ndarray):
            return self.embedding
        elif hasattr(self.embedding, "numpy"):  # torch.Tensor
            return self.embedding.detach().cpu().numpy()  # type: ignore[union-attr]
        else:
            return np.array(self.embedding, dtype=np.float32)


@dataclass
class LatentState(SemanticState):
    """Latent state representation (alias for SemanticState in JEPA context)."""

    @property
    def is_latent(self) -> bool:
        """Marker for clarity in mixed Semantic/Latent code paths."""
        return True


@dataclass
class LatentPrediction:
    """Prediction of a future latent state in JEPA context.

    Note: Distinct from kagami.core.predictive.types.Prediction (generic).
    This type is specialized for latent space predictions.
    """

    predicted_state: LatentState
    confidence: float
    horizon: int
    uncertainty: float = 0.0
    learned_threat: float = 0.0


# Backward compatibility alias
Prediction = LatentPrediction
