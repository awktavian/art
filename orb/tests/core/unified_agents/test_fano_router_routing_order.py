"""Tests for Fano Router - Primary Colony First Fix (Dec 21, 2025).

CIRCUIT TRACE discovered that _route_all_colonies() was returning
actions in index order (0-6) instead of primary first.

This test verifies the fix ensures primary colony is always first.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.unified_agents.fano_action_router import (
    FanoActionRouter,
    create_fano_router,
)


class TestFanoRouterPrimaryFirst:
    """Verify primary colony is always first in routing results."""

    @pytest.fixture
    def router(self) -> FanoActionRouter:
        return FanoActionRouter()

    @pytest.fixture
    def consensus_router(self) -> FanoActionRouter:
        return create_fano_router()

    def test_plan_architecture_routes_to_beacon_first(
        self, consensus_router: FanoActionRouter
    ) -> None:
        """'plan architecture' should route to beacon (4) first."""
        result = consensus_router.route("plan architecture", {})

        assert len(result.actions) > 0
        primary_action = result.actions[0]

        assert primary_action.is_primary is True
        assert primary_action.colony_name == "beacon"
        assert primary_action.colony_idx == 4

    def test_implement_feature_routes_to_forge_first(
        self, consensus_router: FanoActionRouter
    ) -> None:
        """'implement feature' should route to forge (1) first."""
        result = consensus_router.route("implement feature", {})

        assert len(result.actions) > 0
        primary_action = result.actions[0]

        assert primary_action.is_primary is True
        assert primary_action.colony_name == "forge"
        assert primary_action.colony_idx == 1

    def test_debug_error_routes_to_flow_first(self, consensus_router: FanoActionRouter) -> None:
        """'debug error' should route to flow (2) first."""
        result = consensus_router.route("debug error", {})

        assert len(result.actions) > 0
        primary_action = result.actions[0]

        assert primary_action.is_primary is True
        assert primary_action.colony_name == "flow"
        assert primary_action.colony_idx == 2

    def test_research_topic_routes_to_grove_first(self, consensus_router: FanoActionRouter) -> None:
        """'research topic' should route to grove (5) first."""
        result = consensus_router.route("research topic", {})

        assert len(result.actions) > 0
        primary_action = result.actions[0]

        assert primary_action.is_primary is True
        assert primary_action.colony_name == "grove"
        assert primary_action.colony_idx == 5

    def test_all_colonies_mode_has_primary_first(self, router: FanoActionRouter) -> None:
        """In ALL_COLONIES mode (complexity >= 0.7), primary should still be first."""
        # "plan architecture" triggers ALL_COLONIES mode (complexity ~0.78)
        result = router.route("plan architecture", {})

        # Should have 7 actions (all colonies)
        assert len(result.actions) == 7

        # First action must be primary
        assert result.actions[0].is_primary is True

        # Only one primary
        primary_count = sum(1 for a in result.actions if a.is_primary)
        assert primary_count == 1

    def test_fano_line_mode_has_primary_first(self, router: FanoActionRouter) -> None:
        """In FANO_LINE mode (complexity 0.3-0.7), primary should be first."""
        # "build feature" triggers FANO_LINE mode (complexity ~0.57)
        result = router.route("build feature", {})

        # Should have 3 actions (Fano line)
        assert len(result.actions) == 3

        # First action must be primary
        assert result.actions[0].is_primary is True
        assert result.actions[0].fano_role == "source"

    def test_single_mode_is_primary(self, router: FanoActionRouter) -> None:
        """In SINGLE mode (complexity < 0.3), single action is primary."""
        # "debug error" triggers SINGLE mode (complexity ~0.20)
        result = router.route("debug error", {})

        # Should have 1 action
        assert len(result.actions) == 1

        # That action is primary
        assert result.actions[0].is_primary is True
