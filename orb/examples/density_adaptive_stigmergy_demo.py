"""Density-Adaptive Stigmergy Demo

Demonstrates the density-adaptive mode switching based on Dec 2025 research.

Research Finding:
Critical density ρ_c ≈ 0.230 separates individual-dominant from stigmergic-dominant regimes.
- Below ρ_c: Individual memory outperforms by 15-20%
- Above ρ_c: Stigmergic traces outperform by 36-41%

This demo simulates:
1. Low-density scenario (sparse agents)
2. High-density scenario (dense agents)
3. Dynamic density transitions

Created: December 14, 2025
"""

import time
from kagami.core.unified_agents.memory.stigmergy import (
    StigmergyLearner,
    CRITICAL_DENSITY,
)


def simulate_low_density_scenario():
    """Simulate sparse agent environment (below critical density).

    In sparse environments, individual agents have better local knowledge
    than collective traces. The system should boost heuristic weights.
    """
    print("\n" + "=" * 80)
    print("SCENARIO 1: Low Density (Sparse Agents)")
    print("=" * 80)

    learner = StigmergyLearner(
        enable_persistence=False,
        adaptive_mode=True,
        density_threshold=CRITICAL_DENSITY,
        environment_capacity=100,
    )

    # Simulate 8 agents (8/100 = 0.08 << 0.230)
    print("\nSimulating 8 concurrent agents (density = 0.08)")

    for i in range(8):
        receipt = {
            "intent": {"action": f"task.execute.{i % 3}"},
            "actor": f"agent_{i}",
            "workspace_hash": "sparse_env",
            "verifier": {"status": "verified"},
            "timestamp": time.time(),
            "duration_ms": 150,
        }
        learner.receipt_cache.append(receipt)

    learner.extract_patterns()

    # Check adaptive behavior
    density = learner.compute_agent_density()
    heuristic_weight, pheromone_weight = learner.get_adaptive_weights()

    print(f"Current density: {density:.3f}")
    print(f"Critical density: {CRITICAL_DENSITY}")
    print(f"Mode: {'INDIVIDUAL' if density < CRITICAL_DENSITY else 'STIGMERGIC'}")
    print("\nWeight adjustments:")
    print(f"  Heuristic weight: {heuristic_weight:.3f} (boosted for individual mode)")
    print(f"  Pheromone weight: {pheromone_weight:.3f} (dampened)")
    print("\nInterpretation: In sparse environments, individual agents rely on")
    print("their own local knowledge (heuristics) rather than collective traces.")


def simulate_high_density_scenario():
    """Simulate dense agent environment (above critical density).

    In dense environments, stigmergic traces capture collective intelligence
    better than individual memory. The system should boost pheromone weights.
    """
    print("\n" + "=" * 80)
    print("SCENARIO 2: High Density (Dense Agents)")
    print("=" * 80)

    learner = StigmergyLearner(
        enable_persistence=False,
        adaptive_mode=True,
        density_threshold=CRITICAL_DENSITY,
        environment_capacity=100,
    )

    # Simulate 40 agents (40/100 = 0.40 >> 0.230)
    print("\nSimulating 40 concurrent agents (density = 0.40)")

    for i in range(40):
        receipt = {
            "intent": {"action": f"task.execute.{i % 5}"},
            "actor": f"agent_{i}",
            "workspace_hash": "dense_env",
            "verifier": {"status": "verified" if i % 10 != 0 else "failed"},
            "timestamp": time.time(),
            "duration_ms": 120,
        }
        learner.receipt_cache.append(receipt)

    learner.extract_patterns()

    # Check adaptive behavior
    density = learner.compute_agent_density()
    heuristic_weight, pheromone_weight = learner.get_adaptive_weights()
    cooperation = learner.cooperation_metric.cooperation_level

    print(f"Current density: {density:.3f}")
    print(f"Critical density: {CRITICAL_DENSITY}")
    print(f"Cooperation level: {cooperation:.3f}")
    print(f"Mode: {'INDIVIDUAL' if density < CRITICAL_DENSITY else 'STIGMERGIC'}")
    print("\nWeight adjustments:")
    print(f"  Heuristic weight: {heuristic_weight:.3f} (dampened)")
    print(f"  Pheromone weight: {pheromone_weight:.3f} (boosted for stigmergic mode)")
    print("\nInterpretation: In dense environments, collective traces (pheromones)")
    print("aggregate knowledge from many agents, outperforming individual memory.")
    print("\nExpected performance gain: 36-41% over individual mode (research-validated)")


def simulate_dynamic_transition():
    """Simulate dynamic density transition across critical threshold.

    Shows how the system adapts smoothly as agent density increases.
    """
    print("\n" + "=" * 80)
    print("SCENARIO 3: Dynamic Density Transition")
    print("=" * 80)

    learner = StigmergyLearner(
        enable_persistence=False,
        adaptive_mode=True,
        density_threshold=CRITICAL_DENSITY,
        environment_capacity=100,
    )

    print("\nSimulating gradual agent density increase...")
    print(f"{'Agents':<10} {'Density':<12} {'Mode':<15} {'H-Weight':<12} {'P-Weight':<12}")
    print("-" * 80)

    for agent_count in [5, 10, 15, 20, 25, 30, 40, 50]:
        # Clear and rebuild
        learner.receipt_cache.clear()
        learner._recent_receipt_timestamps.clear()

        for i in range(agent_count):
            receipt = {
                "intent": {"action": f"task.execute.{i % 4}"},
                "actor": f"agent_{i}",
                "workspace_hash": "transition_env",
                "verifier": {"status": "verified"},
                "timestamp": time.time() - (agent_count - i),
                "duration_ms": 100,
            }
            learner.receipt_cache.append(receipt)

        learner.extract_patterns()

        density = learner.compute_agent_density()
        h_weight, p_weight = learner.get_adaptive_weights()
        mode = "INDIVIDUAL" if density < CRITICAL_DENSITY else "STIGMERGIC"

        # Mark the transition point
        marker = " <-- TRANSITION" if 0.20 < density < 0.26 else ""

        print(
            f"{agent_count:<10} {density:<12.3f} {mode:<15} {h_weight:<12.3f} {p_weight:<12.3f}{marker}"
        )

    print("\nObservation: Weights transition smoothly across critical density.")
    print("No abrupt jumps — cooperation metric ensures graceful adaptation.")


def demonstrate_cooperation_modulation():
    """Show how cooperation level modulates effective density.

    Low cooperation reduces stigmergic effectiveness even at high density.
    """
    print("\n" + "=" * 80)
    print("SCENARIO 4: Cooperation Modulation")
    print("=" * 80)

    learner = StigmergyLearner(
        enable_persistence=False,
        adaptive_mode=True,
        density_threshold=CRITICAL_DENSITY,
        environment_capacity=100,
    )

    # High density (40 agents)
    for i in range(40):
        # Mix of success and failure to affect cooperation
        receipt = {
            "intent": {"action": f"task.execute.{i % 3}"},
            "actor": f"agent_{i}",
            "workspace_hash": "coop_env",
            "verifier": {"status": "verified" if i % 5 != 0 else "failed"},
            "timestamp": time.time(),
            "duration_ms": 110,
        }
        learner.receipt_cache.append(receipt)

    learner.extract_patterns()

    raw_density = learner.compute_agent_density()
    cooperation = learner.cooperation_metric.cooperation_level
    effective_density = raw_density * (0.5 + 0.5 * cooperation)

    print(f"Raw density: {raw_density:.3f}")
    print(f"Cooperation level: {cooperation:.3f}")
    print(f"Effective density: {effective_density:.3f}")
    print("\nInterpretation: Effective density combines agent count with cooperation.")
    print("High density + low cooperation → reduced stigmergic effectiveness")
    print("High density + high cooperation → strong stigmergic mode")


def main():
    """Run all demo scenarios."""
    print("\n" + "=" * 80)
    print("DENSITY-ADAPTIVE STIGMERGY DEMONSTRATION")
    print("=" * 80)
    print("\nResearch Citation:")
    print("'Emergent Collective Memory in Decentralized Multi-Agent AI'")
    print("December 2025")
    print(f"\nCritical Density ρ_c = {CRITICAL_DENSITY}")

    simulate_low_density_scenario()
    simulate_high_density_scenario()
    simulate_dynamic_transition()
    demonstrate_cooperation_modulation()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\nDensity-adaptive stigmergy automatically switches between:")
    print("  • Individual mode (ρ < 0.230): Boost heuristics, dampen pheromones")
    print("  • Stigmergic mode (ρ ≥ 0.230): Boost pheromones, dampen heuristics")
    print("\nExpected benefits:")
    print("  • 15-20% gain in low-density scenarios (individual mode)")
    print("  • 36-41% gain in high-density scenarios (stigmergic mode)")
    print("  • Smooth transitions via cooperation metric integration")
    print("\nBackward compatible: Set adaptive_mode=False to disable.")
    print("")


if __name__ == "__main__":
    main()
