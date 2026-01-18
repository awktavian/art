"""Tests for Unified Chaos and Catastrophe Dynamics.

Verifies the consolidated implementation in kagami.core.world_model.dynamics.chaos_catastrophe.
"""

from __future__ import annotations

from typing import Any

import pytest

import torch
import torch.nn as nn

from kagami.core.world_model.dynamics.chaos_catastrophe import (
    CatastropheDetector,
    CatastropheMetrics,
    ChaosCatastropheConfig,
    ChaosCatastropheDynamics,
    get_chaos_catastrophe_dynamics,
)

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def dynamics() -> Any:
    """Fixture for standard dynamics instance."""
    config = ChaosCatastropheConfig(catastrophe_latent_dim=64)
    # Set manifold_dim=64 to match input dimension for tests
    return ChaosCatastropheDynamics(config, dim=64, manifold_dim=64)


def test_initialization(dynamics) -> None:
    """Test successful initialization."""
    assert isinstance(dynamics, nn.Module)
    assert dynamics.dim == 64
    assert dynamics.config.catastrophe_latent_dim == 64  # type: ignore[union-attr]
    assert isinstance(dynamics.catastrophe, CatastropheDetector)


def test_forward_shape(dynamics) -> None:
    """Test forward pass output shapes."""
    batch_size = 5
    dim = 64
    x = torch.randn(batch_size, dim)

    risk, vector, dominant = dynamics.detect_catastrophe(x)

    assert risk.shape == (batch_size,)
    assert vector.shape == (batch_size, 7)
    assert isinstance(dominant, str)
    # Dominant type should be one of the 7 types or 'none'
    assert dominant in [*CatastropheDetector.TYPES, "none"]


def test_singularity_detection(dynamics) -> None:
    """Test singularity detection logic."""
    # Mock high risk output
    # We can't easily force the NN to output high risk without training,
    # but we can test the threshold logic by mocking the detector or using white-box testing if accessible.
    # Here we trust the forward pass and check ranges.

    x = torch.randn(10, 64)
    risk, vector, _ = dynamics.detect_catastrophe(x)

    assert torch.all(risk >= 0.0)
    assert torch.all(risk <= 1.0)
    assert torch.all(vector >= 0.0)
    assert torch.all(vector <= 1.0)


def test_cbf_risk_computation(dynamics) -> None:
    """Test CBF risk scalar output."""
    x = torch.randn(1, 64)
    risk_scalar = dynamics.get_cbf_risk(x)

    assert isinstance(risk_scalar, float)
    assert 0.0 <= risk_scalar <= 1.0


def test_factory_singleton() -> None:
    """Test singleton factory behavior.

    The factory uses a global singleton pattern. Once created with a specific
    dimension, subsequent calls return the SAME instance regardless of requested
    dimension. This is by design for memory efficiency.
    """
    from kagami.core.world_model.dynamics.chaos_catastrophe import reset_chaos_catastrophe_dynamics

    # Reset singleton for test isolation
    reset_chaos_catastrophe_dynamics()

    try:
        d1 = get_chaos_catastrophe_dynamics(dim=32)
        d2 = get_chaos_catastrophe_dynamics(dim=32)

        assert d1 is d2
        assert d1.dim == 32

        # Requesting different dim returns SAME instance (singleton policy)
        d3 = get_chaos_catastrophe_dynamics(dim=128)
        assert d3 is d1
        assert d3.dim == 32  # Remains 32 (singleton created first)
    finally:
        # Reset singleton after test
        reset_chaos_catastrophe_dynamics()


def test_detector_forward(dynamics) -> None:
    """Test the internal detector forward pass."""
    x = torch.randn(3, 64)
    # Call forward_detailed on the detector, not the wrapper
    metrics = dynamics.catastrophe.forward_detailed(x)

    assert isinstance(metrics, CatastropheMetrics)
    assert isinstance(metrics.total_risk, float)
    assert 0.0 <= metrics.total_risk <= 1.0
    assert len(metrics.risk_vector) == 7
    assert isinstance(metrics.dominant_type, str)

    # Check properties
    assert isinstance(metrics.near_singularity, bool)
    assert isinstance(metrics.cbf_unsafe, bool)


def test_fano_lines_structure() -> None:
    """Test Fano plane constant correctness."""
    # FANO_LINES is defined in kagami_math.fano_plane (Dec 13, 2025 fix)
    from kagami_math.fano_plane import FANO_LINES

    assert len(FANO_LINES) == 7

    for line in FANO_LINES:
        assert len(line) == 3
        # Indices should be 1-7 (e₁-e₇ per mathematical convention)
        assert all(1 <= idx <= 7 for idx in line)


def test_input_projection() -> None:
    """Test input projection handling."""
    # Config with dim=64, input=32 -> should use projection
    # But ChaosCatastropheDynamics initializes detector with input_dim=dim.
    # The detector has an optional input_proj if input_dim != latent_dim.
    # Default latent_dim is 64.

    config = ChaosCatastropheConfig(catastrophe_latent_dim=64)  # latent 64
    dyn = ChaosCatastropheDynamics(config, manifold_dim=128)  # input 128

    x = torch.randn(5, 128)
    metrics = dyn.catastrophe.forward_detailed(x)
    assert isinstance(metrics.total_risk, float)
    assert 0.0 <= metrics.total_risk <= 1.0
