"""Fast Hadamard Transform for E8 quantization preprocessing.

Implements QuIP#-style Hadamard preprocessing to decorrelate features before
E8 lattice quantization. The Hadamard transform is orthogonal (H^T H = I) and
fast (O(n log n)), making it ideal for preprocessing.

Theory:
-------
The Hadamard matrix H_n is recursively defined:
    H_1 = [1]
    H_n = H_{n/2} ⊗ H_2  where H_2 = [[1, 1], [1, -1]] / sqrt(2)

For n = 8 (E8 lattice):
    H_8 = H_4 ⊗ H_2 = H_2 ⊗ H_2 ⊗ H_2

Properties:
    - Orthogonal: H^T H = I
    - Self-inverse (up to scale): H H = n I
    - Fast: O(n log n) via FFT-like recursion
    - Decorrelates correlated inputs (like Fourier transform)

Benefits for Quantization:
    1. Decorrelates features before quantization
    2. Reduces quantization error on correlated data
    3. Production-validated in QuIP# for LLM quantization
    4. Zero computational overhead (O(n log n))

References:
    - Tseng et al. (2024): QuIP# - Hadamard preprocessing for E8 quantization
    - Hadamard (1893): Original matrix construction
    - Pratt et al. (1969): Fast Hadamard Transform algorithm

Created: December 14, 2025
"""

from __future__ import annotations

import math
from typing import cast

import torch
import torch.nn as nn


def _next_power_of_2(n: int) -> int:
    """Find the next power of 2 >= n."""
    return 1 << (n - 1).bit_length()


def _is_power_of_2(n: int) -> bool:
    """Check if n is a power of 2."""
    return n > 0 and (n & (n - 1)) == 0


def _fast_hadamard_transform_core(x: torch.Tensor) -> torch.Tensor:
    """Fast Hadamard Transform core (non-JIT).

    Implements Cooley-Tukey-style recursive algorithm:
        H_n = H_{n/2} ⊗ H_2

    Requires n to be a power of 2.

    Args:
        x: [..., n] tensor where n is power of 2

    Returns:
        Transformed tensor (NOT normalized)
    """
    n = x.shape[-1]
    x = x.clone()  # Avoid in-place issues
    h = 1
    while h < n:
        # Butterfly operation: process pairs (j, j+h)
        # Reshape to expose the pair structure: [..., n//(2h), 2, h]
        # This groups elements as: [a0...ah-1, b0...bh-1, a0...ah-1, b0...bh-1, ...]
        x_view = x.reshape(*x.shape[:-1], n // (2 * h), 2, h)
        # Apply butterfly: (a, b) -> (a+b, a-b)
        a = x_view[..., 0, :].clone()
        b = x_view[..., 1, :].clone()
        x_view[..., 0, :] = a + b
        x_view[..., 1, :] = a - b
        x = x_view.reshape(*x.shape[:-1], n)
        h *= 2
    return x


def hadamard_transform(x: torch.Tensor, dim: int = -1, normalize: bool = True) -> torch.Tensor:
    """Fast Hadamard Transform.

    Applies orthogonal Hadamard transform along specified dimension.
    If dimension is not a power of 2, uses largest power-of-2 block and
    leaves remainder untransformed (identity). This preserves orthogonality.

    Args:
        x: Input tensor
        dim: Dimension to transform (default -1)
        normalize: Apply normalization to make transform orthogonal (default True)

    Returns:
        Transformed tensor (same shape as input, orthogonal transform if normalize=True)

    Examples:
        >>> x = torch.randn(32, 8)
        >>> x_h = hadamard_transform(x)  # Transform last dimension
        >>> # Verify orthogonality
        >>> assert torch.allclose(
        ...     hadamard_transform(hadamard_transform(x)), x, atol=1e-5
        ... )
    """
    # Move target dimension to end
    if dim != -1:
        x = x.transpose(dim, -1)

    n = x.shape[-1]

    # Handle power-of-2 sizes directly
    if _is_power_of_2(n):
        x_transformed = _fast_hadamard_transform_core(x)
        if normalize:
            x_transformed = x_transformed / math.sqrt(n)
    else:
        # For non-power-of-2, transform largest power-of-2 block
        # and leave remainder as identity. This preserves orthogonality.
        n_block = 1 << ((n - 1).bit_length() - 1)  # Largest power of 2 <= n

        # Transform the block
        x_block = x[..., :n_block]
        x_block_transformed = _fast_hadamard_transform_core(x_block)
        if normalize:
            x_block_transformed = x_block_transformed / math.sqrt(n_block)

        # Keep remainder unchanged (identity transform)
        x_remainder = x[..., n_block:]

        # Concatenate
        x_transformed = torch.cat([x_block_transformed, x_remainder], dim=-1)

    # Restore dimension order
    if dim != -1:
        x_transformed = x_transformed.transpose(dim, -1)

    return x_transformed


def inverse_hadamard_transform(
    x: torch.Tensor, dim: int = -1, normalize: bool = True
) -> torch.Tensor:
    """Inverse Fast Hadamard Transform.

    The Hadamard transform is self-inverse (H^T = H), so this is identical
    to the forward transform.

    Args:
        x: Transformed tensor
        dim: Dimension to transform (default -1)
        normalize: Apply normalization (default True)

    Returns:
        Inverse-transformed tensor
    """
    # Hadamard is self-inverse!
    return hadamard_transform(x, dim=dim, normalize=normalize)


class HadamardE8Quantizer(nn.Module):
    """E8 lattice quantizer with Hadamard preprocessing.

    Wraps ResidualE8LatticeVQ with Hadamard decorrelation preprocessing,
    following the QuIP# design:

        encode: x → H(x) → E8_quantize(H(x)) → codes
        decode: codes → E8_dequantize(codes) → H^{-1}(...) → x

    The Hadamard transform decorrelates features before quantization,
    reducing quantization error on correlated inputs.

    Architecture:
        Input [B, 8]
            ↓
        Hadamard Transform [B, 8]
            ↓
        ResidualE8LatticeVQ
            ↓
        Codes (list of [B, 8] int64)
            ↓
        (decode path)
            ↓
        ResidualE8LatticeVQ.decode
            ↓
        Inverse Hadamard [B, 8]
            ↓
        Output [B, 8]

    Benefits:
        - Better quantization on correlated features
        - Zero overhead (O(n log n) preprocessing)
        - Production-validated (QuIP# for LLMs)
        - Drop-in replacement for ResidualE8LatticeVQ
    """

    def __init__(self, e8_quantizer: nn.Module):
        """Initialize Hadamard-wrapped E8 quantizer.

        Args:
            e8_quantizer: ResidualE8LatticeVQ instance (or compatible)
        """
        super().__init__()
        self.e8_quantizer: nn.Module = e8_quantizer

    def forward(self, x: torch.Tensor, num_levels: int | None = None) -> dict[str, torch.Tensor]:
        """Encode with Hadamard preprocessing.

        Args:
            x: [..., 8] input tensor
            num_levels: Number of residual levels (passed to quantizer)

        Returns:
            dict[str, torch.Tensor] with keys:
                - "quantized": the quantized output tensor [..., 8]
                - "loss": the commitment loss (scalar)
                - "indices": the codebook indices [..., L, 8] where L is number of levels
                - "perplexity": the perplexity metric (scalar)
        """
        if x.shape[-1] != 8:
            raise ValueError("HadamardE8Quantizer expects [..., 8] input")

        # Apply Hadamard preprocessing
        x_hadamard = hadamard_transform(x, dim=-1, normalize=True)

        # Quantize in Hadamard space
        result = self.e8_quantizer(x_hadamard, num_levels=num_levels)
        quantized_hadamard = result["quantized"]

        # Transform back to original space for gradient flow
        # (codes remain in Hadamard space for storage)
        quantized = inverse_hadamard_transform(quantized_hadamard, dim=-1, normalize=True)

        return {
            "quantized": quantized,
            "loss": result["loss"],
            "indices": result["indices"],
            "perplexity": result["perplexity"],
        }

    def decode(self, codes: list[torch.Tensor]) -> torch.Tensor:
        """Decode from Hadamard-space codes.

        Args:
            codes: List of [..., 8] int64 code tensors

        Returns:
            [..., 8] reconstructed tensor in original space
        """
        # Decode in Hadamard space
        decoded_hadamard = cast(torch.Tensor, self.e8_quantizer.decode(codes))  # type: ignore[operator]

        # Transform back to original space
        decoded = inverse_hadamard_transform(decoded_hadamard, dim=-1, normalize=True)

        return decoded

    def get_stats(self) -> dict:
        """Get quantizer statistics."""
        stats = cast(dict, self.e8_quantizer.get_stats())  # type: ignore[operator]
        stats["hadamard_preprocessing"] = True
        return stats


def create_hadamard_e8_quantizer(
    max_levels: int = 16,
    min_levels: int = 1,
    initial_scale: float = 2.0,
    adaptive_levels: bool = True,
) -> HadamardE8Quantizer:
    """Factory function for Hadamard-wrapped E8 quantizer.

    Args:
        max_levels: Maximum residual levels
        min_levels: Minimum residual levels
        initial_scale: Initial quantization scale
        adaptive_levels: Use adaptive level selection

    Returns:
        Configured HadamardE8Quantizer
    """
    from kagami_math.e8_lattice_protocol import (
        E8LatticeResidualConfig,
        ResidualE8LatticeVQ,
    )

    config = E8LatticeResidualConfig(
        max_levels=max_levels,
        min_levels=min_levels,
        initial_scale=initial_scale,
        adaptive_levels=adaptive_levels,
    )
    base_quantizer = ResidualE8LatticeVQ(config)

    return HadamardE8Quantizer(base_quantizer)


__all__ = [
    "HadamardE8Quantizer",
    "create_hadamard_e8_quantizer",
    "hadamard_transform",
    "inverse_hadamard_transform",
]
