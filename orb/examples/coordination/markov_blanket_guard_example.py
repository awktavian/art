"""Example: Markov Blanket Guard in Consensus.

Demonstrates how the Markov blanket guard enforces architectural discipline
in the consensus protocol.

Created: December 15, 2025
"""

import asyncio

from kagami.core.coordination.kagami_consensus import (
    ColonyID,
    CoordinationProposal,
    create_consensus_protocol,
)
from kagami.core.coordination.markov_blanket_guard import (
    MarkovBlanketViolation,
    create_markov_blanket_guard,
)


def create_valid_proposal() -> CoordinationProposal:
    """Create a valid proposal that respects Markov blanket discipline."""
    return CoordinationProposal(
        proposer=ColonyID.FORGE,
        target_colonies=[ColonyID.SPARK, ColonyID.CRYSTAL],
        task_decomposition={
            ColonyID.SPARK: "Generate creative implementation ideas",
            ColonyID.CRYSTAL: "Verify implementation correctness",
        },
        confidence=0.85,
        fano_justification="Forge → Spark × Crystal (Fano line)",
        cbf_margin=0.6,
    )


def create_invalid_proposal_internal_access() -> CoordinationProposal:
    """Create an INVALID proposal that accesses internal state (FORBIDDEN)."""
    proposal = CoordinationProposal(
        proposer=ColonyID.BEACON,
        target_colonies=[ColonyID.FORGE],
        confidence=0.7,
    )
    # VIOLATION: Accessing internal state μ
    proposal._internal_state = {"hidden": "data"}  # type: ignore
    return proposal


def create_invalid_proposal_bypass_active() -> CoordinationProposal:
    """Create an INVALID proposal that bypasses active state (FORBIDDEN)."""
    proposal = CoordinationProposal(
        proposer=ColonyID.FLOW,
        target_colonies=[ColonyID.NEXUS],
        confidence=0.8,
    )
    # VIOLATION: Bypassing active state to modify external η directly
    proposal.direct_action = lambda: print("BYPASS")  # type: ignore
    return proposal


async def example_valid_proposal():
    """Example: Validate a valid proposal."""
    print("\n=== Example 1: Valid Proposal ===")

    guard = create_markov_blanket_guard(strict_mode=True)
    proposal = create_valid_proposal()

    try:
        result = guard.validate_proposal(proposal)
        print(f"✓ Proposal valid: {result.valid}")
        print(f"  Violations: {len(result.violations)}")
        print(f"  Warnings: {len(result.warnings)}")
    except MarkovBlanketViolation as e:
        print(f"✗ Violation detected: {e}")


async def example_invalid_proposal_internal():
    """Example: Detect internal state access violation."""
    print("\n=== Example 2: Internal State Access (FORBIDDEN) ===")

    guard = create_markov_blanket_guard(strict_mode=True)
    proposal = create_invalid_proposal_internal_access()

    try:
        result = guard.validate_proposal(proposal)
        print(f"✓ Proposal valid: {result.valid}")
    except MarkovBlanketViolation as e:
        print("✗ Violation detected (expected):")
        print(f"  Type: {e.violation_type.value}")
        print(f"  Colony: {e.colony_id}")
        print(f"  Details: {e.details}")


async def example_invalid_proposal_bypass():
    """Example: Detect active state bypass violation."""
    print("\n=== Example 3: Active State Bypass (FORBIDDEN) ===")

    guard = create_markov_blanket_guard(strict_mode=True)
    proposal = create_invalid_proposal_bypass_active()

    try:
        result = guard.validate_proposal(proposal)
        print(f"✓ Proposal valid: {result.valid}")
    except MarkovBlanketViolation as e:
        print("✗ Violation detected (expected):")
        print(f"  Type: {e.violation_type.value}")
        print(f"  Colony: {e.colony_id}")
        print(f"  Details: {e.details}")


async def example_lenient_mode():
    """Example: Lenient mode logs warnings instead of raising."""
    print("\n=== Example 4: Lenient Mode ===")

    guard = create_markov_blanket_guard(strict_mode=False)
    proposal = create_invalid_proposal_internal_access()

    result = guard.validate_proposal(proposal)
    print(f"Proposal valid: {result.valid}")
    print(f"Violations: {len(result.violations)}")
    for violation in result.violations:
        print(f"  - {violation['type'].value}: {violation['details']}")
    print(f"Warnings: {len(result.warnings)}")
    for warning in result.warnings:
        print(f"  - {warning}")


async def example_consensus_integration():
    """Example: Markov guard integrated with consensus protocol."""
    print("\n=== Example 5: Consensus Integration ===")

    # Create consensus with Markov guard enabled
    consensus = create_consensus_protocol(
        enable_markov_guard=True,
        enable_cot=False,  # Disable CoT for simplicity
    )

    print(f"Consensus created with Markov guard: {consensus.markov_guard is not None}")

    # Collect proposals (guard validates automatically)
    task = "Implement new feature X with proper testing"
    proposals = await consensus.collect_proposals(task)

    print(f"Collected {len(proposals)} proposals")
    print("All proposals validated by Markov guard ✓")


async def example_state_access_validation():
    """Example: Validate state attribute access."""
    print("\n=== Example 6: State Access Validation ===")

    guard = create_markov_blanket_guard(strict_mode=False)

    # Allowed access (sensory state)
    allowed_attrs = {"z_state", "sensory_state", "observation"}
    result = guard.validate_state_access(
        colony_id=2,
        accessed_attributes=allowed_attrs,
    )
    print(f"Sensory state access valid: {result.valid}")

    # Forbidden access (internal state)
    forbidden_attrs = {"z_state", "_internal_state", "_mu"}
    result = guard.validate_state_access(
        colony_id=2,
        accessed_attributes=forbidden_attrs,
    )
    print(f"Internal state access valid: {result.valid}")
    print(f"Violations: {len(result.violations)}")
    for violation in result.violations:
        print(f"  - {violation['type'].value}: {violation['details']}")


async def main():
    """Run all examples."""
    print("=" * 70)
    print("Markov Blanket Guard Examples")
    print("=" * 70)

    await example_valid_proposal()
    await example_invalid_proposal_internal()
    await example_invalid_proposal_bypass()
    await example_lenient_mode()
    await example_state_access_validation()
    await example_consensus_integration()

    print("\n" + "=" * 70)
    print("All examples completed")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
