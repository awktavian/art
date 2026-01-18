"""JAX Loss Computation - Tiered loss structure.

BRICK-BY-BRICK COMPARISON:
=========================
PyTorch Source                          | JAX Target
----------------------------------------|-------------------------------------
losses/composed.py:UnifiedLossModule    | compute_full_loss()
losses/composed.py:LossConfig           | LossWeights (frozen dataclass)
losses/prediction.py:*                  | Individual loss functions
losses/reconstruction.py:symlog_loss    | symlog_loss (in transforms.py)

Created: January 8, 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

import jax
import jax.numpy as jnp

from .rssm import RSSMOutput
from .transforms import TwoHotEncoder, symlog

# =============================================================================
# LOSS WEIGHTS (frozen for JAX compatibility)
# =============================================================================


@dataclass(frozen=True)
class LossWeights:
    """Loss weights for training (frozen for JAX hashing).

    PyTorch: losses/composed.py:LossConfig (subset)

    Tier 1: Core
    - recon: Reconstruction loss

    Tier 2: Essential
    - kl: KL divergence
    - reward: Reward prediction
    - e8: E8 commitment
    - fano: Fano synergy
    - hjepa: H-JEPA prediction
    - stability: Gradient stability

    Tier 3: Auxiliary
    - value: Value prediction
    - continue_: Continue prediction
    """

    # Tier 1: Core
    recon: float = 1.0

    # Tier 2: Essential
    kl: float = 0.5
    reward: float = 0.5
    e8: float = 0.1
    fano: float = 0.05
    hjepa: float = 0.1
    stability: float = 0.01

    # Tier 3: Auxiliary
    value: float = 0.5
    continue_: float = 0.1


# =============================================================================
# LOSS OUTPUT
# =============================================================================


class LossOutput(NamedTuple):
    """Output from loss computation."""

    total: jnp.ndarray
    recon_loss: jnp.ndarray
    kl_loss: jnp.ndarray
    kl_raw: jnp.ndarray
    reward_loss: jnp.ndarray
    fano_loss: jnp.ndarray
    hjepa_loss: jnp.ndarray
    stability_loss: jnp.ndarray
    value_loss: jnp.ndarray
    continue_loss: jnp.ndarray


# =============================================================================
# FANO SYNERGY LOSS
# =============================================================================


def compute_fano_synergy_loss(h: jnp.ndarray) -> jnp.ndarray:
    """Compute Fano synergy loss for colony coordination.

    PyTorch: losses/composed.py:_compute_fano_synergy_loss (inside GeometricLossComputer)

    Encourages colonies on the same Fano line to have correlated activations.
    The Fano plane has 7 lines, each containing 3 colonies.

    Args:
        h: [B, T, 7, H] or [B, 7, H] hidden states

    Returns:
        Scalar loss (lower = better coordination)
    """
    # Average over time if needed
    if h.ndim == 4:
        h = jnp.mean(h, axis=1)  # [B, 7, H]

    # Fano plane lines
    fano_lines = [(0, 1, 3), (1, 2, 4), (2, 3, 5), (3, 4, 6), (4, 5, 0), (5, 6, 1), (6, 0, 2)]

    synergy_loss = jnp.array(0.0)

    for line in fano_lines:
        i, j, k = line

        # Get colony activations
        h_i = h[:, i]  # [B, H]
        h_j = h[:, j]
        h_k = h[:, k]

        # Normalize
        h_i_norm = h_i / (jnp.linalg.norm(h_i, axis=-1, keepdims=True) + 1e-8)
        h_j_norm = h_j / (jnp.linalg.norm(h_j, axis=-1, keepdims=True) + 1e-8)
        h_k_norm = h_k / (jnp.linalg.norm(h_k, axis=-1, keepdims=True) + 1e-8)

        # Correlation (dot product of normalized vectors)
        corr_ij = jnp.mean(jnp.sum(h_i_norm * h_j_norm, axis=-1))
        corr_jk = jnp.mean(jnp.sum(h_j_norm * h_k_norm, axis=-1))
        corr_ik = jnp.mean(jnp.sum(h_i_norm * h_k_norm, axis=-1))

        # Loss is negative correlation (minimize to maximize correlation)
        synergy_loss = synergy_loss - (corr_ij + corr_jk + corr_ik) / 3

    return synergy_loss / len(fano_lines)


# =============================================================================
# H-JEPA LOSS
# =============================================================================


def compute_hjepa_loss(
    pred_1: jnp.ndarray | None,
    pred_4: jnp.ndarray | None,
    pred_16: jnp.ndarray | None,
    target_1: jnp.ndarray | None,
    target_4: jnp.ndarray | None,
    target_16: jnp.ndarray | None,
) -> jnp.ndarray:
    """Compute H-JEPA multi-horizon prediction loss.

    PyTorch: losses/composed.py:_compute_h_jepa_loss

    Args:
        pred_*: Predictions at horizons 1, 4, 16
        target_*: Targets (stop-gradient applied by caller)

    Returns:
        Scalar loss
    """
    loss = jnp.array(0.0)
    count = 0

    # 1-step prediction
    if pred_1 is not None and target_1 is not None:
        loss = loss + jnp.mean(jnp.square(pred_1 - target_1))
        count += 1

    # 4-step prediction
    if pred_4 is not None and target_4 is not None:
        T_pred = min(pred_4.shape[1], target_4.shape[1])
        if T_pred > 0:
            loss = loss + jnp.mean(jnp.square(pred_4[:, :T_pred] - target_4[:, :T_pred]))
            count += 1

    # 16-step prediction
    if pred_16 is not None and target_16 is not None:
        T_pred = min(pred_16.shape[1], target_16.shape[1])
        if T_pred > 0:
            loss = loss + jnp.mean(jnp.square(pred_16[:, :T_pred] - target_16[:, :T_pred]))
            count += 1

    return loss / max(count, 1)


# =============================================================================
# STABILITY LOSS
# =============================================================================


def compute_stability_loss(h: jnp.ndarray) -> jnp.ndarray:
    """Compute stability regularization loss.

    PyTorch: losses/composed.py:_compute_stability_loss

    Encourages smooth temporal dynamics by penalizing large
    changes between consecutive hidden states.

    Args:
        h: [B, T, 7, H] hidden state sequence

    Returns:
        Scalar loss
    """
    if h.shape[1] < 2:
        return jnp.array(0.0)

    # Temporal difference
    diff = h[:, 1:] - h[:, :-1]
    return jnp.mean(jnp.square(diff))


# =============================================================================
# FULL LOSS COMPUTATION
# =============================================================================


def compute_full_loss(
    outputs: RSSMOutput,
    batch: dict[str, jnp.ndarray],
    weights: LossWeights,
    twohot_encoder: TwoHotEncoder | None = None,
) -> tuple[jnp.ndarray, LossOutput]:
    """Compute full loss with tiered structure.

    PyTorch: losses/composed.py:UnifiedLossModule.forward()

    TIER 1: Core Reconstruction Loss (symlog)
    - Prediction loss: ||symlog(pred) - symlog(target)||²

    TIER 2: Essential Losses
    - KL divergence (balanced)
    - Reward prediction (TwoHot)
    - Fano synergy
    - H-JEPA prediction
    - Stability

    TIER 3: Auxiliary Losses
    - Value prediction
    - Continue prediction

    Args:
        outputs: RSSMOutput from forward pass
        batch: Dictionary with obs, rewards, continues
        weights: LossWeights for weighting
        twohot_encoder: TwoHotEncoder for reward/value loss

    Returns:
        Tuple of (total_loss, LossOutput)
    """
    if twohot_encoder is None:
        twohot_encoder = TwoHotEncoder()

    # =========================================================================
    # TIER 1: Core Reconstruction Loss (symlog)
    # =========================================================================
    obs_target = symlog(batch["obs"])
    obs_pred = outputs.obs_pred
    recon_loss = jnp.mean(jnp.square(obs_pred - obs_target))

    # =========================================================================
    # TIER 2: Essential Losses
    # =========================================================================

    # KL divergence (already computed in RSSM)
    kl_loss = outputs.kl_balanced
    kl_raw = outputs.kl_raw

    # Reward prediction (TwoHot)
    reward_loss = jnp.array(0.0)
    if batch.get("rewards") is not None:
        reward_logits = outputs.reward_logits
        reward_targets = batch["rewards"]
        reward_loss = twohot_encoder.loss(
            reward_logits.reshape(-1, reward_logits.shape[-1]), reward_targets.flatten()
        )

    # Fano synergy
    fano_loss = compute_fano_synergy_loss(outputs.h)

    # H-JEPA prediction
    hjepa_loss = compute_hjepa_loss(
        outputs.hjepa_pred_1,
        outputs.hjepa_pred_4,
        outputs.hjepa_pred_16,
        outputs.hjepa_target_1,
        outputs.hjepa_target_4,
        outputs.hjepa_target_16,
    )

    # Stability
    stability_loss = compute_stability_loss(outputs.h)

    # =========================================================================
    # TIER 3: Auxiliary Losses
    # =========================================================================

    # Value prediction (TwoHot)
    value_loss = jnp.array(0.0)
    # Note: Would need value targets for this (from returns computation)

    # Continue prediction
    continue_loss = jnp.array(0.0)
    if batch.get("continues") is not None:
        # Would need continue_head output
        pass

    # =========================================================================
    # Total Loss
    # =========================================================================
    total_loss = (
        weights.recon * recon_loss
        + weights.kl * kl_loss
        + weights.reward * reward_loss
        + weights.fano * fano_loss
        + weights.hjepa * hjepa_loss
        + weights.stability * stability_loss
        + weights.value * value_loss
        + weights.continue_ * continue_loss
    )

    return total_loss, LossOutput(
        total=total_loss,
        recon_loss=recon_loss,
        kl_loss=kl_loss,
        kl_raw=kl_raw,
        reward_loss=reward_loss,
        fano_loss=fano_loss,
        hjepa_loss=hjepa_loss,
        stability_loss=stability_loss,
        value_loss=value_loss,
        continue_loss=continue_loss,
    )


# =============================================================================
# LOSS FROM PARAMS (for jax.value_and_grad)
# =============================================================================


def loss_fn(
    params: Any,
    apply_fn: Any,
    batch: dict[str, jnp.ndarray],
    weights: LossWeights,
    key: jax.Array,
) -> tuple[jnp.ndarray, LossOutput]:
    """Loss function compatible with jax.value_and_grad.

    Args:
        params: Model parameters
        apply_fn: Model apply function
        batch: Training batch
        weights: Loss weights
        key: Random key

    Returns:
        Tuple of (loss, metrics)
    """
    outputs = apply_fn(
        {"params": params},
        obs=batch["obs"],
        actions=batch["actions"],
        rewards=batch.get("rewards"),
        continues=batch.get("continues"),
        key=key,
        training=True,
    )

    twohot = TwoHotEncoder()
    return compute_full_loss(outputs, batch, weights, twohot)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "LossOutput",
    "LossWeights",
    "compute_fano_synergy_loss",
    "compute_full_loss",
    "compute_hjepa_loss",
    "compute_stability_loss",
    "loss_fn",
]
