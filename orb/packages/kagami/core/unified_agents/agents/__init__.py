"""Colony Agents — LLM-based agents with catastrophe personalities.

This module provides high-level agent classes for the 7 colonies:
- Spark (e₁):   The Dreamer — creative ideation
- Forge (e₂):   The Builder — implementation
- Flow (e₃):    The Healer — debugging/recovery
- Nexus (e₄):   The Bridge — integration
- Beacon (e₅):  The Planner — strategy/architecture
- Grove (e₆):   The Seeker — research/documentation
- Crystal (e₇): The Judge — verification/testing

Each agent:
1. Has distinct personality (docs/colonies.md)
2. Maps to catastrophe type (Thom's 7 elementary catastrophes)
3. Provides specialized tools
4. Knows when to escalate (Fano composition)

USAGE:
======
```python
from kagami.core.unified_agents.agents import create_spark_agent

spark = create_spark_agent()
result = spark.execute(
    task="Brainstorm innovative approaches to X",
    params={"count": 10},
    context={"mode": "divergent"}
)

print(result.output)
print(result.thoughts)

if result.escalation_needed:
    print(f"Escalate to {result.escalation_target}: {result.escalation_reason}")
```

CATASTROPHE MAPPING:
====================
Colony   | Catastrophe    | Dynamics
---------|----------------|------------------------------------------
Spark    | Fold (A₂)      | Sudden ignition at threshold
Forge    | Cusp (A₃)      | Bistable decision with hysteresis
Flow     | Swallowtail    | Multiple recovery paths
Nexus    | Butterfly      | 4D integration manifold
Beacon   | Hyperbolic     | Outward diverging planning
Grove    | Elliptic       | Inward converging search
Crystal  | Parabolic      | Boundary detection

FANO COMPOSITION:
=================
Spark × Forge = Flow       (Ideas + implementation → adaptation)
Spark × Nexus = Beacon     (Ideas + connection → planning)
Spark × Grove = Crystal    (Ideas + research → verification)
Forge × Nexus = Grove      (Implementation + integration → documentation)
Beacon × Forge = Crystal   (Planning + implementation → testing)
Nexus × Flow = Crystal     (Integration + recovery → verification)
Beacon × Flow = Grove      (Planning + adaptation → research)

Created: December 14, 2025
Status: Production
"""

# Import base classes from canonical locations
from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)

# Import colony agents
from kagami.core.unified_agents.agents.beacon_agent import (
    BeaconAgent,
    create_beacon_agent,
)
from kagami.core.unified_agents.agents.crystal_agent import (
    CrystalAgent,
    create_crystal_agent,
)
from kagami.core.unified_agents.agents.flow_agent import (
    FlowAgent,
    create_flow_agent,
)
from kagami.core.unified_agents.agents.forge_agent import (
    ForgeAgent,
    create_forge_agent,
)
from kagami.core.unified_agents.agents.grove_agent import (
    GroveAgent,
    create_grove_agent,
)
from kagami.core.unified_agents.agents.nexus_agent import (
    NexusAgent,
    create_nexus_agent,
)
from kagami.core.unified_agents.agents.spark_agent import (
    SparkAgent,
    create_spark_agent,
)

__all__ = [
    "AgentResult",
    # Base classes
    "BaseColonyAgent",
    # Beacon (e₅) - Planner
    "BeaconAgent",
    # Crystal (e₇) - Judge
    "CrystalAgent",
    # Flow (e₃) - Healer
    "FlowAgent",
    # Forge (e₂) - Builder
    "ForgeAgent",
    # Grove (e₆) - Seeker
    "GroveAgent",
    # Nexus (e₄) - Bridge
    "NexusAgent",
    # Spark (e₁) - Dreamer
    "SparkAgent",
    "create_beacon_agent",
    "create_crystal_agent",
    "create_flow_agent",
    "create_forge_agent",
    "create_grove_agent",
    "create_nexus_agent",
    "create_spark_agent",
]
