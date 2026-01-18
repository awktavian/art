"""World Model Layers - Geometric Transformer Components.

CatastropheKAN is the ONLY KAN implementation.
The 7 elementary catastrophes provide mathematically canonical activation functions.

ACTIVE LAYERS:
- CatastropheKANLayer: Colony-specific catastrophe activations
- MultiColonyCatastropheKAN: All 7 catastrophes in parallel with Fano combiner
- CatastropheKANExpert: MoE expert with catastrophe activation
- SparseMoE: Mixture of Experts (CatastropheKAN experts only)
- GeometricMamba: State space model
- HyperbolicFlashAttention: Optimized attention
- SparseOctonion: E8-quantized layers
"""

from __future__ import annotations

# ============================================================================
# CATASTROPHE KAN - THE ONLY KAN (Dec 7, 2025)
# ============================================================================
from kagami.core.world_model.layers.catastrophe_kan import (
    BatchedCatastropheBasis,
    BatchedCatastropheKANFeedForward,
    BatchedCatastropheKANLayer,
    CatastropheBasis,
    CatastropheKANFeedForward,
    CatastropheKANLayer,
    CatastropheType,
    FanoOctonionCombiner,
    MultiColonyCatastropheKAN,
)

# ============================================================================
# ADAPTIVE E8 QUANTIZATION (Dec 14, 2025)
# ============================================================================
from kagami.core.world_model.layers.e8_adaptive_depth import (
    AdaptiveE8Quantizer,
    E8AdaptiveConfig,
    E8ImportancePredictor,
    ImportanceToMask,
    Snake,
    create_adaptive_e8_quantizer,
)
from kagami.core.world_model.layers.gated_fano_attention import (
    GatedFanoAttention,
)

# ============================================================================
# GEOMETRIC LAYERS
# ============================================================================
from kagami.core.world_model.layers.geometric_mamba import GeometricMamba
from kagami.core.world_model.layers.hyperbolic_flash_attention import (
    HyperbolicFlashAttention,
)

# ============================================================================
# SPARSE MOE (CatastropheKAN experts only)
# ============================================================================
from kagami.core.world_model.layers.sparse_moe import (
    CatastropheKANExpert,
    Expert,
    Router,
    SparseMoE,
    SparseMoEFeedForward,
)
from kagami.core.world_model.layers.sparse_octonion import (
    SparseOctonionActivation,
)

__all__ = [
    # ===== Adaptive E8 Quantization =====
    "AdaptiveE8Quantizer",
    "BatchedCatastropheBasis",
    "BatchedCatastropheKANFeedForward",
    "BatchedCatastropheKANLayer",
    "CatastropheBasis",
    "CatastropheKANExpert",
    "CatastropheKANFeedForward",
    # ===== CATASTROPHE KAN (THE ONLY KAN) =====
    "CatastropheKANLayer",
    "CatastropheType",
    "E8AdaptiveConfig",
    "E8ImportancePredictor",
    "Expert",
    "FanoOctonionCombiner",
    # ===== Gated Fano Attention =====
    "GatedFanoAttention",
    # ===== Geometric layers =====
    "GeometricMamba",
    "HyperbolicFlashAttention",
    "ImportanceToMask",
    "MultiColonyCatastropheKAN",
    "Router",
    "Snake",
    # ===== MoE layers =====
    "SparseMoE",
    "SparseMoEFeedForward",
    "SparseOctonionActivation",
    "create_adaptive_e8_quantizer",
]
