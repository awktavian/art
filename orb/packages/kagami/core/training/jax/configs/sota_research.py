"""SOTA Research-Backed Configuration for OrganismRSSM.

Integrates cutting-edge techniques from:

WORLD MODEL:
- DreamerV3 (Hafner et al., 2023): symlog, TwoHot, balanced KL, free bits
- S4WM (Deng et al., 2024): State space world models, long-term memory
- IRIS (Micheli et al., 2023): Transformer world models, discrete tokens

LLM ARCHITECTURE:
- DeepSeek V3 (2024): Multi-Head Latent Attention (MLA), auxiliary-loss-free MoE
- Mamba-2 (Gu & Dao, 2024): Structured State Space Duality, linear complexity
- Llama 3 (Meta, 2024): GQA, RoPE, SwiGLU
- Gemma 2 (Google, 2024): Sliding window attention, pre/post-norm

DATA EFFICIENCY (Microsoft Phi):
- Phi-4 (2024): 40% synthetic, textbook quality, curriculum learning
- Progressive difficulty: Easy → Hard during training
- Seed selection: High-quality organic texts as generation seeds

VLA (Vision-Language-Action):
- 3D-VLA (IBM, 2025): Generative world model with embodied diffusion
- CogVLA (2025): Instruction-driven routing, sparsification
- MoLe-VLA (2025): Dynamic layer-skipping, 5.6x compute reduction

Created: January 9, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# RESEARCH-BACKED HYPERPARAMETERS
# =============================================================================


class AttentionType(str, Enum):
    """Attention mechanism types."""

    STANDARD = "standard"  # O(n²) - baseline
    GQA = "gqa"  # Grouped Query Attention (Llama 3)
    MLA = "mla"  # Multi-Head Latent Attention (DeepSeek V3)
    SLIDING = "sliding"  # Sliding Window (Gemma 2)
    SPARSE_FANO = "sparse_fano"  # Colony-specific Fano plane attention


class SSMType(str, Enum):
    """State Space Model types."""

    GRU = "gru"  # Standard GRU (DreamerV3)
    MAMBA2 = "mamba2"  # Mamba-2 SSD (linear complexity)
    S4 = "s4"  # S4 structured SSM
    HYBRID = "hybrid"  # Transformer + SSM interleaved


# =============================================================================
# DREAMERV3 OPTIMAL HYPERPARAMETERS
# =============================================================================


@dataclass
class DreamerV3Config:
    """DreamerV3-optimal hyperparameters.

    Source: https://arxiv.org/abs/2301.04104
    Validated on 150+ diverse tasks.
    """

    # Replay buffer
    replay_capacity: int = 1_000_000  # 10^6 steps FIFO
    batch_size: int = 64  # 16-128 optimal
    sequence_length: int = 64  # 50-64 optimal

    # Optimization
    learning_rate: float = 1e-4  # 1e-4 to 4e-5
    adam_eps: float = 1e-8
    grad_clip: float = 1000.0  # High clip, let symlog handle scale
    weight_decay: float = 0.0  # Not used in DreamerV3

    # KL balancing
    kl_free_bits: float = 1.0  # Free bits per dimension
    kl_free_avg: bool = True  # Average over batch
    kl_balance: float = 0.8  # 80% dynamics, 20% representation

    # Imagination
    imagination_horizon: int = 15  # Standard horizon
    gamma: float = 0.997  # Discount factor
    lambda_gae: float = 0.95  # GAE lambda

    # Entropy regularization
    entropy_scale: float = 3e-4  # η = 3×10^-4

    # Normalization
    symlog_obs: bool = True  # Symlog observations
    symlog_rewards: bool = True  # Symlog rewards
    twohot_bins: int = 255  # TwoHot buckets

    # Returns
    return_normalization: str = "symlog"  # or "percentile"
    percentile_low: float = 5.0
    percentile_high: float = 95.0


# =============================================================================
# DEEPSEEK V3 MLA CONFIG
# =============================================================================


@dataclass
class MLAConfig:
    """Multi-Head Latent Attention configuration (DeepSeek V3).

    Source: DeepSeek V3 Technical Report (2024)

    Key innovation: Compress KV into low-rank latent vector.
    Memory reduction: 10-20x during inference.
    """

    # Latent compression
    latent_dim: int = 512  # Compressed KV dimension
    num_latent_heads: int = 8  # Heads in latent space

    # KV compression ratio
    kv_compression_ratio: float = 0.25  # 4x compression

    # Projection
    use_rope_in_latent: bool = True  # RoPE in latent space
    use_bias: bool = False  # No bias (modern practice)

    # Multi-Token Prediction (MTP)
    mtp_enabled: bool = True  # Predict multiple tokens
    mtp_num_tokens: int = 4  # Tokens to predict jointly
    mtp_weight: float = 0.1  # MTP loss weight


# =============================================================================
# MAMBA-2 SSM CONFIG
# =============================================================================


@dataclass
class Mamba2Config:
    """Mamba-2 Structured State Space configuration.

    Source: Mamba-2 (Gu & Dao, 2024)

    Key innovation: Structured State Space Duality (SSD)
    Complexity: O(n) vs O(n²) for attention
    """

    # State space dimensions
    state_dim: int = 64  # SSM state dimension
    expand_factor: int = 2  # Expansion in conv

    # Convolution
    conv_kernel_size: int = 4  # 1D conv kernel

    # Discretization
    dt_min: float = 0.001
    dt_max: float = 0.1
    dt_init: str = "random"  # or "learned"

    # A matrix initialization
    a_init: str = "hippo"  # HiPPO matrix for long memory

    # Hybrid with attention
    hybrid_ratio: float = 0.5  # 50% Mamba, 50% attention
    attention_every_n: int = 4  # Attention every N layers


# =============================================================================
# PHI-4 DATA EFFICIENCY CONFIG
# =============================================================================


@dataclass
class PhiDataConfig:
    """Phi-4 style data efficiency configuration.

    Source: Phi-4 Technical Report (Microsoft, 2024)

    Key insight: Data quality > quantity
    40% synthetic, textbook-quality data
    """

    # Data mixture (Phi-4 optimal)
    synthetic_ratio: float = 0.40  # 40% synthetic
    web_rewrite_ratio: float = 0.15  # 15% web rewrites
    organic_web_ratio: float = 0.15  # 15% organic web
    code_ratio: float = 0.20  # 20% code
    acquired_ratio: float = 0.10  # 10% books, Q&A

    # Synthetic data generation
    use_multi_agent: bool = True  # Multi-agent prompting
    use_self_revision: bool = True  # Self-revision workflows
    use_instruction_reversal: bool = True  # Instruction reversal

    # Quality filtering
    min_quality_score: float = 0.8  # Filter low quality
    textbook_style: bool = True  # Educational formatting

    # Progressive difficulty
    progressive_learning: bool = True
    difficulty_schedule: str = "linear"  # linear, cosine, step

    # Seed selection for synthetic
    seed_quality_threshold: float = 0.9  # High quality seeds
    focus_on_reasoning: bool = True  # Reasoning-rich content


# =============================================================================
# OPTIMAL LLM ARCHITECTURE CONFIG
# =============================================================================


@dataclass
class SOTALLMConfig:
    """State-of-the-art LLM architecture configuration.

    Combines best practices from:
    - Llama 3: GQA, RoPE, SwiGLU
    - Gemma 2: Sliding window, pre/post norm
    - DeepSeek V3: MLA, MoE
    - Mamba-2: Hybrid SSM
    """

    # Core dimensions
    hidden_dim: int = 768  # Match RSSM deter_dim
    intermediate_dim: int = 2048  # ~2.67x hidden (SwiGLU)
    num_layers: int = 24  # Deep network

    # Attention
    attention_type: AttentionType = AttentionType.GQA
    num_attention_heads: int = 16
    num_kv_heads: int = 4  # GQA: 4 KV groups
    head_dim: int = 48  # 768/16

    # Position embedding
    rope_theta: float = 500000.0  # Extended RoPE (Llama 3)
    rope_scaling: str | None = None  # "linear", "dynamic", None
    max_position_embeddings: int = 32768  # 32K context

    # Normalization
    norm_type: str = "rmsnorm"  # RMSNorm (faster than LayerNorm)
    norm_eps: float = 1e-5
    use_pre_norm: bool = True  # Pre-norm (Gemma 2)
    use_post_norm: bool = True  # Also post-norm (Gemma 2)

    # Activation
    hidden_act: str = "silu"  # SwiGLU uses SiLU
    use_swiglu: bool = True  # SwiGLU activation

    # Dropout (usually 0 in modern LLMs)
    attention_dropout: float = 0.0
    hidden_dropout: float = 0.0

    # Sliding window (Gemma 2)
    sliding_window: int | None = 4096  # Local attention window

    # Hybrid SSM
    ssm_type: SSMType = SSMType.HYBRID
    ssm_layers: list[int] = field(default_factory=lambda: [0, 4, 8, 12, 16, 20])


# =============================================================================
# OPTIMAL TRAINING SCHEDULE
# =============================================================================


@dataclass
class SOTATrainingConfig:
    """Research-backed optimal training configuration."""

    # Scale
    total_tokens: int = 15_000_000_000_000  # 15T tokens (DeepSeek V3 scale)
    batch_size: int = 256  # Per-device
    sequence_length: int = 32  # World model sequences
    gradient_accumulation: int = 4  # Effective batch 1024

    # Learning rate
    learning_rate: float = 1e-4  # Peak LR
    min_learning_rate: float = 1e-5  # 10% of peak
    warmup_steps: int = 2000  # Linear warmup
    lr_schedule: str = "cosine"  # Cosine decay

    # Optimizer (AdamW is still SOTA)
    optimizer: str = "adamw"
    adam_beta1: float = 0.9
    adam_beta2: float = 0.95  # Lower for stability
    adam_eps: float = 1e-8
    weight_decay: float = 0.1  # Standard weight decay

    # Gradient handling
    grad_clip: float = 1.0  # Tighter for stability
    grad_clip_type: str = "global_norm"  # or "value"

    # Precision
    precision: str = "bf16"  # BF16 for TPU
    grad_scaler: bool = False  # Not needed with BF16

    # Stability
    z_loss_weight: float = 1e-4  # Router z-loss (MoE)
    aux_loss_free: bool = True  # DeepSeek V3 style


# =============================================================================
# INTEGRATED SOTA CONFIG
# =============================================================================


@dataclass
class SOTAOrganismConfig:
    """Complete SOTA OrganismRSSM configuration.

    Integrates all research-backed optimizations:
    - DreamerV3 world model fundamentals
    - DeepSeek V3 attention efficiency
    - Mamba-2 linear complexity
    - Phi-4 data efficiency
    - Modern LLM architecture
    """

    # Sub-configs
    dreamer: DreamerV3Config = field(default_factory=DreamerV3Config)
    mla: MLAConfig = field(default_factory=MLAConfig)
    mamba: Mamba2Config = field(default_factory=Mamba2Config)
    phi_data: PhiDataConfig = field(default_factory=PhiDataConfig)
    llm: SOTALLMConfig = field(default_factory=SOTALLMConfig)
    training: SOTATrainingConfig = field(default_factory=SOTATrainingConfig)

    # OrganismRSSM specific
    num_colonies: int = 7  # Octonion basis

    # E8 lattice (unique to Kagami)
    e8_enabled: bool = True
    e8_root_classes: int = 240  # E8 root system

    # Fano plane attention (unique to Kagami)
    fano_attention: bool = True

    # S7 phase gating (unique to Kagami)
    s7_phase_gating: bool = True

    def to_rssm_config(self) -> dict[str, Any]:
        """Convert to OrganismRSSMConfig kwargs."""
        return {
            "obs_dim": 128,
            "action_dim": 8,
            "num_colonies": self.num_colonies,
            "deter_dim": self.llm.hidden_dim,
            "stoch_dim": 64,
            "discrete_categories": 32,
            "discrete_classes": 32,
            "latent_classes": self.e8_root_classes,
            "unimix": 0.01,
            "free_bits": self.dreamer.kl_free_bits,
            "kl_dyn_weight": self.dreamer.kl_balance,
            "kl_rep_weight": 1.0 - self.dreamer.kl_balance,
            "num_reward_bins": self.dreamer.twohot_bins,
            "gru_num_blocks": 16,
            "attention_heads": self.llm.num_attention_heads,
            "attention_dropout": self.llm.attention_dropout,
            "hjepa_horizons": (1, 4, 16, 64),
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def get_sota_config() -> SOTAOrganismConfig:
    """Get the full SOTA configuration."""
    return SOTAOrganismConfig()


def get_sota_config_small() -> SOTAOrganismConfig:
    """SOTA config scaled down for testing."""
    config = SOTAOrganismConfig()
    config.llm.hidden_dim = 256
    config.llm.num_layers = 12
    config.llm.num_attention_heads = 8
    config.llm.num_kv_heads = 2
    config.training.batch_size = 32
    return config


def get_sota_config_xl() -> SOTAOrganismConfig:
    """SOTA config scaled up for maximum performance."""
    config = SOTAOrganismConfig()
    config.llm.hidden_dim = 1024
    config.llm.intermediate_dim = 4096
    config.llm.num_layers = 32
    config.llm.num_attention_heads = 16
    config.llm.num_kv_heads = 4
    config.training.batch_size = 512
    return config


# =============================================================================
# RESEARCH CITATIONS
# =============================================================================

CITATIONS = """
@article{hafner2023dreamerv3,
  title={Mastering Diverse Domains through World Models},
  author={Hafner, Danijar and Pasukonis, Jurgis and Ba, Jimmy and Lillicrap, Timothy},
  journal={arXiv preprint arXiv:2301.04104},
  year={2023}
}

@article{gu2024mamba2,
  title={Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Space Duality},
  author={Gu, Albert and Dao, Tri},
  journal={arXiv preprint arXiv:2405.21060},
  year={2024}
}

@article{deepseek2024v3,
  title={DeepSeek-V3 Technical Report},
  author={DeepSeek-AI},
  year={2024}
}

@article{microsoft2024phi4,
  title={Phi-4 Technical Report},
  author={Microsoft Research},
  year={2024}
}

@article{touvron2024llama3,
  title={Llama 3: Technical Report},
  author={Meta AI},
  year={2024}
}

@article{team2024gemma2,
  title={Gemma 2: Improving Open Language Models at a Practical Size},
  author={Google DeepMind},
  year={2024}
}
"""


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "CITATIONS",
    "AttentionType",
    "DreamerV3Config",
    "MLAConfig",
    "Mamba2Config",
    "PhiDataConfig",
    "SOTALLMConfig",
    "SOTAOrganismConfig",
    "SOTATrainingConfig",
    "SSMType",
    "get_sota_config",
    "get_sota_config_small",
    "get_sota_config_xl",
]
