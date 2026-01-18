"""S⁷ Parallel Operations — TEST-ONLY COMPATIBILITY MODULE.

⚠️ WARNING: This module is for TEST COMPATIBILITY ONLY.
For production code, use the canonical implementations:

    # E8 quantization (production)
    from kagami_math.e8 import ResidualE8LatticeVQ, create_e8_quantizer

    # E8 roots
    from kagami_math.dimensions import get_e8_roots

    # S7 hierarchy
    from kagami_math.s7_augmented_hierarchy import S7AugmentedHierarchy

This file provides a simple test-oriented API used by:
- `tests/core/math/test_s7_parallel_ops.py`

The `ParallelE8Quantizer` here uses a simplified 240-root codebook (root indices 0-239)
which is NOT the same as the production `ResidualE8LatticeVQ` that uses true E8 lattice
points with variable-length residual encoding.

ARCHITECTURAL NOTE (Dec 13, 2025):
==================================
The production system uses `ResidualE8LatticeVQ` which:
- Quantizes to TRUE E8 lattice points (8 half-step integer coords)
- Supports 1-24 levels of residual refinement
- Uses varint byte encoding for optimal compression
- Is information-theoretically optimal (Viazovska 2016)

This module's `ParallelE8Quantizer` is a simplified version for testing Fano plane
and colony state operations without the full lattice protocol complexity.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami_math.dimensions import get_e8_roots
from kagami_math.fano_plane import FANO_LINES
from kagami_math.octonions import OctonionManifold


class BatchedS7StateManager(nn.Module):
    """Maintain 7 colony states as a single `(7, 8)` tensor."""

    DOMAIN_ORDER = ("spark", "forge", "flow", "nexus", "beacon", "grove", "crystal")

    def __init__(self, device: str = "cpu", dtype: torch.dtype = torch.float32):
        super().__init__()
        self._device = torch.device(device)

        # Canonical imaginary basis: colony i corresponds to e_{i+1}.
        states = torch.zeros(7, 8, device=self._device, dtype=dtype)
        for i in range(7):
            states[i, i + 1] = 1.0
        self.register_buffer("states", states)

    def update_colony(self, colony_idx: int, new_state: torch.Tensor) -> None:
        """Update one colony state and renormalize to unit norm."""
        idx = int(colony_idx)
        if idx < 0 or idx >= 7:
            raise ValueError("colony_idx must be in [0, 6]")

        x = new_state.to(device=self.states.device, dtype=self.states.dtype).reshape(-1)  # type: ignore[arg-type]
        if x.numel() != 8:
            raise ValueError("new_state must have 8 elements")

        x = F.normalize(x, dim=0, eps=1e-12)
        self.states[idx].copy_(x)  # type: ignore[index]

    def update_all(self, new_states: torch.Tensor) -> None:
        """Replace all colony states and renormalize each row to unit norm."""
        x = new_states.to(device=self.states.device, dtype=self.states.dtype)  # type: ignore[arg-type]
        if x.shape != (7, 8):
            raise ValueError("new_states must have shape (7, 8)")
        x = F.normalize(x, dim=-1, eps=1e-12)
        self.states.copy_(x)  # type: ignore[operator]

    def get_batched_for_e8(self) -> torch.Tensor:
        """Return states scaled to match E8 root norm √2."""
        return self.states * math.sqrt(2.0)  # type: ignore[operator]


class ParallelE8Quantizer(nn.Module):
    """Vectorized 240-root residual quantizer for small batches (e.g. 7 colonies).

    Returns:
        quantized: same shape as input (..., 8)
        indices_list: list[L] of indices in [0, 239] with shape (...,)
        info: dict with at least `quantization_error`

    The forward path is *hard* quantization; gradients use a straight-through
    estimator so tests can verify gradient flow.
    """

    def __init__(
        self,
        num_levels: int = 2,
        device: str = "cpu",
        use_compile: bool = False,
    ):
        super().__init__()
        if int(num_levels) < 1:
            raise ValueError("num_levels must be >= 1")

        self.num_levels = int(num_levels)
        self.use_compile = bool(use_compile)

        roots = get_e8_roots(device=device).to(torch.float32)
        self.register_buffer("roots", roots)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, list[torch.Tensor], dict[str, Any]]:
        if x.shape[-1] != 8:
            raise ValueError("ParallelE8Quantizer expects [..., 8]")

        original_shape = x.shape
        x_flat = x.reshape(-1, 8)

        qsum = torch.zeros_like(x_flat)
        residual = x_flat
        indices_list: list[torch.Tensor] = []

        for _level in range(self.num_levels):
            # Vectorized nearest-root: [N, 240] distances for N small.
            # NOTE (MPS): `torch.cdist` backward is not implemented on MPS.
            # We only need argmin, so squared distances are sufficient.
            r = self.roots
            res = residual.to(dtype=r.dtype)  # type: ignore[arg-type]
            res2 = (res * res).sum(dim=1, keepdim=True)  # [N, 1]
            r2 = (r * r).sum(dim=1).unsqueeze(0)  # type: ignore[operator]  # [1, 240]
            d2 = (res2 + r2 - 2.0 * (res @ r.transpose(0, 1))).clamp_min(0.0)  # type: ignore[operator]  # [N, 240]
            idx = d2.argmin(dim=-1)  # [N]
            y = self.roots.index_select(0, idx)  # type: ignore[operator]  # [N, 8]

            qsum = qsum + y
            residual = x_flat - qsum

            indices_list.append(idx.view(original_shape[:-1]))

        quantized = qsum.view(original_shape)

        # Straight-through estimator: forward uses hard quantized, backward is identity.
        quantized_ste = quantized + (x - x.detach())

        info: dict[str, Any] = {
            "quantization_error": float((x.detach() - quantized.detach()).pow(2).mean().item()),
            "num_levels": int(self.num_levels),
        }
        return quantized_ste, indices_list, info

    @staticmethod
    def indices_to_bytes(indices_list: list[torch.Tensor]) -> bytes:
        """Serialize indices as a tiny test-oriented byte payload.

        Format:
        - 1 byte: number of levels L
        - L * N bytes: uint8 indices for N entries (N=7 for colony batch)
        """
        if not indices_list:
            raise ValueError("indices_list cannot be empty")

        out = bytearray([len(indices_list) & 0xFF])
        for idx in indices_list:
            flat = idx.detach().to("cpu").reshape(-1).to(torch.int64)
            if flat.numel() == 0:
                continue
            if int(flat.min()) < 0 or int(flat.max()) >= 240:
                raise ValueError("indices must be in [0, 239]")
            out.extend(int(v) & 0xFF for v in flat.tolist())
        return bytes(out)


class ParallelFanoProducts(nn.Module):
    """Compute per-Fano-line products and alignments for 7 colony states."""

    def __init__(self, device: str = "cpu"):
        super().__init__()
        self._device = torch.device(device)
        self._manifold = OctonionManifold()

        # Convert 1-indexed (e₁..e₇) to 0-indexed colony slots (0..6)
        i0 = torch.tensor(
            [line[0] - 1 for line in FANO_LINES], dtype=torch.long, device=self._device
        )
        j0 = torch.tensor(
            [line[1] - 1 for line in FANO_LINES], dtype=torch.long, device=self._device
        )
        k0 = torch.tensor(
            [line[2] - 1 for line in FANO_LINES], dtype=torch.long, device=self._device
        )

        self.register_buffer("line_i", i0)
        self.register_buffer("line_j", j0)
        self.register_buffer("line_k", k0)

    def forward(self, states: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if states.shape != (7, 8):
            raise ValueError("states must have shape (7, 8)")

        s = states.to(device=self.line_i.device, dtype=torch.float32)  # type: ignore[arg-type]

        a = s.index_select(0, self.line_i)  # type: ignore[arg-type]
        b = s.index_select(0, self.line_j)  # type: ignore[arg-type]
        c = s.index_select(0, self.line_k)  # type: ignore[arg-type]

        products = self._manifold.cayley_dickson_mul(a, b)  # [7, 8]
        alignments = F.cosine_similarity(products, c, dim=-1)  # [7]
        return products, alignments

    def compute_fano_loss(self, states: torch.Tensor) -> torch.Tensor:
        """A bounded [0, 1] loss measuring Fano consistency."""
        _products, alignments = self.forward(states)
        loss = (1.0 - alignments.clamp(-1.0, 1.0)).mean() * 0.5
        return loss.clamp(0.0, 1.0)


@dataclass
class FusedColonyWorldModelBridgeOutput:
    quantized: torch.Tensor
    indices: list[torch.Tensor]
    e8_info: dict[str, Any]
    fano_products: torch.Tensor
    fano_alignments: torch.Tensor
    fano_loss: torch.Tensor


class FusedColonyWorldModelBridge(nn.Module):
    """Convenience wrapper: states → E8 quantization → Fano products."""

    def __init__(self, num_levels: int = 2, device: str = "cpu"):
        super().__init__()
        self.s7 = BatchedS7StateManager(device=device)
        self.e8 = ParallelE8Quantizer(num_levels=num_levels, device=device, use_compile=False)
        self.fano = ParallelFanoProducts(device=device)

    def forward(self, states: torch.Tensor | None = None) -> FusedColonyWorldModelBridgeOutput:
        x = self.s7.states if states is None else states
        quantized, indices, e8_info = self.e8(x)
        products, alignments = self.fano(quantized.detach())
        fano_loss = self.fano.compute_fano_loss(quantized.detach())
        return FusedColonyWorldModelBridgeOutput(
            quantized=quantized,
            indices=indices,
            e8_info=e8_info,
            fano_products=products,
            fano_alignments=alignments,
            fano_loss=fano_loss,
        )


__all__ = [
    "BatchedS7StateManager",
    "FusedColonyWorldModelBridge",
    "FusedColonyWorldModelBridgeOutput",
    "ParallelE8Quantizer",
    "ParallelFanoProducts",
]
