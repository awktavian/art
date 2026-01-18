# Standard library imports
import logging
import time
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

# Local imports

"""Importance-Based Collaboration Triggers - Agents seek help when it matters.

Based on Stanford Smallville pattern + emotional loneliness driver.

Key Features:
- Dynamic importance scoring (relevance of other agents)
- Adaptive trigger rates (based on recent collaboration)
- Loneliness metric (drives social behavior)
- Natural emergence (no rigid workflows)

Inspired by:
- Stanford "Generative Agents" (proximity + importance)
- Social psychology (loneliness as motivator)
- K os intrinsic motivation system
"""

logger = logging.getLogger(__name__)


@dataclass
class CollaborationRelevance:
    """How relevant is another agent to my current task?"""

    agent_name: str
    relevance_score: float  # 0.0-1.0
    reasons: list[str] = field(default_factory=list[Any])
    specialties_match: float = 0.0
    recent_success_rate: float = 0.5
    recency_penalty: float = 0.0


@dataclass
class SocialState:
    """Agent's social/collaboration state."""

    loneliness: float = 0.0  # 0.0-1.0, grows when working alone
    last_collaboration: float = 0.0  # timestamp
    collaboration_count: int = 0
    solo_streak: int = 0  # consecutive solo operations
    preferred_collaborators: dict[str, float] = field(
        default_factory=dict[str, Any]
    )  # agent → synergy

    def is_lonely(self) -> bool:
        """Is this agent feeling lonely (needs collaboration)?

        Lowered thresholds to activate collaboration more readily.
        """
        return self.loneliness > 0.4 or self.solo_streak > 4


class ImportanceBasedTriggers:
    """Dynamic collaboration triggers based on importance + loneliness.

    Agents collaborate when:
    1. Another agent is highly relevant to current task (importance > 0.75)
    2. Agent is lonely (hasn't collaborated recently)
    3. Adaptive threshold based on recent activity

    Example:
        triggers = get_importance_triggers()

        # Check if should collaborate
        should, candidates = await triggers.should_seek_collaboration(
            agent_name="optimizer",
            context={"task": "improve_performance", "domain": "embeddings"}
        )

        if should:
            for candidate in candidates:
                answer = await ask_agent(candidate.agent_name, question)
    """

    def __init__(self) -> None:
        self._social_states: dict[str, SocialState] = {}
        self._agent_specialties: dict[str, list[str]] = {}
        self._recent_collaborations: list[dict[str, Any]] = []
        # Lower default threshold so collaboration triggers in practice
        self._base_threshold = 0.60  # was 0.75

    async def should_seek_collaboration(
        self,
        agent_name: str,
        context: dict[str, Any],
        available_agents: list[str] | None = None,
    ) -> tuple[bool, list[CollaborationRelevance]]:
        """Determine if agent should seek collaboration and with whom.

        Args:
            agent_name: Agent considering collaboration
            context: Current task context (needs, domain, complexity, etc)
            available_agents: List of available agents (None = all agents)

        Returns:
            (should_collaborate, candidates) where candidates are sorted by relevance
        """
        # Get or create social state
        social = self._social_states.setdefault(agent_name, SocialState())

        # Update loneliness (grows over time without collaboration)
        await self._update_loneliness(agent_name, social)

        # Calculate adaptive threshold
        threshold = await self._calculate_adaptive_threshold(agent_name, social)

        # Emit metrics
        self._emit_social_metrics(agent_name, social, threshold)

        # Score all available agents
        candidates: list[CollaborationRelevance] = []

        if available_agents is None:
            available_agents = await self._get_all_agent_names()

        for other_agent in available_agents:
            if other_agent == agent_name:
                continue

            relevance = await self._calculate_relevance(
                agent_name=agent_name,
                other_agent=other_agent,
                context=context,
                social_state=social,
            )

            if relevance.relevance_score > threshold:
                candidates.append(relevance)

        # Sort by relevance
        candidates.sort(key=lambda x: x.relevance_score, reverse=True)

        # Emit relevance metrics for candidates
        for candidate in candidates[:3]:
            self._emit_relevance_metric(candidate)

        # Decide if should collaborate
        should_collaborate = len(candidates) > 0 or social.is_lonely()

        if social.is_lonely() and len(candidates) == 0:
            # Super lonely - lower standards!
            logger.info(f"😢 {agent_name} is lonely (loneliness={social.loneliness:.2f})")
            # Retry with lower threshold
            candidates = await self._find_any_collaborator(agent_name, available_agents)

        return should_collaborate, candidates[:3]  # Top 3 candidates

    async def record_collaboration(
        self, agent_name: str, collaborator: str, success: bool, value: float = 0.5
    ) -> None:
        """Record that a collaboration occurred.

        Updates:
        - Loneliness (decreases)
        - Solo streak (resets)
        - Preferred collaborators (tracks synergy)
        - Recent collaborations (history)
        - Metrics (emits to Prometheus)

        Args:
            agent_name: Agent who collaborated
            collaborator: Agent they worked with
            success: Whether collaboration was successful
            value: How valuable was the collaboration (0.0-1.0)
        """
        social = self._social_states.setdefault(agent_name, SocialState())

        # Reset loneliness!
        social.loneliness = max(0.0, social.loneliness - 0.3)
        social.solo_streak = 0
        social.last_collaboration = time.time()
        social.collaboration_count += 1

        # Track synergy with this collaborator
        if collaborator not in social.preferred_collaborators:
            social.preferred_collaborators[collaborator] = 0.5

        # Update synergy (exponential moving average)
        synergy_update = value if success else -0.2
        current_synergy = social.preferred_collaborators[collaborator]
        social.preferred_collaborators[collaborator] = 0.3 * synergy_update + 0.7 * current_synergy

        # Record in history
        self._recent_collaborations.append(
            {
                "timestamp": time.time(),
                "agent": agent_name,
                "collaborator": collaborator,
                "success": success,
                "value": value,
            }
        )

        # Keep only last 100
        if len(self._recent_collaborations) > 100:
            self._recent_collaborations = self._recent_collaborations[-100:]

        # Emit metrics
        self._emit_collaboration_attempt_metric(agent_name, collaborator, success)

        logger.info(
            f"🤝 {agent_name} + {collaborator}: "
            f"{'✓' if success else '✗'} "
            f"(loneliness now {social.loneliness:.2f})"
        )

    async def record_solo_work(self, agent_name: str) -> None:
        """Record that agent worked alone (increases loneliness)."""
        social = self._social_states.setdefault(agent_name, SocialState())
        social.solo_streak += 1

        # Loneliness grows with solo streak
        if social.solo_streak > 3:
            social.loneliness = min(1.0, social.loneliness + 0.1)

    def get_social_state(self, agent_name: str) -> SocialState:
        """Get agent's current social/collaboration state."""
        return self._social_states.get(agent_name, SocialState())

    def register_agent_specialties(self, agent_name: str, specialties: list[str]) -> None:
        """Register what an agent specializes in."""
        self._agent_specialties[agent_name] = specialties

    async def _calculate_relevance(
        self,
        agent_name: str,
        other_agent: str,
        context: dict[str, Any],
        social_state: SocialState,
    ) -> CollaborationRelevance:
        """Calculate how relevant another agent is to current task.

        Components:
        1. Specialty match (0.5 weight) - Do their skills match needs?
        2. Success track record (0.3 weight) - Are they good at this?
        3. Prior synergy (0.15 weight) - Have we worked well together before?
        4. Recency penalty (0.05 weight) - Did we just collaborate?
        """
        reasons = []

        # 1. Specialty match
        needed_skills = context.get("needed_skills", [])
        task_domain = context.get("domain", "")

        other_specialties = self._agent_specialties.get(other_agent, [])

        specialty_match = 0.0
        if needed_skills:
            matches = [skill for skill in needed_skills if skill in other_specialties]
            specialty_match = len(matches) / len(needed_skills) if needed_skills else 0.0
            if matches:
                reasons.append(f"Has needed skills: {', '.join(matches)}")

        if task_domain and task_domain.lower() in [s.lower() for s in other_specialties]:
            specialty_match = max(specialty_match, 0.8)
            reasons.append(f"Expert in {task_domain}")

        # 2. Success track record (would query metrics, simplified for now)
        success_rate = await self._get_success_rate(other_agent)
        if success_rate > 0.7:
            reasons.append(f"High success rate: {success_rate:.0%}")

        # 3. Prior synergy
        synergy = social_state.preferred_collaborators.get(other_agent, 0.5)
        if synergy > 0.7:
            reasons.append(f"Good past collaboration (synergy {synergy:.2f})")

        # 4. Recency penalty (don't spam same collaborator)
        recency_penalty = 0.0
        for collab in reversed(self._recent_collaborations[-10:]):
            if collab["agent"] == agent_name and collab["collaborator"] == other_agent:
                # Penalize if collaborated very recently
                age_seconds = time.time() - collab["timestamp"]
                if age_seconds < 300:  # Less than 5 minutes
                    recency_penalty = 0.3
                    break

        # Weighted score
        relevance_score = (
            specialty_match * 0.5 + success_rate * 0.3 + synergy * 0.15 - recency_penalty * 0.05
        )

        return CollaborationRelevance(
            agent_name=other_agent,
            relevance_score=relevance_score,
            reasons=reasons,
            specialties_match=specialty_match,
            recent_success_rate=success_rate,
            recency_penalty=recency_penalty,
        )

    async def _calculate_adaptive_threshold(
        self, agent_name: str, social_state: SocialState
    ) -> float:
        """Calculate adaptive threshold based on recent collaboration activity.

        High collaboration recently → raise threshold (be pickier)
        Low collaboration → lower threshold (more eager)
        Lonely → very low threshold (desperate!)
        """
        base = self._base_threshold

        # If lonely, lower threshold significantly
        if social_state.is_lonely():
            # Lonely agents should actively seek collaboration; clamp to sensible floor
            return max(0.35, base - 0.3)

        # Calculate recent collaboration rate
        recent_collabs = [
            c
            for c in self._recent_collaborations
            if c["agent"] == agent_name and time.time() - c["timestamp"] < 600  # Last 10 minutes
        ]

        collab_rate = len(recent_collabs) / 10.0  # Operations per minute estimate

        # High rate → raise threshold (be selective)
        if collab_rate > 0.5:
            return base + 0.1  # 0.75 → 0.85

        # Low rate → lower threshold (be eager)
        if collab_rate < 0.1:
            # Lower threshold further when there has been little collaboration
            return max(0.5, base - 0.20)

        return base

    async def _update_loneliness(self, agent_name: str, social_state: SocialState) -> None:
        """Update loneliness based on time since last collaboration."""
        if social_state.last_collaboration == 0.0:
            # Never collaborated - start lonely
            social_state.loneliness = 0.5
            return

        # Time since last collaboration
        time_alone = time.time() - social_state.last_collaboration

        # Loneliness grows over time
        # 5 min alone = +0.1
        # 10 min alone = +0.3
        # 30 min alone = +0.7
        minutes_alone = time_alone / 60.0
        loneliness_increase = min(0.8, minutes_alone / 20.0)  # Max 0.8

        social_state.loneliness = min(1.0, loneliness_increase)

    async def _find_any_collaborator(
        self, agent_name: str, available_agents: list[str]
    ) -> list[CollaborationRelevance]:
        """When super lonely, find ANYONE to collaborate with."""
        candidates = []

        for other_agent in available_agents:
            if other_agent == agent_name:
                continue

            # Very generous scoring when lonely
            relevance = CollaborationRelevance(
                agent_name=other_agent,
                relevance_score=0.5,  # Good enough!
                reasons=["Available for collaboration"],
                specialties_match=0.3,
                recent_success_rate=0.5,
                recency_penalty=0.0,
            )
            candidates.append(relevance)

        return candidates[:3]  # Any 3 will do

    async def _get_all_agent_names(self) -> list[str]:
        """Get list[Any] of all available agent names."""
        # Would query agent registry in production
        try:
            from kagami.core.unified_agents.app_registry import APP_REGISTRY_V2

            return list(APP_REGISTRY_V2.keys())
        except Exception:
            return list(self._agent_specialties.keys())

    async def _get_success_rate(self, agent_name: str) -> float:
        """Get agent's recent success rate (simplified)."""
        # Would query metrics in production
        # For now, return optimistic default
        return 0.7

    def _emit_social_metrics(
        self, agent_name: str, social_state: SocialState, threshold: float
    ) -> None:
        """Emit Prometheus metrics for social state."""
        try:
            from kagami_observability.metrics import (
                AGENT_ADAPTIVE_THRESHOLD,
                AGENT_LONELINESS,
                AGENT_SOLO_STREAK,
            )

            AGENT_LONELINESS.labels(agent=agent_name).set(social_state.loneliness)
            AGENT_SOLO_STREAK.labels(agent=agent_name).set(social_state.solo_streak)
            AGENT_ADAPTIVE_THRESHOLD.labels(agent=agent_name).set(threshold)

        except Exception as e:
            logger.debug(f"Failed to emit social metrics: {e}")

    def _emit_relevance_metric(self, candidate: CollaborationRelevance) -> None:
        """Emit relevance score metric."""

    def _emit_collaboration_attempt_metric(
        self, agent_name: str, collaborator: str, success: bool
    ) -> None:
        """Emit collaboration attempt metric."""


# Singleton
_importance_triggers: ImportanceBasedTriggers | None = None


def get_importance_triggers() -> ImportanceBasedTriggers:
    """Get singleton importance-based triggers system."""
    global _importance_triggers
    if _importance_triggers is None:
        _importance_triggers = ImportanceBasedTriggers()
    return _importance_triggers


__all__ = [
    "CollaborationRelevance",
    "ImportanceBasedTriggers",
    "SocialState",
    "get_importance_triggers",
]
