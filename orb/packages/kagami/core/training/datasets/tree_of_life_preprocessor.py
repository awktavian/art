"""TreeOfLife Hierarchical Dataset Preprocessor for TPU Training.

Converts NCBI taxonomy trees to RSSM-compatible format for hyperbolic
geometry learning. Uses Poincare disk embeddings for hierarchical structure.

Usage:
    python -m kagami.core.training.datasets.tree_of_life_preprocessor \
        --input-dir data/tree_of_life \
        --output-dir gs://kagami-training-data/tree_of_life/v1 \
        --num-shards 50

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


# Taxonomic ranks for encoding
TAXONOMIC_RANKS = [
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
]
RANK_TO_IDX = {r: i for i, r in enumerate(TAXONOMIC_RANKS)}


@dataclass
class TreeOfLifeConfig:
    """Configuration for TreeOfLife preprocessing."""

    # Input/output
    input_dir: str = "data/tree_of_life"
    output_dir: str = "gs://kagami-training-data/tree_of_life/v1"
    num_shards: int = 50

    # Sequence settings
    seq_len: int = 32
    obs_dim: int = 64
    action_dim: int = 8

    # Tree settings
    max_nodes: int = 100  # Max nodes per subtree
    max_depth: int = 10  # Max tree depth

    # Poincare embedding
    poincare_dim: int = 8  # Dimension of Poincare disk embedding

    # Random seed
    seed: int = 42


class TreeOfLifePreprocessor:
    """Preprocess TreeOfLife taxonomy for TPU training.

    Converts hierarchical taxonomy trees to sequences for RSSM training:
    - Node depths and parent relationships
    - Poincare disk embeddings (hyperbolic geometry)
    - Tree traversal sequences
    """

    def __init__(self, config: TreeOfLifeConfig | None = None):
        """Initialize preprocessor."""
        self.config = config or TreeOfLifeConfig()
        self._trees: list[dict[str, Any]] = []

    def load_tree_of_life(self) -> int:
        """Load TreeOfLife/NCBI taxonomy data.

        Returns:
            Number of subtrees loaded.
        """
        cfg = self.config
        input_path = Path(cfg.input_dir)

        # Try different loading methods
        if self._try_load_ncbi(input_path):
            pass
        elif self._try_load_newick(input_path):
            pass
        else:
            # Generate synthetic trees
            logger.warning("TreeOfLife data not found, generating synthetic trees")
            self._generate_synthetic_trees()

        logger.info(f"Loaded {len(self._trees)} subtrees")
        return len(self._trees)

    def _try_load_ncbi(self, input_path: Path) -> bool:
        """Try loading NCBI taxonomy files (nodes.dmp, names.dmp)."""
        nodes_file = input_path / "nodes.dmp"
        names_file = input_path / "names.dmp"

        if not nodes_file.exists() or not names_file.exists():
            return False

        try:
            # Parse nodes.dmp
            nodes = {}
            with open(nodes_file) as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) < 3:
                        continue
                    tax_id = int(parts[0].strip())
                    parent_id = int(parts[1].strip())
                    rank = parts[2].strip().lower()
                    nodes[tax_id] = {"parent": parent_id, "rank": rank}

            # Build subtrees
            rng = np.random.default_rng(self.config.seed)
            root_ids = [tid for tid, data in nodes.items() if data["parent"] == tid]

            for root_id in root_ids[:100]:  # Limit for manageable size
                subtree = self._extract_subtree(nodes, root_id)
                if subtree is not None:
                    self._trees.append(subtree)

            return len(self._trees) > 0
        except Exception as e:
            logger.debug(f"Failed to load NCBI: {e}")
            return False

    def _extract_subtree(
        self,
        nodes: dict[int, dict],
        root_id: int,
        max_nodes: int | None = None,
    ) -> dict[str, Any] | None:
        """Extract a subtree rooted at given node."""
        if max_nodes is None:
            max_nodes = self.config.max_nodes

        # BFS to collect nodes
        queue = [root_id]
        collected = []
        parent_map = {}

        while queue and len(collected) < max_nodes:
            node_id = queue.pop(0)
            if node_id not in nodes:
                continue

            collected.append(node_id)
            parent_id = nodes[node_id]["parent"]
            parent_map[node_id] = parent_id

            # Find children
            for child_id, data in nodes.items():
                if data["parent"] == node_id and child_id != node_id:
                    queue.append(child_id)

        if len(collected) < 5:
            return None

        # Reindex nodes
        id_to_idx = {nid: i for i, nid in enumerate(collected)}
        num_nodes = len(collected)

        depths = np.zeros(num_nodes, dtype=np.int32)
        parent_indices = np.full(num_nodes, -1, dtype=np.int32)
        ranks = np.zeros(num_nodes, dtype=np.int32)

        for idx, node_id in enumerate(collected):
            # Compute depth
            depth = 0
            current = node_id
            while current in parent_map and parent_map[current] != current:
                depth += 1
                current = parent_map[current]
                if depth > self.config.max_depth:
                    break
            depths[idx] = min(depth, self.config.max_depth)

            # Parent index
            parent_id = parent_map.get(node_id, node_id)
            if parent_id in id_to_idx:
                parent_indices[idx] = id_to_idx[parent_id]

            # Rank
            rank = nodes.get(node_id, {}).get("rank", "unknown")
            ranks[idx] = RANK_TO_IDX.get(rank, 7)

        return {
            "depths": depths,
            "parent_indices": parent_indices,
            "ranks": ranks,
            "num_nodes": num_nodes,
        }

    def _try_load_newick(self, input_path: Path) -> bool:
        """Try loading Newick format tree files."""
        newick_files = list(input_path.glob("*.nwk")) + list(input_path.glob("*.newick"))
        if not newick_files:
            return False

        # Would need newick parser - skip for now
        return False

    def _generate_synthetic_trees(self) -> None:
        """Generate synthetic hierarchical trees."""
        rng = np.random.default_rng(self.config.seed)
        cfg = self.config

        for _ in range(1000):
            num_nodes = rng.integers(10, cfg.max_nodes)

            depths = np.zeros(num_nodes, dtype=np.int32)
            parent_indices = np.full(num_nodes, -1, dtype=np.int32)
            ranks = np.zeros(num_nodes, dtype=np.int32)

            # Build tree structure
            depths[0] = 0
            parent_indices[0] = -1
            ranks[0] = 0  # Kingdom

            for i in range(1, num_nodes):
                # Pick a random parent from existing nodes
                max_parent = min(i, num_nodes - 1)
                parent_idx = rng.integers(0, max_parent)

                parent_indices[i] = parent_idx
                depths[i] = depths[parent_idx] + 1
                ranks[i] = min(depths[i], len(TAXONOMIC_RANKS) - 1)

            self._trees.append(
                {
                    "depths": depths,
                    "parent_indices": parent_indices,
                    "ranks": ranks,
                    "num_nodes": num_nodes,
                }
            )

    def _poincare_embed(
        self,
        depths: np.ndarray,
        parent_indices: np.ndarray,
        dim: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Embed tree nodes in Poincare disk.

        Uses depth-based radial embedding with angular variation for siblings.
        """
        num_nodes = len(depths)
        embeddings = np.zeros((num_nodes, dim), dtype=np.float32)

        max_depth = depths.max() + 1

        for i in range(num_nodes):
            # Radial coordinate based on depth (closer to center = higher in tree)
            # Use tanh to map to (-1, 1) for Poincare disk
            r = np.tanh(depths[i] / max_depth * 2)

            # Angular coordinates (random within hemisphere for each subtree)
            parent = parent_indices[i]
            if parent >= 0 and parent < num_nodes:
                # Inherit parent angle with small variation
                parent_angle = np.arctan2(embeddings[parent, 1], embeddings[parent, 0] + 1e-8)
                angle = parent_angle + rng.uniform(-0.3, 0.3)
            else:
                angle = rng.uniform(0, 2 * np.pi)

            # 2D Poincare coordinates
            embeddings[i, 0] = r * np.cos(angle)
            embeddings[i, 1] = r * np.sin(angle)

            # Fill remaining dimensions with depth-scaled random
            if dim > 2:
                embeddings[i, 2:] = rng.uniform(-1, 1, size=dim - 2) * (1 - r) * 0.1

        return embeddings

    def _tree_to_sequence(
        self,
        tree: dict[str, Any],
        rng: np.random.Generator,
    ) -> dict[str, np.ndarray]:
        """Convert tree to RSSM-compatible sequence.

        Traversal creates a sequence where each step is a node,
        and actions represent tree navigation (parent/child relationships).
        """
        cfg = self.config
        T = cfg.seq_len
        D = cfg.obs_dim
        A = cfg.action_dim

        obs = np.zeros((T, D), dtype=np.float32)
        actions = np.zeros((T, A), dtype=np.float32)
        rewards = np.zeros((T,), dtype=np.float32)
        continues = np.ones((T,), dtype=np.float32)

        depths = tree["depths"]
        parent_indices = tree["parent_indices"]
        ranks = tree["ranks"]
        num_nodes = min(tree["num_nodes"], T)

        # Compute Poincare embeddings
        poincare = self._poincare_embed(depths, parent_indices, cfg.poincare_dim, rng)

        # DFS traversal order
        traversal = self._dfs_traversal(parent_indices, num_nodes)

        for t in range(T):
            if t < len(traversal):
                node_idx = traversal[t]

                # Poincare embedding (hyperbolic coordinates)
                obs[t, : cfg.poincare_dim] = poincare[node_idx]

                # Depth (normalized)
                obs[t, cfg.poincare_dim] = depths[node_idx] / cfg.max_depth

                # Rank one-hot
                rank = ranks[node_idx]
                if rank < len(TAXONOMIC_RANKS):
                    obs[t, cfg.poincare_dim + 1 + rank] = 1.0

                # Parent embedding (for relational learning)
                parent = parent_indices[node_idx]
                if 0 <= parent < num_nodes:
                    obs[t, 20 : 20 + cfg.poincare_dim] = poincare[parent]

                # Action: direction to next node in traversal
                if t + 1 < len(traversal):
                    next_idx = traversal[t + 1]
                    actions[t, : cfg.poincare_dim] = poincare[next_idx] - poincare[node_idx]

                # Reward for reaching deep nodes
                rewards[t] = depths[node_idx] / cfg.max_depth * 0.1
            else:
                continues[t] = 0.0

        # Symlog transform
        obs = np.sign(obs) * np.log1p(np.abs(obs))

        return {
            "obs": obs,
            "actions": actions,
            "rewards": rewards,
            "continues": continues,
        }

    def _dfs_traversal(self, parent_indices: np.ndarray, num_nodes: int) -> list[int]:
        """Generate DFS traversal order of tree."""
        # Build children lists
        children: dict[int, list[int]] = {i: [] for i in range(num_nodes)}
        root = 0

        for i, parent in enumerate(parent_indices):
            if 0 <= parent < num_nodes and parent != i:
                children[parent].append(i)
            elif parent == -1 or parent == i:
                root = i

        # DFS
        traversal = []
        stack = [root]

        while stack:
            node = stack.pop()
            if node < num_nodes:
                traversal.append(node)
                # Add children in reverse order for correct DFS
                stack.extend(reversed(children.get(node, [])))

        return traversal

    def generate_shard(self, shard_id: int) -> dict[str, np.ndarray]:
        """Generate a single shard."""
        cfg = self.config
        num_trees = len(self._trees)
        trees_per_shard = num_trees // cfg.num_shards

        start_idx = shard_id * trees_per_shard
        end_idx = min(start_idx + trees_per_shard, num_trees)

        N = end_idx - start_idx
        T = cfg.seq_len

        rng = np.random.default_rng(cfg.seed + shard_id)

        all_obs = np.zeros((N, T, cfg.obs_dim), dtype=np.float32)
        all_actions = np.zeros((N, T, cfg.action_dim), dtype=np.float32)
        all_rewards = np.zeros((N, T), dtype=np.float32)
        all_continues = np.ones((N, T), dtype=np.float32)

        for i, tree_idx in enumerate(range(start_idx, end_idx)):
            tree = self._trees[tree_idx]
            seq = self._tree_to_sequence(tree, rng)

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
        filename = f"tree_of_life-{shard_id:05d}-of-{cfg.num_shards:05d}.npz"

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
        """Run full preprocessing pipeline."""
        self.load_tree_of_life()

        if not self._trees:
            logger.error("No trees loaded")
            return []

        paths = []
        for shard_id in range(self.config.num_shards):
            logger.info(f"Processing shard {shard_id}/{self.config.num_shards}...")
            data = self.generate_shard(shard_id)
            path = self.save_shard(shard_id, data)
            paths.append(path)

        return paths


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Preprocess TreeOfLife for TPU training")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/tree_of_life",
        help="Input directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="gs://kagami-training-data/tree_of_life/v1",
        help="Output directory",
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        default=50,
        help="Number of shards",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config = TreeOfLifeConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        num_shards=args.num_shards,
        seed=args.seed,
    )

    preprocessor = TreeOfLifePreprocessor(config)
    preprocessor.preprocess()


if __name__ == "__main__":
    main()
