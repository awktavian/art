"""Sensory to World Model Encoder — Perception → E8/S7 Bridge.

This module bridges the gap between:
- UnifiedSensoryIntegration (512D perception vectors)
- OrganismRSSM (E8 code [8D] + S7 phase [7D])

The encoder learns to compress perception into the geometric structure
required by the world model while preserving semantic information.

Architecture:
    perception [B, 512]
        → compress → [B, 256]
        → E8 encoder → e8_code [B, 8]
        → S7 encoder → s7_phase [B, 7]

The E8 code represents CONTENT (what is perceived).
The S7 phase represents ROUTING (which colonies should attend).

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SensoryToWorldModel(nn.Module):
    """Encode 512D perception vectors to E8 code + S7 phase.

    This is THE bridge between sensory perception and the world model.
    Without this encoder, the OrganismRSSM cannot receive sensory input.

    Args:
        perception_dim: Input perception dimension (default: 512)
        hidden_dim: Intermediate dimension (default: 256)
        e8_dim: E8 lattice dimension (default: 8)
        s7_dim: S7 phase dimension (default: 7)
        use_e8_quantization: Whether to quantize to E8 lattice (default: True)
    """

    def __init__(
        self,
        perception_dim: int = 512,
        hidden_dim: int = 256,
        e8_dim: int = 8,
        s7_dim: int = 7,
        use_e8_quantization: bool = True,
    ):
        super().__init__()

        self.perception_dim = perception_dim
        self.hidden_dim = hidden_dim
        self.e8_dim = e8_dim
        self.s7_dim = s7_dim
        self.use_e8_quantization = use_e8_quantization

        # Compression network: 512 → 256
        self.compress = nn.Sequential(
            nn.Linear(perception_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
        )

        # E8 encoder: 256 → 8 (content encoding)
        self.e8_encoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, e8_dim),
        )

        # S7 encoder: 256 → 7 (routing/attention)
        self.s7_encoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, s7_dim),
        )

        # E8 lattice quantizer (optional)
        self._e8_quantizer = None

        logger.info(
            f"SensoryToWorldModel initialized: {perception_dim}D → "
            f"E8[{e8_dim}] + S7[{s7_dim}], quantize={use_e8_quantization}"
        )

    @property
    def e8_quantizer(self):
        """Lazy load E8 quantizer to avoid import cycles."""
        if self._e8_quantizer is None and self.use_e8_quantization:
            try:
                from kagami.math.e8_lattice_quantizer import nearest_e8

                self._e8_quantizer = nearest_e8
            except ImportError:
                logger.warning("E8 quantizer not available, using raw encoding")
                self.use_e8_quantization = False
        return self._e8_quantizer

    def forward(
        self,
        perception: torch.Tensor,
        return_hidden: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor] | tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode perception to E8 code + S7 phase.

        Args:
            perception: Perception vector [B, 512] or [512]
            return_hidden: If True, also return hidden representation

        Returns:
            e8_code: E8 lattice coordinates [B, 8]
            s7_phase: S7 colony routing phase [B, 7]
            hidden: (optional) Compressed representation [B, 256]
        """
        # Move input to model's device
        device = next(self.parameters()).device
        perception = perception.to(device)

        # Handle unbatched input
        unbatched = perception.dim() == 1
        if unbatched:
            perception = perception.unsqueeze(0)

        # Compress perception
        hidden = self.compress(perception)  # [B, 256]

        # Encode to E8 (content)
        e8_raw = self.e8_encoder(hidden)  # [B, 8]

        # Optionally quantize to E8 lattice
        if self.use_e8_quantization and self.e8_quantizer is not None:
            # Quantize with straight-through gradient
            e8_quantized = self.e8_quantizer(e8_raw)
            e8_code = e8_raw + (e8_quantized - e8_raw).detach()
        else:
            e8_code = e8_raw

        # Encode to S7 (routing)
        s7_raw = self.s7_encoder(hidden)  # [B, 7]
        s7_phase = F.softmax(s7_raw, dim=-1)  # Normalize for routing weights

        # Remove batch dimension if input was unbatched
        if unbatched:
            e8_code = e8_code.squeeze(0)
            s7_phase = s7_phase.squeeze(0)
            hidden = hidden.squeeze(0)

        if return_hidden:
            return e8_code, s7_phase, hidden
        return e8_code, s7_phase

    def encode_sense_data(
        self,
        sense_data: dict,
        sense_type: str,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Convenience method to encode raw sense data.

        This method first converts sense_data dict to perception vector,
        then encodes to E8/S7. Useful for direct sense → world model flow.

        Args:
            sense_data: Dictionary of sense values
            sense_type: Type of sense (e.g., "presence", "gmail")

        Returns:
            e8_code, s7_phase
        """
        # Import encoding function from unified_sensory
        try:
            from kagami.core.integrations.unified_sensory import (
                SenseType,
                get_unified_sensory,
            )

            sensory = get_unified_sensory()

            # Convert string to SenseType enum
            sense_type_enum = SenseType(sense_type)

            # Use existing encoding logic
            perception_list = sensory._encode_to_perception(sense_type_enum, sense_data)

            if perception_list is None:
                # Unknown sense type, return zeros
                device = next(self.parameters()).device
                return (
                    torch.zeros(self.e8_dim, device=device),
                    torch.zeros(self.s7_dim, device=device),
                )

            perception = torch.tensor(perception_list, device=next(self.parameters()).device)
            return self.forward(perception)

        except Exception as e:
            logger.warning(f"Failed to encode sense data: {e}")
            device = next(self.parameters()).device
            return (
                torch.zeros(self.e8_dim, device=device),
                torch.zeros(self.s7_dim, device=device),
            )


# =============================================================================
# Global Instance (Singleton)
# =============================================================================

_sensory_encoder: SensoryToWorldModel | None = None


def get_sensory_encoder(device: str | None = None) -> SensoryToWorldModel:
    """Get global SensoryToWorldModel instance."""
    global _sensory_encoder

    if device is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"

    if _sensory_encoder is None:
        _sensory_encoder = SensoryToWorldModel()
        _sensory_encoder = _sensory_encoder.to(device)
        logger.info(f"Global SensoryToWorldModel created on {device}")

    return _sensory_encoder


def reset_sensory_encoder() -> None:
    """Reset global instance (for testing)."""
    global _sensory_encoder
    _sensory_encoder = None


__all__ = [
    "SensoryToWorldModel",
    "get_sensory_encoder",
    "reset_sensory_encoder",
]
