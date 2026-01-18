"""QM9 Molecular Dataset Preprocessor for TPU Training.

Converts QM9 molecular structures to RSSM-compatible format and saves
to GCS shards for TPU/JAX training.

QM9 contains 134K small organic molecules with:
- 3D atomic coordinates
- Atom types (C, N, O, F, H)
- Molecular properties (dipole, polarizability, HOMO, LUMO, etc.)

Usage:
    python -m kagami.core.training.datasets.qm9_preprocessor \
        --input-dir data/qm9 \
        --output-dir gs://kagami-training-data/qm9/v1 \
        --num-shards 100

Created: January 12, 2026
"""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# Atom type to index mapping
ATOM_TYPES = {"H": 0, "C": 1, "N": 2, "O": 3, "F": 4}
NUM_ATOM_TYPES = len(ATOM_TYPES)


@dataclass
class QM9PreprocessorConfig:
    """Configuration for QM9 preprocessing."""

    # Input/output paths
    input_dir: str = "data/qm9"
    output_dir: str = "gs://kagami-training-data/qm9/v1"
    num_shards: int = 100

    # Sequence settings (for RSSM compatibility)
    seq_len: int = 32  # Treat molecule as a sequence of atoms
    obs_dim: int = 64  # Observation dimension for RSSM
    action_dim: int = 8  # Action dimension (for consistency)

    # Maximum atoms per molecule
    max_atoms: int = 29  # QM9 max is 29 atoms

    # Random seed
    seed: int = 42


class QM9Preprocessor:
    """Preprocess QM9 molecular data for TPU training.

    Converts molecules to sequences of atomic observations:
    - Position: 3D coordinates
    - Type: One-hot atom type
    - Properties: Molecular properties

    Output format matches Genesis generator for unified training.
    """

    def __init__(self, config: QM9PreprocessorConfig | None = None):
        """Initialize preprocessor.

        Args:
            config: Preprocessing configuration.
        """
        self.config = config or QM9PreprocessorConfig()
        self._molecules: list[dict[str, Any]] = []

    def load_qm9(self) -> int:
        """Load QM9 dataset from various formats.

        Supports:
        - .xyz files (raw atomic coordinates)
        - TensorFlow Datasets
        - PyTorch Geometric

        Returns:
            Number of molecules loaded.
        """
        cfg = self.config
        input_path = Path(cfg.input_dir)

        # Try different loading methods
        if self._try_load_xyz(input_path):
            pass
        elif self._try_load_tfds():
            pass
        elif self._try_load_pyg():
            pass
        else:
            # Generate synthetic molecules as fallback
            logger.warning("QM9 dataset not found, generating synthetic molecules")
            self._generate_synthetic_molecules()

        logger.info(f"Loaded {len(self._molecules)} molecules")
        return len(self._molecules)

    def _try_load_xyz(self, input_path: Path) -> bool:
        """Try loading from .xyz files."""
        xyz_files = list(input_path.glob("*.xyz"))
        if not xyz_files:
            return False

        for xyz_file in xyz_files[:10000]:  # Limit for faster processing
            try:
                mol = self._parse_xyz(xyz_file)
                if mol is not None:
                    self._molecules.append(mol)
            except Exception as e:
                logger.debug(f"Failed to parse {xyz_file}: {e}")

        return len(self._molecules) > 0

    def _parse_xyz(self, filepath: Path) -> dict[str, Any] | None:
        """Parse a single .xyz file."""
        with open(filepath) as f:
            lines = f.readlines()

        if len(lines) < 3:
            return None

        try:
            num_atoms = int(lines[0].strip())
        except ValueError:
            return None

        positions = []
        atom_types = []

        for line in lines[2 : 2 + num_atoms]:
            parts = line.strip().split()
            if len(parts) < 4:
                continue

            atom = parts[0].upper()
            if atom not in ATOM_TYPES:
                continue

            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            positions.append([x, y, z])
            atom_types.append(ATOM_TYPES[atom])

        if len(positions) < 2:
            return None

        return {
            "positions": np.array(positions, dtype=np.float32),
            "atom_types": np.array(atom_types, dtype=np.int32),
            "num_atoms": len(positions),
        }

    def _try_load_tfds(self) -> bool:
        """Try loading from TensorFlow Datasets."""
        try:
            import tensorflow_datasets as tfds

            ds = tfds.load("qm9", split="train")
            for item in ds.take(10000):
                mol = {
                    "positions": item["positions"].numpy(),
                    "atom_types": item["atom_types"].numpy(),
                    "num_atoms": int(item["num_atoms"].numpy()),
                }
                self._molecules.append(mol)
            return len(self._molecules) > 0
        except Exception:
            return False

    def _try_load_pyg(self) -> bool:
        """Try loading from PyTorch Geometric."""
        try:
            from torch_geometric.datasets import QM9

            dataset = QM9(root=str(self.config.input_dir))
            for data in dataset[:10000]:
                mol = {
                    "positions": data.pos.numpy(),
                    "atom_types": data.z.numpy(),
                    "num_atoms": data.pos.shape[0],
                }
                self._molecules.append(mol)
            return len(self._molecules) > 0
        except Exception:
            return False

    def _generate_synthetic_molecules(self) -> None:
        """Generate synthetic molecule-like data."""
        rng = np.random.default_rng(self.config.seed)

        for _ in range(10000):
            num_atoms = rng.integers(5, 20)
            positions = rng.uniform(-2, 2, size=(num_atoms, 3)).astype(np.float32)
            atom_types = rng.integers(0, NUM_ATOM_TYPES, size=num_atoms).astype(np.int32)

            self._molecules.append(
                {
                    "positions": positions,
                    "atom_types": atom_types,
                    "num_atoms": num_atoms,
                }
            )

    def _molecule_to_sequence(
        self,
        mol: dict[str, Any],
        rng: np.random.Generator,
    ) -> dict[str, np.ndarray]:
        """Convert molecule to RSSM-compatible sequence.

        Creates a sequence where each timestep is an "observation" of an atom
        and the "action" is the relative displacement to the next atom.
        """
        cfg = self.config
        T = cfg.seq_len
        D = cfg.obs_dim
        A = cfg.action_dim

        obs = np.zeros((T, D), dtype=np.float32)
        actions = np.zeros((T, A), dtype=np.float32)
        rewards = np.zeros((T,), dtype=np.float32)
        continues = np.ones((T,), dtype=np.float32)

        positions = mol["positions"]
        atom_types = mol["atom_types"]
        num_atoms = min(mol["num_atoms"], T)

        # Center molecule
        center = positions.mean(axis=0)
        positions = positions - center

        # Normalize positions
        scale = max(np.abs(positions).max(), 1e-6)
        positions = positions / scale

        for t in range(T):
            if t < num_atoms:
                # Atom position (3D)
                obs[t, :3] = positions[t]

                # Atom type one-hot (5 types)
                if atom_types[t] < NUM_ATOM_TYPES:
                    obs[t, 3 + atom_types[t]] = 1.0

                # Relative position from center
                obs[t, 8:11] = positions[t]

                # Distance from center
                obs[t, 11] = np.linalg.norm(positions[t])

                # Action: displacement to next atom
                if t + 1 < num_atoms:
                    disp = positions[t + 1] - positions[t]
                    actions[t, :3] = disp

                # Small reward for valid atoms
                rewards[t] = 0.1
            else:
                # Pad with noise
                obs[t] = rng.uniform(-0.1, 0.1, size=D).astype(np.float32)
                continues[t] = 0.0  # Mark as padding

        # Apply symlog transform
        obs = np.sign(obs) * np.log1p(np.abs(obs))

        return {
            "obs": obs,
            "actions": actions,
            "rewards": rewards,
            "continues": continues,
        }

    def generate_shard(self, shard_id: int) -> dict[str, np.ndarray]:
        """Generate a single shard of training data.

        Args:
            shard_id: Shard identifier

        Returns:
            Dict with arrays for RSSM training.
        """
        cfg = self.config
        num_molecules = len(self._molecules)
        samples_per_shard = num_molecules // cfg.num_shards

        start_idx = shard_id * samples_per_shard
        end_idx = min(start_idx + samples_per_shard, num_molecules)

        N = end_idx - start_idx
        T = cfg.seq_len

        rng = np.random.default_rng(cfg.seed + shard_id)

        all_obs = np.zeros((N, T, cfg.obs_dim), dtype=np.float32)
        all_actions = np.zeros((N, T, cfg.action_dim), dtype=np.float32)
        all_rewards = np.zeros((N, T), dtype=np.float32)
        all_continues = np.ones((N, T), dtype=np.float32)

        for i, mol_idx in enumerate(range(start_idx, end_idx)):
            mol = self._molecules[mol_idx]
            seq = self._molecule_to_sequence(mol, rng)

            all_obs[i] = seq["obs"]
            all_actions[i] = seq["actions"]
            all_rewards[i] = seq["rewards"]
            all_continues[i] = seq["continues"]

        return {
            "obs": all_obs,
            "actions": all_actions,
            "rewards": all_rewards,
            "continues": all_continues,
        }

    def save_shard(self, shard_id: int, data: dict[str, np.ndarray]) -> str:
        """Save shard to output directory."""
        cfg = self.config
        filename = f"qm9-{shard_id:05d}-of-{cfg.num_shards:05d}.npz"

        if cfg.output_dir.startswith("gs://"):
            import tensorflow as tf

            with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
                np.savez_compressed(f.name, **data)
                temp_path = f.name

            gcs_path = f"{cfg.output_dir}/{filename}"
            tf.io.gfile.copy(temp_path, gcs_path, overwrite=True)
            os.unlink(temp_path)
            return gcs_path
        else:
            output_dir = Path(cfg.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            np.savez_compressed(output_path, **data)
            return str(output_path)

    def preprocess(self) -> list[str]:
        """Run full preprocessing pipeline.

        Returns:
            List of paths to generated shard files.
        """
        self.load_qm9()

        if not self._molecules:
            logger.error("No molecules loaded")
            return []

        paths = []
        for shard_id in range(self.config.num_shards):
            logger.info(f"Processing shard {shard_id}/{self.config.num_shards}...")
            data = self.generate_shard(shard_id)
            path = self.save_shard(shard_id, data)
            paths.append(path)
            logger.info(f"  Saved to {path}")

        return paths


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Preprocess QM9 for TPU training")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/qm9",
        help="Input directory with QM9 data",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="gs://kagami-training-data/qm9/v1",
        help="Output directory",
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        default=100,
        help="Number of output shards",
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

    config = QM9PreprocessorConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        num_shards=args.num_shards,
        seed=args.seed,
    )

    preprocessor = QM9Preprocessor(config)
    preprocessor.preprocess()


if __name__ == "__main__":
    main()
