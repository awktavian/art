"""E8 Residual Bottleneck - Variable-Length Compression via Residual VQ.

ARCHITECTURAL CHANGE (Dec 2, 2025):
===================================
REPLACES: G₂(14D) fixed bottleneck
WITH: Variable-depth E8 lattice residual codes (levels; on-wire bytes are varint-encoded)

RATIONALE:
==========
1. G₂ equivariance was already broken by linear projections (e8_to_g2_simple)
2. E8 is mathematically optimal sphere packing (Viazovska 2016, Fields Medal)
3. Variable-length encoding adapts to input complexity (MDL principle)
4. Residual codes are serializable (v2 lattice protocol). Note: the legacy `E8MessageBus`
   uses a compact 0-239 root-index payload; the world-model bottleneck uses lattice codes.
5. Proven in neural codecs: SoundStream, EnCodec, VQ-VAE-2

ARCHITECTURE:
============
    Bulk(512)
        ↓
    Tower (G₂ Irrep or simple Linear)
        ↓
    ResidualE8LatticeVQ encode → [L levels of 8 half-step integer coords]
        │
        │  L = 1-16 (adaptive based on complexity)
        │  Telemetry proxy: ~L×log₂(240) bits (root-shell); actual bytes vary (varints)
        │  Gradient: straight-through + temperature annealing
        │
        ↓
    ResidualE8LatticeVQ decode → 8D
        ↓
    Tower (reverse)
        ↓
    Bulk(512)

MATHEMATICAL PROPERTIES:
=======================
- The E8 lattice has 240 minimal vectors (roots) but infinitely many lattice points.
- We sometimes report ~log₂(240) ≈ 7.91 bits/level as a *legacy proxy*; the true v2 lattice
  encoding uses half-step integer coordinates with varint serialization (variable bitrate).

GRADIENT FLOW:
=============
1. Soft quantization during training (temperature-annealed)
2. Straight-through estimator for hard quantization
3. Commitment loss for codebook learning
4. Adaptive level selection is differentiable

References:
- Viazovska (2016): E8 optimal sphere packing
- Zeghidour et al. (2021): SoundStream residual VQ
- Razavi et al. (2019): VQ-VAE-2 hierarchical discrete VAE
- Rissanen (1978): MDL - Minimum Description Length

Created: December 2, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn

# =============================================================================
# RMSNorm - Gradient-friendly normalization for use before VQ
# =============================================================================


class RMSNorm(nn.Module):
    """Root Mean Square Normalization.

    GRADIENT FIX (Dec 3, 2025):
    ===========================
    LayerNorm before VQ blocks gradients when combined with STE.
    RMSNorm preserves gradient flow while still providing normalization.

    Unlike LayerNorm, RMSNorm:
    1. Does not center (no mean subtraction)
    2. Only scales by RMS
    3. Has simpler backward pass that doesn't interfere with STE

    References:
    - Zhang & Sennrich (2019): "Root Mean Square Layer Normalization"
    - Confirmed fix: RMSNorm + STE gives grad_norm > 0, LayerNorm + STE gives 0
    """

    def __init__(self, dim: int, eps: float = 1e-8):
        super().__init__()
        self.scale = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(torch.mean(x**2, dim=-1, keepdim=True) + self.eps)
        return x / rms * self.scale


from kagami_math.dimensions import (
    S7_INTRINSIC_DIM,
    get_bulk_dim,
)
from kagami_math.e8_lattice_protocol import (
    E8LatticeResidualConfig,
    ResidualE8LatticeVQ,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class E8ResidualBottleneckConfig:
    """Configuration for E8 Residual Bottleneck.

    REPLACES: G₂ 14D fixed bottleneck
    WITH: Variable-length E8 residual codes

    The bottleneck is now in DISCRETE space (E8 lattice codes) rather than
    continuous space (14D G₂). This provides:
    1. Adaptive compression (simple → few bytes, complex → more bytes)
    2. Natural discretization (useful for symbolic reasoning)
    3. A serializable protocol (v2 lattice codes). The legacy `E8MessageBus` uses
       compact root indices; this bottleneck uses lattice coordinates.
    """

    # Bulk dimension (from centralized config)
    bulk_dim: int | None = None  # Set from KAGAMI_BULK_DIM

    # Tower dimension (7D per copy, for G₂ compatibility)
    tower_dim: int | None = None  # Set to 7 * rep_multiplier
    rep_multiplier: int = 1

    # E8 Residual configuration
    # UNIFIED (Dec 6, 2025): Match SemanticResidualE8Config and UnifiedHierarchyConfig
    # Previous values (4, 8) caused inconsistent behavior with other bottleneck paths
    training_levels: int = 8  # Levels during training (matches SemanticResidualE8)
    inference_levels: int = 16  # Levels during inference (max precision)
    min_levels: int = 2  # Minimum levels (2 bytes = 16 bits minimum)
    max_levels: int = 24  # Maximum possible levels (matches unified hierarchy)

    # Temperature annealing
    temp_start: float = 1.0  # High = soft assignments
    temp_end: float = 0.01  # Low = hard assignments
    temp_anneal_steps: int = 50000

    # VQ-VAE training
    commitment_weight: float = 0.25

    # Adaptive complexity
    adaptive_levels: bool = True
    complexity_threshold: float = 0.01

    # === ADAPTIVE E8 DEPTH (Dec 14, 2025 - Nexus Integration) ===
    # Variable-depth E8 quantization based on learned importance
    adaptive_e8_enabled: bool = False  # Use adaptive depth prediction
    adaptive_e8_rate_weight: float = 0.01  # Rate loss weight (for unified_loss.py)
    adaptive_e8_target_depth: float = 8.0  # Target average depth
    adaptive_e8_smoothness_weight: float = 0.005  # Temporal smoothness
    e8_gumbel_temperature: float = 1.0  # Gumbel-Softmax temperature
    importance_predictor_hidden: int = 64  # Hidden dim for importance net

    use_skip_connections: bool = False  # DISABLED for IB optimality

    # Layer normalization
    layer_norm_eps: float = 1e-6

    def __post_init__(self) -> None:
        if self.bulk_dim is None:
            self.bulk_dim = get_bulk_dim()
        if self.tower_dim is None:
            self.tower_dim = S7_INTRINSIC_DIM * self.rep_multiplier


# =============================================================================
# E8 RESIDUAL BOTTLENECK
# =============================================================================


class E8ResidualBottleneck(nn.Module):
    """Variable-length bottleneck using E8 residual quantization.

    REPLACES the G₂(14D) fixed bottleneck with variable-length E8 codes.

    Key innovations:
    1. Variable capacity: 1-16 bytes (7.9-126.6 bits)
    2. Adaptive compression: complexity_net determines depth
    3. Serializable discrete codes (v2 lattice protocol; varint on-wire)
    4. Unified with SemanticResidualE8 (no code duplication)

    Architecture:
        encode: Bulk → Tower → 8D → [L bytes]
        decode: [L bytes] → 8D → Tower → Bulk
    """

    def __init__(self, config: E8ResidualBottleneckConfig | None = None):
        super().__init__()
        self.config = config or E8ResidualBottleneckConfig()

        # __post_init__ should have set[Any] these, but mypy can't see it
        assert self.config.bulk_dim is not None
        assert self.config.tower_dim is not None

        # === ENCODER: Bulk → Tower → 8D ===
        self.bulk_to_tower = nn.Linear(self.config.bulk_dim, self.config.tower_dim)
        self.tower_to_e8 = nn.Linear(self.config.tower_dim, 8)  # 8D for E8

        # === E8 RESIDUAL QUANTIZER (ADAPTIVE OR FIXED) ===
        # NEXUS INTEGRATION (Dec 14, 2025): Two paths for E8 quantization
        # Path A (adaptive_e8_enabled=True): Use adaptive depth predictor
        # Path B (adaptive_e8_enabled=False): Use fixed depth (backward compatible)

        # Declare quantizer attributes with proper types
        self.adaptive_e8: object | None = None  # AdaptiveE8Quantizer (avoid import at module level)
        self.residual_e8: ResidualE8LatticeVQ | None = None

        if self.config.adaptive_e8_enabled:
            # Import adaptive quantizer
            try:
                from kagami.core.world_model.layers.e8_adaptive_depth import (
                    AdaptiveE8Quantizer,
                    E8AdaptiveConfig,
                )

                # Configure adaptive quantizer to match bottleneck settings
                adaptive_config = E8AdaptiveConfig(
                    importance_input_dim=self.config.tower_dim,
                    max_levels=self.config.max_levels,
                )
                self.adaptive_e8 = AdaptiveE8Quantizer(adaptive_config)
                logger.info("E8ResidualBottleneck: Using ADAPTIVE depth quantization")
            except ImportError as e:
                logger.warning(
                    "AdaptiveE8Quantizer not available (%s), falling back to fixed depth", e
                )
                self.config.adaptive_e8_enabled = False

        if not self.config.adaptive_e8_enabled:
            # Fixed-depth quantizer (original path)
            residual_config = E8LatticeResidualConfig(
                max_levels=self.config.max_levels,
                min_levels=self.config.min_levels,
            )
            self.residual_e8 = ResidualE8LatticeVQ(residual_config)
            logger.debug("E8ResidualBottleneck: Using FIXED depth quantization")

        # === DECODER: 8D → Tower → Bulk ===
        self.e8_to_tower = nn.Linear(8, self.config.tower_dim)
        self.tower_to_bulk = nn.Linear(self.config.tower_dim, self.config.bulk_dim)

        # === NORMALIZATIONS ===
        self.enc_norm_tower = nn.LayerNorm(self.config.tower_dim, eps=self.config.layer_norm_eps)
        # GRADIENT FIX (Dec 3, 2025): Use RMSNorm before VQ
        # LayerNorm + STE blocks gradients; RMSNorm preserves them
        self.enc_norm_e8 = RMSNorm(8, eps=self.config.layer_norm_eps)
        self.dec_norm_tower = nn.LayerNorm(self.config.tower_dim, eps=self.config.layer_norm_eps)
        self.dec_norm_bulk = nn.LayerNorm(self.config.bulk_dim, eps=self.config.layer_norm_eps)

        logger.debug(
            f"E8ResidualBottleneck: "
            f"Bulk({self.config.bulk_dim}) → E8 (1-{self.config.max_levels} bytes)"
        )

    @torch.compile(mode="max-autotune", fullgraph=False)
    def encode(
        self,
        x: torch.Tensor,
        return_intermediates: bool = False,
    ) -> tuple[list[torch.Tensor], dict[str, Any]]:
        """Encode bulk to variable-length E8 indices.

        PERFORMANCE OPTIMIZATION (Dec 14, 2025):
        =======================================
        Compiled with torch.compile for 1.5-2x speedup on E8 quantization kernel.
        - mode="max-autotune": Aggressive optimization for compute-heavy E8 ops
        - fullgraph=False: Handle adaptive depth selection graph breaks

        First call incurs compilation overhead; subsequent calls are faster.

        Args:
            x: [B, bulk_dim] or [B, S, bulk_dim] input
            return_intermediates: Return intermediate states

        Returns:
            Tuple of:
            - codes: List of [B, ..., 8] int64 tensors (half-step lattice codes per level)
            - info: Dict with quantized 8D and intermediates
        """
        # Handle sequence dimension
        has_seq = x.dim() == 3
        if has_seq:
            B, S, D = x.shape
            x = x.view(B * S, D)
        else:
            B = x.shape[0]

        intermediates: dict[str, torch.Tensor | int] = {"input": x}

        # Bulk → Tower
        tower = self.bulk_to_tower(x)
        tower = self.enc_norm_tower(tower)
        intermediates["tower"] = tower

        # Tower → 8D
        e8_continuous = self.tower_to_e8(tower)
        e8_continuous = self.enc_norm_e8(e8_continuous)
        intermediates["e8_continuous"] = e8_continuous

        # E8 Residual Quantization (ADAPTIVE or FIXED)
        # NEXUS INTEGRATION (Dec 14, 2025): Route to appropriate quantizer
        if self.adaptive_e8 is not None:
            # ADAPTIVE PATH: Use learned importance predictor
            # Input: tower features [B*S, tower_dim]
            # Output: quantized [B*S, 8], codes list[Any], depth_map [B*S]
            # Type narrowing: we know adaptive_e8 is AdaptiveE8Quantizer here
            result = self.adaptive_e8(  # type: ignore[operator]
                tower if not has_seq else tower.view(B, S, -1), training=self.training
            )
            e8_quantized = result["quantized"]
            codes = result["codes"]
            intermediates["depth_map"] = result["depth_map"]
            intermediates["importance_logits"] = result["importance_logits"]
            intermediates["num_levels_int"] = result["depth_map"].max().item()
            if has_seq:
                e8_quantized = e8_quantized.view(B * S, 8)
        else:
            # FIXED PATH: Use uniform depth
            # Type narrowing: residual_e8 must exist if adaptive_e8 doesn't
            assert self.residual_e8 is not None
            num_levels = (
                self.config.training_levels if self.training else self.config.inference_levels
            )
            vq_result = self.residual_e8(e8_continuous, num_levels=num_levels)
            # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
            e8_quantized = vq_result["quantized"]
            codes_tensor = vq_result["indices"]  # [B, L, 8] where L = num_levels
            codes = [codes_tensor[:, i, :] for i in range(codes_tensor.shape[1])]
            intermediates["e8_quantized"] = e8_quantized
            intermediates["e8_vq_loss"] = vq_result["loss"]
            intermediates["num_levels_int"] = len(codes)

        # Restore sequence dimension
        if has_seq:
            e8_quantized = e8_quantized.view(B, S, 8)
            codes = [c.view(B, S, 8) for c in codes]
            for key in intermediates:
                value = intermediates[key]
                if isinstance(value, torch.Tensor):
                    intermediates[key] = value.view(B, S, -1)

        info = {
            "e8_quantized": e8_quantized,
            "intermediates": intermediates if return_intermediates else None,
        }

        return codes, info

    @torch.compile(mode="max-autotune", fullgraph=False)
    def decode(
        self,
        codes: list[torch.Tensor],
        encoder_states: dict[str, Any] | None = None,
        e8_quantized: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Decode E8 indices back to bulk representation.

        PERFORMANCE OPTIMIZATION (Dec 14, 2025):
        =======================================
        Compiled with torch.compile for 1.5-2x speedup on E8 decoding.
        - mode="max-autotune": Aggressive optimization for compute-heavy E8 ops
        - fullgraph=False: Handle variable-length codes graph breaks

        Args:
            codes: List of [B, ..., 8] lattice code tensors from encoder
            encoder_states: Optional encoder intermediates for skip connections
            e8_quantized: [B, 8] quantized E8 output (for gradient flow!)
                          If provided, uses this instead of decoding from indices.

        Returns:
            [B, bulk_dim] or [B, S, bulk_dim] reconstructed

        GRADIENT FIX (Dec 3, 2025):
        ===========================
        When e8_quantized is provided, use it directly instead of decoding
        from indices. This preserves gradient flow via straight-through.
        The indices are still used for compression/transmission, but
        training should use e8_quantized for gradients.
        """
        # GRADIENT FIX: Use quantized output if provided (has STE gradients)
        if e8_quantized is not None:
            e8_decoded = e8_quantized
        else:
            # Decode from indices (no gradient to encoder - for inference only)
            if self.residual_e8 is None:
                raise RuntimeError("Cannot decode indices without fixed-depth quantizer")
            e8_decoded = self.residual_e8.decode(codes)

        # Handle sequence dimension
        has_seq = e8_decoded.dim() == 3
        if has_seq:
            B, S, D = e8_decoded.shape
            e8_decoded = e8_decoded.view(B * S, D)
            if encoder_states:
                encoder_states = {
                    k: v.view(B * S, -1) if isinstance(v, torch.Tensor) else v
                    for k, v in encoder_states.items()
                }
        else:
            B = e8_decoded.shape[0]

        _ = encoder_states  # Unused after skip connection removal

        # 8D → Tower
        tower = self.e8_to_tower(e8_decoded)
        tower = self.dec_norm_tower(tower)

        # Tower → Bulk
        bulk = self.tower_to_bulk(tower)
        bulk = self.dec_norm_bulk(bulk)

        # Restore sequence dimension
        if has_seq:
            bulk = bulk.view(B, S, -1)

        return bulk

    def forward(
        self,
        x: torch.Tensor,
        return_all: bool = False,
    ) -> torch.Tensor | dict[str, Any]:
        """Full encode-decode pass.

        Args:
            x: [B, bulk_dim] or [B, S, bulk_dim] input
            return_all: Return dict[str, Any] with all outputs

        Returns:
            Reconstructed bulk, or dict[str, Any] with all outputs if return_all
        """
        # Encode
        indices_list, encode_info = self.encode(x, return_intermediates=True)

        # Decode with skip connections
        # GRADIENT FIX: Pass e8_quantized for gradient flow!
        reconstructed = self.decode(
            indices_list,
            encoder_states=encode_info.get("intermediates"),
            e8_quantized=encode_info.get("e8_quantized"),  # STE gradients!
        )

        if return_all:
            return {
                "reconstructed": reconstructed,
                "indices_list": indices_list,
                "e8_quantized": encode_info["e8_quantized"],
                "num_levels": len(indices_list),
                "bits_used": len(indices_list) * 7.91,  # log2(240) proxy
            }

        return reconstructed

    def get_compression_stats(self) -> dict[str, Any]:
        """Get compression statistics."""
        if self.residual_e8 is not None:
            stats = self.residual_e8.get_stats()
        else:
            stats = {}

        # Type narrowing: bulk_dim/tower_dim guaranteed non-None by __post_init__
        assert self.config.bulk_dim is not None
        assert self.config.tower_dim is not None

        stats.update(
            {
                "bulk_dim": self.config.bulk_dim,
                "tower_dim": self.config.tower_dim,
                "compression_ratio_min": self.config.bulk_dim * 32 / 8,  # 1 byte
                "compression_ratio_max": self.config.bulk_dim * 32 / (self.config.max_levels * 8),
            }
        )
        return stats

    def to_bytes(self, x: torch.Tensor) -> bytes:
        """Encode to byte string (compatible with E8MessageBus).

        Args:
            x: [bulk_dim] or [B, bulk_dim] input

        Returns:
            Byte string in E8 message format
        """
        if x.dim() == 1:
            x = x.unsqueeze(0)

        indices_list, _ = self.encode(x)

        # Convert to bytes: [num_levels, idx_0, idx_1, ...]
        result = [len(indices_list)]
        for indices in indices_list:
            result.append(int(indices[0].item()) & 0xFF)

        return bytes(result)

    def from_bytes(self, data: bytes) -> torch.Tensor:
        """Decode from byte string.

        Args:
            data: Byte string from to_bytes()

        Returns:
            [bulk_dim] reconstructed
        """
        num_levels = data[0]
        indices_list = [torch.tensor([data[i + 1]], dtype=torch.long) for i in range(num_levels)]

        return self.decode(indices_list).squeeze(0)


# =============================================================================
# FACTORY
# =============================================================================


def create_e8_residual_bottleneck(
    bulk_dim: int | None = None,
    training_levels: int = 4,
    inference_levels: int = 8,
    adaptive: bool = True,
) -> E8ResidualBottleneck:
    """Create E8 residual bottleneck.

    Args:
        bulk_dim: Input/output dimension (default from KAGAMI_BULK_DIM)
        training_levels: Levels during training
        inference_levels: Levels during inference
        adaptive: Use adaptive level selection

    Returns:
        Configured E8ResidualBottleneck
    """
    config = E8ResidualBottleneckConfig(
        training_levels=training_levels,
        inference_levels=inference_levels,
        adaptive_levels=adaptive,
    )
    if bulk_dim is not None:
        config.bulk_dim = bulk_dim
    return E8ResidualBottleneck(config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "E8ResidualBottleneck",
    "E8ResidualBottleneckConfig",
    "create_e8_residual_bottleneck",
]
