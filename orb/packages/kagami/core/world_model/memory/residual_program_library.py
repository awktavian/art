"""Residual Catastrophe Program Library — E8 Residual Codes for Program Selection.

ARCHITECTURE (December 3, 2025):
================================
The original CatastropheProgramLibrary uses SINGLE-LEVEL E8 indexing (240 programs).
This module adds RESIDUAL E8 support, enabling 240^L program states:

    L=1:  240 programs (7.9 bits) — original capacity
    L=2:  57,600 programs (15.8 bits) — fine-grained selection
    L=4:  3.3B programs (31.6 bits) — rich program space
    L=8:  1.1e19 programs (63.3 bits) — virtually unlimited

KEY INSIGHT:
============
Programs are points in a hierarchical space:
- Level 0 (base): 240 discrete program "families"
- Level 1+: Residual refinements within families

This matches how catastrophe manifolds work:
- Base level = which catastrophe type
- Residual = specific control parameters within that type

ARCHITECTURE:
=============

    Query (14D G₂) → Project to 8D → E8 Residual Quantization
                                              ↓
    Level 0: Select from 240 base programs (catastrophe families)
    Level 1: Select residual refinement (parameter variations)
    Level 2+: Further refinement (nuanced behaviors)
                                              ↓
    Final: Weighted sum of level embeddings with √240 decay

SCIENTIFIC CLARIFICATION (December 7, 2025):
============================================
The documentation previously claimed this implements "Solomonoff prior P(p) = 2^{-K(p)}".
This is INCORRECT. True Solomonoff induction requires computing Kolmogorov complexity
K(p), which is PROVABLY INCOMPUTABLE (Turing 1936, Chaitin 1966).

What we actually implement:
- A LEARNED complexity score (not K(x))
- Soft attention over program embeddings
- MDL-inspired simplicity bias via reward-based updates

The "prior" is a learned parameter, not a universal distribution. This is a
practical neural approximation that shares conceptual motivation with MDL but
lacks the theoretical guarantees of algorithmic information theory.

Created: December 3, 2025
Updated: December 7, 2025 — Scientific accuracy corrections
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.catastrophe_constants import (
    MAX_CONTROL_PARAMS,
    get_codim,
)
from kagami_math.dimensions import (
    F4_DIM,
    G2_DIM,
    OCTONION_EMBEDDING_DIM,
    generate_e8_roots,
)

from kagami.core.world_model.memory.episodic_memory import safe_orthogonal_init

logger = logging.getLogger(__name__)

# Constants
SQRT_240 = math.sqrt(240)  # ~15.49 — optimal decay factor
CATASTROPHE_CODIM = {i: get_codim(i) for i in range(7)}


@dataclass
class ResidualProgramConfig:
    """Configuration for Residual Catastrophe Program Library."""

    # Core dimensions
    num_base_programs: int = 240  # E₈ root count (level 0)
    program_dim: int = F4_DIM  # 52D embedding per program
    query_dim: int = G2_DIM  # 14D observation

    # === RESIDUAL LEVELS ===
    # UPDATED (Dec 6, 2025): Increased to match system-wide config
    max_levels: int = 16  # Maximum residual levels (capacity ceiling)
    training_levels: int = 8  # Levels during training
    # IMPORTANT: Inference defaults to training depth for ProgramLibrary.
    # Unlike E8 lattice VQ, deeper ProgramLibrary levels have learnable params.
    # Setting inference_levels > training_levels would use untrained weights.
    inference_levels: int = 8  # Levels during inference (must be ≤ trained levels)
    adaptive_levels: bool = True  # Stop early when residual is small
    residual_threshold: float = 0.001  # Stop when attention entropy is low (tighter)

    # === OPTIMAL SCALING ===
    level_decay: float = SQRT_240  # √240 — mathematically optimal

    # === CATASTROPHE INTEGRATION ===
    max_control_params: int = MAX_CONTROL_PARAMS  # (a, b, c, d)

    # === LEARNED SIMPLICITY BIAS (NOT true Solomonoff prior) ===
    # NOTE: These control a learned MDL-inspired heuristic, not a universal prior
    initial_complexity: float = 1.0
    min_complexity: float = 0.1
    max_complexity: float = 10.0
    complexity_per_level: float = 0.5  # Additional cost per residual level

    # === TEMPERATURE ===
    temperature: float = 1.0
    temperature_per_level: float = 0.8  # Sharper at deeper levels

    # === COLONY AFFINITY ===
    use_learned_affinity: bool = True
    affinity_temperature: float = 2.0

    # === TOP-K ===
    top_k: int = 5


class G2ToE8Projection(nn.Module):
    """Project from G₂ (14D) to E₈ space (8D) for residual quantization."""

    def __init__(self, input_dim: int = G2_DIM, output_dim: int = OCTONION_EMBEDDING_DIM):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.GELU(),
            nn.Linear(32, output_dim),
        )
        # MPS-safe orthogonal init: do on CPU first (QR not implemented on MPS)
        assert isinstance(self.proj[0], nn.Linear)
        assert isinstance(self.proj[2], nn.Linear)
        self.proj[0].weight.data = safe_orthogonal_init(self.proj[0].weight, gain=1.0)
        self.proj[2].weight.data = safe_orthogonal_init(self.proj[2].weight, gain=1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        projected = self.proj(x)
        # Normalize to E8 sphere (norm √2)
        return F.normalize(projected, p=2, dim=-1) * math.sqrt(2.0)


class ResidualCatastropheProgramLibrary(nn.Module):
    """Program Library with Residual E8 Addressing.

    This is an enhanced version of CatastropheProgramLibrary that supports
    VARIABLE-LENGTH residual E8 codes for fine-grained program selection.

    CAPACITY SCALING:
    - 1 level:  240 programs
    - 2 levels: 57,600 programs
    - 4 levels: 3.3 billion programs
    - 8 levels: 1.1e19 programs

    HIERARCHICAL STRUCTURE:
    - Level 0: Base program families (240 catastrophe configurations)
    - Level 1+: Residual refinements (variations within families)

    SELECTION ALGORITHM:
    1. Project observation to E8 space
    2. Find nearest E8 root at each level (residual quantization)
    3. Lookup level embeddings
    4. Sum with √240 decay factor
    5. Apply catastrophe control params
    """

    def __init__(self, config: ResidualProgramConfig | None = None) -> None:
        super().__init__()
        self.config = config or ResidualProgramConfig()

        # === E₈ ROOTS (FIXED KEYS) ===
        e8_roots = generate_e8_roots()
        self.register_buffer("roots", e8_roots)  # [240, 8]
        self.register_buffer("roots_normalized", F.normalize(e8_roots, p=2, dim=-1))

        # === HIERARCHICAL PROGRAM EMBEDDINGS ===
        # Each level has 240 learnable embeddings
        self.level_embeddings = nn.ParameterList(
            [
                nn.Parameter(torch.randn(240, self.config.program_dim) * 0.02)
                for _ in range(self.config.max_levels)
            ]
        )

        # === LEARNABLE CATASTROPHE CONTROL PARAMETERS ===
        # Level 0: Base control params per program
        self.base_control_params = nn.Parameter(
            torch.randn(240, self.config.max_control_params) * 0.1
        )

        # Level 1+: Residual control params (smaller adjustments)
        self.residual_control_params = nn.ParameterList(
            [
                nn.Parameter(torch.randn(240, self.config.max_control_params) * 0.02)
                for _ in range(self.config.max_levels - 1)
            ]
        )

        # === LEARNABLE COLONY AFFINITY ===
        if self.config.use_learned_affinity:
            init_affinity = torch.zeros(240, 7)
            for i in range(240):
                init_affinity[i, i % 7] = 1.0  # Round-robin init
            self.affinity_logits = nn.Parameter(init_affinity)

        # === LEARNED COMPLEXITY SCORES (NOT Kolmogorov complexity) ===
        # NOTE (Dec 7, 2025): True K(x) is incomputable. These are learned scalars
        # acting as simplicity biases, updated via gradient descent. They approximate
        # MDL behavior but have no theoretical connection to algorithmic information theory.
        # Base complexity per program family
        self.base_complexity = nn.Parameter(
            torch.full((240,), math.log(self.config.initial_complexity))
        )
        # Residual complexity (learned per level)
        self.residual_complexity = nn.ParameterList(
            [
                nn.Parameter(torch.zeros(240) + self.config.complexity_per_level * (l + 1))
                for l in range(self.config.max_levels - 1)
            ]
        )

        # === LEARNABLE DECAY ===
        self.log_decay = nn.Parameter(torch.tensor(math.log(self.config.level_decay)))

        # === G₂ PROJECTION ===
        self.g2_proj = G2ToE8Projection(
            input_dim=self.config.query_dim,
            output_dim=OCTONION_EMBEDDING_DIM,
        )

        # === REFINEMENT NETWORK ===
        # Optional post-selection refinement
        self.refine = nn.Sequential(
            nn.Linear(self.config.program_dim, self.config.program_dim),
            nn.GELU(),
            nn.Linear(self.config.program_dim, self.config.program_dim),
        )
        self.refine_gate = nn.Parameter(torch.tensor(0.1))

        # Temperature buffer
        self.register_buffer("_temperature", torch.tensor(self.config.temperature))

        logger.debug(f"ResidualCatastropheProgramLibrary: {self.config.max_levels} levels")

    @property
    def decay(self) -> torch.Tensor:
        """Current decay factor."""
        return self.log_decay.exp()

    @property
    def temperature(self) -> float:
        temp_tensor: torch.Tensor = self._temperature  # type: ignore
        return temp_tensor.item()

    @temperature.setter
    def temperature(self, value: float) -> None:
        temp_tensor: torch.Tensor = self._temperature  # type: ignore
        temp_tensor.fill_(max(0.01, value))

    @property
    def effective_levels(self) -> int:
        """Get levels based on training/inference mode."""
        levels = self.config.training_levels if self.training else self.config.inference_levels
        # Clamp to avoid out-of-range if a curriculum/config requests deeper levels
        # than this instance has parameters for.
        return max(1, min(int(levels), int(self.config.max_levels)))

    def _quantize_residual(
        self,
        x: torch.Tensor,
        max_levels: int | None = None,
    ) -> dict[str, Any]:
        """Perform residual E8 quantization.

        Args:
            x: [B, 8] E8-space vector (norm √2)
            max_levels: Override max levels

        Returns:
            Dict with indices, scales, residual_norms per level
        """
        if max_levels is None:
            max_levels = self.effective_levels

        decay = self.decay

        indices = []
        scales = []
        residual_norms = []

        residual = x.clone()

        for level in range(max_levels):
            # Scale for this level
            scale = 2.0 / (decay**level)
            scales.append(scale.item() if isinstance(scale, torch.Tensor) else scale)

            # Scale residual for quantization
            scaled = residual / scale

            # Find nearest E8 root
            # NOTE (MPS): `torch.cdist` backward is not implemented on MPS. We only need
            # argmin here, so squared distances are sufficient (no sqrt needed).
            r: torch.Tensor = self.roots  # type: ignore
            x = scaled.to(dtype=r.dtype)
            x2 = (x * x).sum(dim=1, keepdim=True)  # [B, 1]
            r2 = (r * r).sum(dim=1).unsqueeze(0)  # [1, 240]
            d2 = (x2 + r2 - 2.0 * (x @ r.transpose(0, 1))).clamp_min(0.0)  # [B, 240]
            nearest_idx = d2.argmin(dim=-1)  # [B]
            indices.append(nearest_idx)

            # Get quantized value
            roots_tensor: torch.Tensor = self.roots  # type: ignore
            quantized = roots_tensor[nearest_idx] * scale  # [B, 8]

            # Update residual
            residual = residual - quantized
            residual_norms.append(residual.norm(dim=-1).mean().item())

            # Early stopping if adaptive
            if self.config.adaptive_levels and residual_norms[-1] < self.config.residual_threshold:
                break

        return {
            "indices": indices,  # List of [B] tensors
            "scales": scales,
            "residual_norms": residual_norms,
            "num_levels": len(indices),
        }

    def select(
        self,
        observation: torch.Tensor,
        colony_idx: int | None = None,
        return_details: bool = True,
    ) -> dict[str, Any]:
        """Select program using residual E8 quantization + MDL-inspired prior.

        GRADIENT FLOW: Uses soft attention at each level for differentiability.

        Args:
            observation: [B, query_dim] observation (G₂ 14D)
            colony_idx: Which colony is selecting (0-6)
            return_details: Whether to return detailed info

        Returns:
            Dict with:
            - program: [B, 52] selected program embedding
            - control_params: [B, 4] control parameters for CatastropheKAN
            - level_indices: List of [B] indices per level
            - attention: [B, 240] base attention weights
        """
        # Flatten if needed
        shape = observation.shape
        if len(shape) == 3:
            B, S, D = shape
            observation = observation.view(B * S, D)
        else:
            B = shape[0]

        # === PROJECT TO E8 SPACE ===
        query_8d = self.g2_proj(observation)  # [B, 8]

        # === RESIDUAL QUANTIZATION ===
        quant_result = self._quantize_residual(query_8d)
        level_indices = quant_result["indices"]
        num_levels = quant_result["num_levels"]

        # === HIERARCHICAL EMBEDDING LOOKUP ===
        decay = self.decay
        embedding = torch.zeros(B, self.config.program_dim, device=observation.device)
        control_params = torch.zeros(B, self.config.max_control_params, device=observation.device)

        # Level 0: Base selection with soft attention
        # Compute base similarities for soft attention
        roots_norm: torch.Tensor = self.roots_normalized  # type: ignore
        base_similarities = torch.matmul(query_8d, roots_norm.T)  # [B, 240]

        # Apply MDL-inspired prior (NOT true Solomonoff - see docstring)
        log_prior = -self.base_complexity * math.log(2)  # [240]
        log_posterior = base_similarities + log_prior.unsqueeze(0)

        # Apply colony affinity if specified
        if colony_idx is not None and self.config.use_learned_affinity:
            affinity = F.softmax(
                self.affinity_logits[:, colony_idx] / self.config.affinity_temperature, dim=0
            )
            log_posterior = log_posterior + affinity.unsqueeze(0) * 2.0

        # Soft attention over base programs
        temp = self.temperature
        base_attention = F.softmax(log_posterior / temp, dim=-1)  # [B, 240]

        # Base contribution (soft selection for gradient flow)
        base_embed = torch.matmul(base_attention, self.level_embeddings[0])  # [B, program_dim]
        embedding = embedding + base_embed

        # Base control params
        control_params = control_params + torch.matmul(base_attention, self.base_control_params)

        # === RESIDUAL LEVELS ===
        for level in range(1, num_levels):
            level_decay = decay**level
            level_idx = level_indices[level]

            # Hard selection at residual levels (sharper)
            residual_embed = self.level_embeddings[level][level_idx]  # [B, program_dim]
            embedding = embedding + residual_embed / level_decay

            # Residual control params
            if level - 1 < len(self.residual_control_params):
                residual_ctrl = self.residual_control_params[level - 1][level_idx]
                control_params = control_params + residual_ctrl / level_decay

        # === REFINEMENT ===
        refined = self.refine(embedding)
        embedding = embedding + torch.sigmoid(self.refine_gate) * refined

        # === MASK CONTROL PARAMS BY COLONY CODIM ===
        if colony_idx is not None:
            codim = CATASTROPHE_CODIM[colony_idx]
            mask = torch.zeros_like(control_params)
            mask[:, :codim] = 1.0
            control_params = control_params * mask

        # === COMPUTE TOTAL COMPLEXITY ===
        total_complexity = self._compute_complexity(level_indices, base_attention)

        result = {
            "program": embedding,  # [B, program_dim]
            "control_params": control_params,  # [B, 4]
            "level_indices": level_indices,
            "num_levels": num_levels,
            "complexity": total_complexity,
        }

        if return_details:
            result["attention"] = base_attention
            result["residual_norms"] = quant_result["residual_norms"]
            result["scales"] = quant_result["scales"]

        return result

    def _compute_complexity(
        self,
        level_indices: list[torch.Tensor],
        base_attention: torch.Tensor,
    ) -> torch.Tensor:
        """Compute total learned complexity score (NOT true K(x))."""
        # Base complexity (weighted by attention)
        total = (base_attention * self.base_complexity.exp().unsqueeze(0)).sum(dim=-1)

        # Residual complexity
        for level, idx in enumerate(level_indices[1:]):
            if level < len(self.residual_complexity):
                total = total + self.residual_complexity[level][idx]

        return total

    def get_colony_affinity(self, colony_idx: int) -> torch.Tensor:
        """Get affinity scores for all programs to a specific colony."""
        if self.config.use_learned_affinity:
            return F.softmax(
                self.affinity_logits[:, colony_idx] / self.config.affinity_temperature, dim=0
            )
        # Fallback: round-robin mask
        mask = torch.zeros(240, device=self.affinity_logits.device)
        for i in range(240):
            if i % 7 == colony_idx:
                mask[i] = 1.0 / 35  # 240/7 ≈ 34 programs per colony
        return mask

    def update_complexity(
        self,
        level_indices: list[int | torch.Tensor],
        reward: float,
        colony_idx: int | None = None,
    ) -> None:
        """Update complexity based on execution outcome (MDL learning)."""
        with torch.no_grad():
            # Base complexity update
            base_idx_val = level_indices[0]
            if isinstance(base_idx_val, torch.Tensor):
                base_idx_int: int = int(base_idx_val.item())
            else:
                base_idx_int = int(base_idx_val)
            base_idx = base_idx_int

            if reward > 0:
                self.base_complexity.data[base_idx] -= 0.01 * reward
            else:
                self.base_complexity.data[base_idx] += 0.02 * abs(reward)

            # Clamp
            self.base_complexity.data[base_idx] = torch.clamp(
                self.base_complexity.data[base_idx],
                math.log(self.config.min_complexity),
                math.log(self.config.max_complexity),
            )

            # Update affinity
            if colony_idx is not None and self.config.use_learned_affinity:
                if reward > 0:
                    self.affinity_logits.data[base_idx, colony_idx] += 0.05 * reward
                else:
                    self.affinity_logits.data[base_idx, colony_idx] -= 0.025 * abs(reward)

    def get_stats(self) -> dict[str, Any]:
        """Get library statistics."""
        return {
            "num_base_programs": 240,
            "max_levels": self.config.max_levels,
            "max_programs": 240**self.config.max_levels,
            "max_bits": self.config.max_levels * math.log2(240),
            "current_decay": self.decay.item(),
            "avg_base_complexity": self.base_complexity.exp().mean().item(),
            "effective_levels": self.effective_levels,
        }


# NOTE (Dec 8, 2025): SolomonoffResidualLibrary alias REMOVED — the name was
# misleading. True Solomonoff induction is incomputable. Use
# ResidualCatastropheProgramLibrary directly.


logger.debug("residual_program_library module loaded")
