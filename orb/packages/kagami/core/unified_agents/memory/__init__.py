"""Memory systems for unified agents.

Contains:
- stigmergy.py: Stigmergic learning (migrated from fractal_agents)
- colony_memory_bridge.py: Colony-Memory unification (consolidated from unification/ Dec 7, 2025)
- protocols.py: Backend protocol definitions (added Dec 15, 2025)
- backends.py: Storage backend implementations (added Dec 15, 2025)
"""

from kagami.core.unified_agents.memory.backends import (
    InMemoryBackend,
    WeaviateBackend,
    create_backend,
)

# Colony-Memory Bridge (consolidated from kagami.core.unification)
from kagami.core.unified_agents.memory.colony_memory_bridge import (
    ColonyMemoryBridge,
    ColonyMemoryConfig,
    UnifiedMemoryAccess,
    get_colony_memory_bridge,
    reset_colony_memory_bridge,
)

# Backend abstraction (December 15, 2025)
from kagami.core.unified_agents.memory.protocols import (
    MemoryBackend,
    ReceiptBackend,
)
from kagami.core.unified_agents.memory.stigmergy import (
    StigmergyLearner,
    get_stigmergy_learner,
)

__all__ = [
    "ColonyMemoryBridge",
    # Colony-Memory Bridge
    "ColonyMemoryConfig",
    "InMemoryBackend",
    # Backend abstraction
    "MemoryBackend",
    "ReceiptBackend",
    "StigmergyLearner",
    "UnifiedMemoryAccess",
    "WeaviateBackend",
    "create_backend",
    "get_colony_memory_bridge",
    "get_stigmergy_learner",
    "reset_colony_memory_bridge",
]
