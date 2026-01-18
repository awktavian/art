"""Swarm Coordination — Advanced Multi-Instance Coordination Primitives.

SWARM INTELLIGENCE PATTERNS:
============================
This module provides higher-level coordination primitives built on top of
the MetaOrchestrator for complex multi-instance workflows.

PATTERNS IMPLEMENTED:
=====================
1. SCATTER-GATHER: Distribute work across instances, collect results
2. CONSENSUS VOTING: Multiple instances vote on a decision
3. LEADER-FOLLOWER: One instance leads, others follow
4. AUCTION: Instances bid for tasks based on capabilities
5. PHEROMONE: Stigmergic coordination via shared signals
6. SWARM SEARCH: Parallel exploration with result sharing

GENERAL DESIGN:
===============
All patterns work with ANY OrchestratableInstance implementations.
Not locked to specific use cases (colonies, agents, workers, etc.).

MATHEMATICAL FOUNDATION:
========================
Swarm intelligence based on:
- Stigmergy (Theraulaz & Bonabeau 1999)
- Superorganism cooperation (Reeve & Hölldobler 2007)
- Collective decision-making (Seeley 2010)
- Critical density transitions (Dec 2025 research)

Created: December 28, 2025
Author: Meta-Orchestrator Design (Beacon + Forge)
"""

# Standard library imports
import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

# Local imports
from kagami.core.coordination.meta_orchestrator import (
    MetaOrchestrator,
)

logger = logging.getLogger(__name__)

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class SwarmSignal:
    """Signal for pheromone-based coordination.

    Represents a shared signal that instances can read and modify.
    Signals decay over time (pheromone evaporation).
    """

    signal_id: str
    value: Any
    strength: float = 1.0  # 0-1, decays over time
    source_instance: str | None = None
    created_at: float = field(default_factory=time.time)
    decay_rate: float = 0.95  # Per-hour decay

    def apply_decay(self) -> None:
        """Apply time-based decay to signal strength."""
        age_hours = (time.time() - self.created_at) / 3600.0
        self.strength *= self.decay_rate**age_hours


@dataclass
class Vote:
    """Vote in consensus voting."""

    instance_id: str
    choice: str
    confidence: float  # 0-1
    timestamp: float = field(default_factory=time.time)


@dataclass
class Bid:
    """Bid in task auction."""

    instance_id: str
    task_id: str
    price: float  # Lower is better (cost/effort estimate)
    capability_score: float  # How well instance matches task (0-1)
    timestamp: float = field(default_factory=time.time)

    @property
    def combined_score(self) -> float:
        """Combined score (higher is better)."""
        # High capability + low price = good bid
        return self.capability_score / (self.price + 0.01)


@dataclass
class SwarmSearchResult:
    """Result from parallel swarm search."""

    instance_id: str
    query: str
    result: Any
    confidence: float
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# SCATTER-GATHER PATTERN
# =============================================================================


class ScatterGather:
    """Scatter-Gather coordination pattern.

    Distributes work across multiple instances and gathers results.
    Supports configurable aggregation strategies.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator,
        aggregator: Callable[[list[dict[str, Any]]], Any] | None = None,
    ):
        """Initialize scatter-gather coordinator.

        Args:
            orchestrator: MetaOrchestrator instance
            aggregator: Function to aggregate results (default: list[Any])
        """
        self.orchestrator = orchestrator
        self.aggregator = aggregator or (lambda results: results)

    async def execute(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        instance_ids: list[str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute task across instances and gather results.

        Args:
            task: Task to execute
            params: Task parameters
            instance_ids: Specific instances to use (default: all)
            timeout: Timeout in seconds

        Returns:
            Aggregated results
        """
        params = params or {}
        instance_ids = instance_ids or self.orchestrator.list_instances()

        if not instance_ids:
            return {"success": False, "error": "No instances available"}

        # Scatter: execute on all instances in parallel
        async def execute_on_instance(instance_id: str) -> dict[str, Any]:
            instance = self.orchestrator.get_instance(instance_id)
            if not instance:
                return {"success": False, "error": f"Instance {instance_id} not found"}
            try:
                result = await instance.execute(task, params)
                return {"instance_id": instance_id, **result}
            except Exception as e:
                return {"instance_id": instance_id, "success": False, "error": str(e)}

        # Execute with timeout
        tasks = [execute_on_instance(iid) for iid in instance_ids]
        if timeout:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        else:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        clean_results = []
        for r in results:
            if isinstance(r, BaseException):
                clean_results.append({"success": False, "error": str(r)})
            else:
                clean_results.append(r)

        # Gather: aggregate results
        aggregated = self.aggregator(clean_results)

        return {
            "success": any(r.get("success", False) for r in clean_results),
            "results": clean_results,
            "aggregated": aggregated,
            "instances_used": instance_ids,
        }


# =============================================================================
# CONSENSUS VOTING PATTERN
# =============================================================================


class ConsensusVoting:
    """Consensus voting coordination pattern.

    Multiple instances vote on a decision. Supports various voting strategies.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator,
        quorum_threshold: float = 0.67,  # 2/3 majority
        confidence_weight: bool = True,  # Weight votes by confidence
    ):
        """Initialize consensus voting.

        Args:
            orchestrator: MetaOrchestrator instance
            quorum_threshold: Minimum agreement for consensus (0-1)
            confidence_weight: Weight votes by voter confidence
        """
        self.orchestrator = orchestrator
        self.quorum_threshold = quorum_threshold
        self.confidence_weight = confidence_weight

    async def vote(
        self,
        question: str,
        options: list[str],
        context: dict[str, Any] | None = None,
        instance_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Collect votes from instances.

        Args:
            question: Question to vote on
            options: Available options
            context: Additional context
            instance_ids: Specific instances to poll (default: all)

        Returns:
            Voting result with winner and agreement level
        """
        instance_ids = instance_ids or self.orchestrator.list_instances()
        votes: list[Vote] = []

        async def collect_vote(instance_id: str) -> Vote | None:
            instance = self.orchestrator.get_instance(instance_id)
            if not instance:
                return None

            try:
                result = await instance.execute(
                    task="vote",
                    params={
                        "question": question,
                        "options": options,
                    },
                    context=context,
                )
                if result.get("success"):
                    choice = result.get("result", {}).get("choice", options[0])
                    confidence = result.get("result", {}).get("confidence", 0.5)
                    return Vote(
                        instance_id=instance_id,
                        choice=choice if choice in options else options[0],
                        confidence=confidence,
                    )
            except Exception as e:
                logger.debug(f"Vote collection failed for {instance_id}: {e}")
            return None

        # Collect votes
        vote_tasks = [collect_vote(iid) for iid in instance_ids]
        vote_results = await asyncio.gather(*vote_tasks)
        votes = [v for v in vote_results if v is not None]

        if not votes:
            return {"success": False, "error": "No votes collected"}

        # Tally votes
        tallies: dict[str, float] = defaultdict(float)
        for vote in votes:
            weight = vote.confidence if self.confidence_weight else 1.0
            tallies[vote.choice] += weight

        total_weight = sum(tallies.values())
        if total_weight == 0:
            return {"success": False, "error": "No valid votes"}

        # Normalize
        for choice in tallies:
            tallies[choice] /= total_weight

        # Find winner
        winner = max(tallies.items(), key=lambda x: x[1])
        winner_choice, winner_share = winner

        # Check quorum
        reached_quorum = winner_share >= self.quorum_threshold

        return {
            "success": True,
            "winner": winner_choice,
            "agreement": winner_share,
            "quorum_reached": reached_quorum,
            "tallies": dict(tallies),
            "total_votes": len(votes),
            "voters": [v.instance_id for v in votes],
        }


# =============================================================================
# LEADER-FOLLOWER PATTERN
# =============================================================================


class LeaderFollower:
    """Leader-Follower coordination pattern.

    One instance leads (makes decisions), others follow (execute).
    Leader election based on health/capability.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator,
    ):
        """Initialize leader-follower coordinator.

        Args:
            orchestrator: MetaOrchestrator instance
        """
        self.orchestrator = orchestrator
        self._current_leader: str | None = None

    async def elect_leader(
        self,
        candidates: list[str] | None = None,
    ) -> str | None:
        """Elect a leader from available instances.

        Uses health and capability scores for election.

        Args:
            candidates: Candidate instance IDs (default: all)

        Returns:
            Elected leader instance ID
        """
        candidates = candidates or self.orchestrator.list_instances()

        if not candidates:
            return None

        scores: list[tuple[str, float]] = []
        for instance_id in candidates:
            instance = self.orchestrator.get_instance(instance_id)
            if not instance:
                continue

            health = instance.get_health()
            h_x = health.get("h_x", 0.5)
            load = health.get("load", 0.5)

            # Score: high safety, low load
            score = h_x * (1 - load)
            scores.append((instance_id, score))

        if not scores:
            return None

        # Elect highest scorer
        scores.sort(key=lambda x: x[1], reverse=True)
        self._current_leader = scores[0][0]

        logger.info(f"🏆 Elected leader: {self._current_leader} (score={scores[0][1]:.3f})")
        return self._current_leader

    @property
    def leader(self) -> str | None:
        """Current leader instance ID."""
        return self._current_leader

    async def lead(
        self,
        task: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute task via leader.

        Args:
            task: Task description
            params: Task parameters

        Returns:
            Execution result from leader
        """
        if not self._current_leader:
            await self.elect_leader()

        if not self._current_leader:
            return {"success": False, "error": "No leader available"}

        instance = self.orchestrator.get_instance(self._current_leader)
        if not instance:
            # Leader unavailable, re-elect
            await self.elect_leader()
            instance = self.orchestrator.get_instance(self._current_leader or "")

        if not instance:
            return {"success": False, "error": "Leader unavailable"}

        return await instance.execute(task, params or {})

    async def follow(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        followers: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute task on followers (all non-leader instances).

        Args:
            task: Task description
            params: Task parameters
            followers: Specific followers (default: all non-leaders)

        Returns:
            Results from all followers
        """
        all_instances = self.orchestrator.list_instances()
        followers = followers or [i for i in all_instances if i != self._current_leader]

        results = []
        for instance_id in followers:
            instance = self.orchestrator.get_instance(instance_id)
            if instance:
                try:
                    result = await instance.execute(task, params or {})
                    results.append({"instance_id": instance_id, **result})
                except Exception as e:
                    results.append({"instance_id": instance_id, "success": False, "error": str(e)})

        return results


# =============================================================================
# TASK AUCTION PATTERN
# =============================================================================


class TaskAuction:
    """Task auction coordination pattern.

    Instances bid for tasks based on capabilities and current load.
    Winner executes the task.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator,
    ):
        """Initialize task auction.

        Args:
            orchestrator: MetaOrchestrator instance
        """
        self.orchestrator = orchestrator

    async def auction(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        required_capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run auction for a task.

        Args:
            task: Task description
            params: Task parameters
            required_capabilities: Required capabilities

        Returns:
            Auction result with winner and execution result
        """
        instance_ids = self.orchestrator.list_instances()
        bids: list[Bid] = []

        required_capabilities = required_capabilities or []

        # Collect bids
        for instance_id in instance_ids:
            instance = self.orchestrator.get_instance(instance_id)
            if not instance:
                continue

            # Check capabilities
            capabilities = instance.get_capabilities()
            capability_match = 0.0
            if required_capabilities:
                matching = sum(1 for c in required_capabilities if c in capabilities)
                capability_match = matching / len(required_capabilities)
            else:
                capability_match = 1.0

            # Get load as price (higher load = higher price)
            health = instance.get_health()
            load = health.get("load", 0.5)
            h_x = health.get("h_x", 1.0)

            # Don't accept bids from unsafe instances
            if h_x < 0.1:
                continue

            bid = Bid(
                instance_id=instance_id,
                task_id=task,
                price=load,  # Load as price
                capability_score=capability_match * h_x,
            )
            bids.append(bid)

        if not bids:
            return {"success": False, "error": "No valid bids"}

        # Sort by combined score (highest wins)
        bids.sort(key=lambda b: b.combined_score, reverse=True)
        winner = bids[0]

        logger.info(
            f"🏆 Auction winner: {winner.instance_id} "
            f"(score={winner.combined_score:.3f}, price={winner.price:.3f})"
        )

        # Execute on winner
        instance = self.orchestrator.get_instance(winner.instance_id)
        if not instance:
            return {"success": False, "error": "Winner unavailable"}

        result = await instance.execute(task, params or {})

        return {
            "success": result.get("success", False),
            "winner": winner.instance_id,
            "bid_score": winner.combined_score,
            "result": result,
            "total_bids": len(bids),
        }


# =============================================================================
# PHEROMONE COORDINATION
# =============================================================================


class PheromoneCoordinator:
    """Pheromone-based stigmergic coordination.

    Instances communicate via shared signals (pheromones).
    Signals decay over time, stronger signals indicate successful paths.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator,
        decay_rate: float = 0.95,
    ):
        """Initialize pheromone coordinator.

        Args:
            orchestrator: MetaOrchestrator instance
            decay_rate: Signal decay rate per hour
        """
        self.orchestrator = orchestrator
        self.decay_rate = decay_rate
        self._signals: dict[str, SwarmSignal] = {}
        self._last_decay = time.time()

    def deposit(
        self,
        signal_id: str,
        value: Any,
        strength: float = 1.0,
        source_instance: str | None = None,
    ) -> SwarmSignal:
        """Deposit a pheromone signal.

        Args:
            signal_id: Signal identifier
            value: Signal value
            strength: Signal strength (0-1)
            source_instance: Instance that deposited the signal

        Returns:
            Created signal
        """
        signal = SwarmSignal(
            signal_id=signal_id,
            value=value,
            strength=min(1.0, strength),
            source_instance=source_instance,
            decay_rate=self.decay_rate,
        )
        self._signals[signal_id] = signal
        return signal

    def reinforce(
        self,
        signal_id: str,
        boost: float = 0.1,
    ) -> SwarmSignal | None:
        """Reinforce an existing signal (increase strength).

        Args:
            signal_id: Signal to reinforce
            boost: Strength boost

        Returns:
            Updated signal or None if not found
        """
        signal = self._signals.get(signal_id)
        if signal:
            signal.strength = min(1.0, signal.strength + boost)
        return signal

    def read(
        self,
        signal_id: str,
    ) -> SwarmSignal | None:
        """Read a pheromone signal.

        Args:
            signal_id: Signal to read

        Returns:
            Signal or None if not found
        """
        self._apply_decay()
        return self._signals.get(signal_id)

    def read_all(
        self,
        min_strength: float = 0.1,
    ) -> list[SwarmSignal]:
        """Read all active signals above threshold.

        Args:
            min_strength: Minimum strength threshold

        Returns:
            List of active signals
        """
        self._apply_decay()
        return [s for s in self._signals.values() if s.strength >= min_strength]

    def get_strongest(
        self,
        prefix: str | None = None,
    ) -> SwarmSignal | None:
        """Get strongest signal, optionally filtered by prefix.

        Args:
            prefix: Signal ID prefix to filter by

        Returns:
            Strongest signal or None
        """
        self._apply_decay()
        candidates = list(self._signals.values())
        if prefix:
            candidates = [s for s in candidates if s.signal_id.startswith(prefix)]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.strength)

    def _apply_decay(self) -> None:
        """Apply decay to all signals."""
        now = time.time()
        if now - self._last_decay < 60:  # Decay every minute
            return

        to_remove = []
        for signal_id, signal in self._signals.items():
            signal.apply_decay()
            if signal.strength < 0.01:
                to_remove.append(signal_id)

        for signal_id in to_remove:
            del self._signals[signal_id]

        self._last_decay = now


# =============================================================================
# SWARM SEARCH
# =============================================================================


class SwarmSearch:
    """Parallel swarm search coordination.

    Multiple instances search in parallel, sharing results.
    Best results propagate via pheromone signals.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator,
        pheromone: PheromoneCoordinator | None = None,
    ):
        """Initialize swarm search.

        Args:
            orchestrator: MetaOrchestrator instance
            pheromone: Pheromone coordinator for result sharing
        """
        self.orchestrator = orchestrator
        self.pheromone = pheromone or PheromoneCoordinator(orchestrator)

    async def search(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        instance_ids: list[str] | None = None,
        top_k: int = 3,
    ) -> list[SwarmSearchResult]:
        """Execute parallel search across instances.

        Args:
            query: Search query
            params: Search parameters
            instance_ids: Instances to search with (default: all)
            top_k: Number of top results to return

        Returns:
            Top-k search results sorted by confidence
        """
        instance_ids = instance_ids or self.orchestrator.list_instances()
        results: list[SwarmSearchResult] = []

        async def search_instance(instance_id: str) -> SwarmSearchResult | None:
            instance = self.orchestrator.get_instance(instance_id)
            if not instance:
                return None

            try:
                result = await instance.execute(
                    task="search",
                    params={"query": query, **(params or {})},
                )
                if result.get("success"):
                    return SwarmSearchResult(
                        instance_id=instance_id,
                        query=query,
                        result=result.get("result"),
                        confidence=result.get("result", {}).get("confidence", 0.5),
                    )
            except Exception as e:
                logger.debug(f"Search failed on {instance_id}: {e}")
            return None

        # Parallel search
        search_tasks = [search_instance(iid) for iid in instance_ids]
        search_results = await asyncio.gather(*search_tasks)
        results = [r for r in search_results if r is not None]

        # Sort by confidence
        results.sort(key=lambda r: r.confidence, reverse=True)

        # Deposit pheromones for top results
        for i, result in enumerate(results[:top_k]):
            signal_id = f"search:{query}:{i}"
            self.pheromone.deposit(
                signal_id=signal_id,
                value=result.result,
                strength=result.confidence,
                source_instance=result.instance_id,
            )

        return results[:top_k]


# =============================================================================
# SWARM COORDINATOR (COMBINES ALL PATTERNS)
# =============================================================================


class SwarmCoordinator:
    """Unified swarm coordinator providing access to all patterns.

    This is the main entry point for swarm coordination primitives.
    """

    def __init__(
        self,
        orchestrator: MetaOrchestrator | None = None,
    ):
        """Initialize swarm coordinator.

        Args:
            orchestrator: MetaOrchestrator instance (default: global)
        """
        from .meta_orchestrator import get_meta_orchestrator

        self.orchestrator = orchestrator or get_meta_orchestrator()

        # Initialize patterns
        self.scatter_gather = ScatterGather(self.orchestrator)
        self.consensus = ConsensusVoting(self.orchestrator)
        self.leader_follower = LeaderFollower(self.orchestrator)
        self.auction = TaskAuction(self.orchestrator)
        self.pheromone = PheromoneCoordinator(self.orchestrator)
        self.search = SwarmSearch(self.orchestrator, self.pheromone)

    async def scatter(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Scatter-gather execution."""
        return await self.scatter_gather.execute(task, params, **kwargs)

    async def vote(
        self,
        question: str,
        options: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Consensus voting."""
        return await self.consensus.vote(question, options, **kwargs)

    async def elect_leader(self, **kwargs: Any) -> str | None:
        """Elect leader."""
        return await self.leader_follower.elect_leader(**kwargs)

    async def auction_task(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Task auction."""
        return await self.auction.auction(task, params, **kwargs)

    async def parallel_search(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[SwarmSearchResult]:
        """Parallel swarm search."""
        return await self.search.search(query, params, **kwargs)


# =============================================================================
# FACTORY
# =============================================================================

_swarm_coordinator: SwarmCoordinator | None = None


def get_swarm_coordinator() -> SwarmCoordinator:
    """Get global swarm coordinator instance."""
    global _swarm_coordinator
    if _swarm_coordinator is None:
        _swarm_coordinator = SwarmCoordinator()
    return _swarm_coordinator


def create_swarm_coordinator(
    orchestrator: MetaOrchestrator | None = None,
) -> SwarmCoordinator:
    """Create a new swarm coordinator."""
    return SwarmCoordinator(orchestrator)


def reset_swarm_coordinator() -> None:
    """Reset global swarm coordinator (for testing)."""
    global _swarm_coordinator
    _swarm_coordinator = None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "Bid",
    "ConsensusVoting",
    "LeaderFollower",
    "PheromoneCoordinator",
    "ScatterGather",
    "SwarmCoordinator",
    "SwarmSearch",
    "SwarmSearchResult",
    "SwarmSignal",
    "TaskAuction",
    "Vote",
    "create_swarm_coordinator",
    "get_swarm_coordinator",
    "reset_swarm_coordinator",
]
