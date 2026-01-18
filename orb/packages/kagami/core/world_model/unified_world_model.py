"""UnifiedWorldModel - Automatic KagamiWorldModel + OrganismRSSM Integration.

ARCHITECTURAL DESIGN (December 20, 2025):
=========================================
This module provides seamless integration between KagamiWorldModel and OrganismRSSM,
eliminating manual wiring and ensuring proper state synchronization.

Key Features:
- Automatic S7 phase extraction from world model CoreState
- Single forward() call handles both models
- Proper gradient flow for end-to-end training
- State management across both components
- Training/inference mode handling

Integration Pattern:
    observations [B, S, D] → KagamiWorldModel.encode()
                           → CoreState with s7_phase [B, S, 7]
                           → OrganismRSSM.step_all(s7_phase)
                           → Combined predictions (action, reward, value, continue)

Usage:
    >>> from kagami.core.world_model import UnifiedWorldModel
    >>> model = UnifiedWorldModel(config)
    >>> state = model.forward(observations, actions, training=True)
    >>> loss = model.compute_loss(state, targets)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn

from kagami.core.config.unified_config import (
    RSSMConfig as ColonyRSSMConfig,
)
from kagami.core.config.unified_config import (
    get_kagami_config,
)
from kagami.core.config.world_model_config import WorldModelConfig as KagamiWorldModelConfig

from .kagami_world_model import KagamiWorldModel
from .model_config import CoreState
from .rssm_core import OrganismRSSM

logger = logging.getLogger(__name__)


@dataclass
class UnifiedConfig:
    """Configuration for UnifiedWorldModel.

    Combines world model and RSSM configurations with sensible defaults.
    """

    # World model config
    bulk_dim: int = 512
    device: str = "cpu"
    dtype: str = "float32"  # String for serialization (matching WorldModelConfig)

    # RSSM config overrides
    rssm_action_dim: int = 8  # E8 lattice dimension
    rssm_colony_dim: int = 256
    rssm_stochastic_dim: int = 128
    rssm_num_colonies: int = 7

    # Training settings
    gradient_clip_norm: float = 10.0
    kl_weight: float = 0.1
    reconstruction_weight: float = 1.0

    # Additional world model settings
    num_heads: int = 4
    num_experts: int = 2
    moe_top_k: int = 1

    def to_world_model_config(self) -> KagamiWorldModelConfig:
        """Convert to KagamiWorldModelConfig."""
        return KagamiWorldModelConfig(
            bulk_dim=self.bulk_dim,
            device=self.device,
            dtype=self.dtype,  # String (matches WorldModelConfig)
            rssm_action_dim=self.rssm_action_dim,
            num_heads=self.num_heads,
            num_experts=self.num_experts,
            moe_top_k=self.moe_top_k,
        )

    def to_rssm_config(self) -> ColonyRSSMConfig:
        """Convert to ColonyRSSMConfig.

        NOTE: Creates a NEW config instance - does NOT mutate global config.
        """
        # Get base config and copy to avoid mutation
        base_config = get_kagami_config().world_model.rssm.model_copy()
        base_config.obs_dim = 7  # S7 phase
        base_config.action_dim = self.rssm_action_dim
        base_config.colony_dim = self.rssm_colony_dim
        base_config.stochastic_dim = self.rssm_stochastic_dim
        base_config.num_colonies = self.rssm_num_colonies
        return base_config


@dataclass
class UnifiedState:
    """Unified state combining world model and RSSM states.

    This data structure holds all relevant state from both the world model
    and RSSM, making it easy to pass around and compute losses.
    """

    # World model state
    core_state: CoreState

    # RSSM state tensors
    h_next: torch.Tensor  # [B, 7, H] deterministic state
    z_next: torch.Tensor  # [B, 7, Z] stochastic state
    a_next: torch.Tensor  # [B, 7, A] per-colony actions

    # RSSM predictions
    organism_action: torch.Tensor  # [B, A] mean action across colonies
    predicted_s7: torch.Tensor  # [B, S, 7] predicted S7 phase
    predicted_reward: torch.Tensor | None = None  # [B, 1] predicted reward
    predicted_value: torch.Tensor | None = None  # [B, 1] predicted value
    predicted_continue: torch.Tensor | None = None  # [B, 1] continue probability

    # World model reconstruction
    reconstructed: torch.Tensor | None = None  # [B, S, D] reconstructed observation

    # KL divergence (for loss)
    kl_loss: torch.Tensor | None = None  # [B,] KL divergence

    # Metrics from both models
    world_model_metrics: dict[str, Any] = field(default_factory=dict[str, Any])
    rssm_metrics: dict[str, Any] = field(default_factory=dict[str, Any])

    # Timestep tracking
    timestep: int = 0


class UnifiedWorldModel(nn.Module):
    """Unified world model integrating KagamiWorldModel + OrganismRSSM.

    This class provides a single entry point for world model operations,
    automatically handling the integration between the world model encoder
    and the RSSM dynamics model.

    Architecture Flow:
        1. Observations → KagamiWorldModel.encode() → CoreState
        2. Extract s7_phase from CoreState
        3. Feed s7_phase + actions → OrganismRSSM.step_all()
        4. Return unified state with all predictions

    The model handles:
    - Automatic S7 extraction and feeding
    - State synchronization between components
    - Gradient flow for end-to-end training
    - Action conditioning
    - Reward/value prediction via RSSM heads
    """

    def __init__(
        self,
        config: UnifiedConfig | KagamiWorldModelConfig | None = None,
        rssm_config: ColonyRSSMConfig | None = None,
    ):
        """Initialize unified world model.

        Args:
            config: Unified config, world model config, or None (uses defaults)
            rssm_config: Optional RSSM config override
        """
        super().__init__()

        # Handle different config types
        if config is None:
            config = UnifiedConfig()

        if isinstance(config, UnifiedConfig):
            self.config = config
            wm_config = config.to_world_model_config()
            if rssm_config is None:
                rssm_config = config.to_rssm_config()
        elif isinstance(config, KagamiWorldModelConfig):
            # Convert from world model config
            self.config = UnifiedConfig(
                bulk_dim=config.bulk_dim,
                device=config.device,
                dtype=config.dtype,
                rssm_action_dim=config.rssm_action_dim,
                num_heads=config.num_heads,
                num_experts=config.num_experts,
                moe_top_k=config.moe_top_k,
            )
            wm_config = config
            if rssm_config is None:
                rssm_config = self.config.to_rssm_config()
        else:
            raise TypeError(f"Invalid config type: {type(config)}")

        # Initialize world model
        self.world_model = KagamiWorldModel(wm_config)

        # Initialize RSSM
        self.rssm = OrganismRSSM(rssm_config)

        # Store configs
        self.wm_config = wm_config
        self.rssm_config = rssm_config

        # Internal timestep tracking
        self._timestep: int = 0

        logger.info(
            f"✅ UnifiedWorldModel initialized: bulk_dim={wm_config.bulk_dim}, "
            f"rssm_colonies={rssm_config.num_colonies}, device={wm_config.device}"
        )

    def forward(
        self,
        observations: torch.Tensor,
        actions: torch.Tensor | None = None,
        training: bool = True,
    ) -> UnifiedState:
        """Unified forward pass through world model and RSSM.

        This is the main entry point for the unified model. It handles:
        1. Encoding observations through world model
        2. Extracting S7 phase from core state
        3. Feeding S7 to RSSM for dynamics prediction
        4. Collecting all predictions and metrics

        Args:
            observations: Input observations [B, S, D] or [B, D]
            actions: Optional previous actions [B, A] or [B, S, A]
            training: Whether in training mode (affects sampling)

        Returns:
            UnifiedState with all predictions and state information

        Shape conventions:
            B = batch size
            S = sequence length
            D = observation dimension (typically bulk_dim)
            A = action dimension (typically 8 for E8)
            H = deterministic state dimension (rssm_colony_dim)
            Z = stochastic state dimension (rssm_stochastic_dim)
        """
        # Ensure observations are 3D [B, S, D]
        if observations.dim() == 2:
            observations = observations.unsqueeze(1)  # [B, D] -> [B, 1, D]
        elif observations.dim() != 3:
            raise ValueError(
                f"observations must be [B, S, D] or [B, D], got shape {observations.shape}"
            )

        _B, S, _D = observations.shape

        # Step 1: Encode through world model
        # Process each timestep in sequence to extract S7 phases and E8 codes
        s7_phases_list: list[torch.Tensor] = []
        e8_codes_list: list[torch.Tensor] = []
        core_states: list[CoreState] = []
        wm_metrics_list: list[dict[str, Any]] = []

        for t in range(S):
            obs_t = observations[:, t : t + 1, :]  # [B, 1, D]
            core_state, wm_metrics = self.world_model.encode(obs_t)
            core_states.append(core_state)
            wm_metrics_list.append(wm_metrics)

            # Extract S7 phase
            if core_state.s7_phase is None:
                raise ValueError(f"World model did not produce s7_phase at timestep {t}")
            s7_phase_t = core_state.s7_phase  # [B, 1, 7]
            s7_phases_list.append(s7_phase_t.squeeze(1))  # [B, 7]

            # Extract E8 code
            if core_state.e8_code is None:
                raise ValueError(f"World model did not produce e8_code at timestep {t}")
            e8_code_t = core_state.e8_code  # [B, 1, 8]
            e8_codes_list.append(e8_code_t.squeeze(1))  # [B, 8]

        # Stack S7 phases and E8 codes across sequence
        s7_phases = torch.stack(s7_phases_list, dim=1)  # [B, S, 7]
        e8_codes = torch.stack(e8_codes_list, dim=1)  # [B, S, 8]

        # Use last core state as representative
        final_core_state = core_states[-1]

        # Aggregate world model metrics
        wm_metrics_agg: dict[str, Any] = {}
        if wm_metrics_list:
            # Average numeric metrics
            for key in wm_metrics_list[0]:
                values = [m.get(key) for m in wm_metrics_list]
                if all(isinstance(v, int | float) for v in values):
                    wm_metrics_agg[key] = sum(values) / len(values)  # type: ignore[arg-type]

        # Step 2: Process through RSSM for each timestep
        # RSSM maintains internal state, so we call step_all() sequentially
        rssm_outputs: list[dict[str, Any]] = []
        h_list: list[torch.Tensor] = []
        z_list: list[torch.Tensor] = []
        a_list: list[torch.Tensor] = []

        # Extract per-timestep actions if provided
        action_prev: torch.Tensor | None = None
        for t in range(S):
            if actions is not None:
                if actions.dim() == 2:
                    # [B, A] - same action for all timesteps
                    action_prev = actions
                elif actions.dim() == 3:
                    # [B, S, A] - different action per timestep
                    action_prev = actions[:, t, :] if t > 0 else None
                else:
                    raise ValueError(f"actions must be [B, A] or [B, S, A], got {actions.shape}")

            # Feed S7 phase and E8 code at timestep t
            s7_t = s7_phases[:, t, :]  # [B, 7]
            e8_t = e8_codes[:, t, :]  # [B, 8]
            rssm_out = self.rssm.step_all(
                e8_code=e8_t,  # E8 lattice coordinates (content)
                s7_phase=s7_t,  # S7 phase for colony routing
                action_prev=action_prev,
                sample=training,  # Sample during training, argmax during inference
            )
            rssm_outputs.append(rssm_out)
            h_list.append(rssm_out["h_next"])
            z_list.append(rssm_out["z_next"])
            a_list.append(rssm_out["colony_actions"])

        # Get final RSSM output
        final_rssm_out = rssm_outputs[-1]

        # Aggregate RSSM metrics
        rssm_metrics: dict[str, Any] = {
            "kl_loss": final_rssm_out.get("kl_loss", 0.0),
            "timestep": final_rssm_out.get("timestep", self._timestep),
        }

        # Extract predictions from final timestep
        organism_action = final_rssm_out["organism_action"]  # [B, A] or [A]
        if organism_action.dim() == 1:
            organism_action = organism_action.unsqueeze(0)  # [A] -> [B, A]

        # Stack states across sequence
        h_next = h_list[-1]  # [B, 7, H]
        z_next = z_list[-1]  # [B, 7, Z]
        a_next = a_list[-1]  # [B, 7, A]

        # Get S7 prediction from RSSM (for consistency loss)
        predicted_s7 = final_rssm_out.get("s7_pred", s7_phases)  # [B, S, 7] or [B, 7]
        if predicted_s7.dim() == 2:
            predicted_s7 = predicted_s7.unsqueeze(1)  # [B, 7] -> [B, 1, 7]

        # Get RL predictions if available
        predicted_reward = final_rssm_out.get("predicted_reward")  # [B, 1] or None
        predicted_value = final_rssm_out.get("predicted_value")  # [B, 1] or None
        predicted_continue = final_rssm_out.get("predicted_continue")  # [B, 1] or None

        # KL loss from RSSM
        kl_loss = final_rssm_out.get("kl_loss")  # [B,] or scalar
        if kl_loss is not None and not isinstance(kl_loss, torch.Tensor):
            kl_loss = torch.tensor(kl_loss, device=observations.device)

        # Optional: decode back through world model for reconstruction loss
        reconstructed: torch.Tensor | None = None
        if final_core_state.e8_code is not None:
            try:
                reconstructed, _ = self.world_model.decode(final_core_state)
            except Exception as e:
                logger.debug(f"World model decode failed: {e}")

        # Increment timestep
        self._timestep += 1

        return UnifiedState(
            core_state=final_core_state,
            h_next=h_next,
            z_next=z_next,
            a_next=a_next,
            organism_action=organism_action,
            predicted_s7=predicted_s7,
            predicted_reward=predicted_reward,
            predicted_value=predicted_value,
            predicted_continue=predicted_continue,
            reconstructed=reconstructed,
            kl_loss=kl_loss,
            world_model_metrics=wm_metrics_agg,
            rssm_metrics=rssm_metrics,
            timestep=self._timestep,
        )

    def compute_loss(
        self,
        state: UnifiedState,
        targets: dict[str, torch.Tensor],
        weights: dict[str, float] | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Compute unified loss for training.

        Combines losses from:
        - RSSM KL divergence
        - Reconstruction loss (world model)
        - S7 consistency loss (RSSM prediction vs world model)
        - RL losses (reward, value, continue) if available

        Args:
            state: UnifiedState from forward pass
            targets: Dictionary of target tensors
            weights: Optional loss weights (uses config defaults if None)

        Returns:
            (total_loss, loss_dict) where loss_dict contains individual losses
        """
        if weights is None:
            weights = {
                "kl": self.config.kl_weight,
                "reconstruction": self.config.reconstruction_weight,
                "s7_consistency": 0.1,
                "reward": 1.0,
                "value": 0.5,
                "continue": 0.1,
            }

        losses: dict[str, torch.Tensor] = {}
        device = state.organism_action.device

        # 1. KL divergence loss (from RSSM)
        if state.kl_loss is not None:
            kl = state.kl_loss
            if not isinstance(kl, torch.Tensor):
                kl = torch.tensor(kl, device=device)
            losses["kl"] = kl.mean() * weights["kl"]

        # 2. Reconstruction loss (world model)
        if state.reconstructed is not None and "observations" in targets:
            target_obs = targets["observations"]
            if target_obs.shape != state.reconstructed.shape:
                # Try to match shapes
                if target_obs.dim() == 2:
                    target_obs = target_obs.unsqueeze(1)
                if target_obs.shape[1] != state.reconstructed.shape[1]:
                    # Repeat to match sequence length
                    target_obs = target_obs.repeat(1, state.reconstructed.shape[1], 1)
            recon_loss = torch.nn.functional.mse_loss(state.reconstructed, target_obs)
            losses["reconstruction"] = recon_loss * weights["reconstruction"]

        # 3. S7 consistency loss (RSSM prediction should match world model S7)
        if state.predicted_s7 is not None and state.core_state.s7_phase is not None:
            target_s7 = state.core_state.s7_phase
            # Match shapes
            if state.predicted_s7.shape != target_s7.shape:
                if state.predicted_s7.shape[1] != target_s7.shape[1]:
                    # Average over sequence dimension
                    target_s7 = target_s7.mean(dim=1, keepdim=True)
            s7_loss = torch.nn.functional.mse_loss(state.predicted_s7, target_s7)
            losses["s7_consistency"] = s7_loss * weights["s7_consistency"]

        # 4. RL losses (if targets provided)
        if state.predicted_reward is not None and "rewards" in targets:
            target_reward = targets["rewards"]
            if target_reward.dim() == 1:
                target_reward = target_reward.unsqueeze(-1)
            reward_loss = torch.nn.functional.mse_loss(state.predicted_reward, target_reward)
            losses["reward"] = reward_loss * weights["reward"]

        if state.predicted_value is not None and "values" in targets:
            target_value = targets["values"]
            if target_value.dim() == 1:
                target_value = target_value.unsqueeze(-1)
            value_loss = torch.nn.functional.mse_loss(state.predicted_value, target_value)
            losses["value"] = value_loss * weights["value"]

        if state.predicted_continue is not None and "continues" in targets:
            target_continue = targets["continues"]
            if target_continue.dim() == 1:
                target_continue = target_continue.unsqueeze(-1)
            continue_loss = torch.nn.functional.binary_cross_entropy_with_logits(
                state.predicted_continue, target_continue
            )
            losses["continue"] = continue_loss * weights["continue"]

        # Total loss
        total_loss = sum(losses.values()) if losses else torch.tensor(0.0, device=device)

        # Detach losses for logging
        loss_dict = {
            k: v.detach().item() if isinstance(v, torch.Tensor) else v for k, v in losses.items()
        }
        loss_dict["total"] = (
            total_loss.detach().item() if isinstance(total_loss, torch.Tensor) else total_loss
        )

        return total_loss, loss_dict  # type: ignore[return-value]

    def reset_rssm_state(self, batch_size: int = 1) -> None:
        """Reset RSSM internal state.

        Args:
            batch_size: Batch size for state initialization
        """
        self.rssm.initialize_all(batch_size=batch_size, device=self.wm_config.device)
        self._timestep = 0
        logger.debug(f"✅ RSSM state reset for batch_size={batch_size}")

    def get_state_dict_unified(self) -> dict[str, Any]:
        """Get unified state dictionary for checkpointing.

        Returns:
            Dictionary with both world model and RSSM state dicts
        """
        return {
            "world_model": self.world_model.state_dict(),
            "rssm": self.rssm.state_dict(),
            "timestep": self._timestep,
            "config": self.config,
        }

    def load_state_dict_unified(self, state_dict: dict[str, Any]) -> None:
        """Load unified state dictionary from checkpoint.

        Args:
            state_dict: Dictionary from get_state_dict_unified()
        """
        self.world_model.load_state_dict(state_dict["world_model"])
        self.rssm.load_state_dict(state_dict["rssm"])
        self._timestep = state_dict.get("timestep", 0)
        logger.info(f"✅ Loaded unified checkpoint at timestep {self._timestep}")


def create_unified_world_model(  # type: ignore[no-untyped-def]
    bulk_dim: int = 512,
    device: str = "cpu",
    **kwargs,
) -> UnifiedWorldModel:
    """Factory function for creating UnifiedWorldModel.

    Args:
        bulk_dim: World model bulk dimension
        device: Device for model placement
        **kwargs: Additional config overrides

    Returns:
        Initialized UnifiedWorldModel

    Example:
        >>> model = create_unified_world_model(bulk_dim=256, device="cuda")
        >>> state = model(observations, actions)
        >>> loss, metrics = model.compute_loss(state, targets)
    """
    config = UnifiedConfig(
        bulk_dim=bulk_dim,
        device=device,
        **kwargs,
    )
    return UnifiedWorldModel(config)


__all__ = [
    "UnifiedConfig",
    "UnifiedState",
    "UnifiedWorldModel",
    "create_unified_world_model",
]
