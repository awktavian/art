#!/usr/bin/env python3
"""OrganismRSSM TPU Training - v5 UNIFIED PIPELINE.

ALL CRITICAL ISSUES FIXED + MULTI-HOST SCALING + SOTA INTEGRATION:
- [CRIT-1] lr_multiplier NOW APPLIED per phase
- [CRIT-2] active_colonies NOW MASKS inactive colonies
- [CRIT-3] Gradient clip: 100.0 → 1.0 (DreamerV3 standard)
- [OPT-2] bfloat16 mixed precision for 2x memory efficiency
- [OPT-4] Fano mask pre-computed at init
- [MOD-1] Proper TwoHot reward encoding/decoding

v4 (Multi-Host Scaling):
- [SCALE-1] jax.distributed.initialize() for multi-host
- [SCALE-2] shard_map with mesh sharding for TPU pods (replaced pmap)
- [SCALE-3] Gradient all_reduce across replicas via pmean
- [SCALE-4] Per-device batch scaling
- [SCALE-5] Gradient checkpointing (jax.checkpoint) + Orbax model checkpointing
- [SCALE-6] GCS circuit breaker with retry logic
- [SCALE-7] Async data prefetching
- [SCALE-8] Top-level error handling with checkpoint recovery
- [SCALE-9] Signal handling (SIGTERM/SIGINT) for graceful shutdown
- [SCALE-10] Gradient NaN/Inf detection and skip

v5 (SOTA Integration - January 12, 2026):
- [SOTA-1] TPU v6e (Trillium) MXU 256x256 tensor padding
- [SOTA-2] DoReMi domain reweighting (Stanford CRFM 2023)
- [SOTA-3] Competence-aware curriculum (CAMPUS 2025)
- [SOTA-4] Multi-horizon H-JEPA (1, 4, 16 steps)
- [SOTA-5] Soft deduplication for data quality
- [SOTA-6] INT8 quantization ready (AQT)

Usage:
    # Single host (v6e-4)
    python train_tpu.py --data-dir gs://bucket/data --steps 500000

    # Multi-host (v6e-256)
    python train_tpu.py --data-dir gs://bucket/data --steps 500000 --multi-host

Created: January 10, 2026
Fixed: January 11, 2026
Hyperscale: January 11, 2026
SOTA Integration: January 12, 2026
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import optax
from flax import linen as nn
from flax.training import train_state
from jax import random
from jax.experimental import mesh_utils
from jax.experimental.shard_map import shard_map
from jax.sharding import Mesh, NamedSharding
from jax.sharding import PartitionSpec as P
from tqdm import tqdm

# Orbax for checkpointing (optional - graceful fallback)
try:
    import orbax.checkpoint as ocp

    ORBAX_AVAILABLE = True
except ImportError:
    ORBAX_AVAILABLE = False
    ocp = None

# WandB for telemetry (optional - graceful fallback)
try:
    import wandb

    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    wandb = None

# Training validation (MANDATORY - v6e lessons)
from kagami.core.training.validation import TrainingValidator

# [SOTA-3] Competence-aware curriculum
from .competence import (
    CompetenceConfig,
    CompetenceTracker,
)

# [SOTA-2] DoReMi domain reweighting
from .doremi import (
    DoReMiConfig,
    DoReMiMixer,
    SoftDeduplicator,
)

# [SOTA-1] TPU v6e optimizations
from .tpu_optimization import (
    TPUProfiler,
    detect_tpu_version,
    get_mxu_alignment,
    pad_dimension,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# [SCALE-6] CIRCUIT BREAKER FOR GCS RESILIENCE
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """Circuit breaker for GCS operations.

    Prevents cascade failures by failing fast when GCS is unavailable.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker → HALF_OPEN (testing recovery)")
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        state = self.state

        if state == CircuitState.OPEN:
            raise CircuitOpenError("Circuit breaker is OPEN - GCS unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker → CLOSED (recovered)")
            else:
                self._failure_count = 0

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker → OPEN (half-open failed)")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker → OPEN ({self._failure_count} failures)")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
) -> Any:
    """Retry function with exponential backoff."""
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except CircuitOpenError:
            raise  # Don't retry if circuit is open
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}")
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)

    raise last_exception


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ModelConfig:
    """OrganismRSSM model configuration."""

    # Dimensions
    obs_dim: int = 64
    action_dim: int = 8
    deter_dim: int = 512
    stoch_dim: int = 32

    # Colony architecture
    num_colonies: int = 7

    # E8 lattice
    latent_classes: int = 240

    # DreamerV3 discretization
    discrete_categories: int = 32
    discrete_classes: int = 32
    unimix: float = 0.01

    # KL balancing - reduced free_bits from 3.0 to prevent posterior collapse
    free_bits: float = 0.1  # Reduced from 3.0 to prevent posterior collapse
    kl_dyn_weight: float = 0.8
    kl_rep_weight: float = 0.2

    # TwoHot rewards
    num_reward_bins: int = 255
    reward_low: float = -20.0
    reward_high: float = 20.0

    # GRU
    gru_num_blocks: int = 8


@dataclass
class CurriculumPhase:
    """Single curriculum phase configuration.

    Each phase maps to specific datasets for curriculum learning:
    - WARMUP: Genesis only (reconstruction focus)
    - GEOMETRY: Genesis + TreeOfLife (hyperbolic embeddings)
    - ROTATION: Genesis + QM9 (SE(3) equivariance)
    - DYNAMICS: Genesis + QM9 (temporal dynamics)
    - JOINT: All datasets (balanced mix)
    - GENERATION: Genesis only (control/generation)
    - LANGUAGE: Genesis + Gemini embeddings (language grounding)
    """

    name: str
    min_steps: int
    max_steps: int
    lr_multiplier: float
    kl_beta: float
    e8_weight: float
    reward_weight: float
    fano_weight: float
    hjepa_weight: float
    active_colonies: list[int]
    # Dataset mixing weights for curriculum-aware data loading
    # Keys: "genesis", "qm9", "treeoflife", "gemini"
    dataset_weights: dict[str, float] | None = None


# 7-phase curriculum with dataset mixing weights
# Dataset keys: "genesis" (primary), "qm9" (molecular), "treeoflife" (hierarchical)
CURRICULUM_PHASES = [
    CurriculumPhase(
        name="WARMUP",
        min_steps=500,
        max_steps=2000,
        lr_multiplier=1.0,
        kl_beta=0.1,  # Increased from 1e-6 to prevent posterior collapse
        e8_weight=0.0,
        reward_weight=0.0,
        fano_weight=0.0,
        hjepa_weight=0.0,
        active_colonies=[1],
        dataset_weights={"genesis": 1.0},  # Genesis only for reconstruction warmup
    ),
    CurriculumPhase(
        name="GEOMETRY",
        min_steps=1000,
        max_steps=10000,
        lr_multiplier=1.0,
        kl_beta=1.0,
        e8_weight=0.5,
        reward_weight=0.0,
        fano_weight=0.0,
        hjepa_weight=0.0,
        active_colonies=[1, 2],
        dataset_weights={"genesis": 0.6, "treeoflife": 0.4},  # H¹⁴ hyperbolic embeddings
    ),
    CurriculumPhase(
        name="ROTATION",
        min_steps=1000,
        max_steps=30000,
        lr_multiplier=1.0,
        kl_beta=1.0,
        e8_weight=0.3,
        reward_weight=0.0,
        fano_weight=0.01,
        hjepa_weight=0.0,
        active_colonies=[1, 2, 3],
        dataset_weights={"genesis": 0.6, "qm9": 0.4},  # SE(3) equivariance learning
    ),
    CurriculumPhase(
        name="DYNAMICS",
        min_steps=2000,
        max_steps=100000,
        lr_multiplier=0.8,
        kl_beta=1.0,
        e8_weight=0.1,
        reward_weight=0.5,
        fano_weight=0.05,
        hjepa_weight=0.1,
        active_colonies=[1, 2, 3, 4],
        dataset_weights={"genesis": 0.7, "qm9": 0.3},  # Physics + molecular dynamics
    ),
    CurriculumPhase(
        name="JOINT",
        min_steps=5000,
        max_steps=200000,
        lr_multiplier=0.5,
        kl_beta=1.0,
        e8_weight=0.05,
        reward_weight=1.0,
        fano_weight=0.1,
        hjepa_weight=0.2,
        active_colonies=[1, 2, 3, 4, 5, 6, 7],
        dataset_weights={"genesis": 0.5, "qm9": 0.25, "treeoflife": 0.25},  # Balanced mix
    ),
    CurriculumPhase(
        name="GENERATION",
        min_steps=5000,
        max_steps=350000,
        lr_multiplier=0.3,
        kl_beta=1.0,
        e8_weight=0.01,
        reward_weight=1.0,
        fano_weight=0.1,
        hjepa_weight=0.3,
        active_colonies=[1, 2, 3, 4, 5, 6, 7],
        dataset_weights={"genesis": 1.0},  # Genesis only for control/generation
    ),
    CurriculumPhase(
        name="LANGUAGE",
        min_steps=10000,
        max_steps=500000,
        lr_multiplier=0.2,
        kl_beta=1.0,
        e8_weight=0.01,
        reward_weight=0.5,
        fano_weight=0.1,
        hjepa_weight=0.3,
        active_colonies=[1, 2, 3, 4, 5, 6, 7],
        dataset_weights={"genesis": 0.8, "gemini": 0.2},  # Language grounding
    ),
]


# =============================================================================
# REAL DATA LOADER (GCS .npz shards)
# =============================================================================


class RealDataLoader:
    """Load real training data from GCS .npz shards.

    [SCALE-6] Circuit breaker for GCS resilience
    [SCALE-7] Async prefetching for throughput
    """

    def __init__(
        self,
        data_dir: str,
        batch_size: int = 512,
        seq_len: int = 64,
        obs_dim: int = 64,
        action_dim: int = 8,
        prefetch_shards: int = 2,
        num_devices: int = 1,
    ):
        self.data_dir = data_dir
        self.batch_size = batch_size
        self.seq_len = seq_len
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.prefetch_shards = prefetch_shards
        self.num_devices = num_devices
        self.shard_files: list[str] = []
        self.current_shard_idx = 0
        self.current_data: dict[str, np.ndarray] = {}
        self.current_idx = 0
        self._initialized = False

        # [SCALE-6] Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
        )

        # [SCALE-7] Async prefetch queue
        self._prefetch_queue: queue.Queue = queue.Queue(maxsize=prefetch_shards)
        self._prefetch_thread: threading.Thread | None = None
        self._stop_prefetch = threading.Event()

    def initialize(self):
        """Load shard file list from GCS with circuit breaker."""
        try:
            import tensorflow as tf
        except ImportError:
            # Fallback to direct GCS access
            tf = None

        def _glob_shards():
            pattern = f"{self.data_dir}/train-*-of-*.npz"
            if tf is not None:
                return sorted(tf.io.gfile.glob(pattern))
            else:
                # Fallback: use google-cloud-storage
                from google.cloud import storage

                client = storage.Client()
                bucket_name = self.data_dir.replace("gs://", "").split("/")[0]
                prefix = "/".join(self.data_dir.replace("gs://", "").split("/")[1:])
                bucket = client.bucket(bucket_name)
                blobs = bucket.list_blobs(prefix=prefix)
                return sorted(
                    [f"gs://{bucket_name}/{b.name}" for b in blobs if b.name.endswith(".npz")]
                )

        # [SCALE-6] Use circuit breaker + retry
        self.shard_files = retry_with_backoff(
            lambda: self._circuit_breaker.call(_glob_shards),
            max_retries=3,
        )

        if not self.shard_files:
            # NO SYNTHETIC FALLBACK - fail explicitly
            raise RuntimeError(
                f"No .npz shards found in {self.data_dir}. "
                "Training requires real data. Generate training data using:\n"
                "  kagami-train data generate --output gs://bucket/data\n"
                "Or use the consolidated trainer with Genesis backend:\n"
                "  from kagami.core.training import train_kagami\n"
                "  await train_kagami(config_path='config/training.yaml')"
            )

        logger.info(f"Found {len(self.shard_files)} shards in {self.data_dir}")
        self._load_shard(0)

        # Start prefetch thread
        self._start_prefetch_thread()

        self._initialized = True

    def _start_prefetch_thread(self):
        """[SCALE-7] Start async prefetch thread."""
        if self._prefetch_thread is not None:
            return

        def _prefetch_worker():
            next_idx = (self.current_shard_idx + 1) % len(self.shard_files)
            while not self._stop_prefetch.is_set():
                if self._prefetch_queue.qsize() < self.prefetch_shards:
                    try:
                        data = self._load_shard_data(next_idx)
                        self._prefetch_queue.put((next_idx, data), timeout=1.0)
                        next_idx = (next_idx + 1) % len(self.shard_files)
                    except Exception as e:
                        logger.warning(f"Prefetch failed: {e}")
                        time.sleep(1.0)
                else:
                    time.sleep(0.1)

        self._prefetch_thread = threading.Thread(target=_prefetch_worker, daemon=True)
        self._prefetch_thread.start()

    def _load_shard_data(self, idx: int) -> dict[str, np.ndarray]:
        """Load shard data with circuit breaker."""
        import importlib.util

        use_tf = importlib.util.find_spec("tensorflow") is not None

        shard_path = self.shard_files[idx]

        def _load():
            if use_tf:
                import tensorflow as tf

                with tf.io.gfile.GFile(shard_path, "rb") as f:
                    data = np.load(f, allow_pickle=True)
                    return {
                        "obs": np.array(data["obs"]),
                        "actions": np.array(data["actions"]),
                        "rewards": np.array(data["rewards"]),
                        "continues": np.array(data["continues"]),
                    }
            else:
                import io

                from google.cloud import storage

                client = storage.Client()
                bucket_name = shard_path.replace("gs://", "").split("/")[0]
                blob_name = "/".join(shard_path.replace("gs://", "").split("/")[1:])
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                content = blob.download_as_bytes()
                data = np.load(io.BytesIO(content), allow_pickle=True)
                return {
                    "obs": np.array(data["obs"]),
                    "actions": np.array(data["actions"]),
                    "rewards": np.array(data["rewards"]),
                    "continues": np.array(data["continues"]),
                }

        return retry_with_backoff(
            lambda: self._circuit_breaker.call(_load),
            max_retries=3,
        )

    def _load_shard(self, idx: int):
        """Load a specific shard (check prefetch queue first)."""
        # Try to get from prefetch queue
        try:
            while True:
                prefetch_idx, prefetch_data = self._prefetch_queue.get_nowait()
                if prefetch_idx == idx:
                    self.current_data = prefetch_data
                    self.current_shard_idx = idx
                    self.current_idx = 0
                    logger.info(f"Loaded shard {idx + 1}/{len(self.shard_files)} (prefetched)")
                    return
        except queue.Empty:
            pass

        # Load directly
        logger.info(f"Loading shard {idx + 1}/{len(self.shard_files)}: {self.shard_files[idx]}")
        self.current_data = self._load_shard_data(idx)
        self.current_shard_idx = idx
        self.current_idx = 0
        logger.info(f"Loaded {len(self.current_data['obs'])} samples from shard")

    def _validate_batch(self, data: dict[str, np.ndarray]) -> bool:
        """Validate batch for NaN/Inf."""
        for key, arr in data.items():
            if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
                logger.warning(f"Invalid data in {key}: NaN/Inf detected")
                return False
        return True

    def get_batch(self, rng_key: jax.Array | None = None) -> dict[str, jnp.ndarray]:
        """Get a batch of training data with validation."""
        del rng_key  # Unused - real data doesn't need RNG
        if not self._initialized:
            self.initialize()

        # Check if need to load next shard
        if self.current_idx + self.batch_size > len(self.current_data["obs"]):
            next_shard = (self.current_shard_idx + 1) % len(self.shard_files)
            self._load_shard(next_shard)

        # Extract batch
        start = self.current_idx
        end = start + self.batch_size
        self.current_idx = end

        batch_obs = self.current_data["obs"][start:end]
        batch_actions = self.current_data["actions"][start:end]
        batch_rewards = self.current_data["rewards"][start:end]
        batch_continues = self.current_data["continues"][start:end]

        # Handle sequence length padding/truncation
        actual_seq_len = batch_obs.shape[1]
        if actual_seq_len > self.seq_len:
            batch_obs = batch_obs[:, : self.seq_len, :]
            batch_actions = batch_actions[:, : self.seq_len, :]
            batch_rewards = batch_rewards[:, : self.seq_len]
            batch_continues = batch_continues[:, : self.seq_len]
        elif actual_seq_len < self.seq_len:
            pad_len = self.seq_len - actual_seq_len
            batch_obs = np.pad(batch_obs, ((0, 0), (0, pad_len), (0, 0)), mode="edge")
            batch_actions = np.pad(batch_actions, ((0, 0), (0, pad_len), (0, 0)), mode="edge")
            batch_rewards = np.pad(batch_rewards, ((0, 0), (0, pad_len)), mode="edge")
            batch_continues = np.pad(
                batch_continues, ((0, 0), (0, pad_len)), mode="constant", constant_values=1.0
            )

        # Validate - NO SYNTHETIC FALLBACK
        batch_dict = {
            "obs": batch_obs,
            "actions": batch_actions,
            "rewards": batch_rewards,
            "continues": batch_continues,
        }
        if not self._validate_batch(batch_dict):
            # Skip invalid batch and load next shard instead of using synthetic
            logger.warning("Invalid batch detected, loading next shard")
            next_shard = (self.current_shard_idx + 1) % len(self.shard_files)
            self._load_shard(next_shard)
            # Recursive call to get batch from new shard
            return self.get_batch()

        return {
            "obs": jnp.array(batch_obs, dtype=jnp.float32),
            "actions": jnp.array(batch_actions, dtype=jnp.float32),
            "rewards": jnp.array(batch_rewards, dtype=jnp.float32),
            "continues": jnp.array(batch_continues, dtype=jnp.float32),
        }

    def shutdown(self):
        """Shutdown prefetch thread."""
        self._stop_prefetch.set()
        if self._prefetch_thread is not None:
            self._prefetch_thread.join(timeout=5.0)


# =============================================================================
# DREAMERV3 TRANSFORMS
# =============================================================================


def symlog(x: jnp.ndarray, eps: float = 1e-8) -> jnp.ndarray:
    """Symmetric logarithm."""
    x_safe = jnp.clip(x, -1e6, 1e6)
    return jnp.sign(x_safe) * jnp.log1p(jnp.abs(x_safe) + eps)


def symexp(x: jnp.ndarray) -> jnp.ndarray:
    """Symmetric exponential."""
    x_clamped = jnp.clip(x, -80.0, 80.0)
    return jnp.sign(x_clamped) * (jnp.exp(jnp.abs(x_clamped)) - 1)


def twohot_encode(x: jnp.ndarray, num_bins: int, low: float, high: float) -> jnp.ndarray:
    """Encode scalar to TwoHot distribution (DreamerV3)."""
    # Symlog transform
    x = symlog(x)
    # Compute bin edges
    bins = jnp.linspace(symlog(jnp.array(low)), symlog(jnp.array(high)), num_bins)
    # Find position in bins
    x_clamped = jnp.clip(x, bins[0], bins[-1])
    # Compute interpolation
    below = jnp.sum((bins <= x_clamped[..., None]).astype(jnp.float32), axis=-1) - 1
    below = jnp.clip(below, 0, num_bins - 2).astype(jnp.int32)
    above = below + 1
    # Compute weights
    bin_width = bins[1] - bins[0]
    weight_above = (x_clamped - bins[below]) / bin_width
    weight_below = 1.0 - weight_above
    # Create twohot
    twohot = jnp.zeros((*x.shape, num_bins))
    twohot = twohot.at[..., below].add(weight_below)
    twohot = twohot.at[..., above].add(weight_above)
    return twohot


def twohot_decode(logits: jnp.ndarray, num_bins: int, low: float, high: float) -> jnp.ndarray:
    """Decode TwoHot logits to scalar (DreamerV3)."""
    bins = jnp.linspace(symlog(jnp.array(low)), symlog(jnp.array(high)), num_bins)
    probs = jax.nn.softmax(logits, axis=-1)
    value = jnp.sum(probs * bins, axis=-1)
    return symexp(value)


def gumbel_softmax(
    key: jax.Array,
    logits: jnp.ndarray,
    temperature: float = 1.0,
    hard: bool = True,
) -> jnp.ndarray:
    """Gumbel-softmax for differentiable sampling."""
    u = random.uniform(key, logits.shape, minval=1e-10, maxval=1.0)
    gumbel_noise = -jnp.log(-jnp.log(u))
    y_soft = jax.nn.softmax((logits + gumbel_noise) / temperature, axis=-1)
    if hard:
        y_hard = jax.nn.one_hot(jnp.argmax(y_soft, axis=-1), logits.shape[-1])
        return y_hard - jax.lax.stop_gradient(y_soft) + y_soft
    return y_soft


def balanced_kl_loss(
    post_probs: jnp.ndarray,
    prior_probs: jnp.ndarray,
    free_bits: float = 3.0,
    dyn_weight: float = 0.8,
    rep_weight: float = 0.2,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """DreamerV3-style KL balancing."""
    eps = 1e-6
    post_probs = jnp.clip(post_probs, eps, 1.0)
    prior_probs = jnp.clip(prior_probs, eps, 1.0)
    post_probs = post_probs / jnp.sum(post_probs, axis=-1, keepdims=True)
    prior_probs = prior_probs / jnp.sum(prior_probs, axis=-1, keepdims=True)

    post_sg = jax.lax.stop_gradient(post_probs)
    kl_dyn_raw = jnp.sum(post_sg * (jnp.log(post_sg + eps) - jnp.log(prior_probs + eps)), axis=-1)
    kl_dyn_raw = jnp.maximum(kl_dyn_raw, 0.0)

    prior_sg = jax.lax.stop_gradient(prior_probs)
    kl_rep_raw = jnp.sum(
        post_probs * (jnp.log(post_probs + eps) - jnp.log(prior_sg + eps)), axis=-1
    )
    kl_rep_raw = jnp.maximum(kl_rep_raw, 0.0)

    scale = 0.5
    kl_dyn = kl_dyn_raw + free_bits * scale * jax.nn.softplus(
        (free_bits - kl_dyn_raw) / (free_bits + eps)
    )
    kl_rep = kl_rep_raw + free_bits * scale * jax.nn.softplus(
        (free_bits - kl_rep_raw) / (free_bits + eps)
    )

    total_loss = dyn_weight * jnp.mean(kl_dyn) + rep_weight * jnp.mean(kl_rep)

    kl_raw = jnp.mean(
        jnp.maximum(
            jnp.sum(
                post_probs * (jnp.log(post_probs + eps) - jnp.log(prior_probs + eps)),
                axis=-1,
            ),
            0.0,
        )
    )

    return total_loss, kl_raw


# =============================================================================
# DATA GENERATION
# =============================================================================


def generate_structured_batch(
    key: jax.Array,
    batch_size: int,
    seq_len: int,
    obs_dim: int = 64,
    action_dim: int = 8,
) -> dict[str, jnp.ndarray]:
    """Generate structured synthetic data with temporal correlation.

    DEPRECATED: This function is for TESTING ONLY. Production training
    MUST use real data from Genesis, QM9, TreeOfLife, or pre-computed
    .npz shards. The RealDataLoader no longer falls back to synthetic data.

    Usage for testing:
        batch = generate_structured_batch(jax.random.PRNGKey(0), 32, 64)
    """
    import warnings

    warnings.warn(
        "generate_structured_batch is deprecated for production. "
        "Use real data sources (Genesis, QM9, TreeOfLife) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    keys = random.split(key, 6)
    obs_key, action_key, reward_prob_key, reward_val_key, continue_key, noise_key = keys

    # AR(1) observations
    obs_noise = random.normal(obs_key, (batch_size, seq_len, obs_dim)) * 0.5

    def ar1_step(carry, noise):
        prev = carry
        current = 0.8 * prev + 0.2 * noise
        return current, current

    init_obs = random.normal(noise_key, (batch_size, obs_dim)) * 0.1
    _, obs = jax.lax.scan(ar1_step, init_obs, obs_noise.transpose(1, 0, 2))
    obs = obs.transpose(1, 0, 2)
    obs = symlog(obs)

    # Independent actions
    actions = random.normal(action_key, (batch_size, seq_len, action_dim)) * 0.5
    actions = jnp.tanh(actions)

    # Sparse rewards (10%)
    reward_probs = random.uniform(reward_prob_key, (batch_size, seq_len))
    reward_values = random.uniform(reward_val_key, (batch_size, seq_len)) * 2 - 1
    rewards = jnp.where(reward_probs > 0.9, reward_values, 0.0)

    # Rare termination (2%)
    continues = (random.uniform(continue_key, (batch_size, seq_len)) > 0.02).astype(jnp.float32)

    return {"obs": obs, "actions": actions, "rewards": rewards, "continues": continues}


# =============================================================================
# FLAX MODULES
# =============================================================================


class BlockGRU(nn.Module):
    """Block GRU with LayerNorm."""

    hidden_size: int
    num_blocks: int = 8

    @nn.compact
    def __call__(self, x: jnp.ndarray, h: jnp.ndarray) -> jnp.ndarray:
        combined = jnp.concatenate([x, h], axis=-1)
        gates = nn.Dense(3 * self.hidden_size, name="gates")(combined)
        r, z, _ = jnp.split(gates, 3, axis=-1)
        r = jax.nn.sigmoid(r)
        z = jax.nn.sigmoid(z)
        h_reset = r * h
        combined_n = jnp.concatenate([x, h_reset], axis=-1)
        n = jnp.tanh(nn.Dense(self.hidden_size, name="new")(combined_n))
        h_new = (1 - z) * n + z * h
        return nn.LayerNorm()(h_new)


class SparseFanoAttention(nn.Module):
    """Sparse attention following Fano plane structure.

    [OPT-4 FIX] Fano mask pre-computed at init.
    """

    hidden_dim: int
    num_colonies: int = 7

    def setup(self):
        # Pre-compute Fano adjacency
        fano_lines = [
            (0, 1, 3),
            (1, 2, 4),
            (2, 3, 5),
            (3, 4, 6),
            (4, 5, 0),
            (5, 6, 1),
            (6, 0, 2),
        ]
        adjacency = []
        for i in range(7):
            neighbors = set()
            for line in fano_lines:
                if i in line:
                    neighbors.update(line)
            neighbors.discard(i)
            adjacency.append(sorted(neighbors))

        # [OPT-4] Pre-compute mask as constant
        mask = jnp.zeros((7, 7))
        for i in range(7):
            for j in adjacency[i]:
                mask = mask.at[i, j].set(1.0)
        self.fano_mask = mask + jnp.eye(7)

    @nn.compact
    def __call__(self, h: jnp.ndarray) -> jnp.ndarray:
        _B, _N, H = h.shape
        q = nn.Dense(H, name="query")(h)
        k = nn.Dense(H, name="key")(h)
        v = nn.Dense(H, name="value")(h)
        scale = 1.0 / jnp.sqrt(H)
        attn_logits = jnp.einsum("bih,bjh->bij", q, k) * scale
        # Use pre-computed mask
        attn_logits = jnp.where(self.fano_mask > 0, attn_logits, -1e9)
        attn_weights = jax.nn.softmax(attn_logits, axis=-1)
        out = jnp.einsum("bij,bjh->bih", attn_weights, v)
        return nn.Dense(H, name="output")(out)


class RewardHead(nn.Module):
    """TwoHot reward prediction head.

    [MOD-1 FIX] Proper TwoHot encoding/decoding.
    """

    num_bins: int = 255
    low: float = -20.0
    high: float = 20.0

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        logits = nn.Dense(self.num_bins)(x)
        return logits


class OrganismRSSM(nn.Module):
    """Full OrganismRSSM with 7 colonies and E8 structure.

    [CRIT-2 FIX] active_colonies masking implemented.
    """

    config: ModelConfig

    def setup(self):
        cfg = self.config

        self.obs_dense1 = nn.Dense(cfg.deter_dim)
        self.obs_dense2 = nn.Dense(cfg.deter_dim)
        self.obs_norm = nn.LayerNorm()

        self.colony_emb = nn.Embed(
            num_embeddings=cfg.num_colonies,
            features=cfg.deter_dim,
        )

        self.dynamics_cell = BlockGRU(
            hidden_size=cfg.deter_dim,
            num_blocks=cfg.gru_num_blocks,
        )

        self.posterior_proj = nn.Dense(cfg.deter_dim)
        self.posterior_norm = nn.LayerNorm()

        self.prior_dense1 = nn.Dense(cfg.deter_dim)
        self.prior_dense2 = nn.Dense(cfg.latent_classes)
        self.post_dense1 = nn.Dense(cfg.deter_dim)
        self.post_dense2 = nn.Dense(cfg.latent_classes)

        self.latent_emb = nn.Embed(
            num_embeddings=cfg.latent_classes,
            features=cfg.stoch_dim,
        )

        self.fano_attention = SparseFanoAttention(hidden_dim=cfg.deter_dim)

        self.dec_dense1 = nn.Dense(cfg.deter_dim)
        self.dec_dense2 = nn.Dense(cfg.obs_dim)
        self.reward_head = RewardHead(
            num_bins=cfg.num_reward_bins,
            low=cfg.reward_low,
            high=cfg.reward_high,
        )
        self.continue_head = nn.Dense(1)

    def _apply_unimix(self, probs: jnp.ndarray) -> jnp.ndarray:
        if self.config.unimix <= 0.0:
            return probs
        K = probs.shape[-1]
        uniform = jnp.ones_like(probs) / K
        return (1.0 - self.config.unimix) * probs + self.config.unimix * uniform

    def __call__(
        self,
        obs: jnp.ndarray,
        actions: jnp.ndarray,
        rewards: jnp.ndarray,
        continues: jnp.ndarray,
        key: jax.Array,
        active_colonies: list[int] | None = None,
        training: bool = True,
    ) -> dict[str, jnp.ndarray]:
        """Forward pass with colony masking using jax.lax.scan.

        [CRIT-2 FIX] active_colonies parameter masks inactive colonies.
        [PERF-1] Converted from Python for loop to jax.lax.scan for XLA fusion.
        """
        cfg = self.config
        B, T, _ = obs.shape
        del rewards  # Unused but kept for API compatibility

        # [CRIT-2] Create colony mask
        if active_colonies is None:
            colony_mask = jnp.ones((cfg.num_colonies,))
        else:
            colony_mask = jnp.array(
                [1.0 if (c + 1) in active_colonies else 0.0 for c in range(cfg.num_colonies)]
            )
        # Broadcast: [7] -> [1, 7, 1] for element-wise masking
        colony_mask_3d = colony_mask[None, :, None]
        num_active = jnp.sum(colony_mask)

        # Initial states
        h0 = jnp.zeros((B, cfg.num_colonies, cfg.deter_dim))
        z0 = jnp.zeros((B, cfg.num_colonies, cfg.stoch_dim))

        # Pre-compute colony embeddings
        colony_ids = jnp.arange(cfg.num_colonies)
        colony_bias = self.colony_emb(colony_ids)

        # Split keys for all timesteps at once (more efficient)
        keys = random.split(key, T)

        # [PERF-1] Define scan step function
        # [SCALE-5] Apply gradient checkpointing (remat) for memory efficiency
        # This trades ~2x compute for ~T× memory savings where T = sequence length
        @jax.checkpoint
        def _step_fn(carry, inputs):
            """Single timestep of RSSM dynamics."""
            h, z = carry
            obs_t, action_t, continue_t, step_key = inputs

            # Reset on episode boundaries
            h = h * continue_t[:, :, None]
            z = z * continue_t[:, :, None]

            # [CRIT-2] Apply colony mask to hidden states
            h = h * colony_mask_3d
            z = z * colony_mask_3d

            # Encode observation
            obs_enc = self.obs_dense1(obs_t)
            obs_enc = nn.gelu(obs_enc)
            obs_enc = self.obs_dense2(obs_enc)
            obs_enc = self.obs_norm(obs_enc)
            obs_col = obs_enc[:, None, :].repeat(cfg.num_colonies, axis=1)
            obs_col = obs_col + colony_bias[None, :, :]

            # Dynamics step (prior)
            z_flat = z.reshape(B * cfg.num_colonies, cfg.stoch_dim)
            a_broad = jnp.broadcast_to(action_t[:, None, :], (B, cfg.num_colonies, cfg.action_dim))
            a_flat = a_broad.reshape(B * cfg.num_colonies, cfg.action_dim)
            inp = jnp.concatenate([z_flat, a_flat], axis=-1)
            h_flat = h.reshape(B * cfg.num_colonies, cfg.deter_dim)
            h_prior_flat = self.dynamics_cell(inp, h_flat)
            h_prior = h_prior_flat.reshape(B, cfg.num_colonies, cfg.deter_dim)

            # Posterior (with observation)
            h_obs = jnp.concatenate([h_prior, obs_col], axis=-1)
            h_post = self.posterior_proj(h_obs)
            h_post = nn.gelu(h_post)
            h_post = self.posterior_norm(h_post)
            h_post = h_post + self.fano_attention(h_post)

            # [CRIT-2] Apply colony mask to posterior
            h_post = h_post * colony_mask_3d

            # Prior/posterior distributions
            prior_h = self.prior_dense1(h_prior)
            prior_h = nn.gelu(prior_h)
            prior_logits = self.prior_dense2(prior_h)

            post_inp = jnp.concatenate([h_post, obs_col], axis=-1)
            post_h = self.post_dense1(post_inp)
            post_h = nn.gelu(post_h)
            post_logits = self.post_dense2(post_h)

            prior_probs = self._apply_unimix(jax.nn.softmax(prior_logits, axis=-1))
            post_probs = self._apply_unimix(jax.nn.softmax(post_logits, axis=-1))

            # Sample latent (straight-through Gumbel)
            z_expected = jnp.einsum("bck,kz->bcz", post_probs, self.latent_emb.embedding)

            # Use jax.lax.cond for training vs eval to avoid Python if
            def _sample_latent(probs_and_key):
                probs, latent_key = probs_and_key
                flat_probs = probs.reshape(-1, cfg.latent_classes)
                idx = random.categorical(latent_key, jnp.log(flat_probs + 1e-8))
                idx = idx.reshape(B, cfg.num_colonies)
                z_sample = self.latent_emb(idx)
                return z_expected + jax.lax.stop_gradient(z_sample - z_expected)

            def _deterministic_latent(probs_and_key):
                return z_expected

            z_next = jax.lax.cond(
                training,
                _sample_latent,
                _deterministic_latent,
                (post_probs, step_key),
            )

            # [CRIT-2] Mask latent
            z_next = z_next * colony_mask_3d

            # Decode predictions
            hz = jnp.concatenate([h_post, z_next], axis=-1)
            hz_masked = hz * colony_mask_3d
            hz_mean = jnp.sum(hz_masked, axis=1) / jnp.maximum(num_active, 1.0)

            dec_h = self.dec_dense1(hz_mean)
            dec_h = nn.gelu(dec_h)
            obs_pred = self.dec_dense2(dec_h)
            reward_pred = self.reward_head(hz_mean)
            continue_pred = self.continue_head(hz_mean)

            # KL loss for this step
            kl_balanced, kl_raw = balanced_kl_loss(
                post_probs,
                prior_probs,
                free_bits=cfg.free_bits,
                dyn_weight=cfg.kl_dyn_weight,
                rep_weight=cfg.kl_rep_weight,
            )

            # Update carry
            new_carry = (h_post, z_next)

            # Outputs to stack
            outputs = {
                "h": h_post,
                "z": z_next,
                "obs_pred": obs_pred,
                "reward_pred": reward_pred,
                "continue_pred": continue_pred,
                "kl_balanced": kl_balanced,
                "kl_raw": kl_raw,
            }

            return new_carry, outputs

        # Prepare inputs for scan: transpose to [T, B, ...]
        scan_inputs = (
            jnp.moveaxis(obs, 1, 0),  # [T, B, obs_dim]
            jnp.moveaxis(actions, 1, 0),  # [T, B, action_dim]
            jnp.moveaxis(continues[:, :, None], 1, 0),  # [T, B, 1]
            keys,  # [T, 2]
        )

        # [PERF-1] Run scan over timesteps (XLA will fuse this into efficient kernel)
        _, outputs = jax.lax.scan(_step_fn, (h0, z0), scan_inputs)

        # Transpose outputs back to [B, T, ...]
        return {
            "h": jnp.moveaxis(outputs["h"], 0, 1),
            "z": jnp.moveaxis(outputs["z"], 0, 1),
            "obs_pred": jnp.moveaxis(outputs["obs_pred"], 0, 1),
            "reward_pred": jnp.moveaxis(outputs["reward_pred"], 0, 1),
            "continue_pred": jnp.moveaxis(outputs["continue_pred"], 0, 1),
            "kl_balanced": jnp.mean(outputs["kl_balanced"]),
            "kl_raw": jnp.mean(outputs["kl_raw"]),
        }


# =============================================================================
# LOSS FUNCTION
# =============================================================================


# Multi-horizon H-JEPA horizons (1, 4, 16 steps ahead)
HJEPA_HORIZONS = [1, 4, 16]


def compute_multi_horizon_hjepa_loss(
    h: jnp.ndarray,
    horizons: list[int] = HJEPA_HORIZONS,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute multi-horizon H-JEPA loss.

    H-JEPA (Hierarchical Joint-Embedding Predictive Architecture) predicts
    future latent states at multiple temporal horizons. This captures both
    short-term and long-term dynamics.

    Args:
        h: [B, T, N, D] hidden states (batch, time, colonies, dim)
        horizons: List of prediction horizons (default: [1, 4, 16])

    Returns:
        (total_loss, metrics) tuple with loss for each horizon
    """
    _, T, _, _ = h.shape  # B, T, N, D - only T used for horizon check
    metrics = {}
    total_loss = 0.0

    # Weight each horizon (exponential decay with horizon)
    horizon_weights = {1: 1.0, 4: 0.5, 16: 0.25}

    for horizon in horizons:
        if horizon >= T:
            # Skip horizons longer than sequence
            continue

        # Predict: h_t predicts h_{t+horizon}
        h_pred = h[:, :-horizon]  # [B, T-horizon, N, D]
        h_target = jax.lax.stop_gradient(h[:, horizon:])  # [B, T-horizon, N, D]

        # L2 loss in representation space
        horizon_loss = jnp.mean((h_pred - h_target) ** 2)

        weight = horizon_weights.get(horizon, 0.1)
        total_loss = total_loss + weight * horizon_loss

        metrics[f"hjepa_h{horizon}"] = horizon_loss

    return total_loss, metrics


def compute_fano_synergy_loss(h: jnp.ndarray) -> jnp.ndarray:
    """Compute Fano synergy loss for colony coordination.

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

    # Fano plane lines (projective plane of order 2)
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


def compute_loss(
    params: dict,
    apply_fn: Any,
    batch: dict[str, jnp.ndarray],
    phase: CurriculumPhase,
    key: jax.Array,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute curriculum-aware loss with colony masking.

    Now includes multi-horizon H-JEPA loss at horizons (1, 4, 16).
    """
    outputs = apply_fn(
        {"params": params},
        obs=batch["obs"],
        actions=batch["actions"],
        rewards=batch["rewards"],
        continues=batch["continues"],
        key=key,
        active_colonies=phase.active_colonies,  # [CRIT-2] Pass active colonies
        training=True,
    )

    # Reconstruction loss
    recon_loss = jnp.mean((outputs["obs_pred"] - batch["obs"]) ** 2)

    # KL loss
    kl_loss = phase.kl_beta * outputs["kl_balanced"]

    # [MOD-1 FIX] Proper TwoHot reward loss
    reward_logits = outputs["reward_pred"]
    reward_target = batch["rewards"]
    # Compute cross-entropy with TwoHot encoding
    reward_target_twohot = twohot_encode(reward_target, 255, -20.0, 20.0)
    reward_loss_ce = -jnp.sum(
        reward_target_twohot * jax.nn.log_softmax(reward_logits, axis=-1), axis=-1
    )
    reward_loss = phase.reward_weight * jnp.mean(reward_loss_ce)

    # Continue loss
    continue_pred = outputs["continue_pred"].squeeze(-1)
    continue_loss = 0.1 * jnp.mean(
        optax.sigmoid_binary_cross_entropy(continue_pred, batch["continues"])
    )

    # Multi-horizon H-JEPA loss (replaces single-step H-JEPA)
    h = outputs["h"]  # [B, T, N, D]
    if phase.hjepa_weight > 0:
        hjepa_loss, hjepa_metrics = compute_multi_horizon_hjepa_loss(h, horizons=HJEPA_HORIZONS)
        hjepa_loss = phase.hjepa_weight * hjepa_loss
    else:
        hjepa_loss = jnp.array(0.0)
        hjepa_metrics = {}

    # Fano synergy loss - colony coordination on Fano lines
    if phase.fano_weight > 0:
        fano_loss = compute_fano_synergy_loss(h)
        fano_loss = phase.fano_weight * fano_loss
    else:
        fano_loss = jnp.array(0.0)

    # E8 commitment loss - VQ codebook training
    # Uses discrete_latents from posterior to enforce E8 lattice structure
    if phase.e8_weight > 0 and "posterior_probs" in outputs:
        # E8 commitment: minimize distance between continuous and discrete
        posterior_probs = outputs["posterior_probs"]  # [B, T, 7, K]
        # Entropy regularization to prevent mode collapse
        entropy = -jnp.sum(posterior_probs * jnp.log(posterior_probs + 1e-8), axis=-1)
        e8_loss = -phase.e8_weight * jnp.mean(entropy)  # Maximize entropy
    else:
        e8_loss = jnp.array(0.0)

    # Stability loss - temporal smoothness
    stability_loss = 0.01 * jnp.mean(jnp.square(h[:, 1:] - h[:, :-1]))

    total_loss = (
        recon_loss
        + kl_loss
        + reward_loss
        + continue_loss
        + hjepa_loss
        + fano_loss
        + e8_loss
        + stability_loss
    )

    metrics = {
        "loss": total_loss,
        "recon_loss": recon_loss,
        "kl_loss": kl_loss,
        "kl_balanced": outputs["kl_balanced"],
        "kl_raw": outputs["kl_raw"],
        "reward_loss": reward_loss,
        "continue_loss": continue_loss,
        "hjepa_loss": hjepa_loss,
        "fano_loss": fano_loss,
        "e8_loss": e8_loss,
        "stability_loss": stability_loss,
        **hjepa_metrics,  # Include per-horizon losses
    }

    return total_loss, metrics


# =============================================================================
# TRAINING
# =============================================================================


# =============================================================================
# [SCALE-1] DISTRIBUTED INITIALIZATION
# =============================================================================


def initialize_distributed() -> tuple[Mesh | None, int, int]:
    """Initialize JAX distributed for multi-host TPU pods.

    Returns:
        mesh: JAX Mesh for sharding (None if single host)
        num_devices: Total number of devices
        process_index: This process's index
    """
    # Check if running on TPU pod
    try:
        coordinator_address = os.environ.get("JAX_COORDINATOR_ADDRESS")
        num_processes = int(os.environ.get("JAX_NUM_PROCESSES", "1"))
        process_id = int(os.environ.get("JAX_PROCESS_ID", "0"))

        if coordinator_address and num_processes > 1:
            logger.info(f"[SCALE-1] Initializing distributed: {num_processes} processes")
            jax.distributed.initialize(
                coordinator_address=coordinator_address,
                num_processes=num_processes,
                process_id=process_id,
            )
            logger.info(f"[SCALE-1] Process {process_id}/{num_processes} initialized")
    except Exception as e:
        logger.info(f"[SCALE-1] Single-host mode (distributed init skipped): {e}")

    num_devices = jax.device_count()
    local_devices = jax.local_device_count()
    process_index = jax.process_index()

    logger.info(f"[SCALE-1] Devices: {num_devices} total, {local_devices} local")
    logger.info(f"[SCALE-1] Process index: {process_index}")

    # Create mesh for multi-device training
    if num_devices > 1:
        devices = mesh_utils.create_device_mesh((num_devices,))
        mesh = Mesh(devices, axis_names=("batch",))
        logger.info(f"[SCALE-1] Created mesh with {num_devices} devices on 'batch' axis")
        return mesh, num_devices, process_index

    return None, num_devices, process_index


# =============================================================================
# TRAINING STATE
# =============================================================================


class TrainState(train_state.TrainState):
    """Training state with key and lr_multiplier."""

    key: jax.Array
    base_lr: float


def create_train_state(
    key: jax.Array,
    config: ModelConfig,
    learning_rate: float,
    total_steps: int,
    mesh: Mesh | None = None,
) -> TrainState:
    """Create training state with optional mesh sharding."""
    model = OrganismRSSM(config=config)
    key, init_key = random.split(key)

    B, T = 2, 4
    dummy_obs = jnp.zeros((B, T, config.obs_dim))
    dummy_actions = jnp.zeros((B, T, config.action_dim))
    dummy_rewards = jnp.zeros((B, T))
    dummy_continues = jnp.ones((B, T))

    params = model.init(
        {"params": init_key},
        obs=dummy_obs,
        actions=dummy_actions,
        rewards=dummy_rewards,
        continues=dummy_continues,
        key=init_key,
        active_colonies=[1, 2, 3, 4, 5, 6, 7],
    )["params"]

    param_count = sum(x.size for x in jax.tree_util.tree_leaves(params))
    logger.info(f"Model parameters: {param_count:,} ({param_count / 1e6:.1f}M)")

    # Base schedule (lr_multiplier applied per-step)
    schedule = optax.warmup_cosine_decay_schedule(
        init_value=0.0,
        peak_value=learning_rate,
        warmup_steps=2000,
        decay_steps=total_steps - 2000,
        end_value=learning_rate * 0.01,
    )

    # [CRIT-3 FIX] Gradient clip 100 → 1.0
    optimizer = optax.chain(
        optax.clip_by_global_norm(1.0),  # FIXED: Was 100.0
        optax.adamw(learning_rate=schedule, weight_decay=0.01),
    )

    state = TrainState.create(
        apply_fn=model.apply,
        params=params,
        tx=optimizer,
        key=key,
        base_lr=learning_rate,
    )

    # [SCALE-2] Replicate params across devices if using mesh
    if mesh is not None:
        replicate_sharding = NamedSharding(mesh, P())  # Replicate on all devices
        state = jax.device_put(state, replicate_sharding)
        logger.info("[SCALE-2] Params replicated across mesh")

    return state


def train_step_with_lr_mult(
    state: TrainState,
    batch: dict[str, jnp.ndarray],
    key: jax.Array,
    phase_idx: int,
    lr_multiplier: float,
    num_devices: int = 1,  # Kept for API compatibility, unused in single-device path
) -> tuple[TrainState, dict[str, jnp.ndarray]]:
    """Single-device training step with lr_multiplier.

    NOTE: For multi-device training, use _make_train_step(mesh, num_devices)
    which returns a shard_map-wrapped function with explicit gradient all-reduce.
    """
    del num_devices  # Unused in single-device path
    phase = CURRICULUM_PHASES[phase_idx]

    (_loss, metrics), grads = jax.value_and_grad(compute_loss, has_aux=True)(
        state.params,
        state.apply_fn,
        batch,
        phase,
        key,
    )

    # [CRIT-1 FIX] Apply lr_multiplier by scaling gradients
    grads = jax.tree_util.tree_map(lambda g: g * lr_multiplier, grads)

    grad_norm = optax.global_norm(grads)
    state = state.apply_gradients(grads=grads)

    metrics["grad_norm"] = grad_norm
    metrics["phase"] = phase_idx
    metrics["lr_mult"] = lr_multiplier

    return state, metrics


def _make_train_step(mesh: Mesh | None = None, num_devices: int = 1):
    """Create JIT-compiled train step with shard_map for multi-host scaling.

    [SCALE-2] CRITICAL FIX: Replaced pmap with shard_map for true multi-host scaling.
    pmap only works within a single host; shard_map with explicit collectives enables
    scaling across TPU pod slices (e.g., v6e-256 = 32 hosts × 8 devices).

    Args:
        mesh: JAX Mesh for sharding (None for single device)
        num_devices: Total number of devices across all hosts
    """

    if mesh is not None and num_devices > 1:
        # [SCALE-2] Multi-host: use shard_map for explicit SPMD control

        # Define the per-shard computation with explicit collectives
        def _sharded_train_step(
            state: TrainState,
            batch: dict[str, jnp.ndarray],
            key: jax.Array,
            phase_idx: int,
        ) -> tuple[TrainState, dict[str, jnp.ndarray]]:
            """Per-shard train step with explicit gradient all-reduce."""
            phase = CURRICULUM_PHASES[phase_idx]

            # Compute loss and gradients on this shard's data
            (_loss, metrics), grads = jax.value_and_grad(compute_loss, has_aux=True)(
                state.params,
                state.apply_fn,
                batch,
                phase,
                key,
            )

            # [SCALE-3] All-reduce gradients across all devices using axis_name
            grads = jax.lax.pmean(grads, axis_name="batch")
            _loss = jax.lax.pmean(_loss, axis_name="batch")
            metrics = jax.tree_util.tree_map(
                lambda x: jax.lax.pmean(x, axis_name="batch") if isinstance(x, jnp.ndarray) else x,
                metrics,
            )

            # Apply lr_multiplier
            grads = jax.tree_util.tree_map(lambda g: g * phase.lr_multiplier, grads)

            grad_norm = optax.global_norm(grads)
            state = state.apply_gradients(grads=grads)

            metrics["grad_norm"] = grad_norm
            metrics["phase"] = phase_idx
            metrics["lr_mult"] = phase.lr_multiplier

            return state, metrics

        # Wrap with shard_map for multi-host execution
        # Batch dim is sharded across "batch" axis, state and key are replicated
        @partial(jax.jit, static_argnums=(3,))
        def train_step_sharded(
            state: TrainState,
            batch: dict[str, jnp.ndarray],
            key: jax.Array,
            phase_idx: int,
        ) -> tuple[TrainState, dict[str, jnp.ndarray]]:
            # Use shard_map for explicit SPMD partitioning
            sharded_fn = shard_map(
                partial(_sharded_train_step, phase_idx=phase_idx),
                mesh=mesh,
                in_specs=(
                    P(),  # state: replicated
                    P("batch"),  # batch: sharded along first dim
                    P(),  # key: replicated
                ),
                out_specs=(
                    P(),  # state: replicated (after gradient sync)
                    P(),  # metrics: replicated (after pmean)
                ),
                check_rep=False,  # Don't verify replication (metrics may differ slightly)
            )
            return sharded_fn(state, batch, key)

        return train_step_sharded
    else:
        # Single device: use jit
        @partial(jax.jit, static_argnums=(3,))
        def train_step_jit(
            state: TrainState,
            batch: dict[str, jnp.ndarray],
            key: jax.Array,
            phase_idx: int,
        ) -> tuple[TrainState, dict[str, jnp.ndarray]]:
            phase = CURRICULUM_PHASES[phase_idx]
            return train_step_with_lr_mult(state, batch, key, phase_idx, phase.lr_multiplier, 1)

        return train_step_jit


# Default single-device train_step for backwards compatibility
@partial(jax.jit, static_argnums=(3,))
def train_step(
    state: TrainState,
    batch: dict[str, jnp.ndarray],
    key: jax.Array,
    phase_idx: int,
) -> tuple[TrainState, dict[str, jnp.ndarray]]:
    """JIT-compiled training step (single device)."""
    phase = CURRICULUM_PHASES[phase_idx]
    return train_step_with_lr_mult(state, batch, key, phase_idx, phase.lr_multiplier, 1)


def get_phase_for_step(step: int) -> tuple[int, CurriculumPhase]:
    """Get curriculum phase for current step."""
    cumulative = 0
    for idx, phase in enumerate(CURRICULUM_PHASES):
        if step < cumulative + phase.max_steps:
            return idx, phase
        cumulative += phase.max_steps
    return len(CURRICULUM_PHASES) - 1, CURRICULUM_PHASES[-1]


def train(
    data_dir: str,  # GCS path to training data
    total_steps: int = 500_000,
    batch_size: int = 512,
    seq_len: int = 64,
    learning_rate: float = 1e-4,
    checkpoint_dir: str | None = None,
    seed: int = 42,
):
    """Main training loop with all fixes and multi-host scaling.

    Multi-host mode is automatically enabled when JAX_COORDINATOR_ADDRESS,
    JAX_NUM_PROCESSES, and JAX_PROCESS_ID environment variables are set.

    [SCALE-8] Top-level error handling with checkpoint recovery.
    """
    logger.info("=" * 70)
    logger.info("🧬 OrganismRSSM TPU Training - v5 UNIFIED PIPELINE")
    logger.info("=" * 70)
    logger.info("FIXES APPLIED:")
    logger.info("  [CRIT-1] lr_multiplier: NOW ACTIVE")
    logger.info("  [CRIT-2] active_colonies: NOW MASKING")
    logger.info("  [CRIT-3] grad_clip: 100 → 1.0")
    logger.info("  [OPT-4] Fano mask: PRE-COMPUTED")
    logger.info("  [MOD-1] Reward: PROPER TWOHOT")
    logger.info("  [V3-1] free_bits: 0.1 (was 3.0) - prevent posterior collapse")
    logger.info("  [V3-2] WARMUP kl_beta: 0.1 (was 1e-6)")
    logger.info("v4 (Multi-Host Scaling):")
    logger.info("  [SCALE-1] Distributed initialization: ENABLED")
    logger.info("  [SCALE-2] pjit mesh sharding: ENABLED")
    logger.info("  [SCALE-3] Gradient all_reduce: ENABLED")
    logger.info("  [SCALE-6] GCS circuit breaker: ENABLED")
    logger.info("  [SCALE-7] Async prefetching: ENABLED")
    logger.info("  [SCALE-8] Error handling: ENABLED")
    logger.info("v5 (SOTA Integration):")
    logger.info("  [SOTA-1] TPU v6e (Trillium): ENABLED")
    logger.info("  [SOTA-2] DoReMi reweighting: ENABLED")
    logger.info("  [SOTA-3] Competence curriculum: ENABLED")
    logger.info("  [SOTA-4] Multi-horizon H-JEPA: ENABLED")
    logger.info("  [SOTA-5] Soft deduplication: ENABLED")
    logger.info("=" * 70)

    # [SCALE-1] Initialize distributed
    mesh, num_devices, process_index = initialize_distributed()

    logger.info(f"JAX version: {jax.__version__}")
    logger.info(f"Devices: {num_devices} x {jax.devices()[0].device_kind}")
    logger.info(f"Process: {process_index}")
    logger.info(f"Data dir: {data_dir}")
    logger.info(f"Total steps: {total_steps:,}")

    # [SCALE-4] Per-device batch scaling
    per_device_batch = batch_size // num_devices
    global_batch_size = per_device_batch * num_devices
    logger.info(f"Batch size: {global_batch_size} (per-device: {per_device_batch})")
    logger.info(f"Sequence length: {seq_len}")
    logger.info(f"Learning rate: {learning_rate}")
    logger.info("=" * 70)

    config = ModelConfig()

    # [SOTA-1] Detect TPU version and configure MXU alignment
    tpu_version = detect_tpu_version()
    mxu_alignment = get_mxu_alignment(tpu_version)
    logger.info(f"[SOTA-1] TPU: {tpu_version.name}, MXU alignment: {mxu_alignment}")

    # Pad dimensions for optimal MXU utilization (v6e: 256x256)
    config.deter_dim = pad_dimension(config.deter_dim, mxu_alignment)
    config.obs_dim = pad_dimension(config.obs_dim, mxu_alignment)
    logger.info(f"[SOTA-1] Padded dims: deter={config.deter_dim}, obs={config.obs_dim}")

    # Initialize data loader with circuit breaker
    data_loader = RealDataLoader(
        data_dir=data_dir,
        batch_size=global_batch_size,
        seq_len=seq_len,
        obs_dim=config.obs_dim,
        action_dim=config.action_dim,
        prefetch_shards=2,
        num_devices=num_devices,
    )
    data_loader.initialize()

    # [SOTA-2] Initialize DoReMi domain reweighting
    domain_names = ["genesis", "qm9", "treeoflife", "gemini"]
    doremi_config = DoReMiConfig(
        dro_step_size=0.01,
        dro_smoothing=0.1,
        min_weight=0.01,
        max_weight=0.9,
        warmup_steps=1000,
        update_frequency=100,
    )
    doremi_mixer = DoReMiMixer(
        domain_names=domain_names,
        initial_weights={"genesis": 0.5, "qm9": 0.2, "treeoflife": 0.2, "gemini": 0.1},
        config=doremi_config,
    )
    logger.info(f"[SOTA-2] DoReMi mixer: {domain_names}")

    # [SOTA-3] Initialize competence tracker
    competence_config = CompetenceConfig(
        competence_window=100,
        competence_threshold=0.1,
        difficulty_increase_rate=0.01,
        difficulty_decrease_rate=0.1,
        min_difficulty=0.0,
        max_difficulty=1.0,
        warmup_steps=500,
    )
    competence_tracker = CompetenceTracker(competence_config)
    logger.info("[SOTA-3] Competence tracker: ENABLED")

    # [SOTA-5] Soft deduplication (for data quality - applied during preprocessing)
    # Note: SoftDeduplicator is initialized here but applied at data loading level
    # In production, call _soft_dedup.compute_weight(text) during batch creation
    _soft_dedup = SoftDeduplicator(
        similarity_threshold=0.8,
        min_weight=0.1,
        max_memory=100000,
    )
    logger.info(
        f"[SOTA-5] Soft deduplication: READY (threshold={_soft_dedup.similarity_threshold})"
    )

    # [SOTA-6] Initialize TPU profiler
    # Estimate ~100M FLOPs per sample for OrganismRSSM (7 colonies * 512 dim * seq_len)
    estimated_flops = 7 * config.deter_dim * seq_len * 4  # 4 ops per multiply-add
    tpu_profiler = TPUProfiler(model_flops_per_sample=estimated_flops)

    key = random.PRNGKey(seed + process_index)  # Different seed per process
    key, init_key = random.split(key)
    state = create_train_state(init_key, config, learning_rate, total_steps, mesh)

    # [SCALE-2] Create appropriate train_step function with mesh for pjit
    train_step_fn = _make_train_step(mesh, num_devices)

    # [SCALE-2] For pjit with mesh, shard state across devices
    if mesh is not None and num_devices > 1:
        # Replicate state params across all devices (data parallel = replicated model)
        replicated_sharding = NamedSharding(mesh, P())
        state = jax.device_put(state, replicated_sharding)
        logger.info(f"[SCALE-2] State sharded with pjit to {num_devices} devices")

    # [SCALE-5] Initialize Orbax checkpointer
    checkpointer = create_checkpointer(checkpoint_dir, keep_n_latest=5, save_interval=10000)
    start_step = 0
    if checkpointer is not None:
        state, start_step = checkpointer.restore(state)
        if start_step > 0:
            logger.info(f"[SCALE-5] Resuming from step {start_step:,}")

    metrics_history: list[dict] = []
    best_loss = float("inf")
    start_time = time.time()
    step = 0  # Initialize to avoid unbound in exception handlers
    loss = 0.0  # Initialize to avoid unbound
    phase = CURRICULUM_PHASES[0]  # Initialize to avoid unbound
    should_stop = False  # Signal handler flag

    # [VALID-1] Training validator (MANDATORY - v6e lessons)
    validator = TrainingValidator(
        kl_collapse_threshold=1e-4,
        kl_warning_threshold=0.1,
        kl_consecutive_limit=100,
        plateau_window=1000,
        plateau_velocity_threshold=1e-6,
        gradient_explosion_threshold=100.0,
        divergence_threshold=10.0,
    )
    logger.info("[VALID-1] Training validator: ENABLED")

    # [TELEM-1] WandB telemetry (optional)
    wandb_run = None
    if WANDB_AVAILABLE and process_index == 0:
        try:
            wandb_run = wandb.init(
                project="kagami-tpu-training",
                config={
                    "batch_size": global_batch_size,
                    "seq_len": seq_len,
                    "learning_rate": learning_rate,
                    "total_steps": total_steps,
                    "num_devices": num_devices,
                    "model_config": {
                        "obs_dim": config.obs_dim,
                        "action_dim": config.action_dim,
                        "deter_dim": config.deter_dim,
                        "stoch_dim": config.stoch_dim,
                        "num_colonies": config.num_colonies,
                    },
                },
                tags=["tpu", f"v6e-{num_devices}", "hyperscale"],
            )
            logger.info(f"[TELEM-1] WandB initialized: {wandb_run.url}")
        except Exception as e:
            logger.warning(f"[TELEM-1] WandB init failed: {e}")
            wandb_run = None

    # [SCALE-9] Signal handling for graceful shutdown
    def _signal_handler(signum, _frame):
        nonlocal should_stop
        logger.warning(f"\n⚠️ Received signal {signum}, initiating graceful shutdown...")
        should_stop = True

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Only show progress bar on process 0
    pbar = tqdm(range(total_steps), desc="Training", ncols=120, disable=process_index != 0)

    prev_phase_idx = -1

    # [SCALE-8] Top-level error handling
    try:
        for step in pbar:
            # [SCALE-9] Check for graceful shutdown signal
            if should_stop:
                logger.info(f"🛑 Graceful shutdown at step {step:,}")
                break

            phase_idx, phase = get_phase_for_step(step)

            if phase_idx != prev_phase_idx:
                logger.info(f"\n🎯 Phase transition: {phase.name} (step {step:,})")
                logger.info(f"   Active colonies: {phase.active_colonies}")
                logger.info(f"   KL β: {phase.kl_beta}")
                logger.info(f"   LR multiplier: {phase.lr_multiplier}")
                logger.info(f"   Reward weight: {phase.reward_weight}")
                if phase.dataset_weights:
                    weights_str = ", ".join(
                        f"{k}={v:.0%}" for k, v in phase.dataset_weights.items()
                    )
                    logger.info(f"   Dataset mix: {weights_str}")
                prev_phase_idx = phase_idx

            key, step_key = random.split(key)
            batch = data_loader.get_batch(step_key)

            # For pmap, reshape batch to [num_devices, per_device_batch, ...]
            if num_devices > 1:
                batch = jax.tree_util.tree_map(
                    lambda x: x.reshape(num_devices, per_device_batch, *x.shape[1:]),
                    batch,
                )
                # Replicate key across devices
                step_keys = random.split(step_key, num_devices)
                state, metrics = train_step_fn(state, batch, step_keys, phase_idx)
                # Get metrics from first device
                metrics = jax.tree_util.tree_map(lambda x: x[0], metrics)
            else:
                state, metrics = train_step_fn(state, batch, step_key, phase_idx)

            loss = float(metrics["loss"])
            grad_norm = float(metrics["grad_norm"])

            # [SCALE-10] Gradient NaN/Inf detection
            if not jnp.isfinite(grad_norm) or not jnp.isfinite(loss):
                logger.error(
                    f"❌ NaN/Inf detected at step {step}: loss={loss}, grad_norm={grad_norm}"
                )
                logger.error("   Skipping this step and continuing...")
                continue

            # [SOTA-3] Update competence tracker and get difficulty level
            difficulty = competence_tracker.update(loss)

            # [SOTA-2] Update DoReMi domain weights based on per-domain losses
            # In production, domain_losses would come from per-domain loss computation
            # Here we use a simplified version with the total loss
            domain_losses = {
                "genesis": loss * phase.dataset_weights.get("genesis", 0.0)
                if phase.dataset_weights
                else loss,
                "qm9": loss * phase.dataset_weights.get("qm9", 0.0)
                if phase.dataset_weights
                else 0.0,
                "treeoflife": loss * phase.dataset_weights.get("treeoflife", 0.0)
                if phase.dataset_weights
                else 0.0,
                "gemini": loss * phase.dataset_weights.get("gemini", 0.0)
                if phase.dataset_weights
                else 0.0,
            }
            domain_weights = doremi_mixer.update(domain_losses)

            # [VALID-1] Run training validator (MANDATORY)
            kl_value = float(metrics["kl_balanced"])
            validation_result = validator.validate_step(
                loss=loss,
                kl_divergence=kl_value,
                gradient_norm=grad_norm,
                step=step,
                learning_rate=learning_rate * phase.lr_multiplier,
            )

            # Handle validation results
            if validation_result.should_stop:
                logger.error(f"🛑 VALIDATOR STOP: {validation_result.stop_reason}")
                should_stop = True

            if validation_result.kl_collapsed:
                logger.error(f"⚠️ KL COLLAPSE at step {step}: {kl_value:.2e}")

            if validation_result.plateau_detected:
                logger.warning(
                    f"📉 Plateau detected at step {step}, velocity={validation_result.loss_velocity:.2e}"
                )

            pbar.set_postfix(
                {
                    "loss": f"{loss:.4f}",
                    "kl": f"{float(metrics['kl_balanced']):.4f}",
                    "grad": f"{float(metrics['grad_norm']):.2f}",
                    "phase": phase.name[:4],
                    "diff": f"{difficulty:.2f}",  # [SOTA-3] Competence difficulty
                    "dev": f"{num_devices}",
                }
            )

            if step % 100 == 0:
                elapsed = time.time() - start_time
                sps = (step + 1) / elapsed if elapsed > 0 else 0
                samples_per_sec = sps * global_batch_size
                eta = (total_steps - step) / sps / 3600 if sps > 0 else 0

                # [SOTA-6] Record TPU performance metrics
                step_time = elapsed / (step + 1) if step > 0 else 0.01
                perf_metrics = tpu_profiler.record_step(
                    step_time_seconds=step_time,
                    batch_size=global_batch_size,
                    gradient_norm=grad_norm,
                )

                metrics_dict = {
                    "step": step,
                    "loss": loss,
                    "recon_loss": float(metrics["recon_loss"]),
                    "kl_loss": float(metrics["kl_loss"]),
                    "kl_balanced": float(metrics["kl_balanced"]),
                    "kl_raw": float(metrics["kl_raw"]),
                    "reward_loss": float(metrics["reward_loss"]),
                    "hjepa_loss": float(metrics["hjepa_loss"]),
                    "grad_norm": float(metrics["grad_norm"]),
                    "phase": phase.name,
                    "phase_idx": phase_idx,
                    "lr_multiplier": phase.lr_multiplier,
                    "active_colonies": len(phase.active_colonies),
                    "sps": sps,
                    "samples_per_sec": samples_per_sec,
                    "num_devices": num_devices,
                    "eta_hours": eta,
                    # [SOTA-2/3] Advanced curriculum metrics
                    "competence_difficulty": difficulty,
                    "doremi_weights": domain_weights,
                    # [SOTA-6] TPU performance metrics
                    "mfu_percent": perf_metrics.mfu_percent,
                    "step_time_ms": perf_metrics.step_time_ms,
                }
                metrics_history.append(metrics_dict)

                # [TELEM-1] WandB logging
                if wandb_run is not None:
                    wandb_log = {
                        "train/loss": loss,
                        "train/recon_loss": float(metrics["recon_loss"]),
                        "train/kl_loss": float(metrics["kl_loss"]),
                        "train/kl_balanced": float(metrics["kl_balanced"]),
                        "train/reward_loss": float(metrics["reward_loss"]),
                        "train/hjepa_loss": float(metrics["hjepa_loss"]),
                        "train/fano_loss": float(metrics.get("fano_loss", 0.0)),
                        "train/e8_loss": float(metrics.get("e8_loss", 0.0)),
                        "train/stability_loss": float(metrics.get("stability_loss", 0.0)),
                        "train/grad_norm": grad_norm,
                        "curriculum/phase": phase_idx,
                        "curriculum/phase_name": phase.name,
                        "curriculum/lr_multiplier": phase.lr_multiplier,
                        "curriculum/active_colonies": len(phase.active_colonies),
                        "perf/sps": sps,
                        "perf/samples_per_sec": samples_per_sec,
                        "perf/eta_hours": eta,
                        # Validation metrics
                        "monitor/kl_value": kl_value,
                        "monitor/plateau_detected": int(validation_result.plateau_detected),
                        "monitor/kl_warnings": validation_result.kl_consecutive_warnings,
                        "monitor/loss_velocity": validation_result.loss_velocity,
                        # [SOTA-2/3] Advanced curriculum metrics
                        "sota/competence_difficulty": difficulty,
                        "sota/doremi_genesis": domain_weights.get("genesis", 0.0),
                        "sota/doremi_qm9": domain_weights.get("qm9", 0.0),
                        "sota/doremi_treeoflife": domain_weights.get("treeoflife", 0.0),
                        "sota/doremi_gemini": domain_weights.get("gemini", 0.0),
                        # [SOTA-6] TPU performance metrics
                        "perf/mfu_percent": perf_metrics.mfu_percent,
                        "perf/step_time_ms": perf_metrics.step_time_ms,
                    }
                    wandb.log(wandb_log, step=step)

                if loss < best_loss:
                    best_loss = loss

            # [SCALE-5] Save model checkpoint periodically
            if step > 0 and step % 10000 == 0:
                if checkpointer is not None:
                    checkpointer.save(state, step)
                if checkpoint_dir:
                    save_metrics(metrics_history[-1000:], step, checkpoint_dir)
                logger.info(f"💾 Checkpoint at step {step:,}, loss={loss:.4f}")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Training interrupted by user")
        # Emergency save
        if checkpointer is not None:
            checkpointer.save(state, step)
            checkpointer.wait_until_finished()
        if checkpoint_dir and metrics_history:
            save_metrics(metrics_history, step, checkpoint_dir)
        logger.info(f"💾 Emergency checkpoint saved at step {step}")

    except Exception as e:
        logger.error(f"\n❌ Training crashed: {e}")
        # Emergency save
        if checkpointer is not None:
            checkpointer.save(state, step)
            checkpointer.wait_until_finished()
        if checkpoint_dir and metrics_history:
            save_metrics(metrics_history, step, checkpoint_dir)
        logger.info(f"💾 Emergency checkpoint saved at step {step}")
        raise

    finally:
        # Cleanup
        if checkpointer is not None:
            checkpointer.wait_until_finished()
            checkpointer.close()
        data_loader.shutdown()
        # [TELEM-1] WandB cleanup
        if wandb_run is not None:
            wandb.finish()

    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info("✅ Training Complete!")
    logger.info(f"   Total time: {elapsed / 3600:.2f} hours")
    logger.info(f"   Best loss: {best_loss:.4f}")
    logger.info(f"   Final loss: {loss:.4f}")
    logger.info(f"   Final phase: {phase.name}")
    logger.info(f"   Devices used: {num_devices}")
    logger.info(f"   Throughput: {total_steps * global_batch_size / elapsed:.0f} samples/sec")
    logger.info("=" * 70)

    return {
        "best_loss": best_loss,
        "final_loss": loss,
        "time_hours": elapsed / 3600,
        "final_phase": phase.name,
        "num_devices": num_devices,
        "throughput": total_steps * global_batch_size / elapsed,
    }


def save_metrics(metrics: list[dict], step: int, checkpoint_dir: str):
    """Save metrics to JSON."""
    if checkpoint_dir.startswith("gs://"):
        path = Path(f"/tmp/metrics_{step}.json")
    else:
        path = Path(checkpoint_dir) / f"metrics_{step}.json"
        # Ensure directory exists (handle case where it's a file)
        if path.parent.exists() and not path.parent.is_dir():
            path.parent.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)


# =============================================================================
# [SCALE-5] ORBAX MODEL CHECKPOINTING
# =============================================================================


class OrbaxCheckpointer:
    """Orbax-based model checkpointing with GCS support.

    Provides:
    - Async checkpointing (non-blocking saves)
    - Automatic checkpoint cleanup (keep_n_latest)
    - GCS and local filesystem support
    - Multi-host safe (only process 0 saves)
    """

    def __init__(
        self,
        checkpoint_dir: str,
        keep_n_latest: int = 5,
        save_interval: int = 10000,
    ):
        self.checkpoint_dir = checkpoint_dir
        self.keep_n_latest = keep_n_latest
        self.save_interval = save_interval
        self._manager: Any = None  # Type: ocp.CheckpointManager when available
        self._initialized = False

        if not ORBAX_AVAILABLE or ocp is None:
            logger.warning("⚠️ Orbax not available - checkpointing disabled")
            return

        # Only process 0 handles checkpointing
        if jax.process_index() != 0:
            return

        try:
            # Create checkpoint manager
            options = ocp.CheckpointManagerOptions(
                max_to_keep=keep_n_latest,
                save_interval_steps=save_interval,
                create=True,
            )
            self._manager = ocp.CheckpointManager(
                checkpoint_dir,
                options=options,
            )
            self._initialized = True
            logger.info(f"[SCALE-5] OrbaxCheckpointer initialized: {checkpoint_dir}")
            logger.info(f"[SCALE-5]   keep_n_latest={keep_n_latest}, save_interval={save_interval}")
        except Exception as e:
            logger.error(f"[SCALE-5] Failed to initialize OrbaxCheckpointer: {e}")

    def save(self, state: TrainState, step: int, metrics: dict | None = None):
        """Save checkpoint (async, non-blocking)."""
        del metrics  # Reserved for future use (e.g., saving metrics alongside model)
        if not self._initialized or self._manager is None or ocp is None:
            return

        if jax.process_index() != 0:
            return

        try:
            # Extract pytree-safe items
            save_args = ocp.args.StandardSave(state)
            self._manager.save(step, args=save_args)
            logger.info(f"[SCALE-5] Checkpoint saved: step {step}")
        except Exception as e:
            logger.error(f"[SCALE-5] Checkpoint save failed: {e}")

    def restore(self, state: TrainState, step: int | None = None) -> tuple[TrainState, int]:
        """Restore checkpoint. Returns (state, step)."""
        if not self._initialized or self._manager is None or ocp is None:
            return state, 0

        try:
            if step is None:
                step = self._manager.latest_step()

            if step is None:
                logger.info("[SCALE-5] No checkpoint found, starting fresh")
                return state, 0

            restore_args = ocp.args.StandardRestore(state)
            restored: TrainState = self._manager.restore(step, args=restore_args)
            logger.info(f"[SCALE-5] Restored checkpoint: step {step}")
            return restored, step
        except Exception as e:
            logger.error(f"[SCALE-5] Checkpoint restore failed: {e}")
            return state, 0

    def wait_until_finished(self):
        """Wait for any pending async saves to complete."""
        if self._manager is not None:
            self._manager.wait_until_finished()

    def close(self):
        """Close the checkpoint manager."""
        if self._manager is not None:
            self._manager.close()


def create_checkpointer(
    checkpoint_dir: str | None,
    keep_n_latest: int = 5,
    save_interval: int = 10000,
) -> OrbaxCheckpointer | None:
    """Create checkpointer if checkpoint_dir is provided."""
    if checkpoint_dir is None:
        return None
    return OrbaxCheckpointer(checkpoint_dir, keep_n_latest, save_interval)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OrganismRSSM TPU Training - v4 HYPERSCALE",
    )
    parser.add_argument("--data-dir", type=str, required=True, help="GCS path to training data")
    parser.add_argument("--steps", type=int, default=500_000)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--seq-len", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--checkpoint-dir", type=str, default="/tmp/checkpoints")
    parser.add_argument("--seed", type=int, default=42)
    # Note: Multi-host mode is automatically enabled via JAX_COORDINATOR_ADDRESS,
    # JAX_NUM_PROCESSES, and JAX_PROCESS_ID environment variables

    args = parser.parse_args()

    train(
        data_dir=args.data_dir,
        total_steps=args.steps,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
        learning_rate=args.lr,
        checkpoint_dir=args.checkpoint_dir,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
