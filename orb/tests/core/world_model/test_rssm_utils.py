"""Tests for RSSM Utility Functions.

CREATED: December 19, 2025
Tests encode_for_rssm() and decode_from_rssm() utilities for CoreState ↔ RSSM integration.
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.model_config import CoreState
from kagami.core.world_model.rssm_utils import decode_from_rssm, encode_for_rssm



pytestmark = pytest.mark.tier_integration

class TestEncodeForRSSM:
    """Test encode_for_rssm() utility."""

    def test_extracts_s7_phase_from_core_state(self) -> None:
        """Test extracting S7 phase from CoreState."""
        s7 = torch.randn(4, 7)  # [B, 7]
        core_state = CoreState(
            s7_phase=s7,
            e8_code=torch.randn(4, 8),
            shell_residual=torch.randn(4, 14),
        )

        result = encode_for_rssm(core_state)

        assert result.shape == (4, 7)
        assert torch.allclose(result, s7)

    def test_handles_sequence_dimension(self) -> None:
        """Test handling S7 phase with sequence dimension [B, S, 7] → [B, 7]."""
        s7 = torch.randn(4, 10, 7)  # [B, S, 7]
        core_state = CoreState(s7_phase=s7)

        result = encode_for_rssm(core_state)

        # Should take last timestep
        assert result.shape == (4, 7)
        assert torch.allclose(result, s7[:, -1])

    def test_raises_on_none_s7_phase(self) -> None:
        """Test error when s7_phase is None."""
        core_state = CoreState(s7_phase=None)

        with pytest.raises(ValueError, match="CoreState.s7_phase is None"):
            encode_for_rssm(core_state)

    def test_raises_on_invalid_dimension(self) -> None:
        """Test error when s7_phase has wrong dimension."""
        core_state = CoreState(s7_phase=torch.randn(4, 5))  # Wrong: 5 instead of 7

        with pytest.raises(ValueError, match="last dimension must be 7"):
            encode_for_rssm(core_state)

    def test_raises_on_1d_input(self) -> None:
        """Test error when s7_phase is 1D (missing batch dimension)."""
        core_state = CoreState(s7_phase=torch.randn(7))

        with pytest.raises(ValueError, match="must be at least 2D"):
            encode_for_rssm(core_state)


class TestDecodeFromRSSM:
    """Test decode_from_rssm() utility."""

    def test_creates_core_state_from_s7_phase(self) -> None:
        """Test creating CoreState from S7 phase."""
        s7 = torch.randn(4, 7)  # [B, 7]

        core_state = decode_from_rssm(s7)

        assert core_state.s7_phase is not None
        assert core_state.s7_phase.shape == (4, 1, 7)  # [B, 1, 7] with sequence dim
        assert torch.allclose(core_state.s7_phase[:, 0], s7)
        assert core_state.e8_code is None
        assert core_state.shell_residual is None

    def test_raises_on_wrong_shape(self) -> None:
        """Test error when s7_phase has wrong shape."""
        s7 = torch.randn(4, 5)  # Wrong: 5 instead of 7

        with pytest.raises(ValueError, match="last dimension must be 7"):
            decode_from_rssm(s7)

    def test_raises_on_3d_input(self) -> None:
        """Test error when s7_phase is 3D (should be 2D)."""
        s7 = torch.randn(4, 10, 7)  # [B, S, 7] - too many dimensions

        with pytest.raises(ValueError, match="must be 2D"):
            decode_from_rssm(s7)


class TestRoundTripConversion:
    """Test round-trip CoreState → S7 → CoreState."""

    def test_round_trip_preserves_s7_phase(self) -> None:
        """Test that encode → decode preserves S7 phase."""
        original_s7 = torch.randn(4, 7)
        core_state = CoreState(s7_phase=original_s7)

        # Encode for RSSM
        s7_for_rssm = encode_for_rssm(core_state)

        # Decode back to CoreState
        reconstructed = decode_from_rssm(s7_for_rssm)

        # Check S7 phase matches
        assert reconstructed.s7_phase is not None
        assert torch.allclose(reconstructed.s7_phase[:, 0], original_s7)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
