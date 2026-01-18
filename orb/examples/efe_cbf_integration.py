"""EFE-CBF Integration Example - Safe Policy Selection.

CREATED: December 14, 2025
PURPOSE: Demonstrate complete pipeline from EFE computation to CBF-constrained
         policy selection.

PIPELINE:
========
1. Initialize world model (OrganismRSSM)
2. Create EFE module (ExpectedFreeEnergy)
3. Create CBF module (OptimalCBF)
4. Create optimizer (EFECBFOptimizer)
5. Generate policies
6. Compute EFE for each policy
7. Apply CBF constraints
8. Select safe policy with minimum G

MODES:
=====
- Training: Soft penalty (differentiable)
- Deployment: Hard QP constraint (guaranteed safe)
"""

import torch
import torch.nn.functional as F

from kagami.core.active_inference import (
    EFECBFConfig,
    EFECBFOptimizer,
)
from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig


def example_soft_mode():
    """Example: Training with soft penalty."""
    print("=" * 80)
    print("TRAINING MODE: Soft Penalty")
    print("=" * 80)

    # Configuration
    state_dim = 256
    stochastic_dim = 14
    action_dim = 8
    num_policies = 32
    horizon = 5
    batch = 1

    # Create CBF
    cbf_config = OptimalCBFConfig(
        observation_dim=state_dim + stochastic_dim,
        state_dim=state_dim,
        control_dim=action_dim,
        use_qp_solver=True,
        use_uncertainty=True,
    )
    cbf = OptimalCBF(cbf_config)

    # Create optimizer
    optimizer_config = EFECBFConfig(
        state_dim=state_dim,
        stochastic_dim=stochastic_dim,
        action_dim=action_dim,
        penalty_weight=10.0,
    )
    optimizer = EFECBFOptimizer(optimizer_config, cbf)
    optimizer.train()

    # Simulate EFE computation results
    # In real usage, these come from ExpectedFreeEnergy.forward()
    G_values = torch.randn(batch, num_policies) * 2.0

    # Simulate state trajectories (mean state for each policy)
    states = torch.randn(batch, num_policies, state_dim + stochastic_dim) * 0.5

    # Simulate policies
    policies = torch.randn(batch, num_policies, horizon, action_dim)
    policies = F.normalize(policies, dim=-1)  # Normalize to E8

    print("Input:")
    print(f"  G values: {G_values.shape} (range: [{G_values.min():.2f}, {G_values.max():.2f}])")
    print(f"  States: {states.shape}")
    print(f"  Policies: {policies.shape}")

    # Apply soft constraints
    G_safe, info = optimizer(G_values, states, policies, training=True)

    print("\nSoft Constraint Results:")
    print(f"  Mode: {info['mode']}")
    print(f"  G_safe: {G_safe.shape}")
    print(f"  CBF penalty: {info['cbf_penalty']:.4f}")
    print(f"  Penalty weight: {info['penalty_weight']:.2f}")
    print(f"  Violations: {info['num_violations']}/{batch * num_policies}")
    print(f"  All safe: {info['constraint_satisfied']}")

    # Select best safe policy
    selected, idx, selection_info = optimizer.select_safe_policy(G_values, states, policies)

    print("\nSelected Policy:")
    print(f"  Index: {idx}")
    print(f"  G value: {selection_info['selected_G']:.4f}")
    print(f"  Shape: {selected.shape}")

    # Compute training loss
    loss = G_safe.mean() + 0.1 * info["cbf_penalty"]
    print(f"\nTraining Loss: {loss.item():.4f}")
    print(f"  (G component: {G_safe.mean().item():.4f})")
    print(f"  (Penalty component: {0.1 * info['cbf_penalty']:.4f})")


def example_hard_mode():
    """Example: Deployment with hard QP constraint."""
    print("\n" + "=" * 80)
    print("DEPLOYMENT MODE: Hard QP Constraint")
    print("=" * 80)

    # Configuration (same as training)
    state_dim = 256
    stochastic_dim = 14
    action_dim = 8
    num_policies = 16
    horizon = 5
    batch = 1

    # Create pre-trained CBF and optimizer
    cbf_config = OptimalCBFConfig(
        observation_dim=state_dim + stochastic_dim,
        state_dim=state_dim,
        control_dim=action_dim,
        use_qp_solver=True,
        qp_solver="analytical",
    )
    cbf = OptimalCBF(cbf_config)

    optimizer_config = EFECBFConfig(
        state_dim=state_dim,
        stochastic_dim=stochastic_dim,
        action_dim=action_dim,
        qp_solver_method="analytical",
    )
    optimizer = EFECBFOptimizer(optimizer_config, cbf)
    optimizer.eval()

    # Simulate EFE results
    G_values = torch.randn(batch, num_policies) * 2.0
    states = torch.randn(batch, num_policies, state_dim + stochastic_dim)
    policies = torch.randn(batch, num_policies, horizon, action_dim)
    policies = F.normalize(policies, dim=-1)

    print("Input:")
    print(f"  G values: {G_values.shape}")
    print(f"  States: {states.shape}")
    print(f"  Policies: {policies.shape}")

    # Apply hard constraints
    safe_policies, info = optimizer(G_values, states, policies, training=False)

    print("\nHard Constraint Results:")
    print(f"  Mode: {info['mode']}")
    print(f"  Safe policies: {safe_policies.shape}")
    print(f"  Violations detected: {info['num_violations']}")
    print(f"  QP corrections applied: {info['qp_corrections']:.4f}")
    print(f"  Max correction: {info['max_correction']:.4f}")
    print(f"  All safe: {info['constraint_satisfied']}")

    # Select best safe policy
    selected, idx, selection_info = optimizer.select_safe_policy(
        G_values, states, policies, training=False
    )

    print("\nSelected Safe Policy:")
    print(f"  Index: {idx}")
    print(f"  G value: {selection_info['selected_G']:.4f}")
    print(f"  Shape: {selected.shape}")


def example_statistics():
    """Example: Tracking safety statistics over time."""
    print("\n" + "=" * 80)
    print("SAFETY STATISTICS TRACKING")
    print("=" * 80)

    state_dim = 256
    stochastic_dim = 14
    action_dim = 8
    num_policies = 10
    horizon = 3

    optimizer = EFECBFOptimizer(
        config=EFECBFConfig(
            state_dim=state_dim,
            stochastic_dim=stochastic_dim,
            action_dim=action_dim,
        )
    )
    optimizer.train()

    # Run multiple iterations
    num_iterations = 5
    for _i in range(num_iterations):
        batch = 2
        G_values = torch.randn(batch, num_policies)
        states = torch.randn(batch, num_policies, state_dim + stochastic_dim)
        policies = torch.randn(batch, num_policies, horizon, action_dim)

        _, _ = optimizer(G_values, states, policies, training=True)

    # Get statistics
    stats = optimizer.get_statistics()

    print(f"Statistics after {num_iterations} iterations:")
    print(f"  Total evaluations: {stats['total_evaluations']}")
    print(f"  Total violations: {stats['total_violations']}")
    print(f"  Violation rate: {stats['violation_rate']:.2%}")

    # Reset
    optimizer.reset_statistics()
    stats = optimizer.get_statistics()
    print("\nAfter reset:")
    print(f"  Total evaluations: {stats['total_evaluations']}")
    print(f"  Total violations: {stats['total_violations']}")


def example_gradient_based_training():
    """Example: End-to-end gradient-based training."""
    print("\n" + "=" * 80)
    print("GRADIENT-BASED TRAINING")
    print("=" * 80)

    state_dim = 64  # Smaller for faster training
    stochastic_dim = 8
    action_dim = 4
    num_policies = 8
    horizon = 3
    batch = 2

    # Create optimizer
    optimizer = EFECBFOptimizer(
        config=EFECBFConfig(
            state_dim=state_dim,
            stochastic_dim=stochastic_dim,
            action_dim=action_dim,
            penalty_weight=5.0,
        )
    )
    optimizer.train()

    # Create optimizer for CBF parameters
    cbf_optimizer = torch.optim.Adam(optimizer.cbf.parameters(), lr=1e-3)

    print("Training for 3 steps...")
    for step in range(3):
        cbf_optimizer.zero_grad()

        # Simulate batch
        G_values = torch.randn(batch, num_policies, requires_grad=True)
        states = torch.randn(batch, num_policies, state_dim + stochastic_dim)
        policies = torch.randn(batch, num_policies, horizon, action_dim)

        # Forward
        G_safe, info = optimizer(G_values, states, policies, training=True)

        # Loss: minimize safe G + penalty
        loss = G_safe.mean() + 0.1 * info["cbf_penalty"]

        # Backward
        loss.backward()
        cbf_optimizer.step()

        print(
            f"  Step {step}: loss={loss.item():.4f}, "
            f"penalty={info['cbf_penalty']:.4f}, "
            f"violations={info['num_violations']}"
        )

    print("Training complete!")


if __name__ == "__main__":
    # Run all examples
    example_soft_mode()
    example_hard_mode()
    example_statistics()
    example_gradient_based_training()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)
