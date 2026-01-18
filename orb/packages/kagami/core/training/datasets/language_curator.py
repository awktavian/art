# pyright: reportGeneralTypeIssues=false
"""Language Data Curator for TPU Training.

Prepares instruction-following data for world model language grounding.
Tokenizes text and creates RSSM-compatible sequences for cross-attention.

Supports:
- Flan-T5 instruction dataset
- ShareGPT conversations
- OpenAssistant dialogues
- Custom instruction datasets

Usage:
    python -m kagami.core.training.datasets.language_curator \
        --output-dir gs://kagami-training-data/language/v1 \
        --num-shards 100 \
        --source flan

Created: January 12, 2026
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LanguageCuratorConfig:
    """Configuration for language data curation."""

    # Output settings
    output_dir: str = "gs://kagami-training-data/language/v1"
    num_shards: int = 100
    samples_per_shard: int = 5000

    # Sequence settings
    max_seq_len: int = 512  # Maximum token sequence length
    obs_dim: int = 64  # Observation dimension for RSSM compatibility
    action_dim: int = 8

    # Tokenizer settings (using simple byte-pair encoding placeholder)
    vocab_size: int = 32000
    pad_token_id: int = 0
    eos_token_id: int = 1
    bos_token_id: int = 2

    # Data source
    source: str = "flan"  # flan, sharegpt, openassistant, custom
    input_dir: str = "data/language"

    # Random seed
    seed: int = 42

    # Instruction templates
    instruction_templates: list[str] = field(
        default_factory=lambda: [
            "Explain {topic} in simple terms.",
            "What is the relationship between {topic_a} and {topic_b}?",
            "Describe the process of {process}.",
            "Compare and contrast {item_a} and {item_b}.",
            "What are the main steps to {action}?",
            "Summarize the key points about {topic}.",
            "How does {mechanism} work?",
            "What are the implications of {event}?",
            "Analyze the following: {text}",
            "Provide a detailed explanation of {concept}.",
        ]
    )


class LanguageDataCurator:
    """Curate language data for world model training.

    Creates sequences where:
    - obs: Token embeddings (placeholder as IDs)
    - actions: Next token predictions
    - rewards: Based on instruction completion
    - text_ids: Raw token IDs for cross-attention
    - text_mask: Attention mask
    """

    def __init__(self, config: LanguageCuratorConfig | None = None):
        """Initialize curator."""
        self.config = config or LanguageCuratorConfig()
        self._samples: list[dict[str, Any]] = []
        self._tokenizer = None

    def _init_tokenizer(self) -> None:
        """Initialize tokenizer (simple fallback if transformers unavailable)."""
        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-base", use_fast=True)
            logger.info("Using Flan-T5 tokenizer")
        except Exception:
            logger.warning("Transformers not available, using simple tokenizer")
            self._tokenizer = None

    def _simple_tokenize(self, text: str) -> list[int]:
        """Simple character-level tokenization fallback."""
        cfg = self.config
        tokens = [cfg.bos_token_id]

        for char in text[: cfg.max_seq_len - 2]:
            # Simple hash to vocab range
            token_id = (ord(char) % (cfg.vocab_size - 3)) + 3
            tokens.append(token_id)

        tokens.append(cfg.eos_token_id)

        # Pad to max length
        while len(tokens) < cfg.max_seq_len:
            tokens.append(cfg.pad_token_id)

        return tokens[: cfg.max_seq_len]

    def _tokenize(self, text: str) -> dict[str, np.ndarray]:
        """Tokenize text to model inputs."""
        cfg = self.config

        if self._tokenizer is not None:
            encoded = self._tokenizer(
                text,
                max_length=cfg.max_seq_len,
                padding="max_length",
                truncation=True,
                return_tensors="np",
            )
            return {
                "input_ids": encoded["input_ids"][0],
                "attention_mask": encoded["attention_mask"][0],
            }
        else:
            tokens = self._simple_tokenize(text)
            mask = [1 if t != cfg.pad_token_id else 0 for t in tokens]
            return {
                "input_ids": np.array(tokens, dtype=np.int32),
                "attention_mask": np.array(mask, dtype=np.int32),
            }

    def load_data(self) -> int:
        """Load language data from configured source."""
        cfg = self.config

        self._init_tokenizer()

        if cfg.source == "flan":
            self._load_flan()
        elif cfg.source == "sharegpt":
            self._load_sharegpt()
        elif cfg.source == "openassistant":
            self._load_openassistant()
        elif cfg.source == "custom":
            self._load_custom()
        else:
            # Generate synthetic
            logger.warning(f"Unknown source {cfg.source}, generating synthetic")
            self._generate_synthetic()

        if not self._samples:
            self._generate_synthetic()

        logger.info(f"Loaded {len(self._samples)} instruction samples")
        return len(self._samples)

    def _load_flan(self) -> None:
        """Load Flan instruction dataset."""
        try:
            from datasets import load_dataset

            ds = load_dataset("flan_v2", split="train[:10000]")
            for item in ds:
                self._samples.append(
                    {
                        "instruction": item.get("instruction", ""),
                        "input": item.get("input", ""),
                        "output": item.get("output", ""),
                    }
                )
        except Exception as e:
            logger.warning(f"Could not load Flan: {e}")

    def _load_sharegpt(self) -> None:
        """Load ShareGPT conversation dataset."""
        input_path = Path(self.config.input_dir) / "sharegpt.json"
        if not input_path.exists():
            return

        try:
            with open(input_path) as f:
                data = json.load(f)

            for conv in data[:10000]:
                messages = conv.get("conversations", [])
                for i in range(0, len(messages) - 1, 2):
                    if i + 1 < len(messages):
                        self._samples.append(
                            {
                                "instruction": messages[i].get("value", ""),
                                "input": "",
                                "output": messages[i + 1].get("value", ""),
                            }
                        )
        except Exception as e:
            logger.warning(f"Could not load ShareGPT: {e}")

    def _load_openassistant(self) -> None:
        """Load OpenAssistant dataset."""
        try:
            from datasets import load_dataset

            ds = load_dataset("OpenAssistant/oasst1", split="train[:10000]")
            for item in ds:
                if item.get("role") == "prompter":
                    self._samples.append(
                        {
                            "instruction": item.get("text", ""),
                            "input": "",
                            "output": "",  # Response would be next message
                        }
                    )
        except Exception as e:
            logger.warning(f"Could not load OpenAssistant: {e}")

    def _load_custom(self) -> None:
        """Load custom instruction dataset from JSON files."""
        input_path = Path(self.config.input_dir)
        json_files = list(input_path.glob("*.json"))

        for json_file in json_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)

                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            self._samples.append(
                                {
                                    "instruction": item.get("instruction", item.get("prompt", "")),
                                    "input": item.get("input", ""),
                                    "output": item.get("output", item.get("response", "")),
                                }
                            )
            except Exception as e:
                logger.warning(f"Could not load {json_file}: {e}")

    def _generate_synthetic(self) -> None:
        """Generate synthetic instruction data."""
        rng = np.random.default_rng(self.config.seed)
        cfg = self.config

        # Topic banks for generation
        topics = [
            "machine learning",
            "neural networks",
            "physics simulation",
            "smart home automation",
            "natural language processing",
            "computer vision",
            "reinforcement learning",
            "world models",
            "robotics",
            "autonomous systems",
            "sensor fusion",
            "motion planning",
            "control systems",
            "optimization",
            "probabilistic inference",
            "bayesian methods",
            "graph neural networks",
            "attention mechanisms",
            "transformers",
            "diffusion models",
        ]

        processes = [
            "training a neural network",
            "fine-tuning a language model",
            "deploying a robot",
            "optimizing hyperparameters",
            "collecting training data",
            "building a world model",
            "implementing safety constraints",
            "real-time inference",
            "distributed training",
            "model compression",
        ]

        for _ in range(10000):
            template = rng.choice(cfg.instruction_templates)

            # Fill in template
            instruction = template.format(
                topic=rng.choice(topics),
                topic_a=rng.choice(topics),
                topic_b=rng.choice(topics),
                process=rng.choice(processes),
                item_a=rng.choice(topics),
                item_b=rng.choice(topics),
                action=rng.choice(processes),
                mechanism=rng.choice(topics),
                event=f"advances in {rng.choice(topics)}",
                text=f"The {rng.choice(topics)} system uses advanced techniques.",
                concept=rng.choice(topics),
            )

            # Generate placeholder response
            response_len = rng.integers(50, 200)
            response_words = rng.choice(
                topics + ["the", "a", "is", "are", "can", "be", "with", "for", "to"],
                size=response_len,
            )
            response = " ".join(response_words)

            self._samples.append(
                {
                    "instruction": instruction,
                    "input": "",
                    "output": response,
                }
            )

    def _sample_to_sequence(
        self,
        sample: dict[str, Any],
        rng: np.random.Generator,
    ) -> dict[str, np.ndarray]:
        """Convert instruction sample to RSSM-compatible sequence."""
        cfg = self.config

        # Combine instruction and input
        full_text = sample["instruction"]
        if sample.get("input"):
            full_text += "\n" + sample["input"]
        if sample.get("output"):
            full_text += "\n" + sample["output"]

        # Tokenize
        tokenized = self._tokenize(full_text)
        text_ids = tokenized["input_ids"]
        text_mask = tokenized["attention_mask"]

        # Create RSSM-compatible observation
        # Map token IDs to observation space
        T = min(cfg.max_seq_len, 32)  # Use shorter seq for RSSM
        D = cfg.obs_dim
        A = cfg.action_dim

        obs = np.zeros((T, D), dtype=np.float32)
        actions = np.zeros((T, A), dtype=np.float32)
        rewards = np.zeros((T,), dtype=np.float32)
        continues = np.ones((T,), dtype=np.float32)

        # Sample tokens at regular intervals
        stride = max(1, len(text_ids) // T)
        sampled_ids = text_ids[::stride][:T]

        for t, token_id in enumerate(sampled_ids):
            # Embed token ID as normalized value
            obs[t, 0] = token_id / cfg.vocab_size

            # Position encoding
            obs[t, 1] = t / T

            # Token ID bits (binary representation)
            for bit in range(min(16, D - 2)):
                obs[t, 2 + bit] = (token_id >> bit) & 1

            # Action: predict next token embedding
            if t + 1 < len(sampled_ids):
                next_id = sampled_ids[t + 1]
                actions[t, 0] = (next_id - token_id) / cfg.vocab_size

            # Reward for non-padding tokens
            if token_id != cfg.pad_token_id:
                rewards[t] = 0.1
            else:
                continues[t] = 0.0

        # Symlog transform
        obs = np.sign(obs) * np.log1p(np.abs(obs))

        return {
            "obs": obs,
            "actions": actions,
            "rewards": rewards,
            "continues": continues,
            "text_ids": text_ids.astype(np.int32),
            "text_mask": text_mask.astype(np.int32),
        }

    def generate_shard(self, shard_id: int) -> dict[str, np.ndarray]:
        """Generate a single shard of training data."""
        cfg = self.config
        N = cfg.samples_per_shard
        T = 32  # Shorter seq for RSSM

        rng = np.random.default_rng(cfg.seed + shard_id)

        # Select samples for this shard
        start_idx = (shard_id * N) % len(self._samples)
        indices = [(start_idx + i) % len(self._samples) for i in range(N)]

        all_obs = np.zeros((N, T, cfg.obs_dim), dtype=np.float32)
        all_actions = np.zeros((N, T, cfg.action_dim), dtype=np.float32)
        all_rewards = np.zeros((N, T), dtype=np.float32)
        all_continues = np.ones((N, T), dtype=np.float32)
        all_text_ids = np.zeros((N, cfg.max_seq_len), dtype=np.int32)
        all_text_mask = np.zeros((N, cfg.max_seq_len), dtype=np.int32)

        for i, idx in enumerate(indices):
            sample = self._samples[idx]
            seq = self._sample_to_sequence(sample, rng)

            all_obs[i] = seq["obs"]
            all_actions[i] = seq["actions"]
            all_rewards[i] = seq["rewards"]
            all_continues[i] = seq["continues"]
            all_text_ids[i] = seq["text_ids"]
            all_text_mask[i] = seq["text_mask"]

        return {
            "obs": all_obs,
            "actions": all_actions,
            "rewards": all_rewards,
            "continues": all_continues,
            "text_ids": all_text_ids,
            "text_mask": all_text_mask,
        }

    def save_shard(self, shard_id: int, data: dict[str, np.ndarray]) -> str:
        """Save shard to output directory."""
        cfg = self.config
        filename = f"language-{shard_id:05d}-of-{cfg.num_shards:05d}.npz"

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

    def curate(self) -> list[str]:
        """Run full curation pipeline."""
        self.load_data()

        if not self._samples:
            logger.error("No samples loaded")
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
    parser = argparse.ArgumentParser(description="Curate language data for TPU training")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="gs://kagami-training-data/language/v1",
        help="Output directory",
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        default=100,
        help="Number of shards",
    )
    parser.add_argument(
        "--samples-per-shard",
        type=int,
        default=5000,
        help="Samples per shard",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="flan",
        choices=["flan", "sharegpt", "openassistant", "custom"],
        help="Data source",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/language",
        help="Input directory for custom data",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config = LanguageCuratorConfig(
        output_dir=args.output_dir,
        num_shards=args.num_shards,
        samples_per_shard=args.samples_per_shard,
        source=args.source,
        input_dir=args.input_dir,
        seed=args.seed,
    )

    curator = LanguageDataCurator(config)
    curator.curate()


if __name__ == "__main__":
    main()
