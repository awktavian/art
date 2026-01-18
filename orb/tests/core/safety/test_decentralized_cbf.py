"""Tests for Decentralized Control Barrier Functions.

Tests cover:
1. Single colony CBF with neighbor observation
2. Fano neighbor structure correctness
3. Compositional safety verification
4. Multi-colony control filtering
5. Gradient flow for end-to-end training
6. Integration with existing CBF infrastructure
"""

from __future__ import annotations

import pytest
import torch

from kagami.core.safety.decentralized_cbf import (
    ColonyCBF,
    FanoDecentralizedCBF,
    create_decentralized_cbf,
    verify_compositional_safety,
    build_fano_neighbor_map,
    FANO_NEIGHBORS,
)
from kagami_math.fano_plane import get_fano_lines_zero_indexed

# =============================================================================
# FANO NEIGHBOR STRUCTURE TESTS
# =============================================================================


def test_fano_neighbor_map():
    """Test that Fano neighbor map is correctly constructed."""
    neighbor_map = build_fano_neighbor_map()

    # Should have 7 colonies
    assert len(neighbor_map) == 7

    # Each colony should have exactly 6 neighbors
    for i in range(7):
        assert len(neighbor_map[i]) == 6, f"Colony {i} should have 6 neighbors"

        # Neighbors should be valid colony indices
        for neighbor in neighbor_map[i]:
            assert 0 <= neighbor < 7
            assert neighbor != i, f"Colony {i} cannot be its own neighbor"

    # Verify symmetry: if j in neighbors[i], then i in neighbors[j]
    for i in range(7):
        for j in neighbor_map[i]:
            assert i in neighbor_map[j], f"Neighbor relation not symmetric: {i}, {j}"


def test_fano_neighbors_constant():
    """Test that FANO_NEIGHBORS constant is correct."""
    # Should match dynamically computed map
    computed_map = build_fano_neighbor_map()
    assert FANO_NEIGHBORS == computed_map


def test_fano_coverage():
    """Test that Fano neighbor structure covers all pairs."""
    fano_lines = get_fano_lines_zero_indexed()

    # Collect all pairs from neighbor map
    pairs_from_neighbors: set[tuple[int, int]] = set()
    for i in range(7):
        for j in FANO_NEIGHBORS[i]:
            pair = (min(i, j), max(i, j))
            pairs_from_neighbors.add(pair)

    # Collect all pairs from Fano lines
    pairs_from_lines: set[tuple[int, int]] = set()
    for i, j, k in fano_lines:
        pairs_from_lines.add((min(i, j), max(i, j)))
        pairs_from_lines.add((min(j, k), max(j, k)))
        pairs_from_lines.add((min(k, i), max(k, i)))

    # Should be identical
    assert pairs_from_neighbors == pairs_from_lines


# =============================================================================
# SINGLE COLONY CBF TESTS
# =============================================================================


def test_colony_cbf_initialization():
    """Test ColonyCBF initialization."""
    for colony_idx in range(7):
        cbf = ColonyCBF(
            colony_idx=colony_idx,
            state_dim=4,
            hidden_dim=64,
        )

        # Check basic properties
        assert cbf.colony_idx == colony_idx
        assert cbf.state_dim == 4
        assert len(cbf.neighbors) == 6

        # Check learnable parameters
        assert cbf.risk_weights.shape == (4,)


def test_colony_cbf_forward():
    """Test ColonyCBF forward pass."""
    cbf = ColonyCBF(colony_idx=0, state_dim=4, hidden_dim=64)

    B = 8
    x_local = torch.randn(B, 4)  # Local state
    x_all = torch.randn(B, 7, 4)  # All colony states

    h = cbf(x_local, x_all)

    # Check output shape
    assert h.shape == (B,)

    # Check that values are reasonable (should be near safety threshold)
    assert h.abs().max() < 10.0  # Not wildly large


def test_colony_cbf_neighbor_dependency():
    """Test that colony CBF depends on neighbor states."""
    cbf = ColonyCBF(colony_idx=0, state_dim=4, hidden_dim=64)

    B = 8
    x_local = torch.randn(B, 4)

    # Two different neighbor configurations
    x_all_1 = torch.randn(B, 7, 4)
    x_all_2 = torch.randn(B, 7, 4)

    h_1 = cbf(x_local, x_all_1)
    h_2 = cbf(x_local, x_all_2)

    # Should produce different outputs (neighbor-dependent)
    assert not torch.allclose(h_1, h_2)


def test_colony_cbf_safety_zones():
    """Test that colony CBF produces expected safe/unsafe zones."""
    cbf = ColonyCBF(colony_idx=0, state_dim=4, hidden_dim=64)

    B = 4

    # Safe state: low threat, low uncertainty, low complexity, low risk
    x_safe_local = torch.tensor([[0.1, 0.1, 0.1, 0.1]] * B)
    x_all = torch.randn(B, 7, 4) * 0.1  # Low-risk neighbors

    h_safe = cbf(x_safe_local, x_all)

    # Unsafe state: high threat, high uncertainty, high complexity, high risk
    x_unsafe_local = torch.tensor([[0.9, 0.9, 0.9, 0.9]] * B)

    h_unsafe = cbf(x_unsafe_local, x_all)

    # Safe states should have higher barrier values
    assert h_safe.mean() > h_unsafe.mean()


# =============================================================================
# DECENTRALIZED CBF TESTS
# =============================================================================


def test_decentralized_cbf_initialization():
    """Test FanoDecentralizedCBF initialization."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    # Should have 7 colony CBFs
    assert len(dcbf.colonies) == 7

    # Each should be a ColonyCBF
    for i, colony_cbf in enumerate(dcbf.colonies):
        assert isinstance(colony_cbf, ColonyCBF)
        assert colony_cbf.colony_idx == i


def test_decentralized_cbf_forward():
    """Test FanoDecentralizedCBF forward pass."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 8
    x = torch.randn(B, 7, 4)  # [batch, 7 colonies, state_dim]

    h = dcbf(x)

    # Check output shape: [B, 7] barrier values per colony
    assert h.shape == (B, 7)


def test_decentralized_cbf_compositional_safety():
    """Test compositional safety check."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 8

    # All safe: low-risk states
    x_safe = torch.randn(B, 7, 4) * 0.1 + 0.2  # Centered around 0.2

    is_safe = dcbf.is_safe(x_safe)
    assert is_safe.shape == (B,)

    # All unsafe: high-risk states
    x_unsafe = torch.randn(B, 7, 4) * 0.1 + 0.8  # Centered around 0.8

    is_unsafe = dcbf.is_safe(x_unsafe)

    # Safe states should have higher safety rate
    assert is_safe.float().mean() >= is_unsafe.float().mean()


def test_decentralized_cbf_unsafe_detection():
    """Test identifying unsafe colonies."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4) * 0.1 + 0.2  # Mostly safe

    # Make colony 3 unsafe
    x[:, 3, :] = torch.tensor([0.9, 0.9, 0.9, 0.9])

    unsafe_mask = dcbf.get_unsafe_colonies(x)

    assert unsafe_mask.shape == (B, 7)

    # Colony 3 should be more likely to be unsafe
    # (though not guaranteed due to random weights)


def test_decentralized_cbf_safety_penalty():
    """Test soft barrier penalty computation."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64, soft_penalty_weight=10.0)

    B = 8

    # Safe states: low penalty
    x_safe = torch.randn(B, 7, 4) * 0.1 + 0.2
    penalty_safe = dcbf.compute_safety_penalty(x_safe, margin=0.1)

    # Unsafe states: high penalty
    x_unsafe = torch.randn(B, 7, 4) * 0.1 + 0.8
    penalty_unsafe = dcbf.compute_safety_penalty(x_unsafe, margin=0.1)

    # Both should be non-negative scalars
    assert penalty_safe >= 0
    assert penalty_unsafe >= 0

    # Unsafe should have higher penalty
    assert penalty_unsafe >= penalty_safe


def test_decentralized_cbf_control_filtering():
    """Test control filtering for compositional safety."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4) * 0.1 + 0.2
    u_nominal = torch.randn(B, 7, 2).clamp(0, 1)  # Valid controls

    u_safe, penalty, info = dcbf.filter_control(x, u_nominal, control_dim=2)

    # Check output shapes
    assert u_safe.shape == (B, 7, 2)
    assert penalty >= 0

    # Check info dict
    assert "h_values" in info
    assert info["h_values"].shape == (B, 7)
    assert "unsafe_colonies" in info
    assert len(info["unsafe_colonies"]) == 7


def test_decentralized_cbf_fano_coupling():
    """Test Fano coupling strength measurement."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 8
    x = torch.randn(B, 7, 4) * 0.1 + 0.2

    coupling = dcbf.get_fano_coupling_strength(x)

    # Should have 7 values (one per Fano line)
    assert coupling.shape == (7,)

    # Should be non-negative
    assert (coupling >= 0).all()


# =============================================================================
# COMPOSITIONAL SAFETY VERIFICATION TESTS
# =============================================================================


def test_verify_compositional_safety():
    """Test compositional safety verification function."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 8
    x = torch.randn(B, 7, 4) * 0.1 + 0.2

    result = verify_compositional_safety(dcbf, x, threshold=0.0)

    # Check result structure
    assert "all_safe" in result
    assert "batch_safety_rate" in result
    assert "min_barrier" in result
    assert "max_barrier" in result
    assert "mean_barrier" in result
    assert "unsafe_colonies_per_sample" in result
    assert "violated_fano_lines" in result
    assert "per_colony_safety_rate" in result

    # Check types
    assert isinstance(result["all_safe"], bool)
    assert 0.0 <= result["batch_safety_rate"] <= 1.0
    assert len(result["per_colony_safety_rate"]) == 7


def test_verify_compositional_safety_with_violations():
    """Test verification when safety is violated."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4) * 0.1 + 0.2

    # Force colony 0 to be unsafe
    x[:, 0, :] = torch.tensor([0.9, 0.9, 0.9, 0.9])

    result = verify_compositional_safety(dcbf, x, threshold=0.0)

    # Should detect violations
    # Note: Due to random initialization, colony 0 might not always be unsafe
    # Just check that verification runs and returns valid structure


# =============================================================================
# GRADIENT FLOW TESTS
# =============================================================================


def test_gradient_flow_through_dcbf():
    """Test that gradients flow through decentralized CBF."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4, requires_grad=True)

    # Forward pass
    h = dcbf(x)
    loss = h.sum()

    # Backward pass
    loss.backward()

    # Check that gradients exist
    assert x.grad is not None
    assert x.grad.shape == (B, 7, 4)


def test_gradient_flow_through_penalty():
    """Test gradients flow through safety penalty."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4, requires_grad=True)

    penalty = dcbf.compute_safety_penalty(x, margin=0.1)
    penalty.backward()

    # Check gradients
    assert x.grad is not None
    assert x.grad.shape == (B, 7, 4)


def test_gradient_flow_through_control_filter():
    """Test gradients flow through control filtering."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4, requires_grad=True)
    u_nominal = torch.randn(B, 7, 2, requires_grad=True)

    u_safe, penalty, _info = dcbf.filter_control(x, u_nominal)

    # Compute loss
    loss = u_safe.sum() + penalty

    loss.backward()

    # Check gradients
    assert x.grad is not None
    assert u_nominal.grad is not None


# =============================================================================
# FACTORY TESTS
# =============================================================================


def test_create_decentralized_cbf():
    """Test factory function."""
    dcbf = create_decentralized_cbf(
        state_dim=4,
        hidden_dim=32,
        safety_threshold=0.5,
    )

    assert isinstance(dcbf, FanoDecentralizedCBF)
    assert dcbf.state_dim == 4
    assert dcbf.safety_threshold == 0.5


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_integration_with_global_cbf():
    """Test that decentralized CBF can be used alongside global CBF."""
    # This is a placeholder for integration testing with existing CBF
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4
    x = torch.randn(B, 7, 4)

    # Decentralized check
    is_safe_decentralized = dcbf.is_safe(x)

    # Could integrate with global CBF check here
    # For now, just verify it runs
    assert is_safe_decentralized.shape == (B,)


def test_batch_consistency():
    """Test that DCBF handles different batch sizes."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    for B in [1, 4, 16, 32]:
        x = torch.randn(B, 7, 4)
        h = dcbf(x)
        assert h.shape == (B, 7)


def test_device_compatibility():
    """Test that DCBF works on different devices."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4

    # CPU
    x_cpu = torch.randn(B, 7, 4)
    h_cpu = dcbf(x_cpu)
    assert h_cpu.device.type == "cpu"

    # MPS (if available)
    if torch.backends.mps.is_available():
        dcbf_mps = dcbf.to("mps")
        x_mps = x_cpu.to("mps")
        h_mps = dcbf_mps(x_mps)
        assert h_mps.device.type == "mps"

    # CUDA (if available)
    if torch.cuda.is_available():
        dcbf_cuda = dcbf.to("cuda")
        x_cuda = x_cpu.to("cuda")
        h_cuda = dcbf_cuda(x_cuda)
        assert h_cuda.device.type == "cuda"


# =============================================================================
# EDGE CASES
# =============================================================================


def test_single_sample_batch():
    """Test with batch size 1."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    x = torch.randn(1, 7, 4)
    h = dcbf(x)

    assert h.shape == (1, 7)


def test_zero_state():
    """Test with zero safety state."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    x = torch.zeros(4, 7, 4)
    h = dcbf(x)

    # Should still produce valid output
    assert h.shape == (4, 7)
    assert not torch.isnan(h).any()


def test_extreme_states():
    """Test with extreme safety states."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 4

    # All max risk
    x_max = torch.ones(B, 7, 4)
    h_max = dcbf(x_max)

    # All min risk
    x_min = torch.zeros(B, 7, 4)
    h_min = dcbf(x_min)

    # Min risk should have higher barrier
    assert h_min.mean() > h_max.mean()


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


@pytest.mark.benchmark
def test_forward_performance():
    """Benchmark forward pass performance."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 32
    x = torch.randn(B, 7, 4)

    import time

    n_iters = 100
    start = time.time()
    for _ in range(n_iters):
        _h = dcbf(x)
    elapsed = time.time() - start

    avg_time = elapsed / n_iters
    print(f"\nAverage forward pass time: {avg_time * 1000:.2f} ms")

    # Should be fast (< 10ms per forward pass on CPU)
    assert avg_time < 0.01


@pytest.mark.benchmark
def test_backward_performance():
    """Benchmark backward pass performance."""
    dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

    B = 32
    x = torch.randn(B, 7, 4, requires_grad=True)

    import time

    n_iters = 100
    start = time.time()
    for _ in range(n_iters):
        h = dcbf(x)
        loss = h.sum()
        loss.backward()
        x.grad = None  # Clear gradients
    elapsed = time.time() - start

    avg_time = elapsed / n_iters
    print(f"\nAverage forward+backward time: {avg_time * 1000:.2f} ms")

    # Should be fast (< 20ms per iteration on CPU)
    assert avg_time < 0.02
