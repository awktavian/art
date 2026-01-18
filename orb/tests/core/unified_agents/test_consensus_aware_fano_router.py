"""Tests for ConsensusAwareFanoRouter.

Created: December 15, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.core.unified_agents.fano_action_router import (
    ActionMode,
    ConsensusAwareFanoRouter,
    create_consensus_aware_router,
    create_fano_router,
    fano_line_consensus,
)


@pytest.fixture
def base_router():
    """Create base FanoActionRouter for testing."""
    return create_fano_router()


@pytest.fixture
def consensus_aware_router_disabled(base_router: Any) -> Any:
    """Create ConsensusAwareFanoRouter with consensus disabled."""
    return ConsensusAwareFanoRouter(
        fano_router=base_router,
        enable_consensus=False,
    )


@pytest.fixture
def mock_consensus():
    """Create mock KagamiConsensus."""
    consensus = MagicMock()
    consensus.collect_proposals = AsyncMock()
    consensus.byzantine_consensus = AsyncMock()
    return consensus


class TestConsensusAwareFanoRouter:
    """Test suite for ConsensusAwareFanoRouter."""

    @pytest.mark.asyncio
    async def test_route_with_consensus_disabled(
        self, consensus_aware_router_disabled: Any
    ) -> None:
        """Test routing with consensus disabled (fallback mode)."""
        result = await consensus_aware_router_disabled.route_with_consensus(
            action="build.feature",
            params={"module": "auth"},
        )

        assert result is not None
        assert result.mode in [ActionMode.SINGLE, ActionMode.FANO_LINE, ActionMode.ALL_COLONIES]
        assert len(result.actions) > 0
        assert all(hasattr(a, "colony_name") for a in result.actions)

    @pytest.mark.asyncio
    async def test_route_simple_action(self, consensus_aware_router_disabled: Any) -> None:
        """Test routing simple action (single colony)."""
        result = await consensus_aware_router_disabled.route_with_consensus(
            action="ping",
            params={},
        )

        assert result.mode == ActionMode.SINGLE
        assert len(result.actions) == 1

    @pytest.mark.asyncio
    async def test_route_complex_action(self, consensus_aware_router_disabled: Any) -> None:
        """Test routing complex action.

        Note: High uncertainty actions may trigger OOD escalation to Grove (SINGLE mode).
        This is correct behavior per CLAUDE.md: "No signal matches → Route to Grove"
        """
        result = await consensus_aware_router_disabled.route_with_consensus(
            action="implement.complex.feature",
            params={"complexity": "high"},
        )

        # Valid modes:
        # - FANO_LINE or ALL_COLONIES for known complex actions
        # - SINGLE (Grove) for high uncertainty via OOD escalation
        assert result.mode in [ActionMode.SINGLE, ActionMode.FANO_LINE, ActionMode.ALL_COLONIES]
        assert len(result.actions) >= 1  # At least one action (Grove or Fano line)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_consensus_timeout(self, base_router: Any, mock_consensus: Any) -> None:
        """Test consensus timeout fallback."""

        # Make collect_proposals hang
        async def hang():
            await asyncio.sleep(10)
            return []

        mock_consensus.collect_proposals = hang

        router = ConsensusAwareFanoRouter(
            fano_router=base_router,
            consensus=mock_consensus,
            enable_consensus=True,
            consensus_timeout=0.1,  # Short timeout
        )

        result = await router.route_with_consensus(
            action="build.feature",
            params={},
        )

        # Should fallback to initial routing
        assert result is not None
        assert result.mode in [ActionMode.SINGLE, ActionMode.FANO_LINE, ActionMode.ALL_COLONIES]

    @pytest.mark.asyncio
    async def test_consensus_convergence_failure(
        self, base_router: Any, mock_consensus: Any
    ) -> None:
        """Test consensus convergence failure fallback."""
        from kagami.core.coordination.kagami_consensus import ConsensusState

        # Mock proposals
        mock_consensus.collect_proposals.return_value = []

        # Mock consensus state (failed to converge)
        mock_state = ConsensusState(
            proposals=[],
            agreement_matrix=MagicMock(),
            converged=False,
            iterations=10,
        )
        mock_consensus.byzantine_consensus.return_value = mock_state

        router = ConsensusAwareFanoRouter(
            fano_router=base_router,
            consensus=mock_consensus,
            enable_consensus=True,
        )

        result = await router.route_with_consensus(
            action="build.feature",
            params={},
        )

        # Should fallback to initial routing
        assert result is not None

    @pytest.mark.asyncio
    async def test_factory_creation(self) -> None:
        """Test factory function creates router correctly."""
        router = create_consensus_aware_router(
            enable_consensus=False,
            consensus_timeout=1.0,
        )

        assert isinstance(router, ConsensusAwareFanoRouter)
        assert router.enable_consensus is False
        assert router.consensus_timeout == 1.0


class TestFanoLineConsensus:
    """Test suite for fano_line_consensus function."""

    def test_fano_line_consensus_agreement(self) -> None:
        """Test Fano line consensus with high agreement."""
        from kagami.core.coordination.kagami_consensus import ColonyID, CoordinationProposal

        # Create 3 proposals with high agreement
        proposals = [
            CoordinationProposal(
                proposer=ColonyID.SPARK,
                target_colonies=[ColonyID.FORGE, ColonyID.FLOW],
            ),
            CoordinationProposal(
                proposer=ColonyID.FORGE,
                target_colonies=[ColonyID.FORGE, ColonyID.FLOW],
            ),
            CoordinationProposal(
                proposer=ColonyID.FLOW,
                target_colonies=[ColonyID.FORGE, ColonyID.FLOW, ColonyID.NEXUS],
            ),
        ]

        line = (0, 1, 2)  # Spark, Forge, Flow
        result = fano_line_consensus(line, proposals, quorum_threshold=0.5)

        # Should reach consensus (high agreement)
        assert result is True

    def test_fano_line_consensus_disagreement(self) -> None:
        """Test Fano line consensus with low agreement."""
        from kagami.core.coordination.kagami_consensus import ColonyID, CoordinationProposal

        # Create 3 proposals with low agreement
        proposals = [
            CoordinationProposal(
                proposer=ColonyID.SPARK,
                target_colonies=[ColonyID.FORGE],
            ),
            CoordinationProposal(
                proposer=ColonyID.FORGE,
                target_colonies=[ColonyID.BEACON],
            ),
            CoordinationProposal(
                proposer=ColonyID.FLOW,
                target_colonies=[ColonyID.CRYSTAL],
            ),
        ]

        line = (0, 1, 2)  # Spark, Forge, Flow
        result = fano_line_consensus(line, proposals, quorum_threshold=0.7)

        # Should fail consensus (low agreement)
        assert result is False

    def test_fano_line_consensus_invalid_line(self) -> None:
        """Test Fano line consensus with invalid line."""
        proposals = [MagicMock() for _ in range(7)]

        # Invalid line (not enough proposals)
        line = (10, 11, 12)
        result = fano_line_consensus(line, proposals)

        # Should fail (out of bounds)
        assert result is False


class TestBackwardCompatibility:
    """Test backward compatibility with FanoActionRouter."""

    def test_consensus_disabled_matches_fano_router(self, base_router) -> None:
        """Test that consensus-disabled mode matches FanoActionRouter."""
        consensus_router = ConsensusAwareFanoRouter(
            fano_router=base_router,
            enable_consensus=False,
        )

        actions = ["ping", "build.feature", "analyze.complex.system"]

        for action in actions:
            # Both should produce same routing
            base_result = base_router.route(action=action, params={})
            consensus_result = asyncio.run(
                consensus_router.route_with_consensus(action=action, params={})
            )

            # Check mode and colony selection match
            assert base_result.mode == consensus_result.mode
            base_colonies = {a.colony_idx for a in base_result.actions}
            consensus_colonies = {a.colony_idx for a in consensus_result.actions}
            assert base_colonies == consensus_colonies


class TestMetrics:
    """Test metrics emission."""

    @pytest.mark.asyncio
    async def test_metrics_initialization(self, base_router: Any) -> None:
        """Test metrics are initialized correctly."""
        router = ConsensusAwareFanoRouter(
            fano_router=base_router,
            enable_consensus=False,
        )

        # Metrics should be initialized (or None if import failed)
        assert hasattr(router, "metrics_overrides")
        assert hasattr(router, "metrics_fallbacks")
        assert hasattr(router, "metrics_latency")
