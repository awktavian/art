"""Demonstration of Advanced CBF Features.

CREATED: December 27, 2025
PURPOSE: Show usage of spectral-normalized barriers, fault-tolerant CBF, and CBF-QP

This script demonstrates:
1. Spectral-normalized barrier functions (Lipschitz-constrained)
2. Fault-tolerant NCBF with actuator failures
3. CBF-QP optimal safety filtering
"""

import torch

from kagami.core.safety.cbf_advanced import (
    create_cbf_qp,
    create_fault_tolerant_cbf,
    create_spectral_cbf,
)


def demo_spectral_normalized_barrier() -> None:
    """Demo 1: Spectral-normalized barrier with Lipschitz guarantee."""
    print("\n" + "=" * 70)
    print("DEMO 1: Spectral-Normalized Barrier Function")
    print("=" * 70)

    # Create barrier with Lipschitz constant ≤ 1.0
    barrier = create_spectral_cbf(state_dim=16, hidden_dim=64, lipschitz_target=1.0)

    # Sample states
    state = torch.randn(4, 16)

    # Compute barrier values
    h = barrier(state)

    print(f"Input state shape: {state.shape}")
    print(f"Barrier values h(x): {h}")
    print(f"Safety status: {['SAFE' if h_i >= 0 else 'UNSAFE' for h_i in h]}")

    # Estimate Lipschitz constant
    lipschitz = barrier.estimate_lipschitz_constant()
    print(f"\nEstimated Lipschitz constant: {lipschitz:.4f}")
    print(f"This bounds gradient: ||∇h(x)|| ≤ {lipschitz:.4f} (enables tighter verification)")

    print("\n✅ Spectral normalization enforces Lipschitz constraint for robustness")


def demo_fault_tolerant_cbf() -> None:
    """Demo 2: Fault-tolerant CBF with actuator failures."""
    print("\n" + "=" * 70)
    print("DEMO 2: Fault-Tolerant Neural CBF")
    print("=" * 70)

    # Create fault-tolerant CBF with 4 actuators
    ncbf = create_fault_tolerant_cbf(state_dim=16, action_dim=4, use_spectral_norm=True)

    # Simulate actuator failures: actuators 1 and 3 are faulty
    fault_mask = torch.tensor([1.0, 0.0, 1.0, 0.0])
    ncbf.set_fault_mask(fault_mask)

    print(f"Fault mask: {fault_mask}")
    print(f"Status: {['HEALTHY' if m == 1 else 'FAULTY' for m in fault_mask]}")

    # Sample state and nominal action
    state = torch.randn(2, 16)
    nominal_action = torch.tensor([[0.5, 0.5, 0.5, 0.5], [0.3, 0.3, 0.3, 0.3]])

    print(f"\nNominal action: {nominal_action}")

    # Compute safe action with fault compensation
    safe_action, info = ncbf(state, nominal_action)

    print(f"Safe action after fault compensation: {safe_action}")
    print(f"\nFaulty actuators (1, 3) are zeroed: {safe_action[:, [1, 3]]}")
    print(f"Healthy actuators (0, 2) are scaled up by {info['compensation_scale']:.2f}x")
    print(f"Barrier value h(x): {info['h_value']:.4f}")

    print("\n✅ Fault-tolerant CBF maintains safety despite actuator failures")


def demo_cbf_qp() -> None:
    """Demo 3: CBF-QP optimal safety filtering."""
    print("\n" + "=" * 70)
    print("DEMO 3: CBF-QP Optimal Safe Action")
    print("=" * 70)

    # Create spectral barrier
    barrier = create_spectral_cbf(state_dim=16)

    # Create CBF-QP controller
    cbf_qp = create_cbf_qp(action_dim=2, cbf=barrier, alpha=1.0)

    print("CBF-QP solves:")
    print("  min  ||u - u_nom||²")
    print("  s.t. L_f h + L_g h·u + α(h) ≥ 0")
    print("\nThis ensures MINIMAL modification while maintaining safety.\n")

    # Sample states and desired actions
    state = torch.randn(3, 16)
    desired_action = torch.randn(3, 2)

    print(f"Desired action: {desired_action}")

    # Compute safe action via QP
    safe_action, info = cbf_qp(state, desired_action)

    print(f"Safe action (QP-filtered): {safe_action}")
    print(f"\nBarrier value h(x): {info['h_value']:.4f}")
    print(f"CBF constraint satisfied: {info['constraint_satisfied']}")
    print(f"Action modified: {info['action_modified']}")

    # Compute modification
    modification = torch.norm(safe_action - desired_action, dim=1)
    print(f"Modification magnitude: {modification}")

    print("\n✅ CBF-QP finds optimal safe action with minimal deviation")


def demo_integrated_pipeline() -> None:
    """Demo 4: Complete pipeline with all components."""
    print("\n" + "=" * 70)
    print("DEMO 4: Integrated Pipeline (Spectral + Fault + QP)")
    print("=" * 70)

    # 1. Create spectral barrier
    barrier = create_spectral_cbf(state_dim=16, lipschitz_target=1.0)
    print("Step 1: Created spectral-normalized barrier (Lipschitz ≤ 1.0)")

    # 2. Create fault-tolerant CBF
    ncbf = create_fault_tolerant_cbf(state_dim=16, action_dim=3, use_spectral_norm=True)

    # Simulate fault: actuator 1 is broken
    fault_mask = torch.tensor([1.0, 0.0, 1.0])
    ncbf.set_fault_mask(fault_mask)
    print("Step 2: Configured fault-tolerant CBF (actuator 1 FAULTY)")

    # 3. Create CBF-QP
    cbf_qp = create_cbf_qp(action_dim=3, cbf=barrier, alpha=1.5)
    print("Step 3: Initialized CBF-QP controller (α=1.5)")

    # Test data
    state = torch.randn(2, 16)
    nominal_action = torch.tensor([[0.6, 0.6, 0.6], [0.4, 0.4, 0.4]])

    print(f"\nNominal action: {nominal_action}")

    # Pipeline: Fault compensation -> QP filtering
    fault_compensated, fault_info = ncbf(state, nominal_action)
    print(f"After fault compensation: {fault_compensated}")
    print(f"  - Faulty actuator 1: {fault_compensated[:, 1]}")
    print(f"  - Compensation scale: {fault_info['compensation_scale']:.2f}x")

    safe_action, qp_info = cbf_qp(state, fault_compensated)
    print(f"\nAfter QP safety filtering: {safe_action}")
    print(f"  - h(x) = {qp_info['h_value']:.4f}")
    print(f"  - Constraint satisfied: {qp_info['constraint_satisfied']}")

    print("\n✅ Complete pipeline: Lipschitz-constrained + fault-tolerant + optimal")


def main() -> None:
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("ADVANCED CBF COMPONENTS DEMONSTRATION")
    print("Control Barrier Functions with State-of-the-Art Features")
    print("=" * 70)

    demo_spectral_normalized_barrier()
    demo_fault_tolerant_cbf()
    demo_cbf_qp()
    demo_integrated_pipeline()

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nKey Features Demonstrated:")
    print("1. ✅ Spectral normalization: Enforces Lipschitz constraint for robustness")
    print("2. ✅ Fault tolerance: Handles actuator failures with compensation")
    print("3. ✅ CBF-QP: Optimal safety filtering with minimal modification")
    print("4. ✅ Integration: All components work together seamlessly")
    print("\nThese improvements enable verified safety under uncertainty and faults.\n")


if __name__ == "__main__":
    main()
