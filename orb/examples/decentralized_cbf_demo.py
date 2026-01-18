"""Decentralized Multi-Colony CBF Demo.

This script demonstrates:
1. Creating a decentralized CBF for 7 colonies
2. Checking compositional safety
3. Filtering controls for safety
4. Training with safety penalties
5. Visualizing Fano neighbor coupling

Usage:
    python examples/decentralized_cbf_demo.py
"""

from __future__ import annotations

import torch

from kagami.core.safety.decentralized_cbf import (
    create_decentralized_cbf,
    verify_compositional_safety,
    FANO_NEIGHBORS,
)
from kagami_math.fano_plane import FANO_LINES


def demo_basic_safety():
    """Demo 1: Basic safety checking."""
    print("=" * 70)
    print("DEMO 1: Basic Safety Checking")
    print("=" * 70)

    # Create DCBF
    dcbf = create_decentralized_cbf(state_dim=4, hidden_dim=64)

    B = 4  # batch size

    # Scenario 1: All colonies safe (low risk)
    print("\n--- Scenario 1: Safe States ---")
    x_safe = torch.randn(B, 7, 4) * 0.1 + 0.2  # Low risk, centered at 0.2

    h_safe = dcbf(x_safe)
    is_safe = dcbf.is_safe(x_safe)

    print(f"Barrier values (h):\n{h_safe}")
    print(f"All safe: {is_safe.all().item()}")
    print(f"Safety rate: {is_safe.float().mean().item():.2%}")

    # Scenario 2: Colony 0 (Spark) unsafe
    print("\n--- Scenario 2: Spark Unsafe ---")
    x_unsafe = x_safe.clone()
    x_unsafe[:, 0, :] = torch.tensor([0.9, 0.9, 0.9, 0.9])  # High threat

    h_unsafe = dcbf(x_unsafe)
    is_safe_2 = dcbf.is_safe(x_unsafe)
    unsafe_mask = dcbf.get_unsafe_colonies(x_unsafe)

    print(f"Barrier values (h):\n{h_unsafe}")
    print(f"All safe: {is_safe_2.all().item()}")
    print(f"Unsafe colonies (first sample): {unsafe_mask[0].nonzero().squeeze().tolist()}")


def demo_control_filtering():
    """Demo 2: Control filtering for safety."""
    print("\n" + "=" * 70)
    print("DEMO 2: Control Filtering")
    print("=" * 70)

    dcbf = create_decentralized_cbf(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4) * 0.2 + 0.3  # Mixed risk states

    # Generate nominal controls
    u_nominal = torch.rand(B, 7, 2)  # [aggression, speed]

    print("\nNominal controls (sample 0):")
    print(u_nominal[0])

    # Filter through DCBF
    u_safe, penalty, info = dcbf.filter_control(x, u_nominal, control_dim=2)

    print("\nSafe controls (sample 0):")
    print(u_safe[0])

    print(f"\nSafety penalty: {penalty.item():.4f}")
    print(f"All safe: {info['all_safe']}")
    print(f"Min barrier: {info['min_barrier']:.4f}")
    print(f"Unsafe colonies: {info['unsafe_colonies']}")


def demo_compositional_verification():
    """Demo 3: Compositional safety verification."""
    print("\n" + "=" * 70)
    print("DEMO 3: Compositional Safety Verification")
    print("=" * 70)

    dcbf = create_decentralized_cbf(state_dim=4, hidden_dim=64)

    B = 16
    x = torch.randn(B, 7, 4) * 0.2 + 0.3

    # Run verification
    result = verify_compositional_safety(dcbf, x, threshold=0.0)

    print("\n=== Safety Verification Report ===")
    print(f"All safe: {result['all_safe']}")
    print(f"Batch safety rate: {result['batch_safety_rate']:.2%}")
    print(f"Min barrier: {result['min_barrier']:.4f}")
    print(f"Mean barrier: {result['mean_barrier']:.4f}")
    print(f"Max barrier: {result['max_barrier']:.4f}")
    print(f"Unsafe colonies per sample: {result['unsafe_colonies_per_sample']:.2f}")

    print("\nPer-colony safety rates:")
    colony_names = ["Spark", "Forge", "Flow", "Nexus", "Beacon", "Grove", "Crystal"]
    for i, (name, rate) in enumerate(
        zip(colony_names, result["per_colony_safety_rate"], strict=False)
    ):
        print(f"  {i}. {name:8s}: {rate:.2%}")

    if result["violated_fano_lines"]:
        print("\nViolated Fano lines:")
        for line in result["violated_fano_lines"]:
            colonies = [colony_names[i] for i in line["colonies"]]
            print(f"  Line {line['line_idx']}: {colonies}, {line['violations']} violations")


def demo_fano_coupling():
    """Demo 4: Fano neighbor coupling analysis."""
    print("\n" + "=" * 70)
    print("DEMO 4: Fano Neighbor Coupling")
    print("=" * 70)

    dcbf = create_decentralized_cbf(state_dim=4, hidden_dim=64)

    B = 16
    x = torch.randn(B, 7, 4) * 0.2 + 0.3

    # Measure coupling strength
    coupling = dcbf.get_fano_coupling_strength(x)

    print("\n=== Fano Line Coupling Strength ===")
    colony_names = ["Spark", "Forge", "Flow", "Nexus", "Beacon", "Grove", "Crystal"]

    for i, (line, strength) in enumerate(zip(FANO_LINES, coupling, strict=False)):
        # Convert to 0-indexed names
        line_0idx = [idx - 1 for idx in line]
        names = [colony_names[idx] for idx in line_0idx]
        print(f"Line {i} {{{', '.join(names)}}}: {strength.item():.4f}")

    print(f"\nMean coupling: {coupling.mean().item():.4f}")
    print(f"Max coupling: {coupling.max().item():.4f}")


def demo_training_loop():
    """Demo 5: Training with safety penalties."""
    print("\n" + "=" * 70)
    print("DEMO 5: Training with Safety Penalties")
    print("=" * 70)

    dcbf = create_decentralized_cbf(state_dim=4, hidden_dim=64)
    optimizer = torch.optim.Adam(dcbf.parameters(), lr=1e-3)

    B = 16
    num_steps = 100

    print("\nTraining DCBF to maximize safety...")
    print(f"Steps: {num_steps}, Batch size: {B}")

    for step in range(num_steps):
        # Generate random states
        x = torch.randn(B, 7, 4) * 0.3 + 0.4

        # Compute safety penalty (minimize negative barrier values)
        penalty = dcbf.compute_safety_penalty(x, margin=0.1)

        # Backward pass
        optimizer.zero_grad()
        penalty.backward()
        optimizer.step()

        if (step + 1) % 20 == 0:
            with torch.no_grad():
                h = dcbf(x)
                min_h = h.min().item()
                mean_h = h.mean().item()
                safe_rate = (h >= 0).float().mean().item()

            print(
                f"Step {step + 1:3d}: "
                f"penalty={penalty.item():.4f}, "
                f"h_min={min_h:+.4f}, h_mean={mean_h:+.4f}, "
                f"safe={safe_rate:.2%}"
            )

    print("\nTraining complete!")


def demo_neighbor_structure():
    """Demo 6: Visualize Fano neighbor structure."""
    print("\n" + "=" * 70)
    print("DEMO 6: Fano Neighbor Structure")
    print("=" * 70)

    colony_names = ["Spark", "Forge", "Flow", "Nexus", "Beacon", "Grove", "Crystal"]

    print("\n=== Neighbor Map (via Fano Plane) ===")
    for i, neighbors in FANO_NEIGHBORS.items():
        name = colony_names[i]
        neighbor_names = [colony_names[j] for j in neighbors]
        print(f"{i}. {name:8s} → {', '.join(neighbor_names)}")

    print("\n=== Fano Lines (3-colony compositions) ===")
    for i, line in enumerate(FANO_LINES):
        line_0idx = [idx - 1 for idx in line]
        names = [colony_names[idx] for idx in line_0idx]
        print(f"Line {i}: {{{', '.join(names)}}}")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("DECENTRALIZED MULTI-COLONY CBF DEMONSTRATION")
    print("=" * 70)
    print("\nThis demo showcases the decentralized Control Barrier Function")
    print("implementation for KagamiOS's 7-colony architecture.")
    print("\n7 Colonies: Spark, Forge, Flow, Nexus, Beacon, Grove, Crystal")
    print("Safety Property: ∀i: h_i ≥ 0 ⟹ system safe")

    demo_neighbor_structure()
    demo_basic_safety()
    demo_control_filtering()
    demo_compositional_verification()
    demo_fano_coupling()
    demo_training_loop()

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nSee docs/DECENTRALIZED_CBF_INTEGRATION.md for integration guide.")


if __name__ == "__main__":
    torch.manual_seed(42)  # Reproducibility
    main()
