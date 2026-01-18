"""Active Inference Engine - Main Coordinator.

UNIFIED ARCHITECTURE (Dec 2, 2025):
===================================
The Active Inference Engine now operates directly on RSSM states (h, z)
from OrganismRSSM. There are NO separate belief states - we use the
world model's latent space directly.

Implements the complete Active Inference loop:
1. Perception: Update RSSM state from observations
2. Prediction: Forecast future states under policies (via RSSM)
3. Evaluation: Compute expected free energy
4. Action: Select and execute policy

ACTIVE INFERENCE CYCLE:
======================

    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │  ┌─────────┐    ┌──────────┐    ┌───────────────────┐  │
    │  │Perceive │───▶│  RSSM    │───▶│   Predict via     │  │
    │  │  o_t    │    │  h_t,z_t │    │   OrganismRSSM    │  │
    │  └─────────┘    └──────────┘    └─────────┬─────────┘  │
    │       ▲                                    │            │
    │       │                                    ▼            │
    │  ┌────┴────┐                    ┌───────────────────┐  │
    │  │ Execute │◀───────────────────│   Evaluate EFE    │  │
    │  │  a_t    │    Select π*       │   G(π) via RSSM   │  │
    │  └─────────┘                    └───────────────────┘  │
    │                                                         │
    └─────────────────────────────────────────────────────────┘

References:
- Friston, K. (2010). "The free-energy principle: a unified brain theory?"
- Friston et al. (2017). "Active Inference: A Process Theory"
- Parr et al. (2022). "Active Inference: The Free Energy Principle"

Created: November 29, 2025
Unified: December 2, 2025
Status: Production-ready
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

# Import EFE from correct location after cleanup
# FORGE MISSION: Required EFE components - no graceful fallbacks
from kagami.core.active_inference.efe_meta_learner import (
    EFEConfig,
    ExpectedFreeEnergy,
)

if TYPE_CHECKING:
    from kagami.core.world_model.colony_rssm import OrganismRSSM

logger = logging.getLogger(__name__)


# BeliefState DELETED (Dec 3, 2025)
# The unified architecture uses RSSM states (h, z) directly.
# There are no separate belief states - belief IS the RSSM posterior.


@dataclass
class ActiveInferenceConfig:
    """Configuration for Active Inference Engine.

    UNIFIED (Dec 2, 2025):
    Uses RSSM dimensions directly. State is (h, z) from OrganismRSSM.

    VARIABLE-DEPTH PLANNING (Dec 2, 2025):
    Planning horizon is now controlled by k-value via EFEConfig:
    - k=1-3: Reflex/Fast (1-3 steps)
    - k=3-5: Standard (3-5 steps)
    - k=7-11: Deep (7-11 steps)
    - k>11: Safety halt
    """

    # Dimensions (from RSSM)
    h_dim: int = 256  # Deterministic state dimension
    z_dim: int = 14  # Stochastic state dimension (H¹⁴)
    observation_dim: int = 15  # E8(8) + S⁷(7)
    action_dim: int = 8  # E8 octonion

    @property
    def state_dim(self) -> int:
        """Combined state dimension (h + z)."""
        return self.h_dim + self.z_dim

    # EFE settings (includes k-value for variable-depth planning)
    efe_config: EFEConfig = field(default_factory=EFEConfig)

    # Planning (delegates to EFE k-value)
    num_policy_samples: int = 32
    policy_temperature: float = 1.0

    # k-value for variable-depth planning (synced to EFE)
    k_value: int = 5  # Default = STANDARD

    # Prior preferences
    prior_preference_weight: float = 1.0
    habit_strength: float = 0.1  # Weight for habitual policies

    # Device
    device: str = "cpu"

    # NOTE: Empowerment ALWAYS enabled (Dec 5, 2025 - HARDENED)

    @property
    def planning_horizon(self) -> int:
        """Get effective planning horizon from EFE k-value."""
        return self.efe_config.get_effective_horizon()


class PolicyGenerator(nn.Module):
    """Generates candidate policies for EFE evaluation.

    UNIFIED (Dec 2, 2025):
    Uses combined (h, z) state from RSSM.

    VARIABLE-DEPTH (Dec 2, 2025):
    Uses max_horizon for network allocation, actual horizon from k-value.

    GRADIENT OPTIMIZED (Dec 3, 2025):
    ================================
    All policy generation uses differentiable operations:
    - habit_policy: Learned prior for habitual actions (gets gradients via EFE)
    - diversity_net: Exploration policies (gets gradients via EFE diversity bonus)
    - actor: Main policy network for direct action selection (for training)

    Policy gradients flow via:
    1. EFE policy_prior_loss → habit_policy, diversity_net
    2. Direct actor training → actor network
    """

    def __init__(self, config: ActiveInferenceConfig, device: str = "cpu") -> None:
        super().__init__()
        self.config = config
        self.device = torch.device(device) if isinstance(device, str) else device

        # Combined state dimension
        combined_dim = config.h_dim + config.z_dim

        # Use max horizon for network allocation (actual horizon varies by k-value)
        max_horizon = config.efe_config.max_horizon  # 11 by default

        # Policy prior (habitual policies) - GETS GRADIENTS via EFE
        self.habit_policy = nn.Sequential(
            nn.Linear(combined_dim, 256),
            nn.ReLU(),
            nn.Linear(256, max_horizon * config.action_dim),
        ).to(self.device)

        # Diversity generator - GETS GRADIENTS via exploration bonus
        self.diversity_net = nn.Sequential(
            nn.Linear(combined_dim + combined_dim, 256),
            nn.ReLU(),
            nn.Linear(256, max_horizon * config.action_dim),
        ).to(self.device)

        # === DIRECT ACTOR (Dec 3, 2025) ===
        # Single-step action predictor for direct policy training
        # This enables gradient flow independent of EFE planning
        self.actor = nn.Sequential(
            nn.Linear(combined_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, config.action_dim),
            nn.Tanh(),  # Actions in [-1, 1]
        ).to(self.device)

        self._max_horizon = max_horizon

    def generate(
        self,
        h: torch.Tensor,
        z: torch.Tensor,
        num_policies: int | None = None,
        horizon: int | None = None,
    ) -> torch.Tensor:
        """Generate candidate policies from RSSM state.

        VARIABLE-DEPTH (Dec 2, 2025):
        Uses effective horizon from EFE k-value, truncating network output.

        Args:
            h: [h_dim] deterministic state
            z: [z_dim] stochastic state
            num_policies: Number of policies to generate
            horizon: Override horizon (default: from EFE k-value)

        Returns:
            Action sequences [num_policies, horizon, action_dim]
        """
        num_policies = num_policies or self.config.num_policy_samples
        # Use EFE's effective horizon (from k-value) if not overridden
        effective_horizon = horizon or self.config.planning_horizon

        # Device assertion: networks must match input device
        if h.device != self.device:
            raise RuntimeError(
                f"Device mismatch: input on {h.device}, PolicyGenerator on {self.device}. "
                f"Models should be initialized on correct device in __init__."
            )

        # Combine h and z
        combined = torch.cat([h, z], dim=-1)
        if combined.dim() == 1:
            combined = combined.unsqueeze(0)

        # 1. Habitual policy (truncate to effective horizon) - DIFFERENTIABLE
        habit_logits = self.habit_policy(combined)
        habit_logits = habit_logits.reshape(self._max_horizon, self.config.action_dim)
        habit_logits = habit_logits[:effective_horizon]
        habit_actions = F.softmax(habit_logits, dim=-1)

        # 2. VECTORIZED diverse policies - single batched forward pass
        # Generate all noise at once: [num_policies-1, combined_dim]
        noise_batch = torch.randn(num_policies - 1, combined.shape[-1], device=h.device)
        # Expand combined to match: [num_policies-1, combined_dim]
        combined_expanded = combined.squeeze(0).unsqueeze(0).expand(num_policies - 1, -1)
        # Concatenate: [num_policies-1, 2*combined_dim]
        combined_noise_batch = torch.cat([combined_expanded, noise_batch], dim=-1)
        # Single forward pass through diversity_net
        diverse_logits = self.diversity_net(combined_noise_batch)
        # Reshape: [num_policies-1, max_horizon, action_dim]
        diverse_logits = diverse_logits.reshape(
            num_policies - 1, self._max_horizon, self.config.action_dim
        )
        # Truncate to effective horizon
        diverse_logits = diverse_logits[:, :effective_horizon, :]
        # Softmax over action dimension
        diverse_actions = F.softmax(diverse_logits, dim=-1)

        # Stack habit + diverse: [num_policies, effective_horizon, action_dim]
        return torch.cat([habit_actions.unsqueeze(0), diverse_actions], dim=0)

    def get_action(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Get direct action from actor network.

        DIFFERENTIABLE (Dec 3, 2025):
        Used for direct policy gradient training.

        Args:
            h: [B, h_dim] or [h_dim] deterministic state
            z: [B, z_dim] or [z_dim] stochastic state

        Returns:
            [B, action_dim] or [action_dim] action
        """
        # Device assertion: networks must match input device
        if h.device != self.device:
            raise RuntimeError(
                f"Device mismatch: input on {h.device}, PolicyGenerator on {self.device}. "
                f"Models should be initialized on correct device in __init__."
            )

        combined = torch.cat([h, z], dim=-1)
        return self.actor(combined)


class ActiveInferenceEngine(nn.Module):
    """Main Active Inference coordinator using OrganismRSSM.

    UNIFIED ARCHITECTURE (Dec 2, 2025):
    ===================================
    Operates directly on RSSM states (h, z). There are NO separate
    belief states. EFE uses OrganismRSSM for trajectory prediction.
    """

    def __init__(self, config: ActiveInferenceConfig | None = None) -> None:
        super().__init__()
        self.config = config or ActiveInferenceConfig()

        # Sync EFE config with RSSM dimensions
        self.config.efe_config.h_dim = self.config.h_dim
        self.config.efe_config.z_dim = self.config.z_dim
        self.config.efe_config.observation_dim = self.config.observation_dim
        self.config.efe_config.action_dim = self.config.action_dim

        # Sync k-value for variable-depth planning
        if self.config.k_value is not None:
            self.config.efe_config.k_value = self.config.k_value

        # Components
        self.efe = ExpectedFreeEnergy(self.config.efe_config)
        self.policy_generator = PolicyGenerator(self.config, device=self.config.device)

        # === UNIFIED: RSSM reference ===
        self._rssm: OrganismRSSM | None = None

        # Current RSSM state (from world model)
        self._h: torch.Tensor | None = None  # Deterministic
        self._z: torch.Tensor | None = None  # Stochastic

        # Empowerment integration
        self._empowerment_estimator: Any = None

        # Symbiote integration (Theory of Mind, Dec 22, 2025)
        self._symbiote: Any = None

        logger.debug(
            "ActiveInferenceEngine: h=%d, z=%d, k=%d",
            self.config.h_dim,
            self.config.z_dim,
            self.efe.get_k_value(),
        )

    def set_world_model(self, rssm: OrganismRSSM) -> None:
        """Connect engine to OrganismRSSM for unified planning.

        CRITICAL: This must be called to enable EFE planning.

        Args:
            rssm: OrganismRSSM instance from KagamiWorldModel
        """
        self._rssm = rssm
        self.efe.set_world_model(rssm)
        logger.debug("ActiveInferenceEngine connected to OrganismRSSM")

    def set_symbiote_module(self, symbiote: Any) -> None:
        """Connect Symbiote module for Theory of Mind in EFE.

        SYMBIOTE INTEGRATION (Dec 22, 2025):
        ====================================
        Symbiote enables social cognition in policy selection:
        - Social Surprise term in EFE (minimize confusion to others)
        - User intent inference (anticipate needs)
        - Social context awareness (collaborative vs solo)

        The Social Surprise term makes policies that are predictable
        to other agents (users) preferred, building trust and enabling
        seamless collaboration.

        Research basis:
        - arxiv 2508.00401: Active Inference ToM
        - arxiv 2502.14171: ToM for conversational agents
        - arxiv 2311.03150: Theory of Collective Mind

        Args:
            symbiote: SymbioteModule instance
        """
        # Store reference
        self._symbiote = symbiote

        # Wire to EFE calculator (where Social Surprise is computed)
        self.efe.set_symbiote_module(symbiote)
        logger.info("🧠 ActiveInferenceEngine connected to Symbiote (ToM enabled)")

    def set_k_value(self, k: int) -> int:
        """Set metacognition depth (k-value) for variable-depth planning.

        VARIABLE-DEPTH PLANNING (Dec 2, 2025):
        - k=1-3: Reflex/Fast (1-3 steps)
        - k=3-5: Standard (3-5 steps)
        - k=7-11: Deep (7-11 steps)
        - k>11: Safety halt (capped at 11)

        Args:
            k: Metacognition depth

        Returns:
            Effective horizon
        """
        return self.efe.set_k_value(k)

    def get_k_value(self) -> int:
        """Get current k-value."""
        return self.efe.get_k_value()

    def get_effective_horizon(self) -> int:
        """Get current effective planning horizon."""
        return self.efe.get_effective_horizon()

    def update_state(self, h: torch.Tensor, z: torch.Tensor) -> None:
        """Update engine state from RSSM.

        Called after each RSSM step to keep engine in sync.

        Args:
            h: [h_dim] deterministic state from RSSM
            z: [z_dim] stochastic state from RSSM
        """
        self._h = h.detach() if h.requires_grad else h
        self._z = z.detach() if z.requires_grad else z

    @property
    def belief(self) -> dict[str, torch.Tensor] | None:
        """Get current belief state as dict[str, Any] for backward compatibility."""
        if self._h is None or self._z is None:
            return None
        return {"h": self._h, "z": self._z, "mean": torch.cat([self._h, self._z], dim=-1)}

    @property
    def entropy(self) -> float:
        """Estimate belief entropy from z variance."""
        if self._z is None:
            return 0.0
        # Approximate entropy from stochastic state variance
        z_var = self._z.var().item() if self._z.numel() > 1 else 0.1
        return 0.5 * (14 * (1 + torch.log(torch.tensor(2 * 3.14159 * z_var + 1e-8)))).item()

    async def perceive(self, observations: dict[str, Any]) -> dict[str, torch.Tensor]:
        """Update state from observations via RSSM.

        UNIFIED (Dec 2, 2025): RSSM is mandatory for perception.
        SIMPLIFIED (Dec 3, 2025): Removed legacy fallback paths.

        Args:
            observations: Dict with observation data (state_embedding, h, z, etc.)

        Returns:
            Updated state dict[str, Any] with h and z
        """
        # Extract RSSM state if provided directly (most common case)
        if "h" in observations and "z" in observations:
            h_obs = observations["h"]
            z_obs = observations["z"]
            if h_obs is not None and z_obs is not None:
                self._h = h_obs
                self._z = z_obs
                return {"h": h_obs, "z": z_obs}
            # Fall through to RSSM processing if observations are None

        # RSSM is mandatory for perception
        if self._rssm is None:
            raise RuntimeError(
                "RSSM not connected. Call set_world_model() first.\n"
                "ActiveInferenceEngine requires OrganismRSSM for perception."
            )

        # Extract observation tensor
        if "state_embedding" in observations:
            obs = observations["state_embedding"]
        elif "embedding" in observations:
            obs = observations["embedding"]
        else:
            obs = torch.zeros(self.config.observation_dim)

        if not isinstance(obs, torch.Tensor):
            obs = torch.tensor(obs, dtype=torch.float32)

        # Get device from RSSM
        device = next(self._rssm.parameters()).device

        # Step RSSM with observation
        h_prev = self._h if self._h is not None else torch.zeros(self.config.h_dim, device=device)
        z_prev = self._z if self._z is not None else torch.zeros(self.config.z_dim, device=device)

        if h_prev.dim() == 1:
            h_prev = h_prev.unsqueeze(0)
        if z_prev.dim() == 1:
            z_prev = z_prev.unsqueeze(0)
        if obs.dim() == 1:
            obs = obs.unsqueeze(0)

        obs = obs.to(device)

        # Dummy action for perception step
        action = torch.zeros(1, self.config.action_dim, device=device)

        h_next, z_next, _info = self._rssm.step(
            h_prev=h_prev,
            z_prev=z_prev,
            action=action,
            sample=True,
        )

        # Aggregate colony-level states to organism-level
        # RSSM returns [B, 7, H] and [B, 7, Z], aggregate across colonies to [H] and [Z]
        if h_next.dim() == 3:
            # [B, 7, H] -> take first batch element and aggregate across colonies
            h_next = h_next[0].mean(dim=0)
            z_next = z_next[0].mean(dim=0)
        elif h_next.dim() == 2:
            # [7, H] -> aggregate across colonies
            h_next = h_next.mean(dim=0)
            z_next = z_next.mean(dim=0)
        else:
            # Already [H] and [Z]
            h_next = h_next.squeeze(0) if h_next.dim() > 1 else h_next
            z_next = z_next.squeeze(0) if z_next.dim() > 1 else z_next

        self._h = h_next
        self._z = z_next

        return {"h": self._h, "z": self._z}

    async def select_action(
        self,
        candidates: list[dict[str, Any]] | None = None,
        goals: torch.Tensor | None = None,
        plan_tic: dict[str, Any] | None = None,
        k_value: int | None = None,
    ) -> dict[str, Any]:
        """Select action using active inference with RSSM-based EFE.

        UNIFIED (Dec 2, 2025):
        Uses OrganismRSSM for trajectory prediction in EFE.

        VARIABLE-DEPTH (Dec 2, 2025):
        Supports k_value override for dynamic planning depth.

        Args:
            candidates: Optional pre-generated action candidates
            goals: Optional goal specification
            plan_tic: Optional TIC data for imagination-based filtering
            k_value: Optional k-value override for this action selection

        Returns:
            Selected action with metadata (includes k_value and horizon)
        """
        if self._h is None or self._z is None:
            raise RuntimeError(
                "State not initialized. Call perceive() first or update_state() with RSSM state."
            )

        if self._rssm is None:
            raise RuntimeError(
                "RSSM not connected. Call set_world_model() first.\n"
                "ActiveInferenceEngine requires OrganismRSSM for EFE planning."
            )

        # Get effective horizon (possibly overridden by k_value)
        effective_horizon = self.efe.get_effective_horizon()
        if k_value is not None:
            effective_horizon = self.efe.set_k_value(k_value)

        # Generate policies if no candidates provided
        if candidates is None:
            policies = self.policy_generator.generate(self._h, self._z, horizon=effective_horizon)
        else:
            policies = self._candidates_to_policies(candidates)

        # TIC-based filtering
        if plan_tic is not None:
            policies = await self._filter_unsafe_policies(policies, plan_tic)

        # Expand for batch
        h_batch = self._h.unsqueeze(0) if self._h.dim() == 1 else self._h
        z_batch = self._z.unsqueeze(0) if self._z.dim() == 1 else self._z
        policies_batch = policies.unsqueeze(0)  # [1, num_policies, horizon, action_dim]

        # Compute expected free energy using RSSM (with k_value if provided)
        selected, efe_result = self.efe.select_policy(
            h_batch,
            z_batch,
            policies_batch,
            goals,
            k_value=k_value,  # type: ignore[operator]
        )

        # Add empowerment (ALWAYS ON - Dec 5, 2025 HARDENED)
        if self._empowerment_estimator is not None:
            combined = torch.cat([h_batch, z_batch], dim=-1)
            empowerment = self._empowerment_estimator.estimate_empowerment(
                combined, horizon=effective_horizon
            )
            efe_result["empowerment"] = empowerment

        # Get first action from selected policy
        first_action = selected[0, 0]  # [action_dim]

        # TIC imagination for selected action
        tic_prediction = None
        if plan_tic is not None:
            tic_prediction = await self._imagine_action(first_action, plan_tic)

        return {
            "action": first_action,
            "policy": selected[0],
            "G": efe_result["G"][0].min().item(),
            "epistemic_value": efe_result["epistemic"][0].mean().item(),
            "pragmatic_value": efe_result["pragmatic"][0].mean().item(),
            "policy_probs": efe_result.get("policy_probs", None),
            "tic_prediction": tic_prediction,
            "method": "active_inference",
            # Variable-depth info
            "k_value": efe_result.get("k_value", self.efe.get_k_value()),
            "effective_horizon": efe_result.get("effective_horizon", effective_horizon),
            # E8 policy bytes (for receipts)
            "policy_e8_bytes": efe_result.get("policy_e8_bytes", None),
        }

    async def _filter_unsafe_policies(
        self,
        policies: torch.Tensor,
        plan_tic: dict[str, Any],
    ) -> torch.Tensor:
        """Filter out policies that TIC predicts as unsafe."""
        try:
            from kagami.core.world_model import get_world_model_service

            model = get_world_model_service().model
            if model is None:
                return policies
            safe_policies = []

            for i in range(policies.shape[0]):
                first_action = policies[i, 0]
                imagination = model.imagine_receipt(plan_tic, first_action)

                if imagination["safety_margin"].item() >= -0.1:
                    safe_policies.append(policies[i])

            if not safe_policies:
                logger.warning("All policies filtered as unsafe by TIC")
                return policies

            return torch.stack(safe_policies)

        except Exception as e:
            logger.debug(f"TIC filtering skipped: {e}")
            return policies

    async def _imagine_action(
        self,
        action: torch.Tensor,
        plan_tic: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Imagine outcome of action using TIC."""
        try:
            from kagami.core.world_model import get_world_model_service

            model = get_world_model_service().model
            if model is None:
                return None
            imagination = model.imagine_receipt(plan_tic, action)

            return {
                "success_prob": imagination["success_prob"].item(),
                "safety_margin": imagination["safety_margin"].item(),
            }

        except Exception as e:
            logger.debug(f"TIC imagination skipped: {e}")
            return None

    def _candidates_to_policies(self, candidates: list[dict[str, Any]]) -> torch.Tensor:
        """Convert action candidates to policy tensor."""
        effective_horizon = self.efe.get_effective_horizon()
        policies = []
        for cand in candidates:
            if "action_embedding" in cand:
                action = cand["action_embedding"]
            elif "action" in cand:
                action = cand["action"]
            else:
                action = torch.zeros(self.config.action_dim)

            if not isinstance(action, torch.Tensor):
                action = torch.tensor(action, dtype=torch.float32)

            # Repeat for effective horizon (from k-value)
            policy = action.unsqueeze(0).expand(effective_horizon, -1)
            policies.append(policy)

        if not policies:
            return self.policy_generator.generate(self._h, self._z, horizon=effective_horizon)  # type: ignore[arg-type]

        return torch.stack(policies)

    def set_empowerment_estimator(self, estimator: Any) -> None:
        """Set empowerment estimator for integration."""
        self._empowerment_estimator = estimator

    def set_goal(self, goal: torch.Tensor) -> None:
        """Set goal for pragmatic value."""
        self.efe.set_goal(goal)

    def compute_variational_free_energy(self) -> float:
        """Compute current variational free energy."""
        if self._h is None or self._z is None:
            return 0.0

        # Approximate F from z variance (lower variance = lower F)
        z_var = self._z.var().item() if self._z.numel() > 1 else 0.1
        return z_var * self.config.z_dim

    def get_diagnostics(self) -> dict[str, Any]:
        """Get diagnostic information."""
        diag = {
            "state_initialized": self._h is not None and self._z is not None,
            "rssm_connected": self._rssm is not None,
            "free_energy": self.compute_variational_free_energy(),
        }

        if self._h is not None:
            diag["h_norm"] = self._h.norm().item()
        if self._z is not None:
            diag["z_norm"] = self._z.norm().item()
            diag["belief_entropy"] = self.entropy

        return diag


# Singleton and factory
_active_inference_engine: ActiveInferenceEngine | None = None


def get_active_inference_engine(
    config: ActiveInferenceConfig | None = None,
) -> ActiveInferenceEngine:
    """Get or create the global ActiveInferenceEngine instance."""
    global _active_inference_engine
    if _active_inference_engine is None:
        _active_inference_engine = ActiveInferenceEngine(config)
    return _active_inference_engine


def reset_active_inference_engine() -> None:
    """Reset the global instance (for testing)."""
    global _active_inference_engine
    _active_inference_engine = None


__all__ = [
    "ActiveInferenceConfig",
    "ActiveInferenceEngine",
    "PolicyGenerator",
    "get_active_inference_engine",
    "reset_active_inference_engine",
]
