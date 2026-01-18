"""Test that documented parameter counts match actual model sizes.

This test ensures documentation stays synchronized with actual implementation
by verifying that parameter counts match expected values from CLAUDE.md.

IMPORTANT: If this test fails, it means either:
1. Model architecture changed → Update expected counts in this test AND docs
2. Documentation drift → Update docs to match actual counts

Verification date: December 16, 2025
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.config.unified_config import get_kagami_config
from kagami.core.world_model import KagamiWorldModel
from kagami.core.world_model.rssm_core import OrganismRSSM


pytestmark = pytest.mark.tier_integration


def count_parameters(model: torch.nn.Module) -> int:
    """Count trainable parameters in model.

    Args:
        model: PyTorch model

    Returns:
        Number of trainable parameters
    """
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


@pytest.mark.parametrize(
    "bulk_dim,expected_count,tolerance",
    [
        # Updated Jan 4, 2026: Parameter counts after E8 VQ API + RSSM integration fixes
        (64, 4_610_000, 0.02),  # nano: 4.61M ± 2%
        (128, 4_675_000, 0.02),  # small: 4.68M ± 2%
        (512, 5_064_000, 0.02),  # base: 5.06M ± 2%
        (1024, 5_583_000, 0.02),  # large: 5.58M ± 2%
        (2048, 6_620_000, 0.02),  # xl: 6.62M ± 2%
    ],
)
def test_kagami_world_model_parameter_counts(
    bulk_dim: int, expected_count: int, tolerance: float
) -> None:
    """Test KagamiWorldModel parameter counts match documentation.

    Args:
        bulk_dim: Bulk dimension configuration
        expected_count: Expected parameter count
        tolerance: Acceptable percentage difference
    """
    config = get_kagami_config().world_model
    config.bulk_dim = bulk_dim
    model = KagamiWorldModel(config)

    actual_count = count_parameters(model)
    diff_pct = abs(actual_count - expected_count) / expected_count

    assert diff_pct < tolerance, (
        f"Parameter count for bulk_dim={bulk_dim} differs by {diff_pct * 100:.1f}%: actual={actual_count:,} expected={expected_count:,}"
    )


def test_organism_rssm_parameter_count() -> None:
    """Test OrganismRSSM parameter count matches documentation.

    Expected: 1.57M parameters (1,566,223 exact)
    Verified: January 4, 2026 (after E8 VQ API + RSSM integration fixes)
    """
    config = get_kagami_config().world_model.rssm
    model = OrganismRSSM(config)

    actual_count = count_parameters(model)
    expected_count = 1_566_223  # Exact count from Jan 4, 2026 audit
    tolerance = 0.01  # 1% tolerance (stricter for exact verification)

    diff_pct = abs(actual_count - expected_count) / expected_count

    assert diff_pct < tolerance, (
        f"OrganismRSSM parameter count differs by {diff_pct * 100:.1f}%: actual={actual_count:,} expected={expected_count:,}"
    )


def test_parameter_count_consistency_across_configs() -> None:
    """Test that parameter counts increase monotonically with bulk_dim.

    This ensures that larger configs actually have more parameters.
    """
    bulk_dims = [64, 128, 512, 1024, 2048]
    param_counts = []

    for bulk_dim in bulk_dims:
        config = get_kagami_config().world_model
        config.bulk_dim = bulk_dim
        model = KagamiWorldModel(config)
        param_counts.append(count_parameters(model))

    # Verify monotonic increase
    for i in range(len(param_counts) - 1):
        assert param_counts[i] < param_counts[i + 1], (
            f"Parameter count should increase: bulk_dim={bulk_dims[i]} ({param_counts[i]:,}) < bulk_dim={bulk_dims[i + 1]} ({param_counts[i + 1]:,})"
        )


def test_organism_rssm_smaller_than_base_kagami() -> None:
    """Test that OrganismRSSM is smaller than base KagamiWorldModel.

    OrganismRSSM (1.57M) should be smaller than base config (4.68M).
    Verified: January 4, 2026
    """
    rssm_config = get_kagami_config().world_model.rssm
    rssm = OrganismRSSM(rssm_config)
    rssm_count = count_parameters(rssm)

    kagami_config = get_kagami_config().world_model
    kagami = KagamiWorldModel(kagami_config)
    kagami_count = count_parameters(kagami)

    assert rssm_count < kagami_count, (
        f"OrganismRSSM ({rssm_count:,}) should be smaller than KagamiWorldModel ({kagami_count:,})"
    )
