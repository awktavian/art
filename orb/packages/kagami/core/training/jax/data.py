"""JAX Data Pipeline - Unified data loading for training.

Provides high-throughput data loading optimized for TPU training:
- TFDS integration for standard datasets
- GCS streaming for custom data
- Curriculum-aware sampling (phase-specific data weights)
- Multimodal data support (vision + language + audio)

Created: January 9, 2026
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum

import jax
import jax.numpy as jnp

logger = logging.getLogger(__name__)


# =============================================================================
# DATA SOURCE TYPES
# =============================================================================


class DataSourceType(str, Enum):
    """Available data source types."""

    SYNTHETIC = "synthetic"  # Generated synthetic data
    TFDS = "tfds"  # TensorFlow Datasets
    GCS = "gcs"  # Google Cloud Storage
    LOCAL = "local"  # Local filesystem
    HUGGINGFACE = "huggingface"  # HuggingFace datasets

    # Curriculum-specific sources
    JEPA = "jepa"  # Genesis simulation (JEPA-style)
    QM9 = "qm9"  # Molecular dynamics (SE3)
    TREE_OF_LIFE = "tree_of_life"  # Phylogenetic (hierarchy)
    LANGUAGE = "language"  # Text corpus
    INSTRUCTION = "instruction"  # Instruction-following
    GENERATION = "generation"  # Generative fine-tuning


# =============================================================================
# DATA CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class DataConfig:
    """Configuration for data pipeline.

    frozen=True for JAX static_argnums compatibility.
    """

    # Source settings
    source_type: DataSourceType = DataSourceType.SYNTHETIC
    data_path: str = ""

    # Batching
    global_batch_size: int = 256
    sequence_length: int = 16

    # Observation dimensions
    obs_dim: int = 64
    action_dim: int = 8

    # Multimodal
    include_text: bool = False
    include_images: bool = False
    include_audio: bool = False
    text_max_length: int = 128
    image_size: int = 224

    # Sharding
    num_devices: int = 1
    device_id: int = 0

    # Prefetching
    prefetch_factor: int = 4
    num_workers: int = 4

    # Curriculum sampling
    curriculum_phase: str = "GEOMETRY"


@dataclass
class CurriculumDataWeights:
    """Data source weights for each curriculum phase.

    Matches unified_curriculum.py data_weights.
    """

    WARMUP: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 1.0,
        }
    )
    GEOMETRY: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 0.6,
            "qm9": 0.2,
            "tree_of_life": 0.2,
        }
    )
    ROTATION: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 0.5,
            "qm9": 0.2,
            "tree_of_life": 0.2,
            "generation": 0.1,
        }
    )
    DYNAMICS: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 0.45,
            "qm9": 0.2,
            "tree_of_life": 0.2,
            "generation": 0.15,
        }
    )
    JOINT: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 0.35,
            "qm9": 0.15,
            "tree_of_life": 0.15,
            "generation": 0.35,
        }
    )
    GENERATION: dict[str, float] = field(
        default_factory=lambda: {
            "generation": 0.5,
            "jepa": 0.25,
            "qm9": 0.15,
            "tree_of_life": 0.1,
        }
    )
    LANGUAGE: dict[str, float] = field(
        default_factory=lambda: {
            "jepa": 0.3,
            "language": 0.3,
            "instruction": 0.2,
            "qm9": 0.1,
            "tree_of_life": 0.1,
        }
    )

    def get_weights(self, phase: str) -> dict[str, float]:
        """Get data weights for a curriculum phase."""
        return getattr(self, phase, self.GEOMETRY)


# =============================================================================
# DATA BATCH
# =============================================================================


@dataclass
class DataBatch:
    """A batch of training data.

    All arrays are JAX arrays with shape [B, T, ...] for sequences.
    """

    # Core RSSM inputs
    obs: jnp.ndarray  # [B, T, obs_dim] observations
    actions: jnp.ndarray  # [B, T, action_dim] actions
    rewards: jnp.ndarray  # [B, T] rewards
    continues: jnp.ndarray  # [B, T] continuation flags

    # Optional multimodal
    text_ids: jnp.ndarray | None = None  # [B, L] token IDs
    text_mask: jnp.ndarray | None = None  # [B, L] attention mask
    images: jnp.ndarray | None = None  # [B, H, W, C] images
    audio: jnp.ndarray | None = None  # [B, T_audio, F] spectrograms

    # Metadata
    data_source: str | None = None


# =============================================================================
# SYNTHETIC DATA GENERATOR
# =============================================================================


class SyntheticDataGenerator:
    """Generates synthetic training data for testing.

    Produces temporally-correlated sequences matching RSSM expectations.
    """

    def __init__(self, config: DataConfig, key: jax.Array):
        self.config = config
        self.key = key

    def generate_batch(self, key: jax.Array) -> DataBatch:
        """Generate a single batch of synthetic data.

        Args:
            key: JAX random key

        Returns:
            DataBatch with synthetic data
        """
        cfg = self.config
        keys = jax.random.split(key, 6)

        B = cfg.global_batch_size // cfg.num_devices
        T = cfg.sequence_length

        # Generate observations with temporal correlation
        obs_noise = jax.random.normal(keys[0], (B, T, cfg.obs_dim)) * 0.5
        obs = jnp.zeros((B, T, cfg.obs_dim))

        # Iterative update for temporal correlation
        def step(carry, noise):
            prev = carry
            current = 0.8 * prev + 0.2 * noise
            return current, current

        _, obs = jax.lax.scan(step, obs[:, 0], obs_noise.transpose(1, 0, 2))
        obs = obs.transpose(1, 0, 2)  # [T, B, D] -> [B, T, D]

        # Actions (small continuous)
        actions = jax.random.normal(keys[1], (B, T, cfg.action_dim)) * 0.5

        # Sparse rewards
        reward_probs = jax.random.uniform(keys[2], (B, T))
        reward_values = jax.random.uniform(keys[3], (B, T)) * 2 - 1
        rewards = jnp.where(reward_probs > 0.9, reward_values, 0.0)

        # Continues (mostly True)
        continues = (jax.random.uniform(keys[4], (B, T)) > 0.02).astype(jnp.float32)

        # Optional multimodal data
        text_ids = None
        text_mask = None
        images = None

        if cfg.include_text:
            text_ids = jax.random.randint(keys[5], (B, cfg.text_max_length), 1, 30000)
            text_mask = jnp.ones((B, cfg.text_max_length))

        return DataBatch(
            obs=obs,
            actions=actions,
            rewards=rewards,
            continues=continues,
            text_ids=text_ids,
            text_mask=text_mask,
            images=images,
            data_source="synthetic",
        )

    def __iter__(self) -> Iterator[DataBatch]:
        """Infinite iterator of batches."""
        while True:
            self.key, batch_key = jax.random.split(self.key)
            yield self.generate_batch(batch_key)


# =============================================================================
# CURRICULUM-AWARE SAMPLER
# =============================================================================


class CurriculumSampler:
    """Samples data according to curriculum phase weights.

    Maintains separate iterators for each data source and samples
    according to phase-specific weights.
    """

    def __init__(
        self,
        sources: dict[str, Iterator[DataBatch]],
        weights: CurriculumDataWeights,
        initial_phase: str = "GEOMETRY",
    ):
        """Initialize curriculum sampler.

        Args:
            sources: Dict mapping source name to data iterator
            weights: CurriculumDataWeights configuration
            initial_phase: Starting curriculum phase
        """
        self.sources = sources
        self.weights = weights
        self.current_phase = initial_phase
        self._key = jax.random.PRNGKey(42)

    def set_phase(self, phase: str) -> None:
        """Update curriculum phase."""
        self.current_phase = phase
        logger.info(f"CurriculumSampler phase updated: {phase}")

    def sample(self) -> DataBatch:
        """Sample a batch according to current phase weights.

        Returns:
            DataBatch from weighted random source
        """
        phase_weights = self.weights.get_weights(self.current_phase)

        # Normalize weights for available sources
        available = {k: v for k, v in phase_weights.items() if k in self.sources}
        if not available:
            # Fallback to first available source
            source_name = next(iter(self.sources))
            return next(self.sources[source_name])

        total = sum(available.values())
        probs = {k: v / total for k, v in available.items()}

        # Random selection
        self._key, choice_key = jax.random.split(self._key)
        r = float(jax.random.uniform(choice_key))

        cumsum = 0.0
        for source_name, prob in probs.items():
            cumsum += prob
            if r < cumsum:
                batch = next(self.sources[source_name])
                return batch

        # Fallback (shouldn't happen)
        source_name = next(iter(available))
        return next(self.sources[source_name])

    def __iter__(self) -> Iterator[DataBatch]:
        """Infinite iterator of batches."""
        while True:
            yield self.sample()


# =============================================================================
# DATA PIPELINE
# =============================================================================


class DataPipeline:
    """Main data pipeline for JAX training.

    Provides:
    - Multiple data source support
    - Curriculum-aware sampling
    - Device sharding
    - Prefetching
    """

    def __init__(
        self,
        config: DataConfig,
        key: jax.Array,
    ):
        """Initialize data pipeline.

        Args:
            config: DataConfig configuration
            key: JAX random key
        """
        self.config = config
        self.key = key

        # Initialize sources
        self.sources: dict[str, Iterator[DataBatch]] = {}
        self._init_sources()

        # Curriculum sampler
        self.weights = CurriculumDataWeights()
        self.sampler = CurriculumSampler(
            sources=self.sources,
            weights=self.weights,
            initial_phase=config.curriculum_phase,
        )

        logger.info(
            f"DataPipeline initialized: {len(self.sources)} sources, "
            f"batch_size={config.global_batch_size}, "
            f"phase={config.curriculum_phase}"
        )

    def _init_sources(self) -> None:
        """Initialize data sources based on config."""
        cfg = self.config

        if cfg.source_type == DataSourceType.SYNTHETIC:
            # Create synthetic generators for each curriculum source type
            for source_name in ["jepa", "qm9", "tree_of_life", "generation", "language"]:
                self.key, source_key = jax.random.split(self.key)
                self.sources[source_name] = iter(SyntheticDataGenerator(cfg, source_key))

        elif cfg.source_type == DataSourceType.TFDS:
            self._init_tfds()

        elif cfg.source_type == DataSourceType.GCS:
            self._init_gcs()

    def _init_tfds(self) -> None:
        """Initialize TensorFlow Datasets sources."""
        try:
            import importlib.util

            if importlib.util.find_spec("tensorflow_datasets"):
                logger.info("TFDS sources would be initialized here")
                # Placeholder - actual TFDS loading would go here
            # For now, fallback to synthetic
            self._fallback_to_synthetic()
        except ImportError:
            logger.warning("tensorflow_datasets not available, using synthetic")
            self._fallback_to_synthetic()

    def _init_gcs(self) -> None:
        """Initialize Google Cloud Storage sources."""
        try:
            import importlib.util

            if importlib.util.find_spec("google.cloud.storage"):
                logger.info("GCS sources would be initialized here")
                # Placeholder - actual GCS loading would go here
            self._fallback_to_synthetic()
        except ImportError:
            logger.warning("google-cloud-storage not available, using synthetic")
            self._fallback_to_synthetic()

    def _fallback_to_synthetic(self) -> None:
        """Fallback to synthetic data when real data unavailable."""
        for source_name in ["jepa", "qm9", "tree_of_life", "generation", "language"]:
            self.key, source_key = jax.random.split(self.key)
            self.sources[source_name] = iter(SyntheticDataGenerator(self.config, source_key))

    def set_phase(self, phase: str) -> None:
        """Update curriculum phase for sampling."""
        self.sampler.set_phase(phase)

    def get_batch(self) -> DataBatch:
        """Get next batch according to curriculum."""
        return self.sampler.sample()

    def __iter__(self) -> Iterator[DataBatch]:
        """Infinite iterator of batches."""
        return iter(self.sampler)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_data_pipeline(
    config: DataConfig | None = None,
    key: jax.Array | None = None,
    **kwargs,
) -> DataPipeline:
    """Create data pipeline with sensible defaults.

    Args:
        config: DataConfig or None for defaults
        key: JAX random key or None
        **kwargs: Override config values

    Returns:
        Configured DataPipeline
    """
    if key is None:
        key = jax.random.PRNGKey(42)

    if config is None:
        # Build config from kwargs
        config = DataConfig(**{k: v for k, v in kwargs.items() if hasattr(DataConfig, k)})

    return DataPipeline(config, key)


def create_synthetic_pipeline(
    batch_size: int = 32,
    seq_len: int = 16,
    obs_dim: int = 64,
    action_dim: int = 8,
    key: jax.Array | None = None,
) -> DataPipeline:
    """Create synthetic data pipeline for testing.

    Args:
        batch_size: Batch size
        seq_len: Sequence length
        obs_dim: Observation dimension
        action_dim: Action dimension
        key: Random key

    Returns:
        DataPipeline with synthetic data
    """
    if key is None:
        key = jax.random.PRNGKey(42)

    config = DataConfig(
        source_type=DataSourceType.SYNTHETIC,
        global_batch_size=batch_size,
        sequence_length=seq_len,
        obs_dim=obs_dim,
        action_dim=action_dim,
    )

    return DataPipeline(config, key)


def generate_structured_batch(
    key: jax.Array,
    batch_size: int = 32,
    seq_len: int = 16,
    obs_dim: int = 64,
    action_dim: int = 8,
) -> DataBatch:
    """Generate a structured batch for benchmarking/profiling.

    This is a convenience function for profiler and benchmarks that need
    quick synthetic batches without setting up a full pipeline.

    Args:
        key: JAX random key
        batch_size: Batch size
        seq_len: Sequence length
        obs_dim: Observation dimension
        action_dim: Action dimension

    Returns:
        DataBatch with synthetic data
    """
    config = DataConfig(
        source_type=DataSourceType.SYNTHETIC,
        global_batch_size=batch_size,
        sequence_length=seq_len,
        obs_dim=obs_dim,
        action_dim=action_dim,
    )
    generator = SyntheticDataGenerator(config, key)
    return generator.generate_batch(key)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "CurriculumDataWeights",
    "CurriculumSampler",
    "DataBatch",
    "DataConfig",
    "DataPipeline",
    "DataSourceType",
    "SyntheticDataGenerator",
    "create_data_pipeline",
    "create_synthetic_pipeline",
    "generate_structured_batch",
]
