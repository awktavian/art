#!/usr/bin/env python3
"""Demo: Maslow's Hierarchy of Needs for Autonomous Agents.

This script demonstrates the complete five-level hierarchy:
1. Physiological (Survival)
2. Safety (Security)
3. Belonging (Connection)
4. Esteem (Achievement)
5. Self-Actualization (Growth)

Each level blocks higher levels until satisfied (prepotency principle).
"""

import asyncio
from kagami.core.motivation.maslow import MaslowHierarchy


async def demo_hierarchy_progression() -> None:
    """Demonstrate progression through Maslow's hierarchy."""
    maslow = MaslowHierarchy()

    print("=" * 80)
    print("MASLOW'S HIERARCHY OF NEEDS - AUTONOMOUS AGENT MOTIVATION")
    print("=" * 80)
    print()

    # Scenario 1: Critical safety violation
    print("Scenario 1: SAFETY VIOLATION")
    print("-" * 80)
    context_unsafe = {
        "metrics": {
            "error_rate": 0.15,  # High error rate
            "memory_usage_percent": 40.0,
        },
        "collaboration_metrics": {
            "success_rate": 0.8,  # Good collaboration (ignored)
            "active_fano_pairs": 5,
        },
        "stigmergy_health": {
            "recent_receipts": 10,
            "learned_patterns": 5,
        },
        "capability_metrics": {
            "overall_success_rate": 0.75,  # Good performance (ignored)
            "learning_trend": 0.1,
        },
    }

    goals = await maslow.evaluate_needs(context_unsafe)
    print("Unsatisfied level: SAFETY")
    print(f"Generated {len(goals)} goal(s):")
    for i, goal in enumerate(goals, 1):
        print(f"  {i}. {goal.goal}")
        print(f"     Priority: {goal.priority:.2f}, Drive: {goal.drive.value}")
    print()

    # Scenario 2: Poor collaboration (safety OK)
    print("Scenario 2: BELONGING DEFICIT")
    print("-" * 80)
    context_lonely = {
        "metrics": {
            "error_rate": 0.01,  # Good
            "memory_usage_percent": 40.0,
        },
        "collaboration_metrics": {
            "success_rate": 0.3,  # Poor collaboration!
            "active_fano_pairs": 1,  # Few active Fano lines
        },
        "stigmergy_health": {
            "recent_receipts": 0,  # No receipt exchange
            "learned_patterns": 0,
        },
        "capability_metrics": {
            "overall_success_rate": 0.75,  # Good performance (ignored)
            "learning_trend": 0.1,
        },
    }

    goals = await maslow.evaluate_needs(context_lonely)
    print("Unsatisfied level: BELONGING")
    print(f"Generated {len(goals)} goal(s):")
    for i, goal in enumerate(goals, 1):
        print(f"  {i}. {goal.goal}")
        print(f"     Priority: {goal.priority:.2f}, Drive: {goal.drive.value}")
    print()

    # Scenario 3: Low capability mastery (safety + belonging OK)
    print("Scenario 3: ESTEEM DEFICIT")
    print("-" * 80)
    context_incompetent = {
        "metrics": {
            "error_rate": 0.01,
            "memory_usage_percent": 40.0,
        },
        "collaboration_metrics": {
            "success_rate": 0.8,  # Good
            "active_fano_pairs": 5,
        },
        "stigmergy_health": {
            "recent_receipts": 10,
            "learned_patterns": 5,
        },
        "capability_metrics": {
            "success_rates": {
                "research": 0.3,  # Poor
                "implementation": 0.35,  # Poor
                "debugging": 0.6,  # OK
            },
            "overall_success_rate": 0.42,  # Low overall
            "learning_trend": -0.1,  # Declining
        },
    }

    goals = await maslow.evaluate_needs(context_incompetent)
    print("Unsatisfied level: ESTEEM")
    print(f"Generated {len(goals)} goal(s):")
    for i, goal in enumerate(goals, 1):
        print(f"  {i}. {goal.goal}")
        print(f"     Priority: {goal.priority:.2f}, Drive: {goal.drive.value}")
    print()

    # Scenario 4: All needs satisfied - self-actualization
    print("Scenario 4: SELF-ACTUALIZATION")
    print("-" * 80)
    context_thriving = {
        "metrics": {
            "error_rate": 0.01,
            "memory_usage_percent": 40.0,
        },
        "collaboration_metrics": {
            "success_rate": 0.85,
            "active_fano_pairs": 6,
        },
        "stigmergy_health": {
            "recent_receipts": 20,
            "learned_patterns": 10,
        },
        "capability_metrics": {
            "success_rates": {
                "research": 0.8,
                "implementation": 0.75,
                "debugging": 0.85,
            },
            "overall_success_rate": 0.80,
            "learning_trend": 0.1,
        },
    }

    try:
        goals = await maslow.evaluate_needs(context_thriving)
        print("All lower needs satisfied - pursuing SELF-ACTUALIZATION")
        print(f"Generated {len(goals)} growth goal(s):")
        for i, goal in enumerate(goals[:3], 1):  # Show first 3
            print(f"  {i}. {goal.goal}")
            print(f"     Priority: {goal.priority:.2f}, Drive: {goal.drive.value}")
        if len(goals) > 3:
            print(f"  ... and {len(goals) - 3} more growth goals")
    except RuntimeError as e:
        print("All lower needs satisfied - SELF-ACTUALIZATION available")
        print("(Self-actualization requires LLM service for creative goal generation)")
        print(f"Note: {str(e)[:80]}...")
    print()

    print("=" * 80)
    print("HIERARCHY PRINCIPLE: Lower needs MUST be satisfied before higher needs")
    print("=" * 80)


async def demo_need_status_details() -> None:
    """Show detailed need status for each level."""
    maslow = MaslowHierarchy()

    context = {
        "metrics": {
            "error_rate": 0.01,
            "memory_usage_percent": 40.0,
        },
        "collaboration_metrics": {
            "success_rate": 0.75,
            "active_fano_pairs": 4,
        },
        "stigmergy_health": {
            "recent_receipts": 12,
            "learned_patterns": 5,
        },
        "capability_metrics": {
            "success_rates": {
                "research": 0.8,
                "implementation": 0.65,
                "debugging": 0.7,
            },
            "overall_success_rate": 0.72,
            "learning_trend": 0.05,
        },
    }

    print()
    print("=" * 80)
    print("DETAILED NEED STATUS")
    print("=" * 80)
    print()

    # Check each level individually
    physio = await maslow._check_physiological(context)
    print(f"1. PHYSIOLOGICAL: {'✅ SATISFIED' if physio.satisfied else '❌ UNSATISFIED'}")
    print(f"   Score: {physio.score:.3f} / {maslow._thresholds[physio.level]:.3f}")
    print()

    safety = await maslow._check_safety(context)
    print(f"2. SAFETY: {'✅ SATISFIED' if safety.satisfied else '❌ UNSATISFIED'}")
    print(f"   Score: {safety.score:.3f} / {maslow._thresholds[safety.level]:.3f}")
    print()

    belonging = await maslow._check_belonging(context)
    print(f"3. BELONGING: {'✅ SATISFIED' if belonging.satisfied else '❌ UNSATISFIED'}")
    print(f"   Score: {belonging.score:.3f} / {maslow._thresholds[belonging.level]:.3f}")
    print()

    esteem = await maslow._check_esteem(context)
    print(f"4. ESTEEM: {'✅ SATISFIED' if esteem.satisfied else '❌ UNSATISFIED'}")
    print(f"   Score: {esteem.score:.3f} / {maslow._thresholds[esteem.level]:.3f}")
    print()

    print("5. SELF-ACTUALIZATION: Available when all lower needs satisfied")
    print()


if __name__ == "__main__":
    print()
    asyncio.run(demo_hierarchy_progression())
    asyncio.run(demo_need_status_details())
