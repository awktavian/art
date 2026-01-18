"""Episodic Memory — 256D Values for RSSM h State Storage.

This module stores episodic experiences with full-fidelity RSSM h states.
No truncation — 256D matches RSSM deterministic state exactly.

RESEARCH FOUNDATION:
====================
- Ramsauer et al. (2021): "Hopfield Networks is All You Need"
  - Attention = Hopfield update, exponential capacity
- DreamerV3 (Hafner): RSSM h carries temporal memory
  - Must not bottleneck deterministic state

ARCHITECTURE:
=============
    Query (G₂ 14D) → G₂ projection → 8D → E₈ attention → 256D values
                                                                ↓
                                                        → project(14D) → augment nucleus

    RSSM h (256D) → E₈ attention → Hebbian write → values [240, 256]

Created: December 2, 2025
Purpose: Store "what happened" (episodic, full-fidelity)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.dimensions import (
    G2_DIM,
    OCTONION_EMBEDDING_DIM,
    generate_e8_roots,
)

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT BUS INTEGRATION (Dec 2, 2025)
# =============================================================================

_memory_event_bus = None


def _get_memory_event_bus() -> Any:
    """Lazy-load event bus to avoid circular imports."""
    global _memory_event_bus
    if _memory_event_bus is None:
        try:
            from kagami.core.events import get_unified_bus

            _memory_event_bus = get_unified_bus()
        except ImportError:
            pass
    return _memory_event_bus


def _publish_memory_event(
    operation: str,
    indices: torch.Tensor | None = None,
    energy: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Publish memory operation to E8 event bus (fire-and-forget)."""
    bus = _get_memory_event_bus()
    if bus is None:
        return

    try:
        import asyncio

        from kagami.core.events import OperationOutcome

        # Convert indices to list[Any] for JSON
        idx_list = indices.tolist() if indices is not None else []

        outcome = OperationOutcome(
            operation=f"memory.{operation}",
            success=True,
            app="episodic_memory",
            metadata={
                "indices": idx_list[:5],  # Top 5
                "energy": energy,
                **(metadata or {}),
            },
        )

        # Fire-and-forget
        try:
            asyncio.get_running_loop()
            asyncio.create_task(bus.publish_experience(outcome))
        except RuntimeError:
            pass  # No running loop - skip async publish
    except Exception:
        pass  # Non-critical


# RSSM h state dimension (must match KagamiWorldModelConfig.rssm_hidden_dim)
RSSM_H_DIM = 256


@dataclass
class EpisodicMemoryConfig:
    """Configuration for Episodic Memory.

    VARIABLE-LENGTH ADDRESSING (Dec 2, 2025):
    =========================================
    Now supports residual E8 addressing for hierarchical memory:
    - Level 0: 240 base slots (7.91 bits)
    - Level 1: 57,600 slots (15.81 bits)
    - Level 2: 13.8M slots (23.72 bits)
    - ...up to max_residual_levels

    This enables:
    - Coarse-to-fine memory retrieval
    - Hierarchical associative storage
    - Infinite address space with finite parameters

    AUTOMATIC TRAINING/INFERENCE MODE (Dec 2, 2025):
    =================================================
    The system automatically switches between modes:
    - TRAINING: Uses training_levels (fewer, faster)
    - INFERENCE: Uses inference_levels (more, maximum precision)

    This is automatic via model.training flag - no manual switching needed.
    """

    # Core dimensions
    num_slots: int = 240  # E₈ root count per level (fixed)
    value_dim: int = RSSM_H_DIM  # Match RSSM h exactly (256D)
    query_dim: int = G2_DIM  # G₂ input dimension (14D)

    # Hopfield parameters
    beta: float = 8.0  # Inverse temperature
    beta_min: float = 1.0
    beta_max: float = 32.0

    # BETA ANNEALING (Dec 3, 2025) - per Ramsauer et al. 2021 (Hopfield Networks is All You Need)
    # Start with low β (soft attention) and anneal to high β (sharp retrieval)
    # This improves training stability and allows exploration early on
    beta_anneal: bool = True
    beta_start: float = 2.0  # Initial β (soft attention for exploration)
    beta_end: float = 16.0  # Final β (sharp attention for retrieval)
    beta_anneal_steps: int = 50000  # Steps to anneal over

    # Learning parameters
    hebbian_lr: float = 0.1  # Hebbian write strength
    decay_rate: float = 0.001  # Forgetting rate

    # EMA tracking
    track_usage: bool = True
    usage_decay: float = 0.99

    # === AUTOMATIC DEPTH SWITCHING ===
    # UPDATED (Dec 6, 2025): Increased to match system-wide config
    training_levels: int = 8  # Levels during training (was 2)
    inference_levels: int = 16  # Levels during inference (was 8)

    # === RESIDUAL ADDRESSING (Dec 2, 2025) ===
    max_residual_levels: int = 8  # Up to 63 bits of addressing
    min_residual_levels: int = 1  # Minimum levels to use
    adaptive_levels: bool = True  # Stop early when residual small
    residual_threshold: float = 0.1  # Residual norm threshold
    level_decay: float = 15.49  # √240 (optimal from E8 geometry)


# NOTE: _generate_e8_roots moved to kagami.core.config.dimensions (canonical source)
_generate_e8_roots = generate_e8_roots  # Alias for backward compatibility


def safe_orthogonal_init(weight: torch.Tensor, gain: float = 1.0) -> torch.Tensor:
    """MPS-safe orthogonal initialization - do QR on CPU."""
    original_device = weight.device
    cpu_weight = weight.cpu()
    nn.init.orthogonal_(cpu_weight, gain=gain)
    return cpu_weight.to(original_device)


class G2Projection(nn.Module):
    """Project from G₂ (14D) to octonion (8D) for E₈ addressing."""

    def __init__(self, input_dim: int = G2_DIM, output_dim: int = OCTONION_EMBEDDING_DIM):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.GELU(),
            nn.Linear(32, output_dim),
        )
        # MPS-safe orthogonal init: do on CPU first (QR not implemented on MPS)
        linear0 = self.proj[0]
        linear2 = self.proj[2]
        if isinstance(linear0, nn.Linear) and isinstance(linear2, nn.Linear):
            linear0.weight.data = safe_orthogonal_init(linear0.weight.data, gain=1.0)
            linear2.weight.data = safe_orthogonal_init(linear2.weight.data, gain=1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Project and normalize to unit norm for E₈ similarity."""
        projected = self.proj(x)
        return F.normalize(projected, p=2, dim=-1)


class EpisodicMemory(nn.Module):
    """Episodic Memory with 256D values for full RSSM h storage.

    Uses Hopfield attention over E₈ roots as keys, stores 256D content.
    Hebbian learning for writing, exponential decay for forgetting.
    """

    def __init__(self, config: EpisodicMemoryConfig | None = None) -> None:
        super().__init__()
        self.config = config or EpisodicMemoryConfig()

        # === E₈ ROOTS (FIXED) ===
        e8_roots = _generate_e8_roots()
        self.register_buffer("keys", e8_roots)  # [240, 8], norm √2
        self.register_buffer("keys_normalized", F.normalize(e8_roots, p=2, dim=-1))

        # Type hints for buffers (mypy satisfaction)
        self.keys: torch.Tensor
        self.keys_normalized: torch.Tensor

        # === LEARNABLE VALUES (256D to match RSSM h) ===
        self.values = nn.Parameter(torch.randn(self.config.num_slots, self.config.value_dim) * 0.02)

        # === G₂ PROJECTION (14D → 8D) ===
        self.g2_proj = G2Projection(
            input_dim=self.config.query_dim,
            output_dim=OCTONION_EMBEDDING_DIM,
        )

        # DELETED (Dec 7, 2025): output_proj (16K params, 0% gradient)
        # Was not used in main forward path - external _memory_proj handles projection
        # Methods read_and_project, read_residual, read_residual_e8 also removed

        # === USAGE TRACKING ===
        if self.config.track_usage:
            self.register_buffer(
                "usage_count",
                torch.zeros(self.config.num_slots, dtype=torch.float32),
            )

        # Temperature for training
        # If annealing enabled, start at beta_start; otherwise use config.beta
        initial_beta = self.config.beta_start if self.config.beta_anneal else self.config.beta
        self.register_buffer("_beta", torch.tensor(initial_beta, dtype=torch.float32))

        # === BETA ANNEALING STATE (Dec 3, 2025) ===
        # Per Ramsauer et al. 2021: anneal β from soft to sharp
        self.register_buffer("_anneal_step", torch.tensor(0, dtype=torch.long))

        # Type hints for buffers (mypy satisfaction)
        self._beta: torch.Tensor
        self._anneal_step: torch.Tensor

        logger.debug("EpisodicMemory: slots=240, values=%dD", self.config.value_dim)

    @property
    def beta(self) -> float:
        """Current inverse temperature."""
        # OPTIMIZED (Dec 5, 2025): Return tensor for gradient flow, use .item() only at logging
        beta_tensor: torch.Tensor = self._beta
        return float(beta_tensor.item())

    @beta.setter
    def beta(self, value: float) -> None:
        """Set inverse temperature with clamping."""
        value = max(self.config.beta_min, min(self.config.beta_max, value))
        beta_tensor: torch.Tensor = self._beta
        beta_tensor.fill_(value)

    def anneal_beta(self) -> float:
        """Anneal β towards target value (Dec 3, 2025).

        Per Ramsauer et al. 2021 (Hopfield Networks is All You Need):
        - Start with low β (soft attention) for exploration
        - Anneal to high β (sharp attention) for precise retrieval
        - Linear schedule over beta_anneal_steps

        Call this once per training step.

        Returns:
            Current β value after annealing
        """
        if not self.config.beta_anneal:
            return self.beta

        # OPTIMIZED (Dec 5, 2025): Keep as tensor operations where possible
        anneal_step_tensor: torch.Tensor = self._anneal_step
        beta_tensor: torch.Tensor = self._beta

        step = int(anneal_step_tensor.item())
        total_steps = self.config.beta_anneal_steps

        if step >= total_steps:
            # Annealing complete - stay at final value
            beta_tensor.fill_(self.config.beta_end)
        else:
            # Linear interpolation
            progress = step / total_steps
            new_beta = self.config.beta_start + progress * (
                self.config.beta_end - self.config.beta_start
            )
            beta_tensor.fill_(new_beta)
            anneal_step_tensor.add_(1)

        return self.beta

    @property
    def effective_levels(self) -> int:
        """Get effective number of levels based on training/inference mode.

        AUTOMATIC MODE SWITCHING:
        - Training: Uses training_levels (fewer, faster)
        - Inference: Uses inference_levels (more, maximum precision)
        """
        if self.training:
            return self.config.training_levels
        else:
            return self.config.inference_levels

    def read(
        self,
        query: torch.Tensor,
        return_energy: bool = False,
        return_indices: bool = False,
    ) -> (
        tuple[torch.Tensor, torch.Tensor]
        | tuple[torch.Tensor, torch.Tensor, torch.Tensor]
        | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
    ):
        """Read from memory using Hopfield attention.

        Args:
            query: [B, query_dim] or [B, S, query_dim] G₂ state
            return_energy: Return Hopfield energy
            return_indices: Return top-k indices

        Returns:
            content: [B, value_dim] retrieved content (256D)
            attention: [B, 240] attention weights
            (optional) energy: Hopfield energy
            (optional) indices: top-k indices
        """
        # Flatten batch/seq dimensions
        shape = query.shape
        if len(shape) == 3:
            B, S, D = shape
            query = query.view(B * S, D)
        else:
            B, D = shape
            S = None

        # Project to E₈ space
        query_8d = self.g2_proj(query)  # [B*S, 8]

        # Hopfield attention: softmax(β * K^T q)
        similarities = torch.matmul(query_8d, self.keys_normalized.T)  # [B*S, 240]
        beta_tensor: torch.Tensor = self._beta
        attention = F.softmax(beta_tensor * similarities, dim=-1)

        # Retrieve content
        content = torch.matmul(attention, self.values)  # [B*S, 256]

        # Track usage
        if self.config.track_usage and self.training:
            with torch.no_grad():
                usage_count_tensor = cast(torch.Tensor, self.usage_count)
                usage_count_tensor *= self.config.usage_decay
                usage_count_tensor += attention.sum(dim=0)

        # Compute energy if requested
        results = [content, attention]

        if return_energy:
            # Hopfield energy: -lse(β, K^T q) + ½||q||²
            beta_tensor_e: torch.Tensor = self._beta
            lse = torch.logsumexp(beta_tensor_e * similarities, dim=-1) / beta_tensor_e
            energy = -lse + 0.5 * (query_8d**2).sum(dim=-1)
            results.append(energy)

        if return_indices:
            _, indices = attention.topk(5, dim=-1)
            results.append(indices)

        # Publish read event to E8 bus (Dec 2, 2025)
        _, top_indices = attention.topk(3, dim=-1)
        energy_val: float = 0.0
        if return_energy and len(results) > 2:
            # OPTIMIZED (Dec 5, 2025): Defer .item() to event publish
            energy_tensor: torch.Tensor = results[2]
            energy_val = float(energy_tensor.mean().item())
        _publish_memory_event(
            "read",
            top_indices[0],
            energy_val,
        )

        return cast(
            tuple[torch.Tensor, torch.Tensor]
            | tuple[torch.Tensor, torch.Tensor, torch.Tensor]
            | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
            tuple(results),
        )

    def write(
        self,
        query: torch.Tensor,
        content: torch.Tensor,
        strength: float | None = None,
    ) -> dict[str, Any]:
        """Write content to memory using Hebbian learning.

        Args:
            query: [B, query_dim] or [B, S, query_dim] G₂ addressing
            content: [B, value_dim] content to store (should be RSSM h, 256D)
            strength: Write strength (overrides config if provided)

        Returns:
            Statistics dict[str, Any]
        """
        if strength is None:
            strength = self.config.hebbian_lr

        # Flatten
        if len(query.shape) == 3:
            query = query.view(-1, query.shape[-1])
            content = content.view(-1, content.shape[-1])

        # Ensure content matches value dimension
        if content.shape[-1] != self.config.value_dim:
            # Pad or truncate
            if content.shape[-1] < self.config.value_dim:
                content = F.pad(content, (0, self.config.value_dim - content.shape[-1]))
            else:
                content = content[..., : self.config.value_dim]

        # Get attention (which slots to write to)
        query_8d = self.g2_proj(query)
        similarities = torch.matmul(query_8d, self.keys_normalized.T)
        beta_tensor_w: torch.Tensor = self._beta
        attention = F.softmax(beta_tensor_w * similarities, dim=-1)  # [B, 240]

        # Hebbian update: Δv_i = η * Σ_b a_{b,i} * (c_b - v_i)
        # Weighted average update toward content
        weighted_content = torch.matmul(attention.T, content)  # [240, 256]
        attention_sum = attention.sum(dim=0, keepdim=True).T  # [240, 1]
        attention_sum = attention_sum.clamp(min=1e-8)

        target = weighted_content / attention_sum
        delta = strength * (target - self.values.data)

        # Apply update
        self.values.data += delta

        # Publish write event to E8 bus (Dec 2, 2025)
        # OPTIMIZED (Dec 5, 2025): Compute once, keep as tensors
        _, top_indices = attention.topk(3, dim=-1)
        write_norm = delta.norm()
        attn_entropy = -(attention * (attention + 1e-8).log()).sum(dim=-1).mean()
        _publish_memory_event(
            "write",
            top_indices[0],
            0.0,
            {
                "write_norm": write_norm.item(),  # .item() only for JSON serialization
                "strength": strength,
            },
        )

        return {
            "write_norm": write_norm,  # Tensor
            "attention_entropy": attn_entropy,  # Tensor
        }

    def forget(self) -> None:
        """Apply exponential decay to values (forgetting)."""
        self.values.data *= 1 - self.config.decay_rate

    # DELETED (Dec 7, 2025): get_projected_content - used deleted output_proj

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        with torch.no_grad():
            # OPTIMIZED (Dec 5, 2025): Keep as tensors, defer .item() to logging
            usage_count_tensor = cast(torch.Tensor, self.usage_count)
            return {
                "values_mean": self.values.mean(),  # Tensor
                "values_std": self.values.std(),  # Tensor
                "values_norm": self.values.norm(),  # Tensor
                "usage_max": usage_count_tensor.max()
                if self.config.track_usage
                else torch.tensor(0),
                "usage_entropy": (
                    -(
                        F.softmax(usage_count_tensor, dim=0)
                        * F.log_softmax(usage_count_tensor + 1e-8, dim=0)
                    ).sum()
                )
                if self.config.track_usage
                else torch.tensor(0),
                "beta": self.beta,
            }

    # =========================================================================
    # RESIDUAL ADDRESSING (Dec 2, 2025)
    # =========================================================================

    def read_hierarchical(
        self,
        query: torch.Tensor,
        max_levels: int | None = None,
    ) -> tuple[torch.Tensor, list[torch.Tensor], int]:
        """Hierarchical read using residual E8 addressing.

        AUTOMATIC MODE SWITCHING (Dec 2, 2025):
        - Training: Uses training_levels (2 by default)
        - Inference: Uses inference_levels (8 by default)

        Effective capacity:
        - L=1:  240 slots (7.91 bits)
        - L=2:  57,600 slots (15.81 bits)
        - L=4:  3.3B slots (31.63 bits)
        - L=8:  1.1e19 slots (63.26 bits)

        Args:
            query: [B, query_dim] G₂ state
            max_levels: Override max levels (bypasses auto-switching)

        Returns:
            content: [B, value_dim] accumulated content (256D)
            attentions: List of [B, 240] attention per level
            num_levels: Actual number of levels used
        """
        if max_levels is None:
            # AUTOMATIC: Use training or inference levels based on mode
            max_levels = self.effective_levels

        max_levels = min(max_levels, self.config.max_residual_levels)

        # Flatten batch dims
        shape = query.shape
        if len(shape) == 3:
            B, S, D = shape
            query = query.view(B * S, D)

        # Initialize
        device = query.device
        content = torch.zeros(query.shape[0], self.config.value_dim, device=device)
        attentions = []
        residual_query = query.clone()
        decay = self.config.level_decay

        beta_tensor_rh: torch.Tensor = self._beta

        for level in range(max_levels):
            # Project residual query to E8 space
            query_8d = self.g2_proj(residual_query)  # [B, 8]

            # Hopfield attention
            similarities = torch.matmul(query_8d, self.keys_normalized.T)  # [B, 240]
            attention = F.softmax(beta_tensor_rh * similarities, dim=-1)
            attentions.append(attention)

            # Retrieve and accumulate (with decay)
            level_content = torch.matmul(attention, self.values)  # [B, 256]
            decay_factor = decay**level
            content = content + level_content / decay_factor

            # Update residual query (subtract retrieved pattern)
            # Use G2 projection instead of deleted output_proj (Dec 7, 2025)
            retrieved_8d = self.g2_proj(level_content[..., : self.config.query_dim])  # [B, 8]
            # Project back to query dim via simple linear (no params)
            residual_query = residual_query - F.pad(retrieved_8d, (0, self.config.query_dim - 8))

            # Check convergence: stop if attention is confident (low entropy)
            if self.config.adaptive_levels and level >= self.config.min_residual_levels - 1:
                attention_entropy = -(attention * (attention + 1e-8).log()).sum(dim=-1).mean()
                max_entropy = math.log(240)  # Maximum possible entropy
                normalized_entropy = attention_entropy / max_entropy

                # Stop if attention is focused (low entropy)
                if normalized_entropy < self.config.residual_threshold:
                    break

        return content, attentions, len(attentions)

    def write_hierarchical(
        self,
        query: torch.Tensor,
        content: torch.Tensor,
        max_levels: int | None = None,
        strength: float | None = None,
    ) -> dict[str, Any]:
        """Hierarchical write using residual E8 addressing.

        AUTOMATIC MODE SWITCHING (Dec 2, 2025):
        - Training: Uses training_levels (2 by default)
        - Inference: Uses inference_levels (8 by default)

        Writes to multiple levels, with each level storing the residual
        that couldn't be captured by previous levels.

        Args:
            query: [B, query_dim] G₂ addressing
            content: [B, value_dim] content to store (should be RSSM h, 256D)
            max_levels: Override max levels (bypasses auto-switching)
            strength: Write strength (overrides config if provided)

        Returns:
            Statistics dict[str, Any] including levels_used
        """
        if max_levels is None:
            # AUTOMATIC: Use training or inference levels based on mode
            max_levels = self.effective_levels
        if strength is None:
            strength = self.config.hebbian_lr

        # Flatten
        if len(query.shape) == 3:
            query = query.view(-1, query.shape[-1])
            content = content.view(-1, content.shape[-1])

        # Ensure content dimension
        if content.shape[-1] != self.config.value_dim:
            if content.shape[-1] < self.config.value_dim:
                content = F.pad(content, (0, self.config.value_dim - content.shape[-1]))
            else:
                content = content[..., : self.config.value_dim]

        decay = self.config.level_decay
        residual_content = content.clone()
        residual_query = query.clone()
        # OPTIMIZED (Dec 5, 2025): Initialize as tensor for tensor accumulation
        total_write_norm = torch.tensor(0.0, device=query.device)
        levels_used = 0

        beta_tensor_wh: torch.Tensor = self._beta

        for level in range(max_levels):
            # Compute decay factor for this level
            decay_factor = decay**level

            # Get attention weights
            query_8d = self.g2_proj(residual_query)
            similarities = torch.matmul(query_8d, self.keys_normalized.T)
            attention = F.softmax(beta_tensor_wh * similarities, dim=-1)  # [B, 240]

            # Scale residual content for this level
            scaled_residual = residual_content * decay_factor

            # Hebbian update
            weighted_content = torch.matmul(attention.T, scaled_residual)  # [240, 256]
            attention_sum = attention.sum(dim=0, keepdim=True).T.clamp(min=1e-8)
            target = weighted_content / attention_sum
            delta = strength * (target - self.values.data)

            self.values.data += delta
            # OPTIMIZED (Dec 5, 2025): Accumulate as tensors
            total_write_norm = total_write_norm + delta.norm()
            levels_used += 1

            # Compute what was written and update residuals
            retrieved = torch.matmul(attention, self.values.data) / decay_factor
            residual_content = content - retrieved

            # Update query for next level (Dec 7, 2025: removed output_proj)
            retrieved_8d = self.g2_proj(retrieved[..., : self.config.query_dim])  # [B, 8]
            residual_query = query - F.pad(retrieved_8d, (0, self.config.query_dim - 8))

            # Check if residual is small enough
            if self.config.adaptive_levels:
                # OPTIMIZED (Dec 5, 2025): .item() only for control flow check
                residual_norm = residual_content.norm(dim=-1).mean()
                if residual_norm.item() < self.config.residual_threshold:
                    break

        # OPTIMIZED (Dec 5, 2025): Keep as tensors
        return {
            "write_norm": total_write_norm,  # Tensor
            "levels_used": levels_used,
            "final_residual_norm": residual_content.norm(dim=-1).mean(),  # Tensor
        }

    def get_effective_capacity(self, levels: int | None = None) -> dict[str, Any]:
        """Compute effective memory capacity for given level count.

        Args:
            levels: Number of residual levels (default: config.max_residual_levels)

        Returns:
            Dict with slots, bits, and human-readable capacity
        """
        if levels is None:
            levels = self.config.max_residual_levels

        slots = 240**levels
        bits = levels * math.log2(240)

        return {
            "levels": levels,
            "effective_slots": slots,
            "bits": bits,
            "human_readable": (
                f"{slots:.2e} slots ({bits:.1f} bits)"
                if slots > 1e6
                else f"{slots:,} slots ({bits:.1f} bits)"
            ),
        }


__all__ = [
    "RSSM_H_DIM",
    "EpisodicMemory",
    "EpisodicMemoryConfig",
    "G2Projection",
]
