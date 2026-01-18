"""Fano Attention vs Dense Attention Ablation Study.

This test compares SparseFanoAttention (1,400 params) to Dense Linear (9,604 params)
for inter-colony coupling.

HYPOTHESIS: Fano attention provides proper inductive bias for octonion structure
while requiring 7× fewer parameters.

METRICS:
1. Parameter count
2. Reconstruction quality (colony state prediction)
3. Gradient flow
4. Latency

Created: December 8, 2025
"""

from __future__ import annotations

from typing import Any, cast

import pytest

pytestmark = pytest.mark.tier_integration

import time

import torch
import torch.nn as nn
import torch.nn.functional as F

# =============================================================================
# BASELINE: DENSE ATTENTION
# =============================================================================


class DenseColonyCoupling(nn.Module):
    """Dense linear coupling between all 7 colonies.

    Standard approach: each colony can influence any other colony.
    Parameters: 7 * 14 * 7 * 14 = 9,604 (for z_dim=14)
    """

    def __init__(self, n_colonies: int = 7, z_dim: int = 14):
        super().__init__()
        self.n_colonies = n_colonies
        self.z_dim = z_dim

        # Full coupling matrix
        self.coupling = nn.Linear(n_colonies * z_dim, n_colonies * z_dim)

    def forward(self, colony_states: torch.Tensor) -> torch.Tensor:
        """Apply dense coupling.

        Args:
            colony_states: [B, 7, 14] colony latent states

        Returns:
            coupled: [B, 7, 14] coupled states
        """
        B = colony_states.shape[0]
        flat = colony_states.view(B, -1)  # [B, 98]
        coupled_flat = self.coupling(flat)  # [B, 98]
        return cast(torch.Tensor, coupled_flat.view(B, self.n_colonies, self.z_dim))


# =============================================================================
# FANO ATTENTION (Import from production code)
# =============================================================================


class SparseFanoAttention(nn.Module):
    """Sparse coupling following Fano plane structure.

    Only couples colonies on the same Fano line: 7 lines × 3 colonies each.
    Parameters: ~1,400 (vs 9,604 for dense)

    Fano lines (0-indexed): valid 3-colony compositions
    """

    FANO_LINES = [
        (0, 1, 2),  # Spark × Forge = Flow
        (0, 3, 4),  # Spark × Nexus = Beacon
        (0, 5, 6),  # Spark × Grove = Crystal
        (1, 3, 5),  # Forge × Nexus = Grove
        (4, 1, 6),  # Beacon × Forge = Crystal
        (3, 2, 6),  # Nexus × Flow = Crystal
        (4, 2, 5),  # Beacon × Flow = Grove
    ]

    def __init__(self, z_dim: int = 14, hidden_dim: int = 16):
        super().__init__()
        self.z_dim = z_dim
        self.hidden_dim = hidden_dim

        # Per-line MLP: combines 2 colonies to influence 3rd
        self.line_proj_in = nn.Linear(z_dim * 2, hidden_dim)
        self.line_proj_out = nn.Linear(hidden_dim, z_dim)

        # Line gates (learned importance of each Fano line)
        self.line_gates = nn.Parameter(torch.ones(7) / 7)

    def forward(self, colony_states: torch.Tensor) -> torch.Tensor:
        """Apply sparse Fano coupling.

        Args:
            colony_states: [B, 7, 14] colony latent states

        Returns:
            coupled: [B, 7, 14] coupled states
        """
        B = colony_states.shape[0]
        device = colony_states.device

        # Start with residual
        output = colony_states.clone()
        gates = F.softmax(self.line_gates, dim=0)

        for line_idx, (i, j, k) in enumerate(self.FANO_LINES):
            # Get states for colonies i and j
            x_i = colony_states[:, i, :]  # [B, 14]
            x_j = colony_states[:, j, :]  # [B, 14]

            # Combine via MLP
            combined = torch.cat([x_i, x_j], dim=-1)  # [B, 28]
            h = F.gelu(self.line_proj_in(combined))  # [B, hidden]
            delta = self.line_proj_out(h)  # [B, 14]

            # Apply gated update to colony k
            output[:, k, :] = output[:, k, :] + gates[line_idx] * delta

        return output


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def models():
    """Create both attention models."""
    return {
        "fano": SparseFanoAttention(z_dim=14, hidden_dim=16),
        "dense": DenseColonyCoupling(n_colonies=7, z_dim=14),
    }


@pytest.fixture
def test_data():
    """Generate test data for colony states."""
    torch.manual_seed(42)

    # Random colony states
    random_states = torch.randn(100, 7, 14)

    # Structured: colony states with Fano-line correlations
    structured_states = torch.randn(100, 7, 14)
    for i, j, k in SparseFanoAttention.FANO_LINES:
        # Make colony k correlated with i and j
        structured_states[:, k, :] = 0.5 * (
            structured_states[:, i, :] + structured_states[:, j, :]
        ) + 0.2 * torch.randn(100, 14)

    return {
        "random": random_states,
        "structured": structured_states,
    }


# =============================================================================
# TESTS
# =============================================================================


class TestFanoVsDense:
    """Compare Fano sparse attention to dense coupling."""

    def test_parameter_count(self, models) -> None:
        """Verify Fano has significantly fewer parameters."""
        fano_params = sum(p.numel() for p in models["fano"].parameters())
        dense_params = sum(p.numel() for p in models["dense"].parameters())

        print(f"Fano params: {fano_params:,}")
        print(f"Dense params: {dense_params:,}")
        print(f"Ratio: {dense_params / fano_params:.1f}x")

        # Fano should have ~7x fewer params
        assert fano_params < dense_params / 5, "Fano should have >5x fewer params"

    def test_gradient_flow(self, models, test_data) -> None:
        """Verify gradients flow through both models."""
        for name, model in models.items():
            x = test_data["random"].clone()
            x.requires_grad_(True)

            output = model(x)
            loss = output.sum()
            loss.backward()

            assert x.grad is not None, f"{name}: No gradients"
            assert torch.isfinite(x.grad).all(), f"{name}: Non-finite gradients"

            grad_norm = x.grad.norm().item()
            print(f"{name}: Gradient norm = {grad_norm:.4f}")

    def test_output_shape(self, models, test_data) -> None:
        """Verify both models produce correct output shape."""
        x = test_data["random"]

        for name, model in models.items():
            output = model(x)
            assert output.shape == x.shape, f"{name}: Wrong output shape"

    def test_latency_comparison(self, models, test_data) -> None:
        """Compare inference latency."""
        x = test_data["random"]
        results = {}

        for name, model in models.items():
            model.eval()

            # Warmup
            for _ in range(5):
                _ = model(x)

            # Time
            n_iters = 100
            start = time.perf_counter()
            for _ in range(n_iters):
                _ = model(x)
            elapsed = (time.perf_counter() - start) / n_iters * 1000  # ms

            results[name] = elapsed
            print(f"{name}: {elapsed:.3f} ms per batch")

        # Fano should be faster (fewer ops)
        # But dense is a single matmul, so difference may be small
        print(f"Latency ratio (dense/fano): {results['dense'] / results['fano']:.2f}x")

    def test_structured_data_quality(self, models, test_data) -> None:
        """Test reconstruction on Fano-structured data.

        Hypothesis: Fano attention should preserve Fano-line correlations better.
        """
        x = test_data["structured"]

        results = {}
        for name, model in models.items():
            output = model(x)

            # Measure preservation of Fano-line correlations
            correlations = []
            for i, j, k in SparseFanoAttention.FANO_LINES:
                # How correlated is output_k with input_i + input_j?
                expected = 0.5 * (x[:, i, :] + x[:, j, :])
                actual = output[:, k, :]
                corr = F.cosine_similarity(expected.flatten(), actual.flatten(), dim=0).item()
                correlations.append(corr)

            avg_corr = sum(correlations) / len(correlations)
            results[name] = avg_corr
            print(f"{name}: Avg Fano-line correlation = {avg_corr:.4f}")

        # Document findings
        print("\nFano-structured data preservation:")
        print(f"  Fano attention: {results['fano']:.4f}")
        print(f"  Dense attention: {results['dense']:.4f}")


class TestFanoPlaneProperties:
    """Test that Fano attention respects mathematical properties."""

    def test_fano_line_count(self) -> None:
        """Verify there are exactly 7 Fano lines."""
        assert len(SparseFanoAttention.FANO_LINES) == 7

    def test_each_colony_on_three_lines(self) -> None:
        """Each of 7 colonies should appear on exactly 3 Fano lines."""
        lines = SparseFanoAttention.FANO_LINES
        for colony in range(7):
            appearances = sum(1 for line in lines if colony in line)
            assert appearances == 3, f"Colony {colony} appears on {appearances} lines (expected 3)"

    def test_any_two_colonies_share_one_line(self) -> None:
        """Any two distinct colonies share exactly one Fano line."""
        lines = SparseFanoAttention.FANO_LINES
        for c1 in range(7):
            for c2 in range(c1 + 1, 7):
                shared = sum(1 for line in lines if c1 in line and c2 in line)
                assert shared == 1, f"Colonies {c1},{c2} share {shared} lines (expected 1)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
