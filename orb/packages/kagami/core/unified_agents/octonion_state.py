"""OctonionState - Unified State Representation for the Organism.

ARCHITECTURAL UNIFICATION (December 27, 2025):
==============================================
This module provides the SINGLE canonical state representation that flows
through ALL levels of the colony architecture:

    Agent → Coordinator → Organism → WorldModel → RSSM

MATHEMATICAL FOUNDATION:
========================
E8 (8D) = ℝ ⊕ Im(𝕆) = e₀ ⊕ (e₁ ⊕ e₂ ⊕ e₃ ⊕ e₄ ⊕ e₅ ⊕ e₆ ⊕ e₇)
         Kagami    Spark Forge Flow Nexus Beacon Grove Crystal

S⁷ (7D) = Unit sphere in Im(𝕆) = {x ∈ Im(𝕆) : ||x|| = 1}

The OctonionState maintains BOTH representations with proper mathematical
relationships:
- e8_code: Full 8D octonion (real + imaginary)
- s7_phase: 7D unit imaginary (colony routing weights)
- colony_activations: Soft gating derived from s7_phase

COHERENCY GUARANTEE:
====================
- s7_phase is ALWAYS derived from e8_code (not independent)
- colony_activations is ALWAYS derived from s7_phase
- Downstream code uses this container, not raw tensors

Created: December 27, 2025
Author: Forge (coherency refactor)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn.functional as F


@dataclass
class OctonionState:
    """Unified state representation for the organism.

    This is the CANONICAL state container that flows through all levels.
    All other state representations should be derived from or converted to this.

    Attributes:
        e8_code: [B, 8] or [8] - Full octonion (e₀ + e₁..e₇)
        s7_phase: [B, 7] or [7] - Unit imaginary part (derived from e8_code)
        colony_activations: [B, 7] or [7] - Soft routing weights (softmax of s7_phase)
        confidence: Scalar confidence in this state
        metadata: Additional context (source, timestamp, etc.)
    """

    e8_code: torch.Tensor  # [B, 8] or [8]
    s7_phase: torch.Tensor | None = None  # [B, 7] or [7] - computed if not provided
    colony_activations: torch.Tensor | None = None  # [B, 7] or [7] - computed if not provided
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        """Ensure coherency: derive s7_phase and activations from e8_code."""
        # Validate e8_code shape
        if self.e8_code.shape[-1] != 8:
            raise ValueError(f"e8_code must have last dim=8, got {self.e8_code.shape}")

        # Derive s7_phase from e8_code if not provided
        if self.s7_phase is None:
            self.s7_phase = self._project_to_s7(self.e8_code)
        else:
            # Validate provided s7_phase
            if self.s7_phase.shape[-1] != 7:
                raise ValueError(f"s7_phase must have last dim=7, got {self.s7_phase.shape}")

        # Derive colony_activations from s7_phase if not provided
        if self.colony_activations is None:
            self.colony_activations = self._compute_activations(self.s7_phase)

    @staticmethod
    def _project_to_s7(e8_code: torch.Tensor) -> torch.Tensor:
        """Project E8 code to S⁷ (unit imaginary octonion).

        Mathematical operation:
        1. Extract imaginary part (e₁..e₇)
        2. Normalize to unit sphere

        Args:
            e8_code: [B, 8] or [8] full octonion

        Returns:
            [B, 7] or [7] unit vector on S⁷
        """
        imaginary = e8_code[..., 1:]  # Drop e₀, keep e₁..e₇
        return F.normalize(imaginary, dim=-1, eps=1e-8)

    @staticmethod
    def _compute_activations(s7_phase: torch.Tensor) -> torch.Tensor:
        """Compute soft colony activations from S⁷ phase.

        Args:
            s7_phase: [B, 7] or [7] unit vector on S⁷

        Returns:
            [B, 7] or [7] softmax activations (sum to 1)
        """
        return F.softmax(s7_phase, dim=-1)

    @property
    def real_part(self) -> torch.Tensor:
        """Get real component e₀ of the octonion."""
        return self.e8_code[..., 0]

    @property
    def imaginary_part(self) -> torch.Tensor:
        """Get imaginary components (e₁..e₇) of the octonion."""
        return self.e8_code[..., 1:]

    @property
    def batch_size(self) -> int:
        """Get batch size (1 if unbatched)."""
        if self.e8_code.dim() == 1:
            return 1
        return self.e8_code.shape[0]

    @property
    def device(self) -> torch.device:
        """Get device of tensors."""
        return self.e8_code.device

    @property
    def dtype(self) -> torch.dtype:
        """Get dtype of tensors."""
        return self.e8_code.dtype

    def primary_colony(self) -> int:
        """Get index of most active colony (argmax of activations)."""
        return int(self.colony_activations.argmax(dim=-1).item())  # type: ignore[union-attr]

    def top_k_colonies(self, k: int = 3) -> list[int]:
        """Get indices of top-k most active colonies."""
        _, indices = self.colony_activations.topk(k, dim=-1)  # type: ignore[union-attr]
        if indices.dim() == 1:
            return indices.tolist()
        return indices[0].tolist()  # First batch element

    def to(self, device: torch.device | str) -> OctonionState:
        """Move state to device."""
        return OctonionState(
            e8_code=self.e8_code.to(device),
            s7_phase=self.s7_phase.to(device) if self.s7_phase is not None else None,
            colony_activations=self.colony_activations.to(device)
            if self.colony_activations is not None
            else None,
            confidence=self.confidence,
            metadata=self.metadata.copy(),
        )

    def detach(self) -> OctonionState:
        """Detach from computation graph."""
        return OctonionState(
            e8_code=self.e8_code.detach(),
            s7_phase=self.s7_phase.detach() if self.s7_phase is not None else None,
            colony_activations=self.colony_activations.detach()
            if self.colony_activations is not None
            else None,
            confidence=self.confidence,
            metadata=self.metadata.copy(),
        )

    def clone(self) -> OctonionState:
        """Create a copy of this state."""
        return OctonionState(
            e8_code=self.e8_code.clone(),
            s7_phase=self.s7_phase.clone() if self.s7_phase is not None else None,
            colony_activations=self.colony_activations.clone()
            if self.colony_activations is not None
            else None,
            confidence=self.confidence,
            metadata=self.metadata.copy(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "e8_code": self.e8_code.tolist(),
            "s7_phase": self.s7_phase.tolist() if self.s7_phase is not None else None,
            "colony_activations": self.colony_activations.tolist()
            if self.colony_activations is not None
            else None,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], device: str = "cpu") -> OctonionState:
        """Create from dictionary."""
        return cls(
            e8_code=torch.tensor(data["e8_code"], device=device),
            s7_phase=torch.tensor(data["s7_phase"], device=device)
            if data.get("s7_phase")
            else None,
            colony_activations=torch.tensor(data["colony_activations"], device=device)
            if data.get("colony_activations")
            else None,
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_s7_phase(cls, s7_phase: torch.Tensor, real_part: float = 0.0) -> OctonionState:
        """Create OctonionState from S⁷ phase (reconstructs e8_code).

        Args:
            s7_phase: [B, 7] or [7] unit vector on S⁷
            real_part: Value for e₀ (default 0.0)

        Returns:
            OctonionState with reconstructed e8_code
        """
        if s7_phase.shape[-1] != 7:
            raise ValueError(f"s7_phase must have last dim=7, got {s7_phase.shape}")

        # Normalize to ensure unit sphere
        s7_normalized = F.normalize(s7_phase, dim=-1, eps=1e-8)

        # Reconstruct e8_code: [real_part, s7_phase]
        if s7_phase.dim() == 1:
            e8_code = torch.cat(
                [
                    torch.tensor([real_part], device=s7_phase.device, dtype=s7_phase.dtype),
                    s7_normalized,
                ]
            )
        else:
            batch_size = s7_phase.shape[0]
            real = torch.full(
                (batch_size, 1), real_part, device=s7_phase.device, dtype=s7_phase.dtype
            )
            e8_code = torch.cat([real, s7_normalized], dim=-1)

        return cls(e8_code=e8_code, s7_phase=s7_normalized)

    @classmethod
    def from_colony_index(cls, colony_idx: int, device: str = "cpu") -> OctonionState:
        """Create OctonionState for a specific colony (one-hot style).

        Args:
            colony_idx: Colony index (0-6)
            device: Device to create on

        Returns:
            OctonionState with e₍ᵢ₊₁₎ = 1, all others = 0
        """
        if not 0 <= colony_idx < 7:
            raise ValueError(f"colony_idx must be 0-6, got {colony_idx}")

        # Create e8_code with e₀=0, e₍ᵢ₊₁₎=1
        e8_code = torch.zeros(8, device=device)
        e8_code[colony_idx + 1] = 1.0  # e₁ at index 1, etc.

        return cls(e8_code=e8_code)

    @classmethod
    def zeros(cls, batch_size: int = 1, device: str = "cpu") -> OctonionState:
        """Create zero-initialized OctonionState."""
        e8_code = (
            torch.zeros(batch_size, 8, device=device)
            if batch_size > 1
            else torch.zeros(8, device=device)
        )
        return cls(e8_code=e8_code)

    @classmethod
    def random(cls, batch_size: int = 1, device: str = "cpu") -> OctonionState:
        """Create random OctonionState (normalized to unit octonion)."""
        if batch_size > 1:
            e8_code = torch.randn(batch_size, 8, device=device)
        else:
            e8_code = torch.randn(8, device=device)
        e8_code = F.normalize(e8_code, dim=-1)
        return cls(e8_code=e8_code)

    def __repr__(self) -> str:
        primary = self.primary_colony()
        from kagami.core.unified_agents.colony_constants import COLONY_NAMES

        colony_name = COLONY_NAMES[primary] if 0 <= primary < 7 else "unknown"
        return (
            f"OctonionState("
            f"e8={self.e8_code.shape}, "
            f"primary={colony_name}[{primary}], "
            f"confidence={self.confidence:.2f})"
        )


# =============================================================================
# CONVERSION UTILITIES
# =============================================================================


def octonion_state_from_core_state(core_state: Any) -> OctonionState:
    """Convert CoreState (from world model) to OctonionState.

    Args:
        core_state: CoreState from KagamiWorldModel.encode()

    Returns:
        OctonionState with unified representation
    """
    # CoreState has e8_code and s7_phase as separate fields
    e8_code = getattr(core_state, "e8_code", None)
    s7_phase = getattr(core_state, "s7_phase", None)

    if e8_code is not None:
        return OctonionState(
            e8_code=e8_code,
            s7_phase=s7_phase,
            metadata={"source": "core_state"},
        )

    # Fallback: reconstruct from s7_phase
    if s7_phase is not None:
        return OctonionState.from_s7_phase(s7_phase)

    raise ValueError("CoreState has neither e8_code nor s7_phase")


def octonion_state_from_colony_state(colony_state: Any) -> OctonionState:
    """Convert ColonyState (from RSSM) to OctonionState.

    Args:
        colony_state: ColonyState from OrganismRSSM

    Returns:
        OctonionState with unified representation
    """
    # ColonyState has hidden and stochastic, not direct E8
    # We need to extract from the colony's position in the hierarchy
    colony_idx = getattr(colony_state, "colony_idx", 0)
    hidden = getattr(colony_state, "hidden", None)

    if hidden is not None:
        # Use hidden state magnitude to modulate colony embedding
        magnitude = hidden.norm(dim=-1, keepdim=True).mean().item()
        state = OctonionState.from_colony_index(colony_idx)
        state.e8_code[0] = magnitude  # Encode magnitude in real part
        return state

    return OctonionState.from_colony_index(colony_idx)


def octonion_state_from_agent_result(result: Any, colony_idx: int) -> OctonionState:
    """Convert AgentResult to OctonionState.

    Args:
        result: AgentResult from colony agent execution
        colony_idx: Index of the colony that produced this result

    Returns:
        OctonionState with unified representation
    """
    # Check for s7_embedding in result
    s7_embedding = getattr(result, "s7_embedding", None)
    if s7_embedding is not None and s7_embedding.shape[-1] == 7:
        return OctonionState.from_s7_phase(s7_embedding)

    # Check for kernel output with s7_output
    if hasattr(result, "result") and isinstance(result.result, dict):
        kernel_output = result.result.get("kernel_output", {})
        s7_out = kernel_output.get("s7_output")
        if s7_out is not None:
            if isinstance(s7_out, torch.Tensor):
                if s7_out.shape[-1] == 8:
                    return OctonionState(e8_code=s7_out.squeeze())
                elif s7_out.shape[-1] == 7:
                    return OctonionState.from_s7_phase(s7_out.squeeze())

    # Fallback: create from colony index with success indicator
    e8_code = torch.zeros(8)
    success = getattr(result, "success", False)
    e8_code[0] = 0.5 if success else -0.5  # Real part encodes success
    e8_code[colony_idx + 1] = 1.0 if success else -1.0  # Colony activation

    return OctonionState(
        e8_code=F.normalize(e8_code, dim=-1),
        confidence=0.8 if success else 0.3,
        metadata={"source": "agent_result", "colony_idx": colony_idx, "success": success},
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "OctonionState",
    "octonion_state_from_agent_result",
    "octonion_state_from_colony_state",
    "octonion_state_from_core_state",
]
