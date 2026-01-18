"""Data Generation Script for GCS Shard Pipeline.

Pre-generates training data shards to GCS for efficient TPU training.
Offloads data generation overhead from TPU to CPU instances.

CRITICAL (Jan 12, 2026):
- samples_per_shard must match global_batch_size in TrainingConfig
- Default is 256 samples per shard for batch_size=256 training

Usage:
    # Generate 1024 shards to GCS (256 samples each)
    python generate_data.py --output gs://kagami-training-data/shards --shards 1024

    # Generate locally for testing
    python generate_data.py --output /tmp/shards --shards 64 --workers 4

Created: January 11, 2026
Updated: January 12, 2026 - Fixed batch size to match TrainingConfig
"""

from __future__ import annotations

import argparse
import io
import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for data generation.

    CRITICAL: samples_per_shard must match global_batch_size in training.
    Default is 256 to match TrainingConfig.batch_size.

    Each shard = one training batch.
    """

    # Output settings
    output_path: str = "gs://kagami-training-data/shards"
    total_shards: int = 1024  # More shards for variety
    samples_per_shard: int = 256  # Must match global_batch_size!

    # Sequence settings
    obs_dim: int = 64
    action_dim: int = 8
    seq_len: int = 64

    # Parallelism
    num_workers: int = 8

    # Random seed
    seed: int = 42


def generate_shard(
    shard_idx: int,
    config: GenerationConfig,
    output_path: str,
) -> str:
    """Generate a single shard of training data.

    Creates temporally-correlated synthetic data:
    - Observations: Smooth random walk with autoregressive structure
    - Actions: Correlated with observation changes
    - Rewards: Based on observation magnitude
    - Continues: 99% probability of continuation

    Args:
        shard_idx: Shard index for seeding
        config: Generation configuration
        output_path: Where to save (GCS or local)

    Returns:
        Path to saved shard
    """
    # Deterministic but unique seed per shard
    rng = np.random.default_rng(config.seed + shard_idx * 1000)

    B = config.samples_per_shard
    T = config.seq_len

    # Generate temporally-correlated observations
    # Using AR(1) process with high autocorrelation
    obs = np.zeros((B, T, config.obs_dim), dtype=np.float32)
    obs[:, 0] = rng.standard_normal((B, config.obs_dim)).astype(np.float32)

    ar_coef = 0.95  # High temporal correlation
    noise_scale = 0.1

    for t in range(1, T):
        noise = rng.standard_normal((B, config.obs_dim)).astype(np.float32) * noise_scale
        obs[:, t] = ar_coef * obs[:, t - 1] + noise

    # Generate actions correlated with observation changes
    obs_diff = np.diff(obs, axis=1, prepend=obs[:, :1, :])
    actions = np.zeros((B, T, config.action_dim), dtype=np.float32)
    # Actions are a learned projection of observation changes
    action_proj = rng.standard_normal((config.obs_dim, config.action_dim)).astype(np.float32)
    action_proj /= np.linalg.norm(action_proj, axis=0, keepdims=True)
    for t in range(T):
        actions[:, t] = obs_diff[:, t] @ action_proj
        actions[:, t] += rng.standard_normal((B, config.action_dim)).astype(np.float32) * 0.1

    # Rewards based on observation magnitude (reward for staying near origin)
    obs_norm = np.linalg.norm(obs, axis=-1)
    rewards = (1.0 - np.tanh(obs_norm / 2.0)).astype(np.float32)  # Higher reward near origin
    rewards += rng.standard_normal((B, T)).astype(np.float32) * 0.1

    # Continues: 99% continuation probability with random terminations
    continues = (rng.random((B, T)) > 0.01).astype(np.float32)

    # Save shard
    shard_name = f"shard_{shard_idx:05d}.npz"

    if output_path.startswith("gs://"):
        # Upload to GCS
        from google.cloud import storage

        path = output_path[5:]  # Remove gs://
        parts = path.split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob_path = f"{prefix}/{shard_name}" if prefix else shard_name
        blob = bucket.blob(blob_path)

        # Save to bytes buffer then upload
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer,
            obs=obs,
            actions=actions,
            rewards=rewards,
            continues=continues,
        )
        buffer.seek(0)
        blob.upload_from_file(buffer, content_type="application/octet-stream")

        return f"gs://{bucket_name}/{blob_path}"
    else:
        # Save locally
        local_path = Path(output_path) / shard_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            local_path,
            obs=obs,
            actions=actions,
            rewards=rewards,
            continues=continues,
        )
        return str(local_path)


def worker_fn(args: tuple[int, GenerationConfig, str]) -> str:
    """Worker function for multiprocessing."""
    shard_idx, config, output_path = args
    try:
        result = generate_shard(shard_idx, config, output_path)
        if shard_idx % 50 == 0:
            logger.info(f"Generated shard {shard_idx}")
        return result
    except Exception as e:
        logger.error(f"Failed to generate shard {shard_idx}: {e}")
        raise


def generate_all_shards(config: GenerationConfig) -> list[str]:
    """Generate all shards in parallel.

    Args:
        config: Generation configuration

    Returns:
        List of paths to generated shards
    """
    logger.info(f"Generating {config.total_shards} shards to {config.output_path}")
    logger.info(f"  samples_per_shard: {config.samples_per_shard}")
    logger.info(f"  seq_len: {config.seq_len}")
    logger.info(f"  obs_dim: {config.obs_dim}")
    logger.info(f"  action_dim: {config.action_dim}")

    # Prepare arguments for workers
    args_list = [
        (shard_idx, config, config.output_path) for shard_idx in range(config.total_shards)
    ]

    # Generate in parallel
    with multiprocessing.Pool(config.num_workers) as pool:
        results = pool.map(worker_fn, args_list)

    logger.info(f"Generated {len(results)} shards")
    return results


def main():
    """CLI entry point for data generation."""
    parser = argparse.ArgumentParser(description="Generate training data shards")
    parser.add_argument(
        "--output",
        type=str,
        default="gs://kagami-training-data/shards",
        help="Output path (GCS or local)",
    )
    parser.add_argument(
        "--shards",
        type=int,
        default=1024,
        help="Number of shards to generate",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=256,
        help="Samples per shard (should match batch_size)",
    )
    parser.add_argument(
        "--seq-len",
        type=int,
        default=64,
        help="Sequence length",
    )
    parser.add_argument(
        "--obs-dim",
        type=int,
        default=64,
        help="Observation dimension",
    )
    parser.add_argument(
        "--action-dim",
        type=int,
        default=8,
        help="Action dimension",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel workers",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = GenerationConfig(
        output_path=args.output,
        total_shards=args.shards,
        samples_per_shard=args.samples,
        seq_len=args.seq_len,
        obs_dim=args.obs_dim,
        action_dim=args.action_dim,
        num_workers=args.workers,
        seed=args.seed,
    )

    generate_all_shards(config)


if __name__ == "__main__":
    main()


__all__ = [
    "GenerationConfig",
    "generate_all_shards",
    "generate_shard",
]
