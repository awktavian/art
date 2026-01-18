"""JAX DreamerV3 Transforms - Mirrors PyTorch dreamer_transforms.py.

BRICK-BY-BRICK COMPARISON:
=========================
PyTorch Source                          | JAX Target
----------------------------------------|-------------------------------------
dreamer_transforms.py:symlog            | symlog()
dreamer_transforms.py:symexp            | symexp()
dreamer_transforms.py:symlog_loss       | symlog_loss()
dreamer_transforms.py:balanced_kl_loss  | balanced_kl_loss()
dreamer_transforms.py:TwoHotEncoder     | TwoHotEncoder
dreamer_transforms.py:PercentileNorm    | PercentileNormalizer
dreamer_transforms.py:spherical_softmax | spherical_softmax()
dreamer_transforms.py:spherical_interp  | spherical_interpolate()
dreamer_transforms.py:unimix_categorical| unimix_categorical()

Created: January 8, 2026
"""

from __future__ import annotations

from typing import NamedTuple

import jax
import jax.numpy as jnp
from jax import random

# =============================================================================
# SYMLOG / SYMEXP TRANSFORMS
# =============================================================================


def symlog(x: jnp.ndarray, eps: float = 1e-8) -> jnp.ndarray:
    """Symmetric logarithm - compresses large magnitudes.

    PyTorch: dreamer_transforms.py:symlog()

    symlog(x) = sign(x) * ln(|x| + 1)

    Properties:
    - symlog(0) = 0
    - Preserves sign
    - Linear near origin (gradient ≈ 1 for small x)
    - Logarithmic for large |x|

    Args:
        x: Any tensor
        eps: Numerical stability epsilon

    Returns:
        Compressed tensor (same shape)
    """
    x_safe = jnp.clip(x, -1e6, 1e6)
    return jnp.sign(x_safe) * jnp.log1p(jnp.abs(x_safe) + eps)


def symexp(x: jnp.ndarray) -> jnp.ndarray:
    """Symmetric exponential - inverse of symlog.

    PyTorch: dreamer_transforms.py:symexp()

    symexp(x) = sign(x) * (exp(|x|) - 1)

    Args:
        x: Symlog-compressed tensor

    Returns:
        Original-scale tensor
    """
    x_clamped = jnp.clip(x, -80.0, 80.0)
    return jnp.sign(x_clamped) * jnp.expm1(jnp.abs(x_clamped))


def symlog_loss(pred: jnp.ndarray, target: jnp.ndarray, eps: float = 1e-8) -> jnp.ndarray:
    """Squared error in symlog space.

    PyTorch: dreamer_transforms.py:symlog_loss()

    L = ||symlog(pred) - symlog(target)||²

    More robust than MSE for targets with varying scales.

    Args:
        pred: Predicted values
        target: Target values
        eps: Numerical stability epsilon

    Returns:
        Loss scalar
    """
    return jnp.mean(jnp.square(symlog(pred, eps) - symlog(target, eps)))


# =============================================================================
# KL BALANCING WITH FREE BITS
# =============================================================================


class KLInfo(NamedTuple):
    """KL loss information."""

    kl_dyn: jnp.ndarray
    kl_rep: jnp.ndarray
    kl_raw: jnp.ndarray
    kl_total: jnp.ndarray


def balanced_kl_loss(
    post_probs: jnp.ndarray,
    prior_probs: jnp.ndarray,
    free_bits: float = 1.0,
    dyn_weight: float = 0.8,
    rep_weight: float = 0.2,
) -> tuple[jnp.ndarray, KLInfo]:
    """DreamerV3-style KL balancing with gradient-preserving free bits.

    PyTorch: dreamer_transforms.py:balanced_kl_loss_categorical()

    Computes two asymmetric KL terms with stop-gradients:
    1. DYNAMICS LOSS: KL[sg(posterior) || prior] - trains prior
    2. REPRESENTATION LOSS: KL[posterior || sg(prior)] - trains posterior

    GRADIENT-PRESERVING FREE BITS:
    The standard max(free_bits, KL) blocks gradients when KL < free_bits.
    We use a soft version: kl_soft = KL + free_bits * softplus(1 - KL/free_bits)

    Args:
        post_probs: [B, 7, K] posterior probabilities
        prior_probs: [B, 7, K] prior probabilities
        free_bits: Minimum KL in nats (DreamerV3 default: 1.0)
        dyn_weight: Weight for dynamics loss (default 0.8)
        rep_weight: Weight for representation loss (default 0.2)

    Returns:
        Tuple of (total_loss, KLInfo)
    """
    eps = 1e-6

    # Clamp and normalize
    post_probs = jnp.clip(post_probs, eps, 1.0)
    prior_probs = jnp.clip(prior_probs, eps, 1.0)
    post_probs = post_probs / jnp.sum(post_probs, axis=-1, keepdims=True)
    prior_probs = prior_probs / jnp.sum(prior_probs, axis=-1, keepdims=True)

    # Dynamics loss: KL[sg(post) || prior]
    post_sg = jax.lax.stop_gradient(post_probs)
    kl_dyn_raw = jnp.sum(post_sg * (jnp.log(post_sg + eps) - jnp.log(prior_probs + eps)), axis=-1)
    kl_dyn_raw = jnp.maximum(kl_dyn_raw, 0.0)

    # Representation loss: KL[post || sg(prior)]
    prior_sg = jax.lax.stop_gradient(prior_probs)
    kl_rep_raw = jnp.sum(
        post_probs * (jnp.log(post_probs + eps) - jnp.log(prior_sg + eps)), axis=-1
    )
    kl_rep_raw = jnp.maximum(kl_rep_raw, 0.0)

    # Gradient-preserving free bits
    scale = 0.5
    kl_dyn = kl_dyn_raw + free_bits * scale * jax.nn.softplus(
        (free_bits - kl_dyn_raw) / (free_bits + eps)
    )
    kl_rep = kl_rep_raw + free_bits * scale * jax.nn.softplus(
        (free_bits - kl_rep_raw) / (free_bits + eps)
    )

    # Weighted combination
    total_loss = dyn_weight * jnp.mean(kl_dyn) + rep_weight * jnp.mean(kl_rep)

    # Raw KL for logging
    kl_raw = jnp.mean(
        jnp.maximum(
            jnp.sum(post_probs * (jnp.log(post_probs + eps) - jnp.log(prior_probs + eps)), axis=-1),
            0.0,
        )
    )

    info = KLInfo(
        kl_dyn=jnp.mean(kl_dyn),
        kl_rep=jnp.mean(kl_rep),
        kl_raw=kl_raw,
        kl_total=total_loss,
    )

    return total_loss, info


# =============================================================================
# TWOHOT ENCODING
# =============================================================================


class TwoHotEncoder:
    """Two-hot encoding for continuous values.

    PyTorch: dreamer_transforms.py:TwoHotEncoder

    DreamerV3 uses twohot encoding for reward/return prediction:
    - Values are encoded as soft distribution over bins
    - Bins are exponentially spaced (symexp) for varying scales
    - Network predicts logits, loss is cross-entropy with twohot target
    """

    def __init__(
        self,
        num_bins: int = 255,
        low: float = -20.0,
        high: float = 20.0,
    ):
        self.num_bins = num_bins
        bins_linear = jnp.linspace(low, high, num_bins)
        self.bins = symexp(bins_linear)

    def encode(self, values: jnp.ndarray) -> jnp.ndarray:
        """Encode values as twohot distribution.

        Args:
            values: [...] tensor of values

        Returns:
            [..., num_bins] soft distribution over bins
        """
        original_shape = values.shape
        values_flat = values.flatten()

        # Clamp to bin range
        bin_min, bin_max = self.bins[0], self.bins[-1]
        values_clamped = jnp.clip(values_flat, bin_min, bin_max)

        # Find left bin index
        left_idx = jnp.searchsorted(self.bins, values_clamped) - 1
        left_idx = jnp.clip(left_idx, 0, self.num_bins - 2)
        right_idx = left_idx + 1

        # Interpolation weights
        left_val = self.bins[left_idx]
        right_val = self.bins[right_idx]
        right_weight = (values_clamped - left_val) / (right_val - left_val + 1e-8)
        left_weight = 1 - right_weight

        # Create twohot distribution
        twohot = jnp.zeros((values_flat.shape[0], self.num_bins))
        batch_indices = jnp.arange(values_flat.shape[0])
        twohot = twohot.at[batch_indices, left_idx].set(left_weight)
        twohot = twohot.at[batch_indices, right_idx].set(right_weight)

        return twohot.reshape(*original_shape, self.num_bins)

    def decode(self, logits: jnp.ndarray) -> jnp.ndarray:
        """Decode logits to expected value.

        Args:
            logits: [..., num_bins] logits

        Returns:
            [...] expected values
        """
        probs = jax.nn.softmax(logits, axis=-1)
        return jnp.sum(probs * self.bins, axis=-1)

    def loss(self, logits: jnp.ndarray, targets: jnp.ndarray) -> jnp.ndarray:
        """Cross-entropy loss with twohot targets.

        Args:
            logits: [..., num_bins] predicted logits
            targets: [...] target values

        Returns:
            Loss scalar
        """
        twohot = self.encode(targets)
        log_probs = jax.nn.log_softmax(logits, axis=-1)
        return -jnp.mean(jnp.sum(twohot * log_probs, axis=-1))


# =============================================================================
# PERCENTILE NORMALIZATION
# =============================================================================


class PercentileNormalizer:
    """Normalize returns using running percentiles.

    PyTorch: dreamer_transforms.py:PercentileNormalizer

    DreamerV3 uses percentile-based normalization:
        norm_return = (return - p5) / max(1, p95 - p5)

    Benefits:
    - Robust to outliers (unlike min-max)
    - Allows fixed entropy coefficient
    - Adapts to changing reward scales
    """

    def __init__(
        self,
        percentile_low: float = 5.0,
        percentile_high: float = 95.0,
        decay: float = 0.99,
    ):
        self.percentile_low = percentile_low / 100.0
        self.percentile_high = percentile_high / 100.0
        self.decay = decay

        # Running statistics
        self.p_low = 0.0
        self.p_high = 1.0
        self.initialized = False

    def update(self, values: jnp.ndarray) -> None:
        """Update running percentile estimates."""
        low = float(jnp.quantile(values.flatten(), self.percentile_low))
        high = float(jnp.quantile(values.flatten(), self.percentile_high))

        if not self.initialized:
            self.p_low = low
            self.p_high = high
            self.initialized = True
        else:
            self.p_low = self.decay * self.p_low + (1 - self.decay) * low
            self.p_high = self.decay * self.p_high + (1 - self.decay) * high

    def normalize(self, values: jnp.ndarray, update: bool = True) -> jnp.ndarray:
        """Normalize values using percentiles.

        Args:
            values: Tensor to normalize
            update: Whether to update running estimates

        Returns:
            Normalized tensor in ~[0, 1]
        """
        if update:
            self.update(values)

        scale = max(self.p_high - self.p_low, 1.0)
        return (values - self.p_low) / scale


# =============================================================================
# SPHERICAL OPERATIONS (S7 Geodesic)
# =============================================================================


def spherical_softmax(
    x: jnp.ndarray,
    dim: int = -1,
    temperature: float = 1.0,
) -> jnp.ndarray:
    """Spherical softmax - projects to unit sphere instead of simplex.

    PyTorch: dreamer_transforms.py:spherical_softmax()

    Unlike standard softmax (projects to simplex, sum=1),
    spherical softmax projects to unit sphere (L2 norm=1).
    This respects the Riemannian geometry of S7.

    Args:
        x: Input tensor [..., D]
        dim: Dimension to normalize
        temperature: Temperature scaling

    Returns:
        Normalized tensor on unit sphere
    """
    x_scaled = x / temperature
    x_shifted = x_scaled - jnp.max(x_scaled, axis=dim, keepdims=True)
    x_exp = jnp.exp(x_shifted)

    # L2 normalization instead of sum normalization
    norm = jnp.sqrt(jnp.sum(x_exp**2, axis=dim, keepdims=True) + 1e-8)
    return x_exp / norm


def spherical_interpolate(
    x: jnp.ndarray,
    y: jnp.ndarray,
    t: float | jnp.ndarray,
) -> jnp.ndarray:
    """Spherical linear interpolation (SLERP) on S7.

    PyTorch: dreamer_transforms.py:spherical_interpolate()

    Interpolates along the great circle (geodesic) between two points.

    slerp(x, y, t) = sin((1-t)θ)/sin(θ) * x + sin(tθ)/sin(θ) * y

    Args:
        x: Start point on unit sphere [..., D]
        y: End point on unit sphere [..., D]
        t: Interpolation parameter in [0, 1]

    Returns:
        Interpolated point on unit sphere
    """
    # Normalize inputs
    x = x / (jnp.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)
    y = y / (jnp.linalg.norm(y, axis=-1, keepdims=True) + 1e-8)

    # Compute angle
    dot = jnp.clip(jnp.sum(x * y, axis=-1, keepdims=True), -1.0, 1.0)
    theta = jnp.arccos(dot)
    sin_theta = jnp.sin(theta)

    # Handle small angles (linear interpolation fallback)
    small_angle = jnp.abs(sin_theta) < 1e-6

    # SLERP
    if isinstance(t, (int, float)):
        t = jnp.array(t)

    coeff_x = jnp.sin((1 - t) * theta) / (sin_theta + 1e-8)
    coeff_y = jnp.sin(t * theta) / (sin_theta + 1e-8)

    result = coeff_x * x + coeff_y * y

    # Fallback for small angles
    linear = (1 - t) * x + t * y
    linear_norm = linear / (jnp.linalg.norm(linear, axis=-1, keepdims=True) + 1e-8)

    result = jnp.where(small_angle, linear_norm, result)

    return result / (jnp.linalg.norm(result, axis=-1, keepdims=True) + 1e-8)


# =============================================================================
# CATEGORICAL OPERATIONS
# =============================================================================


def unimix_categorical(probs: jnp.ndarray, unimix: float = 0.01) -> jnp.ndarray:
    """Mix categorical distribution with uniform.

    PyTorch: dreamer_transforms.py:unimix_categorical()

    DreamerV3 uses this to prevent categorical distributions from becoming
    deterministic (which blocks gradients).

    p_mixed = (1 - unimix) * softmax(logits) + unimix * uniform

    Args:
        probs: [..., K] probabilities
        unimix: Mixing coefficient (default 0.01 = 1%)

    Returns:
        [..., K] mixed probabilities
    """
    K = probs.shape[-1]
    uniform = jnp.ones_like(probs) / K
    return (1 - unimix) * probs + unimix * uniform


def gumbel_softmax(
    key: jax.Array,
    logits: jnp.ndarray,
    temperature: float = 1.0,
    hard: bool = True,
) -> jnp.ndarray:
    """Gumbel-softmax for differentiable categorical sampling.

    Args:
        key: JAX random key
        logits: [..., K] unnormalized logits
        temperature: Temperature for softmax
        hard: Whether to use straight-through estimator

    Returns:
        [..., K] sampled (one-hot if hard=True, soft otherwise)
    """
    u = random.uniform(key, logits.shape, minval=1e-10, maxval=1.0)
    gumbel_noise = -jnp.log(-jnp.log(u))
    y_soft = jax.nn.softmax((logits + gumbel_noise) / temperature, axis=-1)

    if hard:
        # Straight-through estimator
        y_hard = jax.nn.one_hot(jnp.argmax(y_soft, axis=-1), logits.shape[-1])
        return y_hard - jax.lax.stop_gradient(y_soft) + y_soft

    return y_soft


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "KLInfo",
    # Percentile normalization
    "PercentileNormalizer",
    # TwoHot
    "TwoHotEncoder",
    # KL balancing
    "balanced_kl_loss",
    "gumbel_softmax",
    "spherical_interpolate",
    # Spherical ops
    "spherical_softmax",
    "symexp",
    # Symlog transforms
    "symlog",
    "symlog_loss",
    # Categorical ops
    "unimix_categorical",
]
