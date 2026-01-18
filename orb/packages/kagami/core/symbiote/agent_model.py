"""Agent Model — Predictive Models of Other Agents' Mental States.

This module implements Bayesian Theory of Mind: building and maintaining
predictive models of other agents' beliefs, goals, and intentions.

MATHEMATICAL FOUNDATION:
========================
An agent model M_a for agent a consists of:

    M_a = (B_a, G_a, I_a, K_a, A_a)

Where:
- B_a: Beliefs (probability distributions over world states)
- G_a: Goals (desired world states with utilities)
- I_a: Intents (current action plans)
- K_a: Knowledge (what the agent knows/doesn't know)
- A_a: Anticipated actions (predicted next moves)

The model is updated via Bayesian inference:

    P(M_a | O) ∝ P(O | M_a) P(M_a)

Where O is our observations of agent a's behavior.

INTEGRATION WITH E8 LATENT SPACE:
=================================
Agent models are embedded in the same E8 latent space as the world model,
enabling:
- Shared representation between self-model and other-agent models
- Efficient comparison via E8 lattice distance
- Natural composition via E8 algebra

References:
- Baker et al. (2017): "Rational Quantitative Attribution of Beliefs,
  Desires and Percepts in Human Mentalizing"
- Rabinowitz et al. (2018): "Machine Theory of Mind"

Created: December 21, 2025
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT TYPES
# =============================================================================


class AgentType(Enum):
    """Types of agents we model."""

    USER = "user"  # Human user interacting with system
    AI_ASSISTANT = "ai"  # Other AI assistants
    COLONY = "colony"  # Internal colony agents
    EXTERNAL = "external"  # External services/APIs
    UNKNOWN = "unknown"  # Unknown agent type


class ConfidenceLevel(Enum):
    """Confidence levels for beliefs/predictions."""

    CERTAIN = "certain"  # >0.95 confidence
    HIGH = "high"  # 0.8-0.95
    MEDIUM = "medium"  # 0.5-0.8
    LOW = "low"  # 0.2-0.5
    UNCERTAIN = "uncertain"  # <0.2


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================


@dataclass
class AgentKnowledge:
    """What we believe an agent knows/doesn't know.

    This represents the epistemic state of the modeled agent:
    - Known facts: What they definitely know
    - Unknown facts: What they don't know (knowledge gaps)
    - False beliefs: What they believe incorrectly
    - Shared context: Common ground with us
    """

    agent_id: str

    # Known facts (topic → certainty)
    known_topics: dict[str, float] = field(default_factory=dict[str, Any])

    # Knowledge gaps (topics they likely don't know)
    unknown_topics: list[str] = field(default_factory=list[Any])

    # Potential misconceptions (topic → correct_value)
    potential_misconceptions: dict[str, Any] = field(default_factory=dict[str, Any])

    # Shared context (common ground)
    shared_context: dict[str, Any] = field(default_factory=dict[str, Any])

    # Last updated
    updated_at: float = field(default_factory=time.time)

    def knowledge_overlap(self, topics: list[str]) -> float:
        """Compute overlap between agent's knowledge and given topics.

        Returns:
            Float [0, 1] indicating how much of topics the agent knows
        """
        if not topics:
            return 1.0

        known_count = sum(
            1 for t in topics if t in self.known_topics and self.known_topics[t] > 0.5
        )
        return known_count / len(topics)


@dataclass
class AgentIntent:
    """Inferred intent of an agent.

    Represents what we believe the agent is trying to accomplish,
    based on their observed behavior and context.
    """

    intent_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Core intent
    action: str = ""  # What they're trying to do
    target: str = ""  # What they're acting on
    purpose: str = ""  # Why they're doing it

    # Confidence
    confidence: float = 0.5
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM

    # Evidence
    evidence: list[str] = field(default_factory=list[Any])

    # Temporal
    detected_at: float = field(default_factory=time.time)
    expected_duration: float | None = None  # How long this intent may persist

    # Alternatives (other possible interpretations)
    alternatives: list[tuple[str, float]] = field(default_factory=list[Any])

    def is_ambiguous(self) -> bool:
        """Check if intent is ambiguous (multiple high-probability alternatives)."""
        if not self.alternatives:
            return self.confidence < 0.6

        # Ambiguous if top alternatives are close in probability
        if self.alternatives and self.alternatives[0][1] > 0.3:
            return True
        return False


@dataclass
class AgentBelief:
    """A specific belief we attribute to an agent.

    Beliefs are propositions the agent holds to be true,
    with associated confidence levels.
    """

    belief_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Content
    proposition: str = ""  # What the agent believes
    confidence: float = 0.5  # Our confidence they hold this belief

    # Source
    source: str = "inferred"  # "stated", "inferred", "assumed"
    evidence: list[str] = field(default_factory=list[Any])

    # Temporal
    acquired_at: float = field(default_factory=time.time)

    # Ground truth (if known)
    is_true: bool | None = None  # None = unknown

    @property
    def is_false_belief(self) -> bool:
        """Check if this is a false belief (agent believes something untrue)."""
        return self.is_true is False


@dataclass
class AgentState:
    """Current state of an agent model.

    Aggregates all our beliefs about an agent at a point in time.
    Can be encoded into E8 latent space for efficient storage/comparison.
    """

    agent_id: str
    agent_type: AgentType = AgentType.UNKNOWN

    # Mental state components
    beliefs: list[AgentBelief] = field(default_factory=list[Any])
    current_intent: AgentIntent | None = None
    knowledge: AgentKnowledge | None = None

    # Goals (inferred)
    goals: list[str] = field(default_factory=list[Any])
    goal_priorities: dict[str, float] = field(default_factory=dict[str, Any])

    # Emotional/affective state (optional)
    emotional_state: dict[str, float] = field(default_factory=dict[str, Any])

    # Interaction history
    last_action: str | None = None
    action_history: list[str] = field(default_factory=list[Any])
    interaction_count: int = 0

    # Prediction quality (calibration)
    prediction_accuracy: float = 0.5  # Rolling average

    # Embedding (E8 latent)
    e8_embedding: torch.Tensor | None = None

    # Timestamp
    updated_at: float = field(default_factory=time.time)

    def add_belief(self, belief: AgentBelief) -> None:
        """Add or update a belief."""
        # Check for existing belief with same proposition
        for i, existing in enumerate(self.beliefs):
            if existing.proposition == belief.proposition:
                self.beliefs[i] = belief
                return
        self.beliefs.append(belief)
        self.updated_at = time.time()

    def get_belief(self, proposition: str) -> AgentBelief | None:
        """Get belief by proposition."""
        for belief in self.beliefs:
            if belief.proposition == proposition:
                return belief
        return None


# =============================================================================
# AGENT MODEL
# =============================================================================


class AgentModel(nn.Module):
    """Neural network model for predicting agent behavior.

    Uses a learned embedding to represent agent state and predict:
    - Next actions
    - Goals/intentions
    - Beliefs about world state
    - Likely confusion/surprise

    ARCHITECTURE:
    =============
    1. State encoder: AgentState → E8 latent (8D)
    2. Dynamics: Predict state transitions given observations
    3. Action predictor: E8 latent → action distribution
    4. Goal inferrer: E8 latent → goal distribution
    5. Surprise estimator: Predict agent's expected surprise

    This integrates with the World Model by sharing the E8 latent space.
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType = AgentType.UNKNOWN,
        state_dim: int = 64,
        e8_dim: int = 8,
        hidden_dim: int = 128,
        num_actions: int = 32,
        num_goals: int = 16,
    ) -> None:
        super().__init__()

        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state_dim = state_dim
        self.e8_dim = e8_dim

        # State encoder: features → E8 latent
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, e8_dim),
        )

        # Dynamics model: E8 + observation → E8'
        self.dynamics = nn.Sequential(
            nn.Linear(e8_dim + state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, e8_dim),
        )

        # Action predictor: E8 → action distribution
        self.action_head = nn.Sequential(
            nn.Linear(e8_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, num_actions),
        )

        # Goal inferrer: E8 → goal distribution
        self.goal_head = nn.Sequential(
            nn.Linear(e8_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, num_goals),
        )

        # Surprise estimator: E8 + observation → expected surprise
        self.surprise_head = nn.Sequential(
            nn.Linear(e8_dim + state_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Softplus(),  # Surprise is non-negative
        )

        # Intent confidence predictor
        self.intent_confidence_head = nn.Sequential(
            nn.Linear(e8_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid(),
        )

        # Current state
        self._current_state: AgentState | None = None
        self._e8_latent: torch.Tensor | None = None

        # History for prediction calibration
        self._prediction_history: list[dict[str, Any]] = []

        logger.debug(
            f"AgentModel initialized: agent={agent_id}, type={agent_type.value}, "
            f"e8_dim={e8_dim}, actions={num_actions}, goals={num_goals}"
        )

    def encode_state(self, features: torch.Tensor) -> torch.Tensor:
        """Encode agent state features to E8 latent.

        Args:
            features: [B, state_dim] state features

        Returns:
            [B, 8] E8 latent embedding
        """
        return cast(torch.Tensor, self.state_encoder(features))

    def predict_next_state(
        self,
        e8_latent: torch.Tensor,
        observation: torch.Tensor,
    ) -> torch.Tensor:
        """Predict agent's next state given observation.

        Args:
            e8_latent: [B, 8] current E8 latent
            observation: [B, state_dim] new observation

        Returns:
            [B, 8] predicted next E8 latent
        """
        combined = torch.cat([e8_latent, observation], dim=-1)
        delta = self.dynamics(combined)
        return cast(torch.Tensor, e8_latent + delta)  # Residual connection

    def predict_action(
        self,
        e8_latent: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Predict agent's next action distribution.

        Args:
            e8_latent: [B, 8] E8 latent

        Returns:
            (action_logits [B, num_actions], action_probs [B, num_actions])
        """
        logits = self.action_head(e8_latent)
        probs = torch.softmax(logits, dim=-1)
        return logits, probs

    def predict_goals(
        self,
        e8_latent: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Infer agent's goals from E8 latent.

        Args:
            e8_latent: [B, 8] E8 latent

        Returns:
            (goal_logits [B, num_goals], goal_probs [B, num_goals])
        """
        logits = self.goal_head(e8_latent)
        probs = torch.softmax(logits, dim=-1)
        return logits, probs

    def estimate_surprise(
        self,
        e8_latent: torch.Tensor,
        observation: torch.Tensor,
    ) -> torch.Tensor:
        """Estimate how surprised the agent would be by an observation.

        High surprise indicates the observation violates the agent's
        expectations, which can signal:
        - Confusion (help needed)
        - Learning opportunity
        - Potential misunderstanding

        Args:
            e8_latent: [B, 8] agent's E8 latent state
            observation: [B, state_dim] observation to evaluate

        Returns:
            [B] expected surprise (non-negative)
        """
        combined = torch.cat([e8_latent, observation], dim=-1)
        surprise = self.surprise_head(combined)
        return cast(torch.Tensor, surprise.squeeze(-1))

    def get_intent_confidence(
        self,
        e8_latent: torch.Tensor,
    ) -> torch.Tensor:
        """Get confidence in our intent inference.

        Low confidence suggests we should ask for clarification.

        Args:
            e8_latent: [B, 8] E8 latent

        Returns:
            [B] confidence in [0, 1]
        """
        return cast(torch.Tensor, self.intent_confidence_head(e8_latent).squeeze(-1))

    def forward(
        self,
        features: torch.Tensor,
        observation: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Full forward pass.

        Args:
            features: [B, state_dim] agent state features
            observation: [B, state_dim] optional new observation

        Returns:
            Dict with all predictions
        """
        # Encode to E8
        e8_latent = self.encode_state(features)

        # Predict actions and goals
        action_logits, action_probs = self.predict_action(e8_latent)
        goal_logits, goal_probs = self.predict_goals(e8_latent)

        # Intent confidence
        intent_confidence = self.get_intent_confidence(e8_latent)

        result = {
            "e8_latent": e8_latent,
            "action_logits": action_logits,
            "action_probs": action_probs,
            "goal_logits": goal_logits,
            "goal_probs": goal_probs,
            "intent_confidence": intent_confidence,
        }

        # If observation provided, predict next state and surprise
        if observation is not None:
            e8_next = self.predict_next_state(e8_latent, observation)
            surprise = self.estimate_surprise(e8_latent, observation)
            result["e8_next"] = e8_next
            result["surprise"] = surprise

        return result

    def update_state(self, state: AgentState) -> None:
        """Update internal state tracking."""
        self._current_state = state
        if state.e8_embedding is not None:
            self._e8_latent = state.e8_embedding

    @property
    def current_state(self) -> AgentState | None:
        """Get current agent state."""
        return self._current_state


# =============================================================================
# FACTORY
# =============================================================================


def create_agent_model(  # type: ignore[no-untyped-def]
    agent_id: str,
    agent_type: AgentType = AgentType.UNKNOWN,
    **kwargs,
) -> AgentModel:
    """Create an agent model.

    Args:
        agent_id: Unique identifier for the agent
        agent_type: Type of agent being modeled
        **kwargs: Additional configuration

    Returns:
        Configured AgentModel
    """
    return AgentModel(
        agent_id=agent_id,
        agent_type=agent_type,
        **kwargs,
    )
