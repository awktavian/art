"""Optimized Fano Plane Tensor Operations for PyTorch.

This module provides high-performance, batched tensor operations for Fano plane geometry.
It serves as the single source of truth for neural implementation of octonion multiplication
structure in the system, replacing ad-hoc table building in individual modules.

It uses the canonical definitions from `kagami.math.fano_plane`.
"""

from __future__ import annotations

import logging
import threading

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from kagami_math.fano_plane import FANO_SIGNS

logger = logging.getLogger(__name__)

_FANO_TABLE_CACHE: dict[str, torch.Tensor] = {}
_CACHE_LOCK = threading.Lock()


def get_fano_multiplication_table(device: torch.device | None = None) -> torch.Tensor:
    """Get the 7x7 Fano multiplication table as a tensor.

    Returns:
        LongTensor[7, 7]: Table where table[i, j] = k means e_(i+1) * e_(j+1) = +/- e_(k+1).
                         Values are 0-indexed (0-6).
                         Diagonal is -1 (representing scalar real part).
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not available for Fano tensor operations")

    cache_key = f"mult_table_{device}"

    # Thread-safe cache access with double-check pattern
    if cache_key in _FANO_TABLE_CACHE:
        return _FANO_TABLE_CACHE[cache_key]

    with _CACHE_LOCK:
        # Double-check inside lock to avoid race condition
        if cache_key in _FANO_TABLE_CACHE:
            return _FANO_TABLE_CACHE[cache_key]

        # Initialize with -1 (undefined/scalar)
        table = torch.full((7, 7), -1, dtype=torch.long)

        for (i, j), (k, _) in FANO_SIGNS.items():
            # Convert 1-indexed to 0-indexed
            table[i - 1, j - 1] = k - 1

        if device:
            table = table.to(device)

        _FANO_TABLE_CACHE[cache_key] = table
        return table


def get_fano_sign_table(device: torch.device | None = None) -> torch.Tensor:
    """Get the 7x7 Fano multiplication sign table as a tensor.

    Returns:
        FloatTensor[7, 7]: Table of signs (+1.0, -1.0).
                          Diagonal is -1.0 (e_i * e_i = -1).
                          Undefined entries are 0.0.
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not available for Fano tensor operations")

    cache_key = f"sign_table_{device}"

    # Thread-safe cache access with double-check pattern
    if cache_key in _FANO_TABLE_CACHE:
        return _FANO_TABLE_CACHE[cache_key]

    with _CACHE_LOCK:
        # Double-check inside lock to avoid race condition
        if cache_key in _FANO_TABLE_CACHE:
            return _FANO_TABLE_CACHE[cache_key]

        signs = torch.zeros((7, 7), dtype=torch.float32)

        for (i, j), (_, sign) in FANO_SIGNS.items():
            signs[i - 1, j - 1] = float(sign)

        # Diagonal is -1 (scalar real part)
        for i in range(7):
            signs[i, i] = -1.0

        if device:
            signs = signs.to(device)

        _FANO_TABLE_CACHE[cache_key] = signs
        return signs
