"""Fano CBF Composition Integration Example.

Demonstrates how FanoActionRouter integrates with FanoCompositionChecker
to ensure safe multi-colony execution.

CREATED: December 14, 2025
"""

import torch

from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF
from kagami.core.safety.fano_cbf_composition import (
    FanoCompositionChecker,
    check_fano_routing_safety,
    compose_fano_barriers,
    compose_fano_barriers_detailed,
)
from kagami.core.unified_agents.fano_action_router import create_fano_router


def example_1_basic_composition():
    """Example 1: Basic barrier composition for two colonies."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Barrier Composition")
    print("=" * 70)

    # Two colonies want to work together
    h_A = 0.3  # Colony A is safe
    h_B = 0.2  # Colony B is safe

    # Shared resources are under control
    shared_resources = {
        "memory": 0.6,  # 60% utilization
        "compute": 0.7,  # 70% utilization
    }

    # Compose barriers (line 0: Spark × Forge = Flow)
    h_composed = compose_fano_barriers(
        h_A=h_A,
        h_B=h_B,
        shared_resources=shared_resources,
        fano_line=0,
    )

    print(f"Colony A barrier: {h_A:.3f}")
    print(f"Colony B barrier: {h_B:.3f}")
    print(
        f"Shared resources: memory={shared_resources['memory']:.2f}, "
        f"compute={shared_resources['compute']:.2f}"
    )
    print(f"Composed barrier: {h_composed:.3f}")
    print(f"Safe to execute: {h_composed >= 0.0}")
    print()


def example_2_detailed_composition():
    """Example 2: Detailed composition with diagnostics."""
    print("=" * 70)
    print("EXAMPLE 2: Detailed Composition Analysis")
    print("=" * 70)

    # Scenario: High resource utilization
    h_A = 0.4  # Colony A safe
    h_B = 0.5  # Colony B safe
    shared_resources = {
        "memory": 0.9,  # 90% utilization - UNSAFE (> 85% threshold)
        "compute": 0.7,  # 70% utilization - safe
    }

    # Get detailed result
    result = compose_fano_barriers_detailed(
        h_A=h_A,
        h_B=h_B,
        shared_resources=shared_resources,
        fano_line=0,
    )

    print(f"Colony A barrier: {result.h_A:.3f}")
    print(f"Colony B barrier: {result.h_B:.3f}")
    print(f"Shared barrier: {result.h_shared:.3f}")
    print(f"Composed barrier: {result.h_composed:.3f}")
    print(f"Is safe: {result.is_safe}")
    print(f"Limiting factor: {result.limiting_factor}")
    print(f"Per-resource barriers: {result.metadata['per_resource_barriers']}")
    print()


def example_3_fano_line_checking():
    """Example 3: Check all 7 Fano lines for safety."""
    print("=" * 70)
    print("EXAMPLE 3: Fano Line Safety Checking")
    print("=" * 70)

    # Create DecentralizedCBF
    cbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=32)

    # Create safe colony states (low risk)
    colony_states = torch.randn(7, 4) * 0.1  # Small random states

    # Create checker
    checker = FanoCompositionChecker(cbf_registry=cbf)

    # Check all Fano lines
    shared_resources = {"memory": 0.6, "compute": 0.7}
    line_barriers = checker.check_all_lines(
        colony_states=colony_states,
        shared_resources=shared_resources,
    )

    print("Fano Line Safety Status:")
    for line_id, h_line in line_barriers.items():
        status = "SAFE" if h_line >= 0 else "UNSAFE"
        print(f"  Line {line_id}: h={h_line:.3f} [{status}]")
    print()


def example_4_unsafe_detection():
    """Example 4: Detect and report unsafe lines."""
    print("=" * 70)
    print("EXAMPLE 4: Unsafe Line Detection")
    print("=" * 70)

    # Create checker
    checker = FanoCompositionChecker()

    # Make some colonies unsafe
    colony_barriers = {
        0: -0.1,  # Spark UNSAFE
        1: 0.3,  # Forge safe
        2: 0.3,  # Flow safe
        3: 0.3,  # Nexus safe
        4: 0.3,  # Beacon safe
        5: 0.3,  # Grove safe
        6: 0.3,  # Crystal safe
    }

    # Get comprehensive verification
    verification = checker.verify_compositional_safety(
        colony_states={},
        shared_resources={"memory": 0.5},
        colony_barriers=colony_barriers,
    )

    print(f"All safe: {verification['all_safe']}")
    print(f"Number of violations: {verification['num_violations']}")
    print(f"Min barrier: {verification['min_barrier']:.3f}")
    print(f"Max barrier: {verification['max_barrier']:.3f}")
    print()

    if verification["violations"]:
        print("Violation Details:")
        for violation in verification["violations"]:
            print(
                f"  Line {violation['line_id']}: "
                f"colonies {violation['colonies']}, "
                f"barrier={violation['barrier']:.3f}"
            )
    print()


def example_5_router_integration():
    """Example 5: Integration with FanoActionRouter."""
    print("=" * 70)
    print("EXAMPLE 5: Router Integration")
    print("=" * 70)

    # Create router and CBF
    router = create_fano_router()
    cbf = FanoDecentralizedCBF(state_dim=4)

    # Route an action
    routing_result = router.route(
        action="build.feature",
        params={"feature": "authentication"},
        complexity=0.5,  # Will use Fano line mode
    )

    print(f"Routing mode: {routing_result.mode}")
    print(f"Complexity: {routing_result.complexity:.2f}")
    print("Actions:")
    for action in routing_result.actions:
        print(
            f"  - Colony {action.colony_idx} ({action.colony_name}): "
            f"weight={action.weight:.2f}, role={action.fano_role}"
        )
    print()

    # Check routing safety
    colony_states = torch.randn(7, 4) * 0.1  # Safe states
    shared_resources = {"memory": 0.6, "compute": 0.7}

    is_safe, info = check_fano_routing_safety(
        routing_result=routing_result,
        colony_states=colony_states,
        shared_resources=shared_resources,
        cbf_registry=cbf,
    )

    print(f"Routing is safe: {is_safe}")
    print(f"Safety info: {info}")
    print()


def example_6_resource_threshold_violation():
    """Example 6: Resource constraint violation."""
    print("=" * 70)
    print("EXAMPLE 6: Resource Constraint Violation")
    print("=" * 70)

    # Colonies are safe, but resources are maxed out
    h_A = 0.5
    h_B = 0.4
    shared_resources = {
        "memory": 0.95,  # 95% > 85% threshold
        "compute": 0.92,  # 92% > 90% threshold
        "bandwidth": 0.85,  # 85% > 80% threshold
    }

    result = compose_fano_barriers_detailed(
        h_A=h_A,
        h_B=h_B,
        shared_resources=shared_resources,
        fano_line=0,
    )

    print("Resource-constrained scenario:")
    print(f"  Colony barriers are safe: A={h_A:.2f}, B={h_B:.2f}")
    print("  But resources are over threshold:")
    for resource, util in shared_resources.items():
        barrier = result.metadata["per_resource_barriers"][resource]
        print(f"    {resource}: {util:.1%} utilization, barrier={barrier:.3f}")
    print()
    print(f"Composed barrier: {result.h_composed:.3f} (UNSAFE)")
    print(f"Limiting factor: {result.limiting_factor}")
    print()


if __name__ == "__main__":
    example_1_basic_composition()
    example_2_detailed_composition()
    example_3_fano_line_checking()
    example_4_unsafe_detection()
    example_5_router_integration()
    example_6_resource_threshold_violation()

    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)
