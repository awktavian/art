"""Tests for Swarm Coordination — Advanced Multi-Instance Patterns.

Tests cover:
1. ScatterGather pattern
2. ConsensusVoting pattern
3. LeaderFollower pattern
4. TaskAuction pattern
5. PheromoneCoordinator
6. SwarmSearch
7. SwarmCoordinator unified interface

Created: December 28, 2025
"""

from __future__ import annotations

import asyncio
import pytest
import time
from typing import Any

from kagami.core.coordination.meta_orchestrator import (
    MetaOrchestrator,
    create_meta_orchestrator,
    reset_meta_orchestrator,
)
from kagami.core.coordination.swarm_coordination import (
    SwarmCoordinator,
    SwarmSignal,
    Vote,
    Bid,
    SwarmSearchResult,
    ScatterGather,
    ConsensusVoting,
    LeaderFollower,
    TaskAuction,
    PheromoneCoordinator,
    SwarmSearch,
    create_swarm_coordinator,
    reset_swarm_coordinator,
)


# =============================================================================
# MOCK INSTANCE (same as test_meta_orchestrator)
# =============================================================================


class MockInstance:
    """Mock OrchestratableInstance for testing."""

    def __init__(
        self,
        instance_id: str = "mock_1",
        instance_type: str = "mock",
        capabilities: list[str] | None = None,
        h_x: float = 1.0,
        load: float = 0.0,
        vote_choice: str | None = None,
        vote_confidence: float = 0.8,
    ):
        self._instance_id = instance_id
        self._instance_type = instance_type
        self._capabilities = capabilities or ["general"]
        self._h_x = h_x
        self._load = load
        self._vote_choice = vote_choice
        self._vote_confidence = vote_confidence
        self._executions: list[tuple[str, dict]] = []

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def instance_type(self) -> str:
        return self._instance_type

    async def execute(
        self,
        task: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._executions.append((task, params))
        await asyncio.sleep(0.001)

        # Handle voting
        if task == "vote" and self._vote_choice:
            return {
                "success": True,
                "result": {
                    "choice": self._vote_choice,
                    "confidence": self._vote_confidence,
                },
            }

        # Handle search
        if task == "search":
            return {
                "success": True,
                "result": {
                    "query": params.get("query"),
                    "instance": self._instance_id,
                    "confidence": 0.7,
                },
            }

        return {
            "success": True,
            "result": {
                "task": task,
                "instance": self._instance_id,
            },
        }

    def get_health(self) -> dict[str, Any]:
        return {
            "h_x": self._h_x,
            "status": "healthy" if self._h_x > 0.5 else "unhealthy",
            "load": self._load,
        }

    def get_capabilities(self) -> list[str]:
        return self._capabilities


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def orchestrator() -> MetaOrchestrator:
    """Create test orchestrator."""
    reset_meta_orchestrator()
    return create_meta_orchestrator(enable_persistence=False)


@pytest.fixture
def mock_instances() -> dict[str, MockInstance]:
    """Create multiple mock instances."""
    return {
        "instance_1": MockInstance(
            instance_id="instance_1",
            h_x=0.9,
            load=0.2,
            vote_choice="option_a",
            vote_confidence=0.9,
        ),
        "instance_2": MockInstance(
            instance_id="instance_2",
            h_x=0.8,
            load=0.3,
            vote_choice="option_a",
            vote_confidence=0.7,
        ),
        "instance_3": MockInstance(
            instance_id="instance_3",
            h_x=0.95,
            load=0.1,
            vote_choice="option_b",
            vote_confidence=0.6,
        ),
    }


@pytest.fixture
def orchestrator_with_instances(
    orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
) -> MetaOrchestrator:
    """Create orchestrator with registered instances."""
    for name, instance in mock_instances.items():
        orchestrator.register_instance(name, instance)
    return orchestrator


# =============================================================================
# SCATTER-GATHER TESTS
# =============================================================================


class TestScatterGather:
    """Tests for ScatterGather pattern."""

    @pytest.mark.asyncio
    async def test_scatter_to_all_instances(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test scattering to all instances."""
        scatter = ScatterGather(orchestrator_with_instances)

        result = await scatter.execute(
            task="parallel task",
            params={"key": "value"},
        )

        assert result["success"] is True
        assert len(result["results"]) == 3
        assert len(result["instances_used"]) == 3

    @pytest.mark.asyncio
    async def test_scatter_to_specific_instances(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test scattering to specific instances."""
        scatter = ScatterGather(orchestrator_with_instances)

        result = await scatter.execute(
            task="parallel task",
            instance_ids=["instance_1", "instance_2"],
        )

        assert len(result["results"]) == 2
        assert len(result["instances_used"]) == 2

    @pytest.mark.asyncio
    async def test_scatter_with_custom_aggregator(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test scatter with custom aggregation function."""

        def count_successes(results: list[dict]) -> int:
            return sum(1 for r in results if r.get("success"))

        scatter = ScatterGather(
            orchestrator_with_instances,
            aggregator=count_successes,
        )

        result = await scatter.execute(task="parallel task")

        assert result["aggregated"] == 3  # All 3 should succeed

    @pytest.mark.asyncio
    async def test_scatter_with_timeout(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test scatter respects timeout."""
        scatter = ScatterGather(orchestrator_with_instances)

        result = await scatter.execute(
            task="parallel task",
            timeout=10.0,  # Generous timeout
        )

        assert result["success"] is True


# =============================================================================
# CONSENSUS VOTING TESTS
# =============================================================================


class TestConsensusVoting:
    """Tests for ConsensusVoting pattern."""

    @pytest.mark.asyncio
    async def test_vote_basic(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test basic voting."""
        consensus = ConsensusVoting(orchestrator_with_instances)

        result = await consensus.vote(
            question="Which option?",
            options=["option_a", "option_b"],
        )

        assert result["success"] is True
        assert result["winner"] in ["option_a", "option_b"]
        assert result["total_votes"] == 3
        assert "agreement" in result

    @pytest.mark.asyncio
    async def test_vote_quorum_reached(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test quorum detection."""
        # 2 out of 3 vote for option_a
        consensus = ConsensusVoting(
            orchestrator_with_instances,
            quorum_threshold=0.6,
        )

        result = await consensus.vote(
            question="Which option?",
            options=["option_a", "option_b"],
        )

        assert result["winner"] == "option_a"  # 2/3 voted for it
        assert result["quorum_reached"] is True

    @pytest.mark.asyncio
    async def test_vote_confidence_weighting(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test confidence-weighted voting."""
        consensus = ConsensusVoting(
            orchestrator_with_instances,
            confidence_weight=True,
        )

        result = await consensus.vote(
            question="Which option?",
            options=["option_a", "option_b"],
        )

        # Higher confidence votes should have more weight
        assert result["success"] is True


# =============================================================================
# LEADER-FOLLOWER TESTS
# =============================================================================


class TestLeaderFollower:
    """Tests for LeaderFollower pattern."""

    @pytest.mark.asyncio
    async def test_elect_leader(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test leader election."""
        lf = LeaderFollower(orchestrator_with_instances)

        leader = await lf.elect_leader()

        assert leader is not None
        assert leader in orchestrator_with_instances.list_instances()
        # instance_3 has highest h_x and lowest load
        assert leader == "instance_3"

    @pytest.mark.asyncio
    async def test_lead_execution(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test leader execution."""
        lf = LeaderFollower(orchestrator_with_instances)
        await lf.elect_leader()

        result = await lf.lead(task="leader task")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_follow_execution(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test follower execution."""
        lf = LeaderFollower(orchestrator_with_instances)
        await lf.elect_leader()

        results = await lf.follow(task="follower task")

        # Should execute on non-leaders
        assert len(results) == 2
        leader = lf.leader
        for r in results:
            assert r["instance_id"] != leader

    @pytest.mark.asyncio
    async def test_leader_property(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test leader property."""
        lf = LeaderFollower(orchestrator_with_instances)

        assert lf.leader is None
        await lf.elect_leader()
        assert lf.leader is not None


# =============================================================================
# TASK AUCTION TESTS
# =============================================================================


class TestTaskAuction:
    """Tests for TaskAuction pattern."""

    @pytest.mark.asyncio
    async def test_auction_basic(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test basic auction."""
        auction = TaskAuction(orchestrator_with_instances)

        result = await auction.auction(
            task="test task",
            params={"key": "value"},
        )

        assert result["success"] is True
        assert result["winner"] is not None
        assert result["total_bids"] == 3

    @pytest.mark.asyncio
    async def test_auction_capability_matching(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test auction considers capabilities."""
        auction = TaskAuction(orchestrator_with_instances)

        result = await auction.auction(
            task="test task",
            required_capabilities=["general"],
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_auction_excludes_unsafe(self, orchestrator: MetaOrchestrator) -> None:
        """Test auction excludes unsafe instances."""
        # Register one safe, one unsafe instance
        orchestrator.register_instance("safe", MockInstance(instance_id="safe", h_x=0.9))
        orchestrator.register_instance("unsafe", MockInstance(instance_id="unsafe", h_x=0.05))

        auction = TaskAuction(orchestrator)
        result = await auction.auction(task="test task")

        assert result["winner"] == "safe"


# =============================================================================
# PHEROMONE COORDINATOR TESTS
# =============================================================================


class TestPheromoneCoordinator:
    """Tests for PheromoneCoordinator."""

    def test_deposit_signal(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test depositing a pheromone signal."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)

        signal = pheromone.deposit(
            signal_id="test_signal",
            value={"path": "/some/path"},
            strength=0.8,
            source_instance="instance_1",
        )

        assert signal.signal_id == "test_signal"
        assert signal.strength == 0.8

    def test_read_signal(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test reading a pheromone signal."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)

        pheromone.deposit("test", "value", 0.9)
        signal = pheromone.read("test")

        assert signal is not None
        assert signal.value == "value"

    def test_reinforce_signal(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test reinforcing a pheromone signal."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)

        pheromone.deposit("test", "value", 0.5)
        pheromone.reinforce("test", boost=0.2)

        signal = pheromone.read("test")
        assert signal is not None
        assert signal.strength == pytest.approx(0.7)

    def test_get_strongest_signal(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test getting strongest signal."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)

        pheromone.deposit("weak", "weak_value", 0.3)
        pheromone.deposit("strong", "strong_value", 0.9)
        pheromone.deposit("medium", "medium_value", 0.6)

        strongest = pheromone.get_strongest()
        assert strongest is not None
        assert strongest.signal_id == "strong"

    def test_get_strongest_with_prefix(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test getting strongest signal with prefix filter."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)

        pheromone.deposit("path:a", "a", 0.9)
        pheromone.deposit("path:b", "b", 0.5)
        pheromone.deposit("other:c", "c", 0.95)

        strongest = pheromone.get_strongest(prefix="path:")
        assert strongest is not None
        assert strongest.signal_id == "path:a"

    def test_read_all_above_threshold(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test reading all signals above threshold."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)

        pheromone.deposit("s1", "v1", 0.9)
        pheromone.deposit("s2", "v2", 0.05)  # Below threshold
        pheromone.deposit("s3", "v3", 0.5)

        signals = pheromone.read_all(min_strength=0.1)
        assert len(signals) == 2


# =============================================================================
# SWARM SEARCH TESTS
# =============================================================================


class TestSwarmSearch:
    """Tests for SwarmSearch."""

    @pytest.mark.asyncio
    async def test_parallel_search(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test parallel search across instances."""
        search = SwarmSearch(orchestrator_with_instances)

        results = await search.search(
            query="test query",
            params={"depth": 1},
        )

        assert len(results) > 0
        assert all(isinstance(r, SwarmSearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_top_k(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test search returns top-k results."""
        search = SwarmSearch(orchestrator_with_instances)

        results = await search.search(
            query="test query",
            top_k=2,
        )

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_deposits_pheromones(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test search deposits pheromone signals for top results."""
        pheromone = PheromoneCoordinator(orchestrator_with_instances)
        search = SwarmSearch(orchestrator_with_instances, pheromone)

        await search.search(query="test query", top_k=2)

        # Should have deposited signals
        signals = pheromone.read_all()
        assert len(signals) > 0


# =============================================================================
# SWARM COORDINATOR UNIFIED INTERFACE TESTS
# =============================================================================


class TestSwarmCoordinator:
    """Tests for SwarmCoordinator unified interface."""

    @pytest.mark.asyncio
    async def test_scatter_method(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test scatter convenience method."""
        swarm = SwarmCoordinator(orchestrator_with_instances)

        result = await swarm.scatter(task="test task")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_vote_method(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test vote convenience method."""
        swarm = SwarmCoordinator(orchestrator_with_instances)

        result = await swarm.vote(
            question="test question",
            options=["a", "b"],
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_elect_leader_method(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test elect_leader convenience method."""
        swarm = SwarmCoordinator(orchestrator_with_instances)

        leader = await swarm.elect_leader()
        assert leader is not None

    @pytest.mark.asyncio
    async def test_auction_task_method(self, orchestrator_with_instances: MetaOrchestrator) -> None:
        """Test auction_task convenience method."""
        swarm = SwarmCoordinator(orchestrator_with_instances)

        result = await swarm.auction_task(task="test task")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_parallel_search_method(
        self, orchestrator_with_instances: MetaOrchestrator
    ) -> None:
        """Test parallel_search convenience method."""
        swarm = SwarmCoordinator(orchestrator_with_instances)

        results = await swarm.parallel_search(query="test query")
        assert len(results) > 0


# =============================================================================
# DATA STRUCTURE TESTS
# =============================================================================


class TestDataStructures:
    """Tests for swarm coordination data structures."""

    def test_swarm_signal_decay(self) -> None:
        """Test SwarmSignal decay."""
        signal = SwarmSignal(
            signal_id="test",
            value="value",
            strength=1.0,
            created_at=time.time() - 7200,  # 2 hours ago
            decay_rate=0.9,
        )

        signal.apply_decay()
        # After 2 hours with 0.9 decay rate: 0.9^2 = 0.81
        assert signal.strength < 1.0

    def test_vote_creation(self) -> None:
        """Test Vote creation."""
        vote = Vote(
            instance_id="test",
            choice="option_a",
            confidence=0.8,
        )

        assert vote.instance_id == "test"
        assert vote.choice == "option_a"
        assert vote.confidence == 0.8

    def test_bid_combined_score(self) -> None:
        """Test Bid combined score calculation."""
        bid = Bid(
            instance_id="test",
            task_id="task",
            price=0.2,  # Low price
            capability_score=0.8,  # High capability
        )

        # Score should be high (good capability, low price)
        assert bid.combined_score > 1.0

    def test_swarm_search_result(self) -> None:
        """Test SwarmSearchResult creation."""
        result = SwarmSearchResult(
            instance_id="test",
            query="test query",
            result={"data": "value"},
            confidence=0.9,
        )

        assert result.instance_id == "test"
        assert result.confidence == 0.9
