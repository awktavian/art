# Meta Orchestrator

Coordinates multiple tasks across sessions.

## What It Does

- Maintains memory across sessions
- Learns good task decomposition
- Routes work efficiently
- Verifies safety

## When to Use

- Multi-step projects spanning sessions
- Complex task decomposition
- Cross-session coordination

## Location

`kagami/core/coordination/meta_orchestrator.py`

## Usage

```python
from kagami.core.coordination.meta_orchestrator import get_meta_orchestrator

meta = get_meta_orchestrator()
```

## Memory Files

```
.cursor/kagami_memory.json      # Episodic memory
.cursor/meta_state.json         # Orchestrator state
.cursor/execution_patterns.json # Learned patterns
```

## Safety

```
h(x) = min(h₁, h₂, ..., hₙ) ≥ 0
```

All instances must be safe.
