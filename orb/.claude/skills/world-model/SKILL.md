# World Model Skill

RSSM-based dynamics prediction. Use for world model modifications and training.

## Architecture

```
KagamiWorldModel (~36M params)

Encoder: 512 → 248 → 133 → 78 → 52 → 14 → 8
Decoder: 8 → 14 → 52 → 78 → 133 → 248 → 512
```

## RSSM State

- **Deterministic (h):** 256D GRU hidden state
- **Stochastic (z):** 14D uncertainty

## Key Files

| File | Purpose |
|------|---------|
| `kagami/core/world_model/kagami_world_model.py` | Main model |
| `kagami/core/world_model/rssm_core.py` | RSSM dynamics |

## Usage

```python
from kagami.core.world_model.rssm_core import get_organism_rssm

rssm = get_organism_rssm()
```

## Commands

```bash
# Smart testing - only affected tests
make test-smart

# Or target specific module
pytest tests/core/world_model/ -v
```
