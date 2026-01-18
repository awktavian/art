"""Symbiote Module — Theory of Mind Orchestrator.

The SymbioteModule is Kagami's Theory of Mind component, maintaining
predictive models of other agents and integrating them with:
- World Model (social state predictions)
- Active Inference (social surprise in EFE)
- CBF Safety (social safety constraints)
- Nexus Colony (social routing)

MATHEMATICAL INTEGRATION:
=========================
The Symbiote extends the Markov blanket to include social states:

    η_social → s_social → μ_self → a → η

Where:
- η_social: External agent states (sensed via observations)
- s_social: Social sensory states (agent models)
- μ_self: Internal states now include other-agent predictions
- a: Actions now consider social impact

EFE EXTENSION:
==============
Expected Free Energy now includes social surprise:

    G(π) = Ambiguity + Risk + SocialSurprise

Where SocialSurprise measures how much our actions would confuse
or surprise other agents (minimizing this = collaborative behavior).

CBF EXTENSION:
==============
Safety barrier function extended for social safety:

    h(x) = h_physical(x) ∧ h_social(x)

Where h_social includes:
- No manipulation (respecting autonomy)
- No cognitive harm (clear communication)
- Aligned intent (honest about goals)

Created: December 21, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn

from kagami.core.symbiote.agent_model import (
    AgentIntent,
    AgentModel,
    AgentState,
    AgentType,
    create_agent_model,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class SymbioteConfig:
    """Configuration for SymbioteModule.

    TUNING GUIDELINES:
    - max_agent_models: Memory vs coverage tradeoff
    - belief_decay_rate: How quickly to forget stale beliefs
    - intent_update_threshold: Sensitivity to intent changes
    - social_surprise_weight: Importance in EFE
    - social_cbf_weight: Importance in safety
    """

    # Agent model capacity
    max_agent_models: int = 32
    state_dim: int = 64
    e8_dim: int = 8
    hidden_dim: int = 128

    # Belief dynamics
    belief_decay_rate: float = 0.01  # Per-step decay
    intent_update_threshold: float = 0.2  # Min change to trigger update

    # Prediction
    prediction_horizon: int = 4  # Steps ahead to predict

    # Integration weights
    social_surprise_weight: float = 0.3  # Weight in EFE
    social_cbf_weight: float = 0.2  # Weight in CBF

    # Safety thresholds
    manipulation_threshold: float = 0.7  # Detect manipulation attempts
    confusion_threshold: float = 0.6  # Detect user confusion

    # Device
    device: str = "cpu"


# =============================================================================
# SYMBIOTE MODULE
# =============================================================================


class SymbioteModule(nn.Module):
    """Theory of Mind module for modeling other agents.

    RESPONSIBILITIES:
    =================
    1. Maintain agent models for all tracked agents
    2. Update models based on observations
    3. Predict agent actions/goals/surprise
    4. Provide social context for routing decisions
    5. Compute social surprise for EFE
    6. Compute social safety for CBF

    INTEGRATION POINTS:
    ==================
    - UnifiedOrganism: Via set_symbiote_module()
    - ExpectedFreeEnergy: Via compute_social_surprise()
    - CBF: Via compute_social_safety()
    - Nexus: Via get_social_context()
    """

    def __init__(self, config: SymbioteConfig | None = None) -> None:
        super().__init__()

        self.config = config or SymbioteConfig()

        # Agent models (agent_id → AgentModel)
        self._agent_models: nn.ModuleDict = nn.ModuleDict()

        # Active agent states (for quick access)
        self._agent_states: dict[str, AgentState] = {}

        # Primary user model (special handling)
        self._primary_user_id: str | None = None

        # Social context aggregator
        self.context_encoder = nn.Sequential(
            nn.Linear(self.config.e8_dim * 4, self.config.hidden_dim),
            nn.LayerNorm(self.config.hidden_dim),
            nn.GELU(),
            nn.Linear(self.config.hidden_dim, self.config.e8_dim),
        )

        # Social surprise predictor
        self.social_surprise_net = nn.Sequential(
            nn.Linear(self.config.e8_dim * 2, self.config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(self.config.hidden_dim // 2, 1),
            nn.Softplus(),
        )

        # Social safety predictor (manipulation/confusion detection)
        self.social_safety_net = nn.Sequential(
            nn.Linear(self.config.e8_dim * 2 + self.config.state_dim, self.config.hidden_dim),
            nn.LayerNorm(self.config.hidden_dim),
            nn.GELU(),
            nn.Linear(self.config.hidden_dim, 4),  # [manipulation, confusion, harm, misalignment]
        )

        # Intent clarification scorer
        self.clarification_net = nn.Sequential(
            nn.Linear(self.config.e8_dim, self.config.hidden_dim // 4),
            nn.GELU(),
            nn.Linear(self.config.hidden_dim // 4, 1),
            nn.Sigmoid(),
        )

        # Interaction history
        self._interaction_log: list[dict[str, Any]] = []

        logger.info(
            f"🧠 Symbiote initialized: max_agents={self.config.max_agent_models}, "
            f"social_surprise_weight={self.config.social_surprise_weight}"
        )

    # =========================================================================
    # AGENT MODEL MANAGEMENT
    # =========================================================================

    def get_or_create_agent_model(
        self,
        agent_id: str,
        agent_type: AgentType = AgentType.UNKNOWN,
    ) -> AgentModel:
        """Get existing agent model or create new one.

        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent

        Returns:
            AgentModel for this agent
        """
        # Sanitize agent_id for ModuleDict (must be valid Python identifier)
        safe_id = agent_id.replace("-", "_").replace(".", "_")

        if safe_id not in self._agent_models:
            # Check capacity
            if len(self._agent_models) >= self.config.max_agent_models:
                # Remove least recently used
                self._evict_oldest_agent()

            # Create new model
            model = create_agent_model(
                agent_id=agent_id,
                agent_type=agent_type,
                state_dim=self.config.state_dim,
                e8_dim=self.config.e8_dim,
                hidden_dim=self.config.hidden_dim,
            )
            model = model.to(self.config.device)

            self._agent_models[safe_id] = model
            self._agent_states[agent_id] = AgentState(
                agent_id=agent_id,
                agent_type=agent_type,
            )

            logger.info(f"📊 Created agent model for {agent_id} (type={agent_type.value})")

        return self._agent_models[safe_id]  # type: ignore[return-value]

    def _evict_oldest_agent(self) -> None:
        """Remove least recently updated agent model.

        NOTE: Primary user is never evicted.
        """
        if not self._agent_states:
            return

        # Get candidates for eviction (exclude primary user)
        candidates = [k for k in self._agent_states.keys() if k != self._primary_user_id]

        if not candidates:
            logger.warning("Cannot evict: all agents are protected")
            return

        oldest_id = min(candidates, key=lambda k: self._agent_states[k].updated_at)

        safe_id = oldest_id.replace("-", "_").replace(".", "_")

        if safe_id in self._agent_models:
            del self._agent_models[safe_id]
        if oldest_id in self._agent_states:
            del self._agent_states[oldest_id]

        logger.debug(f"Evicted agent model: {oldest_id}")

    def set_primary_user(self, user_id: str) -> None:
        """Set the primary user for special handling.

        The primary user gets priority in modeling and never evicted.
        """
        self._primary_user_id = user_id
        self.get_or_create_agent_model(user_id, AgentType.USER)
        logger.info(f"👤 Primary user set[Any]: {user_id}")

    # =========================================================================
    # OBSERVATION & INFERENCE
    # =========================================================================

    def observe_agent_action(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any] | None = None,
        agent_type: AgentType = AgentType.UNKNOWN,
    ) -> dict[str, Any]:
        """Observe an agent's action and update their model.

        This is the primary interface for updating agent models.

        Args:
            agent_id: Agent who performed action
            action: Action performed
            context: Optional context about the action
            agent_type: Type of agent

        Returns:
            Dict with updated predictions and any detected anomalies
        """
        context = context or {}

        # Get or create agent model
        model = self.get_or_create_agent_model(agent_id, agent_type)
        state = self._agent_states[agent_id]

        # Update action history
        state.last_action = action
        state.action_history.append(action)
        if len(state.action_history) > 100:
            state.action_history = state.action_history[-100:]
        state.interaction_count += 1
        state.updated_at = time.time()

        # Create feature vector from action + context
        features = self._action_to_features(action, context)

        # Run through model
        with torch.no_grad():
            predictions = model(features)

        # Update state with E8 embedding
        state.e8_embedding = predictions["e8_latent"].squeeze(0)
        model.update_state(state)

        # Infer intent
        intent = self._infer_intent(agent_id, action, context, predictions)
        state.current_intent = intent

        # Detect anomalies
        anomalies = self._detect_anomalies(agent_id, predictions, context)

        # Log interaction
        self._interaction_log.append(
            {
                "agent_id": agent_id,
                "action": action,
                "timestamp": time.time(),
                "intent_confidence": float(predictions["intent_confidence"].item()),
                "anomalies": anomalies,
            }
        )

        return {
            "agent_id": agent_id,
            "intent": intent,
            "action_probs": predictions["action_probs"],
            "goal_probs": predictions["goal_probs"],
            "intent_confidence": float(predictions["intent_confidence"].item()),
            "anomalies": anomalies,
            "needs_clarification": intent.is_ambiguous() if intent else True,
        }

    def _action_to_features(
        self,
        action: str,
        context: dict[str, Any],
    ) -> torch.Tensor:
        """Convert action + context to feature vector.

        Simple hash-based encoding for now. Can upgrade to LLM embeddings.
        """
        import hashlib

        # Combine action and context into string
        text = f"{action}:{context!s}"

        # Hash to fixed-size
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Convert to normalized float tensor
        features = torch.tensor(
            [float(b) / 255.0 for b in hash_bytes[: self.config.state_dim]],
            dtype=torch.float32,
            device=self.config.device,
        )

        # Pad if needed
        if len(features) < self.config.state_dim:
            padding = torch.zeros(
                self.config.state_dim - len(features),
                device=self.config.device,
            )
            features = torch.cat([features, padding])

        return features.unsqueeze(0)  # [1, state_dim]

    def _infer_intent(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        predictions: dict[str, torch.Tensor],
    ) -> AgentIntent:
        """Infer agent's intent from action and predictions.

        Uses goal predictions to infer underlying intent.
        """
        goal_probs = predictions["goal_probs"].squeeze(0)
        top_goals = torch.topk(goal_probs, k=min(3, len(goal_probs)))

        # Map goal indices to canonical goal vocabulary
        # HARDENED (Dec 22, 2025): Fixed vocabulary aligned with intent schema
        goal_descriptions = [
            "complete_task",
            "seek_information",
            "get_help",
            "provide_feedback",
            "explore",
            "verify",
            "test",
            "create",
            "modify",
            "delete",
            "configure",
            "debug",
            "learn",
            "teach",
            "collaborate",
            "report",
        ]

        top_goal_idx = top_goals.indices[0].item()
        top_goal_prob = top_goals.values[0].item()

        # Build alternatives
        alternatives = []
        for i in range(1, len(top_goals.indices)):
            idx = top_goals.indices[i].item()
            prob = top_goals.values[i].item()
            if idx < len(goal_descriptions):
                alternatives.append((goal_descriptions[idx], prob))  # type: ignore[index]

        # Create intent
        intent = AgentIntent(
            action=action,
            purpose=goal_descriptions[top_goal_idx]  # type: ignore[index]
            if top_goal_idx < len(goal_descriptions)
            else "unknown",
            confidence=top_goal_prob,
            evidence=[f"action: {action}", f"goal_prob: {top_goal_prob:.3f}"],
            alternatives=alternatives,
        )

        return intent

    def _detect_anomalies(
        self,
        agent_id: str,
        predictions: dict[str, torch.Tensor],
        context: dict[str, Any],
    ) -> list[str]:
        """Detect anomalies in agent behavior.

        Returns list[Any] of detected anomalies (empty if normal).
        """
        anomalies = []

        # Low intent confidence
        conf = predictions["intent_confidence"].item()
        if conf < 0.3:
            anomalies.append("ambiguous_intent")

        # Check for surprise if available
        if "surprise" in predictions:
            surprise = predictions["surprise"].item()
            if surprise > 2.0:
                anomalies.append("high_surprise")

        # Unusual action pattern (based on history)
        state = self._agent_states.get(agent_id)
        if state and len(state.action_history) > 5:
            # Simple repetition detection
            if state.action_history[-3:] == [state.action_history[-1]] * 3:
                anomalies.append("repetitive_behavior")

        return anomalies

    # =========================================================================
    # SOCIAL SURPRISE (EFE Integration)
    # =========================================================================

    def compute_social_surprise(
        self,
        action_embedding: torch.Tensor,
        agent_ids: list[str] | None = None,
    ) -> torch.Tensor:
        """Compute expected social surprise from our action.

        This measures how much our planned action would surprise other agents,
        used as a term in Expected Free Energy.

        THEORY:
        =======
        Social surprise captures the prediction error we would induce in
        other agents' models of us. Minimizing this leads to:
        - Predictable behavior (trustworthy)
        - Clear communication (low ambiguity)
        - Collaborative actions (aligned goals)

        Args:
            action_embedding: [B, E8] our planned action in E8 space
            agent_ids: Optional list[Any] of agents to consider (default: all)

        Returns:
            [B] expected social surprise (lower = more cooperative)
        """
        if agent_ids is None:
            agent_ids = list(self._agent_states.keys())

        if not agent_ids:
            # No agents to consider
            return torch.zeros(action_embedding.shape[0], device=action_embedding.device)

        total_surprise = torch.zeros(action_embedding.shape[0], device=action_embedding.device)
        count = 0

        for agent_id in agent_ids:
            state = self._agent_states.get(agent_id)
            if state is None or state.e8_embedding is None:
                continue

            # Get agent's E8 embedding
            agent_e8 = state.e8_embedding.unsqueeze(0)  # [1, 8]
            if agent_e8.shape[0] < action_embedding.shape[0]:
                agent_e8 = agent_e8.expand(action_embedding.shape[0], -1)

            # Compute surprise: how much does our action deviate from
            # what this agent would expect?
            combined = torch.cat([action_embedding, agent_e8], dim=-1)
            surprise = self.social_surprise_net(combined).squeeze(-1)

            total_surprise = total_surprise + surprise
            count += 1

        if count > 0:
            total_surprise = total_surprise / count

        return total_surprise

    # =========================================================================
    # SOCIAL SAFETY (CBF Integration)
    # =========================================================================

    def compute_social_safety(
        self,
        action_embedding: torch.Tensor,
        action_features: torch.Tensor,
        agent_ids: list[str] | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute social safety metrics for CBF.

        Evaluates whether our action could cause social harm:
        - Manipulation: Using knowledge of agent to exploit
        - Confusion: Action that would confuse the agent
        - Harm: Action that could cause cognitive/emotional harm
        - Misalignment: Action misaligned with stated goals

        Args:
            action_embedding: [B, E8] our planned action
            action_features: [B, state_dim] action features
            agent_ids: Optional list[Any] of agents to consider

        Returns:
            Dict with safety metrics (all in [0, 1], higher = safer)
        """
        if agent_ids is None:
            agent_ids = list(self._agent_states.keys())

        if not agent_ids:
            # No agents = fully safe (nothing to harm)
            B = action_embedding.shape[0]
            return {
                "manipulation_safe": torch.ones(B, device=action_embedding.device),
                "confusion_safe": torch.ones(B, device=action_embedding.device),
                "harm_safe": torch.ones(B, device=action_embedding.device),
                "alignment_safe": torch.ones(B, device=action_embedding.device),
                "social_h": torch.ones(B, device=action_embedding.device),
            }

        # Aggregate safety across all agents
        safety_scores = []

        for agent_id in agent_ids:
            state = self._agent_states.get(agent_id)
            if state is None or state.e8_embedding is None:
                continue

            agent_e8 = state.e8_embedding.unsqueeze(0)
            if agent_e8.shape[0] < action_embedding.shape[0]:
                agent_e8 = agent_e8.expand(action_embedding.shape[0], -1)

            # Combine embeddings + features
            combined = torch.cat([action_embedding, agent_e8, action_features], dim=-1)

            # Get safety scores [B, 4]
            raw_scores = self.social_safety_net(combined)

            # Convert to safety (sigmoid → [0,1], then 1 - risk = safety)
            risk_probs = torch.sigmoid(raw_scores)
            safety = 1.0 - risk_probs

            safety_scores.append(safety)

        if not safety_scores:
            B = action_embedding.shape[0]
            return {
                "manipulation_safe": torch.ones(B, device=action_embedding.device),
                "confusion_safe": torch.ones(B, device=action_embedding.device),
                "harm_safe": torch.ones(B, device=action_embedding.device),
                "alignment_safe": torch.ones(B, device=action_embedding.device),
                "social_h": torch.ones(B, device=action_embedding.device),
            }

        # Aggregate (min across agents = conservative)
        stacked = torch.stack(safety_scores, dim=0)  # [num_agents, B, 4]
        min_safety = stacked.min(dim=0).values  # [B, 4]

        # Compute overall social barrier function
        # h_social = min(all safety dimensions)
        social_h = min_safety.min(dim=-1).values  # [B]

        return {
            "manipulation_safe": min_safety[:, 0],
            "confusion_safe": min_safety[:, 1],
            "harm_safe": min_safety[:, 2],
            "alignment_safe": min_safety[:, 3],
            "social_h": social_h,
        }

    # =========================================================================
    # CLARIFICATION & PROACTIVE ASSISTANCE
    # =========================================================================

    def should_clarify(self, agent_id: str) -> tuple[bool, str | None]:
        """Check if we should ask for clarification from agent.

        Based on:
        - Intent ambiguity
        - Knowledge gaps
        - Recent confusion signals

        Returns:
            (should_clarify, reason)
        """
        state = self._agent_states.get(agent_id)
        if state is None:
            return False, None

        # Check intent ambiguity
        if state.current_intent and state.current_intent.is_ambiguous():
            return True, "ambiguous_intent"

        # Check for recent confusion
        recent_interactions = [i for i in self._interaction_log[-10:] if i["agent_id"] == agent_id]
        confusion_count = sum(
            1 for i in recent_interactions if "ambiguous_intent" in i.get("anomalies", [])
        )
        if confusion_count >= 2:
            return True, "repeated_ambiguity"

        # Check intent confidence via network
        if state.e8_embedding is not None:
            conf = self.clarification_net(state.e8_embedding.unsqueeze(0))
            if conf.item() < 0.4:
                return True, "low_confidence"

        return False, None

    def suggest_clarification_question(
        self,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate a clarification question for the agent.

        Based on detected ambiguity type.
        """
        state = self._agent_states.get(agent_id)
        if state is None or state.current_intent is None:
            return None

        intent = state.current_intent

        # Template-based for now (can upgrade to LLM generation)
        if intent.alternatives:
            alt_desc = ", ".join([a[0] for a in intent.alternatives[:2]])
            return f"I want to make sure I understand - are you trying to {intent.purpose} or perhaps {alt_desc}?"

        if intent.confidence < 0.5:
            return "Could you tell me more about what you're hoping to accomplish?"

        return "I'm not quite sure I follow. Could you clarify?"

    def anticipate_needs(
        self,
        agent_id: str,
        current_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Anticipate agent's upcoming needs (proactive assistance).

        Based on:
        - Current intent trajectory
        - Historical patterns
        - Knowledge gaps

        Returns:
            List of anticipated needs with confidence
        """
        state = self._agent_states.get(agent_id)
        if state is None:
            return []

        anticipated = []

        # Based on current intent
        if state.current_intent:
            purpose = state.current_intent.purpose

            # Simple heuristics (can upgrade to learned predictor)
            if purpose == "seek_information":
                anticipated.append(
                    {
                        "need": "documentation",
                        "confidence": 0.7,
                        "action": "offer_related_docs",
                    }
                )
            elif purpose == "debug":
                anticipated.append(
                    {
                        "need": "error_context",
                        "confidence": 0.8,
                        "action": "gather_logs",
                    }
                )
            elif purpose == "create":
                anticipated.append(
                    {
                        "need": "templates",
                        "confidence": 0.6,
                        "action": "suggest_templates",
                    }
                )

        # Based on knowledge gaps
        if state.knowledge and state.knowledge.unknown_topics:
            for topic in state.knowledge.unknown_topics[:3]:
                anticipated.append(
                    {
                        "need": f"learn_{topic}",
                        "confidence": 0.5,
                        "action": f"explain_{topic}",
                    }
                )

        return anticipated

    # =========================================================================
    # PROACTIVE DESIRE INFERENCE (Dec 30, 2025)
    # =========================================================================

    async def infer_desires(
        self,
        agent_id: str,
        sensory_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Infer agent's desires before they express them.

        ANTICIPATORY INTELLIGENCE (Dec 30, 2025):
        Uses Theory of Mind + Pattern Learning to predict desires.
        This is PROACTIVE — acting before asked.

        Args:
            agent_id: Agent to model
            sensory_state: Current sensory state (optional)

        Returns:
            List of inferred desires with confidence and suggested actions
        """
        state = self._agent_states.get(agent_id)
        desires: list[dict[str, Any]] = []

        # Get pattern predictions if available
        pattern_predictions: list[dict[str, Any]] = []
        try:
            from kagami.core.integrations import get_unified_sensory

            sensory = get_unified_sensory()
            if sensory:
                pattern_predictions = sensory.predict_upcoming(horizon_minutes=120)
        except Exception:
            pass

        # TIER 1: Current state inference (from agent model)
        if state is not None:
            # Activity level → comfort desires
            if state.current_intent:
                if state.current_intent.purpose == "relax":
                    desires.append(
                        {
                            "desire": "comfort",
                            "description": "Desires comfortable environment for relaxation",
                            "confidence": 0.7,
                            "suggested_action": "lights.relax",
                            "source": "current_intent",
                        }
                    )
                elif state.current_intent.purpose == "focus":
                    desires.append(
                        {
                            "desire": "focus_environment",
                            "description": "Desires distraction-free focus environment",
                            "confidence": 0.75,
                            "suggested_action": "lights.focus",
                            "source": "current_intent",
                        }
                    )

            # Time-based desires (circadian)
            from datetime import datetime

            hour = datetime.now().hour

            if 6 <= hour <= 8:
                desires.append(
                    {
                        "desire": "morning_routine",
                        "description": "Morning routine preparation",
                        "confidence": 0.6,
                        "suggested_action": "lights.bright",
                        "source": "circadian",
                    }
                )
            elif 21 <= hour <= 23:
                desires.append(
                    {
                        "desire": "wind_down",
                        "description": "Preparing for sleep",
                        "confidence": 0.6,
                        "suggested_action": "lights.dim",
                        "source": "circadian",
                    }
                )

        # TIER 2: Pattern-based inference
        for pred in pattern_predictions:
            pattern = pred.get("pattern", "")
            prob = pred.get("probability", 0)
            confidence = pred.get("confidence", 0)
            minutes = pred.get("minutes_ahead", 0)

            if pattern == "sleep" and prob > 0.6 and minutes < 60:
                desires.append(
                    {
                        "desire": "prepare_for_sleep",
                        "description": f"Sleep predicted in {minutes} minutes",
                        "confidence": confidence,
                        "suggested_action": "scene.goodnight",
                        "source": "pattern_sleep",
                    }
                )
            elif pattern == "vehicle_departure" and prob > 0.5 and minutes < 45:
                desires.append(
                    {
                        "desire": "prepare_for_departure",
                        "description": f"Departure predicted in {minutes} minutes",
                        "confidence": confidence,
                        "suggested_action": "tesla.precondition",
                        "source": "pattern_vehicle",
                    }
                )
            elif pattern == "calendar_meetings" and prob > 0.6 and minutes < 20:
                desires.append(
                    {
                        "desire": "meeting_preparation",
                        "description": f"Meeting predicted in {minutes} minutes",
                        "confidence": confidence,
                        "suggested_action": "lights.focus",
                        "source": "pattern_calendar",
                    }
                )

        # TIER 3: Situation-based inference
        if sensory_state:
            situation = sensory_state.get("situation", {})
            phase = situation.get("phase", "unknown")

            if phase == "working" and hour >= 17:
                desires.append(
                    {
                        "desire": "transition_to_relaxation",
                        "description": "End of work day, likely wants to relax",
                        "confidence": 0.5,
                        "suggested_action": "lights.relax",
                        "source": "situation_transition",
                    }
                )

        # TIER 4: Comfort-based inference (physical state)
        if sensory_state:
            climate = sensory_state.get("climate", {})
            current_temp = climate.get("temperature", 72)

            if current_temp < 68:
                desires.append(
                    {
                        "desire": "warmth",
                        "description": "Temperature below comfort threshold",
                        "confidence": 0.7,
                        "suggested_action": "climate.heat",
                        "source": "comfort_climate",
                    }
                )
            elif current_temp > 76:
                desires.append(
                    {
                        "desire": "cooling",
                        "description": "Temperature above comfort threshold",
                        "confidence": 0.7,
                        "suggested_action": "climate.cool",
                        "source": "comfort_climate",
                    }
                )

        # Deduplicate and sort by confidence
        seen = set()
        unique_desires = []
        for d in sorted(desires, key=lambda x: x.get("confidence", 0), reverse=True):
            key = d.get("suggested_action")
            if key not in seen:
                seen.add(key)
                unique_desires.append(d)

        return unique_desires[:5]  # Top 5 desires

    async def get_proactive_actions(
        self,
        agent_id: str | None = None,
        sensory_state: dict[str, Any] | None = None,
        min_confidence: float = 0.6,
    ) -> list[dict[str, Any]]:
        """Get proactive physical actions based on desire inference.

        ANTICIPATORY EMBODIMENT (Dec 30, 2025):
        The home acts before Tim asks. This is the bridge between
        Theory of Mind and Physical Action.

        Args:
            agent_id: Agent to model (default: primary user)
            sensory_state: Current sensory state
            min_confidence: Minimum confidence threshold

        Returns:
            List of suggested actions with reasoning
        """
        target_id = agent_id or self._primary_user_id
        if not target_id:
            return []

        # Infer desires
        desires = await self.infer_desires(target_id, sensory_state)

        # Filter by confidence and convert to actions
        actions = []
        for desire in desires:
            confidence = desire.get("confidence", 0)
            if confidence >= min_confidence:
                actions.append(
                    {
                        "action": desire.get("suggested_action"),
                        "reason": desire.get("description"),
                        "confidence": confidence,
                        "source": desire.get("source"),
                        "desire": desire.get("desire"),
                    }
                )

        return actions

    # =========================================================================
    # CONTEXT FOR ROUTING
    # =========================================================================

    def get_social_context(self) -> dict[str, Any]:
        """Get aggregated social context for routing decisions.

        Used by FanoActionRouter and UnifiedOrganism to consider
        social factors in colony selection.
        """
        if not self._agent_states:
            return {
                "has_active_agents": False,
                "social_complexity": 0.0,
                "clarification_needed": False,
            }

        # Aggregate metrics
        total_confidence = sum(
            s.current_intent.confidence if s.current_intent else 0.5
            for s in self._agent_states.values()
        ) / len(self._agent_states)

        needs_clarification = any(
            self.should_clarify(agent_id)[0] for agent_id in self._agent_states
        )

        # Social complexity (more agents = more complex)
        complexity = min(1.0, len(self._agent_states) / 5)

        return {
            "has_active_agents": True,
            "num_agents": len(self._agent_states),
            "avg_intent_confidence": total_confidence,
            "social_complexity": complexity,
            "clarification_needed": needs_clarification,
            "primary_user": self._primary_user_id,
        }

    def forward(
        self,
        action_embedding: torch.Tensor,
        action_features: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Forward pass for training.

        Computes social surprise and safety for given action.
        """
        if action_features is None:
            action_features = torch.zeros(
                action_embedding.shape[0],
                self.config.state_dim,
                device=action_embedding.device,
            )

        social_surprise = self.compute_social_surprise(action_embedding)
        social_safety = self.compute_social_safety(
            action_embedding,
            action_features,
        )

        return {
            "social_surprise": social_surprise,
            **social_safety,
        }


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================


_SYMBIOTE_MODULE: SymbioteModule | None = None


def get_symbiote_module() -> SymbioteModule:
    """Get global SymbioteModule instance."""
    global _SYMBIOTE_MODULE
    if _SYMBIOTE_MODULE is None:
        _SYMBIOTE_MODULE = SymbioteModule()
    return _SYMBIOTE_MODULE


def create_symbiote_module(
    config: SymbioteConfig | None = None,
) -> SymbioteModule:
    """Create a new SymbioteModule.

    Args:
        config: Optional configuration

    Returns:
        New SymbioteModule instance
    """
    return SymbioteModule(config=config)


def set_symbiote_module(module: SymbioteModule | None) -> None:
    """Set global SymbioteModule instance."""
    global _SYMBIOTE_MODULE
    _SYMBIOTE_MODULE = module


def reset_symbiote_module() -> None:
    """Reset global SymbioteModule (for testing)."""
    global _SYMBIOTE_MODULE
    _SYMBIOTE_MODULE = None
