"""Example: G₂-Equivariant Gradient Surgery for Multi-Colony Training.

This example demonstrates how to use octonion gradient surgery to train
7 colonies simultaneously without gradient conflicts.

Created: December 14, 2025
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.optim as optim

from kagami.core.learning.octonion_gradient_surgery import (
    G2ParameterGroups,
    OctonionGradientSurgery,
    apply_octonion_gradient_surgery,
)


# =============================================================================
# EXAMPLE 1: G₂ PARAMETER GROUPS (RECOMMENDED)
# =============================================================================


class MultiColonyModel(nn.Module):
    """Example model with G₂-structured parameters.

    Key design principle: Separate parameters for each colony to prevent conflicts.
    """

    def __init__(self, d_model: int = 64) -> None:
        super().__init__()

        # Global parameters (shared across all colonies)
        self.global_embedding = nn.Linear(d_model, d_model)

        # Colony-specific parameters (one per colony)
        # These will be automatically detected by G2ParameterGroups
        self.colony_0_layer = nn.Linear(d_model, d_model)
        self.colony_1_layer = nn.Linear(d_model, d_model)
        self.colony_2_layer = nn.Linear(d_model, d_model)
        self.colony_3_layer = nn.Linear(d_model, d_model)
        self.colony_4_layer = nn.Linear(d_model, d_model)
        self.colony_5_layer = nn.Linear(d_model, d_model)
        self.colony_6_layer = nn.Linear(d_model, d_model)

        # Coupling parameters (Fano lines)
        self.fano_coupling = nn.Linear(d_model, d_model)

        # Output layer
        self.output = nn.Linear(d_model, d_model)

    def forward(self, x: torch.Tensor, colony_idx: int) -> torch.Tensor:
        """Forward pass for a specific colony.

        Args:
            x: Input tensor [batch, d_model]
            colony_idx: Colony index (0-6)

        Returns:
            Output tensor [batch, d_model]
        """
        # Global processing
        x = self.global_embedding(x)

        # Colony-specific processing
        colony_layers = [
            self.colony_0_layer,
            self.colony_1_layer,
            self.colony_2_layer,
            self.colony_3_layer,
            self.colony_4_layer,
            self.colony_5_layer,
            self.colony_6_layer,
        ]
        x = colony_layers[colony_idx](x)

        # Coupling
        x = self.fano_coupling(x)

        # Output
        x = self.output(x)

        return x


def example_g2_parameter_groups() -> None:
    """Example: Train with G₂ parameter groups (safe mode)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: G₂ Parameter Groups (Safe Mode)")
    print("=" * 80)

    # Create model
    model = MultiColonyModel(d_model=32)

    # Examine parameter groups
    param_groups = G2ParameterGroups.from_model(model)
    summary = param_groups.summary()

    print("\nParameter Group Summary:")
    print(f"  Global parameters: {summary['global_params']:,}")
    print(f"  Colony parameters: {summary['total_colony_params']:,}")
    print(f"  Coupling parameters: {summary['coupling_params']:,}")
    print(f"  Total parameters: {summary['total_params']:,}")

    # Create synthetic training data
    batch_size = 8
    d_model = 32
    x = torch.randn(batch_size, d_model)
    targets = [torch.randn(batch_size, d_model) for _ in range(7)]

    # Training loop
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    for step in range(5):
        # Compute losses for each colony
        colony_losses = []
        for i, target in enumerate(targets):
            output = model(x, colony_idx=i)
            loss = ((output - target) ** 2).mean()
            colony_losses.append(loss)

        # Apply G₂ gradient surgery
        apply_octonion_gradient_surgery(
            model,
            colony_losses,
            mode="g2_groups",
        )

        # Update parameters
        optimizer.step()

        # Print progress
        avg_loss = sum(l.item() for l in colony_losses) / 7
        print(f"  Step {step}: avg_loss={avg_loss:.6f}")

    print("\n✓ G₂ parameter groups mode completed successfully")


# =============================================================================
# EXAMPLE 2: OCTONION PROJECTION (EXPERIMENTAL)
# =============================================================================


def example_octonion_projection() -> None:
    """Example: Train with octonion projection (experimental mode)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Octonion Projection (Experimental Mode)")
    print("=" * 80)

    # Create model
    model = MultiColonyModel(d_model=32)

    # Create synthetic training data
    batch_size = 8
    d_model = 32
    x = torch.randn(batch_size, d_model)
    targets = [torch.randn(batch_size, d_model) for _ in range(7)]

    # Training loop
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    for step in range(5):
        # Compute losses for each colony
        colony_losses = []
        for i, target in enumerate(targets):
            output = model(x, colony_idx=i)
            loss = ((output - target) ** 2).mean()
            colony_losses.append(loss)

        # Apply octonion projection
        result = apply_octonion_gradient_surgery(
            model,
            colony_losses,
            mode="octonion_projection",
            conflict_threshold=0.1,
        )

        # Update parameters
        optimizer.step()

        # Print progress
        avg_loss = sum(l.item() for l in colony_losses) / 7
        conflicts = result.get("total_conflicts", 0)
        projections = result.get("total_projections", 0)
        print(
            f"  Step {step}: avg_loss={avg_loss:.6f}, "
            f"conflicts={conflicts}, projections={projections}"
        )

    print("\n✓ Octonion projection mode completed successfully")


# =============================================================================
# EXAMPLE 3: FANO-AWARE PCGRAD
# =============================================================================


def example_fano_pcgrad() -> None:
    """Example: Train with Fano-aware PCGrad."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Fano-Aware PCGrad")
    print("=" * 80)

    # Create model
    model = MultiColonyModel(d_model=32)

    # Create synthetic training data
    batch_size = 8
    d_model = 32
    x = torch.randn(batch_size, d_model)
    targets = [torch.randn(batch_size, d_model) for _ in range(7)]

    # Training loop
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    for step in range(5):
        # Compute losses for each colony
        colony_losses = []
        for i, target in enumerate(targets):
            output = model(x, colony_idx=i)
            loss = ((output - target) ** 2).mean()
            colony_losses.append(loss)

        # Apply Fano-aware PCGrad
        result = apply_octonion_gradient_surgery(
            model,
            colony_losses,
            mode="fano_pcgrad",
            use_fano_alignment=True,
        )

        # Update parameters
        optimizer.step()

        # Print progress
        avg_loss = sum(l.item() for l in colony_losses) / 7
        stats = result.get("stats", {})
        conflict_rate = stats.get("conflict_rate", 0)
        print(f"  Step {step}: avg_loss={avg_loss:.6f}, conflict_rate={conflict_rate:.3f}")

    print("\n✓ Fano-aware PCGrad mode completed successfully")


# =============================================================================
# EXAMPLE 4: MANUAL GRADIENT SURGERY
# =============================================================================


def example_manual_surgery() -> None:
    """Example: Manual control over gradient surgery."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Manual Gradient Surgery")
    print("=" * 80)

    # Create model
    model = MultiColonyModel(d_model=32)

    # Create parameter groups
    param_groups = G2ParameterGroups.from_model(model)

    # Create surgery instance
    surgery = OctonionGradientSurgery(
        mode="g2_groups",
        use_fano_structure=True,
    )

    # Create synthetic training data
    batch_size = 8
    d_model = 32
    x = torch.randn(batch_size, d_model)
    targets = [torch.randn(batch_size, d_model) for _ in range(7)]

    # Training loop
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    params = list(model.parameters())

    for step in range(5):
        # Compute per-colony gradients
        colony_gradients: list[list[torch.Tensor | None]] = []

        for i, target in enumerate(targets):
            model.zero_grad()
            output = model(x, colony_idx=i)
            loss = ((output - target) ** 2).mean()
            loss.backward()

            # Save gradients
            grads = [p.grad.clone() if p.grad is not None else None for p in params]
            colony_gradients.append(grads)

        # Apply gradient surgery
        corrected = surgery.apply_g2_groups(colony_gradients, param_groups)

        # Average across colonies and set
        model.zero_grad()
        for param_idx, param in enumerate(params):
            grad_list = []
            for c in range(7):
                if param_idx < len(corrected[c]) and corrected[c][param_idx] is not None:
                    grad = corrected[c][param_idx]
                    if grad is not None:
                        grad_list.append(grad)

            if grad_list:
                param.grad = torch.stack(grad_list).mean(dim=0)

        # Update parameters
        optimizer.step()

        # Print progress
        avg_loss = (
            sum(((model(x, colony_idx=i) - targets[i]) ** 2).mean().item() for i in range(7)) / 7
        )
        print(f"  Step {step}: avg_loss={avg_loss:.6f}")

    print("\n✓ Manual gradient surgery completed successfully")


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Run all examples."""
    print("\n" + "=" * 80)
    print("G₂-Equivariant Gradient Surgery Examples")
    print("=" * 80)

    # Run examples
    example_g2_parameter_groups()
    example_octonion_projection()
    example_fano_pcgrad()
    example_manual_surgery()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
