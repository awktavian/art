"""Adaptive Data Mixing - Curriculum-Aware Dynamic Sampling.

APOLLO-GRADE TRAINING INFRASTRUCTURE (January 12, 2026)

This module implements ADAPTIVE data mixing that goes beyond static
curriculum weights. It dynamically adjusts data source ratios based on:

1. **Loss Dynamics**: Increase weight for sources with high loss
2. **Gradient Magnitude**: Prioritize sources producing informative gradients
3. **Curriculum Phase**: Base weights from curriculum, adapted dynamically
4. **Diversity Maintenance**: Ensure all sources remain represented
5. **Convergence Detection**: Reduce weight for converged sources

WHY ADAPTIVE > STATIC:
======================
Static curriculum mixing (e.g., JEPA=0.6, QM9=0.2, ToL=0.2) has problems:
- Some sources may converge faster, wasting compute
- Some sources may be harder, needing more samples
- Phase-specific needs vary per training run
- Domain shift between sources requires adaptation

ADAPTIVE ALGORITHM:
==================
```
For each batch:
    1. Sample batch from each source
    2. Compute per-source loss and gradient norms
    3. Update running statistics (EMA)
    4. Compute adaptive weights:
       weight_i = base_i * (loss_i / mean_loss) * diversity_factor
    5. Normalize weights, ensure minimum threshold
    6. Sample next batch using adaptive weights
```

The key insight: sources with higher-than-average loss need more samples,
but we maintain diversity by enforcing minimum weights per source.

References:
- AutoML-Zero: Evolving Machine Learning Algorithms from Scratch
- Data Mixing Laws: DML (Xie et al., 2024)
- Curriculum Learning: Bengio et al. (2009)

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

import jax
import jax.numpy as jnp

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class AdaptiveDataConfig:
    """Configuration for adaptive data mixing.

    REASONING for each parameter:

    - adaptation_rate (0.1): How quickly to update weights. Too high = unstable,
      too low = slow to adapt. 0.1 is a good balance.

    - loss_sensitivity (1.0): Scaling for loss-based adaptation. Higher values
      make adaptation more aggressive based on loss differences.

    - gradient_sensitivity (0.5): Scaling for gradient-based adaptation. Lower
      than loss_sensitivity because gradients are noisier.

    - min_weight (0.05): Minimum weight per source to maintain diversity.
      5% ensures every source is sampled at least occasionally.

    - diversity_bonus (0.1): Extra weight given to undersampled sources.
      Prevents mode collapse to single source.

    - ema_decay (0.99): Smoothing for running statistics. High value for
      stability, prevents overreaction to single batch.

    - warmup_steps (1000): Steps before adaptation kicks in. Need baseline
      statistics before adapting.

    - log_interval (100): How often to log adaptation statistics.
    """

    # Adaptation dynamics
    adaptation_rate: float = 0.1  # How fast to update weights
    loss_sensitivity: float = 1.0  # How much loss affects weight
    gradient_sensitivity: float = 0.5  # How much gradients affect weight

    # Diversity preservation
    min_weight: float = 0.05  # Minimum weight per source
    diversity_bonus: float = 0.1  # Bonus for undersampled sources

    # Smoothing
    ema_decay: float = 0.99  # EMA for running statistics

    # Scheduling
    warmup_steps: int = 1000  # Steps before adaptation starts
    cooldown_factor: float = 0.9  # Reduce adaptation rate over time

    # Logging
    log_interval: int = 100


# =============================================================================
# SOURCE STATISTICS
# =============================================================================


@dataclass
class SourceStats:
    """Running statistics for a data source."""

    name: str
    base_weight: float = 0.2  # From curriculum
    current_weight: float = 0.2  # Adaptive weight

    # Running averages (EMA)
    loss_ema: float = 1.0  # Running loss average
    grad_norm_ema: float = 1.0  # Running gradient norm

    # Counters
    samples_seen: int = 0
    batches_since_sample: int = 0  # For diversity tracking

    # History for analysis
    weight_history: deque = field(default_factory=lambda: deque(maxlen=100))
    loss_history: deque = field(default_factory=lambda: deque(maxlen=100))


# =============================================================================
# ADAPTIVE MIXER
# =============================================================================


class AdaptiveDataMixer:
    """Dynamically adjusts data source mixing ratios.

    USAGE:
    ------
    ```python
    mixer = AdaptiveDataMixer(config, sources)

    # Each training step:
    for step in range(num_steps):
        # Get adaptive weights
        weights = mixer.get_weights()

        # Sample batch using weights
        batch = sample_batch_weighted(sources, weights)

        # Compute loss and gradients
        loss, grads = train_step(model, batch)

        # Update mixer with metrics
        per_source_losses = compute_per_source_loss(batch, source_masks)
        per_source_grads = compute_per_source_grad_norm(grads, source_masks)
        mixer.update(step, per_source_losses, per_source_grads)
    ```
    """

    def __init__(
        self,
        config: AdaptiveDataConfig,
        source_names: list[str],
        base_weights: dict[str, float] | None = None,
    ):
        """Initialize adaptive mixer.

        Args:
            config: Mixer configuration
            source_names: List of source names (e.g., ["jepa", "qm9", "tol"])
            base_weights: Initial weights from curriculum
        """
        self.config = config
        self.source_names = source_names

        # Default to uniform if no base weights
        if base_weights is None:
            base_weights = {name: 1.0 / len(source_names) for name in source_names}

        # Initialize source statistics
        self.sources: dict[str, SourceStats] = {}
        for name in source_names:
            self.sources[name] = SourceStats(
                name=name,
                base_weight=base_weights.get(name, 0.1),
                current_weight=base_weights.get(name, 0.1),
            )

        # Global statistics
        self._global_loss_ema = 1.0
        self._global_grad_ema = 1.0
        self._step = 0

        logger.info(
            f"AdaptiveDataMixer initialized: {len(source_names)} sources, "
            f"base_weights={base_weights}"
        )

    def get_weights(self) -> dict[str, float]:
        """Get current adaptive weights.

        Returns:
            Dict mapping source name to weight
        """
        return {name: stats.current_weight for name, stats in self.sources.items()}

    def get_weights_array(self) -> jnp.ndarray:
        """Get weights as JAX array (for sampling).

        Returns:
            [num_sources] array of weights
        """
        return jnp.array([self.sources[name].current_weight for name in self.source_names])

    def update(
        self,
        step: int,
        per_source_losses: dict[str, float],
        per_source_grads: dict[str, float] | None = None,
    ) -> None:
        """Update adaptive weights based on training metrics.

        ALGORITHM:
        1. Update EMA statistics for each source
        2. Compute loss-based adjustment: sources with higher loss get more weight
        3. Compute gradient-based adjustment: sources with larger gradients are useful
        4. Apply diversity bonus: increase weight for undersampled sources
        5. Normalize and clip weights

        Args:
            step: Current training step
            per_source_losses: Dict of source_name -> loss value
            per_source_grads: Dict of source_name -> gradient norm (optional)
        """
        self._step = step
        cfg = self.config

        # Skip during warmup
        if step < cfg.warmup_steps:
            return

        # Effective adaptation rate (decays over time)
        adaptation_rate = cfg.adaptation_rate * (cfg.cooldown_factor ** (step / 10000))

        # Update source statistics
        for name, loss in per_source_losses.items():
            if name not in self.sources:
                continue

            stats = self.sources[name]

            # Update loss EMA
            stats.loss_ema = cfg.ema_decay * stats.loss_ema + (1 - cfg.ema_decay) * loss
            stats.loss_history.append(loss)
            stats.samples_seen += 1
            stats.batches_since_sample = 0

            # Update gradient norm EMA if provided
            if per_source_grads and name in per_source_grads:
                grad = per_source_grads[name]
                stats.grad_norm_ema = (
                    cfg.ema_decay * stats.grad_norm_ema + (1 - cfg.ema_decay) * grad
                )

        # Update global EMAs
        mean_loss = sum(s.loss_ema for s in self.sources.values()) / len(self.sources)
        self._global_loss_ema = (
            cfg.ema_decay * self._global_loss_ema + (1 - cfg.ema_decay) * mean_loss
        )

        mean_grad = sum(s.grad_norm_ema for s in self.sources.values()) / len(self.sources)
        self._global_grad_ema = (
            cfg.ema_decay * self._global_grad_ema + (1 - cfg.ema_decay) * mean_grad
        )

        # === ADAPTIVE WEIGHT COMPUTATION ===
        new_weights = {}

        for name, stats in self.sources.items():
            # Base weight from curriculum
            weight = stats.base_weight

            # Loss-based adjustment: higher loss = more weight
            if self._global_loss_ema > 0:
                loss_ratio = stats.loss_ema / self._global_loss_ema
                loss_adjustment = 1.0 + cfg.loss_sensitivity * (loss_ratio - 1.0)
                weight *= loss_adjustment

            # Gradient-based adjustment: higher gradient = more informative
            if per_source_grads and self._global_grad_ema > 0:
                grad_ratio = stats.grad_norm_ema / self._global_grad_ema
                grad_adjustment = 1.0 + cfg.gradient_sensitivity * (grad_ratio - 1.0)
                weight *= grad_adjustment

            # Diversity bonus: increase weight for undersampled sources
            stats.batches_since_sample += 1
            if stats.batches_since_sample > 10:
                weight *= 1.0 + cfg.diversity_bonus

            new_weights[name] = weight

        # Normalize weights
        total = sum(new_weights.values())
        if total > 0:
            for name in new_weights:
                new_weights[name] /= total

        # Enforce minimum weights
        for name in new_weights:
            new_weights[name] = max(cfg.min_weight, new_weights[name])

        # Re-normalize after clipping
        total = sum(new_weights.values())
        for name in new_weights:
            new_weights[name] /= total

        # Smooth update (gradual change)
        for name, new_weight in new_weights.items():
            stats = self.sources[name]
            stats.current_weight = (
                1 - adaptation_rate
            ) * stats.current_weight + adaptation_rate * new_weight
            stats.weight_history.append(stats.current_weight)

        # Logging
        if step % cfg.log_interval == 0:
            weight_str = ", ".join(f"{n}={s.current_weight:.3f}" for n, s in self.sources.items())
            logger.info(f"Step {step} adaptive weights: {weight_str}")

    def set_curriculum_phase(
        self,
        phase_name: str,
        phase_weights: dict[str, float],
    ) -> None:
        """Update base weights from curriculum phase change.

        When curriculum advances, update base weights but maintain
        adaptive adjustments.

        Args:
            phase_name: Name of new phase (e.g., "GEOMETRY", "DYNAMICS")
            phase_weights: Base weights for this phase
        """
        logger.info(f"Curriculum phase change to {phase_name}: {phase_weights}")

        for name, base_weight in phase_weights.items():
            if name in self.sources:
                self.sources[name].base_weight = base_weight
                # Soft reset current weight towards new base
                self.sources[name].current_weight = (
                    0.7 * self.sources[name].current_weight + 0.3 * base_weight
                )

    def get_statistics(self) -> dict[str, dict]:
        """Get detailed statistics for each source.

        Returns:
            Dict of source_name -> statistics dict
        """
        return {
            name: {
                "base_weight": stats.base_weight,
                "current_weight": stats.current_weight,
                "loss_ema": stats.loss_ema,
                "grad_norm_ema": stats.grad_norm_ema,
                "samples_seen": stats.samples_seen,
                "batches_since_sample": stats.batches_since_sample,
            }
            for name, stats in self.sources.items()
        }


# =============================================================================
# WEIGHTED BATCH SAMPLER
# =============================================================================


class WeightedBatchSampler:
    """Sample batches from multiple sources using adaptive weights.

    Given iterators over multiple data sources, sample from them
    according to the adaptive weights.
    """

    def __init__(
        self,
        source_iterators: dict[str, iter],
        mixer: AdaptiveDataMixer,
        batch_size: int,
        seed: int = 42,
    ):
        """Initialize sampler.

        Args:
            source_iterators: Dict of source_name -> data iterator
            mixer: AdaptiveDataMixer instance
            batch_size: Total batch size
            seed: Random seed
        """
        self.source_iterators = source_iterators
        self.mixer = mixer
        self.batch_size = batch_size
        self.rng = jax.random.PRNGKey(seed)

    def sample_batch(self) -> tuple[dict, jnp.ndarray]:
        """Sample a mixed batch using adaptive weights.

        Returns:
            (batch_data, source_indices) tuple
            - batch_data: Dict containing batch tensors
            - source_indices: [batch_size] array indicating source per sample
        """
        weights = self.mixer.get_weights_array()
        source_names = self.mixer.source_names

        # Split RNG
        self.rng, sample_key = jax.random.split(self.rng)

        # Sample source indices for each batch element
        source_indices = jax.random.categorical(
            sample_key,
            jnp.log(weights + 1e-8),
            shape=(self.batch_size,),
        )

        # Count samples per source
        counts = {}
        for i, name in enumerate(source_names):
            counts[name] = int(jnp.sum(source_indices == i))

        # Sample from each source
        all_samples = []
        for name, count in counts.items():
            if count > 0:
                iterator = self.source_iterators[name]
                for _ in range(count):
                    try:
                        sample = next(iterator)
                        all_samples.append((name, sample))
                    except StopIteration:
                        # Reset iterator
                        self.source_iterators[name] = iter(self.source_iterators[name])
                        sample = next(self.source_iterators[name])
                        all_samples.append((name, sample))

        # Shuffle samples to mix sources within batch
        self.rng, shuffle_key = jax.random.split(self.rng)
        perm = jax.random.permutation(shuffle_key, len(all_samples))
        shuffled = [all_samples[i] for i in perm]

        # Collate
        # (This is a simplified version - real implementation would stack tensors)
        batch_data = {"samples": [s[1] for s in shuffled]}
        source_mask = jnp.array([source_names.index(s[0]) for s in shuffled])

        return batch_data, source_mask


# =============================================================================
# CURRICULUM-AWARE FACTORY
# =============================================================================


def create_adaptive_mixer_for_curriculum(
    curriculum_phase: str,
    config: AdaptiveDataConfig | None = None,
) -> AdaptiveDataMixer:
    """Create adaptive mixer initialized for a curriculum phase.

    CURRICULUM PHASE WEIGHTS (REASONING):
    =====================================

    WARMUP (100% JEPA):
        - Start with pure reconstruction
        - No curriculum mixing yet
        - Need stable baseline

    GEOMETRY (60% JEPA, 20% QM9, 20% ToL):
        - JEPA teaches temporal dynamics
        - QM9 teaches SE(3) structure (molecular symmetries)
        - ToL teaches hierarchical structure

    ROTATION (50% JEPA, 20% QM9, 20% ToL, 10% GEN):
        - Add generation to test learned structure
        - QM9 still important for equivariance

    DYNAMICS (45% JEPA, 20% QM9, 20% ToL, 15% GEN):
        - Increase generation slightly
        - World model prediction is primary goal

    JOINT (35% JEPA, 15% QM9, 15% ToL, 35% GEN):
        - Balance JEPA and generation
        - Full RSSM + EFE training

    GENERATION (25% JEPA, 15% QM9, 10% ToL, 50% GEN):
        - Heavy on generation
        - Fine-grained control

    LANGUAGE (30% JEPA, 10% QM9, 10% ToL, 30% LANG, 20% INST):
        - Add language sources
        - Reduce geometry sources
        - Language grounding is priority

    Args:
        curriculum_phase: Phase name
        config: Optional configuration

    Returns:
        Configured AdaptiveDataMixer
    """
    if config is None:
        config = AdaptiveDataConfig()

    # Phase-specific base weights
    phase_weights = {
        "WARMUP": {"jepa": 1.0},
        "GEOMETRY": {"jepa": 0.6, "qm9": 0.2, "tree_of_life": 0.2},
        "ROTATION": {"jepa": 0.5, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.1},
        "DYNAMICS": {"jepa": 0.45, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.15},
        "JOINT": {"jepa": 0.35, "qm9": 0.15, "tree_of_life": 0.15, "generation": 0.35},
        "GENERATION": {"jepa": 0.25, "qm9": 0.15, "tree_of_life": 0.1, "generation": 0.5},
        "LANGUAGE": {
            "jepa": 0.3,
            "language": 0.3,
            "instruction": 0.2,
            "qm9": 0.1,
            "tree_of_life": 0.1,
        },
    }

    weights = phase_weights.get(curriculum_phase.upper(), phase_weights["GEOMETRY"])
    source_names = list(weights.keys())

    return AdaptiveDataMixer(config, source_names, weights)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "AdaptiveDataConfig",
    "AdaptiveDataMixer",
    "SourceStats",
    "WeightedBatchSampler",
    "create_adaptive_mixer_for_curriculum",
]
