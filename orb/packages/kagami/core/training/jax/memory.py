"""JAX Memory Modules — Episodic Memory & Matryoshka Representations.

Ports from PyTorch:
1. EpisodicMemory — Hopfield-style associative memory
2. MatryoshkaHourglass — Multi-scale representations
3. GradNormLoss — Gradient-based loss balancing
4. CatastropheAwareLoss — Catastrophe-theory loss weighting

References:
- Ramsauer et al. (2021): Hopfield Networks is All You Need
- Kusupati et al. (2022): Matryoshka Representation Learning
- Chen et al. (2018): GradNorm

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATIONS
# =============================================================================


@dataclass(frozen=True)
class EpisodicMemoryConfig:
    """Configuration for episodic memory."""

    num_slots: int = 240  # E8 root count
    value_dim: int = 256  # RSSM h dimension
    query_dim: int = 14  # G2 dimension

    beta: float = 8.0  # Inverse temperature
    beta_min: float = 1.0
    beta_max: float = 32.0

    hebbian_lr: float = 0.01
    decay: float = 0.999


@dataclass(frozen=True)
class MatryoshkaConfig:
    """Configuration for Matryoshka multi-scale training."""

    max_bulk_dim: int = 2048

    # Exceptional hierarchy scales
    scales: tuple[tuple[str, int], ...] = (
        ("micro", 7),  # S7
        ("nano", 14),  # G2
        ("small", 52),  # F4
        ("base", 78),  # E6
        ("large", 133),  # E7
        ("xl", 248),  # E8
    )

    active_scales: tuple[str, ...] = ("micro", "nano", "small", "base", "large", "xl")

    dropout: float = 0.1
    layer_norm_eps: float = 1e-6


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class MemoryOutput(NamedTuple):
    """Output from episodic memory."""

    retrieved: jnp.ndarray  # [B, value_dim] retrieved values
    attention: jnp.ndarray  # [B, num_slots] attention weights
    energy: jnp.ndarray  # [B] Hopfield energy


class MatryoshkaOutput(NamedTuple):
    """Output from Matryoshka encoder."""

    embeddings: dict[str, jnp.ndarray]  # Scale name → embedding
    quantized: jnp.ndarray  # [B, 8] E8 quantized
    commitment_loss: jnp.ndarray  # VQ commitment loss


# =============================================================================
# EPISODIC MEMORY
# =============================================================================


class EpisodicMemory(nn.Module):
    """Hopfield-style episodic memory with E8 addressing.

    JAX port of PyTorch memory/episodic_memory.py:EpisodicMemory

    Architecture:
        Query (G2 14D) → projection → attention → 256D values
    """

    config: EpisodicMemoryConfig

    @nn.compact
    def __call__(
        self,
        query: jnp.ndarray,
        write: bool = False,
        write_value: jnp.ndarray | None = None,
    ) -> MemoryOutput:
        """Read or write to episodic memory.

        Args:
            query: [B, query_dim] query vector
            write: Whether to write new memory
            write_value: [B, value_dim] value to write (if write=True)

        Returns:
            MemoryOutput
        """
        cfg = self.config
        B = query.shape[0]

        # Memory slots (keys and values)
        keys = self.param(
            "keys",
            nn.initializers.normal(0.02),
            (cfg.num_slots, cfg.query_dim),
        )
        values = self.variable(
            "memory",
            "values",
            lambda: jnp.zeros((cfg.num_slots, cfg.value_dim)),
        )

        # Project query
        query_proj = nn.Dense(cfg.query_dim, name="query_proj")(query)

        # Hopfield attention: softmax(β * q · K^T) · V
        # Similarity [B, num_slots]
        similarity = jnp.matmul(query_proj, keys.T)

        # Temperature-scaled softmax
        attention = jax.nn.softmax(cfg.beta * similarity, axis=-1)

        # Retrieve values [B, value_dim]
        retrieved = jnp.matmul(attention, values.value)

        # Hopfield energy: -β * log(sum(exp(β * sim)))
        energy = -jnp.log(jnp.sum(jnp.exp(cfg.beta * similarity), axis=-1))

        # Hebbian write (if enabled)
        if write and write_value is not None:
            # Find best matching slot
            best_idx = jnp.argmax(attention, axis=-1)

            # Update values with Hebbian learning
            # This is simplified for JAX - in practice would use scatter
            for b in range(B):
                idx = best_idx[b]
                old_val = values.value[idx]
                new_val = (1 - cfg.hebbian_lr) * old_val + cfg.hebbian_lr * write_value[b]
                values.value = values.value.at[idx].set(new_val)

        return MemoryOutput(
            retrieved=retrieved,
            attention=attention,
            energy=energy,
        )


# =============================================================================
# MATRYOSHKA ENCODER
# =============================================================================


class MatryoshkaEncoder(nn.Module):
    """Multi-scale Matryoshka encoder with exceptional hierarchy.

    JAX port of PyTorch matryoshka_hourglass.py:MatryoshkaHourglass (encoder part)

    Input → E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7)
    """

    config: MatryoshkaConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
    ) -> dict[str, jnp.ndarray]:
        """Encode input at multiple scales.

        Args:
            x: [B, max_bulk_dim] input

        Returns:
            Dict mapping scale name to embedding
        """
        cfg = self.config
        scale_dict = dict(cfg.scales)

        embeddings = {}

        # Project to E8
        h = nn.Dense(248, name="to_e8")(x)
        h = nn.LayerNorm(name="ln_e8")(h)
        h = nn.gelu(h)

        # E8 → E7 → E6 → F4 → G2 → S7 (hourglass down)
        prev_dim = 248
        for scale_name, dim in cfg.scales[::-1]:  # xl → micro
            h = nn.Dense(dim, name=f"to_{scale_name}")(h)
            h = nn.LayerNorm(name=f"ln_{scale_name}")(h)
            h = nn.gelu(h)

            if scale_name in cfg.active_scales:
                embeddings[scale_name] = h

            prev_dim = dim

        return embeddings


# =============================================================================
# MATRYOSHKA DECODER
# =============================================================================


class MatryoshkaDecoder(nn.Module):
    """Multi-scale Matryoshka decoder.

    Takes embedding at any scale and reconstructs to target scale.
    """

    config: MatryoshkaConfig
    target_scale: str = "xl"  # Default to full E8

    @nn.compact
    def __call__(
        self,
        embedding: jnp.ndarray,
        source_scale: str,
    ) -> jnp.ndarray:
        """Decode embedding to target scale.

        Args:
            embedding: [B, source_dim] embedding
            source_scale: Name of source scale

        Returns:
            [B, target_dim] decoded output
        """
        cfg = self.config
        scale_dict = dict(cfg.scales)

        source_dim = scale_dict[source_scale]
        target_dim = scale_dict[self.target_scale]

        # Project up through hierarchy
        h = embedding

        scale_order = [s for s, _ in cfg.scales]
        source_idx = scale_order.index(source_scale)
        target_idx = scale_order.index(self.target_scale)

        # Go from source to target
        if target_idx > source_idx:
            # Going up (larger)
            for i in range(source_idx + 1, target_idx + 1):
                scale_name, dim = cfg.scales[i]
                h = nn.Dense(dim, name=f"up_{scale_name}")(h)
                h = nn.LayerNorm(name=f"ln_up_{scale_name}")(h)
                h = nn.gelu(h)
        else:
            # Going down (smaller)
            for i in range(source_idx - 1, target_idx - 1, -1):
                scale_name, dim = cfg.scales[i]
                h = nn.Dense(dim, name=f"down_{scale_name}")(h)
                h = nn.LayerNorm(name=f"ln_down_{scale_name}")(h)
                h = nn.gelu(h)

        return h


# =============================================================================
# MATRYOSHKA HOURGLASS
# =============================================================================


class MatryoshkaHourglass(nn.Module):
    """Full Matryoshka hourglass with encoder/decoder.

    JAX port of PyTorch matryoshka_hourglass.py:MatryoshkaHourglass
    """

    config: MatryoshkaConfig

    def setup(self):
        self.encoder = MatryoshkaEncoder(self.config)

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        target_scales: tuple[str, ...] | None = None,
    ) -> MatryoshkaOutput:
        """Encode and optionally decode at multiple scales.

        Args:
            x: [B, max_bulk_dim] input
            target_scales: Which scales to return (default: all active)

        Returns:
            MatryoshkaOutput
        """
        cfg = self.config

        if target_scales is None:
            target_scales = cfg.active_scales

        # Encode
        embeddings = self.encoder(x)

        # Filter to requested scales
        embeddings = {k: v for k, v in embeddings.items() if k in target_scales}

        # E8 quantization (simplified)
        micro_emb = embeddings.get("micro", jnp.zeros((x.shape[0], 7)))
        quantized = nn.Dense(8, name="to_e8_vq")(micro_emb)

        # Commitment loss (VQ)
        commitment_loss = jnp.mean(
            jnp.square(
                quantized
                - jax.lax.stop_gradient(
                    micro_emb[:, :8]
                    if micro_emb.shape[-1] >= 8
                    else jnp.pad(micro_emb, ((0, 0), (0, 8 - micro_emb.shape[-1])))
                )
            )
        )

        return MatryoshkaOutput(
            embeddings=embeddings,
            quantized=quantized,
            commitment_loss=commitment_loss,
        )


# =============================================================================
# GRADNORM LOSS
# =============================================================================


class GradNormLoss(nn.Module):
    """GradNorm: Gradient Normalization for Adaptive Loss Balancing.

    JAX port of PyTorch losses/uncertainty_weighted.py:GradNormLoss

    Reference: Chen et al. (2018) ICML
    """

    task_names: tuple[str, ...]
    alpha: float = 1.5

    @nn.compact
    def __call__(
        self,
        losses: dict[str, jnp.ndarray],
    ) -> tuple[jnp.ndarray, dict[str, jnp.ndarray], dict[str, float]]:
        """Compute GradNorm-weighted loss.

        Args:
            losses: Dict mapping task name to loss value

        Returns:
            total_loss, weighted_losses, weights
        """
        num_tasks = len(self.task_names)

        # Learnable log weights
        log_weights = self.param(
            "log_weights",
            nn.initializers.zeros,
            (num_tasks,),
        )

        # Normalize via softmax
        weights = jax.nn.softmax(log_weights) * num_tasks

        total_loss = jnp.array(0.0)
        weighted_losses = {}
        weight_dict = {}

        for i, name in enumerate(self.task_names):
            if name not in losses:
                continue

            w = weights[i]
            weighted_loss = w * losses[name]

            total_loss = total_loss + weighted_loss
            weighted_losses[name] = weighted_loss
            weight_dict[name] = float(w)

        return total_loss, weighted_losses, weight_dict


# =============================================================================
# CATASTROPHE-AWARE LOSS
# =============================================================================


class CatastropheAwareLoss(nn.Module):
    """Loss weighting based on catastrophe theory.

    JAX port of PyTorch superorganism_integration.py:CatastropheAwareLoss

    Uses catastrophe potential gradient to weight losses.
    Higher gradient = more critical state = higher weight.
    """

    task_names: tuple[str, ...]
    base_weight: float = 1.0
    catastrophe_scale: float = 0.1

    @nn.compact
    def __call__(
        self,
        losses: dict[str, jnp.ndarray],
        state: jnp.ndarray | None = None,
    ) -> tuple[jnp.ndarray, dict[str, jnp.ndarray], dict[str, float]]:
        """Compute catastrophe-aware weighted loss.

        Args:
            losses: Dict mapping task name to loss value
            state: [B, D] current state (optional, for catastrophe detection)

        Returns:
            total_loss, weighted_losses, weights
        """
        num_tasks = len(self.task_names)

        # Base weights
        base_weights = self.param(
            "base_weights",
            nn.initializers.ones,
            (num_tasks,),
        )

        # Catastrophe modulation (if state provided)
        if state is not None:
            # Simple catastrophe potential: cusp V(x) = x^4/4 - x^2/2
            # Gradient |dV/dx| = |x^3 - x| is high near bifurcation points
            state_norm = jnp.mean(state, axis=-1)  # [B]
            catastrophe_grad = jnp.abs(state_norm**3 - state_norm)
            modulation = 1.0 + self.catastrophe_scale * jnp.mean(catastrophe_grad)
        else:
            modulation = 1.0

        # Apply weights
        weights = base_weights * self.base_weight * modulation
        weights = weights / jnp.sum(weights) * num_tasks  # Normalize

        total_loss = jnp.array(0.0)
        weighted_losses = {}
        weight_dict = {}

        for i, name in enumerate(self.task_names):
            if name not in losses:
                continue

            w = weights[i]
            weighted_loss = w * losses[name]

            total_loss = total_loss + weighted_loss
            weighted_losses[name] = weighted_loss
            weight_dict[name] = float(w)

        return total_loss, weighted_losses, weight_dict


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_episodic_memory(
    config: EpisodicMemoryConfig | None = None,
) -> EpisodicMemory:
    """Create episodic memory module."""
    if config is None:
        config = EpisodicMemoryConfig()
    return EpisodicMemory(config)


def create_matryoshka_hourglass(
    config: MatryoshkaConfig | None = None,
) -> MatryoshkaHourglass:
    """Create Matryoshka hourglass module."""
    if config is None:
        config = MatryoshkaConfig()
    return MatryoshkaHourglass(config)


def create_gradnorm_loss(
    task_names: tuple[str, ...],
    alpha: float = 1.5,
) -> GradNormLoss:
    """Create GradNorm loss module."""
    return GradNormLoss(task_names=task_names, alpha=alpha)


def create_catastrophe_loss(
    task_names: tuple[str, ...],
    catastrophe_scale: float = 0.1,
) -> CatastropheAwareLoss:
    """Create catastrophe-aware loss module."""
    return CatastropheAwareLoss(
        task_names=task_names,
        catastrophe_scale=catastrophe_scale,
    )


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    # Configs
    "EpisodicMemoryConfig",
    "MatryoshkaConfig",
    # Outputs
    "MemoryOutput",
    "MatryoshkaOutput",
    # Modules
    "EpisodicMemory",
    "MatryoshkaEncoder",
    "MatryoshkaDecoder",
    "MatryoshkaHourglass",
    "GradNormLoss",
    "CatastropheAwareLoss",
    # Factories
    "create_episodic_memory",
    "create_matryoshka_hourglass",
    "create_gradnorm_loss",
    "create_catastrophe_loss",
]
