"""Curriculum data loader with Genesis + Geometric Datasets.

Canonical world-model pretraining uses:
- **Genesis puzzles** (PRIMARY): `jepa`, `generation`, `render` (infinite)
- **QM9** (RESTORED Dec 20, 2025): Molecular geometry for SE(3) equivariance
- **TreeOfLife** (RESTORED Dec 20, 2025): Hierarchical trees for H¹⁴ hyperbolic embeddings

Genesis remains the primary data source (50-60% of batches).
QM9/TreeOfLife provide geometric curriculum diversity in specific phases.

Phase → Dataset mapping:
- hierarchy: Genesis + TreeOfLife (hyperbolic embeddings)
- rotation: Genesis + QM9 (SE(3) equivariance)
- dynamics: Genesis + QM9 (physics + molecular dynamics)
- joint: All datasets (balanced mix)
- generation: Genesis only (control)
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset, IterableDataset, Sampler

from kagami.core.config.unified_config import TrainingConfig as PretrainConfig

from .normalizers import get_normalizer

logger = logging.getLogger(__name__)


# =============================================================================
# BucketedBatchSampler - Minimize padding by grouping similar-length sequences
# =============================================================================


class BucketedBatchSampler(Sampler[list[int]]):
    """Batch sampler that groups sequences by similar length to minimize padding.

    This sampler reduces wasted computation from padding by:
    1. Sorting sequences into buckets by length
    2. Sampling entire batches from the same bucket
    3. Shuffling buckets between epochs for training stability

    Example usage:
        >>> lengths = [len(seq) for seq in dataset]
        >>> sampler = BucketedBatchSampler(
        ...     lengths=lengths,
        ...     bucket_boundaries=[64, 128, 256, 512, 1024],
        ...     batch_size=32,
        ...     drop_last=True,
        ... )
        >>> dataloader = DataLoader(dataset, batch_sampler=sampler)

    Args:
        lengths: Sequence lengths for each sample in the dataset.
        bucket_boundaries: Length thresholds defining bucket edges.
            E.g., [64, 128, 256] creates buckets: [0-64), [64-128), [128-256), [256+)
        batch_size: Number of samples per batch.
        drop_last: If True, drop the last incomplete batch in each bucket.
            Recommended for training stability (consistent batch sizes).
        shuffle: If True (default), shuffle samples within buckets and bucket order.
        seed: Base random seed for reproducibility (default 42).
    """

    def __init__(
        self,
        lengths: list[int],
        bucket_boundaries: list[int] | None = None,
        batch_size: int = 32,
        drop_last: bool = False,
        shuffle: bool = True,
        seed: int = 42,
    ):
        super().__init__(None)  # data_source not needed for batch sampler
        self.lengths = lengths
        self.batch_size = batch_size
        self.drop_last = drop_last
        self.shuffle = shuffle
        self.seed = seed
        self.epoch = 0

        # Default boundaries if not provided
        if bucket_boundaries is None:
            bucket_boundaries = [64, 128, 256, 512, 1024]
        self.bucket_boundaries = sorted(bucket_boundaries)

        # Create buckets: assign each sample index to a bucket
        self.buckets = self._create_buckets(lengths, self.bucket_boundaries)

        # Log bucket statistics
        total_samples = sum(len(b) for b in self.buckets.values())
        logger.info(
            f"BucketedBatchSampler: {total_samples} samples in {len(self.buckets)} buckets, "
            f"batch_size={batch_size}, drop_last={drop_last}"
        )
        for bucket_id, indices in sorted(self.buckets.items()):
            if indices:
                min_len = min(lengths[i] for i in indices)
                max_len = max(lengths[i] for i in indices)
                logger.debug(
                    f"  Bucket {bucket_id}: {len(indices)} samples, "
                    f"length range [{min_len}, {max_len}]"
                )

    def _create_buckets(
        self,
        lengths: list[int],
        boundaries: list[int],
    ) -> dict[int, list[int]]:
        """Assign sample indices to buckets based on sequence length.

        Args:
            lengths: Sequence length for each sample.
            boundaries: Bucket boundary thresholds.

        Returns:
            Dict mapping bucket_id -> list of sample indices.
        """
        import bisect

        buckets: dict[int, list[int]] = {i: [] for i in range(len(boundaries) + 1)}

        for idx, length in enumerate(lengths):
            # Find which bucket this length belongs to
            bucket_id = bisect.bisect_right(boundaries, length)
            buckets[bucket_id].append(idx)

        # Remove empty buckets
        return {k: v for k, v in buckets.items() if v}

    def __iter__(self) -> Iterator[list[int]]:
        """Yield batches of indices, grouped by sequence length bucket.

        Yields:
            List of sample indices forming a batch (all from same bucket).
        """
        import random

        # Use epoch-aware random generator for reproducibility
        rng = random.Random(self.seed + self.epoch)

        # Collect all batches across all buckets
        all_batches: list[list[int]] = []

        for _bucket_id, indices in self.buckets.items():
            # Shuffle within bucket if requested
            bucket_indices = list(indices)
            if self.shuffle:
                rng.shuffle(bucket_indices)

            # Create batches from this bucket
            for i in range(0, len(bucket_indices), self.batch_size):
                batch = bucket_indices[i : i + self.batch_size]
                if len(batch) == self.batch_size or not self.drop_last:
                    all_batches.append(batch)

        # Shuffle batch order across buckets for training diversity
        if self.shuffle:
            rng.shuffle(all_batches)

        yield from all_batches

    def __len__(self) -> int:
        """Return total number of batches.

        Note: This is an approximation if drop_last=True since bucket
        sizes may not divide evenly by batch_size.
        """
        total = 0
        for indices in self.buckets.values():
            n_batches = len(indices) // self.batch_size
            if not self.drop_last and len(indices) % self.batch_size > 0:
                n_batches += 1
            total += n_batches
        return total

    def set_epoch(self, epoch: int) -> None:
        """Set epoch for reproducible shuffling across epochs.

        Call this at the start of each epoch for deterministic training:
            >>> for epoch in range(num_epochs):
            ...     sampler.set_epoch(epoch)
            ...     for batch in dataloader:
            ...         ...

        Args:
            epoch: Current epoch number (combined with seed for RNG).
        """
        self.epoch = epoch


def compute_sequence_lengths(dataset: Dataset, length_key: str = "state_t") -> list[int]:
    """Compute sequence lengths for all samples in a dataset.

    This is a helper function for BucketedBatchSampler initialization.
    It iterates through the dataset once to measure sequence lengths.

    Args:
        dataset: A PyTorch Dataset (must be indexable, not IterableDataset).
        length_key: Key in the sample dict containing the sequence tensor.
            Common keys: "state_t", "x", "positions", "text".

    Returns:
        List of sequence lengths, one per sample.

    Raises:
        TypeError: If dataset is an IterableDataset (not indexable).
        KeyError: If length_key is not found in samples.
    """
    if isinstance(dataset, IterableDataset):
        raise TypeError(
            "BucketedBatchSampler requires an indexable Dataset, not IterableDataset. "
            "For IterableDataset, use yield_batches=True mode instead."
        )

    lengths = []
    for i in range(len(dataset)):  # type: ignore[arg-type]
        sample = dataset[i]
        if length_key in sample:
            tensor = sample[length_key]
            if isinstance(tensor, torch.Tensor):
                lengths.append(tensor.shape[0])
            elif hasattr(tensor, "__len__"):
                lengths.append(len(tensor))
            else:
                lengths.append(1)
        else:
            # Try common fallback keys
            for fallback in ["x", "positions", "text", "input_ids"]:
                if fallback in sample:
                    tensor = sample[fallback]
                    if isinstance(tensor, torch.Tensor):
                        lengths.append(tensor.shape[0])
                    elif hasattr(tensor, "__len__"):
                        lengths.append(len(tensor))
                    else:
                        lengths.append(1)
                    break
            else:
                # Default to 1 if no sequence found
                lengths.append(1)

    return lengths


# Global Genesis cache (initialized lazily)
_GENESIS_CACHE: Any = None
_GENESIS_CACHE_ENABLED: bool = False
_GENESIS_CACHE_CONFIG_HASH: str = ""  # Track config for invalidation


def _get_config_value(config: Any, key: str, default: Any = None) -> Any:
    """Get config value from dict or object."""
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _compute_cache_config_hash(config: Any) -> str:
    """Compute hash of cache-relevant config values for invalidation.

    When config changes (e.g., embedding_dim, seq_len, batch_size),
    the cache should be invalidated to prevent stale/incompatible data.
    """
    import hashlib

    # Extract cache-relevant values
    emb_dim = int(
        _get_config_value(config, "student_dim", None)
        or _get_config_value(config, "bulk_dim", None)
        or 128
    )
    seq_len = int(_get_config_value(config, "sequence_length", None) or 8)
    data_config = _get_config_value(config, "data", {})
    cache_size = int(_get_config_value(data_config, "genesis_cache_size", 10000))
    cache_workers = int(_get_config_value(data_config, "genesis_cache_workers", 4))

    # Create deterministic hash string
    hash_input = f"emb={emb_dim}|seq={seq_len}|size={cache_size}|workers={cache_workers}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


def invalidate_genesis_cache() -> None:
    """Invalidate and stop the global Genesis cache.

    Call this when config changes require a fresh cache.
    """
    global _GENESIS_CACHE, _GENESIS_CACHE_ENABLED, _GENESIS_CACHE_CONFIG_HASH

    if _GENESIS_CACHE is not None:
        logger.info("Invalidating Genesis cache due to config change...")
        try:
            _GENESIS_CACHE.stop()
        except Exception as e:
            logger.warning(f"Error stopping Genesis cache: {e}")
        _GENESIS_CACHE = None
        _GENESIS_CACHE_ENABLED = False
        _GENESIS_CACHE_CONFIG_HASH = ""


def _init_genesis_cache(config: Any) -> None:
    """Initialize the global Genesis cache if enabled in config.

    The cache runs background workers that continuously generate puzzles,
    staying ahead of training consumption.

    UPDATED (Dec 31, 2025): Cache is now ENABLED BY DEFAULT.
    Set KAGAMI_GENESIS_CACHE_ENABLED=0 or genesis_cache_enabled=false to disable.
    Cache automatically invalidates when config changes (embedding_dim, seq_len, etc.).
    """
    global _GENESIS_CACHE, _GENESIS_CACHE_ENABLED, _GENESIS_CACHE_CONFIG_HASH
    import os

    # Check if cache is explicitly disabled - try multiple paths
    # Priority: 1) Environment var, 2) config attr, 3) nested data config
    # DEFAULT: ENABLED (changed Dec 31, 2025)
    env_val = os.environ.get("KAGAMI_GENESIS_CACHE_ENABLED", "").lower()
    if env_val in ("0", "false", "no"):
        cache_enabled = False
    elif env_val in ("1", "true", "yes"):
        cache_enabled = True
    else:
        # No explicit env var - check config (default to True)
        cache_enabled = _get_config_value(config, "genesis_cache_enabled", True)
        if cache_enabled is None:
            data_config = _get_config_value(config, "data", None)
            if data_config:
                cache_enabled = _get_config_value(data_config, "genesis_cache_enabled", True)
            else:
                cache_enabled = True  # Default enabled

    if not cache_enabled:
        logger.info("Genesis cache disabled (set KAGAMI_GENESIS_CACHE_ENABLED=1 to enable)")
        return

    # Check for config changes that require cache invalidation
    new_config_hash = _compute_cache_config_hash(config)
    if _GENESIS_CACHE is not None:
        if _GENESIS_CACHE_CONFIG_HASH and new_config_hash != _GENESIS_CACHE_CONFIG_HASH:
            logger.info(
                f"Config changed (hash {_GENESIS_CACHE_CONFIG_HASH[:8]} -> {new_config_hash[:8]}), "
                "invalidating cache..."
            )
            invalidate_genesis_cache()
        else:
            logger.info("Genesis cache already initialized with matching config")
            return

    try:
        from .genesis_cache import GenesisCacheManager

        # Get cache configuration from env vars first, then config
        cache_size = int(os.environ.get("KAGAMI_GENESIS_CACHE_SIZE", 0)) or int(
            _get_config_value(_get_config_value(config, "data", {}), "genesis_cache_size", 10000)
        )
        cache_workers = int(os.environ.get("KAGAMI_GENESIS_CACHE_WORKERS", 0)) or int(
            _get_config_value(_get_config_value(config, "data", {}), "genesis_cache_workers", 4)
        )

        # Get embedding dim from training config
        emb_dim = int(
            _get_config_value(config, "student_dim", None)
            or _get_config_value(config, "bulk_dim", None)
            or 128
        )
        seq_len = int(_get_config_value(config, "sequence_length", None) or 8)

        logger.info(
            f"Starting Genesis cache: size={cache_size}, workers={cache_workers}, "
            f"dim={emb_dim}, seq_len={seq_len}"
        )

        _GENESIS_CACHE = GenesisCacheManager(
            cache_size=cache_size,
            num_workers=cache_workers,
            puzzle_dim=emb_dim,
            seq_len=seq_len,
        )
        _GENESIS_CACHE.start()
        _GENESIS_CACHE_ENABLED = True
        _GENESIS_CACHE_CONFIG_HASH = new_config_hash

        logger.info(f"Genesis cache started (config hash: {new_config_hash[:8]}) and warming up...")

    except Exception as e:
        logger.warning(f"Failed to start Genesis cache: {e}")
        _GENESIS_CACHE = None
        _GENESIS_CACHE_ENABLED = False


def _get_cached_genesis_sample() -> dict[str, Any] | None:
    """Get a sample from the Genesis cache if available.

    Returns:
        Puzzle dict or None if cache disabled/empty
    """
    global _GENESIS_CACHE

    if not _GENESIS_CACHE_ENABLED or _GENESIS_CACHE is None:
        return None

    try:
        return _GENESIS_CACHE.get(timeout=0.01)  # Very short timeout
    except Exception:
        return None


def get_genesis_cache_stats() -> dict[str, Any]:
    """Get Genesis cache statistics."""
    global _GENESIS_CACHE

    if _GENESIS_CACHE is None:
        return {"enabled": False}

    return _GENESIS_CACHE.stats()


# Data root (relative to project)
DATA_ROOT = Path(__file__).parent.parent.parent.parent / "data"

# =============================================================================
# Multiprocessing-safe curriculum steering (spawn-safe)
# =============================================================================
#
# When DataLoader uses multiple workers with an IterableDataset, worker outputs
# can interleave and "mix modalities" inside a single batch if batching happens
# in the DataLoader. The fix is: dataset yields fully-collated batches, and we
# share phase/weights across workers using lock-free shared memory.
#
# References:
# - PyTorch DataLoader IterableDataset multiprocessing notes
# - Common macOS resource_tracker semaphore leak issues when using locks/pin_memory:
#   https://github.com/pytorch/pytorch/issues/97432
#
_PHASE_TO_ID: dict[str, int] = {
    "hierarchy": 0,
    "rotation": 1,
    "dynamics": 2,
    "joint": 3,
    "generation": 4,
    "render": 5,
    "video": 5,
}
_ID_TO_PHASE: dict[int, str] = {v: k for k, v in _PHASE_TO_ID.items()}

# Fixed set of sources for shared-weight steering.
_WEIGHT_SOURCES: tuple[str, ...] = ("jepa", "generation", "qm9", "treeoflife", "render")
_WEIGHT_INDEX: dict[str, int] = {k: i for i, k in enumerate(_WEIGHT_SOURCES)}

# Scheduler alias keys → dataset keys.
_WEIGHT_ALIASES: dict[str, str] = {
    # Common curriculum aliases
    "h14": "treeoflife",
    "hierarchy": "treeoflife",
    "tree": "treeoflife",
    "s7": "jepa",
    # Render/video
    "video_prediction": "render",
    "video": "render",
}


def _normalize_phase_name(phase: Any) -> str:
    """Normalize various phase representations to a lowercase string key.

    Handles:
    - str: "dynamics"
    - Enum: CurriculumPhase.DYNAMICS → "dynamics"
    - int: 0..4 (best-effort mapping to canonical phase names)
    """
    if isinstance(phase, str):
        s = phase
    elif hasattr(phase, "name"):
        # Enum-like
        s = str(phase.name)
    elif isinstance(phase, int):
        s = {0: "hierarchy", 1: "rotation", 2: "dynamics", 3: "joint", 4: "generation"}.get(
            int(phase),
            "joint",
        )
    else:
        s = str(phase)

    s = (s or "joint").strip().lower()
    if "." in s:
        s = s.split(".")[-1]
    return s or "joint"


class CurriculumDataset(IterableDataset):
    """Curriculum dataset with Genesis + Geometric data sources.

    RESTORED (Dec 20, 2025): QM9 and TreeOfLife re-enabled for geometric curriculum.

    Data sources:
    - Genesis: JEPA dynamics, generation/control, optional render stream
    - QM9: Molecular geometry (SE(3) equivariance, gauge theory)
    - TreeOfLife: Hierarchical trees (H¹⁴ hyperbolic embeddings)

    Phases modulate dataset mixture + puzzle difficulty.
    Genesis remains primary (50-60% of batches in joint phase).
    """

    def __init__(
        self,
        config: PretrainConfig,
        phase: str = "joint",
        data_root: Path | None = None,
        *,
        yield_batches: bool = False,
        shared_phase: Any | None = None,
        shared_weights: Any | None = None,
    ):
        super().__init__()
        self.config = config
        self.phase = _normalize_phase_name(phase)
        self.data_root = Path(data_root) if data_root else DATA_ROOT
        # When True, __iter__ yields pre-collated homogeneous batches.
        # This is REQUIRED for DataLoader multiprocessing with IterableDataset,
        # otherwise worker interleaving can mix modalities inside a batch.
        self._yield_batches = bool(yield_batches)
        # Optional shared state for multiprocessing (spawn-safe).
        # If provided, set_phase / set_sampling_weights will update these values and
        # worker copies will observe the updated curriculum steering.
        self._shared_phase = shared_phase
        self._shared_weights = shared_weights

        # Load datasets based on phase
        self.datasets: dict[str, Dataset] = {}
        self._load_datasets()
        self._sampling_weights: dict[str, float] | None = None

        logger.info(f"CurriculumDataset: phase={phase}, datasets={list(self.datasets.keys())}")

    # ---------------------------------------------------------------------
    # Curriculum steering (phase + sampling weights)
    # ---------------------------------------------------------------------

    def set_phase(self, phase: str) -> None:
        """Update the active curriculum phase (affects which datasets are eligible)."""
        self.phase = _normalize_phase_name(phase)
        if self._shared_phase is not None:
            try:
                self._shared_phase.value = _PHASE_TO_ID.get(self.phase, _PHASE_TO_ID["joint"])
            except Exception:
                pass

    def set_sampling_weights(self, weights: dict[str, float] | None) -> None:
        """Set per-source sampling weights (used to align with AdaptiveCurriculumScheduler).

        The scheduler uses abstract keys like "h14", "s7", "jepa", "generation".
        We support both canonical dataset keys and these aliases.
        """
        if not weights:
            self._sampling_weights = None
            return
        cleaned: dict[str, float] = {}
        for k, v in dict(weights).items():
            try:
                fv = float(v)
            except Exception:
                continue
            if fv <= 0:
                continue
            cleaned[str(k)] = fv
        self._sampling_weights = cleaned or None
        # Propagate to shared weights for DataLoader worker processes (if enabled).
        if self._shared_weights is not None:
            try:
                # Reset all weights (unknown keys remain 0).
                for i in range(len(_WEIGHT_SOURCES)):
                    self._shared_weights[i] = 0.0
                for k, v in (self._sampling_weights or {}).items():
                    key = _WEIGHT_ALIASES.get(k, k)
                    idx = _WEIGHT_INDEX.get(key)
                    if idx is not None:
                        self._shared_weights[idx] = float(v)
            except Exception:
                # Best-effort only; workers will fall back to local weights if any.
                pass

    def _current_phase(self) -> str:
        """Get the current phase (shared across workers if enabled)."""
        if self._shared_phase is not None:
            try:
                pid = int(self._shared_phase.value)
                return _ID_TO_PHASE.get(pid, "joint")
            except Exception:
                return self.phase
        return self.phase

    def _load_datasets(self) -> None:
        """Load real datasets from data/ directory.

        Genesis is ALWAYS the primary data source (Dec 28, 2025).
        QM9 provides curriculum diversity for SE(3) equivariance.
        """
        import time

        logger.info("_load_datasets: Starting (Genesis-first architecture)...")

        # Initialize Genesis cache if enabled (background workers will fill it)
        _init_genesis_cache(self.config)

        # Prefer student_dim for embedding alignment; fall back to legacy names.
        emb_dim = int(
            getattr(self.config, "student_dim", None)
            or getattr(self.config, "bulk_dim", None)
            or 512
        )
        seq_len = int(getattr(self.config, "sequence_length", None) or 32)
        batch_size = int(getattr(self.config, "batch_size", None) or 1)

        # Genesis puzzles - PRIMARY data source (Dec 28, 2025)
        # Always enabled - this is the core training signal
        logger.info("_load_datasets: Loading Genesis puzzles (infinite)...")
        t0 = time.time()

        from .datasets.genesis_sim_loader import GenesisSimDataset

        # Throughput tuning:
        # - buffer_steps: enough history to decorrelate samples
        # - samples_per_step: amortize expensive Genesis stepping across many samples
        buffer_steps = max(4096, batch_size * 4)
        samples_per_step = max(32, min(512, batch_size // 8))
        reset_interval_steps = max(512, buffer_steps // 4)

        # Test Genesis backend availability BEFORE creating datasets
        # This prevents lazy initialization failures during training
        test_ds = GenesisSimDataset(
            split="train",
            seq_len=2,
            embedding_dim=emb_dim,
            use_real_genesis=True,
            puzzle_mode="jepa",
            buffer_steps=16,
            samples_per_step=1,
            reset_interval_steps=8,
        )
        # Actually test the backend by trying to get one sample
        test_iter = iter(test_ds)
        _test_sample = next(test_iter)
        del test_ds, test_iter, _test_sample
        logger.info("Genesis backend test passed")

        # JEPA-style dynamics puzzles (primary Genesis stream).
        genesis_jepa = GenesisSimDataset(
            split="train",
            seq_len=seq_len,
            embedding_dim=emb_dim,
            use_real_genesis=True,
            puzzle_mode="jepa",
            buffer_steps=buffer_steps,
            samples_per_step=samples_per_step,
            reset_interval_steps=reset_interval_steps,
        )
        self.datasets["jepa"] = genesis_jepa  # curriculum key

        # Generation / control puzzles (goal-conditioned; used in later phases).
        genesis_gen = GenesisSimDataset(
            split="train",
            seq_len=seq_len,
            embedding_dim=emb_dim,
            use_real_genesis=True,
            puzzle_mode="generation",
            buffer_steps=buffer_steps,
            samples_per_step=samples_per_step,
            reset_interval_steps=reset_interval_steps,
        )
        self.datasets["generation"] = genesis_gen

        # Render stream: puzzles WITH rendered frames for neural renderer training.
        enable_render_stream = bool(
            getattr(self.config, "enable_render_stream", False)
            or getattr(self.config, "enable_video_prediction", False)
        )
        if enable_render_stream:
            render_width = int(getattr(self.config, "render_width", 128))
            render_height = int(getattr(self.config, "render_height", 128))
            genesis_render = GenesisSimDataset(
                split="train",
                seq_len=seq_len,
                embedding_dim=emb_dim,
                use_real_genesis=True,
                puzzle_mode="jepa",
                buffer_steps=max(1024, buffer_steps // 4),
                samples_per_step=max(8, samples_per_step // 8),
                reset_interval_steps=max(256, reset_interval_steps // 4),
                enable_rendering=True,
                render_width=render_width,
                render_height=render_height,
                render_every_n_steps=2,
            )
            self.datasets["render"] = genesis_render
            logger.info(
                "Loaded render stream: %dx%d (video prediction enabled)",
                render_width,
                render_height,
            )

        t1 = time.time()
        logger.info(f"_load_datasets: GenesisSimDataset created in {t1 - t0:.2f}s")
        logger.info(
            "✅ Loaded Genesis puzzles: jepa=%s generation=%s render=%s (infinite iterators)",
            type(genesis_jepa).__name__,
            type(genesis_gen).__name__,
            "enabled" if enable_render_stream else "disabled",
        )

        # QM9 Molecular Geometry - curriculum diversity source
        # Always loaded for SE(3) equivariance learning
        t_qm9 = time.time()
        from .datasets.qm9_dataset import QM9Dataset

        qm9_dir = getattr(self.config, "qm9_cache_dir", None) or (self.data_root / "qm9")
        qm9_ds = QM9Dataset(
            data_dir=qm9_dir,
            max_samples=getattr(self.config, "max_samples", None) or 100_000,
            shuffle=True,
            split="train",
            embedding_dim=emb_dim,
        )
        self.datasets["qm9"] = qm9_ds
        logger.info(f"✅ Loaded QM9: {len(qm9_ds)} molecules in {time.time() - t_qm9:.2f}s")

        # TreeOfLife Hierarchical Structures (optional - requires NCBI taxonomy)
        # Load if data directory exists and contains valid data
        tol_dir = getattr(self.config, "treeoflife_cache_dir", None) or (
            self.data_root / "tree_of_life"
        )
        if (tol_dir / "nodes.dmp").exists():
            t_tol = time.time()
            try:
                from .datasets.tree_of_life_dataset import TreeOfLifeDataset

                tol_ds = TreeOfLifeDataset(
                    root_dir=tol_dir,
                    max_samples=getattr(self.config, "max_samples", None) or 10_000,
                    split="train",
                    embedding_dim=emb_dim,
                )
                self.datasets["treeoflife"] = tol_ds
                logger.info(
                    f"✅ Loaded TreeOfLife: {len(tol_ds)} trees in {time.time() - t_tol:.2f}s"
                )
            except Exception as e:
                logger.warning(f"TreeOfLife loading failed (optional): {e}")
        else:
            logger.info(
                "TreeOfLife data not found (optional: download NCBI taxonomy to data/tree_of_life/)"
            )

    def _get_phase_datasets(self) -> list[str]:
        """Get datasets for current curriculum phase.

        FIXED (Dec 28, 2025): Only use datasets that are actually loaded.
        Phase map defines PREFERRED datasets, but only available ones are used.
        """
        phase_map = {
            # UPDATED CURRICULUM (Dec 28, 2025):
            # TreeOfLife ENABLED for hierarchical structure learning
            # Genesis + QM9 + TreeOfLife are all active data sources
            "hierarchy": ["jepa", "qm9", "treeoflife"],  # Hierarchy + geometry
            "rotation": ["jepa", "qm9", "treeoflife"],  # SE(3) equivariance
            "dynamics": ["jepa", "qm9", "treeoflife"],  # Physics + dynamics
            "joint": ["jepa", "generation", "qm9", "treeoflife"],  # All sources
            "generation": ["generation", "jepa", "treeoflife"],  # Generative
            # Render phase adds video prediction (render stream).
            "render": ["render", "jepa"],
            "video": ["render", "jepa"],
        }

        preferred = phase_map.get(self.phase, list(self.datasets.keys()))
        available = [d for d in preferred if d in self.datasets]

        if not available:
            raise RuntimeError(
                f"No datasets available for phase '{self.phase}'.\n"
                f"Preferred: {preferred}\n"
                f"Loaded: {list(self.datasets.keys())}\n"
                f"Check your config: enable_genesis, enable_qm9, enable_treeoflife"
            )

        logger.info(f"Phase '{self.phase}' using datasets: {available}")
        return available

    def _weight_for_source(self, source: str) -> float:
        """Compute an effective sampling weight for a given dataset key."""
        # Prefer shared weights when multiprocessing is enabled.
        if self._shared_weights is not None:
            idx = _WEIGHT_INDEX.get(source)
            if idx is None:
                return 0.0
            try:
                return max(0.0, float(self._shared_weights[idx]))
            except Exception:
                return 0.0

        if not self._sampling_weights:
            return 1.0

        w = self._sampling_weights
        # Direct weight if present
        direct = float(w.get(source, 0.0))

        return max(0.0, direct)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        """Iterate over curriculum data.

        FIXED (Dec 28, 2025): Added source tracking and logging.
        """
        current_phase = self._current_phase()
        self.phase = current_phase  # keep local in sync for _get_phase_datasets()
        phase_datasets = self._get_phase_datasets()

        # Create iterators for each dataset (some are infinite, some finite)
        iterators = {name: iter(self.datasets[name]) for name in phase_datasets}

        import random

        # Source statistics for logging
        source_counts: dict[str, int] = dict[str, Any].fromkeys(phase_datasets, 0)
        total_samples = 0
        log_interval = 1000  # Log every N samples
        try:
            from torch.utils.data import get_worker_info

            info = get_worker_info()
            worker_id = int(getattr(info, "id", 0) or 0) if info is not None else 0
        except Exception:
            worker_id = 0

        while True:
            # Phase can change during training; update eligible datasets on transition.
            phase_now = self._current_phase()
            if phase_now != current_phase:
                current_phase = phase_now
                self.phase = current_phase
                phase_datasets = self._get_phase_datasets()
                for name in phase_datasets:
                    if name not in iterators:
                        iterators[name] = iter(self.datasets[name])

            # IMPORTANT: Choose a source per-batch to keep DataLoader batches homogeneous.
            if self._sampling_weights or self._shared_weights is not None:
                weights = [self._weight_for_source(s) for s in phase_datasets]
                if sum(weights) > 0:
                    source = random.choices(phase_datasets, weights=weights, k=1)[0]
                else:
                    source = random.choice(phase_datasets)
            else:
                source = random.choice(phase_datasets)

            batch_n = max(int(getattr(self.config, "batch_size", 1) or 1), 1)

            # ------------------------------------------------------------------
            # Batch-yield mode (multiprocessing-safe for IterableDataset)
            # ------------------------------------------------------------------
            if self._yield_batches:
                samples: list[dict[str, Any]] = []
                for _ in range(batch_n):
                    sample = None

                    # Try cache first for Genesis sources (jepa/generation)
                    if source in ("jepa", "generation") and _GENESIS_CACHE_ENABLED:
                        sample = _get_cached_genesis_sample()

                    # Fall back to direct iteration if cache miss
                    if sample is None:
                        try:
                            sample = next(iterators[source])
                        except StopIteration:
                            # Restart iterator (finite datasets like QM9)
                            iterators[source] = iter(self.datasets[source])
                            sample = next(iterators[source])

                    # Track source statistics
                    source_counts[source] += 1
                    total_samples += 1

                    # Log source distribution periodically
                    if worker_id == 0 and total_samples % log_interval == 0:
                        dist_str = ", ".join(
                            f"{k}: {v / total_samples * 100:.1f}%" for k, v in source_counts.items()
                        )
                        # Include cache stats if enabled
                        cache_info = ""
                        if _GENESIS_CACHE_ENABLED:
                            stats = get_genesis_cache_stats()
                            cache_info = f" | Cache: {stats.get('size', 0)}/{stats.get('max_size', 0)} ({stats.get('hit_rate', 0) * 100:.1f}% hits)"
                        logger.info(
                            f"📊 Data source distribution ({total_samples} samples): {dist_str}{cache_info}"
                        )

                    samples.append(self._normalize_sample(sample, source))

                # Collate into a single homogeneous batch dict.
                batch = curriculum_collate_fn(samples)
                # Ensure these are scalars (training loop expects strings, not lists).
                batch["source"] = source
                batch["source_type"] = self._source_to_type(source)
                yield batch
                continue

            # ------------------------------------------------------------------
            # Sample-yield mode (single worker only)
            # ------------------------------------------------------------------
            for _ in range(batch_n):
                sample = None

                # Try cache first for Genesis sources (jepa/generation)
                if source in ("jepa", "generation") and _GENESIS_CACHE_ENABLED:
                    sample = _get_cached_genesis_sample()

                # Fall back to direct iteration if cache miss
                if sample is None:
                    try:
                        sample = next(iterators[source])
                    except StopIteration:
                        # Restart iterator (finite datasets like QM9)
                        iterators[source] = iter(self.datasets[source])
                        sample = next(iterators[source])

                # Track source statistics
                source_counts[source] += 1
                total_samples += 1

                # Log source distribution periodically
                if worker_id == 0 and total_samples % log_interval == 0:
                    dist_str = ", ".join(
                        f"{k}: {v / total_samples * 100:.1f}%" for k, v in source_counts.items()
                    )
                    logger.info(
                        f"📊 Data source distribution ({total_samples} samples): {dist_str}"
                    )

                # Normalize to common format
                yield self._normalize_sample(sample, source)

    def _normalize_sample(self, sample: dict[str, Any], source: str) -> dict[str, Any]:
        """Normalize sample to common training format.

        CRITICAL (Dec 14, 2025): PRESERVE GEOMETRIC STRUCTURE.
        Do NOT flatten positions/adjacency/hierarchy into generic features.
        The model needs raw geometric data to compute geometry-aware losses.

        TRAIL-016 (Dec 14, 2025): Refactored to use normalizer registry.
        Reduced CC from 28 to 3 by extracting type-specific normalizers.
        """
        # Get type-specific normalizer from registry
        normalizer = get_normalizer(source)

        # Normalize using type-specific logic
        normalized = normalizer.normalize(sample, source)

        # Add source metadata
        normalized["source"] = source
        normalized["source_type"] = self._source_to_type(source)

        return normalized

    def _source_to_type(self, source: str) -> str:
        """Map source to curriculum phase type."""
        type_map = {
            "jepa": "jepa",
            "generation": "generation",
            "render": "render",
        }
        return type_map.get(source, "unknown")


def curriculum_collate_fn(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Collate function for curriculum batches.

    IMPROVED (Dec 31, 2025): Returns padding_mask for variable-length sequences.
    The mask is True for padded positions, False for real data.
    This prevents loss computation on padded zeros.
    """
    if not batch:
        return {}

    out: dict[str, Any] = {}
    keys = set().union(*(b.keys() for b in batch))

    # Track sequence lengths for padding mask generation
    _sequence_lengths: dict[str, list[int]] = {}
    _max_lengths: dict[str, int] = {}

    for key in keys:
        values = [b.get(key) for b in batch if key in b]
        if not values:
            continue

        # Filter out None values
        values = [v for v in values if v is not None]
        if not values:
            continue

        if isinstance(values[0], torch.Tensor):
            try:
                # Stack tensors of same shape
                tensor_values: list[torch.Tensor] = values  # type: ignore
                out[key] = torch.stack(tensor_values)
            except RuntimeError:
                # Handle variable sequence lengths by padding
                tensor_values = values  # type: ignore
                first_shape = tensor_values[0].shape
                if len(first_shape) == 1:
                    # 1D tensors: pad sequence dimension
                    lengths = [v.shape[0] for v in tensor_values]
                    max_size = max(lengths)
                    padded: list[torch.Tensor] = [
                        torch.nn.functional.pad(v, (0, max_size - v.shape[0]))
                        for v in tensor_values
                    ]
                    out[key] = torch.stack(padded)
                    # Track for padding mask
                    _sequence_lengths[key] = lengths
                    _max_lengths[key] = max_size
                elif len(first_shape) == 2:
                    # 2D tensors [seq_len, features]: pad both dimensions if needed
                    seq_lengths = [v.shape[0] for v in tensor_values]
                    max_seq_len = max(seq_lengths)
                    max_feature_dim = max(v.shape[1] for v in tensor_values)
                    padded = []
                    for v in tensor_values:
                        seq_len, feature_dim = v.shape
                        v_mut = v
                        # Pad sequence dimension
                        if seq_len < max_seq_len:
                            seq_padding = torch.zeros(
                                max_seq_len - seq_len, feature_dim, dtype=v.dtype, device=v.device
                            )
                            v_mut = torch.cat([v_mut, seq_padding], dim=0)
                        # Pad feature dimension
                        if feature_dim < max_feature_dim:
                            feature_padding = torch.zeros(
                                max_seq_len,
                                max_feature_dim - feature_dim,
                                dtype=v_mut.dtype,
                                device=v_mut.device,
                            )
                            v_mut = torch.cat([v_mut, feature_padding], dim=1)
                        padded.append(v_mut)
                    out[key] = torch.stack(padded)
                    # Track for padding mask
                    _sequence_lengths[key] = seq_lengths
                    _max_lengths[key] = max_seq_len
                else:
                    # For higher dimensional tensors, keep as list[Any]
                    out[key] = values
        elif isinstance(values[0], int | float):
            out[key] = torch.tensor(values)
        else:
            out[key] = values

    # Generate padding masks for variable-length sequences
    # Mask is True for PADDED positions (positions to ignore in loss)
    for key, lengths in _sequence_lengths.items():
        max_len = _max_lengths[key]
        batch_size = len(lengths)
        # Create mask: True = padded (ignore), False = real data
        padding_mask = torch.ones(batch_size, max_len, dtype=torch.bool)
        for i, length in enumerate(lengths):
            padding_mask[i, :length] = False
        out[f"{key}_padding_mask"] = padding_mask

    # Also create a unified padding_mask if we have common sequence keys
    # Priority: state_t > x > positions (most common sequence data)
    for priority_key in ["state_t", "x", "positions", "text"]:
        if priority_key in _sequence_lengths:
            out["padding_mask"] = out[f"{priority_key}_padding_mask"]
            out["sequence_lengths"] = torch.tensor(_sequence_lengths[priority_key])
            break

    return out


def validate_batch(batch: dict[str, Any]) -> bool:
    """Validate that batch has required fields for training.

    UPDATED (Dec 14, 2025): Accept geometric structure directly.

    Returns:
        True if batch is valid, False otherwise
    """
    if not isinstance(batch, dict):
        return False

    # Accept any of these data types:
    # - Text: "text"
    # - Vision: "image", "video"
    # - Molecular geometry: "positions" [N, 3]
    # - Hierarchy: "node_depths", "adjacency"
    # - Dynamics: "state_t", "state_t_plus_1"
    # - Generic: "x" (legacy)

    has_data = any(
        key in batch
        for key in [
            "text",
            "image",
            "video",
            "positions",  # QM9 molecular geometry
            "node_depths",  # TreeOfLife hierarchy
            "adjacency",  # TreeOfLife graph
            "state_t",  # Genesis dynamics
            "x",  # Generic input (legacy)
        ]
    )

    return has_data


def create_curriculum_dataloader(
    config: PretrainConfig,
    phase: str = "joint",
    data_root: Path | None = None,
) -> DataLoader:
    """Create dataloader with REAL curriculum data.

    Args:
        config: Training configuration
        phase: Curriculum phase (hierarchy, rotation, dynamics, joint, generation)
        data_root: Override data directory

    Returns:
        DataLoader with real curriculum data

    Performance Optimizations (Dec 16, 2025):
        - num_workers: Parallel data loading (default 8 for M3 Ultra)
        - prefetch_factor: Pre-load batches per worker (2-3x speedup)
        - persistent_workers: Avoid worker process restart overhead
        - pin_memory: False for MPS (not needed), True for CUDA (faster transfer)
    """
    import time

    logger.info("create_curriculum_dataloader: Starting...")
    t0 = time.time()

    # Decide parallelism up-front so the dataset can yield worker-safe batches.
    num_workers = int(getattr(config, "num_workers", 0) or 0)
    use_parallelism = num_workers > 0

    phase_name = _normalize_phase_name(phase)

    # Shared curriculum steering across DataLoader workers (spawn-safe).
    shared_phase = None
    shared_weights = None
    if use_parallelism:
        import multiprocessing as _mp

        ctx = _mp.get_context("spawn")
        shared_phase = ctx.Value(
            "i",
            _PHASE_TO_ID.get(phase_name, _PHASE_TO_ID["joint"]),
            lock=False,
        )
        # Fixed-size array of weights keyed by _WEIGHT_SOURCES (lock-free to avoid semaphore leaks).
        shared_weights = ctx.Array("d", [0.0] * len(_WEIGHT_SOURCES), lock=False)

    dataset = CurriculumDataset(
        config=config,
        phase=phase_name,
        data_root=data_root,
        yield_batches=use_parallelism,
        shared_phase=shared_phase,
        shared_weights=shared_weights,
    )
    t1 = time.time()
    logger.info(f"create_curriculum_dataloader: CurriculumDataset created in {t1 - t0:.2f}s")

    # NOTE: CurriculumDataset is an IterableDataset that internally batches by source.
    # With DataLoader multiprocessing, worker interleaving can mix modalities inside
    # a batch unless the dataset yields pre-collated batches.

    # Pin memory for CUDA (faster host->device transfer), disable for MPS
    pin_memory = config.device == "cuda" if hasattr(config, "device") else False

    return DataLoader(
        dataset,
        batch_size=None if use_parallelism else config.batch_size,
        num_workers=num_workers,
        collate_fn=None if use_parallelism else curriculum_collate_fn,
        pin_memory=pin_memory,
        # Prefetch N batches per worker for smooth pipeline (only if workers enabled)
        prefetch_factor=int(getattr(config, "prefetch_factor", 2) or 2)
        if use_parallelism
        else None,
        # Keep workers alive between epochs (avoid recreation overhead)
        persistent_workers=use_parallelism,
        multiprocessing_context="spawn" if use_parallelism else None,
    )


# For backwards compatibility with tests only
def create_test_dataloader(config: PretrainConfig) -> DataLoader:
    """Create small dataloader for unit tests using real data subset."""
    # Use first 100 samples for fast tests
    config.max_samples = 100
    config.batch_size = min(config.batch_size, 8)
    return create_curriculum_dataloader(config, phase="joint")


def create_validation_dataloader(
    config: PretrainConfig,
    phase: str = "joint",
    data_root: Path | None = None,
) -> DataLoader:
    """Create validation dataloader with different seed for train/val split.

    Args:
        config: Training configuration
        phase: Curriculum phase (same as training for consistency)
        data_root: Override data directory

    Returns:
        DataLoader with validation data (15% split via different seed)

    Note:
        Uses seed=1337 for validation vs seed=42 for training to ensure
        disjoint samples from infinite Genesis stream.
    """
    import copy

    logger.info("create_validation_dataloader: Starting...")

    # Deep copy config to avoid mutating training config
    val_config = copy.deepcopy(config)

    # Mirror training parallelism, but keep disjointness via per-source seeds.
    num_workers = int(getattr(config, "num_workers", 0) or 0)
    use_parallelism = num_workers > 0

    # Create dataset with same settings (yield batches if parallel)
    phase_name = _normalize_phase_name(phase)

    shared_phase = None
    shared_weights = None
    if use_parallelism:
        import multiprocessing as _mp

        ctx = _mp.get_context("spawn")
        shared_phase = ctx.Value(
            "i",
            _PHASE_TO_ID.get(phase_name, _PHASE_TO_ID["joint"]),
            lock=False,
        )
        shared_weights = ctx.Array("d", [0.0] * len(_WEIGHT_SOURCES), lock=False)

    dataset = CurriculumDataset(
        config=val_config,
        phase=phase_name,
        data_root=data_root,
        yield_batches=use_parallelism,
        shared_phase=shared_phase,
        shared_weights=shared_weights,
    )

    # Override seeds in underlying datasets to ensure disjoint samples
    # Genesis datasets use internal RNG - we need to access and modify them
    for source_name, source_ds in dataset.datasets.items():
        if hasattr(source_ds, "seed"):
            # Genesis datasets have seed attribute
            source_ds.seed = 1337  # Validation seed (vs 42 for train)
            logger.debug(f"Set validation seed=1337 for {source_name}")
        if hasattr(source_ds, "_rng"):
            # Override internal RNG if present
            import random

            source_ds._rng = random.Random(1337)

    pin_memory = config.device == "cuda" if hasattr(config, "device") else False

    return DataLoader(
        dataset,
        batch_size=None if use_parallelism else config.batch_size,
        num_workers=num_workers,
        collate_fn=None if use_parallelism else curriculum_collate_fn,
        pin_memory=pin_memory,
        prefetch_factor=int(getattr(config, "prefetch_factor", 2) or 2)
        if use_parallelism
        else None,
        persistent_workers=use_parallelism,
        multiprocessing_context="spawn" if use_parallelism else None,
    )


def create_bucketed_dataloader(
    dataset: Dataset,
    batch_size: int = 32,
    bucket_boundaries: list[int] | None = None,
    drop_last: bool = False,
    shuffle: bool = True,
    num_workers: int = 0,
    length_key: str = "state_t",
    pin_memory: bool = False,
    prefetch_factor: int | None = None,
    persistent_workers: bool = False,
) -> DataLoader:
    """Create a DataLoader with bucketed batch sampling for efficient variable-length sequences.

    This factory function combines BucketedBatchSampler with a standard DataLoader,
    automatically computing sequence lengths and setting up the sampler.

    The bucketed sampler groups sequences by similar length, which:
    - Reduces padding waste (shorter sequences aren't padded to max length)
    - Improves training throughput (less wasted computation on padding)
    - Maintains training stability (batches have consistent sizes within bucket)

    Args:
        dataset: An indexable PyTorch Dataset (NOT IterableDataset).
        batch_size: Number of samples per batch.
        bucket_boundaries: Length thresholds for bucket edges.
            Default: [64, 128, 256, 512, 1024]
        drop_last: If True, drop incomplete batches for training stability.
        shuffle: If True, shuffle within buckets and across batch order.
        num_workers: Number of data loading workers.
        length_key: Key in sample dict containing sequence tensor.
            Common values: "state_t", "x", "positions", "text".
        pin_memory: Pin memory for faster GPU transfer (use True for CUDA).
        prefetch_factor: Batches to prefetch per worker.
        persistent_workers: Keep workers alive between epochs.

    Returns:
        DataLoader with BucketedBatchSampler for efficient batching.

    Example:
        >>> dataset = QM9Dataset(data_dir="data/qm9")
        >>> loader = create_bucketed_dataloader(
        ...     dataset,
        ...     batch_size=64,
        ...     bucket_boundaries=[16, 32, 64, 128],
        ...     drop_last=True,
        ...     length_key="positions",
        ... )
        >>> for batch in loader:
        ...     # All sequences in batch have similar length
        ...     print(batch["positions"].shape)

    Raises:
        TypeError: If dataset is an IterableDataset.
    """
    if isinstance(dataset, IterableDataset):
        raise TypeError(
            "create_bucketed_dataloader requires an indexable Dataset. "
            "For CurriculumDataset (IterableDataset), use yield_batches=True mode instead, "
            "which already handles homogeneous batching internally."
        )

    # Compute sequence lengths for all samples
    logger.info(f"Computing sequence lengths for {len(dataset)} samples...")  # type: ignore[arg-type]
    lengths = compute_sequence_lengths(dataset, length_key=length_key)
    logger.info(
        f"Sequence length stats: min={min(lengths)}, max={max(lengths)}, "
        f"mean={sum(lengths) / len(lengths):.1f}"
    )

    # Create bucketed batch sampler
    batch_sampler = BucketedBatchSampler(
        lengths=lengths,
        bucket_boundaries=bucket_boundaries,
        batch_size=batch_size,
        drop_last=drop_last,
        shuffle=shuffle,
    )

    # DataLoader with batch_sampler (batch_size must be None)
    use_workers = num_workers > 0
    return DataLoader(
        dataset,
        batch_sampler=batch_sampler,
        num_workers=num_workers,
        collate_fn=curriculum_collate_fn,
        pin_memory=pin_memory,
        prefetch_factor=prefetch_factor if use_workers else None,
        persistent_workers=persistent_workers and use_workers,
    )
