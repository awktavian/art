"""Motor Decoder - Geometric Manifold to Motor Commands

Decodes H⁷ × S⁷ manifold states into executable motor commands.

Motor Actions (Dec 30, 2025 - FULL AUDIT):
  - Discrete: Symbolic robot actions (grasp, release, move, etc.)
  - Continuous: Joint velocities, gripper force, control parameters
  - Digital: 160+ Composio EFFECTOR actions (send_email, create_task, etc.)
  - SmartHome: 60+ Physical EFFECTOR actions (lights, shades, audio, locks)
  - Meta: Control flow actions (wait, observe, delegate)
  - Speech: TTS synthesis parameters

Architecture (Markov Blanket a → η):
  The motor decoder output heads map to the environment modification side:
  - discrete_head → Robot manipulation actions (future)
  - continuous_head → Continuous control parameters
  - digital_head → Composio WRITE actions
  - smarthome_head → SmartHome SET/CONTROL actions
  - meta_head → Control flow actions
  - speech_head → TTS synthesis embedding

Source of Truth: kagami.core.embodiment.action_space
"""

import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# ACTION SPACE IMPORTS (Source of Truth)
# =============================================================================
# All action lists are imported from the central action_space module

from kagami.core.embodiment.action_space import (
    GENERATION_EFFECTORS,
    MOTOR_DECODER_DIGITAL_ACTIONS,
    MOTOR_DECODER_META_ACTIONS,
    MOTOR_DECODER_SMARTHOME_ACTIONS,
    POSTPROCESS_EFFECTORS,
)

# Backwards compatibility aliases
DIGITAL_ACTIONS = MOTOR_DECODER_DIGITAL_ACTIONS
SMARTHOME_ACTIONS = MOTOR_DECODER_SMARTHOME_ACTIONS
META_ACTIONS = MOTOR_DECODER_META_ACTIONS
# Unified generation actions (optimized: 12 effectors + 4 post-process = 16)
GENERATION_ACTIONS = GENERATION_EFFECTORS + POSTPROCESS_EFFECTORS


class MotorDecoder(nn.Module):
    """Decode motor commands from geometric manifold states.

    Maps (H⁷ × S⁷) → motor commands across multiple actuator types.

    Output heads (all are EFFECTORS in the Markov blanket a → η):
      - discrete_head: Symbolic robot actions (grasp, move, etc.)
      - continuous_head: Continuous control parameters [7D]
      - digital_head: Composio WRITE actions (50 primary)
      - smarthome_head: SmartHome SET/CONTROL actions (50 primary)
      - meta_head: Control flow actions (observe, wait, delegate, etc.)
      - speech_head: TTS synthesis embedding [64D]
      - uncertainty_head: Epistemic confidence [0, 1]

    Total Action Space: 160+ effector actions from action_space.py
    """

    def __init__(
        self,
        input_dim: int = 256,  # From Matryoshka final layer
        num_discrete_actions: int | None = None,  # Auto-sized from DISCRETE_ACTIONS
        continuous_action_dim: int = 7,  # Joint velocities, force control
        num_digital_tools: int | None = None,  # Auto-sized from DIGITAL_ACTIONS
        num_smarthome_actions: int | None = None,  # Auto-sized from SMARTHOME_ACTIONS
        num_meta_actions: int | None = None,  # Auto-sized from META_ACTIONS
        num_generation_actions: int | None = None,  # Auto-sized from GENERATION_ACTIONS
        device: str | None = None,
    ) -> None:
        super().__init__()

        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"

        self.device = device

        # Auto-size from action lists
        if num_discrete_actions is None:
            num_discrete_actions = len(DISCRETE_ACTIONS)
        if num_digital_tools is None:
            num_digital_tools = len(DIGITAL_ACTIONS)
        if num_smarthome_actions is None:
            num_smarthome_actions = len(SMARTHOME_ACTIONS)
        if num_meta_actions is None:
            num_meta_actions = len(META_ACTIONS)
        if num_generation_actions is None:
            num_generation_actions = len(GENERATION_ACTIONS)

        self.num_discrete_actions = num_discrete_actions
        self.num_digital_tools = num_digital_tools
        self.num_smarthome_actions = num_smarthome_actions
        self.num_meta_actions = num_meta_actions
        self.num_generation_actions = num_generation_actions

        # Shared feature extraction
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_dim, input_dim * 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(input_dim * 2, input_dim),
        ).to(device)

        # Discrete action head (symbolic robot actions)
        self.discrete_head = nn.Sequential(
            nn.Linear(input_dim, num_discrete_actions),
        ).to(device)

        # Continuous action head (continuous control)
        self.continuous_head = nn.Sequential(
            nn.Linear(input_dim, continuous_action_dim),
            nn.Tanh(),  # Bounded ∈ [-1, 1]
        ).to(device)

        # Digital tool head (Composio EFFECTORS - Gmail, Slack, etc.)
        self.digital_head = nn.Sequential(
            nn.Linear(input_dim, num_digital_tools),
        ).to(device)

        # SmartHome action head (physical EFFECTORS - lights, shades, etc.)
        self.smarthome_head = nn.Sequential(
            nn.Linear(input_dim, num_smarthome_actions),
        ).to(device)

        # Meta action head (control flow - observe, wait, delegate, etc.)
        self.meta_head = nn.Sequential(
            nn.Linear(input_dim, num_meta_actions),
        ).to(device)

        # Generation head (Forge colony - all AI generation EFFECTORS)
        # Covers: Music, Image, Video, 3D, Audio generation
        self.generation_head = nn.Sequential(
            nn.Linear(input_dim, num_generation_actions),
        ).to(device)

        # Action uncertainty head (epistemic confidence)
        self.uncertainty_head = nn.Sequential(
            nn.Linear(input_dim, 1),
            nn.Sigmoid(),  # ∈ [0, 1]
        ).to(device)

        # Speech parameters (for TTS integration)
        self.speech_head = nn.Sequential(
            nn.Linear(input_dim, 64),  # Speech embedding for voice synthesis
        ).to(device)

        logger.info(
            f"✅ MotorDecoder: discrete={num_discrete_actions}, "
            f"digital={num_digital_tools}, smarthome={num_smarthome_actions}, "
            f"meta={num_meta_actions}, generation={num_generation_actions}"
        )

    def forward(
        self,
        manifold_state: torch.Tensor,  # [B, N, dim] or [B, dim]
    ) -> dict[str, torch.Tensor]:
        """Decode motor commands from manifold state.

        Args:
            manifold_state: [B, N, dim] or [B, dim] predicted state

        Returns:
            Dictionary with all action head outputs:
            - discrete_actions: [B, num_discrete] robot action logits
            - continuous_actions: [B, 7] continuous control ∈ [-1, 1]
            - digital_tools: [B, num_digital] Composio effector logits
            - smarthome_actions: [B, num_smarthome] SmartHome effector logits
            - generation_actions: [B, num_generation] AI generation logits
            - action_uncertainty: [B, 1] confidence ∈ [0, 1]
            - speech_params: [B, 64] TTS embedding
        """
        # Move input to decoder's device
        manifold_state = manifold_state.to(self.device)

        # Pool over sequence dimension if present
        if manifold_state.dim() == 3:
            pooled = manifold_state.mean(dim=1)  # [B, dim]
        else:
            pooled = manifold_state  # [B, dim]

        # Extract features
        features = self.feature_extractor(pooled)  # [B, dim]

        # Decode to all action types
        discrete = self.discrete_head(features)  # [B, num_discrete]
        continuous = self.continuous_head(features)  # [B, continuous_dim]
        digital = self.digital_head(features)  # [B, num_digital]
        smarthome = self.smarthome_head(features)  # [B, num_smarthome]
        meta = self.meta_head(features)  # [B, num_meta]
        generation = self.generation_head(features)  # [B, num_generation]
        uncertainty = self.uncertainty_head(features)  # [B, 1]
        speech = self.speech_head(features)  # [B, 64]

        return {
            "discrete_actions": discrete,
            "continuous_actions": continuous,
            "digital_tools": digital,
            "smarthome_actions": smarthome,
            "meta_actions": meta,
            "generation_actions": generation,
            "action_uncertainty": uncertainty,
            "speech_params": speech,
        }

    def decode_digital_action(
        self,
        logits: torch.Tensor,
    ) -> dict[str, Any]:
        """Decode digital tool logits to Composio action + confidence.

        Args:
            logits: [B, num_digital] logits

        Returns:
            Dictionary with selected action and confidence
        """
        return self.decode_discrete_action(logits, DIGITAL_ACTIONS)

    def decode_smarthome_action(
        self,
        logits: torch.Tensor,
    ) -> dict[str, Any]:
        """Decode SmartHome action logits to device command + confidence.

        Args:
            logits: [B, num_smarthome] logits

        Returns:
            Dictionary with selected action and confidence
        """
        return self.decode_discrete_action(logits, SMARTHOME_ACTIONS)

    def decode_meta_action(
        self,
        logits: torch.Tensor,
    ) -> dict[str, Any]:
        """Decode meta action logits to control flow command + confidence.

        Args:
            logits: [B, num_meta] logits

        Returns:
            Dictionary with selected action and confidence
        """
        return self.decode_discrete_action(logits, META_ACTIONS)

    def decode_generation_action(
        self,
        logits: torch.Tensor,
    ) -> dict[str, Any]:
        """Decode generation action logits to AI generation command + confidence.

        Covers: Music, Image, Video, 3D, Audio generation.

        Args:
            logits: [B, num_generation] logits

        Returns:
            Dictionary with selected action and confidence
        """
        return self.decode_discrete_action(logits, GENERATION_ACTIONS)

    def get_best_action_across_heads(
        self,
        outputs: dict[str, torch.Tensor],
    ) -> dict[str, Any]:
        """Get the best action across all heads by comparing confidences.

        Args:
            outputs: Dict from forward() with all action logits

        Returns:
            Dictionary with best action, head, and confidence
        """
        best: dict[str, Any] = {"action": None, "head": None, "confidence": 0.0}

        # Check each head
        for head_name, action_list in [
            ("digital", DIGITAL_ACTIONS),
            ("smarthome", SMARTHOME_ACTIONS),
            ("meta", META_ACTIONS),
            ("generation", GENERATION_ACTIONS),
        ]:
            key = f"{head_name}_tools" if head_name == "digital" else f"{head_name}_actions"
            if key not in outputs:
                continue

            logits = outputs[key]
            result = self.decode_discrete_action(logits, action_list)

            if result["confidence"] > best["confidence"]:
                best = {
                    "action": result["action"],
                    "head": head_name,
                    "confidence": result["confidence"],
                    "action_id": result["action_id"],
                }

        return best

    def decode_discrete_action(
        self,
        actions: torch.Tensor,
        action_names: list[str],
    ) -> dict[str, Any]:
        """Decode discrete action logits to action name + confidence.

        Args:
            actions: [B, num_actions] logits
            action_names: List of action names (len = num_actions)

        Returns:
            Dictionary with selected action and confidence
        """
        # Get highest scoring action
        # Clamp logits to avoid NaN in softmax
        actions_clamped = torch.clamp(actions, min=-10.0, max=10.0)
        probs = F.softmax(actions_clamped, dim=-1)

        # Handle NaN
        if torch.isnan(probs).any():
            probs = torch.ones_like(probs) / probs.shape[-1]  # Uniform dist

        best_action_idx = probs.argmax(dim=-1).item()
        confidence = probs[0, best_action_idx].item()  # type: ignore  # Dynamic index

        return {
            "action": (
                action_names[best_action_idx] if best_action_idx < len(action_names) else "unknown"  # type: ignore[index]
            ),  # Dynamic index
            "action_id": best_action_idx,
            "confidence": confidence,
            "all_probs": probs[0].tolist(),
        }

    def decode_continuous_action(
        self,
        actions: torch.Tensor,
        action_space: dict[str, Any],
    ) -> dict[str, float]:
        """Decode continuous actions to actual control values.

        Args:
            actions: [B, continuous_dim] ∈ [-1, 1]
            action_space: Dict with min/max for each dimension

        Returns:
            Dictionary mapping actuator name to value
        """
        # Scale from [-1, 1] to actual range
        scaled = {}

        for i, (name, bounds) in enumerate(action_space.items()):
            if i >= actions.shape[-1]:
                break

            value = actions[0, i].item()
            min_val, max_val = bounds["min"], bounds["max"]

            # Scale from [-1, 1] → [min, max]
            scaled_value = min_val + (value + 1) / 2 * (max_val - min_val)
            scaled[name] = scaled_value

        return scaled


# =============================================================================
# DISCRETE ROBOT ACTIONS (physical manipulation - future robotics)
# =============================================================================

DISCRETE_ACTIONS = [
    # Physical actions (for robotics integration)
    "grasp",
    "release",
    "move_forward",
    "move_backward",
    "turn_left",
    "turn_right",
    "reach_up",
    "reach_down",
    "reach_left",
    "reach_right",
    "push",
    "pull",
    "lift",
    "place",
    # Speech actions
    "speak",
    "listen",
    "acknowledge",
    "question",
]

# =============================================================================
# CONTINUOUS ACTION SPACE (control parameters)
# =============================================================================

CONTINUOUS_ACTION_SPACE = {
    "joint_1_velocity": {"min": -1.0, "max": 1.0},
    "joint_2_velocity": {"min": -1.0, "max": 1.0},
    "joint_3_velocity": {"min": -1.0, "max": 1.0},
    "gripper_force": {"min": 0.0, "max": 1.0},
    "movement_speed": {"min": 0.0, "max": 1.0},
    "head_pan": {"min": -180.0, "max": 180.0},
    "head_tilt": {"min": -90.0, "max": 90.0},
}

# Note: DIGITAL_ACTIONS, SMARTHOME_ACTIONS, and META_ACTIONS are imported
# from kagami.core.embodiment.action_space (source of truth)


# =============================================================================
# FACTORY & SINGLETON
# =============================================================================

_motor_decoder: MotorDecoder | None = None


def create_motor_decoder(
    input_dim: int = 256,
    device: str | None = None,
) -> MotorDecoder:
    """Factory function for motor decoder.

    Returns:
        MotorDecoder instance

    Example:
        >>> decoder = create_motor_decoder()
        >>> state = torch.randn(1, 16, 256)  # From Matryoshka
        >>> actions = decoder(state)
        >>>
        >>> # Decode digital (Composio) action
        >>> digital = decoder.decode_digital_action(actions["digital_tools"])
        >>> print(f"Digital: {digital['action']} ({digital['confidence']:.2f})")
        >>>
        >>> # Decode SmartHome action
        >>> sh = decoder.decode_smarthome_action(actions["smarthome_actions"])
        >>> print(f"SmartHome: {sh['action']} ({sh['confidence']:.2f})")
    """
    return MotorDecoder(
        input_dim=input_dim,
        device=device,
    )


def get_motor_decoder(device: str | None = None) -> MotorDecoder:
    """Get global MotorDecoder singleton instance.

    Args:
        device: Torch device (only used on first call)

    Returns:
        Global MotorDecoder instance
    """
    global _motor_decoder

    if _motor_decoder is None:
        _motor_decoder = create_motor_decoder(device=device)
        logger.info("✅ Global MotorDecoder created")

    return _motor_decoder


def reset_motor_decoder() -> None:
    """Reset global instance (for testing)."""
    global _motor_decoder
    _motor_decoder = None


__all__ = [
    "CONTINUOUS_ACTION_SPACE",
    "DIGITAL_ACTIONS",
    "DISCRETE_ACTIONS",
    "GENERATION_ACTIONS",
    "SMARTHOME_ACTIONS",
    "MotorDecoder",
    "create_motor_decoder",
    "get_motor_decoder",
    "reset_motor_decoder",
]
