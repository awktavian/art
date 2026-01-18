"""World Model Decoder - E8 VQ → Bulk Reconstruction.

ARCHITECTURE (December 20, 2025):
==================================
    E8 VQ(8) → Tower → S7(7) → G2(14) → F4(52) → E6(78) → E7(133) → E8(248) → Bulk(512)

This decoder maps compact E8 VQ (Vector Quantized) latent representations back to
high-dimensional bulk space using the TRUE exceptional Lie algebra hierarchy.

KEY FEATURES:
=============
1. **Exceptional Hierarchy Expansion**: S7→G2→F4→E6→E7→E8 cascade with Clebsch-Gordan
2. **E8 Residual Decoding**: Decode variable-length E8 lattice codes
3. **G₂ Irrep Tower**: Processes tower representation with G₂ tensor products
4. **Fano Colony Interactions**: Enforces octonion multiplication structure
5. **Pure Geometric Path**: NO skip connections (enforced Dec 7, 2025)

MATHEMATICAL FOUNDATIONS:
=========================
- Exceptional Lie Algebras: Standard representation theory (embedding maps)
- G₂ as Aut(O): Baez (2002)
- S7 Parallelizability: Adams (1960)
- E8 Sphere Packing: Viazovska (2017) - Fields Medal

USAGE:
======
    from kagami.core.world_model.decoder import Decoder
    from kagami.core.world_model.equivariance.unified_equivariant_hierarchy import (
        create_unified_hourglass,
    )

    hourglass = create_unified_hourglass(bulk_dim=512)
    decoder = Decoder(hourglass)

    # Decode E8 VQ latent
    e8_vq = torch.randn(batch_size, 8)
    result = decoder(e8_vq, return_all=True)

    # Access reconstruction
    reconstructed = result["reconstructed"]  # [B, 512] or [B, S, 512]

    # Access intermediate states
    decoder_states = result["decoder_states"]
    # Keys: "e8_vq", "tower_out", "s7", "e8", "bulk"

GRADIENT FLOW:
==============
Full backpropagation through:
1. E8 VQ → Tower: CatastropheKAN expansion
2. Tower → S7: CatastropheKAN projection
3. S7 → E8(248): Exceptional hierarchy embedding (Clebsch-Gordan)
4. E8(248) → Bulk: Linear projection

NO SKIP CONNECTIONS: Pure information flow through geometric bottleneck.
This enforces that all information passes through the E8 VQ bottleneck.

References:
- Liu et al. (2024): KAN: Kolmogorov-Arnold Networks
- Viazovska (2017): Sphere Packing in Dimension 8
- Bronstein et al. (2021): Geometric Deep Learning

Created: December 20, 2025
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn


class Decoder(nn.Module):
    """Decoder: Maps E8 quantized latent back to bulk-dimensional space.

    ARCHITECTURE:
    =============
        E8 VQ [B, 8]
            ↓
        Tower Processing (G₂ Irrep + Fano)
            ↓
        S7(7) → G2(14) → F4(52) → E6(78) → E7(133) → E8(248)
            ↓
        Output [B, bulk_dim]

    The decoder expands compact E8 VQ latents through the exceptional Lie algebra
    hierarchy, reconstructing high-dimensional observations.

    PURE GEOMETRIC PATH:
    ====================
    NO skip connections. All information flows through the E8 VQ bottleneck.
    This ensures:
    1. Latent space is truly compact (no bypass)
    2. Reconstruction quality directly measures compression
    3. Gradient flow is symmetric with encoder

    LATENT SPACE:
    =============
    - **E8 VQ**: 8D quantized latent (240 roots, optimal packing)
    - **S7 Phase**: 7D imaginary octonion phase (intermediate)
    - **Hierarchy**: G2→F4→E6→E7→E8 expansion states

    GRADIENT FLOW:
    ==============
    Full backpropagation through:
    1. Exceptional hierarchy embeddings (Clebsch-Gordan coefficients)
    2. G₂ irrep tower (geometric tensor products)
    3. Fano colony interactions (octonion multiplication)
    4. CatastropheKAN layers (catastrophe-aware activations)

    Args:
        hourglass: UnifiedEquivariantHourglass instance (handles full architecture)

    Example:
        >>> hourglass = create_unified_hourglass(bulk_dim=512)
        >>> decoder = Decoder(hourglass)
        >>> e8_vq = torch.randn(4, 8)
        >>> result = decoder(e8_vq, return_all=True)
        >>> reconstructed = result["reconstructed"]  # [4, 512]
        >>> s7_phase = result["decoder_states"]["s7"]  # [4, 7]
    """

    def __init__(self, hourglass: Any):
        """Initialize decoder with hourglass architecture.

        Args:
            hourglass: UnifiedEquivariantHourglass containing full architecture
                       (encoder + E8 VQ + decoder)
        """
        super().__init__()
        self.hourglass = hourglass

    def forward(
        self,
        e8_vq: torch.Tensor,
        return_all: bool = True,
        encoder_states: dict[str, torch.Tensor] | None = None,
    ) -> torch.Tensor | dict[str, Any]:
        """Decode E8 VQ latent to bulk space.

        ARCHITECTURE:
        =============
        1. E8 VQ → Tower: CatastropheKAN expansion
        2. Tower → S7: G₂ irrep tower + Fano + CatastropheKAN
        3. S7 → E8(248): Exceptional hierarchy embedding (Clebsch-Gordan)
        4. E8(248) → Bulk: Linear projection

        SKIP CONNECTIONS REMOVED (Dec 7, 2025):
        =======================================
        Pure geometric path enforced. No encoder state bypass.
        The `encoder_states` argument is kept for API compatibility but IGNORED.

        Args:
            e8_vq: E8 quantized latent
                   - [B, 8]: Batch of latents
                   - [B, S, 8]: Batch of sequences
            return_all: Return full decoder states (default: True)
                        If False, returns only reconstructed tensor
            encoder_states: IGNORED. Kept for API compatibility.
                            Skip connections removed Dec 7, 2025.

        Returns:
            If return_all=False:
                Reconstructed tensor [B, bulk_dim] or [B, S, bulk_dim]

            If return_all=True:
                Dictionary containing:
                    - **reconstructed** or **bulk**: Reconstructed output
                    - **decoder_states**: Dict with intermediate states
                        - "e8_vq": Input E8 VQ latent
                        - "tower_in": Tower after E8→Tower
                        - "tower_out": Tower after G₂ processing
                        - "s7": S7 phase (7D, imaginary octonion)
                        - "e8": E8 adjoint representation (248D)
                        - "bulk": Output bulk space
                    - **e8**: E8 VQ input (alias)

        Shape Handling:
            - Input [B, 8] → Output [B, bulk_dim]
            - Input [B, S, 8] → Output [B, S, bulk_dim]

        Raises:
            ValueError: If input tensor is not 8-dimensional E8 VQ
        """
        # Validate E8 VQ shape
        if e8_vq.shape[-1] != 8:
            raise ValueError(f"Decoder expects 8D E8 VQ input, got shape {e8_vq.shape}")

        # Delegate to hourglass decoder
        # The hourglass handles:
        # 1. Sequence dimension handling
        # 2. Tower processing (G₂ + Fano)
        # 3. Exceptional hierarchy embedding
        # 4. Bulk projection
        #
        # NOTE: encoder_states is IGNORED (skip connections removed Dec 7, 2025)
        result = self.hourglass.decode(
            e8_vq,
            encoder_states=None,  # Force pure geometric path
            return_all=return_all,
        )

        # Hourglass.decode returns either:
        # - torch.Tensor (if return_all=False): Just the reconstructed bulk
        # - dict[str, Any] (if return_all=True): Full intermediates
        if isinstance(result, torch.Tensor):
            # Lightweight return: just reconstruction
            if not return_all:
                return result
            else:
                # Wrap in dict[str, Any] for consistency
                return {
                    "reconstructed": result,
                    "bulk": result,  # Alias
                    "decoder_states": {},
                    "e8": e8_vq,
                }

        # Full intermediates returned
        intermediates = result

        # Normalize output keys for consistency
        output: dict[str, Any] = {}

        # Reconstructed output (primary output)
        if "bulk" in intermediates:
            output["reconstructed"] = intermediates["bulk"]
            output["bulk"] = intermediates["bulk"]  # Keep both
        elif "reconstructed" in intermediates:
            output["reconstructed"] = intermediates["reconstructed"]

        # Decoder states (intermediate hierarchy)
        output["decoder_states"] = intermediates

        # E8 VQ input (for reference)
        output["e8"] = intermediates.get("e8_vq", e8_vq)

        return output

    def __repr__(self) -> str:
        """String representation."""
        config = self.hourglass.config
        return (
            f"Decoder(\n"
            f"  e8_vq_dim=8,\n"
            f"  tower_dim={config.tower_dim},\n"
            f"  bulk_dim={config.bulk_dim},\n"
            f"  pure_geometric_path=True\n"
            f")"
        )


__all__ = ["Decoder"]
