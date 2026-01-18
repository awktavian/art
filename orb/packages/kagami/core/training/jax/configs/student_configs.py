"""Student Model Configurations for Knowledge Distillation.

Defines three student model sizes for deployment:
- Small (12M): Raspberry Pi / embedded devices
- Base (50M): Desktop / mobile apps
- Large (200M): Server API / cloud inference

Each config is optimized for its target platform's constraints:
- Memory footprint
- Inference latency
- Model capacity

Usage:
    from kagami.core.training.jax.configs.student_configs import (
        get_student_config,
        STUDENT_CONFIGS,
    )

    config = get_student_config("small")

Created: January 12, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jax.numpy as jnp


@dataclass
class StudentConfig:
    """Full configuration for a student model."""

    # Identity
    name: str
    description: str = ""

    # Model dimensions
    obs_dim: int = 64
    action_dim: int = 8
    deter_dim: int = 256
    stoch_dim: int = 16
    hidden_dim: int = 256

    # Architecture
    num_colonies: int = 7  # Maintain E8 structure
    latent_classes: int = 240  # E8 roots
    gru_num_blocks: int = 4
    num_attention_heads: int = 4

    # Reward/continue heads
    num_reward_bins: int = 255
    reward_low: float = -20.0
    reward_high: float = 20.0

    # Distillation settings
    temperature: float = 2.0  # Softmax temperature for KD
    alpha_hard: float = 0.5  # Weight for hard label loss
    alpha_soft: float = 0.5  # Weight for soft label loss
    alpha_feature: float = 0.3  # Weight for feature distillation
    alpha_relational: float = 0.2  # Weight for relational distillation

    # Training
    batch_size: int = 64
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    warmup_steps: int = 1000
    total_steps: int = 100000

    # Target platform constraints
    max_memory_mb: int = 512  # Max memory budget in MB
    target_latency_ms: float = 100.0  # Target inference latency

    # Dtype
    dtype: Any = field(default_factory=lambda: jnp.float32)

    @property
    def estimated_params(self) -> int:
        """Estimate total parameter count."""
        # Rough estimates based on architecture
        obs_params = self.obs_dim * self.hidden_dim
        gru_params = 3 * self.deter_dim * (self.stoch_dim + self.action_dim + self.deter_dim)
        attention_params = 4 * self.hidden_dim * self.hidden_dim  # Q, K, V, O
        prior_post_params = 2 * self.deter_dim * self.latent_classes
        decoder_params = self.hidden_dim * self.obs_dim
        head_params = self.hidden_dim * (self.num_reward_bins + 1)

        total = (
            obs_params
            + gru_params * self.gru_num_blocks
            + attention_params * self.num_attention_heads
            + prior_post_params
            + decoder_params
            + head_params
        )

        return int(total)

    @property
    def estimated_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        # Parameters + activations + optimizer state
        param_bytes = self.estimated_params * 4  # float32
        activation_multiplier = 2.0  # Rough estimate
        optimizer_multiplier = 2.0  # AdamW states

        total_bytes = param_bytes * (1 + activation_multiplier + optimizer_multiplier)
        return total_bytes / (1024 * 1024)


# =============================================================================
# PRE-DEFINED CONFIGURATIONS
# =============================================================================


STUDENT_SMALL = StudentConfig(
    name="small",
    description="12M params for Raspberry Pi / embedded devices",
    deter_dim=256,
    stoch_dim=16,
    hidden_dim=256,
    gru_num_blocks=4,
    num_attention_heads=4,
    temperature=3.0,  # Higher temp for more knowledge transfer
    alpha_soft=0.7,  # Rely more on teacher
    alpha_hard=0.3,
    batch_size=32,  # Smaller batches for limited memory
    learning_rate=1e-4,
    total_steps=150000,  # More steps for smaller model
    max_memory_mb=256,
    target_latency_ms=50.0,  # Fast inference needed
    dtype=jnp.float32,  # No bfloat16 on RPi
)


STUDENT_BASE = StudentConfig(
    name="base",
    description="50M params for desktop and mobile apps",
    deter_dim=384,
    stoch_dim=32,
    hidden_dim=384,
    gru_num_blocks=6,
    num_attention_heads=6,
    temperature=2.0,
    alpha_soft=0.5,
    alpha_hard=0.5,
    batch_size=64,
    learning_rate=1e-4,
    total_steps=100000,
    max_memory_mb=512,
    target_latency_ms=100.0,
    dtype=jnp.float32,
)


STUDENT_LARGE = StudentConfig(
    name="large",
    description="200M params for server API / cloud inference",
    deter_dim=512,
    stoch_dim=32,
    hidden_dim=512,
    gru_num_blocks=8,
    num_attention_heads=8,
    temperature=1.5,  # Lower temp - can handle nuance
    alpha_soft=0.4,
    alpha_hard=0.6,  # More emphasis on hard labels
    alpha_feature=0.4,  # More feature matching
    batch_size=128,
    learning_rate=5e-5,  # Lower LR for larger model
    total_steps=80000,
    max_memory_mb=4096,
    target_latency_ms=200.0,
    dtype=jnp.bfloat16,  # Use bfloat16 on server
)


# Config registry
STUDENT_CONFIGS = {
    "small": STUDENT_SMALL,
    "base": STUDENT_BASE,
    "large": STUDENT_LARGE,
}


def get_student_config(name: str) -> StudentConfig:
    """Get student configuration by name.

    Args:
        name: One of 'small', 'base', 'large'

    Returns:
        StudentConfig instance

    Raises:
        ValueError: If name is not recognized
    """
    if name not in STUDENT_CONFIGS:
        raise ValueError(
            f"Unknown student config: {name}. Available: {list(STUDENT_CONFIGS.keys())}"
        )
    return STUDENT_CONFIGS[name]


def list_student_configs() -> list[str]:
    """List available student configuration names."""
    return list(STUDENT_CONFIGS.keys())


def print_student_configs() -> None:
    """Print summary of all student configurations."""
    print("=" * 60)
    print("Student Model Configurations")
    print("=" * 60)

    for name, config in STUDENT_CONFIGS.items():
        print(f"\n{name.upper()}: {config.description}")
        print(f"  Dimensions: deter={config.deter_dim}, stoch={config.stoch_dim}")
        print(f"  GRU Blocks: {config.gru_num_blocks}")
        print(f"  Attention Heads: {config.num_attention_heads}")
        print(
            f"  Est. Parameters: {config.estimated_params:,} ({config.estimated_params / 1e6:.1f}M)"
        )
        print(f"  Est. Memory: {config.estimated_memory_mb:.0f} MB")
        print(f"  Target Latency: {config.target_latency_ms:.0f} ms")
        print(f"  Temperature: {config.temperature}")

    print("\n" + "=" * 60)


__all__ = [
    "STUDENT_BASE",
    "STUDENT_CONFIGS",
    "STUDENT_LARGE",
    "STUDENT_SMALL",
    "StudentConfig",
    "get_student_config",
    "list_student_configs",
    "print_student_configs",
]


if __name__ == "__main__":
    print_student_configs()
