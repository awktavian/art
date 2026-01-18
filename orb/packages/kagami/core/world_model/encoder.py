"""World Model Encoder - Bulk → E8 VQ Compression.

ARCHITECTURE (December 20, 2025):
==================================
    Bulk(512) → E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7) → Tower → E8 VQ(8)

This encoder maps high-dimensional bulk observations to a compact E8 VQ (Vector Quantized)
latent space using the TRUE exceptional Lie algebra hierarchy.

KEY FEATURES:
=============
1. **Exceptional Hierarchy Compression**: E8→E7→E6→F4→G2→S7 cascade with Clebsch-Gordan
2. **E8 Residual Bottleneck**: Variable-length optimal sphere packing (1-16 levels)
3. **S7 Phase Extraction**: Extracts 7D octonion phase at all hierarchy levels
4. **G₂ Irrep Tower**: Processes tower representation with G₂ tensor products
5. **Fano Colony Interactions**: Enforces octonion multiplication structure

MATHEMATICAL FOUNDATIONS:
=========================
- E8 Sphere Packing: Viazovska (2017) - Fields Medal
- Exceptional Lie Algebras: Standard representation theory
- S7 Parallelizability: Adams (1960)
- G₂ as Aut(O): Baez (2002)

USAGE:
======
    from kagami.core.world_model.encoder import Encoder
    from kagami.core.world_model.equivariance.unified_equivariant_hierarchy import (
        create_unified_hourglass,
    )

    hourglass = create_unified_hourglass(bulk_dim=512)
    encoder = Encoder(hourglass)

    # Encode observation
    x = torch.randn(batch_size, 512)
    result = encoder(x, return_all=True)

    # Access E8 VQ latent
    e8_vq = result["e8_vq"]  # [B, 8] or [B, S, 8]

    # Access S7 phases (7D octonion)
    s7_phase = result["encoder_states"]["s7"]  # [B, 7] or [B, S, 7]

    # Access full hierarchy
    hierarchy = result["encoder_states"]
    # Keys: "e8_248", "e7", "e6", "f4", "g2", "s7", "tower_out", "e8_continuous"

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


class Encoder(nn.Module):
    """Encoder: Maps bulk-dimensional input to E8 quantized latent space.

    ARCHITECTURE:
    =============
        Input [B, bulk_dim]
            ↓
        E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7)
            ↓
        Tower Processing (G₂ Irrep + Fano)
            ↓
        E8 VQ [B, 8]

    The encoder compresses high-dimensional observations through the exceptional
    Lie algebra hierarchy, extracting geometric structure at each level.

    LATENT SPACE:
    =============
    - **E8 VQ**: 8D quantized latent, optimal sphere packing
    - **S7 Phase**: 7D imaginary octonion phase (colony coherence)
    - **Hierarchy**: E8, E7, E6, F4, G2 intermediate states

    GRADIENT FLOW:
    ==============
    Full backpropagation through:
    1. E8 residual quantization (VQ-VAE with EMA codebook)
    2. Exceptional hierarchy projections (Clebsch-Gordan coefficients)
    3. G₂ irrep tower (geometric tensor products)
    4. Fano colony interactions (octonion multiplication)

    Args:
        hourglass: UnifiedEquivariantHourglass instance (handles full architecture)

    Example:
        >>> hourglass = create_unified_hourglass(bulk_dim=512)
        >>> encoder = Encoder(hourglass)
        >>> x = torch.randn(4, 512)
        >>> result = encoder(x, return_all=True)
        >>> e8_vq = result["e8_vq"]  # [4, 8]
        >>> s7_phase = result["encoder_states"]["s7"]  # [4, 7]
    """

    def __init__(self, hourglass: Any):
        """Initialize encoder with hourglass architecture.

        Args:
            hourglass: UnifiedEquivariantHourglass containing full architecture
                       (encoder + E8 VQ + decoder)
        """
        super().__init__()
        self.hourglass = hourglass

    def forward(
        self,
        x: torch.Tensor,
        return_all: bool = True,
        seq_len: int | None = None,
    ) -> dict[str, Any]:
        """Encode input to E8 VQ latent space.

        ARCHITECTURE:
        =============
        1. Bulk → E8(248): Linear projection to exceptional space
        2. E8 → S7: Cascade through E7, E6, F4, G2 using Clebsch-Gordan
        3. S7 → Tower: CatastropheKAN processing
        4. Tower → E8 VQ: G₂ irrep tower + Fano interactions + VQ

        Args:
            x: Input tensor
               - [B, bulk_dim]: Batch of observations
               - [B, S, bulk_dim]: Batch of sequences
            return_all: Return full hierarchy states (default: True)
                        If False, returns lightweight dict[str, Any] with minimal info
            seq_len: Unused, kept for API compatibility

        Returns:
            Dictionary containing:
                - **e8_vq** or **e8_quantized**: [B, 8] or [B, S, 8] E8 VQ latent
                - **encoder_states** or **intermediates**: Dict with hierarchy states
                    - "e8_248": E8 adjoint representation (248D)
                    - "e7": E7 state (133D)
                    - "e6": E6 state (78D)
                    - "f4": F4 state (52D)
                    - "g2": G2 state (14D)
                    - "s7": S7 phase (7D, imaginary octonion)
                    - "tower_out": Tower representation after G₂ processing
                    - "e8_continuous": Continuous E8 before quantization
                - **nucleus_sequence**: [B, L, 8] or [B, S, L, 8] per-level E8 codes
                - **num_levels**: Number of E8 residual levels used
                - **metrics**: Dict with quantization_error, etc.

        Shape Handling:
            - Input [B, D] → Output E8 [B, 8]
            - Input [B, S, D] → Output E8 [B, S, 8]

        Raises:
            ValueError: If input tensor has invalid shape (dim < 2 or dim > 3)
        """
        # Validate input shape
        if x.dim() < 2 or x.dim() > 3:
            raise ValueError(f"Input must be 2D [B, D] or 3D [B, S, D], got shape {x.shape}")

        # Delegate to hourglass encoder
        # The hourglass handles:
        # 1. Sequence dimension handling
        # 2. Exceptional hierarchy projection
        # 3. Tower processing (G₂ + Fano)
        # 4. E8 residual quantization
        result = self.hourglass.encode(
            x,
            return_intermediates=return_all,
            return_all=return_all,
            seq_len=seq_len,
        )

        # Hourglass.encode returns either:
        # - dict[str, Any] (if return_intermediates=True)
        # - tuple[Any, ...] (codes, dict[str, Any]) (if return_intermediates=False)
        if isinstance(result, dict):
            # Full intermediates returned
            intermediates = result
            encoder_states = result  # Alias for compatibility
        else:
            # Lightweight return: (codes, info_dict)
            codes, info_dict = result
            intermediates = info_dict.get("intermediates", {})
            encoder_states = intermediates

            # Add codes to top level
            intermediates["e8_codes"] = codes
            intermediates["e8_indices"] = codes  # Legacy alias

        # Normalize output keys for consistency
        # The hourglass may use either "e8_vq" or "e8_quantized" depending on path
        output: dict[str, Any] = {}

        # E8 VQ latent (primary output)
        if "e8_vq" in intermediates:
            output["e8_vq"] = intermediates["e8_vq"]
        elif "e8_quantized" in intermediates:
            output["e8_vq"] = intermediates["e8_quantized"]
            output["e8_quantized"] = intermediates["e8_quantized"]  # Keep both

        # Encoder states (hierarchy)
        output["encoder_states"] = encoder_states
        output["intermediates"] = intermediates  # Alias for backward compatibility

        # Nucleus sequence (per-level E8 codes)
        if "nucleus_sequence" in intermediates:
            output["nucleus_sequence"] = intermediates["nucleus_sequence"]

        # Number of E8 residual levels used
        if "num_levels" in intermediates:
            output["num_levels"] = intermediates["num_levels"]
        elif "nucleus_levels" in intermediates:
            output["num_levels"] = intermediates["nucleus_levels"]

        # Metrics (quantization error, etc.)
        if "metrics" in intermediates:
            output["metrics"] = intermediates["metrics"]

        return output

    def __repr__(self) -> str:
        """String representation."""
        config = self.hourglass.config
        return (
            f"Encoder(\n"
            f"  bulk_dim={config.bulk_dim},\n"
            f"  tower_dim={config.tower_dim},\n"
            f"  e8_vq_dim=8,\n"
            f"  training_levels={config.training_levels},\n"
            f"  inference_levels={config.inference_levels}\n"
            f")"
        )


__all__ = ["Encoder"]
