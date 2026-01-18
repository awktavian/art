# Kagami Training Infrastructure

**Apollo-Grade Training for OrganismRSSM World Model**

## Overview

This is THE single source of truth for all training operations. Like the Apollo program, we have:

1. **One mission control** — The `kagami-train` CLI
2. **One flight plan** — `config/training.yaml`
3. **One telemetry system** — Integrated monitoring dashboard
4. **One launch sequence** — Repeatable pipeline

## Quick Start

```bash
# Install training dependencies
pip install kagami[tpu]

# Run the full pipeline
kagami-train pipeline --config config/training.yaml

# Or run individual stages
kagami-train data generate                    # Generate training data
kagami-train tpu start                         # Start TPU training
kagami-train distill --student small           # Knowledge distillation
kagami-train export --checkpoint gs://... --format onnx  # Export model
kagami-train monitor                           # Live dashboard
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       kagami-train CLI                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐     │
│  │   Data    │  │    TPU    │  │  Distill  │  │  Export   │     │
│  │ Generator │→ │ Trainer   │→ │  Pipeline │→ │  Models   │     │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘     │
│       ↓              ↓              ↓              ↓             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 GCS (Single Source of Truth)             │    │
│  │  gs://kagami-training-data  →  gs://kagami-checkpoints  │    │
│  │                             →  gs://kagami-models       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Monitoring Dashboard                      │    │
│  │  Loss curves · KL health · Gradient norms · Phase progress│    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Configuration

All settings in `config/training.yaml`:

```yaml
gcs:
  data_bucket: gs://kagami-training-data
  checkpoint_bucket: gs://kagami-checkpoints
  model_bucket: gs://kagami-models

tpu:
  name: kagami-tpu
  zone: us-central2-b
  type: v6e-4

training:
  total_steps: 500000
  batch_size: 256
  learning_rate: 1.0e-4

curriculum:
  phases:
    - name: WARMUP
    - name: GEOMETRY
    - name: ROTATION
    - name: DYNAMICS
    - name: JOINT
    - name: GENERATION
    - name: LANGUAGE
```

## Pipeline Stages

### 1. Data Generation (`kagami-train data generate`)

Generates training data shards to GCS:
- **Genesis**: Physics puzzles (1000 shards)
- **QM9**: Molecular geometry (100 shards)
- **TreeOfLife**: Hierarchical taxonomy (200 shards)
- **Language**: Instruction-following (500 shards)

### 2. TPU Training (`kagami-train tpu start`)

Runs OrganismRSSM training on TPU v6e:
- 7-phase curriculum (WARMUP → LANGUAGE)
- Multi-horizon H-JEPA loss
- E8 lattice quantization
- Automatic checkpointing to GCS

### 3. Distillation (`kagami-train distill`)

Creates student models from teacher:
- **Small** (12M): Raspberry Pi / embedded
- **Base** (50M): Desktop / mobile
- **Large** (200M): Server API

### 4. Export (`kagami-train export`)

Converts to deployment formats:
- **ONNX**: Cross-platform inference
- **CoreML**: iOS/macOS (Neural Engine)
- **TFLite**: Android (GPU delegate)

## Monitoring

The integrated dashboard shows:
- Real-time loss/KL/gradient curves
- Curriculum phase progress
- TPU health and utilization
- Data quality diagnostics

```bash
kagami-train monitor
# Opens http://localhost:8765
```

## Deleted One-Offs

The following scripts were deleted and consolidated:

| Old Script | Replacement |
|------------|-------------|
| `scripts/generate_training_data.py` | `kagami-train data generate` |
| `scripts/verify_training_stability.py` | Integrated into training validator |
| `scripts/deploy/monitor_training.py` | `kagami-train monitor` |
| `scripts/smoke_test_pretraining.py` | `pytest tests/training/` |
| `scripts/visualization/parse_training_log.py` | Integrated into telemetry |
| `config/training_*.yaml` (4 files) | `config/training.yaml` |

## GCS Bucket Structure

```
gs://kagami-training-data/
├── genesis/v1/          # Physics puzzles
├── qm9/v1/              # Molecular data
├── tree_of_life/v1/     # Taxonomy
└── language/v1/         # Language data

gs://kagami-checkpoints/
├── organism-rssm/       # Training checkpoints (90-day lifecycle)
└── distillation/        # Distillation checkpoints

gs://kagami-models/
├── teacher/             # Full teacher model
├── student-small/       # 12M student
├── student-base/        # 50M student
├── student-large/       # 200M student
├── onnx/                # ONNX exports
├── coreml/              # CoreML exports
└── tflite/              # TFLite exports
```

## Philosophy

> "Like the Apollo mission, we have one mission control, one flight plan, one telemetry system."

- **Repeatable**: Same config = same results
- **Observable**: Integrated monitoring, not separate scripts
- **Centralized**: All state in GCS, nothing local
- **Declarative**: YAML config, not imperative scripts

---

Created: January 12, 2026
