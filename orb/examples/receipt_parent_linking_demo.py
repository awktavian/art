"""Demo: Receipt Parent Linking for PLAN→EXECUTE→VERIFY Chains

This example demonstrates how to use parent_receipt_id to create
receipt chains that track operation phases.

Created: December 19, 2025
"""

from kagami.core.receipts.facade import UnifiedReceiptFacade as URF


def demo_basic_chain():
    """Demo 1: Basic PLAN→EXECUTE→VERIFY chain."""
    print("\n=== Demo 1: Basic PLAN→EXECUTE→VERIFY Chain ===\n")

    # Generate correlation ID for this operation
    correlation_id = URF.generate_correlation_id(name="build_feature")
    print(f"Operation correlation_id: {correlation_id}\n")

    # PLAN phase (root)
    print("Phase 1: PLAN")
    plan_receipt = URF.emit(
        correlation_id=correlation_id,
        event_name="feature.plan",
        action="plan_architecture",
        phase="PLAN",
        status="success",
        event_data={
            "feature": "user_authentication",
            "estimated_complexity": 0.7,
        },
    )
    plan_id = plan_receipt["correlation_id"]
    print(f"  - Receipt ID: {plan_id}")
    print(f"  - Parent: {plan_receipt.get('parent_receipt_id', 'None (root)')}")
    print(f"  - Phase: {plan_receipt['phase']}\n")

    # EXECUTE phase (child of PLAN)
    print("Phase 2: EXECUTE")
    execute_receipt = URF.emit(
        correlation_id=correlation_id,
        event_name="feature.execute",
        action="implement_feature",
        phase="EXECUTE",
        parent_receipt_id=plan_id,  # Link to parent
        status="success",
        event_data={
            "files_modified": 5,
            "tests_written": 12,
        },
    )
    print(f"  - Receipt ID: {execute_receipt['correlation_id']}")
    print(f"  - Parent: {execute_receipt['parent_receipt_id']}")
    print(f"  - Phase: {execute_receipt['phase']}\n")

    # VERIFY phase (child of PLAN)
    print("Phase 3: VERIFY")
    verify_receipt = URF.emit(
        correlation_id=correlation_id,
        event_name="feature.verify",
        action="run_tests",
        phase="VERIFY",
        parent_receipt_id=plan_id,  # Link to parent
        status="success",
        event_data={
            "tests_passed": 12,
            "tests_failed": 0,
            "coverage": 0.95,
        },
    )
    print(f"  - Receipt ID: {verify_receipt['correlation_id']}")
    print(f"  - Parent: {verify_receipt['parent_receipt_id']}")
    print(f"  - Phase: {verify_receipt['phase']}\n")

    print("Chain structure:")
    print("  PLAN (root)")
    print(f"    ├─> EXECUTE (parent={plan_id[:8]}...)")
    print(f"    └─> VERIFY (parent={plan_id[:8]}...)\n")


def demo_nested_operations():
    """Demo 2: Nested operations with parent linking."""
    print("\n=== Demo 2: Nested Operations ===\n")

    # Parent operation
    parent_corr_id = URF.generate_correlation_id(name="epic_implementation")
    print(f"Epic correlation_id: {parent_corr_id}\n")

    URF.emit(
        correlation_id=parent_corr_id,
        event_name="epic.start",
        action="start_epic",
        phase="PLAN",
        status="success",
    )
    print(f"Epic PLAN: {parent_corr_id[:8]}...")

    # Child operation 1
    child1_corr_id = URF.generate_correlation_id(name="feature_1")
    URF.emit(
        correlation_id=child1_corr_id,
        event_name="feature.execute",
        action="implement_feature_1",
        phase="EXECUTE",
        parent_receipt_id=parent_corr_id,  # Link to epic
        status="success",
    )
    print(f"  ├─> Feature 1 EXECUTE: {child1_corr_id[:8]}...")

    # Child operation 2
    child2_corr_id = URF.generate_correlation_id(name="feature_2")
    URF.emit(
        correlation_id=child2_corr_id,
        event_name="feature.execute",
        action="implement_feature_2",
        phase="EXECUTE",
        parent_receipt_id=parent_corr_id,  # Link to epic
        status="success",
    )
    print(f"  └─> Feature 2 EXECUTE: {child2_corr_id[:8]}...\n")


def demo_colony_lifecycle():
    """Demo 3: Colony lifecycle tracking (future use case)."""
    print("\n=== Demo 3: Colony Lifecycle Tracking ===\n")

    colony_id = URF.generate_correlation_id(name="colony_forge")
    print(f"Colony correlation_id: {colony_id}\n")

    # Colony spawn (root)
    URF.emit(
        correlation_id=colony_id,
        event_name="colony.spawn",
        action="spawn",
        phase="PLAN",
        colony="forge",
        status="success",
        event_data={
            "port": 8002,
            "pid": 12345,
        },
    )
    print(f"Colony spawn: {colony_id[:8]}...")

    # Health check (child of spawn)
    health_receipt = URF.emit(
        correlation_id=colony_id,
        event_name="colony.health_check",
        action="health_check",
        phase="EXECUTE",
        parent_receipt_id=colony_id,
        colony="forge",
        status="success",
        event_data={
            "is_healthy": True,
            "uptime_seconds": 123.45,
        },
    )
    print(f"  ├─> Health check: {health_receipt['correlation_id'][:8]}...")

    # Restart (child of spawn, after failure)
    restart_receipt = URF.emit(
        correlation_id=colony_id,
        event_name="colony.restart",
        action="restart",
        phase="EXECUTE",
        parent_receipt_id=colony_id,
        colony="forge",
        status="success",
        event_data={
            "restart_count": 1,
            "reason": "process_died",
        },
    )
    print(f"  ├─> Restart: {restart_receipt['correlation_id'][:8]}...")

    # Shutdown (child of spawn)
    shutdown_receipt = URF.emit(
        correlation_id=colony_id,
        event_name="colony.shutdown",
        action="shutdown",
        phase="VERIFY",
        parent_receipt_id=colony_id,
        colony="forge",
        status="success",
        event_data={
            "graceful": True,
            "total_uptime_seconds": 456.78,
        },
    )
    print(f"  └─> Shutdown: {shutdown_receipt['correlation_id'][:8]}...\n")


def demo_backward_compatibility():
    """Demo 4: Backward compatibility - receipts without parent links."""
    print("\n=== Demo 4: Backward Compatibility ===\n")

    # Old-style receipt (no parent_receipt_id)
    old_receipt = URF.emit(
        correlation_id=URF.generate_correlation_id(name="legacy_op"),
        event_name="operation.execute",
        action="legacy_action",
        status="success",
    )

    print("Legacy receipt (no parent_receipt_id):")
    print(f"  - Correlation ID: {old_receipt['correlation_id'][:8]}...")
    print(f"  - Parent: {old_receipt.get('parent_receipt_id', 'None')}")
    print(f"  - Status: {old_receipt['status']}\n")

    print("✓ Legacy receipts work without parent_receipt_id")
    print("✓ Backward compatibility maintained\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Receipt Parent Linking Demo")
    print("Demonstrates PLAN→EXECUTE→VERIFY phase tracking")
    print("=" * 70)

    demo_basic_chain()
    demo_nested_operations()
    demo_colony_lifecycle()
    demo_backward_compatibility()

    print("=" * 70)
    print("Demo complete!")
    print("=" * 70 + "\n")
