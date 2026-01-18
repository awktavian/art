"""World Model Embodiment Bridge — RSSM to Physical Actions.

Connects OrganismRSSM imagination to physical SmartHome actions.
This is the motor cortex — where cognitive predictions become physical reality.

ARCHITECTURE (Dec 30, 2025):
============================
1. RSSM imagines futures under candidate physical actions
2. Evaluate imagined trajectories for comfort/preference
3. Select best action sequence via EFE-like evaluation
4. Execute first action through PhysicalPolicySpace

The World Model's action space now includes physical embodiment.
The house is the body. The RSSM is the brain.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

    from kagami.core.world_model.rssm_core import OrganismRSSM

logger = logging.getLogger(__name__)


@dataclass
class PhysicalAction:
    """A candidate physical action for evaluation."""

    action_type: str  # e.g., "climate.comfort", "lights.focus"
    parameters: dict[str, Any] = field(default_factory=dict)
    action_tensor: torch.Tensor | None = None  # Encoded action for RSSM


@dataclass
class ImaginedOutcome:
    """Result of imagining a physical action trajectory."""

    action: PhysicalAction
    trajectory: dict[str, torch.Tensor]
    comfort_score: float
    safety_score: float
    preference_alignment: float
    total_score: float


# Physical action encodings (8D to match E8 action space)
PHYSICAL_ACTION_ENCODINGS = {
    # Climate (affects comfort)
    "climate.comfort": torch.tensor([1.0, 0.0, 0.5, 0.0, 0.0, 0.5, 0.0, 0.0]),
    "climate.heat": torch.tensor([1.0, 0.5, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0]),
    "climate.cool": torch.tensor([1.0, -0.5, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0]),
    # Lighting (affects alertness/relaxation)
    "lights.focus": torch.tensor([0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 0.5, 0.0]),
    "lights.relax": torch.tensor([0.0, 0.0, 0.5, -0.3, 0.0, 0.0, 0.3, 0.0]),
    "lights.bright": torch.tensor([0.0, 0.0, 1.0, 0.7, 0.0, 0.0, 0.7, 0.0]),
    "lights.dim": torch.tensor([0.0, 0.0, 0.3, -0.5, 0.0, 0.0, 0.2, 0.0]),
    # Scenes (compound effects)
    "scene.movie": torch.tensor([0.3, 0.0, 0.3, -0.3, 0.5, 0.0, 0.5, 0.5]),
    "scene.goodnight": torch.tensor([0.5, -0.3, 0.1, -0.7, 0.0, 0.0, 0.0, 0.3]),
    # Audio
    "audio.play": torch.tensor([0.0, 0.0, 0.0, 0.0, 0.5, 0.3, 0.0, 0.5]),
    "audio.announce": torch.tensor([0.0, 0.0, 0.0, 0.3, 0.3, 0.0, 0.0, 0.2]),
    # Security
    "security.lock_all": torch.tensor([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
    # Shades
    "shades.open": torch.tensor([0.0, 0.0, 0.5, 0.3, 0.0, 0.3, 0.0, 0.0]),
    "shades.close": torch.tensor([0.0, 0.0, 0.3, -0.2, 0.0, -0.2, 0.0, 0.2]),
    # Vehicle
    "tesla.precondition": torch.tensor([0.5, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5]),
}


class WorldModelEmbodiment:
    """Bridge between OrganismRSSM and physical embodiment.

    Uses RSSM imagination to select optimal physical actions.
    This completes the perception-action loop for physical embodiment.

    Usage:
        bridge = WorldModelEmbodiment()
        await bridge.initialize(rssm, smart_home)

        # Proactive action selection
        action = await bridge.select_optimal_action()

        # Or evaluate specific action
        outcome = bridge.imagine_action(PhysicalAction("scene.movie", {}))
    """

    def __init__(self) -> None:
        self._rssm: OrganismRSSM | None = None
        self._controller: SmartHomeController | None = None
        self._device = "cpu"

        # State tracking
        self._current_h: torch.Tensor | None = None
        self._current_z: torch.Tensor | None = None

        # Statistics
        self._imagination_count = 0
        self._action_count = 0
        self._last_action: str | None = None

    async def initialize(
        self,
        rssm: OrganismRSSM | None = None,
        controller: SmartHomeController | None = None,
    ) -> bool:
        """Initialize the embodiment bridge.

        Args:
            rssm: OrganismRSSM instance (or lazy-load)
            controller: SmartHomeController (or lazy-load)

        Returns:
            True if initialization successful
        """
        # Load RSSM
        if rssm is not None:
            self._rssm = rssm
        else:
            try:
                from kagami.core.world_model.rssm_core import get_organism_rssm

                self._rssm = get_organism_rssm()
            except Exception as e:
                logger.warning(f"RSSM not available: {e}")

        # Load SmartHome controller
        if controller is not None:
            self._controller = controller
        else:
            try:
                from kagami_smarthome import get_smart_home

                self._controller = await get_smart_home()
            except Exception as e:
                logger.warning(f"SmartHome not available: {e}")

        # Get device from RSSM
        if self._rssm is not None:
            try:
                self._device = next(self._rssm.parameters()).device.type
            except StopIteration:
                self._device = "cpu"

        success = self._rssm is not None or self._controller is not None
        if success:
            logger.info(
                f"✅ WorldModelEmbodiment initialized: "
                f"rssm={'connected' if self._rssm else 'none'}, "
                f"controller={'connected' if self._controller else 'none'}"
            )
        return success

    def update_state(self, h: torch.Tensor, z: torch.Tensor) -> None:
        """Update current RSSM state from external source.

        Called when sensory integration updates the world model.

        Args:
            h: Deterministic state [B, h_dim]
            z: Stochastic state [B, z_dim]
        """
        self._current_h = h.detach()
        self._current_z = z.detach()

    def encode_action(self, action_type: str) -> torch.Tensor:
        """Encode physical action type to 8D tensor.

        Args:
            action_type: Action string (e.g., "climate.comfort")

        Returns:
            8D action tensor for RSSM
        """
        if action_type in PHYSICAL_ACTION_ENCODINGS:
            return PHYSICAL_ACTION_ENCODINGS[action_type].to(self._device)

        # Unknown action: zero vector (no-op)
        logger.debug(f"Unknown action type: {action_type}, using zero encoding")
        return torch.zeros(8, device=self._device)

    def imagine_action(
        self,
        action: PhysicalAction,
        horizon: int = 5,
    ) -> ImaginedOutcome | None:
        """Imagine trajectory under a physical action.

        Args:
            action: Physical action to evaluate
            horizon: Imagination horizon (timesteps)

        Returns:
            ImaginedOutcome with trajectory and scores, or None if RSSM unavailable
        """
        if self._rssm is None:
            return None

        if self._current_h is None or self._current_z is None:
            # Initialize from RSSM if no current state
            states = self._rssm.get_current_states()
            if states:
                self._current_h = torch.stack([s.deterministic for s in states], dim=1).mean(dim=1)
                self._current_z = torch.stack([s.stochastic for s in states], dim=1).mean(dim=1)
            else:
                logger.warning("No RSSM state available for imagination")
                return None

        self._imagination_count += 1

        # Encode action to tensor
        action_tensor = self.encode_action(action.action_type)
        action.action_tensor = action_tensor

        # Create action sequence (repeat action for horizon)
        batch_size = self._current_h.shape[0] if self._current_h.dim() > 1 else 1
        h = self._current_h.unsqueeze(0) if self._current_h.dim() == 1 else self._current_h
        z = self._current_z.unsqueeze(0) if self._current_z.dim() == 1 else self._current_z

        policy = action_tensor.unsqueeze(0).unsqueeze(0).expand(batch_size, horizon, -1)

        # Imagine trajectory
        with torch.no_grad():
            trajectory = self._rssm.imagine(h, z, policy)

        # Evaluate trajectory
        comfort_score = self._evaluate_comfort(trajectory, action.action_type)
        safety_score = self._evaluate_safety(trajectory)
        preference_alignment = self._evaluate_preferences(trajectory, action.action_type)

        total_score = 0.4 * comfort_score + 0.3 * safety_score + 0.3 * preference_alignment

        return ImaginedOutcome(
            action=action,
            trajectory=trajectory,
            comfort_score=comfort_score,
            safety_score=safety_score,
            preference_alignment=preference_alignment,
            total_score=total_score,
        )

    def _evaluate_comfort(self, trajectory: dict[str, torch.Tensor], action_type: str) -> float:
        """Evaluate comfort from imagined trajectory.

        Args:
            trajectory: RSSM imagination output
            action_type: The action being evaluated

        Returns:
            Comfort score [0, 1]
        """
        # Simple heuristic: climate/lighting actions improve comfort
        comfort_actions = ["climate.", "lights.relax", "scene.movie", "scene.goodnight"]
        base_score = 0.5

        for prefix in comfort_actions:
            if action_type.startswith(prefix):
                base_score = 0.7
                break

        # Trajectory stability contributes to comfort
        if "h_states" in trajectory:
            h_states = trajectory["h_states"]
            # Lower variance = more stable = more comfortable
            variance = h_states.var(dim=1).mean().item()
            stability_bonus = max(0, 0.3 - variance * 0.1)
            base_score += stability_bonus

        return min(1.0, base_score)

    def _evaluate_safety(self, trajectory: dict[str, torch.Tensor]) -> float:
        """Evaluate safety of imagined trajectory.

        Args:
            trajectory: RSSM imagination output

        Returns:
            Safety score [0, 1], where 1 = completely safe
        """
        # Check for extreme states that might indicate unsafe conditions
        if "e8_predictions" in trajectory:
            e8_preds = trajectory["e8_predictions"]
            # Large deviations from origin are potentially unsafe
            magnitude = e8_preds.norm(dim=-1).mean().item()
            if magnitude > 2.0:
                return 0.5  # Elevated risk
            return 0.9  # Generally safe

        return 0.8  # Default: assume safe

    def _evaluate_preferences(self, trajectory: dict[str, torch.Tensor], action_type: str) -> float:
        """Evaluate alignment with user preferences.

        Args:
            trajectory: RSSM imagination output
            action_type: The action being evaluated

        Returns:
            Preference alignment score [0, 1]
        """
        # Integrate with Theory of Mind / BDI model for preference alignment
        # First try to get BDI-based preference model, fall back to heuristics
        try:
            # Try multiple possible locations for Theory of Mind module
            preference_model = None
            try:
                from kagami.core.theory_of_mind import get_preference_model

                preference_model = get_preference_model()
            except ImportError:
                # Try alternative location
                from kagami.core.cognition.theory_of_mind import get_preference_model

                preference_model = get_preference_model()

            if preference_model is not None:
                return preference_model.score_action_alignment(action_type)
        except ImportError:
            logger.debug("Theory of Mind module not available - using heuristic preferences")
        except Exception as e:
            logger.warning(f"Failed to get BDI preference model: {e}")

        # Fall back to action-type heuristics based on Tim's known preferences

        # Tim's known preferences (from TIM_PROFILE.md)
        tim_preferences = {
            "scene.movie": 0.9,  # Loves movies
            "lights.focus": 0.8,  # Values deep work
            "climate.comfort": 0.8,  # Quality-focused
            "audio.play": 0.7,  # Enjoys music
            "scene.goodnight": 0.9,  # Values sleep
            "tesla.precondition": 0.8,  # Convenience
        }

        return tim_preferences.get(action_type, 0.6)

    async def select_optimal_action(
        self,
        candidate_actions: list[str] | None = None,
        horizon: int = 5,
    ) -> PhysicalAction | None:
        """Select optimal physical action via imagination.

        Evaluates candidate actions through RSSM imagination and selects
        the one with highest total score.

        Args:
            candidate_actions: Actions to consider (default: common actions)
            horizon: Imagination horizon

        Returns:
            Best PhysicalAction, or None if evaluation fails
        """
        if candidate_actions is None:
            candidate_actions = [
                "climate.comfort",
                "lights.focus",
                "lights.relax",
                "scene.movie",
                "audio.play",
            ]

        outcomes: list[ImaginedOutcome] = []

        for action_type in candidate_actions:
            action = PhysicalAction(action_type=action_type)
            outcome = self.imagine_action(action, horizon)
            if outcome:
                outcomes.append(outcome)

        if not outcomes:
            return None

        # Select best by total score
        best = max(outcomes, key=lambda o: o.total_score)
        logger.info(
            f"🧠 Selected action: {best.action.action_type} "
            f"(score={best.total_score:.2f}, comfort={best.comfort_score:.2f})"
        )
        return best.action

    async def execute_action(self, action: PhysicalAction) -> dict[str, Any]:
        """Execute a physical action through SmartHome.

        Args:
            action: PhysicalAction to execute

        Returns:
            Execution result
        """
        if self._controller is None:
            return {"success": False, "error": "SmartHome controller not available"}

        self._action_count += 1
        self._last_action = action.action_type

        # Use PhysicalPolicySpace for execution
        try:
            from kagami.core.motivation.physical_policy_space import get_physical_policy_space

            policy_space = get_physical_policy_space()
            result = await policy_space.execute("smarthome", action.action_type, action.parameters)

            return {
                "success": result.success,
                "action": result.action,
                "details": result.details,
                "error": result.error,
            }
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {"success": False, "error": str(e)}

    async def predict_and_act(self, horizon: int = 5) -> dict[str, Any]:
        """Main loop: predict optimal action and execute it.

        This is the proactive embodiment cycle:
        1. Imagine futures under candidate actions
        2. Select best action
        3. Execute

        Args:
            horizon: Imagination horizon

        Returns:
            Result including selected action and execution outcome
        """
        # Select optimal action
        action = await self.select_optimal_action(horizon=horizon)
        if action is None:
            return {"success": False, "error": "No suitable action found"}

        # Execute
        result = await self.execute_action(action)

        return {
            "selected_action": action.action_type,
            "parameters": action.parameters,
            **result,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get embodiment statistics."""
        return {
            "rssm_connected": self._rssm is not None,
            "controller_connected": self._controller is not None,
            "imagination_count": self._imagination_count,
            "action_count": self._action_count,
            "last_action": self._last_action,
            "has_state": self._current_h is not None,
        }


# Singleton
_embodiment_bridge: WorldModelEmbodiment | None = None


async def get_world_model_embodiment() -> WorldModelEmbodiment:
    """Get global WorldModelEmbodiment instance."""
    global _embodiment_bridge
    if _embodiment_bridge is None:
        _embodiment_bridge = WorldModelEmbodiment()
        await _embodiment_bridge.initialize()
    return _embodiment_bridge


def reset_world_model_embodiment() -> None:
    """Reset singleton (for testing)."""
    global _embodiment_bridge
    _embodiment_bridge = None


__all__ = [
    "PHYSICAL_ACTION_ENCODINGS",
    "ImaginedOutcome",
    "PhysicalAction",
    "WorldModelEmbodiment",
    "get_world_model_embodiment",
    "reset_world_model_embodiment",
]
