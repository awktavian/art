"""Fano Coherence Estimator — Colony Alignment via TRUE Octonion Multiplication.

SCIENTIFIC CLARIFICATION (December 8, 2025):
=============================================
This module computes FANO COHERENCE using the canonical `multiply_8d` from
`kagami/core/world_model/manifolds/octonion.py`. This is NOT IIT's Φ.

TRUE IIT Φ would require:
- Computing integrated information over ALL 2^n bipartitions (exponential)
- Finding the Minimum Information Partition (NP-hard)
- Earth Mover's Distance on probability distributions

What we compute:
- TRUE octonion multiplication via canonical `multiply_8d`
- All 7 × B Fano products in a SINGLE batched operation
- Coherence = mean alignment across Fano lines

S⁷ PARALLELISM (Dec 8, 2025):
=============================
Uses same indexing pattern as `ParallelFanoProducts` but supports batch dim.
All [B, 7] products computed in ONE multiply_8d call (no Python loops).

Created: November 30, 2025
Updated: December 8, 2025 — Fully batched S⁷ parallel, uses canonical multiply_8d
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami_math.fano_plane import FANO_LINES
from kagami_math.octonions import multiply_8d


class FanoCoherenceEstimator(nn.Module):
    """Estimates colony coherence via batched Fano plane multiplication.

    USES: Canonical `multiply_8d` from `manifolds/octonion.py`
    PATTERN: Same index tensors as `ParallelFanoProducts`, but with batch support

    This is NOT IIT's integrated information Φ (which is NP-hard).
    """

    # Buffer type declarations
    line_i: torch.Tensor
    line_j: torch.Tensor
    line_k: torch.Tensor

    def __init__(self, dim: int = 8):
        super().__init__()
        self.dim = dim

        # Fano line indices (0-indexed) — same as ParallelFanoProducts
        line_i = torch.tensor([line[0] - 1 for line in FANO_LINES], dtype=torch.long)
        line_j = torch.tensor([line[1] - 1 for line in FANO_LINES], dtype=torch.long)
        line_k = torch.tensor([line[2] - 1 for line in FANO_LINES], dtype=torch.long)

        self.register_buffer("line_i", line_i)
        self.register_buffer("line_j", line_j)
        self.register_buffer("line_k", line_k)

    def forward(self, colony_states: torch.Tensor) -> torch.Tensor:
        """Compute Fano coherence — FULLY BATCHED S⁷ PARALLEL.

        All [B, 7] Fano products computed in ONE multiply_8d call.
        No Python loops — pure tensor ops for torch.compile compatibility.

        Args:
            colony_states: [B, 7, D] tensor of colony embeddings.
                           D=8 uses full octonion multiplication.
                           D<8: padded to 8D.

        Returns:
            coherence: [B, 1] (or [B, S, 1] if a sequence dim is provided)
                      scalar coherence estimate in [0, 1].
        """
        # Support both:
        # - [B, 7, D]
        # - [B, S, 7, D] (sequence of colony states)
        is_sequence = colony_states.dim() == 4
        if is_sequence:
            B, S, N, D = colony_states.shape
            colony_states_flat = colony_states.reshape(B * S, N, D)
        else:
            B = colony_states.shape[0]
            D = colony_states.shape[-1]
            colony_states_flat = colony_states

        # Normalize states for scale-invariant coherence
        states = F.normalize(colony_states_flat, p=2, dim=-1)  # [B*?, 7, D]

        # Ensure 8D for octonion multiplication
        if D < 8:
            states_8d = F.pad(states, (0, 8 - D))  # [B, 7, 8]
        elif D > 8:
            states_8d = states[..., :8]
        else:
            states_8d = states

        # =========================================================
        # S⁷ PARALLEL: Gather all [B, 7] inputs at once
        # =========================================================
        # Same pattern as ParallelFanoProducts but with batch dim
        states_i = states_8d[:, self.line_i, :]  # [B*?, 7, 8]
        states_j = states_8d[:, self.line_j, :]  # [B*?, 7, 8]
        states_k = states_8d[:, self.line_k, :]  # [B*?, 7, 8]

        # Flatten for batched multiply: [B*7, 8]
        B_flat = states_8d.shape[0]
        states_i_flat = states_i.reshape(B_flat * 7, 8)
        states_j_flat = states_j.reshape(B_flat * 7, 8)

        # ONE multiply_8d call for ALL [B, 7] products
        products_flat = multiply_8d(states_i_flat, states_j_flat)  # [B*7, 8]

        # Reshape back: [B, 7, 8]
        products = products_flat.reshape(B_flat, 7, 8)

        # Compute alignment: cosine similarity (abs for ±e_k)
        products_norm = F.normalize(products, p=2, dim=-1)
        states_k_norm = F.normalize(states_k, p=2, dim=-1)
        alignments = (products_norm * states_k_norm).sum(dim=-1).abs()  # [B, 7]

        # Mean across 7 Fano lines
        coherence_raw = alignments.mean(dim=-1, keepdim=True)  # [B, 1]

        # Light sigmoid for smoothness
        coherence = torch.sigmoid((coherence_raw - 0.5) * 5.0)

        if is_sequence:
            return coherence.view(B, S, 1)
        return coherence

    def compute_full_octonion_coherence(self, core_state_octonion: torch.Tensor) -> torch.Tensor:
        """Compute coherence using full octonion state.

        Implements proper octonion coherence calculation:
        - Real component represents magnitude/stability
        - Imaginary components represent phase/coherence
        - Coherence = normalized magnitude of imaginary part relative to total norm

        Args:
            core_state_octonion: [B, 8] full octonion state [real, i1, i2, i3, i4, i5, i6, i7].

        Returns:
            coherence: [B, 1] coherence estimate [0, 1]
        """
        # Extract real and imaginary components
        imaginary = core_state_octonion[..., 1:]  # [B, 7]

        # Compute magnitudes
        total_norm = core_state_octonion.norm(dim=-1, keepdim=True)  # [B, 1]
        imag_norm = imaginary.norm(dim=-1, keepdim=True)  # [B, 1]

        # Coherence = ratio of imaginary magnitude to total magnitude
        # High coherence when imaginary components dominate (phase alignment)
        # Low coherence when real component dominates (magnitude without phase structure)
        coherence_ratio = imag_norm / (total_norm + 1e-8)

        # Also consider phase alignment: how well imaginary components align
        # Use cosine similarity between imaginary components as phase coherence
        if imaginary.shape[-1] > 1:
            # Normalize imaginary components
            imag_normalized = F.normalize(imaginary, p=2, dim=-1)  # [B, 7]
            # Average pairwise cosine similarity (measures phase alignment)
            # For 7D, compute mean of all pairwise dot products
            phase_coherence = (
                (imag_normalized.unsqueeze(-2) * imag_normalized.unsqueeze(-1))
                .sum(dim=-1)
                .mean(dim=-1, keepdim=True)
            )  # [B, 1]
            # Combine magnitude ratio and phase alignment
            coherence = coherence_ratio * (0.5 + 0.5 * phase_coherence)
        else:
            coherence = coherence_ratio

        # Bound to [0, 1] with sigmoid
        return torch.sigmoid(coherence * 5.0)


# No backward compatibility alias - use FanoCoherenceEstimator directly
