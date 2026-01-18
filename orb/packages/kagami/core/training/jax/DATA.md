# Training Data Specification

**Complete guide to training data sources, formats, and curriculum.**

## 📊 Overview

```
                           TRAINING DATA ARCHITECTURE
                           =========================

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                      DATA SOURCES (by priority)                          │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                          │
    │  🎮 GENESIS (Primary 50-60%)        📐 QM9 (15-25%)                      │
    │  ├── JEPA puzzles (dynamics)        └── 130K molecules                   │
    │  ├── Generation (control)               ├── 3D positions [N, 3]          │
    │  └── Render (video frames)              ├── Atom types [N]               │
    │                                         └── Edge indices [E, 2]          │
    │                                                                          │
    │  🌳 TreeOfLife (10-20%)             📚 Language (10-30%)                 │
    │  └── NCBI taxonomy                  └── Instruction following             │
    │      ├── Node depths [N]                ├── Text tokens [L]              │
    │      ├── Parent indices [N]             └── Attention mask [L]           │
    │      └── Adjacency matrix [N, N]                                         │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        CURRICULUM SAMPLER                                │
    │                                                                          │
    │  Phase → Data Weights → Weighted Random Selection → Batch                │
    │                                                                          │
    │  WARMUP:     jepa=100%                                                   │
    │  GEOMETRY:   jepa=60%, qm9=20%, tree=20%                                │
    │  ROTATION:   jepa=50%, qm9=20%, tree=20%, gen=10%                       │
    │  DYNAMICS:   jepa=45%, qm9=20%, tree=20%, gen=15%                       │
    │  JOINT:      jepa=35%, qm9=15%, tree=15%, gen=35%                       │
    │  GENERATION: gen=50%, jepa=25%, qm9=15%, tree=10%                       │
    │  LANGUAGE:   jepa=30%, lang=30%, inst=20%, qm9=10%, tree=10%            │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘
```

---

## 🎮 GENESIS Physics Puzzles (Primary Source)

**Infinite simulation stream from Genesis physics engine.**

### JEPA Mode (Dynamics Learning)

| Puzzle Type | Description | Concepts |
|-------------|-------------|----------|
| `free_fall_bounce` | Object falling with gravity and bouncing | Gravity, collision, energy |
| `two_body_collision_1d` | Two objects approaching and colliding | Momentum, elasticity |
| `spring_mass` | Mass on spring oscillating | Harmonic motion, periodicity |
| `damped_motion` | Motion with friction/damping | Energy dissipation |
| `impulse_response` | Object responds to force impulses | Causality, control |

### Generation Mode (Control Learning)

| Puzzle Type | Description | Concepts |
|-------------|-------------|----------|
| `goal_reach_with_barrier` | Navigate to goal avoiding obstacles | Path planning, CBF |
| `goal_reach_switching` | Goal changes during episode | Adaptation, replanning |

### Data Format

```python
{
    "state_t": Tensor[T, D],           # [32, 64] State sequence
    "action_t": Tensor[T, A],          # [32, 8]  Action sequence (E8)
    "state_t_plus_1": Tensor[T, D],    # [32, 64] Next state
    "rewards": Tensor[T],              # [32]     Sparse rewards
    "continues": Tensor[T],            # [32]     Episode continuation

    # Optional rendering (enable_rendering=True)
    "frames_t": Tensor[T, 3, H, W],    # [32, 3, 128, 128] RGB frames
    "frames_t_plus_1": Tensor[T, 3, H, W],

    # Metadata
    "fingerprint": str,                # Unique sample ID
    "caption": str,                    # Dynamic physics description
    "metadata": {
        "puzzle_type": str,
        "difficulty": float,           # 0.0-1.0
        "episode_id": int,
        "physics_dt": float,           # 1/60 default
        "backend": "real_genesis",
    }
}
```

### State Vector Layout

```
state[D=64] = [
    action[0:8],      # Previous action (E8 lattice)
    goal[8:11],       # Goal position (xyz) for generation mode
    physics[11:64],   # Flattened physics state:
                      #   - Object positions [N, 3]
                      #   - Object velocities [N, 3]
                      #   - Object orientations [N, 4]
                      #   - Contact forces
]
```

### Throughput Optimization

```python
# Amortized simulation: many samples per physics step
buffer_steps = 8192       # Rolling replay buffer
samples_per_step = 256    # Training windows per physics step
reset_interval = 2048     # Reset puzzle every N steps

# Result: 256 training samples per Genesis.step() call
# Throughput: ~10,000 samples/second on M3 Ultra
```

---

## 📐 QM9 Molecular Geometry

**130,000 molecular structures for SE(3) equivariance learning.**

### Purpose

- Learn 3D spatial structure
- SE(3) rotational equivariance
- Gauge theory grounding
- E8 lattice geometry

### Data Format

```python
{
    # Core geometry
    "positions": Tensor[N, 3],         # Atom positions in Angstroms
    "atom_types": Tensor[N],           # Atomic numbers (6=C, 7=N, 8=O, etc.)
    "edge_index": Tensor[2, E],        # Bond connectivity

    # Properties (regression targets)
    "dipole_moment": float,            # Debye
    "polarizability": float,           # Bohr³
    "HOMO": float,                     # eV
    "LUMO": float,                     # eV
    "gap": float,                      # HOMO-LUMO gap
    "zpve": float,                     # Zero-point vibrational energy

    # Metadata
    "smiles": str,                     # Molecular SMILES
    "num_atoms": int,                  # N (typically 3-29)
}
```

### Normalization to RSSM Format

```python
# QM9 → state_t mapping:
# 1. Flatten positions: [N, 3] → [N*3]
# 2. Pad to obs_dim: [N*3] → [obs_dim]
# 3. Add atom embedding: one-hot [N, num_elements]

def normalize_qm9(sample):
    pos = sample["positions"].reshape(-1)  # [N*3]
    state = pad_to_dim(pos, obs_dim)
    return {"state_t": state, ...}
```

---

## 🌳 TreeOfLife Hierarchical Structures

**Phylogenetic trees from NCBI taxonomy for hyperbolic embedding learning.**

### Purpose

- Hyperbolic geometry (H¹⁴)
- Hierarchical reasoning
- Tree structure understanding
- Parent-child relationships

### Data Format

```python
{
    # Tree structure
    "node_depths": Tensor[N],          # Depth of each node (root=0)
    "parent_indices": Tensor[N],       # Parent node for each node (-1 for root)
    "adjacency": Tensor[N, N],         # Sparse adjacency matrix

    # Node properties
    "node_names": List[str],           # Taxonomic names
    "node_ranks": List[str],           # kingdom/phylum/class/order/...

    # Hyperbolic embedding target
    "poincare_coords": Tensor[N, 2],   # 2D Poincaré disk embedding

    # Metadata
    "subtree_root": str,               # Root taxon name
    "num_nodes": int,
}
```

### Hierarchical Statistics

| Rank | Count | Avg Depth |
|------|-------|-----------|
| Kingdom | 7 | 0 |
| Phylum | 89 | 1 |
| Class | 397 | 2 |
| Order | 1,267 | 3 |
| Family | 10,000+ | 4 |
| Genus | 100,000+ | 5 |
| Species | 2,000,000+ | 6 |

---

## 📚 Language Data

**Instruction-following and language grounding (LANGUAGE phase).**

### Sources

| Dataset | Size | Purpose |
|---------|------|---------|
| Flan-T5 instructions | 15M | Instruction following |
| ShareGPT | 90K | Conversation |
| OpenAssistant | 160K | Multi-turn dialogue |
| LAION-COCO | 600M | Vision-language pairs |

### Data Format

```python
{
    # Text input
    "text_ids": Tensor[L],             # Token IDs
    "text_mask": Tensor[L],            # Attention mask

    # Optional paired data
    "images": Tensor[H, W, 3],         # Paired image (vision-language)
    "audio": Tensor[T_a, F],           # Paired audio (speech)

    # Instruction format
    "instruction": str,                # User instruction
    "response": str,                   # Target response

    # Metadata
    "source": str,                     # Dataset source
    "language": str,                   # ISO language code
}
```

---

## 🔄 Multimodal Integration

**How different modalities combine in training.**

### Modality Encoders

| Modality | Encoder | Dimension | Projection |
|----------|---------|-----------|------------|
| Text | E5-large-v2 | 1024 → 768 | MLP ×3 |
| Vision | SigLIP 2 large | 1024 → 768 | MLP ×3 |
| Audio | Whisper large-v3 | 1280 → 768 | MLP ×3 |
| State | E8 encoder | 64 → 768 | MLP ×2 |

### Fusion Architecture

```
    Text ──────┐
               │
    Vision ────┼──► Cross-Modal Attention ──► Fused [768]
               │    (16 heads, 4 layers)
    Audio ─────┘
               │
               ▼
    ┌─────────────────────────┐
    │   Hierarchical Fusion   │
    │   (HiVG-style)          │
    │   + LoRA (rank=32)      │
    │   + Modality Gating     │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │   Entity-Level Attn     │
    │   (7 colonies)          │
    └────────────┬────────────┘
                 │
                 ▼
           RSSM Hidden [768]
```

---

## 📏 Model Sizes and Memory

### Parameter Counts

| Size | deter | stoch | heads | params | Memory (B=256) |
|------|-------|-------|-------|--------|----------------|
| Small | 256 | 16 | 4 | ~12M | ~2GB |
| Base | 384 | 32 | 8 | ~50M | ~8GB |
| **Large** | **768** | **64** | **16** | **~200M** | **~32GB** |
| XL | 1024 | 96 | 16 | ~500M | ~80GB |

### TPU v6e-4 Fit

```
TPU v6e-4: 4 chips × 48GB HBM2e = 192GB total

Large model (200M params):
- Model weights: ~800MB (FP32)
- Activations (B=256, T=32): ~20GB
- Gradients: ~800MB
- Optimizer state (AdamW): ~2.4GB
- Total: ~24GB ✓ (fits with headroom)

Effective batch size with gradient accumulation:
- Per-device batch: 64
- Accumulation steps: 4
- Effective batch: 64 × 4 × 4 chips = 1024
```

---

## 🎯 Knowledge Distillation Pipeline

**Train large teacher → Distill to smaller students.**

### Distillation Loss

```python
L_distill = α × L_student + (1-α) × L_KD

where:
  L_KD = T² × KL(p_teacher/T || p_student/T)
  T = temperature (typically 4.0)
  α = 0.1 (10% hard labels, 90% soft labels)
```

### Distillation Targets

| Component | Teacher Output | Student Target |
|-----------|---------------|----------------|
| Posterior | p(z\|h, o) [B, 7, 240] | Match distribution |
| Hidden | h [B, 7, 768] | L2 projection |
| HJEPA | h_pred [B, 7, 768] | L2 projection |
| Observations | ô [B, 64] | L2 (symlog) |
| Rewards | r_logits [B, 255] | KL (TwoHot) |

### Student Sizes for Deployment

| Target | Size | deter | Latency | Use Case |
|--------|------|-------|---------|----------|
| **Edge** | Small | 256 | 10ms | Raspberry Pi, Mobile |
| **Desktop** | Base | 384 | 20ms | MacBook, PC |
| **Server** | Large | 768 | 50ms | Cloud API |
| **Research** | XL | 1024 | 100ms | LMARENA |

### Distillation Schedule

```python
# Phase 1: Response-based distillation (10K steps)
# Match final outputs only
distill_outputs(teacher, student, batch)

# Phase 2: Feature-based distillation (40K steps)
# Match intermediate representations
distill_features(teacher, student, batch, layer_map)

# Phase 3: Relational distillation (50K steps)
# Match attention patterns and colony interactions
distill_relations(teacher, student, batch)
```

---

## 🧪 Data Validation

### Batch Validation

```python
def validate_batch(batch: dict) -> bool:
    """Validate batch has required fields."""
    return any(key in batch for key in [
        "state_t",       # Genesis dynamics
        "positions",     # QM9 geometry
        "node_depths",   # TreeOfLife hierarchy
        "text_ids",      # Language
    ])
```

### Shape Verification

```python
# Required shapes for Large model (B=256, T=32)
assert batch["state_t"].shape == (256, 32, 128)
assert batch["actions"].shape == (256, 32, 8)
assert batch["rewards"].shape == (256, 32)
assert batch["continues"].shape == (256, 32)

# Optional multimodal
if "text_ids" in batch:
    assert batch["text_ids"].shape == (256, 512)
if "images" in batch:
    assert batch["images"].shape == (256, 384, 384, 3)
```

---

## 🚀 Quick Start

```python
from kagami.core.training.jax.configs.large_tpu import get_large_model_config
from kagami.core.training.jax.data import create_data_pipeline, DataConfig

# Get large model config
config = get_large_model_config()

# Create data pipeline
data_config = DataConfig(
    source_type="synthetic",  # or "tfds", "gcs"
    global_batch_size=256,
    sequence_length=32,
    obs_dim=128,
    include_text=True,
    include_images=True,
    curriculum_phase="GEOMETRY",
)

pipeline = create_data_pipeline(data_config)

# Training loop
for batch in pipeline:
    # batch.obs: [256, 32, 128]
    # batch.actions: [256, 32, 8]
    # batch.text_ids: [256, 512] (if enabled)
    train_step(state, batch, key, weights)
```

---

## 📁 Data Directory Structure

```
data/
├── genesis/           # Genesis cache (auto-generated)
│   └── puzzles.db
├── qm9/              # QM9 molecular data
│   ├── qm9.xyz       # Raw structures
│   └── processed/    # Cached tensors
├── tree_of_life/     # NCBI taxonomy
│   ├── nodes.dmp     # Node definitions
│   ├── names.dmp     # Node names
│   └── processed/    # Cached trees
└── language/         # Language data
    ├── flan/
    ├── sharegpt/
    └── openassistant/
```

---

*Training data is the substrate of intelligence. Quality data → Quality model.*
