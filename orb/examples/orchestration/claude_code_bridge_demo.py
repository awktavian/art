#!/usr/bin/env python
"""Claude Code Task Bridge - Usage Examples.

This script demonstrates how to use the ClaudeCodeTaskBridge to spawn
colony agents via Claude Code Task tool instead of Python processes.

Usage:
    python examples/orchestration/claude_code_bridge_demo.py

Created: December 15, 2025
"""

import asyncio

from kagami.orchestration.claude_code_bridge import (
    BridgeConfig,
    BridgeMode,
    create_claude_code_bridge,
)


async def example_1_single_agent():
    """Example 1: Spawn single colony agent."""
    print("\n" + "=" * 60)
    print("Example 1: Single Agent Spawning")
    print("=" * 60)

    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    result = await bridge.spawn_colony_agent(
        colony_name="forge",
        task="Implement authentication module with JWT support",
        params={"file_path": "kagami/auth.py", "include_tests": True},
    )

    print(f"\nColony: {result.colony_name} (colony_{result.colony_idx})")
    print(f"Success: {result.success}")
    print(f"Latency: {result.latency_ms:.1f}ms")
    print(f"Correlation ID: {result.correlation_id}")
    print(f"Output: {result.output}")


async def example_2_parallel_agents():
    """Example 2: Spawn multiple agents in parallel (MAXIMUM PARALLELISM)."""
    print("\n" + "=" * 60)
    print("Example 2: Parallel Agent Spawning")
    print("=" * 60)

    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID, enable_parallel=True))

    # Launch 3 forge agents to implement 3 independent modules
    tasks = [
        ("forge", "Implement user authentication module", {"file": "kagami/auth/user.py"}),
        ("forge", "Implement token management module", {"file": "kagami/auth/token.py"}),
        ("forge", "Implement session handling module", {"file": "kagami/auth/session.py"}),
    ]

    print(f"\nSpawning {len(tasks)} agents in parallel...")

    results = await bridge.spawn_parallel_agents(tasks)

    print(f"\nCompleted: {len(results)} agents")
    for i, result in enumerate(results, 1):
        print(
            f"  {i}. {result.colony_name}: "
            f"success={result.success}, "
            f"latency={result.latency_ms:.1f}ms"
        )


async def example_3_fano_line():
    """Example 3: Execute task along Fano line (3 colonies)."""
    print("\n" + "=" * 60)
    print("Example 3: Fano Line Execution (PLAN-EXECUTE-VERIFY)")
    print("=" * 60)

    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    # Beacon × Forge = Crystal (plan + implement → verify)
    print("\nFano line: beacon × forge = crystal")
    print("Phase: PLAN (beacon) + EXECUTE (forge) → VERIFY (crystal)")

    results = await bridge.execute_fano_line(
        source="beacon",
        partner="forge",
        task="Design and implement authentication system",
        params={"output_dir": "kagami/auth/", "include_docs": True},
    )

    print(f"\nFano line complete: {len(results)} colonies executed")
    print(f"  Phase 1a: {results[0].colony_name} (parallel)")
    print(f"  Phase 1b: {results[1].colony_name} (parallel)")
    print(f"  Phase 2:  {results[2].colony_name} (synthesis)")

    # All share same correlation ID
    print(f"\nShared correlation ID: {results[0].correlation_id}")


async def example_4_all_colonies():
    """Example 4: Engage all 7 colonies for complex task."""
    print("\n" + "=" * 60)
    print("Example 4: All-Colony Orchestration (Synthesis)")
    print("=" * 60)

    bridge = create_claude_code_bridge(
        BridgeConfig(mode=BridgeMode.HYBRID, enable_parallel=True, max_concurrent=7)
    )

    # Complex task: Design and implement complete authentication system
    # Engage all 7 colonies in parallel
    tasks = [
        ("spark", "Brainstorm authentication strategies (OAuth, JWT, etc.)", {}),
        ("beacon", "Design authentication system architecture", {}),
        ("grove", "Research authentication security best practices", {}),
        ("forge", "Implement core authentication module", {"file": "kagami/auth/core.py"}),
        ("nexus", "Integrate auth with existing API endpoints", {"endpoints": "all"}),
        ("flow", "Debug authentication flow edge cases", {}),
        ("crystal", "Verify authentication security properties", {"audit": "full"}),
    ]

    print("\nSpawning all 7 colonies in parallel...")

    results = await bridge.spawn_parallel_agents(tasks)

    print("\nAll-colony orchestration complete")
    for result in results:
        status = "✓" if result.success else "✗"
        print(f"  {status} {result.colony_name:8s}: latency={result.latency_ms:6.1f}ms")


async def example_5_hybrid_mode():
    """Example 5: Hybrid mode - automatic Python vs Claude Code selection."""
    print("\n" + "=" * 60)
    print("Example 5: Hybrid Mode (Automatic Selection)")
    print("=" * 60)

    from kagami.orchestration.claude_code_bridge import should_use_claude_code

    # Test different task types
    test_cases = [
        ("implement", {"file_path": "test.py"}, "File manipulation → Claude Code"),
        ("research", {"use_web": True}, "Web research → Claude Code"),
        ("train", {"epochs": 100}, "ML training → Python"),
        ("compute", {"tensor": "..."}, "Numerical compute → Python"),
        ("debug", {"interactive": True}, "Interactive debug → Claude Code"),
    ]

    print("\nTask routing decisions:")
    for task_type, context, description in test_cases:
        use_claude = should_use_claude_code(task_type, context)  # type: ignore[arg-type]
        mode = "Claude Code" if use_claude else "Python"
        print(f"  {description:<40s} → {mode}")


async def example_6_fano_composition():
    """Example 6: Explore Fano plane composition rules."""
    print("\n" + "=" * 60)
    print("Example 6: Fano Plane Composition Rules")
    print("=" * 60)

    bridge = create_claude_code_bridge()

    # Test known Fano compositions
    compositions = [
        ("spark", "forge", "flow"),  # creative + implement → adapt
        ("spark", "nexus", "beacon"),  # creative + integrate → plan
        ("spark", "grove", "crystal"),  # creative + research → verify
        ("forge", "nexus", "grove"),  # implement + integrate → research
        ("beacon", "forge", "crystal"),  # plan + implement → verify
        ("nexus", "flow", "crystal"),  # integrate + debug → verify
        ("beacon", "flow", "grove"),  # plan + debug → research
    ]

    print("\nFano plane compositions:")
    for source, partner, expected_result in compositions:
        result = bridge.get_fano_composition(source, partner)
        status = "✓" if result == expected_result else "✗"
        print(f"  {status} {source:8s} × {partner:8s} = {result:8s}")


async def example_7_stats_monitoring():
    """Example 7: Monitor bridge execution statistics."""
    print("\n" + "=" * 60)
    print("Example 7: Statistics & Monitoring")
    print("=" * 60)

    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    # Execute some tasks
    await bridge.spawn_colony_agent("spark", "Brainstorm ideas", {})
    await bridge.spawn_colony_agent("forge", "Implement module", {})
    await bridge.spawn_colony_agent("crystal", "Verify implementation", {})

    # Get statistics
    stats = bridge.get_stats()

    print("\nBridge Statistics:")
    print(f"  Mode: {stats['mode']}")
    print(f"  Model: {stats['model']}")
    print(f"  Total Executions: {stats['total_executions']}")
    print(f"  Active Tasks: {stats['active_tasks']}")
    print("\nConfiguration:")
    print(f"  Timeout: {stats['config']['timeout_seconds']}s")
    print(f"  Parallel Enabled: {stats['config']['enable_parallel']}")
    print(f"  Max Concurrent: {stats['config']['max_concurrent']}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Claude Code Task Bridge - Usage Examples")
    print("=" * 60)
    print("\nNOTE: This is a PROTOTYPE. Task tool invocations are placeholders.")
    print("In production, these would spawn actual Claude Code agents.")

    await example_1_single_agent()
    await example_2_parallel_agents()
    await example_3_fano_line()
    await example_4_all_colonies()
    await example_5_hybrid_mode()
    await example_6_fano_composition()
    await example_7_stats_monitoring()

    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
