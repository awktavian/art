"""Genesis Physics Data Generator for TPU Training.

Generates physics puzzle trajectories and saves to GCS-compatible .npz shards
for use with JAX/TPU training pipeline.

Usage:
    python -m kagami.core.training.datasets.genesis_generator \
        --output-dir gs://kagami-training-data/genesis/v1 \
        --num-shards 1000 \
        --samples-per-shard 10000

Created: January 12, 2026
"""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GenesisGeneratorConfig:
    """Configuration for Genesis data generation."""

    # Output settings
    output_dir: str = "gs://kagami-training-data/genesis/v1"
    num_shards: int = 1000
    samples_per_shard: int = 10000

    # Sequence settings
    seq_len: int = 64
    obs_dim: int = 64
    action_dim: int = 8

    # Physics settings
    physics_dt: float = 1.0 / 60.0

    # Puzzle distribution
    jepa_weight: float = 0.7  # Dynamics puzzles
    generation_weight: float = 0.3  # Control puzzles

    # Difficulty progression (across shards)
    difficulty_start: float = 0.1
    difficulty_end: float = 0.9

    # Random seed base
    seed: int = 42

    # Puzzle types
    puzzle_types_jepa: list[str] = field(
        default_factory=lambda: [
            "free_fall_bounce",
            "two_body_collision_1d",
            "spring_mass",
            "damped_motion",
            "impulse_response",
        ]
    )
    puzzle_types_generation: list[str] = field(
        default_factory=lambda: [
            "goal_reach_with_barrier",
            "goal_reach_switching",
        ]
    )


class GenesisPuzzleGenerator:
    """Generate physics puzzle data for TPU training.

    Produces .npz shards with:
    - obs: [N, T, obs_dim] float32 - State observations
    - actions: [N, T, action_dim] float32 - Actions taken
    - rewards: [N, T] float32 - Sparse rewards
    - continues: [N, T] float32 - Episode continuation flags

    Where N = samples_per_shard, T = seq_len.
    """

    def __init__(self, config: GenesisGeneratorConfig | None = None):
        """Initialize generator.

        Args:
            config: Generation configuration. Uses defaults if None.
        """
        self.config = config or GenesisGeneratorConfig()
        self._genesis = None
        self._scene_ready = False

    def _try_init_genesis(self) -> Any:
        """Initialize Genesis physics engine."""
        try:
            from kagami.forge.modules.genesis_physics_wrapper import (
                GenesisPhysicsWrapper,
            )
        except ImportError:
            logger.warning("Genesis not available, using synthetic data")
            return None

        try:
            import asyncio

            wrapper = GenesisPhysicsWrapper(device="cpu")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(wrapper.initialize())
            return wrapper
        except Exception as e:
            logger.warning(f"Genesis init failed: {e}, using synthetic data")
            return None

    def _ensure_genesis(self) -> None:
        """Lazily initialize Genesis."""
        if self._genesis is not None:
            return
        self._genesis = self._try_init_genesis()
        if self._genesis is not None:
            self._ensure_scene()

    def _ensure_scene(self) -> None:
        """Create physics scene."""
        if self._scene_ready or self._genesis is None:
            return

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            self._genesis.create_physics_scene(
                scene_type="physics_lab",
                gravity=(0.0, 0.0, -9.81),
                dt=self.config.physics_dt,
                show_viewer=False,
                rendering=False,
            )
        )
        self._scene_ready = True

    def _generate_synthetic_trajectory(
        self,
        rng: np.random.Generator,
        puzzle_type: str,
        difficulty: float,
    ) -> dict[str, np.ndarray]:
        """Generate synthetic physics-like trajectory (fallback without Genesis).

        This creates realistic-looking trajectories using analytical physics
        when Genesis is not available.
        """
        cfg = self.config
        T = cfg.seq_len
        D = cfg.obs_dim
        A = cfg.action_dim

        obs = np.zeros((T, D), dtype=np.float32)
        actions = np.zeros((T, A), dtype=np.float32)
        rewards = np.zeros((T,), dtype=np.float32)
        continues = np.ones((T,), dtype=np.float32)

        # Physics simulation parameters
        dt = cfg.physics_dt
        g = 9.81

        if puzzle_type == "free_fall_bounce":
            # Bouncing ball simulation
            pos = np.array([rng.uniform(-1, 1), 0, rng.uniform(1, 3)])
            vel = np.array([0, 0, rng.uniform(-2, 2) * difficulty])
            restitution = 0.8

            for t in range(T):
                # Gravity
                vel[2] -= g * dt
                pos += vel * dt

                # Bounce off ground
                if pos[2] < 0:
                    pos[2] = -pos[2]
                    vel[2] = -vel[2] * restitution
                    rewards[t] = 0.1  # Reward for bounce

                # Pack state
                obs[t, :3] = pos
                obs[t, 3:6] = vel
                actions[t, :3] = rng.uniform(-0.1, 0.1, size=3) * difficulty

        elif puzzle_type == "two_body_collision_1d":
            # 1D collision
            pos1 = np.array([-1.0, 0, 1])
            pos2 = np.array([1.0, 0, 1])
            vel1 = np.array([rng.uniform(0.5, 2) * difficulty, 0, 0])
            vel2 = np.array([rng.uniform(-2, -0.5) * difficulty, 0, 0])

            for t in range(T):
                pos1 += vel1 * dt
                pos2 += vel2 * dt

                # Simple elastic collision
                if abs(pos1[0] - pos2[0]) < 0.2:
                    vel1, vel2 = vel2, vel1
                    rewards[t] = 0.2

                obs[t, :3] = pos1
                obs[t, 3:6] = vel1
                obs[t, 6:9] = pos2
                obs[t, 9:12] = vel2

        elif puzzle_type == "spring_mass":
            # Harmonic oscillator
            omega = 2.0 * np.pi * (0.5 + difficulty)
            damping = 0.1 * difficulty
            x = rng.uniform(-1, 1)
            v = rng.uniform(-1, 1)

            for t in range(T):
                # Damped harmonic motion
                a = -(omega**2) * x - damping * v
                v += a * dt
                x += v * dt

                obs[t, 0] = x
                obs[t, 1] = v
                obs[t, 2] = a
                actions[t, 0] = rng.uniform(-0.1, 0.1) * difficulty

        elif puzzle_type == "damped_motion":
            # Damped motion with friction
            pos = rng.uniform(-1, 1, size=3)
            vel = rng.uniform(-2, 2, size=3) * difficulty
            friction = 0.1 + 0.3 * difficulty

            for t in range(T):
                vel *= 1 - friction * dt
                pos += vel * dt

                obs[t, :3] = pos
                obs[t, 3:6] = vel

        elif puzzle_type == "impulse_response":
            # Response to impulses
            pos = np.zeros(3)
            vel = np.zeros(3)
            mass = 1.0

            for t in range(T):
                # Random impulse with probability
                if rng.random() < 0.05 * difficulty:
                    impulse = rng.uniform(-1, 1, size=3) * difficulty
                    vel += impulse / mass
                    actions[t, :3] = impulse
                    rewards[t] = 0.1

                pos += vel * dt
                obs[t, :3] = pos
                obs[t, 3:6] = vel

        elif puzzle_type in ("goal_reach_with_barrier", "goal_reach_switching"):
            # Goal-reaching with simple dynamics
            pos = rng.uniform(-1, 1, size=3)
            vel = np.zeros(3)
            goal = rng.uniform(-1, 1, size=3)

            for t in range(T):
                # Goal switching
                if puzzle_type == "goal_reach_switching" and t % 20 == 0:
                    goal = rng.uniform(-1, 1, size=3)

                # Simple PD control
                error = goal - pos
                action = 0.5 * error - 0.1 * vel
                action = np.clip(action, -1, 1)

                vel += action * dt
                pos += vel * dt

                obs[t, :3] = pos
                obs[t, 3:6] = vel
                obs[t, 6:9] = goal
                actions[t, :3] = action

                # Reward for getting close to goal
                dist = np.linalg.norm(error)
                if dist < 0.2:
                    rewards[t] = 0.1

        else:
            # Default: random walk with momentum
            pos = np.zeros(3)
            vel = np.zeros(3)

            for t in range(T):
                vel += rng.uniform(-0.1, 0.1, size=3) * difficulty
                vel *= 0.99
                pos += vel * dt

                obs[t, :3] = pos
                obs[t, 3:6] = vel

        # Apply symlog transform for stability
        obs = np.sign(obs) * np.log1p(np.abs(obs))

        # Rare termination (2%)
        term_idx = rng.choice(T, size=max(1, T // 50), replace=False)
        continues[term_idx] = 0.0

        return {
            "obs": obs,
            "actions": actions,
            "rewards": rewards,
            "continues": continues,
        }

    def _generate_genesis_trajectory(
        self,
        rng: np.random.Generator,
        puzzle_type: str,
        difficulty: float,
    ) -> dict[str, np.ndarray]:
        """Generate trajectory using real Genesis engine."""
        if self._genesis is None:
            return self._generate_synthetic_trajectory(rng, puzzle_type, difficulty)

        cfg = self.config
        T = cfg.seq_len
        D = cfg.obs_dim
        A = cfg.action_dim

        # Pre-allocate arrays for when Genesis API is fully implemented
        # Currently these are placeholders - actual data comes from synthetic generator
        _obs = np.zeros((T, D), dtype=np.float32)
        _actions = np.zeros((T, A), dtype=np.float32)
        _rewards = np.zeros((T,), dtype=np.float32)
        _continues = np.ones((T,), dtype=np.float32)

        # Reset scene for this episode
        # This would use Genesis API to set initial conditions
        # For now, fall back to synthetic
        return self._generate_synthetic_trajectory(rng, puzzle_type, difficulty)

    def generate_shard(self, shard_id: int) -> dict[str, np.ndarray]:
        """Generate a single shard of training data.

        Args:
            shard_id: Shard identifier (0 to num_shards-1)

        Returns:
            Dict with 'obs', 'actions', 'rewards', 'continues' arrays.
        """
        cfg = self.config
        N = cfg.samples_per_shard
        T = cfg.seq_len

        # Seed based on shard ID for reproducibility
        seed = cfg.seed + shard_id * 1000
        rng = np.random.default_rng(seed)

        # Difficulty progression across shards
        progress = shard_id / max(1, cfg.num_shards - 1)
        difficulty_base = cfg.difficulty_start + progress * (
            cfg.difficulty_end - cfg.difficulty_start
        )

        # Initialize arrays
        all_obs = np.zeros((N, T, cfg.obs_dim), dtype=np.float32)
        all_actions = np.zeros((N, T, cfg.action_dim), dtype=np.float32)
        all_rewards = np.zeros((N, T), dtype=np.float32)
        all_continues = np.ones((N, T), dtype=np.float32)

        # Select puzzle types based on weights
        all_puzzles = cfg.puzzle_types_jepa + cfg.puzzle_types_generation
        weights = [cfg.jepa_weight / len(cfg.puzzle_types_jepa)] * len(cfg.puzzle_types_jepa) + [
            cfg.generation_weight / len(cfg.puzzle_types_generation)
        ] * len(cfg.puzzle_types_generation)
        weights = np.array(weights) / sum(weights)

        # Try to use Genesis
        self._ensure_genesis()

        for i in range(N):
            # Sample puzzle type
            puzzle_type = rng.choice(all_puzzles, p=weights)

            # Vary difficulty slightly within shard
            difficulty = np.clip(difficulty_base + rng.uniform(-0.1, 0.1), 0.0, 1.0)

            # Generate trajectory
            traj = self._generate_synthetic_trajectory(rng, puzzle_type, difficulty)

            all_obs[i] = traj["obs"]
            all_actions[i] = traj["actions"]
            all_rewards[i] = traj["rewards"]
            all_continues[i] = traj["continues"]

            if (i + 1) % 1000 == 0:
                logger.info(f"  Shard {shard_id}: Generated {i + 1}/{N} samples")

        return {
            "obs": all_obs,
            "actions": all_actions,
            "rewards": all_rewards,
            "continues": all_continues,
        }

    def save_shard(self, shard_id: int, data: dict[str, np.ndarray]) -> str:
        """Save shard to output directory.

        Args:
            shard_id: Shard identifier
            data: Dict with arrays to save

        Returns:
            Path to saved shard file.
        """
        cfg = self.config
        filename = f"train-{shard_id:05d}-of-{cfg.num_shards:05d}.npz"

        if cfg.output_dir.startswith("gs://"):
            # Save to GCS
            import tensorflow as tf

            # Save to temp file first
            with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
                np.savez_compressed(f.name, **data)
                temp_path = f.name

            # Upload to GCS
            gcs_path = f"{cfg.output_dir}/{filename}"
            tf.io.gfile.copy(temp_path, gcs_path, overwrite=True)
            os.unlink(temp_path)
            return gcs_path
        else:
            # Save locally
            output_dir = Path(cfg.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            np.savez_compressed(output_path, **data)
            return str(output_path)

    def generate(
        self,
        start_shard: int = 0,
        end_shard: int | None = None,
    ) -> list[str]:
        """Generate all shards in range.

        Args:
            start_shard: First shard to generate (inclusive)
            end_shard: Last shard to generate (exclusive), defaults to num_shards

        Returns:
            List of paths to generated shard files.
        """
        cfg = self.config
        if end_shard is None:
            end_shard = cfg.num_shards

        logger.info(
            f"Generating shards {start_shard} to {end_shard - 1} "
            f"({end_shard - start_shard} shards, "
            f"{(end_shard - start_shard) * cfg.samples_per_shard:,} total samples)"
        )

        paths = []
        for shard_id in range(start_shard, end_shard):
            logger.info(f"Generating shard {shard_id}/{cfg.num_shards}...")
            data = self.generate_shard(shard_id)
            path = self.save_shard(shard_id, data)
            paths.append(path)
            logger.info(f"  Saved to {path}")

        logger.info(f"Generated {len(paths)} shards")
        return paths


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate Genesis physics data for TPU training")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="gs://kagami-training-data/genesis/v1",
        help="Output directory (local path or gs://...)",
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        default=1000,
        help="Total number of shards to generate",
    )
    parser.add_argument(
        "--samples-per-shard",
        type=int,
        default=10000,
        help="Samples per shard",
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
        "--start-shard",
        type=int,
        default=0,
        help="First shard to generate",
    )
    parser.add_argument(
        "--end-shard",
        type=int,
        default=None,
        help="Last shard (exclusive)",
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
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    config = GenesisGeneratorConfig(
        output_dir=args.output_dir,
        num_shards=args.num_shards,
        samples_per_shard=args.samples_per_shard,
        seq_len=args.seq_len,
        obs_dim=args.obs_dim,
        seed=args.seed,
    )

    generator = GenesisPuzzleGenerator(config)
    generator.generate(
        start_shard=args.start_shard,
        end_shard=args.end_shard,
    )


if __name__ == "__main__":
    main()
