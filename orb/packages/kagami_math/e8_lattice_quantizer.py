"""E8 lattice quantizer (nearest lattice point) and utilities.

This is the *theoretical* E8 lattice (Viazovska 2017):
  E8 = D8 ∪ (D8 + (1/2,...,1/2))

Where:
  D8 = { z ∈ Z^8 : sum(z) is even }.

We implement a fast, vectorized nearest-point algorithm by comparing the nearest
point in each coset:
  - nearest in D8
  - nearest in D8 + 1/2
and choosing the closer.
"""

from __future__ import annotations

import torch

# Tiebreaker epsilon for deterministic nearest-point selection
_TIEBREAKER_EPSILON = 1e-10


def _nearest_d8(x: torch.Tensor) -> torch.Tensor:
    """Nearest point in D8 to x (vectorized).

    Algorithm (Conway & Sloane 1999):
    1. Round all coordinates to nearest integer → z
    2. If sum(z) is even → return z (already in D8)
    3. If sum(z) is odd:
       - Try all 8 possible single-coordinate flips (±1)
       - Choose the one with minimum distance to x

    Args:
        x: [..., 8] float tensor
    Returns:
        z: [..., 8] float tensor in Z^8 with even coordinate sum
    """
    if x.shape[-1] != 8:
        raise ValueError("E8 lattice lives in R^8")

    z = torch.round(x)
    parity = z.sum(dim=-1).to(torch.int64) & 1  # 1 if odd
    if not torch.any(parity):
        return z

    # If parity is odd, try all 8 single-coordinate flips and choose minimum distance
    # Vectorized: create [batch, 8, 8] tensor with all 8 candidates per batch element
    batch_shape = x.shape[:-1]
    # Avoid .item() to keep graph compile-friendly
    batch_size = 1
    for dim in batch_shape:
        batch_size *= dim

    x_flat = x.reshape(batch_size, 8)
    z_flat = z.reshape(batch_size, 8)
    parity_flat = parity.reshape(batch_size)

    # Create candidates: [batch, 8, 8]
    # For each batch element, candidate i flips coordinate i by ±1
    candidates = z_flat.unsqueeze(1).expand(-1, 8, -1).clone()  # [batch, 8, 8]

    # For each candidate i, flip coordinate i
    # Direction: flip toward x (if x[i] > z[i], flip up; else flip down)
    diff = x_flat - z_flat  # [batch, 8]
    flip_dir = torch.where(diff >= 0, 1.0, -1.0)  # [batch, 8]

    # Apply flips: candidates[b, i, i] += flip_dir[b, i]
    flip_mask = torch.eye(8, device=x.device, dtype=x.dtype)  # [8, 8]
    candidates = candidates + flip_dir.unsqueeze(1) * flip_mask  # [batch, 8, 8]

    # Compute distances: [batch, 8]
    distances = (x_flat.unsqueeze(1) - candidates).pow(2).sum(dim=-1)  # [batch, 8]

    # Add tiny tiebreaker for deterministic selection
    tiebreaker = torch.arange(8, device=x.device, dtype=x.dtype) * _TIEBREAKER_EPSILON
    distances = distances + tiebreaker

    # Select minimum distance candidate for odd-parity elements
    best_idx = distances.argmin(dim=-1)  # [batch]

    # Gather best candidates using torch.where for compile-friendliness
    # Build selection tensor: [batch, 8]
    best_candidates = torch.gather(
        candidates,  # [batch, 8, 8]
        dim=1,
        index=best_idx.unsqueeze(-1).unsqueeze(-1).expand(-1, 1, 8),
    ).squeeze(1)  # [batch, 8]

    # Apply correction only for odd parity elements
    odd_mask = parity_flat.bool().unsqueeze(-1)  # [batch, 1]
    z_fixed_flat = torch.where(odd_mask, best_candidates, z_flat)

    return z_fixed_flat.reshape(x.shape)


def nearest_e8(x: torch.Tensor) -> torch.Tensor:
    """Nearest point in the E8 lattice to x (vectorized).

    Args:
        x: [..., 8] float tensor
    Returns:
        y: [..., 8] float tensor in E8
    """
    z0 = _nearest_d8(x)  # D8 candidate
    z1 = _nearest_d8(x - 0.5) + 0.5  # shifted coset candidate

    d0 = (x - z0).pow(2).sum(dim=-1)
    d1 = (x - z1).pow(2).sum(dim=-1)
    choose1 = d1 < d0
    return torch.where(choose1.unsqueeze(-1), z1, z0)


def e8_to_half_step_ints(y: torch.Tensor) -> torch.Tensor:
    """Convert E8 lattice point to integer coordinates in half-step units.

    For y in E8, a = 2y has:
      - all coordinates even OR all coordinates odd
      - sum(a) divisible by 4

    Returns:
        a: [..., 8] int64 tensor
    """
    a = torch.round(y * 2.0).to(torch.int64)
    return a


def half_step_ints_to_e8(a: torch.Tensor) -> torch.Tensor:
    """Convert half-step integer coords back to float E8 lattice point."""
    if a.shape[-1] != 8:
        raise ValueError("E8 lattice lives in R^8")
    return a.to(torch.float32) / 2.0
