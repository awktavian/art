"""Orchestration - Colony Process Management & Coordination.

This module provides process supervision and coordination for the 7 colony
agents in the KagamiOS system.

Components:
- ColonyManager: Process supervisor for colony agents
- ColonyRPC: E8-based inter-colony message passing
- IntentRouter: High-level intent routing API
- Health monitoring and auto-restart
- Load balancing and routing
- Fano line routing for multi-hop communication

Usage:
    from kagami.orchestration import create_colony_manager, IntentRouter

    manager = create_colony_manager()
    await manager.start_all()

    # Route to least-loaded colony
    colony_idx = manager.get_least_loaded_colony()

    # Check health
    if manager.all_healthy():
        print("All colonies operational")

    # Intent orchestration (high-level API)
    router = IntentRouter()
    result = await router.execute_intent(
        intent="research.web",
        context={"query": "how to implement E8 lattice"}
    )

    # Inter-colony communication
    rpc = ColonyRPC()
    msg = E8Message(
        source_colony=0,
        target_colony=6,
        e8_payload=[...],
        intent={"task": "verify"},
        correlation_id=str(uuid.uuid4()),
        timestamp=time.time(),
    )
    await rpc.send_message(msg)

    # Graceful shutdown
    await manager.stop_all()

Created: December 14, 2025
"""

from kagami.orchestration.colony_manager import (
    ColonyManager,
    ColonyManagerConfig,
    ColonyProcessInfo,
    create_colony_manager,
)
from kagami.orchestration.intent_orchestrator import (
    ColonyIntentRouter,
    IntentExecutionError,
    IntentParseError,
    create_intent_router,
    get_global_intent_router,
)

# Backwards compatibility alias
IntentRouter = ColonyIntentRouter
from kagami.orchestration.claude_code_bridge import (
    BridgeConfig,
    BridgeMode,
    ClaudeCodeTaskBridge,
    TaskResult,
    create_claude_code_bridge,
    get_claude_code_bridge,
    should_use_claude_code,
)

# NOTE: colony_rpc has circular import issues with unified_agents
# Import it directly when needed: from kagami.orchestration.colony_rpc import ColonyRPC

__all__ = [
    "BridgeConfig",
    "BridgeMode",
    # Claude Code Bridge
    "ClaudeCodeTaskBridge",
    # Intent Router
    "ColonyIntentRouter",
    # Colony Manager
    "ColonyManager",
    "ColonyManagerConfig",
    "ColonyProcessInfo",
    "IntentExecutionError",
    "IntentParseError",
    "IntentRouter",  # Backwards compatibility alias
    "TaskResult",
    "create_claude_code_bridge",
    "create_colony_manager",
    "create_intent_router",
    "get_claude_code_bridge",
    "get_global_intent_router",
    "should_use_claude_code",
]
