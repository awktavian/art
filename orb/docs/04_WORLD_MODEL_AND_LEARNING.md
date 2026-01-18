# World Model and Learning Systems

**The Neural Architecture of Prediction: How Kagami Learns to Imagine**

---

## Overview

Kagami's world model is not a single neural network but an integrated system for predicting, imagining, and learning from experience. At its core lies the **OrganismRSSM** (Recurrent State-Space Model) -- a 2.6-4.1M parameter architecture (depending on enabled features) that learns compressed representations of reality and uses them to imagine futures before acting.

This document covers:
1. OrganismRSSM world model architecture
2. Multimodal encoding (video, audio, text)
3. The 7-phase curriculum based on catastrophe theory
4. Active inference and free energy minimization
5. Sleep-dependent memory consolidation
6. JAX/PyTorch training infrastructure

---

## 1. OrganismRSSM: The World Model

The world model is where perception becomes prediction. OrganismRSSM learns a compressed state space of the world, then uses it to imagine trajectories -- asking "what if I did X?" thousands of times per second.

### Architecture Diagram

```
+-------------------------------------------------------------------------+
|                         OrganismRSSM                                     |
|                     (2.6-4.1M parameters)                                |
+-------------------------------------------------------------------------+
|                                                                          |
|   +-------------+    +---------------+    +---------------------------+ |
|   | Observation | -> | Encoder       | -> | Colony Embeddings (7 x D) | |
|   | (64-dim)    |    | Dense -> GELU |    | + Position Bias           | |
|   +-------------+    +---------------+    +---------------------------+ |
|                                                   |                      |
|                                                   v                      |
|   +------------------------------------------------------------------+  |
|   |                    BlockGRU Dynamics Cell                         |  |
|   |                    (8 blocks x 512 hidden)                        |  |
|   |         Input: [z_flat, action_flat] -> h_prior                  |  |
|   +------------------------------------------------------------------+  |
|                               |                                          |
|                               v                                          |
|   +------------------------------------------------------------------+  |
|   |               SparseFanoAttention (Cross-Colony)                  |  |
|   |               Fano plane structure: 7 points, 7 lines             |  |
|   |               Only 3 colonies interact per attention head         |  |
|   +------------------------------------------------------------------+  |
|                               |                                          |
|                               v                                          |
|   +-----------------+  +------------------+  +------------------------+ |
|   | Prior Network   |  | Posterior Net    |  | E8 Latent Quantizer    | |
|   | h_prior -> prob |  | h_post -> prob   |  | 240 discrete classes   | |
|   +-----------------+  +------------------+  +------------------------+ |
|           |                    |                       |                 |
|           v                    v                       v                 |
|   +------------------------------------------------------------------+  |
|   |                    KL-Balanced Loss                               |  |
|   |        free_bits=0.1, dyn_weight=0.8, rep_weight=0.2             |  |
|   +------------------------------------------------------------------+  |
|                                                                          |
|   +------------------------------------------------------------------+  |
|   |                    Prediction Heads                               |  |
|   |  - obs_pred:      Dense(512) -> Dense(64)                        |  |
|   |  - reward_pred:   TwoHot (255 bins, [-20, 20])                   |  |
|   |  - continue_pred: Dense(1) (binary)                              |  |
|   +------------------------------------------------------------------+  |
|                                                                          |
+--------------------------------------------------------------------------+
```

### Key Components

| Component | Description | Parameters |
|-----------|-------------|------------|
| **obs_encoder** | Dense(512) -> GELU -> Dense(512) -> LayerNorm | 98K |
| **colony_emb** | 7 x 512 embedding table | 3.5K |
| **dynamics_cell** | BlockGRU with 8 blocks | 2.1M |
| **fano_attention** | SparseFanoAttention (7 -> 3 sparsity) | 0.4M |
| **prior/posterior** | Dense projection + softmax | 0.6M |
| **latent_emb** | E8 lattice: 240 x 32 | 7.7K |
| **decoder** | Dense(512) -> GELU -> Dense(64) | 0.4M |
| **reward_head** | TwoHot: Dense(255) | 0.1M |
| **continue_head** | Binary: Dense(1) | 0.5K |

### The Seven Colonies

The RSSM is organized into 7 specialized colonies, each handling different aspects of cognition:

```
          1 (Spark)
         /|\
        / | \
       4--+--2
      / \ | / \
     6---7|3---5
        (Crystal)

Lines (composition rules):
  (1,2,3), (1,4,5), (1,7,6), (2,4,6), (2,5,7), (3,4,7), (3,6,5)
```

| Colony | Symbol | Specialization | Catastrophe Type |
|--------|--------|----------------|------------------|
| Spark | Fire | Innovation and Creativity | A2 (Fold) |
| Forge | Hammer | Implementation Quality | A3 (Cusp) |
| Flow | Wave | Resilience and Recovery | A4 (Swallowtail) |
| Nexus | Chain | Integration and Connections | A5 (Butterfly) |
| Beacon | Tower | Architecture and Planning | D4+ (Hyperbolic) |
| Grove | Leaf | Documentation and Knowledge | D4- (Elliptic) |
| Crystal | Gem | Verification and Quality | D5 (Parabolic) |

### E8 Lattice Quantization

The stochastic latent space uses E8 lattice quantization with 240 discrete codes. This provides:

- **Mathematical elegance**: E8 is the densest sphere packing in 8 dimensions
- **Kissing number 240**: Each code has exactly 240 nearest neighbors
- **Natural action space**: 240 discrete options for decision-making

```
E8 Properties:
  Dimension: 8
  Kissing Number: 240
  Minimal Vectors: 240 (all same length)
  Symmetry Group: Weyl(E8), order 696,729,600
```

### SparseFanoAttention

Colony communication uses the Fano plane structure -- the projective plane over F2. Only colonies on the same "line" can directly attend to each other:

```python
# Fano lines encode which colonies can collaborate
FANO_LINES = [
    (0, 1, 2),  # Spark x Forge = Flow
    (0, 3, 4),  # Spark x Nexus = Beacon
    (0, 5, 6),  # Spark x Crystal = Grove
    (1, 3, 5),  # Forge x Nexus = Grove
    (1, 4, 6),  # Forge x Beacon = Crystal
    (2, 3, 6),  # Flow x Nexus = Crystal
    (2, 4, 5),  # Flow x Beacon = Grove
]
```

This sparsity reduces computation while enforcing meaningful collaboration patterns.

---

## 2. Multimodal Encoding

Kagami processes video, audio, and text through specialized encoders, then fuses them for world model input.

### Multimodal Pipeline Architecture

```
+-----------------------------------------------------------------------------+
|                          INPUT MODALITIES                                    |
+----------------------+----------------------+--------------------------------+
|       VIDEO          |       AUDIO          |           TEXT                 |
|   [B, T, H, W, C]    |    [B, samples]      |        [B, L]                  |
|        |             |         |            |          |                     |
|        v             |         v            |          v                     |
|  +-----------+       |  +-----------+       |  +-----------+                 |
|  | Spatiotem-|       |  | Mel-Spec  |       |  | Token     |                 |
|  | poral Enc |       |  | Extraction|       |  | Embedding |                 |
|  +-----+-----+       |  +-----+-----+       |  +-----+-----+                 |
|        |             |        |             |        |                       |
|        v             |        v             |        v                       |
|  +-----------+       |  +-----------+       |  +-----------+                 |
|  | Vector    |       |  | Audio     |       |  | Positional|                 |
|  | Quantizer |       |  | Transformer|      |  | Encoding  |                 |
|  | (VQ-VAE)  |       |  | (AST)     |       |  +-----+-----+                 |
|  +-----+-----+       |  +-----+-----+       |        |                       |
|        |             |        |             |        |                       |
|   z_video            |   z_audio            |   z_text                       |
|   [B, T', D]         |   [B, N, D]          |   [B, L, D]                    |
+--------+-------------+--------+-------------+--------+-----------------------+
         |                      |                      |
         +----------------------+----------------------+
                                |
                                v
+-----------------------------------------------------------------------------+
|                        MULTIMODAL FUSION                                     |
|                                                                              |
|  +-----------------------------------------------------------------------+  |
|  | Modality Projection + Modality Embeddings                             |  |
|  | - Video: Dense(D, fused_dim) + learnable video_mod_emb               |  |
|  | - Audio: Dense(D, fused_dim) + learnable audio_mod_emb               |  |
|  | - Text:  Dense(D, fused_dim) + learnable text_mod_emb                |  |
|  +-----------------------------------------------------------------------+  |
|                                  |                                           |
|                                  v                                           |
|  +-----------------------------------------------------------------------+  |
|  | Cross-Modal Transformer (4 layers)                                    |  |
|  | - Concatenate all modality tokens                                     |  |
|  | - Self-attention across modalities                                    |  |
|  | - FFN with GELU                                                       |  |
|  +-----------------------------------------------------------------------+  |
|                                  |                                           |
|                             z_fused                                          |
|                            [B, M, D]                                         |
+-------------------------------+----------------------------------------------+
                                |
                                v
                        +---------------+
                        | OrganismRSSM  |
                        | (7 Colonies)  |
                        +---------------+
```

### Video Tokenizer (Genie-Style)

The video encoder uses spatiotemporal VQ-VAE inspired by DeepMind's Genie:

```python
VideoTokenizerConfig(
    image_size=224,
    patch_size=16,          # Spatial patch size
    temporal_patch=4,       # Frames per temporal patch
    codebook_size=8192,     # VQ codebook size
    codebook_dim=512,       # Embedding dimension
)
```

**Key Features:**
- **Spatiotemporal patches**: 16x16 spatial, 4-frame temporal
- **Vector quantizer**: 8K codes, 512-dim with EMA updates
- **Latent Action Model (LAM)**: Infers actions from video without labels

### Audio Encoder (AST-Style)

Audio uses Audio Spectrogram Transformer architecture:

```python
AudioEncoderConfig(
    sample_rate=16000,
    n_mels=128,            # Mel spectrogram bands
    hidden_dim=768,
    num_layers=12,
)
```

**Key Features:**
- **Mel spectrogram**: 128 bands, 10ms hop
- **Patch embedding**: 16x16 patches on spectrogram
- **Audio-visual alignment**: Contrastive loss for cross-modal learning

### E2E Pipeline Performance (CPU, batch=4)

| Stage | Latency |
|-------|---------|
| Audio Spectrogram | 0.65ms |
| Audio Encoder | 0.09ms |
| Video Tokenizer | 0.33ms |
| RSSM Forward | 7.91ms |
| **E2E (JIT fused)** | **0.40ms** |

---

## 3. The 7-Phase Curriculum

Training follows a 7-phase curriculum that progressively activates colonies and adjusts loss weights. This is grounded in catastrophe theory -- each phase corresponds to a different topological structure of the learning landscape.

### Curriculum Progression

```
Phase 1: WARMUP         Phase 2: GEOMETRY       Phase 3: ROTATION
[Colony 1]              [Colonies 1,2]          [Colonies 1,2,3]
    *                       * *                     * * *
    |                       |/                      |X|
    v                       v                       v
Simple patterns         2D structure            3D rotations

Phase 4: DYNAMICS       Phase 5: JOINT          Phases 6-7: GENERATION/LANGUAGE
[Colonies 1-4]          [All 7 colonies]        [All 7 + multimodal]
  * * * *                 * * * * * * *          Full world model
  |X|X|X|                 |X|X|X|X|X|X|          Video + Audio + Text
    v                           v                       v
Temporal dynamics       Full integration        Complete capability
```

### Phase Details

| Phase | Steps | Colonies | KL Beta | E8 | Fano | H-JEPA | Datasets |
|-------|-------|----------|---------|-----|------|--------|----------|
| **WARMUP** | 0-2K | [1] | 0.1 | 0 | 0 | 0 | Genesis |
| **GEOMETRY** | 2K-10K | [1,2] | 1.0 | 0.5 | 0 | 0 | Genesis, TreeOfLife |
| **ROTATION** | 10K-30K | [1,2,3] | 1.0 | 0.3 | 0.01 | 0 | Genesis, QM9 |
| **DYNAMICS** | 30K-100K | [1,2,3,4] | 1.0 | 0.1 | 0.05 | 0.1 | Genesis, QM9 |
| **JOINT** | 100K-200K | all 7 | 1.0 | 0.05 | 0.1 | 0.2 | All mixed |
| **GENERATION** | 200K-350K | all 7 | 1.0 | 0.01 | 0.1 | 0.3 | Genesis |
| **LANGUAGE** | 350K-500K | all 7 | 1.0 | 0.01 | 0.1 | 0.3 | Genesis, Gemini |

### Colony Masking

Each phase activates only specific colonies. Inactive colonies have hidden states and gradients masked:

```python
# Example: Phase GEOMETRY activates colonies 1 and 2
colony_mask = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

# Applied to hidden states
colony_mask_3d = colony_mask[None, :, None]  # [1, 7, 1] for broadcast
h = h * colony_mask_3d  # Masked hidden states
z = z * colony_mask_3d  # Masked latents
```

### Catastrophe-Aware Training

Each colony corresponds to a different catastrophe type from Thom's classification:

| Catastrophe | Colony | Learning Characteristic |
|-------------|--------|------------------------|
| Fold (A2) | Spark | Quick jumps, binary discoveries |
| Cusp (A3) | Forge | Bistable states, requires clear signal |
| Swallowtail (A4) | Flow | Smooth transitions, healing gradient |
| Butterfly (A5) | Nexus | Multi-stable, connection building |
| Hyperbolic (D4+) | Beacon | Global overview, strategic learning |
| Elliptic (D4-) | Grove | Deep exploration, knowledge accumulation |
| Parabolic (D5) | Crystal | Highest complexity, verification mastery |

### Phase-Aware Loss Adjustment

Near phase boundaries, learning rates and loss weights are adjusted for stability:

```python
def select_curriculum_phase(colony_state: ColonyState) -> CurriculumPhase:
    """Select training phase based on catastrophe distance."""
    d = colony_state.catastrophe_distance

    if d > STABLE_THRESHOLD:
        # Far from boundary: aggressive learning OK
        return CurriculumPhase.EXPLORATION
    elif d > CAUTION_THRESHOLD:
        # Approaching boundary: careful refinement
        return CurriculumPhase.REFINEMENT
    else:
        # Near boundary: stability-focused learning
        return CurriculumPhase.STABILIZATION
```

---

## 4. Active Inference and Free Energy

Kagami operates under the Free Energy Principle from neuroscience. Rather than passive prediction, the system actively minimizes surprise by both updating beliefs AND taking action.

### The Free Energy Principle

```
F = E[log q(s)] - E[log p(o,s)]
  = Complexity - Accuracy

Minimize F by:
  1. Updating beliefs q(s) to match observations (perception)
  2. Taking actions to make observations match predictions (action)
```

### RSSM as Active Inference

The OrganismRSSM implements active inference through:

1. **Prior Network**: Predicts what SHOULD happen (p(o|s,a))
2. **Posterior Network**: Infers what IS happening (q(s|o))
3. **KL Divergence**: Measures surprise between prior and posterior
4. **Action Selection**: Chooses actions to minimize expected free energy

```
                    +----------------+
                    |   Observation  |
                    +-------+--------+
                            |
                            v
    +-------------------+   |   +-------------------+
    |   Prior p(s'|s,a) | <-+-> | Posterior q(s|o) |
    +-------------------+       +-------------------+
            |                           |
            |     KL Divergence         |
            +----------->+<-------------+
                         |
                         v
                  +-------------+
                  | Free Energy |
                  |   = Surprise |
                  +-------------+
                         |
                         v
              +--------------------+
              | Action Selection   |
              | (minimize EFE)     |
              +--------------------+
```

### Expected Free Energy (EFE)

For goal-directed behavior, Kagami uses Expected Free Energy:

```python
def compute_expected_free_energy(
    predicted_state,
    preferred_outcome,
    epistemic_value  # Curiosity bonus
):
    # Pragmatic value: Does this achieve my goals?
    pragmatic = -log_likelihood(predicted_state, preferred_outcome)

    # Epistemic value: Does this reduce uncertainty?
    epistemic = information_gain(predicted_state)

    return pragmatic - beta * epistemic
```

This balances:
- **Exploitation**: Achieving preferred outcomes
- **Exploration**: Reducing uncertainty about the world

### KL-Balanced Loss

The training loss uses DreamerV3's KL balancing:

```python
# Balanced KL prevents posterior collapse AND prior drift
kl_balanced = (
    kl_dyn_weight * KL(sg(posterior) || prior)    # Dynamics loss
  + kl_rep_weight * KL(posterior || sg(prior))    # Representation loss
)

# With free nats to prevent over-regularization
kl_loss = max(kl_balanced, free_bits)
```

---

## 5. Sleep-Dependent Memory Consolidation

> **Status: Aspirational Architecture**
>
> The sleep consolidation system described below represents the target design. Core infrastructure exists (episodic buffer, semantic store interfaces), but the full NREM/REM-like replay and generalization phases are not yet implemented. This section documents the intended behavior.

Just as biological brains consolidate memories during sleep, Kagami will run consolidation during idle periods. This transfers ephemeral experiences into durable knowledge.

### The Two-Stage Model

```
Acquisition Phase (Wake)          Consolidation Phase (Sleep)
        |                                    |
        v                                    v
   New Experience ----------------------> Episodic Buffer (fast)
                                                 |
                                                 v (replay)
                                         Semantic Store (slow)
```

### Consolidation Phases

#### Phase 1: Preparation

```python
async def prepare_consolidation(self):
    """Enter sleep mode."""
    # Stop accepting new experiences
    self._accepting_new = False

    # Identify consolidation candidates
    candidates = await self._find_consolidation_candidates()

    # Estimate duration
    duration = len(candidates) * CONSOLIDATION_TIME_PER_MEMORY
    return ConsolidationPlan(candidates, duration)
```

#### Phase 2: Replay (NREM-like)

Slow-wave replay strengthens connections:

```python
async def replay_and_consolidate(self, memories: list[Memory]):
    """Replay memories for consolidation."""
    for memory in memories:
        # Reactivate memory representation
        activation = self._reactivate(memory)

        # Find related semantic knowledge
        related = await self._find_related(memory)

        # Strengthen connections
        for node in related:
            self._strengthen_connection(memory, node)

        # Update importance
        memory.importance = self._compute_importance(memory)
```

#### Phase 3: Generalization (REM-like)

Dream-like recombination finds abstract patterns:

```python
async def generalize_patterns(self, patterns: list[Pattern]):
    """Generalize through dreaming."""
    for pattern in patterns:
        # Generate variations
        variations = self._generate_variations(pattern)

        # Test against history
        for var in variations:
            score = await self._test_against_history(var)
            if score > pattern.confidence:
                pattern.update(var)

        # Abstract common structure
        pattern.abstract = self._extract_abstract_form(pattern)
```

#### Phase 4: Pruning

Forgetting low-value memories:

```python
async def prune_memories(self):
    """Synaptic homeostasis."""
    for memory in self._memories:
        value = (
            memory.importance * 0.4 +
            memory.recency * 0.3 +
            memory.access_frequency * 0.3
        )

        if value < PRUNING_THRESHOLD:
            await self._prune(memory,
                keep_summary=value > SUMMARY_THRESHOLD)
```

### Dream Visualization

During consolidation, the system visualizes its "dreaming":

```
+-----------------------------------------------------------+
|                    DREAMING...                             |
|                                                            |
|    o---o---o     Pattern: friday_movie                    |
|     \   /        Confidence: 0.78 -> 0.85                 |
|      o------o    Connections: +3                          |
|     /   \                                                  |
|    o---o---o     Variations tested: 12                    |
|                  Best variation: time +/- 30min           |
|                                                            |
|   ########....  Progress: 60%                             |
+-----------------------------------------------------------+
```

### Consolidation Schedule

**Nightly Consolidation:**
```
23:00 - Prepare (identify candidates)
23:05 - Phase 1: Replay episodic memories
00:00 - Phase 2: Generalize patterns
01:00 - Phase 3: Prune low-value memories
02:00 - Phase 4: Optimize indices
03:00 - Complete, resume accepting memories
```

**Incremental Consolidation:**
- Mini-consolidations every 2 hours during low activity
- Focus on recent memories only
- No full generalization pass

---

## 6. JAX/PyTorch Training Infrastructure

Training runs on JAX for TPU acceleration with full PyTorch feature parity for development.

### Training Pipeline

```
+-----------------------------------------------------------------------------+
|                           TRAINING INFRASTRUCTURE                            |
+-----------------------------------------------------------------------------+
|                                                                              |
|   +---------------+    +------------------+    +-------------------------+  |
|   | Data Pipeline |    | Model + Optimizer|    | Distributed Training    |  |
|   +---------------+    +------------------+    +-------------------------+  |
|   | Genesis Engine|    | OrganismRSSM     |    | JAX Mesh Sharding       |  |
|   | TFRecords     |    | AdamW + Schedule |    | TPU v6e-4 pods          |  |
|   | Streaming     |    | Gradient Accum   |    | Buffer Donation         |  |
|   +-------+-------+    +--------+---------+    +-----------+-------------+  |
|           |                     |                          |                 |
|           v                     v                          v                 |
|   +---------------------------------------------------------------------+   |
|   |                         Training Step                                |   |
|   |  @jax.jit(donate_argnums=(0,))                                      |   |
|   |  def train_step(state, batch, key, phase_idx):                      |   |
|   |      loss, grads = jax.value_and_grad(compute_loss)(...)            |   |
|   |      return state.apply_gradients(grads=grads), metrics             |   |
|   +---------------------------------------------------------------------+   |
|                                    |                                         |
|                                    v                                         |
|   +---------------------------------------------------------------------+   |
|   |                          Profiling                                   |   |
|   |  - JAX Profiler (trace steps 100, 500, 1K, 5K, 10K)                 |   |
|   |  - TensorBoard integration                                          |   |
|   |  - Memory sampling every 100 steps                                  |   |
|   +---------------------------------------------------------------------+   |
|                                                                              |
+------------------------------------------------------------------------------+
```

### Loss Composition

```python
total_loss = (
    recon_loss                         # MSE(obs_pred, obs_target)
  + kl_beta * kl_balanced              # Balanced KL with free nats
  + reward_weight * reward_loss        # TwoHot (255 bins)
  + 0.1 * continue_loss                # Binary CE
  + hjepa_weight * hjepa_loss          # Multi-horizon [1, 4, 16]
  + fano_weight * fano_loss            # Colony coordination
  + e8_weight * e8_loss                # E8 commitment
  + 0.01 * stability_loss              # Temporal smoothness
)
```

### Multi-Horizon H-JEPA

Hierarchical prediction at multiple temporal horizons:

```python
HJEPA_HORIZONS = [1, 4, 16]  # Steps ahead

def compute_multi_horizon_hjepa_loss(h, horizons=[1, 4, 16]):
    total_loss = 0
    for horizon in horizons:
        target = h[:, horizon:, :]
        pred = h[:, :-horizon, :]
        loss = jnp.mean((pred - jax.lax.stop_gradient(target))**2)
        total_loss += loss / len(horizons)
    return total_loss
```

### XLA Optimizations

```python
# Compiler flags for TPU efficiency
os.environ.setdefault("XLA_FLAGS", " ".join([
    "--xla_gpu_enable_latency_hiding_scheduler=true",
    "--xla_gpu_enable_async_collectives=true",
    "--xla_gpu_enable_highest_priority_async_stream=true",
]))
os.environ.setdefault("TPU_MEGACORE", "megacore_dense")

# Buffer donation for memory reuse
@partial(jax.jit, static_argnums=(3,), donate_argnums=(0,))
def train_step(state, batch, key, phase_idx):
    ...

# bfloat16 for observations
batch["obs"] = jnp.array(obs, dtype=jnp.bfloat16)
```

### PyTorch - JAX Feature Parity

| Category | PyTorch Classes | JAX Classes | Parity |
|----------|----------------|-------------|--------|
| Core RSSM | 5 | 5 | 100% |
| Encoding | 12 | 12 | 100% |
| Generation | 8 | 8 | 100% |
| Temporal | 15 | 15 | 100% |
| Actor-Critic | 4 | 4 | 100% |
| Losses | 8 | 8 | 100% |
| **TOTAL** | **86** | **86** | **100%** |

### Temporal Dynamics Backends

| Backend | Class | Complexity | Use Case |
|---------|-------|------------|----------|
| **Transformer** | `TransformerDynamics` | O(n^2) | Best quality, parallel training |
| **Mamba** | `MambaDynamics` | O(n) | Long sequences, efficient |
| **GRU** | (baseline) | O(n) | Simple baseline |
| **Diffusion** | `DiffusionDynamics` | O(n*T) | DiT/Sora-style generation |

### Benchmark Results (Local CPU)

| Metric | Value |
|--------|-------|
| Steps/sec | 1.44 |
| Samples/sec | 92 |
| Tokens/sec | 2,949 |
| Avg step time | 694ms |
| Loss convergence | 1.06 -> 0.13 (87% reduction) |
| Gradient norm | 1.47 (healthy) |

---

## Generation Capabilities

The world model enables generative output -- imagining video and audio from internal states.

### Video + Audio Generation Pipeline

```
World Model State (h)
         |
         +-----------------------------+
         |                             |
         v                             v
+---------------------+       +---------------------+
| VideoDynamicsModel  |       | AudioDecoder        |
| (Autoregressive)    |       | (HiFi-GAN style)    |
|                     |       |                     |
| h_t + a_t -> z_{t+1}|       | h -> mel -> waveform|
| z_{t+1} -> frame    |       |                     |
+---------------------+       +---------------------+
         |                             |
         v                             v
   Generated Video                Generated Audio
   [B, T, H, W, C]                [B, samples]
```

### Unified Generation API

```python
from kagami.core.training.jax import UnifiedGenerator, GenerationConfig

config = GenerationConfig(
    video_config=VideoGeneratorConfig(
        latent_dim=512,
        frame_height=224,
        frame_width=224,
    ),
    audio_config=AudioGeneratorConfig(
        latent_dim=512,
        mel_channels=128,
        upsample_rates=(8, 8, 2, 2),  # 256x upsampling
    ),
)

unified = UnifiedGenerator(config)

# Generate both from world model states
output = unified.apply(
    params,
    h_sequence,  # [B, T, D] from RSSM
    actions,     # [B, T-1]
    method=unified.generate_both
)

video = output.video.frames    # [B, T, H, W, C]
audio = output.audio.waveform  # [B, samples]
```

---

## Summary

The world model and learning systems form the cognitive core of Kagami:

1. **OrganismRSSM**: 7-colony architecture with E8 quantization and Fano attention
2. **Multimodal Encoding**: Unified video/audio/text understanding
3. **Catastrophe-Aware Curriculum**: 7-phase progressive training
4. **Active Inference**: Free energy minimization for perception and action
5. **Memory Consolidation**: Sleep-dependent learning and forgetting
6. **JAX/PyTorch Parity**: Production training infrastructure

The system doesn't just predict -- it imagines, plans, learns, dreams, and consolidates. It minimizes surprise not by being passive, but by actively shaping its world to match its beliefs.

---

## References

1. **Hafner, D. et al. (2020)** -- "Dream to Control: Learning Behaviors by Latent Imagination" (DreamerV2)
2. **Hafner, D. et al. (2023)** -- "Mastering Diverse Domains through World Models" (DreamerV3)
3. **Friston, K. (2010)** -- "The free-energy principle: a unified brain theory?"
4. **Bengio, Y. et al. (2009)** -- "Curriculum Learning"
5. **Diekelmann, S. & Born, J. (2010)** -- "The memory function of sleep"
6. **Viazovska, M. (2016)** -- "The sphere packing problem in dimension 8"
7. **DeepMind (2024)** -- "Genie: Generative Interactive Environments"

---

*Last updated: January 12, 2026*
*Full PyTorch to JAX feature parity achieved.*
