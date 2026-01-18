"""KagamiWorldModel Custom Layers.

EXTRACTED FROM kagami_world_model.py (December 13, 2025):
========================================================
Custom neural network layers for the Kagami World Model.
This reduces the main model file complexity by separating layer definitions.

Contains:
- SwiGLUFFN: Swish-Gated Linear Unit Feed Forward Network
- Other custom layer implementations
- Layer utility functions
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class SwiGLUFFN(nn.Module):
    """Swish-Gated Linear Unit Feed Forward Network.

    Implements the SwiGLU activation function from PaLM paper:
    SwiGLU(x) = Swish(W₁x) ⊙ (W₂x)

    This is used throughout the KagamiWorldModel for better gradient flow
    and improved representational capacity.
    """

    def __init__(self, dim: int, hidden_dim: int, dropout: float = 0.0):
        super().__init__()
        self.w1 = nn.Linear(dim, hidden_dim, bias=False)
        self.w2 = nn.Linear(dim, hidden_dim, bias=False)
        self.w3 = nn.Linear(hidden_dim, dim, bias=False)
        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through SwiGLU FFN."""
        return self.w3(self.dropout(F.silu(self.w1(x)) * self.w2(x)))


class E8ResidualBlock(nn.Module):
    """E8 Residual Block for the bottleneck layer.

    Implements residual connections around E8 quantization to preserve
    gradient flow and enable deeper architectures.
    """

    def __init__(self, dim: int = 8, num_levels: int = 4):
        super().__init__()
        self.dim = dim
        self.num_levels = num_levels

        # Projection layers
        self.pre_proj = nn.Linear(dim, dim)
        self.post_proj = nn.Linear(dim, dim)

        # Layer norm for stability
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass with residual connection around E8 quantization."""
        residual = x

        # Pre-quantization processing
        x = self.norm1(x)
        x = self.pre_proj(x)

        # E8 quantization would happen here (simplified for this layer)
        # In actual implementation, this calls the E8 quantization module

        # Post-quantization processing
        x = self.norm2(x)
        x = self.post_proj(x)

        # Residual connection
        return x + residual


# G2IrrepTower: import from canonical source (consolidated Dec 25, 2025)
# Uses mathematically correct Clebsch-Gordan decomposition.
# See kagami/core/math/g2_irrep_tower.py for full implementation.
from kagami_math.g2_irrep_tower import G2IrrepTower

__all__ = [
    "E8ResidualBlock",
    "G2IrrepTower",
    "SwiGLUFFN",
    "create_swiglu_ffn",
    "get_layer_info",
]


# Layer utility functions


def create_swiglu_ffn(dim: int, expansion_factor: float = 4.0, dropout: float = 0.0) -> SwiGLUFFN:
    """Create a SwiGLU FFN with standard expansion factor."""
    hidden_dim = int(dim * expansion_factor)
    return SwiGLUFFN(dim, hidden_dim, dropout)


def get_layer_info(layer: nn.Module) -> dict[str, Any]:
    """Get information about a layer for debugging."""
    info = {
        "type": type(layer).__name__,
        "parameters": sum(p.numel() for p in layer.parameters()),
        "trainable": sum(p.numel() for p in layer.parameters() if p.requires_grad),
    }

    if hasattr(layer, "in_features") and hasattr(layer, "out_features"):
        info["input_dim"] = layer.in_features
        info["output_dim"] = layer.out_features

    return info
