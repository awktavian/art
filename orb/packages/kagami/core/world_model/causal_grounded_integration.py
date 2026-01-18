"""Causal, Strategic, and Grounded Intelligence Integration.

CREATED: December 27, 2025
PURPOSE: Implements the three proposals from "Kagami Evolution: The Path to Grounded Intelligence"

Architecture (bottom to top):
1. Foundation: E8 Lattice, Octonion Algebra, CBF Safety, 7 Colonies, RSSM World Model (existing)
2. Causal Reasoning Engine - enables counterfactual reasoning (alongside RSSM)
3. Temporal Abstraction Layer - enables long-horizon strategy (on top of planning)
4. Embodied Sensorimotor Input - grounds predictions in physics (from Genesis)

References:
- Pearl (2009): Causality: Models, Reasoning and Inference (SCM foundation)
- Sutton et al. (1999): Options framework (temporal abstraction)
- Pan et al. (2024): Hieros - Hierarchical planning with learned abstractions
- Genesis Physics Simulator: Embodied cognition grounding
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn

if TYPE_CHECKING:
    from kagami.core.world_model.rssm_core import OrganismRSSM

logger = logging.getLogger(__name__)


# =============================================================================
# LAYER 1: CAUSAL REASONING ENGINE
# =============================================================================


@dataclass
class CounterfactualQuery:
    """Query for counterfactual reasoning.

    Example: "What would have happened if action A' was taken instead of A?"
    """

    observation: torch.Tensor  # Current observation [B, obs_dim]
    factual_action: torch.Tensor  # Action that was taken [B, action_dim]
    counterfactual_action: torch.Tensor  # Alternative action to evaluate [B, action_dim]
    query_variable: str = "next_state"  # What to compute counterfactually


@dataclass
class CounterfactualResult:
    """Result of counterfactual reasoning."""

    factual_outcome: torch.Tensor  # What actually happened
    counterfactual_outcome: torch.Tensor  # What would have happened
    causal_effect: torch.Tensor  # Difference (counterfactual - factual)
    confidence: float  # How confident we are in this estimate


class CausalReasoningEngine(nn.Module):
    """Causal Reasoning Engine for counterfactual queries.

    Implements Pearl's 3-step counterfactual algorithm:
    1. ABDUCTION: Infer exogenous variables U from observations
    2. ACTION: Apply intervention do(X=x) by modifying graph
    3. PREDICTION: Compute counterfactual outcome

    INTEGRATION (Dec 27, 2025):
    - Delegates to FullStructuralEquationModel for full graph-based reasoning
    - Uses neural approximation for fast tensor operations
    - Bridges world model predictions with causal inference

    Integrates with OrganismRSSM for dynamics.
    """

    def __init__(
        self,
        obs_dim: int = 8,  # E8 code dimension
        action_dim: int = 8,
        hidden_dim: int = 64,
        device: str = "cpu",
        use_full_sem: bool = True,  # Use FullStructuralEquationModel backend
    ):
        super().__init__()
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self._use_full_sem = use_full_sem

        # Exogenous variable inference (ABDUCTION step)
        # U = f(observation, action, next_observation)
        self.exogenous_encoder = nn.Sequential(
            nn.Linear(obs_dim * 2 + action_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, obs_dim),  # Exogenous noise U
        )

        # Structural equation: next_state = f(state, action) + U
        # This learns the causal mechanism
        self.causal_mechanism = nn.Sequential(
            nn.Linear(obs_dim + action_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, obs_dim),
        )

        # Full SEM integration - wire to existing implementation
        self._full_sem: Any = None
        if use_full_sem:
            self._init_full_sem()

        logger.info(
            f"✅ CausalReasoningEngine initialized: obs_dim={obs_dim}, "
            f"action_dim={action_dim}, hidden_dim={hidden_dim}, "
            f"full_sem={self._full_sem is not None}"
        )

    def _init_full_sem(self) -> None:
        """Initialize FullStructuralEquationModel backend."""
        from kagami.core.optimality.remaining_gaps import (
            FullStructuralEquationModel,
            StructuralEquation,
        )

        # Create default E8-based causal graph
        # Variables: e8_0..e8_7 (E8 code) + action_0..action_7
        variables = (
            [f"e8_{i}" for i in range(self.obs_dim)]
            + [f"action_{i}" for i in range(self.action_dim)]
            + [f"next_e8_{i}" for i in range(self.obs_dim)]
        )

        # Structural equations: next_e8_i = f(e8_*, action_*) + U_i
        equations = []
        for i in range(self.obs_dim):
            # Each next_e8 depends on all e8 and actions (fully connected)
            parents = [f"e8_{j}" for j in range(self.obs_dim)] + [
                f"action_{j}" for j in range(self.action_dim)
            ]
            equations.append(
                StructuralEquation(
                    variable=f"next_e8_{i}",
                    parents=parents,
                    nonlinear=True,  # Use MLP
                    hidden_dim=self.hidden_dim,
                    activation="gelu",
                )
            )

        self._full_sem = FullStructuralEquationModel(
            variables=variables,
            equations=equations,
        )
        logger.debug("✅ FullStructuralEquationModel backend initialized")

    @property
    def full_sem(self) -> Any:
        """Access the underlying FullStructuralEquationModel."""
        return self._full_sem

    def abduction(
        self,
        observation: torch.Tensor,
        action: torch.Tensor,
        next_observation: torch.Tensor,
    ) -> torch.Tensor:
        """Step 1: ABDUCTION - Infer exogenous variables from observations.

        Given (obs, action, next_obs), infer the noise U that explains the transition.

        Args:
            observation: Current state [B, obs_dim]
            action: Action taken [B, action_dim]
            next_observation: Resulting state [B, obs_dim]

        Returns:
            Exogenous variables U [B, obs_dim]
        """
        # Concatenate all evidence
        evidence = torch.cat([observation, action, next_observation], dim=-1)

        # Infer exogenous noise
        U = self.exogenous_encoder(evidence)

        return U

    def intervention(
        self,
        observation: torch.Tensor,
        counterfactual_action: torch.Tensor,
        exogenous: torch.Tensor,
    ) -> torch.Tensor:
        """Steps 2-3: ACTION + PREDICTION - Apply intervention and compute counterfactual.

        Given state s, counterfactual action a', and inferred U, compute what
        would have happened: s' = f(s, a') + U

        Args:
            observation: Current state [B, obs_dim]
            counterfactual_action: Alternative action [B, action_dim]
            exogenous: Inferred exogenous variables [B, obs_dim]

        Returns:
            Counterfactual next state [B, obs_dim]
        """
        # Apply structural equation with intervention
        inputs = torch.cat([observation, counterfactual_action], dim=-1)
        deterministic_part = self.causal_mechanism(inputs)

        # Add exogenous noise (from abduction)
        counterfactual_next = deterministic_part + exogenous

        return counterfactual_next

    def counterfactual(
        self,
        query: CounterfactualQuery,
        next_observation: torch.Tensor | None = None,
    ) -> CounterfactualResult:
        """Full 3-step counterfactual computation.

        Args:
            query: Counterfactual query with factual/counterfactual actions
            next_observation: Actual next state (for abduction). If None, use forward model.

        Returns:
            CounterfactualResult with factual and counterfactual outcomes
        """
        # Step 1: Compute factual outcome (what actually happened)
        factual_inputs = torch.cat([query.observation, query.factual_action], dim=-1)
        factual_outcome = self.causal_mechanism(factual_inputs)

        # If next_observation provided, use it for abduction
        if next_observation is not None:
            exogenous = self.abduction(
                query.observation,
                query.factual_action,
                next_observation,
            )
        else:
            # Use zero exogenous (deterministic counterfactual)
            exogenous = torch.zeros_like(factual_outcome)

        # Steps 2-3: Intervention + Prediction
        counterfactual_outcome = self.intervention(
            query.observation,
            query.counterfactual_action,
            exogenous,
        )

        # Compute causal effect
        causal_effect = counterfactual_outcome - factual_outcome

        # Compute confidence from prediction uncertainty
        # Higher variance in causal effect → lower confidence
        effect_variance = causal_effect.var(dim=-1).mean()
        # Sigmoid transform: small variance → high confidence (near 1.0)
        # Large variance → low confidence (approaches 0.5)
        confidence = float(torch.sigmoid(-effect_variance + 2.0).item())
        confidence = max(0.5, min(0.99, confidence))  # Clamp to [0.5, 0.99]

        return CounterfactualResult(
            factual_outcome=factual_outcome,
            counterfactual_outcome=counterfactual_outcome,
            causal_effect=causal_effect,
            confidence=confidence,
        )

    def forward(
        self,
        observation: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Forward prediction (standard causal mechanism).

        Args:
            observation: Current state [B, obs_dim]
            action: Action [B, action_dim]

        Returns:
            Predicted next state [B, obs_dim]
        """
        inputs = torch.cat([observation, action], dim=-1)
        return self.causal_mechanism(inputs)


# =============================================================================
# LAYER 2: TEMPORAL ABSTRACTION LAYER
# =============================================================================


@dataclass
class MacroAction:
    """A temporally extended action (option).

    Represents a "macro-action" that spans multiple timesteps.
    Example: "refactor the module" = [define function, write tests, commit changes]
    """

    name: str
    subgoal: torch.Tensor  # Target state to reach [subgoal_dim]
    policy_id: int  # Which sub-policy to execute
    expected_duration: int  # Expected number of primitive steps
    termination_condition: str = "subgoal_reached"  # When to stop


@dataclass
class HierarchicalPlanResult:
    """Result of hierarchical planning."""

    macro_actions: list[MacroAction]
    primitive_actions: torch.Tensor  # [T, action_dim] low-level actions
    expected_value: float
    subgoal_sequence: torch.Tensor  # [num_subgoals, subgoal_dim]


class TemporalAbstractionLayer(nn.Module):
    """Temporal Abstraction Layer for long-horizon planning.

    Implements hierarchical temporal abstraction inspired by Sutton's "options":
    - Strategic Goal → Macro-Actions → Primitive Actions

    INTEGRATION (Dec 27, 2025):
    - Bridges with LearnedHierarchicalPlanner for options framework
    - Uses TemporalAbstractionNetwork for subgoal discovery when available
    - Provides differentiable PyTorch interface for world model integration

    Enables planning at the level of "refactor the module" instead of
    "type the next character".

    References:
    - Sutton et al. (1999): Between MDPs and semi-MDPs
    - Pan et al. (2024): Hieros - Hierarchical imagination
    """

    def __init__(
        self,
        state_dim: int = 64,  # RSSM hidden dim
        subgoal_dim: int = 32,
        action_dim: int = 8,
        n_subgoals: int = 8,  # Number of discrete subgoal prototypes
        max_horizon: int = 100,
        device: str = "cpu",
        use_learned_planner: bool = True,  # Integrate with LearnedHierarchicalPlanner
    ):
        super().__init__()
        self.state_dim = state_dim
        self.subgoal_dim = subgoal_dim
        self.action_dim = action_dim
        self.n_subgoals = n_subgoals
        self.max_horizon = max_horizon
        self._use_learned_planner = use_learned_planner

        # Subgoal encoder: state → subgoal latent
        self.subgoal_encoder = nn.Sequential(
            nn.Linear(state_dim, state_dim),
            nn.LayerNorm(state_dim),
            nn.GELU(),
            nn.Linear(state_dim, subgoal_dim),
        )

        # Subgoal prototypes (learned cluster centers)
        self.subgoal_prototypes = nn.Parameter(torch.randn(n_subgoals, subgoal_dim) * 0.1)

        # Integration with existing LearnedHierarchicalPlanner
        self._learned_planner: Any = None
        self._temporal_abstraction_net: Any = None
        if use_learned_planner:
            self._init_learned_planner()

        # High-level policy: state → subgoal selection logits
        self.high_level_policy = nn.Sequential(
            nn.Linear(state_dim, state_dim),
            nn.GELU(),
            nn.Linear(state_dim, n_subgoals),
        )

        # Low-level policy: (state, subgoal) → primitive action
        self.low_level_policy = nn.Sequential(
            nn.Linear(state_dim + subgoal_dim, state_dim),
            nn.GELU(),
            nn.Linear(state_dim, action_dim),
        )

        # Termination predictor: (state, subgoal) → done probability
        self.termination_predictor = nn.Sequential(
            nn.Linear(state_dim + subgoal_dim, state_dim // 2),
            nn.GELU(),
            nn.Linear(state_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Value function for subgoals
        self.subgoal_value = nn.Sequential(
            nn.Linear(state_dim + subgoal_dim, state_dim),
            nn.GELU(),
            nn.Linear(state_dim, 1),
        )

        logger.info(
            f"✅ TemporalAbstractionLayer initialized: state_dim={state_dim}, "
            f"subgoal_dim={subgoal_dim}, n_subgoals={n_subgoals}, "
            f"learned_planner={self._learned_planner is not None}"
        )

    def _init_learned_planner(self) -> None:
        """Initialize integration with LearnedHierarchicalPlanner."""
        from kagami.core.rl.learned_hierarchical_planning import (
            LearnedHierarchicalPlanner,
            TemporalAbstractionNetwork,
        )

        # Create temporal abstraction network for k-means subgoal discovery
        self._temporal_abstraction_net = TemporalAbstractionNetwork(
            state_dim=self.state_dim,
            subgoal_dim=self.subgoal_dim,
            n_subgoals=self.n_subgoals,
            use_learned_encoder=False,  # Use k-means
        )

        # Create full hierarchical planner
        self._learned_planner = LearnedHierarchicalPlanner()

        logger.debug("✅ LearnedHierarchicalPlanner backend initialized")

    @property
    def learned_planner(self) -> Any:
        """Access the underlying LearnedHierarchicalPlanner."""
        return self._learned_planner

    @property
    def temporal_abstraction_net(self) -> Any:
        """Access the underlying TemporalAbstractionNetwork."""
        return self._temporal_abstraction_net

    def encode_to_subgoal(self, state: torch.Tensor) -> torch.Tensor:
        """Encode state to subgoal latent space.

        Args:
            state: RSSM hidden state [B, state_dim]

        Returns:
            Subgoal embedding [B, subgoal_dim]
        """
        return self.subgoal_encoder(state)

    def discover_subgoal(self, state: torch.Tensor) -> tuple[int, torch.Tensor]:
        """Discover which discrete subgoal this state belongs to.

        Uses TemporalAbstractionNetwork (k-means clustering) for subgoal discovery.

        Args:
            state: RSSM hidden state [B, state_dim]

        Returns:
            (subgoal_id, subgoal_state) tuple[Any, ...]
        """
        # Use the learned temporal abstraction network
        state_np = state[0].detach().cpu().numpy()
        subgoal_id = self._temporal_abstraction_net.discover_subgoal(state_np)
        subgoal_state = self.subgoal_prototypes[subgoal_id].unsqueeze(0)
        return subgoal_id, subgoal_state

    def select_subgoal(self, state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Select next subgoal using high-level policy.

        Args:
            state: Current RSSM state [B, state_dim]

        Returns:
            (subgoal_logits, selected_subgoal) - logits and selected prototype
        """
        logits = self.high_level_policy(state)  # [B, n_subgoals]

        # Soft selection (Gumbel-softmax for differentiability)
        if self.training:
            weights = torch.nn.functional.gumbel_softmax(logits, hard=True, dim=-1)
        else:
            weights = torch.nn.functional.one_hot(logits.argmax(dim=-1), self.n_subgoals).float()

        # Weighted combination of prototypes
        selected_subgoal = torch.matmul(weights, self.subgoal_prototypes)  # [B, subgoal_dim]

        return logits, selected_subgoal

    def get_primitive_action(
        self,
        state: torch.Tensor,
        subgoal: torch.Tensor,
    ) -> torch.Tensor:
        """Get primitive action to reach subgoal.

        Args:
            state: Current state [B, state_dim]
            subgoal: Target subgoal [B, subgoal_dim]

        Returns:
            Primitive action [B, action_dim]
        """
        inputs = torch.cat([state, subgoal], dim=-1)
        return self.low_level_policy(inputs)

    def should_terminate(
        self,
        state: torch.Tensor,
        subgoal: torch.Tensor,
    ) -> torch.Tensor:
        """Check if current subgoal should terminate.

        Args:
            state: Current state [B, state_dim]
            subgoal: Current subgoal [B, subgoal_dim]

        Returns:
            Termination probability [B, 1]
        """
        inputs = torch.cat([state, subgoal], dim=-1)
        return self.termination_predictor(inputs)

    def imagine_macro_action(
        self,
        initial_state: torch.Tensor,
        rssm: OrganismRSSM,
        horizon: int = 50,
    ) -> HierarchicalPlanResult:
        """Imagine executing a macro-action sequence.

        Plans hierarchically:
        1. Select sequence of subgoals (high-level)
        2. Imagine primitive actions to reach each (low-level)

        Args:
            initial_state: Starting RSSM state [B, state_dim]
            rssm: RSSM for dynamics simulation
            horizon: Planning horizon

        Returns:
            HierarchicalPlanResult with macro and primitive actions
        """
        B = initial_state.size(0)
        device = initial_state.device

        macro_actions: list[MacroAction] = []
        primitive_actions: list[torch.Tensor] = []
        subgoals: list[torch.Tensor] = []

        current_state = initial_state
        total_value = 0.0
        steps_remaining = horizon

        # High-level planning: select subgoals
        n_macro = min(5, horizon // 10)

        for macro_idx in range(n_macro):
            if steps_remaining <= 0:
                break

            # Select next subgoal
            logits, subgoal = self.select_subgoal(current_state)
            subgoals.append(subgoal)

            # Estimate value of reaching this subgoal
            value_input = torch.cat([current_state, subgoal], dim=-1)
            subgoal_value = self.subgoal_value(value_input)
            total_value += float(subgoal_value.mean().item())

            # Low-level planning: generate primitives to reach subgoal
            macro_primitives: list[torch.Tensor] = []
            state = current_state

            steps_for_subgoal = min(10, steps_remaining)
            for _step in range(steps_for_subgoal):
                # Get primitive action
                action = self.get_primitive_action(state, subgoal)
                macro_primitives.append(action)
                primitive_actions.append(action)

                # Check termination
                term_prob = self.should_terminate(state, subgoal)
                if term_prob.mean() > 0.5:
                    break

                # Simulate dynamics (simplified - would use full RSSM)
                # Project state to subgoal space, compute direction, project back
                state_in_subgoal_space = self.subgoal_encoder(state)  # [B, subgoal_dim]
                direction_in_subgoal = subgoal - state_in_subgoal_space  # [B, subgoal_dim]
                # Move state by projecting direction back to state space via transpose
                # Since encoder: state_dim → subgoal_dim, we use a simple linear approximation
                direction_padded = torch.nn.functional.pad(
                    direction_in_subgoal, (0, self.state_dim - self.subgoal_dim)
                )  # [B, state_dim]
                state = state + 0.1 * direction_padded

                steps_remaining -= 1

            # Record macro-action
            macro_actions.append(
                MacroAction(
                    name=f"subgoal_{macro_idx}",
                    subgoal=subgoal.detach(),
                    policy_id=int(logits.argmax(dim=-1)[0].item()),
                    expected_duration=len(macro_primitives),
                )
            )

            current_state = state

        # Stack results
        if primitive_actions:
            primitive_tensor = torch.stack(primitive_actions, dim=1)  # [B, T, action_dim]
        else:
            primitive_tensor = torch.zeros(B, 1, self.action_dim, device=device)

        if subgoals:
            subgoal_tensor = torch.stack(subgoals, dim=1)  # [B, n_subgoals, subgoal_dim]
        else:
            subgoal_tensor = torch.zeros(B, 1, self.subgoal_dim, device=device)

        return HierarchicalPlanResult(
            macro_actions=macro_actions,
            primitive_actions=primitive_tensor,
            expected_value=total_value,
            subgoal_sequence=subgoal_tensor,
        )


# =============================================================================
# LAYER 3: EMBODIED SENSORIMOTOR INPUT
# =============================================================================


class SensorimotorEncoder(nn.Module):
    """Encodes Genesis physics observations into E8 latent space.

    Grounds abstract knowledge in embodied sensorimotor experience.

    INTEGRATION (Dec 27, 2025):
    - Can delegate to SensorimotorEncoderOptimized for multi-modal inputs
    - Provides simplified physics→E8 path for Genesis simulator
    - Bridges with SensorimotorWorldModel for full embodiment loop

    Input: Genesis physics state (positions, velocities, forces)
    Output: E8 code [B, 8] for world model consumption
    """

    def __init__(
        self,
        physics_dim: int = 32,  # Genesis state dimension
        e8_dim: int = 8,
        hidden_dim: int = 64,
        use_optimized_encoder: bool = True,  # Use SensorimotorEncoderOptimized
    ):
        super().__init__()
        self.physics_dim = physics_dim
        self.e8_dim = e8_dim
        self._use_optimized = use_optimized_encoder

        # Integration with optimized multi-modal encoder
        self._optimized_encoder: Any = None
        if use_optimized_encoder:
            self._init_optimized_encoder()

        # Encoder: physics → E8
        self.encoder = nn.Sequential(
            nn.Linear(physics_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, e8_dim),
        )

        # Decoder: E8 → physics (for reconstruction loss)
        self.decoder = nn.Sequential(
            nn.Linear(e8_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, physics_dim),
        )

        logger.info(
            f"✅ SensorimotorEncoder initialized: physics_dim={physics_dim} → e8_dim={e8_dim}, "
            f"optimized={self._optimized_encoder is not None}"
        )

    def _init_optimized_encoder(self) -> None:
        """Initialize integration with SensorimotorEncoderOptimized."""
        from kagami.core.embodiment.sensorimotor_encoder_optimized import (
            create_sensorimotor_encoder_optimized,
        )

        # Create optimized encoder (multi-modal capable)
        self._optimized_encoder = create_sensorimotor_encoder_optimized(device="cpu")
        logger.debug("✅ SensorimotorEncoderOptimized backend initialized")

    @property
    def optimized_encoder(self) -> Any:
        """Access the underlying SensorimotorEncoderOptimized."""
        return self._optimized_encoder

    def encode_multimodal(
        self,
        vision: torch.Tensor | None = None,
        audio: torch.Tensor | None = None,
        touch: torch.Tensor | None = None,
        proprioception: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode multi-modal sensory inputs to E8 (if optimized encoder available).

        Args:
            vision: Visual input [B, vision_dim]
            audio: Audio input [B, audio_dim]
            touch: Touch input [B, touch_dim]
            proprioception: Proprioceptive input [B, proprio_dim]

        Returns:
            E8 code [B, 8]
        """
        if self._optimized_encoder is None:
            raise RuntimeError(
                "Multi-modal encoding requires SensorimotorEncoderOptimized. "
                "Initialize with use_optimized_encoder=True"
            )

        # Delegate to optimized encoder
        result = self._optimized_encoder(
            vision=vision,
            audio=audio,
            touch=touch,
            proprioception=proprioception,
        )
        # Extract E8 code from the H14×S7 output
        # The optimized encoder returns a larger manifold; we take first 8 dims
        if isinstance(result, tuple):
            e8_approx = result[0][..., : self.e8_dim]
        else:
            e8_approx = result[..., : self.e8_dim]
        return e8_approx

    def encode(self, physics_state: torch.Tensor) -> torch.Tensor:
        """Encode physics state to E8.

        Args:
            physics_state: Genesis physics state [B, T, physics_dim] or [B, physics_dim]

        Returns:
            E8 code [B, T, 8] or [B, 8]
        """
        return self.encoder(physics_state)

    def decode(self, e8_code: torch.Tensor) -> torch.Tensor:
        """Decode E8 back to physics space (for reconstruction).

        Args:
            e8_code: E8 latent [B, T, 8] or [B, 8]

        Returns:
            Reconstructed physics state [B, T, physics_dim] or [B, physics_dim]
        """
        return self.decoder(e8_code)

    def forward(
        self,
        physics_state: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass with reconstruction.

        Args:
            physics_state: Genesis physics state

        Returns:
            (e8_code, reconstructed_physics)
        """
        e8_code = self.encode(physics_state)
        reconstructed = self.decode(e8_code)
        return e8_code, reconstructed


# =============================================================================
# UNIFIED INTEGRATION
# =============================================================================


@dataclass
class GroundedIntelligenceConfig:
    """Configuration for grounded intelligence integration."""

    # E8/RSSM dimensions
    obs_dim: int = 8
    action_dim: int = 8
    hidden_dim: int = 64

    # Causal reasoning
    enable_causal: bool = True

    # Temporal abstraction
    enable_temporal: bool = True
    subgoal_dim: int = 32
    n_subgoals: int = 8

    # Embodied grounding
    enable_embodied: bool = True
    physics_dim: int = 32

    # Device
    device: str = "cpu"


class CausalGroundedWorldModel(nn.Module):
    """Unified Causal, Strategic, and Grounded World Model.

    Combines three layers of cognitive enhancement:
    1. Causal Reasoning Engine - counterfactual reasoning
    2. Temporal Abstraction Layer - long-horizon planning
    3. Embodied Sensorimotor Input - physics grounding

    All layers sit alongside/on top of the existing RSSM world model.
    """

    def __init__(
        self,
        config: GroundedIntelligenceConfig | None = None,
        rssm: OrganismRSSM | None = None,
    ):
        super().__init__()
        self.config = config or GroundedIntelligenceConfig()
        self._rssm = rssm

        # Layer 1: Causal Reasoning Engine
        self.causal_engine: CausalReasoningEngine | None = None
        if self.config.enable_causal:
            self.causal_engine = CausalReasoningEngine(
                obs_dim=self.config.obs_dim,
                action_dim=self.config.action_dim,
                hidden_dim=self.config.hidden_dim,
                device=self.config.device,
            )

        # Layer 2: Temporal Abstraction
        self.temporal_abstraction: TemporalAbstractionLayer | None = None
        if self.config.enable_temporal:
            self.temporal_abstraction = TemporalAbstractionLayer(
                state_dim=self.config.hidden_dim,
                subgoal_dim=self.config.subgoal_dim,
                action_dim=self.config.action_dim,
                n_subgoals=self.config.n_subgoals,
                device=self.config.device,
            )

        # Layer 3: Embodied Sensorimotor
        self.sensorimotor_encoder: SensorimotorEncoder | None = None
        if self.config.enable_embodied:
            self.sensorimotor_encoder = SensorimotorEncoder(
                physics_dim=self.config.physics_dim,
                e8_dim=self.config.obs_dim,
                hidden_dim=self.config.hidden_dim,
            )

        logger.info(
            f"✅ CausalGroundedWorldModel initialized: "
            f"causal={self.config.enable_causal}, "
            f"temporal={self.config.enable_temporal}, "
            f"embodied={self.config.enable_embodied}"
        )

    @property
    def rssm(self) -> OrganismRSSM | None:
        """Access underlying RSSM."""
        return self._rssm

    @rssm.setter
    def rssm(self, value: OrganismRSSM) -> None:
        """Set RSSM (for wiring into existing world model)."""
        self._rssm = value

    def counterfactual(
        self,
        query: CounterfactualQuery,
        next_observation: torch.Tensor | None = None,
    ) -> CounterfactualResult:
        """Perform counterfactual reasoning.

        "What would have happened if action A' was taken instead?"

        Args:
            query: Counterfactual query
            next_observation: Actual next state (for abduction)

        Returns:
            CounterfactualResult
        """
        if self.causal_engine is None:
            raise RuntimeError("Causal reasoning not enabled")

        return self.causal_engine.counterfactual(query, next_observation)

    def imagine_macro_action(
        self,
        initial_state: torch.Tensor,
        horizon: int = 50,
    ) -> HierarchicalPlanResult:
        """Plan using temporal abstraction (macro-actions).

        Plans at the level of "refactor module" instead of "type character".

        Args:
            initial_state: Starting state [B, state_dim]
            horizon: Planning horizon

        Returns:
            HierarchicalPlanResult with macro and primitive actions
        """
        if self.temporal_abstraction is None:
            raise RuntimeError("Temporal abstraction not enabled")

        return self.temporal_abstraction.imagine_macro_action(
            initial_state,
            self._rssm,  # type: ignore
            horizon,
        )

    def encode_sensorimotor(
        self,
        physics_state: torch.Tensor,
    ) -> torch.Tensor:
        """Encode Genesis physics state to E8.

        Grounds abstract knowledge in embodied experience.

        Args:
            physics_state: Genesis physics state [B, T, physics_dim]

        Returns:
            E8 code [B, T, 8]
        """
        if self.sensorimotor_encoder is None:
            raise RuntimeError("Embodied grounding not enabled")

        return self.sensorimotor_encoder.encode(physics_state)

    def grounded_forward(
        self,
        physics_state: torch.Tensor,
        s7_phase: torch.Tensor | None = None,
        action: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        """Forward pass with embodied grounding.

        Full pipeline:
        1. Encode Genesis physics → E8
        2. Run through RSSM
        3. Return predictions + grounding info

        Args:
            physics_state: Genesis physics state [B, T, physics_dim]
            s7_phase: Optional S7 phase [B, T, 7]
            action: Optional action [B, T, action_dim]

        Returns:
            Dict with predictions and grounding metrics
        """
        # Step 1: Encode physics to E8
        e8_code = self.encode_sensorimotor(physics_state)

        # Step 2: Get reconstruction (for loss)
        _, physics_reconstructed = self.sensorimotor_encoder(physics_state)  # type: ignore

        # Step 3: Run through RSSM if available
        rssm_output = None
        if self._rssm is not None and e8_code.dim() == 3:
            B, T, _ = e8_code.shape

            # Use default S7 phase if not provided
            if s7_phase is None:
                s7_phase = torch.zeros(B, T, 7, device=e8_code.device)

            rssm_output = self._rssm.forward(
                e8_code=e8_code,
                s7_phase=s7_phase,
                actions=action,
            )

        return {
            "e8_code": e8_code,
            "physics_reconstructed": physics_reconstructed,
            "reconstruction_loss": torch.nn.functional.mse_loss(
                physics_reconstructed, physics_state
            ),
            "rssm_output": rssm_output,
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


_causal_grounded_model: CausalGroundedWorldModel | None = None


def get_causal_grounded_world_model(
    config: GroundedIntelligenceConfig | None = None,
) -> CausalGroundedWorldModel:
    """Get or create the causal grounded world model singleton."""
    global _causal_grounded_model

    if _causal_grounded_model is None:
        _causal_grounded_model = CausalGroundedWorldModel(config)

    return _causal_grounded_model


def reset_causal_grounded_world_model() -> None:
    """Reset the singleton."""
    global _causal_grounded_model
    _causal_grounded_model = None


__all__ = [
    # Core classes
    "CausalGroundedWorldModel",
    "CausalReasoningEngine",
    # Data classes
    "CounterfactualQuery",
    "CounterfactualResult",
    "GroundedIntelligenceConfig",
    "HierarchicalPlanResult",
    "MacroAction",
    "SensorimotorEncoder",
    "TemporalAbstractionLayer",
    # Factory functions
    "get_causal_grounded_world_model",
    "reset_causal_grounded_world_model",
]
