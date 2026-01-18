#!/usr/bin/env python3
"""Demonstration of ConsensusAwareFanoRouter.

This script demonstrates the consensus-aware routing capabilities:
1. Initial routing proposal from FanoActionRouter (fast heuristic)
2. Consensus validation via KagamiConsensus (Byzantine quorum)
3. Fallback modes (timeout, convergence failure)
4. Backward compatibility with FanoActionRouter

Created: December 15, 2025
"""

import asyncio
import logging

from kagami.core.unified_agents.fano_action_router import (
    create_consensus_aware_router,
    create_fano_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_consensus_disabled():
    """Demo 1: Consensus disabled (pure FanoActionRouter mode)."""
    print("\n" + "=" * 80)
    print("DEMO 1: Consensus Disabled (Fast Mode)")
    print("=" * 80)

    router = create_consensus_aware_router(
        enable_consensus=False,  # Bypass consensus (testing/fallback)
    )

    test_actions = [
        ("ping", {}, "Simple action → single colony"),
        ("build.feature", {"module": "auth"}, "Build action → single or Fano"),
        ("analyze.complex.system", {"depth": "full"}, "Complex → Fano or all colonies"),
    ]

    for action, params, description in test_actions:
        result = await router.route_with_consensus(
            action=action,
            params=params,
        )

        print(f"\n{description}")
        print(f"  Action: {action}")
        print(f"  Mode: {result.mode.value}")
        print(f"  Colonies: {[a.colony_name for a in result.actions]}")
        print(f"  Complexity: {result.complexity:.2f}")


async def demo_consensus_enabled():
    """Demo 2: Consensus enabled (Byzantine validation)."""
    print("\n" + "=" * 80)
    print("DEMO 2: Consensus Enabled (Byzantine Validation)")
    print("=" * 80)

    # Note: This will fail gracefully since we don't have real colony agents running
    # In production, consensus would query actual colony agents for proposals
    router = create_consensus_aware_router(
        enable_consensus=True,
        consensus_timeout=1.0,  # Short timeout for demo
    )

    result = await router.route_with_consensus(
        action="implement.security.feature",
        params={"critical": True},
    )

    print("\nAction: implement.security.feature")
    print(f"Mode: {result.mode.value}")
    print(f"Colonies: {[a.colony_name for a in result.actions]}")
    print(f"Metadata: {result.metadata}")


async def demo_fano_line_routing():
    """Demo 3: Fano line composition (3-colony routing)."""
    print("\n" + "=" * 80)
    print("DEMO 3: Fano Line Composition (3-Colony Routing)")
    print("=" * 80)

    router = create_consensus_aware_router(enable_consensus=False)

    # Force complexity to trigger Fano line mode
    result = await router.route_with_consensus(
        action="build.complex.feature",
        params={},
        complexity=0.5,  # Explicit complexity in Fano range (0.3-0.7)
    )

    print("\nAction: build.complex.feature")
    print(f"Mode: {result.mode.value}")
    print(f"Colonies: {[a.colony_name for a in result.actions]}")
    if result.fano_line:
        print(f"Fano Line: {result.fano_line}")
        print("  Colony roles:")
        for action in result.actions:
            print(f"    {action.colony_name}: {action.fano_role or 'N/A'}")


async def demo_all_colonies():
    """Demo 4: All colonies mode (synthesis tasks)."""
    print("\n" + "=" * 80)
    print("DEMO 4: All Colonies Mode (Synthesis Tasks)")
    print("=" * 80)

    router = create_consensus_aware_router(enable_consensus=False)

    # Force high complexity to trigger all-colonies mode
    result = await router.route_with_consensus(
        action="architect.entire.system",
        params={},
        complexity=0.9,  # High complexity → all colonies
    )

    print("\nAction: architect.entire.system")
    print(f"Mode: {result.mode.value}")
    print(f"Colonies ({len(result.actions)}): {[a.colony_name for a in result.actions]}")
    print("Weights:")
    for action in result.actions:
        print(
            f"  {action.colony_name}: {action.weight:.2f} ({'PRIMARY' if action.is_primary else 'secondary'})"
        )


async def demo_backward_compatibility():
    """Demo 5: Backward compatibility with FanoActionRouter."""
    print("\n" + "=" * 80)
    print("DEMO 5: Backward Compatibility")
    print("=" * 80)

    # Create both routers
    base_router = create_fano_router()
    consensus_router = create_consensus_aware_router(enable_consensus=False)

    test_action = "build.module"
    test_params = {"name": "auth"}

    # Route with base router (sync)
    base_result = base_router.route(
        action=test_action,
        params=test_params,
    )

    # Route with consensus router (async, consensus disabled)
    consensus_result = await consensus_router.route_with_consensus(
        action=test_action,
        params=test_params,
    )

    print(f"\nAction: {test_action}")
    print("\nBase FanoActionRouter:")
    print(f"  Mode: {base_result.mode.value}")
    print(f"  Colonies: {[a.colony_name for a in base_result.actions]}")

    print("\nConsensusAwareFanoRouter (disabled):")
    print(f"  Mode: {consensus_result.mode.value}")
    print(f"  Colonies: {[a.colony_name for a in consensus_result.actions]}")

    # Verify they match
    base_colonies = {a.colony_idx for a in base_result.actions}
    consensus_colonies = {a.colony_idx for a in consensus_result.actions}

    if base_result.mode == consensus_result.mode and base_colonies == consensus_colonies:
        print("\n✓ Results match (backward compatible)")
    else:
        print("\n✗ Results differ (unexpected)")


async def main():
    """Run all demos."""
    print("\n" + "=" * 80)
    print("ConsensusAwareFanoRouter Demonstration")
    print("=" * 80)

    await demo_consensus_disabled()
    await demo_consensus_enabled()
    await demo_fano_line_routing()
    await demo_all_colonies()
    await demo_backward_compatibility()

    print("\n" + "=" * 80)
    print("Demo Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
