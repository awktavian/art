# TPU Optimization Master Plan: Kagami World Model Training

**CREATED**: January 12, 2026
**STATUS**: Active Implementation
**VERSION**: 1.0

---

## Executive Summary

This document synthesizes state-of-the-art research (2025-2026) with analysis of the Kagami codebase to provide a comprehensive optimization plan for TPU training of the OrganismRSSM world model. The plan covers three major areas:

1. **TPU Hardware Optimization** - Exploiting v6e Trillium capabilities
2. **World Model Architecture** - SOTA enhancements to OrganismRSSM
3. **Training Data Design** - Curriculum learning and data pipeline optimization

---

## Current System Analysis

### Strengths of Existing Implementation

| Component | Implementation | Quality |
|-----------|---------------|---------|
| **Distributed Training** | `shard_map` + `NamedSharding` (SCALE-2) | Excellent |
| **Gradient Management** | Checkpointing + NaN detection (SCALE-5,10) | Excellent |
| **Fault Tolerance** | Circuit breaker + async prefetch (SCALE-6,7) | Excellent |
| **Curriculum System** | 7-phase catastrophe-aligned curriculum | Excellent |
| **Training Validation** | KL collapse detection (v6e lessons) | Excellent |
| **Multi-Host Scaling** | `jax.distributed.initialize()` (SCALE-1) | Good |

### Gaps Identified

| Gap | Priority | Impact | SOTA Reference |
|-----|----------|--------|----------------|
| **No INT8/FP8 Quantization** | P0 | 1.2-1.4x speedup | AQT, MaxText |
| **No Tensor Padding to 256** | P0 | MXU underutilization | v6e spec |
| **No DoReMi-style Mixing** | P1 | Suboptimal data weights | DoReMi paper |
| **No Hierarchical Memory** | P1 | Limited long-horizon | UniWM, AgeMem |
| **No JEPA-style Prediction** | P1 | Pixel-space overhead | V-JEPA 2 |
| **No Competence-Aware Curriculum** | P2 | Fixed difficulty | CAMPUS |
| **No Soft Deduplication** | P2 | Information loss | SoftDedup |

---

## Part 1: TPU Hardware Optimization

### 1.1 INT8 Quantized Training (AQT)

**Impact**: 1.2-1.4x training speedup, 53% MFU demonstrated at scale

```python
# packages/kagami/core/training/jax/quantization.py

from typing import Any
import jax.numpy as jnp
import flax.linen as nn

# AQT integration for Dense layers
try:
    from aqt import flax as aqt_flax
    AQT_AVAILABLE = True
except ImportError:
    AQT_AVAILABLE = False


class QuantizedDense(nn.Module):
    """INT8 quantized Dense layer using AQT.

    On TPU v5e/v6e, INT8 ops run 2x faster than BF16.
    """
    features: int
    use_bias: bool = True
    quantize: bool = True

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        if self.quantize and AQT_AVAILABLE:
            # AQT quantized Dense
            return aqt_flax.DenseAqt(
                features=self.features,
                use_bias=self.use_bias,
                rhs_quant_mode='dynamic',
                lhs_quant_mode='dynamic',
            )(x)
        else:
            # Fallback to standard Dense
            return nn.Dense(
                features=self.features,
                use_bias=self.use_bias,
            )(x)


class QuantizationConfig:
    """Configuration for quantized training."""

    enable_int8: bool = True  # INT8 for matrix ops
    enable_fp8: bool = False  # FP8 (experimental, requires MaxText)

    # Which layers to quantize
    quantize_attention: bool = True
    quantize_mlp: bool = True
    quantize_embeddings: bool = False  # Keep embeddings in FP32

    # Dynamic vs static quantization
    quantization_mode: str = "dynamic"  # "dynamic", "static"
```

### 1.2 Tensor Padding for v6e Trillium (256x256 MXU)

**Impact**: 4.7x compute improvement vs v5e requires proper alignment

```python
# packages/kagami/core/training/jax/tpu_utils.py

import jax.numpy as jnp
from functools import lru_cache


def pad_to_tpu_alignment(dim: int, tpu_version: str = "v6e") -> int:
    """Pad dimension to TPU systolic array alignment.

    TPU v4/v5: 128x128 MXU → pad to multiples of 128
    TPU v6e:   256x256 MXU → pad to multiples of 256

    Args:
        dim: Original dimension
        tpu_version: "v4", "v5", "v5e", "v5p", "v6e"

    Returns:
        Padded dimension
    """
    alignment = 256 if tpu_version in ("v6e", "trillium") else 128
    return ((dim + alignment - 1) // alignment) * alignment


@lru_cache(maxsize=128)
def get_optimal_hidden_dim(base_dim: int, tpu_version: str = "v6e") -> int:
    """Get optimal hidden dimension for TPU efficiency.

    Example for v6e (256 alignment):
    - 768 → 768 (already aligned to 256)
    - 1024 → 1024 (already aligned)
    - 1536 → 1536 (already aligned)
    - 2048 → 2048 (already aligned)

    For attention heads:
    - d_model=768, n_heads=6 → d_head=128 (good for v4/v5)
    - d_model=1024, n_heads=4 → d_head=256 (optimal for v6e)
    """
    return pad_to_tpu_alignment(base_dim, tpu_version)


# Update OrganismRSSM config for v6e
V6E_OPTIMIZED_CONFIG = {
    "deter_dim": 768,      # 768 = 3 × 256 ✓
    "stoch_dim": 64,       # stoch_dim × classes = 64 × 240 = 15360 (not critical)
    "latent_classes": 240, # E8 roots (keep for mathematical structure)
    "hidden_dim": 1024,    # 1024 = 4 × 256 ✓
    "ff_dim": 2048,        # 2048 = 8 × 256 ✓
    "attention_heads": 4,  # 1024 / 4 = 256 per head ✓ (optimal for v6e)
}
```

### 1.3 Mixed Precision Strategy

**Current**: BF16 only
**Optimal**: BF16 activations + FP32 master weights + optional INT8 matmuls

```python
# packages/kagami/core/training/jax/precision.py

import jax
import jax.numpy as jnp
from typing import Any


class MixedPrecisionPolicy:
    """Mixed precision training policy for TPU.

    Best practice (2025):
    - Master weights: FP32 (for optimizer state)
    - Activations: BF16 (2x memory savings)
    - Matrix multiplies: INT8 optional (additional 1.2x speedup)
    - Accumulations: FP32 (no loss scaling needed with BF16)
    """

    compute_dtype = jnp.bfloat16
    param_dtype = jnp.float32
    output_dtype = jnp.float32

    @staticmethod
    def cast_to_compute(x: jnp.ndarray) -> jnp.ndarray:
        """Cast tensor to compute dtype (BF16)."""
        return x.astype(jnp.bfloat16)

    @staticmethod
    def cast_to_output(x: jnp.ndarray) -> jnp.ndarray:
        """Cast tensor back to output dtype (FP32)."""
        return x.astype(jnp.float32)

    @staticmethod
    def should_use_fp32(param_name: str) -> bool:
        """Determine if parameter should stay in FP32.

        Keep in FP32:
        - Layer norms (stability)
        - Embeddings (precision for discrete lookups)
        - Final output projections
        """
        fp32_patterns = ['norm', 'embed', 'output', 'logits']
        return any(p in param_name.lower() for p in fp32_patterns)
```

### 1.4 Optimized Data Pipeline

**Current**: Basic tf.data with prefetch
**Optimal**: Full tf.data AUTOTUNE + interleaved reading + length bucketing

```python
# packages/kagami/core/training/jax/optimized_data.py

import tensorflow as tf


def create_tpu_optimized_pipeline(
    data_pattern: str,
    global_batch_size: int,
    sequence_length: int,
    num_devices: int,
) -> tf.data.Dataset:
    """Create fully optimized tf.data pipeline for TPU.

    Optimizations applied:
    1. Interleaved reading (deterministic=False for throughput)
    2. Parallel parsing with AUTOTUNE
    3. Multi-stage prefetching
    4. Length bucketing for variable sequences
    """

    # Get shard files
    files = tf.io.gfile.glob(data_pattern)
    files_ds = tf.data.Dataset.from_tensor_slices(files)

    # Shuffle files
    files_ds = files_ds.shuffle(buffer_size=len(files))

    # OPTIMIZATION 1: Interleaved parallel reading
    dataset = files_ds.interleave(
        lambda x: tf.data.TFRecordDataset(
            x,
            compression_type="GZIP",
            buffer_size=8 * 1024 * 1024,  # 8MB read buffer
        ),
        cycle_length=tf.data.AUTOTUNE,
        block_length=16,
        num_parallel_calls=tf.data.AUTOTUNE,
        deterministic=False,  # Critical for throughput
    )

    # Shuffle
    dataset = dataset.shuffle(buffer_size=10000)

    # OPTIMIZATION 2: Parallel parsing
    def parse_fn(serialized):
        features = tf.io.parse_single_example(
            serialized,
            features={
                "obs": tf.io.FixedLenFeature([sequence_length * 64], tf.float32),
                "actions": tf.io.FixedLenFeature([sequence_length * 8], tf.float32),
                "rewards": tf.io.FixedLenFeature([sequence_length], tf.float32),
                "continues": tf.io.FixedLenFeature([sequence_length], tf.float32),
            }
        )
        return {
            "obs": tf.reshape(features["obs"], [sequence_length, 64]),
            "actions": tf.reshape(features["actions"], [sequence_length, 8]),
            "rewards": features["rewards"],
            "continues": features["continues"],
        }

    dataset = dataset.map(
        parse_fn,
        num_parallel_calls=tf.data.AUTOTUNE,
        deterministic=False,
    )

    # OPTIMIZATION 3: Batch with drop_remainder (required for TPU)
    per_device_batch = global_batch_size // num_devices
    dataset = dataset.batch(per_device_batch, drop_remainder=True)

    # OPTIMIZATION 4: Multi-stage prefetch
    dataset = dataset.prefetch(tf.data.AUTOTUNE)

    return dataset
```

---

## Part 2: World Model Architecture Enhancements

### 2.1 Multi-Horizon H-JEPA Prediction

**Current**: Single-step prediction
**Optimal**: Multi-horizon (h=1, 4, 16) in latent space (V-JEPA style)

```python
# Enhancement to OrganismRSSM in train_tpu.py

class MultiHorizonPredictor(nn.Module):
    """Multi-horizon prediction in latent space (JEPA-style).

    Predicts at multiple temporal horizons for better long-range modeling.
    """
    horizons: tuple[int, ...] = (1, 4, 16)
    hidden_dim: int = 512

    @nn.compact
    def __call__(
        self,
        latent_state: jnp.ndarray,  # [B, T, D]
    ) -> dict[int, jnp.ndarray]:
        """Predict future latent states at multiple horizons.

        Returns:
            Dict mapping horizon -> predicted latent states
        """
        predictions = {}

        for h in self.horizons:
            # Horizon-specific predictor
            pred_h = nn.Dense(self.hidden_dim, name=f"pred_h{h}_1")(latent_state)
            pred_h = nn.relu(pred_h)
            pred_h = nn.Dense(latent_state.shape[-1], name=f"pred_h{h}_2")(pred_h)

            # Predict h steps ahead
            # Compare: pred_h[:, :-h] should match latent_state[:, h:]
            predictions[h] = pred_h

        return predictions


def compute_hjepa_loss(
    predictions: dict[int, jnp.ndarray],
    targets: jnp.ndarray,
    horizon_weights: dict[int, float] = None,
) -> jnp.ndarray:
    """Compute multi-horizon JEPA loss.

    Loss computed in latent space (NOT pixel space).
    """
    if horizon_weights is None:
        horizon_weights = {1: 1.0, 4: 0.5, 16: 0.25}

    total_loss = 0.0
    for h, pred in predictions.items():
        weight = horizon_weights.get(h, 1.0)
        # MSE between predicted and actual future states
        loss_h = jnp.mean((pred[:, :-h] - targets[:, h:]) ** 2)
        total_loss += weight * loss_h

    return total_loss
```

### 2.2 Hierarchical Memory System

**Current**: No explicit memory
**Optimal**: Short-term + long-term hierarchical memory

```python
# packages/kagami/core/training/jax/memory.py

import jax.numpy as jnp
import flax.linen as nn
from typing import Optional


class HierarchicalMemory(nn.Module):
    """Hierarchical memory for long-horizon world modeling.

    Based on UniWM (2025) architecture:
    - Short-term: Working memory (recent observations)
    - Long-term: Episodic memory (trajectory context)
    """
    short_term_size: int = 64
    long_term_size: int = 1024
    memory_dim: int = 512
    num_heads: int = 8

    @nn.compact
    def __call__(
        self,
        query: jnp.ndarray,          # Current state [B, D]
        short_term: jnp.ndarray,     # [B, S, D]
        long_term: Optional[jnp.ndarray] = None,  # [B, L, D]
    ) -> jnp.ndarray:
        """Retrieve from hierarchical memory.

        Returns:
            Retrieved context [B, D]
        """
        # Short-term retrieval (attention over recent observations)
        q = nn.Dense(self.memory_dim, name="query_proj")(query)
        k_short = nn.Dense(self.memory_dim, name="key_short_proj")(short_term)
        v_short = nn.Dense(self.memory_dim, name="value_short_proj")(short_term)

        # Multi-head attention for short-term
        short_context = nn.MultiHeadDotProductAttention(
            num_heads=self.num_heads,
            name="short_term_attn",
        )(q[:, None, :], k_short, v_short)[:, 0, :]

        if long_term is None:
            return short_context

        # Long-term retrieval (key-based lookup)
        k_long = nn.Dense(self.memory_dim, name="key_long_proj")(long_term)
        v_long = nn.Dense(self.memory_dim, name="value_long_proj")(long_term)

        long_context = nn.MultiHeadDotProductAttention(
            num_heads=self.num_heads,
            name="long_term_attn",
        )(q[:, None, :], k_long, v_long)[:, 0, :]

        # Gated combination
        gate = nn.sigmoid(nn.Dense(1, name="memory_gate")(
            jnp.concatenate([short_context, long_context], axis=-1)
        ))

        return gate * short_context + (1 - gate) * long_context
```

### 2.3 Improved RSSM with Transformer SSM

**Current**: GRU-based dynamics
**Optimal**: Option for Transformer-based dynamics (TransDreamer style)

```python
# packages/kagami/core/training/jax/transformer_ssm.py

import jax.numpy as jnp
import flax.linen as nn


class TransformerSSM(nn.Module):
    """Transformer-based State Space Model.

    Replaces GRU dynamics with Transformer for better long-range dependencies.
    Based on TransDreamer (2025) architecture.
    """
    hidden_dim: int = 512
    num_heads: int = 8
    num_layers: int = 4
    max_seq_len: int = 256

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,  # [B, T, D]
        train: bool = True,
    ) -> jnp.ndarray:
        """Process sequence with causal Transformer.

        Args:
            x: Input sequence
            train: Training mode

        Returns:
            Transformed sequence (same shape)
        """
        B, T, D = x.shape

        # Positional encoding
        pos_embed = self.param(
            "pos_embed",
            nn.initializers.normal(stddev=0.02),
            (self.max_seq_len, self.hidden_dim),
        )
        x = x + pos_embed[:T]

        # Causal mask
        causal_mask = jnp.triu(
            jnp.ones((T, T)) * float('-inf'),
            k=1,
        )

        # Transformer layers
        for i in range(self.num_layers):
            # Self-attention with causal mask
            x_norm = nn.LayerNorm(name=f"norm1_{i}")(x)
            attn_out = nn.MultiHeadDotProductAttention(
                num_heads=self.num_heads,
                name=f"attn_{i}",
            )(x_norm, x_norm, mask=causal_mask)
            x = x + attn_out

            # Feed-forward
            x_norm = nn.LayerNorm(name=f"norm2_{i}")(x)
            ff_out = nn.Dense(self.hidden_dim * 4, name=f"ff1_{i}")(x_norm)
            ff_out = nn.gelu(ff_out)
            ff_out = nn.Dense(self.hidden_dim, name=f"ff2_{i}")(ff_out)
            x = x + ff_out

        return nn.LayerNorm(name="final_norm")(x)
```

---

## Part 3: Training Data Design

### 3.1 DoReMi-Style Data Mixing

**Current**: Fixed phase-based weights
**Optimal**: Adaptive weights based on domain excess loss

```python
# packages/kagami/core/training/jax/doremi.py

import jax.numpy as jnp
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DoReMiConfig:
    """Configuration for DoReMi-style data mixing."""
    dro_step_size: float = 0.01
    dro_smoothing: float = 0.1
    min_weight: float = 0.01
    max_weight: float = 0.9


@dataclass
class DomainStats:
    """Per-domain statistics for DoReMi."""
    name: str
    current_weight: float = 0.1
    cumulative_loss: float = 0.0
    sample_count: int = 0
    reference_loss: Optional[float] = None


class DoReMiMixer:
    """DoReMi-inspired domain reweighting.

    Key idea: Use excess loss (loss - reference_loss) to upweight
    domains where the model is underperforming.

    Reference: Stanford CRFM DoReMi paper (2023)
    """

    def __init__(
        self,
        domain_names: list[str],
        initial_weights: dict[str, float],
        config: DoReMiConfig = DoReMiConfig(),
    ):
        self.config = config
        self.domains = {
            name: DomainStats(
                name=name,
                current_weight=initial_weights.get(name, 0.1),
            )
            for name in domain_names
        }

    def get_weights(self) -> dict[str, float]:
        """Get current domain weights."""
        return {name: d.current_weight for name, d in self.domains.items()}

    def update(
        self,
        domain_losses: dict[str, float],
        reference_losses: Optional[dict[str, float]] = None,
    ) -> None:
        """Update weights based on domain losses.

        Args:
            domain_losses: Per-domain loss values
            reference_losses: Reference model losses (for excess computation)
        """
        # Compute excess losses
        excess_losses = {}
        for name, loss in domain_losses.items():
            if name not in self.domains:
                continue

            domain = self.domains[name]
            ref_loss = (
                reference_losses.get(name, 0)
                if reference_losses
                else domain.reference_loss or 0
            )
            excess_losses[name] = max(0, loss - ref_loss)

            # Update stats
            domain.cumulative_loss += loss
            domain.sample_count += 1

        # Group DRO update
        self._dro_update(excess_losses)

    def _dro_update(self, excess_losses: dict[str, float]) -> None:
        """Apply Group DRO weight update.

        Exponentiated gradient ascent on worst-case domain.
        """
        weights = self.get_weights()
        total_excess = sum(
            weights.get(name, 0) * loss
            for name, loss in excess_losses.items()
        )

        if total_excess < 1e-8:
            return

        # Update log-weights proportional to excess loss
        for name, loss in excess_losses.items():
            if name not in self.domains:
                continue

            domain = self.domains[name]
            gradient = loss / total_excess

            # Exponentiated gradient update
            log_weight = jnp.log(domain.current_weight + 1e-8)
            log_weight += self.config.dro_step_size * gradient
            new_weight = float(jnp.exp(log_weight))

            # Clamp to valid range
            domain.current_weight = max(
                self.config.min_weight,
                min(self.config.max_weight, new_weight)
            )

        # Normalize to sum to 1
        self._normalize_weights()

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1."""
        total = sum(d.current_weight for d in self.domains.values())
        if total > 0:
            for domain in self.domains.values():
                domain.current_weight /= total
```

### 3.2 Competence-Aware Curriculum

**Current**: Fixed phase thresholds
**Optimal**: Adaptive difficulty based on model competence

```python
# Enhancement to curriculum.py

from collections import deque
from dataclasses import dataclass


@dataclass
class CompetenceConfig:
    """Configuration for competence-aware learning."""
    competence_window: int = 100  # Steps to measure competence
    competence_threshold: float = 0.1  # Improvement threshold
    difficulty_increase_rate: float = 0.01
    difficulty_decrease_rate: float = 0.1  # Faster decrease on struggle
    min_difficulty: float = 0.0
    max_difficulty: float = 1.0


class CompetenceTracker:
    """Track model competence for adaptive curriculum.

    Based on CAMPUS (2025) framework.
    """

    def __init__(self, config: CompetenceConfig = CompetenceConfig()):
        self.config = config
        self._loss_history: deque[float] = deque(maxlen=config.competence_window)
        self._difficulty: float = 0.0

    @property
    def difficulty(self) -> float:
        """Current difficulty level [0, 1]."""
        return self._difficulty

    def update(self, loss: float) -> float:
        """Update competence and return new difficulty.

        Args:
            loss: Current loss value

        Returns:
            New difficulty level
        """
        self._loss_history.append(loss)

        if len(self._loss_history) < self.config.competence_window // 2:
            return self._difficulty

        # Compute competence as improvement rate
        mid = len(self._loss_history) // 2
        recent_mean = sum(list(self._loss_history)[mid:]) / (len(self._loss_history) - mid)
        older_mean = sum(list(self._loss_history)[:mid]) / mid

        improvement = (older_mean - recent_mean) / (older_mean + 1e-8)

        # Adjust difficulty based on competence
        if improvement > self.config.competence_threshold:
            # Model is learning well → increase difficulty
            self._difficulty = min(
                self.config.max_difficulty,
                self._difficulty + self.config.difficulty_increase_rate
            )
        elif improvement < -self.config.competence_threshold:
            # Model is struggling → decrease difficulty faster
            self._difficulty = max(
                self.config.min_difficulty,
                self._difficulty - self.config.difficulty_decrease_rate
            )

        return self._difficulty

    def get_sample_weight(self, sample_difficulty: float) -> float:
        """Get sampling weight for a sample based on its difficulty.

        Samples near current difficulty level get higher weight.
        """
        # Gaussian weighting centered on current difficulty
        diff = abs(sample_difficulty - self._difficulty)
        return float(jnp.exp(-diff ** 2 / 0.2))
```

### 3.3 Soft Deduplication

**Current**: No deduplication
**Optimal**: Reweight duplicates instead of removing

```python
# packages/kagami/core/training/jax/dedup.py

import jax.numpy as jnp
from collections import defaultdict
from typing import Optional
import hashlib


class SoftDeduplicator:
    """Soft deduplication: reweight instead of remove.

    Preserves information while reducing redundancy.
    Based on SoftDedup (2025) research.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        min_weight: float = 0.1,
    ):
        self.similarity_threshold = similarity_threshold
        self.min_weight = min_weight
        self._signature_counts: defaultdict[str, int] = defaultdict(int)

    def compute_weight(self, text: str) -> float:
        """Compute sample weight based on duplication count.

        Higher duplication → lower weight (but never zero).
        """
        signature = self._compute_signature(text)
        count = self._signature_counts[signature]
        self._signature_counts[signature] += 1

        # Weight decreases with count (asymptotic to min_weight)
        weight = max(self.min_weight, 1.0 / (1 + 0.5 * count))
        return weight

    def _compute_signature(self, text: str, n: int = 5) -> str:
        """Compute locality-sensitive signature.

        Uses character n-grams for fast similarity detection.
        """
        # Extract n-grams
        ngrams = set()
        for i in range(min(len(text), 500) - n + 1):
            ngrams.add(text[i:i+n])

        # Sort and hash
        sorted_ngrams = sorted(ngrams)[:20]  # Top 20 for signature
        signature = hashlib.md5("".join(sorted_ngrams).encode()).hexdigest()
        return signature

    def reset(self) -> None:
        """Reset signature counts (for new epoch)."""
        self._signature_counts.clear()
```

---

## Part 4: Implementation Roadmap

### Phase 1: TPU Hardware Optimization (Week 1)

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Add tensor padding to 256 for v6e | P0 | 2h | MXU efficiency |
| Integrate AQT INT8 quantization | P0 | 4h | 1.2-1.4x speedup |
| Optimize tf.data pipeline | P1 | 4h | I/O throughput |
| Add FP8 experimental support | P2 | 2h | Future-proofing |

### Phase 2: World Model Architecture (Week 2)

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Implement multi-horizon H-JEPA | P1 | 6h | Long-range prediction |
| Add hierarchical memory | P1 | 8h | Long-horizon reasoning |
| Optional Transformer SSM | P2 | 6h | Alternative dynamics |
| Improve Fano attention | P2 | 4h | Colony coordination |

### Phase 3: Training Data Design (Week 3)

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Implement DoReMi mixing | P1 | 6h | Optimal data weights |
| Add competence-aware curriculum | P1 | 4h | Adaptive difficulty |
| Implement soft deduplication | P2 | 4h | Information preservation |
| Enhance data pipeline profiling | P2 | 2h | Performance monitoring |

---

## Performance Targets

### Training Throughput

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| MFU | 58.3% | 65%+ | INT8 + padding + optimized pipeline |
| Tokens/sec/chip | 12,500 | 15,000+ | All optimizations combined |
| Checkpoint time | 1.2s async | <1.0s | Orbax native integration |

### Model Quality

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Reconstruction loss | 0.05 | 0.03 | Multi-horizon JEPA |
| Long-horizon prediction | N/A | <0.1 MSE @ h=16 | Hierarchical memory |
| Phase transition time | Manual | Auto | Competence-aware curriculum |

---

## References

### TPU Optimization
- [Google Cloud TPU v6e Documentation](https://cloud.google.com/tpu/docs/v6e)
- [AQT for TPU v5e](https://cloud.google.com/blog/products/compute/accurate-quantized-training-aqt)
- [MaxText Repository](https://github.com/AI-Hypercomputer/maxtext)
- [JAX Scaling Book](https://jax-ml.github.io/scaling-book/)

### World Models
- [V-JEPA 2 (Meta AI)](https://ai.meta.com/vjepa/)
- [DreamerV3 Paper](https://arxiv.org/abs/2301.04104)
- [Genie 2 (DeepMind)](https://deepmind.google/blog/genie-2/)
- [UniWM Paper](https://arxiv.org/abs/2510.08713)

### Training Data
- [DoReMi (Stanford CRFM)](https://crfm.stanford.edu/2023/09/14/doremi.html)
- [Data Mixing Laws (ICLR 2025)](https://proceedings.iclr.cc/)
- [Curriculum Learning Survey](https://arxiv.org/abs/2405.07490)

---

*Document Version: 1.0 | Created: January 12, 2026*
