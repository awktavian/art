from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import torch


def test_nearest_e8_outputs_valid_lattice_points():
    from kagami_math.e8_lattice_quantizer import nearest_e8, e8_to_half_step_ints

    x = torch.randn(2048, 8)
    y = nearest_e8(x)
    a = e8_to_half_step_ints(y)

    # All coordinates even or all odd
    parity = a & 1
    all_even = parity.sum(dim=-1) == 0
    all_odd = parity.sum(dim=-1) == 8
    assert torch.all(all_even | all_odd)

    # Sum divisible by 4 (E8 condition under half-step representation)
    assert torch.all((a.sum(dim=-1) % 4) == 0)


def test_protocol_v2_roundtrip_exact_on_quantized():
    from kagami_math.e8_lattice_protocol import ResidualE8LatticeVQ

    m = ResidualE8LatticeVQ()
    x = torch.randn(8)
    result = m(x, num_levels=4)
    q = result["quantized"]

    b = m.encode_bytes(x, num_levels=4)
    q2, _codes2 = m.decode_bytes(b)

    assert torch.allclose(q, q2, atol=0.0)


def test_forward_returns_dict_with_required_keys():
    """Test that forward() returns dict with standardized keys."""
    from kagami_math.e8_lattice_protocol import ResidualE8LatticeVQ

    m = ResidualE8LatticeVQ()
    x = torch.randn(4, 8)  # batch of 4
    result = m(x, num_levels=4)

    # Check all required keys are present
    assert "quantized" in result
    assert "loss" in result
    assert "indices" in result
    assert "perplexity" in result

    # Check types
    assert isinstance(result["quantized"], torch.Tensor)
    assert isinstance(result["loss"], torch.Tensor)
    assert isinstance(result["indices"], torch.Tensor)
    assert isinstance(result["perplexity"], torch.Tensor)

    # Check shapes
    assert result["quantized"].shape == x.shape  # [..., 8]
    assert result["loss"].ndim == 0  # scalar
    assert result["indices"].shape[-1] == 8  # [..., L, 8]
    assert result["perplexity"].ndim == 0  # scalar
