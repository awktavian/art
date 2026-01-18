from __future__ import annotations

from typing import cast

"""Matryoshka Fiber Bundle - Nested Hierarchical Structure.

Implements nested fiber bundles with hierarchical base spaces aligned to
the Exceptional Lie Algebra Hierarchy:

    E₁₄ ⊂ E₂₁ ⊂ E₅₂ ⊂ E₇₈ ⊂ E₁₃₃ ⊂ E₂₄₈ ⊂ E₅₁₂
     ↓     ↓     ↓     ↓      ↓      ↓      ↓
    G₂    H¹⁴×S⁷  F₄   E₆    E₇     E₈    Bulk

Each level Eᵢ has:
- Base space: ℝᵢ (semantic embeddings at dimension i)
- Fiber: H¹⁴ × S⁷ (hyperbolic × octonion structure, 21D manifold)
- Section σᵢ: ℝᵢ → Eᵢ (embed_to_manifold)
- Projection πᵢ: Eᵢ → ℝᵢ (lift_from_manifold)

CRITICAL DISTINCTION:
====================
- S⁷ INTRINSIC dimension: 7 (as a Riemannian manifold)
- S⁷ EMBEDDING dimension: 8 (coordinates in ℝ⁸)
- Manifold dimension: H¹⁴ × S⁷ = 14 + 7 = 21D (NOT 22!)

The 7D intrinsic representation uses the imaginary octonion components (e₁...e₇).
The real component e₀ is constrained by the unit sphere condition ||o|| = 1.

Mathematical properties:
1. Nested inclusion: Eᵢ ⊂ Eⱼ for i < j (natural embeddings)
2. Compatible fibers: Same H¹⁴ × S⁷ at all levels
3. Resolution hierarchy: Higher dimensions = more information
4. G₂-equivariant: 14D hyperbolic preserves octonion automorphisms

Based on:
- Fiber bundle theory (Steenrod, 1951)
- Matryoshka representations (Kusupati et al., 2022)
- Exceptional Lie Groups (Yokota, 2009)
- K OS unified manifold architecture
"""
import logging
from dataclasses import dataclass

import torch
import torch.nn as nn

# v2 lattice protocol (true E8 lattice)
from kagami_math.e8_lattice_protocol import E8LatticeResidualConfig, ResidualE8LatticeVQ
from kagami_math.e8_lattice_quantizer import nearest_e8

try:
    from kagami.core.world_model.manifolds.adaptive_curvature import AdaptivePoincareManifold

    ADAPTIVE_CURVATURE_AVAILABLE = True
except ImportError:
    ADAPTIVE_CURVATURE_AVAILABLE = False
logger = logging.getLogger(__name__)


@dataclass
class MatryoshkaFiberConfig:
    """Configuration for Matryoshka fiber bundle.

    The fiber bundle maps semantic embeddings to a geometric manifold:
        σ: ℝᵈ → H¹⁴ × S⁷

    where:
    - H¹⁴: 14-dimensional hyperbolic space (G₂ Lie algebra)
    - S⁷: 7-sphere of unit octonions (7D intrinsic, 8D embedding)

    EXCEPTIONAL HIERARCHY DIMENSIONS (Nov 30, 2025):
    =================================================
    Dimensions align with G₂ ⊂ F₄ ⊂ E₆ ⊂ E₇ ⊂ E₈:
    - 14:  G₂ (automorphisms of octonions, 12 roots + 2 Cartan)
    - 21:  H¹⁴ × S⁷ manifold dimension (14 + 7, NOT 22!)
    - 52:  F₄ (Albert algebra, 48 roots + 4 Cartan)
    - 78:  E₆ (structure group, 72 roots + 6 Cartan)
    - 133: E₇ (Freudenthal system, 126 roots + 7 Cartan)
    - 248: E₈ (complete lattice, 240 roots + 8 Cartan)
    - 512: Bulk (task-specific)

    CRITICAL DIMENSION DISTINCTION:
    ===============================
    - s7_intrinsic_dim = 7 (tangent space dimension, imaginary octonions e₁...e₇)
    - octonion_embedding_dim = 8 (ℝ⁸ coordinates for actual octonion operations)
    - manifold_dim = hyperbolic_dim + s7_intrinsic_dim = 14 + 7 = 21

    The 8th octonion component (e₀) is constrained by ||o|| = 1, so intrinsic dim = 7.
    """

    # EXCEPTIONAL HIERARCHY DIMENSIONS (from centralized config)
    # Uses get_matryoshka_dimensions() for dynamic bulk_dim based on KAGAMI_BULK_DIM
    dimensions: tuple[int, ...] | None = None  # Set in __post_init__ from config
    hyperbolic_dim: int = 14  # H¹⁴ dimension (G₂-aligned) - FIXED
    s7_intrinsic_dim: int = 7  # S⁷ intrinsic dimension (imaginary octonions) - FIXED
    octonion_embedding_dim: int = 8  # ℝ⁸ embedding for octonion vectors - FIXED
    default_dim: int = 248  # E₈ as default
    curvature_init: float = 0.1
    learnable_curvature: bool = True
    per_level_curvature: bool = True
    use_adaptive_curvature: bool = False

    def __post_init__(self) -> None:
        """Validate configuration and set[Any] dynamic dimensions."""
        from kagami_math.dimensions import get_matryoshka_dimensions

        # Set dimensions from centralized config if not provided
        if self.dimensions is None:
            object.__setattr__(self, "dimensions", get_matryoshka_dimensions())

        assert self.hyperbolic_dim == 14, "hyperbolic_dim must be 14 (G₂ dimension)"
        assert self.s7_intrinsic_dim == 7, "s7_intrinsic_dim must be 7 (intrinsic S⁷)"
        assert self.octonion_embedding_dim == 8, "octonion_embedding_dim must be 8 (ℝ⁸)"

        manifold_dim = self.hyperbolic_dim + self.s7_intrinsic_dim
        assert manifold_dim == 21, (
            f"manifold_dim must be 21 (H¹⁴ × S⁷ = 14 + 7), got {manifold_dim}"
        )

        logger.info(
            f"MatryoshkaFiberConfig: H¹⁴ × S⁷ = {manifold_dim}D manifold, bulk={self.dimensions[-1]}D"  # type: ignore[index]
        )


class MatryoshkaFiberBundle(nn.Module):
    """Hierarchical fiber bundle with nested base spaces.

    This is the fiber bundle generalization of Matryoshka embeddings.
    Instead of a single bundle E → ℝᵈ, we have a nested sequence:

        E₃₂ ⊂ E₆₄ ⊂ ... ⊂ E₁₀₂₄

    With natural inclusion maps and compatible fiber structure.

    Usage:
        # Embed to manifold at different resolutions
        z_32, o_32 = bundle.embed_to_manifold(semantic, target_dim=32)
        z_256, o_256 = bundle.embed_to_manifold(semantic, target_dim=256)

        # Higher dimensions contain more information
        # Lower dimensions are more efficient
    """

    def __init__(self, config: MatryoshkaFiberConfig) -> None:
        super().__init__()
        self.config = config

        # Use G₂-exact encoder if hyperbolic_dim == 14 (mathematically optimal!)
        use_g2_exact = config.hyperbolic_dim == 14

        if use_g2_exact:
            logger.info("🔬 Using G₂-exact encoders (dim(G₂) = 14, mathematically optimal!)")
            from kagami.core.world_model.equivariance.g2_exact_encoder import G2ExactEncoderH14

            # G₂-exact encoders for each Matryoshka dimension
            self.encoders = nn.ModuleDict()
            for dim in config.dimensions:  # type: ignore[union-attr]
                self.encoders[str(dim)] = G2ExactEncoderH14(
                    input_dim=dim, num_g2_layers=2, hidden_dim=32
                )
        else:
            # Simple linear encoders (for non-14D configurations)
            logger.info(f"Using simple encoders (hyperbolic_dim={config.hyperbolic_dim})")
            self.encoders = nn.ModuleDict()
            for dim in config.dimensions:  # type: ignore[union-attr]
                self.encoders[str(dim)] = nn.Sequential(
                    nn.Linear(dim, 128), nn.GELU(), nn.Linear(128, config.hyperbolic_dim)
                )

        # Decoders (same for both)
        self.decoders = nn.ModuleDict()
        for dim in config.dimensions:  # type: ignore[union-attr]
            self.decoders[str(dim)] = nn.Sequential(
                nn.Linear(config.hyperbolic_dim, 128), nn.GELU(), nn.Linear(128, dim)
            )

        # Dedicated S⁷ encoders (semantic → 8D embedding) per level
        # Output is 8D for actual octonion operations (embedding dimension)
        self.octonion_encoders = nn.ModuleDict()
        for dim in config.dimensions:  # type: ignore[union-attr]
            self.octonion_encoders[str(dim)] = nn.Sequential(
                nn.Linear(dim, 32),
                nn.GELU(),
                nn.Linear(32, config.octonion_embedding_dim),  # 8D embedding
            )

        # E8 lattice VQ for S⁷ quantization (v2: true lattice, 1-level)
        self.octonion_vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(
                max_levels=1,
                min_levels=1,
                initial_scale=1.0,
                adaptive_levels=False,
            )
        )

        if config.use_adaptive_curvature and ADAPTIVE_CURVATURE_AVAILABLE:
            self.adaptive_manifolds = nn.ModuleDict(
                {
                    str(dim): AdaptivePoincareManifold(
                        dim=config.hyperbolic_dim,
                        embedding_dim=dim,
                        curvature_init=config.curvature_init,
                        num_heads=1,
                    )
                    for dim in config.dimensions  # type: ignore[union-attr]
                }
            )
            logger.info(
                f"✨ Matryoshka bundle using adaptive curvature at all {len(config.dimensions)} levels"  # type: ignore[arg-type]
            )
        elif config.per_level_curvature:
            self.curvatures = nn.ParameterDict(
                {
                    str(dim): nn.Parameter(torch.tensor(config.curvature_init))
                    for dim in config.dimensions  # type: ignore[union-attr]
                }
            )
        else:
            self.curvature = nn.Parameter(torch.tensor(config.curvature_init))

        # Default Z for decompression.
        # With true lattice points there is no finite codebook to index, so we use a single
        # learned default hyperbolic component for all byte-only reconstructions.
        self.default_z = nn.Parameter(torch.zeros(config.hyperbolic_dim))

        self._poincare = None
        self._octonion = None

    @property
    def poincare(self) -> None:
        """Lazy-load Poincaré manifold operations."""
        if self._poincare is None:
            from kagami.core.world_model.manifolds.poincare import PoincareManifold

            self._poincare = PoincareManifold(  # type: ignore[assignment]
                dim=self.config.hyperbolic_dim,
                curvature_init=self.config.curvature_init,
                learnable_curvature=True,
            )
        return self._poincare

    @property
    def octonion(self) -> None:
        """Lazy-load octonion operations."""
        if self._octonion is None:
            from kagami_math.octonions import OctonionManifold

            self._octonion = OctonionManifold()
        return self._octonion

    def get_curvature(self, dimension: int, semantic: torch.Tensor | None = None) -> torch.Tensor:
        """Get curvature for given dimension level.

        Args:
            dimension: Dimension level from exceptional hierarchy (14, 21, 52, 78, etc.)
            semantic: Optional semantic embeddings for adaptive curvature [B, D] or [B, N, D]

        Returns:
            Curvature value (adaptive if enabled, otherwise static)
        """
        if self.config.use_adaptive_curvature and ADAPTIVE_CURVATURE_AVAILABLE:
            if semantic is None:
                raise ValueError("semantic embeddings required for adaptive curvature")
            manifold = self.adaptive_manifolds[str(dimension)]
            return cast(torch.Tensor, manifold.get_curvature(semantic))  # type: ignore[operator]
        elif self.config.per_level_curvature:
            return cast(torch.Tensor, self.curvatures[str(dimension)].clamp(min=0.001, max=1.0))
        else:
            return self.curvature.clamp(min=0.001, max=1.0)

    def embed_to_manifold(
        self, semantic: torch.Tensor, target_dim: int | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Section map σ: ℝᵈ → H¹⁴ × S⁷.

        Args:
            semantic: Semantic embeddings [B, d] where d ∈ dimensions
            target_dim: Target dimension (auto-detects if None)

        Returns:
            z: Hyperbolic coordinates [B, 14] on H¹⁴
            o: Octonion coordinates [B, 8] on S⁷
        """
        _B, d = semantic.shape
        if target_dim is None:
            target_dim = d
        assert (
            target_dim in self.config.dimensions  # type: ignore[operator]
        ), f"Dimension {target_dim} not in {self.config.dimensions}"
        assert d == target_dim, f"Input dimension {d} doesn't match target {target_dim}"
        encoder = self.encoders[str(target_dim)]
        v = encoder(semantic)
        z = self.poincare.exp0(v)  # type: ignore[attr-defined]

        # Learn octonion head from semantic directly (do not slice hyperbolic)
        o_unnorm = self.octonion_encoders[str(target_dim)](semantic)
        o = self.octonion.project_to_s7(o_unnorm)  # type: ignore[attr-defined]

        # OPTIONAL: Quantize to E8 lattice if in "Crystal Mode"
        # This aligns the continuous S⁷ fiber with the discrete E8 geometry
        # Used for stable long-term prediction (V-JEPA 2 style)
        if not self.training:
            # Map to nearest E8 lattice point and re-normalize to S⁷.
            o = nearest_e8(o)
            o = nn.functional.normalize(o, p=2, dim=-1)

        return (z, o)

    def lift_from_manifold(
        self, z: torch.Tensor, o: torch.Tensor, target_dim: int | None = None
    ) -> torch.Tensor:
        """Projection map π: H¹⁴ × S⁷ → ℝᵈ.

        Args:
            z: Hyperbolic coordinates [B, 14]
            o: Octonion coordinates [B, 8]
            target_dim: Target semantic dimension (default: config.default_dim)

        Returns:
            Semantic embeddings [B, target_dim]
        """
        if target_dim is None:
            target_dim = self.config.default_dim
        v = self.poincare.log0(z)  # type: ignore[attr-defined]
        decoder = self.decoders[str(target_dim)]
        semantic = decoder(v)
        semantic = nn.functional.normalize(semantic, p=2, dim=-1)
        return semantic

    def to_bytes(self, semantic_batch: torch.Tensor) -> bytes:
        """Compress semantic batch to framed v2 E8 payloads.

        Args:
            semantic_batch: [B, D] float tensor

        Returns:
            Framed bytes: varint(B) then [varint(len_i) | payload_i] * B
        """
        # 1. Embed to manifold (get Octonion part)
        _, o = self.embed_to_manifold(semantic_batch)
        # 2. Encode each sample as a v2 payload (1 level)
        from kagami_math.e8_lattice_protocol import _encode_varint  # local helper

        out = bytearray()
        out.extend(_encode_varint(int(o.shape[0])))
        for i in range(o.shape[0]):
            payload = self.octonion_vq.encode_bytes(o[i], num_levels=1)
            out.extend(_encode_varint(len(payload)))
            out.extend(payload)
        return bytes(out)

    def from_bytes(self, byte_data: bytes, target_dim: int | None = None) -> torch.Tensor:
        """Decompress framed v2 E8 payloads to semantic embeddings.

        Args:
            byte_data: bytes object
            target_dim: Desired semantic dimension

        Returns:
            [len(bytes), target_dim] float tensor
        """
        from kagami_math.e8_lattice_protocol import _decode_varint  # local helper

        # Frame decode: varint(B) then [len|payload]*B
        B, off = _decode_varint(byte_data, 0)
        device = self.default_z.device
        o_list = []
        for _ in range(B):
            n, off = _decode_varint(byte_data, off)
            payload = byte_data[off : off + n]
            off += n
            o_q, _codes = self.octonion_vq.decode_bytes(payload)
            o_list.append(o_q.to(device))
        o = torch.stack(o_list, dim=0)
        z = self.default_z.unsqueeze(0).expand(B, -1)
        return self.lift_from_manifold(z, o, target_dim=target_dim)

    def compute_reconstruction_error(self, semantic: torch.Tensor, dimension: int) -> torch.Tensor:
        """Compute π ∘ σ reconstruction error.

        Fiber bundle invariant: π(σ(s)) ≈ s

        Args:
            semantic: Input embeddings [B, d]
            dimension: Dimension level to test

        Returns:
            Reconstruction error (MSE)
        """
        z, o = self.embed_to_manifold(semantic, target_dim=dimension)
        reconstructed = self.lift_from_manifold(z, o, target_dim=dimension)
        error = torch.nn.functional.mse_loss(reconstructed, semantic)
        return error

    def forward(
        self, x: torch.Tensor, target_dim: int | None = None
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass: semantic → manifold → semantic (with reconstruction).

        Args:
            x: Input embeddings [B, d]
            target_dim: Target dimension (auto-detects if None)

        Returns:
            z: Hyperbolic coordinates [B, 14]
            o: Octonion coordinates [B, 8]
            reconstructed: Reconstructed semantics [B, d]
        """
        if target_dim is None:
            target_dim = x.shape[-1]
        z, o = self.embed_to_manifold(x, target_dim=target_dim)
        reconstructed = self.lift_from_manifold(z, o, target_dim=target_dim)
        return (z, o, reconstructed)


_matryoshka_bundle: MatryoshkaFiberBundle | None = None


def get_matryoshka_bundle(config: MatryoshkaFiberConfig | None = None) -> MatryoshkaFiberBundle:
    """Get global Matryoshka fiber bundle (singleton)."""
    global _matryoshka_bundle
    if _matryoshka_bundle is None:
        if config is None:
            config = MatryoshkaFiberConfig()
        _matryoshka_bundle = MatryoshkaFiberBundle(config)
    return _matryoshka_bundle
