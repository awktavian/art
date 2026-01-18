"""DoReMi-Style Domain Reweighting for Data Mixing.

Implements Domain Reweighting with Minimax Optimization (DoReMi) for optimal
training data mixing. Based on Stanford CRFM research showing 2.6x training
efficiency improvement over default domain weights.

Key Concepts:
- Excess Loss: loss - reference_loss (measures underperformance per domain)
- Group DRO: Exponentiated gradient ascent on worst-case domain
- Domain Reweighting: Dynamically adjust sampling weights based on excess loss

References:
- DoReMi: Optimizing Data Mixtures Speeds Up Language Model Pretraining
  (Xie et al., NeurIPS 2023, Stanford CRFM)
- https://crfm.stanford.edu/2023/09/14/doremi.html
- https://github.com/sangmichaelxie/doremi

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import jax.numpy as jnp

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class DoReMiConfig:
    """Configuration for DoReMi-style data mixing.

    Args:
        dro_step_size: Step size for exponentiated gradient updates
        dro_smoothing: Smoothing factor for loss tracking
        min_weight: Minimum domain weight (prevents zero-sampling)
        max_weight: Maximum domain weight (prevents single-domain dominance)
        warmup_steps: Steps before starting DRO updates (collect baseline)
        update_frequency: Steps between weight updates
        use_reference_model: Whether to use reference model for excess loss
    """

    dro_step_size: float = 0.01
    dro_smoothing: float = 0.1
    min_weight: float = 0.01
    max_weight: float = 0.9
    warmup_steps: int = 1000
    update_frequency: int = 100
    use_reference_model: bool = False


# =============================================================================
# DOMAIN STATISTICS
# =============================================================================


@dataclass
class DomainStats:
    """Per-domain statistics for DoReMi tracking."""

    name: str
    current_weight: float = 0.1
    cumulative_loss: float = 0.0
    sample_count: int = 0
    reference_loss: float | None = None

    # Exponential moving averages
    loss_ema: float = 1.0
    excess_loss_ema: float = 0.0

    # History for analysis
    weight_history: list[float] = field(default_factory=list)
    loss_history: list[float] = field(default_factory=list)

    def update_ema(self, loss: float, smoothing: float = 0.1) -> None:
        """Update exponential moving averages."""
        self.loss_ema = smoothing * loss + (1 - smoothing) * self.loss_ema

        if self.reference_loss is not None:
            excess = max(0, loss - self.reference_loss)
            self.excess_loss_ema = smoothing * excess + (1 - smoothing) * self.excess_loss_ema


# =============================================================================
# DOREMI MIXER
# =============================================================================


class DoReMiMixer:
    """DoReMi-inspired domain reweighting for optimal data mixing.

    The key insight is that domains where the model underperforms relative
    to a reference (excess loss > 0) should receive higher sampling weight.

    This implements Group Distributionally Robust Optimization (DRO):
    1. Track per-domain loss
    2. Compute excess loss (loss - reference)
    3. Update weights via exponentiated gradient ascent
    4. Sample proportionally to updated weights

    Example:
        >>> mixer = DoReMiMixer(
        ...     domain_names=["jepa", "qm9", "tree_of_life"],
        ...     initial_weights={"jepa": 0.5, "qm9": 0.25, "tree_of_life": 0.25}
        ... )
        >>> # During training
        >>> weights = mixer.get_weights()
        >>> # Sample batch according to weights
        >>> batch = sample_from_domains(weights)
        >>> # After computing loss
        >>> mixer.update({"jepa": 0.05, "qm9": 0.08, "tree_of_life": 0.03})
    """

    def __init__(
        self,
        domain_names: list[str],
        initial_weights: dict[str, float],
        config: DoReMiConfig = DoReMiConfig(),
    ):
        """Initialize DoReMi mixer.

        Args:
            domain_names: List of domain names
            initial_weights: Initial sampling weights per domain
            config: DoReMi configuration
        """
        self.config = config
        self._step = 0

        # Initialize domain statistics
        self.domains: dict[str, DomainStats] = {}
        for name in domain_names:
            weight = initial_weights.get(name, 1.0 / len(domain_names))
            self.domains[name] = DomainStats(name=name, current_weight=weight)

        # Normalize initial weights
        self._normalize_weights()

        logger.info(
            f"DoReMi mixer initialized with {len(domain_names)} domains: "
            f"{', '.join(f'{n}={self.domains[n].current_weight:.2f}' for n in domain_names)}"
        )

    def get_weights(self) -> dict[str, float]:
        """Get current domain sampling weights.

        Returns:
            Dictionary mapping domain name to sampling weight
        """
        return {name: d.current_weight for name, d in self.domains.items()}

    def update(
        self,
        domain_losses: dict[str, float],
        reference_losses: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Update weights based on domain losses.

        Implements Group DRO: upweight domains with high excess loss.

        Args:
            domain_losses: Per-domain loss values from training
            reference_losses: Optional reference model losses for excess computation

        Returns:
            Updated domain weights
        """
        self._step += 1

        # Update domain statistics
        for name, loss in domain_losses.items():
            if name not in self.domains:
                continue

            domain = self.domains[name]
            domain.cumulative_loss += loss
            domain.sample_count += 1
            domain.loss_history.append(loss)

            # Update reference loss if provided
            if reference_losses and name in reference_losses:
                domain.reference_loss = reference_losses[name]

            # Update EMAs
            domain.update_ema(loss, self.config.dro_smoothing)

        # Skip weight updates during warmup
        if self._step < self.config.warmup_steps:
            return self.get_weights()

        # Only update at specified frequency
        if self._step % self.config.update_frequency != 0:
            return self.get_weights()

        # Compute excess losses
        excess_losses = self._compute_excess_losses(domain_losses, reference_losses)

        # Apply Group DRO update
        self._dro_update(excess_losses)

        # Log weight changes
        if self._step % (self.config.update_frequency * 10) == 0:
            weights = self.get_weights()
            logger.info(
                f"DoReMi step {self._step}: "
                f"{', '.join(f'{n}={w:.3f}' for n, w in sorted(weights.items()))}"
            )

        return self.get_weights()

    def _compute_excess_losses(
        self,
        domain_losses: dict[str, float],
        reference_losses: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Compute excess loss per domain.

        Excess loss = max(0, model_loss - reference_loss)

        If no reference is available, use the domain's historical average.
        """
        excess_losses = {}

        for name, loss in domain_losses.items():
            if name not in self.domains:
                continue

            domain = self.domains[name]

            # Get reference loss
            if reference_losses and name in reference_losses:
                ref_loss = reference_losses[name]
            elif domain.reference_loss is not None:
                ref_loss = domain.reference_loss
            else:
                # Use historical average as baseline
                ref_loss = domain.loss_ema * 0.9  # Target 10% below average

            # Excess loss (only positive)
            excess_losses[name] = max(0.0, loss - ref_loss)

        return excess_losses

    def _dro_update(self, excess_losses: dict[str, float]) -> None:
        """Apply Group DRO weight update.

        Implements exponentiated gradient ascent:
        w_i(t+1) = w_i(t) * exp(eta * excess_loss_i) / Z

        where Z is a normalization constant.

        Domains with higher excess loss get upweighted.
        """
        weights = self.get_weights()

        # Compute weighted total excess (DRO objective)
        total_excess = sum(weights.get(name, 0) * loss for name, loss in excess_losses.items())

        if total_excess < 1e-8:
            return  # No update needed

        # Exponentiated gradient update
        for name, loss in excess_losses.items():
            if name not in self.domains:
                continue

            domain = self.domains[name]

            # Gradient: proportional to excess loss
            gradient = loss / (total_excess + 1e-8)

            # Exponentiated gradient: w <- w * exp(eta * grad)
            log_weight = float(jnp.log(domain.current_weight + 1e-8))
            log_weight += self.config.dro_step_size * gradient
            new_weight = float(jnp.exp(log_weight))

            # Clamp to valid range
            domain.current_weight = max(
                self.config.min_weight,
                min(self.config.max_weight, new_weight),
            )

            # Record in history
            domain.weight_history.append(domain.current_weight)

        # Normalize to sum to 1
        self._normalize_weights()

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1."""
        total = sum(d.current_weight for d in self.domains.values())
        if total > 0:
            for domain in self.domains.values():
                domain.current_weight /= total

    def set_reference_losses(self, reference_losses: dict[str, float]) -> None:
        """Set reference losses from a proxy/reference model.

        In the original DoReMi paper, a small (280M) proxy model is trained
        to establish baseline losses per domain.

        Args:
            reference_losses: Per-domain reference loss values
        """
        for name, loss in reference_losses.items():
            if name in self.domains:
                self.domains[name].reference_loss = loss
                logger.info(f"Set reference loss for {name}: {loss:.4f}")

    def get_statistics(self) -> dict[str, Any]:
        """Get mixer statistics for logging/monitoring.

        Returns:
            Dictionary with per-domain statistics
        """
        stats = {
            "step": self._step,
            "domains": {},
        }

        for name, domain in self.domains.items():
            stats["domains"][name] = {
                "weight": domain.current_weight,
                "loss_ema": domain.loss_ema,
                "excess_loss_ema": domain.excess_loss_ema,
                "sample_count": domain.sample_count,
                "reference_loss": domain.reference_loss,
            }

        return stats

    def state_dict(self) -> dict[str, Any]:
        """Get state for checkpointing.

        Returns:
            State dictionary
        """
        return {
            "step": self._step,
            "config": {
                "dro_step_size": self.config.dro_step_size,
                "dro_smoothing": self.config.dro_smoothing,
                "min_weight": self.config.min_weight,
                "max_weight": self.config.max_weight,
            },
            "domains": {
                name: {
                    "current_weight": d.current_weight,
                    "cumulative_loss": d.cumulative_loss,
                    "sample_count": d.sample_count,
                    "reference_loss": d.reference_loss,
                    "loss_ema": d.loss_ema,
                    "excess_loss_ema": d.excess_loss_ema,
                }
                for name, d in self.domains.items()
            },
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Load state from checkpoint.

        Args:
            state: State dictionary
        """
        self._step = state.get("step", 0)

        for name, domain_state in state.get("domains", {}).items():
            if name in self.domains:
                d = self.domains[name]
                d.current_weight = domain_state.get("current_weight", d.current_weight)
                d.cumulative_loss = domain_state.get("cumulative_loss", 0)
                d.sample_count = domain_state.get("sample_count", 0)
                d.reference_loss = domain_state.get("reference_loss")
                d.loss_ema = domain_state.get("loss_ema", 1.0)
                d.excess_loss_ema = domain_state.get("excess_loss_ema", 0.0)

        logger.info(f"Loaded DoReMi state from step {self._step}")


# =============================================================================
# TOPIC-AWARE MIXING (Extension)
# =============================================================================


class TopicAwareMixer(DoReMiMixer):
    """Topic-based mixing that clusters sources by semantic topic.

    Research shows topic-based mixing consistently outperforms source-based
    mixing across DoReMi, temperature-based, and manual methods.

    Reference: Topic Over Source (Arxiv 2502.16802)
    """

    def __init__(
        self,
        topic_clusters: dict[str, list[str]],  # topic -> [sources]
        topic_weights: dict[str, float],
        config: DoReMiConfig = DoReMiConfig(),
    ):
        """Initialize topic-aware mixer.

        Args:
            topic_clusters: Mapping of topic name to list of source names
            topic_weights: Initial weights per topic
            config: DoReMi configuration
        """
        # Flatten sources but track topic membership
        all_sources = []
        self._source_to_topic: dict[str, str] = {}

        for topic, sources in topic_clusters.items():
            for source in sources:
                all_sources.append(source)
                self._source_to_topic[source] = topic

        # Derive per-source weights from topic weights
        initial_weights = {}
        for topic, sources in topic_clusters.items():
            per_source = topic_weights.get(topic, 0.1) / len(sources)
            for source in sources:
                initial_weights[source] = per_source

        super().__init__(all_sources, initial_weights, config)
        self._topic_weights = topic_weights.copy()

    def get_topic_weights(self) -> dict[str, float]:
        """Get aggregated weights by topic."""
        topic_sums: dict[str, float] = defaultdict(float)

        for name, stats in self.domains.items():
            topic = self._source_to_topic[name]
            topic_sums[topic] += stats.current_weight

        return dict(topic_sums)


# =============================================================================
# SOFT DEDUPLICATION (Extension)
# =============================================================================


class SoftDeduplicator:
    """Soft deduplication: reweight duplicates instead of removing.

    Preserves information while reducing redundancy.
    Based on SoftDedup (2025) research.

    Unlike hard deduplication (remove duplicates), soft dedup assigns
    lower weights to repeated samples, allowing the model to still
    see them but with reduced impact.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        min_weight: float = 0.1,
        max_memory: int = 100000,
    ):
        """Initialize soft deduplicator.

        Args:
            similarity_threshold: Threshold for considering samples similar
            min_weight: Minimum weight for highly duplicated samples
            max_memory: Maximum signatures to track (older signatures evicted)
        """
        self.similarity_threshold = similarity_threshold
        self.min_weight = min_weight
        self.max_memory = max_memory

        self._signature_counts: defaultdict[str, int] = defaultdict(int)
        self._access_order: list[str] = []

    def compute_weight(self, text: str) -> float:
        """Compute sample weight based on duplication.

        Higher duplication -> lower weight (but never zero).

        Args:
            text: Sample text

        Returns:
            Weight in range [min_weight, 1.0]
        """
        signature = self._compute_signature(text)

        # Get current count and increment
        count = self._signature_counts[signature]
        self._signature_counts[signature] = count + 1

        # Track access order for eviction
        self._access_order.append(signature)
        self._evict_if_needed()

        # Weight decreases with count (asymptotic to min_weight)
        # w = 1 / (1 + 0.5 * count) approaches min_weight as count -> inf
        weight = 1.0 / (1 + 0.5 * count)
        return max(self.min_weight, weight)

    def _compute_signature(self, text: str, n: int = 5) -> str:
        """Compute locality-sensitive signature.

        Uses character n-grams for fast similarity detection.
        """
        import hashlib

        # Extract n-grams from beginning of text
        ngrams = set()
        text_sample = text[:500]  # First 500 chars
        for i in range(len(text_sample) - n + 1):
            ngrams.add(text_sample[i : i + n])

        # Sort and hash top ngrams
        sorted_ngrams = sorted(ngrams)[:20]
        signature = hashlib.md5("".join(sorted_ngrams).encode()).hexdigest()
        return signature

    def _evict_if_needed(self) -> None:
        """Evict oldest signatures if over memory limit."""
        while len(self._signature_counts) > self.max_memory:
            # Evict oldest accessed signature
            if self._access_order:
                oldest = self._access_order.pop(0)
                if oldest in self._signature_counts:
                    del self._signature_counts[oldest]

    def reset(self) -> None:
        """Reset signature counts (for new epoch)."""
        self._signature_counts.clear()
        self._access_order.clear()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DoReMiConfig",
    "DoReMiMixer",
    "DomainStats",
    "SoftDeduplicator",
    "TopicAwareMixer",
]
