"""Swarm Intelligence - Bio-Inspired Multi-Agent Coordination.

Active components:
- identity: Instance and colony identity
- agent_graph: Agent social graphs
- success_trails: Pheromone-like trail reinforcement
- reflex_layer: Fast path for common patterns

For service discovery, use the canonical cluster implementation:
    from kagami.core.cluster.service_registry import get_service_registry

For distributed consensus, use KagamiConsensus:
    from kagami.core.coordination.kagami_consensus import create_consensus_protocol

Created: October 2025
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kagami.core.cluster.service_registry import ServiceRegistry
    from kagami.core.swarm.agent_graph import AgentGraph
    from kagami.core.swarm.identity import Colony, InstanceIdentity
    from kagami.core.swarm.reflex_layer import ReflexLayer
    from kagami.core.swarm.success_trails import SuccessTrailTracker, Trail

# HARDENED: All swarm components are REQUIRED - no optional fallbacks
# Re-export from canonical location for backwards compatibility
from kagami.core.cluster.service_registry import (
    ServiceRegistry,
    get_service_registry,
)
from kagami.core.swarm.agent_graph import AgentGraph, get_agent_graph
from kagami.core.swarm.identity import (
    Colony,
    InstanceIdentity,
    get_instance_id,
    get_instance_identity,
)
from kagami.core.swarm.reflex_layer import ReflexLayer, get_reflex_layer
from kagami.core.swarm.success_trails import (
    SuccessTrailTracker,
    Trail,
    get_success_trail_tracker,
)

__all__ = [
    # Agent Graph
    "AgentGraph",
    # Identity
    "Colony",
    "InstanceIdentity",
    # Reflex
    "ReflexLayer",
    # Service Discovery
    "ServiceRegistry",
    # Success Trails
    "SuccessTrailTracker",
    "Trail",
    "get_agent_graph",
    "get_instance_id",
    "get_instance_identity",
    "get_reflex_layer",
    "get_service_registry",
    "get_success_trail_tracker",
]
