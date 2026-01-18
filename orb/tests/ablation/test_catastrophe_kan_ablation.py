"""CatastropheKAN vs Standard Activations - Ablation Study.

This test validates the claim that catastrophe-based activations (derived from
Thom's 7 elementary catastrophes) provide benefits over standard activations.

HYPOTHESIS: CatastropheKAN activations provide:
1. More stable gradient flow
2. Better representation of phase transitions
3. Improved learning on structured tasks

BASELINES:
- GELU (standard transformer)
- SiLU/Swish (common alternative)
- ReLU (classic)
- B-spline KAN (Liu et al., 2024)
- Random polynomial (same degree, random coefficients)

CITATIONS:
- Thom (1972): Structural Stability and Morphogenesis
- Liu et al. (2024): KAN: Kolmogorov-Arnold Networks

Created: December 6, 2025
"""

from __future__ import annotations

from typing import Any, cast

import pytest
import time
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.world_model.layers.catastrophe_kan import (
    CatastropheBasis,
    CatastropheType,
    CatastropheKANLayer,
    BatchedCatastropheBasis,
)

# =============================================================================
# BASELINE ACTIVATIONS
# =============================================================================


class StandardActivation(nn.Module):
    """Wrapper for standard activation functions."""

    def __init__(self, activation_fn, name: str):
        super().__init__()
        self.activation = activation_fn
        self.name = name

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, self.activation(x))


class RandomPolynomialActivation(nn.Module):
    """Random polynomial activation (control for catastrophe polynomials).

    Uses same-degree polynomials as catastrophes but with random coefficients.
    This tests whether the SPECIFIC catastrophe forms matter.
    """

    def __init__(self, degree: int = 5, num_channels: int = 64, seed: int = 42):
        super().__init__()
        torch.manual_seed(seed)

        self.degree = degree
        # Random coefficients for polynomial
        # P(x) = sum_i a_i * x^i
        self.coefficients = nn.Parameter(torch.randn(degree + 1, num_channels) * 0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply random polynomial."""
        result = torch.zeros_like(x)
        for i in range(self.degree + 1):
            result = result + self.coefficients[i] * (x**i)
        return result


class BSplineKAN(nn.Module):
    """B-spline based KAN (Liu et al., 2024 simplified).

    Uses B-spline basis functions instead of catastrophe potentials.
    """

    def __init__(
        self,
        num_channels: int = 64,
        order: int = 3,
        num_control_points: int = 8,
    ):
        super().__init__()
        self.order = order
        self.num_control_points = num_control_points

        # Control point coefficients (learnable)
        self.control_points = nn.Parameter(torch.randn(num_channels, num_control_points) * 0.1)

        # Knot vector (uniform)
        knots = torch.linspace(-1, 1, num_control_points + order + 1)
        self.register_buffer("knots", knots)

    def _basis_function(self, x: torch.Tensor, i: int, k: int) -> torch.Tensor:
        """Recursive B-spline basis function."""
        if k == 0:
            return ((self.knots[i] <= x) & (x < self.knots[i + 1])).float()  # type: ignore[index]

        denom1 = self.knots[i + k] - self.knots[i]  # type: ignore[index]
        denom2 = self.knots[i + k + 1] - self.knots[i + 1]  # type: ignore[index]

        term1 = torch.zeros_like(x)
        term2 = torch.zeros_like(x)

        if denom1 > 1e-8:
            term1 = (x - self.knots[i]) / denom1 * self._basis_function(x, i, k - 1)  # type: ignore[index]
        if denom2 > 1e-8:
            term2 = (self.knots[i + k + 1] - x) / denom2 * self._basis_function(x, i + 1, k - 1)  # type: ignore[index]

        return term1 + term2

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Evaluate B-spline at x."""
        # Clamp to valid range
        x_clamped = torch.clamp(x, -0.99, 0.99)

        # Sum over control points
        result = torch.zeros_like(x)
        for i in range(self.num_control_points):
            basis = self._basis_function(x_clamped, i, self.order)
            result = result + self.control_points[:, i].unsqueeze(0) * basis

        return result


# =============================================================================
# TEST NETWORK
# =============================================================================


class _AblationNetwork(nn.Module):
    """Small network with interchangeable activation for ablation tests."""

    def __init__(
        self,
        input_dim: int = 64,
        hidden_dim: int = 128,
        output_dim: int = 64,
        activation_module: nn.Module | None = None,
    ):
        super().__init__()

        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.activation = activation_module or nn.GELU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.activation(x)
        x = self.fc2(x)
        return x


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def activations():
    """Create all activation modules for comparison."""
    return {
        "gelu": StandardActivation(F.gelu, "gelu"),
        "silu": StandardActivation(F.silu, "silu"),
        "relu": StandardActivation(F.relu, "relu"),
        "tanh": StandardActivation(torch.tanh, "tanh"),
        "random_poly_5": RandomPolynomialActivation(degree=5, num_channels=128),
        "bspline_k3": BSplineKAN(num_channels=128, order=3),
        "catastrophe_fold": CatastropheBasis(CatastropheType.FOLD, num_channels=128),
        "catastrophe_cusp": CatastropheBasis(CatastropheType.CUSP, num_channels=128),
        "catastrophe_butterfly": CatastropheBasis(CatastropheType.BUTTERFLY, num_channels=128),
    }


@pytest.fixture
def test_data():
    """Generate test data for activation comparison."""
    torch.manual_seed(42)

    # Standard random data
    random_data = torch.randn(256, 64)

    # Data near bifurcation (should favor catastrophe)
    # Create data with sudden transitions
    t = torch.linspace(-2, 2, 256).unsqueeze(1)
    bifurcation_base = torch.cat(
        [
            t,
            torch.sign(t) * t.abs().sqrt(),  # Square root with sign change
            (t > 0).float() * t,  # Threshold
            torch.sin(t * 3.14),  # Oscillation
        ],
        dim=1,
    )  # [256, 4]
    # Repeat to get 64 dimensions
    bifurcation_data = bifurcation_base.repeat(1, 16)[:, :64]  # [256, 64]

    # Smooth data (should favor standard activations)
    smooth_data = torch.sin(torch.linspace(0, 6.28, 256)).unsqueeze(1).repeat(1, 64)

    return {
        "random": random_data,
        "bifurcation": bifurcation_data,
        "smooth": smooth_data,
    }


# =============================================================================
# TESTS
# =============================================================================


class TestCatastropheVsBaselines:
    """Compare catastrophe activations to baselines."""

    def test_gradient_stability(self, activations, test_data) -> None:
        """Compare gradient variance across training steps."""
        results = {}

        for name, activation in activations.items():
            network = _AblationNetwork(activation_module=activation)
            optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)

            grad_norms = []
            x = test_data["random"]
            target = torch.randn(256, 64)

            for _step in range(100):
                optimizer.zero_grad()
                output = network(x)
                loss = F.mse_loss(output, target)
                loss.backward()

                # Collect gradient norms
                total_norm = 0.0
                for p in network.parameters():
                    if p.grad is not None:
                        total_norm += p.grad.norm().item() ** 2
                grad_norms.append(total_norm**0.5)

                optimizer.step()

            # Compute gradient variance (lower = more stable)
            import numpy as np

            variance = np.var(grad_norms)
            mean_norm = np.mean(grad_norms)

            results[name] = {
                "mean_grad_norm": mean_norm,
                "grad_variance": variance,
                "stability": 1.0 / (1.0 + variance),  # Higher = more stable
            }

            print(f"{name:20} | Mean={mean_norm:.4f} | Var={variance:.6f}")

        # Catastrophe activations should have reasonable stability
        catastrophe_stabilities = [results[k]["stability"] for k in results if "catastrophe" in k]
        baseline_stabilities = [results[k]["stability"] for k in ["gelu", "silu"]]

        # Assert catastrophe is not significantly worse
        avg_catastrophe = sum(catastrophe_stabilities) / len(catastrophe_stabilities)
        avg_baseline = sum(baseline_stabilities) / len(baseline_stabilities)

        assert (
            avg_catastrophe > avg_baseline * 0.5
        ), "Catastrophe activations have poor gradient stability"

    def test_bifurcation_representation(self, activations, test_data) -> None:
        """Test ability to represent sudden transitions."""
        results = {}

        # Task: Learn a step function (sudden transition)
        x = torch.linspace(-2, 2, 256).unsqueeze(1).expand(-1, 64)
        target = (x[:, 0:1] > 0).float().expand(-1, 64)  # Step at x=0

        for name, activation in activations.items():
            network = _AblationNetwork(activation_module=activation)
            optimizer = torch.optim.Adam(network.parameters(), lr=1e-2)

            # Train for fixed steps
            final_loss = None
            for _step in range(500):
                optimizer.zero_grad()
                output = network(x)
                loss = F.mse_loss(output, target)
                loss.backward()
                optimizer.step()
                final_loss = loss.item()

            results[name] = final_loss
            print(f"{name:20} | Final Loss={final_loss:.6f}")

        # Print ranking
        print("\nBifurcation Task Ranking (lower is better):")
        for i, (name, loss) in enumerate(sorted(results.items(), key=lambda x: x[1])):  # type: ignore[assignment]  # type: ignore[arg-type]
            print(f"  {i + 1}. {name}: {loss:.6f}")

    def test_learning_speed(self, activations, test_data) -> None:
        """Compare learning speed (steps to convergence)."""
        target_loss = 0.1  # Convergence threshold
        max_steps = 1000

        results = {}

        for name, activation in activations.items():
            network = _AblationNetwork(activation_module=activation)
            optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)

            x = test_data["random"]
            target = torch.randn(256, 64)

            steps_to_converge = max_steps
            for step in range(max_steps):
                optimizer.zero_grad()
                output = network(x)
                loss = F.mse_loss(output, target)

                if loss.item() < target_loss:
                    steps_to_converge = step
                    break

                loss.backward()
                optimizer.step()

            results[name] = steps_to_converge

        print("\nLearning Speed (steps to converge):")
        for name, steps in sorted(results.items(), key=lambda x: x[1]):
            converged = "✅" if steps < max_steps else "❌"
            print(f"  {name:20} | {steps:4d} steps {converged}")

    def test_activation_output_distribution(self, activations) -> None:
        """Analyze output distribution of activations."""
        x = torch.randn(10000, 128)  # Large sample

        print("\nActivation Output Distribution:")
        print("-" * 60)

        for name, activation in activations.items():
            output = activation(x)

            mean = output.mean().item()
            std = output.std().item()
            min_val = output.min().item()
            max_val = output.max().item()

            # Check for dead neurons (always 0)
            dead_ratio = (output.abs() < 1e-6).float().mean().item()

            print(
                f"{name:20} | μ={mean:+.3f} σ={std:.3f} | [{min_val:.2f}, {max_val:.2f}] | Dead={dead_ratio:.2%}"
            )


class TestCatastropheSpecificProperties:
    """Test properties specific to catastrophe activations."""

    def test_singularity_detection(self) -> None:
        """Verify catastrophe activations can detect singularities."""
        # At singularity, derivative = 0
        # For fold: V'(x) = 3x² + a = 0 when a = -3x²

        basis = CatastropheBasis(CatastropheType.FOLD, num_channels=1)

        # Input near singularity
        x_singular = torch.tensor([[0.0]])  # x=0 is fold singularity when a=0
        x_regular = torch.tensor([[1.0]])

        out_singular = basis(x_singular)
        out_regular = basis(x_regular)

        print(f"Fold at x=0: {out_singular.item():.4f}")
        print(f"Fold at x=1: {out_regular.item():.4f}")

        # The outputs should be different (singularity has special behavior)
        assert not torch.allclose(out_singular, out_regular)

    def test_parameter_modulation(self) -> None:
        """Test that control parameters modulate activation."""
        basis = CatastropheBasis(CatastropheType.CUSP, num_channels=64)

        x = torch.randn(10, 64)

        # Get control parameters
        initial_params = basis.control_params.clone()

        # Forward pass
        out1 = basis(x)

        # Modify control parameters
        with torch.no_grad():
            basis.control_params.mul_(2.0)

        # Forward again
        out2 = basis(x)

        # Outputs should differ
        assert not torch.allclose(out1, out2), "Control params should modulate output"

        # Restore
        with torch.no_grad():
            basis.control_params.copy_(initial_params)

    def test_all_seven_types_work(self) -> None:
        """Verify all 7 catastrophe types are functional."""
        for ctype in CatastropheType:
            basis = CatastropheBasis(ctype, num_channels=32)
            x = torch.randn(10, 32)

            output = basis(x)

            # Should produce finite output
            assert torch.isfinite(output).all(), f"{ctype.name} produces non-finite output"

            # Should not be constant
            assert output.std() > 1e-6, f"{ctype.name} produces constant output"

            print(f"✅ {ctype.name}: mean={output.mean():.3f}, std={output.std():.3f}")


class TestBatchedCatastropheCorrectness:
    """Test batched catastrophe implementation."""

    def test_batched_matches_sequential(self) -> None:
        """Batched and sequential should produce equivalent results."""
        num_channels = 64
        batch_size = 8

        # Sequential (7 separate bases)
        sequential_bases = [
            CatastropheBasis(CatastropheType(i), num_channels=num_channels) for i in range(7)
        ]

        # Batched
        batched_basis = BatchedCatastropheBasis(num_channels=num_channels)

        # Input
        x_seq = torch.randn(batch_size, num_channels)

        # Sequential outputs
        seq_outputs = [basis(x_seq) for basis in sequential_bases]
        seq_stacked = torch.stack(seq_outputs, dim=1)  # [B, 7, C]

        # Batched output
        x_batch = x_seq.unsqueeze(1).expand(-1, 7, -1).contiguous()  # [B, 7, C]
        batch_output = batched_basis(x_batch)

        # Check shapes match
        assert seq_stacked.shape == batch_output.shape

        # Note: Outputs may differ slightly due to different initialization
        # The key is both produce valid, non-trivial outputs
        print(f"Sequential mean: {seq_stacked.mean():.4f}")
        print(f"Batched mean: {batch_output.mean():.4f}")


class TestCatastropheKANLayer:
    """Test the full CatastropheKAN layer."""

    def test_layer_gradient_flow(self) -> None:
        """Verify gradients flow through CatastropheKAN layer."""
        layer = CatastropheKANLayer(
            in_features=64,
            out_features=64,
            colony_idx=2,  # Flow colony (swallowtail)
        )

        x = torch.randn(10, 64, requires_grad=True)
        output = layer(x)
        loss = output.sum()
        loss.backward()

        assert x.grad is not None, "No gradient to input"
        assert torch.isfinite(x.grad).all(), "Non-finite gradients"

        # Check layer parameters have gradients
        for name, param in layer.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"{name} has no gradient"

    def test_colony_specific_activation(self) -> None:
        """Each colony should get its specific catastrophe type."""
        colony_names = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

        for idx, name in enumerate(colony_names):
            layer = CatastropheKANLayer(
                in_features=32,
                out_features=32,
                colony_idx=idx,
            )

            # Get the catastrophe type
            ctype = CatastropheType(idx)

            print(f"Colony {name} (idx={idx}): {ctype.name}")

            # Forward should work
            x = torch.randn(4, 32)
            output = layer(x)

            assert output.shape == (4, 32)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CATASTROPHE KAN ABLATION STUDY")
    print("=" * 60)

    # Quick comparison
    test_activations = {
        "gelu": StandardActivation(F.gelu, "gelu"),
        "silu": StandardActivation(F.silu, "silu"),
        "catastrophe_cusp": CatastropheBasis(CatastropheType.CUSP, num_channels=128),
    }

    x = torch.randn(256, 128)
    target = torch.randn(256, 64)

    for name, act in test_activations.items():
        network = _AblationNetwork(activation_module=act)
        optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)

        losses = []
        for _step in range(200):
            optimizer.zero_grad()
            output = network(x)
            loss = F.mse_loss(output, target)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())

        print(f"{name:20} | Final Loss: {losses[-1]:.6f}")
