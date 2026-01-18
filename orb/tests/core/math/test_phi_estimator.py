"""Tests for Fano Coherence Estimator.

Verifies that the estimator:
1. Runs on tensor inputs.
2. Returns valid range [0, 1].
3. Responds to coherence (aligned inputs gives higher coherence).
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch
from kagami_math.phi_estimator import FanoCoherenceEstimator


def test_fano_coherence_estimator_shape():
    est = FanoCoherenceEstimator()
    B, S, D = 2, 5, 8
    # 7 colony states
    states = torch.randn(B, S, 7, D)

    coherence = est(states)
    assert coherence.shape == (B, S, 1)
    assert (coherence >= 0).all() and (coherence <= 1).all()


def test_fano_coherence_sensitivity():
    """Test that coherent states yield higher coherence than random states."""
    est = FanoCoherenceEstimator()
    B, D = 10, 8

    # 1. Coherent State: Fano triples aligned
    # We manually construct a state where e1 * e2 = e3 roughly holds
    # For simplicity, make all vectors identical (highly correlated)
    coherent_states = torch.ones(B, 7, D)
    # Add small noise
    coherent_states = coherent_states + torch.randn_like(coherent_states) * 0.01

    # 2. Incoherent State: Random vectors
    incoherent_states = torch.randn(B, 7, D)

    coherence_coherent = est(coherent_states).mean()
    coherence_incoherent = est(incoherent_states).mean()

    # Coherent system (high correlation/integration) should have higher coherence
    # Note: The current simple proxy uses triple correlation.
    # Identical vectors have high correlation.
    assert (
        coherence_coherent > coherence_incoherent
    ), f"Coherent {coherence_coherent} should be > Incoherent {coherence_incoherent}"


def test_full_octonion_coherence_placeholder():
    est = FanoCoherenceEstimator()
    state = torch.randn(2, 8)
    coherence = est.compute_full_octonion_coherence(state)
    assert coherence.shape == (2, 1)
