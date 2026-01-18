# Adaptive Data Mixing: Design Rationale

**Created: January 12, 2026**

## Why Adaptive > Static

Static curriculum mixing has fundamental limitations:

### The Problem with Static Weights

```yaml
# Traditional static mixing
GEOMETRY:
  jepa: 0.6
  qm9: 0.2
  tree_of_life: 0.2
```

**Issues:**
1. **Convergence Asymmetry**: QM9 (molecular) may converge 3x faster than JEPA
2. **Wasted Compute**: After QM9 converges, 20% of compute is wasted
3. **Underfitting**: JEPA may need 80% to achieve same quality
4. **Run Variability**: Optimal mix varies per random seed, initialization

### The Adaptive Solution

```python
# Adaptive: weights respond to training dynamics
mixer.update(
    per_source_losses={"jepa": 0.5, "qm9": 0.1, "tol": 0.3},
    per_source_grads={"jepa": 2.5, "qm9": 0.3, "tol": 1.2},
)
# Result: jepa weight ↑, qm9 weight ↓
```

## Algorithm Deep Dive

### Core Principle: Loss-Proportional Sampling

Sources with higher loss need more samples. This is the fundamental insight.

```
weight_i ∝ base_i × (loss_i / mean_loss) × diversity_factor
```

### Step-by-Step

1. **Compute Per-Source Loss**
   ```python
   loss_jepa = compute_loss(batch_jepa)  # 0.5
   loss_qm9 = compute_loss(batch_qm9)    # 0.1
   loss_tol = compute_loss(batch_tol)    # 0.3
   mean_loss = (0.5 + 0.1 + 0.3) / 3     # 0.3
   ```

2. **Loss Ratio Adjustment**
   ```python
   # jepa: 0.5/0.3 = 1.67 (needs more)
   # qm9:  0.1/0.3 = 0.33 (needs less)
   # tol:  0.3/0.3 = 1.00 (balanced)
   ```

3. **Apply Sensitivity Scaling**
   ```python
   loss_adjustment = 1.0 + sensitivity * (loss_ratio - 1.0)
   # jepa: 1.0 + 1.0 * 0.67 = 1.67
   # qm9:  1.0 + 1.0 * -0.67 = 0.33
   ```

4. **Gradient Adjustment (Optional)**
   ```python
   # Higher gradients = more informative samples
   grad_adjustment = 1.0 + 0.5 * (grad_ratio - 1.0)
   ```

5. **Diversity Preservation**
   ```python
   # If source hasn't been sampled in 10+ batches
   if batches_since_sample > 10:
       weight *= 1.1  # 10% diversity bonus
   ```

6. **Normalize with Minimum**
   ```python
   # Ensure no source drops below 5%
   weight = max(0.05, weight)
   weights = weights / sum(weights)  # Normalize to 1.0
   ```

## Hyperparameter Reasoning

### `adaptation_rate = 0.1`

**Why 0.1?**
- Too high (0.5): Weights oscillate wildly
- Too low (0.01): Adaptation too slow to matter
- 0.1: Smooth adaptation over ~10 batches

**Derivation:**
- 63% adaptation after 10 steps: `1 - (1-0.1)^10 ≈ 0.65`
- 95% adaptation after 30 steps: `1 - (1-0.1)^30 ≈ 0.96`
- This matches typical phase duration (~5000 steps)

### `loss_sensitivity = 1.0`

**Why 1.0?**
- Linear relationship between loss ratio and weight
- 2x higher loss → 2x higher weight (after normalization)
- Could increase to 2.0 for more aggressive adaptation

### `gradient_sensitivity = 0.5`

**Why 0.5 (half of loss)?**
- Gradients are noisier than losses
- Don't want single large gradient to dominate
- Secondary signal to loss

### `min_weight = 0.05`

**Why 5%?**
- Prevents complete collapse to single source
- With 5 sources: ensures each gets ≥1% of samples
- At batch_size=256: ≥12 samples per source minimum

### `ema_decay = 0.99`

**Why 0.99?**
- Effective window: ~100 steps (`1/(1-0.99)`)
- Smooths out batch-to-batch variance
- High enough to prevent overreaction

### `warmup_steps = 1000`

**Why 1000?**
- Need baseline statistics before adaptation
- 1000 steps ≈ 256K samples at batch=256
- Enough to estimate loss distributions

## Curriculum Integration

### Phase Transitions

When curriculum phase changes, base weights update:

```python
# Phase: GEOMETRY → DYNAMICS
old_weights = {"jepa": 0.6, "qm9": 0.2, "tol": 0.2}
new_weights = {"jepa": 0.45, "qm9": 0.2, "tol": 0.2, "gen": 0.15}

# Soft transition (70% old + 30% new)
current_weight = 0.7 * adaptive_weight + 0.3 * new_base
```

**Why soft transition?**
- Sudden weight changes disrupt training
- Adaptive adjustments should persist across phases
- 70/30 blend preserves learnings

### Phase-Specific Reasoning

```
WARMUP (100% JEPA):
- Pure reconstruction, no mixing
- Establish baseline dynamics

GEOMETRY (60/20/20 JEPA/QM9/ToL):
- JEPA: Temporal dynamics (60%)
- QM9: SE(3) from molecules (20%)
- ToL: Hierarchy from phylogeny (20%)

DYNAMICS (45/20/20/15):
- Reduce JEPA as dynamics learned
- Add generation to test structure

JOINT (35/15/15/35):
- Balance core and generation
- Full RSSM + EFE training

LANGUAGE (30/30/20/10/10):
- Add language sources (50% total)
- Reduce geometry (20% total)
- Language grounding priority
```

## Empirical Validation

### Expected Behavior

```
Step 0-1000 (Warmup):
  jepa=1.0 (no mixing)

Step 1000-5000 (GEOMETRY):
  Initial: jepa=0.60, qm9=0.20, tol=0.20
  If QM9 converges faster:
    jepa=0.70, qm9=0.10, tol=0.20

Step 5000-10000 (DYNAMICS):
  Initial: jepa=0.45, qm9=0.20, tol=0.20, gen=0.15
  If generation is hard:
    jepa=0.35, qm9=0.15, tol=0.15, gen=0.35
```

### Metrics to Track

```yaml
# Log these every 100 steps
adaptive_metrics:
  - per_source_weight       # Current weights
  - per_source_loss_ema     # Running loss
  - per_source_grad_norm    # Gradient norms
  - weight_stability        # Weight variance over last 100 steps
  - diversity_score         # min(weights) * num_sources
```

## Failure Modes & Mitigations

### Mode Collapse
**Symptom**: One source gets 90%+ weight
**Cause**: Extreme loss difference
**Mitigation**: `min_weight=0.05` enforces minimum

### Oscillation
**Symptom**: Weights swing wildly
**Cause**: High adaptation_rate + noisy losses
**Mitigation**: `ema_decay=0.99` smooths statistics

### Underfitting Minority Sources
**Symptom**: High loss on low-weight sources
**Cause**: Not enough samples to learn
**Mitigation**: `diversity_bonus=0.1` for undersampled sources

## Comparison to Alternatives

### Data Mixing Laws (DML)
**Paper**: Xie et al., 2024
**Approach**: Predict optimal mix from dataset characteristics
**Limitation**: Requires pre-training analysis, static during training
**Our advantage**: Online adaptation during training

### Automatic Curriculum Learning
**Paper**: Graves et al., 2017
**Approach**: Sample based on learning progress
**Limitation**: Measures progress, not difficulty
**Our advantage**: Loss-based measures difficulty directly

### Multi-Task Learning Gradient Surgery
**Paper**: Yu et al., 2020
**Approach**: Modify gradients to reduce interference
**Limitation**: Computational overhead, complex implementation
**Our advantage**: Simple weight adjustment, no gradient modification

## Summary

**Adaptive data mixing is essential because:**
1. Different data sources converge at different rates
2. Static mixing wastes compute on converged sources
3. Optimal mix varies per run, model, initialization
4. Online adaptation responds to actual training dynamics

**Key design choices:**
- Loss-proportional weighting (fundamental principle)
- Conservative adaptation (0.1 rate, 0.99 EMA)
- Diversity preservation (5% minimum, 10% bonus)
- Soft curriculum transitions (70/30 blend)

**Expected improvement**: 10-30% faster convergence to target loss compared to static mixing.
