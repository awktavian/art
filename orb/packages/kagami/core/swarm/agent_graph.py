"""Agent Social Graph - Track Who Works Well Together.

Like bee colonies where successful forager teams form naturally,
this tracks which agents collaborate successfully and forms neighborhoods.

Bio-Inspiration:
- Bees: Successful forager pairs work together again
- Ants: Task groups form based on local interaction success
- Result: Self-organizing teams with high synergy

Usage:
    graph = get_agent_graph()

    # Record collaboration
    await graph.record_collaboration(
        agent1="sage",
        agent2="optimizer",
        outcome_quality=0.9  # High quality result
    )

    # Get good collaborators
    neighbors = graph.get_neighbors("sage", threshold=0.7)

    # Assemble optimal team
    team = graph.find_team(["optimization", "learning"], max_size=3)
"""

import logging
from typing import Any, cast

logger = logging.getLogger(__name__)


class AgentGraph:
    """Network of agent relationships - who works well with whom.

    STAIR 4: Track protocol stability (emergent communication patterns).
    """

    def __init__(self) -> None:
        # (agent1, agent2) -> synergy score (0.0-1.0)
        self._edges: dict[tuple[str, str], float] = {}

        # (agent1, agent2) -> collaboration count
        self._collaboration_counts: dict[tuple[str, str], int] = {}

        # agent -> set[Any] of capabilities
        self._capabilities: dict[str, set[str]] = {}

        # Exponential moving average alpha
        self._alpha = 0.3

        # STAIR 4: Protocol stability tracking
        # (agent1, agent2) -> list[Any] of recent outcomes (for variance calculation)
        self._recent_outcomes: dict[tuple[str, str], list[float]] = {}
        self._protocol_stability: dict[tuple[str, str], float] = {}  # 0-1, higher = more stable

    async def record_collaboration(
        self,
        agent1: str,
        agent2: str,
        outcome_quality: float,
        task_type: str | None = None,
    ) -> None:
        """Record collaboration outcome.

        Args:
            agent1: First agent name
            agent2: Second agent name
            outcome_quality: Quality of collaboration result (0.0-1.0)
            task_type: Optional task type for capability tracking
        """
        # Normalize edge (always sorted order)
        edge = cast(tuple[str, str], tuple(sorted([agent1, agent2])))

        # Get current synergy
        current = self._edges.get(edge, 0.5)  # Default neutral

        # Update with EMA
        updated = self._alpha * outcome_quality + (1 - self._alpha) * current
        self._edges[edge] = updated

        # Track count
        self._collaboration_counts[edge] = self._collaboration_counts.get(edge, 0) + 1

        # Update capabilities if task provided
        if task_type:
            self._capabilities.setdefault(agent1, set()).add(task_type)
            self._capabilities.setdefault(agent2, set()).add(task_type)

        # STAIR 4: Track protocol stability (emergent communication patterns)
        # Keep sliding window of last 10 outcomes
        if edge not in self._recent_outcomes:
            self._recent_outcomes[edge] = []
        self._recent_outcomes[edge].append(outcome_quality)
        if len(self._recent_outcomes[edge]) > 10:
            self._recent_outcomes[edge] = self._recent_outcomes[edge][-10:]

        # Compute stability: low variance = stable protocol
        if len(self._recent_outcomes[edge]) >= 3:
            import statistics

            try:
                variance = statistics.variance(self._recent_outcomes[edge])
                # Stability = 1 - variance (scaled to 0-1)
                # Low variance → high stability → emergent protocol
                stability = max(0.0, 1.0 - (variance * 4.0))  # Scale to 0-1
                self._protocol_stability[edge] = stability

                # HIGH STABILITY = EMERGENT PROTOCOL
                if stability > 0.7 and self._collaboration_counts[edge] >= 5:
                    logger.info(
                        f"✨ EMERGENT PROTOCOL: {agent1} ↔ {agent2} stability={stability:.2f} "
                        f"(consistent outcomes over {self._collaboration_counts[edge]} collaborations)"
                    )

                    # Track emergent protocol metric
                    try:
                        from kagami_observability.metrics import get_counter

                        counter = get_counter(
                            "kagami_emergent_protocols_total",
                            "Total emergent collaboration protocols detected",
                        )
                        counter.labels(agent1=edge[0], agent2=edge[1]).inc()
                    except Exception:
                        pass

            except Exception:
                pass

        # Emit metric

        logger.info(
            f"🤝 Collaboration: {agent1} + {agent2} = {updated:.2f} synergy "
            f"({self._collaboration_counts[edge]} times)"
        )

    def get_neighbors(self, agent: str, threshold: float = 0.7) -> list[str]:
        """Get agents with strong connection to this agent.

        Args:
            agent: Agent name
            threshold: Minimum synergy threshold

        Returns:
            List of neighbor agent names
        """
        neighbors: list[Any] = []

        for (a1, a2), synergy in self._edges.items():
            if synergy >= threshold:
                if a1 == agent:
                    neighbors.append(a2)
                elif a2 == agent:
                    neighbors.append(a1)

        logger.debug(f"🕸️  {agent} has {len(neighbors)} neighbors (threshold={threshold})")
        return neighbors

    def find_team(
        self,
        required_skills: list[str],
        max_size: int = 3,
        optimize_for: str = "synergy",
    ) -> list[str]:
        """Assemble team with required skills and good synergy.

        Like bee swarms: agents with high synergy work together better.

        Args:
            required_skills: List of required capabilities
            max_size: Maximum team size
            optimize_for: "synergy" | "coverage" | "balanced"

        Returns:
            List of agent names forming optimal team
        """
        # Find agents with required skills
        candidates = set()
        for skill in required_skills:
            for agent, caps in self._capabilities.items():
                if skill in caps:
                    candidates.add(agent)

        if not candidates:
            logger.warning(f"No agents found with skills: {required_skills}")
            return []

        if len(candidates) <= max_size:
            return list(candidates)

        # Optimize team composition
        if optimize_for == "synergy":
            team = self._find_max_synergy_team(candidates, max_size)
        elif optimize_for == "coverage":
            team = self._find_max_coverage_team(candidates, required_skills, max_size)
        else:  # balanced
            team = self._find_balanced_team(candidates, required_skills, max_size)

        logger.info(f"🏆 Assembled team: {team} for skills {required_skills}")
        return team

    def _find_max_synergy_team(self, candidates: set[str], max_size: int) -> list[str]:
        """Find team subset with maximum total synergy."""
        candidates_list = list(candidates)

        if len(candidates_list) <= max_size:
            return candidates_list

        # Greedy: Start with highest-synergy pair, add best collaborators
        best_team: list[Any] = []

        # Find best initial pair
        best_pair = None
        best_synergy = 0.0

        for i, a1 in enumerate(candidates_list):
            for a2 in candidates_list[i + 1 :]:
                edge = tuple(sorted([a1, a2]))
                synergy = self._edges.get(edge, 0.5)  # type: ignore[arg-type]
                if synergy > best_synergy:
                    best_synergy = synergy
                    best_pair = [a1, a2]

        if best_pair:
            best_team = best_pair
        else:
            # No collaborations yet - pick first two
            best_team = candidates_list[:2]

        # Add remaining agents with best synergy to team
        remaining = [a for a in candidates_list if a not in best_team]

        while len(best_team) < max_size and remaining:
            # Find agent with best average synergy to current team
            best_candidate = None
            best_avg_synergy = 0.0

            for candidate in remaining:
                # Compute average synergy with team
                synergies: list[Any] = []
                for team_member in best_team:
                    edge = tuple(sorted([candidate, team_member]))
                    synergy = self._edges.get(edge, 0.5)  # type: ignore[arg-type]
                    synergies.append(synergy)

                avg_synergy = sum(synergies) / len(synergies) if synergies else 0.5

                if avg_synergy > best_avg_synergy:
                    best_avg_synergy = avg_synergy
                    best_candidate = candidate

            if best_candidate:
                best_team.append(best_candidate)
                remaining.remove(best_candidate)
            else:
                break

        return best_team

    def _find_max_coverage_team(
        self, candidates: set[str], required_skills: list[str], max_size: int
    ) -> list[str]:
        """Find team that covers all required skills."""
        team: list[Any] = []
        covered_skills = set()  # type: ignore  # Var

        # Greedy: Add agents that cover most uncovered skills
        remaining = list(candidates)

        while len(team) < max_size and len(covered_skills) < len(required_skills):
            best_agent = None
            best_new_coverage = 0

            for agent in remaining:
                caps = self._capabilities.get(agent, set())
                new_coverage = len(set(required_skills) & caps - covered_skills)

                if new_coverage > best_new_coverage:
                    best_new_coverage = new_coverage
                    best_agent = agent

            if best_agent:
                team.append(best_agent)
                remaining.remove(best_agent)
                covered_skills.update(
                    self._capabilities.get(best_agent, set()) & set(required_skills)
                )
            else:
                break

        return team

    def _find_balanced_team(
        self, candidates: set[str], required_skills: list[str], max_size: int
    ) -> list[str]:
        """Find team balancing synergy and coverage."""
        # Start with coverage
        team = self._find_max_coverage_team(candidates, required_skills, max_size)

        # If room left, add high-synergy agents
        if len(team) < max_size:
            remaining = [a for a in candidates if a not in team]
            synergy_team = self._find_max_synergy_team(set(remaining), max_size - len(team))
            team.extend(synergy_team)

        return team

    def get_cluster_coefficient(self) -> float:
        """Measure agent network clustering (small-world indicator).

        Returns:
            Cluster coefficient 0.0-1.0 (>0.3 = good local neighborhoods)
        """
        if len(self._edges) < 3:
            return 0.0

        # Get all agents
        agents = set()
        for a1, a2 in self._edges.keys():
            agents.add(a1)
            agents.add(a2)

        if len(agents) < 3:
            return 0.0

        # Count triangles (agent triads with all edges)
        triangles = 0
        connected_triples = 0

        agents_list = list(agents)
        for i, a1 in enumerate(agents_list):
            for j, a2 in enumerate(agents_list[i + 1 :], start=i + 1):
                for _k, a3 in enumerate(agents_list[j + 1 :], start=j + 1):
                    # Check if this is a connected triple
                    edge12 = tuple(sorted([a1, a2])) in self._edges
                    edge13 = tuple(sorted([a1, a3])) in self._edges
                    edge23 = tuple(sorted([a2, a3])) in self._edges

                    if edge12 or edge13 or edge23:
                        connected_triples += 1

                        if edge12 and edge13 and edge23:
                            triangles += 1

        if connected_triples == 0:
            return 0.0

        cluster_coef = (3 * triangles) / connected_triples
        return min(1.0, cluster_coef)

    def get_stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        agents = set()
        for a1, a2 in self._edges.keys():
            agents.add(a1)
            agents.add(a2)

        return {
            "agents": len(agents),
            "edges": len(self._edges),
            "avg_synergy": (sum(self._edges.values()) / len(self._edges) if self._edges else 0.0),
            "cluster_coefficient": self.get_cluster_coefficient(),
            "total_collaborations": sum(self._collaboration_counts.values()),
        }


# Singleton
_AGENT_GRAPH: AgentGraph | None = None


def get_agent_graph() -> AgentGraph:
    """Get singleton agent social graph."""
    global _AGENT_GRAPH
    if _AGENT_GRAPH is None:
        _AGENT_GRAPH = AgentGraph()
    return _AGENT_GRAPH


__all__ = ["AgentGraph", "get_agent_graph"]
