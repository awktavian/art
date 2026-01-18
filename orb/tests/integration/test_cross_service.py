"""Cross-Service Integration Tests — Comprehensive ecosystem verification.

Tests for the cross-service integration system:
1. GitHub Development Flow
2. Linear Sprint Sync
3. Notion Knowledge Base
4. Learning Pipeline
5. Service Context Injection
6. Stigmergy Cross-Service Learning

These tests verify the ecosystem operates cohesively end-to-end.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_composio_service():
    """Create a mock Composio service."""
    service = MagicMock()
    service.initialized = True
    service.initialize = AsyncMock(return_value=True)
    service.get_connected_apps = AsyncMock(
        return_value=[
            {"toolkit": "github", "status": "ACTIVE"},
            {"toolkit": "linear", "status": "ACTIVE"},
            {"toolkit": "notion", "status": "ACTIVE"},
            {"toolkit": "slack", "status": "ACTIVE"},
        ]
    )
    service.execute_action = AsyncMock(
        return_value={
            "success": True,
            "data": {"id": "test-123"},
        }
    )
    return service


# =============================================================================
# GITHUB FLOW TESTS
# =============================================================================


class TestGitHubDevelopmentFlow:
    """Tests for GitHubDevelopmentFlow."""

    @pytest.mark.asyncio
    async def test_create_branch(self, mock_composio_service):
        """Test branch creation."""
        from kagami.core.orchestration.github_flow import GitHubDevelopmentFlow

        with patch(
            "kagami.core.orchestration.github_flow.get_composio_service",
            return_value=mock_composio_service,
        ):
            # Mock get reference response
            mock_composio_service.execute_action.side_effect = [
                # GET_A_REFERENCE
                {"data": {"object": {"sha": "abc123"}}},
                # CREATE_A_REFERENCE
                {"success": True, "data": {"ref": "refs/heads/feature/test"}},
            ]

            flow = GitHubDevelopmentFlow()
            await flow.initialize()

            branch = await flow.create_branch("feature/test-branch")

            assert branch is not None
            assert branch.name == "feature/test-branch"
            assert branch.sha == "abc123"

    @pytest.mark.asyncio
    async def test_create_pr(self, mock_composio_service):
        """Test PR creation."""
        from kagami.core.orchestration.github_flow import GitHubDevelopmentFlow

        with patch(
            "kagami.core.orchestration.github_flow.get_composio_service",
            return_value=mock_composio_service,
        ):
            mock_composio_service.execute_action.return_value = {
                "data": {
                    "number": 42,
                    "title": "Test PR",
                    "body": "Test description",
                    "state": "open",
                    "html_url": "https://github.com/test/pr/42",
                    "draft": False,
                }
            }

            flow = GitHubDevelopmentFlow()
            await flow.initialize()

            pr = await flow.create_pr(
                title="Test PR",
                head="feature/test",
                body="Test description",
            )

            assert pr is not None
            assert pr.number == 42
            assert pr.title == "Test PR"

    @pytest.mark.asyncio
    async def test_get_workflow_runs(self, mock_composio_service):
        """Test getting CI workflow runs."""
        from kagami.core.orchestration.github_flow import GitHubDevelopmentFlow

        with patch(
            "kagami.core.orchestration.github_flow.get_composio_service",
            return_value=mock_composio_service,
        ):
            mock_composio_service.execute_action.return_value = {
                "data": {
                    "workflow_runs": [
                        {
                            "id": 1,
                            "name": "CI",
                            "status": "completed",
                            "conclusion": "success",
                            "html_url": "https://github.com/test/actions/1",
                            "created_at": "2025-01-04T12:00:00Z",
                            "head_sha": "abc123",
                        }
                    ]
                }
            }

            flow = GitHubDevelopmentFlow()
            await flow.initialize()

            runs = await flow.get_workflow_runs(limit=5)

            assert len(runs) == 1
            assert runs[0].name == "CI"


# =============================================================================
# LINEAR SYNC TESTS
# =============================================================================


class TestLinearSprintSync:
    """Tests for LinearSprintSync."""

    @pytest.mark.asyncio
    async def test_get_cycles(self, mock_composio_service):
        """Test getting Linear cycles."""
        from kagami.core.orchestration.linear_sync import LinearSprintSync

        with patch(
            "kagami.core.orchestration.linear_sync.get_composio_service",
            return_value=mock_composio_service,
        ):
            mock_composio_service.execute_action.side_effect = [
                # GET_ALL_LINEAR_TEAMS
                {"data": {"teams": {"nodes": [{"key": "KAG", "id": "team-123"}]}}},
                # GET_CYCLES_BY_TEAM_ID
                {
                    "data": {
                        "team": {
                            "cycles": {
                                "nodes": [
                                    {
                                        "id": "cycle-1",
                                        "number": 1,
                                        "name": "Sprint 1",
                                        "startsAt": "2025-01-01T00:00:00Z",
                                        "endsAt": "2025-01-15T00:00:00Z",
                                        "progress": 0.5,
                                    }
                                ]
                            }
                        }
                    }
                },
            ]

            sync = LinearSprintSync()
            await sync.initialize()

            cycles = await sync.get_cycles()

            assert len(cycles) == 1
            assert cycles[0].number == 1
            assert cycles[0].display_name == "Sprint 1"

    @pytest.mark.asyncio
    async def test_create_issue(self, mock_composio_service):
        """Test creating Linear issue."""
        from kagami.core.orchestration.linear_sync import LinearSprintSync

        with patch(
            "kagami.core.orchestration.linear_sync.get_composio_service",
            return_value=mock_composio_service,
        ):
            mock_composio_service.execute_action.side_effect = [
                # GET_ALL_LINEAR_TEAMS
                {"data": {"teams": {"nodes": [{"key": "KAG", "id": "team-123"}]}}},
                # CREATE_LINEAR_ISSUE
                {
                    "data": {
                        "issueCreate": {
                            "issue": {
                                "id": "issue-1",
                                "identifier": "KAG-123",
                                "title": "Test Issue",
                            }
                        }
                    }
                },
            ]

            sync = LinearSprintSync()
            await sync.initialize()

            issue = await sync.create_issue(
                title="Test Issue",
                description="Test description",
            )

            assert issue is not None
            assert issue.identifier == "KAG-123"

    @pytest.mark.asyncio
    async def test_velocity_metrics(self, mock_composio_service):
        """Test velocity calculation."""
        from kagami.core.orchestration.linear_sync import (
            LinearSprintSync,
            VelocityMetrics,
        )

        # Create metrics directly for unit testing
        metrics = VelocityMetrics(
            cycle_id="cycle-1",
            cycle_number=1,
            points_planned=20,
            points_completed=15,
            issues_planned=10,
            issues_completed=8,
            carry_over=5,
        )

        assert metrics.velocity == 0.75
        assert metrics.completion_rate == 0.8


# =============================================================================
# NOTION KB TESTS
# =============================================================================


class TestNotionKnowledgeBase:
    """Tests for NotionKnowledgeBase."""

    @pytest.mark.asyncio
    async def test_store_research(self, mock_composio_service):
        """Test storing research findings."""
        from kagami.core.orchestration.notion_kb import NotionKnowledgeBase

        with patch(
            "kagami.core.orchestration.notion_kb.get_composio_service",
            return_value=mock_composio_service,
        ):
            mock_composio_service.execute_action.return_value = {"data": {"id": "page-123"}}

            kb = NotionKnowledgeBase()
            await kb.initialize()

            entry = await kb.store_research(
                topic="E8 Optimization",
                findings="Key finding...",
                source="Grove research",
                confidence=0.9,
            )

            assert entry is not None
            assert entry.topic == "E8 Optimization"

    @pytest.mark.asyncio
    async def test_log_decision(self, mock_composio_service):
        """Test logging architectural decision."""
        from kagami.core.orchestration.notion_kb import (
            NotionKnowledgeBase,
            DecisionStatus,
        )

        with patch(
            "kagami.core.orchestration.notion_kb.get_composio_service",
            return_value=mock_composio_service,
        ):
            mock_composio_service.execute_action.return_value = {"data": {"id": "page-456"}}

            kb = NotionKnowledgeBase()
            await kb.initialize()

            entry = await kb.log_decision(
                title="Use E8 for routing",
                context="Need efficient routing...",
                decision="Implement E8 lattice",
                consequences=["+efficiency", "-complexity"],
                status=DecisionStatus.ACCEPTED,
            )

            assert entry is not None
            assert entry.title == "Use E8 for routing"
            assert entry.status == DecisionStatus.ACCEPTED


# =============================================================================
# LEARNING PIPELINE TESTS
# =============================================================================


class TestLearningPipeline:
    """Tests for LearningPipeline."""

    @pytest.mark.asyncio
    async def test_record_action(self):
        """Test recording service action."""
        from kagami.core.orchestration.learning_pipeline import LearningPipeline

        pipeline = LearningPipeline()
        # Don't initialize (avoid external dependencies)
        pipeline._initialized = True

        await pipeline.record_action(
            colony="forge",
            service="github",
            action="GITHUB_CREATE_A_REFERENCE",
            success=True,
            duration_ms=150,
        )

        assert pipeline.metrics.total_actions_recorded == 1
        assert pipeline.metrics.successful_actions == 1
        assert "forge" in pipeline.metrics.active_colonies
        assert "github" in pipeline.metrics.active_services

    @pytest.mark.asyncio
    async def test_action_buffer(self):
        """Test action buffer accumulation."""
        from kagami.core.orchestration.learning_pipeline import LearningPipeline

        pipeline = LearningPipeline()
        pipeline._initialized = True

        # Record multiple actions
        for i in range(5):
            await pipeline.record_action(
                colony="forge",
                service="github",
                action=f"ACTION_{i}",
                success=i % 2 == 0,  # Alternating success
            )

        assert pipeline.metrics.total_actions_recorded == 5
        assert pipeline.metrics.successful_actions == 3
        assert pipeline.metrics.failed_actions == 2

    def test_routing_suggestions_empty(self):
        """Test routing suggestions with no data."""
        from kagami.core.orchestration.learning_pipeline import LearningPipeline

        pipeline = LearningPipeline()
        pipeline._initialized = True

        suggestions = pipeline.get_routing_suggestions("test task")

        # Should return empty list when no stigmergy data
        assert suggestions == []

    def test_status(self):
        """Test status reporting."""
        from kagami.core.orchestration.learning_pipeline import LearningPipeline

        pipeline = LearningPipeline()

        status = pipeline.get_status()

        assert "initialized" in status
        assert "total_actions" in status
        assert "success_rate" in status


# =============================================================================
# SERVICE CONTEXT INJECTION TESTS
# =============================================================================


class TestServiceContextInjection:
    """Tests for service context injection."""

    def test_get_service_context(self):
        """Test getting service context for colony."""
        from kagami.core.unified_agents.router_scoring import (
            COLONY_SERVICE_MAP,
            RouterScoringMixin,
        )

        # Create a minimal instance
        class TestRouter(RouterScoringMixin):
            pass

        router = TestRouter()

        # Test forge context
        context = router.get_service_context("forge")
        assert "GitHub" in context or "github" in context.lower()
        assert "Linear" in context or "linear" in context.lower()

        # Test grove context
        context = router.get_service_context("grove")
        assert "Notion" in context or "notion" in context.lower()

    def test_get_colony_services(self):
        """Test getting primary services for colony."""
        from kagami.core.unified_agents.router_scoring import RouterScoringMixin

        class TestRouter(RouterScoringMixin):
            pass

        router = TestRouter()

        services = router.get_colony_services("forge")
        assert "github" in services
        assert "linear" in services

    def test_should_prefer_service_colony(self):
        """Test service-based colony preference."""
        from kagami.core.unified_agents.router_scoring import RouterScoringMixin

        class TestRouter(RouterScoringMixin):
            pass

        router = TestRouter()

        # GitHub actions should prefer forge
        assert router.should_prefer_service_colony("create github branch", {}) == "forge"

        # Research actions should prefer grove
        assert router.should_prefer_service_colony("research in notion", {}) == "grove"

        # Verification should prefer crystal
        assert router.should_prefer_service_colony("verify github pr", {}) == "crystal"

    def test_inject_service_context(self):
        """Test context injection."""
        from kagami.core.unified_agents.router_scoring import RouterScoringMixin

        class TestRouter(RouterScoringMixin):
            pass

        router = TestRouter()

        context = {"task": "build feature"}
        enhanced = router.inject_service_context("forge", "build", context)

        assert enhanced["_service_context_injected"] is True
        assert "service_context" in enhanced
        assert "primary_services" in enhanced


# =============================================================================
# STIGMERGY CROSS-SERVICE TESTS
# =============================================================================


class TestStigmergyCrossService:
    """Tests for stigmergy cross-service learning."""

    def test_record_service_action(self):
        """Test recording service action in stigmergy."""
        from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

        learner = StigmergyLearner(
            enable_persistence=False,
            enable_game_model=False,
        )

        # Record some actions
        learner.record_service_action(
            colony="forge",
            service="github",
            action="CREATE_BRANCH",
            success=True,
            duration_ms=100,
        )

        learner.record_service_action(
            colony="forge",
            service="github",
            action="CREATE_BRANCH",
            success=True,
            duration_ms=120,
        )

        learner.record_service_action(
            colony="forge",
            service="github",
            action="CREATE_BRANCH",
            success=False,
            duration_ms=50,
        )

        # Check pattern was created
        pattern_key = ("github:CREATE_BRANCH", "forge")
        assert pattern_key in learner.patterns

        pattern = learner.patterns[pattern_key]
        assert pattern.success_count == 2
        assert pattern.failure_count == 1

    def test_get_colony_service_affinity(self):
        """Test getting colony service affinity."""
        from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

        learner = StigmergyLearner(
            enable_persistence=False,
            enable_game_model=False,
        )

        # Record actions for multiple services
        for _ in range(10):
            learner.record_service_action(
                colony="forge",
                service="github",
                action="CREATE_PR",
                success=True,
            )

        for _ in range(5):
            learner.record_service_action(
                colony="forge",
                service="linear",
                action="CREATE_ISSUE",
                success=True,
            )

        for _ in range(5):
            learner.record_service_action(
                colony="forge",
                service="linear",
                action="CREATE_ISSUE",
                success=False,
            )

        affinities = learner.get_colony_service_affinity("forge")

        # GitHub should have higher affinity (100% success)
        # Linear should have lower affinity (50% success)
        assert "github" in affinities
        assert "linear" in affinities
        assert affinities["github"] > affinities["linear"]

    def test_get_best_colony_for_service(self):
        """Test finding best colony for service."""
        from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

        learner = StigmergyLearner(
            enable_persistence=False,
            enable_game_model=False,
        )

        # Forge is good at GitHub
        for _ in range(10):
            learner.record_service_action(
                colony="forge",
                service="github",
                action="CREATE_PR",
                success=True,
            )

        # Flow is bad at GitHub
        for _ in range(10):
            learner.record_service_action(
                colony="flow",
                service="github",
                action="CREATE_PR",
                success=False,
            )

        best = learner.get_best_colony_for_service("github")
        assert best == "forge"

    def test_get_cross_service_patterns(self):
        """Test getting cross-service patterns."""
        from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

        learner = StigmergyLearner(
            enable_persistence=False,
            enable_game_model=False,
        )

        # Record enough actions to meet thresholds
        for _ in range(10):
            learner.record_service_action(
                colony="forge",
                service="github",
                action="CREATE_BRANCH",
                success=True,
                duration_ms=100,
            )

        patterns = learner.get_cross_service_patterns(
            min_count=5,
            min_success_rate=0.5,
        )

        assert len(patterns) > 0
        assert patterns[0]["service"] == "github"
        assert patterns[0]["colony"] == "forge"
        assert patterns[0]["success_rate"] == 1.0


# =============================================================================
# COLONY PROMPT TESTS
# =============================================================================


class TestColonyPrompts:
    """Tests for enhanced colony prompts."""

    def test_service_hints_present(self):
        """Test that service hints are present in colony prompts."""
        from kagami.core.prompts.colonies import COLONY_PROMPTS

        for _name, prompt in COLONY_PROMPTS.items():
            # Check that service hints are defined
            assert hasattr(prompt, "service_hints")
            assert hasattr(prompt, "primary_services")
            assert hasattr(prompt, "service_actions")

    def test_forge_has_github_linear(self):
        """Test Forge has GitHub and Linear services."""
        from kagami.core.prompts.colonies import FORGE

        assert "github" in FORGE.primary_services
        assert "linear" in FORGE.primary_services
        assert "github" in FORGE.service_actions

    def test_grove_has_notion(self):
        """Test Grove has Notion service."""
        from kagami.core.prompts.colonies import GROVE

        assert "notion" in GROVE.primary_services
        assert "notion" in GROVE.service_actions

    def test_system_prompt_includes_hints(self):
        """Test system prompt includes service hints."""
        from kagami.core.prompts.colonies import FORGE

        system_prompt = FORGE.system_prompt

        # Should include service integration section
        assert "GitHub" in system_prompt or "github" in system_prompt.lower()

    def test_get_service_context_method(self):
        """Test get_service_context method."""
        from kagami.core.prompts.colonies import FORGE, GROVE

        forge_context = FORGE.get_service_context()
        assert "GitHub" in forge_context or "github" in forge_context.lower()

        grove_context = GROVE.get_service_context()
        assert "Notion" in grove_context or "notion" in grove_context.lower()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestEcosystemIntegration:
    """End-to-end ecosystem integration tests."""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self, mock_composio_service):
        """Test a full workflow through the ecosystem."""
        from kagami.core.orchestration.github_flow import GitHubDevelopmentFlow
        from kagami.core.orchestration.linear_sync import LinearSprintSync
        from kagami.core.orchestration.learning_pipeline import LearningPipeline

        with (
            patch(
                "kagami.core.orchestration.github_flow.get_composio_service",
                return_value=mock_composio_service,
            ),
            patch(
                "kagami.core.orchestration.linear_sync.get_composio_service",
                return_value=mock_composio_service,
            ),
        ):
            # Setup mocks
            mock_composio_service.execute_action.side_effect = [
                # Linear: GET_ALL_LINEAR_TEAMS
                {"data": {"teams": {"nodes": [{"key": "KAG", "id": "team-123"}]}}},
                # Linear: CREATE_LINEAR_ISSUE
                {
                    "data": {
                        "issueCreate": {
                            "issue": {"id": "issue-1", "identifier": "KAG-100", "title": "Test"}
                        }
                    }
                },
                # GitHub: GET_A_REFERENCE
                {"data": {"object": {"sha": "abc123"}}},
                # GitHub: CREATE_A_REFERENCE
                {"success": True, "data": {"ref": "refs/heads/feature/kag-100"}},
            ]

            # Initialize components
            linear_sync = LinearSprintSync()
            await linear_sync.initialize()

            github_flow = GitHubDevelopmentFlow()
            await github_flow.initialize()

            pipeline = LearningPipeline()
            pipeline._initialized = True

            # Workflow: Create Linear issue, then create branch
            issue = await linear_sync.create_issue(
                title="Test Feature",
                description="Implement test feature",
            )

            if issue:
                # Record the action
                await pipeline.record_action(
                    colony="beacon",
                    service="linear",
                    action="CREATE_LINEAR_ISSUE",
                    success=True,
                    duration_ms=200,
                )

            # Create branch for the issue
            branch = await github_flow.create_branch(
                branch_name="feature/kag-100-test-feature",
                linear_issue_id=issue.identifier if issue else None,
            )

            if branch:
                await pipeline.record_action(
                    colony="forge",
                    service="github",
                    action="CREATE_A_REFERENCE",
                    success=True,
                    duration_ms=150,
                )

            # Verify pipeline recorded actions
            assert pipeline.metrics.total_actions_recorded >= 2
            assert "beacon" in pipeline.metrics.active_colonies
            assert "forge" in pipeline.metrics.active_colonies

    @pytest.mark.asyncio
    async def test_status_reporting(self, mock_composio_service):
        """Test that all components report status correctly."""
        from kagami.core.orchestration.github_flow import GitHubDevelopmentFlow
        from kagami.core.orchestration.linear_sync import LinearSprintSync
        from kagami.core.orchestration.notion_kb import NotionKnowledgeBase
        from kagami.core.orchestration.learning_pipeline import LearningPipeline

        # GitHub Flow status
        github_flow = GitHubDevelopmentFlow()
        status = github_flow.get_status()
        assert "initialized" in status
        assert "repo" in status

        # Linear Sync status
        linear_sync = LinearSprintSync()
        status = linear_sync.get_status()
        assert "initialized" in status
        assert "team_key" in status

        # Notion KB status
        notion_kb = NotionKnowledgeBase()
        status = notion_kb.get_status()
        assert "initialized" in status

        # Learning Pipeline status
        pipeline = LearningPipeline()
        status = pipeline.get_status()
        assert "initialized" in status
        assert "total_actions" in status
