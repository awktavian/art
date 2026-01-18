# JAX Training Architecture

## Overview

This directory contains the complete JAX/Flax implementation of OrganismRSSM training,
designed for TPU hyperscale training with bulletproof monitoring.

**Total: 8,172 lines of JAX code**

## 🎯 Quick Start: LARGE Model for TPU Distillation

```python
from kagami.core.training.jax.configs import get_large_model_config

# Load LARGE config (~200M params) - teacher for distillation
config = get_large_model_config()

# Model: deter=768, stoch=64, heads=16
model = OrganismRSSM(config.rssm)

# Training: batch=256, seq=32, lr=1e-4, steps=500K
trainer = Trainer(config)

# See DATA.md for complete training data specification
```

| Model | Params | deter | stoch | heads | TPU Memory |
|-------|--------|-------|-------|-------|------------|
| Small | 12M | 256 | 16 | 4 | ~2GB |
| Base | 50M | 384 | 32 | 8 | ~8GB |
| **Large** | **200M** | **768** | **64** | **16** | **~32GB** |
| XL | 500M | 1024 | 96 | 16 | ~80GB |

## System Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              TRAINING LOOP                                      │
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ DataPipeline│───▶│ OrganismRSSM│───▶│ compute_loss│───▶│ train_step  │     │
│  │ (data.py)   │    │ (rssm.py)   │    │ (losses.py) │    │ (train.py)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                  │                  │                  │             │
│         ▼                  ▼                  ▼                  ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Curriculum  │    │ Telemetry   │    │ Controller  │    │ Checkpoint  │     │
│  │ Sampler     │    │ Monitors    │    │ Intervention│    │ Manager     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

## File Index

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 160 | Public API exports |
| `config.py` | 307 | Configuration dataclasses |
| `rssm.py` | 627 | OrganismRSSM model |
| `modules.py` | 382 | BlockGRU, DiscreteLatentEncoder, SparseAttention |
| `heads.py` | 394 | Encoder, Decoder, Reward, Continue |
| `transforms.py` | 505 | DreamerV3 transforms |
| `losses.py` | 392 | Loss computation |
| `curriculum.py` | 603 | 7-phase curriculum |
| `data.py` | 525 | Data pipeline |
| `telemetry.py` | 586 | Training monitors |
| `control.py` | 572 | Checkpointing, control |
| `train.py` | 496 | Training loop |
| `multimodal/` | 2,623 | Language-conditioned RSSM |

## OrganismRSSM Architecture

```
Input: obs[B,T,D], actions[B,T,A]
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                    OrganismRSSM                          │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 7 Colonies (e₁...e₇ octonion imaginary basis)    │   │
│  │                                                   │   │
│  │   Colony 1 ─┬─ h[384] deterministic state        │   │
│  │   Colony 2 ─┤  z[32×32] stochastic latent        │   │
│  │   ...       │                                     │   │
│  │   Colony 7 ─┘                                     │   │
│  └──────────────────────────────────────────────────┘   │
│                          │                               │
│                    ┌─────▼─────┐                        │
│                    │ BlockGRU  │ (8 blocks)             │
│                    └─────┬─────┘                        │
│                          │                               │
│        ┌─────────────────┼─────────────────┐            │
│        ▼                 ▼                 ▼            │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐       │
│  │ E8 Root  │     │ Fano     │     │ S7 Phase │       │
│  │ Categorical│   │ Attention│     │ Gating   │       │
│  │ (240 cls) │     └──────────┘     └──────────┘       │
│  └──────────┘                                          │
└─────────────────────────────────────────────────────────┘
       │
       ▼
Output: h_next, z_next, obs_pred, reward_pred, continue_pred
```

### Key Components

- **BlockGRU**: 8-block residual GRU for temporal dynamics
- **DiscreteLatentEncoder**: 32 categorical distributions × 32 classes
- **E8 Root Categorical**: 240-class latent aligned to E8 lattice roots
- **SparseAttention**: Colony-to-colony via Fano plane structure
- **S7 Phase Gating**: 7-sphere fiber bundle phase coherence

## 7-Phase Curriculum

| Phase | Catastrophe | Colonies | β (KL) | E8 | Focus |
|-------|-------------|----------|--------|-----|-------|
| 0. WARMUP | None | 1 | 1e-6 | 0.0 | Stabilize encoder/decoder |
| 1. GEOMETRY | Fold (A₂) | 2 | 1.0 | 0.5 | E8 lattice structure |
| 2. ROTATION | Cusp (A₃) | 3 | 1.0 | 0.3 | SE(3) equivariance |
| 3. DYNAMICS | Swallowtail (A₄) | 4 | 1.0 | 0.1 | World model prediction |
| 4. JOINT | Butterfly (A₅) | 7 | 1.0 | 0.05 | RSSM + EFE unified |
| 5. GENERATION | Hyperbolic (D₄⁺) | 7 | 1.0 | 0.01 | Fine-grained generation |
| 6. LANGUAGE | Elliptic (D₄⁻) | 7 | 1.0 | 0.01 | Language grounding |

### Transition Criteria

Each phase transition requires ALL of:
1. Minimum steps reached
2. Loss below threshold
3. Gradient norm converged
4. Loss velocity stable

### KL Annealing (WARMUP)

- β = 1e-6 during WARMUP (NOT 0 to avoid JAX recompilation)
- β = 1.0 for all subsequent phases
- Prevents posterior collapse during initial training

## Loss Functions

```
L_total = recon × L_recon
        + β × kl × L_kl_balanced
        + reward × L_reward
        + e8 × L_e8_commitment
        + fano × L_fano_synergy
        + hjepa × L_hjepa
        + stability × L_stability
```

### DreamerV3 Transforms

- `symlog(x)`: Symmetric log compression for rewards
- `TwoHotEncoder`: 255-bin two-hot encoding
- `balanced_kl_loss_categorical`: Balanced KL with free bits
- `SimNorm`: Similarity-based normalization
- `unimix_categorical`: Uniform mixing to prevent collapse

## Telemetry System

### Monitors

| Monitor | What | Threshold | Action |
|---------|------|-----------|--------|
| KLCollapseDetector | KL → 0 | 1e-4 | Raise RuntimeError |
| PlateauDetector | Loss stuck | velocity < 1e-6 | Reduce LR × 0.5 |
| GradientMonitor | grad_norm | > 1000 | Log error |
| DivergenceDetector | NaN/Inf | any | Restore checkpoint |

### From v6e Failure Analysis (Jan 6, 2026)

**What went wrong:**
- KL went from 0.113 → -1.49e-7 (numerical underflow)
- Loss plateaued at 0.4-0.45 for 40K steps
- No warnings raised

**What we fixed:**
- `KLCollapseDetector`: Raises after 100 consecutive warnings
- `PlateauDetector`: Adaptive LR reduction with cooldown
- `free_bits=3.0`: Increased from 1.0 for 240-class latent

## Data Pipeline

### Curriculum-Aware Sampling

```python
WARMUP:     {"jepa": 1.0}
GEOMETRY:   {"jepa": 0.6, "qm9": 0.2, "tree_of_life": 0.2}
ROTATION:   {"jepa": 0.5, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.1}
DYNAMICS:   {"jepa": 0.45, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.15}
JOINT:      {"jepa": 0.35, "qm9": 0.15, "tree_of_life": 0.15, "generation": 0.35}
GENERATION: {"generation": 0.5, "jepa": 0.25, "qm9": 0.15, "tree_of_life": 0.1}
LANGUAGE:   {"jepa": 0.3, "language": 0.3, "instruction": 0.2, "qm9": 0.1, "tree_of_life": 0.1}
```

### DataBatch Structure

```python
@dataclass
class DataBatch:
    obs: jnp.ndarray           # [B, T, obs_dim]
    actions: jnp.ndarray       # [B, T, action_dim]
    rewards: jnp.ndarray       # [B, T]
    continues: jnp.ndarray     # [B, T]
    text_ids: jnp.ndarray | None      # [B, L]
    text_mask: jnp.ndarray | None     # [B, L]
    images: jnp.ndarray | None        # [B, H, W, C]
```

## Control System

### TrainingController

```python
controller = TrainingController(config)
controller.start()

while controller.should_continue(step):
    # Training step
    ...

    # Checkpoint
    if controller.should_checkpoint(step):
        controller.checkpoint_manager.save(step, params, opt_state)
```

### Features

- **Pause/Resume**: `request_pause()`, `request_resume()`
- **Signal Handling**: SIGTERM (preemption), SIGINT (user)
- **Preemption Detection**: GCE metadata polling
- **Intervention Queue**: LR override, phase forcing

## Multimodal Integration

### LanguageConditionedRSSM

```
Text ─────────────────────────┐
         │                    │
         ▼                    │
    TextEncoder               │
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────┐
│ HierarchicalCrossModalFusion (HiVG)     │
│                                          │
│    language_emb ───┬─── h (RSSM state)  │
│                    │                     │
│                ┌───▼───┐                │
│                │ Cross │ × N layers     │
│                │ Attn  │                │
│                └───────┘                │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ EntityGrounding (LED-WM style)          │
│                                          │
│    language_emb → colony attention      │
│    Maps to 7 specific colonies          │
└─────────────────────────────────────────┘
         │
         ▼
    h_conditioned (language-grounded state)
```

### Research Basis

- **SigLIP 2**: Vision-language encoder (chosen for JAX native support)
- **HiVG**: Hierarchical Visual Grounding (multi-layer fusion)
- **LED-WM**: Language-Entity-Driven World Models (entity grounding)

## Usage

### Basic Training

```python
import jax
from kagami.core.training.jax import (
    OrganismRSSM, OrganismRSSMConfig,
    Curriculum, CurriculumConfig,
    TrainingTelemetry,
    create_train_state, train_step,
)
from kagami.core.training.jax.data import DataPipeline, DataConfig

# Config
model_config = OrganismRSSMConfig()
curriculum_config = CurriculumConfig(num_chips=4, total_steps=100_000)

# Initialize
model = OrganismRSSM(model_config)
curriculum = Curriculum(curriculum_config)
telemetry = TrainingTelemetry()

# Data
data_config = DataConfig(global_batch_size=64)
pipeline = DataPipeline(data_config, jax.random.PRNGKey(42))

# Train state
key = jax.random.PRNGKey(0)
state = create_train_state(key, model, curriculum_config.baseline_lr)

# Training loop
for step in range(curriculum_config.total_steps):
    batch = pipeline.get_batch()
    state, metrics = train_step(state, batch, curriculum.get_loss_weights(step))

    # Telemetry
    result = telemetry.step(
        loss=metrics["total_loss"],
        kl=metrics["kl_loss"],
        grad_norm=metrics["grad_norm"],
        current_lr=curriculum_config.baseline_lr,
        step=step,
    )

    # Curriculum
    if curriculum.should_advance(step, metrics["total_loss"]):
        curriculum.advance(step)
        pipeline.set_phase(curriculum.current_phase.name.value)
```

## Testing

```bash
# Syntax validation (no JAX required)
python3 -c "import ast; ast.parse(open('rssm.py').read())"

# Full test (requires JAX)
pytest tests/training/test_jax_training.py -v
```

## References

- **DreamerV3**: https://arxiv.org/abs/2301.04104
- **SigLIP 2**: https://arxiv.org/abs/2409.04383
- **HiVG**: https://arxiv.org/abs/2311.04106
- **LED-WM**: https://arxiv.org/abs/2310.15821
- **v6e Failure Analysis**: Internal (Jan 6, 2026)

---

Created: January 8, 2026
Updated: January 9, 2026 - Added WARMUP, LANGUAGE phases, telemetry, control
