"""Integration test for PhaseTransitionDetector in UnifiedOrganism.

Validates end-to-end phase detection during multi-colony task execution.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)
from kagami.core.unified_agents.phase_detector import CoordinationPhase


@pytest.mark.asyncio
class TestOrganismPhaseDetection:
    """Test phase detection in unified organism."""

    async def test_organism_has_phase_detector(self) -> None:
        """Test that organism initializes phase detector."""
        organism = UnifiedOrganism()

        assert hasattr(organism, "phase_detector")
        assert organism.phase_detector is not None
        assert organism.phase_detector.current_phase == CoordinationPhase.UNKNOWN

    async def test_organism_tracks_coupling_strength(self) -> None:
        """Test that organism tracks coupling strength."""
        organism = UnifiedOrganism()

        assert hasattr(organism, "_coupling_strength")
        assert organism._coupling_strength == 1.0

    async def test_phase_stats_in_organism_stats(self) -> None:
        """Test that organism stats include phase detector stats."""
        organism = UnifiedOrganism()

        stats = organism.get_stats()

        assert "phase_detector" in stats
        assert "coupling_strength" in stats
        assert stats["coupling_strength"] == 1.0

        phase_stats = stats["phase_detector"]
        assert "current_phase" in phase_stats
        assert "csr" in phase_stats
        assert "td_variance" in phase_stats

    async def test_get_phase_stats_method(self) -> None:
        """Test get_phase_stats() method."""
        organism = UnifiedOrganism()

        phase_stats = organism.get_phase_stats()

        assert phase_stats is not None
        assert "current_phase" in phase_stats
        assert "total_updates" in phase_stats
        assert "fano_line_summary" in phase_stats

    async def test_phase_detector_survives_organism_lifecycle(self) -> None:
        """Test that phase detector persists through organism start/stop."""
        organism = UnifiedOrganism()

        # Start organism
        await organism.start()
        assert organism.phase_detector is not None

        # Stop organism
        await organism.stop()
        assert organism.phase_detector is not None
        # Phase detector should still be accessible


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
